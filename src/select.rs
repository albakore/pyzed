//! The dropdown behind `pz.pick_list` and `ui.select`: Iced's `PickList` with the keyboard.
//!
//! Iced 0.14's pick list only answers the mouse. This one (the same drawing and menu,
//! adapted from `iced_widget::pick_list`, MIT) can also have the keyboard focus, like a
//! text field: a click or Tab focuses it, and it keeps the focus after a choice closes the
//! menu. While focused and closed, ↑/↓ (and ←/→) pick the previous or next option without
//! opening it, Home/End the first and last, and typing jumps to an option by its first
//! letters. Enter, Space, Alt+↓ or F4 open the menu; there ↑/↓ move the highlight, Enter
//! picks it and Escape closes it. The keys it uses do not reach `on_key`.

use std::time::{Duration, Instant};

use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer::{self, Renderer as _};
use iced::advanced::text::{self, Renderer as _, Text, paragraph};
use iced::advanced::widget::operation::Focusable;
use iced::advanced::widget::{Id, Operation, Tree, tree};
use iced::advanced::{Clipboard, Shell, Widget, mouse, overlay};
use iced::keyboard::{self, Key, key::Named};
use iced::overlay::menu::{self, Menu};
use iced::widget::pick_list::{Status, Style};
use iced::{
    Color, Element, Event, Font, Length, Padding, Pixels, Point, Rectangle, Size, Theme, Vector,
    alignment, window,
};

use crate::app::Message;
use crate::widget::PyMsg;

type Renderer = iced::Renderer;
type Paragraph = <Renderer as text::Renderer>::Paragraph;

type StyleFn<'a> = Box<dyn Fn(&Theme, Status) -> Style + 'a>;

/// How long typed letters keep adding up to one search ("ap" + "p" → "app").
const TYPE_AHEAD: Duration = Duration::from_millis(900);

pub struct Select<'a> {
    options: Vec<String>,
    selected: Option<String>,
    on_select: Option<PyMsg>,
    on_open: Option<PyMsg>,
    on_close: Option<PyMsg>,
    placeholder: Option<String>,
    width: Length,
    padding: Padding,
    text_size: Option<Pixels>,
    font: Option<Font>,
    handle: Option<(Font, char, Pixels)>,
    menu_height: Length,
    id: Option<Id>,
    focus_border: Option<Color>,
    style: StyleFn<'a>,
    menu_style: menu::StyleFn<'a, Theme>,
    last_status: Option<Status>,
}

impl<'a> Select<'a> {
    pub fn new(options: Vec<String>, selected: Option<String>, on_select: Option<PyMsg>) -> Self {
        Self {
            options,
            selected,
            on_select,
            on_open: None,
            on_close: None,
            placeholder: None,
            width: Length::Shrink,
            padding: Padding::from([5, 10]),
            text_size: None,
            font: None,
            handle: None,
            menu_height: Length::Shrink,
            id: None,
            focus_border: None,
            style: Box::new(iced::widget::pick_list::default),
            menu_style: Box::new(menu::default),
            last_status: None,
        }
    }

    pub fn on_open(mut self, message: Option<PyMsg>) -> Self {
        self.on_open = message;
        self
    }

    pub fn on_close(mut self, message: Option<PyMsg>) -> Self {
        self.on_close = message;
        self
    }

    pub fn placeholder(mut self, placeholder: Option<String>) -> Self {
        self.placeholder = placeholder;
        self
    }

    pub fn width(mut self, width: Length) -> Self {
        self.width = width;
        self
    }

    pub fn padding(mut self, padding: Padding) -> Self {
        self.padding = padding;
        self
    }

    pub fn text_size(mut self, size: f32) -> Self {
        self.text_size = Some(Pixels(size));
        self
    }

    pub fn font(mut self, font: Font) -> Self {
        self.font = Some(font);
        self
    }

    pub fn handle(mut self, font: Font, code_point: char, size: f32) -> Self {
        self.handle = Some((font, code_point, Pixels(size)));
        self
    }

    pub fn menu_height(mut self, height: Length) -> Self {
        self.menu_height = height;
        self
    }

    pub fn id(mut self, id: Option<String>) -> Self {
        self.id = id.map(Id::from);
        self
    }

    /// The border color while it has the keyboard focus (and the menu is closed).
    pub fn focus_border(mut self, color: Option<Color>) -> Self {
        self.focus_border = color;
        self
    }

    pub fn style(mut self, style: impl Fn(&Theme, Status) -> Style + 'a) -> Self {
        self.style = Box::new(style);
        self
    }

    pub fn menu_style(mut self, style: impl Fn(&Theme) -> menu::Style + 'a) -> Self {
        self.menu_style = Box::new(style);
        self
    }

