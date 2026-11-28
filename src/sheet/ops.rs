//! Workbook operations: rows and columns, sorting, filters, copy and paste, autofill,
//! find and replace, merges and sheets.

use std::collections::{BTreeMap, HashMap, HashSet};
use std::sync::Arc;

use super::addr::{self, Area, MAX_COLS, MAX_ROWS};
use super::formula::{self, Ref, RefKind};
use super::functions::Criterion;
use super::model::{Book, Cell, Clip, FormulaCell, Input, Sheet};
use super::value::{self, Value};

/// A copy of a cell moved by `(dr, dc)`: its formula's relative references move with it.
pub fn moved_cell(cell: &Cell, dr: i64, dc: i64) -> Cell {
    let mut out = cell.clone();
    if let Some(f) = cell.formula()
        && (dr != 0 || dc != 0)
    {
        let src = formula::rewrite_refs(&f.src, |r| r.offset(dr, dc));
        out.input = Input::Formula(Arc::new(FormulaCell::new(&src)));
    }
    out
}

fn adjust_area_insert(a: Area, rows: bool, at: u32, n: u32) -> Area {
    let mut a = a;
    if rows {
        if a.r0 >= at {
            a.r0 = (a.r0 + n).min(MAX_ROWS - 1);
        }
        if a.r1 >= at && !(a.r1 == MAX_ROWS - 1) {
            a.r1 = (a.r1 + n).min(MAX_ROWS - 1);
        }
    } else {
        if a.c0 >= at {
            a.c0 = (a.c0 + n).min(MAX_COLS - 1);
        }
        if a.c1 >= at && !(a.c1 == MAX_COLS - 1) {
            a.c1 = (a.c1 + n).min(MAX_COLS - 1);
        }
    }
    a
}

fn adjust_area_delete(a: Area, rows: bool, at: u32, n: u32) -> Option<Area> {
    let end = at + n; // exclusive
    let (lo, hi) = if rows { (a.r0, a.r1) } else { (a.c0, a.c1) };
    let whole = if rows {
        a.r1 == MAX_ROWS - 1 && a.r0 == 0
    } else {
        a.c1 == MAX_COLS - 1 && a.c0 == 0
    };
    if whole {
        return Some(a);
    }
    if lo >= at && hi < end {
        return None;
    }
    let map = |v: u32, is_end: bool| -> u32 {
        if v < at {
            v
        } else if v >= end {
            v - n
        } else if is_end {
            at.saturating_sub(1).max(if at == 0 { 0 } else { at - 1 })
        } else {
            at
        }
    };
    let (nlo, nhi) = (map(lo, false), map(hi, true));
    let (nlo, nhi) = if hi >= end && lo >= at && lo < end {
        (at, hi - n)
    } else {
        (nlo, nhi)
    };
    let mut out = a;
    if rows {
        out.r0 = nlo;
        out.r1 = nhi.max(nlo);
    } else {
        out.c0 = nlo;
        out.c1 = nhi.max(nlo);
    }
    Some(out)
}

impl Book {
    // --- Rows and columns ------------------------------------------------

    /// Rewrites every formula of the book that points at `sheet` with `f`.
    fn rewrite_formulas(&mut self, sheet: usize, f: &dyn Fn(&Ref) -> Option<Option<Ref>>) {
        let target = self.sheets[sheet].name.clone();
        for si in 0..self.sheets.len() {
            let positions: Vec<(u32, u32)> = self.sheets[si].formulas.iter().copied().collect();
            for (c, r) in positions {
                let Some(cell) = self.sheets[si].cell(r, c) else {
                    continue;
                };
                let Some(fc) = cell.formula() else { continue };
                let src = formula::rewrite_refs(&fc.src, |rf| {
                    let points = match &rf.sheet {
                        Some(name) => name.eq_ignore_ascii_case(&target),
                        None => si == sheet,
                    };
                    if !points {
                        return Some(rf.clone());
                    }
                    match f(rf) {
                        Some(new) => new,
                        None => Some(rf.clone()),
                    }
                });
                if src != *fc.src {
                    let new = Input::Formula(Arc::new(FormulaCell::new(&src)));
                    self.sheets[si].cell_mut(r, c).input = new;
                }
            }
        }
        // Conditional formats and validations with formulas live on their own sheet.
    }

