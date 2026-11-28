//! Drawing the grid: only the visible cells, in four panes (frozen rows and columns), then the
//! headers, the cell being typed in, the formula bar, the scrollbars and the popups.

use std::cell::RefCell;
use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use std::time::{Duration, Instant};

use iced::advanced::graphics::geometry::Renderer as _;
use iced::advanced::renderer::{Quad, Renderer as _};
use iced::advanced::text::{self, LineHeight, Paragraph as _, Renderer as _, Text};
use iced::widget::canvas::{self, Path};
use iced::{Background, Border, Color, Em, Font, Pixels, Point, Rectangle, Size, alignment};

use super::edit::{self, Edit};
use super::geo::{FX_W, Geo, NAME_W, Pane};
use super::{Drag, SheetProps};
use crate::sheet::addr::{Area, col_name};
use crate::sheet::display::Shown;
use crate::sheet::model::{Book, HAlign, Sheet, VAlign};

type Renderer = iced::Renderer;
type Paragraph = <Renderer as text::Renderer>::Paragraph;

/// Space between a cell's edge and its text.
pub const PAD: f32 = 5.0;
pub const CHECK: char = '\u{e06c}';
pub const CHEVRON: char = '\u{e06d}';
pub const FUNNEL: char = '\u{e0dc}';
/// How long the caret stays on (and off).
pub const BLINK: Duration = Duration::from_millis(530);
/// Height of a row in the popups.
pub const ITEM_H: f32 = 26.0;

thread_local! {
    static WIDTHS: RefCell<HashMap<(String, u32, u64), f32>> = RefCell::new(HashMap::new());
}

pub fn font_for(bold: bool, italic: bool, mono: bool) -> Font {
    let mut f = Font::with_name(if mono {
        crate::style::mono()
    } else {
        crate::style::sans()
    });
    if bold {
        f.weight = iced::font::Weight::Bold;
    }
    if italic {
        f.style = iced::font::Style::Italic;
    }
    f
}

fn icons() -> Font {
    Font::with_name(crate::style::ICONS)
}

/// Font size in pixels for a size in points (10 pt is the widget's text size).
pub fn font_px(size: Option<u16>, base: f32) -> f32 {
    size.map_or(base, |pt| pt as f32 * base / 10.0)
}

/// Width of one line of text (memorized).
pub fn measure(text: &str, font: Font, size: f32) -> f32 {
    if text.is_empty() {
        return 0.0;
    }
    let mut h = std::collections::hash_map::DefaultHasher::new();
    font.hash(&mut h);
    let key = (text.to_string(), size.to_bits(), h.finish());
    if let Some(w) = WIDTHS.with(|m| m.borrow().get(&key).copied()) {
        return w;
    }
    let p = Paragraph::with_text(Text {
        content: text,
        bounds: Size::new(1.0e5, 1.0e4),
        size: Pixels(size),
        line_height: LineHeight::Relative(1.25),
        font,
        align_x: text::Alignment::Default,
        align_y: alignment::Vertical::Top,
        shaping: text::Shaping::Advanced,
        wrapping: text::Wrapping::None,
        letter_spacing: Em::ZERO,
    });
    let w = p.min_width();
    WIDTHS.with(|m| {
        let mut m = m.borrow_mut();
        if m.len() > 8192 {
            m.clear();
        }
        m.insert(key, w);
    });
    w
}

/// Height of `text` wrapped at `width`.
pub fn wrapped_height(text: &str, font: Font, size: f32, width: f32) -> f32 {
    let p = Paragraph::with_text(Text {
        content: text,
        bounds: Size::new(width.max(1.0), 1.0e5),
        size: Pixels(size),
        line_height: LineHeight::Relative(1.25),
        font,
        align_x: text::Alignment::Default,
        align_y: alignment::Vertical::Top,
        shaping: text::Shaping::Advanced,
        wrapping: text::Wrapping::WordOrGlyph,
        letter_spacing: Em::ZERO,
    });
    p.min_bounds().height
}

pub fn color(c: u32) -> Color {
    Color::from_rgba8(
        (c >> 24) as u8,
        (c >> 16) as u8,
        (c >> 8) as u8,
        (c & 0xFF) as f32 / 255.0,
    )
}

fn alpha(c: Color, a: f32) -> Color {
    Color { a: c.a * a, ..c }
}

/// The theme's text color, or black / white when a cell's fill would hide it (a light fill in a
/// dark theme), like Sheets and Excel where text without a color is black.
fn readable(text: Color, fill: Option<Color>) -> Color {
    let lum = |c: Color| 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
    match fill {
        Some(f) if f.a > 0.3 => {
            let (lf, lt) = (lum(f), lum(text));
            if lf > 0.55 && lt > 0.5 {
                Color::from_rgb8(0x1f, 0x1f, 0x1f)
            } else if lf < 0.3 && lt < 0.5 {
                Color::WHITE
            } else {
                text
            }
        }
        _ => text,
    }
}

pub fn fill(r: &mut Renderer, b: Rectangle, c: Color) {
    if b.width <= 0.0 || b.height <= 0.0 {
        return;
    }
    r.fill_quad(
        Quad {
            bounds: b,
            ..Quad::default()
        },
        Background::Color(c),
    );
}

fn rounded(r: &mut Renderer, b: Rectangle, bg: Color, border: Color, radius: f32) {
    r.fill_quad(
        Quad {
            bounds: b,
            border: Border {
                color: border,
                width: if border.a > 0.0 { 1.0 } else { 0.0 },
                radius: radius.into(),
                ..Default::default()
            },
            ..Quad::default()
        },
        Background::Color(bg),
    );
}

/// A rectangle's outline drawn inside it, only on the given sides (top, right, bottom, left).
fn outline(r: &mut Renderer, b: Rectangle, c: Color, w: f32, sides: [bool; 4]) {
    if sides[0] {
        fill(r, Rectangle { height: w, ..b }, c);
    }
    if sides[2] {
        fill(
            r,
            Rectangle {
                y: b.y + b.height - w,
                height: w,
                ..b
            },
            c,
        );
    }
    if sides[3] {
        fill(r, Rectangle { width: w, ..b }, c);
    }
    if sides[1] {
        fill(
            r,
            Rectangle {
                x: b.x + b.width - w,
                width: w,
                ..b
            },
            c,
        );
    }
}

fn dashed(r: &mut Renderer, b: Rectangle, c: Color, w: f32, phase: f32) {
    let (on, off) = (5.0, 3.0);
    let mut seg = |x0: f32, y0: f32, len: f32, horizontal: bool| {
        let mut t = -(phase % (on + off));
        while t < len {
            let a = t.max(0.0);
            let e = (t + on).min(len);
            if e > a {
                let q = if horizontal {
                    Rectangle {
                        x: x0 + a,
                        y: y0,
                        width: e - a,
                        height: w,
                    }
                } else {
                    Rectangle {
                        x: x0,
                        y: y0 + a,
                        width: w,
                        height: e - a,
                    }
                };
                fill(r, q, c);
            }
            t += on + off;
        }
    };
    seg(b.x, b.y, b.width, true);
    seg(b.x, b.y + b.height - w, b.width, true);
    seg(b.x, b.y, b.height, false);
    seg(b.x + b.width - w, b.y, b.height, false);
}

