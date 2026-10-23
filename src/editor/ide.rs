//! IDE helpers of the code editor: the word under the mouse (for hover and go to definition)
//! and sticky scroll, which pins the headers of the blocks around the first visible line to the
//! top of the editor (like VS Code and Zed).

use std::sync::Arc;

use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer::{self, Quad};
use iced::advanced::text::{self as core_text, Highlighter as _, Paragraph as _, Renderer as _};
use iced::advanced::widget::{Tree, Widget};
use iced::advanced::{Clipboard, Shell, mouse};
use iced::widget::text::LineHeight;
use iced::widget::text_editor;
use iced::{Background, Color, Element, Event, Length, Pixels, Point, Rectangle, Size, Theme};

use super::{EditorState, Measure, Metrics, PAD_LEFT, PAD_Y, indent_of, paragraph};
use crate::app::Message;
use crate::highlighter::{self, Highlighter};
use crate::widget::EditorProps;

type Renderer = iced::Renderer;

/// The word under the mouse: its real line and byte columns (0-based) and where it is drawn,
/// relative to the editor's top left corner.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Hit {
    pub line: usize,
    pub column: usize,
    pub start: usize,
    pub end: usize,
    pub x: f32,
    pub y: f32,
    pub height: f32,
}

impl Hit {
    /// What identifies the word: two hits on the same word are the same hover.
    pub fn key(&self) -> (usize, usize, usize) {
        (self.line, self.start, self.end)
    }
}

fn is_word(c: char) -> bool {
    c.is_alphanumeric() || c == '_'
}

/// The byte range of the identifier with the character at byte `at`, if it is part of one.
fn word_at(line: &str, at: usize) -> Option<(usize, usize)> {
    let c = line.get(at..)?.chars().next()?;
    if !is_word(c) {
        return None;
    }
    let start = line[..at]
        .char_indices()
        .rev()
        .take_while(|(_, c)| is_word(*c))
        .last()
        .map_or(at, |(i, _)| i);
    let end = line[at..]
        .char_indices()
        .find(|(_, c)| !is_word(*c))
        .map_or(line.len(), |(i, _)| at + i);
    Some((start, end))
}

/// Where byte `at` of `line` is drawn: its x and the wrapped row it is on.
fn locate(m: &Metrics, measure: &mut Measure, line: &str, at: usize) -> (f32, u32) {
    let prefix = &line[..at];
    match m.wrap_width {
        None => (measure.width(prefix, m.font, m.size, m.line_height), 0),
        Some(_) if prefix.is_empty() => (0.0, 0),
        Some(width) => {
            let p = paragraph(prefix, m.font, m.size, m.line_height, Some(width));
            let rows = ((p.min_bounds().height / m.line_height).round() as usize).max(1);
            let x = p
                .grapheme_position(rows - 1, usize::MAX)
                .map_or(0.0, |p| p.x);
            (x, rows as u32 - 1)
        }
    }
}

impl EditorState {
    /// The word at `local` (relative to the editor's top left corner), if the mouse is over one.
    pub(crate) fn hit(&self, local: Point) -> Option<Hit> {
        let m = self.metrics.borrow();
        let viewport = self.viewport.get()?;
        if !m.ready || local.x < m.left || local.y < self.sticky_height.get() {
            return None;
        }
        let lh = m.line_height.max(1.0);
        let x = local.x - m.left - PAD_LEFT + viewport.x;
        let y = local.y + viewport.y - PAD_Y;
        if x < 0.0 || y < 0.0 {
            return None;
        }
        let row = (y / lh) as u32;
        let visible = m.starts.partition_point(|s| *s <= row).checked_sub(1)?;
        if visible + 1 >= m.starts.len() {
            return None;
        }
        let text = self.content.line(visible)?.text.into_owned();
        let sub = row - m.starts[visible];
        let p = paragraph(&text, m.font, m.size, lh, m.wrap_width);
        let core_text::Hit::CharOffset(index) =
            p.hit_test(Point::new(x, sub as f32 * lh + lh / 2.0))?;
        let index = index.min(text.len());
        // The click point is nearest to a boundary: the word may be the one before it.
        let before = text[..index].char_indices().last().map(|(i, _)| i);
        let mut measure = self.measure.borrow_mut();
        for at in [Some(index), before].into_iter().flatten() {
            let Some((start, end)) = word_at(&text, at) else {
                continue;
            };
            let (x0, r0) = locate(&m, &mut measure, &text, start);
            let (x1, r1) = locate(&m, &mut measure, &text, end);
            let inside = r0 <= sub && sub <= r1 && (r0 != sub || x >= x0) && (r1 != sub || x <= x1);
            if inside {
                return Some(Hit {
                    line: self.real_line(visible),
                    column: at,
                    start,
                    end,
                    x: m.left + PAD_LEFT + x0 - viewport.x,
                    y: PAD_Y + (m.starts[visible] + r0) as f32 * lh - viewport.y,
                    height: lh,
                });
            }
        }
        None
    }

