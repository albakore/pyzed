//! Mouse, keyboard and input method events of the grid.

use std::time::{Duration, Instant};

use iced::advanced::input_method;
use iced::advanced::{Clipboard, Shell, clipboard, mouse};
use iced::keyboard::{self, Key, Modifiers, key::Named};
use iced::{Event, Point, Rectangle, window};

use super::edit::{self, Edit};
use super::geo::Geo;
use super::paint::{self, BLINK};
use super::{Drag, Emit, SheetProps};
use crate::app::Message;
use crate::sheet::addr::{Area, MAX_COLS, MAX_ROWS, col_name, parse_area, split_sheet};
use crate::sheet::model::{Book, Selection, Sheet, Style};
use crate::sheet::ops;
use crate::sheet::value::Value;

const DOUBLE_CLICK: Duration = Duration::from_millis(450);

fn ro(p: &SheetProps, book: &Book) -> bool {
    p.readonly || book.readonly
}

fn geo(p: &SheetProps, book: &Book, bounds: Rectangle) -> Geo {
    Geo::new(bounds, book.sheet(), p.formula_bar, p.headers)
}

#[allow(clippy::too_many_arguments)]
pub fn handle(
    p: &SheetProps,
    book: &mut Book,
    bounds: Rectangle,
    event: &Event,
    cursor: mouse::Cursor,
    clip: &mut dyn Clipboard,
    shell: &mut Shell<'_, Message>,
    emits: &mut Vec<Emit>,
) {
    if book
        .ui
        .edit
        .as_ref()
        .is_some_and(|e| e.sheet >= book.sheets.len())
    {
        book.ui.edit = None;
    }
    book.active = book.active.min(book.sheets.len() - 1);
    match event {
        Event::Mouse(mouse::Event::ButtonPressed(button)) => {
            press(p, book, bounds, *button, cursor, shell, emits)
        }
        Event::Mouse(mouse::Event::ButtonReleased(mouse::Button::Left)) => {
            release(p, book, bounds, shell, emits)
        }
        Event::Mouse(mouse::Event::CursorMoved { .. }) => moved(p, book, bounds, cursor, shell),
        Event::Mouse(mouse::Event::CursorLeft) => {
            if book.ui.hover.take().is_some() {
                shell.request_redraw();
            }
        }
        Event::Mouse(mouse::Event::WheelScrolled { delta, .. }) => {
            if cursor.is_over(bounds) {
                wheel(p, book, bounds, *delta, shell);
            }
        }
        Event::Keyboard(keyboard::Event::ModifiersChanged(m)) => book.ui.modifiers = *m,
        Event::Keyboard(keyboard::Event::KeyPressed {
            key,
            modified_key,
            modifiers,
            text,
            ..
        }) => {
            if book.ui.focused {
                book.ui.modifiers = *modifiers;
                let used = if book.ui.name.is_some() {
                    name_key(book, key, text.as_deref())
                } else if book.ui.edit.is_some() {
                    edit_key(
                        p,
                        book,
                        bounds,
                        key,
                        *modifiers,
                        text.as_deref(),
                        clip,
                        emits,
                    )
                } else {
                    grid_key(
                        p,
                        book,
                        bounds,
                        key,
                        modified_key,
                        *modifiers,
                        text.as_deref(),
                        clip,
                        emits,
                    )
                };
                if used {
                    crate::app::claim_key(key);
                    shell.capture_event();
                    shell.request_redraw();
                }
            }
        }
        Event::InputMethod(ev) => {
            if !book.ui.focused {
                return;
            }
            match ev {
                input_method::Event::Preedit(text, _) => {
                    book.ui.preedit = Some(text.clone());
                    if book.ui.edit.is_none() && !text.is_empty() && !ro(p, book) {
                        begin_edit(book, Some(String::new()), true);
                    }
                    shell.request_redraw();
                }
                input_method::Event::Commit(text) => {
                    book.ui.preedit = None;
                    if book.ui.edit.is_none() {
                        if ro(p, book) {
                            return;
                        }
                        begin_edit(book, Some(String::new()), true);
                    }
                    if let Some(e) = book.ui.edit.as_mut() {
                        e.insert(text);
                    }
                    paint::restart_blink(book);
                    shell.capture_event();
                    shell.request_redraw();
                }
                input_method::Event::Closed => {
                    book.ui.preedit = None;
                }
                input_method::Event::Opened => {}
            }
        }
        Event::Window(window::Event::RedrawRequested(now)) => frame(p, book, bounds, *now, shell),
        _ => {}
    }
}

// --- Selection -----------------------------------------------------------------

fn select_one(s: &mut Sheet, r: u32, c: u32) {
    let a = s.merge_at(r, c).unwrap_or(Area::cell(r, c));
    s.selection = Selection {
        ranges: vec![a],
        active: (a.r0, a.c0),
        anchor: (a.r0, a.c0),
    };
}

fn set_last(s: &mut Sheet, a: Area) {
    match s.selection.ranges.last_mut() {
        Some(l) => *l = a,
        None => s.selection.ranges.push(a),
    }
}

fn grow_to(s: &mut Sheet, r: u32, c: u32) {
    if r + 2 >= s.rows && s.rows < MAX_ROWS {
        s.grow(s.rows + 100, s.ncols);
    }
    if c + 2 >= s.ncols && s.ncols < MAX_COLS {
        s.grow(s.rows, s.ncols + 10);
    }
}

/// One step from `(r, c)`, over hidden rows and columns and out of a merged cell.
fn step(s: &Sheet, r: u32, c: u32, dr: i32, dc: i32) -> (u32, u32) {
    let (mut nr, mut nc) = (r as i64, c as i64);
    if let Some(m) = s.merge_at(r, c) {
        if dr > 0 {
            nr = m.r1 as i64;
        }
        if dr < 0 {
            nr = m.r0 as i64;
        }
        if dc > 0 {
            nc = m.c1 as i64;
        }
        if dc < 0 {
            nc = m.c0 as i64;
        }
    }
    let (or, oc) = (nr, nc);
    loop {
        nr += dr as i64;
        nc += dc as i64;
        if nr < 0 || nc < 0 || nr >= s.rows as i64 || nc >= s.ncols as i64 {
            // Nothing visible that way: stay.
            if (or, oc) == (r as i64, c as i64) {
                return (r, c);
            }
            return (
                or.clamp(0, s.rows as i64 - 1) as u32,
                oc.clamp(0, s.ncols as i64 - 1) as u32,
            );
        }
        let hidden = (dr != 0 && s.row_axis.is_hidden(nr as u32))
            || (dc != 0 && s.col_axis.is_hidden(nc as u32));
        if !hidden {
            break;
        }
    }
    (nr as u32, nc as u32)
}

/// Moves the active cell (or the selection's moving corner with `extend`); returns the cell to show.
fn move_sel(book: &mut Book, dr: i32, dc: i32, extend: bool, jump: bool) -> (u32, u32) {
    let s = book.sheet_mut();
    let sel = s.selection.clone();
    if extend {
        let a = sel.range();
        let anc = sel.anchor;
        let corner = (
            if anc.0 == a.r0 { a.r1 } else { a.r0 },
            if anc.1 == a.c0 { a.c1 } else { a.c0 },
        );
        let n = if jump {
            ops::jump(s, corner.0, corner.1, dr, dc)
        } else {
            step(s, corner.0, corner.1, dr, dc)
        };
        grow_to(s, n.0, n.1);
        let area = s.expand_merges(Area::new(anc.0, anc.1, n.0, n.1));
        set_last(s, area);
        n
    } else {
        let (r, c) = sel.active;
        let n = if jump {
            ops::jump(s, r, c, dr, dc)
        } else {
            step(s, r, c, dr, dc)
        };
        grow_to(s, n.0, n.1);
        select_one(s, n.0, n.1);
        n
    }
}

