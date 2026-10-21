//! Layout widgets: a track grid (CSS-grid-like columns and rows) and resizable panels.

use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer::{self, Quad};
use iced::advanced::widget::{self, Tree, Widget};
use iced::advanced::{Clipboard, Shell, mouse, overlay};
use iced::alignment::{Horizontal, Vertical};
use iced::{Background, Color, Element, Event, Length, Padding, Point, Rectangle, Size, Vector};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyList, PyString, PyTuple};

use crate::style::{self, Any};
use crate::widget::{Kind, PyMsg, child, new};

// ---------------------------------------------------------------------------
// Track grid
// ---------------------------------------------------------------------------

/// The size of one column or row of a track grid.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Track {
    /// Fixed size in pixels.
    Px(f32),
    /// A share of the space left after the fixed and auto tracks.
    Fr(f32),
    /// As big as its largest item.
    Auto,
}

impl Track {
    fn parse(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        if let Ok(s) = value.cast::<PyString>() {
            return Self::parse_str(&s.to_cow()?);
        }
        let px: f32 = value.extract().map_err(|_| {
            PyValueError::new_err("grid tracks are numbers (pixels), \"auto\" or \"<n>fr\"")
        })?;
        Ok(Track::Px(px))
    }

    fn parse_str(s: &str) -> PyResult<Self> {
        let s = s.trim();
        let bad = || {
            PyValueError::new_err(format!(
                "invalid grid track {s:?}: use a number (pixels), \"auto\" or \"<n>fr\""
            ))
        };
        if s == "auto" {
            Ok(Track::Auto)
        } else if let Some(n) = s.strip_suffix("fr") {
            let n = if n.is_empty() {
                1.0
            } else {
                n.parse::<f32>().map_err(|_| bad())?
            };
            Ok(Track::Fr(n.max(0.0)))
        } else {
            let px = s.strip_suffix("px").unwrap_or(s);
            px.parse::<f32>().map(Track::Px).map_err(|_| bad())
        }
    }
}

/// `None` | int (that many `1fr` tracks) | "200 1fr auto" | [200, "1fr", "auto"]
pub fn tracks(value: &Any<'_>) -> PyResult<Vec<Track>> {
    let Some(value) = value.as_ref().filter(|v| !v.is_none()) else {
        return Ok(Vec::new());
    };
    if let Ok(n) = value.extract::<usize>() {
        return Ok(vec![Track::Fr(1.0); n]);
    }
    if let Ok(s) = value.cast::<PyString>() {
        return s
            .to_cow()?
            .split_whitespace()
            .map(Track::parse_str)
            .collect();
    }
    if value.cast::<PyList>().is_ok() || value.cast::<PyTuple>().is_ok() {
        return value.try_iter()?.map(|item| Track::parse(&item?)).collect();
    }
    Err(PyValueError::new_err(
        "grid columns/rows: an int, a string like \"200 1fr auto\" or a list of tracks",
    ))
}

/// Where an item goes in a track grid; set with `pz.cell(...)`.
#[derive(Clone, Copy, Debug, Default)]
pub struct Placement {
    pub column: Option<usize>,
    pub row: Option<usize>,
    pub column_span: usize,
    pub row_span: usize,
    pub align_x: Option<Horizontal>,
    pub align_y: Option<Vertical>,
}

pub struct TrackGridProps {
    pub children: Vec<Py<crate::widget::Widget>>,
    pub columns: Vec<Track>,
    pub rows: Vec<Track>,
    pub column_gap: f32,
    pub row_gap: f32,
    pub padding: Padding,
    pub width: Length,
    pub height: Length,
    pub align_x: Horizontal,
    pub align_y: Vertical,
}

/// Places a child in a grid cell. Outside a grid it is just the child.
#[pyfunction]
#[pyo3(signature = (content, *, column=None, row=None, column_span=1, row_span=1, align_x=None,
    align_y=None))]
#[allow(clippy::too_many_arguments)]
pub fn cell(
    py: Python<'_>,
    content: &Bound<'_, PyAny>,
    column: Option<usize>,
    row: Option<usize>,
    column_span: usize,
    row_span: usize,
    align_x: Option<&str>,
    align_y: Option<&str>,
) -> PyResult<Py<crate::widget::Widget>> {
    new(
        py,
        Kind::Cell {
            child: child(content)?,
            placement: Placement {
                column,
                row,
                column_span: column_span.max(1),
                row_span: row_span.max(1),
                align_x: style::align_x(align_x)?,
                align_y: style::align_y(align_y)?,
            },
        },
    )
}

