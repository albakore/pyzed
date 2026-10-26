//! Custom widgets used by the code editor: the cursors (`Caret`), the boxes behind and around
//! the text (`Boxes`: other cursors' selections, search results, matching brackets), the
//! `Minimap` and `EditorInput` (tracks the modifiers; Ctrl + mouse wheel changes the font size).

use std::cell::Cell;
use std::time::{Duration, Instant};

use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer::{self, Quad};
use iced::advanced::text::{self as core_text, Renderer as _};
use iced::advanced::widget::{self, Tree, Widget, tree};
use iced::advanced::{Clipboard, Shell, input_method, mouse, overlay};
use iced::widget::text::LineHeight;
use iced::widget::text_editor;
use iced::{
    Background, Border, Color, Element, Event, Font, Length, Pixels, Point, Rectangle, Size, Theme,
    Vector, keyboard, window,
};

use crate::app::Message;
use crate::editor::{EditorState, PAD_LEFT, PAD_Y, scroll_id};
use crate::widget::PyMsg;

type Renderer = iced::Renderer;

const BLINK: Duration = Duration::from_millis(500);

/// How the text cursor is drawn (like Zed's `cursor_shape`).
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub enum CaretShape {
    #[default]
    Bar,
    Block,
    Underline,
    Hollow,
}

impl CaretShape {
    pub fn parse(name: &str) -> Option<Self> {
        Some(match name {
            "bar" | "line" => Self::Bar,
            "block" => Self::Block,
            "underline" | "underscore" => Self::Underline,
            "hollow" => Self::Hollow,
            _ => return None,
        })
    }
}

/// The text cursor, drawn on top of the editor while it has focus.
pub struct Caret<'a> {
    pub state: &'a EditorState,
    /// Top-left corner of the cursor's cell, relative to the text layer.
    pub origin: Point,
    pub char_width: f32,
    pub line_height: f32,
    pub shape: CaretShape,
    pub width: f32,
    pub blink: bool,
    pub color: Color,
    /// The glyph under a block cursor, redrawn in `under_color`.
    pub under: Option<char>,
    pub under_color: Color,
    pub font: Font,
    pub size: f32,
    /// The cursor has a selection (it is hidden then, like iced's own).
    pub selecting: bool,
    /// The text editor's own cursor: hidden as soon as it selects, since a selection drag moves
    /// it without building the editor again.
    pub primary: bool,
}

#[derive(Default)]
struct CaretState {
    /// Where the cursor was last drawn and since when (blinking restarts when it moves).
    moved: Cell<Option<(Point, Instant)>>,
    window_focused: Cell<bool>,
}

impl Caret<'_> {
    fn visible(&self, state: &CaretState) -> bool {
        if !self.state.focused.get()
            || !state.window_focused.get()
            || self.selecting
            || (self.primary && self.state.content.cursor().selection.is_some())
            || self.state.composing.get()
        {
            return false;
        }
        let now = crate::recorder::now();
        let since = match state.moved.get() {
            Some((at, since)) if at == self.origin => since,
            _ => {
                state.moved.set(Some((self.origin, now)));
                now
            }
        };
        !self.blink || ((now - since).as_millis() / BLINK.as_millis()).is_multiple_of(2)
    }
}

impl Widget<Message, Theme, Renderer> for Caret<'_> {
    fn tag(&self) -> tree::Tag {
        tree::Tag::of::<CaretState>()
    }

    fn state(&self) -> tree::State {
        tree::State::new(CaretState {
            moved: Cell::new(None),
            window_focused: Cell::new(true),
        })
    }

    fn size(&self) -> Size<Length> {
        Size::new(Length::Shrink, Length::Shrink)
    }

    fn layout(&mut self, _: &mut Tree, _: &Renderer, _: &layout::Limits) -> layout::Node {
        layout::Node::new(Size::ZERO)
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        _layout: Layout<'_>,
        _cursor: mouse::Cursor,
        _renderer: &Renderer,
        _clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        _viewport: &Rectangle,
    ) {
        let state = tree.state.downcast_ref::<CaretState>();
        match event {
            Event::Window(window::Event::Focused) => {
                state.window_focused.set(true);
                state.moved.set(None);
                shell.request_redraw();
            }
            Event::Window(window::Event::Unfocused) => {
                state.window_focused.set(false);
                shell.request_redraw();
            }
            Event::Window(window::Event::RedrawRequested(now))
                if self.blink && self.state.focused.get() && state.window_focused.get() =>
            {
                let since = state.moved.get().map_or(*now, |(_, since)| since);
                let elapsed = now.saturating_duration_since(since).as_millis();
                let wait = BLINK.as_millis() - elapsed % BLINK.as_millis();
                shell.request_redraw_at(*now + Duration::from_millis(wait as u64));
            }
            _ => {}
        }
    }

    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut Renderer,
        _theme: &Theme,
        _style: &renderer::Style,
        layout: Layout<'_>,
        _cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        let state = tree.state.downcast_ref::<CaretState>();
        if !self.visible(state) {
            return;
        }
        use iced::advanced::Renderer as _;
        let at = layout.bounds().position() + Vector::new(self.origin.x, self.origin.y);
        let (lh, cw) = (self.line_height, self.char_width);
        let width = self.width.max(1.0);
        let bounds = match self.shape {
            CaretShape::Bar => Rectangle::new(at, Size::new(width, lh)),
            CaretShape::Block | CaretShape::Hollow => Rectangle::new(at, Size::new(cw, lh)),
            CaretShape::Underline => Rectangle::new(
                Point::new(at.x, at.y + lh - width.max(2.0)),
                Size::new(cw, width.max(2.0)),
            ),
        };
        if !bounds.intersects(viewport) {
            return;
        }
        if self.shape == CaretShape::Hollow {
            renderer.fill_quad(
                Quad {
                    bounds,
                    border: Border {
                        color: self.color,
                        width: 1.0,
                        radius: 0.0.into(),
                        ..Default::default()
                    },
                    ..Quad::default()
                },
                Background::Color(Color::TRANSPARENT),
            );
            return;
        }
        renderer.fill_quad(
            Quad {
                bounds,
                ..Quad::default()
            },
            Background::Color(self.color),
        );
        if self.shape == CaretShape::Block
            && let Some(ch) = self.under
        {
            renderer.fill_text(
                core_text::Text {
                    content: ch.to_string(),
                    bounds: Size::new(cw * 2.0, lh),
                    size: Pixels(self.size),
                    line_height: LineHeight::Absolute(Pixels(lh)),
                    font: self.font,
                    align_x: core_text::Alignment::Default,
                    align_y: iced::alignment::Vertical::Top,
                    shaping: core_text::Shaping::Advanced,
                    wrapping: core_text::Wrapping::None,
                    letter_spacing: iced::Em::ZERO,
                },
                at,
                self.under_color,
                *viewport,
            );
        }
    }
}

