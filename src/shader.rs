//! `pz.shader`: a widget painted by a WGSL fragment function, like a Shadertoy.
//!
//! Python gives the body of `fn shade(uv, px, size, time) -> vec4<f32>`, named uniforms and
//! named textures; this module wraps it in a full shader, checks it with naga (so mistakes
//! raise in Python), and draws it with a wgpu pipeline per distinct source. Renderers without
//! a GPU (the tiny-skia fallback, CI screenshots) draw the `fallback` background instead.
//!
//! Nothing here knows about any particular shader: `pyzed.shading` builds its node graphs
//! into the same WGSL in Python.

use std::collections::{HashMap, HashSet};
use std::hash::{Hash, Hasher};
use std::sync::{Arc, LazyLock, Mutex};
use std::time::Instant;

use iced::widget::shader::{self as iced_shader, Viewport};
use iced::widget::{container, shader as shader_widget};
use iced::{Background, Element, Length, Rectangle, mouse};
use iced_wgpu::wgpu;
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::app::Message;
use crate::style::{self, Any};
use crate::widget::{Kind, Widget, new};

/// Uniform slots a shader can name (each one a `vec4`).
const SLOTS: usize = 32;
/// Textures a shader can name.
const MAX_TEXTURES: usize = 8;

/// When the process started: every shader's `time` counts from here, so they stay in sync.
static START: LazyLock<Instant> = LazyLock::new(Instant::now);

const HEADER: &str = r#"
struct PyzedGlobals {
    rect: vec4<f32>,
    info: vec4<f32>,
    values: array<vec4<f32>, 32>,
}

@group(0) @binding(0) var<uniform> pyzed: PyzedGlobals;

// Where the pointer is, from 0 to 1 across the widget (negative when it is outside).
fn mouse() -> vec2<f32> {
    return pyzed.info.zw;
}
"#;

const FOOTER: &str = r#"
@vertex
fn pyzed_vs(@builtin(vertex_index) index: u32) -> @builtin(position) vec4<f32> {
    let x = f32(i32(index & 1u) * 4 - 1);
    let y = f32(i32(index >> 1u) * 4 - 1);
    return vec4<f32>(x, y, 0.0, 1.0);
}

@fragment
fn pyzed_fs(@builtin(position) frag: vec4<f32>) -> @location(0) vec4<f32> {
    let scale = pyzed.info.y;
    let size = pyzed.rect.zw / scale;
    let px = (frag.xy - pyzed.rect.xy) / scale;
    var color = clamp(shade(px / size, px, size, pyzed.info.x), vec4<f32>(0.0), vec4<f32>(1.0));
    // PYZED_OUTPUT
    return color;
}
"#;

/// What a named uniform holds, and so what its accessor returns.
#[derive(Clone, Copy)]
enum Slot {
    Float,
    Vec2,
    Vec3,
    Vec4,
}

/// An image a shader samples, decoded to RGBA once (cached by file and modification time).
#[derive(Debug)]
pub struct Texture {
    key: u64,
    width: u32,
    height: u32,
    pixels: bytes::Bytes,
}

static TEXTURES: LazyLock<Mutex<HashMap<u64, Arc<Texture>>>> = LazyLock::new(Default::default);
/// Sources naga already accepted, so a view that builds the same shader every frame checks it once.
static VALID: LazyLock<Mutex<HashSet<u64>>> = LazyLock::new(Default::default);

fn white() -> Arc<Texture> {
    Arc::new(Texture {
        key: 0,
        width: 1,
        height: 1,
        pixels: bytes::Bytes::from_static(&[255, 255, 255, 255]),
    })
}

