//! Turns the Python-built `Widget` tree into iced elements.

use std::cell::RefCell;
use std::collections::HashMap;
use std::sync::Arc;

use elsa::FrozenMap;
use iced::advanced::text::Wrapping;
use iced::widget::text::LineHeight;
use iced::widget::{
    self, Space, button, checkbox, column, container, markdown, mouse_area, progress_bar, qr_code,
    row, rule, scrollable, slider, svg, text, text_editor, text_input, toggler, tooltip,
    vertical_slider,
};
use iced::{Background, Border, Color, Element, Font, Length, Pixels, Task, Theme};
use pyo3::prelude::*;

use crate::app::Message;
use crate::editor::{self, EditorState, Outcome};
use crate::extra::{self, CanvasCache};
use crate::sticky::{Split, SplitStyle};
use crate::style::ICONS;
use crate::widget::{Kind, SvgSource, Widget};

/// Everything that must outlive a single `view()` call: editor buffers, decoded images,
/// parsed markdown, canvas geometry... Keyed by id or by content hash.
#[derive(Default)]
pub struct Caches {
    editors: FrozenMap<String, Box<EditorState>>,
    pending_cursors: RefCell<HashMap<String, text_editor::Position>>,
    images: RefCell<HashMap<u64, extra::Decoded>>,
    image_masks: extra::MaskCache,
    svgs: RefCell<HashMap<u64, svg::Handle>>,
    canvases: FrozenMap<String, Box<CanvasCache>>,
    markdown: FrozenMap<u64, Vec<markdown::Item>>,
    qr: FrozenMap<u64, Box<qr_code::Data>>,
}

impl Caches {
    pub fn set_editor_text(&mut self, id: &str, text: &str) {
        match self.editors.as_mut().get_mut(id) {
            Some(editor) => editor.reset(text),
            None => {
                self.editors
                    .insert(id.to_owned(), Box::new(EditorState::new(text)));
            }
        }
    }

    pub fn set_editor_cursor(
        &mut self,
        id: &str,
        position: text_editor::Position,
    ) -> Task<Message> {
        match self.editors.as_mut().get_mut(id) {
            Some(editor) => editor.move_to(id, position),
            None => {
                self.pending_cursors
                    .borrow_mut()
                    .insert(id.to_owned(), position);
                Task::none()
            }
        }
    }

    pub fn perform_editor(&mut self, id: &str, action: text_editor::Action) -> Option<Outcome> {
        let editor = self.editors.as_mut().get_mut(id)?;
        Some(editor.perform(id, action))
    }

    pub fn indent_editor(
        &mut self,
        id: &str,
        key: crate::editor::IndentKey,
        size: usize,
    ) -> Option<Outcome> {
        let editor = self.editors.as_mut().get_mut(id)?;
        Some(editor.indent(id, key, size))
    }

    pub fn page_editor(&mut self, id: &str, down: bool, select: bool) -> Option<Outcome> {
        let editor = self.editors.as_mut().get_mut(id)?;
        Some(editor.page(id, down, select))
    }

    /// Drops content-keyed caches that grew large (they are rebuilt on demand).
    pub fn prune(&mut self) {
        if self.markdown.as_mut().len() > 32 {
            self.markdown.as_mut().clear();
        }
        if self.qr.as_mut().len() > 64 {
            self.qr.as_mut().clear();
        }
        if self.images.get_mut().len() > 512 {
            self.images.get_mut().clear();
        }
        if self.image_masks.get_mut().len() > 64 {
            self.image_masks.get_mut().clear();
        }
        if self.svgs.get_mut().len() > 1024 {
            self.svgs.get_mut().clear();
        }
        if self.canvases.as_mut().len() > 256 {
            self.canvases.as_mut().clear();
        }
    }

