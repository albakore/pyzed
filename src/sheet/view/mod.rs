//! The spreadsheet grid widget (`pz.sheet`): draws only the visible cells of a workbook and
//! handles selection, typing, the formula bar, the keyboard shortcuts of Sheets and Excel,
//! copy and paste, resizing, filling and the reference picking of formulas.
//!
//! The widget keeps its state (what is being typed, what is being dragged) in the workbook
//! itself (`Book::ui`), so it survives when the view is rebuilt and Python can read it.

use std::sync::Arc;
use std::time::Instant;

use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer;
use iced::advanced::widget::operation::Focusable;
use iced::advanced::widget::{Operation, Tree, Widget};
use iced::advanced::{Clipboard, Shell, mouse};
use iced::keyboard::Modifiers;
use iced::{Color, Element, Event, Length, Point, Rectangle, Size, Theme};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use super::Shared;
use super::addr::Area;
use super::model::{Book, Sheet};
use crate::app::Message;
use crate::widget::PyMsg;

pub mod edit;
pub mod geo;
mod input;
pub mod paint;

pub use edit::Edit;

type Renderer = iced::Renderer;

/// The colors of the grid (from the theme, set by Python).
#[derive(Debug, Clone)]
pub struct Colors {
    pub background: Color,
    pub grid: Color,
    pub header: Color,
    pub header_text: Color,
    pub header_active: Color,
    pub header_active_text: Color,
    pub text: Color,
    pub muted: Color,
    pub accent: Color,
    pub selection: Color,
    pub frozen: Color,
    pub editor: Color,
    pub border: Color,
    pub error: Color,
    pub note: Color,
    pub popup: Color,
    pub popup_text: Color,
    pub popup_selected: Color,
    /// Colors of the references of a formula being typed.
    pub refs: Vec<Color>,
}

fn rgb(hex: u32) -> Color {
    Color::from_rgb8((hex >> 16) as u8, (hex >> 8) as u8, hex as u8)
}

impl Default for Colors {
    fn default() -> Self {
        Colors {
            background: rgb(0xffffff),
            grid: rgb(0xe2e3e3),
            header: rgb(0xf8f9fa),
            header_text: rgb(0x5f6368),
            header_active: rgb(0xd3e3fd),
            header_active_text: rgb(0x0b57d0),
            text: rgb(0x202124),
            muted: rgb(0x80868b),
            accent: rgb(0x1a73e8),
            selection: Color {
                a: 0.12,
                ..rgb(0x1a73e8)
            },
            frozen: rgb(0xc4c7c5),
            editor: rgb(0xffffff),
            border: rgb(0xc4c7c5),
            error: rgb(0xd93025),
            note: rgb(0xf9ab00),
            popup: rgb(0xffffff),
            popup_text: rgb(0x202124),
            popup_selected: rgb(0xe8f0fe),
            refs: [
                0x1a73e8, 0xd93025, 0x9334e6, 0x188038, 0xe37400, 0x007b83, 0xc5221f, 0x8430ce,
            ]
            .into_iter()
            .map(rgb)
            .collect(),
        }
    }
}

/// What `pz.sheet(...)` was given.
pub struct SheetProps {
    pub book: Shared,
    pub colors: Colors,
    pub text_size: f32,
    pub formula_bar: bool,
    pub headers: bool,
    pub width: Length,
    pub height: Length,
    pub readonly: bool,
    pub on_change: Option<PyMsg>,
    pub on_select: Option<PyMsg>,
    pub on_context: Option<PyMsg>,
    pub on_dropdown: Option<PyMsg>,
    pub on_filter: Option<PyMsg>,
    pub on_find: Option<PyMsg>,
    pub on_invalid: Option<PyMsg>,
    pub on_edit: Option<PyMsg>,
}

/// What the mouse is dragging.
#[derive(Debug, Clone)]
pub enum Drag {
    Cells,
    Rows,
    Cols,
    ResizeCol {
        col: u32,
        start: f32,
        size: f32,
        now: f32,
    },
    ResizeRow {
        row: u32,
        start: f32,
        size: f32,
        now: f32,
    },
    Fill {
        source: Area,
    },
    VScroll {
        grab: f32,
    },
    HScroll {
        grab: f32,
    },
    Point {
        anchor: (u32, u32),
    },
    Text,
}

