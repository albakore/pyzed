//! Small custom widgets that iced does not ship: a left-sticky wrapper (used for the
//! editor gutter, so line numbers stay put while the code scrolls horizontally) and
//! a resizable split.

use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer::{self, Quad};
use iced::advanced::widget::{self, Tree, Widget};
use iced::advanced::{Clipboard, Shell, mouse, overlay};
use iced::{Background, Color, Element, Event, Length, Point, Rectangle, Size, Vector};

/// Lays out `gutter` and `content` side by side, keeping `gutter` pinned to the left edge
/// of the visible area of an enclosing scrollable. The gutter is drawn last, on its own
/// layer, so the content scrolls underneath it.
///
/// Both children live in this one widget (instead of a `row`) because a row skips
/// children outside the viewport, which would hide the gutter once the content is
/// scrolled further than the gutter is wide.
pub struct StickyLeft<'a, Message, Theme, Renderer> {
    gutter: Element<'a, Message, Theme, Renderer>,
    content: Element<'a, Message, Theme, Renderer>,
    background: Option<Color>,
}

impl<'a, Message, Theme, Renderer> StickyLeft<'a, Message, Theme, Renderer> {
    pub fn new(
        gutter: impl Into<Element<'a, Message, Theme, Renderer>>,
        content: impl Into<Element<'a, Message, Theme, Renderer>>,
        background: Option<Color>,
    ) -> Self {
        Self {
            gutter: gutter.into(),
            content: content.into(),
            background,
        }
    }
}

fn shift(bounds: Rectangle, viewport: &Rectangle) -> f32 {
    (viewport.x - bounds.x).max(0.0)
}

impl<Message, Theme, Renderer> Widget<Message, Theme, Renderer>
    for StickyLeft<'_, Message, Theme, Renderer>