#[allow(clippy::too_many_arguments)]
pub fn label(
    r: &mut Renderer,
    content: &str,
    at: Point,
    ax: text::Alignment,
    ay: alignment::Vertical,
    font: Font,
    size: f32,
    c: Color,
    clip: Rectangle,
    wrap: Option<f32>,
) {
    r.fill_text(
        Text {
            content: content.to_string(),
            bounds: Size::new(wrap.unwrap_or(1.0e5), 1.0e4),
            size: Pixels(size),
            line_height: LineHeight::Relative(1.25),
            font,
            align_x: ax,
            align_y: ay,
            shaping: text::Shaping::Advanced,
            wrapping: if wrap.is_some() {
                text::Wrapping::WordOrGlyph
            } else {
                text::Wrapping::None
            },
            letter_spacing: Em::ZERO,
        },
        at,
        c,
        clip,
    );
}

fn is_blank(sh: &Shown) -> bool {
    sh.text.is_empty()
        && sh.fill.is_none()
        && sh.bar.is_none()
        && sh.checkbox.is_none()
        && !sh.dropdown
        && !sh.note
        && !sh.invalid
        && sh.error.is_none()
        && !sh.borders.iter().any(|b| *b)
}

/// The cell holds something (so text from its left does not run over it).
fn occupied(s: &Sheet, r: u32, c: u32) -> bool {
    s.cell(r, c).is_some_and(|x| x.has_content())
        || !s.value(r, c).is_empty()
        || s.merge_at(r, c).is_some()
}

struct Item {
    r: u32,
    c: u32,
    rect: Rectangle,
    shown: Shown,
    merged: bool,
}

pub fn caret_on(book: &Book) -> bool {
    match book.ui.blink {
        Some(t) => (t.elapsed().as_millis() / BLINK.as_millis()).is_multiple_of(2),
        None => true,
    }
}

pub fn paint(p: &SheetProps, book: &mut Book, r: &mut Renderer, bounds: Rectangle) {
    if book
        .ui
        .edit
        .as_ref()
        .is_some_and(|e| e.sheet >= book.sheets.len())
    {
        book.ui.edit = None;
    }
    let si = book.active.min(book.sheets.len() - 1);
    let mut g = Geo::new(bounds, &book.sheets[si], p.formula_bar, p.headers);
    if book.ui.reveal {
        book.ui.reveal = false;
        let (ar, ac) = book.sheets[si].selection.active;
        g.reveal(&mut book.sheets[si], ar, ac);
    }
    let book: &Book = book;
    let c = &p.colors;
    fill(r, bounds, c.background);
    let s = &book.sheets[si];
    for pane in g.panes(s) {
        r.with_layer(pane.clip, |r| draw_pane(p, book, si, &g, &pane, r));
    }
    if g.fc > 0 {
        fill(
            r,
            Rectangle {
                x: g.grid.x + g.fw - 1.0,
                y: g.colh.y,
                width: 2.0,
                height: g.grid.height + g.colh.height,
            },
            c.frozen,
        );
    }
    if g.fr > 0 {
        fill(
            r,
            Rectangle {
                x: g.rowh.x,
                y: g.grid.y + g.fh - 1.0,
                width: g.grid.width + g.rowh.width,
                height: 2.0,
            },
            c.frozen,
        );
    }
    if g.headers {
        draw_headers(p, book, si, &g, r);
    }
    if let Some(e) = &book.ui.edit
        && e.sheet == si
    {
        r.with_layer(g.grid, |r| draw_editor(p, book, &g, e, r));
    }
    if g.bar.is_some() {
        draw_bar(p, book, si, &g, r);
    }
    draw_scrollbars(p, book, s, &g, r);
    r.with_layer(bounds, |r| draw_popups(p, book, si, &g, r));
}

