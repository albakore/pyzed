//! Widgets beyond the basics: bitmap images, canvas drawing, rich text, markdown,
//! QR codes, pick lists, radios, resizable splits, grids and responsive layouts.

use std::hash::{Hash, Hasher};

use iced::widget::canvas::{self as cv, Frame, Path, Stroke};
use iced::widget::{
    self, image as img, markdown as md, pick_list as pl, qr_code as qr, radio as rd, text,
};
use iced::{
    Background, Border, Color, ContentFit, Element, Font, Length, Padding, Pixels, Point, Radians,
    Rectangle, Size, Theme, Vector, mouse,
};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyString, PyTuple};

use crate::app::Message;
use crate::style::{self, Any, ICONS, MONO, SANS};
use crate::widget::{Kind, PyMsg, Widget, child, new};

fn hash_bytes(bytes: &[u8]) -> u64 {
    let mut h = std::collections::hash_map::DefaultHasher::new();
    bytes.hash(&mut h);
    h.finish()
}

fn content_fit(value: Option<&str>) -> PyResult<Option<ContentFit>> {
    Ok(match value {
        None => None,
        Some("contain") => Some(ContentFit::Contain),
        Some("cover") => Some(ContentFit::Cover),
        Some("fill") => Some(ContentFit::Fill),
        Some("none") => Some(ContentFit::None),
        Some("scale-down" | "scale_down") => Some(ContentFit::ScaleDown),
        Some(other) => {
            return Err(PyValueError::new_err(format!(
                "invalid content_fit {other:?}: use contain, cover, fill, none or scale-down"
            )));
        }
    })
}

// ---------------------------------------------------------------------------
// Images
// ---------------------------------------------------------------------------

#[derive(Clone)]
pub enum ImageSource {
    Path(String),
    Bytes(Vec<u8>),
    Rgba {
        width: u32,
        height: u32,
        pixels: Vec<u8>,
    },
}

impl ImageSource {
    fn key(&self) -> u64 {
        match self {
            ImageSource::Path(p) => hash_bytes(p.as_bytes()),
            ImageSource::Bytes(b) => hash_bytes(b) ^ 0x9e37_79b9,
            ImageSource::Rgba {
                width,
                height,
                pixels,
            } => hash_bytes(pixels) ^ ((*width as u64) << 32 | *height as u64),
        }
    }

    /// Decodes the image once (cached by content) into RGBA pixels.
    ///
    /// Decoding here, instead of handing iced a path, makes the first frame complete
    /// (wgpu loads files in the background, so off-screen screenshots came out empty)
    /// and gives `Picture` the pixels it needs to crop and round corners itself.
    pub fn decode(
        &self,
        cache: &std::cell::RefCell<std::collections::HashMap<u64, Decoded>>,
    ) -> Decoded {
        let key = self.key();
        if let Some(decoded) = cache.borrow().get(&key) {
            return decoded.clone();
        }
        let rgba = match self {
            ImageSource::Path(p) => ::image::open(p).map(|i| i.to_rgba8()).ok(),
            ImageSource::Bytes(b) => ::image::load_from_memory(b).map(|i| i.to_rgba8()).ok(),
            ImageSource::Rgba {
                width,
                height,
                pixels,
            } => ::image::RgbaImage::from_raw(*width, *height, pixels.clone()),
        };
        let decoded = match rgba {
            Some(rgba) => {
                let (width, height) = rgba.dimensions();
                let pixels = bytes::Bytes::from(rgba.into_raw());
                Decoded {
                    key,
                    handle: img::Handle::from_rgba(width, height, pixels.clone()),
                    size: Some((width, height)),
                    pixels,
                }
            }
            // Unreadable: let iced try (and show nothing, as it does for broken images).
            None => Decoded {
                key,
                handle: match self {
                    ImageSource::Path(p) => img::Handle::from_path(p),
                    ImageSource::Bytes(b) => img::Handle::from_bytes(b.clone()),
                    ImageSource::Rgba { .. } => img::Handle::from_bytes(Vec::new()),
                },
                size: None,
                pixels: bytes::Bytes::new(),
            },
        };
        cache.borrow_mut().insert(key, decoded.clone());
        decoded
    }
}

/// A decoded bitmap: an iced handle plus its RGBA pixels (cheap to clone).
#[derive(Clone)]
pub struct Decoded {
    key: u64,
    pub handle: img::Handle,
    size: Option<(u32, u32)>,
    pixels: bytes::Bytes,
}

/// Cropped / rounded copies of images, keyed by image, crop rectangle and corner radius.
pub type MaskCache =
    std::cell::RefCell<std::collections::HashMap<(u64, [u32; 4], [u32; 2]), img::Handle>>;

fn image_source(source: &Bound<'_, PyAny>, size: Option<(u32, u32)>) -> PyResult<ImageSource> {
    if let Ok(bytes) = source.cast::<PyBytes>() {
        let data = bytes.as_bytes().to_vec();
        return Ok(match size {
            Some((width, height)) => {
                if data.len() != (width * height * 4) as usize {
                    return Err(PyValueError::new_err(format!(
                        "RGBA data must be width*height*4 = {} bytes, got {}",
                        width * height * 4,
                        data.len()
                    )));
                }
                ImageSource::Rgba {
                    width,
                    height,
                    pixels: data,
                }
            }
            None => ImageSource::Bytes(data),
        });
    }
    if let Ok(array) = source.cast::<pyo3::types::PyByteArray>() {
        return image_source(&PyBytes::new(source.py(), &array.to_vec()), size);
    }
    if let Ok(path) = source.extract::<std::path::PathBuf>() {
        return Ok(ImageSource::Path(path.to_string_lossy().into_owned()));
    }
    Err(PyTypeError::new_err(
        "image source must be a path, bytes (encoded file) or raw RGBA bytes with size=",
    ))
}

pub struct ImageProps {
    pub source: ImageSource,
    pub width: Option<Length>,
    pub height: Option<Length>,
    pub fit: Option<ContentFit>,
    pub nearest: bool,
    pub opacity: f32,
    pub radius: f32,
    pub rotation: f32,
    pub scale: f32,
    pub viewer: Option<(f32, f32, f32)>,
}

/// A bitmap image (PNG, JPEG, GIF, BMP, WebP, ...) from a path or bytes.
#[pyfunction]
#[pyo3(signature = (source, *, width=None, height=None, content_fit=None, filter="linear",
    opacity=1.0, radius=0.0, rotation=0.0, scale=1.0, size=None))]
#[allow(clippy::too_many_arguments)]
pub fn image(
    py: Python<'_>,
    source: &Bound<'_, PyAny>,
    width: Any<'_>,
    height: Any<'_>,
    content_fit: Option<&str>,
    filter: &str,
    opacity: f32,
    radius: f32,
    rotation: f32,
    scale: f32,
    size: Option<(u32, u32)>,
) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Image(Box::new(ImageProps {
            source: image_source(source, size)?,
            width: style::opt_length(&width)?,
            height: style::opt_length(&height)?,
            fit: self::content_fit(content_fit)?,
            nearest: filter == "nearest",
            opacity,
            radius,
            rotation,
            scale,
            viewer: None,
        })),
    )
}

