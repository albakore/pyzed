//! Turns the Python-built `Widget` tree into iced elements.

use elsa::FrozenMap;
use iced::advanced::text::Wrapping;
use iced::widget::text::LineHeight;
use iced::widget::{
    self, Space, button, checkbox, column, container, mouse_area, progress_bar, row, rule,
    scrollable, slider, svg, text, text_editor, text_input, toggler, tooltip,
};
use iced::{Background, Border, Color, Element, Font, Length, Padding, Pixels, Theme};
use pyo3::prelude::*;

use crate::app::{EditorState, Message};
use crate::highlighter::{self, Highlighter};
use crate::style::ICONS;
use crate::widget::{EditorProps, Kind, Widget};

pub type Editors = FrozenMap<String, Box<EditorState>>;

pub struct Ctx<'a> {
    pub editors: &'a Editors,
    pub pending_cursors:
        &'a std::cell::RefCell<std::collections::HashMap<String, text_editor::Position>>,
}

fn with_alpha(color: Color, a: f32) -> Color {
    Color {
        a: color.a * a,
        ..color
    }
}

pub fn build<'a>(py: Python<'_>, node: &Py<Widget>, ctx: &Ctx<'a>) -> Element<'a, Message> {
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
            r.into()
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
        } => {
            let mut t = text_input(placeholder, value).secure(*secure);
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
            cursor,
        } => {
            let mut m = mouse_area(build(py, child, ctx));
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
            width,
            style,
        } => {
            let cb = on_change.clone();
            let mut s = slider(*min..=*max, *value, move |v| match &cb {
                Some(cb) => Message::Slide(cb.clone(), v),
                None => Message::Noop,
            })
            .step(*step);
            if let Some(w) = width {
                s = s.width(*w);
            }
            let st = style.clone();
            s.style(move |theme: &Theme, status| {
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
            })
            .into()
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
        Kind::Editor(props) => editor(props, ctx),
        Kind::Svg {
            source,
            width,
            height,
            color,
        } => {
            let handle = match source {
                crate::widget::SvgSource::Path(p) => svg::Handle::from_path(p),
                crate::widget::SvgSource::Bytes(b) => svg::Handle::from_memory(b.clone()),
            };
            let mut s = svg(handle);
            if let Some(w) = width {
                s = s.width(*w);
            }
            if let Some(h) = height {
                s = s.height(*h);
            }
            if let Some(c) = *color {
                s = s.style(move |_, _| svg::Style { color: Some(c) });
            }
            s.into()
        }
    }
}

