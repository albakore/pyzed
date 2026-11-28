//! How a cell looks: its text in its number format, its style with conditional formatting
//! applied, and the marks of validation (checkbox, dropdown, invalid value).

use std::collections::HashMap;

use super::eval::Grid;
use super::format;
use super::model::{Book, Check, HAlign, Rule, VAlign};
use super::value::{Error, Value, compare};

#[derive(Debug, Clone, Default)]
pub struct Shown {
    pub text: String,
    pub color: Option<u32>,
    pub fill: Option<u32>,
    pub bold: bool,
    pub italic: bool,
    pub underline: bool,
    pub strike: bool,
    pub align: Option<HAlign>,
    pub valign: Option<VAlign>,
    pub wrap: bool,
    pub size: Option<u16>,
    pub mono: bool,
    pub borders: [bool; 4],
    pub border_color: Option<u32>,
    /// A data bar: its length (0..1) and color.
    pub bar: Option<(f32, u32)>,
    pub checkbox: Option<bool>,
    pub dropdown: bool,
    pub invalid: bool,
    pub error: Option<Error>,
    pub note: bool,
    /// Numbers (and dates) go to the right, booleans to the center, text to the left.
    pub numeric: bool,
    pub boolean: bool,
    pub formula: bool,
}

#[derive(Default)]
pub struct DisplayCache {
    version: u64,
    /// (sheet, rule index) → smallest and largest number of the range.
    ranges: HashMap<(usize, usize), (f64, f64)>,
    /// (sheet, rule index) → how many times each value appears.
    counts: HashMap<(usize, usize), HashMap<String, usize>>,
}

fn mix(a: u32, b: u32, t: f32) -> u32 {
    let ch = |x: u32, s: u32| ((x >> s) & 0xFF) as f32;
    let m = |s: u32| {
        ((ch(a, s) + (ch(b, s) - ch(a, s)) * t)
            .round()
            .clamp(0.0, 255.0) as u32)
            << s
    };
    m(24) | m(16) | m(8) | m(0)
}

impl Book {
    fn range_stats(&self, sheet: usize, idx: usize) -> (f64, f64) {
        let mut cache = self.cache.borrow_mut();
        if cache.version != self.version {
            *cache = DisplayCache {
                version: self.version,
                ..Default::default()
            };
        }
        if let Some(v) = cache.ranges.get(&(sheet, idx)) {
            return *v;
        }
        let s = &self.sheets[sheet];
        let area = s.conditional[idx].area;
        let (mut lo, mut hi) = (f64::INFINITY, f64::NEG_INFINITY);
        Grid::for_each(&self.grid(), sheet, area, &mut |_, _, v| {
            if let Value::Number(n) = v {
                lo = lo.min(*n);
                hi = hi.max(*n);
            }
        });
        cache.ranges.insert((sheet, idx), (lo, hi));
        (lo, hi)
    }

    fn value_count(&self, sheet: usize, idx: usize, key: &str) -> usize {
        let mut cache = self.cache.borrow_mut();
        if cache.version != self.version {
            *cache = DisplayCache {
                version: self.version,
                ..Default::default()
            };
        }
        cache.counts.entry((sheet, idx)).or_insert_with(|| {
            let area = self.sheets[sheet].conditional[idx].area;
            let mut counts: HashMap<String, usize> = HashMap::new();
            Grid::for_each(&self.grid(), sheet, area, &mut |_, _, v| {
                *counts.entry(v.display().to_lowercase()).or_default() += 1;
            });
            counts
        });
        cache.counts[&(sheet, idx)].get(key).copied().unwrap_or(0)
    }

    /// Whether `v` passes the validation rule of cell `(r, c)`.
    pub fn valid(&self, sheet: usize, r: u32, c: u32, v: &Value) -> bool {
        let s = &self.sheets[sheet];
        let Some(val) = s.validation_at(r, c) else {
            return true;
        };
        if v.is_empty() {
            return true;
        }
        match &val.check {
            Check::List(items) => {
                let t = v.display();
                items.iter().any(|i| i.eq_ignore_ascii_case(&t))
            }
            Check::ListRange(range) => self
                .list_items(sheet, range)
                .iter()
                .any(|i| i.eq_ignore_ascii_case(&v.display())),
            Check::Number { min, max, integer } => match v {
                Value::Number(n) => {
                    min.is_none_or(|m| *n >= m)
                        && max.is_none_or(|m| *n <= m)
                        && (!integer || n.fract() == 0.0)
                }
                _ => false,
            },
            Check::Date { min, max } => match v {
                Value::Number(n) => min.is_none_or(|m| *n >= m) && max.is_none_or(|m| *n <= m),
                _ => false,
            },
            Check::TextLength { min, max } => {
                let n = v.display().chars().count();
                min.is_none_or(|m| n >= m) && max.is_none_or(|m| n <= m)
            }
            Check::Checkbox => matches!(v, Value::Bool(_)),
            Check::Formula(f) => {
                let shift = (r as i64 - val.area.r0 as i64, c as i64 - val.area.c0 as i64);
                self.eval_at(f, sheet, val.area.r0, val.area.c0, shift)
                    .as_bool()
                    .unwrap_or(false)
            }
        }
    }