/// Enter and Tab: inside a selected range they cycle through its cells.
fn enter_move(book: &mut Book, dr: i32, dc: i32) -> (u32, u32) {
    let s = book.sheet_mut();
    let sel = s.selection.clone();
    let a = sel.range();
    let merged = s.merge_at(sel.active.0, sel.active.1);
    if sel.ranges.len() == 1 && !a.is_cell() && Some(a) != merged {
        let (mut r, mut c) = sel.active;
        if dr != 0 {
            let nr = r as i64 + dr as i64;
            if nr > a.r1 as i64 {
                r = a.r0;
                c = if c >= a.c1 { a.c0 } else { c + 1 };
            } else if nr < a.r0 as i64 {
                r = a.r1;
                c = if c <= a.c0 { a.c1 } else { c - 1 };
            } else {
                r = nr as u32;
            }
        } else {
            let nc = c as i64 + dc as i64;
            if nc > a.c1 as i64 {
                c = a.c0;
                r = if r >= a.r1 { a.r0 } else { r + 1 };
            } else if nc < a.c0 as i64 {
                c = a.c1;
                r = if r <= a.r0 { a.r1 } else { r - 1 };
            } else {
                c = nc as u32;
            }
        }
        s.selection.active = (r, c);
        (r, c)
    } else {
        move_sel(book, dr, dc, false, false)
    }
}

fn reveal(p: &SheetProps, book: &mut Book, bounds: Rectangle, at: (u32, u32)) {
    let mut g = geo(p, book, bounds);
    g.reveal(book.sheet_mut(), at.0, at.1);
}

// --- Editing ---------------------------------------------------------------------

fn begin_edit(book: &mut Book, text: Option<String>, enter_mode: bool) {
    let si = book.active;
    let s = book.sheet();
    let (r, c) = s.selection.active;
    let (r, c) = s.merge_at(r, c).map_or((r, c), |m| (m.r0, m.c0));
    let original = s.cell(r, c).map(|x| x.input_text()).unwrap_or_default();
    let mut e = Edit::new(si, r, c, original.clone(), enter_mode);
    if let Some(t) = text {
        e.cursor = t.len();
        e.anchor = t.len();
        e.text = t;
    }
    e.original = original;
    book.ui.edit = Some(e);
    book.ui.reveal = true;
    paint::restart_blink(book);
}

/// Stores what was typed; `false` when a strict validation rule refused it (the editor stays).
fn commit(book: &mut Book, emits: &mut Vec<Emit>) -> bool {
    let Some(e) = book.ui.edit.take() else {
        return true;
    };
    book.ui.preedit = None;
    let text = e.final_text();
    if text == e.original || e.sheet >= book.sheets.len() {
        return true;
    }
    if !text.starts_with('=')
        && let Some(v) = book.sheets[e.sheet].validation_at(e.row, e.col).cloned()
        && !matches!(v.check, crate::sheet::model::Check::Checkbox)
    {
        let value = book
            .typed_cell(e.sheet, e.row, e.col, &text)
            .map(|c| c.value)
            .unwrap_or(Value::Empty);
        if !book.valid(e.sheet, e.row, e.col, &value) && v.strict {
            emits.push(Emit::Invalid {
                cell: edit::address(e.row, e.col),
                value: text,
                message: v.message.clone(),
            });
            book.ui.edit = Some(e);
            return false;
        }
    }
    book.set_input(e.sheet, e.row, e.col, &text);
    emits.push(Emit::Change {
        action: "edit",
        range: edit::address(e.row, e.col),
    });
    true
}

/// Ctrl+Enter: the same input in every selected cell (formulas move with each cell).
fn commit_all(book: &mut Book, emits: &mut Vec<Emit>) {
    let Some(e) = book.ui.edit.take() else { return };
    let text = e.final_text();
    let si = e.sheet;
    let Some(base) = book.typed_cell(si, e.row, e.col, &text) else {
        let areas = book.sheets[si].selection.ranges.clone();
        book.clear(si, &areas, "contents");
        emits.push(Emit::Change {
            action: "edit",
            range: super::selection_text(&book.sheets[si]),
        });
        return;
    };
    let s = &book.sheets[si];
    let mut cells = Vec::new();
    for a in &s.selection.ranges {
        let Some(a) = a.clamp(s.rows, s.ncols) else {
            continue;
        };
        if a.cells() > 200_000 {
            continue;
        }
        for r in a.r0..=a.r1 {
            for c in a.c0..=a.c1 {
                let mut cell =
                    ops::moved_cell(&base, r as i64 - e.row as i64, c as i64 - e.col as i64);
                if let Some(old) = s.cell(r, c) {
                    cell.style = old.style;
                    cell.note = old.note.clone();
                }
                cells.push((r, c, Some(cell)));
            }
        }
    }
    book.write(si, cells);
    emits.push(Emit::Change {
        action: "edit",
        range: super::selection_text(&book.sheets[si]),
    });
}

// --- Mouse -----------------------------------------------------------------------------

