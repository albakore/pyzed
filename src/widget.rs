//! The widget tree that Python builds on every `view()` call.
//!
//! Python never touches iced directly: it builds a tree of lightweight, immutable
//! `Widget` nodes, and `render.rs` turns that tree into real iced elements.

use std::sync::Arc;

use iced::alignment::{Horizontal, Vertical};
use iced::{Color, Font, Length, Padding};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyString, PyTuple};

use crate::extra;
use crate::style::{self, Any, BoxStyle};

/// A Python value used as a message (or a callable producing one).
#[derive(Clone)]
pub struct PyMsg(pub Arc<Py<PyAny>>);

impl PyMsg {
    pub fn new(obj: &Bound<'_, PyAny>) -> Self {
        Self(Arc::new(obj.clone().unbind()))
    }

    pub fn maybe(obj: &Any<'_>) -> Option<Self> {
        obj.as_ref().filter(|o| !o.is_none()).map(Self::new)
    }
}

impl std::fmt::Debug for PyMsg {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("PyMsg")
    }
}

#[derive(Debug, Clone, Default)]
pub struct Layout {
    pub width: Option<Length>,
    pub height: Option<Length>,
    pub padding: Option<Padding>,
    pub max_width: Option<f32>,
    pub max_height: Option<f32>,
}

impl Layout {
    fn new(width: &Any<'_>, height: &Any<'_>, padding: &Any<'_>) -> PyResult<Self> {
        Ok(Self {
            width: style::opt_length(width)?,
            height: style::opt_length(height)?,
            padding: style::opt_padding(padding)?,
            max_width: None,
            max_height: None,
        })
    }
}

#[derive(Debug, Clone)]
pub struct TextProps {
    pub content: String,
    pub size: Option<f32>,
    pub color: Option<Color>,
    pub font: Option<Font>,
    pub line_height: Option<f32>,
    pub align_x: Option<Horizontal>,
    pub align_y: Option<Vertical>,
    pub width: Option<Length>,
    pub height: Option<Length>,
    pub wrap: bool,
}

#[derive(Debug, Clone, Default)]
pub struct ButtonStyle {
    pub base: BoxStyle,
    pub hover_background: Option<Color>,
    pub hover_text_color: Option<Color>,
    pub hover_border_color: Option<Color>,
    pub pressed_background: Option<Color>,
    pub disabled_text_color: Option<Color>,
}

#[derive(Debug, Clone, Default)]
pub struct InputStyle {
    pub background: Option<Color>,
    pub border_color: Option<Color>,
    pub hover_border_color: Option<Color>,
    pub focus_border_color: Option<Color>,
    pub border_width: Option<f32>,
    pub radius: Option<iced::border::Radius>,
    pub text_color: Option<Color>,
    pub placeholder_color: Option<Color>,
    pub selection_color: Option<Color>,
    pub icon_color: Option<Color>,
}

#[derive(Debug, Clone, Default)]
pub struct ScrollStyle {
    pub rail: Option<Color>,
    pub scroller: Option<Color>,
    pub scroller_hover: Option<Color>,
    pub width: f32,
    pub scroller_width: f32,
    pub margin: f32,
}

#[derive(Debug, Clone, Default)]
pub struct ToggleStyle {
    pub accent: Option<Color>,
    pub background: Option<Color>,
    pub border_color: Option<Color>,
    pub foreground: Option<Color>,
    pub text_color: Option<Color>,
}

#[derive(Debug, Clone)]
pub struct EditorProps {
    pub id: Arc<str>,
    pub text: String,
    pub language: String,
    pub size: f32,
    pub line_height: f32,
    pub font: Font,
    pub layout: Layout,
    pub syntax: Vec<(String, Color, bool, bool)>,
    pub background: Option<Color>,
    pub text_color: Option<Color>,
    pub selection_color: Option<Color>,
    pub placeholder: Option<String>,
    pub placeholder_color: Option<Color>,
    pub gutter: bool,
    pub gutter_color: Option<Color>,
    pub gutter_active_color: Option<Color>,
    pub gutter_width: Option<f32>,
    pub markers: Vec<(usize, Color)>,
    pub wrap: bool,
    pub active_line: Option<Color>,
    pub scrollbar_color: Option<Color>,
    pub on_change: Option<PyMsg>,
    pub on_cursor: Option<PyMsg>,
    /// End-of-line virtual text (1-based line, text, color): diagnostics, code lens.
    pub annotations: Vec<(usize, String, Option<Color>)>,
    /// Draw spaces as `·` and tabs as `→` in this color.
    pub whitespace: Option<Color>,
    /// Tab inserts spaces up to the next multiple of `tab_size`; Enter keeps the indentation.
    pub tab_size: Option<usize>,
    /// Keys the editor ignores (handled by the app's `on_key` instead), e.g. `"up"`, `"enter"`.
    pub capture_keys: Vec<String>,
    pub on_scroll: Option<PyMsg>,
    /// Typing a bracket or quote also inserts its closing pair.
    pub auto_close: bool,
    /// Fold chevrons in the gutter and Ctrl+Shift+[ / ] to fold and unfold.
    pub folding: bool,
    pub minimap: Option<MinimapProps>,
    pub cursor: CursorProps,
    /// `on_zoom(step)` with +1, -1 or 0 (reset) for Ctrl+= / Ctrl+- / Ctrl+0 and Ctrl+wheel.
    pub on_zoom: Option<PyMsg>,
}

#[derive(Debug, Clone, Copy)]
pub struct MinimapProps {
    pub width: f32,
    pub thumb: Option<Color>,
}

#[derive(Debug, Clone, Copy)]
pub struct CursorProps {
    pub shape: crate::editor_widgets::CaretShape,
    pub width: f32,
    pub blink: bool,
    pub color: Option<Color>,
}