    /// The visible lines whose headers stick to the top while the editor scrolls, outermost
    /// first, and how far the innermost one is pushed up as its block ends.
    pub(crate) fn sticky_lines(&self, max: usize) -> (Vec<usize>, f32) {
        let m = self.metrics.borrow();
        let Some(viewport) = self.viewport.get() else {
            return (Vec::new(), 0.0);
        };
        if !m.ready || max == 0 || m.starts.len() < 2 {
            return (Vec::new(), 0.0);
        }
        let lh = m.line_height.max(1.0);
        let count = m.starts.len() - 1;
        let line_text = |i: usize| self.content.line(i).map(|l| l.text.into_owned());
        let line_at = |y: f32| -> usize {
            let row = ((y - PAD_Y).max(0.0) / lh) as u32;
            m.starts
                .partition_point(|s| *s <= row)
                .saturating_sub(1)
                .min(count - 1)
        };
        // The headers around the line under the stuck ones: settle in two passes, since the
        // headers cover the first rows of the view.
        let mut headers = Vec::new();
        for _ in 0..2 {
            let below = line_at(viewport.y + headers.len() as f32 * lh);
            let mut found = scopes(&line_text, below);
            found.truncate(max);
            // A header still in view below its slot needs no sticking.
            let mut kept = Vec::new();
            for (slot, line) in found.into_iter().enumerate() {
                let top = PAD_Y + m.starts[line] as f32 * lh;
                if top >= viewport.y + slot as f32 * lh {
                    break;
                }
                kept.push(line);
            }
            if kept == headers {
                break;
            }
            headers = kept;
        }
        let Some(&last) = headers.last() else {
            return (headers, 0.0);
        };
        // The innermost header slides up with the last line of its block.
        let end = block_end(&line_text, last, count);
        let bottom = PAD_Y + m.starts[end + 1] as f32 * lh;
        let shift = (bottom - (viewport.y + headers.len() as f32 * lh)).min(0.0);
        (headers, shift)
    }
}

/// The headers of the blocks containing visible line `line`, outermost first: by indentation,
/// each line above it that is less indented than everything below it so far.
fn scopes(text: &dyn Fn(usize) -> Option<String>, line: usize) -> Vec<usize> {
    // A blank line belongs to the block of the next line that is not.
    let mut current = None;
    let mut i = line;
    while current.is_none() {
        match text(i) {
            Some(t) => current = indent_of(&t),
            None => break,
        }
        i += 1;
    }
    let Some(mut level) = current else {
        return Vec::new();
    };
    let mut out = Vec::new();
    let mut i = line;
    while level > 0 && i > 0 {
        i -= 1;
        let Some(t) = text(i) else { break };
        let Some(indent) = indent_of(&t) else {
            continue;
        };
        if indent >= level {
            continue;
        }
        level = indent;
        // `):` closing a signature split over lines: the header is the line that opened it.
        let mut header = i;
        if t.trim_start().starts_with([')', ']', '}']) {
            while header > 0 {
                header -= 1;
                match text(header)
                    .as_deref()
                    .and_then(|t| indent_of(t).map(|n| (n, t)))
                {
                    Some((n, t)) if n == indent && !t.trim_start().starts_with([')', ']', '}']) => {
                        break;
                    }
                    Some((n, _)) if n < indent => {
                        header += 1;
                        break;
                    }
                    _ => {}
                }
            }
        }
        i = header;
        out.push(header);
    }
    out.reverse();
    out
}

/// The last line of the block opened by `header` (the lines below it that are more indented).
fn block_end(text: &dyn Fn(usize) -> Option<String>, header: usize, count: usize) -> usize {
    let level = text(header).as_deref().and_then(indent_of).unwrap_or(0);
    let mut end = header;
    for i in header + 1..count {
        match text(i).as_deref().map(indent_of) {
            Some(Some(n)) if n <= level => {
                // A closing `)` or `]` at the header's level still belongs to it.
                let closer = text(i).is_some_and(|t| t.trim_start().starts_with([')', ']', '}']));
                if !closer {
                    break;
                }
                end = i;
            }
            Some(Some(_)) => end = i,
            Some(None) => {}
            None => break,
        }
    }
    end
}