fn draw_pane(p: &SheetProps, book: &Book, si: usize, g: &Geo, pane: &Pane, r: &mut Renderer) {
    let s = &book.sheets[si];
    let c = &p.colors;
    let (r0, r1) = pane.rows;
    let (c0, c1) = pane.cols;
    if r0 >= r1 || c0 >= c1 {
        return;
    }
    let base = p.text_size;
    if s.gridlines {
        for col in c0..c1 {
            if s.col_axis.is_hidden(col) {
                continue;
            }
            let x = g.x_of(s, col) + s.col_axis.size(col) - 1.0;
            fill(
                r,
                Rectangle {
                    x,
                    y: pane.clip.y,
                    width: 1.0,
                    height: pane.clip.height,
                },
                c.grid,
            );
        }
        for row in r0..r1 {
            if s.row_axis.is_hidden(row) {
                continue;
            }
            let y = g.y_of(s, row) + s.row_axis.size(row) - 1.0;
            fill(
                r,
                Rectangle {
                    x: pane.clip.x,
                    y,
                    width: pane.clip.width,
                    height: 1.0,
                },
                c.grid,
            );
        }
    }
    let view = Area::new(r0, c0, r1 - 1, c1 - 1);
    let merges: Vec<Area> = s
        .merges
        .iter()
        .filter(|m| m.intersects(&view))
        .copied()
        .collect();
    // Cells a few columns to the left can run their text into view.
    let lo = if c0 >= g.fc {
        c0.saturating_sub(6).max(g.fc)
    } else {
        c0
    };
    let mut items: Vec<Item> = Vec::new();
    for row in r0..r1 {
        if s.row_axis.is_hidden(row) {
            continue;
        }
        for col in lo..c1 {
            if s.col_axis.is_hidden(col) || merges.iter().any(|m| m.contains(row, col)) {
                continue;
            }
            if col < c0
                && !s.cell(row, col).is_some_and(|x| x.has_content())
                && s.value(row, col).is_empty()
            {
                continue;
            }
            let shown = book.shown(si, row, col);
            if is_blank(&shown) {
                continue;
            }
            items.push(Item {
                r: row,
                c: col,
                rect: g.cell_rect(s, row, col),
                shown,
                merged: false,
            });
        }
    }
    for m in &merges {
        let shown = book.shown(si, m.r0, m.c0);
        items.push(Item {
            r: m.r0,
            c: m.c0,
            rect: g.area_rect(s, *m),
            shown,
            merged: true,
        });
    }
    for m in &merges {
        // Hide the gridlines inside a merged cell.
        let rect = g.area_rect(s, *m);
        if book.shown(si, m.r0, m.c0).fill.is_none() {
            fill(
                r,
                Rectangle {
                    width: rect.width - 1.0,
                    height: rect.height - 1.0,
                    ..rect
                },
                c.background,
            );
        }
    }
    // Fills and data bars.
    for it in &items {
        if let Some(f) = it.shown.fill {
            fill(r, it.rect, color(f));
        }
        if let Some((t, bc)) = it.shown.bar {
            let b = it.rect;
            let w = (b.width - 4.0) * t;
            rounded(
                r,
                Rectangle {
                    x: b.x + 2.0,
                    y: b.y + 3.0,
                    width: w,
                    height: b.height - 7.0,
                },
                alpha(color(bc), 0.75),
                Color::TRANSPARENT,
                2.0,
            );
        }
    }
    // Text.
    let hash_w = measure("#", font_for(false, false, false), base);
    for it in &items {
        let sh = &it.shown;
        let rect = it.rect;
        if let Some(checked) = sh.checkbox {
            let size = 15.0;
            let b = Rectangle {
                x: rect.center_x() - size / 2.0,
                y: rect.center_y() - size / 2.0,
                width: size,
                height: size,
            };
            if checked {
                rounded(r, b, c.accent, Color::TRANSPARENT, 3.0);
                label(
                    r,
                    &CHECK.to_string(),
                    b.center(),
                    text::Alignment::Center,
                    alignment::Vertical::Center,
                    icons(),
                    12.0,
                    Color::WHITE,
                    rect,
                    None,
                );
            } else {
                rounded(r, b, Color::TRANSPARENT, c.muted, 3.0);
            }
            continue;
        }
        if sh.text.is_empty() {
            continue;
        }
        let size = font_px(sh.size, base);
        let font = font_for(sh.bold, sh.italic, sh.mono);
        let tc = sh
            .color
            .map(color)
            .unwrap_or_else(|| readable(c.text, sh.fill.map(color)));
        let align = sh.align.unwrap_or(if sh.numeric {
            HAlign::Right
        } else if sh.boolean || sh.error.is_some() {
            HAlign::Center
        } else {
            HAlign::Left
        });
        let dd = if sh.dropdown { 18.0 } else { 0.0 };
        let inner = rect.width - 2.0 * PAD - dd;
        let valign = sh.valign.unwrap_or(VAlign::Bottom);
        let (y, ay) = match valign {
            VAlign::Top => (rect.y + 2.0, alignment::Vertical::Top),
            VAlign::Middle => (rect.center_y(), alignment::Vertical::Center),
            VAlign::Bottom => (rect.y + rect.height - 3.0, alignment::Vertical::Bottom),
        };
        let (x, ax) = match align {
            HAlign::Left => (rect.x + PAD, text::Alignment::Left),
            HAlign::Center => (rect.x + (rect.width - dd) / 2.0, text::Alignment::Center),
            HAlign::Right => (rect.x + rect.width - PAD - dd, text::Alignment::Right),
        };
        if sh.wrap {
            let x = match align {
                HAlign::Left => rect.x + PAD,
                HAlign::Center => rect.x + PAD + inner / 2.0,
                HAlign::Right => rect.x + PAD + inner,
            };
            label(
                r,
                &sh.text,
                Point::new(x, y),
                ax,
                ay,
                font,
                size,
                tc,
                rect,
                Some(inner.max(1.0)),
            );
            continue;
        }
        let first = sh
            .text
            .lines()
            .map(|l| measure(l, font, size))
            .fold(0.0f32, f32::max);
        let mut content = sh.text.clone();
        let mut clip = rect;
        if first > inner {
            if sh.numeric && !it.merged {
                let n = ((inner / hash_w).floor() as usize).max(1);
                content = "#".repeat(n);
            } else if !it.merged {
                let need = first + 2.0 * PAD;
                let extend_right = matches!(align, HAlign::Left | HAlign::Center);
                let extend_left = matches!(align, HAlign::Right | HAlign::Center);
                if extend_right {
                    let mut k = it.c + 1;
                    while clip.width < need && k < s.ncols && k < it.c + 30 && !occupied(s, it.r, k)
                    {
                        clip.width += s.col_axis.size(k);
                        k += 1;
                    }
                }
                if extend_left {
                    let mut k = it.c;
                    while clip.width < need && k > 0 && k + 30 > it.c && !occupied(s, it.r, k - 1) {
                        k -= 1;
                        let w = s.col_axis.size(k);
                        clip.x -= w;
                        clip.width += w;
                    }
                }
                // The overflowing text covers the gridlines it runs over.
                if clip.width > rect.width && sh.fill.is_none() {
                    let cover = Rectangle {
                        x: clip.x,
                        y: rect.y,
                        width: clip.width - 1.0,
                        height: rect.height - 1.0,
                    };
                    fill(r, cover, c.background);
                }
            }
        }
        label(
            r,
            &content,
            Point::new(x, y),
            ax,
            ay,
            font,
            size,
            tc,
            clip,
            None,
        );
        if sh.underline || sh.strike {
            let w = if content == sh.text {
                first
            } else {
                measure(&content, font, size)
            };
            let lx = match align {
                HAlign::Left => x,
                HAlign::Center => x - w / 2.0,
                HAlign::Right => x - w,
            };
            let text_top = match valign {
                VAlign::Top => y,
                VAlign::Middle => y - size * 0.625,
                VAlign::Bottom => y - size * 1.25,
            };
            r.with_layer(clip, |r| {
                if sh.underline {
                    fill(
                        r,
                        Rectangle {
                            x: lx,
                            y: text_top + size * 1.1,
                            width: w,
                            height: 1.0,
                        },
                        tc,
                    );
                }
                if sh.strike {
                    fill(
                        r,
                        Rectangle {
                            x: lx,
                            y: text_top + size * 0.68,
                            width: w,
                            height: 1.0,
                        },
                        tc,
                    );
                }
            });
        }
    }
    // Borders, dropdown arrows and the corner marks.
    let mut marks: Vec<(Point, f32, Color, bool)> = Vec::new();
    for it in &items {
        let sh = &it.shown;
        let b = it.rect;
        if sh.borders.iter().any(|x| *x) {
            let bc = sh.border_color.map(color).unwrap_or(c.text);
            let o = Rectangle {
                x: b.x - 1.0,
                y: b.y - 1.0,
                width: b.width + 1.0,
                height: b.height + 1.0,
            };
            outline(r, o, bc, 1.0, sh.borders);
        }
        if sh.dropdown {
            label(
                r,
                &CHEVRON.to_string(),
                Point::new(b.x + b.width - PAD, b.center_y()),
                text::Alignment::Right,
                alignment::Vertical::Center,
                icons(),
                13.0,
                c.muted,
                b,
                None,
            );
        }
        if sh.note {
            marks.push((Point::new(b.x + b.width - 1.0, b.y), 7.0, c.note, true));
        }
        if sh.invalid || sh.error.is_some() {
            marks.push((Point::new(b.x, b.y), 7.0, c.error, false));
        }
    }
    if !marks.is_empty() {
        let mut frame = canvas::Frame::with_bounds(r, pane.clip);
        for (at, size, col, right) in marks {
            let path = Path::new(|pb| {
                pb.move_to(at);
                if right {
                    pb.line_to(Point::new(at.x - size, at.y));
                    pb.line_to(Point::new(at.x, at.y + size));
                } else {
                    pb.line_to(Point::new(at.x + size, at.y));
                    pb.line_to(Point::new(at.x, at.y + size));
                }
                pb.close();
            });
            frame.fill(&path, col);
        }
        r.draw_geometry(frame.into_geometry());
    }
    // Filter buttons.
    if let Some(f) = &s.filter
        && f.area.r0 >= r0
        && f.area.r0 < r1
    {
        for col in f.area.c0.max(c0)..=f.area.c1.min(c1 - 1) {
            if s.col_axis.is_hidden(col) {
                continue;
            }
            let b = filter_button(g, s, f.area.r0, col);
            let active = f.conditions.contains_key(&col)
                || f.hidden.get(&col).is_some_and(|h| !h.is_empty())
                || f.sorted.is_some_and(|x| x.0 == col);
            rounded(
                r,
                b,
                if active {
                    alpha(c.accent, 0.15)
                } else {
                    c.header
                },
                c.border,
                3.0,
            );
            label(
                r,
                &(if active { FUNNEL } else { CHEVRON }).to_string(),
                b.center(),
                text::Alignment::Center,
                alignment::Vertical::Center,
                icons(),
                11.0,
                if active { c.accent } else { c.muted },
                b,
                None,
            );
        }
    }
    // References of the formula being typed.
    if let Some(e) = &book.ui.edit {
        for rf in ref_colors(e).into_iter().flatten() {
            let on_sheet = match &rf.2.sheet {
                Some(name) => name.eq_ignore_ascii_case(&s.name),
                None => e.sheet == si,
            };
            if !on_sheet {
                continue;
            }
            let Some(a) = rf.2.area.clamp(s.rows, s.ncols) else {
                continue;
            };
            let Some(sub) = a.intersection(&view) else {
                continue;
            };
            let col = c.refs[rf.3 % c.refs.len()];
            let rect = g.area_rect(s, sub);
            fill(r, rect, alpha(col, 0.10));
            let sides = [
                sub.r0 == a.r0,
                sub.c1 == a.c1,
                sub.r1 == a.r1,
                sub.c0 == a.c0,
            ];
            let o = Rectangle {
                x: rect.x - 1.0,
                y: rect.y - 1.0,
                width: rect.width + 1.0,
                height: rect.height + 1.0,
            };
            if e.point.as_ref().is_some_and(|pt| pt.start == rf.0) {
                dashed(r, o, col, 2.0, 0.0);
            } else {
                outline(r, o, col, 1.5, sides);
            }
        }
    }
    // The copied range.
    if let Some(clip) = &book.clip
        && clip.sheet == si
        && let Some(sub) = clip.area.intersection(&view)
    {
        let rect = g.area_rect(s, sub);
        dashed(
            r,
            Rectangle {
                x: rect.x - 1.0,
                y: rect.y - 1.0,
                width: rect.width + 1.0,
                height: rect.height + 1.0,
            },
            c.accent,
            2.0,
            0.0,
        );
    }
    // Selection.
    let sel = &s.selection;
    let active = s
        .merge_at(sel.active.0, sel.active.1)
        .unwrap_or(Area::cell(sel.active.0, sel.active.1));
    let active_rect = g.area_rect(s, active);
    let editing_here = book.ui.edit.as_ref().is_some_and(|e| e.sheet == si);
    let n = sel.ranges.len();
    for (i, a) in sel.ranges.iter().enumerate() {
        let Some(a) = a.clamp(s.rows, s.ncols) else {
            continue;
        };
        let Some(sub) = a.intersection(&view) else {
            continue;
        };
        let rect = g.area_rect(s, sub);
        if !a.is_cell() && a != active {
            let tint = alpha(c.accent, 0.12);
            if i + 1 == n && a.contains(active.r0, active.c0) {
                // Everything but the active cell.
                let ar = active_rect;
                let top = Rectangle {
                    height: (ar.y - rect.y).max(0.0),
                    ..rect
                };
                let bottom_y = ar.y + ar.height;
                let bottom = Rectangle {
                    y: bottom_y,
                    height: (rect.y + rect.height - bottom_y).max(0.0),
                    ..rect
                };
                let mid_y = ar.y.max(rect.y);
                let mid_h = (ar.y + ar.height).min(rect.y + rect.height) - mid_y;
                let left = Rectangle {
                    x: rect.x,
                    y: mid_y,
                    width: (ar.x - rect.x).max(0.0),
                    height: mid_h.max(0.0),
                };
                let right_x = ar.x + ar.width;
                let right = Rectangle {
                    x: right_x,
                    y: mid_y,
                    width: (rect.x + rect.width - right_x).max(0.0),
                    height: mid_h.max(0.0),
                };
                for q in [top, bottom, left, right] {
                    fill(r, q, tint);
                }
            } else {
                fill(r, rect, tint);
            }
            if i + 1 == n {
                let sides = [
                    sub.r0 == a.r0,
                    sub.c1 == a.c1,
                    sub.r1 == a.r1,
                    sub.c0 == a.c0,
                ];
                let o = Rectangle {
                    x: rect.x - 1.0,
                    y: rect.y - 1.0,
                    width: rect.width + 1.0,
                    height: rect.height + 1.0,
                };
                outline(r, o, c.accent, 1.0, sides);
            }
        }
    }
    if !editing_here && active.intersects(&view) {
        let o = Rectangle {
            x: active_rect.x - 1.0,
            y: active_rect.y - 1.0,
            width: active_rect.width + 1.0,
            height: active_rect.height + 1.0,
        };
        outline(r, o, c.accent, 2.0, [true; 4]);
    }
    if let Some(t) = book.ui.fill_target
        && let Some(sub) = t.intersection(&view)
    {
        let rect = g.area_rect(s, sub);
        dashed(
            r,
            Rectangle {
                x: rect.x - 1.0,
                y: rect.y - 1.0,
                width: rect.width + 1.0,
                height: rect.height + 1.0,
            },
            c.muted,
            1.0,
            0.0,
        );
    }
    if !editing_here
        && !p.readonly
        && !book.readonly
        && let Some(h) = fill_handle(g, s)
        && let last = sel.range()
        && view.contains(last.r1, last.c1)
    {
        fill(
            r,
            Rectangle {
                x: h.x - 1.0,
                y: h.y - 1.0,
                width: h.width + 2.0,
                height: h.height + 2.0,
            },
            c.background,
        );
        fill(r, h, c.accent);
    }
}