fn press(
    p: &SheetProps,
    book: &mut Book,
    bounds: Rectangle,
    button: mouse::Button,
    cursor: mouse::Cursor,
    shell: &mut Shell<'_, Message>,
    emits: &mut Vec<Emit>,
) {
    let Some(pos) = cursor.position_over(bounds) else {
        if book.ui.focused {
            book.ui.focused = false;
            book.ui.name = None;
            // A formula waiting for a reference stays open (to pick one on another sheet).
            if book
                .ui
                .edit
                .as_ref()
                .is_some_and(|e| !(e.is_formula() && e.can_point()))
            {
                commit(book, emits);
                book.ui.edit = None;
            }
            shell.request_redraw();
        }
        return;
    };
    book.ui.focused = true;
    shell.capture_event();
    shell.request_redraw();
    let now = Instant::now();
    let double = button == mouse::Button::Left
        && book
            .ui
            .last_click
            .is_some_and(|(t, at)| now.duration_since(t) < DOUBLE_CLICK && at.distance(pos) < 5.0);
    book.ui.last_click = if double { None } else { Some((now, pos)) };
    let shift = book.ui.modifiers.shift();
    let ctrl = book.ui.modifiers.command();
    let mut g = geo(p, book, bounds);
    let si = book.active;

    if button == mouse::Button::Right {
        let s = book.sheet();
        let (kind, r, c) = if g.colh.contains(pos) {
            ("column", 0, g.col_at(s, pos.x))
        } else if g.rowh.contains(pos) {
            ("row", g.row_at(s, pos.y), 0)
        } else if g.grid.contains(pos) {
            ("cell", g.row_at(s, pos.y), g.col_at(s, pos.x))
        } else {
            return;
        };
        if book.ui.edit.is_some() && !commit(book, emits) {
            return;
        }
        let s = book.sheet_mut();
        let inside = match kind {
            "column" => s
                .selection
                .ranges
                .iter()
                .any(|a| a.c0 <= c && c <= a.c1 && a.whole_cols()),
            "row" => s
                .selection
                .ranges
                .iter()
                .any(|a| a.r0 <= r && r <= a.r1 && a.whole_rows()),
            _ => s.selection.contains(r, c),
        };
        if !inside {
            match kind {
                "column" => select_cols(s, c, c, (g.row_at(s, g.grid.y + g.fh + 1.0), c)),
                "row" => select_rows(s, r, r, (r, g.col_at(s, g.grid.x + g.fw + 1.0))),
                _ => select_one(s, r, c),
            }
            emits.push(Emit::Select);
        }
        emits.push(Emit::Context {
            kind,
            cell: edit::address(r, c),
            x: pos.x - bounds.x,
            y: pos.y - bounds.y,
        });
        return;
    }
    if button != mouse::Button::Left {
        return;
    }

    // Function suggestions.
    if let Some((_, rows)) = paint::suggest_box(p, book, &g)
        && let Some((_, name)) = rows.iter().find(|(r, _)| r.contains(pos))
    {
        if let Some(e) = book.ui.edit.as_mut() {
            e.accept(name);
        }
        paint::restart_blink(book);
        return;
    }

    // Formula bar.
    if let Some(bar) = g.bar
        && bar.contains(pos)
    {
        if g.name_box.contains(pos) {
            if book.ui.edit.is_some() && !commit(book, emits) {
                return;
            }
            book.ui.name = Some(String::new());
            paint::restart_blink(book);
            return;
        }
        book.ui.name = None;
        if ro(p, book) {
            return;
        }
        if book.ui.edit.is_none() {
            begin_edit(book, None, false);
        }
        if let Some(e) = book.ui.edit.as_mut() {
            e.in_bar = true;
            e.enter_mode = false;
            let text = e.text.replace('\n', " ");
            let font = paint::font_for(false, false, false);
            let at = hit(&text, font, p.text_size, pos.x - (g.input.x + paint::PAD));
            e.move_to(at, shift);
            if double {
                e.anchor = edit::word_left(&e.text, at);
                e.cursor = edit::word_right(&e.text, at);
            }
        }
        book.ui.drag = Some(Drag::Text);
        paint::restart_blink(book);
        return;
    }
    book.ui.name = None;

    // Scrollbars.
    let s = book.sheet();
    if g.vbar.contains(pos) {
        if let Some(t) = g.vthumb(s) {
            if t.contains(pos) {
                book.ui.drag = Some(Drag::VScroll { grab: pos.y - t.y });
            } else {
                let page = g.grid.height - g.fh;
                let dy = if pos.y < t.y { -page } else { page };
                let (sx, sy) = (g.sx, g.sy + dy);
                g.scroll_to(book.sheet_mut(), sx, sy);
            }
        }
        return;
    }
    if g.hbar.contains(pos) {
        if let Some(t) = g.hthumb(s) {
            if t.contains(pos) {
                book.ui.drag = Some(Drag::HScroll { grab: pos.x - t.x });
            } else {
                let page = g.grid.width - g.fw;
                let dx = if pos.x < t.x { -page } else { page };
                let (sx, sy) = (g.sx + dx, g.sy);
                g.scroll_to(book.sheet_mut(), sx, sy);
            }
        }
        return;
    }

    // Editing: the caret, or picking references for a formula.
    if let Some(e) = book.ui.edit.as_ref()
        && g.grid.contains(pos)
    {
        let on_sheet = e.sheet == si;
        let er = paint::editor_rect(p, book, &g, e);
        if on_sheet && er.contains(pos) {
            let (font, size) = paint::edit_font(p, book, e);
            let lh = size * 1.25;
            let line = (((pos.y - er.y - 3.5) / lh).floor().max(0.0)) as usize;
            let mut start = 0;
            for (i, l) in e.text.split('\n').enumerate() {
                if i == line {
                    break;
                }
                start += l.len() + 1;
            }
            let start = start.min(e.text.len());
            let end = e.text[start..]
                .find('\n')
                .map_or(e.text.len(), |i| start + i);
            let at = start + hit(&e.text[start..end], font, size, pos.x - (er.x + paint::PAD));
            let e = book.ui.edit.as_mut().unwrap();
            e.in_bar = false;
            e.move_to(at, shift);
            if double {
                e.anchor = edit::word_left(&e.text, at);
                e.cursor = edit::word_right(&e.text, at);
            }
            book.ui.drag = Some(Drag::Text);
            paint::restart_blink(book);
            return;
        }
        if e.is_formula() && e.can_point() {
            let s = book.sheet();
            let (r, c) = (g.row_at(s, pos.y), g.col_at(s, pos.x));
            let other = (e.sheet != si).then(|| book.sheet().name.clone());
            let e = book.ui.edit.as_mut().unwrap();
            if shift && let Some(pt) = e.point.clone() {
                e.set_point(pt.anchor, (r, c), other.as_deref());
                book.ui.drag = Some(Drag::Point { anchor: pt.anchor });
            } else {
                if !e.point.as_ref().is_some_and(|pt| pt.end == e.cursor) {
                    e.point = None;
                }
                e.point = None;
                e.set_point((r, c), (r, c), other.as_deref());
                book.ui.drag = Some(Drag::Point { anchor: (r, c) });
            }
            return;
        }
        if !commit(book, emits) {
            return;
        }
    } else if book.ui.edit.is_some()
        && (g.colh.contains(pos) || g.rowh.contains(pos) || g.corner.contains(pos))
        && !commit(book, emits)
    {
        return;
    }

    let s = book.sheet();
    // Corner: everything.
    if g.headers && g.corner.contains(pos) {
        let s = book.sheet_mut();
        let all = Area::new(0, 0, s.rows - 1, s.ncols - 1);
        let active = s.selection.active;
        s.selection = Selection {
            ranges: vec![all],
            active,
            anchor: active,
        };
        emits.push(Emit::Select);
        return;
    }
    // Column headers.
    if g.headers && g.colh.contains(pos) {
        if let Some(col) = g.col_edge(s, pos.x) {
            if double {
                autofit_cols(book, col);
                emits.push(Emit::Change {
                    action: "resize",
                    range: col_name(col),
                });
            } else {
                let size = s.col_axis.size(col);
                book.ui.drag = Some(Drag::ResizeCol {
                    col,
                    start: pos.x,
                    size,
                    now: g.x_of(s, col) + size,
                });
            }
            return;
        }
        let c = g.col_at(s, pos.x);
        let top = g.row_at(s, g.grid.y + g.fh + 1.0);
        let s = book.sheet_mut();
        if shift {
            let anc = s.selection.anchor.1;
            let rows = s.rows;
            set_last(s, Area::new(0, anc.min(c), rows - 1, anc.max(c)));
        } else if ctrl {
            let rows = s.rows;
            s.selection.ranges.push(Area::new(0, c, rows - 1, c));
            s.selection.active = (top, c);
            s.selection.anchor = (top, c);
        } else {
            select_cols(s, c, c, (top, c));
        }
        book.ui.drag = Some(Drag::Cols);
        return;
    }
    // Row headers.
    if g.headers && g.rowh.contains(pos) {
        if let Some(row) = g.row_edge(s, pos.y) {
            if double {
                autofit_row(p, book, row);
                emits.push(Emit::Change {
                    action: "resize",
                    range: (row + 1).to_string(),
                });
            } else {
                let size = s.row_axis.size(row);
                book.ui.drag = Some(Drag::ResizeRow {
                    row,
                    start: pos.y,
                    size,
                    now: g.y_of(s, row) + size,
                });
            }
            return;
        }
        let r = g.row_at(s, pos.y);
        let left = g.col_at(s, g.grid.x + g.fw + 1.0);
        let s = book.sheet_mut();
        if shift {
            let anc = s.selection.anchor.0;
            let cols = s.ncols;
            set_last(s, Area::new(anc.min(r), 0, anc.max(r), cols - 1));
        } else if ctrl {
            let cols = s.ncols;
            s.selection.ranges.push(Area::new(r, 0, r, cols - 1));
            s.selection.active = (r, left);
            s.selection.anchor = (r, left);
        } else {
            select_rows(s, r, r, (r, left));
        }
        book.ui.drag = Some(Drag::Rows);
        return;
    }
    if !g.grid.contains(pos) {
        return;
    }
    // Fill handle.
    if !ro(p, book)
        && let Some(h) = paint::fill_handle(&g, s)
        && (Rectangle {
            x: h.x - 3.0,
            y: h.y - 3.0,
            width: h.width + 6.0,
            height: h.height + 6.0,
        })
        .contains(pos)
    {
        book.ui.drag = Some(Drag::Fill {
            source: s.selection.range(),
        });
        book.ui.fill_target = None;
        return;
    }
    let (r, c) = (g.row_at(s, pos.y), g.col_at(s, pos.x));
    // Filter buttons.
    if let Some(f) = &s.filter
        && r == f.area.r0
        && f.area.c0 <= c
        && c <= f.area.c1
    {
        let b = paint::filter_button(&g, s, r, c);
        if b.contains(pos) {
            emits.push(Emit::Filter {
                column: col_name(c),
                x: b.x - bounds.x,
                y: b.y + b.height - bounds.y,
            });
            return;
        }
    }
    let shown = book.shown(si, r, c);
    let cell_rect = g.area_rect(s, s.merge_at(r, c).unwrap_or(Area::cell(r, c)));
    // Checkboxes.
    if let Some(checked) = shown.checkbox
        && !ro(p, book)
        && !shift
        && !ctrl
    {
        let b = Rectangle {
            x: cell_rect.center_x() - 10.0,
            y: cell_rect.center_y() - 10.0,
            width: 20.0,
            height: 20.0,
        };
        if b.contains(pos) {
            select_one(book.sheet_mut(), r, c);
            book.set_value(si, r, c, Value::Bool(!checked));
            emits.push(Emit::Select);
            emits.push(Emit::Change {
                action: "edit",
                range: edit::address(r, c),
            });
            return;
        }
    }
    // Dropdowns.
    if shown.dropdown
        && !ro(p, book)
        && pos.x > cell_rect.x + cell_rect.width - 20.0
        && !shift
        && !ctrl
    {
        select_one(book.sheet_mut(), r, c);
        emits.push(Emit::Select);
        open_dropdown(p, book, bounds, emits);
        return;
    }
    if double && !ro(p, book) {
        select_one(book.sheet_mut(), r, c);
        begin_edit(book, None, false);
        return;
    }
    let s = book.sheet_mut();
    let a = s.merge_at(r, c).unwrap_or(Area::cell(r, c));
    if shift {
        let anc = s.selection.anchor;
        let area = s.expand_merges(Area::new(anc.0, anc.1, r, c));
        set_last(s, area);
    } else if ctrl {
        s.selection.ranges.push(a);
        s.selection.active = (a.r0, a.c0);
        s.selection.anchor = (a.r0, a.c0);
    } else {
        select_one(s, r, c);
    }
    book.ui.drag = Some(Drag::Cells);
}

