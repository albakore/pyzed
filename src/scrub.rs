//! A number you change by dragging, like the number fields of Figma and Blender.
//!
//! `Scrub` wraps a field (the text input of a number field): pressing the left button over
//! it and moving the mouse sideways reports how far it moved, so Python can step the value,
//! even when the pointer leaves the field or the window. A double click hands the field the
//! keyboard focus with its text selected, to type a value; Enter, Escape or a click outside
//! give it back. While the field has the focus (a double click, or Tab), every event goes
//! to it as usual.

use std::time::{Duration, Instant};

use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer;
use iced::advanced::widget::operation::{Focusable, TextInput};
use iced::advanced::widget::{self, Id, Operation, Tree, Widget};
use iced::advanced::{Clipboard, Shell, mouse, overlay};
use iced::keyboard::{self, key};
use iced::{Element, Event, Length, Point, Rectangle, Size, Vector};

use crate::app::Message;
use crate::widget::PyMsg;

/// Sideways travel (in logical pixels) before a press turns into a scrub.
const THRESHOLD: f32 = 3.0;
/// Longest gap between the two clicks of a double click.
const DOUBLE_CLICK: Duration = Duration::from_millis(400);

#[derive(Default)]
struct State {
    /// Where the left button went down over the field (while it is not being typed in).
    press: Option<Point>,
    /// The pointer's last position while scrubbing.
    last: Option<Point>,
    scrubbing: bool,
    last_click: Option<Instant>,
    /// The field had the focus after the last event (read by `mouse_interaction`).
    editing: bool,
}

/// Wraps `content` (a field) and reports sideways drags over it.
pub struct Scrub<'a, Theme, Renderer> {
    content: Element<'a, Message, Theme, Renderer>,
    on_scrub: Option<PyMsg>,
    on_start: Option<PyMsg>,
    on_end: Option<PyMsg>,
}

impl<'a, Theme, Renderer> Scrub<'a, Theme, Renderer> {
    pub fn new(
        content: impl Into<Element<'a, Message, Theme, Renderer>>,
        on_scrub: Option<PyMsg>,
        on_start: Option<PyMsg>,
        on_end: Option<PyMsg>,
    ) -> Self {
        Self {
            content: content.into(),
            on_scrub,
            on_start,
            on_end,
        }
    }
}

/// Finds out whether a focusable widget inside has the focus.
struct Probe(bool);

impl Operation for Probe {
    fn traverse(&mut self, operate: &mut dyn FnMut(&mut dyn Operation)) {
        operate(self);
    }

    fn focusable(&mut self, _id: Option<&Id>, _bounds: Rectangle, state: &mut dyn Focusable) {
        self.0 |= state.is_focused();
    }
}

/// Focuses the field inside (`Focus(true)`) or takes the focus away from it.
struct Focus(bool);

impl Operation for Focus {
    fn traverse(&mut self, operate: &mut dyn FnMut(&mut dyn Operation)) {
        operate(self);
    }

    fn focusable(&mut self, _id: Option<&Id>, _bounds: Rectangle, state: &mut dyn Focusable) {
        if self.0 {
            state.focus();
        } else {
            state.unfocus();
        }
    }
}

/// Selects the whole text of the field inside (after focusing it, which moves the cursor to the end).
struct SelectAll;

impl Operation for SelectAll {
    fn traverse(&mut self, operate: &mut dyn FnMut(&mut dyn Operation)) {
        operate(self);
    }

    fn text_input(&mut self, _id: Option<&Id>, _bounds: Rectangle, state: &mut dyn TextInput) {
        state.select_all();
    }
}

impl<Theme, Renderer> Scrub<'_, Theme, Renderer>
where
    Renderer: iced::advanced::Renderer,
{
    fn run(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn Operation,
    ) {
        self.content
            .as_widget_mut()
            .operate(&mut tree.children[0], layout, renderer, operation);
    }

    fn editing(&mut self, tree: &mut Tree, layout: Layout<'_>, renderer: &Renderer) -> bool {
        let mut probe = Probe(false);
        self.run(tree, layout, renderer, &mut probe);
        probe.0
    }
}

