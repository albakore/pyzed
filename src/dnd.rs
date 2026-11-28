//! Drag and drop: things the pointer can pick up (`draggable`), places that take them
//! (`droppable`) and lists whose items reorder and move between lists (`sortable`).
//!
//! Everything that moves during a drag happens here, natively, without calling Python per
//! frame: the preview that follows the pointer, the items that slide aside to open a gap, the
//! shadow (or translucent ghost) where the item will land, snapping and alignment guides, the
//! wire of a node editor, scrolling near the edges and the animations when an item is dropped
//! or the drag is cancelled. Python hears about the moments that matter: start, enter, leave,
//! over (when the landing place changes), drop and end.
//!
//! There is one pointer, so one drag at a time: its state is one thread-local [`Session`].
//! [`Root`] wraps every window's view. Before an event reaches the widgets it moves the
//! session's pointer; while the event goes through the tree, the drop targets under the pointer
//! that accept the dragged item register as candidates (the innermost wins); after it, `Root`
//! commits the winner, tells Python what changed and ends the drag on release.
//!
//! The session keeps window coordinates. Widgets inside scrollables see their layout and the
//! cursor in content coordinates; [`shift`] is the difference.

use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};

use iced::advanced::Renderer as _;
use iced::advanced::graphics::geometry::Renderer as _;
use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer::{self, Quad};
use iced::advanced::widget::{self, Tree, Widget};
use iced::advanced::{Clipboard, Shell, mouse, overlay};
use iced::keyboard::{self, Modifiers};
use iced::widget::canvas::{self, Path, Stroke};
use iced::{
    Alignment, Border, Color, Element, Event, Length, Padding, Point, Rectangle, Shadow, Size,
    Theme, Transformation, Vector, touch, window,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use crate::app::Message;
use crate::widget::{Kind, PyMsg, Widget as Node};

type Renderer = iced::Renderer;

/// How long the rest of the app waits for Python to apply a drop before items show where they
/// were again (when the handler changed nothing).
const DONE_HOLD: Duration = Duration::from_millis(400);
/// Distance from a scrolling area's edge where a drag scrolls it.
const EDGE: f32 = 48.0;
/// Fastest automatic scroll, in pixels per frame.
const EDGE_SPEED: f32 = 18.0;
/// How close (pixels) an edge or center must be for an alignment guide to snap.
const GUIDE_SNAP: f32 = 6.0;

// ---------------------------------------------------------------------------
// Options (built from the dicts `pyzed.dnd` passes)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Axis {
    X,
    Y,
}

/// Where the preview may go.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Bounds {
    Free,
    Window,
    /// Inside the closest drop target or sortable around the draggable.
    Parent,
}

/// How the dragged item looks at its original place while it is dragged.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Source {
    /// Drawn with this opacity.
    Ghost(f32),
    Hide,
    Keep,
}

/// What follows the pointer.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Preview {
    /// A copy of the item (or the `preview` widget given).
    Item,
    /// A curve from where the drag started to the pointer, like the cables of a node editor.
    Wire,
    /// Nothing: only the targets react.
    Nothing,
}

/// A target's look while something it accepts is dragged (`active`) or is over it (`over`).
#[derive(Debug, Clone, Copy, Default)]
pub struct Highlight {
    pub background: Option<Color>,
    pub border: Option<Color>,
    pub width: f32,
    pub radius: f32,
}

impl Highlight {
    fn is_empty(&self) -> bool {
        self.background.is_none() && self.border.is_none()
    }

    fn draw(&self, renderer: &mut Renderer, bounds: Rectangle) {
        if self.is_empty() {
            return;
        }
        renderer.fill_quad(
            Quad {
                bounds,
                border: Border {
                    color: self.border.unwrap_or(Color::TRANSPARENT),
                    width: if self.border.is_some() {
                        self.width
                    } else {
                        0.0
                    },
                    radius: self.radius.into(),
                    ..Default::default()
                },
                ..Default::default()
            },
            self.background.unwrap_or(Color::TRANSPARENT),
        );
    }
}

/// What a target shows where the item would land.
#[derive(Debug, Clone, Copy)]
pub enum Placeholder {
    Nothing,
    /// A filled shape the size of the item.
    Shadow(Highlight),
    /// A translucent copy of the item (drawn by the preview).
    Ghost(f32),
}

pub struct DragProps {
    pub id: Arc<str>,
    pub types: Arc<[String]>,
    pub data: Option<PyMsg>,
    pub disabled: bool,
    pub handle: bool,
    pub axis: Option<Axis>,
    pub bounds: Bounds,
    pub grid: Option<(f32, f32)>,
    pub threshold: f32,
    pub delay: Duration,
    pub source: Source,
    pub preview: Preview,
    pub lift: f32,
    pub shadow: Option<Color>,
    pub opacity: f32,
    pub radius: f32,
    pub wire: (Color, f32),
    pub drop_ms: f32,
    pub from_children: bool,
    pub cursor: bool,
    pub on_start: Option<PyMsg>,
    pub on_move: Option<PyMsg>,
    pub on_end: Option<PyMsg>,
    /// Set by a sortable for its items: the list, the item's index and whether dropping
    /// elsewhere copies it (`pull="clone"`) or is not allowed (`pull=False`).
    pub list: Option<Arc<str>>,
    pub index: usize,
    pub copy: bool,
    pub stay: bool,
}

pub struct DropProps {
    pub id: Arc<str>,
    pub accepts: Option<Arc<[String]>>,
    pub can_drop: Option<PyMsg>,
    pub disabled: bool,
    pub snap: Option<(f32, f32)>,
    pub guides: bool,
    pub snap_preview: bool,
    pub placeholder: Placeholder,
    pub active: Highlight,
    pub over: Highlight,
    pub guide_color: Color,
    pub on_drop: Option<PyMsg>,
    pub on_enter: Option<PyMsg>,
    pub on_leave: Option<PyMsg>,
    pub on_over: Option<PyMsg>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Direction {
    Vertical,
    Horizontal,
    /// Rows that wrap, like a grid of cards.
    Wrap,
}

pub struct SortProps {
    pub target: Arc<DropProps>,
    pub children: Vec<Py<Node>>,
    pub keys: Vec<Arc<str>>,
    pub data: Vec<Option<PyMsg>>,
    pub locked: Vec<bool>,
    pub item: ItemTemplate,
    pub direction: Direction,
    pub spacing: f32,
    pub line_spacing: f32,
    pub width: Length,
    pub height: Length,
    pub padding: Padding,
    pub align: Alignment,
    /// Items may change places inside this list.
    pub sort: bool,
    pub max_items: Option<usize>,
    pub combine: bool,
    pub animation: f32,
    pub draggable: bool,
}

/// The drag options a sortable gives each of its items.
pub struct ItemTemplate {
    pub types: Arc<[String]>,
    pub handle: bool,
    pub lock_axis: bool,
    pub source: Source,
    pub preview: Preview,
    pub lift: f32,
    pub shadow: Option<Color>,
    pub opacity: f32,
    pub radius: f32,
    pub threshold: f32,
    pub delay: Duration,
    pub drop_ms: f32,
    pub from_children: bool,
    pub copy: bool,
    pub stay: bool,
    pub on_start: Option<PyMsg>,
    pub on_end: Option<PyMsg>,
}

fn item<'py>(opts: &Bound<'py, PyDict>, key: &str) -> PyResult<Option<Bound<'py, PyAny>>> {
    Ok(opts.get_item(key)?.filter(|v| !v.is_none()))
}

fn f32_or(opts: &Bound<'_, PyDict>, key: &str, default: f32) -> PyResult<f32> {
    item(opts, key)?.map_or(Ok(default), |v| v.extract::<f32>())
}

fn bool_or(opts: &Bound<'_, PyDict>, key: &str, default: bool) -> PyResult<bool> {
    item(opts, key)?.map_or(Ok(default), |v| v.is_truthy())
}