fn select_cols(s: &mut Sheet, c0: u32, c1: u32, active: (u32, u32)) {
    let rows = s.rows;
    s.selection = Selection {
        ranges: vec![Area::new(0, c0, rows - 1, c1)],
        active,
        anchor: active,
    };
}

fn select_rows(s: &mut Sheet, r0: u32, r1: u32, active: (u32, u32)) {
    let cols = s.ncols;
    s.selection = Selection {
        ranges: vec![Area::new(r0, 0, r1, cols - 1)],
        active,
        anchor: active,
    };
}

fn open_dropdown(p: &SheetProps, book: &mut Book, bounds: Rectangle, emits: &mut Vec<Emit>) {
    let si = book.active;
    let (r, c) = book.sheet().selection.active;
    let Some(options) = book.dropdown(si, r, c) else {
        return;
    };
    let g = geo(p, book, bounds);
    let s = book.sheet();
    let rect = g.area_rect(s, s.merge_at(r, c).unwrap_or(Area::cell(r, c)));
    emits.push(Emit::Dropdown {
        cell: edit::address(r, c),
        options,
        x: rect.x - bounds.x,
        y: rect.y + rect.height - bounds.y,
        width: rect.width,
    });
}

/// The byte offset in `text` nearest to `x` (from the start of the text).
fn hit(text: &str, font: iced::Font, size: f32, x: f32) -> usize {
    if x <= 0.0 || text.is_empty() {
        return 0;
    }
    let mut best = text.len();
    let mut prev_w = 0.0;
    let mut prev_i = 0;
    for (i, ch) in text.char_indices() {
        let end = i + ch.len_utf8();
        let w = paint::measure(&text[..end], font, size);
        if w >= x {
            best = if x - prev_w < w - x { prev_i } else { end };
            return best;
        }
        prev_w = w;
        prev_i = end;
    }
    best
}

fn autofit_cols(book: &mut Book, col: u32) {
    let si = book.active;
    let s = book.sheet();
    let cols: Vec<u32> = match s
        .selection
        .ranges
        .iter()
        .find(|a| a.whole_cols() && a.c0 <= col && col <= a.c1)
    {
        Some(a) => (a.c0..=a.c1).collect(),
        None => vec![col],
    };
    let widths: Vec<(u32, f32)> = cols
        .iter()
        .map(|&c| (c, super::estimate_width(book, si, c)))
        .collect();
    book.grouped(|b| {
        for (c, w) in widths {
            b.set_size(si, false, &[c], Some(w));
        }
    });
}

fn autofit_row(p: &SheetProps, book: &mut Book, row: u32) {
    let si = book.active;
    let s = book.sheet();
    let mut h = s.row_axis.default;
    let (_, cols) = s.extent();
    for c in 0..cols {
        let sh = book.shown(si, row, c);
        if sh.text.is_empty() {
            continue;
        }
        let size = paint::font_px(sh.size, p.text_size);
        let font = paint::font_for(sh.bold, sh.italic, sh.mono);
        let th = if sh.wrap {
            paint::wrapped_height(&sh.text, font, size, s.col_axis.size(c) - 2.0 * paint::PAD)
        } else {
            sh.text.lines().count().max(1) as f32 * size * 1.25
        };
        h = h.max(th + 8.0);
    }
    let size = if (h - s.row_axis.default).abs() < 0.5 {
        None
    } else {
        Some(h.ceil())
    };
    book.set_size(si, true, &[row], size);
}

fn release(
    p: &SheetProps,
    book: &mut Book,
    bounds: Rectangle,
    shell: &mut Shell<'_, Message>,
    emits: &mut Vec<Emit>,
) {
    let Some(drag) = book.ui.drag.take() else {
        return;
    };
    let si = book.active;
    match drag {
        Drag::ResizeCol { col, now, .. } => {
            let g = geo(p, book, bounds);
            let s = book.sheet();
            let w = (now - g.x_of(s, col)).max(8.0).round();
            let cols: Vec<u32> = match s
                .selection
                .ranges
                .iter()
                .find(|a| a.whole_cols() && a.c0 <= col && col <= a.c1)
            {
                Some(a) => (a.c0..=a.c1).collect(),
                None => vec![col],
            };
            book.set_size(si, false, &cols, Some(w));
            emits.push(Emit::Change {
                action: "resize",
                range: col_name(col),
            });
        }
        Drag::ResizeRow { row, now, .. } => {
            let g = geo(p, book, bounds);
            let s = book.sheet();
            let h = (now - g.y_of(s, row)).max(6.0).round();
            let rows: Vec<u32> = match s
                .selection
                .ranges
                .iter()
                .find(|a| a.whole_rows() && a.r0 <= row && row <= a.r1)
            {
                Some(a) => (a.r0..=a.r1).collect(),
                None => vec![row],
            };
            book.set_size(si, true, &rows, Some(h));
            emits.push(Emit::Change {
                action: "resize",
                range: (row + 1).to_string(),
            });
        }
        Drag::Fill { source } => {
            if let Some(t) = book.ui.fill_target.take()
                && t != source
            {
                book.fill(si, source, t);
                let s = book.sheet_mut();
                set_last(s, t);
                emits.push(Emit::Change {
                    action: "fill",
                    range: t.to_string(),
                });
                emits.push(Emit::Select);
            }
        }
        Drag::Cells | Drag::Rows | Drag::Cols => emits.push(Emit::Select),
        _ => {}
    }
    shell.request_redraw();
}

fn moved(
    p: &SheetProps,
    book: &mut Book,
    bounds: Rectangle,
    cursor: mouse::Cursor,
    shell: &mut Shell<'_, Message>,
) {
    let Some(pos) = cursor.position() else { return };
    book.ui.pointer = Some(pos);
    let g = geo(p, book, bounds);
    if book.ui.drag.is_none() {
        let s = book.sheet();
        let hover = (cursor.is_over(g.grid) && g.grid.contains(pos)).then(|| {
            let (r, c) = (g.row_at(s, pos.y), g.col_at(s, pos.x));
            s.merge_at(r, c).map_or((r, c), |m| (m.r0, m.c0))
        });
        let tip = |h: Option<(u32, u32)>| {
            h.is_some_and(|(r, c)| {
                let sh = book.shown(book.active, r, c);
                sh.note || sh.error.is_some() || sh.invalid
            })
        };
        if hover != book.ui.hover {
            let redraw = tip(hover) || tip(book.ui.hover);
            book.ui.hover = hover;
            if redraw {
                shell.request_redraw();
            }
        }
        return;
    }
    drag_to(p, book, &g, pos);
    shell.request_redraw();
}