/// A texture from a path, encoded image bytes or `None`/`""` (white).
fn load_texture(name: &str, source: &Bound<'_, PyAny>) -> PyResult<Arc<Texture>> {
    if source.is_none() || source.extract::<String>().is_ok_and(|s| s.is_empty()) {
        return Ok(white());
    }
    let image = crate::extra::image_source(source, None)?;
    let key = match &image {
        crate::extra::ImageSource::Path(p) => {
            let modified = std::fs::metadata(p)
                .and_then(|m| m.modified())
                .ok()
                .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                .map(|d| d.as_nanos())
                .unwrap_or(0);
            hash_str(&format!("{p}\u{0}{modified}"))
        }
        crate::extra::ImageSource::Bytes(b) => {
            let mut h = std::collections::hash_map::DefaultHasher::new();
            b.hash(&mut h);
            h.finish()
        }
        crate::extra::ImageSource::Rgba { pixels, .. } => {
            let mut h = std::collections::hash_map::DefaultHasher::new();
            pixels.hash(&mut h);
            h.finish()
        }
    };
    if let Some(found) = TEXTURES.lock().expect("shader textures").get(&key) {
        return Ok(found.clone());
    }
    let decoded = match &image {
        crate::extra::ImageSource::Path(p) => ::image::open(p).map(|i| i.to_rgba8()),
        crate::extra::ImageSource::Bytes(b) => ::image::load_from_memory(b).map(|i| i.to_rgba8()),
        crate::extra::ImageSource::Rgba { .. } => unreachable!("no size was given"),
    }
    .map_err(|e| PyValueError::new_err(format!("can't read the texture {name:?}: {e}")))?;
    let (width, height) = decoded.dimensions();
    let texture = Arc::new(Texture {
        key,
        width,
        height,
        pixels: bytes::Bytes::from(decoded.into_raw()),
    });
    let mut cache = TEXTURES.lock().expect("shader textures");
    if cache.len() > 64 {
        cache.clear();
    }
    cache.insert(key, texture.clone());
    Ok(texture)
}

pub struct ShaderProps {
    source: Arc<str>,
    key: u64,
    textures: Vec<Arc<Texture>>,
    values: [[f32; 4]; SLOTS],
    width: Length,
    height: Length,
    animate: bool,
    uses_mouse: bool,
    time: Option<f32>,
    fallback: Option<Background>,
}

fn hash_str(s: &str) -> u64 {
    let mut h = std::collections::hash_map::DefaultHasher::new();
    s.hash(&mut h);
    h.finish()
}

/// The full WGSL module for the user's code, uniforms and textures.
fn compose(code: &str, slots: &[(String, Slot)], textures: &[String]) -> String {
    let mut out = String::from(HEADER);
    for (i, name) in textures.iter().enumerate() {
        let (t, s) = (1 + 2 * i, 2 + 2 * i);
        out.push_str(&format!(
            "@group(0) @binding({t}) var pyzed_texture{i}: texture_2d<f32>;\n\
             @group(0) @binding({s}) var pyzed_sampler{i}: sampler;\n\
             fn {name}(uv: vec2<f32>) -> vec4<f32> {{\n    \
             return textureSampleLevel(pyzed_texture{i}, pyzed_sampler{i}, uv, 0.0);\n}}\n"
        ));
    }
    for (i, (name, slot)) in slots.iter().enumerate() {
        let (ty, swizzle) = match slot {
            Slot::Float => ("f32", "x"),
            Slot::Vec2 => ("vec2<f32>", "xy"),
            Slot::Vec3 => ("vec3<f32>", "xyz"),
            Slot::Vec4 => ("vec4<f32>", "xyzw"),
        };
        out.push_str(&format!(
            "fn {name}() -> {ty} {{\n    return pyzed.values[{i}].{swizzle};\n}}\n"
        ));
    }
    out.push_str("\n// --- your code ---\n");
    out.push_str(code);
    out.push_str("\n// --- end of your code ---\n");
    out.push_str(FOOTER);
    out
}