fn string(opts: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<String>> {
    item(opts, key)?
        .map(|v| v.str()?.extract::<String>())
        .transpose()
}

fn strings(opts: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<Arc<[String]>>> {
    let Some(value) = item(opts, key)? else {
        return Ok(None);
    };
    if let Ok(s) = value.extract::<String>() {
        return Ok(Some(vec![s].into()));
    }
    let mut out = Vec::new();
    for v in value.try_iter()? {
        out.push(v?.str()?.extract::<String>()?);
    }
    Ok(Some(out.into()))
}

fn msg(opts: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<PyMsg>> {
    Ok(item(opts, key)?.map(|v| PyMsg::new(&v)))
}

fn color(opts: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<Color>> {
    item(opts, key)?
        .map(|v| crate::style::color(&v))
        .transpose()
}

fn pair(opts: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<(f32, f32)>> {
    let Some(value) = item(opts, key)? else {
        return Ok(None);
    };
    if let Ok(n) = value.extract::<f32>() {
        return Ok((n > 0.0).then_some((n, n)));
    }
    let (x, y): (f32, f32) = value.extract()?;
    Ok((x > 0.0 && y > 0.0).then_some((x, y)))
}

fn highlight(opts: &Bound<'_, PyDict>, key: &str) -> PyResult<Highlight> {
    let Some(value) = item(opts, key)? else {
        return Ok(Highlight::default());
    };
    let d = value.cast::<PyDict>()?;
    Ok(Highlight {
        background: color(d, "background")?,
        border: color(d, "border_color")?,
        width: f32_or(d, "border_width", 1.0)?,
        radius: f32_or(d, "radius", 0.0)?,
    })
}

fn source(opts: &Bound<'_, PyDict>) -> PyResult<Source> {
    Ok(match string(opts, "source")?.as_deref() {
        None | Some("ghost") => Source::Ghost(f32_or(opts, "source_opacity", 0.35)?),
        Some("hide") => Source::Hide,
        Some("keep") => Source::Keep,
        Some(other) => {
            return Err(PyValueError::new_err(format!(
                "source must be 'ghost', 'hide' or 'keep', not {other:?}"
            )));
        }
    })
}

fn preview(opts: &Bound<'_, PyDict>) -> PyResult<Preview> {
    Ok(match string(opts, "preview_mode")?.as_deref() {
        None | Some("item") => Preview::Item,
        Some("wire") => Preview::Wire,
        Some("none") => Preview::Nothing,
        Some(other) => {
            return Err(PyValueError::new_err(format!(
                "preview must be a widget, 'wire' or 'none', not {other:?}"
            )));
        }
    })
}

fn duration(opts: &Bound<'_, PyDict>, key: &str) -> PyResult<Duration> {
    Ok(Duration::from_secs_f32(
        f32_or(opts, key, 0.0)?.max(0.0) / 1000.0,
    ))
}

pub fn drag_props(opts: &Bound<'_, PyDict>) -> PyResult<DragProps> {
    let id = string(opts, "id")?.ok_or_else(|| PyValueError::new_err("a draggable needs an id"))?;
    Ok(DragProps {
        id: id.into(),
        types: strings(opts, "type")?.unwrap_or_else(|| vec!["item".to_owned()].into()),
        data: msg(opts, "data")?,
        disabled: bool_or(opts, "disabled", false)?,
        handle: bool_or(opts, "handle", false)?,
        axis: match string(opts, "axis")?.as_deref() {
            None => None,
            Some("x") => Some(Axis::X),
            Some("y") => Some(Axis::Y),
            Some(other) => {
                return Err(PyValueError::new_err(format!(
                    "axis must be 'x' or 'y', not {other:?}"
                )));
            }
        },
        bounds: match string(opts, "bounds")?.as_deref() {
            None => Bounds::Free,
            Some("window") => Bounds::Window,
            Some("parent") => Bounds::Parent,
            Some(other) => {
                return Err(PyValueError::new_err(format!(
                    "bounds must be 'window' or 'parent', not {other:?}"
                )));
            }
        },
        grid: pair(opts, "grid")?,
        threshold: f32_or(opts, "threshold", 4.0)?,
        delay: duration(opts, "delay")?,
        source: source(opts)?,
        preview: preview(opts)?,
        lift: f32_or(opts, "lift", 1.03)?,
        shadow: color(opts, "shadow")?,
        opacity: f32_or(opts, "opacity", 1.0)?,
        radius: f32_or(opts, "radius", 6.0)?,
        wire: (
            color(opts, "wire_color")?.unwrap_or(Color::from_rgb8(0x74, 0xad, 0xe8)),
            f32_or(opts, "wire_width", 2.0)?,
        ),
        drop_ms: f32_or(opts, "drop_animation", 180.0)?,
        from_children: bool_or(opts, "from_children", false)?,
        cursor: bool_or(opts, "cursor", true)?,
        on_start: msg(opts, "on_drag_start")?,
        on_move: msg(opts, "on_drag_move")?,
        on_end: msg(opts, "on_drag_end")?,
        list: None,
        index: 0,
        copy: false,
        stay: false,
    })
}

pub fn drop_props(opts: &Bound<'_, PyDict>) -> PyResult<DropProps> {
    let id =
        string(opts, "id")?.ok_or_else(|| PyValueError::new_err("a drop target needs an id"))?;
    let placeholder = match string(opts, "placeholder")?.as_deref() {
        None | Some("none") => Placeholder::Nothing,
        Some("shadow") => Placeholder::Shadow(highlight(opts, "placeholder_style")?),
        Some("ghost") => Placeholder::Ghost(f32_or(opts, "ghost_opacity", 0.4)?),
        Some(other) => {
            return Err(PyValueError::new_err(format!(
                "placeholder must be 'shadow', 'ghost' or 'none', not {other:?}"
            )));
        }
    };
    Ok(DropProps {
        id: id.into(),
        accepts: strings(opts, "accepts")?,
        can_drop: msg(opts, "can_drop")?,
        disabled: bool_or(opts, "disabled", false)?,
        snap: pair(opts, "snap")?,
        guides: bool_or(opts, "guides", false)?,
        snap_preview: bool_or(opts, "snap_preview", false)?,
        placeholder,
        active: highlight(opts, "active_style")?,
        over: highlight(opts, "over_style")?,
        guide_color: color(opts, "guide_color")?.unwrap_or(Color::from_rgb8(0xe0, 0x4f, 0xa0)),
        on_drop: msg(opts, "on_drop")?,
        on_enter: msg(opts, "on_enter")?,
        on_leave: msg(opts, "on_leave")?,
        on_over: msg(opts, "on_over")?,
    })
}

// ---------------------------------------------------------------------------
// Python
// ---------------------------------------------------------------------------

/// Makes `content` draggable (see `pyzed.dnd.draggable`, which fills in the options).
#[pyfunction]
#[pyo3(signature = (content, preview, options))]
pub fn _draggable(
    py: Python<'_>,
    content: &Bound<'_, PyAny>,
    preview: Option<&Bound<'_, PyAny>>,
    options: &Bound<'_, PyDict>,
) -> PyResult<Py<Node>> {
    let preview = preview
        .filter(|p| !p.is_none() && !p.is_instance_of::<pyo3::types::PyString>())
        .map(crate::widget::child)
        .transpose()?;
    crate::widget::new(
        py,
        Kind::Draggable {
            child: crate::widget::child(content)?,
            preview,
            props: Arc::new(drag_props(options)?),
        },
    )
}

/// Makes `content` a drop target (see `pyzed.dnd.droppable`).
#[pyfunction]
pub fn _droppable(
    py: Python<'_>,
    content: &Bound<'_, PyAny>,
    options: &Bound<'_, PyDict>,
) -> PyResult<Py<Node>> {
    crate::widget::new(
        py,
        Kind::Droppable {
            child: crate::widget::child(content)?,
            props: Arc::new(drop_props(options)?),
        },
    )
}

/// The part of a draggable (made with `handle=True`) that starts the drag.
///
/// Inside a ``pz.draggable(..., handle=True)`` or the items of a ``pz.sortable(...,
/// handle=True)``, only a press on ``content`` starts a drag: the rest of the item keeps its
/// clicks, text selection and inputs. ``cursor`` is shown over it (``"grab"`` by default).
#[pyfunction]
#[pyo3(signature = (content, *, cursor=Some("grab")))]
pub fn drag_handle(
    py: Python<'_>,
    content: &Bound<'_, PyAny>,
    cursor: Option<&str>,
) -> PyResult<Py<Node>> {
    crate::widget::new(
        py,
        Kind::DragHandle {
            child: crate::widget::child(content)?,
            cursor: crate::extra::parse_cursor(cursor)?,
        },
    )
}

/// A list whose items can be dragged to reorder them (see `pyzed.dnd.sortable`).
#[pyfunction]
pub fn _sortable(
    py: Python<'_>,
    children: &Bound<'_, PyList>,
    options: &Bound<'_, PyDict>,
) -> PyResult<Py<Node>> {
    let count = children.len();
    let mut nodes = Vec::with_capacity(count);
    for child in children.iter() {
        nodes.push(crate::widget::child(&child)?);
    }
    let keys: Vec<Arc<str>> = match item(options, "keys")? {
        Some(keys) => {
            let mut out = Vec::new();
            for key in keys.try_iter()? {
                out.push(Arc::from(key?.str()?.extract::<String>()?));
            }
            out
        }
        None => (0..count).map(|i| Arc::from(i.to_string())).collect(),
    };
    if keys.len() != count {
        return Err(PyValueError::new_err(format!(
            "sortable got {count} children and {} keys",
            keys.len()
        )));
    }
    let data = match item(options, "data")? {
        Some(values) => {
            let mut out = Vec::new();
            for value in values.try_iter()? {
                out.push(Some(PyMsg::new(&value?)));
            }
            out
        }
        None => vec![None; count],
    };
    let locked_keys: Vec<String> = match item(options, "locked")? {
        Some(v) => {
            let mut out = Vec::new();
            for key in v.try_iter()? {
                out.push(key?.str()?.extract::<String>()?);
            }
            out
        }
        None => Vec::new(),
    };
    let locked = keys
        .iter()
        .map(|k| locked_keys.iter().any(|l| **l == **k))
        .collect();
    let target = drop_props(options)?;
    let group = strings(options, "group")?;
    let types = group
        .clone()
        .unwrap_or_else(|| vec![format!("sortable:{}", target.id)].into());
    let pull = item(options, "pull")?;
    let (copy, stay) = match pull {
        Some(p) if p.extract::<String>().is_ok_and(|s| s == "clone") => (true, false),
        Some(p) => (false, !p.is_truthy()?),
        None => (false, false),
    };
    let direction = match string(options, "direction")?.as_deref() {
        None | Some("vertical") => Direction::Vertical,
        Some("horizontal") => Direction::Horizontal,
        Some("wrap") | Some("grid") => Direction::Wrap,
        Some(other) => {
            return Err(PyValueError::new_err(format!(
                "direction must be 'vertical', 'horizontal' or 'wrap', not {other:?}"
            )));
        }
    };
    let spacing = f32_or(options, "spacing", 0.0)?;
    let width = crate::style::opt_length(&item(options, "width")?)?;
    let height = crate::style::opt_length(&item(options, "height")?)?;
    let padding = crate::style::opt_padding(&item(options, "padding")?)?.unwrap_or_default();
    let align = match string(options, "align")?.as_deref() {
        None | Some("start") | Some("left") | Some("top") => Alignment::Start,
        Some("center") => Alignment::Center,
        Some("end") | Some("right") | Some("bottom") => Alignment::End,
        Some(other) => {
            return Err(PyValueError::new_err(format!(
                "align must be 'start', 'center' or 'end', not {other:?}"
            )));
        }
    };
    let mut target = target;
    if target.accepts.is_none() {
        target.accepts = Some(strings(options, "put_types")?.unwrap_or_else(|| types.clone()));
    }
    let put = bool_or(options, "put", true)?;
    let props = SortProps {
        children: nodes,
        keys,
        data,
        locked,
        item: ItemTemplate {
            types,
            handle: bool_or(options, "handle", false)?,
            lock_axis: bool_or(options, "lock_axis", false)?,
            source: source(options)?,
            preview: preview(options)?,
            lift: f32_or(options, "lift", 1.03)?,
            shadow: color(options, "shadow")?,
            opacity: f32_or(options, "opacity", 1.0)?,
            radius: f32_or(options, "radius", 6.0)?,
            threshold: f32_or(options, "threshold", 4.0)?,
            delay: duration(options, "delay")?,
            drop_ms: f32_or(options, "drop_animation", 180.0)?,
            from_children: bool_or(options, "from_children", false)?,
            copy,
            stay,
            on_start: msg(options, "on_drag_start")?,
            on_end: msg(options, "on_drag_end")?,
        },
        direction,
        spacing,
        line_spacing: f32_or(options, "line_spacing", spacing)?,
        width: width.unwrap_or(match direction {
            Direction::Horizontal => Length::Shrink,
            _ => Length::Fill,
        }),
        height: height.unwrap_or(Length::Shrink),
        padding,
        align,
        sort: bool_or(options, "sort", true)?,
        max_items: item(options, "max_items")?
            .map(|v| v.extract())
            .transpose()?,
        combine: bool_or(options, "combine", false)?,
        animation: f32_or(options, "animation", 200.0)?,
        draggable: bool_or(options, "draggable", true)?,
        target: Arc::new(DropProps {
            disabled: target.disabled || !put,
            ..target
        }),
    };
    crate::widget::new(py, Kind::Sortable(Arc::new(props)))
}

/// The drag in progress, as a dict (`None` when nothing is dragged): what `pz.dnd.current()`
/// returns, for views that change while something is dragged.
#[pyfunction]
pub fn _current(py: Python<'_>) -> PyResult<Option<Py<PyAny>>> {
    SESSION.with(|s| {
        // Asked from a `can_drop` while a target is testing the drag: nothing new to say.
        let Ok(session) = s.try_borrow() else {
            return Ok(None);
        };
        match session.as_ref() {
            Some(session) if session.phase == Phase::Dragging => Ok(Some(
                event(py, "current", session, session.over.as_ref())?.unbind(),
            )),
            _ => Ok(None),
        }
    })
}

/// Cancels the drag in progress, if any (the preview goes back).
#[pyfunction]
pub fn _cancel() {
    SESSION.with(|s| {
        if let Some(session) = s.borrow_mut().as_mut()
            && session.phase == Phase::Dragging
        {
            session.cancel_requested = true;
        }
    });
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(_draggable, m)?)?;
    m.add_function(wrap_pyfunction!(_droppable, m)?)?;
    m.add_function(wrap_pyfunction!(_sortable, m)?)?;
    m.add_function(wrap_pyfunction!(drag_handle, m)?)?;
    m.add_function(wrap_pyfunction!(_current, m)?)?;
    m.add_function(wrap_pyfunction!(_cancel, m)?)?;
    Ok(())
}

/// Builds a `pyzed.dnd.DragEvent` for `kind` from the session and the target.
fn event<'py>(
    py: Python<'py>,
    kind: &str,
    session: &Session,
    target: Option<&Target>,
) -> PyResult<Bound<'py, PyAny>> {
    let kw = PyDict::new(py);
    kw.set_item("source", &*session.source)?;
    kw.set_item(
        "data",
        session
            .data
            .as_ref()
            .map(|d| d.0.bind(py).clone())
            .unwrap_or_else(|| pyo3::types::PyString::new(py, &session.source).into_any()),
    )?;
    kw.set_item("types", session.types.to_vec())?;
    kw.set_item("from_list", session.list.as_deref())?;
    kw.set_item("from_index", session.list.as_ref().map(|_| session.index))?;
    kw.set_item("copy", session.copy || session.modifiers.alt())?;
    kw.set_item("window_x", session.pointer.x)?;
    kw.set_item("window_y", session.pointer.y)?;
    kw.set_item("dx", session.pointer.x - session.start.x)?;
    kw.set_item("dy", session.pointer.y - session.start.y)?;
    kw.set_item("width", session.origin.width)?;
    kw.set_item("height", session.origin.height)?;
    kw.set_item("shift", session.modifiers.shift())?;
    kw.set_item("ctrl", session.modifiers.control())?;
    kw.set_item("alt", session.modifiers.alt())?;
    kw.set_item("logo", session.modifiers.logo())?;
    if let Some(t) = target {
        kw.set_item("target", &*t.id)?;
        kw.set_item("index", t.index)?;
        kw.set_item("combine", t.combine.as_deref())?;
        kw.set_item("x", session.pointer.x - t.bounds.x)?;
        kw.set_item("y", session.pointer.y - t.bounds.y)?;
        kw.set_item("item_x", t.item.x)?;
        kw.set_item("item_y", t.item.y)?;
    }
    py.import("pyzed.dnd")?
        .getattr("DragEvent")?
        .call((kind,), Some(&kw))
}

fn publish(
    shell: &mut Shell<'_, Message>,
    handler: Option<&PyMsg>,
    make: impl FnOnce(Python<'_>) -> PyResult<Bound<'_, PyAny>>,
) {
    let Some(handler) = handler else { return };
    Python::attach(|py| match make(py) {
        Ok(value) => shell.publish(Message::Dnd(handler.clone(), PyMsg::new(&value))),
        Err(err) => err.print(py),
    });
}

// ---------------------------------------------------------------------------
// Shared state
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq)]
enum Phase {
    Dragging,
    /// Released: the preview flies from `from` to `to` (landing on a target or going back).
    Flying {
        from: Point,
        to: Point,
        start: Instant,
        dropped: bool,
    },
    /// Dropped and reported: waiting for Python's new view (items stay where they were shown).
    Done(Instant),
}

/// The drag in progress.
pub struct Session {
    window: Option<window::Id>,
    source: Arc<str>,
    list: Option<Arc<str>>,
    index: usize,
    types: Arc<[String]>,
    data: Option<PyMsg>,
    props: Arc<DragProps>,
    copy: bool,
    stay: bool,
    /// Where the item was (window coordinates) when the drag started.
    origin: Rectangle,
    /// The pointer minus the item's top-left when the drag started.
    grab: Vector,
    start: Point,
    pointer: Point,
    /// The preview's top-left following the pointer (constrained, before a target snaps it).
    free: Point,
    /// Where the preview is drawn now.
    preview: Point,
    /// Scale of the lifted preview (animates from 1 to `props.lift`).
    lifted: f32,
    constraint: Option<Rectangle>,
    over: Option<Target>,
    /// The pointer is over a target that does not take this item.
    rejected: bool,
    modifiers: Modifiers,
    phase: Phase,
    /// `can_drop` answers, by target id.
    checked: HashMap<Arc<str>, bool>,
    cancel_requested: bool,
    last_over: Option<LastOver>,
}

/// The last landing place told to Python: index, combine key and where the item lands.
type LastOver = (Option<usize>, Option<Arc<str>>, (i32, i32));

/// The item just dropped: its key, the list it landed in, where it was shown and when.
type Landed = (Arc<str>, Arc<str>, Point, Instant);

impl Session {
    fn dragging(&self) -> bool {
        self.phase == Phase::Dragging
    }

    /// Whether `types` (a target's `accepts`) takes the dragged item.
    fn accepted_by(&self, accepts: &Option<Arc<[String]>>) -> bool {
        match accepts {
            None => true,
            Some(list) => list
                .iter()
                .any(|a| a == "*" || self.types.iter().any(|t| t == a)),
        }
    }

    fn size(&self) -> Size {
        self.origin.size()
    }

    fn preview_rect(&self) -> Rectangle {
        Rectangle::new(self.preview, self.size())
    }

    /// The point targets test: the pointer, or the preview's center when the preview can't
    /// follow the pointer everywhere (an axis lock or bounds).
    fn probe(&self) -> Point {
        if self.props.axis.is_some() || self.constraint.is_some() {
            Rectangle::new(self.free, self.size()).center()
        } else {
            self.pointer
        }
    }
}

/// A drop target under the pointer that takes the dragged item.
#[derive(Clone)]
struct Target {
    id: Arc<str>,
    bounds: Rectangle,
    clip: Rectangle,
    depth: u32,
    index: Option<usize>,
    /// Where the list shows the gap: the index, or the last one while combining.
    gap: Option<usize>,
    combine: Option<Arc<str>>,
    /// The landing top-left relative to the target.
    item: Point,
    /// Where the item would land (window coordinates).
    landing: Option<Rectangle>,
    snap_preview: bool,
    ghost: Option<f32>,
    guides: Vec<(Point, Point)>,
    guide_color: Color,
    on_drop: Option<PyMsg>,
    on_enter: Option<PyMsg>,
    on_leave: Option<PyMsg>,
    on_over: Option<PyMsg>,
}

/// What one event's trip through a window's widgets found.
#[derive(Default)]
struct Pass {
    best: Option<Target>,
    rejected: bool,
    /// Draggable items seen (window coordinates), for alignment guides.
    items: Vec<(Arc<str>, Rectangle)>,
    /// A drag handle under the pointer was pressed.
    handle: bool,
    /// A draggable took this press (the ones around it don't start a drag).
    claimed: bool,
    depth: u32,
    /// Bounds of the drop targets around the widget being updated (innermost last).
    parents: Vec<Rectangle>,
}

/// A sortable item's animation: its offset from its place in the layout.
#[derive(Clone, Copy, Default)]
struct ItemAnim {
    offset: Vector,
    /// Where it was laid out last time (relative to the list).
    last: Option<Vector>,
}

#[derive(Default)]
struct ListAnim {
    items: HashMap<Arc<str>, ItemAnim>,
    frame: Option<Instant>,
    size: Option<Size>,
}

thread_local! {
    static SESSION: RefCell<Option<Session>> = const { RefCell::new(None) };
    static PASS: RefCell<Pass> = RefCell::new(Pass::default());
    /// The pointer in window coordinates, as the root saw it last.
    static POINTER: Cell<Option<Point>> = const { Cell::new(None) };
    static WINDOW: Cell<Option<window::Id>> = const { Cell::new(None) };
    /// The bounds of the window's view being updated.
    static VIEW: Cell<Option<Rectangle>> = const { Cell::new(None) };
    /// Inside the item being dragged: its own drop targets don't take it.
    static SUPPRESS: Cell<u32> = const { Cell::new(0) };
    static LISTS: RefCell<HashMap<Arc<str>, ListAnim>> = RefCell::new(HashMap::new());
    /// The item just dropped and where it was shown, so its list animates it from there.
    static LANDED: RefCell<Option<Landed>> = const { RefCell::new(None) };
}

fn with_session<R>(f: impl FnOnce(&Session) -> R) -> Option<R> {
    SESSION.with(|s| s.borrow().as_ref().map(f))
}

/// The active session in the window being updated.
fn here<R>(f: impl FnOnce(&Session) -> R) -> Option<R> {
    let window = WINDOW.get();
    SESSION.with(|s| {
        s.borrow()
            .as_ref()
            .filter(|s| s.window.is_none() || window.is_none() || s.window == window)
            .map(f)
    })
}

/// Content coordinates minus window coordinates for a widget that got `cursor`.
fn shift(cursor: mouse::Cursor) -> Option<Vector> {
    let at = match cursor {
        mouse::Cursor::Available(p) | mouse::Cursor::Levitating(p) => p,
        mouse::Cursor::Unavailable => return None,
    };
    POINTER.get().map(|p| at - p)
}

/// A new view is being built: a drop that was waiting for it is over.
/// Forgets every drag and list animation (a new app starts, or a recording).
pub fn reset() {
    SESSION.with(|s| *s.borrow_mut() = None);
    LISTS.with(|l| l.borrow_mut().clear());
    LANDED.with(|l| *l.borrow_mut() = None);
    SUPPRESS.set(0);
}

pub fn begin_view() {
    SESSION.with(|s| {
        let mut session = s.borrow_mut();
        if matches!(session.as_ref().map(|s| s.phase), Some(Phase::Done(_))) {
            *session = None;
        }
    });
}

fn lerp(a: Point, b: Point, t: f32) -> Point {
    Point::new(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)
}

fn ease_out(t: f32) -> f32 {
    let t = t.clamp(0.0, 1.0);
    1.0 - (1.0 - t).powi(3)
}

// ---------------------------------------------------------------------------
// Geometry (no iced state: unit tested)
// ---------------------------------------------------------------------------

/// Places items of `sizes` one after another from `start`, like the list lays them out.
fn flow(
    direction: Direction,
    sizes: &[Size],
    start: Point,
    width: f32,
    spacing: f32,
    line_spacing: f32,
) -> Vec<Point> {
    let mut out = Vec::with_capacity(sizes.len());
    let (mut x, mut y, mut line) = (start.x, start.y, 0.0f32);
    for size in sizes {
        match direction {
            Direction::Vertical => {
                out.push(Point::new(start.x, y));
                y += size.height + spacing;
            }
            Direction::Horizontal => {
                out.push(Point::new(x, start.y));
                x += size.width + spacing;
            }
            Direction::Wrap => {
                if x > start.x && x + size.width > start.x + width + 0.5 {
                    x = start.x;
                    y += line + line_spacing;
                    line = 0.0;
                }
                out.push(Point::new(x, y));
                x += size.width + spacing;
                line = line.max(size.height);
            }
        }
    }
    out
}

/// Where the item being dragged over a list goes: the insertion index among the other items,
/// or the item it would be dropped onto (`combine`).
fn insertion(
    direction: Direction,
    slots: &[Rectangle],
    center: Point,
    combine: bool,
) -> (usize, Option<usize>) {
    if combine {
        for (i, r) in slots.iter().enumerate() {
            let inner = match direction {
                Direction::Vertical => Rectangle {
                    y: r.y + r.height * 0.25,
                    height: r.height * 0.5,
                    ..*r
                },
                Direction::Horizontal => Rectangle {
                    x: r.x + r.width * 0.25,
                    width: r.width * 0.5,
                    ..*r
                },
                Direction::Wrap => Rectangle {
                    x: r.x + r.width * 0.2,
                    y: r.y + r.height * 0.2,
                    width: r.width * 0.6,
                    height: r.height * 0.6,
                },
            };
            if inner.contains(center) {
                return (i, Some(i));
            }
        }
    }
    let index = match direction {
        Direction::Vertical => slots.iter().filter(|r| r.center_y() < center.y).count(),
        Direction::Horizontal => slots.iter().filter(|r| r.center_x() < center.x).count(),
        Direction::Wrap => {
            let nearest = slots.iter().enumerate().min_by(|(_, a), (_, b)| {
                let da = a.center().distance(center);
                let db = b.center().distance(center);
                da.total_cmp(&db)
            });
            match nearest {
                None => 0,
                Some((i, r)) => {
                    let after = if (center.y - r.center_y()).abs() > r.height / 2.0 {
                        center.y > r.center_y()
                    } else {
                        center.x > r.center_x()
                    };
                    i + usize::from(after)
                }
            }
        }
    };
    (index, None)
}

/// Snaps `rect` to the edges and centers of `others` (and of `area`) closer than
/// [`GUIDE_SNAP`], returning the moved rect and the guide lines to draw.
fn align_guides(
    rect: Rectangle,
    others: &[Rectangle],
    area: Rectangle,
) -> (Rectangle, Vec<(Point, Point)>) {
    let mut candidates: Vec<Rectangle> = others.to_vec();
    candidates.push(area);
    let xs = |r: &Rectangle| [r.x, r.center_x(), r.x + r.width];
    let ys = |r: &Rectangle| [r.y, r.center_y(), r.y + r.height];
    let mut best_x: Option<(f32, f32)> = None; // (delta, line x)
    let mut best_y: Option<(f32, f32)> = None;
    for other in &candidates {
        for a in xs(&rect) {
            for b in xs(other) {
                let d = b - a;
                if d.abs() <= GUIDE_SNAP && best_x.is_none_or(|(bd, _)| d.abs() < bd.abs()) {
                    best_x = Some((d, b));
                }
            }
        }
        for a in ys(&rect) {
            for b in ys(other) {
                let d = b - a;
                if d.abs() <= GUIDE_SNAP && best_y.is_none_or(|(bd, _)| d.abs() < bd.abs()) {
                    best_y = Some((d, b));
                }
            }
        }
    }
    let moved = Rectangle {
        x: rect.x + best_x.map_or(0.0, |(d, _)| d),
        y: rect.y + best_y.map_or(0.0, |(d, _)| d),
        ..rect
    };
    let mut lines = Vec::new();
    if let Some((_, x)) = best_x {
        let mut top = moved.y;
        let mut bottom = moved.y + moved.height;
        for other in &candidates {
            if xs(other).iter().any(|v| (v - x).abs() < 0.5) {
                top = top.min(other.y);
                bottom = bottom.max(other.y + other.height);
            }
        }
        lines.push((Point::new(x, top), Point::new(x, bottom)));
    }
    if let Some((_, y)) = best_y {
        let mut left = moved.x;
        let mut right = moved.x + moved.width;
        for other in &candidates {
            if ys(other).iter().any(|v| (v - y).abs() < 0.5) {
                left = left.min(other.x);
                right = right.max(other.x + other.width);
            }
        }
        lines.push((Point::new(left, y), Point::new(right, y)));
    }
    (moved, lines)
}

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------

/// Wraps a window's view: moves the drag along, commits the target under the pointer,
/// scrolls near the edges and ends the drag on release.
pub struct Root<'a> {
    window: window::Id,
    content: Element<'a, Message, Theme, Renderer>,
}