/// Each reference of the formula being typed, with its color index (same text, same color).
#[allow(clippy::type_complexity)]
pub fn ref_colors(e: &Edit) -> Vec<Option<(usize, usize, crate::sheet::formula::Ref, usize)>> {
    let mut seen: Vec<String> = Vec::new();
    e.refs()
        .into_iter()
        .map(|(a, b, rf)| {
            let key = e.text[a..b].replace('$', "").to_ascii_uppercase();
            let idx = match seen.iter().position(|k| *k == key) {
                Some(i) => i,
                None => {
                    seen.push(key);
                    seen.len() - 1
                }
            };
            Some((a, b, rf, idx))
        })
        .collect()
}

/// The small square at the bottom right of the selection, dragged to fill.
pub fn fill_handle(g: &Geo, s: &Sheet) -> Option<Rectangle> {
    let a = s.selection.range().clamp(s.rows, s.ncols)?;
    if a.whole_cols() || a.whole_rows() {
        return None;
    }
    let rect = g.area_rect(s, a);
    let (x, y) = (rect.x + rect.width - 1.0, rect.y + rect.height - 1.0);
    let h = Rectangle {
        x: x - 3.0,
        y: y - 3.0,
        width: 6.0,
        height: 6.0,
    };
    g.grid.contains(Point::new(x, y)).then_some(h)
}