/// Parses and validates `source`; the error reads like a compiler's, with the line.
fn check(source: &str) -> Result<(), String> {
    let key = hash_str(source);
    if VALID.lock().expect("shader cache").contains(&key) {
        return Ok(());
    }
    let module = naga::front::wgsl::parse_str(source).map_err(|e| e.emit_to_string(source))?;
    let mut validator = naga::valid::Validator::new(
        naga::valid::ValidationFlags::all(),
        naga::valid::Capabilities::empty(),
    );
    validator
        .validate(&module)
        .map_err(|e| e.emit_to_string(source))?;
    let mut valid = VALID.lock().expect("shader cache");
    if valid.len() > 4096 {
        valid.clear();
    }
    valid.insert(key);
    Ok(())
}

fn identifier(name: &str) -> bool {
    let mut chars = name.chars();
    chars
        .next()
        .is_some_and(|c| c.is_ascii_alphabetic() || c == '_')
        && chars.all(|c| c.is_ascii_alphanumeric() || c == '_')
}

/// A uniform value: a number, 2 to 4 numbers or a color.
fn value(value: &Bound<'_, PyAny>) -> PyResult<(Slot, [f32; 4])> {
    if let Ok(v) = value.extract::<f32>() {
        return Ok((Slot::Float, [v, 0.0, 0.0, 0.0]));
    }
    if let Ok(v) = value.extract::<Vec<f32>>() {
        let slot = match v.len() {
            2 => Slot::Vec2,
            3 => Slot::Vec3,
            4 => Slot::Vec4,
            _ => {
                return Err(PyValueError::new_err(
                    "a shader uniform takes 1 to 4 numbers",
                ));
            }
        };
        let mut out = [0.0; 4];
        out[..v.len()].copy_from_slice(&v);
        return Ok((slot, out));
    }
    let color = style::color(value).map_err(|_| {
        PyTypeError::new_err("a shader uniform is a number, a tuple of 2 to 4 numbers or a color")
    })?;
    Ok((Slot::Vec4, [color.r, color.g, color.b, color.a]))
}

/// The uniforms and textures of a shader, checked: `(slots, values, texture names, textures)`.
type Inputs = (Vec<(String, Slot)>, [[f32; 4]; SLOTS], Vec<String>, Vec<Arc<Texture>>);

fn inputs(uniforms: Option<&Bound<'_, PyDict>>, textures: Option<&Bound<'_, PyDict>>) -> PyResult<Inputs> {
    let mut slots = Vec::new();
    let mut values = [[0.0; 4]; SLOTS];
    let mut names: HashSet<String> = HashSet::new();
    if let Some(uniforms) = uniforms {
        for (i, (name, v)) in uniforms.iter().enumerate() {
            let name: String = name.extract()?;
            if !identifier(&name) {
                return Err(PyValueError::new_err(format!(
                    "{name:?} is not a valid uniform name (letters, digits and _)"
                )));
            }
            if i >= SLOTS {
                return Err(PyValueError::new_err(format!(
                    "a shader takes at most {SLOTS} uniforms"
                )));
            }
            let (slot, v) = value(&v)?;
            names.insert(name.clone());
            slots.push((name, slot));
            values[i] = v;
        }
    }
    let mut texture_names = Vec::new();
    let mut loaded = Vec::new();
    if let Some(textures) = textures {
        for (i, (name, source)) in textures.iter().enumerate() {
            let name: String = name.extract()?;
            if !identifier(&name) || names.contains(&name) {
                return Err(PyValueError::new_err(format!(
                    "{name:?} is not a valid texture name (letters, digits and _, not a uniform's)"
                )));
            }
            if i >= MAX_TEXTURES {
                return Err(PyValueError::new_err(format!(
                    "a shader takes at most {MAX_TEXTURES} textures"
                )));
            }
            loaded.push(load_texture(&name, &source)?);
            texture_names.push(name);
        }
    }
    Ok((slots, values, texture_names, loaded))
}