/// Assigns every item a cell, honouring explicit positions and filling the rest row by row.
/// Returns `(column, row, column_span, row_span)` per item and the number of rows used.
pub fn place(items: &[Placement], columns: usize) -> (Vec<(usize, usize, usize, usize)>, usize) {
    let columns = columns.max(1);
    let mut taken: Vec<Vec<bool>> = Vec::new();
    let fits = |taken: &Vec<Vec<bool>>, c: usize, r: usize, cs: usize, rs: usize| {
        c + cs <= columns
            && (r..r + rs).all(|row| {
                taken
                    .get(row)
                    .is_none_or(|cells| (c..c + cs).all(|col| !cells[col]))
            })
    };
    let mark = |taken: &mut Vec<Vec<bool>>, c: usize, r: usize, cs: usize, rs: usize| {
        while taken.len() < r + rs {
            taken.push(vec![false; columns]);
        }
        for row in taken.iter_mut().skip(r).take(rs) {
            for cell in row.iter_mut().skip(c).take(cs) {
                *cell = true;
            }
        }
    };
    let mut out = vec![(0, 0, 1, 1); items.len()];
    // Explicitly placed items first, so auto-placed ones flow around them.
    for (i, p) in items.iter().enumerate() {
        if let (Some(c), Some(r)) = (p.column, p.row) {
            let c = c.min(columns - 1);
            let cs = p.column_span.clamp(1, columns - c);
            mark(&mut taken, c, r, cs, p.row_span);
            out[i] = (c, r, cs, p.row_span);
        }
    }
    let mut cursor = (0usize, 0usize); // (row, column)
    for (i, p) in items.iter().enumerate() {
        if p.column.is_some() && p.row.is_some() {
            continue;
        }
        let cs = p.column_span.clamp(1, columns);
        let rs = p.row_span;
        let spot = match (p.column, p.row) {
            (Some(c), None) => {
                let c = c.min(columns - cs);
                (0..).find(|&r| fits(&taken, c, r, cs, rs)).map(|r| (c, r))
            }
            (None, Some(r)) => (0..=columns - cs)
                .find(|&c| fits(&taken, c, r, cs, rs))
                .map(|c| (c, r))
                .or(Some((0, r))),
            _ => {
                let (mut r, mut c) = cursor;
                loop {
                    if c + cs > columns {
                        r += 1;
                        c = 0;
                    }
                    if fits(&taken, c, r, cs, rs) {
                        break;
                    }
                    c += 1;
                }
                cursor = (r, c + cs);
                Some((c, r))
            }
        };
        let (c, r) = spot.unwrap_or((0, 0));
        mark(&mut taken, c, r, cs, rs);
        out[i] = (c, r, cs, rs);
    }
    (out, taken.len())
}

/// Sizes tracks along one axis: fixed ones as given, auto ones from `content(track)`,
/// and `fr` ones share what is left of `available` (or act as auto when it is unbounded).
pub fn size_tracks(
    tracks: &[Track],
    gap: f32,
    available: f32,
    mut content: impl FnMut(usize) -> f32,
) -> Vec<f32> {
    let gaps = gap * tracks.len().saturating_sub(1) as f32;
    let mut sizes: Vec<f32> = tracks
        .iter()
        .enumerate()
        .map(|(i, t)| match t {
            Track::Px(px) => *px,
            Track::Auto => content(i),
            Track::Fr(_) => 0.0,
        })
        .collect();
    if available.is_finite() {
        // Auto tracks never push the grid past the space it has: shrink them to fit.
        let fixed: f32 = tracks
            .iter()
            .zip(&sizes)
            .filter(|(t, _)| matches!(t, Track::Px(_)))
            .map(|(_, s)| s)
            .sum();
        let auto: f32 = tracks
            .iter()
            .zip(&sizes)
            .filter(|(t, _)| matches!(t, Track::Auto))
            .map(|(_, s)| s)
            .sum();
        let room = (available - fixed - gaps).max(0.0);
        if auto > room && auto > 0.0 {
            let scale = room / auto;
            for (size, track) in sizes.iter_mut().zip(tracks) {
                if matches!(track, Track::Auto) {
                    *size *= scale;
                }
            }
        }
    }
    let fr_total: f32 = tracks
        .iter()
        .map(|t| if let Track::Fr(f) = t { *f } else { 0.0 })
        .sum();
    if fr_total > 0.0 {
        if available.is_finite() {
            let used: f32 = sizes.iter().sum::<f32>() + gaps;
            let left = (available - used).max(0.0);
            for (i, t) in tracks.iter().enumerate() {
                if let Track::Fr(f) = t {
                    sizes[i] = left * f / fr_total;
                }
            }
        } else {
            for (i, t) in tracks.iter().enumerate() {
                if matches!(t, Track::Fr(_)) {
                    sizes[i] = content(i);
                }
            }
        }
    }
    sizes
}