    pub fn insert(&mut self, sheet: usize, rows: bool, at: u32, n: u32) {
        if n == 0 {
            return;
        }
        self.structural(|b| {
            {
                let s = &mut b.sheets[sheet];
                if rows {
                    for col in &mut s.cols {
                        let tail = col.split_off(&at);
                        for (r, cell) in tail {
                            if r + n < MAX_ROWS {
                                col.insert(r + n, cell);
                            }
                        }
                    }
                    s.row_axis.shift(at, n as i64);
                    s.rows = (s.rows + n).min(MAX_ROWS);
                } else {
                    let at_i = (at as usize).min(s.cols.len());
                    for _ in 0..n {
                        if at_i <= s.cols.len() {
                            s.cols.insert(at_i, BTreeMap::new());
                        }
                    }
                    s.cols.truncate(MAX_COLS as usize);
                    s.col_axis.shift(at, n as i64);
                    s.ncols = (s.ncols + n).min(MAX_COLS);
                }
                s.formulas = s
                    .cols
                    .iter()
                    .enumerate()
                    .flat_map(|(c, m)| {
                        m.iter()
                            .filter(|(_, cell)| cell.is_formula())
                            .map(move |(&r, _)| (c as u32, r))
                    })
                    .collect();
                s.merges = s
                    .merges
                    .iter()
                    .map(|a| adjust_area_insert(*a, rows, at, n))
                    .collect();
                for cf in &mut s.conditional {
                    cf.area = adjust_area_insert(cf.area, rows, at, n);
                }
                for v in &mut s.validations {
                    v.area = adjust_area_insert(v.area, rows, at, n);
                }
                if let Some(f) = &mut s.filter {
                    f.area = adjust_area_insert(f.area, rows, at, n);
                    if !rows {
                        f.hidden = f
                            .hidden
                            .drain()
                            .map(|(c, v)| (if c >= at { c + n } else { c }, v))
                            .collect();
                        f.conditions = f
                            .conditions
                            .drain()
                            .map(|(c, v)| (if c >= at { c + n } else { c }, v))
                            .collect();
                    }
                }
            }
            b.rewrite_formulas(sheet, &|r: &Ref| {
                let mut out = r.clone();
                match (rows, r.kind) {
                    (true, RefKind::Cols) | (false, RefKind::Rows) => return None,
                    _ => {}
                }
                out.area = adjust_area_insert(r.area, rows, at, n);
                Some(Some(out))
            });
        });
    }

    pub fn delete(&mut self, sheet: usize, rows: bool, at: u32, n: u32) {
        if n == 0 {
            return;
        }
        self.structural(|b| {
            {
                let s = &mut b.sheets[sheet];
                let end = at + n;
                if rows {
                    for col in &mut s.cols {
                        let mut tail = col.split_off(&at);
                        let rest = tail.split_off(&end);
                        for (r, cell) in rest {
                            col.insert(r - n, cell);
                        }
                    }
                    s.row_axis.shift(at, -(n as i64));
                    s.rows = s.rows.saturating_sub(n).max(1);
                } else {
                    let lo = (at as usize).min(s.cols.len());
                    let hi = (end as usize).min(s.cols.len());
                    s.cols.drain(lo..hi);
                    s.col_axis.shift(at, -(n as i64));
                    s.ncols = s.ncols.saturating_sub(n).max(1);
                }
                s.formulas = s
                    .cols
                    .iter()
                    .enumerate()
                    .flat_map(|(c, m)| {
                        m.iter()
                            .filter(|(_, cell)| cell.is_formula())
                            .map(move |(&r, _)| (c as u32, r))
                    })
                    .collect();
                s.merges = s
                    .merges
                    .iter()
                    .filter_map(|a| adjust_area_delete(*a, rows, at, n))
                    .filter(|a| !a.is_cell())
                    .collect();
                s.conditional
                    .retain_mut(|cf| match adjust_area_delete(cf.area, rows, at, n) {
                        Some(a) => {
                            cf.area = a;
                            true
                        }
                        None => false,
                    });
                s.validations
                    .retain_mut(|v| match adjust_area_delete(v.area, rows, at, n) {
                        Some(a) => {
                            v.area = a;
                            true
                        }
                        None => false,
                    });
                if let Some(f) = &mut s.filter {
                    match adjust_area_delete(f.area, rows, at, n) {
                        Some(a) => f.area = a,
                        None => s.filter = None,
                    }
                }
                let sel = &mut s.selection;
                let (r, c) = sel.active;
                let (r, c) = if rows {
                    (r.min(s.rows - 1), c)
                } else {
                    (r, c.min(s.ncols - 1))
                };
                *sel = super::model::Selection {
                    ranges: vec![Area::cell(r, c)],
                    active: (r, c),
                    anchor: (r, c),
                };
            }
            b.rewrite_formulas(sheet, &|r: &Ref| {
                match (rows, r.kind) {
                    (true, RefKind::Cols) | (false, RefKind::Rows) => return None,
                    _ => {}
                }
                let mut out = r.clone();
                match adjust_area_delete(r.area, rows, at, n) {
                    Some(a) => {
                        out.area = a;
                        if r.kind == RefKind::Cell && !a.is_cell() {
                            out.area = Area::cell(a.r0, a.c0);
                        }
                        Some(Some(out))
                    }
                    None => Some(None),
                }
            });
        });
    }

    pub fn set_size(&mut self, sheet: usize, rows: bool, indexes: &[u32], size: Option<f32>) {
        self.structural(|b| {
            let s = &mut b.sheets[sheet];
            let axis = if rows {
                &mut s.row_axis
            } else {
                &mut s.col_axis
            };
            for &i in indexes {
                match size {
                    Some(v) => {
                        axis.sizes.insert(i, v.max(2.0));
                    }
                    None => {
                        axis.sizes.remove(&i);
                    }
                }
            }
            axis.rebuild();
        });
    }

    pub fn set_hidden(&mut self, sheet: usize, rows: bool, indexes: &[u32], hidden: bool) {
        self.structural(|b| {
            let s = &mut b.sheets[sheet];
            let axis = if rows {
                &mut s.row_axis
            } else {
                &mut s.col_axis
            };
            for &i in indexes {
                if hidden {
                    axis.hidden.insert(i);
                } else {
                    axis.hidden.remove(&i);
                }
            }
            axis.rebuild();
        });
    }

    // --- Merges ------------------------------------------------------------