/// A widget painted on the GPU by your WGSL function
/// `fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32>`, which
/// returns the color (RGBA, 0 to 1) of every pixel. `uv` goes from 0 to 1 across the widget,
/// `px` and `size` are in pixels, `time` counts seconds and `mouse()` gives the pointer as a
/// `uv`. Each entry of `uniforms` (a number, 2 to 4 numbers or a color; up to 32) becomes a
/// function of the same name: `{"speed": 2}` -> `speed()`. Each entry of `textures` (an image
/// path or encoded bytes; up to 8) becomes a function that samples it: `{"albedo": "rock.png"}`
/// -> `albedo(uv)` returns its color at `uv` (the image repeats outside 0..1). Without a GPU
/// (and in screenshots taken without one) the widget shows `fallback`, a color or gradient.
/// Raises `ValueError` with the compiler's message when the code is not valid WGSL.
#[pyfunction]
#[pyo3(signature = (code, *, uniforms=None, textures=None, width=None, height=None, animate=true, time=None, fallback=None))]
#[allow(clippy::too_many_arguments)]
pub fn shader(
    py: Python<'_>,
    code: &str,
    uniforms: Option<&Bound<'_, PyDict>>,
    textures: Option<&Bound<'_, PyDict>>,
    width: Any<'_>,
    height: Any<'_>,
    animate: bool,
    time: Option<f32>,
    fallback: Any<'_>,
) -> PyResult<Py<Widget>> {
    let (slots, values, texture_names, textures) = inputs(uniforms, textures)?;
    if !code.contains("fn shade") {
        return Err(PyValueError::new_err(
            "invalid shader: define fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32>",
        ));
    }
    let source = compose(code, &slots, &texture_names);
    check(&source).map_err(|e| PyValueError::new_err(format!("invalid shader:\n{e}")))?;
    let fallback = match fallback.filter(|v| !v.is_none()) {
        None => None,
        Some(v) => {
            // A `pz.Gradient`, an `(angle, stops)` tuple or a color.
            let v = if v.hasattr("to_value")? {
                v.call_method0("to_value")?
            } else {
                v
            };
            if v.is_instance_of::<pyo3::types::PyTuple>() {
                style::gradient(&Some(v))?.map(Background::Gradient)
            } else {
                Some(Background::Color(style::color(&v)?))
            }
        }
    };
    new(
        py,
        Kind::Shader(Box::new(ShaderProps {
            key: hash_str(&source),
            source: source.into(),
            textures,
            values,
            width: style::opt_length(&width)?.unwrap_or(Length::Fill),
            height: style::opt_length(&height)?.unwrap_or(Length::Fill),
            animate,
            uses_mouse: code.contains("mouse()"),
            time,
            fallback,
        })),
    )
}

/// The whole WGSL module `pz.shader` builds around `code` (with the uniforms' and textures'
/// functions), without checking it: to map a compiler error's line back to your code.
#[pyfunction]
#[pyo3(signature = (code, *, uniforms=None, textures=None))]
pub fn shader_module(
    code: &str,
    uniforms: Option<&Bound<'_, PyDict>>,
    textures: Option<&Bound<'_, PyDict>>,
) -> PyResult<String> {
    let mut slots = Vec::new();
    if let Some(uniforms) = uniforms {
        for (name, v) in uniforms.iter() {
            slots.push((name.extract::<String>()?, value(&v)?.0));
        }
    }
    let mut names = Vec::new();
    if let Some(textures) = textures {
        for name in textures.keys() {
            names.push(name.extract::<String>()?);
        }
    }
    Ok(compose(code, &slots, &names))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(shader, m)?)?;
    m.add_function(wrap_pyfunction!(shader_module, m)?)?;
    Ok(())
}

pub fn render(props: &ShaderProps) -> Element<'static, Message> {
    let program = Program {
        source: props.source.clone(),
        key: props.key,
        textures: props.textures.clone(),
        values: props.values,
        animate: props.animate,
        uses_mouse: props.uses_mouse,
        time: props.time,
    };
    let fallback = props.fallback;
    container(
        shader_widget(program)
            .width(Length::Fill)
            .height(Length::Fill),
    )
    .width(props.width)
    .height(props.height)
    .style(move |_| container::Style {
        background: fallback,
        ..Default::default()
    })
    .into()
}