/// An image you can pan (drag) and zoom (scroll wheel), like Iced's image viewer.
#[pyfunction]
#[pyo3(signature = (source, *, width=None, height=None, min_scale=0.25, max_scale=10.0,
    scale_step=0.10, filter="linear", size=None))]
#[allow(clippy::too_many_arguments)]
pub fn image_viewer(
    py: Python<'_>,
    source: &Bound<'_, PyAny>,
    width: Any<'_>,
    height: Any<'_>,
    min_scale: f32,
    max_scale: f32,
    scale_step: f32,
    filter: &str,
    size: Option<(u32, u32)>,
) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Image(Box::new(ImageProps {
            source: image_source(source, size)?,
            width: style::opt_length(&width)?,
            height: style::opt_length(&height)?,
            fit: None,
            nearest: filter == "nearest",
            opacity: 1.0,
            radius: 0.0,
            rotation: 0.0,
            scale: 1.0,
            viewer: Some((min_scale, max_scale, scale_step)),
        })),
    )
}

pub fn render_image<'a>(
    props: &ImageProps,
    decoded: Decoded,
    masks: &'a MaskCache,
) -> Element<'a, Message> {
    let filter = if props.nearest {
        img::FilterMethod::Nearest
    } else {
        img::FilterMethod::Linear
    };
    if let Some((min, max, step)) = props.viewer {
        let mut v = widget::image::viewer(decoded.handle)
            .min_scale(min)
            .max_scale(max)
            .scale_step(step)
            .filter_method(filter);
        if let Some(w) = props.width {
            v = v.width(w);
        }
        if let Some(h) = props.height {
            v = v.height(h);
        }
        return v.into();
    }
    let width = props.width.unwrap_or(Length::Shrink);
    let height = props.height.unwrap_or(Length::Shrink);
    if decoded.size.is_none() || props.rotation != 0.0 {
        // Rotated: iced's widget, inside a clipping container. The software renderer
        // still lets the rotated corners spill out of the box.
        let mut i = widget::image(decoded.handle)
            .filter_method(filter)
            .opacity(props.opacity)
            .scale(props.scale)
            .rotation(Radians(props.rotation.to_radians()))
            .width(width)
            .height(height);
        if let Some(fit) = props.fit {
            i = i.content_fit(fit);
        }
        if props.radius > 0.0 {
            i = i.border_radius(props.radius);
        }
        return widget::container(i).clip(true).into();
    }
    Element::new(Picture {
        decoded,
        width,
        height,
        fit: props.fit.unwrap_or(ContentFit::Contain),
        filter,
        opacity: props.opacity,
        radius: props.radius,
        scale: props.scale,
        masks,
    })
}

/// A bitmap that crops itself to its box and rounds its own corners, so `cover`,
/// `none` and `radius` look the same with wgpu and with the software renderer
/// (tiny-skia ignores both the clip bounds and the border radius of images).
struct Picture<'a> {
    decoded: Decoded,
    width: Length,
    height: Length,
    fit: ContentFit,
    filter: img::FilterMethod,
    opacity: f32,
    radius: f32,
    scale: f32,
    masks: &'a MaskCache,
}

impl Picture<'_> {
    fn image_size(&self) -> Size {
        let (w, h) = self.decoded.size.unwrap_or((1, 1));
        Size::new(w as f32, h as f32)
    }

    /// Where the whole (uncropped) image lands inside `bounds`, like iced's image widget.
    fn drawing_bounds(&self, bounds: Rectangle) -> Rectangle {
        let size = self.fit.fit(self.image_size(), bounds.size()) * self.scale;
        let position = match self.fit {
            ContentFit::None => bounds.position(),
            _ => Point::new(
                bounds.center_x() - size.width / 2.0,
                bounds.center_y() - size.height / 2.0,
            ),
        };
        Rectangle::new(position, size)
    }

    /// The visible part of the image with rounded corners, as a cached RGBA handle.
    fn masked(&self, drawing: Rectangle, visible: Rectangle) -> Option<img::Handle> {
        let (iw, ih) = self.decoded.size?;
        let sx = iw as f32 / drawing.width;
        let sy = ih as f32 / drawing.height;
        let x0 = (((visible.x - drawing.x) * sx).round() as u32).min(iw - 1);
        let y0 = (((visible.y - drawing.y) * sy).round() as u32).min(ih - 1);
        let cw = ((visible.width * sx).round() as u32).clamp(1, iw - x0);
        let ch = ((visible.height * sy).round() as u32).clamp(1, ih - y0);
        // The radius is in logical pixels of the box; in image pixels it scales per axis.
        let rx = (self.radius * sx).min(cw as f32 / 2.0);
        let ry = (self.radius * sy).min(ch as f32 / 2.0);
        let key = (
            self.decoded.key,
            [x0, y0, cw, ch],
            [(rx * 16.0) as u32, (ry * 16.0) as u32],
        );
        if let Some(handle) = self.masks.borrow().get(&key) {
            return Some(handle.clone());
        }
        let src = &self.decoded.pixels;
        let mut out = Vec::with_capacity((cw * ch * 4) as usize);
        for y in y0..y0 + ch {
            let start = ((y * iw + x0) * 4) as usize;
            out.extend_from_slice(&src[start..start + (cw * 4) as usize]);
        }
        if rx >= 0.5 && ry >= 0.5 {
            round_corners(&mut out, cw, ch, rx, ry);
        }
        let handle = img::Handle::from_rgba(cw, ch, out);
        self.masks.borrow_mut().insert(key, handle.clone());
        Some(handle)
    }
}

/// Fades the pixels outside elliptical corners of radii `rx`/`ry` (anti-aliased).
fn round_corners(pixels: &mut [u8], width: u32, height: u32, rx: f32, ry: f32) {
    let edge = 1.0 / rx.min(ry);
    let (w, h) = (width as f32, height as f32);
    let corner_rows = (ry.ceil() as u32).min(height);
    let rows = (0..corner_rows).chain(height.saturating_sub(corner_rows).max(corner_rows)..height);
    for y in rows {
        let py = y as f32 + 0.5;
        let dy = if py < ry {
            ry - py
        } else if py > h - ry {
            py - (h - ry)
        } else {
            continue;
        };
        for x in 0..width {
            let px = x as f32 + 0.5;
            let dx = if px < rx {
                rx - px
            } else if px > w - rx {
                px - (w - rx)
            } else {
                continue;
            };
            let d = ((dx / rx).powi(2) + (dy / ry).powi(2)).sqrt();
            let coverage = ((1.0 - d) / edge + 0.5).clamp(0.0, 1.0);
            if coverage < 1.0 {
                let a = &mut pixels[((y * width + x) * 4 + 3) as usize];
                *a = (*a as f32 * coverage).round() as u8;
            }
        }
    }
}

