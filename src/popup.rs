//! `pz.popup`: content shown over everything else, next to the widget it belongs to.
//!
//! A date picker's calendar or a drop-down panel must not be cut off by the panel or the
//! designer box it sits in, so the content is drawn in an overlay layer (like a tooltip or
//! a pick list's menu) placed beside the base: below it by default, flipped to the other side
//! when it does not fit, and kept inside the window. A press outside it or Escape calls
//! `on_dismiss`; presses on the base are left to the base, so it can toggle the popup.

use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer;
use iced::advanced::widget::{self, Tree, Widget};
use iced::advanced::{Clipboard, Shell, mouse, overlay};
use iced::{Element, Event, Length, Point, Rectangle, Size, Vector, keyboard, touch};

use crate::app::Message;

type Theme = iced::Theme;
type Renderer = iced::Renderer;

/// The side of the base the content opens on.
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Side {
    Bottom,
    Top,
    Right,
    Left,
}

/// How the content lines up with the base along that side.
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Align {
    Start,
    Center,
    End,
}

pub struct Popup<'a> {
    base: Element<'a, Message, Theme, Renderer>,
    content: Element<'a, Message, Theme, Renderer>,
    open: bool,
    on_dismiss: Option<Message>,
    side: Side,
    align: Align,
    gap: f32,
}

impl<'a> Popup<'a> {
    pub fn new(
        base: impl Into<Element<'a, Message, Theme, Renderer>>,
        content: Option<Element<'a, Message, Theme, Renderer>>,
        on_dismiss: Option<Message>,
        side: Side,
        align: Align,
        gap: f32,
    ) -> Self {
        let open = content.is_some();
        Self {
            base: base.into(),
            content: content.unwrap_or_else(|| iced::widget::Space::new().into()),
            open,
            on_dismiss,
            side,
            align,
            gap,
        }
    }
}

impl Widget<Message, Theme, Renderer> for Popup<'_> {
    fn children(&self) -> Vec<Tree> {
        vec![Tree::new(&self.base), Tree::new(&self.content)]
    }

    fn diff(&self, tree: &mut Tree) {
        tree.diff_children(&[self.base.as_widget(), self.content.as_widget()]);
    }

    fn size(&self) -> Size<Length> {
        self.base.as_widget().size()
    }

    fn size_hint(&self) -> Size<Length> {
        self.base.as_widget().size_hint()
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        self.base
            .as_widget_mut()
            .layout(&mut tree.children[0], renderer, limits)
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
        self.base.as_widget_mut().update(
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
        self.base.as_widget().mouse_interaction(
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
        self.base.as_widget().draw(
            &tree.children[0],
            renderer,
            theme,
            style,
            layout,
            cursor,
            viewport,
        );
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        self.base
            .as_widget_mut()
            .operate(&mut tree.children[0], layout, renderer, operation);
    }

    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &Renderer,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<overlay::Element<'b, Message, Theme, Renderer>> {
        let mut children = tree.children.iter_mut();
        let base_tree = children.next().unwrap();
        let content_tree = children.next().unwrap();
        let base =
            self.base
                .as_widget_mut()
                .overlay(base_tree, layout, renderer, viewport, translation);
        let popup = self.open.then(|| {
            overlay::Element::new(Box::new(Overlay {
                content: &mut self.content,
                tree: content_tree,
                anchor: layout.bounds() + translation,
                on_dismiss: self.on_dismiss.clone(),
                side: self.side,
                align: self.align,
                gap: self.gap,
                node: None,
            }))
        });
        match (base, popup) {
            (None, None) => None,
            (Some(one), None) | (None, Some(one)) => Some(one),
            (Some(base), Some(popup)) => {
                Some(overlay::Group::with_children(vec![base, popup]).overlay())
            }
        }
    }
}

impl<'a> From<Popup<'a>> for Element<'a, Message, Theme, Renderer> {
    fn from(popup: Popup<'a>) -> Self {
        Element::new(popup)
    }
}

struct Overlay<'a, 'b> {
    content: &'b mut Element<'a, Message, Theme, Renderer>,
    tree: &'b mut Tree,
    /// The base's bounds, in window coordinates.
    anchor: Rectangle,
    on_dismiss: Option<Message>,
    side: Side,
    align: Align,
    gap: f32,
    /// The content's layout where it was placed, for overlays opened inside it (a pick list).
    node: Option<layout::Node>,
}