impl<'a> From<Caret<'a>> for Element<'a, Message> {
    fn from(caret: Caret<'a>) -> Self {
        Element::new(caret)
    }
}

// ---------------------------------------------------------------------------
// Line numbers
// ---------------------------------------------------------------------------

/// The gutter's line numbers. Only the ones on screen are drawn: a long file has thousands, and
/// one text with all of them was laid out again on every edit that adds or removes a line.
pub struct LineNumbers<'a> {
    /// The first row of each visible line, and one past the last (folds and wrapped lines).
    pub starts: Vec<u32>,
    /// The line (from 0) each visible line shows.
    pub reals: Vec<usize>,
    /// The number of the cursor's line is drawn in `active` (read when drawing: a selection
    /// drag moves the cursor without building the editor again).
    pub state: &'a EditorState,
    pub width: f32,
    pub padding: iced::Padding,
    pub line_height: f32,
    pub font: Font,
    pub size: f32,
    pub color: Color,
    pub active: Color,
}

impl LineNumbers<'_> {
    fn height(&self) -> f32 {
        let rows = self.starts.last().copied().unwrap_or(0);
        rows as f32 * self.line_height + self.padding.top + self.padding.bottom
    }
}

impl Widget<Message, Theme, Renderer> for LineNumbers<'_> {
    fn size(&self) -> Size<Length> {
        Size::new(Length::Fixed(self.width), Length::Fixed(self.height()))
    }

    fn layout(&mut self, _: &mut Tree, _: &Renderer, _: &layout::Limits) -> layout::Node {
        layout::Node::new(Size::new(self.width, self.height()))
    }

    fn draw(
        &self,
        _tree: &Tree,
        renderer: &mut Renderer,
        _theme: &Theme,
        _style: &renderer::Style,
        layout: Layout<'_>,
        _cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        let bounds = layout.bounds();
        let lh = self.line_height.max(1.0);
        let Some(visible) = bounds.intersection(viewport) else {
            return;
        };
        let top = bounds.y + self.padding.top;
        let first = ((visible.y - top) / lh).floor().max(0.0) as u32;
        let last = ((visible.y + visible.height - top) / lh).ceil().max(0.0) as u32;
        let right = bounds.x + bounds.width - self.padding.right;
        let width = (bounds.width - self.padding.left - self.padding.right).max(0.0);
        let lines = self.reals.len().min(self.starts.len().saturating_sub(1));
        let from = self.starts[..lines].partition_point(|start| *start <= first);
        let cursor = self.state.content.cursor().position.line;
        for n in from.saturating_sub(1)..lines {
            let row = self.starts[n];
            if row >= last {
                break;
            }
            renderer.fill_text(
                core_text::Text {
                    content: (self.reals[n] + 1).to_string(),
                    bounds: Size::new(width, lh),
                    size: Pixels(self.size),
                    line_height: LineHeight::Absolute(Pixels(lh)),
                    font: self.font,
                    align_x: core_text::Alignment::Right,
                    align_y: iced::alignment::Vertical::Top,
                    shaping: core_text::Shaping::Basic,
                    wrapping: core_text::Wrapping::None,
                    letter_spacing: iced::Em::ZERO,
                },
                Point::new(right, top + row as f32 * lh),
                if n == cursor { self.active } else { self.color },
                bounds,
            );
        }
    }
}

impl<'a> From<LineNumbers<'a>> for Element<'a, Message> {
    fn from(numbers: LineNumbers<'a>) -> Self {
        Element::new(numbers)
    }
}

/// The band behind the cursor's line, placed when drawn: a selection drag moves the cursor
/// without building the editor again. Always there, transparent without a `color`: it gives the
/// text layers their size.
pub struct ActiveLine<'a> {
    pub state: &'a EditorState,
    /// The first row of each visible line, and one past the last (folds and wrapped lines).
    pub starts: Vec<u32>,
    pub line_height: f32,
    pub size: Size,
    pub color: Option<Color>,
}

impl Widget<Message, Theme, Renderer> for ActiveLine<'_> {
    fn size(&self) -> Size<Length> {
        Size::new(
            Length::Fixed(self.size.width),
            Length::Fixed(self.size.height),
        )
    }

    fn layout(&mut self, _: &mut Tree, _: &Renderer, _: &layout::Limits) -> layout::Node {
        layout::Node::new(self.size)
    }

    fn draw(
        &self,
        _tree: &Tree,
        renderer: &mut Renderer,
        _theme: &Theme,
        _style: &renderer::Style,
        layout: Layout<'_>,
        _cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        use iced::advanced::Renderer as _;
        let (Some(color), Some(last)) = (self.color, self.starts.len().checked_sub(2)) else {
            return;
        };
        let line = self.state.content.cursor().position.line.min(last);
        let (first, next) = (self.starts[line], self.starts[line + 1]);
        let bounds = layout.bounds();
        let band = Rectangle {
            x: bounds.x,
            y: bounds.y + PAD_Y + first as f32 * self.line_height,
            width: bounds.width,
            height: (next - first) as f32 * self.line_height,
        };
        if band.intersects(viewport) {
            renderer.fill_quad(
                Quad {
                    bounds: band,
                    ..Quad::default()
                },
                Background::Color(color),
            );
        }
    }
}

impl<'a> From<ActiveLine<'a>> for Element<'a, Message> {
    fn from(band: ActiveLine<'a>) -> Self {
        Element::new(band)
    }
}

// ---------------------------------------------------------------------------
// FoldMarks
// ---------------------------------------------------------------------------

/// The fold chevrons of the gutter. Folded lines always show theirs; the other foldable lines
/// only while the mouse is over the gutter (`reach` is how far it goes to the left). Only the
/// chevrons on screen are drawn: a widget per chevron made long files slow to draw and hover.
pub struct FoldMarks {
    /// The first row of each visible line, and one past the last.
    pub starts: Vec<u32>,
    /// `(visible line, folded)`, sorted by line.
    pub marks: Vec<(usize, bool)>,
    /// The message of a click on the chevron of a visible line.
    pub on_toggle: Box<dyn Fn(usize) -> Message>,
    pub width: f32,
    pub reach: f32,
    pub top: f32,
    pub line_height: f32,
    pub font: Font,
    pub glyphs: (char, char),
    pub size: f32,
    pub color: Color,
    pub hover: Color,
}