pub fn filter_button(g: &Geo, s: &Sheet, r: u32, c: u32) -> Rectangle {
    let b = g.cell_rect(s, r, c);
    let size = (b.height - 6.0).clamp(12.0, 18.0);
    Rectangle {
        x: b.x + b.width - size - 3.0,
        y: b.y + (b.height - size) / 2.0,
        width: size,
        height: size,
    }
}

fn draw_headers(p: &SheetProps, book: &Book, si: usize, g: &Geo, r: &mut Renderer) {
    let s = &book.sheets[si];
    let c = &p.colors;
    let sel = &s.selection;
    let size = p.text_size * 0.92;
    let font = font_for(false, false, false);
    let bold = font_for(true, false, false);
    fill(r, g.colh, c.header);
    fill(r, g.rowh, c.header);
    let whole_col = |col: u32| {
        sel.ranges
            .iter()
            .any(|a| a.r0 == 0 && a.r1 + 1 >= s.rows && a.c0 <= col && col <= a.c1)
    };
    let some_col = |col: u32| sel.ranges.iter().any(|a| a.c0 <= col && col <= a.c1);
    let whole_row = |row: u32| {
        sel.ranges
            .iter()
            .any(|a| a.c0 == 0 && a.c1 + 1 >= s.ncols && a.r0 <= row && row <= a.r1)
    };
    let some_row = |row: u32| sel.ranges.iter().any(|a| a.r0 <= row && row <= a.r1);
    let scroll_cols = g.scroll_cols(s);
    let scroll_rows = g.scroll_rows(s);
    let col_parts = [
        (
            (0, g.fc),
            Rectangle {
                width: g.fw,
                ..g.colh
            },
        ),
        (
            scroll_cols,
            Rectangle {
                x: g.colh.x + g.fw,
                width: (g.colh.width - g.fw).max(0.0),
                ..g.colh
            },
        ),
    ];
    for ((a, b), clip) in col_parts {
        if a >= b {
            continue;
        }
        r.with_layer(clip, |r| {
            let mut marks = Vec::new();
            for col in a..b {
                if s.col_axis.is_hidden(col) {
                    marks.push(g.x_of(s, col));
                    continue;
                }
                let x = g.x_of(s, col);
                let w = s.col_axis.size(col);
                let rect = Rectangle {
                    x,
                    y: g.colh.y,
                    width: w,
                    height: g.colh.height,
                };
                let (bg, fg, f) = if whole_col(col) {
                    (c.accent, Color::WHITE, bold)
                } else if some_col(col) {
                    (c.header_active, c.header_active_text, bold)
                } else {
                    (c.header, c.header_text, font)
                };
                fill(r, rect, bg);
                fill(
                    r,
                    Rectangle {
                        x: x + w - 1.0,
                        width: 1.0,
                        ..rect
                    },
                    c.grid,
                );
                label(
                    r,
                    &col_name(col),
                    rect.center(),
                    text::Alignment::Center,
                    alignment::Vertical::Center,
                    f,
                    size,
                    fg,
                    rect,
                    None,
                );
            }
            // A double line where hidden columns are, like Sheets.
            for x in marks {
                for dx in [-3.0, 1.0] {
                    fill(
                        r,
                        Rectangle {
                            x: x + dx,
                            y: g.colh.y + 4.0,
                            width: 1.5,
                            height: g.colh.height - 8.0,
                        },
                        c.muted,
                    );
                }
            }
        });
    }
    fill(
        r,
        Rectangle {
            y: g.colh.y + g.colh.height - 1.0,
            height: 1.0,
            ..g.colh
        },
        c.border,
    );
    let row_parts = [
        (
            (0, g.fr),
            Rectangle {
                height: g.fh,
                ..g.rowh
            },
        ),
        (
            scroll_rows,
            Rectangle {
                y: g.rowh.y + g.fh,
                height: (g.rowh.height - g.fh).max(0.0),
                ..g.rowh
            },
        ),
    ];
    for ((a, b), clip) in row_parts {
        if a >= b {
            continue;
        }
        r.with_layer(clip, |r| {
            let mut marks = Vec::new();
            for row in a..b {
                if s.row_axis.is_hidden(row) {
                    if !s.row_axis.filtered.contains(&row) {
                        marks.push(g.y_of(s, row));
                    }
                    continue;
                }
                let y = g.y_of(s, row);
                let h = s.row_axis.size(row);
                let rect = Rectangle {
                    x: g.rowh.x,
                    y,
                    width: g.rowh.width,
                    height: h,
                };
                let (bg, fg, f) = if whole_row(row) {
                    (c.accent, Color::WHITE, bold)
                } else if some_row(row) {
                    (c.header_active, c.header_active_text, bold)
                } else {
                    (c.header, c.header_text, font)
                };
                fill(r, rect, bg);
                fill(
                    r,
                    Rectangle {
                        y: y + h - 1.0,
                        height: 1.0,
                        ..rect
                    },
                    c.grid,
                );
                label(
                    r,
                    &(row + 1).to_string(),
                    rect.center(),
                    text::Alignment::Center,
                    alignment::Vertical::Center,
                    f,
                    size,
                    fg,
                    rect,
                    None,
                );
            }
            for y in marks {
                for dy in [-3.0, 1.0] {
                    fill(
                        r,
                        Rectangle {
                            x: g.rowh.x + 4.0,
                            y: y + dy,
                            width: g.rowh.width - 8.0,
                            height: 1.5,
                        },
                        c.muted,
                    );
                }
            }
        });
    }
    fill(
        r,
        Rectangle {
            x: g.rowh.x + g.rowh.width - 1.0,
            width: 1.0,
            ..g.rowh
        },
        c.border,
    );
    let all = sel
        .ranges
        .iter()
        .any(|a| a.r0 == 0 && a.c0 == 0 && a.r1 + 1 >= s.rows && a.c1 + 1 >= s.ncols);
    fill(r, g.corner, if all { c.accent } else { c.header });
    outline(r, g.corner, c.border, 1.0, [false, true, true, false]);
    // Guide while resizing.
    match &book.ui.drag {
        Some(Drag::ResizeCol { now, .. }) => {
            fill(
                r,
                Rectangle {
                    x: *now - 1.0,
                    y: g.colh.y,
                    width: 2.0,
                    height: g.colh.height + g.grid.height,
                },
                c.accent,
            );
        }
        Some(Drag::ResizeRow { now, .. }) => {
            fill(
                r,
                Rectangle {
                    x: g.rowh.x,
                    y: *now - 1.0,
                    width: g.rowh.width + g.grid.width,
                    height: 2.0,
                },
                c.accent,
            );
        }
        _ => {}
    }
}