    fn enabled(&self) -> bool {
        self.on_select.is_some()
    }

    fn selected_index(&self) -> Option<usize> {
        let selected = self.selected.as_ref()?;
        self.options.iter().position(|o| o == selected)
    }

    fn select(&self, index: usize, shell: &mut Shell<'_, Message>) {
        if let (Some(cb), Some(option)) = (&self.on_select, self.options.get(index))
            && self.selected.as_ref() != Some(option)
        {
            shell.publish(Message::Input(cb.clone(), option.clone()));
        }
    }

    fn open(&self, state: &mut State, shell: &mut Shell<'_, Message>) {
        state.is_open = true;
        state.hovered_option = self.selected_index();
        if let Some(cb) = &self.on_open {
            shell.publish(Message::Py(cb.clone()));
        }
    }

    fn close(&self, state: &mut State, shell: &mut Shell<'_, Message>) {
        state.is_open = false;
        if let Some(cb) = &self.on_close {
            shell.publish(Message::Py(cb.clone()));
        }
    }

    /// The option after `from` (or the first one) whose label starts with what was typed.
    fn search(&self, state: &mut State, typed: &str, from: Option<usize>) -> Option<usize> {
        let now = Instant::now();
        if state
            .typed_at
            .is_some_and(|at| now.duration_since(at) <= TYPE_AHEAD)
        {
            state.typed.push_str(typed);
        } else {
            state.typed = typed.to_string();
        }
        state.typed_at = Some(now);
        let needle = state.typed.to_lowercase();
        let total = self.options.len();
        // A new search starts after the current option; a longer one may stay on it.
        let start = match from {
            Some(i) if state.typed.chars().count() == 1 => i + 1,
            Some(i) => i,
            None => 0,
        };
        (0..total)
            .map(|k| (start + k) % total)
            .find(|&i| self.options[i].to_lowercase().starts_with(&needle))
    }

    /// The keys of a focused select. Returns whether the key was used.
    fn key(
        &self,
        state: &mut State,
        key: &Key,
        modifiers: keyboard::Modifiers,
        shell: &mut Shell<'_, Message>,
    ) -> bool {
        let total = self.options.len();
        if total == 0 {
            return false;
        }
        let last = total - 1;
        let step = |current: Option<usize>, delta: isize| -> usize {
            match current {
                Some(i) => (i as isize + delta).clamp(0, last as isize) as usize,
                None if delta < 0 => last,
                None => 0,
            }
        };
        if state.is_open {
            let hovered = state.hovered_option;
            let target = match key.as_ref() {
                Key::Named(Named::ArrowDown) if modifiers.alt() => {
                    return true;
                }
                Key::Named(Named::ArrowUp) if modifiers.alt() => {
                    self.close(state, shell);
                    return true;
                }
                Key::Named(Named::ArrowDown) => step(hovered, 1),
                Key::Named(Named::ArrowUp) => step(hovered, -1),
                Key::Named(Named::PageDown) => step(hovered, 8),
                Key::Named(Named::PageUp) => step(hovered, -8),
                Key::Named(Named::Home) => 0,
                Key::Named(Named::End) => last,
                Key::Named(Named::Enter | Named::Space) => {
                    state.is_open = false;
                    if let Some(i) = hovered {
                        self.select(i, shell);
                    }
                    return true;
                }
                Key::Named(Named::Escape | Named::F4) => {
                    self.close(state, shell);
                    return true;
                }
                Key::Named(Named::Tab) => {
                    // Closes and lets Tab move the focus on.
                    self.close(state, shell);
                    return false;
                }
                Key::Character(c)
                    if !(modifiers.control() || modifiers.alt() || modifiers.logo()) =>
                {
                    match self.search(state, c, hovered) {
                        Some(i) => i,
                        None => return true,
                    }
                }
                _ => return false,
            };
            state.hovered_option = Some(target);
            return true;
        }
        if modifiers.control() || modifiers.logo() {
            return false;
        }
        let current = self.selected_index();
        let target = match key.as_ref() {
            Key::Named(Named::ArrowDown | Named::ArrowUp) if modifiers.alt() => {
                self.open(state, shell);
                return true;
            }
            Key::Named(Named::Enter | Named::Space | Named::F4) if !modifiers.alt() => {
                self.open(state, shell);
                return true;
            }
            Key::Named(Named::ArrowDown | Named::ArrowRight) if !modifiers.alt() => {
                step(current, 1)
            }
            Key::Named(Named::ArrowUp | Named::ArrowLeft) if !modifiers.alt() => step(current, -1),
            Key::Named(Named::PageDown) => step(current, 8),
            Key::Named(Named::PageUp) => step(current, -8),
            Key::Named(Named::Home) => 0,
            Key::Named(Named::End) => last,
            Key::Character(c) if !modifiers.alt() => match self.search(state, c, current) {
                Some(i) => i,
                None => return true,
            },
            _ => return false,
        };
        self.select(target, shell);
        true
    }
}