struct Program {
    source: Arc<str>,
    key: u64,
    textures: Vec<Arc<Texture>>,
    values: [[f32; 4]; SLOTS],
    animate: bool,
    uses_mouse: bool,
    time: Option<f32>,
}

impl iced_shader::Program<Message> for Program {
    type State = ();
    type Primitive = Primitive;

    fn update(
        &self,
        _state: &mut (),
        event: &iced::Event,
        _bounds: Rectangle,
        _cursor: mouse::Cursor,
    ) -> Option<iced_shader::Action<Message>> {
        match event {
            iced::Event::Window(iced::window::Event::RedrawRequested(_))
                if self.animate && self.time.is_none() && !crate::animation::settled() =>
            {
                Some(iced_shader::Action::request_redraw())
            }
            iced::Event::Mouse(mouse::Event::CursorMoved { .. } | mouse::Event::CursorLeft)
                if self.uses_mouse =>
            {
                Some(iced_shader::Action::request_redraw())
            }
            _ => None,
        }
    }

    fn draw(&self, _state: &(), cursor: mouse::Cursor, bounds: Rectangle) -> Primitive {
        let time = match self.time {
            Some(t) => t,
            None if crate::animation::settled() => 0.0,
            None => START.elapsed().as_secs_f32(),
        };
        let mouse = cursor
            .position_in(bounds)
            .map(|p| [p.x / bounds.width.max(1.0), p.y / bounds.height.max(1.0)])
            .unwrap_or([-1.0, -1.0]);
        Primitive {
            source: self.source.clone(),
            key: self.key,
            textures: self.textures.clone(),
            values: self.values,
            time,
            mouse,
        }
    }
}

#[derive(Debug)]
pub struct Primitive {
    source: Arc<str>,
    key: u64,
    textures: Vec<Arc<Texture>>,
    values: [[f32; 4]; SLOTS],
    time: f32,
    mouse: [f32; 2],
}

impl Primitive {
    fn instance(&self, bounds: &Rectangle) -> u64 {
        let mut h = std::collections::hash_map::DefaultHasher::new();
        self.key.hash(&mut h);
        for t in &self.textures {
            t.key.hash(&mut h);
        }
        [bounds.x, bounds.y, bounds.width, bounds.height]
            .map(f32::to_bits)
            .hash(&mut h);
        h.finish()
    }
}

struct Instance {
    buffer: wgpu::Buffer,
    bind_group: wgpu::BindGroup,
    key: u64,
}

/// The bind group layout (uniforms, then a texture and a sampler per texture) for a number of textures.
struct Layout {
    bind_group: wgpu::BindGroupLayout,
    pipeline: wgpu::PipelineLayout,
}

pub struct Pipeline {
    format: wgpu::TextureFormat,
    layouts: HashMap<usize, Layout>,
    sampler: wgpu::Sampler,
    pipelines: HashMap<u64, wgpu::RenderPipeline>,
    instances: HashMap<u64, Instance>,
    textures: HashMap<u64, wgpu::TextureView>,
    used: HashSet<u64>,
    used_textures: HashSet<u64>,
    /// The instance each primitive drew last, so `draw` (which can't hash bounds) finds it.
    current: std::sync::Mutex<Vec<u64>>,
}

const UNIFORM_SIZE: u64 = (4 + 4 + 4 * SLOTS as u64) * 4;