impl<Theme> iced::advanced::Widget<Message, Theme, iced::Renderer> for Picture<'_> {
    fn size(&self) -> Size<Length> {
        Size::new(self.width, self.height)
    }

    fn layout(
        &mut self,
        _tree: &mut iced::advanced::widget::Tree,
        _renderer: &iced::Renderer,
        limits: &iced::advanced::layout::Limits,
    ) -> iced::advanced::layout::Node {
        // Same sizing rules as iced's image widget.
        let image = self.image_size();
        let bounds = limits.resolve(self.width, self.height, image);
        let full = self.fit.fit(image, bounds);
        let size = Size::new(
            match self.width {
                Length::Shrink => bounds.width.min(full.width),
                _ => bounds.width,
            },
            match self.height {
                Length::Shrink => bounds.height.min(full.height),
                _ => bounds.height,
            },
        );
        iced::advanced::layout::Node::new(size)
    }

    fn draw(
        &self,
        _tree: &iced::advanced::widget::Tree,
        renderer: &mut iced::Renderer,
        _theme: &Theme,
        _style: &iced::advanced::renderer::Style,
        layout: iced::advanced::Layout<'_>,
        _cursor: mouse::Cursor,
        _viewport: &Rectangle,
    ) {
        use iced::advanced::image::Renderer as _;
        let bounds = layout.bounds();
        let drawing = self.drawing_bounds(bounds);
        let Some(visible) = drawing.intersection(&bounds) else {
            return;
        };
        let image = |handle: img::Handle| iced::advanced::image::Image {
            handle,
            filter_method: self.filter,
            rotation: Radians(0.0),
            border_radius: Default::default(),
            opacity: self.opacity,
            snap: true,
        };
        let overflows =
            visible.width < drawing.width - 0.5 || visible.height < drawing.height - 0.5;
        let (handle, target) = if self.radius <= 0.0 && !overflows {
            (self.decoded.handle.clone(), drawing)
        } else {
            match self.masked(drawing, visible) {
                Some(handle) => (handle, visible),
                None => return,
            }
        };
        // wgpu uploads big images (over 2 MB) in the background, so the first frame (the
        // only one an off-screen screenshot gets) would be empty; upload them right away.
        if let iced::advanced::image::Handle::Rgba { width, height, .. } = &handle
            && (*width as usize) * (*height as usize) * 4 >= 2 * 1024 * 1024
        {
            let _ = renderer.load_image(&handle);
        }
        renderer.draw_image(
            image(handle),
            target,
            target.intersection(&bounds).unwrap_or(target),
        );
    }
}

// ---------------------------------------------------------------------------
// Canvas
// ---------------------------------------------------------------------------

#[derive(Clone, Default)]
struct Paint {
    fill: Option<Color>,
    stroke: Option<Color>,
    width: f32,
    dash: Vec<f32>,
    round: bool,
}

#[derive(Clone)]
enum PathOp {
    Move(Point),
    Line(Point),
    Quad(Point, Point),
    Cubic(Point, Point, Point),
    Arc(Point, f32, f32, f32),
    Close,
}

#[derive(Clone)]
enum Shape {
    Background(Color),
    Rect {
        bounds: Rectangle,
        radius: f32,
        paint: Paint,
    },
    Rects {
        rects: Vec<Rectangle>,
        color: Color,
    },
    Circle {
        center: Point,
        radius: f32,
        paint: Paint,
    },
    Line {
        from: Point,
        to: Point,
        paint: Paint,
    },
    Path {
        ops: Vec<PathOp>,
        paint: Paint,
    },
    Text {
        position: Point,
        content: String,
        size: f32,
        color: Color,
        font: Font,
        align_x: text::Alignment,
        align_y: iced::alignment::Vertical,
    },
    Save,
    Restore,
    Translate(Vector),
    Rotate(f32),
    Scale(f32, f32),
}

pub struct CanvasProps {
    shapes: Vec<Shape>,
    width: Length,
    height: Length,
    pub cache_key: Option<(String, u64)>,
    on_press: Option<PyMsg>,
    on_release: Option<PyMsg>,
    on_right_press: Option<PyMsg>,
    on_move: Option<PyMsg>,
    on_scroll: Option<PyMsg>,
    cursor: Option<mouse::Interaction>,
}

fn get<'py>(d: &Bound<'py, PyDict>, key: &str) -> PyResult<Option<Bound<'py, PyAny>>> {
    Ok(d.get_item(key)?.filter(|v| !v.is_none()))
}

fn num(d: &Bound<'_, PyDict>, key: &str, default: f32) -> PyResult<f32> {
    Ok(match get(d, key)? {
        Some(v) => v.extract()?,
        None => default,
    })
}

fn paint(d: &Bound<'_, PyDict>) -> PyResult<Paint> {
    Ok(Paint {
        fill: style::opt_color(&get(d, "fill")?)?,
        stroke: style::opt_color(&get(d, "stroke")?)?,
        width: num(d, "width", 1.0)?,
        dash: match get(d, "dash")? {
            Some(v) => v.extract()?,
            None => Vec::new(),
        },
        round: match get(d, "cap")? {
            Some(v) => v.extract::<String>()? == "round",
            None => false,
        },
    })
}