pub enum Kind {
    Text(TextProps),
    Column {
        children: Vec<Py<Widget>>,
        spacing: f32,
        layout: Layout,
        align: Option<Horizontal>,
        clip: bool,
    },
    Row {
        children: Vec<Py<Widget>>,
        spacing: f32,
        layout: Layout,
        align: Option<Vertical>,
        clip: bool,
        wrap: Option<f32>,
    },
    Container {
        child: Py<Widget>,
        layout: Layout,
        align_x: Option<Horizontal>,
        align_y: Option<Vertical>,
        style: BoxStyle,
        clip: bool,
    },
    Button {
        child: Py<Widget>,
        on_press: Option<PyMsg>,
        layout: Layout,
        style: Option<ButtonStyle>,
        clip: bool,
    },
    TextInput {
        value: String,
        placeholder: String,
        on_input: Option<PyMsg>,
        on_submit: Option<PyMsg>,
        id: Option<String>,
        size: Option<f32>,
        font: Option<Font>,
        layout: Layout,
        secure: bool,
        icon: Option<(char, f32)>,
        align_x: Option<Horizontal>,
        style: InputStyle,
    },
    Scrollable {
        child: Py<Widget>,
        direction: String,
        layout: Layout,
        id: Option<String>,
        anchor_bottom: bool,
        style: ScrollStyle,
        on_scroll: Option<PyMsg>,
    },
    Space {
        width: Length,
        height: Length,
    },
    Rule {
        horizontal: bool,
        thickness: f32,
        color: Option<Color>,
    },
    MouseArea {
        child: Py<Widget>,
        on_press: Option<PyMsg>,
        on_release: Option<PyMsg>,
        on_right_press: Option<PyMsg>,
        on_double_click: Option<PyMsg>,
        on_enter: Option<PyMsg>,
        on_exit: Option<PyMsg>,
        on_move: Option<PyMsg>,
        on_scroll: Option<PyMsg>,
        on_middle_press: Option<PyMsg>,
        cursor: Option<iced::mouse::Interaction>,
    },
    Stack {
        children: Vec<Py<Widget>>,
        layout: Layout,
    },
    Opaque {
        child: Py<Widget>,
    },
    Hover {
        base: Py<Widget>,
        top: Py<Widget>,
    },
    Tooltip {
        child: Py<Widget>,
        tip: Py<Widget>,
        position: String,
        gap: f32,
        style: BoxStyle,
    },
    Checkbox {
        checked: bool,
        label: Option<String>,
        on_toggle: Option<PyMsg>,
        size: Option<f32>,
        text_size: Option<f32>,
        style: ToggleStyle,
    },
    Toggler {
        checked: bool,
        label: Option<String>,
        on_toggle: Option<PyMsg>,
        size: Option<f32>,
        text_size: Option<f32>,
        style: ToggleStyle,
    },
    Slider {
        min: f32,
        max: f32,
        value: f32,
        step: f32,
        on_change: Option<PyMsg>,
        on_release: Option<PyMsg>,
        width: Option<Length>,
        height: Option<Length>,
        vertical: bool,
        style: ToggleStyle,
    },
    ProgressBar {
        min: f32,
        max: f32,
        value: f32,
        width: Option<Length>,
        height: Option<Length>,
        style: ToggleStyle,
        radius: f32,
    },
    Editor(Box<EditorProps>),
    Svg {
        source: SvgSource,
        width: Option<Length>,
        height: Option<Length>,
        color: Option<Color>,
        fit: Option<iced::ContentFit>,
        opacity: f32,
        rotation: f32,
    },
    Image(Box<extra::ImageProps>),
    Canvas(Arc<extra::CanvasProps>),
    RichText(Box<extra::RichProps>),
    Markdown(Box<extra::MarkdownProps>),
    QrCode(Box<extra::QrProps>),
    PickList(Box<extra::PickListProps>),
    Radio(Box<extra::RadioProps>),
    Split(Box<extra::SplitProps>),
    Pin {
        child: Py<Widget>,
        x: f32,
        y: f32,
        width: Length,
        height: Length,
    },
    Grid {
        children: Vec<Py<Widget>>,
        columns: Option<usize>,
        max_width: Option<f32>,
        spacing: f32,
        height: Option<Length>,
        aspect_ratio: Option<f32>,
        width: Option<f32>,
    },
    Responsive(PyMsg),
    /// A grid with sized column and row tracks (`grid(columns=[...])`).
    TrackGrid(Box<crate::layout::TrackGridProps>),
    /// A child placed in a track grid cell (`cell(...)`).
    Cell {
        child: Py<Widget>,
        placement: crate::layout::Placement,
    },
    Resizable(Box<crate::layout::ResizableProps>),
    /// Common events attached with `.on(...)` (see `events.rs`).
    Events {
        child: Py<Widget>,
        handlers: crate::events::Handlers,
        cursor: Option<iced::mouse::Interaction>,
    },
    Styled(Box<crate::styled::StyleProps>),
}

pub enum SvgSource {
    Path(String),
    Bytes(Vec<u8>),
}

/// An immutable node of the UI tree. Create them with the functions in `pyzed`.
#[pyclass(module = "pyzed._core", frozen)]
pub struct Widget {
    pub kind: Kind,
}