    pub fn merge(&mut self, sheet: usize, area: Area) {
        if area.is_cell() {
            return;
        }
        self.structural(|b| {
            let s = &mut b.sheets[sheet];
            s.merges.retain(|m| !m.intersects(&area));
            // Only the first cell keeps its content.
            for r in area.r0..=area.r1 {
                for c in area.c0..=area.c1 {
                    if (r, c) != (area.r0, area.c0)
                        && let Some(cell) = s.cols.get_mut(c as usize).and_then(|m| m.get_mut(&r))
                    {
                        cell.input = Input::Empty;
                        cell.value = Value::Empty;
                        s.formulas.remove(&(c, r));
                    }
                }
            }
            s.merges.push(area);
        });
    }

    pub fn unmerge(&mut self, sheet: usize, area: Area) {
        self.structural(|b| b.sheets[sheet].merges.retain(|m| !m.intersects(&area)));
    }

    // --- Sorting -------------------------------------------------------------

    /// Sorts the rows of `area` by the given columns (absolute indexes, `true` = descending).
    pub fn sort(&mut self, sheet: usize, area: Area, keys: &[(u32, bool)], header: bool) {
        let s = &self.sheets[sheet];
        let Some(area) = area.clamp(s.rows, s.ncols) else {
            return;
        };
        let area = if area.whole_cols() || area.r1 >= s.extent().0 {
            Area::new(
                area.r0,
                area.c0,
                area.r1.min(s.extent().0.saturating_sub(1)).max(area.r0),
                area.c1,
            )
        } else {
            area
        };
        let first = if header { area.r0 + 1 } else { area.r0 };
        if first > area.r1 {
            return;
        }
        let mut rows: Vec<u32> = (first..=area.r1).collect();
        rows.sort_by(|&x, &y| {
            for &(col, desc) in keys {
                let (vx, vy) = (s.value(x, col), s.value(y, col));
                // Blanks always go last.
                let o = match (vx.is_empty(), vy.is_empty()) {
                    (true, false) => std::cmp::Ordering::Greater,
                    (false, true) => std::cmp::Ordering::Less,
                    _ => {
                        let o = vx.sort_cmp(&vy);
                        if desc { o.reverse() } else { o }
                    }
                };
                if o != std::cmp::Ordering::Equal {
                    return o;
                }
            }
            x.cmp(&y)
        });
        let mut cells = Vec::new();
        for (i, &src) in rows.iter().enumerate() {
            let dst = first + i as u32;
            for c in area.c0..=area.c1 {
                let cell = s
                    .cell(src, c)
                    .map(|cell| moved_cell(cell, dst as i64 - src as i64, 0));
                if src != dst || cell.is_some() {
                    cells.push((dst, c, cell));
                }
            }
        }
        self.write(sheet, cells);
    }

    // --- Filters ---------------------------------------------------------------

    pub fn apply_filter(&mut self, sheet: usize) {
        let s = &mut self.sheets[sheet];
        s.row_axis.filtered.clear();
        if let Some(f) = &s.filter {
            let crit: HashMap<u32, Criterion> = f
                .conditions
                .iter()
                .map(|(&c, t)| (c, Criterion::new(&Value::text(t.as_str()))))
                .collect();
            let last = f.area.r1.min(s.extent().0.max(f.area.r0 + 1) - 1);
            let mut hide = Vec::new();
            for r in f.area.r0 + 1..=last {
                let hidden = f
                    .hidden
                    .iter()
                    .any(|(&c, vals)| vals.contains(&shown(s, &self.styles, r, c)))
                    || crit.iter().any(|(&c, cr)| !cr.matches(&s.value(r, c)));
                if hidden {
                    hide.push(r);
                }
            }
            s.row_axis.filtered.extend(hide);
        }
        s.row_axis.rebuild();
        self.touch();
    }

    pub fn set_filter(&mut self, sheet: usize, area: Option<Area>) {
        self.structural(|b| {
            let s = &mut b.sheets[sheet];
            s.filter = area.map(|area| {
                let area = if area.is_cell() {
                    data_region(s, area.r0, area.c0)
                } else {
                    area
                };
                let (rows, _) = s.extent();
                let area = Area::new(
                    area.r0,
                    area.c0,
                    area.r1.min(rows.max(area.r0 + 1) - 1).max(area.r0),
                    area.c1,
                );
                super::model::Filter {
                    area,
                    ..Default::default()
                }
            });
        });
        self.apply_filter(sheet);
    }

    /// The distinct values (as shown) of a filter column and whether each is visible.
    pub fn filter_values(&self, sheet: usize, col: u32) -> Vec<(String, bool)> {
        let s = &self.sheets[sheet];
        let Some(f) = &s.filter else {
            return Vec::new();
        };
        let hidden = f.hidden.get(&col);
        let mut seen = HashSet::new();
        let mut out = Vec::new();
        for r in f.area.r0 + 1..=f.area.r1 {
            let t = shown(s, &self.styles, r, col);
            if seen.insert(t.clone()) {
                let vis = hidden.is_none_or(|h| !h.contains(&t));
                out.push((t, vis));
            }
        }
        out.sort_by(|a, b| {
            let na = value::parse_number(&a.0);
            let nb = value::parse_number(&b.0);
            match (na, nb) {
                (Some(x), Some(y)) => x.0.partial_cmp(&y.0).unwrap_or(std::cmp::Ordering::Equal),
                (Some(_), None) => std::cmp::Ordering::Less,
                (None, Some(_)) => std::cmp::Ordering::Greater,
                _ => value::cmp_text(&a.0, &b.0),
            }
        });
        out
    }

