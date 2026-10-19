//! Custom widgets used by the code editor: the cursor (`Caret`), the `Minimap` and
//! `ZoomWheel` (Ctrl + mouse wheel changes the font size).

use std::cell::Cell;
use std::time::{Duration, Instant};

use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer::{self, Quad};
use iced::advanced::text::{self as core_text, Renderer as _};
use iced::advanced::widget::{self, Tree, Widget, tree};
use iced::advanced::{Clipboard, Shell, mouse, overlay};
use iced::widget::text::LineHeight;
use iced::{
    Background, Border, Color, Element, Event, Font, Length, Pixels, Point, Rectangle, Size, Theme,
    Vector, keyboard, window,
};

use crate::app::Message;
use crate::editor::{EditorState, PAD_Y, scroll_id};
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
            || self.state.content.cursor().selection.is_some()
        {
            return false;
        }
        let now = Instant::now();
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
    pub id: std::sync::Arc<str>,
    pub width: f32,
    pub height: f32,
    /// Height of an editor line.
    pub line_height: f32,
    pub thumb: Option<Color>,
    /// Covers the text scrolled under the minimap.
    pub background: Option<Color>,
}

#[derive(Default)]
struct MinimapState {
    /// While dragging the thumb: where it was grabbed, from its top.
    grab: Option<f32>,
}

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

    fn scroll_to(&self, y: f32, g: &Geometry, shell: &mut Shell<'_, Message>) {
        let y = y.clamp(0.0, g.max_scroll);
        if (y - g.scroll).abs() >= 0.5 {
            shell.publish(Message::EditorScroll {
                id: scroll_id(&self.id),
                y,
            });
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
            Event::Mouse(mouse::Event::WheelScrolled { delta }) if cursor.is_over(bounds) => {
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
            let cache = self.state.minimap.borrow();
            let first = metrics
                .starts
                .partition_point(|row| (*row as f32 + 1.0) * MINI_LINE < g.offset)
                .saturating_sub(1);
            let left = bounds.x + 4.0;
            for (line, runs) in cache.lines.iter().enumerate().skip(first) {
                let Some(row) = metrics.starts.get(line) else {
                    break;
                };
                let y = bounds.y + *row as f32 * MINI_LINE - g.offset;
                if y > bounds.y + bounds.height {
                    break;
                }
                for (column, len, color) in runs {
                    let x = left + *column as f32 * MINI_COLUMN;
                    if x >= bounds.x + bounds.width {
                        break;
                    }
                    let w = (*len as f32 * MINI_COLUMN).min(bounds.x + bounds.width - x);
                    renderer.fill_quad(
                        Quad {
                            bounds: Rectangle::new(Point::new(x, y), Size::new(w, MINI_TEXT)),
                            ..Quad::default()
                        },
                        Background::Color(Color {
                            a: color.a * 0.7,
                            ..*color
                        }),
                    );
                }
            }
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
// ZoomWheel
// ---------------------------------------------------------------------------

/// Turns Ctrl/Cmd + mouse wheel over its content into `on_zoom(+1 | -1)`, before the content
/// (a scrollable) sees the wheel.
pub struct ZoomWheel<'a> {
    content: Element<'a, Message>,
    on_zoom: PyMsg,
}

impl<'a> ZoomWheel<'a> {
    pub fn new(content: impl Into<Element<'a, Message>>, on_zoom: PyMsg) -> Self {
        Self {
            content: content.into(),
            on_zoom,
        }
    }
}

#[derive(Default)]
struct ZoomState {
    modifiers: keyboard::Modifiers,
}

impl Widget<Message, Theme, Renderer> for ZoomWheel<'_> {
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
        let state = tree.state.downcast_mut::<ZoomState>();
        match event {
            Event::Keyboard(keyboard::Event::ModifiersChanged(modifiers)) => {
                state.modifiers = *modifiers;
            }
            // Some X11 setups miss the change when the key goes up.
            Event::Keyboard(keyboard::Event::KeyReleased {
                key:
                    keyboard::Key::Named(keyboard::key::Named::Control | keyboard::key::Named::Super),
                ..
            }) => {
                state
                    .modifiers
                    .remove(keyboard::Modifiers::CTRL | keyboard::Modifiers::LOGO);
            }
            Event::Mouse(mouse::Event::WheelScrolled { delta })
                if state.modifiers.command() && cursor.is_over(layout.bounds()) =>
            {
                let y = match delta {
                    mouse::ScrollDelta::Lines { y, .. } | mouse::ScrollDelta::Pixels { y, .. } => {
                        *y
                    }
                };
                if y != 0.0 {
                    shell.publish(Message::Slide(self.on_zoom.clone(), y.signum()));
                }
                shell.capture_event();
                return;
            }
            _ => {}
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

impl<'a> From<ZoomWheel<'a>> for Element<'a, Message> {
    fn from(wheel: ZoomWheel<'a>) -> Self {
        Element::new(wheel)
    }
}
