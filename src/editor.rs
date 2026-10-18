//! The code editor: iced's `text_editor` plus a gutter with line numbers and git markers,
//! horizontal scrolling, soft wrap (with line numbers that follow wrapped lines) and
//! Zed-style autoscroll that keeps the cursor visible.

use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use std::sync::Arc;

use iced::advanced::text::{self as core_text, Paragraph as _, Wrapping};
use iced::widget::text::LineHeight;
use iced::widget::text_editor::{self, Binding, Motion};
use iced::widget::{self, Space, column, container, responsive, row, scrollable, text};
use iced::{
    Background, Border, Color, Element, Font, Length, Padding, Pixels, Rectangle, Size, Task,
    Theme, keyboard,
};

use crate::app::Message;
use crate::highlighter::{self, Highlighter};
use crate::sticky::{Probe, StickyLeft};
use crate::widget::EditorProps;

type Paragraph = <iced::Renderer as core_text::Renderer>::Paragraph;

const PAD_Y: f32 = 4.0;
const PAD_LEFT: f32 = 4.0;
const PAD_RIGHT: f32 = 12.0;
const MARKER_WIDTH: f32 = 3.0;

/// Layout facts captured while rendering, used to keep the cursor in view.
#[derive(Default, Clone)]
struct Metrics {
    ready: bool,
    /// Width of the gutter (markers + numbers); text starts after it plus `PAD_LEFT`.
    left: f32,
    line_height: f32,
    size: f32,
    font: Font,
    wrap_width: Option<f32>,
    /// `starts[i]` = visual rows before logical line `i` (has `line_count + 1` entries).
    starts: Vec<u32>,
}

#[derive(Default)]
struct Measure {
    key: u64,
    widths: HashMap<u64, f32>,
    rows: HashMap<u64, u32>,
}

/// The persistent state of one editor (keyed by its `id`).
pub struct EditorState {
    pub content: text_editor::Content,
    metrics: RefCell<Metrics>,
    measure: RefCell<Measure>,
    /// The visible area of the scrollable, in content coordinates (updated every frame).
    viewport: Cell<Option<Rectangle>>,
}

impl EditorState {
    pub fn new(text: &str) -> Self {
        Self {
            content: text_editor::Content::with_text(text),
            metrics: RefCell::default(),
            measure: RefCell::default(),
            viewport: Cell::new(None),
        }
    }

    pub fn reset(&mut self, text: &str) {
        self.content = text_editor::Content::with_text(text);
    }
}

pub fn hash_of(bytes: &[u8]) -> u64 {
    hash(bytes)
}

fn hash<T: Hash + ?Sized>(value: &T) -> u64 {
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    value.hash(&mut hasher);
    hasher.finish()
}

fn paragraph(
    content: &str,
    font: Font,
    size: f32,
    line_height: f32,
    width: Option<f32>,
) -> Paragraph {
    Paragraph::with_text(core_text::Text {
        content,
        bounds: Size::new(width.unwrap_or(f32::INFINITY), f32::INFINITY),
        size: Pixels(size),
        line_height: LineHeight::Absolute(Pixels(line_height)),
        font,
        align_x: core_text::Alignment::Default,
        align_y: iced::alignment::Vertical::Top,
        shaping: core_text::Shaping::Advanced,
        wrapping: if width.is_some() {
            Wrapping::WordOrGlyph
        } else {
            Wrapping::None
        },
    })
}

impl Measure {
    fn reset_if(&mut self, key: u64) {
        if self.key != key {
            self.key = key;
            self.widths.clear();
            self.rows.clear();
        }
        // Keep memory bounded for long editing sessions.
        if self.widths.len() > 50_000 {
            self.widths.clear();
        }
        if self.rows.len() > 50_000 {
            self.rows.clear();
        }
    }