/// Where along a side of length `span` starting at `start` content of `size` begins.
fn aligned(align: Align, start: f32, span: f32, size: f32) -> f32 {
    match align {
        Align::Start => start,
        Align::Center => start + (span - size) / 2.0,
        Align::End => start + span - size,
    }
}

impl Overlay<'_, '_> {
    /// The top-left corner of content of `size` in a window of `bounds`.
    fn place(&self, size: Size, bounds: Size) -> Point {
        let a = self.anchor;
        let gap = self.gap;
        let below = a.y + a.height + gap;
        let above = a.y - gap - size.height;
        let after = a.x + a.width + gap;
        let before = a.x - gap - size.width;
        let (x, y) = match self.side {
            Side::Bottom | Side::Top => {
                let fits_below = below + size.height <= bounds.height;
                let fits_above = above >= 0.0;
                let y = match self.side {
                    Side::Bottom if !fits_below && fits_above => above,
                    Side::Top if !fits_above && fits_below => below,
                    Side::Bottom => below,
                    _ => above,
                };
                (aligned(self.align, a.x, a.width, size.width), y)
            }
            Side::Right | Side::Left => {
                let fits_after = after + size.width <= bounds.width;
                let fits_before = before >= 0.0;
                let x = match self.side {
                    Side::Right if !fits_after && fits_before => before,
                    Side::Left if !fits_before && fits_after => after,
                    Side::Right => after,
                    _ => before,
                };
                (x, aligned(self.align, a.y, a.height, size.height))
            }
        };
        Point::new(
            x.min(bounds.width - size.width).max(0.0),
            y.min(bounds.height - size.height).max(0.0),
        )
    }

    fn dismiss(&self, shell: &mut Shell<'_, Message>) {
        if let Some(message) = &self.on_dismiss {
            shell.publish(message.clone());
        }
    }
}

impl overlay::Overlay<Message, Theme, Renderer> for Overlay<'_, '_> {
    fn layout(&mut self, renderer: &Renderer, bounds: Size) -> layout::Node {
        let limits = layout::Limits::new(Size::ZERO, bounds);
        let node = self
            .content
            .as_widget_mut()
            .layout(self.tree, renderer, &limits);
        let at = self.place(node.size(), bounds);
        let node = node.move_to(at);
        self.node = Some(node.clone());
        node
    }

    fn draw(
        &self,
        renderer: &mut Renderer,
        theme: &Theme,
        style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
    ) {
        self.content.as_widget().draw(
            self.tree,
            renderer,
            theme,
            style,
            layout,
            cursor,
            &layout.bounds(),
        );
    }

    fn operate(
        &mut self,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        self.content
            .as_widget_mut()
            .operate(self.tree, layout, renderer, operation);
    }

    fn update(
        &mut self,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
    ) {
        let bounds = layout.bounds();
        match event {
            Event::Mouse(mouse::Event::ButtonPressed(_))
            | Event::Touch(touch::Event::FingerPressed { .. })
                if !cursor.is_over(bounds) && !cursor.is_over(self.anchor) =>
            {
                self.dismiss(shell);
            }
            Event::Keyboard(keyboard::Event::KeyPressed {
                key: keyboard::Key::Named(keyboard::key::Named::Escape),
                ..
            }) => {
                self.dismiss(shell);
                shell.capture_event();
                return;
            }
            _ => {}
        }
        self.content.as_widget_mut().update(
            self.tree, event, layout, cursor, renderer, clipboard, shell, &bounds,
        );
    }

    fn mouse_interaction(
        &self,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &Renderer,
    ) -> mouse::Interaction {
        if !cursor.is_over(layout.bounds()) {
            return mouse::Interaction::None;
        }
        // anything but None tells iced the pointer is over the popup, not over what is under it
        match self.content.as_widget().mouse_interaction(
            self.tree,
            layout,
            cursor,
            &layout.bounds(),
            renderer,
        ) {
            mouse::Interaction::None => mouse::Interaction::Idle,
            other => other,
        }
    }

    fn overlay<'c>(
        &'c mut self,
        _layout: Layout<'c>,
        renderer: &Renderer,
    ) -> Option<overlay::Element<'c, Message, Theme, Renderer>> {
        let node = self.node.as_ref()?;
        let viewport = node.bounds();
        self.content.as_widget_mut().overlay(
            self.tree,
            Layout::new(node),
            renderer,
            &viewport,
            Vector::ZERO,
        )
    }
}