fn editor<'a>(props: &EditorProps, ctx: &Ctx<'a>) -> Element<'a, Message> {
    let key: &str = &props.id;
    let state: &'a EditorState = match ctx.editors.get(key) {
        Some(state) => state,
        None => {
            let mut state = EditorState::new(&props.text);
            if let Some(position) = ctx.pending_cursors.borrow_mut().remove(key) {
                state.content.move_to(text_editor::Cursor {
                    position,
                    selection: None,
                });
            }
            ctx.editors.insert(key.to_owned(), Box::new(state))
        }
    };

    let lh = props.line_height;
    let pad_y = 4.0;
    let line_count = state.content.line_count().max(1);
    let cursor_line = state.content.cursor().position.line;

    let id = props.id.clone();
    let on_change = props.on_change.clone();
    let on_cursor = props.on_cursor.clone();

    let (bg, fg, sel, placeholder_color) = (
        props.background,
        props.text_color,
        props.selection_color,
        props.placeholder_color,
    );

    let theme_id = highlighter::theme_id(&props.syntax);
    let token = if highlighter::has_syntax(&props.language) {
        props.language.clone()
    } else {
        "txt".into()
    };

    let mut editor = text_editor(&state.content)
        .font(props.font)
        .size(props.size)
        .line_height(LineHeight::Absolute(Pixels(lh)))
        .padding(Padding {
            top: pad_y,
            bottom: pad_y,
            left: 4.0,
            right: 12.0,
        })
        .wrapping(if props.wrap {
            Wrapping::Word
        } else {
            Wrapping::None
        })
        .height(Length::Shrink)
        .on_action(move |action| Message::Editor {
            id: id.clone(),
            action,
            on_change: on_change.clone(),
            on_cursor: on_cursor.clone(),
        })
        .style(move |theme: &Theme, status| {
            let mut out = text_editor::default(theme, status);
            out.background = Background::Color(Color::TRANSPARENT);
            out.border = Border::default();
            if let Some(c) = fg {
                out.value = c;
            }
            if let Some(c) = sel {
                out.selection = c;
            }
            if let Some(c) = placeholder_color {
                out.placeholder = c;
            }
            out
        });
    if let Some(p) = &props.placeholder {
        editor = editor.placeholder(p.clone());
    }
    let editor = editor.highlight_with::<Highlighter>(
        highlighter::Settings {
            token,
            theme: theme_id,
            font: props.font,
        },
        highlighter::Highlight::to_format,
    );

    let mut body = row![].height(Length::Shrink);

    if props.gutter {
        let digits = line_count.to_string().len().max(2) as f32;
        let width = props
            .gutter_width
            .unwrap_or(digits * props.size * 0.62 + 28.0);
        let dim = props
            .gutter_color
            .unwrap_or(Color::from_rgb8(0x4e, 0x5a, 0x5f));
        let active = props
            .gutter_active_color
            .unwrap_or(Color::from_rgb8(0xd0, 0xd4, 0xda));
        let numbers = |range: std::ops::Range<usize>, color: Color| {
            let content = range
                .map(|n| (n + 1).to_string())
                .collect::<Vec<_>>()
                .join("\n");
            text(content)
                .font(props.font)
                .size(props.size)
                .line_height(LineHeight::Absolute(Pixels(lh)))
                .color(color)
                .width(Length::Fill)
                .align_x(iced::alignment::Horizontal::Right)
                .wrapping(Wrapping::None)
        };
        let cursor_line = cursor_line.min(line_count - 1);
        let mut gutter = column![].width(Length::Fixed(width)).padding(Padding {
            top: pad_y,
            bottom: pad_y,
            left: 0.0,
            right: 14.0,
        });
        if cursor_line > 0 {
            gutter = gutter.push(numbers(0..cursor_line, dim));
        }
        gutter = gutter.push(numbers(cursor_line..cursor_line + 1, active));
        if cursor_line + 1 < line_count {
            gutter = gutter.push(numbers(cursor_line + 1..line_count, dim));
        }

        // Git-style change markers drawn as thin bars on the left edge of the gutter.
        let mut markers = props.markers.clone();
        markers.sort_by_key(|(line, _)| *line);
        let mut bars = column![].width(Length::Fixed(3.0)).padding(Padding {
            top: pad_y,
            ..Padding::ZERO
        });
        let mut next = 1usize;
        for (line, color) in markers {
            if line < next || line > line_count {
                continue;
            }
            if line > next {
                bars = bars.push(Space::new().height(Length::Fixed((line - next) as f32 * lh)));
            }
            bars = bars.push(
                container(Space::new())
                    .width(Length::Fixed(3.0))
                    .height(Length::Fixed(lh))
                    .style(move |_| container::Style {
                        background: Some(Background::Color(color)),
                        ..Default::default()
                    }),
            );
            next = line + 1;
        }
        body = body.push(bars).push(gutter);
    }
    body = body.push(editor);

    let mut scroller = widget::Scrollable::with_direction(
        body,
        scrollable::Direction::Vertical(
            scrollable::Scrollbar::new().width(8.0).scroller_width(8.0),
        ),
    )
    .style(|theme: &Theme, status| {
        let mut out = scrollable::default(theme, status);
        out.vertical_rail.background = None;
        out.vertical_rail.border = Border::default();
        out.vertical_rail.scroller.background = Background::Color(with_alpha(
            theme.extended_palette().background.strong.color,
            0.6,
        ));
        out.vertical_rail.scroller.border = Border {
            radius: 0.0.into(),
            ..Border::default()
        };
        out
    })
    .width(props.layout.width.unwrap_or(Length::Fill))
    .height(props.layout.height.unwrap_or(Length::Fill));
    if let Some(p) = props.layout.padding {
        scroller = scroller.height(props.layout.height.unwrap_or(Length::Fill));
        return container(scroller)
            .padding(p)
            .style(move |_| container::Style {
                background: bg.map(Background::Color),
                ..Default::default()
            })
            .into();
    }
    container(scroller)
        .width(props.layout.width.unwrap_or(Length::Fill))
        .height(props.layout.height.unwrap_or(Length::Fill))
        .style(move |_| container::Style {
            background: bg.map(Background::Color),
            ..Default::default()
        })
        .into()
}