fn parse_shape(value: &Bound<'_, PyAny>) -> PyResult<Shape> {
    let d = value
        .cast::<PyDict>()
        .map_err(|_| PyTypeError::new_err("canvas shapes are dicts; build them with pyzed.draw"))?;
    let kind: String = get(d, "type")?
        .ok_or_else(|| PyValueError::new_err("shape without 'type'"))?
        .extract()?;
    Ok(match kind.as_str() {
        "background" => Shape::Background(style::color(
            &get(d, "color")?.ok_or_else(|| PyValueError::new_err("background needs color"))?,
        )?),
        "rect" => Shape::Rect {
            bounds: Rectangle::new(
                Point::new(num(d, "x", 0.0)?, num(d, "y", 0.0)?),
                Size::new(num(d, "w", 0.0)?, num(d, "h", 0.0)?),
            ),
            radius: num(d, "radius", 0.0)?,
            paint: paint(d)?,
        },
        "rects" => {
            let mut rects = Vec::new();
            if let Some(items) = get(d, "rects")? {
                for item in items.try_iter()? {
                    let (x, y, w, h): (f32, f32, f32, f32) = item?.extract()?;
                    rects.push(Rectangle::new(Point::new(x, y), Size::new(w, h)));
                }
            }
            Shape::Rects {
                rects,
                color: style::color(
                    &get(d, "fill")?.ok_or_else(|| PyValueError::new_err("rects needs fill"))?,
                )?,
            }
        }
        "circle" => Shape::Circle {
            center: Point::new(num(d, "x", 0.0)?, num(d, "y", 0.0)?),
            radius: num(d, "r", 1.0)?,
            paint: paint(d)?,
        },
        "line" => Shape::Line {
            from: Point::new(num(d, "x1", 0.0)?, num(d, "y1", 0.0)?),
            to: Point::new(num(d, "x2", 0.0)?, num(d, "y2", 0.0)?),
            paint: paint(d)?,
        },
        "path" => {
            let mut ops = Vec::new();
            if let Some(items) = get(d, "ops")? {
                for item in items.try_iter()? {
                    let item = item?;
                    let t = item.cast::<PyTuple>()?;
                    let op: String = t.get_item(0)?.extract()?;
                    let f = |i: usize| -> PyResult<f32> { t.get_item(i)?.extract() };
                    ops.push(match op.as_str() {
                        "M" => PathOp::Move(Point::new(f(1)?, f(2)?)),
                        "L" => PathOp::Line(Point::new(f(1)?, f(2)?)),
                        "Q" => PathOp::Quad(Point::new(f(1)?, f(2)?), Point::new(f(3)?, f(4)?)),
                        "C" => PathOp::Cubic(
                            Point::new(f(1)?, f(2)?),
                            Point::new(f(3)?, f(4)?),
                            Point::new(f(5)?, f(6)?),
                        ),
                        "A" => PathOp::Arc(Point::new(f(1)?, f(2)?), f(3)?, f(4)?, f(5)?),
                        "Z" => PathOp::Close,
                        other => {
                            return Err(PyValueError::new_err(format!(
                                "unknown path op {other:?}"
                            )));
                        }
                    });
                }
            }
            Shape::Path {
                ops,
                paint: paint(d)?,
            }
        }
        "text" => Shape::Text {
            position: Point::new(num(d, "x", 0.0)?, num(d, "y", 0.0)?),
            content: get(d, "content")?
                .map(|v| v.str().map(|s| s.to_string()))
                .transpose()?
                .unwrap_or_default(),
            size: num(d, "size", 14.0)?,
            color: style::opt_color(&get(d, "color")?)?.unwrap_or(Color::WHITE),
            font: {
                let family: Option<String> = get(d, "font")?.map(|v| v.extract()).transpose()?;
                let weight = get(d, "weight")?;
                style::font(Some(family.as_deref().unwrap_or("sans")), &weight, false)?
                    .unwrap_or(Font::with_name(SANS))
            },
            align_x: match get(d, "align_x")?
                .map(|v| v.extract::<String>())
                .transpose()?
                .as_deref()
            {
                Some("center") => text::Alignment::Center,
                Some("end" | "right") => text::Alignment::Right,
                _ => text::Alignment::Left,
            },
            align_y: style::align_y(
                get(d, "align_y")?
                    .map(|v| v.extract::<String>())
                    .transpose()?
                    .as_deref(),
            )?
            .unwrap_or(iced::alignment::Vertical::Top),
        },
        "save" => Shape::Save,
        "restore" => Shape::Restore,
        "translate" => Shape::Translate(Vector::new(num(d, "x", 0.0)?, num(d, "y", 0.0)?)),
        "rotate" => Shape::Rotate(num(d, "degrees", 0.0)?.to_radians()),
        "scale" => {
            let x = num(d, "x", 1.0)?;
            Shape::Scale(x, num(d, "y", x)?)
        }
        other => {
            return Err(PyValueError::new_err(format!(
                "unknown shape type {other:?}"
            )));
        }
    })
}

fn cursor_kind(value: Option<&str>) -> PyResult<Option<mouse::Interaction>> {
    use mouse::Interaction;
    Ok(match value {
        None => None,
        Some("pointer") => Some(Interaction::Pointer),
        Some("text") => Some(Interaction::Text),
        Some("grab") => Some(Interaction::Grab),
        Some("grabbing") => Some(Interaction::Grabbing),
        Some("crosshair") => Some(Interaction::Crosshair),
        Some("not-allowed") => Some(Interaction::NotAllowed),
        Some("resize-horizontal") => Some(Interaction::ResizingHorizontally),
        Some("resize-vertical") => Some(Interaction::ResizingVertically),
        Some("move") => Some(Interaction::Move),
        Some("idle" | "default") => Some(Interaction::Idle),
        Some(other) => return Err(PyValueError::new_err(format!("unknown cursor {other:?}"))),
    })
}

pub fn parse_cursor(value: Option<&str>) -> PyResult<Option<mouse::Interaction>> {
    cursor_kind(value)
}

/// A drawing surface. `shapes` is a list built with `pyzed.draw` (rect, circle, line,
/// path, text, transforms...). Pointer callbacks receive canvas-relative coordinates.
///
/// Give it an `id` to cache the tessellated geometry between frames: it is only rebuilt
/// when the shapes change.
#[pyfunction]
#[pyo3(signature = (shapes=None, *, width=None, height=None, id=None, on_press=None,
    on_release=None, on_right_press=None, on_move=None, on_scroll=None, cursor=None))]
#[allow(clippy::too_many_arguments)]
pub fn canvas(
    py: Python<'_>,
    shapes: Any<'_>,
    width: Any<'_>,
    height: Any<'_>,
    id: Option<String>,
    on_press: Any<'_>,
    on_release: Any<'_>,
    on_right_press: Any<'_>,
    on_move: Any<'_>,
    on_scroll: Any<'_>,
    cursor: Option<&str>,
) -> PyResult<Py<Widget>> {
    let mut parsed = Vec::new();
    if let Some(shapes) = &shapes {
        for item in crate::widget::flatten(shapes)? {
            parsed.push(parse_shape(&item)?);
        }
    }
    let cache_key = match (&id, &shapes) {
        (Some(id), Some(shapes)) => {
            // Shapes are plain dicts/tuples/numbers, so their repr is a stable fingerprint.
            let repr = shapes.repr()?;
            Some((id.clone(), hash_bytes(repr.to_cow()?.as_bytes())))
        }
        (Some(id), None) => Some((id.clone(), 0)),
        _ => None,
    };
    new(
        py,
        Kind::Canvas(std::sync::Arc::new(CanvasProps {
            shapes: parsed,
            width: style::opt_length(&width)?.unwrap_or(Length::Fill),
            height: style::opt_length(&height)?.unwrap_or(Length::Fill),
            cache_key,
            on_press: PyMsg::maybe(&on_press),
            on_release: PyMsg::maybe(&on_release),
            on_right_press: PyMsg::maybe(&on_right_press),
            on_move: PyMsg::maybe(&on_move),
            on_scroll: PyMsg::maybe(&on_scroll),
            cursor: cursor_kind(cursor)?,
        })),
    )
}

/// Geometry cache for a canvas with an `id`.
#[derive(Default)]
pub struct CanvasCache {
    hash: std::cell::Cell<u64>,
    cache: cv::Cache,
}

struct Drawing<'a> {
    props: std::sync::Arc<CanvasProps>,
    cache: Option<&'a CanvasCache>,
}

fn stroke_of<'b>(paint: &'b Paint, color: Color) -> Stroke<'b> {
    let mut s = Stroke::default().with_color(color).with_width(paint.width);
    if paint.round {
        s = s
            .with_line_cap(cv::LineCap::Round)
            .with_line_join(cv::LineJoin::Round);
    }
    if !paint.dash.is_empty() {
        s.line_dash = cv::LineDash {
            segments: &paint.dash,
            offset: 0,
        };
    }
    s
}

fn apply(frame: &mut Frame, path: &Path, paint: &Paint) {
    if let Some(fill) = paint.fill {
        frame.fill(path, fill);
    }
    if let Some(stroke) = paint.stroke {
        frame.stroke(path, stroke_of(paint, stroke));
    }
}

