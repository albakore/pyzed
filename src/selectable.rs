//! Text the mouse can select and copy, like a web page: press and drag over it, double-click a
//! word, triple-click a whole block, then Ctrl+C (Cmd+C). Ctrl+A selects the whole group.
//!
//! Texts that share a *group* make one selection area: the blocks of a Markdown answer or the
//! lines of a console. Each one gets its place in the group from the order it is built in
//! (`next_index`, counted again on every `view`), and the selection can run from one block to
//! the next. There is one selection at a time; a press anywhere else in the group clears it.
//!
//! The selection lives here (not in the widget tree) because it spans many widgets: each block
//! draws its own part of it and the first selected block answers Ctrl+C with the text of all.

use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::rc::Rc;
use std::sync::Arc;
use std::time::{Duration, Instant};

use iced::advanced::layout::{self, Layout};
use iced::advanced::mouse::click::{self, Click};
use iced::advanced::renderer::{self, Renderer as _};
use iced::advanced::text::{self as core_text, Paragraph as _, Renderer as _, Span};
use iced::advanced::widget::{Tree, Widget, tree};
use iced::advanced::{Clipboard, Shell, clipboard, mouse};
use iced::alignment;
use iced::keyboard;
use iced::widget::text::{LineHeight, Shaping, Wrapping};
use iced::{Color, Element, Event, Font, Length, Pixels, Point, Rectangle, Size, Vector};
use iced_graphics::text::Paragraph;
use iced_graphics::text::cosmic_text;

type Renderer = iced::Renderer;

/// A place in a group's text: the block, the line in it (split at `\n`) and the byte in the line.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
struct Pos {
    block: usize,
    line: usize,
    index: usize,
}

struct Active {
    group: Rc<str>,
    anchor: Pos,
    focus: Pos,
    dragging: bool,
    /// When the press that started it came: the other blocks see the same press right after (and
    /// keep it); a later press anywhere else in the group clears it.
    since: Instant,
}

/// Longer than one event takes to reach every widget, shorter than two presses of a hand.
const SAME_PRESS: Duration = Duration::from_millis(40);

/// The lines of one block and what goes between it and the next one when copying.
struct Block {
    lines: Rc<Vec<String>>,
    joiner: &'static str,
}

thread_local! {
    static ACTIVE: RefCell<Option<Active>> = const { RefCell::new(None) };
    static LAST_CLICK: Cell<Option<Click>> = const { Cell::new(None) };
    static MODIFIERS: Cell<keyboard::Modifiers> = const { Cell::new(keyboard::Modifiers::empty()) };
    /// The next index of each group in the view being built.
    static NEXT: RefCell<HashMap<Rc<str>, usize>> = RefCell::new(HashMap::new());
    /// How many blocks each group had when it was last built.
    static COUNT: RefCell<HashMap<Rc<str>, usize>> = RefCell::new(HashMap::new());
    static TEXTS: RefCell<HashMap<Rc<str>, HashMap<usize, Block>>> = RefCell::new(HashMap::new());
}

/// Called before a window's view is built: the groups count their blocks again from 0.
pub fn begin_frame() {
    NEXT.with_borrow_mut(|next| next.clear());
}

/// The group named `name` (shared, so cloning it per block is cheap).
pub fn group(name: &str) -> Rc<str> {
    NEXT.with_borrow(|next| next.get_key_value(name).map(|(k, _)| Rc::clone(k)))
        .unwrap_or_else(|| Rc::from(name))
}

/// The place of the next block of `group` in this view.
pub fn next_index(group: &Rc<str>) -> usize {
    let index = NEXT.with_borrow_mut(|next| {
        let n = next.entry(Rc::clone(group)).or_insert(0);
        *n += 1;
        *n - 1
    });
    COUNT.with_borrow_mut(|count| {
        count.insert(Rc::clone(group), index + 1);
    });
    index
}

/// The end of the last block of `group`.
fn end_of(group: &str) -> Pos {
    let last = count(group).saturating_sub(1);
    lines_of(group, last).map_or(
        Pos {
            block: last,
            line: 0,
            index: 0,
        },
        |(lines, _)| {
            let line = lines.len().saturating_sub(1);
            Pos {
                block: last,
                line,
                index: lines.get(line).map_or(0, String::len),
            }
        },
    )
}