fn layout(device: &wgpu::Device, textures: usize) -> Layout {
    let mut entries = vec![wgpu::BindGroupLayoutEntry {
        binding: 0,
        visibility: wgpu::ShaderStages::FRAGMENT,
        ty: wgpu::BindingType::Buffer {
            ty: wgpu::BufferBindingType::Uniform,
            has_dynamic_offset: false,
            min_binding_size: wgpu::BufferSize::new(UNIFORM_SIZE),
        },
        count: None,
    }];
    for i in 0..textures as u32 {
        entries.push(wgpu::BindGroupLayoutEntry {
            binding: 1 + 2 * i,
            visibility: wgpu::ShaderStages::FRAGMENT,
            ty: wgpu::BindingType::Texture {
                sample_type: wgpu::TextureSampleType::Float { filterable: true },
                view_dimension: wgpu::TextureViewDimension::D2,
                multisampled: false,
            },
            count: None,
        });
        entries.push(wgpu::BindGroupLayoutEntry {
            binding: 2 + 2 * i,
            visibility: wgpu::ShaderStages::FRAGMENT,
            ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
            count: None,
        });
    }
    let bind_group = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
        label: Some("pyzed shader"),
        entries: &entries,
    });
    let pipeline = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
        label: Some("pyzed shader"),
        bind_group_layouts: &[&bind_group],
        push_constant_ranges: &[],
    });
    Layout {
        bind_group,
        pipeline,
    }
}

impl iced_shader::Pipeline for Pipeline {
    fn new(device: &wgpu::Device, _queue: &wgpu::Queue, format: wgpu::TextureFormat) -> Self {
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("pyzed shader"),
            address_mode_u: wgpu::AddressMode::Repeat,
            address_mode_v: wgpu::AddressMode::Repeat,
            address_mode_w: wgpu::AddressMode::Repeat,
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            mipmap_filter: wgpu::FilterMode::Nearest,
            ..Default::default()
        });
        Self {
            format,
            layouts: HashMap::new(),
            sampler,
            pipelines: HashMap::new(),
            instances: HashMap::new(),
            textures: HashMap::new(),
            used: HashSet::new(),
            used_textures: HashSet::new(),
            current: std::sync::Mutex::new(Vec::new()),
        }
    }

    fn trim(&mut self) {
        let used = std::mem::take(&mut self.used);
        self.instances.retain(|id, _| used.contains(id));
        let keys: HashSet<u64> = self.instances.values().map(|i| i.key).collect();
        self.pipelines.retain(|key, _| keys.contains(key));
        let used_textures = std::mem::take(&mut self.used_textures);
        self.textures.retain(|key, _| used_textures.contains(key));
        self.current.lock().expect("shader instances").clear();
    }
}

impl iced_shader::Primitive for Primitive {
    type Pipeline = Pipeline;