    fn width(&mut self, line: &str, font: Font, size: f32, lh: f32) -> f32 {
        if line.is_empty() {
            return 0.0;
        }
        *self
            .widths
            .entry(hash(line))
            .or_insert_with(|| paragraph(line, font, size, lh, None).min_bounds().width)
    }

    fn rows(&mut self, line: &str, font: Font, size: f32, lh: f32, width: f32) -> u32 {
        if line.is_empty() {
            return 1;
        }
        *self.rows.entry(hash(line)).or_insert_with(|| {
            let height = paragraph(line, font, size, lh, Some(width))
                .min_bounds()
                .height;
            ((height / lh).round() as u32).max(1)
        })
    }
}

/// Result of applying an action to an editor.
pub struct Outcome {
    pub edited: bool,
    pub cursor_moved: bool,
    pub cursor: (usize, usize),
    pub text: String,
    pub scroll: Task<Message>,
}

pub fn scroll_id(id: &str) -> String {
    format!("{id}::scroll")
}

impl EditorState {
    pub fn perform(&mut self, id: &str, action: text_editor::Action) -> Outcome {
        let before = self.content.cursor().position;
        let is_edit = action.is_edit();
        let follows = !matches!(action, text_editor::Action::Scroll { .. });
        self.content.perform(action);
        self.outcome(id, before, is_edit, follows)
    }

    /// Moves the cursor by a page (iced's own page motion assumes a fixed-height editor).
    pub fn page(&mut self, id: &str, down: bool, select: bool) -> Outcome {
        let before = self.content.cursor().position;
        let lh = self.metrics.borrow().line_height.max(1.0);
        let height = self.viewport.get().map(|v| v.height).unwrap_or(lh * 20.0);
        let lines = ((height / lh).floor() as usize).saturating_sub(1).max(1);
        let motion = if down { Motion::Down } else { Motion::Up };
        for _ in 0..lines {
            self.content.perform(if select {
                text_editor::Action::Select(motion)
            } else {
                text_editor::Action::Move(motion)
            });
        }
        self.outcome(id, before, false, true)
    }

    pub fn move_to(&mut self, id: &str, position: text_editor::Position) -> Task<Message> {
        self.content.move_to(text_editor::Cursor {
            position,
            selection: None,
        });
        self.autoscroll(id)
    }

    fn outcome(
        &mut self,
        id: &str,
        before: text_editor::Position,
        edited: bool,
        follows: bool,
    ) -> Outcome {
        let after = self.content.cursor().position;
        let cursor_moved = before != after || edited;
        Outcome {
            edited,
            cursor_moved,
            cursor: (after.line, after.column),
            text: if edited {
                self.content.text()
            } else {
                String::new()
            },
            scroll: if cursor_moved && follows {
                self.autoscroll(id)
            } else {
                Task::none()
            },
        }
    }