    fn editor(&self, id: &str, text: &str) -> &EditorState {
        if let Some(state) = self.editors.get(id) {
            return state;
        }
        let mut state = EditorState::new(text);
        if let Some(position) = self.pending_cursors.borrow_mut().remove(id) {
            state.content.move_to(text_editor::Cursor {
                position,
                selection: None,
            });
        }
        self.editors.insert(id.to_owned(), Box::new(state))
    }

    fn svg(&self, source: &SvgSource) -> svg::Handle {
        let key = match source {
            SvgSource::Path(p) => crate::editor::hash_of(p.as_bytes()),
            SvgSource::Bytes(b) => crate::editor::hash_of(b) ^ 0x51,
        };
        if let Some(h) = self.svgs.borrow().get(&key) {
            return h.clone();
        }
        let handle = match source {
            SvgSource::Path(p) => svg::Handle::from_path(p),
            SvgSource::Bytes(b) => svg::Handle::from_memory(b.clone()),
        };
        self.svgs.borrow_mut().insert(key, handle.clone());
        handle
    }
}

#[derive(Clone, Copy)]
pub struct Ctx<'a> {
    caches: &'a Caches,
}

impl<'a> Ctx<'a> {
    pub fn new(caches: &'a Caches) -> Self {
        Self { caches }
    }
}

fn with_alpha(color: Color, a: f32) -> Color {
    Color {
        a: color.a * a,
        ..color
    }
}