// ---------------------------------------------------------------------------
// StickyScroll
// ---------------------------------------------------------------------------

/// Draws the sticky headers over the top of the editor; a click on one moves the cursor there.
pub struct StickyScroll<'a> {
    state: &'a EditorState,
    props: Arc<EditorProps>,
    token: String,
    theme_id: u64,
    /// Width on the right left uncovered (the minimap and the vertical scrollbar).
    right: f32,
}

impl<'a> StickyScroll<'a> {
    pub fn new(
        state: &'a EditorState,
        props: Arc<EditorProps>,
        token: String,
        theme_id: u64,
        right: f32,
    ) -> Self {
        Self {
            state,
            props,
            token,
            theme_id,
            right,
        }
    }

    fn rows(&self) -> (Vec<usize>, f32) {
        self.state.sticky_lines(self.props.sticky_scroll)
    }
}

impl Widget<Message, Theme, Renderer> for StickyScroll<'_> {
    fn size(&self) -> Size<Length> {
        Size::new(Length::Fill, Length::Fill)
    }

    fn layout(&mut self, _: &mut Tree, _: &Renderer, limits: &layout::Limits) -> layout::Node {
        layout::Node::new(limits.max())
    }

    fn update(
        &mut self,
        _tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        _renderer: &Renderer,
        _clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        _viewport: &Rectangle,
    ) {
        let Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left)) = event else {
            return;
        };
        let height = self.state.sticky_height.get();
        let bounds = layout.bounds();
        let Some(at) = cursor.position_in(bounds) else {
            return;
        };
        if height <= 0.0 || at.y >= height || at.x > bounds.width - self.right {
            return;
        }
        let (lines, _) = self.rows();
        let lh = self.props.line_height;
        let slot = (at.y / lh) as usize;
        let Some(&line) = lines.get(slot.min(lines.len().saturating_sub(1))) else {
            return;
        };
        let row = self
            .state
            .metrics
            .borrow()
            .starts
            .get(line)
            .copied()
            .unwrap_or(0);
        shell.publish(Message::Editor {
            id: self.props.id.clone(),
            action: text_editor::Action::Click(Point::new(0.0, row as f32 * lh + lh / 2.0)),
            on_change: self.props.on_change.clone(),
            on_cursor: self.props.on_cursor.clone(),
        });
        shell.capture_event();
    }

    fn mouse_interaction(
        &self,
        _tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        _viewport: &Rectangle,
        _renderer: &Renderer,
    ) -> mouse::Interaction {
        let bounds = layout.bounds();
        match cursor.position_in(bounds) {
            Some(at)
                if at.y < self.state.sticky_height.get() && at.x <= bounds.width - self.right =>
            {
                mouse::Interaction::Pointer
            }
            _ => mouse::Interaction::None,
        }
    }

    fn draw(
        &self,
        _tree: &Tree,
        renderer: &mut Renderer,
        theme: &Theme,
        _style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        _viewport: &Rectangle,
    ) {
        use iced::advanced::Renderer as _;
        let (lines, shift) = self.rows();
        let p = &self.props;
        let lh = p.line_height;
        let height = (lines.len() as f32 * lh + shift).max(0.0);
        self.state.sticky_height.set(height);
        if lines.is_empty() {
            return;
        }
        let bounds = layout.bounds();
        let width = (bounds.width - self.right).max(0.0);
        let (left, scroll_x) = {
            let m = self.state.metrics.borrow();
            (m.left, self.state.viewport.get().map_or(0.0, |v| v.x))
        };
        let background = p
            .background
            .unwrap_or(theme.extended_palette().background.base.color);
        let text_color = p.text_color.unwrap_or(theme.palette().text);
        let area = Rectangle::new(bounds.position(), Size::new(width, height));
        renderer.with_layer(area, |renderer| {
            renderer.fill_quad(
                Quad {
                    bounds: area,
                    ..Quad::default()
                },
                Background::Color(background),
            );
            let hovered = cursor
                .position_in(area)
                .map(|at| ((at.y / lh) as usize).min(lines.len() - 1));
            let mut highlighter = Highlighter::new(&highlighter::Settings {
                token: self.token.clone(),
                theme: self.theme_id,
                font: p.font,
                default: p.text_color,
            });
            let mut measure = self.state.measure.borrow_mut();
            // The innermost header first: pushed up, it slides under the others.
            for (slot, &line) in lines.iter().enumerate().rev() {
                let last = slot + 1 == lines.len();
                let y = bounds.y + slot as f32 * lh + if last { shift } else { 0.0 };
                let row = Rectangle::new(Point::new(bounds.x, y), Size::new(width, lh));
                if hovered == Some(slot)
                    && let Some(color) = p.active_line
                {
                    renderer.fill_quad(
                        Quad {
                            bounds: row,
                            ..Quad::default()
                        },
                        Background::Color(color),
                    );
                }
                let text = self
                    .state
                    .content
                    .line(line)
                    .map(|l| l.text.into_owned())
                    .unwrap_or_default();
                // The code, scrolled sideways with the editor and clipped at the gutter.
                let code = Rectangle::new(
                    Point::new(bounds.x + left, y),
                    Size::new((width - left).max(0.0), lh),
                );
                let origin = bounds.x + left + PAD_LEFT - scroll_x;
                for (range, highlight) in highlighter.highlight_line(&text) {
                    let piece = &text[range.clone()];
                    if piece.trim().is_empty() {
                        continue;
                    }
                    let format = highlight.to_format(theme);
                    let x = origin + measure.width(&text[..range.start], p.font, p.size, lh);
                    renderer.fill_text(
                        core_text::Text {
                            content: piece.to_owned(),
                            bounds: Size::new(f32::INFINITY, lh),
                            size: Pixels(p.size),
                            line_height: LineHeight::Absolute(Pixels(lh)),
                            font: format.font.unwrap_or(p.font),
                            align_x: core_text::Alignment::Default,
                            align_y: iced::alignment::Vertical::Top,
                            shaping: core_text::Shaping::Advanced,
                            wrapping: core_text::Wrapping::None,
                            letter_spacing: iced::Em::ZERO,
                        },
                        Point::new(x, y),
                        format.color.unwrap_or(text_color),
                        code,
                    );
                }
                if p.gutter && left > 0.0 {
                    let number = (self.state.real_line(line) + 1).to_string();
                    let digits = measure.width(&number, p.font, p.size, lh);
                    let pad = if p.folding {
                        4.0 + super::FOLD_WIDTH
                    } else {
                        14.0
                    };
                    renderer.fill_text(
                        core_text::Text {
                            content: number,
                            bounds: Size::new(f32::INFINITY, lh),
                            size: Pixels(p.size),
                            line_height: LineHeight::Absolute(Pixels(lh)),
                            font: p.font,
                            align_x: core_text::Alignment::Default,
                            align_y: iced::alignment::Vertical::Top,
                            shaping: core_text::Shaping::Basic,
                            wrapping: core_text::Wrapping::None,
                            letter_spacing: iced::Em::ZERO,
                        },
                        Point::new(bounds.x + left - pad - digits, y),
                        p.gutter_color.unwrap_or(text_color),
                        Rectangle::new(Point::new(bounds.x, y), Size::new(left, lh)),
                    );
                }
            }
        });
        // A soft shadow under the stuck lines.
        for (i, opacity) in [0.22f32, 0.12, 0.05].into_iter().enumerate() {
            renderer.fill_quad(
                Quad {
                    bounds: Rectangle::new(
                        Point::new(bounds.x, bounds.y + height + i as f32),
                        Size::new(width, 1.0),
                    ),
                    ..Quad::default()
                },
                Background::Color(Color {
                    a: opacity,
                    ..Color::BLACK
                }),
            );
        }
    }
}

impl<'a> From<StickyScroll<'a>> for Element<'a, Message> {
    fn from(sticky: StickyScroll<'a>) -> Self {
        Element::new(sticky)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lines(text: &str) -> impl Fn(usize) -> Option<String> + '_ {
        move |i| text.split('\n').nth(i).map(str::to_owned)
    }

    #[test]
    fn words() {
        assert_eq!(word_at("foo.bar_1(x)", 5), Some((4, 9)));
        assert_eq!(word_at("foo.bar_1(x)", 3), None);
        assert_eq!(word_at("añadir()", 2), Some((0, 7)));
    }

    #[test]
    fn scopes_by_indentation() {
        let text =
            "class A:\n    def f(\n        self,\n    ):\n        x = 1\n\n        y = 2\nz = 3";
        let get = lines(text);
        assert_eq!(scopes(&get, 6), vec![0, 1]);
        assert_eq!(scopes(&get, 5), vec![0, 1]);
        assert_eq!(scopes(&get, 7), Vec::<usize>::new());
        assert_eq!(block_end(&get, 1, 8), 6);
        assert_eq!(block_end(&get, 0, 8), 6);
    }
}