/// Follows the pointer while dragging (also called while auto-scrolling).
fn drag_to(p: &SheetProps, book: &mut Book, g: &Geo, pos: Point) {
    let _ = p;
    let Some(drag) = book.ui.drag.clone() else {
        return;
    };
    let si = book.active;
    let s = book.sheet();
    let (r, c) = (g.row_at(s, pos.y), g.col_at(s, pos.x));
    match drag {
        Drag::Cells => {
            let s = book.sheet_mut();
            let anc = s.selection.anchor;
            let area = s.expand_merges(Area::new(anc.0, anc.1, r, c));
            set_last(s, area);
        }
        Drag::Rows => {
            let s = book.sheet_mut();
            let anc = s.selection.anchor.0;
            let cols = s.ncols;
            set_last(s, Area::new(anc.min(r), 0, anc.max(r), cols - 1));
        }
        Drag::Cols => {
            let s = book.sheet_mut();
            let anc = s.selection.anchor.1;
            let rows = s.rows;
            set_last(s, Area::new(0, anc.min(c), rows - 1, anc.max(c)));
        }
        Drag::ResizeCol {
            col, start, size, ..
        } => {
            let x0 = g.x_of(s, col);
            let w = (size + pos.x - start).max(8.0);
            book.ui.drag = Some(Drag::ResizeCol {
                col,
                start,
                size,
                now: x0 + w,
            });
        }
        Drag::ResizeRow {
            row, start, size, ..
        } => {
            let y0 = g.y_of(s, row);
            let h = (size + pos.y - start).max(6.0);
            book.ui.drag = Some(Drag::ResizeRow {
                row,
                start,
                size,
                now: y0 + h,
            });
        }
        Drag::Fill { source } => {
            let dr = if r > source.r1 {
                r - source.r1
            } else {
                source.r0.saturating_sub(r)
            };
            let dc = if c > source.c1 {
                c - source.c1
            } else {
                source.c0.saturating_sub(c)
            };
            book.ui.fill_target = if dr == 0 && dc == 0 {
                None
            } else if dr >= dc {
                Some(Area::new(
                    source.r0.min(r),
                    source.c0,
                    source.r1.max(r),
                    source.c1,
                ))
            } else {
                Some(Area::new(
                    source.r0,
                    source.c0.min(c),
                    source.r1,
                    source.c1.max(c),
                ))
            };
        }
        Drag::VScroll { grab } => {
            if let Some(t) = g.vthumb(s) {
                let track = g.vbar.height - t.height;
                let (_, my) = g.max_scroll(s);
                let f = ((pos.y - grab - g.vbar.y) / track.max(1.0)).clamp(0.0, 1.0);
                let mut g2 = *g;
                g2.scroll_to(book.sheet_mut(), g.sx, f * my);
            }
        }
        Drag::HScroll { grab } => {
            if let Some(t) = g.hthumb(s) {
                let track = g.hbar.width - t.width;
                let (mx, _) = g.max_scroll(s);
                let f = ((pos.x - grab - g.hbar.x) / track.max(1.0)).clamp(0.0, 1.0);
                let mut g2 = *g;
                g2.scroll_to(book.sheet_mut(), f * mx, g.sy);
            }
        }
        Drag::Point { anchor } => {
            let other = book
                .ui
                .edit
                .as_ref()
                .is_some_and(|e| e.sheet != si)
                .then(|| book.sheet().name.clone());
            if let Some(e) = book.ui.edit.as_mut() {
                e.set_point(anchor, (r, c), other.as_deref());
            }
        }
        Drag::Text => {
            let font = paint::font_for(false, false, false);
            let in_bar = book.ui.edit.as_ref().is_some_and(|e| e.in_bar);
            if in_bar {
                if let Some(e) = book.ui.edit.as_mut() {
                    let text = e.text.replace('\n', " ");
                    let at = hit(&text, font, p.text_size, pos.x - (g.input.x + paint::PAD));
                    e.cursor = at;
                }
            } else if let Some(e) = book.ui.edit.clone() {
                let er = paint::editor_rect(p, book, g, &e);
                let (font, size) = paint::edit_font(p, book, &e);
                let (start, end) = {
                    let lh = size * 1.25;
                    let line = (((pos.y - er.y - 3.5) / lh).floor().max(0.0)) as usize;
                    let mut start = 0;
                    for (i, l) in e.text.split('\n').enumerate() {
                        if i == line {
                            break;
                        }
                        start += l.len() + 1;
                    }
                    let start = start.min(e.text.len());
                    (
                        start,
                        e.text[start..]
                            .find('\n')
                            .map_or(e.text.len(), |i| start + i),
                    )
                };
                let at = start + hit(&e.text[start..end], font, size, pos.x - (er.x + paint::PAD));
                if let Some(e) = book.ui.edit.as_mut() {
                    e.cursor = at;
                }
            }
        }
    }
}

fn wheel(
    p: &SheetProps,
    book: &mut Book,
    bounds: Rectangle,
    delta: mouse::ScrollDelta,
    shell: &mut Shell<'_, Message>,
) {
    let mut g = geo(p, book, bounds);
    let (mut dx, mut dy) = match delta {
        mouse::ScrollDelta::Lines { x, y } => (-x * 60.0, -y * 3.0 * book.sheet().row_axis.default),
        mouse::ScrollDelta::Pixels { x, y } => (-x, -y),
    };
    if book.ui.modifiers.shift() && dx == 0.0 {
        std::mem::swap(&mut dx, &mut dy);
    }
    let (mx, my) = g.max_scroll(book.sheet());
    // Scrolling past the end adds rows and columns, like Sheets.
    if dy > 0.0 && g.sy + dy > my - 4.0 {
        let s = book.sheet_mut();
        let rows = s.rows;
        s.grow(rows + 100, s.ncols);
        g = geo(p, book, bounds);
    }
    if dx > 0.0 && g.sx + dx > mx - 4.0 {
        let s = book.sheet_mut();
        let cols = s.ncols;
        s.grow(s.rows, cols + 5);
        g = geo(p, book, bounds);
    }
    let (sx, sy) = (g.sx + dx, g.sy + dy);
    g.scroll_to(book.sheet_mut(), sx, sy);
    if let Some(pos) = book.ui.pointer
        && book.ui.drag.is_some()
    {
        drag_to(p, book, &g, pos);
    }
    shell.capture_event();
    shell.request_redraw();
}

/// Every frame: the caret blink, auto-scroll while dragging and the input method's area.
fn frame(
    p: &SheetProps,
    book: &mut Book,
    bounds: Rectangle,
    now: Instant,
    shell: &mut Shell<'_, Message>,
) {
    if !book.ui.focused {
        return;
    }
    let g = geo(p, book, bounds);
    if let Some(e) = book.ui.edit.clone() {
        let caret = paint::caret_rect(p, book, &g, &e);
        shell.request_input_method(&iced::advanced::InputMethod::Enabled {
            cursor: caret,
            purpose: iced::advanced::input_method::Purpose::Normal,
            preedit: None::<iced::advanced::input_method::Preedit<&str>>,
        });
        if let Some(t) = book.ui.blink {
            let n = now.duration_since(t).as_millis() / BLINK.as_millis() + 1;
            shell.request_redraw_at(window::RedrawRequest::At(t + BLINK * n as u32));
        }
    } else if book.ui.name.is_none() {
        // Typing starts editing the active cell: the input method needs to be on already.
        let s = book.sheet();
        let (r, c) = s.selection.active;
        let rect = g.cell_rect(s, r, c);
        if !ro(p, book) {
            shell.request_input_method(&iced::advanced::InputMethod::Enabled {
                cursor: rect,
                purpose: iced::advanced::input_method::Purpose::Normal,
                preedit: None::<iced::advanced::input_method::Preedit<&str>>,
            });
        }
    }
    if let Some(pos) = book.ui.pointer
        && matches!(
            book.ui.drag,
            Some(Drag::Cells | Drag::Rows | Drag::Cols | Drag::Fill { .. } | Drag::Point { .. })
        )
        && !g.grid.contains(pos)
    {
        let speed = |d: f32| (d / 2.0).clamp(-40.0, 40.0);
        let dx = if pos.x > g.grid.x + g.grid.width {
            speed(pos.x - g.grid.x - g.grid.width)
        } else if pos.x < g.grid.x + g.fw && g.sx > 0.0 {
            speed(pos.x - g.grid.x - g.fw)
        } else {
            0.0
        };
        let dy = if pos.y > g.grid.y + g.grid.height {
            speed(pos.y - g.grid.y - g.grid.height)
        } else if pos.y < g.grid.y + g.fh && g.sy > 0.0 {
            speed(pos.y - g.grid.y - g.fh)
        } else {
            0.0
        };
        if dx != 0.0 || dy != 0.0 {
            let mut g2 = g;
            if dy > 0.0 && g.sy + dy >= g.max_scroll(book.sheet()).1 {
                let s = book.sheet_mut();
                let rows = s.rows;
                s.grow(rows + 50, s.ncols);
            }
            g2.scroll_to(book.sheet_mut(), g.sx + dx, g.sy + dy);
            let clamped = Point::new(
                pos.x.clamp(g.grid.x + 1.0, g.grid.x + g.grid.width - 1.0),
                pos.y.clamp(g.grid.y + 1.0, g.grid.y + g.grid.height - 1.0),
            );
            let g3 = geo(p, book, bounds);
            drag_to(p, book, &g3, clamped);
            shell.request_redraw_at(window::RedrawRequest::At(now + Duration::from_millis(16)));
        }
    }
}