    /// Scrolls just enough to reveal the cursor (like Zed's autoscroll).
    fn autoscroll(&self, id: &str) -> Task<Message> {
        let metrics = self.metrics.borrow();
        let Some(viewport) = self.viewport.get() else {
            return Task::none();
        };
        if !metrics.ready {
            return Task::none();
        }
        let position = self.content.cursor().position;
        let lh = metrics.line_height;
        let line = self
            .content
            .line(position.line)
            .map(|l| l.text.into_owned())
            .unwrap_or_default();
        let prefix: String = line.chars().take(position.column).collect();
        let mut measure = self.measure.borrow_mut();
        let row_start = metrics
            .starts
            .get(position.line)
            .copied()
            .unwrap_or(position.line as u32);
        let intra = match metrics.wrap_width {
            Some(width) if !prefix.is_empty() => {
                // Rows taken by the text before the cursor, minus the row it is on.
                let rows = paragraph(&prefix, metrics.font, metrics.size, lh, Some(width))
                    .min_bounds()
                    .height
                    / lh;
                (rows.round() as u32).saturating_sub(1)
            }
            _ => 0,
        };
        let top = PAD_Y + (row_start + intra) as f32 * lh;
        let bottom = top + lh;
        let margin = lh;
        let y = if top - margin < viewport.y {
            Some((top - margin).max(0.0))
        } else if bottom + margin > viewport.y + viewport.height {
            Some(bottom + margin - viewport.height)
        } else {
            None
        };
        let x = if metrics.wrap_width.is_none() {
            let char_width = metrics.size * 0.6;
            let cx =
                metrics.left + PAD_LEFT + measure.width(&prefix, metrics.font, metrics.size, lh);
            let visible_left = viewport.x + metrics.left + PAD_LEFT;
            let visible_right = viewport.x + viewport.width - PAD_RIGHT;
            if cx - char_width * 4.0 < visible_left {
                Some((cx - metrics.left - PAD_LEFT - char_width * 4.0).max(0.0))
            } else if cx + char_width * 4.0 > visible_right {
                Some(cx + char_width * 4.0 + PAD_RIGHT - viewport.width)
            } else {
                None
            }
        } else {
            None
        };
        if x.is_none() && y.is_none() {
            return Task::none();
        }
        let mut moved = viewport;
        if let Some(x) = x {
            moved.x = x;
        }
        if let Some(y) = y {
            moved.y = y;
        }
        self.viewport.set(Some(moved));
        iced::widget::operation::scroll_to(scroll_id(id), scrollable::AbsoluteOffset { x, y })
    }
}

fn with_alpha(color: Color, a: f32) -> Color {
    Color {
        a: color.a * a,
        ..color
    }
}

/// Builds the editor element. `state` lives as long as the view (it is owned by the
/// app's caches), so the closure below can borrow it.
pub fn view<'a>(state: &'a EditorState, props: &EditorProps) -> Element<'a, Message> {
    let props = Arc::new(props.clone());
    let bg = props.background;
    let padding = props.layout.padding.unwrap_or(Padding::ZERO);
    let width = props.layout.width.unwrap_or(Length::Fill);
    let height = props.layout.height.unwrap_or(Length::Fill);
    container(responsive(move |size| body(state, &props, size)))
        .padding(padding)
        .width(width)
        .height(height)
        .style(move |_| container::Style {
            background: bg.map(Background::Color),
            ..Default::default()
        })
        .into()
}

fn numbers<'a>(
    starts: &[u32],
    range: std::ops::Range<usize>,
    color: Color,
    props: &EditorProps,
) -> Element<'a, Message> {
    let lh = props.line_height;
    let mut content = String::new();
    for n in range.clone() {
        if n > range.start {
            content.push('\n');
        }
        content.push_str(&(n + 1).to_string());
        let rows = starts[n + 1] - starts[n];
        for _ in 1..rows {
            content.push('\n');
        }
    }
    let rows = starts[range.end] - starts[range.start];
    text(content)
        .font(props.font)
        .size(props.size)
        .line_height(LineHeight::Absolute(Pixels(lh)))
        .color(color)
        .width(Length::Fill)
        .height(Length::Fixed(rows as f32 * lh))
        .align_x(iced::alignment::Horizontal::Right)
        .wrapping(Wrapping::None)
        .into()
}