fn draw_shapes(frame: &mut Frame, shapes: &[Shape]) {
    for shape in shapes {
        match shape {
            Shape::Background(color) => frame.fill_rectangle(Point::ORIGIN, frame.size(), *color),
            Shape::Rect {
                bounds,
                radius,
                paint,
            } => {
                let path = if *radius > 0.0 {
                    Path::rounded_rectangle(bounds.position(), bounds.size(), (*radius).into())
                } else {
                    Path::rectangle(bounds.position(), bounds.size())
                };
                apply(frame, &path, paint);
            }
            Shape::Rects { rects, color } => {
                for r in rects {
                    frame.fill_rectangle(r.position(), r.size(), *color);
                }
            }
            Shape::Circle {
                center,
                radius,
                paint,
            } => apply(frame, &Path::circle(*center, *radius), paint),
            Shape::Line { from, to, paint } => {
                let color = paint.stroke.or(paint.fill).unwrap_or(Color::WHITE);
                frame.stroke(&Path::line(*from, *to), stroke_of(paint, color));
            }
            Shape::Path { ops, paint } => {
                let path = Path::new(|b| {
                    for op in ops {
                        match op {
                            PathOp::Move(p) => b.move_to(*p),
                            PathOp::Line(p) => b.line_to(*p),
                            PathOp::Quad(c, p) => b.quadratic_curve_to(*c, *p),
                            PathOp::Cubic(c1, c2, p) => b.bezier_curve_to(*c1, *c2, *p),
                            PathOp::Arc(center, radius, start, end) => b.arc(cv::path::Arc {
                                center: *center,
                                radius: *radius,
                                start_angle: Radians(start.to_radians()),
                                end_angle: Radians(end.to_radians()),
                            }),
                            PathOp::Close => b.close(),
                        }
                    }
                });
                apply(frame, &path, paint);
            }
            Shape::Text {
                position,
                content,
                size,
                color,
                font,
                align_x,
                align_y,
            } => frame.fill_text(cv::Text {
                content: content.clone(),
                position: *position,
                color: *color,
                size: Pixels(*size),
                font: *font,
                align_x: *align_x,
                align_y: *align_y,
                ..cv::Text::default()
            }),
            Shape::Save => frame.push_transform(),
            Shape::Restore => frame.pop_transform(),
            Shape::Translate(v) => frame.translate(*v),
            Shape::Rotate(r) => frame.rotate(Radians(*r)),
            Shape::Scale(x, y) => frame.scale_nonuniform(Vector::new(*x, *y)),
        }
    }
}

impl cv::Program<Message> for Drawing<'_> {
    type State = ();

    fn update(
        &self,
        _state: &mut (),
        event: &cv::Event,
        bounds: Rectangle,
        cursor: mouse::Cursor,
    ) -> Option<cv::Action<Message>> {
        let props = &self.props;
        let position = cursor.position_in(bounds);
        let point = |cb: &Option<PyMsg>| -> Option<cv::Action<Message>> {
            let (cb, p) = (cb.as_ref()?, position?);
            Some(cv::Action::publish(Message::Point(cb.clone(), p.x, p.y)).and_capture())
        };
        match event {
            cv::Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left)) => {
                point(&props.on_press)
            }
            cv::Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Right)) => {
                point(&props.on_right_press)
            }
            cv::Event::Mouse(mouse::Event::ButtonReleased(mouse::Button::Left)) => {
                point(&props.on_release)
            }
            cv::Event::Mouse(mouse::Event::CursorMoved { .. }) => {
                let (cb, p) = (props.on_move.as_ref()?, position?);
                Some(cv::Action::publish(Message::Point(cb.clone(), p.x, p.y)))
            }
            cv::Event::Mouse(mouse::Event::WheelScrolled { delta }) => {
                let cb = props.on_scroll.as_ref()?;
                position?;
                let (x, y) = match delta {
                    mouse::ScrollDelta::Lines { x, y } => (*x, *y),
                    mouse::ScrollDelta::Pixels { x, y } => (*x / 60.0, *y / 60.0),
                };
                Some(cv::Action::publish(Message::Point(cb.clone(), x, y)).and_capture())
            }
            _ => None,
        }
    }

    fn draw(
        &self,
        _state: &(),
        renderer: &iced::Renderer,
        _theme: &Theme,
        bounds: Rectangle,
        _cursor: mouse::Cursor,
    ) -> Vec<cv::Geometry> {
        match self.cache {
            Some(cache) => vec![cache.cache.draw(renderer, bounds.size(), |frame| {
                draw_shapes(frame, &self.props.shapes)
            })],
            None => {
                let mut frame = Frame::new(renderer, bounds.size());
                draw_shapes(&mut frame, &self.props.shapes);
                vec![frame.into_geometry()]
            }
        }
    }

    fn mouse_interaction(
        &self,
        _state: &(),
        bounds: Rectangle,
        cursor: mouse::Cursor,
    ) -> mouse::Interaction {
        match self.props.cursor {
            Some(c) if cursor.is_over(bounds) => c,
            _ => mouse::Interaction::default(),
        }
    }
}

pub fn render_canvas<'a>(
    props: std::sync::Arc<CanvasProps>,
    cache: Option<&'a CanvasCache>,
) -> Element<'a, Message> {
    if let (Some(cache), Some((_, hash))) = (cache, &props.cache_key)
        && cache.hash.get() != *hash
    {
        cache.cache.clear();
        cache.hash.set(*hash);
    }
    let (width, height) = (props.width, props.height);
    widget::canvas(Drawing { props, cache })
        .width(width)
        .height(height)
        .into()
}

// ---------------------------------------------------------------------------
// Rich text
// ---------------------------------------------------------------------------

/// A styled fragment of `rich_text`. Create it with `pyzed.span`.
#[pyclass(module = "pyzed._core", frozen)]
#[derive(Clone)]
pub struct Span {
    text: String,
    size: Option<f32>,
    color: Option<Color>,
    font: Option<Font>,
    background: Option<Color>,
    radius: f32,
    padding: Padding,
    underline: bool,
    strikethrough: bool,
    link: Option<PyMsg>,
}

#[pymethods]
impl Span {
    fn __repr__(&self) -> String {
        format!("<Span {:?}>", self.text)
    }
}

/// A styled piece of text for `rich_text`. `link` makes it clickable: it is sent (or
/// called, if it is a function) when the span is clicked.
#[pyfunction]
#[pyo3(signature = (text, *, color=None, size=None, font=None, weight=None, italic=false,
    bg=None, radius=0.0, padding=None, underline=false, strikethrough=false, link=None))]
#[allow(clippy::too_many_arguments)]
pub fn span(
    text: &Bound<'_, PyAny>,
    color: Any<'_>,
    size: Option<f32>,
    font: Option<&str>,
    weight: Any<'_>,
    italic: bool,
    bg: Any<'_>,
    radius: f32,
    padding: Any<'_>,
    underline: bool,
    strikethrough: bool,
    link: Any<'_>,
) -> PyResult<Span> {
    Ok(Span {
        text: match text.cast::<PyString>() {
            Ok(s) => s.to_cow()?.into_owned(),
            Err(_) => text.str()?.to_cow()?.into_owned(),
        },
        size,
        color: style::opt_color(&color)?,
        font: style::font(font, &weight, italic)?,
        background: style::opt_color(&bg)?,
        radius,
        padding: style::opt_padding(&padding)?.unwrap_or(Padding::ZERO),
        underline,
        strikethrough,
        link: PyMsg::maybe(&link),
    })
}