/// The font of the cell being typed in.
pub fn edit_font(p: &SheetProps, book: &Book, e: &Edit) -> (Font, f32) {
    let st = book.style(book.sheets[e.sheet].style_of(e.row, e.col));
    (
        font_for(st.bold, st.italic, st.mono),
        font_px(st.size, p.text_size),
    )
}

/// Where the cell editor is drawn.
pub fn editor_rect(p: &SheetProps, book: &Book, g: &Geo, e: &Edit) -> Rectangle {
    let s = &book.sheets[e.sheet];
    let area = s.merge_at(e.row, e.col).unwrap_or(Area::cell(e.row, e.col));
    let cell = g.area_rect(s, area);
    let (font, size) = edit_font(p, book, e);
    let lines: Vec<&str> = e.text.split('\n').collect();
    let w = lines
        .iter()
        .map(|l| measure(l, font, size))
        .fold(0.0f32, f32::max)
        + 2.0 * PAD
        + 8.0;
    let right = g.grid.x + g.grid.width;
    let width = w.min(right - cell.x).max(cell.width);
    let lh = size * 1.25;
    let height = (lines.len() as f32 * lh + 7.0).max(cell.height);
    Rectangle {
        x: cell.x,
        y: cell.y,
        width,
        height,
    }
}

/// Where the caret is, in the cell editor or the formula bar.
pub fn caret_rect(p: &SheetProps, book: &Book, g: &Geo, e: &Edit) -> Rectangle {
    let (font, size) = edit_font(p, book, e);
    let lh = size * 1.25;
    if e.in_bar || e.sheet != book.active {
        let text = e.text.replace('\n', " ");
        let x = measure(&text[..e.cursor], font, p.text_size);
        let off = bar_offset(g, x);
        return Rectangle {
            x: g.input.x + PAD + x - off,
            y: g.input.y + (g.input.height - lh) / 2.0,
            width: 1.5,
            height: lh,
        };
    }
    let er = editor_rect(p, book, g, e);
    let before = &e.text[..e.cursor];
    let line = before.matches('\n').count();
    let start = before.rfind('\n').map_or(0, |i| i + 1);
    let x = measure(&e.text[start..e.cursor], font, size);
    Rectangle {
        x: er.x + PAD + x,
        y: er.y + 3.5 + line as f32 * lh,
        width: 1.5,
        height: lh,
    }
}

/// How far the formula bar's text scrolls to show the caret at `x`.
fn bar_offset(g: &Geo, x: f32) -> f32 {
    (x - (g.input.width - 2.0 * PAD - 4.0)).max(0.0)
}

/// Draws `text` with the references of a formula in their colors.
#[allow(clippy::too_many_arguments)]
fn spans(
    r: &mut Renderer,
    p: &SheetProps,
    e: Option<&Edit>,
    text: &str,
    offset: usize,
    at: Point,
    font: Font,
    size: f32,
    base: Color,
    clip: Rectangle,
) {
    let mut colored: Vec<(usize, usize, Color)> = Vec::new();
    if let Some(e) = e {
        for (a, b, _, idx) in ref_colors(e).into_iter().flatten() {
            colored.push((a, b, p.colors.refs[idx % p.colors.refs.len()]));
        }
    }
    let end = offset + text.len();
    let mut x = at.x;
    let mut pos = offset;
    let draw = |r: &mut Renderer, from: usize, to: usize, col: Color, x: &mut f32| {
        if to <= from {
            return;
        }
        let piece = &text[from - offset..to - offset];
        label(
            r,
            piece,
            Point::new(*x, at.y),
            text::Alignment::Left,
            alignment::Vertical::Top,
            font,
            size,
            col,
            clip,
            None,
        );
        *x += measure(piece, font, size);
    };
    for (a, b, col) in colored {
        let (a, b) = (a.max(offset), b.min(end));
        if a >= b || a < pos {
            continue;
        }
        draw(r, pos, a, base, &mut x);
        draw(r, a, b, col, &mut x);
        pos = b;
    }
    draw(r, pos, end, base, &mut x);
}

fn draw_editor(p: &SheetProps, book: &Book, g: &Geo, e: &Edit, r: &mut Renderer) {
    let c = &p.colors;
    let er = editor_rect(p, book, g, e);
    let (font, size) = edit_font(p, book, e);
    let lh = size * 1.25;
    fill(r, er, c.editor);
    let o = Rectangle {
        x: er.x - 1.0,
        y: er.y - 1.0,
        width: er.width + 1.0,
        height: er.height + 1.0,
    };
    outline(r, o, c.accent, 2.0, [true; 4]);
    let (sa, sb) = e.selection();
    let mut start = 0usize;
    for (li, line) in e.text.split('\n').enumerate() {
        let y = er.y + 3.5 + li as f32 * lh;
        let end = start + line.len();
        if sa != sb {
            let (a, b) = (sa.max(start), sb.min(end));
            if a < b {
                let x0 = measure(&e.text[start..a], font, size);
                let x1 = measure(&e.text[start..b], font, size);
                fill(
                    r,
                    Rectangle {
                        x: er.x + PAD + x0,
                        y,
                        width: x1 - x0,
                        height: lh,
                    },
                    alpha(c.accent, 0.25),
                );
            }
        }
        spans(
            r,
            p,
            e.is_formula().then_some(e),
            line,
            start,
            Point::new(er.x + PAD, y),
            font,
            size,
            c.text,
            er,
        );
        start = end + 1;
    }
    if book.ui.focused && !e.in_bar {
        let cr = caret_rect(p, book, g, e);
        if let Some(pre) = &book.ui.preedit
            && !pre.is_empty()
        {
            let w = measure(pre, font, size);
            fill(
                r,
                Rectangle {
                    x: cr.x,
                    y: cr.y,
                    width: w,
                    height: lh,
                },
                c.editor,
            );
            label(
                r,
                pre,
                Point::new(cr.x, cr.y),
                text::Alignment::Left,
                alignment::Vertical::Top,
                font,
                size,
                c.text,
                er,
                None,
            );
            fill(
                r,
                Rectangle {
                    x: cr.x,
                    y: cr.y + lh - 1.0,
                    width: w,
                    height: 1.0,
                },
                c.text,
            );
        } else if caret_on(book) {
            fill(r, cr, c.text);
        }
    }
}