impl<Theme, Renderer> Widget<Message, Theme, Renderer> for Scrub<'_, Theme, Renderer>
where
    Renderer: iced::advanced::Renderer,
{
    fn tag(&self) -> widget::tree::Tag {
        widget::tree::Tag::of::<State>()
    }

    fn state(&self) -> widget::tree::State {
        widget::tree::State::new(State::default())
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

    fn size_hint(&self) -> Size<Length> {
        self.content.as_widget().size_hint()
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
        operation: &mut dyn Operation,
    ) {
        self.run(tree, layout, renderer, operation);
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
        let editing = self.editing(tree, layout, renderer);
        let state = tree.state.downcast_mut::<State>();
        state.editing = editing;
        match event {
            Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left))
                if !editing && cursor.is_over(bounds) && cursor.is_over(*viewport) =>
            {
                let at = cursor.position().unwrap_or_default();
                let now = Instant::now();
                shell.capture_event();
                if matches!(state.last_click, Some(time) if now.duration_since(time) <= DOUBLE_CLICK)
                {
                    state.last_click = None;
                    state.press = None;
                    self.run(tree, layout, renderer, &mut Focus(true));
                    self.run(tree, layout, renderer, &mut SelectAll);
                    tree.state.downcast_mut::<State>().editing = true;
                    shell.request_redraw();
                    return;
                }
                state.last_click = Some(now);
                state.press = Some(at);
                state.last = Some(at);
                state.scrubbing = false;
                return;
            }
            Event::Mouse(mouse::Event::CursorMoved { position }) if state.press.is_some() => {
                let start = state.press.unwrap_or(*position);
                if !state.scrubbing && (position.x - start.x).abs() > THRESHOLD {
                    state.scrubbing = true;
                    state.last_click = None;
                    if let Some(msg) = &self.on_start {
                        shell.publish(Message::Py(msg.clone()));
                    }
                }
                if state.scrubbing {
                    let last = state.last.unwrap_or(start);
                    state.last = Some(*position);
                    let dx = position.x - last.x;
                    if dx != 0.0
                        && let Some(msg) = &self.on_scrub
                    {
                        shell.publish(Message::Slide(msg.clone(), dx));
                    }
                    shell.capture_event();
                    return;
                }
            }
            Event::Mouse(mouse::Event::ButtonReleased(mouse::Button::Left))
                if state.press.is_some() =>
            {
                state.press = None;
                if std::mem::take(&mut state.scrubbing) {
                    if let Some(msg) = &self.on_end {
                        shell.publish(Message::Py(msg.clone()));
                    }
                    shell.capture_event();
                }
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
        // Enter hands the value back too: the field stops being typed in, like Figma's.
        if editing
            && matches!(
                event,
                Event::Keyboard(keyboard::Event::KeyPressed {
                    key: keyboard::Key::Named(key::Named::Enter),
                    ..
                })
            )
        {
            self.run(tree, layout, renderer, &mut Focus(false));
            shell.request_redraw();
        }
        let editing = self.editing(tree, layout, renderer);
        tree.state.downcast_mut::<State>().editing = editing;
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
        renderer: &Renderer,
    ) -> mouse::Interaction {
        let state = tree.state.downcast_ref::<State>();
        if state.scrubbing || (!state.editing && cursor.is_over(layout.bounds())) {
            return mouse::Interaction::ResizingHorizontally;
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

impl<'a, Theme, Renderer> From<Scrub<'a, Theme, Renderer>> for Element<'a, Message, Theme, Renderer>
where
    Theme: 'a,
    Renderer: iced::advanced::Renderer + 'a,
{
    fn from(scrub: Scrub<'a, Theme, Renderer>) -> Self {
        Element::new(scrub)
    }
}