pub struct RichProps {
    spans: Vec<Span>,
    size: Option<f32>,
    color: Option<Color>,
    font: Option<Font>,
    line_height: Option<f32>,
    width: Option<Length>,
    align_x: Option<iced::alignment::Horizontal>,
    wrap: bool,
}

/// Text made of differently styled spans (strings are plain spans).
#[pyfunction]
#[pyo3(signature = (spans, *, size=None, color=None, font=None, line_height=None, width=None,
    align_x=None, wrap=true))]
#[allow(clippy::too_many_arguments)]
pub fn rich_text(
    py: Python<'_>,
    spans: &Bound<'_, PyAny>,
    size: Option<f32>,
    color: Any<'_>,
    font: Option<&str>,
    line_height: Option<f32>,
    width: Any<'_>,
    align_x: Option<&str>,
    wrap: bool,
) -> PyResult<Py<Widget>> {
    let mut parsed = Vec::new();
    for item in crate::widget::flatten(spans)? {
        if let Ok(s) = item.cast::<Span>() {
            parsed.push(s.get().clone());
        } else {
            parsed.push(span(
                &item, None, None, None, None, false, None, 0.0, None, false, false, None,
            )?);
        }
    }
    new(
        py,
        Kind::RichText(Box::new(RichProps {
            spans: parsed,
            size,
            color: style::opt_color(&color)?,
            font: style::font(font, &None, false)?,
            line_height,
            width: style::opt_length(&width)?,
            align_x: style::align_x(align_x)?,
            wrap,
        })),
    )
}

pub fn render_rich<'a>(props: &RichProps) -> Element<'a, Message> {
    let spans: Vec<text::Span<'a, PyMsg, Font>> = props
        .spans
        .iter()
        .map(|s| {
            let mut out = text::Span::new(s.text.clone())
                .underline(s.underline)
                .strikethrough(s.strikethrough)
                .padding(s.padding);
            if let Some(size) = s.size {
                out = out.size(size);
            }
            if let Some(color) = s.color {
                out = out.color(color);
            }
            if let Some(font) = s.font {
                out = out.font(font);
            }
            if let Some(bg) = s.background {
                out = out.background(bg).border(Border {
                    radius: s.radius.into(),
                    ..Border::default()
                });
            }
            if let Some(link) = &s.link {
                out = out.link(link.clone());
            }
            out
        })
        .collect();
    let mut r = widget::rich_text(spans).on_link_click(Message::Py);
    if let Some(size) = props.size {
        r = r.size(size);
    }
    if let Some(color) = props.color {
        r = r.color(color);
    }
    if let Some(font) = props.font {
        r = r.font(font);
    }
    if let Some(lh) = props.line_height {
        r = r.line_height(text::LineHeight::Relative(lh));
    }
    if let Some(w) = props.width {
        r = r.width(w);
    }
    if let Some(a) = props.align_x {
        r = r.align_x(a);
    }
    if !props.wrap {
        r = r.wrapping(text::Wrapping::None);
    }
    r.into()
}

// ---------------------------------------------------------------------------
// Markdown
// ---------------------------------------------------------------------------

pub struct MarkdownProps {
    pub source: String,
    pub key: u64,
    size: f32,
    text_color: Option<Color>,
    link_color: Option<Color>,
    code_color: Option<Color>,
    code_bg: Option<Color>,
    on_link: Option<PyMsg>,
    width: Option<Length>,
}

/// Renders Markdown (headings, lists, code blocks, quotes, tables, links...).
/// `on_link(url)` is called when a link is clicked.
#[pyfunction]
#[pyo3(signature = (source, *, size=14.0, color=None, link_color=None, code_color=None,
    code_bg=None, on_link=None, width=None))]
#[allow(clippy::too_many_arguments)]
pub fn markdown(
    py: Python<'_>,
    source: &str,
    size: f32,
    color: Any<'_>,
    link_color: Any<'_>,
    code_color: Any<'_>,
    code_bg: Any<'_>,
    on_link: Any<'_>,
    width: Any<'_>,
) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Markdown(Box::new(MarkdownProps {
            source: source.to_owned(),
            key: hash_bytes(source.as_bytes()),
            size,
            text_color: style::opt_color(&color)?,
            link_color: style::opt_color(&link_color)?,
            code_color: style::opt_color(&code_color)?,
            code_bg: style::opt_color(&code_bg)?,
            on_link: PyMsg::maybe(&on_link),
            width: style::opt_length(&width)?,
        })),
    )
}

pub fn parse_markdown(source: &str) -> Vec<md::Item> {
    md::parse(source).collect()
}

pub fn render_markdown<'a>(props: &MarkdownProps, items: &'a [md::Item]) -> Element<'a, Message> {
    let link_color = props.link_color;
    let code_color = props.code_color;
    let code_bg = props.code_bg;
    let mut style = md::Style::from_palette(iced::theme::Palette::DARK);
    style.font = Font::with_name(SANS);
    style.inline_code_font = Font::with_name(MONO);
    style.code_block_font = Font::with_name(MONO);
    if let Some(c) = link_color {
        style.link_color = c;
    }
    if let Some(c) = code_color {
        style.inline_code_color = c;
    }
    if let Some(bg) = code_bg {
        style.inline_code_highlight.background = Background::Color(bg);
    }
    let mut settings = md::Settings::with_text_size(props.size, style);
    settings.code_size = Pixels(props.size * 0.9);
    let on_link = props.on_link.clone();
    let view = md::view(items, settings).map(move |url: md::Uri| match &on_link {
        Some(cb) => Python::attach(|py| match url.into_pyobject(py) {
            Ok(value) => Message::Call(cb.clone(), PyMsg::new(value.as_any())),
            Err(_) => Message::Noop,
        }),
        None => Message::Noop,
    });
    let text_color = props.text_color;
    let mut c = widget::container(view).style(move |_| widget::container::Style {
        text_color,
        ..Default::default()
    });
    if let Some(w) = props.width {
        c = c.width(w);
    }
    c.into()
}

// ---------------------------------------------------------------------------
// QR codes
// ---------------------------------------------------------------------------

pub struct QrProps {
    pub data: String,
    pub key: u64,
    cell_size: f32,
    color: Option<Color>,
    background: Option<Color>,
}

/// A QR code encoding `data`.
#[pyfunction]
#[pyo3(signature = (data, *, cell_size=4.0, color=None, bg=None))]
pub fn qr_code(
    py: Python<'_>,
    data: &str,
    cell_size: f32,
    color: Any<'_>,
    bg: Any<'_>,
) -> PyResult<Py<Widget>> {
    if qr::Data::new(data).is_err() {
        return Err(PyValueError::new_err("data is too long for a QR code"));
    }
    new(
        py,
        Kind::QrCode(Box::new(QrProps {
            data: data.to_owned(),
            key: hash_bytes(data.as_bytes()),
            cell_size,
            color: style::opt_color(&color)?,
            background: style::opt_color(&bg)?,
        })),
    )
}