pub fn interaction(
    p: &SheetProps,
    book: &Book,
    bounds: Rectangle,
    cursor: mouse::Cursor,
) -> mouse::Interaction {
    match &book.ui.drag {
        Some(Drag::ResizeCol { .. }) => return mouse::Interaction::ResizingColumn,
        Some(Drag::ResizeRow { .. }) => return mouse::Interaction::ResizingRow,
        Some(Drag::Fill { .. }) => return mouse::Interaction::Crosshair,
        Some(Drag::Text) => return mouse::Interaction::Text,
        Some(_) => return mouse::Interaction::Cell,
        None => {}
    }
    let Some(pos) = cursor.position_over(bounds) else {
        return mouse::Interaction::default();
    };
    let g = geo(p, book, bounds);
    let s = book.sheet();
    if let Some(bar) = g.bar
        && bar.contains(pos)
    {
        return if g.input.contains(pos) || g.name_box.contains(pos) {
            mouse::Interaction::Text
        } else {
            mouse::Interaction::default()
        };
    }
    if g.headers && g.colh.contains(pos) {
        return if g.col_edge(s, pos.x).is_some() {
            mouse::Interaction::ResizingColumn
        } else {
            mouse::Interaction::Pointer
        };
    }
    if g.headers && g.rowh.contains(pos) {
        return if g.row_edge(s, pos.y).is_some() {
            mouse::Interaction::ResizingRow
        } else {
            mouse::Interaction::Pointer
        };
    }
    if g.vbar.contains(pos) || g.hbar.contains(pos) || g.corner.contains(pos) {
        return mouse::Interaction::default();
    }
    if let Some(e) = &book.ui.edit
        && e.sheet == book.active
        && paint::editor_rect(p, book, &g, e).contains(pos)
    {
        return mouse::Interaction::Text;
    }
    if !ro(p, book)
        && let Some(h) = paint::fill_handle(&g, s)
        && (Rectangle {
            x: h.x - 3.0,
            y: h.y - 3.0,
            width: h.width + 6.0,
            height: h.height + 6.0,
        })
        .contains(pos)
    {
        return mouse::Interaction::Crosshair;
    }
    if g.grid.contains(pos) {
        let (r, c) = (g.row_at(s, pos.y), g.col_at(s, pos.x));
        if let Some(f) = &s.filter
            && r == f.area.r0
            && f.area.c0 <= c
            && c <= f.area.c1
            && paint::filter_button(&g, s, r, c).contains(pos)
        {
            return mouse::Interaction::Pointer;
        }
        let sh = book.shown(book.active, r, c);
        if sh.checkbox.is_some()
            || (sh.dropdown && pos.x > g.cell_rect(s, r, c).x + g.cell_rect(s, r, c).width - 20.0)
        {
            return mouse::Interaction::Pointer;
        }
        return mouse::Interaction::Cell;
    }
    mouse::Interaction::default()
}

// --- Keyboard ------------------------------------------------------------------------------

fn name_key(book: &mut Book, key: &Key, text: Option<&str>) -> bool {
    let Some(name) = book.ui.name.as_mut() else {
        return false;
    };
    match key {
        Key::Named(Named::Escape) => book.ui.name = None,
        Key::Named(Named::Backspace) => {
            name.pop();
        }
        Key::Named(Named::Enter) => {
            let target = std::mem::take(name);
            book.ui.name = None;
            let (sheet, rest) = split_sheet(target.trim());
            let si = match sheet {
                Some(n) => match book.sheet_index(&n) {
                    Some(i) => i,
                    None => return true,
                },
                None => book.active,
            };
            if let Some(a) = parse_area(&rest.to_ascii_uppercase()) {
                book.active = si;
                let s = &mut book.sheets[si];
                s.grow(a.r1.min(MAX_ROWS - 2) + 2, a.c1.min(MAX_COLS - 2) + 2);
                let a = a.clamp(s.rows, s.ncols).unwrap_or(a);
                s.selection = Selection {
                    ranges: vec![a],
                    active: (a.r0, a.c0),
                    anchor: (a.r0, a.c0),
                };
                book.ui.reveal = true;
            }
        }
        _ => match text {
            Some(t) if !t.chars().any(|c| c.is_control()) => name.push_str(t),
            _ => return false,
        },
    }
    paint::restart_blink(book);
    true
}

#[allow(clippy::too_many_arguments)]
fn edit_key(
    p: &SheetProps,
    book: &mut Book,
    bounds: Rectangle,
    key: &Key,
    m: Modifiers,
    text: Option<&str>,
    clip: &mut dyn Clipboard,
    emits: &mut Vec<Emit>,
) -> bool {
    let g = geo(p, book, bounds);
    let suggestions = paint::suggest_box(p, book, &g)
        .map(|(_, rows)| rows.into_iter().map(|r| r.1).collect::<Vec<_>>())
        .unwrap_or_default();
    let si = book.active;
    let ctrl = m.command();
    let Some(e) = book.ui.edit.as_mut() else {
        return false;
    };
    let pointing = e.enter_mode && !e.in_bar && e.can_point();
    match key {
        Key::Named(Named::Escape) => {
            if !suggestions.is_empty() {
                e.closed = true;
            } else {
                book.ui.edit = None;
                book.ui.preedit = None;
            }
        }
        Key::Named(Named::Enter) if m.alt() => e.insert("\n"),
        Key::Named(Named::Enter) | Key::Named(Named::Tab)
            if !suggestions.is_empty() && !m.shift() =>
        {
            let name = suggestions[e.suggest % suggestions.len()];
            e.accept(name);
        }
        Key::Named(Named::Enter) => {
            if ctrl {
                commit_all(book, emits);
            } else if commit(book, emits) {
                let at = enter_move(book, if m.shift() { -1 } else { 1 }, 0);
                reveal(p, book, bounds, at);
                emits.push(Emit::Select);
            }
        }
        Key::Named(Named::Tab) => {
            if commit(book, emits) {
                let at = enter_move(book, 0, if m.shift() { -1 } else { 1 });
                reveal(p, book, bounds, at);
                emits.push(Emit::Select);
            }
        }
        Key::Named(Named::ArrowUp | Named::ArrowDown) if !suggestions.is_empty() => {
            let n = suggestions.len();
            e.suggest = if matches!(key, Key::Named(Named::ArrowDown)) {
                (e.suggest + 1) % n
            } else {
                (e.suggest + n - 1) % n
            };
        }
        Key::Named(
            arrow @ (Named::ArrowUp | Named::ArrowDown | Named::ArrowLeft | Named::ArrowRight),
        ) if e.enter_mode && !e.in_bar => {
            let (dr, dc) = match arrow {
                Named::ArrowUp => (-1, 0),
                Named::ArrowDown => (1, 0),
                Named::ArrowLeft => (0, -1),
                _ => (0, 1),
            };
            if pointing && e.sheet == si {
                // Pick a reference with the arrows.
                let s = &book.sheets[si];
                let (anchor, cur) = match &e.point {
                    Some(pt) => (pt.anchor, pt.cur),
                    None => ((e.row, e.col), (e.row, e.col)),
                };
                let n = if ctrl {
                    ops::jump(s, cur.0, cur.1, dr, dc)
                } else {
                    step(s, cur.0, cur.1, dr, dc)
                };
                let anchor = if m.shift() { anchor } else { n };
                e.set_point(anchor, n, None);
                let mut g = g;
                g.reveal(&mut book.sheets[si], n.0, n.1);
            } else if commit(book, emits) {
                let at = move_sel(book, dr, dc, false, false);
                reveal(p, book, bounds, at);
                emits.push(Emit::Select);
            }
        }
        Key::Named(Named::ArrowLeft) => e.left(ctrl, m.shift()),
        Key::Named(Named::ArrowRight) => e.right(ctrl, m.shift()),
        Key::Named(Named::ArrowUp) => {
            let (start, _) = e.line_bounds();
            if start == 0 {
                e.move_to(0, m.shift());
            } else {
                let col = e.cursor - start;
                let pstart = e.text[..start - 1].rfind('\n').map_or(0, |i| i + 1);
                let at = (pstart + col).min(start - 1);
                let at = floor_char(&e.text, at);
                e.move_to(at, m.shift());
            }
        }
        Key::Named(Named::ArrowDown) => {
            let (start, end) = e.line_bounds();
            if end == e.text.len() {
                let n = e.text.len();
                e.move_to(n, m.shift());
            } else {
                let col = e.cursor - start;
                let nend = e.text[end + 1..]
                    .find('\n')
                    .map_or(e.text.len(), |i| end + 1 + i);
                let at = floor_char(&e.text, (end + 1 + col).min(nend));
                e.move_to(at, m.shift());
            }
        }
        Key::Named(Named::Home) => {
            let at = if ctrl { 0 } else { e.line_bounds().0 };
            e.move_to(at, m.shift());
        }
        Key::Named(Named::End) => {
            let at = if ctrl {
                e.text.len()
            } else {
                e.line_bounds().1
            };
            e.move_to(at, m.shift());
        }
        Key::Named(Named::Backspace) => e.backspace(ctrl),
        Key::Named(Named::Delete) => e.delete(ctrl),
        Key::Named(Named::F2) => e.enter_mode = !e.enter_mode,
        Key::Named(Named::F4) => e.toggle_absolute(),
        Key::Character(ch) if ctrl => match ch.as_str() {
            "a" => {
                e.anchor = 0;
                e.cursor = e.text.len();
            }
            "c" | "x" => {
                let sel = e.selected().to_string();
                if !sel.is_empty() {
                    clip.write(clipboard::Kind::Standard, sel);
                    if ch.as_str() == "x" {
                        e.backspace(false);
                    }
                }
            }
            "v" => {
                if let Some(t) = clip.read(clipboard::Kind::Standard) {
                    let t = t.trim_end_matches(['\n', '\r']);
                    e.insert(t);
                }
            }
            "z" => {
                let o = e.original.clone();
                let n = o.len();
                e.text = o;
                e.cursor = n;
                e.anchor = n;
                e.point = None;
            }
            ";" => {
                let t = today_text(book, m.shift());
                if let Some(e) = book.ui.edit.as_mut() {
                    e.insert(&t);
                }
            }
            _ => return false,
        },
        _ => match text {
            Some(t) if !t.chars().any(|c| c.is_control()) && !ctrl => {
                e.insert(t);
            }
            _ => return false,
        },
    }
    paint::restart_blink(book);
    if book.ui.edit.is_some() {
        book.ui.reveal = false;
    }
    true
}