#[pymethods]
impl Widget {
    fn __repr__(&self) -> String {
        let name = match &self.kind {
            Kind::Text(t) => return format!("<Widget text {:?}>", t.content),
            Kind::Column { children, .. } => {
                return format!("<Widget column [{}]>", children.len());
            }
            Kind::Row { children, .. } => return format!("<Widget row [{}]>", children.len()),
            Kind::Container { .. } => "container",
            Kind::Button { .. } => "button",
            Kind::TextInput { .. } => "text_input",
            Kind::Scrollable { .. } => "scrollable",
            Kind::Space { .. } => "space",
            Kind::Rule { .. } => "rule",
            Kind::MouseArea { .. } => "mouse_area",
            Kind::Stack { .. } => "stack",
            Kind::Opaque { .. } => "opaque",
            Kind::Hover { .. } => "hover",
            Kind::Tooltip { .. } => "tooltip",
            Kind::Checkbox { .. } => "checkbox",
            Kind::Toggler { .. } => "toggler",
            Kind::Slider { .. } => "slider",
            Kind::ProgressBar { .. } => "progress_bar",
            Kind::Editor(_) => "code_editor",
            Kind::Svg { .. } => "svg",
            Kind::Image(_) => "image",
            Kind::Canvas(_) => "canvas",
            Kind::RichText(_) => "rich_text",
            Kind::Markdown(_) => "markdown",
            Kind::QrCode(_) => "qr_code",
            Kind::PickList(_) => "pick_list",
            Kind::Radio(_) => "radio",
            Kind::Split(_) => "split",
            Kind::Pin { .. } => "pin",
            Kind::Grid { .. } => "grid",
            Kind::Responsive(_) => "responsive",
            Kind::TrackGrid(props) => return format!("<Widget grid [{}]>", props.children.len()),
            Kind::Cell { child, .. } => {
                let inner = Python::attach(|py| child.bind(py).get().__repr__());
                return format!("<Widget cell {inner}>");
            }
            Kind::Resizable(_) => "resizable",
            Kind::Styled(props) => {
                let inner = Python::attach(|py| props.child.bind(py).get().__repr__());
                return format!("{inner}.style()");
            }
            Kind::Events {
                child, handlers, ..
            } => {
                let names: Vec<&str> = handlers.0.iter().map(|(k, _)| k.name()).collect();
                let inner = Python::attach(|py| child.bind(py).get().__repr__());
                return format!("{inner}.on({})", names.join(", "));
            }
        };
        format!("<Widget {name}>")
    }

    /// Styles the widget like CSS and returns the wrapped widget.
    ///
    /// Accepts ``pz.Style`` objects, dicts and names given to ``pz.define_style``, then
    /// properties by keyword (later ones win): ``background``, ``color``, ``font``,
    /// ``weight``, ``italic``, ``size``, ``line_height``, ``border_color``,
    /// ``border_width``, ``radius``, ``shadow``, ``padding``, ``margin``, ``width``,
    /// ``height``, ``max_width``, ``max_height``, ``align_x``, ``align_y`` and ``clip``.
    /// Text properties apply to every text inside; with ``defaults=True`` they only fill in
    /// what texts don't set themselves (how ``App.style`` works). Calling ``style`` again merges.
    #[pyo3(signature = (*styles, defaults=false, **props))]
    fn style(
        slf: &Bound<'_, Self>,
        styles: &Bound<'_, pyo3::types::PyTuple>,
        defaults: bool,
        props: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Py<Widget>> {
        crate::styled::apply(slf, styles, defaults, props)
    }

    /// The style properties set with ``style()`` (an empty dict if none).
    fn style_props<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyDict>> {
        match &slf.get().kind {
            Kind::Styled(props) => Ok(props.source.bind(slf.py()).copy()?),
            _ => Ok(PyDict::new(slf.py())),
        }
    }

    /// Attaches common event handlers and returns the wrapped widget.
    ///
    /// Events: click, double_click, right_click, middle_click, mouse_down, mouse_up,
    /// mouse_enter, mouse_leave, mouse_move, scroll, drag_start, drag, drag_end, focus,
    /// blur, key_down, key_up and resize (names may also start with ``on_``). Each
    /// handler is a callable (called with a ``pyzed.Event`` if it takes an argument) or
    /// a message for ``update``; ``None`` removes a handler. ``cursor`` sets the mouse
    /// cursor shown over the widget. Calling ``on`` again merges the handlers.
    #[pyo3(signature = (*, cursor=None, **handlers))]
    fn on(
        slf: &Bound<'_, Self>,
        cursor: Option<&str>,
        handlers: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Py<Widget>> {
        let py = slf.py();
        let (child, mut merged, mut pointer) = match &slf.get().kind {
            Kind::Events {
                child,
                handlers,
                cursor,
            } => (child.clone_ref(py), handlers.clone(), *cursor),
            _ => (
                slf.clone().unbind(),
                crate::events::Handlers::default(),
                None,
            ),
        };
        if let Some(cursor) = cursor {
            pointer = extra::parse_cursor(Some(cursor))?;
        }
        if let Some(handlers) = handlers {
            for (name, handler) in handlers.iter() {
                let name: String = name.extract()?;
                let kind = crate::events::EventKind::parse(&name).ok_or_else(|| {
                    let known: Vec<&str> = crate::events::EventKind::ALL
                        .iter()
                        .map(|k| k.name())
                        .collect();
                    PyValueError::new_err(format!(
                        "unknown event {name:?}; available events: {}",
                        known.join(", ")
                    ))
                })?;
                if handler.is_none() {
                    merged.remove(kind);
                } else {
                    merged.set(kind, PyMsg::new(&handler));
                }
            }
        }
        new(
            py,
            Kind::Events {
                child,
                handlers: merged,
                cursor: pointer,
            },
        )
    }
}

/// The names of the common events, in catalog order.
#[pyfunction]
pub fn event_names() -> Vec<&'static str> {
    crate::events::EventKind::ALL
        .iter()
        .map(|k| k.name())
        .collect()
}

pub fn new(py: Python<'_>, kind: Kind) -> PyResult<Py<Widget>> {
    Py::new(py, Widget { kind })
}

fn plain_text(py: Python<'_>, content: String) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Text(TextProps {
            content,
            size: None,
            color: None,
            font: None,
            line_height: None,
            align_x: None,
            align_y: None,
            width: None,
            height: None,
            wrap: true,
        }),
    )
}

/// Accepts a Widget, a string (turned into text) or a number.
pub fn child(value: &Bound<'_, PyAny>) -> PyResult<Py<Widget>> {
    let py = value.py();
    if let Ok(w) = value.cast::<Widget>() {
        return Ok(w.clone().unbind());
    }
    if let Ok(s) = value.cast::<PyString>() {
        return plain_text(py, s.to_cow()?.into_owned());
    }
    if value.is_none() {
        return new(
            py,
            Kind::Space {
                width: Length::Shrink,
                height: Length::Shrink,
            },
        );
    }
    if value.extract::<f64>().is_ok() {
        return plain_text(py, value.str()?.to_cow()?.into_owned());
    }
    Err(PyValueError::new_err(format!(
        "expected a Widget or str, got {}",
        value.get_type().name()?
    )))
}