impl<'a> Root<'a> {
    pub fn new(
        window: window::Id,
        content: impl Into<Element<'a, Message, Theme, Renderer>>,
    ) -> Self {
        Self {
            window,
            content: content.into(),
        }
    }
}

/// Pointer events, mouse or touch.
enum Pointer {
    Move(Point),
    Release,
}

fn pointer_event(event: &Event) -> Option<Pointer> {
    match event {
        Event::Mouse(mouse::Event::CursorMoved { position }) => Some(Pointer::Move(*position)),
        Event::Touch(touch::Event::FingerMoved { position, .. }) => Some(Pointer::Move(*position)),
        Event::Mouse(mouse::Event::ButtonReleased(mouse::Button::Left))
        | Event::Touch(touch::Event::FingerLifted { .. })
        | Event::Touch(touch::Event::FingerLost { .. }) => Some(Pointer::Release),
        _ => None,
    }
}

impl Root<'_> {
    /// Moves the preview to follow `at`, inside the drag's constraints.
    fn follow(session: &mut Session, at: Point) {
        session.pointer = at;
        let props = &session.props;
        let mut pos = at - session.grab;
        match props.axis {
            Some(Axis::X) => pos.y = session.origin.y,
            Some(Axis::Y) => pos.x = session.origin.x,
            None => {}
        }
        if let Some((gx, gy)) = props.grid {
            pos.x = session.origin.x + ((pos.x - session.origin.x) / gx).round() * gx;
            pos.y = session.origin.y + ((pos.y - session.origin.y) / gy).round() * gy;
        }
        if let Some(area) = session.constraint {
            let size = session.size();
            pos.x = pos.x.min(area.x + area.width - size.width).max(area.x);
            pos.y = pos.y.min(area.y + area.height - size.height).max(area.y);
        }
        session.free = pos;
    }

    /// Commits the best target found by the pass and tells Python what changed.
    fn commit(session: &mut Session, pass: &mut Pass, shell: &mut Shell<'_, Message>) {
        let best = pass.best.take();
        session.rejected = best.is_none() && pass.rejected;
        let before = session.over.as_ref().map(|t| t.id.clone());
        let after = best.as_ref().map(|t| t.id.clone());
        if before != after {
            if let Some(old) = &session.over {
                let old = old.clone();
                publish(shell, old.on_leave.as_ref(), |py| {
                    event(py, "leave", session, Some(&old))
                });
            }
            if let Some(new) = &best {
                publish(shell, new.on_enter.as_ref(), |py| {
                    event(py, "enter", session, Some(new))
                });
            }
            session.last_over = None;
            shell.invalidate_layout();
        }
        session.preview = match &best {
            Some(t) if t.snap_preview => t.landing.map_or(session.free, |l| l.position()),
            _ => session.free,
        };
        if let Some(t) = &best {
            let key = (
                t.index,
                t.combine.clone(),
                (t.item.x.round() as i32, t.item.y.round() as i32),
            );
            if session.last_over.as_ref() != Some(&key) {
                if session.last_over.as_ref().is_some_and(|k| k.0 != key.0) {
                    shell.invalidate_layout();
                }
                session.last_over = Some(key);
                publish(shell, t.on_over.as_ref(), |py| {
                    event(py, "over", session, Some(t))
                });
            }
        }
        session.over = best;
        shell.request_redraw();
    }

    /// The pointer was released (or Escape pressed): fly to the landing place or back.
    fn release(session: &mut Session, now: Instant, shell: &mut Shell<'_, Message>) {
        let dropped = session.over.is_some() && !session.cancel_requested;
        let to = match (&session.over, dropped) {
            (Some(t), true) => t.landing.map_or(session.preview, |l| l.position()),
            _ => session.origin.position(),
        };
        let quick = crate::animation::settled()
            || session.props.drop_ms <= 0.0
            || session.props.preview != Preview::Item
            || (dropped && session.over.as_ref().is_some_and(|t| t.landing.is_none()));
        if quick {
            Self::finish(session, dropped, now, shell);
        } else {
            session.phase = Phase::Flying {
                from: session.preview,
                to,
                start: now,
                dropped,
            };
            shell.request_redraw();
        }
    }

    fn finish(session: &mut Session, dropped: bool, now: Instant, shell: &mut Shell<'_, Message>) {
        if dropped && let Some(target) = session.over.clone() {
            let landed = target.landing.map_or(session.preview, |l| l.position());
            LANDED.with(|l| {
                *l.borrow_mut() = Some((session.source.clone(), target.id.clone(), landed, now))
            });
            publish(shell, target.on_drop.as_ref(), |py| {
                event(py, "drop", session, Some(&target))
            });
        }
        let target = if dropped { session.over.clone() } else { None };
        let kind = if dropped { "end" } else { "cancel" };
        publish(shell, session.props.on_end.as_ref(), |py| {
            let e = event(py, kind, session, target.as_ref())?;
            e.setattr("dropped", dropped)?;
            Ok(e)
        });
        if !dropped {
            session.over = None;
        }
        session.phase = Phase::Done(now);
        shell.invalidate_layout();
        shell.request_redraw_at(now + DONE_HOLD);
    }

    /// Scrolls the area around the target when the pointer is near its edge.
    #[allow(clippy::too_many_arguments)]
    fn autoscroll(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        viewport: &Rectangle,
    ) {
        let Some((clip, bounds, at)) = with_session(|s| {
            s.over
                .as_ref()
                .filter(|_| s.dragging())
                .map(|t| (t.clip, t.bounds, s.probe()))
        })
        .flatten() else {
            return;
        };
        let speed = |distance: f32| EDGE_SPEED * (1.0 - (distance / EDGE).clamp(0.0, 1.0));
        let mut dy = 0.0;
        let mut dx = 0.0;
        if bounds.height > clip.height + 1.0 {
            if at.y < clip.y + EDGE && bounds.y < clip.y - 0.5 {
                dy = speed(at.y - clip.y);
            } else if at.y > clip.y + clip.height - EDGE
                && bounds.y + bounds.height > clip.y + clip.height + 0.5
            {
                dy = -speed(clip.y + clip.height - at.y);
            }
        }
        if bounds.width > clip.width + 1.0 {
            if at.x < clip.x + EDGE && bounds.x < clip.x - 0.5 {
                dx = speed(at.x - clip.x);
            } else if at.x > clip.x + clip.width - EDGE
                && bounds.x + bounds.width > clip.x + clip.width + 0.5
            {
                dx = -speed(clip.x + clip.width - at.x);
            }
        }
        if dx == 0.0 && dy == 0.0 {
            return;
        }
        let wheel = Event::Mouse(mouse::Event::WheelScrolled {
            delta: mouse::ScrollDelta::Pixels { x: dx, y: dy },
            phase: mouse::ScrollPhase::Moved,
        });
        self.content.as_widget_mut().update(
            tree, &wheel, layout, cursor, renderer, clipboard, shell, viewport,
        );
        shell.request_redraw();
    }
}