#[derive(Default, Clone, Copy, PartialEq)]
struct FoldState {
    /// The mouse is over the gutter.
    gutter: bool,
    /// The visible line whose chevron is under the mouse.
    hovered: Option<usize>,
}

impl FoldMarks {
    fn height(&self) -> f32 {
        let rows = self.starts.last().copied().unwrap_or(0);
        rows as f32 * self.line_height + self.top * 2.0
    }

    fn row_bounds(&self, bounds: Rectangle, line: usize) -> Rectangle {
        let y = bounds.y + self.top + self.starts[line] as f32 * self.line_height;
        Rectangle::new(
            Point::new(bounds.x, y),
            Size::new(bounds.width, self.line_height),
        )
    }

    fn state_at(&self, bounds: Rectangle, cursor: mouse::Cursor) -> FoldState {
        let Some(p) = cursor.position() else {
            return FoldState::default();
        };
        let gutter = Rectangle {
            x: bounds.x - self.reach,
            width: bounds.width + self.reach,
            ..bounds
        };
        if !gutter.contains(p) {
            return FoldState::default();
        }
        let lh = self.line_height.max(1.0);
        let row = ((p.y - bounds.y - self.top) / lh).floor();
        let hovered = (row >= 0.0 && bounds.contains(p))
            .then(|| {
                let row = row as u32;
                let at = self
                    .marks
                    .partition_point(|(line, _)| self.starts[*line] < row);
                self.marks
                    .get(at)
                    .filter(|(line, _)| self.starts[*line] == row)
                    .map(|(line, _)| *line)
            })
            .flatten();
        FoldState {
            gutter: true,
            hovered,
        }
    }
}

impl Widget<Message, Theme, Renderer> for FoldMarks {
    fn tag(&self) -> tree::Tag {
        tree::Tag::of::<FoldState>()
    }

    fn state(&self) -> tree::State {
        tree::State::new(FoldState::default())
    }

    fn size(&self) -> Size<Length> {
        Size::new(Length::Fixed(self.width), Length::Fixed(self.height()))
    }

    fn layout(&mut self, _: &mut Tree, _: &Renderer, _: &layout::Limits) -> layout::Node {
        layout::Node::new(Size::new(self.width, self.height()))
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        _renderer: &Renderer,
        _clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        _viewport: &Rectangle,
    ) {
        let bounds = layout.bounds();
        match event {
            Event::Mouse(mouse::Event::CursorMoved { .. } | mouse::Event::CursorLeft) => {
                let now = self.state_at(bounds, cursor);
                let state = tree.state.downcast_mut::<FoldState>();
                if now != *state {
                    *state = now;
                    shell.request_redraw();
                }
            }
            Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left)) => {
                let now = self.state_at(bounds, cursor);
                if let Some(line) = now.hovered {
                    shell.publish((self.on_toggle)(line));
                    shell.capture_event();
                }
            }
            _ => {}
        }
    }

    fn mouse_interaction(
        &self,
        _tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        _viewport: &Rectangle,
        _renderer: &Renderer,
    ) -> mouse::Interaction {
        if self.state_at(layout.bounds(), cursor).hovered.is_some() {
            mouse::Interaction::Pointer
        } else {
            mouse::Interaction::default()
        }
    }

    fn draw(
        &self,
        _tree: &Tree,
        renderer: &mut Renderer,
        _theme: &Theme,
        _style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        let bounds = layout.bounds();
        let Some(visible) = bounds.intersection(viewport) else {
            return;
        };
        let lh = self.line_height.max(1.0);
        let state = self.state_at(bounds, cursor);
        let first = ((visible.y - bounds.y - self.top) / lh).floor().max(0.0) as u32;
        let last = ((visible.y + visible.height - bounds.y - self.top) / lh)
            .ceil()
            .max(0.0) as u32;
        let from = self
            .marks
            .partition_point(|(line, _)| self.starts[*line] < first);
        for &(line, folded) in &self.marks[from..] {
            if self.starts[line] >= last {
                break;
            }
            if !folded && !state.gutter {
                continue;
            }
            let row = self.row_bounds(bounds, line);
            renderer.fill_text(
                core_text::Text {
                    content: if folded { self.glyphs.1 } else { self.glyphs.0 }.to_string(),
                    bounds: row.size(),
                    size: Pixels(self.size),
                    line_height: LineHeight::Absolute(Pixels(lh)),
                    font: self.font,
                    align_x: core_text::Alignment::Center,
                    align_y: iced::alignment::Vertical::Top,
                    shaping: core_text::Shaping::Basic,
                    wrapping: core_text::Wrapping::None,
                    letter_spacing: iced::Em::ZERO,
                },
                Point::new(row.center_x(), row.y),
                if state.hovered == Some(line) {
                    self.hover
                } else {
                    self.color
                },
                bounds,
            );
        }
    }
}

impl<'a> From<FoldMarks> for Element<'a, Message> {
    fn from(marks: FoldMarks) -> Self {
        Element::new(marks)
    }
}

// ---------------------------------------------------------------------------
// Boxes
// ---------------------------------------------------------------------------

/// A rectangle drawn by `Boxes`, relative to the text layer.
pub struct BoxRect {
    pub bounds: Rectangle,
    /// `None`: the theme's selection color.
    pub fill: Option<Color>,
    pub alpha: f32,
    pub border: Option<Color>,
}

/// Indent guides: a thin line at each level of indentation of the visible lines, through the
/// blank lines of a block, the one of the block around the cursor brighter (like Zed's). With
/// several colors they take turns by depth (rainbow guides).
pub struct IndentGuides<'a> {
    pub state: &'a EditorState,
    /// The guide colors by depth (taking turns), and the color of the active guide at each depth.
    pub colors: Vec<Color>,
    pub active: Vec<Color>,
    /// Columns per level of indentation, and the width of a column.
    pub tab: usize,
    pub column: f32,
    pub line_height: f32,
}

/// How many levels a line is indented (tabs reach the next multiple of `tab` columns), or
/// `None` for a blank line.
pub(crate) fn indent_level(line: &str, tab: usize) -> Option<usize> {
    let tab = tab.max(1);
    let mut columns = 0;
    for c in line.chars() {
        match c {
            ' ' => columns += 1,
            '\t' => columns = (columns / tab + 1) * tab,
            c if c.is_whitespace() => {}
            _ => return Some(columns / tab),
        }
    }
    None
}