fn offsets(sizes: &[f32], gap: f32) -> Vec<f32> {
    let mut at = 0.0;
    sizes
        .iter()
        .map(|s| {
            let start = at;
            at += s + gap;
            start
        })
        .collect()
}

fn span(sizes: &[f32], start: usize, count: usize, gap: f32) -> f32 {
    let end = (start + count).min(sizes.len());
    let n = end.saturating_sub(start);
    sizes[start.min(sizes.len())..end].iter().sum::<f32>() + gap * n.saturating_sub(1) as f32
}

pub struct TrackGrid<'a, Message, Theme, Renderer> {
    items: Vec<(Element<'a, Message, Theme, Renderer>, Placement)>,
    columns: Vec<Track>,
    rows: Vec<Track>,
    column_gap: f32,
    row_gap: f32,
    padding: Padding,
    width: Length,
    height: Length,
    align_x: Horizontal,
    align_y: Vertical,
}

impl<'a, Message, Theme, Renderer> TrackGrid<'a, Message, Theme, Renderer> {
    pub fn new(
        items: Vec<(Element<'a, Message, Theme, Renderer>, Placement)>,
        props: &TrackGridProps,
    ) -> Self {
        Self {
            items,
            columns: if props.columns.is_empty() {
                vec![Track::Fr(1.0)]
            } else {
                props.columns.clone()
            },
            rows: props.rows.clone(),
            column_gap: props.column_gap,
            row_gap: props.row_gap,
            padding: props.padding,
            width: props.width,
            height: props.height,
            align_x: props.align_x,
            align_y: props.align_y,
        }
    }
}

impl<Message, Theme, Renderer> Widget<Message, Theme, Renderer>
    for TrackGrid<'_, Message, Theme, Renderer>
where
    Renderer: iced::advanced::Renderer,
{
    fn children(&self) -> Vec<Tree> {
        self.items.iter().map(|(e, _)| Tree::new(e)).collect()
    }

    fn diff(&self, tree: &mut Tree) {
        let elements: Vec<_> = self.items.iter().map(|(e, _)| e).collect();
        tree.diff_children(&elements);
    }

    fn size(&self) -> Size<Length> {
        Size::new(self.width, self.height)
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        let limits = limits.width(self.width).height(self.height);
        let max = limits.max();
        let inner_w = if self.width == Length::Shrink {
            f32::INFINITY
        } else {
            max.width - self.padding.left - self.padding.right
        };
        let inner_h = if self.height == Length::Shrink {
            f32::INFINITY
        } else {
            max.height - self.padding.top - self.padding.bottom
        };
        let placements: Vec<Placement> = self.items.iter().map(|(_, p)| *p).collect();
        let (cells, used_rows) = place(&placements, self.columns.len());
        let rows: Vec<Track> = (0..used_rows.max(self.rows.len()))
            .map(|i| self.rows.get(i).copied().unwrap_or(Track::Auto))
            .collect();

        // Measures an item: its natural size when given at most `room`.
        let mut measure = |i: usize, room: Size| -> Size {
            let (element, _) = &mut self.items[i];
            element
                .as_widget_mut()
                .layout(
                    &mut tree.children[i],
                    renderer,
                    &layout::Limits::new(Size::ZERO, room),
                )
                .size()
        };

        let col_sizes = size_tracks(&self.columns, self.column_gap, inner_w, |col| {
            (0..cells.len())
                .filter(|&i| cells[i].0 == col && cells[i].2 == 1)
                .map(|i| {
                    let room = Size::new(
                        if inner_w.is_finite() {
                            inner_w
                        } else {
                            max.width
                        },
                        max.height,
                    );
                    measure(i, room).width
                })
                .fold(0.0, f32::max)
        });
        let row_sizes = size_tracks(&rows, self.row_gap, inner_h, |row| {
            (0..cells.len())
                .filter(|&i| cells[i].1 == row && cells[i].3 == 1)
                .map(|i| {
                    let (c, _, cs, _) = cells[i];
                    let room = Size::new(span(&col_sizes, c, cs, self.column_gap), max.height);
                    measure(i, room).height
                })
                .fold(0.0, f32::max)
        });
        let xs = offsets(&col_sizes, self.column_gap);
        let ys = offsets(&row_sizes, self.row_gap);

        let mut nodes = Vec::with_capacity(self.items.len());
        for (i, (element, p)) in self.items.iter_mut().enumerate() {
            let (c, r, cs, rs) = cells[i];
            let cell = Size::new(
                span(&col_sizes, c, cs, self.column_gap),
                span(&row_sizes, r, rs, self.row_gap),
            );
            let node = element.as_widget_mut().layout(
                &mut tree.children[i],
                renderer,
                &layout::Limits::new(Size::ZERO, cell),
            );
            let size = node.size();
            let dx = match p.align_x.unwrap_or(self.align_x) {
                Horizontal::Left => 0.0,
                Horizontal::Center => (cell.width - size.width) / 2.0,
                Horizontal::Right => cell.width - size.width,
            };
            let dy = match p.align_y.unwrap_or(self.align_y) {
                Vertical::Top => 0.0,
                Vertical::Center => (cell.height - size.height) / 2.0,
                Vertical::Bottom => cell.height - size.height,
            };
            nodes.push(node.move_to(Point::new(
                self.padding.left + xs.get(c).copied().unwrap_or(0.0) + dx.max(0.0),
                self.padding.top + ys.get(r).copied().unwrap_or(0.0) + dy.max(0.0),
            )));
        }
        let content = Size::new(
            col_sizes.iter().sum::<f32>()
                + self.column_gap * col_sizes.len().saturating_sub(1) as f32
                + self.padding.left
                + self.padding.right,
            row_sizes.iter().sum::<f32>()
                + self.row_gap * row_sizes.len().saturating_sub(1) as f32
                + self.padding.top
                + self.padding.bottom,
        );
        layout::Node::with_children(limits.resolve(self.width, self.height, content), nodes)
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
            for (((element, _), state), layout) in self
                .items
                .iter_mut()
                .zip(&mut tree.children)
                .zip(layout.children())
            {
                element
                    .as_widget_mut()
                    .operate(state, layout, renderer, operation);
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
        for (((element, _), state), layout) in self
            .items
            .iter_mut()
            .zip(&mut tree.children)
            .zip(layout.children())
        {
            element.as_widget_mut().update(
                state, event, layout, cursor, renderer, clipboard, shell, viewport,
            );
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
            .map(|(((element, _), state), layout)| {
                element
                    .as_widget()
                    .mouse_interaction(state, layout, cursor, viewport, renderer)
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
        if let Some(clipped) = layout.bounds().intersection(viewport) {
            for (((element, _), state), layout) in
                self.items.iter().zip(&tree.children).zip(layout.children())
            {
                if layout.bounds().intersects(&clipped) {
                    element
                        .as_widget()
                        .draw(state, renderer, theme, style, layout, cursor, &clipped);
                }
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
        let overlays: Vec<_> = self
            .items
            .iter_mut()
            .zip(&mut tree.children)
            .zip(layout.children())
            .filter_map(|(((element, _), state), layout)| {
                element
                    .as_widget_mut()
                    .overlay(state, layout, renderer, viewport, translation)
            })
            .collect();
        (!overlays.is_empty()).then(|| overlay::Group::with_children(overlays).overlay())
    }
}

impl<'a, Message, Theme, Renderer> From<TrackGrid<'a, Message, Theme, Renderer>>
    for Element<'a, Message, Theme, Renderer>
where
    Message: 'a,
    Theme: 'a,
    Renderer: iced::advanced::Renderer + 'a,
{
    fn from(grid: TrackGrid<'a, Message, Theme, Renderer>) -> Self {
        Element::new(grid)
    }
}

// ---------------------------------------------------------------------------
// Resizable
// ---------------------------------------------------------------------------

/// The side of a resizable panel that carries the drag handle.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Edge {
    Left,
    Right,
    Top,
    Bottom,
}

impl Edge {
    pub fn parse(value: &str) -> PyResult<Self> {
        Ok(match value {
            "left" => Edge::Left,
            "right" => Edge::Right,
            "top" => Edge::Top,
            "bottom" => Edge::Bottom,
            other => {
                return Err(PyValueError::new_err(format!(
                    "invalid edge {other:?}: use \"left\", \"right\", \"top\" or \"bottom\""
                )));
            }
        })
    }

    fn horizontal(self) -> bool {
        matches!(self, Edge::Left | Edge::Right)
    }
}

pub struct ResizableProps {
    pub child: Py<crate::widget::Widget>,
    pub edge: Edge,
    pub size: f32,
    pub min: f32,
    pub max: f32,
    pub on_resize: Option<PyMsg>,
    pub color: Option<Color>,
    pub hover_color: Option<Color>,
    pub thickness: f32,
    pub handle: f32,
    pub cross: Length,
}

/// A panel whose `edge` ("left", "right", "top" or "bottom") can be dragged to resize
/// it. `size` is the width (or height for "top"/"bottom") it starts with; the panel
/// keeps the size the user drags it to, and `on_resize(size)` is called when a drag
/// ends so you can store it. Changing `size` later resets it. The handle is drawn as a
/// `thickness`-wide line on that edge (`color`, `hover_color` while hovered or dragged).
///
/// Events:
/// - `on_resize(size)`: Called with the new size when a drag ends.
#[pyfunction]
#[pyo3(signature = (content, *, edge="right", size=240.0, min_size=80.0, max_size=None,
    on_resize=None, color=None, hover_color=None, thickness=1.0, handle=8.0, width=None,
    height=None))]
#[allow(clippy::too_many_arguments)]
pub fn resizable(
    py: Python<'_>,
    content: &Bound<'_, PyAny>,
    edge: &str,
    size: f32,
    min_size: f32,
    max_size: Option<f32>,
    on_resize: Any<'_>,
    color: Any<'_>,
    hover_color: Any<'_>,
    thickness: f32,
    handle: f32,
    width: Any<'_>,
    height: Any<'_>,
) -> PyResult<Py<crate::widget::Widget>> {
    let edge = Edge::parse(edge)?;
    // The cross axis is the one `size` doesn't control: height for left/right edges.
    let cross = if edge.horizontal() { &height } else { &width };
    new(
        py,
        Kind::Resizable(Box::new(ResizableProps {
            child: child(content)?,
            edge,
            size,
            min: min_size.max(0.0),
            max: max_size.unwrap_or(f32::INFINITY),
            on_resize: PyMsg::maybe(&on_resize),
            color: style::opt_color(&color)?,
            hover_color: style::opt_color(&hover_color)?,
            thickness: thickness.max(0.0),
            handle: handle.max(thickness),
            cross: style::opt_length(cross)?.unwrap_or(Length::Fill),
        })),
    )
}

pub struct ResizeStyle {
    pub color: Color,
    pub hover_color: Color,
    pub line: f32,
    pub handle: f32,
}

pub struct Resizable<'a, Message, Theme, Renderer> {
    content: Element<'a, Message, Theme, Renderer>,
    edge: Edge,
    size: f32,
    min: f32,
    max: f32,
    style: ResizeStyle,
    cross: Length,
    on_resize: Option<Box<dyn Fn(f32) -> Message + 'a>>,
}

#[derive(Default)]
struct ResizeState {
    /// The size the user dragged to, until the `size` prop changes.
    dragged: Option<f32>,
    prop: Option<f32>,
    /// Pointer position and panel size when the drag started.
    drag: Option<(f32, f32)>,
}

impl<'a, Message, Theme, Renderer> Resizable<'a, Message, Theme, Renderer> {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        content: impl Into<Element<'a, Message, Theme, Renderer>>,
        edge: Edge,
        size: f32,
        range: (f32, f32),
        style: ResizeStyle,
        cross: Length,
        on_resize: Option<Box<dyn Fn(f32) -> Message + 'a>>,
    ) -> Self {
        Self {
            content: content.into(),
            edge,
            size,
            min: range.0,
            max: range.1.max(range.0),
            style,
            cross,
            on_resize,
        }
    }

    fn clamp(&self, size: f32) -> f32 {
        size.clamp(self.min, self.max)
    }

    fn line_bounds(&self, bounds: Rectangle) -> Rectangle {
        let line = self.style.line;
        match self.edge {
            Edge::Left => Rectangle {
                width: line,
                ..bounds
            },
            Edge::Right => Rectangle {
                x: bounds.x + bounds.width - line,
                width: line,
                ..bounds
            },
            Edge::Top => Rectangle {
                height: line,
                ..bounds
            },
            Edge::Bottom => Rectangle {
                y: bounds.y + bounds.height - line,
                height: line,
                ..bounds
            },
        }
    }

    fn handle_bounds(&self, bounds: Rectangle) -> Rectangle {
        let line = self.line_bounds(bounds);
        let grow = (self.style.handle - self.style.line) / 2.0;
        if self.edge.horizontal() {
            Rectangle {
                x: line.x - grow,
                width: self.style.handle,
                ..line
            }
        } else {
            Rectangle {
                y: line.y - grow,
                height: self.style.handle,
                ..line
            }
        }
    }

    fn active(&self, state: &ResizeState, bounds: Rectangle, cursor: mouse::Cursor) -> bool {
        state.drag.is_some() || cursor.is_over(self.handle_bounds(bounds))
    }
}

impl<Message, Theme, Renderer> Widget<Message, Theme, Renderer>
    for Resizable<'_, Message, Theme, Renderer>
where
    Renderer: iced::advanced::Renderer,
{
    fn tag(&self) -> widget::tree::Tag {
        widget::tree::Tag::of::<ResizeState>()
    }

    fn state(&self) -> widget::tree::State {
        widget::tree::State::new(ResizeState::default())
    }

    fn children(&self) -> Vec<Tree> {
        vec![Tree::new(&self.content)]
    }

    fn diff(&self, tree: &mut Tree) {
        tree.diff_children(std::slice::from_ref(&self.content));
    }

    fn size(&self) -> Size<Length> {
        if self.edge.horizontal() {
            Size::new(Length::Shrink, self.cross)
        } else {
            Size::new(self.cross, Length::Shrink)
        }
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        let state = tree.state.downcast_mut::<ResizeState>();
        if state.prop != Some(self.size) {
            state.prop = Some(self.size);
            state.dragged = None;
        }
        let wanted = self.clamp(state.dragged.unwrap_or(self.size));
        let max = limits.max();
        let line = self.style.line;
        let (size, content, offset) = if self.edge.horizontal() {
            let height = limits.height(self.cross).max().height;
            let width = wanted.min(max.width);
            let inner = Size::new((width - line).max(0.0), height);
            let offset = if self.edge == Edge::Left { line } else { 0.0 };
            (Size::new(width, height), inner, Point::new(offset, 0.0))
        } else {
            let width = limits.width(self.cross).max().width;
            let height = wanted.min(max.height);
            let inner = Size::new(width, (height - line).max(0.0));
            let offset = if self.edge == Edge::Top { line } else { 0.0 };
            (Size::new(width, height), inner, Point::new(0.0, offset))
        };
        let child = self
            .content
            .as_widget_mut()
            .layout(
                &mut tree.children[0],
                renderer,
                &layout::Limits::new(Size::ZERO, content)
                    .width(Length::Fill)
                    .height(Length::Fill),
            )
            .move_to(offset);
        layout::Node::with_children(size, vec![child])
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        self.content.as_widget_mut().operate(
            &mut tree.children[0],
            layout.children().next().unwrap(),
            renderer,
            operation,
        );
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
        let bounds = layout.bounds();
        let horizontal = self.edge.horizontal();
        let along = |p: Point| if horizontal { p.x } else { p.y };
        let state = tree.state.downcast_mut::<ResizeState>();
        match event {
            Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left)) => {
                if let Some(at) = cursor.position_over(self.handle_bounds(bounds)) {
                    let current = if horizontal {
                        bounds.width
                    } else {
                        bounds.height
                    };
                    state.drag = Some((along(at), current));
                    shell.capture_event();
                    shell.request_redraw();
                    return;
                }
            }
            Event::Mouse(mouse::Event::CursorMoved { position }) => {
                if let Some((start, from)) = state.drag {
                    let delta = along(*position) - start;
                    let grow = match self.edge {
                        Edge::Right | Edge::Bottom => delta,
                        Edge::Left | Edge::Top => -delta,
                    };
                    state.dragged = Some((from + grow).clamp(self.min, self.max));
                    shell.invalidate_layout();
                    shell.request_redraw();
                    shell.capture_event();
                    return;
                }
            }
            Event::Mouse(mouse::Event::ButtonReleased(mouse::Button::Left))
                if state.drag.take().is_some() =>
            {
                if let (Some(on_resize), Some(size)) = (&self.on_resize, state.dragged) {
                    shell.publish(on_resize(size));
                }
                shell.capture_event();
                shell.request_redraw();
                return;
            }
            _ => {}
        }
        self.content.as_widget_mut().update(
            &mut tree.children[0],
            event,
            layout.children().next().unwrap(),
            cursor,
            renderer,
            clipboard,
            shell,
            viewport,
        );
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
        renderer: &Renderer,
    ) -> mouse::Interaction {
        let state = tree.state.downcast_ref::<ResizeState>();
        if self.active(state, layout.bounds(), cursor) {
            return if self.edge.horizontal() {
                mouse::Interaction::ResizingHorizontally
            } else {
                mouse::Interaction::ResizingVertically
            };
        }
        self.content.as_widget().mouse_interaction(
            &tree.children[0],
            layout.children().next().unwrap(),
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
        self.content.as_widget().draw(
            &tree.children[0],
            renderer,
            theme,
            style,
            layout.children().next().unwrap(),
            cursor,
            viewport,
        );
        let state = tree.state.downcast_ref::<ResizeState>();
        let bounds = layout.bounds();
        let active = self.active(state, bounds, cursor);
        let mut line = self.line_bounds(bounds);
        if active && self.style.line < 2.0 {
            // Thicker while hovered or dragged so the handle is easy to see.
            if self.edge.horizontal() {
                line.x -= 1.0;
                line.width += 2.0;
            } else {
                line.y -= 1.0;
                line.height += 2.0;
            }
        }
        if line.width <= 0.0 || line.height <= 0.0 {
            return;
        }
        let color = if active {
            self.style.hover_color
        } else {
            self.style.color
        };
        renderer.with_layer(bounds.expand(2.0), |renderer| {
            renderer.fill_quad(
                Quad {
                    bounds: line,
                    ..Quad::default()
                },
                Background::Color(color),
            );
        });
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
            layout.children().next().unwrap(),
            renderer,
            viewport,
            translation,
        )
    }
}