impl Widget<Message, Theme, Renderer> for Root<'_> {
    fn tag(&self) -> widget::tree::Tag {
        self.content.as_widget().tag()
    }

    fn state(&self) -> widget::tree::State {
        self.content.as_widget().state()
    }

    fn children(&self) -> Vec<Tree> {
        self.content.as_widget().children()
    }

    fn diff(&self, tree: &mut Tree) {
        self.content.as_widget().diff(tree);
    }

    fn size(&self) -> Size<Length> {
        self.content.as_widget().size()
    }

    fn size_hint(&self) -> Size<Length> {
        self.content.as_widget().size_hint()
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        self.content.as_widget_mut().layout(tree, renderer, limits)
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        self.content
            .as_widget_mut()
            .operate(tree, layout, renderer, operation);
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        viewport: &Rectangle,
    ) {
        WINDOW.set(Some(self.window));
        VIEW.set(Some(layout.bounds()));
        let pointer = pointer_event(event);
        if let Some(Pointer::Move(at)) = pointer {
            POINTER.set(Some(at));
        } else if let Some(at) = cursor.position() {
            POINTER.set(Some(at));
        }
        let mine = here(|_| ()).is_some();
        let now = crate::recorder::now();
        // Move the drag before the widgets see the event, so targets test the new place.
        if mine {
            SESSION.with(|s| {
                let mut s = s.borrow_mut();
                let Some(session) = s.as_mut() else { return };
                if let Event::Keyboard(keyboard::Event::ModifiersChanged(m)) = event {
                    session.modifiers = *m;
                }
                if session.dragging()
                    && let Some(Pointer::Move(at)) = pointer
                {
                    Self::follow(session, at);
                    publish(shell, session.props.on_move.as_ref(), |py| {
                        event_py(py, "move", session)
                    });
                }
            });
        }
        PASS.with(|p| *p.borrow_mut() = Pass::default());
        SUPPRESS.set(0);
        self.content.as_widget_mut().update(
            tree, event, layout, cursor, renderer, clipboard, shell, viewport,
        );
        if !mine && here(|_| ()).is_none() {
            return;
        }
        let mut pass = PASS.with(|p| std::mem::take(&mut *p.borrow_mut()));
        let redraw = matches!(event, Event::Window(window::Event::RedrawRequested(_)));
        let mut scroll = false;
        SESSION.with(|s| {
            let mut s = s.borrow_mut();
            let Some(session) = s.as_mut() else { return };
            if session.window.is_none() {
                session.window = Some(self.window);
            }
            if session.window != Some(self.window) {
                return;
            }
            let escape = matches!(
                event,
                Event::Keyboard(keyboard::Event::KeyPressed {
                    key: keyboard::Key::Named(keyboard::key::Named::Escape),
                    ..
                })
            );
            match session.phase {
                Phase::Dragging => {
                    if escape || session.cancel_requested {
                        session.cancel_requested = true;
                        session.over = None;
                        Self::release(session, now, shell);
                        if escape {
                            shell.capture_event();
                        }
                        return;
                    }
                    if matches!(pointer, Some(Pointer::Release)) {
                        Self::release(session, now, shell);
                        return;
                    }
                    let moved = matches!(pointer, Some(Pointer::Move(_)))
                        || redraw
                        || matches!(event, Event::Mouse(mouse::Event::WheelScrolled { .. }));
                    if moved {
                        Self::commit(session, &mut pass, shell);
                        // Lift: the preview grows a little as it is picked up.
                        let lift = session.props.lift;
                        if (session.lifted - lift).abs() > 0.001 {
                            let step = if crate::animation::settled() {
                                1.0
                            } else {
                                0.25
                            };
                            session.lifted += (lift - session.lifted) * step;
                            if (session.lifted - lift).abs() < 0.002 {
                                session.lifted = lift;
                            }
                            shell.request_redraw();
                        }
                        scroll = redraw;
                    }
                }
                Phase::Flying {
                    from,
                    to,
                    start,
                    dropped,
                } => {
                    if let Event::Window(window::Event::RedrawRequested(now)) = event {
                        let total = session.props.drop_ms.max(1.0) / 1000.0;
                        let t = now.saturating_duration_since(start).as_secs_f32() / total;
                        session.preview = lerp(from, to, ease_out(t));
                        session.lifted = 1.0 + (session.props.lift - 1.0) * (1.0 - ease_out(t));
                        if t >= 1.0 {
                            session.preview = to;
                            Self::finish(session, dropped, *now, shell);
                        } else {
                            shell.request_redraw();
                        }
                    }
                }
                Phase::Done(at) => {
                    if redraw && now.saturating_duration_since(at) >= DONE_HOLD {
                        *s = None;
                        shell.invalidate_layout();
                        shell.request_redraw();
                    }
                }
            }
        });
        if scroll {
            self.autoscroll(tree, layout, cursor, renderer, clipboard, shell, viewport);
        }
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
        renderer: &Renderer,
    ) -> mouse::Interaction {
        let window = self.window;
        let dragging = SESSION.with(|s| {
            s.borrow()
                .as_ref()
                .filter(|s| s.dragging() && s.window.is_none_or(|w| w == window) && s.props.cursor)
                .map(|s| s.rejected)
        });
        match dragging {
            Some(true) => mouse::Interaction::NotAllowed,
            Some(false) => mouse::Interaction::Grabbing,
            None => self
                .content
                .as_widget()
                .mouse_interaction(tree, layout, cursor, viewport, renderer),
        }
    }

    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut Renderer,
        theme: &Theme,
        style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        WINDOW.set(Some(self.window));
        self.content
            .as_widget()
            .draw(tree, renderer, theme, style, layout, cursor, viewport);
    }

    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &Renderer,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<overlay::Element<'b, Message, Theme, Renderer>> {
        WINDOW.set(Some(self.window));
        self.content
            .as_widget_mut()
            .overlay(tree, layout, renderer, viewport, translation)
    }
}