fn body<'a>(state: &'a EditorState, props: &Arc<EditorProps>, size: Size) -> Element<'a, Message> {
    let lh = props.line_height;
    let line_count = state.content.line_count().max(1);
    let cursor_line = state.content.cursor().position.line.min(line_count - 1);

    let gutter_width = if props.gutter {
        let digits = line_count.to_string().len().max(2) as f32;
        props
            .gutter_width
            .unwrap_or(digits * props.size * 0.62 + 28.0)
    } else {
        0.0
    };
    let left = if props.gutter {
        MARKER_WIDTH + gutter_width
    } else {
        0.0
    };
    let wrap_width = props
        .wrap
        .then(|| (size.width - left - PAD_LEFT - PAD_RIGHT).max(props.size * 4.0));

    // Measure every line once (results are cached per line text).
    let mut starts = Vec::with_capacity(line_count + 1);
    starts.push(0u32);
    let mut max_width = 0.0f32;
    {
        let mut measure = state.measure.borrow_mut();
        measure.reset_if(hash(&(
            props.font,
            props.size.to_bits(),
            lh.to_bits(),
            wrap_width.map(f32::to_bits),
        )));
        let mut total = 0u32;
        for line in state.content.lines() {
            let rows = match wrap_width {
                Some(width) => measure.rows(&line.text, props.font, props.size, lh, width),
                None => {
                    max_width =
                        max_width.max(measure.width(&line.text, props.font, props.size, lh));
                    1
                }
            };
            total += rows;
            starts.push(total);
        }
        while starts.len() < line_count + 1 {
            total += 1;
            starts.push(total);
        }
    }

    let editor_width = match wrap_width {
        Some(_) => (size.width - left).max(1.0),
        None => (max_width + PAD_LEFT + PAD_RIGHT + props.size * 2.0).max(size.width - left),
    };

    *state.metrics.borrow_mut() = Metrics {
        ready: true,
        left,
        line_height: lh,
        size: props.size,
        font: props.font,
        wrap_width,
        starts: starts.clone(),
    };

    let id = props.id.clone();
    let on_change = props.on_change.clone();
    let on_cursor = props.on_cursor.clone();
    let (fg, sel, placeholder_color) = (
        props.text_color,
        props.selection_color,
        props.placeholder_color,
    );

    let theme_id = highlighter::theme_id(&props.syntax);
    let token = if highlighter::has_syntax(&props.language) {
        props.language.clone()
    } else {
        "txt".into()
    };

    let page_id = props.id.clone();
    let page_cursor = props.on_cursor.clone();
    let mut editor = widget::text_editor(&state.content)
        .font(props.font)
        .size(props.size)
        .line_height(LineHeight::Absolute(Pixels(lh)))
        .padding(Padding {
            top: PAD_Y,
            bottom: PAD_Y,
            left: PAD_LEFT,
            right: PAD_RIGHT,
        })
        .width(editor_width)
        .wrapping(if props.wrap {
            Wrapping::WordOrGlyph
        } else {
            Wrapping::None
        })
        .height(Length::Shrink)
        .on_action(move |action| Message::Editor {
            id: id.clone(),
            action,
            on_change: on_change.clone(),
            on_cursor: on_cursor.clone(),
        })
        .key_binding(move |press| {
            let page = |down: bool, select: bool| {
                Some(Binding::Custom(Message::EditorPage {
                    id: page_id.clone(),
                    down,
                    select,
                    on_cursor: page_cursor.clone(),
                }))
            };
            if !matches!(press.status, text_editor::Status::Focused { .. }) {
                return Binding::from_key_press(press);
            }
            let select = press.modifiers.shift();
            match press.key.as_ref() {
                keyboard::Key::Named(keyboard::key::Named::PageDown) => page(true, select),
                keyboard::Key::Named(keyboard::key::Named::PageUp) => page(false, select),
                _ => Binding::from_key_press(press),
            }
        })
        .style(move |theme: &Theme, status| {
            let mut out = text_editor::default(theme, status);
            out.background = Background::Color(Color::TRANSPARENT);
            out.border = Border::default();
            if let Some(c) = fg {
                out.value = c;
            }
            if let Some(c) = sel {
                out.selection = c;
            }
            if let Some(c) = placeholder_color {
                out.placeholder = c;
            }
            out
        });
    if let Some(p) = &props.placeholder {
        editor = editor.placeholder(p.clone());
    }
    let editor = editor.highlight_with::<Highlighter>(
        highlighter::Settings {
            token,
            theme: theme_id,
            font: props.font,
        },
        highlighter::Highlight::to_format,
    );

    // The active line is highlighted with a band drawn underneath the text.
    let code: Element<'a, Message> = match props.active_line {
        Some(color) => {
            let top = PAD_Y + starts[cursor_line] as f32 * lh;
            let rows = starts[cursor_line + 1] - starts[cursor_line];
            let band = column![
                Space::new().height(Length::Fixed(top)),
                container(Space::new())
                    .width(Length::Fixed(editor_width))
                    .height(Length::Fixed(rows as f32 * lh))
                    .style(move |_| container::Style {
                        background: Some(Background::Color(color)),
                        ..Default::default()
                    }),
            ]
            // A stack takes the size of its first child, so the band spans the whole text.
            .height(Length::Fixed(
                2.0 * PAD_Y + starts[starts.len() - 1] as f32 * lh,
            ));
            widget::Stack::with_children([band.into(), editor.into()]).into()
        }
        None => editor.into(),
    };

    let body: Element<'_, Message> = if props.gutter {
        let dim = props
            .gutter_color
            .unwrap_or(Color::from_rgb8(0x4e, 0x5a, 0x5f));
        let active = props
            .gutter_active_color
            .unwrap_or(Color::from_rgb8(0xd0, 0xd4, 0xda));
        let mut gutter = column![]
            .width(Length::Fixed(gutter_width))
            .padding(Padding {
                top: PAD_Y,
                bottom: PAD_Y,
                left: 0.0,
                right: 14.0,
            });
        if cursor_line > 0 {
            gutter = gutter.push(numbers(&starts, 0..cursor_line, dim, props));
        }
        gutter = gutter.push(numbers(
            &starts,
            cursor_line..cursor_line + 1,
            active,
            props,
        ));
        if cursor_line + 1 < line_count {
            gutter = gutter.push(numbers(&starts, cursor_line + 1..line_count, dim, props));
        }

        // Git-style change markers drawn as thin bars on the left edge of the gutter.
        let mut markers = props.markers.clone();
        markers.sort_by_key(|(line, _)| *line);
        let mut bars = column![]
            .width(Length::Fixed(MARKER_WIDTH))
            .padding(Padding {
                top: PAD_Y,
                ..Padding::ZERO
            });
        let mut next = 1usize;
        for (line, color) in markers {
            if line < next || line > line_count {
                continue;
            }
            if line > next {
                let gap = starts[line - 1] - starts[next - 1];
                bars = bars.push(Space::new().height(Length::Fixed(gap as f32 * lh)));
            }
            let rows = starts[line] - starts[line - 1];
            bars = bars.push(
                container(Space::new())
                    .width(Length::Fixed(MARKER_WIDTH))
                    .height(Length::Fixed(rows as f32 * lh))
                    .style(move |_| container::Style {
                        background: Some(Background::Color(color)),
                        ..Default::default()
                    }),
            );
            next = line + 1;
        }
        let gutter_bg = props.background.or(Some(Color::TRANSPARENT));
        StickyLeft::new(row![bars, gutter], code, gutter_bg).into()
    } else {
        code
    };

    let bar = scrollable::Scrollbar::new().width(8.0).scroller_width(8.0);
    let direction = if props.wrap {
        scrollable::Direction::Vertical(bar)
    } else {
        scrollable::Direction::Both {
            vertical: bar,
            horizontal: bar,
        }
    };
    let scroller_color = props.scrollbar_color;
    widget::Scrollable::with_direction(Probe::new(body, &state.viewport), direction)
        .id(scroll_id(&props.id))
        .style(move |theme: &Theme, status| {
            let mut out = scrollable::default(theme, status);
            let color = scroller_color.unwrap_or(with_alpha(
                theme.extended_palette().background.strong.color,
                0.6,
            ));
            for rail in [&mut out.vertical_rail, &mut out.horizontal_rail] {
                rail.background = None;
                rail.border = Border::default();
                rail.scroller.background = Background::Color(color);
                rail.scroller.border = Border::default();
            }
            out
        })
        .width(Length::Fill)
        .height(Length::Fill)
        .into()
}