    // --- Clipboard -------------------------------------------------------------

    /// Text of each cell as shown, tab-separated (what Google Sheets and Excel paste).
    pub fn tsv(&self, sheet: usize, area: Area) -> String {
        let s = &self.sheets[sheet];
        let Some(area) = area.clamp(s.rows, s.ncols) else {
            return String::new();
        };
        let (er, ec) = s.extent();
        let area = Area::new(
            area.r0,
            area.c0,
            area.r1.min(er.max(area.r0 + 1) - 1).max(area.r0),
            area.c1.min(ec.max(area.c0 + 1) - 1).max(area.c0),
        );
        let mut out = String::new();
        for r in area.r0..=area.r1 {
            if s.row_axis.filtered.contains(&r) {
                continue;
            }
            let fields: Vec<String> = (area.c0..=area.c1)
                .map(|c| quote_tsv(&shown(s, &self.styles, r, c)))
                .collect();
            out.push_str(&fields.join("\t"));
            out.push('\n');
        }
        out
    }

    pub fn copy(&mut self, sheet: usize, area: Area, cut: bool) -> String {
        let text = self.tsv(sheet, area);
        let s = &self.sheets[sheet];
        let area = area.clamp(s.rows, s.ncols).unwrap_or(area);
        let area = if area.cells() > 4_000_000 {
            Area::new(
                area.r0,
                area.c0,
                area.r0 + 1999,
                area.c1.min(area.c0 + 1999),
            )
        } else {
            area
        };
        let cells = (area.r0..=area.r1)
            .map(|r| (area.c0..=area.c1).map(|c| s.cell(r, c).cloned()).collect())
            .collect();
        self.clip = Some(Clip {
            sheet,
            area,
            cells,
            text: text.clone(),
            cut,
        });
        text
    }

    /// Pastes `text` at `target` (a TSV from the system clipboard; when it is what this book
    /// copied, formulas and formats come too). `values_only` pastes the values alone.
    pub fn paste(&mut self, sheet: usize, target: Area, text: &str, values_only: bool) -> Area {
        let internal = self
            .clip
            .as_ref()
            .filter(|c| normalize(&c.text) == normalize(text))
            .cloned();
        if let Some(clip) = internal {
            return self.grouped(|b| b.paste_clip(sheet, target, &clip, values_only));
        }
        let rows = parse_tsv(text);
        if rows.is_empty() {
            return target;
        }
        let h = rows.len() as u32;
        let w = rows.iter().map(|r| r.len()).max().unwrap_or(1) as u32;
        let mut cells = Vec::new();
        for (i, row) in rows.iter().enumerate() {
            for (j, field) in row.iter().enumerate() {
                let (r, c) = (target.r0 + i as u32, target.c0 + j as u32);
                if r >= MAX_ROWS || c >= MAX_COLS {
                    continue;
                }
                let cell = self.typed_cell(sheet, r, c, field);
                cells.push((r, c, cell));
            }
        }
        self.write(sheet, cells);
        Area::new(target.r0, target.c0, target.r0 + h - 1, target.c0 + w - 1)
    }

    fn paste_clip(&mut self, sheet: usize, target: Area, clip: &Clip, values_only: bool) -> Area {
        let (h, w) = (clip.area.rows(), clip.area.cols());
        // A target several times the copied block's size is filled with copies of it.
        let reps_r = if target.rows().is_multiple_of(h) {
            target.rows() / h
        } else {
            1
        };
        let reps_c = if target.cols().is_multiple_of(w) {
            target.cols() / w
        } else {
            1
        };
        let mut cells = Vec::new();
        for rr in 0..reps_r {
            for rc in 0..reps_c {
                for (i, row) in clip.cells.iter().enumerate() {
                    for (j, cell) in row.iter().enumerate() {
                        let r = target.r0 + rr * h + i as u32;
                        let c = target.c0 + rc * w + j as u32;
                        if r >= MAX_ROWS || c >= MAX_COLS {
                            continue;
                        }
                        let dr = r as i64 - (clip.area.r0 + i as u32) as i64;
                        let dc = c as i64 - (clip.area.c0 + j as u32) as i64;
                        let new = cell.as_ref().map(|cell| {
                            if values_only {
                                let old =
                                    self.sheets[sheet].cell(r, c).cloned().unwrap_or_default();
                                Cell {
                                    input: if cell.value.is_empty() {
                                        Input::Empty
                                    } else {
                                        Input::Value(cell.value.clone())
                                    },
                                    value: cell.value.clone(),
                                    style: old.style,
                                    note: old.note,
                                }
                            } else if clip.cut {
                                cell.clone()
                            } else {
                                moved_cell(cell, dr, dc)
                            }
                        });
                        cells.push((r, c, new));
                    }
                }
            }
        }
        let pasted = Area::new(
            target.r0,
            target.c0,
            target.r0 + reps_r * h - 1,
            target.c0 + reps_c * w - 1,
        );
        if clip.cut && !values_only {
            // Moving: clear the source (except where the paste lands) and point formulas that
            // read the moved cells at their new place.
            let src = clip.area;
            let mut clears = Vec::new();
            for r in src.r0..=src.r1 {
                for c in src.c0..=src.c1 {
                    if !(clip.sheet == sheet && pasted.contains(r, c)) {
                        clears.push((r, c, None));
                    }
                }
            }
            self.write(clip.sheet, clears);
            let (dr, dc) = (
                target.r0 as i64 - src.r0 as i64,
                target.c0 as i64 - src.c0 as i64,
            );
            let src_name = self.sheets[clip.sheet].name.clone();
            let dst_name = self.sheets[sheet].name.clone();
            let same = clip.sheet == sheet;
            for si in 0..self.sheets.len() {
                let positions: Vec<(u32, u32)> = self.sheets[si].formulas.iter().copied().collect();
                let mut rewrites = Vec::new();
                for (c, r) in positions {
                    let Some(cell) = self.sheets[si].cell(r, c) else {
                        continue;
                    };
                    let Some(f) = cell.formula() else { continue };
                    let new = formula::rewrite_refs(&f.src, |rf| {
                        let on_src = match &rf.sheet {
                            Some(n) => n.eq_ignore_ascii_case(&src_name),
                            None => si == clip.sheet,
                        };
                        if !on_src
                            || !(src.contains(rf.area.r0, rf.area.c0)
                                && src.contains(rf.area.r1, rf.area.c1))
                        {
                            return Some(rf.clone());
                        }
                        let mut out = rf.clone();
                        out.area = Area::new(
                            (rf.area.r0 as i64 + dr) as u32,
                            (rf.area.c0 as i64 + dc) as u32,
                            (rf.area.r1 as i64 + dr) as u32,
                            (rf.area.c1 as i64 + dc) as u32,
                        );
                        if !same {
                            out.sheet = if si == sheet {
                                None
                            } else {
                                Some(dst_name.as_str().into())
                            };
                        }
                        Some(out)
                    });
                    if new != *f.src {
                        let mut cell = cell.clone();
                        cell.input = Input::Formula(Arc::new(FormulaCell::new(&new)));
                        rewrites.push((r, c, Some(cell)));
                    }
                }
                self.write(si, rewrites);
            }
            self.write(sheet, cells);
            self.clip = None;
        } else {
            self.write(sheet, cells);
        }
        pasted
    }

