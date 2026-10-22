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
use iced::{Color, Element, Event, Length, Rectangle, Size, Vector, window};
use pyo3::prelude::*;
use std::any::Any;
use std::sync::Arc;

use crate::widget::PyMsg;

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

/// A control that can have the keyboard focus (`pz.focusable`): a click or Tab gives it the
/// focus, and while it has it the keys in `keys` go to `on_key(combo)` instead of the rest of
/// the app. A ring is drawn around it once the keyboard is used on it, like a browser's
/// `:focus-visible`.
pub struct KeyFocus<'a> {
    content: Element<'a, crate::app::Message>,
    id: Option<Id>,
    keys: Arc<[String]>,
    on_key: Option<PyMsg>,
    ring: Option<Color>,
    radius: f32,
    offset: f32,
}

#[derive(Default)]
struct KeyState {
    focused: bool,
    /// Whether the ring shows: focus from the keyboard, or keys used since the click.
    visible: bool,
}

impl Focusable for KeyState {
    fn is_focused(&self) -> bool {
        self.focused
    }

    fn focus(&mut self) {
        self.focused = true;
        self.visible = true;
    }

    fn unfocus(&mut self) {
        self.focused = false;
        self.visible = false;
    }
}

impl<'a> KeyFocus<'a> {
    pub fn new(content: Element<'a, crate::app::Message>, props: &FocusProps) -> Self {
        Self {
            content,
            id: props.id.clone().map(Id::from),
            keys: props.keys.clone(),
            on_key: props.on_key.clone(),
            ring: props.ring,
            radius: props.radius,
            offset: props.offset,
        }
    }

    fn takes(&self, combo: &str) -> bool {
        self.keys.iter().any(|k| k == combo || k == "*")
    }
}

type Rend = iced::Renderer;

impl Widget<crate::app::Message, iced::Theme, Rend> for KeyFocus<'_> {
    fn tag(&self) -> widget::tree::Tag {
        widget::tree::Tag::of::<KeyState>()
    }

    fn state(&self) -> widget::tree::State {
        widget::tree::State::new(KeyState::default())
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
        renderer: &Rend,
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
        renderer: &Rend,
        operation: &mut dyn Operation,
    ) {
        if self.on_key.is_some() {
            let state = tree.state.downcast_mut::<KeyState>();
            operation.focusable(self.id.as_ref(), layout.bounds(), state);
        }
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
        renderer: &Rend,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, crate::app::Message>,
        viewport: &Rectangle,
    ) {
        let state = tree.state.downcast_mut::<KeyState>();
        if let Event::Keyboard(iced::keyboard::Event::KeyPressed { key, modifiers, .. }) = event
            && state.focused
            && let Some(on_key) = &self.on_key
            && let Some(combo) = crate::app::key_combo(key, *modifiers)
            && self.takes(&combo)
        {
            state.visible = true;
            shell.publish(crate::app::Message::Input(on_key.clone(), combo));
            crate::app::claim_key();
            shell.capture_event();
            shell.request_redraw();
            return;
        }
        if let Event::Mouse(mouse::Event::ButtonPressed(_))
        | Event::Touch(iced::touch::Event::FingerPressed { .. }) = event
        {
            let over = cursor.is_over(layout.bounds());
            if over != state.focused && self.on_key.is_some() {
                state.focused = over;
                state.visible = false;
                shell.request_redraw();
            }
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
        renderer: &Rend,
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
        renderer: &mut Rend,
        theme: &iced::Theme,
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
        let state = tree.state.downcast_ref::<KeyState>();
        if let Some(color) = self.ring
            && state.focused
            && state.visible
        {
            use iced::advanced::Renderer as _;
            let bounds = layout.bounds().expand(self.offset);
            renderer.fill_quad(
                renderer::Quad {
                    bounds,
                    border: iced::Border {
                        color,
                        width: 1.5,
                        radius: (self.radius + self.offset).into(),
                    },
                    ..renderer::Quad::default()
                },
                iced::Background::Color(Color::TRANSPARENT),
            );
        }
    }

    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &Rend,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<overlay::Element<'b, crate::app::Message, iced::Theme, Rend>> {
        self.content.as_widget_mut().overlay(
            &mut tree.children[0],
            layout,
            renderer,
            viewport,
            translation,
        )
    }
}