/// What the name box shows: the active cell, or the selected range.
pub fn name_text(s: &Sheet) -> String {
    let a = s.selection.range();
    let active = s.merge_at(s.selection.active.0, s.selection.active.1);
    if a.is_cell() || Some(a) == active {
        edit::address(s.selection.active.0, s.selection.active.1)
    } else {
        a.to_string()
    }
}

fn draw_bar(p: &SheetProps, book: &Book, si: usize, g: &Geo, r: &mut Renderer) {
    let Some(bar) = g.bar else { return };
    let c = &p.colors;
    let s = &book.sheets[si];
    let size = p.text_size;
    let font = font_for(false, false, false);
    fill(r, bar, c.background);
    fill(
        r,
        Rectangle {
            y: bar.y + bar.height - 1.0,
            height: 1.0,
            ..bar
        },
        c.border,
    );
    // Name box.
    let nb = Rectangle {
        x: g.name_box.x + 4.0,
        y: g.name_box.y + 4.0,
        width: g.name_box.width - 8.0,
        height: g.name_box.height - 8.0,
    };
    let naming = book.ui.name.as_ref();
    rounded(
        r,
        nb,
        c.background,
        if naming.is_some() {
            c.accent
        } else {
            Color::TRANSPARENT
        },
        4.0,
    );
    let name = naming.cloned().unwrap_or_else(|| name_text(s));
    label(
        r,
        &name,
        Point::new(nb.x + 6.0, nb.center_y()),
        text::Alignment::Left,
        alignment::Vertical::Center,
        font,
        size,
        c.text,
        nb,
        None,
    );
    if let Some(n) = naming
        && caret_on(book)
    {
        let x = nb.x + 6.0 + measure(n, font, size);
        fill(
            r,
            Rectangle {
                x,
                y: nb.center_y() - size * 0.62,
                width: 1.5,
                height: size * 1.25,
            },
            c.text,
        );
    }
    fill(
        r,
        Rectangle {
            x: g.name_box.x + NAME_W - 1.0,
            y: bar.y + 6.0,
            width: 1.0,
            height: bar.height - 12.0,
        },
        c.border,
    );
    label(
        r,
        "fx",
        Point::new(g.name_box.x + NAME_W + FX_W / 2.0, bar.center_y()),
        text::Alignment::Center,
        alignment::Vertical::Center,
        font_for(false, true, false),
        size,
        c.muted,
        bar,
        None,
    );
    // Contents.
    let e = book.ui.edit.as_ref();
    let text = match e {
        Some(e) => e.text.replace('\n', " "),
        None => {
            let (ar, ac) = s.selection.active;
            s.cell(ar, ac)
                .map(|x| x.input_text())
                .unwrap_or_default()
                .replace('\n', " ")
        }
    };
    let clip = Rectangle {
        x: g.input.x,
        y: g.input.y,
        width: g.input.width,
        height: g.input.height,
    };
    let lh = size * 1.25;
    let y = g.input.y + (g.input.height - lh) / 2.0;
    let mut off = 0.0;
    if let Some(e) = e
        && e.in_bar
    {
        off = bar_offset(g, measure(&text[..e.cursor.min(text.len())], font, size));
    }
    let x0 = g.input.x + PAD - off;
    r.with_layer(clip, |r| {
        if let Some(e) = e
            && e.in_bar
        {
            let (sa, sb) = e.selection();
            if sa != sb {
                let a = measure(&text[..sa], font, size);
                let b = measure(&text[..sb], font, size);
                fill(
                    r,
                    Rectangle {
                        x: x0 + a,
                        y,
                        width: b - a,
                        height: lh,
                    },
                    alpha(c.accent, 0.25),
                );
            }
        }
        spans(
            r,
            p,
            e.filter(|e| e.is_formula()),
            &text,
            0,
            Point::new(x0, y),
            font,
            size,
            c.text,
            clip,
        );
        if let Some(e) = e
            && e.in_bar
            && book.ui.focused
            && caret_on(book)
        {
            let x = x0 + measure(&text[..e.cursor.min(text.len())], font, size);
            fill(
                r,
                Rectangle {
                    x,
                    y,
                    width: 1.5,
                    height: lh,
                },
                c.text,
            );
        }
    });
}

fn draw_scrollbars(p: &SheetProps, book: &Book, s: &Sheet, g: &Geo, r: &mut Renderer) {
    let c = &p.colors;
    fill(r, g.vbar, c.background);
    fill(r, g.hbar, c.background);
    fill(
        r,
        Rectangle {
            x: g.vbar.x,
            y: g.hbar.y,
            width: g.vbar.width,
            height: g.hbar.height,
        },
        c.background,
    );
    let dragging_v = matches!(book.ui.drag, Some(Drag::VScroll { .. }));
    let dragging_h = matches!(book.ui.drag, Some(Drag::HScroll { .. }));
    if let Some(t) = g.vthumb(s) {
        rounded(
            r,
            t,
            alpha(c.muted, if dragging_v { 0.75 } else { 0.4 }),
            Color::TRANSPARENT,
            3.0,
        );
    }
    if let Some(t) = g.hthumb(s) {
        rounded(
            r,
            t,
            alpha(c.muted, if dragging_h { 0.75 } else { 0.4 }),
            Color::TRANSPARENT,
            3.0,
        );
    }
}