    /// The items of a dropdown validation's range (`"Sheet2!A1:A9"`).
    pub fn list_items(&self, sheet: usize, range: &str) -> Vec<String> {
        let (name, rest) = super::addr::split_sheet(range);
        let si = match name {
            Some(n) => match self.sheet_index(&n) {
                Some(i) => i,
                None => return Vec::new(),
            },
            None => sheet,
        };
        let Some(area) = super::addr::parse_area(rest) else {
            return Vec::new();
        };
        let s = &self.sheets[si];
        let Some(area) = area.clamp(s.extent().0.max(1), s.extent().1.max(1)) else {
            return Vec::new();
        };
        let mut out = Vec::new();
        for r in area.r0..=area.r1 {
            for c in area.c0..=area.c1 {
                let t = super::ops::shown(s, &self.styles, r, c);
                if !t.is_empty() && !out.contains(&t) {
                    out.push(t);
                }
            }
        }
        out
    }

    /// The options of a cell's dropdown, if it has one.
    pub fn dropdown(&self, sheet: usize, r: u32, c: u32) -> Option<Vec<String>> {
        match &self.sheets[sheet].validation_at(r, c)?.check {
            Check::List(items) => Some(items.clone()),
            Check::ListRange(range) => Some(self.list_items(sheet, range)),
            _ => None,
        }
    }

    pub fn shown(&self, sheet: usize, r: u32, c: u32) -> Shown {
        let s = &self.sheets[sheet];
        let cell = s.cell(r, c);
        let style = self.style(cell.map_or(0, |c| c.style));
        let v = s.value(r, c);
        let (text, fmt_color) = format::format(&v, style.format.as_deref());
        let mut out = Shown {
            text,
            color: fmt_color.or(style.color),
            fill: style.fill,
            bold: style.bold,
            italic: style.italic,
            underline: style.underline,
            strike: style.strike,
            align: style.align,
            valign: style.valign,
            wrap: style.wrap,
            size: style.size,
            mono: style.mono,
            borders: style.borders,
            border_color: style.border_color,
            numeric: matches!(v, Value::Number(_)),
            boolean: matches!(v, Value::Bool(_)),
            error: v.error(),
            note: cell.is_some_and(|c| c.note.is_some()),
            formula: cell.is_some_and(|c| c.is_formula()),
            ..Default::default()
        };
        if let Some(val) = s.validation_at(r, c) {
            match &val.check {
                Check::Checkbox => out.checkbox = Some(matches!(v, Value::Bool(true))),
                Check::List(_) | Check::ListRange(_) => out.dropdown = true,
                _ => {}
            }
            if !matches!(val.check, Check::Checkbox) && !self.valid(sheet, r, c, &v) {
                out.invalid = true;
            }
        }
        for (i, cf) in s.conditional.iter().enumerate() {
            if !cf.area.contains(r, c) {
                continue;
            }
            let hit = match &cf.rule {
                Rule::Compare(op, a, b) => {
                    if v.is_empty() {
                        false
                    } else {
                        use std::cmp::Ordering::*;
                        let o = compare(&v, a);
                        match op.as_str() {
                            ">" => o == Greater,
                            ">=" => o != Less,
                            "<" => o == Less,
                            "<=" => o != Greater,
                            "=" => o == Equal,
                            "<>" => o != Equal,
                            "between" => o != Less && compare(&v, b) != Greater,
                            "not_between" => o == Less || compare(&v, b) == Greater,
                            _ => false,
                        }
                    }
                }
                Rule::TextContains(t) => v.display().to_lowercase().contains(&t.to_lowercase()),
                Rule::TextNotContains(t) => !v.display().to_lowercase().contains(&t.to_lowercase()),
                Rule::TextStarts(t) => v.display().to_lowercase().starts_with(&t.to_lowercase()),
                Rule::TextEnds(t) => v.display().to_lowercase().ends_with(&t.to_lowercase()),
                Rule::Empty => v.is_empty(),
                Rule::NotEmpty => !v.is_empty(),
                Rule::Formula(f) => {
                    let shift = (r as i64 - cf.area.r0 as i64, c as i64 - cf.area.c0 as i64);
                    self.eval_at(f, sheet, cf.area.r0, cf.area.c0, shift)
                        .as_bool()
                        .unwrap_or(false)
                }
                Rule::Duplicate => {
                    !v.is_empty() && self.value_count(sheet, i, &v.display().to_lowercase()) > 1
                }
                Rule::Unique => {
                    !v.is_empty() && self.value_count(sheet, i, &v.display().to_lowercase()) == 1
                }
                Rule::Scale(colors) => {
                    if let Value::Number(n) = v {
                        let (lo, hi) = self.range_stats(sheet, i);
                        let t = if hi > lo {
                            ((n - lo) / (hi - lo)) as f32
                        } else {
                            0.5
                        };
                        let color = match colors.as_slice() {
                            [a, b] => mix(*a, *b, t),
                            [a, m, b] => {
                                if t < 0.5 {
                                    mix(*a, *m, t * 2.0)
                                } else {
                                    mix(*m, *b, (t - 0.5) * 2.0)
                                }
                            }
                            _ => continue,
                        };
                        out.fill = Some(color);
                    }
                    continue;
                }
                Rule::Bar(color) => {
                    if let Value::Number(n) = v {
                        let (lo, hi) = self.range_stats(sheet, i);
                        let lo = lo.min(0.0);
                        let t = if hi > lo {
                            ((n - lo) / (hi - lo)) as f32
                        } else {
                            1.0
                        };
                        out.bar = Some((t.clamp(0.0, 1.0), *color));
                    }
                    continue;
                }
            };
            if hit {
                let st = &cf.style;
                if st.color.is_some() {
                    out.color = st.color;
                }
                if st.fill.is_some() {
                    out.fill = st.fill;
                }
                if let Some(b) = st.bold {
                    out.bold = b;
                }
                if let Some(b) = st.italic {
                    out.italic = b;
                }
                if let Some(b) = st.strike {
                    out.strike = b;
                }
                if let Some(b) = st.underline {
                    out.underline = b;
                }
            }
        }
        out
    }
}