/// Flattens nested lists/tuples/iterables into a flat list, skipping `None` and `False`.
pub fn flatten<'py>(value: &Bound<'py, PyAny>) -> PyResult<Vec<Bound<'py, PyAny>>> {
    fn collect<'py>(value: &Bound<'py, PyAny>, out: &mut Vec<Bound<'py, PyAny>>) -> PyResult<()> {
        if value.is_none() {
            return Ok(());
        }
        if let Ok(flag) = value.cast::<pyo3::types::PyBool>()
            && !flag.is_true()
        {
            return Ok(());
        }
        if value.cast::<PyList>().is_ok() || value.cast::<PyTuple>().is_ok() {
            for item in value.try_iter()? {
                collect(&item?, out)?;
            }
            return Ok(());
        }
        out.push(value.clone());
        Ok(())
    }
    let mut out = Vec::new();
    collect(value, &mut out)?;
    Ok(out)
}

/// Flattens nested lists/tuples of children, skipping `None` and `False`.
pub fn children(value: &Any<'_>) -> PyResult<Vec<Py<Widget>>> {
    fn collect(value: &Bound<'_, PyAny>, out: &mut Vec<Py<Widget>>) -> PyResult<()> {
        if value.is_none() {
            return Ok(());
        }
        if let Ok(flag) = value.cast::<pyo3::types::PyBool>()
            && !flag.is_true()
        {
            return Ok(());
        }
        if value.cast::<PyList>().is_ok()
            || value.cast::<PyTuple>().is_ok()
            || (value.hasattr("__iter__")?
                && !value.cast::<PyString>().is_ok()
                && value.cast::<Widget>().is_err())
        {
            for item in value.try_iter()? {
                collect(&item?, out)?;
            }
            return Ok(());
        }
        out.push(child(value)?);
        Ok(())
    }
    let mut out = Vec::new();
    if let Some(value) = value {
        collect(value, &mut out)?;
    }
    Ok(out)
}

fn icon_char(value: &Any<'_>) -> PyResult<Option<char>> {
    match value {
        Some(v) if !v.is_none() => {
            let s: String = v.extract()?;
            Ok(s.chars().next())
        }
        _ => Ok(None),
    }
}

// ---------------------------------------------------------------------------
// Constructors exposed to Python
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (content, *, size=None, color=None, font=None, weight=None, italic=false,
    line_height=None, align_x=None, align_y=None, width=None, height=None, wrap=true))]
#[allow(clippy::too_many_arguments)]
pub fn text(
    py: Python<'_>,
    content: &Bound<'_, PyAny>,
    size: Option<f32>,
    color: Any<'_>,
    font: Option<&str>,
    weight: Any<'_>,
    italic: bool,
    line_height: Option<f32>,
    align_x: Option<&str>,
    align_y: Option<&str>,
    width: Any<'_>,
    height: Any<'_>,
    wrap: bool,
) -> PyResult<Py<Widget>> {
    let content = match content.cast::<PyString>() {
        Ok(s) => s.to_cow()?.into_owned(),
        Err(_) => content.str()?.to_cow()?.into_owned(),
    };
    new(
        py,
        Kind::Text(TextProps {
            content,
            size,
            color: style::opt_color(&color)?,
            font: style::font(font, &weight, italic)?,
            line_height,
            align_x: style::align_x(align_x)?,
            align_y: style::align_y(align_y)?,
            width: style::opt_length(&width)?,
            height: style::opt_length(&height)?,
            wrap,
        }),
    )
}

#[pyfunction]
#[pyo3(signature = (children=None, *, spacing=0.0, padding=None, width=None, height=None,
    align=None, max_width=None, clip=false))]
#[allow(clippy::too_many_arguments)]
pub fn column(
    py: Python<'_>,
    children: Any<'_>,
    spacing: f32,
    padding: Any<'_>,
    width: Any<'_>,
    height: Any<'_>,
    align: Option<&str>,
    max_width: Option<f32>,
    clip: bool,
) -> PyResult<Py<Widget>> {
    let mut layout = Layout::new(&width, &height, &padding)?;
    layout.max_width = max_width;
    new(
        py,
        Kind::Column {
            children: self::children(&children)?,
            spacing,
            layout,
            align: style::align_x(align)?,
            clip,
        },
    )
}

#[pyfunction]
#[pyo3(signature = (children=None, *, spacing=0.0, padding=None, width=None, height=None,
    align=None, clip=false, wrap=false, line_spacing=None))]
#[allow(clippy::too_many_arguments)]
pub fn row(
    py: Python<'_>,
    children: Any<'_>,
    spacing: f32,
    padding: Any<'_>,
    width: Any<'_>,
    height: Any<'_>,
    align: Option<&str>,
    clip: bool,
    wrap: bool,
    line_spacing: Option<f32>,
) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Row {
            children: self::children(&children)?,
            spacing,
            layout: Layout::new(&width, &height, &padding)?,
            align: style::align_y(align)?,
            clip,
            wrap: wrap.then_some(line_spacing.unwrap_or(spacing)),
        },
    )
}

#[pyfunction]
#[pyo3(signature = (content=None, *, padding=None, width=None, height=None, max_width=None,
    max_height=None, align_x=None, align_y=None, center=false, bg=None, color=None,
    border_color=None, border_width=0.0, radius=None, shadow=None, clip=false, gradient=None))]