impl<'a> From<Root<'a>> for Element<'a, Message, Theme, Renderer> {
    fn from(root: Root<'a>) -> Self {
        Element::new(root)
    }
}

fn event_py<'py>(py: Python<'py>, kind: &str, session: &Session) -> PyResult<Bound<'py, PyAny>> {
    event(py, kind, session, session.over.as_ref())
}

// ---------------------------------------------------------------------------
// Draggable
// ---------------------------------------------------------------------------

#[derive(Default)]
struct DragState {
    /// Pressed here (content coordinates) at this time, waiting to move far enough.
    press: Option<(Point, Instant)>,
    /// Content minus window coordinates when last known.
    shift: Cell<Vector>,
}

pub struct Draggable<'a> {
    content: Element<'a, Message, Theme, Renderer>,
    preview: Option<Element<'a, Message, Theme, Renderer>>,
    props: Arc<DragProps>,
}

impl<'a> Draggable<'a> {
    pub fn new(
        content: impl Into<Element<'a, Message, Theme, Renderer>>,
        preview: Option<Element<'a, Message, Theme, Renderer>>,
        props: Arc<DragProps>,
    ) -> Self {
        Self {
            content: content.into(),
            preview,
            props,
        }
    }

    fn is_source(&self, session: &Session) -> bool {
        session.source == self.props.id && session.list == self.props.list
    }

    /// The drag in progress is this one and it hasn't been handed back to Python yet.
    fn active(&self) -> Option<Phase> {
        here(|s| self.is_source(s).then_some(s.phase)).flatten()
    }

    /// Starts dragging: `pressed` is where the press was and `shift` turns content coordinates
    /// into window ones.
    fn start(
        &self,
        origin: Rectangle,
        pressed: Point,
        shift: Vector,
        shell: &mut Shell<'_, Message>,
    ) {
        let props = &self.props;
        let window_at = pressed - shift;
        let now_at = POINTER.get().unwrap_or(window_at);
        let constraint = match props.bounds {
            Bounds::Free => None,
            Bounds::Window => VIEW.get(),
            Bounds::Parent => PASS.with(|p| p.borrow().parents.last().copied()),
        };
        let mut session = Session {
            window: WINDOW.get(),
            source: props.id.clone(),
            list: props.list.clone(),
            index: props.index,
            types: props.types.clone(),
            data: props.data.clone(),
            props: props.clone(),
            copy: props.copy,
            stay: props.stay,
            origin,
            grab: window_at - origin.position(),
            start: window_at,
            pointer: window_at,
            free: origin.position(),
            preview: origin.position(),
            lifted: 1.0,
            constraint,
            over: None,
            rejected: false,
            modifiers: Modifiers::default(),
            phase: Phase::Dragging,
            checked: HashMap::new(),
            cancel_requested: false,
            last_over: None,
        };
        Root::follow(&mut session, now_at);
        session.preview = session.free;
        publish(shell, props.on_start.as_ref(), |py| {
            event(py, "start", &session, None)
        });
        SESSION.with(|s| *s.borrow_mut() = Some(session));
        shell.invalidate_layout();
        shell.request_redraw();
    }
}

impl Widget<Message, Theme, Renderer> for Draggable<'_> {
    fn tag(&self) -> widget::tree::Tag {
        widget::tree::Tag::of::<DragState>()
    }

    fn state(&self) -> widget::tree::State {
        widget::tree::State::new(DragState::default())
    }

    fn children(&self) -> Vec<Tree> {
        let mut trees = vec![Tree::new(&self.content)];
        if let Some(preview) = &self.preview {
            trees.push(Tree::new(preview));
        }
        trees
    }

    fn diff(&self, tree: &mut Tree) {
        match &self.preview {
            Some(preview) => tree.diff_children(&[self.content.as_widget(), preview.as_widget()]),
            None => tree.diff_children(std::slice::from_ref(&self.content)),
        }
    }

    fn size(&self) -> Size<Length> {
        self.content.as_widget().size()
    }

    fn size_hint(&self) -> Size<Length> {
        self.content.as_widget().size_hint()
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        self.content
            .as_widget_mut()
            .layout(&mut tree.children[0], renderer, limits)
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        self.content
            .as_widget_mut()
            .operate(&mut tree.children[0], layout, renderer, operation);
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        viewport: &Rectangle,
    ) {
        let captured_before = shell.is_event_captured();
        let dragged = matches!(self.active(), Some(Phase::Dragging | Phase::Flying { .. }));
        if dragged {
            SUPPRESS.set(SUPPRESS.get() + 1);
        }
        self.content.as_widget_mut().update(
            &mut tree.children[0],
            event,
            layout,
            cursor,
            renderer,
            clipboard,
            shell,
            viewport,
        );
        if dragged {
            SUPPRESS.set(SUPPRESS.get() - 1);
        }
        let state = tree.state.downcast_mut::<DragState>();
        let bounds = layout.bounds();
        if let Some(shift) = shift(cursor) {
            state.shift.set(shift);
        }
        let shift = state.shift.get();
        if here(|s| s.dragging()).unwrap_or(false) {
            // Seen by drop targets that align what is dropped to the other items.
            PASS.with(|p| {
                p.borrow_mut()
                    .items
                    .push((self.props.id.clone(), bounds - shift))
            });
        }
        if self.props.disabled {
            state.press = None;
            return;
        }
        let now = crate::recorder::now();
        let press_at = match event {
            Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left)) => {
                cursor.position_over(bounds)
            }
            Event::Touch(touch::Event::FingerPressed { position, .. }) => {
                let at = *position + shift;
                bounds.contains(at).then_some(at)
            }
            _ => None,
        };
        if let Some(at) = press_at {
            let (claimed, handle) = PASS.with(|p| {
                let p = p.borrow();
                (p.claimed, p.handle)
            });
            let captured = shell.is_event_captured() && !captured_before;
            let ok = !claimed
                && cursor.is_over(*viewport)
                && (!self.props.handle || handle)
                && (self.props.handle || self.props.from_children || !captured);
            if ok && with_session(|_| ()).is_none() {
                state.press = Some((at, now));
                PASS.with(|p| p.borrow_mut().claimed = true);
                if !self.props.delay.is_zero() {
                    shell.request_redraw_at(now + self.props.delay);
                }
            }
            return;
        }
        if let Event::Window(window::Event::RedrawRequested(_)) = event
            && let Some((start, pressed)) = state.press
            && !self.props.delay.is_zero()
            && now.saturating_duration_since(pressed) >= self.props.delay
        {
            // A long press: the drag starts without moving.
            state.press = None;
            if with_session(|_| ()).is_none() {
                self.start(bounds - shift, start, shift, shell);
            }
            return;
        }
        match pointer_event(event) {
            Some(Pointer::Move(_)) => {
                let Some((start, pressed)) = state.press else {
                    return;
                };
                let at = match event {
                    Event::Touch(touch::Event::FingerMoved { position, .. }) => *position + shift,
                    _ => match cursor {
                        mouse::Cursor::Available(p) | mouse::Cursor::Levitating(p) => p,
                        mouse::Cursor::Unavailable => return,
                    },
                };
                let far = at.distance(start) > self.props.threshold;
                if !self.props.delay.is_zero()
                    && now.saturating_duration_since(pressed) < self.props.delay
                {
                    if far {
                        // Moved before the long press: a scroll or a swipe, not a drag.
                        state.press = None;
                    }
                    return;
                }
                if far {
                    state.press = None;
                    if with_session(|_| ()).is_none() {
                        self.start(bounds - shift, start, shift, shell);
                    }
                }
            }
            Some(Pointer::Release) => state.press = None,
            None => {}
        }
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
        renderer: &Renderer,
    ) -> mouse::Interaction {
        let inner = self.content.as_widget().mouse_interaction(
            &tree.children[0],
            layout,
            cursor,
            viewport,
            renderer,
        );
        if inner != mouse::Interaction::None && inner != mouse::Interaction::Idle {
            return inner;
        }
        if !self.props.disabled
            && !self.props.handle
            && self.props.cursor
            && cursor.is_over(layout.bounds())
        {
            return mouse::Interaction::Grab;
        }
        inner
    }

    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut Renderer,
        theme: &Theme,
        style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        let draw = |renderer: &mut Renderer| {
            self.content.as_widget().draw(
                &tree.children[0],
                renderer,
                theme,
                style,
                layout,
                cursor,
                viewport,
            )
        };
        let copy = self.props.copy;
        match self.active() {
            Some(_) if copy => draw(renderer),
            Some(phase) => match self.props.source {
                Source::Keep => draw(renderer),
                Source::Hide => {}
                Source::Ghost(_) if matches!(phase, Phase::Done(_)) => {}
                Source::Ghost(opacity) => {
                    crate::animation::with_opacity(opacity, || draw(renderer))
                }
            },
            None => draw(renderer),
        }
    }

    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &Renderer,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<overlay::Element<'b, Message, Theme, Renderer>> {
        let active = matches!(self.active(), Some(Phase::Dragging | Phase::Flying { .. }));
        if !active {
            return self.content.as_widget_mut().overlay(
                &mut tree.children[0],
                layout,
                renderer,
                viewport,
                translation,
            );
        }
        // While dragged, the item's own overlays (tooltips, menus) stay closed.
        let (first, rest) = tree.children.split_at_mut(1);
        let preview = Preview_ {
            content: &self.content,
            tree: &first[0],
            layout,
            custom: self
                .preview
                .as_mut()
                .zip(rest.first_mut())
                .map(|(p, t)| (p, t, None)),
            props: self.props.clone(),
        };
        Some(overlay::Element::new(Box::new(preview)))
    }
}

impl<'a> From<Draggable<'a>> for Element<'a, Message, Theme, Renderer> {
    fn from(d: Draggable<'a>) -> Self {
        Element::new(d)
    }
}

/// The preview that follows the pointer, the ghost where it would land, guides and wires.
#[allow(non_camel_case_types)]
/// A custom preview widget: its element, its tree and its layout once computed.
type CustomPreview<'a, 'b> = (
    &'b mut Element<'a, Message, Theme, Renderer>,
    &'b mut Tree,
    Option<layout::Node>,
);

struct Preview_<'a, 'b> {
    content: &'b Element<'a, Message, Theme, Renderer>,
    tree: &'b Tree,
    layout: Layout<'b>,
    custom: Option<CustomPreview<'a, 'b>>,
    props: Arc<DragProps>,
}

impl Preview_<'_, '_> {
    #[allow(clippy::too_many_arguments)]
    fn draw_item(
        &self,
        renderer: &mut Renderer,
        theme: &Theme,
        style: &renderer::Style,
        cursor: mouse::Cursor,
        at: Point,
        scale: f32,
        opacity: f32,
        shadow: bool,
    ) {
        let bounds = self.layout.bounds();
        let size = match &self.custom {
            Some((_, _, Some(node))) => node.size(),
            _ => bounds.size(),
        };
        let rect = Rectangle::new(at, size);
        if shadow && let Some(color) = self.props.shadow {
            let grown = Rectangle {
                x: rect.center_x() - rect.width * scale / 2.0,
                y: rect.center_y() - rect.height * scale / 2.0,
                width: rect.width * scale,
                height: rect.height * scale,
            };
            renderer.fill_quad(
                Quad {
                    bounds: grown,
                    border: Border {
                        radius: self.props.radius.into(),
                        ..Default::default()
                    },
                    shadow: Shadow {
                        color,
                        offset: Vector::new(0.0, 6.0),
                        blur_radius: 18.0,
                    },
                    ..Default::default()
                },
                Color::TRANSPARENT,
            );
        }
        let center = rect.center();
        let viewport = Rectangle::new(Point::ORIGIN, Size::new(f32::MAX / 4.0, f32::MAX / 4.0));
        crate::animation::with_opacity(opacity, || match &self.custom {
            Some((element, tree, Some(node))) => {
                let transformation = Transformation::translate(center.x, center.y)
                    * Transformation::scale(scale)
                    * Transformation::translate(-center.x, -center.y)
                    * Transformation::translate(at.x, at.y);
                renderer.with_transformation(transformation, |renderer| {
                    element.as_widget().draw(
                        tree,
                        renderer,
                        theme,
                        style,
                        Layout::new(node),
                        mouse::Cursor::Unavailable,
                        &viewport,
                    );
                });
            }
            _ => {
                let transformation = Transformation::translate(center.x, center.y)
                    * Transformation::scale(scale)
                    * Transformation::translate(-center.x, -center.y)
                    * Transformation::translate(at.x - bounds.x, at.y - bounds.y);
                let _ = cursor;
                renderer.with_transformation(transformation, |renderer| {
                    self.content.as_widget().draw(
                        self.tree,
                        renderer,
                        theme,
                        style,
                        self.layout,
                        mouse::Cursor::Unavailable,
                        &viewport,
                    );
                });
            }
        });
    }
}