/// The widget's state, kept in the workbook (see the module docs).
#[derive(Debug, Default)]
pub struct Ui {
    pub focused: bool,
    pub edit: Option<Edit>,
    pub drag: Option<Drag>,
    /// Scroll to the active cell on the next frame.
    pub reveal: bool,
    pub pointer: Option<Point>,
    pub last_click: Option<(Instant, Point)>,
    pub modifiers: Modifiers,
    pub fill_target: Option<Area>,
    pub preedit: Option<String>,
    /// When the caret last moved (it blinks from there).
    pub blink: Option<Instant>,
    /// The name box being typed in (to go to a cell or range).
    pub name: Option<String>,
    pub hover: Option<(u32, u32)>,
}

/// Something to tell Python (sent after the workbook is unlocked).
#[derive(Debug, Clone)]
pub enum Emit {
    Change {
        action: &'static str,
        range: String,
    },
    Select,
    Context {
        kind: &'static str,
        cell: String,
        x: f32,
        y: f32,
    },
    Dropdown {
        cell: String,
        options: Vec<String>,
        x: f32,
        y: f32,
        width: f32,
    },
    Filter {
        column: String,
        x: f32,
        y: f32,
    },
    Find(&'static str),
    Invalid {
        cell: String,
        value: String,
        message: Option<String>,
    },
    Edit(bool),
}

pub struct SheetView {
    props: Arc<SheetProps>,
}

impl SheetView {
    pub fn new(props: Arc<SheetProps>) -> Self {
        SheetView { props }
    }
}

/// Roughly how wide column `col` must be to show its values (for autofit).
pub fn estimate_width(book: &Book, sheet: usize, col: u32) -> f32 {
    let s = &book.sheets[sheet];
    let mut w = 40.0f32;
    if let Some(m) = s.cols.get(col as usize) {
        for (&r, _) in m.iter().take(5000) {
            let shown = book.shown(sheet, r, col);
            if shown.text.is_empty() {
                continue;
            }
            let size = paint::font_px(shown.size, 13.0);
            let font = paint::font_for(shown.bold, shown.italic, shown.mono);
            let text = shown.text.lines().next().unwrap_or("");
            let extra = if shown.dropdown { 22.0 } else { 0.0 };
            w = w.max(paint::measure(text, font, size) + 2.0 * paint::PAD + 6.0 + extra);
        }
    }
    w.min(600.0).ceil()
}

/// Shows the active cell on the next frame.
pub fn request_reveal(book: &mut Book) {
    book.ui.reveal = true;
}

fn lock(book: &Shared) -> std::sync::MutexGuard<'_, Book> {
    book.lock().unwrap_or_else(|e| e.into_inner())
}

struct FocusProxy<'a>(&'a mut Ui);

impl Focusable for FocusProxy<'_> {
    fn is_focused(&self) -> bool {
        self.0.focused
    }

    fn focus(&mut self) {
        self.0.focused = true;
    }

    fn unfocus(&mut self) {
        self.0.focused = false;
    }
}

impl Widget<Message, Theme, Renderer> for SheetView {
    fn size(&self) -> Size<Length> {
        Size::new(self.props.width, self.props.height)
    }

    fn layout(
        &mut self,
        _tree: &mut Tree,
        _renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        let size = limits.resolve(self.props.width, self.props.height, Size::new(640.0, 400.0));
        layout::Node::new(size)
    }

    fn operate(
        &mut self,
        _tree: &mut Tree,
        layout: Layout<'_>,
        _renderer: &Renderer,
        operation: &mut dyn Operation,
    ) {
        let mut book = lock(&self.props.book);
        operation.focusable(None, layout.bounds(), &mut FocusProxy(&mut book.ui));
    }