/// The level of each line in `lines` (from `level(i)`), a blank line taking the smaller level of
/// the lines around it (looking at most `reach` lines away).
pub(crate) fn guide_levels(
    level: &dyn Fn(usize) -> Option<Option<usize>>,
    lines: std::ops::Range<usize>,
    reach: usize,
) -> Vec<usize> {
    let mut above = 0;
    for i in (lines.start.saturating_sub(reach)..lines.start).rev() {
        if let Some(Some(l)) = level(i) {
            above = l;
            break;
        }
    }
    let mut out = Vec::with_capacity(lines.len());
    let mut below: Option<(usize, usize)> = None; // (line, level) of the next non-blank line
    for i in lines.clone() {
        match level(i) {
            Some(Some(l)) => {
                above = l;
                out.push(l);
            }
            Some(None) => {
                if below.is_none_or(|(at, _)| at <= i) {
                    below = (i + 1..i + 1 + reach)
                        .find_map(|j| match level(j) {
                            Some(Some(l)) => Some(Some((j, l))),
                            Some(None) => None,
                            None => Some(None),
                        })
                        .flatten()
                        .or(Some((usize::MAX, 0)));
                }
                out.push(above.min(below.map_or(0, |(_, l)| l)));
            }
            None => break,
        }
    }
    out
}

impl Widget<Message, Theme, Renderer> for IndentGuides<'_> {
    fn size(&self) -> Size<Length> {
        Size::new(Length::Shrink, Length::Shrink)
    }

    fn layout(&mut self, _: &mut Tree, _: &Renderer, _: &layout::Limits) -> layout::Node {
        layout::Node::new(Size::ZERO)
    }

    fn draw(
        &self,
        _tree: &Tree,
        renderer: &mut Renderer,
        _theme: &Theme,
        _style: &renderer::Style,
        layout: Layout<'_>,
        _cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        use iced::advanced::Renderer as _;
        const REACH: usize = 400;
        if self.colors.is_empty() {
            return;
        }
        let m = self.state.metrics.borrow();
        let starts = &m.starts;
        let count = starts.len().saturating_sub(1);
        if count == 0 {
            return;
        }
        let lh = self.line_height.max(1.0);
        let origin = layout.bounds().position();
        let top = viewport.y - origin.y - PAD_Y;
        let bottom = top + viewport.height;
        let first = starts
            .partition_point(|s| *s as f32 * lh <= top)
            .saturating_sub(1)
            .min(count);
        let last = starts
            .partition_point(|s| (*s as f32) * lh < bottom)
            .min(count);
        if first >= last {
            return;
        }
        let content = &self.state.content;
        let level = |i: usize| {
            content
                .line(i)
                .map(|line| indent_level(&line.text, self.tab))
        };
        let levels = guide_levels(&level, first..last, REACH);
        // The block around the cursor: under a header (a line followed by deeper ones), its body.
        let cursor = content.cursor().position.line.min(count - 1);
        let around = guide_levels(&level, cursor..cursor + 2, REACH);
        let here = around.first().copied().unwrap_or(0);
        let next = around.get(1).copied().unwrap_or(0);
        let (depth, anchor) = if next > here {
            (Some(here), cursor + 1)
        } else {
            (here.checked_sub(1), cursor)
        };
        let block = depth.map(|d| {
            // Blank lines don't end the block: the next line that is not blank decides.
            let outside =
                |i: usize| matches!(level(i), Some(Some(l)) if l <= d) || level(i).is_none();
            let mut start = anchor;
            while start > 0 && anchor - start < 4 * REACH && !outside(start - 1) {
                start -= 1;
            }
            let mut end = anchor + 1;
            while end < count && end - anchor < 4 * REACH && !outside(end) {
                end += 1;
            }
            (d, start..end)
        });
        let x_of =
            |d: usize| (origin.x + PAD_LEFT + (d * self.tab) as f32 * self.column).round() + 0.5;
        let mut open: Vec<Option<usize>> = Vec::new();
        let draw = |renderer: &mut Renderer, d: usize, from: usize, to: usize| {
            let active = block
                .as_ref()
                .is_some_and(|(bd, range)| *bd == d && range.start < to && from < range.end);
            let palette = if active && !self.active.is_empty() {
                &self.active
            } else {
                &self.colors
            };
            let y = origin.y + PAD_Y + starts[from] as f32 * lh;
            let height = (starts[to] - starts[from]) as f32 * lh;
            renderer.fill_quad(
                Quad {
                    bounds: Rectangle::new(Point::new(x_of(d) - 0.5, y), Size::new(1.0, height)),
                    ..Quad::default()
                },
                Background::Color(palette[d % palette.len()]),
            );
        };
        for (offset, l) in levels.iter().copied().chain(std::iter::once(0)).enumerate() {
            let i = first + offset;
            for (d, slot) in open.iter_mut().enumerate() {
                if d >= l
                    && let Some(from) = slot.take()
                {
                    draw(renderer, d, from, i);
                }
            }
            if open.len() < l {
                open.resize(l, None);
            }
            for slot in open.iter_mut().take(l) {
                slot.get_or_insert(i);
            }
        }
    }
}

impl<'a> From<IndentGuides<'a>> for Element<'a, Message> {
    fn from(guides: IndentGuides<'a>) -> Self {
        Element::new(guides)
    }
}

/// Rectangles behind or around the text: the selections of the other cursors, search results,
/// the other occurrences of the selection and the matching brackets.
pub struct Boxes<'a> {
    pub rects: Vec<BoxRect>,
    /// Hidden while this editor has a selection (the brackets next to the cursor).
    pub unless_selecting: Option<&'a EditorState>,
}