    /// Clears `what` (`"all"`, `"contents"` or `"formats"`) in the areas, as one undo step.
    pub fn clear(&mut self, sheet: usize, areas: &[Area], what: &str) {
        let s = &self.sheets[sheet];
        let (er, ec) = s.extent();
        let mut cells = Vec::new();
        for a in areas {
            let Some(area) = a.clamp(er.max(1), ec.max(1)) else {
                continue;
            };
            for c in area.c0..=area.c1 {
                let Some(col) = s.cols.get(c as usize) else {
                    continue;
                };
                for (&r, old) in col.range(area.r0..=area.r1) {
                    let new = match what {
                        "contents" => Some(Cell {
                            input: Input::Empty,
                            value: Value::Empty,
                            style: old.style,
                            note: old.note.clone(),
                        }),
                        "formats" => Some(Cell {
                            style: 0,
                            ..old.clone()
                        }),
                        _ => None,
                    };
                    cells.push((r, c, new.filter(|c| !c.is_blank())));
                }
            }
        }
        self.write(sheet, cells);
    }

    // --- Fill --------------------------------------------------------------------

    /// Extends `source` to fill `target` (which contains it), continuing number series,
    /// dates, "Item 1, Item 2" and weekday or month names, and moving formulas.
    pub fn fill(&mut self, sheet: usize, source: Area, target: Area) {
        if source == target {
            return;
        }
        let s = &self.sheets[sheet];
        let mut cells = Vec::new();
        let vertical = target.cols() == source.cols();
        let lines: Vec<u32> = if vertical {
            (source.c0..=source.c1).collect()
        } else {
            (source.r0..=source.r1).collect()
        };
        for line in lines {
            let src_cells: Vec<(u32, u32)> = if vertical {
                (source.r0..=source.r1).map(|r| (r, line)).collect()
            } else {
                (source.c0..=source.c1).map(|c| (line, c)).collect()
            };
            let seeds: Vec<Option<Cell>> = src_cells
                .iter()
                .map(|&(r, c)| s.cell(r, c).cloned())
                .collect();
            let first_is_date = seeds[0]
                .as_ref()
                .and_then(|c| self.styles.get(c.style as usize))
                .and_then(|st| st.format.as_deref())
                .is_some_and(|f| super::format::get(f).is_date());
            let series = Series::detect(&seeds, first_is_date);
            let len = seeds.len() as i64;
            let dests: Vec<(u32, u32, i64)> = if vertical {
                (target.r0..=target.r1)
                    .filter(|r| !(source.r0..=source.r1).contains(r))
                    .map(|r| (r, line, r as i64 - source.r0 as i64))
                    .collect()
            } else {
                (target.c0..=target.c1)
                    .filter(|c| !(source.c0..=source.c1).contains(c))
                    .map(|c| (line, c, c as i64 - source.c0 as i64))
                    .collect()
            };
            for (r, c, k) in dests {
                let idx = k.rem_euclid(len) as usize;
                let seed = &seeds[idx];
                let (sr, sc) = src_cells[idx];
                let cell = match seed {
                    Some(cell) if cell.is_formula() => {
                        Some(moved_cell(cell, r as i64 - sr as i64, c as i64 - sc as i64))
                    }
                    Some(cell) => {
                        let mut out = cell.clone();
                        if let Some(v) = series.value(k) {
                            out.input = Input::Value(v.clone());
                            out.value = v;
                        }
                        Some(out)
                    }
                    None => None,
                };
                cells.push((r, c, cell));
            }
        }
        self.write(sheet, cells);
    }

