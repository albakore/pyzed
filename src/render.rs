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
    /// Fold commands for editors not rendered yet (applied when they are created).
    pending_folds: RefCell<HashMap<String, Vec<crate::editor::FoldOp>>>,
    /// Selections for editors not rendered yet.
    pending_selections: RefCell<HashMap<String, Vec<crate::editor::TextRange>>>,
    images: RefCell<HashMap<u64, extra::Decoded>>,
    image_masks: extra::MaskCache,
    svgs: RefCell<HashMap<u64, svg::Handle>>,
    canvases: FrozenMap<String, Box<CanvasCache>>,
    markdown: FrozenMap<u64, Vec<markdown::Item>>,
    qr: FrozenMap<u64, Box<qr_code::Data>>,
    /// `presence(...)` nodes: the key shown and the content leaving.
    presence: RefCell<HashMap<String, crate::animation::PresenceEntry>>,
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

    pub fn key_editor(
        &mut self,
        id: &str,
        key: crate::editor::EditKey,
        size: Option<usize>,
        pairs: bool,
    ) -> Option<Outcome> {
        let editor = self.editors.as_mut().get_mut(id)?;
        Some(editor.key(id, key, size, pairs))
    }

    pub fn fold_editor_command(&mut self, id: &str, op: crate::editor::FoldOp) -> Task<Message> {
        match self.fold_editor(id, op) {
            Some(outcome) => outcome.scroll,
            None => {
                self.pending_folds
                    .borrow_mut()
                    .entry(id.to_owned())
                    .or_default()
                    .push(op);
                Task::none()
            }
        }
    }

    pub fn fold_editor(&mut self, id: &str, op: crate::editor::FoldOp) -> Option<Outcome> {
        let editor = self.editors.as_mut().get_mut(id)?;
        Some(editor.fold_op(id, op))
    }

    pub fn run_editor(
        &mut self,
        id: &str,
        action: crate::editor::EditorAction,
        ctx: &crate::editor::ActionContext,
    ) -> Option<Outcome> {
        let editor = self.editors.as_mut().get_mut(id)?;
        Some(editor.run(id, action, ctx))
    }

    /// The action context of the editor's last render (`None` if it was never rendered).
    pub fn editor_context(&self, id: &str) -> Option<std::sync::Arc<crate::editor::ActionContext>> {
        self.editors.get(id)?.context.borrow().clone()
    }

    pub fn select_editor_ranges(
        &mut self,
        id: &str,
        ranges: &[crate::editor::TextRange],
    ) -> Task<Message> {
        match self.editors.as_mut().get_mut(id) {
            Some(editor) => editor.select_ranges(id, ranges),
            None => {
                self.pending_selections
                    .borrow_mut()
                    .insert(id.to_owned(), ranges.to_vec());
                Task::none()
            }
        }
    }

    pub fn replace_editor_ranges(
        &mut self,
        id: &str,
        edits: &[crate::editor::RangeEdit],
    ) -> Option<Outcome> {
        let editor = self.editors.as_mut().get_mut(id)?;
        Some(editor.replace_ranges(id, edits))
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
        for op in self
            .pending_folds
            .borrow_mut()
            .remove(id)
            .unwrap_or_default()
        {
            let _ = state.fold_op(id, op);
        }
        if let Some(ranges) = self.pending_selections.borrow_mut().remove(id) {
            let _ = state.select_ranges(id, &ranges);
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
    /// Text properties set by the closest `style()` ancestors.
    text: crate::styled::TextStyle,
    /// Text properties that only fill in what texts leave unset (`App.style`).
    text_defaults: crate::styled::TextStyle,
    /// The next box takes the animated padding of an `Animated` parent (`PadSlot`).
    pad_slot: bool,
    /// Texts follow the animated font size of an `Animated` ancestor (`SizedText`).
    font_slot: bool,
}

impl<'a> Ctx<'a> {
    pub fn new(caches: &'a Caches) -> Self {
        Self {
            caches,
            text: Default::default(),
            text_defaults: Default::default(),
            pad_slot: false,
            font_slot: false,
        }
    }
}

fn with_alpha(color: Color, a: f32) -> Color {
    Color {
        a: color.a * a,
        ..color
    }
}

/// Containers and buttons, with the box properties of a `style()` call (`over`) applied to
/// the widget itself instead of a wrapper, so `ui.button(...).style(radius=0)` squares it.
fn build_box<'a>(
    py: Python<'_>,
    node_ref: &Py<Widget>,
    ctx: Ctx<'a>,
    over: Option<&crate::styled::StyleProps>,
) -> Element<'a, Message> {
    let node = node_ref.bind(py).get();
    let pad_slot = ctx.pad_slot;
    let ctx = Ctx {
        pad_slot: false,
        ..ctx
    };
    // The box's content, inside a `PadSlot` when an `Animated` parent animates the padding.
    let content = |child: &Py<Widget>, padding: Option<iced::Padding>| -> Element<'a, Message> {
        let element = build(py, child, ctx);
        if pad_slot {
            crate::animation::PadSlot::new(element, padding.unwrap_or(iced::Padding::ZERO)).into()
        } else {
            element
        }
    };
    match &node.kind {
        Kind::Container {
            child,
            layout,
            align_x,
            align_y,
            style,
            clip,
        } => {
            let layout = &crate::styled::layout(layout, over);
            let mut c = container(content(child, layout.padding))
                .clip(*clip || over.is_some_and(|o| o.clip));
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
            if let Some(a) = over.and_then(|o| o.align_x).or(*align_x) {
                c = c.align_x(a);
            }
            if let Some(a) = over.and_then(|o| o.align_y).or(*align_y) {
                c = c.align_y(a);
            }
            let style = crate::styled::boxed(style, over).container();
            c.style(move |theme| crate::animation::container_style(style, theme))
                .into()
        }
        Kind::Button {
            child,
            on_press,
            layout,
            style,
            clip,
        } => {
            let layout = &crate::styled::layout(layout, over);
            let mut b = button(content(
                child,
                layout.padding.or(Some(button::DEFAULT_PADDING)),
            ))
            .on_press_maybe(on_press.clone().map(Message::Py))
            .clip(*clip || over.is_some_and(|o| o.clip));
            if let Some(w) = layout.width {
                b = b.width(w);
            }
            if let Some(h) = layout.height {
                b = b.height(h);
            }
            if let Some(p) = layout.padding {
                b = b.padding(p);
            }
            let style = match (style.clone(), over) {
                (s, Some(o)) => Some(crate::styled::button(s.unwrap_or_default(), o)),
                (s, None) => s,
            };
            match style {
                None => {
                    b = b.style(|theme: &Theme, status| {
                        crate::animation::button_style(button::primary(theme, status), theme)
                    });
                }
                Some(s) => {
                    b = b.style(move |theme: &Theme, status| {
                        let text_color = s
                            .base
                            .text_color
                            .unwrap_or(theme.extended_palette().background.base.text);
                        let mut out = button::Style {
                            background: s
                                .base
                                .gradient
                                .map(Background::Gradient)
                                .or(s.base.background.map(Background::Color)),
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
                                if let Some(bg) = bg {
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
                        crate::animation::button_style(out, theme)
                    })
                }
            }
            b.into()
        }
        _ => build(py, node_ref, ctx),
    }
}

/// Whether the widget's first drawn style is its own box (container or button), which
/// takes the box paints of an `Animated` around it.
fn draws_box(py: Python<'_>, node: &Py<Widget>) -> bool {
    match &node.bind(py).get().kind {
        Kind::Container { .. } | Kind::Button { .. } | Kind::Styled(_) => true,
        Kind::Events { child, .. } | Kind::Animated { child, .. } => draws_box(py, child),
        _ => false,
    }
}

fn build_presence<'a>(
    py: Python<'_>,
    props: &crate::animation::PresenceProps,
    ctx: Ctx<'a>,
) -> Element<'a, Message> {
    use crate::animation::{Animated, Presence, PresenceEntry, Spec};
    let salted = |spec: &Spec, salt: &str| {
        Arc::new(Spec {
            anims: spec.anims.iter().cloned().map(|a| a.salted(salt)).collect(),
            ..spec.clone()
        })
    };
    let now = std::time::Instant::now();
    // Take what we need, then release the map: the children may hold presences too.
    let leaving = {
        let mut map = ctx.caches.presence.borrow_mut();
        if map.len() > 256 {
            map.clear();
        }
        let entry = map
            .entry(props.id.clone())
            .or_insert_with(|| PresenceEntry {
                key: props.key.clone(),
                current: props.child.clone_ref(py),
                exit: props.exit.clone(),
                leaving: None,
            });
        if entry.key != props.key {
            let old_key = std::mem::replace(&mut entry.key, props.key.clone());
            let old = std::mem::replace(&mut entry.current, props.child.clone_ref(py));
            entry.leaving = Some((old, old_key, entry.exit.clone(), now));
        } else {
            entry.current = props.child.clone_ref(py);
        }
        entry.exit = props.exit.clone();
        let over = |spec: &Spec, start: std::time::Instant| {
            crate::animation::reduced_motion()
                || now.saturating_duration_since(start).as_secs_f32() > spec.longest() + 0.05
        };
        if entry
            .leaving
            .as_ref()
            .is_some_and(|(_, _, spec, start)| over(spec, *start))
        {
            entry.leaving = None;
        }
        entry
            .leaving
            .as_ref()
            .map(|(w, key, spec, _)| (w.clone_ref(py), key.clone(), spec.clone()))
    };
    let leaving: Element<'a, Message> = match leaving {
        Some((widget, key, spec)) => Animated::new(
            build(py, &widget, ctx),
            salted(&spec, &format!("exit:{key}")),
        )
        .into(),
        None => Space::new().into(),
    };
    let current = Animated::new(
        build(py, &props.child, ctx),
        salted(&props.enter, &format!("enter:{}", props.key)),
    );
    Presence::new(leaving, current).into()
}