impl Widget<Message, Theme, Renderer> for Boxes<'_> {
    fn size(&self) -> Size<Length> {
        Size::new(Length::Shrink, Length::Shrink)
    }

    fn layout(&mut self, _: &mut Tree, _: &Renderer, _: &layout::Limits) -> layout::Node {
        layout::Node::new(Size::ZERO)
    }

    fn draw(
        &self,
        _tree: &Tree,
        renderer: &mut Renderer,
        theme: &Theme,
        _style: &renderer::Style,
        layout: Layout<'_>,
        _cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        use iced::advanced::Renderer as _;
        if self
            .unless_selecting
            .is_some_and(|state| state.content.cursor().selection.is_some())
        {
            return;
        }
        let origin = layout.bounds().position();
        let selection = theme.extended_palette().primary.weak.color;
        for rect in &self.rects {
            let bounds = rect.bounds + Vector::new(origin.x, origin.y);
            if !bounds.intersects(viewport) {
                continue;
            }
            let fill = rect.fill.unwrap_or(selection);
            renderer.fill_quad(
                Quad {
                    bounds,
                    border: Border {
                        color: rect.border.unwrap_or(Color::TRANSPARENT),
                        width: if rect.border.is_some() { 1.0 } else { 0.0 },
                        radius: 2.0.into(),
                        ..Default::default()
                    },
                    ..Quad::default()
                },
                Background::Color(Color {
                    a: fill.a * rect.alpha,
                    ..fill
                }),
            );
        }
    }
}

impl<'a> From<Boxes<'a>> for Element<'a, Message> {
    fn from(boxes: Boxes<'a>) -> Self {
        Element::new(boxes)
    }
}

// ---------------------------------------------------------------------------
// Minimap
// ---------------------------------------------------------------------------

/// Height of one line in the minimap, the height of its text and the width of a column.
const MINI_LINE: f32 = 3.0;
const MINI_TEXT: f32 = 2.0;
const MINI_COLUMN: f32 = 1.2;

/// A zoomed-out view of the visible text with the scrolled area highlighted (like Zed's and
/// VS Code's). Clicking scrolls there; dragging the highlighted area scrolls along. When the
/// text is taller than the minimap, the minimap scrolls with the editor.
pub struct Minimap<'a> {
    pub state: &'a EditorState,
    pub width: f32,
    pub height: f32,
    /// Height of an editor line.
    pub line_height: f32,
    pub thumb: Option<Color>,
    /// Covers the text scrolled under the minimap.
    pub background: Option<Color>,
    /// The color of text without a syntax color.
    pub text_color: Color,
}

/// The `(column, length, color)` runs of non-blank text of a highlighted line, with tabs
/// every 4 columns.
fn minimap_runs(
    line: &str,
    spans: &[crate::highlighter::Span],
    fallback: Color,
) -> Vec<(u16, u16, Color)> {
    let mut columns = Vec::with_capacity(line.len() + 1);
    let mut col = 0u16;
    for (i, ch) in line.char_indices() {
        while columns.len() <= i {
            columns.push(col);
        }
        col = if ch == '\t' {
            (col / 4 + 1) * 4
        } else {
            col.saturating_add(1)
        };
    }
    while columns.len() <= line.len() {
        columns.push(col);
    }
    let mut runs = Vec::new();
    for span in spans {
        let color = span.color.unwrap_or(fallback);
        let Some(text) = line.get(span.range.clone()) else {
            continue;
        };
        // Split the span at whitespace so blank stretches stay empty.
        let mut start = None;
        for (i, ch) in text
            .char_indices()
            .chain(std::iter::once((text.len(), ' ')))
        {
            let at = span.range.start + i;
            match (ch.is_whitespace(), start) {
                (false, None) => start = Some(at),
                (true, Some(s)) => {
                    let (a, b) = (columns[s], columns[at]);
                    runs.push((a, b.saturating_sub(a).max(1), color));
                    start = None;
                }
                _ => {}
            }
        }
    }
    runs
}

#[derive(Default)]
struct MinimapState {
    /// While dragging the thumb: where it was grabbed, from its top.
    grab: Option<f32>,
    /// The runs of the lines on screen, by line, with what they were made from (the line's
    /// spans, a hash of its text and the default color): drawing them again reuses them.
    runs: std::cell::RefCell<std::collections::HashMap<usize, MiniRuns>>,
}

type MiniRuns = ((usize, u64, u32), Vec<(u16, u16, Color)>);

/// Scroll geometry shared by drawing and input.
struct Geometry {
    /// Scroll offset of the editor and its largest value.
    scroll: f32,
    max_scroll: f32,
    viewport: f32,
    /// How far the minimap is scrolled.
    offset: f32,
    /// Minimap pixels the minimap scrolls per editor pixel.
    ratio: f32,
    thumb_top: f32,
    thumb_height: f32,
}

impl Minimap<'_> {
    fn geometry(&self, bounds: Rectangle) -> Option<Geometry> {
        let viewport = self.state.viewport.get()?;
        let metrics = self.state.metrics.borrow();
        let rows = *metrics.starts.last()? as f32;
        let lh = self.line_height.max(1.0);
        let content = 2.0 * PAD_Y + rows * lh;
        let max_scroll = (content - viewport.height).max(0.0);
        let mini = rows * MINI_LINE;
        let ratio = if mini > bounds.height && max_scroll > 0.0 {
            (mini - bounds.height) / max_scroll
        } else {
            0.0
        };
        let scroll = viewport.y.clamp(0.0, max_scroll);
        let offset = scroll * ratio;
        Some(Geometry {
            scroll,
            max_scroll,
            viewport: viewport.height,
            offset,
            ratio,
            thumb_top: scroll / lh * MINI_LINE - offset,
            thumb_height: (viewport.height / lh * MINI_LINE).min(bounds.height),
        })
    }

    /// Scrolls the editor on the next frame, through `EditorInput`: no message, so dragging the
    /// thumb does not build the app again (like scrolling with the wheel).
    fn scroll_to(&self, y: f32, g: &Geometry, shell: &mut Shell<'_, Message>) {
        let y = y.clamp(0.0, g.max_scroll);
        if (y - g.scroll).abs() >= 0.5 {
            self.state
                .scroll
                .set(Some(iced::widget::scrollable::AbsoluteOffset {
                    x: None,
                    y: Some(y),
                }));
            shell.request_redraw();
        }
    }

    /// The editor offset that puts the thumb's top at `top`.
    fn scroll_for_thumb(&self, top: f32, g: &Geometry) -> f32 {
        let per_pixel = MINI_LINE / self.line_height.max(1.0) - g.ratio;
        if per_pixel <= 0.0 {
            return g.scroll;
        }
        top / per_pixel
    }
}