#[allow(clippy::too_many_arguments)]
pub fn container(
    py: Python<'_>,
    content: Any<'_>,
    padding: Any<'_>,
    width: Any<'_>,
    height: Any<'_>,
    max_width: Option<f32>,
    max_height: Option<f32>,
    align_x: Option<&str>,
    align_y: Option<&str>,
    center: bool,
    bg: Any<'_>,
    color: Any<'_>,
    border_color: Any<'_>,
    border_width: f32,
    radius: Any<'_>,
    shadow: Any<'_>,
    clip: bool,
    gradient: Any<'_>,
) -> PyResult<Py<Widget>> {
    let mut layout = Layout::new(&width, &height, &padding)?;
    layout.max_width = max_width;
    layout.max_height = max_height;
    let (mut ax, mut ay) = (style::align_x(align_x)?, style::align_y(align_y)?);
    if center {
        ax = ax.or(Some(Horizontal::Center));
        ay = ay.or(Some(Vertical::Center));
        layout.width = layout.width.or(Some(Length::Fill));
        layout.height = layout.height.or(Some(Length::Fill));
    }
    let child = match &content {
        Some(c) => self::child(c)?,
        None => new(
            py,
            Kind::Space {
                width: Length::Shrink,
                height: Length::Shrink,
            },
        )?,
    };
    new(
        py,
        Kind::Container {
            child,
            layout,
            align_x: ax,
            align_y: ay,
            style: {
                let mut s =
                    style::box_style(&bg, &color, &border_color, border_width, &radius, &shadow)?;
                s.gradient = style::gradient(&gradient)?;
                s
            },
            clip,
        },
    )
}

#[pyfunction]
#[pyo3(signature = (content, on_press=None, *, padding=None, width=None, height=None, bg=None,
    color=None, border_color=None, border_width=0.0, radius=None, shadow=None, hover_bg=None,
    hover_color=None, hover_border_color=None, pressed_bg=None, disabled_color=None, clip=false))]
#[allow(clippy::too_many_arguments)]
pub fn button(
    py: Python<'_>,
    content: &Bound<'_, PyAny>,
    on_press: Any<'_>,
    padding: Any<'_>,
    width: Any<'_>,
    height: Any<'_>,
    bg: Any<'_>,
    color: Any<'_>,
    border_color: Any<'_>,
    border_width: f32,
    radius: Any<'_>,
    shadow: Any<'_>,
    hover_bg: Any<'_>,
    hover_color: Any<'_>,
    hover_border_color: Any<'_>,
    pressed_bg: Any<'_>,
    disabled_color: Any<'_>,
    clip: bool,
) -> PyResult<Py<Widget>> {
    let base = style::box_style(&bg, &color, &border_color, border_width, &radius, &shadow)?;
    let style = ButtonStyle {
        base,
        hover_background: style::opt_color(&hover_bg)?,
        hover_text_color: style::opt_color(&hover_color)?,
        hover_border_color: style::opt_color(&hover_border_color)?,
        pressed_background: style::opt_color(&pressed_bg)?,
        disabled_text_color: style::opt_color(&disabled_color)?,
    };
    let customized = !style.base.is_empty()
        || style.hover_background.is_some()
        || style.hover_text_color.is_some()
        || style.pressed_background.is_some();
    new(
        py,
        Kind::Button {
            child: self::child(content)?,
            on_press: PyMsg::maybe(&on_press),
            layout: Layout::new(&width, &height, &padding)?,
            style: customized.then_some(style),
            clip,
        },
    )
}

#[pyfunction]
#[pyo3(signature = (value, *, placeholder="", on_input=None, on_submit=None, id=None, size=None,
    font=None, padding=None, width=None, secure=false, icon=None, icon_size=None, bg=None,
    border_color=None, hover_border_color=None, focus_border_color=None, border_width=None,
    radius=None, color=None, placeholder_color=None, selection_color=None, icon_color=None, align_x=None))]
#[allow(clippy::too_many_arguments)]
pub fn text_input(
    py: Python<'_>,
    value: &str,
    placeholder: &str,
    on_input: Any<'_>,
    on_submit: Any<'_>,
    id: Option<String>,
    size: Option<f32>,
    font: Option<&str>,
    padding: Any<'_>,
    width: Any<'_>,
    secure: bool,
    icon: Any<'_>,
    icon_size: Option<f32>,
    bg: Any<'_>,
    border_color: Any<'_>,
    hover_border_color: Any<'_>,
    focus_border_color: Any<'_>,
    border_width: Option<f32>,
    radius: Any<'_>,
    color: Any<'_>,
    placeholder_color: Any<'_>,
    selection_color: Any<'_>,
    icon_color: Any<'_>,
    align_x: Option<&str>,
) -> PyResult<Py<Widget>> {
    let radius = match &radius {
        Some(r) if !r.is_none() => Some(style::radius(&Some(r.clone()))?),
        _ => None,
    };
    new(
        py,
        Kind::TextInput {
            value: value.to_owned(),
            placeholder: placeholder.to_owned(),
            on_input: PyMsg::maybe(&on_input),
            on_submit: PyMsg::maybe(&on_submit),
            id,
            size,
            font: style::font(font, &None, false)?,
            layout: Layout::new(&width, &None, &padding)?,
            secure,
            icon: icon_char(&icon)?.map(|c| (c, icon_size.unwrap_or(14.0))),
            align_x: style::align_x(align_x)?,
            style: InputStyle {
                background: style::opt_color(&bg)?,
                border_color: style::opt_color(&border_color)?,
                hover_border_color: style::opt_color(&hover_border_color)?,
                focus_border_color: style::opt_color(&focus_border_color)?,
                border_width,
                radius,
                text_color: style::opt_color(&color)?,
                placeholder_color: style::opt_color(&placeholder_color)?,
                selection_color: style::opt_color(&selection_color)?,
                icon_color: style::opt_color(&icon_color)?,
            },
        },
    )
}

#[pyfunction]
#[pyo3(signature = (content, *, direction="vertical", width=None, height=None, padding=None,
    id=None, anchor_bottom=false, rail=None, scroller=None, scroller_hover=None,
    scrollbar_width=8.0, scroller_width=None, margin=0.0, on_scroll=None))]