pub fn render_qr<'a>(props: &QrProps, data: &'a qr::Data) -> Element<'a, Message> {
    let (cell, bg) = (
        props.color.unwrap_or(Color::BLACK),
        props.background.unwrap_or(Color::WHITE),
    );
    widget::qr_code(data)
        .cell_size(props.cell_size)
        .style(move |_| qr::Style {
            cell,
            background: bg,
        })
        .into()
}

// ---------------------------------------------------------------------------
// Pick list & radio
// ---------------------------------------------------------------------------

pub struct PickListProps {
    options: Vec<String>,
    selected: Option<String>,
    on_select: Option<PyMsg>,
    placeholder: Option<String>,
    width: Option<Length>,
    padding: Option<Padding>,
    text_size: Option<f32>,
    font: Option<Font>,
    handle: Option<(char, f32)>,
    menu_height: Option<Length>,
    style: PickStyle,
}

#[derive(Clone, Default)]
struct PickStyle {
    bg: Option<Color>,
    text: Option<Color>,
    placeholder: Option<Color>,
    handle: Option<Color>,
    border: Option<Color>,
    hover_border: Option<Color>,
    radius: Option<f32>,
    menu_bg: Option<Color>,
    menu_text: Option<Color>,
    menu_border: Option<Color>,
    selected_bg: Option<Color>,
    selected_text: Option<Color>,
}

/// A dropdown to pick one of `options` (strings). `on_select(option)` receives the choice.
#[pyfunction]
#[pyo3(signature = (options, selected=None, on_select=None, *, placeholder=None, width=None,
    padding=None, text_size=None, font=None, handle=None, handle_size=12.0, menu_height=None,
    bg=None, color=None, placeholder_color=None, handle_color=None, border_color=None,
    hover_border_color=None, radius=None, menu_bg=None, menu_color=None, menu_border_color=None,
    selected_bg=None, selected_color=None))]
#[allow(clippy::too_many_arguments)]
pub fn pick_list(
    py: Python<'_>,
    options: &Bound<'_, PyAny>,
    selected: Option<String>,
    on_select: Any<'_>,
    placeholder: Option<String>,
    width: Any<'_>,
    padding: Any<'_>,
    text_size: Option<f32>,
    font: Option<&str>,
    handle: Option<String>,
    handle_size: f32,
    menu_height: Any<'_>,
    bg: Any<'_>,
    color: Any<'_>,
    placeholder_color: Any<'_>,
    handle_color: Any<'_>,
    border_color: Any<'_>,
    hover_border_color: Any<'_>,
    radius: Option<f32>,
    menu_bg: Any<'_>,
    menu_color: Any<'_>,
    menu_border_color: Any<'_>,
    selected_bg: Any<'_>,
    selected_color: Any<'_>,
) -> PyResult<Py<Widget>> {
    let options = options
        .try_iter()?
        .map(|o| o.and_then(|o| Ok(o.str()?.to_cow()?.into_owned())))
        .collect::<PyResult<Vec<_>>>()?;
    new(
        py,
        Kind::PickList(Box::new(PickListProps {
            options,
            selected,
            on_select: PyMsg::maybe(&on_select),
            placeholder,
            width: style::opt_length(&width)?,
            padding: style::opt_padding(&padding)?,
            text_size,
            font: style::font(font, &None, false)?,
            handle: handle
                .and_then(|h| h.chars().next())
                .map(|c| (c, handle_size)),
            menu_height: style::opt_length(&menu_height)?,
            style: PickStyle {
                bg: style::opt_color(&bg)?,
                text: style::opt_color(&color)?,
                placeholder: style::opt_color(&placeholder_color)?,
                handle: style::opt_color(&handle_color)?,
                border: style::opt_color(&border_color)?,
                hover_border: style::opt_color(&hover_border_color)?,
                radius,
                menu_bg: style::opt_color(&menu_bg)?,
                menu_text: style::opt_color(&menu_color)?,
                menu_border: style::opt_color(&menu_border_color)?,
                selected_bg: style::opt_color(&selected_bg)?,
                selected_text: style::opt_color(&selected_color)?,
            },
        })),
    )
}

pub fn render_pick_list<'a>(props: &PickListProps) -> Element<'a, Message> {
    let cb = props.on_select.clone();
    let mut p = widget::pick_list(
        props.options.clone(),
        props.selected.clone(),
        move |value: String| match &cb {
            Some(cb) => Message::Input(cb.clone(), value),
            None => Message::Noop,
        },
    );
    if let Some(ph) = &props.placeholder {
        p = p.placeholder(ph.clone());
    }
    if let Some(w) = props.width {
        p = p.width(w);
    }
    if let Some(pad) = props.padding {
        p = p.padding(pad);
    }
    if let Some(s) = props.text_size {
        p = p.text_size(s);
    }
    if let Some(f) = props.font {
        p = p.font(f);
    }
    if let Some(h) = props.menu_height {
        p = p.menu_height(h);
    }
    if let Some((code_point, size)) = props.handle {
        p = p.handle(pl::Handle::Static(pl::Icon {
            font: Font::with_name(ICONS),
            code_point,
            size: Some(Pixels(size)),
            line_height: text::LineHeight::Relative(1.0),
            shaping: text::Shaping::Basic,
        }));
    }
    let st = props.style.clone();
    let menu = props.style.clone();
    p.style(move |theme: &Theme, status| {
        let mut out = pl::default(theme, status);
        if let Some(bg) = st.bg {
            out.background = Background::Color(bg);
        }
        if let Some(c) = st.text {
            out.text_color = c;
        }
        if let Some(c) = st.placeholder {
            out.placeholder_color = c;
        }
        if let Some(c) = st.handle {
            out.handle_color = c;
        }
        if let Some(c) = st.border {
            out.border.color = c;
        }
        if let Some(r) = st.radius {
            out.border.radius = r.into();
        }
        if matches!(status, pl::Status::Hovered | pl::Status::Opened { .. })
            && let Some(c) = st.hover_border
        {
            out.border.color = c;
        }
        out
    })
    .menu_style(move |theme: &Theme| {
        let mut out = iced::overlay::menu::default(theme);
        if let Some(bg) = menu.menu_bg {
            out.background = Background::Color(bg);
        }
        if let Some(c) = menu.menu_text {
            out.text_color = c;
        }
        if let Some(c) = menu.menu_border {
            out.border.color = c;
            out.border.width = 1.0;
        }
        if let Some(r) = menu.radius {
            out.border.radius = r.into();
        }
        if let Some(c) = menu.selected_bg {
            out.selected_background = Background::Color(c);
        }
        if let Some(c) = menu.selected_text {
            out.selected_text_color = c;
        }
        out
    })
    .into()
}

pub struct RadioProps {
    label: String,
    selected: bool,
    on_select: Option<PyMsg>,
    size: Option<f32>,
    text_size: Option<f32>,
    spacing: Option<f32>,
    accent: Option<Color>,
    bg: Option<Color>,
    border: Option<Color>,
    text: Option<Color>,
}

/// A radio button. Group several of them yourself; `on_select` is sent when it is clicked.
#[pyfunction]
#[pyo3(signature = (label, selected, on_select=None, *, size=None, text_size=None, spacing=None,
    accent=None, bg=None, border_color=None, color=None))]