/// The text selected in `group`, or `None` when nothing is selected there.
///
/// For context menus: a right click keeps the selection, and the menu's Copy reads it here.
#[pyo3::pyfunction]
pub fn selected_text(group: &str) -> Option<String> {
    ACTIVE.with_borrow(|active| {
        let a = active.as_ref().filter(|a| &*a.group == group)?;
        let (s, e) = if a.anchor <= a.focus {
            (a.anchor, a.focus)
        } else {
            (a.focus, a.anchor)
        };
        (s != e).then(|| text_between(group, s, e))
    })
}

/// Selects all the text of `group` (as Ctrl+A over it does).
#[pyo3::pyfunction]
pub fn select_all(group: &str) {
    if count(group) == 0 {
        return;
    }
    ACTIVE.set(Some(Active {
        group: Rc::from(group),
        anchor: Pos {
            block: 0,
            line: 0,
            index: 0,
        },
        focus: end_of(group),
        dragging: false,
        since: Instant::now(),
    }));
}

/// Clears the selection of `group`.
#[pyo3::pyfunction]
pub fn clear_selection(group: &str) {
    ACTIVE.with_borrow_mut(|active| {
        if active.as_ref().is_some_and(|a| &*a.group == group) {
            *active = None;
        }
    });
}

/// A group of its own, for a text that is selectable alone.
pub fn own_group() -> Rc<str> {
    let n = next_index(&group("\u{0}own"));
    Rc::from(format!("\u{0}own{n}"))
}

fn count(group: &str) -> usize {
    COUNT.with_borrow(|count| count.get(group).copied().unwrap_or(0))
}

fn lines_of(group: &str, block: usize) -> Option<(Rc<Vec<String>>, &'static str)> {
    TEXTS.with_borrow(|texts| {
        texts
            .get(group)
            .and_then(|blocks| blocks.get(&block))
            .map(|b| (Rc::clone(&b.lines), b.joiner))
    })
}

fn slice(line: &str, from: usize, to: usize) -> &str {
    let mut a = from.min(line.len());
    let mut b = to.min(line.len()).max(a);
    while !line.is_char_boundary(a) {
        a -= 1;
    }
    while !line.is_char_boundary(b) {
        b += 1;
    }
    &line[a..b]
}

/// The text between `start` and `end` (in order) of `group`.
fn text_between(group: &str, start: Pos, end: Pos) -> String {
    let mut out = String::new();
    for block in start.block
        ..=end
            .block
            .min(count(group).saturating_sub(1).max(start.block))
    {
        let Some((lines, joiner)) = lines_of(group, block) else {
            continue;
        };
        let (l0, i0) = if block == start.block {
            (start.line, start.index)
        } else {
            (0, 0)
        };
        let last = lines.len().saturating_sub(1);
        let (l1, i1) = if block == end.block {
            (end.line.min(last), end.index)
        } else {
            (last, usize::MAX)
        };
        for l in l0..=l1.max(l0) {
            let Some(line) = lines.get(l) else { break };
            let from = if l == l0 { i0 } else { 0 };
            let to = if l == l1 { i1 } else { usize::MAX };
            out.push_str(slice(line, from, to));
            if l < l1 {
                out.push('\n');
            }
        }
        if block < end.block {
            out.push_str(joiner);
        }
    }
    out
}

fn word_at(line: &str, index: usize) -> (usize, usize) {
    let is_word = |c: char| c.is_alphanumeric() || c == '_';
    let index = slice(line, 0, index).len();
    let start = line[..index]
        .char_indices()
        .rev()
        .take_while(|(_, c)| is_word(*c))
        .last()
        .map_or(index, |(i, _)| i);
    let end = line[index..]
        .char_indices()
        .find(|(_, c)| !is_word(*c))
        .map_or(line.len(), |(i, _)| index + i);
    if start == end {
        // not on a word: select the character under the pointer
        let next = line[index..].chars().next().map_or(0, char::len_utf8);
        (index, index + next)
    } else {
        (start, end)
    }
}

/// Text (a list of spans, so it can carry links, code and styles) whose characters can be selected.
pub struct Selectable<'a, Link, Message> {
    spans: Arc<[Span<'a, Link, Font>]>,
    group: Rc<str>,
    index: usize,
    joiner: &'static str,
    size: Option<Pixels>,
    line_height: LineHeight,
    width: Length,
    height: Length,
    font: Option<Font>,
    wrapping: Wrapping,
    color: Option<Color>,
    highlight: Color,
    on_link: Option<Box<dyn Fn(Link) -> Message + 'a>>,
    hovered_link: Option<usize>,
}