/// The function suggestions under the cell being typed in: the box and each row.
pub fn suggest_box(
    p: &SheetProps,
    book: &Book,
    g: &Geo,
) -> Option<(Rectangle, Vec<(Rectangle, &'static str)>)> {
    let e = book.ui.edit.as_ref()?;
    if !book.ui.focused {
        return None;
    }
    let list = e.suggestions();
    if list.is_empty()
        || (list.len() == 1 && e.typed_function().is_some_and(|(_, w)| w == list[0].0))
    {
        return None;
    }
    let anchor = anchor_rect(p, book, g, e);
    let h = list.len() as f32 * ITEM_H + 8.0;
    let w = 320.0f32.min(g.bounds.width - 8.0);
    let b = place(g, anchor, w, h);
    let rows = list
        .iter()
        .enumerate()
        .map(|(i, f)| {
            (
                Rectangle {
                    x: b.x + 4.0,
                    y: b.y + 4.0 + i as f32 * ITEM_H,
                    width: b.width - 8.0,
                    height: ITEM_H,
                },
                f.0,
            )
        })
        .collect();
    Some((b, rows))
}

fn anchor_rect(p: &SheetProps, book: &Book, g: &Geo, e: &Edit) -> Rectangle {
    if e.in_bar || e.sheet != book.active {
        g.input
    } else {
        editor_rect(p, book, g, e)
    }
}

/// A popup of `w`×`h` under `anchor` (or over it when there is no room).
fn place(g: &Geo, anchor: Rectangle, w: f32, h: f32) -> Rectangle {
    let b = g.bounds;
    let x = anchor.x.min(b.x + b.width - w - 4.0).max(b.x + 4.0);
    let below = anchor.y + anchor.height + 4.0;
    let y = if below + h <= b.y + b.height || anchor.y - h - 4.0 < b.y {
        below
    } else {
        anchor.y - h - 4.0
    };
    Rectangle {
        x,
        y,
        width: w,
        height: h,
    }
}

fn popup(r: &mut Renderer, p: &SheetProps, b: Rectangle) {
    let c = &p.colors;
    r.fill_quad(
        Quad {
            bounds: b,
            border: Border {
                color: c.border,
                width: 1.0,
                radius: 6.0.into(),
                ..Default::default()
            },
            shadow: iced::Shadow {
                color: Color {
                    a: 0.18,
                    ..Color::BLACK
                },
                offset: iced::Vector::new(0.0, 2.0),
                blur_radius: 8.0,
            },
            ..Quad::default()
        },
        Background::Color(c.popup),
    );
}

fn draw_popups(p: &SheetProps, book: &Book, si: usize, g: &Geo, r: &mut Renderer) {
    let c = &p.colors;
    let size = p.text_size;
    let font = font_for(false, false, false);
    let bold = font_for(true, false, false);
    let mono = font_for(false, false, true);
    if let Some((b, rows)) = suggest_box(p, book, g) {
        let e = book.ui.edit.as_ref().unwrap();
        popup(r, p, b);
        for (i, (rect, name)) in rows.iter().enumerate() {
            if i == e.suggest % rows.len() {
                rounded(r, *rect, c.popup_selected, Color::TRANSPARENT, 4.0);
            }
            label(
                r,
                name,
                Point::new(rect.x + 8.0, rect.center_y()),
                text::Alignment::Left,
                alignment::Vertical::Center,
                bold,
                size,
                c.popup_text,
                *rect,
                None,
            );
            let args = edit::hint(name).map(|h| h.1.join(", ")).unwrap_or_default();
            let nx = rect.x + 16.0 + measure(name, bold, size);
            label(
                r,
                &args,
                Point::new(nx, rect.center_y()),
                text::Alignment::Left,
                alignment::Vertical::Center,
                font,
                size * 0.9,
                c.muted,
                *rect,
                None,
            );
        }
        return;
    }
    if let Some(e) = book.ui.edit.as_ref()
        && book.ui.focused
        && let Some((name, i)) = e.current_call()
        && let Some((fname, args, desc)) = edit::hint(&name)
    {
        let hi = edit::hint_arg(&args, i);
        let head_w = measure(fname, bold, size)
            + measure("()", font, size)
            + args
                .iter()
                .enumerate()
                .map(|(k, a)| {
                    measure(a, if Some(k) == hi { bold } else { font }, size)
                        + measure(", ", font, size)
                })
                .sum::<f32>();
        let w = (head_w + 24.0)
            .max(measure(desc, font, size * 0.92).min(380.0) + 24.0)
            .min(g.bounds.width - 8.0);
        let dh = wrapped_height(desc, font, size * 0.92, w - 24.0);
        let h = size * 1.25 + dh + 22.0;
        let anchor = anchor_rect(p, book, g, e);
        let b = place(g, anchor, w, h);
        popup(r, p, b);
        let mut x = b.x + 12.0;
        let y = b.y + 8.0;
        let put = |r: &mut Renderer, t: &str, f: Font, col: Color, x: &mut f32| {
            label(
                r,
                t,
                Point::new(*x, y),
                text::Alignment::Left,
                alignment::Vertical::Top,
                f,
                size,
                col,
                b,
                None,
            );
            *x += measure(t, f, size);
        };
        put(r, fname, bold, c.popup_text, &mut x);
        put(r, "(", font, c.popup_text, &mut x);
        for (k, a) in args.iter().enumerate() {
            if k > 0 {
                put(r, ", ", font, c.popup_text, &mut x);
            }
            let on = Some(k) == hi;
            put(
                r,
                a,
                if on { bold } else { font },
                if on { c.accent } else { c.popup_text },
                &mut x,
            );
        }
        put(r, ")", font, c.popup_text, &mut x);
        label(
            r,
            desc,
            Point::new(b.x + 12.0, y + size * 1.25 + 6.0),
            text::Alignment::Left,
            alignment::Vertical::Top,
            font,
            size * 0.92,
            c.muted,
            b,
            Some(w - 24.0),
        );
        return;
    }
    // Notes, errors and validation messages of the cell under the pointer (or the active one).
    if book.ui.edit.is_none()
        && book.ui.drag.is_none()
        && let Some((hr, hc)) = book.ui.hover
    {
        let s = &book.sheets[si];
        let shown = book.shown(si, hr, hc);
        let mut lines: Vec<(String, bool)> = Vec::new();
        if let Some(err) = shown.error {
            let why = book.sheets[si]
                .cell(hr, hc)
                .and_then(|x| x.formula().map(|f| f.src.to_string()))
                .map(|_| err.describe().to_string())
                .unwrap_or_else(|| err.describe().to_string());
            lines.push((format!("{} {}", err.as_str(), why), true));
        }
        if shown.invalid {
            let msg = s
                .validation_at(hr, hc)
                .and_then(|v| v.message.clone())
                .unwrap_or_else(|| {
                    "Invalid: this value breaks the cell's data validation rule.".into()
                });
            lines.push((msg, true));
        }
        if let Some(note) = s.cell(hr, hc).and_then(|x| x.note.clone()) {
            lines.push((note.to_string(), false));
        }
        if lines.is_empty() {
            return;
        }
        let w = 260.0f32.min(g.bounds.width - 8.0);
        let mut h = 16.0;
        for (t, _) in &lines {
            h += wrapped_height(t, font, size * 0.92, w - 20.0) + 4.0;
        }
        let area = s.merge_at(hr, hc).unwrap_or(Area::cell(hr, hc));
        let cell = g.area_rect(s, area);
        let anchor = Rectangle {
            x: cell.x + cell.width + 2.0,
            y: cell.y - cell.height - 4.0,
            width: 0.0,
            height: cell.height,
        };
        let b = place(g, anchor, w, h);
        popup(r, p, b);
        let mut y = b.y + 8.0;
        for (t, err) in &lines {
            let f = if *err { bold } else { font };
            let col = if *err { c.error } else { c.popup_text };
            label(
                r,
                t,
                Point::new(b.x + 10.0, y),
                text::Alignment::Left,
                alignment::Vertical::Top,
                f,
                size * 0.92,
                col,
                b,
                Some(w - 20.0),
            );
            y += wrapped_height(t, f, size * 0.92, w - 20.0) + 4.0;
        }
        let _ = mono;
    }
}

/// Starts the caret's blink again (it stays on while typing).
pub fn restart_blink(book: &mut Book) {
    book.ui.blink = Some(Instant::now());
}
