//! The common events every widget can have (click, double click, hover, drag, focus,
//! keys, resize...), implemented once in a wrapper widget instead of in each component.
//!
//! Python attaches them with `widget.on(click=..., drag=...)`. The wrapper only observes
//! events: it never captures them, so buttons, inputs and other children inside keep
//! working, and an event bubbles to every wrapper under the pointer, like in a browser.

use std::time::{Duration, Instant};

use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer;
use iced::advanced::widget::{self, Tree, Widget};
use iced::advanced::{Clipboard, Shell, mouse, overlay};
use iced::keyboard::{self, Modifiers};
use iced::{Element, Event, Length, Point, Rectangle, Size, Vector};

use crate::app::Message;
use crate::widget::PyMsg;

/// Pointer travel (in logical pixels) before a press turns into a drag.
const DRAG_THRESHOLD: f32 = 4.0;
/// Longest gap between the two clicks of a double click.
const DOUBLE_CLICK: Duration = Duration::from_millis(400);

macro_rules! event_kinds {
    ($($variant:ident => $name:literal),* $(,)?) => {
        /// One of the common events. `name()` is what Python uses (`on(double_click=...)`).
        #[derive(Debug, Clone, Copy, PartialEq, Eq)]
        pub enum EventKind { $($variant),* }

        impl EventKind {
            pub const ALL: &'static [EventKind] = &[$(EventKind::$variant),*];

            pub fn name(self) -> &'static str {
                match self { $(EventKind::$variant => $name),* }
            }

            pub fn parse(name: &str) -> Option<Self> {
                let name = name.strip_prefix("on_").unwrap_or(name);
                match name { $($name => Some(EventKind::$variant),)* _ => None }
            }
        }
    };
}

event_kinds! {
    Click => "click",
    DoubleClick => "double_click",
    RightClick => "right_click",
    MiddleClick => "middle_click",
    MouseDown => "mouse_down",
    MouseUp => "mouse_up",
    MouseEnter => "mouse_enter",
    MouseLeave => "mouse_leave",
    MouseMove => "mouse_move",
    Scroll => "scroll",
    DragStart => "drag_start",
    Drag => "drag",
    DragEnd => "drag_end",
    Focus => "focus",
    Blur => "blur",
    KeyDown => "key_down",
    KeyUp => "key_up",
    Resize => "resize",
}

/// What happened, sent to Python as a `pyzed.Event`.
#[derive(Debug, Clone)]
pub struct EventData {
    pub kind: EventKind,
    /// Pointer position relative to the widget's top-left corner.
    pub x: f32,
    pub y: f32,
    /// Pointer position in the window (it can be outside it while dragging).
    pub window_x: f32,
    pub window_y: f32,
    pub button: Option<&'static str>,
    /// Scroll amount (in lines) or drag movement since the previous drag event.
    pub dx: f32,
    pub dy: f32,
    /// The widget's size.
    pub width: f32,
    pub height: f32,
    /// The key combo for key events, such as `"ctrl-s"`.
    pub key: Option<String>,
    pub modifiers: Modifiers,
}

/// The handlers attached to one widget.
#[derive(Debug, Clone, Default)]
pub struct Handlers(pub Vec<(EventKind, PyMsg)>);

impl Handlers {
    fn get(&self, kind: EventKind) -> Option<&PyMsg> {
        self.0.iter().find(|(k, _)| *k == kind).map(|(_, m)| m)
    }

    fn has(&self, kind: EventKind) -> bool {
        self.get(kind).is_some()
    }

    /// Adds or replaces the handler for `kind`.
    pub fn set(&mut self, kind: EventKind, handler: PyMsg) {
        match self.0.iter_mut().find(|(k, _)| *k == kind) {
            Some(slot) => slot.1 = handler,
            None => self.0.push((kind, handler)),
        }
    }

    pub fn remove(&mut self, kind: EventKind) {
        self.0.retain(|(k, _)| *k != kind);
    }

    fn clickable(&self) -> bool {
        [
            EventKind::Click,
            EventKind::DoubleClick,
            EventKind::DragStart,
            EventKind::Drag,
        ]
        .iter()
        .any(|k| self.has(*k))
    }
}