#[allow(clippy::too_many_arguments)]
pub fn scrollable(
    py: Python<'_>,
    content: &Bound<'_, PyAny>,
    direction: &str,
    width: Any<'_>,
    height: Any<'_>,
    padding: Any<'_>,
    id: Option<String>,
    anchor_bottom: bool,
    rail: Any<'_>,
    scroller: Any<'_>,
    scroller_hover: Any<'_>,
    scrollbar_width: f32,
    scroller_width: Option<f32>,
    margin: f32,
    on_scroll: Any<'_>,
) -> PyResult<Py<Widget>> {
    if !matches!(direction, "vertical" | "horizontal" | "both") {
        return Err(PyValueError::new_err(
            "direction must be 'vertical', 'horizontal' or 'both'",
        ));
    }
    new(
        py,
        Kind::Scrollable {
            child: self::child(content)?,
            direction: direction.to_owned(),
            layout: Layout::new(&width, &height, &padding)?,
            id,
            anchor_bottom,
            style: ScrollStyle {
                rail: style::opt_color(&rail)?,
                scroller: style::opt_color(&scroller)?,
                scroller_hover: style::opt_color(&scroller_hover)?,
                width: scrollbar_width,
                scroller_width: scroller_width.unwrap_or(scrollbar_width),
                margin,
            },
            on_scroll: PyMsg::maybe(&on_scroll),
        },
    )
}

#[pyfunction]
#[pyo3(signature = (width=None, height=None))]
pub fn space(py: Python<'_>, width: Any<'_>, height: Any<'_>) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Space {
            width: style::opt_length(&width)?.unwrap_or(Length::Shrink),
            height: style::opt_length(&height)?.unwrap_or(Length::Shrink),
        },
    )
}

#[pyfunction]
#[pyo3(signature = (*, vertical=false, thickness=1.0, color=None))]
pub fn rule(
    py: Python<'_>,
    vertical: bool,
    thickness: f32,
    color: Any<'_>,
) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Rule {
            horizontal: !vertical,
            thickness,
            color: style::opt_color(&color)?,
        },
    )
}

#[pyfunction]
#[pyo3(signature = (content, *, on_press=None, on_release=None, on_right_press=None,
    on_double_click=None, on_enter=None, on_exit=None, on_move=None, on_scroll=None,
    on_middle_press=None, cursor=None))]
#[allow(clippy::too_many_arguments)]
pub fn mouse_area(
    py: Python<'_>,
    content: &Bound<'_, PyAny>,
    on_press: Any<'_>,
    on_release: Any<'_>,
    on_right_press: Any<'_>,
    on_double_click: Any<'_>,
    on_enter: Any<'_>,
    on_exit: Any<'_>,
    on_move: Any<'_>,
    on_scroll: Any<'_>,
    on_middle_press: Any<'_>,
    cursor: Option<&str>,
) -> PyResult<Py<Widget>> {
    let cursor = extra::parse_cursor(cursor)?;
    new(
        py,
        Kind::MouseArea {
            child: self::child(content)?,
            on_press: PyMsg::maybe(&on_press),
            on_release: PyMsg::maybe(&on_release),
            on_right_press: PyMsg::maybe(&on_right_press),
            on_double_click: PyMsg::maybe(&on_double_click),
            on_enter: PyMsg::maybe(&on_enter),
            on_exit: PyMsg::maybe(&on_exit),
            on_move: PyMsg::maybe(&on_move),
            on_scroll: PyMsg::maybe(&on_scroll),
            on_middle_press: PyMsg::maybe(&on_middle_press),
            cursor,
        },
    )
}

#[pyfunction]
#[pyo3(signature = (children=None, *, width=None, height=None))]
pub fn stack(
    py: Python<'_>,
    children: Any<'_>,
    width: Any<'_>,
    height: Any<'_>,
) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Stack {
            children: self::children(&children)?,
            layout: Layout::new(&width, &height, &None)?,
        },
    )
}

/// Makes a widget block mouse interactions with whatever sits below it in a `stack`.
#[pyfunction]
pub fn opaque(py: Python<'_>, content: &Bound<'_, PyAny>) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Opaque {
            child: child(content)?,
        },
    )
}

/// Shows `top` over `base` only while the mouse hovers it.
#[pyfunction]
pub fn hover(
    py: Python<'_>,
    base: &Bound<'_, PyAny>,
    top: &Bound<'_, PyAny>,
) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Hover {
            base: child(base)?,
            top: child(top)?,
        },
    )
}

#[pyfunction]
#[pyo3(signature = (content, tip, *, position="bottom", gap=4.0, bg=None, color=None,
    border_color=None, border_width=0.0, radius=None, shadow=None))]
#[allow(clippy::too_many_arguments)]
pub fn tooltip(
    py: Python<'_>,
    content: &Bound<'_, PyAny>,
    tip: &Bound<'_, PyAny>,
    position: &str,
    gap: f32,
    bg: Any<'_>,
    color: Any<'_>,
    border_color: Any<'_>,
    border_width: f32,
    radius: Any<'_>,
    shadow: Any<'_>,
) -> PyResult<Py<Widget>> {
    if !matches!(position, "top" | "bottom" | "left" | "right" | "cursor") {
        return Err(PyValueError::new_err(
            "position must be top, bottom, left, right or cursor",
        ));
    }
    new(
        py,
        Kind::Tooltip {
            child: child(content)?,
            tip: child(tip)?,
            position: position.to_owned(),
            gap,
            style: style::box_style(&bg, &color, &border_color, border_width, &radius, &shadow)?,
        },
    )
}

fn toggle_style(
    accent: &Any<'_>,
    bg: &Any<'_>,
    border_color: &Any<'_>,
    fg: &Any<'_>,
    color: &Any<'_>,
) -> PyResult<ToggleStyle> {
    Ok(ToggleStyle {
        accent: style::opt_color(accent)?,
        background: style::opt_color(bg)?,
        border_color: style::opt_color(border_color)?,
        foreground: style::opt_color(fg)?,
        text_color: style::opt_color(color)?,
    })
}

#[pyfunction]
#[pyo3(signature = (checked, label=None, *, on_toggle=None, size=None, text_size=None,
    accent=None, bg=None, border_color=None, check_color=None, color=None))]