    // --- Find and replace --------------------------------------------------------

    pub fn find(
        &self,
        query: &str,
        case: bool,
        whole: bool,
        formulas: bool,
        sheets: Option<usize>,
    ) -> Vec<(usize, u32, u32)> {
        if query.is_empty() {
            return Vec::new();
        }
        let q = if case {
            query.to_string()
        } else {
            query.to_lowercase()
        };
        let mut out = Vec::new();
        for (si, s) in self.sheets.iter().enumerate() {
            if sheets.is_some_and(|x| x != si) {
                continue;
            }
            let mut hits = Vec::new();
            for (c, m) in s.cols.iter().enumerate() {
                for (&r, cell) in m {
                    if !cell.has_content() {
                        continue;
                    }
                    let text = if formulas && cell.is_formula() {
                        cell.input_text()
                    } else {
                        shown(s, &self.styles, r, c as u32)
                    };
                    let text = if case { text } else { text.to_lowercase() };
                    let hit = if whole { text == q } else { text.contains(&q) };
                    if hit {
                        hits.push((r, c as u32));
                    }
                }
            }
            hits.sort();
            out.extend(hits.into_iter().map(|(r, c)| (si, r, c)));
        }
        out
    }

    /// Replaces `query` in the cells' contents; returns how many cells changed.
    pub fn replace(
        &mut self,
        query: &str,
        with: &str,
        case: bool,
        whole: bool,
        sheets: Option<usize>,
        only: Option<(usize, u32, u32)>,
    ) -> usize {
        let hits = match only {
            Some(p) => vec![p],
            None => self.find(query, case, whole, true, sheets),
        };
        let mut count = 0;
        self.grouped(|b| {
            let mut by_sheet: HashMap<usize, Vec<(u32, u32, Option<Cell>)>> = HashMap::new();
            for (si, r, c) in hits {
                let Some(cell) = b.sheets[si].cell(r, c) else {
                    continue;
                };
                let text = cell.input_text();
                let new = if whole {
                    let eq = if case {
                        text == query
                    } else {
                        text.to_lowercase() == query.to_lowercase()
                    };
                    if eq { with.to_string() } else { continue }
                } else if case {
                    text.replace(query, with)
                } else {
                    replace_ci(&text, query, with)
                };
                if new != text {
                    let cell = b.typed_cell(si, r, c, &new);
                    by_sheet.entry(si).or_default().push((r, c, cell));
                    count += 1;
                }
            }
            for (si, cells) in by_sheet {
                b.write(si, cells);
            }
        });
        count
    }

    // --- Sheets --------------------------------------------------------------

    pub fn unique_name(&self, base: &str) -> String {
        if self.sheet_index(base).is_none() {
            return base.to_string();
        }
        let stem = base
            .trim_end_matches(|c: char| c.is_ascii_digit())
            .trim_end();
        let stem = if stem.is_empty() { "Sheet" } else { stem };
        (2..)
            .map(|i| format!("{stem}{i}"))
            .find(|n| self.sheet_index(n).is_none())
            .unwrap()
    }

    pub fn add_sheet(&mut self, name: Option<&str>, at: Option<usize>) -> usize {
        let name = match name {
            Some(n) => self.unique_name(n),
            None => self.unique_name(&format!("Sheet{}", self.sheets.len() + 1)),
        };
        self.structural(|b| {
            let at = at.unwrap_or(b.sheets.len()).min(b.sheets.len());
            b.sheets.insert(at, Sheet::new(&name));
            b.active = at;
            at
        })
    }

    pub fn remove_sheet(&mut self, index: usize) -> bool {
        if self.sheets.len() <= 1 || index >= self.sheets.len() {
            return false;
        }
        self.structural(|b| {
            b.sheets.remove(index);
            if b.active >= b.sheets.len() || b.active > index {
                b.active = b.active.saturating_sub(1).min(b.sheets.len() - 1);
            }
        });
        true
    }

    pub fn rename_sheet(&mut self, index: usize, name: &str) -> Result<(), String> {
        let name = name.trim();
        if name.is_empty() || name.contains(['!', '[', ']', '*', '?', '/', '\\', ':']) {
            return Err(format!("invalid sheet name {name:?}"));
        }
        if let Some(i) = self.sheet_index(name)
            && i != index
        {
            return Err(format!("there is already a sheet called {name:?}"));
        }
        let old = self.sheets[index].name.clone();
        self.structural(|b| {
            b.sheets[index].name = name.to_string();
            // Formulas that named the sheet follow the new name.
            for si in 0..b.sheets.len() {
                let positions: Vec<(u32, u32)> = b.sheets[si].formulas.iter().copied().collect();
                for (c, r) in positions {
                    let Some(f) = b.sheets[si].cell(r, c).and_then(|c| c.formula()) else {
                        continue;
                    };
                    let src = formula::rewrite_refs(&f.src, |rf| {
                        let mut out = rf.clone();
                        if rf
                            .sheet
                            .as_deref()
                            .is_some_and(|n| n.eq_ignore_ascii_case(&old))
                        {
                            out.sheet = Some(name.into());
                        }
                        Some(out)
                    });
                    if src != *f.src {
                        b.sheets[si].cell_mut(r, c).input =
                            Input::Formula(Arc::new(FormulaCell::new(&src)));
                    }
                }
            }
        });
        Ok(())
    }