fn floor_char(text: &str, mut i: usize) -> usize {
    while i > 0 && !text.is_char_boundary(i) {
        i -= 1;
    }
    i
}

fn today_text(book: &Book, time: bool) -> String {
    let now = crate::sheet::value::now_serial(book.utc_offset);
    if time {
        crate::sheet::format::format(&Value::Number(now.fract()), Some("h:mm")).0
    } else {
        crate::sheet::format::format(&Value::Number(now.floor()), Some("yyyy-mm-dd")).0
    }
}

#[allow(clippy::too_many_arguments)]
fn grid_key(
    p: &SheetProps,
    book: &mut Book,
    bounds: Rectangle,
    key: &Key,
    modified: &Key,
    m: Modifiers,
    text: Option<&str>,
    clip: &mut dyn Clipboard,
    emits: &mut Vec<Emit>,
) -> bool {
    let ctrl = m.command();
    let shift = m.shift();
    let readonly = ro(p, book);
    let si = book.active;
    let select = |emits: &mut Vec<Emit>| emits.push(Emit::Select);
    match key {
        Key::Named(
            arrow @ (Named::ArrowUp | Named::ArrowDown | Named::ArrowLeft | Named::ArrowRight),
        ) => {
            if m.alt() && *arrow == Named::ArrowDown {
                open_dropdown(p, book, bounds, emits);
                return true;
            }
            let (dr, dc) = match arrow {
                Named::ArrowUp => (-1, 0),
                Named::ArrowDown => (1, 0),
                Named::ArrowLeft => (0, -1),
                _ => (0, 1),
            };
            let at = move_sel(book, dr, dc, shift, ctrl);
            reveal(p, book, bounds, at);
            select(emits);
        }
        Key::Named(Named::Enter) => {
            if ctrl {
                return false;
            }
            let at = enter_move(book, if shift { -1 } else { 1 }, 0);
            reveal(p, book, bounds, at);
            select(emits);
        }
        Key::Named(Named::Tab) => {
            let at = enter_move(book, 0, if shift { -1 } else { 1 });
            reveal(p, book, bounds, at);
            select(emits);
        }
        Key::Named(Named::Home) => {
            let s = book.sheet_mut();
            let (r, _) = s.selection.active;
            let to = if ctrl {
                (s.freeze.0.min(s.rows - 1), s.freeze.1.min(s.ncols - 1))
            } else {
                (r, 0)
            };
            let to = if ctrl && s.freeze == (0, 0) {
                (0, 0)
            } else {
                to
            };
            if shift {
                let anc = s.selection.anchor;
                let a = s.expand_merges(Area::new(anc.0, anc.1, to.0, to.1));
                set_last(s, a);
            } else {
                select_one(s, to.0, to.1);
            }
            reveal(p, book, bounds, to);
            select(emits);
        }
        Key::Named(Named::End) => {
            let s = book.sheet_mut();
            let (er, ec) = s.extent();
            let (r, c) = s.selection.active;
            let to = if ctrl {
                (er.saturating_sub(1), ec.saturating_sub(1))
            } else {
                (r, ops::jump(s, r, c, 0, 1).1)
            };
            if shift {
                let anc = s.selection.anchor;
                let a = s.expand_merges(Area::new(anc.0, anc.1, to.0, to.1));
                set_last(s, a);
            } else {
                select_one(s, to.0, to.1);
            }
            reveal(p, book, bounds, to);
            select(emits);
        }
        Key::Named(page @ (Named::PageDown | Named::PageUp)) => {
            let g = geo(p, book, bounds);
            let s = book.sheet();
            let (a, b) = g.scroll_rows(s);
            let n = (b - a).saturating_sub(1).max(1) as i32;
            let dir = if *page == Named::PageDown { 1 } else { -1 };
            let mut at = (0, 0);
            for _ in 0..n {
                at = move_sel(book, dir, 0, shift, false);
            }
            let sy = g.sy + dir as f32 * (g.grid.height - g.fh);
            let mut g2 = geo(p, book, bounds);
            let sx = g2.sx;
            g2.scroll_to(book.sheet_mut(), sx, sy);
            reveal(p, book, bounds, at);
            select(emits);
        }
        Key::Named(Named::F2) => {
            if readonly {
                return false;
            }
            begin_edit(book, None, false);
        }
        Key::Named(Named::Delete) => {
            if readonly {
                return false;
            }
            let areas = book.sheet().selection.ranges.clone();
            book.clear(si, &areas, "contents");
            emits.push(Emit::Change {
                action: "clear",
                range: super::selection_text(book.sheet()),
            });
        }
        Key::Named(Named::Backspace) => {
            if readonly {
                return false;
            }
            let (r, c) = book.sheet().selection.active;
            book.clear(si, &[Area::cell(r, c)], "contents");
            emits.push(Emit::Change {
                action: "clear",
                range: edit::address(r, c),
            });
            begin_edit(book, Some(String::new()), true);
        }
        Key::Named(Named::Escape) => {
            if book.clip.is_none() {
                return false;
            }
            book.clip = None;
        }
        Key::Named(Named::Space) if ctrl || shift && !ctrl => {
            let s = book.sheet_mut();
            let a = s.selection.range();
            let active = s.selection.active;
            if ctrl && shift {
                let all = Area::new(0, 0, s.rows - 1, s.ncols - 1);
                s.selection = Selection {
                    ranges: vec![all],
                    active,
                    anchor: active,
                };
            } else if ctrl {
                select_cols(s, a.c0, a.c1, active);
            } else {
                select_rows(s, a.r0, a.r1, active);
            }
            select(emits);
        }
        Key::Named(Named::Space)
            if !readonly
                && book
                    .shown(
                        si,
                        book.sheet().selection.active.0,
                        book.sheet().selection.active.1,
                    )
                    .checkbox
                    .is_some() =>
        {
            let (r, c) = book.sheet().selection.active;
            let v = book.sheet().value(r, c);
            book.set_value(si, r, c, Value::Bool(!matches!(v, Value::Bool(true))));
            emits.push(Emit::Change {
                action: "edit",
                range: edit::address(r, c),
            });
        }
        Key::Character(ch) if ctrl => {
            let k = ch.as_str().to_ascii_lowercase();
            let modk = match modified {
                Key::Character(c) => c.to_string(),
                _ => String::new(),
            };
            return ctrl_key(p, book, bounds, &k, &modk, m, clip, emits);
        }
        Key::Character(ch) if m.alt() && !ctrl && ch.as_str() == "=" => {
            if readonly {
                return false;
            }
            autosum(book);
        }
        _ => match text {
            Some(t) if !t.chars().any(|c| c.is_control()) && !ctrl && !m.alt() && !t.is_empty() => {
                if readonly {
                    return false;
                }
                begin_edit(book, Some(t.to_string()), true);
            }
            _ => return false,
        },
    }
    true
}