where
    Renderer: iced::advanced::Renderer,
{
    fn children(&self) -> Vec<Tree> {
        vec![Tree::new(&self.gutter), Tree::new(&self.content)]
    }

    fn diff(&self, tree: &mut Tree) {
        tree.diff_children(&[&self.gutter, &self.content]);
    }

    fn size(&self) -> Size<Length> {
        Size::new(Length::Shrink, Length::Shrink)
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        let gutter = self
            .gutter
            .as_widget_mut()
            .layout(&mut tree.children[0], renderer, limits);
        let width = gutter.size().width;
        let rest = limits.shrink(Size::new(width, 0.0));
        let content = self
            .content
            .as_widget_mut()
            .layout(&mut tree.children[1], renderer, &rest)
            .move_to(Point::new(width, 0.0));
        let size = Size::new(
            width + content.size().width,
            gutter.size().height.max(content.size().height),
        );
        layout::Node::with_children(
            limits.resolve(Length::Shrink, Length::Shrink, size),
            vec![gutter, content],
        )
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        let mut children = layout.children();
        let (g, c) = (children.next().unwrap(), children.next().unwrap());
        let (tg, tc) = tree.children.split_at_mut(1);
        self.gutter
            .as_widget_mut()
            .operate(&mut tg[0], g, renderer, operation);
        self.content
            .as_widget_mut()
            .operate(&mut tc[0], c, renderer, operation);
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
        let mut children = layout.children();
        let (g, c) = (children.next().unwrap(), children.next().unwrap());
        let dx = shift(layout.bounds(), viewport);
        let over_gutter = cursor
            .position()
            .is_some_and(|p| p.x < g.bounds().x + dx + g.bounds().width);
        let (tg, tc) = tree.children.split_at_mut(1);
        self.gutter.as_widget_mut().update(
            &mut tg[0],
            event,
            g,
            cursor - Vector::new(dx, 0.0),
            renderer,
            clipboard,
            shell,
            viewport,
        );
        // The gutter covers the content under it, so the content doesn't see the cursor there.
        let content_cursor = if over_gutter {
            mouse::Cursor::Unavailable
        } else {
            cursor
        };
        self.content.as_widget_mut().update(
            &mut tc[0],
            event,
            c,
            content_cursor,
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
        let mut children = layout.children();
        let (g, c) = (children.next().unwrap(), children.next().unwrap());
        let dx = shift(layout.bounds(), viewport);
        let gutter = self.gutter.as_widget().mouse_interaction(
            &tree.children[0],
            g,
            cursor - Vector::new(dx, 0.0),
            viewport,
            renderer,
        );
        if gutter != mouse::Interaction::None {
            return gutter;
        }
        if cursor
            .position()
            .is_some_and(|p| p.x < g.bounds().x + dx + g.bounds().width)
        {
            return mouse::Interaction::None;
        }
        self.content
            .as_widget()
            .mouse_interaction(&tree.children[1], c, cursor, viewport, renderer)
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
        let mut children = layout.children();
        let (g, c) = (children.next().unwrap(), children.next().unwrap());
        if c.bounds().intersects(viewport) {
            self.content.as_widget().draw(
                &tree.children[1],
                renderer,
                theme,
                style,
                c,
                cursor,
                viewport,
            );
        }

        let bounds = g.bounds();
        let dx = shift(layout.bounds(), viewport);
        let shown = Rectangle {
            x: bounds.x + dx,
            height: layout.bounds().height,
            ..bounds
        };
        let Some(clip) = shown.intersection(viewport) else {
            return;
        };
        renderer.with_layer(clip, |renderer| {
            if let Some(color) = self.background {
                renderer.fill_quad(
                    Quad {
                        bounds: shown,
                        ..Quad::default()
                    },
                    Background::Color(color),
                );
            }
            renderer.with_translation(Vector::new(dx, 0.0), |renderer| {
                self.gutter.as_widget().draw(
                    &tree.children[0],
                    renderer,
                    theme,
                    style,
                    g,
                    cursor - Vector::new(dx, 0.0),
                    &Rectangle {
                        x: viewport.x - dx,
                        ..*viewport
                    },
                );
            });
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
        let mut children = layout.children();
        let _gutter = children.next();
        let c = children.next()?;
        self.content.as_widget_mut().overlay(
            &mut tree.children[1],
            c,
            renderer,
            viewport,
            translation,
        )
    }
}

impl<'a, Message, Theme, Renderer> From<StickyLeft<'a, Message, Theme, Renderer>>
    for Element<'a, Message, Theme, Renderer>
where
    Message: 'a,
    Theme: 'a,
    Renderer: iced::advanced::Renderer + 'a,
{
    fn from(sticky: StickyLeft<'a, Message, Theme, Renderer>) -> Self {
        Element::new(sticky)
    }
}

// ---------------------------------------------------------------------------
// Split
// ---------------------------------------------------------------------------

/// Two panes separated by a draggable divider. `ratio` is the share of the first pane.
pub struct Split<'a, Message, Theme, Renderer> {
    first: Element<'a, Message, Theme, Renderer>,
    second: Element<'a, Message, Theme, Renderer>,
    vertical: bool,
    ratio: f32,
    min_first: f32,
    min_second: f32,
    handle: f32,
    line: f32,
    color: Color,
    hover_color: Color,
    on_resize: Option<Box<dyn Fn(f32) -> Message + 'a>>,
    width: Length,
    height: Length,
}

#[derive(Default)]
struct SplitState {
    dragging: bool,
    /// The ratio the user dragged to, until the `ratio` prop changes.
    dragged: Option<f32>,
    prop: Option<f32>,
}

pub struct SplitStyle {
    pub color: Color,
    pub hover_color: Color,
    pub line: f32,
    pub handle: f32,
}

impl<'a, Message, Theme, Renderer> Split<'a, Message, Theme, Renderer> {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        first: impl Into<Element<'a, Message, Theme, Renderer>>,
        second: impl Into<Element<'a, Message, Theme, Renderer>>,
        vertical: bool,
        ratio: f32,
        min: (f32, f32),
        style: SplitStyle,
        on_resize: Option<Box<dyn Fn(f32) -> Message + 'a>>,
        size: (Length, Length),
    ) -> Self {
        Self {
            first: first.into(),
            second: second.into(),
            vertical,
            ratio: ratio.clamp(0.0, 1.0),
            min_first: min.0,
            min_second: min.1,
            handle: style.handle.max(style.line),
            line: style.line,
            color: style.color,
            hover_color: style.hover_color,
            on_resize,
            width: size.0,
            height: size.1,
        }
    }

    /// Main-axis length available to both panes, and the first pane's length.
    fn split(&self, total: f32, ratio: f32) -> (f32, f32) {
        let available = (total - self.line).max(0.0);
        let mut first = (available * ratio).round();
        let max_first = (available - self.min_second).max(0.0);
        first = first.min(max_first).max(self.min_first.min(available));
        (available, first)
    }

    fn handle_bounds(&self, layout: Layout<'_>) -> Rectangle {
        let bounds = layout.bounds();
        let first = layout
            .children()
            .next()
            .map(|l| l.bounds())
            .unwrap_or(bounds);
        let grow = (self.handle - self.line) / 2.0;
        if self.vertical {
            Rectangle {
                x: bounds.x,
                y: first.y + first.height - grow,
                width: bounds.width,
                height: self.handle,
            }
        } else {
            Rectangle {
                x: first.x + first.width - grow,
                y: bounds.y,
                width: self.handle,
                height: bounds.height,
            }
        }
    }

    fn line_bounds(&self, layout: Layout<'_>) -> Rectangle {
        let bounds = layout.bounds();
        let first = layout
            .children()
            .next()
            .map(|l| l.bounds())
            .unwrap_or(bounds);
        if self.vertical {
            Rectangle {
                x: bounds.x,
                y: first.y + first.height,
                width: bounds.width,
                height: self.line,
            }
        } else {
            Rectangle {
                x: first.x + first.width,
                y: bounds.y,
                width: self.line,
                height: bounds.height,
            }
        }
    }
}

impl<Message, Theme, Renderer> Widget<Message, Theme, Renderer>
    for Split<'_, Message, Theme, Renderer>
where
    Renderer: iced::advanced::Renderer,
{
    fn tag(&self) -> widget::tree::Tag {
        widget::tree::Tag::of::<SplitState>()
    }

    fn state(&self) -> widget::tree::State {
        widget::tree::State::new(SplitState::default())
    }

    fn children(&self) -> Vec<Tree> {
        vec![Tree::new(&self.first), Tree::new(&self.second)]
    }

    fn diff(&self, tree: &mut Tree) {
        tree.diff_children(&[&self.first, &self.second]);
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
        let size = limits.max();
        let total = if self.vertical {
            size.height
        } else {
            size.width
        };
        let state = tree.state.downcast_mut::<SplitState>();
        if state.prop != Some(self.ratio) {
            state.prop = Some(self.ratio);
            state.dragged = None;
        }
        let ratio = state.dragged.unwrap_or(self.ratio);
        let (available, first_len) = self.split(total, ratio);
        let second_len = (available - first_len).max(0.0);
        let (first_size, second_size, offset) = if self.vertical {
            (
                Size::new(size.width, first_len),
                Size::new(size.width, second_len),
                Point::new(0.0, first_len + self.line),
            )
        } else {
            (
                Size::new(first_len, size.height),
                Size::new(second_len, size.height),
                Point::new(first_len + self.line, 0.0),
            )
        };
        let first = self.first.as_widget_mut().layout(
            &mut tree.children[0],
            renderer,
            &layout::Limits::new(Size::ZERO, first_size)
                .width(Length::Fill)
                .height(Length::Fill),
        );
        let second = self
            .second
            .as_widget_mut()
            .layout(
                &mut tree.children[1],
                renderer,
                &layout::Limits::new(Size::ZERO, second_size)
                    .width(Length::Fill)
                    .height(Length::Fill),
            )
            .move_to(offset);
        layout::Node::with_children(size, vec![first, second])
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        let mut children = layout.children();
        let (a, b) = (children.next().unwrap(), children.next().unwrap());
        let (ta, tb) = tree.children.split_at_mut(1);
        self.first
            .as_widget_mut()
            .operate(&mut ta[0], a, renderer, operation);
        self.second
            .as_widget_mut()
            .operate(&mut tb[0], b, renderer, operation);
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
        let handle = self.handle_bounds(layout);
        let bounds = layout.bounds();
        let state = tree.state.downcast_mut::<SplitState>();
        match event {
            Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left))
                if cursor.is_over(handle) =>
            {
                state.dragging = true;
                shell.capture_event();
                shell.request_redraw();
                return;
            }
            Event::Mouse(mouse::Event::ButtonReleased(mouse::Button::Left)) if state.dragging => {
                state.dragging = false;
                shell.capture_event();
                shell.request_redraw();
                return;
            }
            Event::Mouse(mouse::Event::CursorMoved { position }) if state.dragging => {
                let (start, total) = if self.vertical {
                    (bounds.y, bounds.height)
                } else {
                    (bounds.x, bounds.width)
                };
                let available = (total - self.line).max(1.0);
                let pos = if self.vertical {
                    position.y
                } else {
                    position.x
                };
                let first = (pos - start - self.line / 2.0).clamp(
                    self.min_first.min(available),
                    (available - self.min_second).max(0.0),
                );
                // Without `on_resize` the split keeps the dragged ratio itself.
                state.dragged = Some(first / available);
                if let Some(on_resize) = &self.on_resize {
                    shell.publish(on_resize(first / available));
                }
                shell.invalidate_layout();
                shell.request_redraw();
                shell.capture_event();
                return;
            }
            _ => {}
        }
        let mut children = layout.children();
        let (a, b) = (children.next().unwrap(), children.next().unwrap());
        let (ta, tb) = tree.children.split_at_mut(1);
        self.first.as_widget_mut().update(
            &mut ta[0], event, a, cursor, renderer, clipboard, shell, viewport,
        );
        self.second.as_widget_mut().update(
            &mut tb[0], event, b, cursor, renderer, clipboard, shell, viewport,
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
        let state = tree.state.downcast_ref::<SplitState>();
        if state.dragging || cursor.is_over(self.handle_bounds(layout)) {
            return if self.vertical {
                mouse::Interaction::ResizingVertically
            } else {
                mouse::Interaction::ResizingHorizontally
            };
        }
        let mut children = layout.children();
        let (a, b) = (children.next().unwrap(), children.next().unwrap());
        self.first
            .as_widget()
            .mouse_interaction(&tree.children[0], a, cursor, viewport, renderer)
            .max(self.second.as_widget().mouse_interaction(
                &tree.children[1],
                b,
                cursor,
                viewport,
                renderer,
            ))
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
        let mut children = layout.children();
        let (a, b) = (children.next().unwrap(), children.next().unwrap());
        self.first.as_widget().draw(
            &tree.children[0],
            renderer,
            theme,
            style,
            a,
            cursor,
            viewport,
        );
        self.second.as_widget().draw(
            &tree.children[1],
            renderer,
            theme,
            style,
            b,
            cursor,
            viewport,
        );
        let state = tree.state.downcast_ref::<SplitState>();
        let active = state.dragging || cursor.is_over(self.handle_bounds(layout));
        let line = self.line_bounds(layout);
        let color = if active { self.hover_color } else { self.color };
        let bounds = if active && self.line < 2.0 {
            // Thicken the divider while it is hovered so it is easier to see.
            if self.vertical {
                Rectangle {
                    y: line.y - 1.0,
                    height: line.height + 2.0,
                    ..line
                }
            } else {
                Rectangle {
                    x: line.x - 1.0,
                    width: line.width + 2.0,
                    ..line
                }
            }
        } else {
            line
        };
        renderer.with_layer(layout.bounds(), |renderer| {
            renderer.fill_quad(
                Quad {
                    bounds,
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
        let mut children = layout.children();
        let (a, b) = (children.next().unwrap(), children.next().unwrap());
        let (ta, tb) = tree.children.split_at_mut(1);
        let first =
            self.first
                .as_widget_mut()
                .overlay(&mut ta[0], a, renderer, viewport, translation);
        let second =
            self.second
                .as_widget_mut()
                .overlay(&mut tb[0], b, renderer, viewport, translation);
        let overlays: Vec<_> = first.into_iter().chain(second).collect();
        (!overlays.is_empty()).then(|| overlay::Group::with_children(overlays).overlay())
    }
}

impl<'a, Message, Theme, Renderer> From<Split<'a, Message, Theme, Renderer>>
    for Element<'a, Message, Theme, Renderer>
where
    Message: 'a,
    Theme: 'a,
    Renderer: iced::advanced::Renderer + 'a,
{
    fn from(split: Split<'a, Message, Theme, Renderer>) -> Self {
        Element::new(split)
    }
}

// ---------------------------------------------------------------------------
// Probe
// ---------------------------------------------------------------------------

/// Records the visible part of its content (in content coordinates) every frame.
///
/// Placed directly inside a scrollable, it tells us the scroll offset and viewport
/// size without routing a message through `update` on every scroll event.
pub struct Probe<'a, Message, Theme, Renderer> {
    content: Element<'a, Message, Theme, Renderer>,
    sink: &'a std::cell::Cell<Option<Rectangle>>,
    keep_wheel: bool,
}

impl<'a, Message, Theme, Renderer> Probe<'a, Message, Theme, Renderer> {
    pub fn new(
        content: impl Into<Element<'a, Message, Theme, Renderer>>,
        sink: &'a std::cell::Cell<Option<Rectangle>>,
    ) -> Self {
        Self {
            content: content.into(),
            sink,
            keep_wheel: false,
        }
    }

    /// Keeps mouse wheel events from the content, so the scrollable around scrolls even when
    /// the content would capture them (a text editor laid out at its full height does).
    pub fn keep_wheel(mut self) -> Self {
        self.keep_wheel = true;
        self
    }

    fn record(&self, layout: Layout<'_>, viewport: &Rectangle) {
        let bounds = layout.bounds();
        self.sink.set(Some(Rectangle {
            x: viewport.x - bounds.x,
            y: viewport.y - bounds.y,
            width: viewport.width,
            height: viewport.height,
        }));
    }
}

impl<Message, Theme, Renderer> Widget<Message, Theme, Renderer>
    for Probe<'_, Message, Theme, Renderer>
where
    Renderer: iced::advanced::Renderer,
{
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
        self.record(layout, viewport);
        if self.keep_wheel && matches!(event, Event::Mouse(mouse::Event::WheelScrolled { .. })) {
            return;
        }
        self.content.as_widget_mut().update(
            tree, event, layout, cursor, renderer, clipboard, shell, viewport,
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
        self.content
            .as_widget()
            .mouse_interaction(tree, layout, cursor, viewport, renderer)
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
        self.record(layout, viewport);
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
        self.content
            .as_widget_mut()
            .overlay(tree, layout, renderer, viewport, translation)
    }
}

impl<'a, Message, Theme, Renderer> From<Probe<'a, Message, Theme, Renderer>>
    for Element<'a, Message, Theme, Renderer>
where
    Message: 'a,
    Theme: 'a,
    Renderer: iced::advanced::Renderer + 'a,
{
    fn from(probe: Probe<'a, Message, Theme, Renderer>) -> Self {
        Element::new(probe)
    }
}