impl<'a, Link, Message> Selectable<'a, Link, Message>
where
    Link: Clone + 'static,
{
    /// The next block of `group`, showing `spans`.
    pub fn new(spans: impl Into<Arc<[Span<'a, Link, Font>]>>, group: &Rc<str>) -> Self {
        Self {
            spans: spans.into(),
            group: Rc::clone(group),
            index: next_index(group),
            joiner: "\n",
            size: None,
            line_height: LineHeight::default(),
            width: Length::Shrink,
            height: Length::Shrink,
            font: None,
            // a long word (a path, a URL) breaks instead of running out of its parent
            wrapping: Wrapping::WordOrGlyph,
            color: None,
            highlight: Color::from_rgba(0.45, 0.68, 0.91, 0.3),
            on_link: None,
            hovered_link: None,
        }
    }

    /// What goes between this block and the next one when both are copied (`"\n"` by default).
    pub fn joiner(mut self, joiner: &'static str) -> Self {
        self.joiner = joiner;
        self
    }

    pub fn size(mut self, size: impl Into<Pixels>) -> Self {
        self.size = Some(size.into());
        self
    }

    pub fn line_height(mut self, line_height: impl Into<LineHeight>) -> Self {
        self.line_height = line_height.into();
        self
    }

    pub fn width(mut self, width: impl Into<Length>) -> Self {
        self.width = width.into();
        self
    }

    pub fn height(mut self, height: impl Into<Length>) -> Self {
        self.height = height.into();
        self
    }

    pub fn font(mut self, font: Font) -> Self {
        self.font = Some(font);
        self
    }

    pub fn wrapping(mut self, wrapping: Wrapping) -> Self {
        self.wrapping = wrapping;
        self
    }

    pub fn color(mut self, color: Option<Color>) -> Self {
        self.color = color;
        self
    }

    /// The color drawn behind the selected text.
    pub fn highlight(mut self, color: Option<Color>) -> Self {
        if let Some(color) = color {
            self.highlight = color;
        }
        self
    }

    pub fn on_link_click(mut self, f: impl Fn(Link) -> Message + 'a) -> Self {
        self.on_link = Some(Box::new(f));
        self
    }

    /// The selected part of this block: `(start, end)` as (line, byte) pairs.
    fn range(&self, lines: &[String]) -> Option<((usize, usize), (usize, usize))> {
        ACTIVE.with_borrow(|active| {
            let a = active.as_ref().filter(|a| a.group == self.group)?;
            let (s, e) = if a.anchor <= a.focus {
                (a.anchor, a.focus)
            } else {
                (a.focus, a.anchor)
            };
            if s == e || self.index < s.block || self.index > e.block {
                return None;
            }
            let last = lines.len().saturating_sub(1);
            let from = if s.block == self.index {
                (s.line, s.index)
            } else {
                (0, 0)
            };
            let to = if e.block == self.index {
                (e.line, e.index)
            } else {
                (last, lines.get(last).map_or(0, String::len))
            };
            Some((from, to))
        })
    }
}

struct State<Link> {
    spans: Arc<[Span<'static, Link, Font>]>,
    paragraph: Paragraph,
    lines: Rc<Vec<String>>,
    span_pressed: Option<usize>,
}

/// Where `point` (relative to the text) falls: a line and a byte, clamped to the text.
fn hit(paragraph: &Paragraph, lines: &[String], point: Point) -> (usize, usize) {
    let last = lines.len().saturating_sub(1);
    if point.y < 0.0 {
        return (0, 0);
    }
    if point.y >= paragraph.min_bounds().height {
        return (last, lines.get(last).map_or(0, String::len));
    }
    match paragraph.buffer().hit(point.x.max(0.0), point.y) {
        Some(cursor) => (cursor.line, cursor.index),
        None => (last, lines.get(last).map_or(0, String::len)),
    }
}

impl<Link, Message> Widget<Message, iced::Theme, Renderer> for Selectable<'_, Link, Message>
where
    Link: Clone + PartialEq + 'static,
{
    fn tag(&self) -> tree::Tag {
        tree::Tag::of::<State<Link>>()
    }

    fn state(&self) -> tree::State {
        tree::State::new(State::<Link> {
            spans: Arc::from([]),
            paragraph: Paragraph::default(),
            lines: Rc::new(Vec::new()),
            span_pressed: None,
        })
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
        let state = tree.state.downcast_mut::<State<Link>>();
        let spans: &[Span<'_, Link, Font>] = &self.spans;
        let node = layout::sized(limits, self.width, self.height, |limits| {
            let bounds = limits.max();
            let size = self.size.unwrap_or_else(|| renderer.default_size());
            let font = self.font.unwrap_or_else(|| renderer.default_font());
            let text = || core_text::Text {
                content: spans,
                bounds,
                size,
                line_height: self.line_height,
                font,
                align_x: core_text::Alignment::Left,
                align_y: alignment::Vertical::Top,
                shaping: Shaping::Advanced,
                wrapping: self.wrapping,
                letter_spacing: iced::Em::ZERO,
            };
            if &*state.spans != spans {
                state.paragraph = Paragraph::with_spans(text());
                state.spans = spans.iter().cloned().map(Span::to_static).collect();
                state.lines = Rc::new(
                    state
                        .paragraph
                        .buffer()
                        .lines
                        .iter()
                        .map(|line| line.text().to_owned())
                        .collect(),
                );
            } else {
                match state.paragraph.compare(core_text::Text {
                    content: (),
                    bounds,
                    size,
                    line_height: self.line_height,
                    font,
                    align_x: core_text::Alignment::Left,
                    align_y: alignment::Vertical::Top,
                    shaping: Shaping::Advanced,
                    wrapping: self.wrapping,
                    letter_spacing: iced::Em::ZERO,
                }) {
                    core_text::Difference::None => {}
                    core_text::Difference::Bounds => state.paragraph.resize(bounds),
                    core_text::Difference::Shape => state.paragraph = Paragraph::with_spans(text()),
                }
            }
            state.paragraph.min_bounds()
        });
        let lines = Rc::clone(&state.lines);
        TEXTS.with_borrow_mut(|texts| {
            texts.entry(Rc::clone(&self.group)).or_default().insert(
                self.index,
                Block {
                    lines,
                    joiner: self.joiner,
                },
            );
        });
        node
    }

    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut Renderer,
        _theme: &iced::Theme,
        defaults: &renderer::Style,
        layout: Layout<'_>,
        _cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        let bounds = layout.bounds();
        if !bounds.intersects(viewport) {
            return;
        }
        let state = tree.state.downcast_ref::<State<Link>>();
        let origin = bounds.position() - Point::ORIGIN;
        let color = crate::animation::fade(self.color.unwrap_or(defaults.text_color));

        if let Some(((l0, i0), (l1, i1))) = self.range(&state.lines) {
            let (start, end) = (
                cosmic_text::Cursor::new(l0, i0),
                cosmic_text::Cursor::new(l1, i1),
            );
            let fill = crate::animation::fade(self.highlight);
            for run in state.paragraph.buffer().layout_runs() {
                if run.line_i < l0 || run.line_i > l1 {
                    continue;
                }
                let (x, mut w) = run.highlight(start, end).unwrap_or((0.0, 0.0));
                if run.line_i < l1 && run.glyphs.last().is_none_or(|g| g.end >= run.text.len()) {
                    // the line break is selected too: show it as a little space
                    w += 4.0;
                }
                if w <= 0.0 {
                    continue;
                }
                renderer.fill_quad(
                    renderer::Quad {
                        bounds: Rectangle::new(
                            Point::new(x, run.line_top) + origin,
                            Size::new(w, run.line_height),
                        ),
                        ..renderer::Quad::default()
                    },
                    fill,
                );
            }
        }

        for (index, span) in self.spans.iter().enumerate() {
            let hovered = self.on_link.is_some() && Some(index) == self.hovered_link;
            if span.highlight.is_none() && !span.underline && !span.strikethrough && !hovered {
                continue;
            }
            let regions = state.paragraph.span_bounds(index);
            if let Some(highlight) = span.highlight {
                for b in &regions {
                    let b = Rectangle::new(
                        b.position() - Vector::new(span.padding.left, span.padding.top),
                        b.size() + Size::new(span.padding.x(), span.padding.y()),
                    );
                    renderer.fill_quad(
                        renderer::Quad {
                            bounds: b + origin,
                            border: highlight.border,
                            ..renderer::Quad::default()
                        },
                        highlight.background,
                    );
                }
            }
            if span.underline || span.strikethrough || hovered {
                let size = span.size.or(self.size).unwrap_or(renderer.default_size());
                let line_height = span
                    .line_height
                    .unwrap_or(self.line_height)
                    .to_absolute(size);
                let line_color = span.color.map_or(color, crate::animation::fade);
                let baseline = origin + Vector::new(0.0, size.0 + (line_height.0 - size.0) / 2.0);
                for b in &regions {
                    if span.underline || hovered {
                        renderer.fill_quad(
                            renderer::Quad {
                                bounds: Rectangle::new(
                                    b.position() + baseline - Vector::new(0.0, size.0 * 0.08),
                                    Size::new(b.width, 1.0),
                                ),
                                ..renderer::Quad::default()
                            },
                            line_color,
                        );
                    }
                    if span.strikethrough {
                        renderer.fill_quad(
                            renderer::Quad {
                                bounds: Rectangle::new(
                                    b.position() + baseline - Vector::new(0.0, size.0 / 2.0),
                                    Size::new(b.width, 1.0),
                                ),
                                ..renderer::Quad::default()
                            },
                            line_color,
                        );
                    }
                }
            }
        }

        renderer.fill_paragraph(&state.paragraph, bounds.position(), color, *viewport);
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        _renderer: &Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        _viewport: &Rectangle,
    ) {
        let bounds = layout.bounds();
        let state = tree.state.downcast_mut::<State<Link>>();
        let position = cursor.position();
        let mine = |a: &Active| a.group == self.group;

        if self.on_link.is_some() {
            let was = self.hovered_link;
            self.hovered_link = cursor
                .position_in(bounds)
                .and_then(|p| state.paragraph.hit_span(p))
                .filter(|&span| self.spans.get(span).is_some_and(|s| s.link.is_some()));
            if was != self.hovered_link {
                shell.request_redraw();
            }
        }

        match event {
            Event::Keyboard(keyboard::Event::ModifiersChanged(modifiers)) => {
                MODIFIERS.set(*modifiers)
            }
            Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left)) => match position {
                Some(p) if bounds.contains(p) => {
                    let (line, index) = hit(
                        &state.paragraph,
                        &state.lines,
                        p - (bounds.position() - Point::ORIGIN),
                    );
                    let click = Click::new(p, mouse::Button::Left, LAST_CLICK.get());
                    LAST_CLICK.set(Some(click));
                    let here = Pos {
                        block: self.index,
                        line,
                        index,
                    };
                    let (anchor, focus) = match click.kind() {
                        click::Kind::Single => {
                            let kept = MODIFIERS.get().shift().then(|| {
                                ACTIVE.with_borrow(|a| {
                                    a.as_ref().filter(|a| mine(a)).map(|a| a.anchor)
                                })
                            });
                            (kept.flatten().unwrap_or(here), here)
                        }
                        click::Kind::Double => {
                            let text = state.lines.get(line).map_or("", String::as_str);
                            let (a, b) = word_at(text, index);
                            (Pos { index: a, ..here }, Pos { index: b, ..here })
                        }
                        click::Kind::Triple => {
                            let last = state.lines.len().saturating_sub(1);
                            (
                                Pos {
                                    line: 0,
                                    index: 0,
                                    ..here
                                },
                                Pos {
                                    line: last,
                                    index: state.lines.get(last).map_or(0, String::len),
                                    ..here
                                },
                            )
                        }
                    };
                    ACTIVE.set(Some(Active {
                        group: Rc::clone(&self.group),
                        anchor,
                        focus,
                        dragging: true,
                        since: Instant::now(),
                    }));
                    state.span_pressed = self.hovered_link;
                    shell.request_redraw();
                }
                _ => {
                    let cleared = ACTIVE.with_borrow_mut(|active| {
                        if active
                            .as_ref()
                            .is_some_and(|a| mine(a) && a.since.elapsed() > SAME_PRESS)
                        {
                            *active = None;
                            true
                        } else {
                            false
                        }
                    });
                    if cleared {
                        shell.request_redraw();
                    }
                }
            },
            Event::Mouse(mouse::Event::CursorMoved { .. }) => {
                let Some(p) = position else { return };
                if p.y < bounds.y || p.y >= bounds.y + bounds.height {
                    return;
                }
                let moved = ACTIVE.with_borrow_mut(|active| match active.as_mut() {
                    Some(a) if mine(a) && a.dragging => {
                        let (line, index) = hit(
                            &state.paragraph,
                            &state.lines,
                            p - (bounds.position() - Point::ORIGIN),
                        );
                        let focus = Pos {
                            block: self.index,
                            line,
                            index,
                        };
                        let changed = a.focus != focus;
                        a.focus = focus;
                        changed
                    }
                    _ => false,
                });
                if moved {
                    shell.request_redraw();
                }
            }
            Event::Mouse(mouse::Event::ButtonReleased(mouse::Button::Left)) => {
                let collapsed = ACTIVE.with_borrow_mut(|active| match active.as_mut() {
                    Some(a) if mine(a) => {
                        a.dragging = false;
                        a.anchor == a.focus
                    }
                    _ => true,
                });
                // a click on a link (not a drag that selected text) opens it
                let pressed = state
                    .span_pressed
                    .take()
                    .filter(|&span| collapsed && Some(span) == self.hovered_link);
                let link = pressed
                    .and_then(|span| self.spans.get(span))
                    .and_then(|s| s.link.clone());
                if let (Some(link), Some(on_link)) = (link, &self.on_link) {
                    shell.publish(on_link(link));
                }
            }
            Event::Keyboard(keyboard::Event::KeyPressed { key, modifiers, .. }) => {
                let Some((group, start, end)) = ACTIVE.with_borrow(|active| {
                    let a = active.as_ref().filter(|a| mine(a))?;
                    let (s, e) = if a.anchor <= a.focus {
                        (a.anchor, a.focus)
                    } else {
                        (a.focus, a.anchor)
                    };
                    Some((Rc::clone(&a.group), s, e))
                }) else {
                    return;
                };
                match key.as_ref() {
                    keyboard::Key::Character(c)
                        if modifiers.command() && c.eq_ignore_ascii_case("c") =>
                    {
                        if start != end && self.index == start.block {
                            clipboard
                                .write(clipboard::Kind::Standard, text_between(&group, start, end));
                            // the app's own Ctrl+C (copying the selected controls) must not
                            // overwrite what was just copied
                            crate::app::claim_key(key);
                            shell.capture_event();
                        }
                    }
                    keyboard::Key::Character(c)
                        if modifiers.command() && c.eq_ignore_ascii_case("a") =>
                    {
                        if self.index == 0 {
                            let end = end_of(&group);
                            ACTIVE.with_borrow_mut(|active| {
                                if let Some(a) = active.as_mut() {
                                    a.anchor = Pos {
                                        block: 0,
                                        line: 0,
                                        index: 0,
                                    };
                                    a.focus = end;
                                }
                            });
                            crate::app::claim_key(key);
                            shell.capture_event();
                            shell.request_redraw();
                        }
                    }
                    keyboard::Key::Named(keyboard::key::Named::Escape)
                        if self.index == start.block && start != end =>
                    {
                        ACTIVE.set(None);
                        shell.request_redraw();
                    }
                    _ => {}
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
        if self.hovered_link.is_some() {
            mouse::Interaction::Pointer
        } else if cursor.is_over(layout.bounds()) {
            mouse::Interaction::Text
        } else {
            mouse::Interaction::None
        }
    }
}

impl<'a, Link, Message> From<Selectable<'a, Link, Message>> for Element<'a, Message>
where
    Link: Clone + PartialEq + 'static,
    Message: 'a,
{
    fn from(text: Selectable<'a, Link, Message>) -> Self {
        Element::new(text)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn block(group: &Rc<str>, index: usize, lines: &[&str], joiner: &'static str) {
        TEXTS.with_borrow_mut(|texts| {
            texts.entry(Rc::clone(group)).or_default().insert(
                index,
                Block {
                    lines: Rc::new(lines.iter().map(|s| (*s).to_owned()).collect()),
                    joiner,
                },
            );
        });
    }

    #[test]
    fn copies_across_blocks_and_lines() {
        begin_frame();
        let g = group("test");
        for _ in 0..3 {
            next_index(&g);
        }
        block(&g, 0, &["Hello world"], "\n\n");
        block(&g, 1, &["fn main() {", "}"], "\n\n");
        block(&g, 2, &["Bye"], "\n\n");
        let at = |block, line, index| Pos { block, line, index };
        assert_eq!(text_between(&g, at(0, 0, 6), at(0, 0, 11)), "world");
        assert_eq!(
            text_between(&g, at(0, 0, 6), at(2, 0, 1)),
            "world\n\nfn main() {\n}\n\nB"
        );
        assert_eq!(text_between(&g, at(1, 0, 3), at(1, 1, 1)), "main() {\n}");
    }

    #[test]
    fn words() {
        assert_eq!(word_at("let some_name = 1", 6), (4, 13));
        assert_eq!(word_at("a + b", 2), (2, 3));
        assert_eq!(word_at("ñandú y", 3), (0, 7));
    }
}