impl overlay::Overlay<Message, Theme, Renderer> for Preview_<'_, '_> {
    fn layout(&mut self, renderer: &Renderer, bounds: Size) -> layout::Node {
        if let Some((element, tree, node)) = &mut self.custom {
            let limits = layout::Limits::new(Size::ZERO, bounds);
            *node = Some(element.as_widget_mut().layout(tree, renderer, &limits));
        }
        let rect = with_session(|s| s.preview_rect()).unwrap_or_default();
        layout::Node::new(rect.size()).move_to(rect.position())
    }

    fn draw(
        &self,
        renderer: &mut Renderer,
        theme: &Theme,
        style: &renderer::Style,
        _layout: Layout<'_>,
        cursor: mouse::Cursor,
    ) {
        let Some((at, lifted, over, start, pointer, phase, grab)) = with_session(|s| {
            (
                s.preview,
                s.lifted,
                s.over.clone(),
                s.start,
                s.pointer,
                s.phase,
                s.grab,
            )
        }) else {
            return;
        };
        let props = &self.props;
        if let Some(target) = &over {
            for (a, b) in &target.guides {
                let rect = if (a.x - b.x).abs() < 0.5 {
                    Rectangle::new(Point::new(a.x - 0.5, a.y), Size::new(1.0, b.y - a.y))
                } else {
                    Rectangle::new(Point::new(a.x, a.y - 0.5), Size::new(b.x - a.x, 1.0))
                };
                renderer.fill_quad(
                    Quad {
                        bounds: rect,
                        ..Default::default()
                    },
                    target.guide_color,
                );
            }
            if let (Some(opacity), Some(landing), Phase::Dragging) =
                (target.ghost, target.landing, phase)
                && props.preview == Preview::Item
            {
                renderer.with_layer(target.clip, |renderer| {
                    self.draw_item(
                        renderer,
                        theme,
                        style,
                        cursor,
                        landing.position(),
                        1.0,
                        opacity,
                        false,
                    );
                });
            }
        }
        match props.preview {
            Preview::Item => self.draw_item(
                renderer,
                theme,
                style,
                cursor,
                at,
                lifted,
                props.opacity,
                true,
            ),
            Preview::Wire => {
                if phase != Phase::Dragging {
                    return;
                }
                let from = start;
                let to = match &over {
                    Some(t) if t.snap_preview => t.landing.map_or(pointer, |l| l.position() + grab),
                    _ => pointer,
                };
                let bend = ((to.x - from.x).abs() * 0.5).max(40.0);
                let path = Path::new(|p| {
                    p.move_to(from);
                    p.bezier_curve_to(
                        Point::new(from.x + bend, from.y),
                        Point::new(to.x - bend, to.y),
                        to,
                    );
                });
                let size = Size::new(from.x.max(to.x) + bend + 8.0, from.y.max(to.y) + 8.0);
                let mut frame = canvas::Frame::new(renderer, size);
                frame.stroke(
                    &path,
                    Stroke::default()
                        .with_color(props.wire.0)
                        .with_width(props.wire.1)
                        .with_line_cap(canvas::LineCap::Round),
                );
                frame.fill(&Path::circle(to, props.wire.1 * 2.0), props.wire.0);
                renderer.draw_geometry(frame.into_geometry());
            }
            Preview::Nothing => {}
        }
    }

    fn mouse_interaction(
        &self,
        _layout: Layout<'_>,
        _cursor: mouse::Cursor,
        _renderer: &Renderer,
    ) -> mouse::Interaction {
        // Never hide the widgets underneath from the pointer: they are the drop targets.
        mouse::Interaction::None
    }
}

// ---------------------------------------------------------------------------
// Drag handle
// ---------------------------------------------------------------------------

pub struct Handle<'a> {
    content: Element<'a, Message, Theme, Renderer>,
    cursor: Option<mouse::Interaction>,
}

impl<'a> Handle<'a> {
    pub fn new(
        content: impl Into<Element<'a, Message, Theme, Renderer>>,
        cursor: Option<mouse::Interaction>,
    ) -> Self {
        Self {
            content: content.into(),
            cursor,
        }
    }
}

impl Widget<Message, Theme, Renderer> for Handle<'_> {
    fn children(&self) -> Vec<Tree> {
        vec![Tree::new(&self.content)]
    }

    fn diff(&self, tree: &mut Tree) {
        tree.diff_children(std::slice::from_ref(&self.content));
    }

    fn size(&self) -> Size<Length> {
        self.content.as_widget().size()
    }

    fn size_hint(&self) -> Size<Length> {
        self.content.as_widget().size_hint()
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        self.content
            .as_widget_mut()
            .layout(&mut tree.children[0], renderer, limits)
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        self.content
            .as_widget_mut()
            .operate(&mut tree.children[0], layout, renderer, operation);
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        viewport: &Rectangle,
    ) {
        self.content.as_widget_mut().update(
            &mut tree.children[0],
            event,
            layout,
            cursor,
            renderer,
            clipboard,
            shell,
            viewport,
        );
        let pressed = match event {
            Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left)) => {
                cursor.is_over(layout.bounds())
            }
            Event::Touch(touch::Event::FingerPressed { position, .. }) => {
                shift(cursor).is_some_and(|s| layout.bounds().contains(*position + s))
            }
            _ => false,
        };
        if pressed {
            PASS.with(|p| p.borrow_mut().handle = true);
        }
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
        renderer: &Renderer,
    ) -> mouse::Interaction {
        let inner = self.content.as_widget().mouse_interaction(
            &tree.children[0],
            layout,
            cursor,
            viewport,
            renderer,
        );
        match self.cursor {
            Some(c)
                if cursor.is_over(layout.bounds())
                    && matches!(inner, mouse::Interaction::None | mouse::Interaction::Idle) =>
            {
                c
            }
            _ => inner,
        }
    }

    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut Renderer,
        theme: &Theme,
        style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        self.content.as_widget().draw(
            &tree.children[0],
            renderer,
            theme,
            style,
            layout,
            cursor,
            viewport,
        );
    }

    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &Renderer,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<overlay::Element<'b, Message, Theme, Renderer>> {
        self.content.as_widget_mut().overlay(
            &mut tree.children[0],
            layout,
            renderer,
            viewport,
            translation,
        )
    }
}

impl<'a> From<Handle<'a>> for Element<'a, Message, Theme, Renderer> {
    fn from(h: Handle<'a>) -> Self {
        Element::new(h)
    }
}

// ---------------------------------------------------------------------------
// Drop targets
// ---------------------------------------------------------------------------

/// Whether the drag in progress may be dropped on the target `props` (types, `disabled`,
/// `stay` and the Python `can_drop`, asked once per drag).
fn accepts(session: &mut Session, props: &DropProps, list: bool) -> bool {
    if props.disabled || !session.accepted_by(&props.accepts) {
        return false;
    }
    if session.stay && session.list.as_ref() != Some(&props.id) {
        return false;
    }
    let _ = list;
    let Some(check) = &props.can_drop else {
        return true;
    };
    if let Some(answer) = session.checked.get(&props.id) {
        return *answer;
    }
    let answer = Python::attach(|py| {
        let result = event(py, "check", session, None).and_then(|e| {
            e.setattr("target", &*props.id)?;
            py.import("pyzed.dnd")?
                .getattr("_check")?
                .call1((check.0.bind(py), e))
        });
        match result.and_then(|r| r.is_truthy()) {
            Ok(answer) => answer,
            Err(err) => {
                err.print(py);
                false
            }
        }
    });
    session.checked.insert(props.id.clone(), answer);
    answer
}

/// Whether a drag going on would be taken by `props` (for the `active` highlight; only the
/// answers already known from `can_drop`).
fn would_accept(props: &DropProps) -> bool {
    here(|s| {
        s.dragging()
            && !props.disabled
            && s.accepted_by(&props.accepts)
            && !(s.stay && s.list.as_ref() != Some(&props.id))
            && s.checked.get(&props.id).copied().unwrap_or(true)
    })
    .unwrap_or(false)
}

fn over_me(id: &Arc<str>) -> bool {
    here(|s| !matches!(s.phase, Phase::Done(_)) && s.over.as_ref().is_some_and(|t| &t.id == id))
        .unwrap_or(false)
}

/// Registers `target` as a candidate of this pass (the deepest wins).
fn offer(target: Target) {
    if SUPPRESS.get() > 0 {
        return;
    }
    PASS.with(|p| {
        let mut p = p.borrow_mut();
        let better = p.best.as_ref().is_none_or(|b| target.depth > b.depth);
        if better {
            p.best = Some(target);
        }
    });
}

#[derive(Default)]
struct DropState {
    shift: Cell<Vector>,
}

pub struct Droppable<'a> {
    content: Element<'a, Message, Theme, Renderer>,
    props: Arc<DropProps>,
}

impl<'a> Droppable<'a> {
    pub fn new(
        content: impl Into<Element<'a, Message, Theme, Renderer>>,
        props: Arc<DropProps>,
    ) -> Self {
        Self {
            content: content.into(),
            props,
        }
    }
}

/// Runs `f` (the children's update) one level deeper, with `bounds` as the closest target.
fn deeper<R>(bounds: Rectangle, f: impl FnOnce() -> R) -> R {
    let depth = PASS.with(|p| {
        let mut p = p.borrow_mut();
        p.depth += 1;
        p.parents.push(bounds);
        p.depth
    });
    let result = f();
    PASS.with(|p| {
        let mut p = p.borrow_mut();
        p.depth = depth - 1;
        p.parents.pop();
    });
    result
}

fn depth() -> u32 {
    PASS.with(|p| p.borrow().depth)
}

impl Widget<Message, Theme, Renderer> for Droppable<'_> {
    fn tag(&self) -> widget::tree::Tag {
        widget::tree::Tag::of::<DropState>()
    }

    fn state(&self) -> widget::tree::State {
        widget::tree::State::new(DropState::default())
    }

    fn children(&self) -> Vec<Tree> {
        vec![Tree::new(&self.content)]
    }

    fn diff(&self, tree: &mut Tree) {
        tree.diff_children(std::slice::from_ref(&self.content));
    }

    fn size(&self) -> Size<Length> {
        self.content.as_widget().size()
    }

    fn size_hint(&self) -> Size<Length> {
        self.content.as_widget().size_hint()
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        self.content
            .as_widget_mut()
            .layout(&mut tree.children[0], renderer, limits)
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        self.content
            .as_widget_mut()
            .operate(&mut tree.children[0], layout, renderer, operation);
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        viewport: &Rectangle,
    ) {
        let state = tree.state.downcast_ref::<DropState>();
        if let Some(s) = shift(cursor) {
            state.shift.set(s);
        }
        let shift = state.shift.get();
        let bounds = layout.bounds();
        deeper(bounds - shift, || {
            self.content.as_widget_mut().update(
                &mut tree.children[0],
                event,
                layout,
                cursor,
                renderer,
                clipboard,
                shell,
                viewport,
            );
        });
        let screen = bounds - shift;
        let clip = screen.intersection(&(*viewport - shift)).unwrap_or(screen);
        let depth = depth() + 1;
        let props = &self.props;
        SESSION.with(|s| {
            let mut s = s.borrow_mut();
            let Some(session) = s.as_mut() else { return };
            if !session.dragging() || session.window.is_some_and(|w| Some(w) != WINDOW.get()) {
                return;
            }
            if !clip.contains(session.probe()) {
                return;
            }
            if !accepts(session, props, false) {
                PASS.with(|p| p.borrow_mut().rejected = true);
                return;
            }
            let size = session.size();
            let mut rel = session.free - screen.position();
            if let Some((gx, gy)) = props.snap {
                rel.x = (rel.x / gx).round() * gx;
                rel.y = (rel.y / gy).round() * gy;
            }
            let mut guides = Vec::new();
            if props.guides {
                let others: Vec<Rectangle> = PASS.with(|p| {
                    p.borrow()
                        .items
                        .iter()
                        .filter(|(id, r)| **id != *session.source && screen.intersects(r))
                        .map(|(_, r)| *r)
                        .collect()
                });
                let rect = Rectangle::new(screen.position() + rel, size);
                let (moved, lines) = align_guides(rect, &others, screen);
                rel = moved.position() - screen.position();
                guides = lines;
            }
            let landing = Rectangle::new(screen.position() + rel, size);
            let wants_landing =
                props.snap_preview || !matches!(props.placeholder, Placeholder::Nothing);
            offer(Target {
                id: props.id.clone(),
                bounds: screen,
                clip,
                depth,
                index: None,
                gap: None,
                combine: None,
                item: Point::new(rel.x, rel.y),
                landing: wants_landing.then_some(landing),
                snap_preview: props.snap_preview,
                ghost: match props.placeholder {
                    Placeholder::Ghost(o) => Some(o),
                    _ => None,
                },
                guides,
                guide_color: props.guide_color,
                on_drop: props.on_drop.clone(),
                on_enter: props.on_enter.clone(),
                on_leave: props.on_leave.clone(),
                on_over: props.on_over.clone(),
            });
        });
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
        renderer: &Renderer,
    ) -> mouse::Interaction {
        self.content.as_widget().mouse_interaction(
            &tree.children[0],
            layout,
            cursor,
            viewport,
            renderer,
        )
    }

    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut Renderer,
        theme: &Theme,
        style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        let bounds = layout.bounds();
        self.content.as_widget().draw(
            &tree.children[0],
            renderer,
            theme,
            style,
            layout,
            cursor,
            viewport,
        );
        let over = over_me(&self.props.id);
        if over || would_accept(&self.props) {
            let state = tree.state.downcast_ref::<DropState>();
            let shift = state.shift.get();
            if over
                && let Placeholder::Shadow(look) = self.props.placeholder
                && let Some(landing) = here(|s| s.over.as_ref().and_then(|t| t.landing)).flatten()
            {
                renderer.with_layer(bounds, |renderer| look.draw(renderer, landing + shift));
            }
            let look = if over && !self.props.over.is_empty() {
                self.props.over
            } else {
                self.props.active
            };
            look.draw(renderer, bounds);
        }
    }

    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &Renderer,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<overlay::Element<'b, Message, Theme, Renderer>> {
        self.content.as_widget_mut().overlay(
            &mut tree.children[0],
            layout,
            renderer,
            viewport,
            translation,
        )
    }
}

