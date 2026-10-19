//! Keyboard focus: Tab and Shift+Tab move between the fields of a window.
//!
//! Iced 0.14 runs a widget operation over every open window as one tree, so its own
//! `focus_next` would jump from the last field of one window into another window.
//! `Scope` marks the root of each window's view and `cycle` only counts and moves the
//! fields under the marker of the window where the key was pressed (and wraps around).

use iced::Task;
use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer;
use iced::advanced::widget::operation::{Focusable, Outcome};
use iced::advanced::widget::{self, Id, Operation, Tree, Widget};
use iced::advanced::{Clipboard, Shell, mouse, overlay};
use iced::{Element, Event, Length, Rectangle, Size, Vector, window};
use std::any::Any;

/// The marker a window's root reports to operations.
struct Marker(window::Id);

/// Wraps the root of a window's view so focus operations know which window they are in.
pub struct Scope<'a, Message, Theme, Renderer> {
    window: window::Id,
    content: Element<'a, Message, Theme, Renderer>,
}

impl<'a, Message, Theme, Renderer> Scope<'a, Message, Theme, Renderer> {
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

impl<Message, Theme, Renderer> Widget<Message, Theme, Renderer>
    for Scope<'_, Message, Theme, Renderer>
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
        operation.custom(None, layout.bounds(), &mut Marker(self.window));
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

impl<'a, Message, Theme, Renderer> From<Scope<'a, Message, Theme, Renderer>>
    for Element<'a, Message, Theme, Renderer>
where
    Message: 'a,
    Theme: 'a,
    Renderer: iced::advanced::Renderer + 'a,
{
    fn from(scope: Scope<'a, Message, Theme, Renderer>) -> Self {
        Element::new(scope)
    }
}

/// Whether `state` is the marker of a window root, and whether it is `window`.
fn entered(state: &dyn Any, window: window::Id) -> Option<bool> {
    state
        .downcast_ref::<Marker>()
        .map(|marker| marker.0 == window)
}

/// First pass: counts the fields of the window and finds the focused one.
struct Count {
    window: window::Id,
    forward: bool,
    inside: bool,
    focused: Option<usize>,
    total: usize,
}

impl Operation for Count {
    fn traverse(&mut self, operate: &mut dyn FnMut(&mut dyn Operation)) {
        operate(self);
    }

    fn custom(&mut self, _id: Option<&Id>, _bounds: Rectangle, state: &mut dyn Any) {
        if let Some(inside) = entered(state, self.window) {
            self.inside = inside;
        }
    }

    fn focusable(&mut self, _id: Option<&Id>, _bounds: Rectangle, state: &mut dyn Focusable) {
        if !self.inside {
            return;
        }
        if state.is_focused() {
            self.focused = Some(self.total);
        }
        self.total += 1;
    }

    fn finish(&self) -> Outcome<()> {
        if self.total == 0 {
            return Outcome::None;
        }
        let target = next_index(self.focused, self.total, self.forward);
        Outcome::Chain(Box::new(Apply {
            window: self.window,
            inside: false,
            target,
            current: 0,
        }))
    }
}

/// Second pass: focuses the target field of the window and unfocuses the rest.
struct Apply {
    window: window::Id,
    inside: bool,
    target: usize,
    current: usize,
}

impl Operation for Apply {
    fn traverse(&mut self, operate: &mut dyn FnMut(&mut dyn Operation)) {
        operate(self);
    }

    fn custom(&mut self, _id: Option<&Id>, _bounds: Rectangle, state: &mut dyn Any) {
        if let Some(inside) = entered(state, self.window) {
            self.inside = inside;
        }
    }

    fn focusable(&mut self, _id: Option<&Id>, _bounds: Rectangle, state: &mut dyn Focusable) {
        if !self.inside {
            return;
        }
        if self.current == self.target {
            state.focus();
        } else {
            state.unfocus();
        }
        self.current += 1;
    }
}

/// The field that gets the focus: the next (or previous) one, wrapping around; the first
/// (or last) one when nothing is focused.
pub fn next_index(focused: Option<usize>, total: usize, forward: bool) -> usize {
    match (focused, forward) {
        (None, true) => 0,
        (None, false) => total - 1,
        (Some(i), true) => (i + 1) % total,
        (Some(i), false) => (i + total - 1) % total,
    }
}

/// Moves the focus to the next (`forward`) or previous field of `window`.
pub fn cycle<T: Send + 'static>(window: window::Id, forward: bool) -> Task<T> {
    iced::advanced::widget::operate(Count {
        window,
        forward,
        inside: false,
        focused: None,
        total: 0,
    })
    .discard()
}

#[cfg(test)]
mod tests {
    use super::next_index;

    #[test]
    fn wraps_around() {
        assert_eq!(next_index(None, 3, true), 0);
        assert_eq!(next_index(None, 3, false), 2);
        assert_eq!(next_index(Some(2), 3, true), 0);
        assert_eq!(next_index(Some(0), 3, false), 2);
        assert_eq!(next_index(Some(1), 3, true), 2);
    }
}