    pub fn move_sheet(&mut self, from: usize, to: usize) {
        if from >= self.sheets.len() || to >= self.sheets.len() || from == to {
            return;
        }
        self.structural(|b| {
            let s = b.sheets.remove(from);
            b.sheets.insert(to, s);
            b.active = to;
        });
    }

    pub fn duplicate_sheet(&mut self, index: usize) -> usize {
        let name = self.unique_name(&format!("{} copy", self.sheets[index].name));
        self.structural(|b| {
            let mut s = b.sheets[index].clone();
            s.name = name;
            b.sheets.insert(index + 1, s);
            b.active = index + 1;
            index + 1
        })
    }
}

/// The text a cell shows with its number format.
pub fn shown(s: &Sheet, styles: &[super::model::Style], r: u32, c: u32) -> String {
    let v = s.value(r, c);
    let fmt = s
        .cell(r, c)
        .and_then(|cell| styles.get(cell.style as usize))
        .and_then(|st| st.format.clone());
    super::format::format(&v, fmt.as_deref()).0
}

/// The block of non-empty cells around `(r, c)` (what Ctrl+A and filters pick).
pub fn data_region(s: &Sheet, r: u32, c: u32) -> Area {
    let filled =
        |r: u32, c: u32| s.cell(r, c).is_some_and(|x| x.has_content()) || !s.value(r, c).is_empty();
    let mut a = Area::cell(r, c);
    loop {
        let mut grown = a;
        let r0 = a.r0.saturating_sub(1);
        let c0 = a.c0.saturating_sub(1);
        let r1 = (a.r1 + 1).min(s.rows - 1);
        let c1 = (a.c1 + 1).min(s.ncols - 1);
        if a.r0 > 0 && (c0..=c1).any(|c| filled(r0, c)) {
            grown.r0 = r0;
        }
        if a.r1 < s.rows - 1 && (c0..=c1).any(|c| filled(r1, c)) {
            grown.r1 = r1;
        }
        if a.c0 > 0 && (r0..=r1).any(|r| filled(r, c0)) {
            grown.c0 = c0;
        }
        if a.c1 < s.ncols - 1 && (r0..=r1).any(|r| filled(r, c1)) {
            grown.c1 = c1;
        }
        if grown == a {
            return a;
        }
        a = grown;
    }
}

fn replace_ci(text: &str, query: &str, with: &str) -> String {
    if query.is_empty() {
        return text.to_string();
    }
    let lower = text.to_lowercase();
    let q = query.to_lowercase();
    if lower.len() != text.len() {
        return text.replace(query, with);
    }
    let mut out = String::new();
    let mut last = 0;
    for (i, _) in lower.match_indices(&q) {
        out.push_str(&text[last..i]);
        out.push_str(with);
        last = i + q.len();
    }
    out.push_str(&text[last..]);
    out
}

fn normalize(s: &str) -> String {
    s.replace("\r\n", "\n").trim_end_matches('\n').to_string()
}

pub fn quote_tsv(field: &str) -> String {
    if field.contains(['\t', '\n', '"']) {
        format!("\"{}\"", field.replace('"', "\"\""))
    } else {
        field.to_string()
    }
}

/// Splits tab- (or comma-) separated text into rows of fields, with quoted fields.
pub fn parse_delimited(text: &str, delim: char) -> Vec<Vec<String>> {
    let text = text.strip_prefix('\u{feff}').unwrap_or(text);
    let mut rows = Vec::new();
    let mut row = Vec::new();
    let mut field = String::new();
    let mut chars = text.chars().peekable();
    let mut quoted = false;
    let mut at_start = true;
    while let Some(ch) = chars.next() {
        if quoted {
            if ch == '"' {
                if chars.peek() == Some(&'"') {
                    field.push('"');
                    chars.next();
                } else {
                    quoted = false;
                }
            } else {
                field.push(ch);
            }
            continue;
        }
        match ch {
            '"' if at_start => {
                quoted = true;
                at_start = false;
            }
            c if c == delim => {
                row.push(std::mem::take(&mut field));
                at_start = true;
            }
            '\r' => {}
            '\n' => {
                row.push(std::mem::take(&mut field));
                rows.push(std::mem::take(&mut row));
                at_start = true;
            }
            c => {
                field.push(c);
                at_start = false;
            }
        }
    }
    if !field.is_empty() || !row.is_empty() {
        row.push(field);
        rows.push(row);
    }
    rows
}

pub fn parse_tsv(text: &str) -> Vec<Vec<String>> {
    parse_delimited(text, '\t')
}

// ---------------------------------------------------------------------------
// Autofill series
// ---------------------------------------------------------------------------

const WEEKDAYS: [&str; 7] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
];
const MONTHS: [&str; 12] = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
];

enum Series {
    Copy,
    Linear {
        start: f64,
        step: f64,
    },
    Suffix {
        prefix: String,
        start: i64,
        step: i64,
        width: usize,
    },
    Names {
        list: &'static [&'static str],
        short: bool,
        upper: bool,
        start: i64,
        step: i64,
    },
}