impl<'a> From<Droppable<'a>> for Element<'a, Message, Theme, Renderer> {
    fn from(d: Droppable<'a>) -> Self {
        Element::new(d)
    }
}

// ---------------------------------------------------------------------------
// Sortable
// ---------------------------------------------------------------------------

#[derive(Default)]
struct SortState {
    shift: Cell<Vector>,
    /// Room added at the end for an item coming from another list.
    extra: Size,
}

pub struct Sortable<'a> {
    items: Vec<Element<'a, Message, Theme, Renderer>>,
    keys: Vec<Arc<str>>,
    props: Arc<SortProps>,
}

impl<'a> Sortable<'a> {
    pub fn new(items: Vec<Element<'a, Message, Theme, Renderer>>, props: Arc<SortProps>) -> Self {
        Self {
            keys: props.keys.clone(),
            items,
            props,
        }
    }

    /// The drag options of item `index`.
    pub fn item_props(props: &SortProps, index: usize) -> DragProps {
        let t = &props.item;
        let axis = match props.direction {
            Direction::Vertical if t.lock_axis => Some(Axis::Y),
            Direction::Horizontal if t.lock_axis => Some(Axis::X),
            _ => None,
        };
        DragProps {
            id: props.keys[index].clone(),
            types: t.types.clone(),
            data: props.data[index].clone(),
            disabled: props.locked[index] || !props.draggable,
            handle: t.handle,
            axis,
            bounds: if t.lock_axis {
                Bounds::Parent
            } else {
                Bounds::Free
            },
            grid: None,
            threshold: t.threshold,
            delay: t.delay,
            source: t.source,
            preview: t.preview,
            lift: t.lift,
            shadow: t.shadow,
            opacity: t.opacity,
            radius: t.radius,
            wire: (Color::TRANSPARENT, 0.0),
            drop_ms: t.drop_ms,
            from_children: t.from_children,
            cursor: true,
            on_start: t.on_start.clone(),
            on_move: None,
            on_end: t.on_end.clone(),
            list: Some(props.target.id.clone()),
            index,
            copy: t.copy,
            stay: t.stay,
        }
    }

    fn content(&self, bounds: Rectangle) -> Rectangle {
        bounds.shrink(self.props.padding)
    }

    /// The index of the item being dragged, when it comes from this list (and leaves a gap).
    fn source_index(&self, session: &Session) -> Option<usize> {
        (session.list.as_ref() == Some(&self.props.target.id) && !session.copy)
            .then(|| self.keys.iter().position(|k| *k == session.source))
            .flatten()
    }

    /// Where every item should be shown (offsets from its layout) and where the dragged item
    /// would land, for a drag that is (`insert`) or isn't over this list.
    fn arrange(
        &self,
        rects: &[Rectangle],
        content: Rectangle,
        source: Option<usize>,
        insert: Option<usize>,
        gap: Size,
    ) -> (Vec<Vector>, Option<Rectangle>) {
        let props = &*self.props;
        let mut offsets = vec![Vector::ZERO; rects.len()];
        if source.is_none() && insert.is_none() {
            return (offsets, None);
        }
        let others: Vec<usize> = (0..rects.len()).filter(|i| Some(*i) != source).collect();
        let mut order: Vec<Option<usize>> = others.iter().map(|i| Some(*i)).collect();
        if let Some(t) = insert {
            order.insert(t.min(order.len()), None);
        }
        let gap = match props.direction {
            Direction::Vertical => Size::new(
                source
                    .map_or(
                        rects
                            .iter()
                            .map(|r| r.width)
                            .fold(0.0, f32::max)
                            .max(if rects.is_empty() { content.width } else { 0.0 }),
                        |s| rects[s].width,
                    )
                    .max(1.0),
                gap.height,
            ),
            Direction::Horizontal => Size::new(
                gap.width,
                source
                    .map_or(
                        rects.iter().map(|r| r.height).fold(0.0, f32::max).max(
                            if rects.is_empty() {
                                content.height
                            } else {
                                0.0
                            },
                        ),
                        |s| rects[s].height,
                    )
                    .max(1.0),
            ),
            Direction::Wrap => source.map_or(gap, |s| rects[s].size()),
        };
        let sizes: Vec<Size> = order
            .iter()
            .map(|o| o.map_or(gap, |i| rects[i].size()))
            .collect();
        let start = content.position();
        let places = flow(
            props.direction,
            &sizes,
            start,
            content.width,
            props.spacing,
            props.line_spacing,
        );
        let mut landing = None;
        for (slot, place) in order.iter().zip(places) {
            match slot {
                Some(i) => {
                    let r = rects[*i];
                    let target = match props.direction {
                        Direction::Vertical => Point::new(r.x, place.y),
                        Direction::Horizontal => Point::new(place.x, r.y),
                        Direction::Wrap => place,
                    };
                    offsets[*i] = target - r.position();
                }
                None => {
                    let x = match props.direction {
                        Direction::Vertical => source.map_or(content.x, |s| rects[s].x),
                        _ => place.x,
                    };
                    let y = match props.direction {
                        Direction::Horizontal => source.map_or(content.y, |s| rects[s].y),
                        _ => place.y,
                    };
                    landing = Some(Rectangle::new(Point::new(x, y), gap));
                }
            }
        }
        (offsets, landing)
    }

    fn rects(layout: Layout<'_>) -> Vec<Rectangle> {
        layout.children().map(|l| l.bounds()).collect()
    }

    /// The extra room this list needs for a dragged item coming from another list.
    fn wanted_extra(&self, node: &layout::Node) -> Size {
        let props = &*self.props;
        let me = &props.target.id;
        here(|s| {
            let over = s.over.as_ref().filter(|t| &t.id == me && t.gap.is_some())?;
            let _ = over;
            if self.source_index(s).is_some() {
                return None;
            }
            let rects: Vec<Rectangle> = node.children().iter().map(|n| n.bounds()).collect();
            let content = Rectangle::new(Point::ORIGIN, node.size()).shrink(props.padding);
            let (_, landing) = self.arrange(&rects, content, None, over.gap, s.size());
            let landing = landing?;
            // Only what doesn't fit already: a list that fills its column has room to spare.
            let used = rects.iter().fold(content, |a, r| a.union(r));
            let end = used.union(&landing);
            Some(Size::new(
                (end.x + end.width - (used.x + used.width)).max(0.0),
                (end.y + end.height - (used.y + used.height)).max(0.0),
            ))
        })
        .flatten()
        .unwrap_or(Size::ZERO)
    }
}

