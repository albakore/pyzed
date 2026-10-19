//! `pz.shader`: a widget painted by a WGSL fragment function, like a Shadertoy.
//!
//! Python gives the body of `fn shade(uv, px, size, time) -> vec4<f32>` and named uniforms;
//! this module wraps it in a full shader, checks it with naga (so mistakes raise in Python),
//! and draws it with a wgpu pipeline per distinct source. Renderers without a GPU (the
//! tiny-skia fallback, CI screenshots) draw the `fallback` background instead.

use std::collections::{HashMap, HashSet};
use std::hash::{Hash, Hasher};
use std::sync::{Arc, LazyLock};
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
const SLOTS: usize = 8;

/// When the process started: every shader's `time` counts from here, so they stay in sync.
static START: LazyLock<Instant> = LazyLock::new(Instant::now);

const HEADER: &str = r#"
struct PyzedGlobals {
    rect: vec4<f32>,
    info: vec4<f32>,
    values: array<vec4<f32>, 8>,
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

pub struct ShaderProps {
    source: Arc<str>,
    key: u64,
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

/// The full WGSL module for the user's code and uniforms.
fn compose(code: &str, slots: &[(String, Slot)]) -> String {
    let mut out = String::from(HEADER);
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
    let module = naga::front::wgsl::parse_str(source).map_err(|e| e.emit_to_string(source))?;
    let mut validator = naga::valid::Validator::new(
        naga::valid::ValidationFlags::all(),
        naga::valid::Capabilities::empty(),
    );
    validator
        .validate(&module)
        .map_err(|e| e.emit_to_string(source))?;
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

/// A widget painted on the GPU by your WGSL function
/// `fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32>`, which
/// returns the color (RGBA, 0 to 1) of every pixel. `uv` goes from 0 to 1 across the widget,
/// `px` and `size` are in pixels, `time` counts seconds and `mouse()` gives the pointer as a
/// `uv`. Each entry of `uniforms` (a number, 2 to 4 numbers or a color; up to 8) becomes a
/// function of the same name: `{"speed": 2}` -> `speed()`. Without a GPU (and in screenshots
/// taken without one) the widget shows `fallback`, a color or gradient. Raises `ValueError`
/// with the compiler's message when the code is not valid WGSL.
#[pyfunction]
#[pyo3(signature = (code, *, uniforms=None, width=None, height=None, animate=true, time=None, fallback=None))]
#[allow(clippy::too_many_arguments)]
pub fn shader(
    py: Python<'_>,
    code: &str,
    uniforms: Option<&Bound<'_, PyDict>>,
    width: Any<'_>,
    height: Any<'_>,
    animate: bool,
    time: Option<f32>,
    fallback: Any<'_>,
) -> PyResult<Py<Widget>> {
    let mut slots = Vec::new();
    let mut values = [[0.0; 4]; SLOTS];
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
            slots.push((name, slot));
            values[i] = v;
        }
    }
    if !code.contains("fn shade") {
        return Err(PyValueError::new_err(
            "invalid shader: define fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32>",
        ));
    }
    let source = compose(code, &slots);
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

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(shader, m)?)?;
    Ok(())
}

pub fn render(props: &ShaderProps) -> Element<'static, Message> {
    let program = Program {
        source: props.source.clone(),
        key: props.key,
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
    values: [[f32; 4]; SLOTS],
    time: f32,
    mouse: [f32; 2],
}

impl Primitive {
    fn instance(&self, bounds: &Rectangle) -> u64 {
        let mut h = std::collections::hash_map::DefaultHasher::new();
        self.key.hash(&mut h);
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

pub struct Pipeline {
    format: wgpu::TextureFormat,
    layout: wgpu::BindGroupLayout,
    pipeline_layout: wgpu::PipelineLayout,
    pipelines: HashMap<u64, wgpu::RenderPipeline>,
    instances: HashMap<u64, Instance>,
    used: HashSet<u64>,
    /// The instance each primitive drew last, so `draw` (which can't hash bounds) finds it.
    current: std::sync::Mutex<Vec<u64>>,
}

const UNIFORM_SIZE: u64 = (4 + 4 + 4 * SLOTS as u64) * 4;

impl iced_shader::Pipeline for Pipeline {
    fn new(device: &wgpu::Device, _queue: &wgpu::Queue, format: wgpu::TextureFormat) -> Self {
        let layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("pyzed shader"),
            entries: &[wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::FRAGMENT,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: false,
                    min_binding_size: wgpu::BufferSize::new(UNIFORM_SIZE),
                },
                count: None,
            }],
        });
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("pyzed shader"),
            bind_group_layouts: &[&layout],
            push_constant_ranges: &[],
        });
        Self {
            format,
            layout,
            pipeline_layout,
            pipelines: HashMap::new(),
            instances: HashMap::new(),
            used: HashSet::new(),
            current: std::sync::Mutex::new(Vec::new()),
        }
    }

    fn trim(&mut self) {
        let used = std::mem::take(&mut self.used);
        self.instances.retain(|id, _| used.contains(id));
        let keys: HashSet<u64> = self.instances.values().map(|i| i.key).collect();
        self.pipelines.retain(|key, _| keys.contains(key));
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
        let pipeline_layout = &pipeline.pipeline_layout;
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
                layout: Some(pipeline_layout),
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

        let id = self.instance(bounds);
        let layout = &pipeline.layout;
        let instance = pipeline.instances.entry(id).or_insert_with(|| {
            let buffer = device.create_buffer(&wgpu::BufferDescriptor {
                label: Some("pyzed shader uniforms"),
                size: UNIFORM_SIZE,
                usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
                mapped_at_creation: false,
            });
            let bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
                label: Some("pyzed shader"),
                layout,
                entries: &[wgpu::BindGroupEntry {
                    binding: 0,
                    resource: buffer.as_entire_binding(),
                }],
            });
            Instance {
                buffer,
                bind_group,
                key: self.key,
            }
        });

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