impl Widget<Message, Theme, Renderer> for Minimap<'_> {
    fn tag(&self) -> tree::Tag {
        tree::Tag::of::<MinimapState>()
    }

    fn state(&self) -> tree::State {
        tree::State::new(MinimapState::default())
    }

    fn size(&self) -> Size<Length> {
        Size::new(Length::Fixed(self.width), Length::Fixed(self.height))
    }

    fn layout(&mut self, _: &mut Tree, _: &Renderer, _: &layout::Limits) -> layout::Node {
        layout::Node::new(Size::new(self.width, self.height))
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        _renderer: &Renderer,
        _clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        _viewport: &Rectangle,
    ) {
        let bounds = layout.bounds();
        let state = tree.state.downcast_mut::<MinimapState>();
        let Some(g) = self.geometry(bounds) else {
            return;
        };
        match event {
            Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left)) => {
                let Some(p) = cursor.position_in(bounds) else {
                    return;
                };
                if p.y >= g.thumb_top && p.y <= g.thumb_top + g.thumb_height {
                    state.grab = Some(p.y - g.thumb_top);
                } else {
                    // Center the clicked line, then keep dragging from the thumb's middle.
                    let line = (p.y + g.offset) / MINI_LINE;
                    self.scroll_to(line * self.line_height - g.viewport / 2.0, &g, shell);
                    state.grab = Some(g.thumb_height / 2.0);
                }
                shell.capture_event();
            }
            Event::Mouse(mouse::Event::CursorMoved { .. }) => {
                if let (Some(grab), Some(p)) = (state.grab, cursor.position()) {
                    let top = p.y - bounds.y - grab;
                    self.scroll_to(self.scroll_for_thumb(top, &g), &g, shell);
                    shell.capture_event();
                }
            }
            Event::Mouse(mouse::Event::ButtonReleased(mouse::Button::Left)) => {
                if state.grab.take().is_some() {
                    shell.capture_event();
                }
            }
            Event::Mouse(mouse::Event::WheelScrolled { delta, .. }) if cursor.is_over(bounds) => {
                let dy = match delta {
                    mouse::ScrollDelta::Lines { y, .. } => -y * self.line_height * 3.0,
                    mouse::ScrollDelta::Pixels { y, .. } => -y,
                };
                self.scroll_to(g.scroll + dy, &g, shell);
                shell.capture_event();
            }
            _ => {}
        }
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        _viewport: &Rectangle,
        _renderer: &Renderer,
    ) -> mouse::Interaction {
        let state = tree.state.downcast_ref::<MinimapState>();
        if state.grab.is_some() {
            mouse::Interaction::Grabbing
        } else if cursor.is_over(layout.bounds()) {
            mouse::Interaction::Pointer
        } else {
            mouse::Interaction::default()
        }
    }

    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut Renderer,
        theme: &Theme,
        _style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        _viewport: &Rectangle,
    ) {
        use iced::advanced::Renderer as _;
        let bounds = layout.bounds();
        let Some(g) = self.geometry(bounds) else {
            return;
        };
        let state = tree.state.downcast_ref::<MinimapState>();
        renderer.with_layer(bounds, |renderer| {
            if let Some(color) = self.background {
                renderer.fill_quad(
                    Quad {
                        bounds,
                        ..Quad::default()
                    },
                    Background::Color(color),
                );
            }
            let metrics = self.state.metrics.borrow();
            let document = self.state.syntax.lock();
            let first = metrics
                .starts
                .partition_point(|row| (*row as f32 + 1.0) * MINI_LINE < g.offset)
                .saturating_sub(1);
            let left = bounds.x + 4.0;
            let count = metrics.starts.len().saturating_sub(1);
            let mut cache = state.runs.borrow_mut();
            let mut last = first;
            for line in first..count {
                last = line;
                let row = metrics.starts[line];
                let y = bounds.y + row as f32 * MINI_LINE - g.offset;
                if y > bounds.y + bounds.height {
                    break;
                }
                // Lines not highlighted yet stay empty for the moment.
                let Some(spans) = document.spans(line) else {
                    continue;
                };
                let Some(text) = self.state.content.line(line) else {
                    break;
                };
                let key = (
                    std::sync::Arc::as_ptr(spans) as *const () as usize,
                    {
                        use std::hash::{Hash, Hasher};
                        let mut hasher = std::collections::hash_map::DefaultHasher::new();
                        text.text.hash(&mut hasher);
                        hasher.finish()
                    },
                    u32::from_le_bytes(self.text_color.into_rgba8()),
                );
                let runs = match cache.entry(line) {
                    std::collections::hash_map::Entry::Occupied(entry) if entry.get().0 == key => {
                        entry.into_mut()
                    }
                    entry => {
                        let runs = (key, minimap_runs(&text.text, spans, self.text_color));
                        match entry {
                            std::collections::hash_map::Entry::Occupied(mut e) => {
                                e.insert(runs);
                                e.into_mut()
                            }
                            std::collections::hash_map::Entry::Vacant(e) => e.insert(runs),
                        }
                    }
                };
                for &(column, len, color) in &runs.1 {
                    let x = left + column as f32 * MINI_COLUMN;
                    if x >= bounds.x + bounds.width {
                        break;
                    }
                    let w = (len as f32 * MINI_COLUMN).min(bounds.x + bounds.width - x);
                    renderer.fill_quad(
                        Quad {
                            bounds: Rectangle::new(Point::new(x, y), Size::new(w, MINI_TEXT)),
                            ..Quad::default()
                        },
                        Background::Color(Color {
                            a: color.a * 0.7,
                            ..color
                        }),
                    );
                }
            }
            cache.retain(|line, _| (first..=last).contains(line));
            drop(cache);
            let base = self
                .thumb
                .unwrap_or(theme.extended_palette().background.strong.color);
            let active = state.grab.is_some() || cursor.is_over(bounds);
            renderer.fill_quad(
                Quad {
                    bounds: Rectangle::new(
                        Point::new(bounds.x, bounds.y + g.thumb_top),
                        Size::new(bounds.width, g.thumb_height),
                    ),
                    ..Quad::default()
                },
                Background::Color(Color {
                    a: base.a * if active { 0.5 } else { 0.3 },
                    ..base
                }),
            );
        });
    }
}

impl<'a> From<Minimap<'a>> for Element<'a, Message> {
    fn from(minimap: Minimap<'a>) -> Self {
        Element::new(minimap)
    }
}

// ---------------------------------------------------------------------------
// EditorInput
// ---------------------------------------------------------------------------

/// Keeps the editor's keyboard modifiers up to date (Alt+click adds a cursor), turns
/// Ctrl/Cmd + mouse wheel over its content into `on_zoom(+1 | -1)`, before the content
/// (a scrollable) sees the wheel, and reports the word the mouse rests on to `on_hover`.
pub struct EditorInput<'a> {
    content: Element<'a, Message>,
    id: std::sync::Arc<str>,
    state: &'a EditorState,
    on_zoom: Option<PyMsg>,
    on_hover: Option<PyMsg>,
    hover_delay: Duration,
    /// Highlight the lines below the view a little each frame (the minimap shows them).
    highlight_all: bool,
}