    fn prepare(
        &self,
        pipeline: &mut Pipeline,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        bounds: &Rectangle,
        viewport: &Viewport,
    ) {
        let format = pipeline.format;
        let count = self.textures.len();
        let layout = pipeline
            .layouts
            .entry(count)
            .or_insert_with(|| layout(device, count));
        pipeline.pipelines.entry(self.key).or_insert_with(|| {
            let output = if format.is_srgb() {
                // Colors are written like on the web (sRGB); the target expects linear ones.
                "color = vec4<f32>(pow(color.rgb, vec3<f32>(2.2)), color.a);"
            } else {
                ""
            };
            let source = self.source.replace("// PYZED_OUTPUT", output);
            let module = device.create_shader_module(wgpu::ShaderModuleDescriptor {
                label: Some("pyzed shader"),
                source: wgpu::ShaderSource::Wgsl(source.into()),
            });
            device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
                label: Some("pyzed shader"),
                layout: Some(&layout.pipeline),
                vertex: wgpu::VertexState {
                    module: &module,
                    entry_point: Some("pyzed_vs"),
                    buffers: &[],
                    compilation_options: Default::default(),
                },
                fragment: Some(wgpu::FragmentState {
                    module: &module,
                    entry_point: Some("pyzed_fs"),
                    targets: &[Some(wgpu::ColorTargetState {
                        format,
                        blend: Some(wgpu::BlendState::ALPHA_BLENDING),
                        write_mask: wgpu::ColorWrites::ALL,
                    })],
                    compilation_options: Default::default(),
                }),
                primitive: wgpu::PrimitiveState::default(),
                depth_stencil: None,
                multisample: wgpu::MultisampleState::default(),
                multiview: None,
                cache: None,
            })
        });

        for texture in &self.textures {
            pipeline.used_textures.insert(texture.key);
            pipeline.textures.entry(texture.key).or_insert_with(|| {
                let size = wgpu::Extent3d {
                    width: texture.width.max(1),
                    height: texture.height.max(1),
                    depth_or_array_layers: 1,
                };
                let gpu = device.create_texture(&wgpu::TextureDescriptor {
                    label: Some("pyzed shader texture"),
                    size,
                    mip_level_count: 1,
                    sample_count: 1,
                    dimension: wgpu::TextureDimension::D2,
                    // The pixels stay as stored (sRGB, like the shader's colors).
                    format: wgpu::TextureFormat::Rgba8Unorm,
                    usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
                    view_formats: &[],
                });
                queue.write_texture(
                    wgpu::TexelCopyTextureInfo {
                        texture: &gpu,
                        mip_level: 0,
                        origin: wgpu::Origin3d::ZERO,
                        aspect: wgpu::TextureAspect::All,
                    },
                    &texture.pixels,
                    wgpu::TexelCopyBufferLayout {
                        offset: 0,
                        bytes_per_row: Some(4 * size.width),
                        rows_per_image: Some(size.height),
                    },
                    size,
                );
                gpu.create_view(&wgpu::TextureViewDescriptor::default())
            });
        }

        let id = self.instance(bounds);
        if !pipeline.instances.contains_key(&id) {
            let buffer = device.create_buffer(&wgpu::BufferDescriptor {
                label: Some("pyzed shader uniforms"),
                size: UNIFORM_SIZE,
                usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
                mapped_at_creation: false,
            });
            let mut entries = vec![wgpu::BindGroupEntry {
                binding: 0,
                resource: buffer.as_entire_binding(),
            }];
            for (i, texture) in self.textures.iter().enumerate() {
                let view = &pipeline.textures[&texture.key];
                entries.push(wgpu::BindGroupEntry {
                    binding: 1 + 2 * i as u32,
                    resource: wgpu::BindingResource::TextureView(view),
                });
                entries.push(wgpu::BindGroupEntry {
                    binding: 2 + 2 * i as u32,
                    resource: wgpu::BindingResource::Sampler(&pipeline.sampler),
                });
            }
            let bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
                label: Some("pyzed shader"),
                layout: &pipeline.layouts[&count].bind_group,
                entries: &entries,
            });
            pipeline.instances.insert(
                id,
                Instance {
                    buffer,
                    bind_group,
                    key: self.key,
                },
            );
        }
        let instance = &pipeline.instances[&id];

        let scale = viewport.scale_factor();
        let mut data: Vec<f32> = vec![
            bounds.x * scale,
            bounds.y * scale,
            bounds.width * scale,
            bounds.height * scale,
            self.time,
            scale,
            self.mouse[0],
            self.mouse[1],
        ];
        data.extend(self.values.iter().flatten());
        let bytes: Vec<u8> = data.iter().flat_map(|v| v.to_ne_bytes()).collect();
        queue.write_buffer(&instance.buffer, 0, &bytes);
        pipeline.used.insert(id);
        pipeline.current.lock().expect("shader instances").push(id);
    }

    fn draw(&self, pipeline: &Pipeline, render_pass: &mut wgpu::RenderPass<'_>) -> bool {
        // Primitives draw in the order they were prepared: take the next prepared instance
        // of this shader.
        let id = {
            let mut current = pipeline.current.lock().expect("shader instances");
            let Some(at) = current.iter().position(|id| {
                pipeline
                    .instances
                    .get(id)
                    .is_some_and(|i| i.key == self.key)
            }) else {
                return true;
            };
            current.remove(at)
        };
        let (Some(instance), Some(render)) = (
            pipeline.instances.get(&id),
            pipeline.pipelines.get(&self.key),
        ) else {
            return true;
        };
        render_pass.set_pipeline(render);
        render_pass.set_bind_group(0, &instance.bind_group, &[]);
        render_pass.draw(0..3, 0..1);
        true
    }
}