#[derive(Default)]
struct State {
    menu: menu::State,
    keyboard_modifiers: keyboard::Modifiers,
    is_open: bool,
    focused: bool,
    hovered_option: Option<usize>,
    options: Vec<paragraph::Plain<Paragraph>>,
    placeholder: paragraph::Plain<Paragraph>,
    typed: String,
    typed_at: Option<Instant>,
}

impl Focusable for State {
    fn is_focused(&self) -> bool {
        self.focused
    }

    fn focus(&mut self) {
        self.focused = true;
    }

    fn unfocus(&mut self) {
        self.focused = false;
        self.is_open = false;
    }
}

impl Widget<Message, Theme, Renderer> for Select<'_> {
    fn tag(&self) -> tree::Tag {
        tree::Tag::of::<State>()
    }

    fn state(&self) -> tree::State {
        tree::State::new(State::default())
    }

    fn size(&self) -> Size<Length> {
        Size::new(self.width, Length::Shrink)
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        let state = tree.state.downcast_mut::<State>();
        let font = self.font.unwrap_or_else(|| renderer.default_font());
        let text_size = self.text_size.unwrap_or_else(|| renderer.default_size());
        let line_height = text::LineHeight::default();
        state
            .options
            .resize_with(self.options.len(), Default::default);
        let option_text = Text {
            content: "",
            bounds: Size::new(f32::INFINITY, line_height.to_absolute(text_size).into()),
            size: text_size,
            line_height,
            font,
            align_x: text::Alignment::Default,
            align_y: alignment::Vertical::Center,
            shaping: text::Shaping::default(),
            wrapping: text::Wrapping::default(),
            letter_spacing: iced::Em::ZERO,
        };
        for (option, paragraph) in self.options.iter().zip(state.options.iter_mut()) {
            let _ = paragraph.update(Text {
                content: option,
                ..option_text
            });
        }
        if let Some(placeholder) = &self.placeholder {
            let _ = state.placeholder.update(Text {
                content: placeholder,
                ..option_text
            });
        }
        let max_width = match self.width {
            Length::Shrink => {
                let labels = state
                    .options
                    .iter()
                    .fold(0.0, |w, p| f32::max(w, p.min_width()));
                labels.max(
                    self.placeholder
                        .as_ref()
                        .map_or(0.0, |_| state.placeholder.min_width()),
                )
            }
            _ => 0.0,
        };
        let intrinsic = Size::new(
            max_width + text_size.0 + self.padding.left,
            f32::from(line_height.to_absolute(text_size)),
        );
        let size = limits
            .width(self.width)
            .shrink(self.padding)
            .resolve(self.width, Length::Shrink, intrinsic)
            .expand(self.padding);
        layout::Node::new(size)
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        _renderer: &Renderer,
        operation: &mut dyn Operation,
    ) {
        if self.enabled() {
            let state = tree.state.downcast_mut::<State>();
            operation.focusable(self.id.as_ref(), layout.bounds(), state);
        }
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
        let state = tree.state.downcast_mut::<State>();
        let enabled = self.enabled();
        if !enabled && state.focused {
            state.unfocus();
        }
        match event {
            Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left))
            | Event::Touch(iced::touch::Event::FingerPressed { .. }) => {
                let over = cursor.is_over(layout.bounds());
                if state.is_open {
                    // The menu did not take the click: it was outside the menu or on the field.
                    self.close(state, shell);
                    state.focused = over;
                    shell.capture_event();
                } else if over && enabled {
                    state.focused = true;
                    self.open(state, shell);
                    shell.capture_event();
                } else if state.focused {
                    state.focused = false;
                    shell.request_redraw();
                }
            }
            Event::Mouse(mouse::Event::WheelScrolled {
                delta: mouse::ScrollDelta::Lines { y, .. },
                ..
            }) if state.keyboard_modifiers.command()
                && cursor.is_over(layout.bounds())
                && !state.is_open =>
            {
                let current = self.selected_index();
                let target = if *y < 0.0 {
                    Some(current.map_or(0, |i| i + 1))
                } else if *y > 0.0 {
                    Some(current.map_or(self.options.len().saturating_sub(1), |i| {
                        i.saturating_sub(1)
                    }))
                } else {
                    None
                };
                if let Some(i) = target.filter(|&i| i < self.options.len()) {
                    self.select(i, shell);
                }
                shell.capture_event();
            }
            Event::Keyboard(keyboard::Event::ModifiersChanged(modifiers)) => {
                state.keyboard_modifiers = *modifiers;
            }
            Event::Keyboard(keyboard::Event::KeyPressed { key, modifiers, .. })
                if state.focused && enabled =>
            {
                if self.key(state, key, *modifiers, shell) {
                    crate::app::claim_key(key);
                    shell.capture_event();
                    shell.request_redraw();
                }
            }
            Event::Window(window::Event::Unfocused) if state.is_open => self.close(state, shell),
            _ => {}
        }

        let is_hovered = cursor.is_over(layout.bounds());
        let status = if state.is_open {
            Status::Opened { is_hovered }
        } else if is_hovered {
            Status::Hovered
        } else {
            Status::Active
        };
        if let Event::Window(window::Event::RedrawRequested(_)) = event {
            self.last_status = Some(status);
        } else if self.last_status.is_some_and(|last| last != status) {
            shell.request_redraw();
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
        if cursor.is_over(layout.bounds()) && self.enabled() {
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
        _cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        let state = tree.state.downcast_ref::<State>();
        let font = self.font.unwrap_or_else(|| renderer.default_font());
        let bounds = layout.bounds();
        let mut style = (self.style)(theme, self.last_status.unwrap_or(Status::Active));
        if state.focused
            && !state.is_open
            && let Some(color) = self.focus_border
        {
            style.border.color = color;
            style.border.width = style.border.width.max(1.0);
        }
        renderer.fill_quad(
            renderer::Quad {
                bounds,
                border: style.border,
                ..renderer::Quad::default()
            },
            style.background,
        );
        if let Some((font, code_point, size)) = self.handle {
            let line_height = text::LineHeight::Relative(1.0);
            renderer.fill_text(
                Text {
                    content: code_point.to_string(),
                    size,
                    line_height,
                    font,
                    bounds: Size::new(bounds.width, f32::from(line_height.to_absolute(size))),
                    align_x: text::Alignment::Right,
                    align_y: alignment::Vertical::Center,
                    shaping: text::Shaping::Basic,
                    wrapping: text::Wrapping::default(),
                    letter_spacing: iced::Em::ZERO,
                },
                Point::new(
                    bounds.x + bounds.width - self.padding.right,
                    bounds.center_y(),
                ),
                style.handle_color,
                *viewport,
            );
        }
        let selected = self.selected.as_ref();
        if let Some(label) = selected.cloned().or_else(|| self.placeholder.clone()) {
            let text_size = self.text_size.unwrap_or_else(|| renderer.default_size());
            let line_height = text::LineHeight::default();
            let height = f32::from(line_height.to_absolute(text_size));
            // Drawn from its top: the region redrawn when the label changes starts at the text's
            // position, and from the middle (`Vertical::Center`) the top half of the old label stayed.
            renderer.fill_text(
                Text {
                    content: label,
                    size: text_size,
                    line_height,
                    font,
                    bounds: Size::new(bounds.width - self.padding.x(), height),
                    align_x: text::Alignment::Default,
                    align_y: alignment::Vertical::Top,
                    shaping: text::Shaping::default(),
                    wrapping: text::Wrapping::default(),
                    letter_spacing: iced::Em::ZERO,
                },
                Point::new(
                    bounds.x + self.padding.left,
                    bounds.center_y() - height / 2.0,
                ),
                if selected.is_some() {
                    style.text_color
                } else {
                    style.placeholder_color
                },
                *viewport,
            );
        }
    }

    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &Renderer,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<overlay::Element<'b, Message, Theme, Renderer>> {
        let state = tree.state.downcast_mut::<State>();
        if !state.is_open {
            return None;
        }
        let font = self.font.unwrap_or_else(|| renderer.default_font());
        let bounds = layout.bounds();
        let on_select = self.on_select.clone();
        let is_open = &mut state.is_open;
        let mut menu = Menu::new(
            &mut state.menu,
            &self.options,
            &mut state.hovered_option,
            move |option: String| {
                *is_open = false;
                match &on_select {
                    Some(cb) => Message::Input(cb.clone(), option),
                    None => Message::Noop,
                }
            },
            None,
            &self.menu_style,
        )
        .width(bounds.width)
        .padding(self.padding)
        .font(font)
        .text_shaping(text::Shaping::default());
        if let Some(size) = self.text_size {
            menu = menu.text_size(size);
        }
        Some(menu.overlay(
            layout.position() + translation,
            *viewport,
            bounds.height,
            self.menu_height,
        ))
    }
}

impl<'a> From<Select<'a>> for Element<'a, Message, Theme, Renderer> {
    fn from(select: Select<'a>) -> Self {
        Element::new(select)
    }
}