#[derive(Default)]
struct State {
    hovered: bool,
    focused: bool,
    press: Option<(mouse::Button, Point)>,
    drag: Option<Point>,
    last_click: Option<(Instant, Point)>,
    size: Option<Size>,
    modifiers: Modifiers,
}

/// Wraps `content` and reports the common events to the attached handlers.
pub struct EventArea<'a, Theme, Renderer> {
    content: Element<'a, Message, Theme, Renderer>,
    handlers: Handlers,
    cursor: Option<mouse::Interaction>,
}

impl<'a, Theme, Renderer> EventArea<'a, Theme, Renderer> {
    pub fn new(
        content: impl Into<Element<'a, Message, Theme, Renderer>>,
        handlers: Handlers,
        cursor: Option<mouse::Interaction>,
    ) -> Self {
        Self {
            content: content.into(),
            handlers,
            cursor,
        }
    }
}

fn button_name(button: mouse::Button) -> &'static str {
    match button {
        mouse::Button::Left => "left",
        mouse::Button::Right => "right",
        mouse::Button::Middle => "middle",
        mouse::Button::Back => "back",
        mouse::Button::Forward => "forward",
        mouse::Button::Other(_) => "other",
    }
}

impl<Theme, Renderer> Widget<Message, Theme, Renderer> for EventArea<'_, Theme, Renderer>
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
        let state = tree.state.downcast_mut::<State>();
        let bounds = layout.bounds();
        let handlers = &self.handlers;
        let base = |kind: EventKind, at: Option<Point>, modifiers: Modifiers| EventData {
            kind,
            x: at.map_or(0.0, |p| p.x - bounds.x),
            y: at.map_or(0.0, |p| p.y - bounds.y),
            window_x: at.map_or(0.0, |p| p.x),
            window_y: at.map_or(0.0, |p| p.y),
            button: None,
            dx: 0.0,
            dy: 0.0,
            width: bounds.width,
            height: bounds.height,
            key: None,
            modifiers,
        };
        let mut publish = |data: EventData| {
            if let Some(handler) = handlers.get(data.kind) {
                shell.publish(Message::Event(handler.clone(), Box::new(data)));
            }
        };

        // Any event (redraws included) is a chance to notice a new size.
        if handlers.has(EventKind::Resize) && state.size != Some(bounds.size()) {
            state.size = Some(bounds.size());
            publish(base(EventKind::Resize, None, state.modifiers));
        }

        let position = cursor.position();
        let over = cursor.position_over(bounds).is_some() && cursor.is_over(*viewport);
        let modifiers = state.modifiers;
        match event {
            Event::Keyboard(keyboard::Event::ModifiersChanged(m)) => state.modifiers = *m,
            Event::Mouse(mouse::Event::CursorMoved { .. } | mouse::Event::CursorLeft) => {
                if over != state.hovered {
                    state.hovered = over;
                    let kind = if over {
                        EventKind::MouseEnter
                    } else {
                        EventKind::MouseLeave
                    };
                    publish(base(kind, position, modifiers));
                }
                let Some(at) = position else { return };
                if over {
                    publish(base(EventKind::MouseMove, Some(at), modifiers));
                }
                if let Some((mouse::Button::Left, start)) = state.press {
                    if state.drag.is_none() && at.distance(start) > DRAG_THRESHOLD {
                        state.drag = Some(start);
                        publish(EventData {
                            button: Some("left"),
                            ..base(EventKind::DragStart, Some(start), modifiers)
                        });
                    }
                    if let Some(last) = state.drag {
                        state.drag = Some(at);
                        publish(EventData {
                            button: Some("left"),
                            dx: at.x - last.x,
                            dy: at.y - last.y,
                            ..base(EventKind::Drag, Some(at), modifiers)
                        });
                    }
                }
            }
            Event::Mouse(mouse::Event::ButtonPressed(button)) => {
                if over {
                    let at = position.unwrap_or_default();
                    state.press = Some((*button, at));
                    let name = Some(button_name(*button));
                    publish(EventData {
                        button: name,
                        ..base(EventKind::MouseDown, Some(at), modifiers)
                    });
                    if !state.focused {
                        state.focused = true;
                        publish(base(EventKind::Focus, Some(at), modifiers));
                    }
                    let kind = match button {
                        mouse::Button::Right => Some(EventKind::RightClick),
                        mouse::Button::Middle => Some(EventKind::MiddleClick),
                        _ => None,
                    };
                    if let Some(kind) = kind {
                        publish(EventData {
                            button: name,
                            ..base(kind, Some(at), modifiers)
                        });
                    }
                } else if state.focused {
                    state.focused = false;
                    publish(base(EventKind::Blur, position, modifiers));
                }
            }
            Event::Mouse(mouse::Event::ButtonReleased(button)) => {
                let pressed = state.press.take();
                let name = Some(button_name(*button));
                if over {
                    publish(EventData {
                        button: name,
                        ..base(EventKind::MouseUp, position, modifiers)
                    });
                }
                let dragged = if *button == mouse::Button::Left {
                    state.drag.take()
                } else {
                    None
                };
                if let Some(last) = dragged {
                    // Released outside the window, the cursor is often already gone: use where it was last.
                    publish(EventData {
                        button: name,
                        ..base(EventKind::DragEnd, position.or(Some(last)), modifiers)
                    });
                } else if over && matches!(pressed, Some((b, _)) if b == *button) {
                    if *button != mouse::Button::Left {
                        return;
                    }
                    let at = position.unwrap_or_default();
                    publish(EventData {
                        button: name,
                        ..base(EventKind::Click, Some(at), modifiers)
                    });
                    let now = Instant::now();
                    match state.last_click {
                        Some((time, point))
                            if now.duration_since(time) <= DOUBLE_CLICK
                                && at.distance(point) <= 2.0 * DRAG_THRESHOLD =>
                        {
                            state.last_click = None;
                            publish(EventData {
                                button: name,
                                ..base(EventKind::DoubleClick, Some(at), modifiers)
                            });
                        }
                        _ => state.last_click = Some((now, at)),
                    }
                }
            }
            Event::Mouse(mouse::Event::WheelScrolled { delta }) if over => {
                let (dx, dy) = match delta {
                    mouse::ScrollDelta::Lines { x, y } => (*x, *y),
                    mouse::ScrollDelta::Pixels { x, y } => (x / 60.0, y / 60.0),
                };
                publish(EventData {
                    dx,
                    dy,
                    ..base(EventKind::Scroll, position, modifiers)
                });
            }
            Event::Keyboard(keyboard::Event::KeyPressed { key, modifiers, .. })
                if state.focused =>
            {
                if let Some(combo) = crate::app::key_combo(key, *modifiers) {
                    publish(EventData {
                        key: Some(combo),
                        ..base(EventKind::KeyDown, position, *modifiers)
                    });
                }
            }
            Event::Keyboard(keyboard::Event::KeyReleased { key, modifiers, .. })
                if state.focused =>
            {
                // Some platforms report no modifiers on release; use the ones still held.
                let held = *modifiers | state.modifiers;
                if let Some(combo) = crate::app::key_combo(key, held) {
                    publish(EventData {
                        key: Some(combo),
                        ..base(EventKind::KeyUp, position, held)
                    });
                }
            }
            _ => {}
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
        let state = tree.state.downcast_ref::<State>();
        if state.drag.is_some() && self.handlers.has(EventKind::Drag) {
            return mouse::Interaction::Grabbing;
        }
        let inner = self.content.as_widget().mouse_interaction(
            &tree.children[0],
            layout,
            cursor,
            viewport,
            renderer,
        );
        if inner != mouse::Interaction::None && inner != mouse::Interaction::Idle {
            return inner;
        }
        if !cursor.is_over(layout.bounds()) {
            return inner;
        }
        match self.cursor {
            Some(cursor) => cursor,
            None if self.handlers.clickable() => mouse::Interaction::Pointer,
            None => inner,
        }
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

impl<'a, Theme, Renderer> From<EventArea<'a, Theme, Renderer>>
    for Element<'a, Message, Theme, Renderer>
where
    Theme: 'a,
    Renderer: iced::advanced::Renderer + 'a,
{
    fn from(area: EventArea<'a, Theme, Renderer>) -> Self {
        Element::new(area)
    }
}