#[allow(clippy::too_many_arguments)]
pub fn checkbox(
    py: Python<'_>,
    checked: bool,
    label: Option<String>,
    on_toggle: Any<'_>,
    size: Option<f32>,
    text_size: Option<f32>,
    accent: Any<'_>,
    bg: Any<'_>,
    border_color: Any<'_>,
    check_color: Any<'_>,
    color: Any<'_>,
) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Checkbox {
            checked,
            label,
            on_toggle: PyMsg::maybe(&on_toggle),
            size,
            text_size,
            style: toggle_style(&accent, &bg, &border_color, &check_color, &color)?,
        },
    )
}

#[pyfunction]
#[pyo3(signature = (checked, label=None, *, on_toggle=None, size=None, text_size=None,
    accent=None, bg=None, border_color=None, knob_color=None, color=None))]
#[allow(clippy::too_many_arguments)]
pub fn toggler(
    py: Python<'_>,
    checked: bool,
    label: Option<String>,
    on_toggle: Any<'_>,
    size: Option<f32>,
    text_size: Option<f32>,
    accent: Any<'_>,
    bg: Any<'_>,
    border_color: Any<'_>,
    knob_color: Any<'_>,
    color: Any<'_>,
) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Toggler {
            checked,
            label,
            on_toggle: PyMsg::maybe(&on_toggle),
            size,
            text_size,
            style: toggle_style(&accent, &bg, &border_color, &knob_color, &color)?,
        },
    )
}

#[pyfunction]
#[pyo3(signature = (min, max, value, *, step=1.0, on_change=None, on_release=None, width=None,
    height=None, vertical=false, accent=None, bg=None, knob_color=None, border_color=None))]
#[allow(clippy::too_many_arguments)]
pub fn slider(
    py: Python<'_>,
    min: f32,
    max: f32,
    value: f32,
    step: f32,
    on_change: Any<'_>,
    on_release: Any<'_>,
    width: Any<'_>,
    height: Any<'_>,
    vertical: bool,
    accent: Any<'_>,
    bg: Any<'_>,
    knob_color: Any<'_>,
    border_color: Any<'_>,
) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::Slider {
            min,
            max,
            value,
            step,
            on_change: PyMsg::maybe(&on_change),
            on_release: PyMsg::maybe(&on_release),
            width: style::opt_length(&width)?,
            height: style::opt_length(&height)?,
            vertical,
            style: toggle_style(&accent, &bg, &border_color, &knob_color, &None)?,
        },
    )
}

#[pyfunction]
#[pyo3(signature = (value, *, min=0.0, max=1.0, width=None, height=None, accent=None, bg=None, radius=2.0))]
#[allow(clippy::too_many_arguments)]
pub fn progress_bar(
    py: Python<'_>,
    value: f32,
    min: f32,
    max: f32,
    width: Any<'_>,
    height: Any<'_>,
    accent: Any<'_>,
    bg: Any<'_>,
    radius: f32,
) -> PyResult<Py<Widget>> {
    new(
        py,
        Kind::ProgressBar {
            min,
            max,
            value,
            width: style::opt_length(&width)?,
            height: style::opt_length(&height)?,
            style: toggle_style(&accent, &bg, &None, &None, &None)?,
            radius,
        },
    )
}

/// A code editor backed by iced's `text_editor`, with syntax highlighting and a gutter.
///
/// Editors are *uncontrolled*: `text` is only the initial value for a given `id`.
/// Use `Command.set_editor_text` to replace the contents later.
#[pyfunction]
#[pyo3(signature = (id, text="", *, language="txt", size=14.0, line_height=None, font=None,
    width=None, height=None, padding=None, syntax=None, bg=None, color=None, selection_color=None,
    placeholder=None, placeholder_color=None, gutter=true, gutter_color=None,
    gutter_active_color=None, gutter_width=None, markers=None, wrap=false, on_change=None,
    on_cursor=None, active_line=None, scrollbar_color=None, annotations=None, whitespace=None,
    tab_size=None, capture_keys=None, on_scroll=None, auto_close=false, folding=false,
    minimap=None, minimap_thumb=None, cursor_shape="bar", cursor_width=2.0, cursor_blink=true,
    cursor_color=None, on_zoom=None))]