pub fn build<'a>(py: Python<'_>, node: &Py<Widget>, ctx: Ctx<'a>) -> Element<'a, Message> {
    let node = node.bind(py).get();

    match &node.kind {
        Kind::Text(t) => {
            let mut w = text(t.content.clone());
            if let Some(size) = t.size {
                w = w.size(size);
            }
            if let Some(color) = t.color {
                w = w.color(color);
            }
            if let Some(font) = t.font {
                w = w.font(font);
            }
            if let Some(lh) = t.line_height {
                w = w.line_height(LineHeight::Relative(lh));
            }
            if let Some(a) = t.align_x {
                w = w.align_x(a);
            }
            if let Some(a) = t.align_y {
                w = w.align_y(a);
            }
            if let Some(width) = t.width {
                w = w.width(width);
            }
            if let Some(height) = t.height {
                w = w.height(height);
            }
            if !t.wrap {
                w = w.wrapping(Wrapping::None);
            }
            w.into()
        }
        Kind::Column {
            children,
            spacing,
            layout,
            align,
            clip,
        } => {
            let mut c = column(children.iter().map(|c| build(py, c, ctx)))
                .spacing(*spacing)
                .clip(*clip);
            if let Some(w) = layout.width {
                c = c.width(w);
            }
            if let Some(h) = layout.height {
                c = c.height(h);
            }
            if let Some(p) = layout.padding {
                c = c.padding(p);
            }
            if let Some(m) = layout.max_width {
                c = c.max_width(m);
            }
            if let Some(a) = align {
                c = c.align_x(*a);
            }
            c.into()
        }
        Kind::Row {
            children,
            spacing,
            layout,
            align,
            clip,
            wrap,
        } => {
            let mut r = row(children.iter().map(|c| build(py, c, ctx)))
                .spacing(*spacing)
                .clip(*clip);
            if let Some(w) = layout.width {
                r = r.width(w);
            }
            if let Some(h) = layout.height {
                r = r.height(h);
            }
            if let Some(p) = layout.padding {
                r = r.padding(p);
            }
            if let Some(a) = align {
                r = r.align_y(*a);
            }
            match wrap {
                Some(line_spacing) => r.wrap().vertical_spacing(*line_spacing).into(),
                None => r.into(),
            }
        }
        Kind::Container {
            child,
            layout,
            align_x,
            align_y,
            style,
            clip,
        } => {
            let mut c = container(build(py, child, ctx)).clip(*clip);
            if let Some(w) = layout.width {
                c = c.width(w);
            }
            if let Some(h) = layout.height {
                c = c.height(h);
            }
            if let Some(p) = layout.padding {
                c = c.padding(p);
            }
            if let Some(m) = layout.max_width {
                c = c.max_width(m);
            }
            if let Some(m) = layout.max_height {
                c = c.max_height(m);
            }
            if let Some(a) = align_x {
                c = c.align_x(*a);
            }
            if let Some(a) = align_y {
                c = c.align_y(*a);
            }
            if !style.is_empty() {
                let style = style.container();
                c = c.style(move |_| style);
            }
            c.into()
        }
        Kind::Button {
            child,
            on_press,
            layout,
            style,
            clip,
        } => {
            let mut b = button(build(py, child, ctx))
                .on_press_maybe(on_press.clone().map(Message::Py))
                .clip(*clip);
            if let Some(w) = layout.width {
                b = b.width(w);
            }
            if let Some(h) = layout.height {
                b = b.height(h);
            }
            if let Some(p) = layout.padding {
                b = b.padding(p);
            }
            if let Some(s) = style.clone() {
                b = b.style(move |theme: &Theme, status| {
                    let text_color = s
                        .base
                        .text_color
                        .unwrap_or(theme.extended_palette().background.base.text);
                    let mut out = button::Style {
                        background: s.base.background.map(Background::Color),
                        text_color,
                        border: s.base.border(),
                        shadow: s.base.shadow.unwrap_or_default(),
                        snap: true,
                    };
                    match status {
                        button::Status::Active => {}
                        button::Status::Hovered | button::Status::Pressed => {
                            let pressed = matches!(status, button::Status::Pressed);
                            let bg = if pressed {
                                s.pressed_background.or(s.hover_background)
                            } else {
                                s.hover_background
                            };
                            if let Some(bg) = bg.or(s.base.background) {
                                out.background = Some(Background::Color(bg));
                            }
                            if let Some(c) = s.hover_text_color {
                                out.text_color = c;
                            }
                            if let Some(c) = s.hover_border_color {
                                out.border.color = c;
                            }
                        }
                        button::Status::Disabled => {
                            out.text_color =
                                s.disabled_text_color.unwrap_or(with_alpha(text_color, 0.5));
                            out.background = out.background.map(|bg| bg.scale_alpha(0.5));
                        }
                    }
                    out
                });
            }
            b.into()
        }
        Kind::TextInput {
            value,
            placeholder,
            on_input,
            on_submit,
            id,
            size,
            font,
            layout,
            secure,
            icon,
            style,
            align_x,
        } => {
            let mut t = text_input(placeholder, value).secure(*secure);
            if let Some(a) = align_x {
                t = t.align_x(*a);
            }
            if let Some(cb) = on_input.clone() {
                t = t.on_input(move |s| Message::Input(cb.clone(), s));
            }
            if let Some(m) = on_submit.clone() {
                t = t.on_submit(Message::Py(m));
            }
            if let Some(id) = id {
                t = t.id(id.clone());
            }
            if let Some(s) = size {
                t = t.size(*s);
            }
            if let Some(f) = font {
                t = t.font(*f);
            }
            if let Some(p) = layout.padding {
                t = t.padding(p);
            }
            if let Some(w) = layout.width {
                t = t.width(w);
            }
            if let Some((code_point, size)) = icon {
                t = t.icon(text_input::Icon {
                    font: Font::with_name(ICONS),
                    code_point: *code_point,
                    size: Some(Pixels(*size)),
                    spacing: 8.0,
                    side: text_input::Side::Left,
                });
            }
            let s = style.clone();
            t = t.style(move |theme: &Theme, status| {
                let mut out = text_input::default(theme, status);
                if let Some(bg) = s.background {
                    out.background = Background::Color(bg);
                }
                if let Some(c) = s.border_color {
                    out.border.color = c;
                }
                if let Some(w) = s.border_width {
                    out.border.width = w;
                }
                if let Some(r) = s.radius {
                    out.border.radius = r;
                }
                match status {
                    text_input::Status::Hovered => {
                        if let Some(c) = s.hover_border_color {
                            out.border.color = c;
                        }
                    }
                    text_input::Status::Focused { .. } => {
                        if let Some(c) = s.focus_border_color {
                            out.border.color = c;
                        }
                    }
                    _ => {}
                }
                if let Some(c) = s.text_color {
                    out.value = c;
                }
                if let Some(c) = s.placeholder_color {
                    out.placeholder = c;
                }
                if let Some(c) = s.selection_color {
                    out.selection = c;
                }
                if let Some(c) = s.icon_color {
                    out.icon = c;
                }
                out
            });
            t.into()
        }
        Kind::Scrollable {
            child,
            direction,
            layout,
            id,
            anchor_bottom,
            style,
            on_scroll,
        } => {
            let bar = scrollable::Scrollbar::new()
                .width(style.width)
                .scroller_width(style.scroller_width)
                .margin(style.margin);
            let dir = match direction.as_str() {
                "horizontal" => scrollable::Direction::Horizontal(bar),
                "both" => scrollable::Direction::Both {
                    vertical: bar,
                    horizontal: bar,
                },
                _ => scrollable::Direction::Vertical(bar),
            };
            let content: Element<'a, Message> = match layout.padding {
                Some(p) => container(build(py, child, ctx)).padding(p).into(),
                None => build(py, child, ctx),
            };
            let mut s = widget::Scrollable::with_direction(content, dir);
            if let Some(w) = layout.width {
                s = s.width(w);
            }
            if let Some(h) = layout.height {
                s = s.height(h);
            }
            if let Some(id) = id {
                s = s.id(id.clone());
            }
            if let Some(cb) = on_scroll.clone() {
                s = s.on_scroll(move |viewport| Message::Scrolled(cb.clone(), viewport));
            }
            if *anchor_bottom {
                s = s.anchor_bottom();
            }
            let st = style.clone();
            s = s.style(move |theme: &Theme, status| {
                let mut out = scrollable::default(theme, status);
                let hovered = matches!(
                    status,
                    scrollable::Status::Hovered {
                        is_vertical_scrollbar_hovered: true,
                        ..
                    } | scrollable::Status::Hovered {
                        is_horizontal_scrollbar_hovered: true,
                        ..
                    } | scrollable::Status::Dragged { .. }
                );
                for rail in [&mut out.vertical_rail, &mut out.horizontal_rail] {
                    if let Some(c) = st.rail {
                        rail.background = Some(Background::Color(c));
                    }
                    let scroller = if hovered {
                        st.scroller_hover.or(st.scroller)
                    } else {
                        st.scroller
                    };
                    if let Some(c) = scroller {
                        rail.scroller.background = Background::Color(c);
                    }
                    rail.border = Border::default();
                    rail.scroller.border.radius = (st.scroller_width / 2.0).into();
                }
                out
            });
            s.into()
        }
        Kind::Space { width, height } => Space::new().width(*width).height(*height).into(),
        Kind::Rule {
            horizontal,
            thickness,
            color,
        } => {
            let color = *color;
            let style = move |theme: &Theme| rule::Style {
                color: color.unwrap_or(theme.extended_palette().background.strong.color),
                radius: 0.0.into(),
                fill_mode: rule::FillMode::Full,
                snap: true,
            };
            if *horizontal {
                rule::horizontal(*thickness).style(style).into()
            } else {
                rule::vertical(*thickness).style(style).into()
            }
        }
        Kind::MouseArea {
            child,
            on_press,
            on_release,
            on_right_press,
            on_double_click,
            on_enter,
            on_exit,
            on_move,
            on_scroll,
            on_middle_press,
            cursor,
        } => {
            let mut m = mouse_area(build(py, child, ctx));
            if let Some(cb) = on_move.clone() {
                m = m.on_move(move |p| Message::Point(cb.clone(), p.x, p.y));
            }
            if let Some(cb) = on_scroll.clone() {
                m = m.on_scroll(move |delta| {
                    let (x, y) = match delta {
                        iced::mouse::ScrollDelta::Lines { x, y } => (x, y),
                        iced::mouse::ScrollDelta::Pixels { x, y } => (x / 60.0, y / 60.0),
                    };
                    Message::Point(cb.clone(), x, y)
                });
            }
            if let Some(msg) = on_middle_press.clone() {
                m = m.on_middle_press(Message::Py(msg));
            }
            if let Some(msg) = on_press.clone() {
                m = m.on_press(Message::Py(msg));
            }
            if let Some(msg) = on_release.clone() {
                m = m.on_release(Message::Py(msg));
            }
            if let Some(msg) = on_right_press.clone() {
                m = m.on_right_press(Message::Py(msg));
            }
            if let Some(msg) = on_double_click.clone() {
                m = m.on_double_click(Message::Py(msg));
            }
            if let Some(msg) = on_enter.clone() {
                m = m.on_enter(Message::Py(msg));
            }
            if let Some(msg) = on_exit.clone() {
                m = m.on_exit(Message::Py(msg));
            }
            if let Some(c) = cursor {
                m = m.interaction(*c);
            }
            m.into()
        }
        Kind::Stack { children, layout } => {
            let mut s = widget::Stack::with_children(children.iter().map(|c| build(py, c, ctx)));
            if let Some(w) = layout.width {
                s = s.width(w);
            }
            if let Some(h) = layout.height {
                s = s.height(h);
            }
            s.into()
        }
        Kind::Opaque { child } => widget::opaque(build(py, child, ctx)),
        Kind::Events {
            child,
            handlers,
            cursor,
        } => crate::events::EventArea::new(build(py, child, ctx), handlers.clone(), *cursor).into(),
        Kind::Hover { base, top } => widget::hover(build(py, base, ctx), build(py, top, ctx)),
        Kind::Tooltip {
            child,
            tip,
            position,
            gap,
            style,
        } => {
            let position = match position.as_str() {
                "top" => tooltip::Position::Top,
                "left" => tooltip::Position::Left,
                "right" => tooltip::Position::Right,
                "cursor" => tooltip::Position::FollowCursor,
                _ => tooltip::Position::Bottom,
            };
            let style = style.container();
            tooltip(
                build(py, child, ctx),
                container(build(py, tip, ctx)).style(move |_| style),
                position,
            )
            .gap(*gap)
            .into()
        }
        Kind::Checkbox {
            checked,
            label,
            on_toggle,
            size,
            text_size,
            style,
        } => {
            let mut c = checkbox(*checked);
            if let Some(label) = label {
                c = c.label(label.clone());
            }
            if let Some(cb) = on_toggle.clone() {
                c = c.on_toggle(move |b| Message::Toggle(cb.clone(), b));
            }
            if let Some(s) = size {
                c = c.size(*s);
            }
            if let Some(s) = text_size {
                c = c.text_size(*s);
            }
            let st = style.clone();
            c.style(move |theme: &Theme, status| {
                let mut out = checkbox::primary(theme, status);
                let is_checked = match status {
                    checkbox::Status::Active { is_checked }
                    | checkbox::Status::Hovered { is_checked }
                    | checkbox::Status::Disabled { is_checked } => is_checked,
                };
                if is_checked {
                    if let Some(a) = st.accent {
                        out.background = Background::Color(a);
                        out.border.color = a;
                    }
                } else {
                    if let Some(bg) = st.background {
                        out.background = Background::Color(bg);
                    }
                    if let Some(b) = st.border_color {
                        out.border.color = b;
                    }
                }
                if let Some(fg) = st.foreground {
                    out.icon_color = fg;
                }
                if st.text_color.is_some() {
                    out.text_color = st.text_color;
                }
                out
            })
            .into()
        }
        Kind::Toggler {
            checked,
            label,
            on_toggle,
            size,
            text_size,
            style,
        } => {
            let mut t = toggler(*checked);
            if let Some(label) = label {
                t = t.label(label.clone());
            }
            if let Some(cb) = on_toggle.clone() {
                t = t.on_toggle(move |b| Message::Toggle(cb.clone(), b));
            }
            if let Some(s) = size {
                t = t.size(*s);
            }
            if let Some(s) = text_size {
                t = t.text_size(*s);
            }
            let st = style.clone();
            t.style(move |theme: &Theme, status| {
                let mut out = toggler::default(theme, status);
                let on = match status {
                    toggler::Status::Active { is_toggled }
                    | toggler::Status::Hovered { is_toggled }
                    | toggler::Status::Disabled { is_toggled } => is_toggled,
                };
                if on {
                    if let Some(a) = st.accent {
                        out.background = Background::Color(a);
                    }
                } else if let Some(bg) = st.background {
                    out.background = Background::Color(bg);
                }
                if let Some(b) = st.border_color {
                    out.background_border_color = b;
                    out.background_border_width = 1.0;
                }
                if let Some(fg) = st.foreground {
                    out.foreground = Background::Color(fg);
                }
                if st.text_color.is_some() {
                    out.text_color = st.text_color;
                }
                out
            })
            .into()
        }
        Kind::Slider {
            min,
            max,
            value,
            step,
            on_change,
            on_release,
            width,
            height,
            vertical,
            style,
        } => {
            let cb = on_change.clone();
            let on_change = move |v| match &cb {
                Some(cb) => Message::Slide(cb.clone(), v),
                None => Message::Noop,
            };
            let st = style.clone();
            let style = move |theme: &Theme, status| {
                let mut out = slider::default(theme, status);
                if let Some(a) = st.accent {
                    out.rail.backgrounds.0 = Background::Color(a);
                    out.handle.background = Background::Color(a);
                }
                if let Some(bg) = st.background {
                    out.rail.backgrounds.1 = Background::Color(bg);
                }
                if let Some(fg) = st.foreground {
                    out.handle.background = Background::Color(fg);
                }
                if let Some(b) = st.border_color {
                    out.handle.border_color = b;
                    out.handle.border_width = 1.0;
                }
                out
            };
            if *vertical {
                let mut s = vertical_slider(*min..=*max, *value, on_change)
                    .step(*step)
                    .style(style);
                if let Some(m) = on_release.clone() {
                    s = s.on_release(Message::Py(m));
                }
                if let Some(Length::Fixed(w)) = width {
                    s = s.width(*w);
                }
                if let Some(h) = height {
                    s = s.height(*h);
                }
                s.into()
            } else {
                let mut s = slider(*min..=*max, *value, on_change)
                    .step(*step)
                    .style(style);
                if let Some(m) = on_release.clone() {
                    s = s.on_release(Message::Py(m));
                }
                if let Some(w) = width {
                    s = s.width(*w);
                }
                if let Some(Length::Fixed(h)) = height {
                    s = s.height(*h);
                }
                s.into()
            }
        }
        Kind::ProgressBar {
            min,
            max,
            value,
            width,
            height,
            style,
            radius,
        } => {
            let mut p = progress_bar(*min..=*max, *value);
            if let Some(w) = width {
                p = p.length(*w);
            }
            p = p.girth(height.unwrap_or(Length::Fixed(4.0)));
            let st = style.clone();
            let radius = *radius;
            p.style(move |theme: &Theme| {
                let mut out = progress_bar::primary(theme);
                if let Some(a) = st.accent {
                    out.bar = Background::Color(a);
                }
                if let Some(bg) = st.background {
                    out.background = Background::Color(bg);
                }
                out.border = Border {
                    radius: radius.into(),
                    ..Border::default()
                };
                out
            })
            .into()
        }
        Kind::Editor(props) => editor::view(ctx.caches.editor(&props.id, &props.text), props),
        Kind::Svg {
            source,
            width,
            height,
            color,
            fit,
            opacity,
            rotation,
        } => {
            let mut s = svg(ctx.caches.svg(source))
                .opacity(*opacity)
                .rotation(iced::Radians(rotation.to_radians()));
            if let Some(w) = width {
                s = s.width(*w);
            }
            if let Some(h) = height {
                s = s.height(*h);
            }
            if let Some(f) = fit {
                s = s.content_fit(*f);
            }
            if let Some(c) = *color {
                s = s.style(move |_, _| svg::Style { color: Some(c) });
            }
            s.into()
        }
        Kind::Image(props) => extra::render_image(
            props,
            props.source.decode(&ctx.caches.images),
            &ctx.caches.image_masks,
        ),
        Kind::Canvas(props) => {
            let cache = props
                .cache_key
                .as_ref()
                .map(|(id, _)| match ctx.caches.canvases.get(id) {
                    Some(cache) => cache,
                    None => ctx.caches.canvases.insert(id.clone(), Box::default()),
                });
            extra::render_canvas(Arc::clone(props), cache)
        }
        Kind::RichText(props) => extra::render_rich(props),
        Kind::Markdown(props) => {
            let items = match ctx.caches.markdown.get(&props.key) {
                Some(items) => items,
                None => ctx
                    .caches
                    .markdown
                    .insert(props.key, extra::parse_markdown(&props.source)),
            };
            extra::render_markdown(props, items)
        }
        Kind::QrCode(props) => {
            let data = match ctx.caches.qr.get(&props.key) {
                Some(data) => Some(data),
                None => qr_code::Data::new(&props.data)
                    .ok()
                    .map(|data| ctx.caches.qr.insert(props.key, Box::new(data))),
            };
            match data {
                Some(data) => extra::render_qr(props, data),
                None => text("QR data too long").into(),
            }
        }
        Kind::PickList(props) => extra::render_pick_list(props),
        Kind::Radio(props) => extra::render_radio(props),
        Kind::Split(props) => {
            let on_resize = props.on_resize.clone().map(|cb| {
                Box::new(move |ratio: f32| Message::Slide(cb.clone(), ratio))
                    as Box<dyn Fn(f32) -> Message + 'a>
            });
            let color = props.color.unwrap_or(Color::from_rgb8(0x46, 0x4b, 0x57));
            Split::new(
                build(py, &props.first, ctx),
                build(py, &props.second, ctx),
                props.vertical,
                props.ratio,
                props.min,
                SplitStyle {
                    color,
                    hover_color: props.hover_color.unwrap_or(color),
                    line: props.thickness,
                    handle: props.handle,
                },
                on_resize,
                (props.width, props.height),
            )
            .into()
        }
        Kind::Pin {
            child,
            x,
            y,
            width,
            height,
        } => widget::pin(build(py, child, ctx))
            .x(*x)
            .y(*y)
            .width(*width)
            .height(*height)
            .into(),
        Kind::Grid {
            children,
            columns,
            max_width,
            spacing,
            height,
            aspect_ratio,
            width,
        } => {
            let mut g = widget::grid(children.iter().map(|c| build(py, c, ctx))).spacing(*spacing);
            if let Some(n) = columns {
                g = g.columns(*n);
            }
            if let Some(m) = max_width {
                g = g.fluid(*m);
            }
            if let Some(w) = width {
                g = g.width(*w);
            }
            if let Some(r) = aspect_ratio {
                g = g.height(widget::grid::aspect_ratio(*r, 1.0));
            } else if let Some(h) = height {
                g = g.height(*h);
            }
            g.into()
        }
        Kind::Responsive(callback) => {
            let callback = callback.clone();
            widget::responsive(move |size| {
                Python::attach(|py| {
                    let result = callback
                        .0
                        .bind(py)
                        .call1((size.width, size.height))
                        .and_then(|w| crate::widget::child(&w));
                    match result {
                        Ok(node) => build(py, &node, ctx),
                        Err(err) => {
                            err.print(py);
                            text(crate::app::format_error(py, &err))
                                .color(Color::from_rgb8(0xd0, 0x72, 0x77))
                                .into()
                        }
                    }
                })
            })
            .into()
        }
    }
}