pub fn build<'a>(py: Python<'_>, node_ref: &Py<Widget>, ctx: Ctx<'a>) -> Element<'a, Message> {
    let node = node_ref.bind(py).get();

    match &node.kind {
        Kind::Text(t) => {
            let font = ctx.text.font(t.font, &ctx.text_defaults);
            let size = ctx.text.size(t.size, t.font, &ctx.text_defaults);
            let color = ctx.text.color.or(t.color).or(ctx.text_defaults.color);
            let line_height = ctx
                .text
                .line_height
                .or(t.line_height)
                .or(ctx.text_defaults.line_height);
            let content = t.content.clone();
            let (align_x, align_y, width, height, wrap) =
                (t.align_x, t.align_y, t.width, t.height, t.wrap);
            let make = move |size: Option<f32>| {
                let mut w = text(content.clone());
                if let Some(size) = size {
                    w = w.size(size);
                }
                if let Some(color) = color {
                    w = w.style(move |_| text::Style {
                        color: Some(crate::animation::fade(color)),
                    });
                }
                if let Some(font) = font {
                    w = w.font(font);
                }
                if let Some(lh) = line_height {
                    w = w.line_height(LineHeight::Relative(lh));
                }
                if let Some(a) = align_x {
                    w = w.align_x(a);
                }
                if let Some(a) = align_y {
                    w = w.align_y(a);
                }
                if let Some(width) = width {
                    w = w.width(width);
                }
                if let Some(height) = height {
                    w = w.height(height);
                }
                if !wrap {
                    w = w.wrapping(Wrapping::None);
                }
                w
            };
            if ctx.font_slot {
                crate::animation::SizedText::new(size, make).into()
            } else {
                make(size).into()
            }
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
        Kind::Container { .. } | Kind::Button { .. } => build_box(py, node_ref, ctx, None),
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
            align_x,
            style,
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
            if let Some(s) = ctx.text.size(*size, *font, &ctx.text_defaults) {
                t = t.size(s);
            }
            if let Some(f) = ctx.text.font(*font, &ctx.text_defaults) {
                t = t.font(f);
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
                crate::animation::fade_text_input(out)
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
                crate::animation::fade_scrollable(out)
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
            let style = move |theme: &Theme| {
                crate::animation::fade_rule(rule::Style {
                    color: color.unwrap_or(theme.extended_palette().background.strong.color),
                    radius: 0.0.into(),
                    fill_mode: rule::FillMode::Full,
                    snap: true,
                })
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
        Kind::Styled(props) => {
            let inner = if props.defaults {
                Ctx {
                    text_defaults: ctx.text_defaults.merged(&props.text),
                    ..ctx
                }
            } else {
                Ctx {
                    text: ctx.text.merged(&props.text),
                    ..ctx
                }
            };
            let target = props.child.bind(py).get();
            let element = match &target.kind {
                Kind::Container { .. } | Kind::Button { .. } => {
                    build_box(py, &props.child, inner, Some(props))
                }
                Kind::Events {
                    child,
                    handlers,
                    cursor,
                } if matches!(
                    child.bind(py).get().kind,
                    Kind::Container { .. } | Kind::Button { .. }
                ) =>
                {
                    crate::events::EventArea::new(
                        build_box(py, child, inner, Some(props)),
                        handlers.clone(),
                        *cursor,
                    )
                    .into()
                }
                _ if inner.pad_slot => {
                    let child = build(
                        py,
                        &props.child,
                        Ctx {
                            pad_slot: false,
                            ..inner
                        },
                    );
                    let own = props.padding.unwrap_or(iced::Padding::ZERO);
                    crate::styled::wrap(crate::animation::PadSlot::new(child, own).into(), props)
                }
                _ => crate::styled::wrap(build(py, &props.child, inner), props),
            };
            // The margin goes outside the effects, so a rotated or blurred box keeps its spacing.
            crate::styled::margin(crate::styled::effects_of(element, props), props)
        }
        Kind::Events {
            child,
            handlers,
            cursor,
        } => crate::events::EventArea::new(build(py, child, ctx), handlers.clone(), *cursor).into(),
        Kind::Animated { child, spec } => {
            let pad_inside = spec.has_padding() && draws_box(py, child);
            let inner = Ctx {
                pad_slot: ctx.pad_slot || pad_inside,
                font_slot: ctx.font_slot || spec.has_font_size(),
                ..ctx
            };
            let mut element = build(py, child, inner);
            if spec.has_paint() && !draws_box(py, child) {
                // Box paints need a box: give the element one.
                element = container(element)
                    .style(|theme| {
                        crate::animation::container_style(container::Style::default(), theme)
                    })
                    .into();
            }
            crate::animation::Animated::new(element, spec.clone())
                .pad_inside(pad_inside)
                .into()
        }
        Kind::Presence(props) => build_presence(py, props, ctx),
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
                container(build(py, tip, ctx))
                    .style(move |theme| crate::animation::container_style(style, theme)),
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
                crate::animation::fade_checkbox(out)
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
                crate::animation::fade_toggler(out)
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
                crate::animation::fade_slider(out)
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
                crate::animation::fade_progress(out)
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
                s = s.style(move |_, _| svg::Style {
                    color: Some(crate::animation::fade(c)),
                });
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
        Kind::Shader(props) => crate::shader::render(props),
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
            // A fixed height is the height of each row; iced would split it among all rows.
            let row_height = match (aspect_ratio, height) {
                (None, Some(Length::Fixed(h))) => Some(*h),
                _ => None,
            };
            let mut g = widget::grid(children.iter().map(|c| {
                let element = build(py, c, ctx);
                match row_height {
                    Some(h) => widget::container(element)
                        .width(Length::Fill)
                        .height(h)
                        .into(),
                    None => element,
                }
            }))
            .spacing(*spacing);
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
            } else if row_height.is_some() {
                g = g.height(Length::Shrink);
            } else if let Some(h) = height {
                g = g.height(*h);
            }
            g.into()
        }
        Kind::TrackGrid(props) => {
            let items = props
                .children
                .iter()
                .map(|c| match &c.bind(py).get().kind {
                    Kind::Cell { child, placement } => (build(py, child, ctx), *placement),
                    _ => (
                        build(py, c, ctx),
                        crate::layout::Placement {
                            column_span: 1,
                            row_span: 1,
                            ..Default::default()
                        },
                    ),
                })
                .collect();
            crate::layout::TrackGrid::new(items, props).into()
        }
        Kind::Cell { child, .. } => build(py, child, ctx),
        Kind::Resizable(props) => {
            let on_resize = props.on_resize.clone().map(|cb| {
                Box::new(move |size: f32| Message::Slide(cb.clone(), size))
                    as Box<dyn Fn(f32) -> Message + 'a>
            });
            let color = props.color.unwrap_or(Color::from_rgb8(0x46, 0x4b, 0x57));
            crate::layout::Resizable::new(
                build(py, &props.child, ctx),
                props.edge,
                props.size,
                (props.min, props.max),
                crate::layout::ResizeStyle {
                    color,
                    hover_color: props.hover_color.unwrap_or(color),
                    line: props.thickness,
                    handle: props.handle,
                },
                props.cross,
                on_resize,
            )
            .into()
        }
        Kind::WindowEdges { child, border } => {
            crate::frame::WindowEdges::new(build(py, child, ctx), *border).into()
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
        Kind::Virtual {
            count,
            item,
            item_height,
            spacing,
            overscan,
            width,
        } => {
            let item = item.clone();
            crate::virtualize::VirtualColumn::new(
                *count,
                *item_height,
                *spacing,
                *overscan,
                width.unwrap_or(Length::Fill),
                move |index| {
                    Python::attach(|py| {
                        let result = item
                            .0
                            .bind(py)
                            .call1((index,))
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
                },
            )
            .into()
        }
    }
}