impl<'a, Message, Theme, Renderer> From<Resizable<'a, Message, Theme, Renderer>>
    for Element<'a, Message, Theme, Renderer>
where
    Message: 'a,
    Theme: 'a,
    Renderer: iced::advanced::Renderer + 'a,
{
    fn from(resizable: Resizable<'a, Message, Theme, Renderer>) -> Self {
        Element::new(resizable)
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(cell, m)?)?;
    m.add_function(wrap_pyfunction!(resizable, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn auto(n: usize) -> Vec<Placement> {
        vec![
            Placement {
                column_span: 1,
                row_span: 1,
                ..Default::default()
            };
            n
        ]
    }

    #[test]
    fn auto_flow_fills_rows() {
        let (cells, rows) = place(&auto(5), 2);
        assert_eq!(rows, 3);
        assert_eq!(cells[4], (0, 2, 1, 1));
    }

    #[test]
    fn explicit_items_are_skipped_by_auto_flow() {
        let mut items = auto(3);
        items[2] = Placement {
            column: Some(0),
            row: Some(0),
            column_span: 2,
            row_span: 1,
            ..Default::default()
        };
        let (cells, _) = place(&items, 2);
        assert_eq!(cells[2], (0, 0, 2, 1));
        assert_eq!(cells[0], (0, 1, 1, 1));
        assert_eq!(cells[1], (1, 1, 1, 1));
    }

    #[test]
    fn fr_tracks_share_the_rest() {
        let sizes = size_tracks(
            &[Track::Px(100.0), Track::Fr(1.0), Track::Fr(3.0)],
            10.0,
            520.0,
            |_| 0.0,
        );
        assert_eq!(sizes, vec![100.0, 100.0, 300.0]);
    }

    #[test]
    fn auto_tracks_shrink_to_fit() {
        let sizes = size_tracks(
            &[Track::Px(100.0), Track::Auto, Track::Fr(1.0)],
            0.0,
            300.0,
            |_| 500.0,
        );
        assert_eq!(sizes, vec![100.0, 200.0, 0.0]);
    }

    #[test]
    fn fr_tracks_act_as_auto_when_unbounded() {
        let sizes = size_tracks(&[Track::Fr(1.0)], 0.0, f32::INFINITY, |_| 42.0);
        assert_eq!(sizes, vec![42.0]);
    }
}