impl Widget<Message, Theme, Renderer> for Sortable<'_> {
    fn tag(&self) -> widget::tree::Tag {
        widget::tree::Tag::of::<SortState>()
    }

    fn state(&self) -> widget::tree::State {
        widget::tree::State::new(SortState::default())
    }

    fn children(&self) -> Vec<Tree> {
        self.items.iter().map(Tree::new).collect()
    }

    fn diff(&self, tree: &mut Tree) {
        tree.diff_children(&self.items);
    }

    fn size(&self) -> Size<Length> {
        Size::new(self.props.width, self.props.height)
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        let props = &*self.props;
        let mut node = match props.direction {
            Direction::Vertical | Direction::Horizontal => layout::flex::resolve(
                if props.direction == Direction::Vertical {
                    layout::flex::Axis::Vertical
                } else {
                    layout::flex::Axis::Horizontal
                },
                renderer,
                limits,
                props.width,
                props.height,
                props.padding,
                props.spacing,
                props.align,
                &mut self.items,
                &mut tree.children,
            ),
            Direction::Wrap => {
                let limits = limits.width(props.width).height(props.height);
                let inner = limits.shrink(props.padding);
                let max = inner.max();
                let child_limits =
                    layout::Limits::new(Size::ZERO, Size::new(max.width, f32::INFINITY));
                let mut nodes: Vec<layout::Node> = self
                    .items
                    .iter_mut()
                    .zip(tree.children.iter_mut())
                    .map(|(item, tree)| item.as_widget_mut().layout(tree, renderer, &child_limits))
                    .collect();
                let sizes: Vec<Size> = nodes.iter().map(|n| n.size()).collect();
                let start = Point::new(props.padding.left, props.padding.top);
                let places = flow(
                    Direction::Wrap,
                    &sizes,
                    start,
                    max.width,
                    props.spacing,
                    props.line_spacing,
                );
                let mut used = Size::ZERO;
                for (node, place) in nodes.iter_mut().zip(places) {
                    node.move_to_mut(place);
                    used.width = used.width.max(place.x + node.size().width - start.x);
                    used.height = used.height.max(place.y + node.size().height - start.y);
                }
                let size = limits.resolve(
                    props.width,
                    props.height,
                    Size::new(
                        used.width + props.padding.x(),
                        used.height + props.padding.y(),
                    ),
                );
                layout::Node::with_children(size, nodes)
            }
        };
        let extra = self.wanted_extra(&node);
        let state = tree.state.downcast_mut::<SortState>();
        state.extra = extra;
        if extra != Size::ZERO {
            let size = node.size();
            let grown = limits.resolve(
                props.width,
                props.height,
                Size::new(size.width + extra.width, size.height + extra.height),
            );
            let children = node.children().to_vec();
            node = layout::Node::with_children(grown, children);
        }
        node
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        operation.container(None, layout.bounds());
        operation.traverse(&mut |operation| {
            for ((item, tree), layout) in self
                .items
                .iter_mut()
                .zip(tree.children.iter_mut())
                .zip(layout.children())
            {
                item.as_widget_mut()
                    .operate(tree, layout, renderer, operation);
            }
        });
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        viewport: &Rectangle,
    ) {
        let props = &*self.props;
        let id = props.target.id.clone();
        let state = tree.state.downcast_ref::<SortState>();
        if let Some(s) = shift(cursor) {
            state.shift.set(s);
        }
        let shift = state.shift.get();
        let bounds = layout.bounds();
        let screen = bounds - shift;
        let offsets: Vec<Vector> = LISTS.with(|l| {
            let lists = l.borrow();
            let anim = lists.get(&id);
            self.keys
                .iter()
                .map(|k| {
                    anim.and_then(|a| a.items.get(k))
                        .map_or(Vector::ZERO, |i| i.offset)
                })
                .collect()
        });
        deeper(screen, || {
            for (((item, tree), layout), offset) in self
                .items
                .iter_mut()
                .zip(tree.children.iter_mut())
                .zip(layout.children())
                .zip(&offsets)
            {
                item.as_widget_mut().update(
                    tree,
                    event,
                    layout,
                    cursor - *offset,
                    renderer,
                    clipboard,
                    shell,
                    viewport,
                );
            }
        });
        let rects = Self::rects(layout);
        let content = self.content(bounds);
        // Candidate: the drag is over this list and it takes it.
        let clip = screen.intersection(&(*viewport - shift)).unwrap_or(screen);
        let level = depth() + 1;
        let target = &props.target;
        SESSION.with(|s| {
            let mut s = s.borrow_mut();
            let Some(session) = s.as_mut() else { return };
            if !session.dragging() || session.window.is_some_and(|w| Some(w) != WINDOW.get()) {
                return;
            }
            if !clip.contains(session.probe()) {
                return;
            }
            let source = self.source_index(session);
            let own = session.list.as_ref() == Some(&id);
            let full = props
                .max_items
                .is_some_and(|m| !own && self.keys.len() >= m);
            if (own && !props.sort && !session.copy) || full || !accepts(session, target, true) {
                if !(own && !props.sort) {
                    PASS.with(|p| p.borrow_mut().rejected = true);
                }
                return;
            }
            if own && session.copy {
                // Dropping a palette item back on its palette does nothing.
                return;
            }
            let center = Rectangle::new(session.free, session.size()).center() + shift;
            let others: Vec<usize> = (0..rects.len()).filter(|i| Some(*i) != source).collect();
            // Test against the items where they are shown (the gap where it is now): an item
            // gives way when the dragged one passes its middle, and comes back only when it
            // passes it again, so the list doesn't flicker at the boundary.
            let shown = match &session.over {
                Some(t) if t.id == id => t.gap,
                Some(_) => None,
                None => source,
            };
            let (offsets, _) = self.arrange(&rects, content, source, shown, session.size());
            let slots: Vec<Rectangle> = others.iter().map(|i| rects[*i] + offsets[*i]).collect();
            let (index, onto) = insertion(props.direction, &slots, center, props.combine);
            let combine = onto.map(|o| self.keys[others[o]].clone());
            let (_, landing) = if combine.is_some() {
                (Vec::new(), None)
            } else {
                self.arrange(&rects, content, source, Some(index), session.size())
            };
            let landing = landing.map(|l| l - shift);
            offer(Target {
                id: id.clone(),
                bounds: screen,
                clip,
                depth: level,
                index: combine.is_none().then_some(index),
                gap: if combine.is_some() {
                    shown
                } else {
                    Some(index)
                },
                combine,
                item: landing.map_or(Point::ORIGIN, |l| {
                    Point::new(l.x - screen.x, l.y - screen.y)
                }),
                landing,
                snap_preview: false,
                ghost: match target.placeholder {
                    Placeholder::Ghost(o) => Some(o),
                    _ => None,
                },
                guides: Vec::new(),
                guide_color: target.guide_color,
                on_drop: target.on_drop.clone(),
                on_enter: target.on_enter.clone(),
                on_leave: target.on_leave.clone(),
                on_over: target.on_over.clone(),
            });
        });
        // Animations: items slide to where the drag wants them and from where they were.
        if let Event::Window(window::Event::RedrawRequested(now)) = event {
            let wanted = here(|s| {
                let source = self.source_index(s);
                let over = s.over.as_ref().filter(|t| t.id == id);
                let insert = over.and_then(|t| t.gap);
                let source = if s.copy { None } else { source };
                if source.is_none() && insert.is_none() {
                    return None;
                }
                Some(self.arrange(&rects, content, source, insert, s.size()).0)
            })
            .flatten()
            .unwrap_or_else(|| vec![Vector::ZERO; rects.len()]);
            let landed = LANDED.with(|l| {
                l.borrow().clone().filter(|(_, list, _, at)| {
                    *list == id && now.saturating_duration_since(*at) < Duration::from_secs(1)
                })
            });
            let settle = crate::animation::settled() || props.animation <= 0.0;
            let tau = (props.animation / 1000.0 / 4.0).max(0.001);
            let mut moving = false;
            let mut took_landed = false;
            LISTS.with(|l| {
                let mut lists = l.borrow_mut();
                let anim = lists.entry(id.clone()).or_default();
                let dt = anim.frame.map_or(0.0, |f| {
                    now.saturating_duration_since(f).as_secs_f32().min(0.05)
                });
                anim.frame = Some(*now);
                // Lists that change size across their main axis (the window resized) don't animate it.
                let cross_changed = anim.size.is_some_and(|old| match props.direction {
                    Direction::Vertical | Direction::Wrap => (old.width - bounds.width).abs() > 0.5,
                    Direction::Horizontal => (old.height - bounds.height).abs() > 0.5,
                });
                anim.size = Some(bounds.size());
                for ((key, rect), target) in self.keys.iter().zip(&rects).zip(&wanted) {
                    let rel = rect.position() - bounds.position();
                    let entry = anim.items.entry(key.clone()).or_default();
                    if let Some(last) = entry.last
                        && last != rel
                        && !cross_changed
                    {
                        entry.offset += last - rel;
                    }
                    entry.last = Some(rel);
                    if let Some((landed_key, _, at, _)) = &landed
                        && landed_key == key
                    {
                        entry.offset = *at - (rect.position() - shift);
                        took_landed = true;
                    }
                    let diff = *target - entry.offset;
                    if settle || (diff.x.abs() < 0.3 && diff.y.abs() < 0.3) {
                        entry.offset = *target;
                    } else {
                        let k = if dt <= 0.0 {
                            0.0
                        } else {
                            1.0 - (-dt / tau).exp()
                        };
                        entry.offset += diff * k;
                        moving = true;
                    }
                }
                let keys = &self.keys;
                anim.items.retain(|k, _| keys.contains(k));
            });
            if took_landed {
                LANDED.with(|l| *l.borrow_mut() = None);
            }
            if moving {
                shell.request_redraw();
            }
        }
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
        renderer: &Renderer,
    ) -> mouse::Interaction {
        self.items
            .iter()
            .zip(&tree.children)
            .zip(layout.children())
            .map(|((item, tree), layout)| {
                item.as_widget()
                    .mouse_interaction(tree, layout, cursor, viewport, renderer)
            })
            .max()
            .unwrap_or_default()
    }

    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut Renderer,
        theme: &Theme,
        style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        let props = &*self.props;
        let id = &props.target.id;
        let bounds = layout.bounds();
        let state = tree.state.downcast_ref::<SortState>();
        let shift = state.shift.get();
        let over = over_me(id);
        let accepting = would_accept(&props.target);
        if over || accepting {
            let look = if over && !props.target.over.is_empty() {
                props.target.over
            } else {
                props.target.active
            };
            if look.background.is_some() {
                Highlight {
                    border: None,
                    ..look
                }
                .draw(renderer, bounds);
            }
        }
        let (landing, combine) = here(|s| {
            s.over
                .as_ref()
                .filter(|t| &t.id == id)
                .map(|t| (t.landing, t.combine.clone()))
        })
        .flatten()
        .unwrap_or((None, None));
        if over
            && let (Placeholder::Shadow(look), Some(landing)) = (props.target.placeholder, landing)
        {
            look.draw(renderer, landing + shift);
        }
        let offsets: Vec<Vector> = LISTS.with(|l| {
            let lists = l.borrow();
            let anim = lists.get(id);
            self.keys
                .iter()
                .map(|k| {
                    anim.and_then(|a| a.items.get(k))
                        .map_or(Vector::ZERO, |i| i.offset)
                })
                .collect()
        });
        let visible = *viewport;
        for (((item, tree), layout), (key, offset)) in self
            .items
            .iter()
            .zip(&tree.children)
            .zip(layout.children())
            .zip(self.keys.iter().zip(&offsets))
        {
            let shown = layout.bounds() + *offset;
            if !shown.intersects(&visible) {
                continue;
            }
            let draw = |renderer: &mut Renderer| {
                item.as_widget().draw(
                    tree,
                    renderer,
                    theme,
                    style,
                    layout,
                    cursor - *offset,
                    &(visible - *offset),
                );
            };
            if *offset == Vector::ZERO {
                draw(renderer);
            } else {
                renderer.with_translation(*offset, draw);
            }
            if combine.as_ref() == Some(key) {
                let look = if props.target.over.is_empty() {
                    props.target.active
                } else {
                    props.target.over
                };
                Highlight {
                    background: look.background,
                    border: look.border.or(Some(Color::from_rgb8(0x74, 0xad, 0xe8))),
                    width: look.width.max(2.0),
                    radius: props.item.radius,
                }
                .draw(renderer, shown);
            }
        }
        if (over || accepting) && !props.target.over.is_empty()
            || (accepting && !props.target.active.is_empty())
        {
            let look = if over && !props.target.over.is_empty() {
                props.target.over
            } else {
                props.target.active
            };
            if look.border.is_some() {
                Highlight {
                    background: None,
                    ..look
                }
                .draw(renderer, bounds);
            }
        }
    }

    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &Renderer,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<overlay::Element<'b, Message, Theme, Renderer>> {
        let id = &self.props.target.id;
        let offsets: Vec<Vector> = LISTS.with(|l| {
            let lists = l.borrow();
            let anim = lists.get(id);
            self.keys
                .iter()
                .map(|k| {
                    anim.and_then(|a| a.items.get(k))
                        .map_or(Vector::ZERO, |i| i.offset)
                })
                .collect()
        });
        let children: Vec<_> = self
            .items
            .iter_mut()
            .zip(tree.children.iter_mut())
            .zip(layout.children())
            .zip(offsets)
            .filter_map(|(((item, tree), layout), offset)| {
                item.as_widget_mut()
                    .overlay(tree, layout, renderer, viewport, translation + offset)
            })
            .collect();
        (!children.is_empty()).then(|| overlay::Group::with_children(children).overlay())
    }
}

impl<'a> From<Sortable<'a>> for Element<'a, Message, Theme, Renderer> {
    fn from(s: Sortable<'a>) -> Self {
        Element::new(s)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rect(x: f32, y: f32, w: f32, h: f32) -> Rectangle {
        Rectangle::new(Point::new(x, y), Size::new(w, h))
    }

    #[test]
    fn flow_wraps_rows() {
        let sizes = [Size::new(40.0, 20.0); 5];
        let places = flow(Direction::Wrap, &sizes, Point::ORIGIN, 100.0, 10.0, 5.0);
        assert_eq!(places[0], Point::new(0.0, 0.0));
        assert_eq!(places[1], Point::new(50.0, 0.0));
        assert_eq!(places[2], Point::new(0.0, 25.0));
        assert_eq!(places[4], Point::new(0.0, 50.0));
    }

    #[test]
    fn insertion_follows_the_centers() {
        let slots = [
            rect(0.0, 0.0, 100.0, 20.0),
            rect(0.0, 30.0, 100.0, 20.0),
            rect(0.0, 60.0, 100.0, 20.0),
        ];
        assert_eq!(
            insertion(Direction::Vertical, &slots, Point::new(10.0, -5.0), false),
            (0, None)
        );
        assert_eq!(
            insertion(Direction::Vertical, &slots, Point::new(10.0, 45.0), false),
            (2, None)
        );
        assert_eq!(
            insertion(Direction::Vertical, &slots, Point::new(10.0, 99.0), false),
            (3, None)
        );
        // In the middle of an item, combining wins.
        assert_eq!(
            insertion(Direction::Vertical, &slots, Point::new(10.0, 40.0), true),
            (1, Some(1))
        );
    }

    #[test]
    fn insertion_in_a_grid() {
        let slots = [
            rect(0.0, 0.0, 40.0, 40.0),
            rect(50.0, 0.0, 40.0, 40.0),
            rect(0.0, 50.0, 40.0, 40.0),
        ];
        assert_eq!(
            insertion(Direction::Wrap, &slots, Point::new(80.0, 20.0), false).0,
            2
        );
        assert_eq!(
            insertion(Direction::Wrap, &slots, Point::new(55.0, 20.0), false).0,
            1
        );
        assert_eq!(
            insertion(Direction::Wrap, &slots, Point::new(30.0, 70.0), false).0,
            3
        );
    }

    #[test]
    fn guides_snap_to_close_edges() {
        let other = rect(100.0, 100.0, 50.0, 50.0);
        let area = rect(0.0, 0.0, 1000.0, 1000.0);
        let (moved, lines) = align_guides(rect(103.0, 300.0, 50.0, 50.0), &[other], area);
        assert_eq!(moved.x, 100.0);
        assert_eq!(moved.y, 300.0);
        assert_eq!(lines.len(), 1);
        let (moved, lines) = align_guides(rect(300.0, 300.0, 50.0, 50.0), &[other], area);
        assert_eq!(moved, rect(300.0, 300.0, 50.0, 50.0));
        assert!(lines.is_empty());
    }
}