#[allow(clippy::too_many_arguments)]
pub fn radio(
    py: Python<'_>,
    label: String,
    selected: bool,
    on_select: Any<'_>,
    size: Option<f32>,
    text_size: Option<f32>,
    spacing: Option<f32>,
    accent: Any<'_>,
    bg: Any<'_>,
    border_color: Any<'_>,
    color: Any<'_>,
) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Radio(Box::new(RadioProps {
            label,
            selected,
            on_select: PyMsg::maybe(&on_select),
            size,
            text_size,
            spacing,
            accent: style::opt_color(&accent)?,
            bg: style::opt_color(&bg)?,
            border: style::opt_color(&border_color)?,
            text: style::opt_color(&color)?,
        })),
    )
}

pub fn render_radio<'a>(props: &RadioProps) -> Element<'a, Message> {
    let msg = match &props.on_select {
        Some(m) => Message::Py(m.clone()),
        None => Message::Noop,
    };
    let mut r = widget::Radio::new(
        props.label.clone(),
        0u8,
        props.selected.then_some(0u8),
        |_| msg,
    );
    if let Some(s) = props.size {
        r = r.size(s);
    }
    if let Some(s) = props.text_size {
        r = r.text_size(s);
    }
    if let Some(s) = props.spacing {
        r = r.spacing(s);
    }
    let (accent, bg, border, text_color) = (props.accent, props.bg, props.border, props.text);
    r.style(move |theme: &Theme, status| {
        let mut out = rd::default(theme, status);
        let selected = match status {
            rd::Status::Active { is_selected } | rd::Status::Hovered { is_selected } => is_selected,
        };
        if let Some(bg) = bg {
            out.background = Background::Color(bg);
        }
        if let Some(a) = accent {
            out.dot_color = a;
            if selected {
                out.border_color = a;
            }
        }
        if let Some(b) = border
            && !selected
        {
            out.border_color = b;
        }
        if text_color.is_some() {
            out.text_color = text_color;
        }
        out
    })
    .into()
}

// ---------------------------------------------------------------------------
// Layout helpers: split, pin, grid, responsive
// ---------------------------------------------------------------------------

pub struct SplitProps {
    pub first: Py<Widget>,
    pub second: Py<Widget>,
    pub vertical: bool,
    pub ratio: f32,
    pub min: (f32, f32),
    pub on_resize: Option<PyMsg>,
    pub color: Option<Color>,
    pub hover_color: Option<Color>,
    pub thickness: f32,
    pub handle: f32,
    pub width: Length,
    pub height: Length,
}

/// Two panes with a draggable divider. `ratio` (0..1) is the first pane's share and
/// `on_resize(ratio)` is called while dragging. `vertical=True` stacks them top/bottom.
#[pyfunction]
#[pyo3(signature = (first, second, *, ratio=0.5, on_resize=None, vertical=false, min_size=80.0,
    min_size_second=None, color=None, hover_color=None, thickness=1.0, handle=8.0, width=None,
    height=None))]
#[allow(clippy::too_many_arguments)]
pub fn split(
    py: Python<'_>,
    first: &Bound<'_, PyAny>,
    second: &Bound<'_, PyAny>,
    ratio: f32,
    on_resize: Any<'_>,
    vertical: bool,
    min_size: f32,
    min_size_second: Option<f32>,
    color: Any<'_>,
    hover_color: Any<'_>,
    thickness: f32,
    handle: f32,
    width: Any<'_>,
    height: Any<'_>,
) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Split(Box::new(SplitProps {
            first: child(first)?,
            second: child(second)?,
            vertical,
            ratio,
            min: (min_size, min_size_second.unwrap_or(min_size)),
            on_resize: PyMsg::maybe(&on_resize),
            color: style::opt_color(&color)?,
            hover_color: style::opt_color(&hover_color)?,
            thickness,
            handle,
            width: style::opt_length(&width)?.unwrap_or(Length::Fill),
            height: style::opt_length(&height)?.unwrap_or(Length::Fill),
        })),
    )
}

/// Places `content` at `(x, y)` inside a box of the given size (use it in a `stack`
/// to position popovers and context menus).
#[pyfunction]
#[pyo3(signature = (content, *, x=0.0, y=0.0, width=None, height=None))]
pub fn pin(
    py: Python<'_>,
    content: &Bound<'_, PyAny>,
    x: f32,
    y: f32,
    width: Any<'_>,
    height: Any<'_>,
) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Pin {
            child: child(content)?,
            x,
            y,
            width: style::opt_length(&width)?.unwrap_or(Length::Fill),
            height: style::opt_length(&height)?.unwrap_or(Length::Fill),
        },
    )
}

/// Lays children out in a grid with a fixed number of `columns`, or as many columns of
/// at most `max_width` as fit (`fluid`). `height` is the row height (number, "fill"...)
/// or `aspect_ratio` keeps cells at width/height.
#[pyfunction]
#[pyo3(signature = (children=None, *, columns=None, max_width=None, spacing=0.0, height=None,
    aspect_ratio=None, width=None))]
#[allow(clippy::too_many_arguments)]
pub fn grid(
    py: Python<'_>,
    children: Any<'_>,
    columns: Option<usize>,
    max_width: Option<f32>,
    spacing: f32,
    height: Any<'_>,
    aspect_ratio: Option<f32>,
    width: Option<f32>,
) -> PyResult<Py<Widget>> {
    if columns.is_none() && max_width.is_none() {
        return Err(PyValueError::new_err("grid needs columns= or max_width="));
    }
    new(
        py,
        Kind::Grid {
            children: crate::widget::children(&children)?,
            columns,
            max_width,
            spacing,
            height: style::opt_length(&height)?,
            aspect_ratio,
            width,
        },
    )
}

/// Builds its content from `function(width, height)` with the space actually available,
/// so a layout can adapt (e.g. hide a sidebar when narrow).
#[pyfunction]
pub fn responsive(py: Python<'_>, function: &Bound<'_, PyAny>) -> PyResult<Py<Widget>> {
    if !function.is_callable() {
        return Err(PyTypeError::new_err(
            "responsive() needs a function (width, height) -> widget",
        ));
    }
    new(py, Kind::Responsive(PyMsg::new(function)))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Span>()?;
    m.add_function(wrap_pyfunction!(self::image, m)?)?;
    m.add_function(wrap_pyfunction!(image_viewer, m)?)?;
    m.add_function(wrap_pyfunction!(canvas, m)?)?;
    m.add_function(wrap_pyfunction!(span, m)?)?;
    m.add_function(wrap_pyfunction!(rich_text, m)?)?;
    m.add_function(wrap_pyfunction!(markdown, m)?)?;
    m.add_function(wrap_pyfunction!(qr_code, m)?)?;
    m.add_function(wrap_pyfunction!(pick_list, m)?)?;
    m.add_function(wrap_pyfunction!(radio, m)?)?;
    m.add_function(wrap_pyfunction!(split, m)?)?;
    m.add_function(wrap_pyfunction!(pin, m)?)?;
    m.add_function(wrap_pyfunction!(grid, m)?)?;
    m.add_function(wrap_pyfunction!(responsive, m)?)?;
    Ok(())
}