impl<'a> EditorInput<'a> {
    pub fn highlight_all(mut self, all: bool) -> Self {
        self.highlight_all = all;
        self
    }

    pub fn new(
        content: impl Into<Element<'a, Message>>,
        id: std::sync::Arc<str>,
        state: &'a EditorState,
        on_zoom: Option<PyMsg>,
        on_hover: Option<PyMsg>,
        hover_delay: Duration,
    ) -> Self {
        Self {
            content: content.into(),
            id,
            state,
            on_zoom,
            on_hover,
            hover_delay,
            highlight_all: false,
        }
    }
}

/// How long a shown hover stays after the mouse leaves its word (time to reach the popup).
const HOVER_GRACE: Duration = Duration::from_millis(300);

#[derive(Default)]
struct ZoomState {
    modifiers: keyboard::Modifiers,
    /// Where the mouse rests (relative to the editor) and since when.
    rest: Option<(Point, Instant)>,
    /// The word whose hover is shown: `(line, start, end)`.
    shown: Option<(usize, usize, usize)>,
    /// When the shown hover goes away, after the mouse left its word.
    hide_at: Option<Instant>,
    /// The name under the mouse while Ctrl is held, underlined like a link (and its color).
    link: Option<(crate::editor::Hit, Option<Color>)>,
}

impl EditorInput<'_> {
    /// Ctrl over a name that may lead to a definition underlines it (Ctrl+click goes there).
    fn track_link(
        &self,
        state: &mut ZoomState,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        shell: &mut Shell<'_, Message>,
    ) {
        let m = state.modifiers;
        let bounds = layout.bounds();
        let link = match cursor.position() {
            Some(at) if m.command() && !m.alt() && !m.shift() && bounds.contains(at) => self
                .state
                .link(Point::new(at.x - bounds.x, at.y - bounds.y)),
            _ => None,
        };
        let key = |l: &Option<(crate::editor::Hit, Option<Color>)>| {
            l.as_ref()
                .map(|(hit, _)| (hit.key(), hit.x.to_bits(), hit.y.to_bits()))
        };
        if key(&link) != key(&state.link) {
            state.link = link;
            shell.request_redraw();
        }
    }

    /// Follows the mouse for `on_hover`: a rest on a word reports it, leaving the word hides it
    /// (after a moment, so the mouse can reach the popup), and typing, clicking or scrolling hide it.
    fn track_hover(
        &self,
        state: &mut ZoomState,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        shell: &mut Shell<'_, Message>,
    ) {
        let Some(on_hover) = &self.on_hover else {
            return;
        };
        let hide = |state: &mut ZoomState, shell: &mut Shell<'_, Message>| {
            state.hide_at = None;
            if state.shown.take().is_some() {
                shell.publish(Message::Hover(on_hover.clone(), None));
            }
        };
        let bounds = layout.bounds();
        match event {
            Event::Mouse(mouse::Event::CursorMoved { .. }) => {
                let now = Instant::now();
                // Over a layer above the editor (the hover popup itself): keep it.
                let Some(position) = cursor.position() else {
                    state.rest = None;
                    state.hide_at = None;
                    return;
                };
                if !bounds.contains(position) {
                    state.rest = None;
                    if state.shown.is_some() && state.hide_at.is_none() {
                        state.hide_at = Some(now + HOVER_GRACE);
                        shell.request_redraw_at(now + HOVER_GRACE);
                    }
                    return;
                }
                let local = Point::new(position.x - bounds.x, position.y - bounds.y);
                state.rest = Some((local, now));
                shell.request_redraw_at(now + self.hover_delay);
                if let Some(shown) = state.shown {
                    let same = self.state.hit(local).is_some_and(|hit| hit.key() == shown);
                    if same {
                        state.hide_at = None;
                    } else if state.hide_at.is_none() {
                        state.hide_at = Some(now + HOVER_GRACE);
                        shell.request_redraw_at(now + HOVER_GRACE);
                    }
                }
            }
            Event::Window(window::Event::RedrawRequested(now)) => {
                if let Some(at) = state.hide_at
                    && *now >= at
                {
                    hide(state, shell);
                }
                if let Some((local, since)) = state.rest {
                    if now.saturating_duration_since(since) >= self.hover_delay {
                        state.rest = None;
                        if let Some(hit) = self.state.hit(local)
                            && state.shown != Some(hit.key())
                        {
                            state.shown = Some(hit.key());
                            state.hide_at = None;
                            shell.publish(Message::Hover(on_hover.clone(), Some(hit)));
                        }
                    } else {
                        shell.request_redraw_at(since + self.hover_delay);
                    }
                }
            }
            Event::Mouse(mouse::Event::ButtonPressed(_)) if cursor.position().is_some() => {
                state.rest = None;
                hide(state, shell)
            }
            Event::Mouse(mouse::Event::WheelScrolled { .. }) if cursor.is_over(bounds) => {
                state.rest = None;
                hide(state, shell)
            }
            Event::Keyboard(keyboard::Event::KeyPressed { .. }) => {
                state.rest = None;
                hide(state, shell)
            }
            Event::Mouse(mouse::Event::CursorLeft) => {
                state.rest = None;
            }
            _ => {}
        }
    }
}

impl EditorInput<'_> {
    /// Applies the scroll the minimap or a selection drag left in the editor's state.
    fn apply_scroll(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        shell: &mut Shell<'_, Message>,
    ) {
        let Some(offset) = self.state.scroll.take() else {
            return;
        };
        let mut scroll =
            widget::operation::scrollable::scroll_to(widget::Id::from(scroll_id(&self.id)), offset);
        self.content
            .as_widget_mut()
            .operate(&mut tree.children[0], layout, renderer, &mut scroll);
        shell.request_redraw();
    }
}