impl<'a> From<KeyFocus<'a>> for Element<'a, crate::app::Message> {
    fn from(widget: KeyFocus<'a>) -> Self {
        Element::new(widget)
    }
}

/// What `pz.focusable` keeps in its widget node.
pub struct FocusProps {
    pub id: Option<String>,
    pub keys: Arc<[String]>,
    pub on_key: Option<PyMsg>,
    pub ring: Option<Color>,
    pub radius: f32,
    pub offset: f32,
}

/// Lets ``content`` have the keyboard focus like a text field: a click or Tab focuses it
/// (``Command.focus(id)`` too) and, while focused, the key combos in ``keys`` (``"space"``,
/// ``"up"``, ``"shift-right"``...; ``"*"`` for every key) call ``on_key(combo)`` instead of
/// reaching the app's ``on_key``. A ring in ``ring_color`` is drawn ``ring_offset`` pixels
/// around it once the keyboard is used on it. Without ``on_key`` it is just ``content``.
///
/// Events:
/// - `on_key(combo)`: Callable that receives one of ``keys`` pressed while it has the focus.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (content, on_key=None, *, keys=None, id=None, ring_color=None, ring_radius=4.0, ring_offset=2.0))]
pub fn focusable(
    py: Python<'_>,
    content: &Bound<'_, PyAny>,
    on_key: crate::style::Any<'_>,
    keys: Option<Vec<String>>,
    id: Option<String>,
    ring_color: crate::style::Any<'_>,
    ring_radius: f32,
    ring_offset: f32,
) -> PyResult<Py<crate::widget::Widget>> {
    let keys: Vec<String> = keys
        .unwrap_or_else(|| {
            [
                "space", "enter", "up", "down", "left", "right", "home", "end",
            ]
            .map(String::from)
            .to_vec()
        })
        .into_iter()
        .map(|k| normalize_combo(&k))
        .collect();
    crate::widget::new(
        py,
        crate::widget::Kind::Focus {
            child: crate::widget::child(content)?,
            props: Box::new(FocusProps {
                id,
                keys: keys.into(),
                on_key: PyMsg::maybe(&on_key),
                ring: crate::style::opt_color(&ring_color)?,
                radius: ring_radius,
                offset: ring_offset,
            }),
        },
    )
}

/// ``"Shift+Up"`` → ``"shift-up"``, with the modifiers in the order `key_combo` writes them.
fn normalize_combo(keys: &str) -> String {
    let lower = keys.trim().to_lowercase().replace('+', "-");
    if lower == "-" || lower == "*" {
        return lower;
    }
    let mut parts: Vec<&str> = lower.split('-').collect();
    let key = parts.pop().unwrap_or_default();
    let has = |m: &str| {
        parts
            .iter()
            .any(|p| *p == m || (m == "cmd" && (*p == "super" || *p == "meta")))
    };
    let mut out = String::new();
    for m in ["ctrl", "alt", "shift", "cmd"] {
        if has(m) {
            out.push_str(m);
            out.push('-');
        }
    }
    out.push_str(if key.is_empty() { "-" } else { key });
    out
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(focusable, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{next_index, normalize_combo};

    #[test]
    fn normalizes_combos() {
        assert_eq!(normalize_combo("Shift+Up"), "shift-up");
        assert_eq!(normalize_combo("shift-ctrl-a"), "ctrl-shift-a");
        assert_eq!(normalize_combo("space"), "space");
        assert_eq!(normalize_combo("*"), "*");
    }

    #[test]
    fn wraps_around() {
        assert_eq!(next_index(None, 3, true), 0);
        assert_eq!(next_index(None, 3, false), 2);
        assert_eq!(next_index(Some(2), 3, true), 0);
        assert_eq!(next_index(Some(0), 3, false), 2);
        assert_eq!(next_index(Some(1), 3, true), 2);
    }
}