    fn update(
        &mut self,
        _tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        _renderer: &Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        _viewport: &Rectangle,
    ) {
        let mut emits = Vec::new();
        let sheet_name;
        let editing_before;
        let editing_after;
        {
            let mut book = lock(&self.props.book);
            editing_before = book.ui.edit.is_some();
            input::handle(
                &self.props,
                &mut book,
                layout.bounds(),
                event,
                cursor,
                clipboard,
                shell,
                &mut emits,
            );
            editing_after = book.ui.edit.is_some();
            sheet_name = book.sheet().name.clone();
        }
        if editing_before != editing_after {
            emits.push(Emit::Edit(editing_after));
        }
        let size = layout.bounds().size();
        publish(&self.props, emits, &sheet_name, size, shell);
    }

    fn mouse_interaction(
        &self,
        _tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        _viewport: &Rectangle,
        _renderer: &Renderer,
    ) -> mouse::Interaction {
        let book = lock(&self.props.book);
        input::interaction(&self.props, &book, layout.bounds(), cursor)
    }

    fn draw(
        &self,
        _tree: &Tree,
        renderer: &mut Renderer,
        _theme: &Theme,
        _style: &renderer::Style,
        layout: Layout<'_>,
        _cursor: mouse::Cursor,
        _viewport: &Rectangle,
    ) {
        let mut book = lock(&self.props.book);
        paint::paint(&self.props, &mut book, renderer, layout.bounds());
    }
}

impl<'a> From<SheetView> for Element<'a, Message, Theme, Renderer> {
    fn from(view: SheetView) -> Self {
        Element::new(view)
    }
}

/// Sends the events to Python (with the workbook unlocked: Python may lock it).
fn publish(
    props: &SheetProps,
    emits: Vec<Emit>,
    sheet: &str,
    size: Size,
    shell: &mut Shell<'_, Message>,
) {
    if emits.is_empty() {
        return;
    }
    Python::attach(|py| {
        for e in emits {
            let (cb, value) = match build(py, props, &e, sheet, size) {
                Ok(Some(x)) => x,
                Ok(None) => continue,
                Err(err) => {
                    err.print(py);
                    continue;
                }
            };
            shell.publish(Message::Call(cb, PyMsg::new(&value)));
        }
    });
}

fn build<'py>(
    py: Python<'py>,
    props: &SheetProps,
    e: &Emit,
    sheet: &str,
    size: Size,
) -> PyResult<Option<(PyMsg, Bound<'py, PyAny>)>> {
    let d = PyDict::new(py);
    d.set_item("sheet", sheet)?;
    // The grid's own size, so menus opened at x/y can be kept inside it.
    d.set_item("view_width", size.width)?;
    d.set_item("view_height", size.height)?;
    let cb = match e {
        Emit::Change { action, range } => {
            d.set_item("action", *action)?;
            d.set_item("range", range)?;
            &props.on_change
        }
        Emit::Select => &props.on_select,
        Emit::Context { kind, cell, x, y } => {
            d.set_item("kind", *kind)?;
            d.set_item("cell", cell)?;
            d.set_item("x", *x)?;
            d.set_item("y", *y)?;
            &props.on_context
        }
        Emit::Dropdown {
            cell,
            options,
            x,
            y,
            width,
        } => {
            d.set_item("cell", cell)?;
            d.set_item("options", PyList::new(py, options)?)?;
            d.set_item("x", *x)?;
            d.set_item("y", *y)?;
            d.set_item("width", *width)?;
            &props.on_dropdown
        }
        Emit::Filter { column, x, y } => {
            d.set_item("column", column)?;
            d.set_item("x", *x)?;
            d.set_item("y", *y)?;
            &props.on_filter
        }
        Emit::Find(mode) => {
            d.set_item("mode", *mode)?;
            &props.on_find
        }
        Emit::Invalid {
            cell,
            value,
            message,
        } => {
            d.set_item("cell", cell)?;
            d.set_item("value", value)?;
            d.set_item("message", message)?;
            &props.on_invalid
        }
        Emit::Edit(editing) => {
            d.set_item("editing", *editing)?;
            &props.on_edit
        }
    };
    Ok(cb.clone().map(|cb| (cb, d.into_any())))
}

/// The selection's last range, for messages.
pub fn selection_text(s: &Sheet) -> String {
    s.selection.range().to_string()
}