impl Series {
    fn detect(seeds: &[Option<Cell>], first_is_date: bool) -> Series {
        let values: Vec<Value> = seeds
            .iter()
            .map(|c| match c.as_ref().map(|c| &c.input) {
                Some(Input::Value(v)) => v.clone(),
                _ => Value::Empty,
            })
            .collect();
        if values.iter().all(|v| matches!(v, Value::Number(_))) {
            let nums: Vec<f64> = values
                .iter()
                .map(|v| if let Value::Number(n) = v { *n } else { 0.0 })
                .collect();
            if nums.len() == 1 {
                // A single date continues day by day; a single number is copied.
                let is_date = first_is_date;
                return if is_date {
                    Series::Linear {
                        start: nums[0],
                        step: 1.0,
                    }
                } else {
                    Series::Copy
                };
            }
            let step = (nums[nums.len() - 1] - nums[0]) / (nums.len() - 1) as f64;
            return Series::Linear {
                start: nums[0],
                step,
            };
        }
        if values.iter().all(|v| matches!(v, Value::Text(_))) {
            let texts: Vec<&str> = values
                .iter()
                .map(|v| if let Value::Text(t) = v { &**t } else { "" })
                .collect();
            for (list, short) in [
                (&WEEKDAYS[..], false),
                (&WEEKDAYS[..], true),
                (&MONTHS[..], false),
                (&MONTHS[..], true),
            ] {
                let idx: Option<Vec<i64>> = texts
                    .iter()
                    .map(|t| {
                        list.iter()
                            .position(|name| {
                                let n = if short { &name[..3] } else { name };
                                n.eq_ignore_ascii_case(t)
                            })
                            .map(|i| i as i64)
                    })
                    .collect();
                if let Some(idx) = idx {
                    let step = if idx.len() > 1 { idx[1] - idx[0] } else { 1 };
                    let upper = texts[0].chars().all(|c| !c.is_lowercase());
                    return Series::Names {
                        list,
                        short,
                        upper: upper && texts[0].len() > 1,
                        start: idx[0],
                        step,
                    };
                }
            }
            // "Item 1", "Q3", "Room 007".
            let split: Option<Vec<(String, i64, usize)>> = texts
                .iter()
                .map(|t| {
                    let digits = t.chars().rev().take_while(|c| c.is_ascii_digit()).count();
                    if digits == 0 || digits > 15 {
                        return None;
                    }
                    let (p, d) = t.split_at(t.len() - digits);
                    Some((p.to_string(), d.parse().ok()?, d.len()))
                })
                .collect();
            if let Some(parts) = split
                && parts.iter().all(|p| p.0 == parts[0].0)
            {
                let step = if parts.len() > 1 {
                    (parts[parts.len() - 1].1 - parts[0].1) / (parts.len() as i64 - 1)
                } else {
                    1
                };
                let width = if parts[0].2 > 1
                    && texts[0].ends_with(&format!("{:0w$}", parts[0].1, w = parts[0].2))
                    && format!("{}", parts[0].1).len() < parts[0].2
                {
                    parts[0].2
                } else {
                    0
                };
                return Series::Suffix {
                    prefix: parts[0].0.clone(),
                    start: parts[0].1,
                    step,
                    width,
                };
            }
        }
        Series::Copy
    }

    /// The value at position `k` (0 = the first seed).
    fn value(&self, k: i64) -> Option<Value> {
        match self {
            Series::Copy => None,
            Series::Linear { start, step } => Some(Value::Number(start + step * k as f64)),
            Series::Suffix {
                prefix,
                start,
                step,
                width,
            } => {
                let n = start + step * k;
                Some(Value::text(if *width > 0 {
                    format!("{prefix}{n:0w$}", w = width)
                } else {
                    format!("{prefix}{n}")
                }))
            }
            Series::Names {
                list,
                short,
                upper,
                start,
                step,
            } => {
                let i = (start + step * k).rem_euclid(list.len() as i64) as usize;
                let name = if *short { &list[i][..3] } else { list[i] };
                Some(Value::text(if *upper {
                    name.to_uppercase()
                } else {
                    name.to_string()
                }))
            }
        }
    }
}

/// Moves the active cell to the edge of the data in a direction (Ctrl+arrow).
pub fn jump(s: &Sheet, r: u32, c: u32, dr: i32, dc: i32) -> (u32, u32) {
    let filled = |r: u32, c: u32| !s.value(r, c).is_empty();
    let step = |r: u32, c: u32| -> Option<(u32, u32)> {
        let nr = r as i64 + dr as i64;
        let nc = c as i64 + dc as i64;
        (nr >= 0 && nc >= 0 && nr < s.rows as i64 && nc < s.ncols as i64)
            .then_some((nr as u32, nc as u32))
    };
    let Some(next) = step(r, c) else {
        return (r, c);
    };
    let (mut cr, mut cc) = (r, c);
    if filled(r, c) && filled(next.0, next.1) {
        // Run to the last filled cell.
        while let Some((nr, nc)) = step(cr, cc) {
            if !filled(nr, nc) {
                break;
            }
            cr = nr;
            cc = nc;
        }
        return (cr, cc);
    }
    // Run to the next filled cell (or the edge).
    (cr, cc) = next;
    while !filled(cr, cc) {
        match step(cr, cc) {
            Some((nr, nc)) => {
                cr = nr;
                cc = nc;
            }
            None => break,
        }
    }
    let _ = addr::col_name(0);
    (cr, cc)
}