impl Widget<Message, Theme, Renderer> for EditorInput<'_> {
    fn tag(&self) -> tree::Tag {
        tree::Tag::of::<ZoomState>()
    }

    fn state(&self) -> tree::State {
        tree::State::new(ZoomState::default())
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
        self.apply_scroll(tree, layout, renderer, shell);
        let state = tree.state.downcast_mut::<ZoomState>();
        self.track_hover(state, event, layout, cursor, shell);
        // A few milliseconds a frame until every line is highlighted.
        if let Event::Window(window::Event::RedrawRequested(_)) = event
            && self.highlight_all
            && !self.state.syntax.lock().advance(Duration::from_millis(4))
        {
            shell.request_redraw();
        }
        if let Event::Window(window::Event::RedrawRequested(_)) = event
            && self.state.reveal.get()
        {
            if self.state.viewport.get().is_some() {
                self.state.reveal.set(false);
                shell.publish(Message::EditorReveal(self.id.clone()));
            } else {
                shell.request_redraw(); // not drawn yet: try again on the next frame
            }
        }
        // The text editor draws the input method's preedit itself; the caret hides meanwhile
        // and the committed text is grouped with typing for undo.
        if let Event::InputMethod(ime) = event
            && self.state.focused.get()
        {
            match ime {
                input_method::Event::Preedit(content, _) => {
                    self.state.composing.set(!content.is_empty())
                }
                input_method::Event::Commit(_) => {
                    self.state.composing.set(false);
                    self.state.ime_commit.set(true);
                }
                input_method::Event::Opened | input_method::Event::Closed => {
                    self.state.composing.set(false)
                }
            }
        }
        match event {
            Event::Keyboard(keyboard::Event::ModifiersChanged(modifiers)) => {
                state.modifiers = *modifiers;
            }
            Event::Keyboard(keyboard::Event::KeyPressed { repeat, .. }) => {
                self.state.repeat.set(*repeat);
            }
            // Some X11 setups miss the change when the key goes up.
            Event::Keyboard(keyboard::Event::KeyReleased {
                key: keyboard::Key::Named(named),
                ..
            }) => {
                use keyboard::key::Named;
                match named {
                    Named::Control | Named::Super => state
                        .modifiers
                        .remove(keyboard::Modifiers::CTRL | keyboard::Modifiers::LOGO),
                    Named::Alt => state.modifiers.remove(keyboard::Modifiers::ALT),
                    _ => {}
                }
            }
            Event::Mouse(mouse::Event::WheelScrolled { delta, .. })
                if state.modifiers.command()
                    && cursor.is_over(layout.bounds())
                    && self.on_zoom.is_some() =>
            {
                let Some(on_zoom) = &self.on_zoom else {
                    return;
                };
                let y = match delta {
                    mouse::ScrollDelta::Lines { y, .. } | mouse::ScrollDelta::Pixels { y, .. } => {
                        *y
                    }
                };
                if y != 0.0 {
                    shell.publish(Message::Slide(on_zoom.clone(), y.signum()));
                }
                shell.capture_event();
                return;
            }
            _ => {}
        }
        self.state.modifiers.set(state.modifiers);
        if state.modifiers.command() || state.link.is_some() {
            self.track_link(state, layout, cursor, shell);
        }
        // A selection drag moves the cursor right here instead of sending the app a message per
        // mouse move: the app would build its whole view again each time (scrolling doesn't
        // either). It hears of the new cursor once, when the button goes up.
        let mut messages = Vec::new();
        let mut inner = Shell::new(&mut messages);
        self.content.as_widget_mut().update(
            &mut tree.children[0],
            event,
            layout,
            cursor,
            renderer,
            clipboard,
            &mut inner,
            viewport,
        );
        let dragged = Cell::new(false);
        shell.merge(inner, |message| match message {
            Message::Editor {
                id,
                action: action @ text_editor::Action::Drag(_),
                ..
            } if id == self.id => {
                self.state.content.perform_ref(action);
                dragged.set(true);
                None
            }
            message => Some(message),
        });
        if dragged.get() {
            self.state.dragged.set(true);
            if let Some(offset) = self.state.autoscroll_offset() {
                self.state.scroll.set(Some(offset));
            }
            self.apply_scroll(tree, layout, renderer, shell);
            shell.request_redraw();
        }
        if let Event::Mouse(mouse::Event::ButtonReleased(mouse::Button::Left)) = event
            && self.state.dragged.take()
        {
            shell.publish(Message::EditorDragged(self.id.clone()));
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
        if tree.state.downcast_ref::<ZoomState>().link.is_some() {
            return mouse::Interaction::Pointer;
        }
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
        self.content.as_widget().draw(
            &tree.children[0],
            renderer,
            theme,
            style,
            layout,
            cursor,
            viewport,
        );
        if let Some((hit, color)) = &tree.state.downcast_ref::<ZoomState>().link {
            use iced::advanced::Renderer as _;
            let bounds = layout.bounds();
            let thickness = (hit.height / 16.0).clamp(1.0, 2.0);
            renderer.fill_quad(
                Quad {
                    bounds: Rectangle::new(
                        Point::new(bounds.x + hit.x, bounds.y + hit.y + hit.height * 0.86),
                        Size::new(hit.width, thickness),
                    ),
                    ..Quad::default()
                },
                Background::Color(color.unwrap_or(theme.palette().text)),
            );
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

impl<'a> From<EditorInput<'a>> for Element<'a, Message> {
    fn from(wheel: EditorInput<'a>) -> Self {
        Element::new(wheel)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn indentation_levels_count_tabs_to_the_next_stop() {
        assert_eq!(indent_level("x", 4), Some(0));
        assert_eq!(indent_level("        x", 4), Some(2));
        assert_eq!(indent_level("  \tx", 4), Some(1));
        assert_eq!(indent_level("      x", 4), Some(1));
        assert_eq!(indent_level("   ", 4), None);
    }

    #[test]
    fn blank_lines_take_the_smaller_level_around_them() {
        let text = [
            "def f():",
            "    if x:",
            "        a()",
            "",
            "        b()",
            "",
            "    c()",
            "",
            "d()",
        ];
        let level = |i: usize| text.get(i).map(|line| indent_level(line, 4));
        assert_eq!(
            guide_levels(&level, 0..text.len(), 400),
            [0, 1, 2, 2, 2, 1, 1, 0, 0]
        );
        // A window that starts on a blank line looks above it.
        assert_eq!(guide_levels(&level, 3..6, 400), [2, 2, 1]);
    }

    #[test]
    fn minimap_runs_follow_the_spans() {
        let red = Color::from_rgb(1.0, 0.0, 0.0);
        let span = |range: std::ops::Range<usize>, color| crate::highlighter::Span {
            range,
            color,
            font: None,
            link: false,
        };
        let runs = minimap_runs(
            "ab cd",
            &[span(0..2, Some(red)), span(2..5, None)],
            Color::WHITE,
        );
        assert_eq!(runs, [(0, 2, red), (3, 2, Color::WHITE)]); // the space between stays empty
    }
}