#[allow(clippy::too_many_arguments)]
pub fn code_editor(
    py: Python<'_>,
    id: &str,
    text: &str,
    language: &str,
    size: f32,
    line_height: Option<f32>,
    font: Option<&str>,
    width: Any<'_>,
    height: Any<'_>,
    padding: Any<'_>,
    syntax: Option<Bound<'_, PyDict>>,
    bg: Any<'_>,
    color: Any<'_>,
    selection_color: Any<'_>,
    placeholder: Option<String>,
    placeholder_color: Any<'_>,
    gutter: bool,
    gutter_color: Any<'_>,
    gutter_active_color: Any<'_>,
    gutter_width: Option<f32>,
    markers: Option<Bound<'_, PyDict>>,
    wrap: bool,
    on_change: Any<'_>,
    on_cursor: Any<'_>,
    active_line: Any<'_>,
    scrollbar_color: Any<'_>,
    annotations: Option<Bound<'_, PyDict>>,
    whitespace: Any<'_>,
    tab_size: Option<usize>,
    capture_keys: Option<Vec<String>>,
    on_scroll: Any<'_>,
    auto_close: bool,
    folding: bool,
    minimap: Option<f32>,
    minimap_thumb: Any<'_>,
    cursor_shape: &str,
    cursor_width: f32,
    cursor_blink: bool,
    cursor_color: Any<'_>,
    on_zoom: Any<'_>,
) -> PyResult<Py<Widget>> {
    let shape = crate::editor_widgets::CaretShape::parse(cursor_shape).ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err(format!(
            "cursor_shape must be \"bar\", \"block\", \"underline\" or \"hollow\", not {cursor_shape:?}"
        ))
    })?;
    // syntax: {"keyword": "#b477cf", "comment": ("#5d636f", "italic"), ...}
    let mut rules = Vec::new();
    if let Some(syntax) = syntax {
        for (scope, value) in syntax.iter() {
            let scope: String = scope.extract()?;
            let (color_value, flags) = match value.cast::<PyTuple>() {
                Ok(t) if t.len() == 2 => (t.get_item(0)?, t.get_item(1)?.extract::<String>()?),
                _ => (value.clone(), String::new()),
            };
            rules.push((
                scope,
                style::color(&color_value)?,
                flags.contains("italic"),
                flags.contains("bold"),
            ));
        }
    }
    let mut marker_list = Vec::new();
    if let Some(markers) = markers {
        for (line, value) in markers.iter() {
            marker_list.push((line.extract::<usize>()?, style::color(&value)?));
        }
    }
    // annotations: {3: "2 references", 7: ("undefined name", "#e06c75")}
    let mut annotation_list = Vec::new();
    if let Some(annotations) = annotations {
        for (line, value) in annotations.iter() {
            let (label, color) = match value.cast::<PyTuple>() {
                Ok(t) if t.len() == 2 => (
                    t.get_item(0)?.extract::<String>()?,
                    style::opt_color(&Some(t.get_item(1)?))?,
                ),
                _ => (value.extract::<String>()?, None),
            };
            annotation_list.push((line.extract::<usize>()?, label, color));
        }
    }
    let font = style::font(Some(font.unwrap_or("mono")), &None, false)?.unwrap_or(Font::MONOSPACE);
    new(
        py,
        Kind::Editor(Box::new(EditorProps {
            id: Arc::from(id),
            text: text.to_owned(),
            language: language.to_owned(),
            size,
            line_height: line_height.unwrap_or((size * 1.6).round()),
            font,
            layout: Layout::new(&width, &height, &padding)?,
            syntax: rules,
            background: style::opt_color(&bg)?,
            text_color: style::opt_color(&color)?,
            selection_color: style::opt_color(&selection_color)?,
            placeholder,
            placeholder_color: style::opt_color(&placeholder_color)?,
            gutter,
            gutter_color: style::opt_color(&gutter_color)?,
            gutter_active_color: style::opt_color(&gutter_active_color)?,
            gutter_width,
            markers: marker_list,
            wrap,
            active_line: style::opt_color(&active_line)?,
            scrollbar_color: style::opt_color(&scrollbar_color)?,
            annotations: annotation_list,
            whitespace: style::opt_color(&whitespace)?,
            tab_size: tab_size.filter(|n| *n > 0),
            capture_keys: capture_keys.unwrap_or_default(),
            on_scroll: PyMsg::maybe(&on_scroll),
            auto_close,
            folding,
            minimap: match minimap {
                Some(width) if width > 0.0 => Some(MinimapProps {
                    width,
                    thumb: style::opt_color(&minimap_thumb)?,
                }),
                _ => None,
            },
            cursor: CursorProps {
                shape,
                width: cursor_width,
                blink: cursor_blink,
                color: style::opt_color(&cursor_color)?,
            },
            on_zoom: PyMsg::maybe(&on_zoom),
            on_change: PyMsg::maybe(&on_change),
            on_cursor: PyMsg::maybe(&on_cursor),
        })),
    )
}

#[pyfunction]
#[pyo3(signature = (source, *, width=None, height=None, color=None, content_fit=None,
    opacity=1.0, rotation=0.0))]
#[allow(clippy::too_many_arguments)]
pub fn svg(
    py: Python<'_>,
    source: &Bound<'_, PyAny>,
    width: Any<'_>,
    height: Any<'_>,
    color: Any<'_>,
    content_fit: Option<&str>,
    opacity: f32,
    rotation: f32,
) -> PyResult<Py<Widget>> {
    let source = if let Ok(bytes) = source.cast::<pyo3::types::PyBytes>() {
        SvgSource::Bytes(bytes.as_bytes().to_vec())
    } else {
        let s: String = source.extract()?;
        if s.trim_start().starts_with('<') {
            SvgSource::Bytes(s.into_bytes())
        } else {
            SvgSource::Path(s)
        }
    };
    new(
        py,
        Kind::Svg {
            source,
            width: style::opt_length(&width)?,
            height: style::opt_length(&height)?,
            color: style::opt_color(&color)?,
            fit: match content_fit {
                None => None,
                Some("contain") => Some(iced::ContentFit::Contain),
                Some("cover") => Some(iced::ContentFit::Cover),
                Some("fill") => Some(iced::ContentFit::Fill),
                Some("none") => Some(iced::ContentFit::None),
                Some("scale-down" | "scale_down") => Some(iced::ContentFit::ScaleDown),
                Some(other) => {
                    return Err(PyValueError::new_err(format!(
                        "invalid content_fit {other:?}"
                    )));
                }
            },
            opacity,
            rotation,
        },
    )
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Widget>()?;
    m.add_function(wrap_pyfunction!(text, m)?)?;
    m.add_function(wrap_pyfunction!(column, m)?)?;
    m.add_function(wrap_pyfunction!(row, m)?)?;
    m.add_function(wrap_pyfunction!(container, m)?)?;
    m.add_function(wrap_pyfunction!(button, m)?)?;
    m.add_function(wrap_pyfunction!(text_input, m)?)?;
    m.add_function(wrap_pyfunction!(scrollable, m)?)?;
    m.add_function(wrap_pyfunction!(space, m)?)?;
    m.add_function(wrap_pyfunction!(rule, m)?)?;
    m.add_function(wrap_pyfunction!(mouse_area, m)?)?;
    m.add_function(wrap_pyfunction!(event_names, m)?)?;
    m.add_function(wrap_pyfunction!(stack, m)?)?;
    m.add_function(wrap_pyfunction!(opaque, m)?)?;
    m.add_function(wrap_pyfunction!(hover, m)?)?;
    m.add_function(wrap_pyfunction!(tooltip, m)?)?;
    m.add_function(wrap_pyfunction!(checkbox, m)?)?;
    m.add_function(wrap_pyfunction!(toggler, m)?)?;
    m.add_function(wrap_pyfunction!(slider, m)?)?;
    m.add_function(wrap_pyfunction!(progress_bar, m)?)?;
    m.add_function(wrap_pyfunction!(code_editor, m)?)?;
    m.add_function(wrap_pyfunction!(svg, m)?)?;
    Ok(())
}