#[allow(clippy::too_many_arguments)]
fn ctrl_key(
    p: &SheetProps,
    book: &mut Book,
    bounds: Rectangle,
    k: &str,
    modk: &str,
    m: Modifiers,
    clip: &mut dyn Clipboard,
    emits: &mut Vec<Emit>,
) -> bool {
    let shift = m.shift();
    let si = book.active;
    let readonly = ro(p, book);
    let areas = book.sheet().selection.ranges.clone();
    let range = book.sheet().selection.range();
    let change = |emits: &mut Vec<Emit>, action: &'static str, book: &Book| {
        emits.push(Emit::Change {
            action,
            range: super::selection_text(book.sheet()),
        });
    };
    // Number formats (Excel): Ctrl+Shift+1 number, 2 time, 3 date, 4 currency, 5 percent, 6 scientific, ~ general.
    if shift && !readonly {
        let fmt: Option<Option<&str>> = match (k, modk) {
            ("1", _) | (_, "!") => Some(Some("#,##0.00")),
            ("2", _) | (_, "@") => Some(Some("h:mm AM/PM")),
            ("3", _) | (_, "#") => Some(Some("d-mmm-yy")),
            ("4", _) | (_, "$") => Some(Some("$#,##0.00")),
            ("5", _) | (_, "%") => Some(Some("0%")),
            ("6", _) | (_, "^") => Some(Some("0.00E+00")),
            ("`", _) | (_, "~") => Some(None),
            _ => None,
        };
        if let Some(fmt) = fmt {
            book.restyle(si, &areas, |st| st.format = fmt.map(Into::into));
            change(emits, "format", book);
            return true;
        }
    }
    match k {
        "c" | "x" => {
            let cut = k == "x" && !readonly;
            let text = book.copy(si, range, cut);
            clip.write(clipboard::Kind::Standard, text);
        }
        "v" => {
            if readonly {
                return false;
            }
            let Some(text) = clip.read(clipboard::Kind::Standard) else {
                return true;
            };
            let area = book.paste(si, range, &text, shift);
            let s = book.sheet_mut();
            s.grow(area.r1 + 2, area.c1 + 2);
            s.selection = Selection {
                ranges: vec![area],
                active: (area.r0, area.c0),
                anchor: (area.r0, area.c0),
            };
            change(emits, "paste", book);
            emits.push(Emit::Select);
        }
        "z" if !shift => {
            if readonly || !book.undo() {
                return readonly;
            }
            change(emits, "undo", book);
        }
        "y" | "z" => {
            if readonly || !book.redo() {
                return readonly;
            }
            change(emits, "redo", book);
        }
        "a" => {
            let s = book.sheet_mut();
            let (r, c) = s.selection.active;
            let region = ops::data_region(s, r, c);
            let all = Area::new(0, 0, s.rows - 1, s.ncols - 1);
            let target = if s.selection.ranges.len() == 1
                && s.selection.range() != region
                && !region.is_cell()
            {
                region
            } else {
                all
            };
            let active = s.selection.active;
            s.selection = Selection {
                ranges: vec![target],
                active,
                anchor: active,
            };
            emits.push(Emit::Select);
        }
        "b" | "i" | "u" | "5" if !readonly => {
            let st = book
                .style(book.sheet().style_of(range.r0, range.c0))
                .clone();
            match k {
                "b" => book.restyle(si, &areas, |x| x.bold = !st.bold),
                "i" => book.restyle(si, &areas, |x| x.italic = !st.italic),
                "u" => book.restyle(si, &areas, |x| x.underline = !st.underline),
                _ => book.restyle(si, &areas, |x| x.strike = !st.strike),
            }
            change(emits, "format", book);
        }
        "\\" if !readonly => {
            book.restyle(si, &areas, |x| {
                let format = x.format.clone();
                *x = Style::default();
                x.format = format;
            });
            change(emits, "format", book);
        }
        "d" | "r" if !readonly => {
            let down = k == "d";
            let (src, target) = if down {
                if range.rows() > 1 {
                    (Area::new(range.r0, range.c0, range.r0, range.c1), range)
                } else if range.r0 > 0 {
                    (
                        Area::new(range.r0 - 1, range.c0, range.r0 - 1, range.c1),
                        Area::new(range.r0 - 1, range.c0, range.r1, range.c1),
                    )
                } else {
                    return true;
                }
            } else if range.cols() > 1 {
                (Area::new(range.r0, range.c0, range.r1, range.c0), range)
            } else if range.c0 > 0 {
                (
                    Area::new(range.r0, range.c0 - 1, range.r1, range.c0 - 1),
                    Area::new(range.r0, range.c0 - 1, range.r1, range.c1),
                )
            } else {
                return true;
            };
            // A plain copy, like Excel (no series).
            let s = &book.sheets[si];
            let mut cells = Vec::new();
            for r in target.r0..=target.r1 {
                for c in target.c0..=target.c1 {
                    if src.contains(r, c) {
                        continue;
                    }
                    let (sr, sc) = if down { (src.r0, c) } else { (r, src.c0) };
                    let cell = s
                        .cell(sr, sc)
                        .map(|x| ops::moved_cell(x, r as i64 - sr as i64, c as i64 - sc as i64));
                    cells.push((r, c, cell));
                }
            }
            book.write(si, cells);
            change(emits, "fill", book);
        }
        ";" if !readonly => {
            let t = today_text(book, shift);
            begin_edit(book, Some(t), true);
        }
        "f" => emits.push(Emit::Find("find")),
        "h" => emits.push(Emit::Find("replace")),
        "l" if shift && !readonly => {
            if book.sheet().filter.is_some() {
                book.set_filter(si, None);
            } else {
                let (r, c) = book.sheet().selection.active;
                let region = if range.is_cell() {
                    ops::data_region(book.sheet(), r, c)
                } else {
                    range
                };
                book.set_filter(si, Some(region));
            }
            change(emits, "filter", book);
        }
        "home" => {}
        _ => return false,
    }
    let _ = bounds;
    true
}

/// Alt+=: a SUM of the numbers above (or to the left of) the active cell.
fn autosum(book: &mut Book) {
    let s = book.sheet();
    let (r, c) = s.selection.active;
    let num = |r: u32, c: u32| matches!(s.value(r, c), Value::Number(_));
    let mut text = String::from("=SUM()");
    if r > 0 && num(r - 1, c) {
        let mut top = r - 1;
        while top > 0 && num(top - 1, c) {
            top -= 1;
        }
        text = format!("=SUM({})", Area::new(top, c, r - 1, c));
    } else if c > 0 && num(r, c - 1) {
        let mut left = c - 1;
        while left > 0 && num(r, left - 1) {
            left -= 1;
        }
        text = format!("=SUM({})", Area::new(r, left, r, c - 1));
    }
    begin_edit(book, Some(text.clone()), false);
    if text == "=SUM()"
        && let Some(e) = book.ui.edit.as_mut()
    {
        e.cursor = 5;
        e.anchor = 5;
    }
}
