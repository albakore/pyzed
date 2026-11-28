//! The workbook: sheets of cells, styles, the dependency graph, recalculation and undo.

use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::sync::Arc;

use super::addr::{Area, MAX_COLS, MAX_ROWS};
use super::eval::{Ctx, Grid, Val};
use super::formula::{self, Expr};
use super::value::{self, DateHint, Error, NumberHint, Value};

pub type Pos = (usize, u32, u32);

// ---------------------------------------------------------------------------
// Cells and styles
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct FormulaCell {
    /// The text after `=`.
    pub src: Arc<str>,
    pub expr: Option<Arc<Expr>>,
    pub refs: Arc<Vec<formula::Ref>>,
    pub volatile: bool,
}

impl FormulaCell {
    pub fn new(src: &str) -> Self {
        let src: Arc<str> = src.into();
        match formula::parse(&src) {
            Ok(e) => {
                let mut refs = Vec::new();
                formula::collect_refs(&e, &mut refs);
                let volatile = formula::is_volatile(&e);
                Self {
                    src,
                    expr: Some(Arc::new(e)),
                    refs: Arc::new(refs),
                    volatile,
                }
            }
            Err(_) => Self {
                src,
                expr: None,
                refs: Arc::new(Vec::new()),
                volatile: false,
            },
        }
    }
}

#[derive(Debug, Clone, Default)]
pub enum Input {
    #[default]
    Empty,
    Value(Value),
    Formula(Arc<FormulaCell>),
}

#[derive(Debug, Clone, Default)]
pub struct Cell {
    pub input: Input,
    pub value: Value,
    pub style: u32,
    pub note: Option<Arc<str>>,
}

impl Cell {
    pub fn is_formula(&self) -> bool {
        matches!(self.input, Input::Formula(_))
    }

    pub fn formula(&self) -> Option<&FormulaCell> {
        match &self.input {
            Input::Formula(f) => Some(f),
            _ => None,
        }
    }

    /// Nothing worth keeping (no content, style or note).
    pub fn is_blank(&self) -> bool {
        matches!(self.input, Input::Empty) && self.style == 0 && self.note.is_none()
    }

    pub fn has_content(&self) -> bool {
        !matches!(self.input, Input::Empty | Input::Value(Value::Empty))
    }

    /// What the cell shows in the formula bar: `=SUM(A1:A3)`, `12.5`, `hello`.
    pub fn input_text(&self) -> String {
        match &self.input {
            Input::Empty => String::new(),
            Input::Formula(f) => format!("={}", f.src),
            Input::Value(Value::Text(t)) => {
                // Text that would be read as something else keeps the apostrophe.
                if t.starts_with('=') || value::parse_number(t).is_some() {
                    format!("'{t}")
                } else {
                    t.to_string()
                }
            }
            Input::Value(v) => v.display(),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum HAlign {
    Left,
    Center,
    Right,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum VAlign {
    Top,
    Middle,
    Bottom,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Hash)]
pub struct Style {
    pub bold: bool,
    pub italic: bool,
    pub underline: bool,
    pub strike: bool,
    pub color: Option<u32>,
    pub fill: Option<u32>,
    pub align: Option<HAlign>,
    pub valign: Option<VAlign>,
    pub wrap: bool,
    /// Font size in points (`None`: the sheet's size).
    pub size: Option<u16>,
    pub mono: bool,
    pub format: Option<Arc<str>>,
    /// Border lines: top, right, bottom, left.
    pub borders: [bool; 4],
    pub border_color: Option<u32>,
}

// ---------------------------------------------------------------------------
// Row and column sizes
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct Axis {
    pub default: f32,
    pub sizes: BTreeMap<u32, f32>,
    pub hidden: BTreeSet<u32>,
    pub filtered: BTreeSet<u32>,
    /// Indexes whose size differs from `default`, with the sum of the differences up to them.
    cache: Vec<(u32, f64)>,
}

impl Axis {
    pub fn new(default: f32) -> Self {
        Self {
            default,
            sizes: BTreeMap::new(),
            hidden: BTreeSet::new(),
            filtered: BTreeSet::new(),
            cache: Vec::new(),
        }
    }

    pub fn is_hidden(&self, i: u32) -> bool {
        self.hidden.contains(&i) || self.filtered.contains(&i)
    }

    pub fn size(&self, i: u32) -> f32 {
        if self.is_hidden(i) {
            0.0
        } else {
            self.sizes.get(&i).copied().unwrap_or(self.default)
        }
    }

    pub fn rebuild(&mut self) {
        let mut keys: BTreeSet<u32> = self.sizes.keys().copied().collect();
        keys.extend(self.hidden.iter().copied());
        keys.extend(self.filtered.iter().copied());
        let mut acc = 0.0f64;
        self.cache.clear();
        for k in keys {
            acc += (self.size(k) - self.default) as f64;
            self.cache.push((k, acc));
        }
    }

    /// Where item `i` starts.
    pub fn offset(&self, i: u32) -> f64 {
        let n = self.cache.partition_point(|(k, _)| *k < i);
        let delta = if n == 0 { 0.0 } else { self.cache[n - 1].1 };
        i as f64 * self.default as f64 + delta
    }

    /// The item under position `pos` (clamped to `count - 1`).
    pub fn index_at(&self, pos: f64, count: u32) -> u32 {
        if pos <= 0.0 || count == 0 {
            return 0;
        }
        let (mut lo, mut hi) = (0u32, count);
        while lo + 1 < hi {
            let mid = lo + (hi - lo) / 2;
            if self.offset(mid) <= pos {
                lo = mid
            } else {
                hi = mid
            }
        }
        lo
    }

    /// Shifts sizes and hidden marks after inserting (`n > 0`) or deleting (`n < 0`) at `at`.
    pub fn shift(&mut self, at: u32, n: i64) {
        self.sizes = self
            .sizes
            .iter()
            .filter_map(|(&k, &v)| shift_index(k, at, n).map(|k| (k, v)))
            .collect();
        let mvs = |set: &BTreeSet<u32>| -> BTreeSet<u32> {
            set.iter().filter_map(|&k| shift_index(k, at, n)).collect()
        };
        self.hidden = mvs(&self.hidden);
        self.filtered = mvs(&self.filtered);
        self.rebuild();
    }
}

/// Where index `k` goes after inserting/deleting `n` items at `at` (`None`: deleted).
pub fn shift_index(k: u32, at: u32, n: i64) -> Option<u32> {
    if k < at {
        return Some(k);
    }
    if n < 0 && (k as i64) < at as i64 - n {
        return None;
    }
    Some((k as i64 + n) as u32)
}

// ---------------------------------------------------------------------------
// Conditional formats, validation, filters
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub enum Rule {
    /// `>`, `<`, `>=`, `<=`, `=`, `<>`, `between`, `not_between`.
    Compare(String, Value, Value),
    TextContains(String),
    TextNotContains(String),
    TextStarts(String),
    TextEnds(String),
    Empty,
    NotEmpty,
    /// A formula written for the range's first cell (`=$C2>100`), TRUE applies the style.
    Formula(Arc<FormulaCell>),
    /// Colors from the smallest to the largest value (2 or 3 stops).
    Scale(Vec<u32>),
    /// A bar as long as the value relative to the range's largest one.
    Bar(u32),
    Duplicate,
    Unique,
}

#[derive(Debug, Clone, Default)]
pub struct CondStyle {
    pub color: Option<u32>,
    pub fill: Option<u32>,
    pub bold: Option<bool>,
    pub italic: Option<bool>,
    pub strike: Option<bool>,
    pub underline: Option<bool>,
}

#[derive(Debug, Clone)]
pub struct CondFormat {
    pub area: Area,
    pub rule: Rule,
    pub style: CondStyle,
}

#[derive(Debug, Clone)]
pub enum Check {
    /// One of these values (a dropdown in the cell).
    List(Vec<String>),
    /// One of the values of a range (`"Sheet2!A1:A9"`).
    ListRange(String),
    Number {
        min: Option<f64>,
        max: Option<f64>,
        integer: bool,
    },
    TextLength {
        min: Option<usize>,
        max: Option<usize>,
    },
    Date {
        min: Option<f64>,
        max: Option<f64>,
    },
    /// TRUE or FALSE, shown and toggled as a checkbox.
    Checkbox,
    /// A formula for the range's first cell that must be TRUE.
    Formula(Arc<FormulaCell>),
}

#[derive(Debug, Clone)]
pub struct Validation {
    pub area: Area,
    pub check: Check,
    /// Refuse invalid input (otherwise it is kept and marked).
    pub strict: bool,
    pub message: Option<String>,
}

#[derive(Debug, Clone, Default)]
pub struct Filter {
    /// The header row and the rows below it.
    pub area: Area,
    /// Per column: the values (as shown) to hide.
    pub hidden: HashMap<u32, HashSet<String>>,
    /// Per column: a criterion (`">5"`, `"*north*"`) rows must match.
    pub conditions: HashMap<u32, String>,
    /// The column sorted from the filter menu and its direction.
    pub sorted: Option<(u32, bool)>,
}

impl Default for Area {
    fn default() -> Self {
        Area::cell(0, 0)
    }
}

#[derive(Debug, Clone)]
pub struct Selection {
    /// Selected areas; the last one is where the active cell is.
    pub ranges: Vec<Area>,
    pub active: (u32, u32),
    /// The corner that moves with Shift+arrows.
    pub anchor: (u32, u32),
}

impl Default for Selection {
    fn default() -> Self {
        Self {
            ranges: vec![Area::cell(0, 0)],
            active: (0, 0),
            anchor: (0, 0),
        }
    }
}

impl Selection {
    pub fn range(&self) -> Area {
        *self
            .ranges
            .last()
            .unwrap_or(&Area::cell(self.active.0, self.active.1))
    }

    pub fn contains(&self, r: u32, c: u32) -> bool {
        self.ranges.iter().any(|a| a.contains(r, c))
    }
}

// ---------------------------------------------------------------------------
// Sheets
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct Sheet {
    pub name: String,
    pub cols: Vec<BTreeMap<u32, Cell>>,
    /// Rows and columns shown (they grow as cells are used).
    pub rows: u32,
    pub ncols: u32,
    pub row_axis: Axis,
    pub col_axis: Axis,
    pub freeze: (u32, u32),
    pub merges: Vec<Area>,
    pub conditional: Vec<CondFormat>,
    pub validations: Vec<Validation>,
    pub filter: Option<Filter>,
    pub selection: Selection,
    pub scroll: (f32, f32),
    /// Values spilled by array formulas (`SEQUENCE`, `FILTER`, `=A1:B3`...), by column.
    pub spill: Vec<BTreeMap<u32, Value>>,
    /// The area each array formula wanted (it shows #SPILL! when blocked).
    pub spill_areas: HashMap<(u32, u32), Area>,
    pub gridlines: bool,
    pub tab_color: Option<u32>,
    /// Formula cells, as (col, row), for dependency lookups by range.
    pub formulas: BTreeSet<(u32, u32)>,
}

pub const DEFAULT_ROWS: u32 = 1000;
pub const DEFAULT_COLS: u32 = 26;
pub const ROW_HEIGHT: f32 = 24.0;
pub const COL_WIDTH: f32 = 100.0;

impl Sheet {
    pub fn new(name: &str) -> Self {
        let mut s = Sheet {
            name: name.to_string(),
            cols: Vec::new(),
            rows: DEFAULT_ROWS,
            ncols: DEFAULT_COLS,
            row_axis: Axis::new(ROW_HEIGHT),
            col_axis: Axis::new(COL_WIDTH),
            freeze: (0, 0),
            merges: Vec::new(),
            conditional: Vec::new(),
            validations: Vec::new(),
            filter: None,
            selection: Selection::default(),
            scroll: (0.0, 0.0),
            spill: Vec::new(),
            spill_areas: HashMap::new(),
            gridlines: true,
            tab_color: None,
            formulas: BTreeSet::new(),
        };
        s.row_axis.rebuild();
        s.col_axis.rebuild();
        s
    }

    pub fn cell(&self, r: u32, c: u32) -> Option<&Cell> {
        self.cols.get(c as usize)?.get(&r)
    }

    pub fn cell_mut(&mut self, r: u32, c: u32) -> &mut Cell {
        if self.cols.len() <= c as usize {
            self.cols.resize_with(c as usize + 1, BTreeMap::new);
        }
        self.cols[c as usize].entry(r).or_default()
    }

    /// Replaces a cell (`None` removes it) and returns the old one.
    pub fn put(&mut self, r: u32, c: u32, cell: Option<Cell>) -> Option<Cell> {
        let old = match cell {
            Some(cell) if !cell.is_blank() => {
                if cell.is_formula() {
                    self.formulas.insert((c, r));
                } else {
                    self.formulas.remove(&(c, r));
                }
                self.cell_mut(r, c);
                self.cols[c as usize].insert(r, cell)
            }
            _ => {
                self.formulas.remove(&(c, r));
                self.cols.get_mut(c as usize).and_then(|m| m.remove(&r))
            }
        };
        self.grow(r + 1, c + 1);
        old
    }

    pub fn grow(&mut self, rows: u32, cols: u32) {
        self.rows = self.rows.max(rows).min(MAX_ROWS);
        self.ncols = self.ncols.max(cols).min(MAX_COLS);
    }

    pub fn value(&self, r: u32, c: u32) -> Value {
        match self.cell(r, c) {
            Some(cell) if !matches!(cell.input, Input::Empty) => cell.value.clone(),
            _ => self
                .spill
                .get(c as usize)
                .and_then(|m| m.get(&r))
                .cloned()
                .unwrap_or(Value::Empty),
        }
    }

    /// Rows and columns that hold something (for whole-column references).
    pub fn extent(&self) -> (u32, u32) {
        let mut rows = 0;
        let mut cols = 0;
        for (c, m) in self.cols.iter().enumerate() {
            if let Some((&r, _)) = m.iter().next_back() {
                rows = rows.max(r + 1);
                cols = cols.max(c as u32 + 1);
            }
        }
        for (c, m) in self.spill.iter().enumerate() {
            if let Some((&r, _)) = m.iter().next_back() {
                rows = rows.max(r + 1);
                cols = cols.max(c as u32 + 1);
            }
        }
        (rows, cols)
    }

    pub fn merge_at(&self, r: u32, c: u32) -> Option<Area> {
        self.merges.iter().find(|m| m.contains(r, c)).copied()
    }

    /// Grows an area until it covers every merge it touches.
    pub fn expand_merges(&self, mut a: Area) -> Area {
        loop {
            let mut grown = a;
            for m in &self.merges {
                if m.intersects(&grown) {
                    grown = grown.union(m);
                }
            }
            if grown == a {
                return a;
            }
            a = grown;
        }
    }

    pub fn style_of(&self, r: u32, c: u32) -> u32 {
        self.cell(r, c).map_or(0, |c| c.style)
    }

    pub fn validation_at(&self, r: u32, c: u32) -> Option<&Validation> {
        self.validations
            .iter()
            .rev()
            .find(|v| v.area.contains(r, c))
    }
}

// ---------------------------------------------------------------------------
// The workbook
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub enum Change {
    Cells {
        sheet: usize,
        cells: Vec<(u32, u32, Option<Cell>, Option<Cell>)>,
    },
    /// A whole-book snapshot (structural changes: rows, columns, sheets, merges...).
    Book {
        before: Vec<Sheet>,
        after: Vec<Sheet>,
        active: (usize, usize),
    },
}

#[derive(Debug, Clone, Default)]
struct Deps {
    /// Formula cells reading a single cell.
    single: HashMap<Pos, Vec<Pos>>,
    /// Formula cells reading a range: (sheet, area, formula).
    ranges: Vec<(usize, Area, Pos)>,
    volatile: HashSet<Pos>,
}

/// The internal clipboard: what was copied, so pasting keeps formulas and formats.
#[derive(Debug, Clone)]
pub struct Clip {
    pub sheet: usize,
    pub area: Area,
    pub cells: Vec<Vec<Option<Cell>>>,
    pub text: String,
    pub cut: bool,
}

pub struct Book {
    pub sheets: Vec<Sheet>,
    pub active: usize,
    pub styles: Vec<Style>,
    style_ids: HashMap<Style, u32>,
    pub undo: Vec<Change>,
    pub redo: Vec<Change>,
    /// Bumped on every change (views compare it to redraw).
    pub version: u64,
    pub utc_offset: i64,
    /// Typed dates like 03/04/2025 are month first (US) instead of day first.
    pub month_first: bool,
    deps: Deps,
    pub clip: Option<Clip>,
    /// Cells changed by edits since Python last asked (A1 addresses per sheet).
    pub changed: Vec<Pos>,
    pub readonly: bool,
    /// Grouping of several edits into one undo step.
    group: Option<Vec<Change>>,
    pub last_error: Option<String>,
    pub cache: std::cell::RefCell<super::display::DisplayCache>,
    /// The grid widget's state (what is being typed or dragged).
    pub ui: super::view::Ui,
}

impl Default for Book {
    fn default() -> Self {
        Self::new()
    }
}

struct BookGrid<'a>(&'a Book);

impl Grid for BookGrid<'_> {
    fn value(&self, sheet: usize, row: u32, col: u32) -> Value {
        self.0
            .sheets
            .get(sheet)
            .map(|s| s.value(row, col))
            .unwrap_or(Value::Error(Error::Ref))
    }

    fn sheet_index(&self, name: &str) -> Option<usize> {
        self.0.sheet_index(name)
    }

    fn extent(&self, sheet: usize) -> (u32, u32) {
        self.0
            .sheets
            .get(sheet)
            .map(|s| s.extent())
            .unwrap_or((0, 0))
    }

    fn for_each(&self, sheet: usize, area: Area, f: &mut dyn FnMut(u32, u32, &Value)) {
        let Some(s) = self.0.sheets.get(sheet) else {
            return;
        };
        let c1 = area.c1.min(s.cols.len().max(s.spill.len()) as u32);
        for c in area.c0..=c1 {
            if let Some(m) = s.cols.get(c as usize) {
                for (&r, cell) in m.range(area.r0..=area.r1) {
                    if !matches!(cell.input, Input::Empty) && !cell.value.is_empty() {
                        f(r, c, &cell.value);
                    }
                }
            }
            if let Some(m) = s.spill.get(c as usize) {
                for (&r, v) in m.range(area.r0..=area.r1) {
                    if s.cell(r, c)
                        .is_none_or(|cell| matches!(cell.input, Input::Empty))
                    {
                        f(r, c, v);
                    }
                }
            }
        }
    }

    fn utc_offset(&self) -> i64 {
        self.0.utc_offset
    }

    fn sheet_name(&self, sheet: usize) -> String {
        self.0
            .sheets
            .get(sheet)
            .map(|s| s.name.clone())
            .unwrap_or_default()
    }

    fn is_formula(&self, sheet: usize, row: u32, col: u32) -> bool {
        self.0
            .sheets
            .get(sheet)
            .and_then(|s| s.cell(row, col))
            .is_some_and(|c| c.is_formula())
    }
}

/// What typing a value into a cell gave: the value, and a format for it when it showed one.
pub fn parse_input(text: &str, month_first: bool) -> (Input, Option<&'static str>) {
    if text.is_empty() {
        return (Input::Empty, None);
    }
    if let Some(src) = text.strip_prefix('=')
        && !src.is_empty()
    {
        return (
            Input::Formula(Arc::new(FormulaCell::new(&formula::normalize(src)))),
            None,
        );
    }
    if let Some(t) = text.strip_prefix('\'') {
        return (Input::Value(Value::text(t)), None);
    }
    if let Some((n, hint)) = value::parse_number(text) {
        let fmt = match hint {
            NumberHint::Plain => None,
            NumberHint::Percent => Some(if text.contains('.') { "0.00%" } else { "0%" }),
            NumberHint::Currency('€') => Some("#,##0.00 €"),
            NumberHint::Currency('£') => Some("£#,##0.00"),
            NumberHint::Currency('¥') => Some("¥#,##0"),
            NumberHint::Currency(_) => Some("$#,##0.00"),
            NumberHint::Thousands => Some(if text.contains('.') {
                "#,##0.00"
            } else {
                "#,##0"
            }),
        };
        return (Input::Value(Value::Number(n)), fmt);
    }
    if let Some((n, hint)) = value::parse_date(text, month_first) {
        let fmt = match hint {
            DateHint::Date => "yyyy-mm-dd",
            DateHint::DateTime => "yyyy-mm-dd hh:mm",
            DateHint::Time => {
                if text.matches(':').count() == 2 {
                    "hh:mm:ss"
                } else if text.to_ascii_uppercase().contains('M') {
                    "h:mm AM/PM"
                } else {
                    "hh:mm"
                }
            }
        };
        return (Input::Value(Value::Number(n)), Some(fmt));
    }
    match text.to_ascii_uppercase().as_str() {
        "TRUE" => return (Input::Value(Value::Bool(true)), None),
        "FALSE" => return (Input::Value(Value::Bool(false)), None),
        _ => {}
    }
    if let Some(e) = Error::parse(text) {
        return (Input::Value(Value::Error(e)), None);
    }
    (Input::Value(Value::text(text)), None)
}

impl Book {
    pub fn new() -> Self {
        let mut b = Book {
            sheets: vec![Sheet::new("Sheet1")],
            active: 0,
            styles: vec![Style::default()],
            style_ids: HashMap::new(),
            undo: Vec::new(),
            redo: Vec::new(),
            version: 0,
            utc_offset: 0,
            month_first: true,
            deps: Deps::default(),
            clip: None,
            changed: Vec::new(),
            readonly: false,
            group: None,
            last_error: None,
            cache: Default::default(),
            ui: Default::default(),
        };
        b.style_ids.insert(Style::default(), 0);
        b
    }

    pub fn sheet_index(&self, name: &str) -> Option<usize> {
        self.sheets
            .iter()
            .position(|s| s.name.eq_ignore_ascii_case(name))
    }

    pub fn sheet(&self) -> &Sheet {
        &self.sheets[self.active]
    }

    pub fn sheet_mut(&mut self) -> &mut Sheet {
        &mut self.sheets[self.active]
    }

    pub fn style(&self, id: u32) -> &Style {
        self.styles.get(id as usize).unwrap_or(&self.styles[0])
    }

    pub fn intern(&mut self, style: Style) -> u32 {
        if let Some(&id) = self.style_ids.get(&style) {
            return id;
        }
        let id = self.styles.len() as u32;
        self.styles.push(style.clone());
        self.style_ids.insert(style, id);
        id
    }

    pub fn touch(&mut self) {
        self.version = self.version.wrapping_add(1);
    }

    // --- Undo -------------------------------------------------------------

    fn record(&mut self, change: Change) {
        if let Some(g) = &mut self.group {
            g.push(change);
            return;
        }
        self.undo.push(change);
        if self.undo.len() > 200 {
            self.undo.remove(0);
        }
        self.redo.clear();
    }

    /// Runs `f` as one undo step.
    pub fn grouped<T>(&mut self, f: impl FnOnce(&mut Self) -> T) -> T {
        if self.group.is_some() {
            return f(self);
        }
        self.group = Some(Vec::new());
        let out = f(self);
        let changes = self.group.take().unwrap_or_default();
        match changes.len() {
            0 => {}
            1 => self.record(changes.into_iter().next().unwrap()),
            _ => {
                let one_sheet = changes.iter().all(|c| matches!(c, Change::Cells { sheet, .. } if Some(*sheet) == match &changes[0] { Change::Cells { sheet, .. } => Some(*sheet), _ => None }));
                if one_sheet {
                    let mut merged: Vec<(u32, u32, Option<Cell>, Option<Cell>)> = Vec::new();
                    let mut index: HashMap<(u32, u32), usize> = HashMap::new();
                    let mut sheet_id = 0;
                    for c in changes {
                        if let Change::Cells { sheet, cells } = c {
                            sheet_id = sheet;
                            for (r, col, before, after) in cells {
                                match index.get(&(r, col)) {
                                    Some(&i) => merged[i].3 = after,
                                    None => {
                                        index.insert((r, col), merged.len());
                                        merged.push((r, col, before, after));
                                    }
                                }
                            }
                        }
                    }
                    self.record(Change::Cells {
                        sheet: sheet_id,
                        cells: merged,
                    });
                } else {
                    // Rebuild the state before the group by undoing its changes on a copy.
                    let after = self.sheets.clone();
                    let mut before = self.sheets.clone();
                    for c in changes.iter().rev() {
                        match c {
                            Change::Cells { sheet, cells } => {
                                if let Some(s) = before.get_mut(*sheet) {
                                    for (r, col, old, _) in cells.iter().rev() {
                                        s.put(*r, *col, old.clone());
                                    }
                                }
                            }
                            Change::Book { before: b, .. } => before = b.clone(),
                        }
                    }
                    self.record(Change::Book {
                        before,
                        after,
                        active: (self.active, self.active),
                    });
                }
            }
        }
        out
    }

    /// Pushes an already applied change (used to merge several into one step).
    pub fn push_raw(&mut self, change: Change) {
        self.record(change);
    }

    /// Records a structural change: `f` changes the sheets, the whole book is snapshotted.
    pub fn structural<T>(&mut self, f: impl FnOnce(&mut Self) -> T) -> T {
        let before = self.sheets.clone();
        let active = self.active;
        let out = f(self);
        self.rebuild_deps();
        self.recalc_all();
        let after = self.sheets.clone();
        self.record(Change::Book {
            before,
            after,
            active: (active, self.active),
        });
        self.touch();
        out
    }

    pub fn can_undo(&self) -> bool {
        !self.undo.is_empty()
    }

    pub fn can_redo(&self) -> bool {
        !self.redo.is_empty()
    }

    pub fn undo(&mut self) -> bool {
        let Some(change) = self.undo.pop() else {
            return false;
        };
        self.apply_change(&change, true);
        self.redo.push(change);
        true
    }

    pub fn redo(&mut self) -> bool {
        let Some(change) = self.redo.pop() else {
            return false;
        };
        self.apply_change(&change, false);
        self.undo.push(change);
        true
    }

    fn apply_change(&mut self, change: &Change, undo: bool) {
        match change {
            Change::Cells { sheet, cells } => {
                let mut touched = Vec::new();
                for (r, c, before, after) in cells {
                    let cell = if undo { before } else { after };
                    if let Some(s) = self.sheets.get_mut(*sheet) {
                        let old = s.put(*r, *c, cell.clone());
                        let was_formula = old.as_ref().is_some_and(|c| c.is_formula());
                        let is_formula = cell.as_ref().is_some_and(|c| c.is_formula());
                        if was_formula || is_formula {
                            self.update_deps((*sheet, *r, *c), old.as_ref(), cell.as_ref());
                        }
                    }
                    touched.push((*r, *c));
                }
                if let Some(s) = self.sheets.get_mut(*sheet)
                    && let Some(&(r, c)) = touched.first()
                {
                    let area = touched
                        .iter()
                        .fold(Area::cell(r, c), |a, &(r, c)| a.union(&Area::cell(r, c)));
                    s.selection = Selection {
                        ranges: vec![area],
                        active: (r, c),
                        anchor: (r, c),
                    };
                    self.active = *sheet;
                }
                let changed: Vec<Pos> = touched.iter().map(|&(r, c)| (*sheet, r, c)).collect();
                self.recalc(&changed);
                self.changed.extend(changed);
            }
            Change::Book {
                before,
                after,
                active,
            } => {
                let keep_sel: Vec<(Selection, (f32, f32))> = self
                    .sheets
                    .iter()
                    .map(|s| (s.selection.clone(), s.scroll))
                    .collect();
                self.sheets = if undo { before.clone() } else { after.clone() };
                for (s, (sel, scroll)) in self.sheets.iter_mut().zip(keep_sel) {
                    if sel.active.0 < s.rows && sel.active.1 < s.ncols {
                        s.selection = sel;
                        s.scroll = scroll;
                    }
                }
                self.active = (if undo { active.0 } else { active.1 }).min(self.sheets.len() - 1);
                self.rebuild_deps();
                self.recalc_all();
            }
        }
        self.touch();
    }

    // --- Writing cells -----------------------------------------------------

    /// Replaces cells (`None` clears them) as one undo step and recalculates.
    pub fn write(&mut self, sheet: usize, cells: Vec<(u32, u32, Option<Cell>)>) {
        if cells.is_empty() || sheet >= self.sheets.len() {
            return;
        }
        let mut log = Vec::with_capacity(cells.len());
        let mut changed = Vec::with_capacity(cells.len());
        for (r, c, cell) in cells {
            let old = self.sheets[sheet].put(r, c, cell.clone());
            let was_formula = old.as_ref().is_some_and(|c| c.is_formula());
            let is_formula = cell.as_ref().is_some_and(|c| c.is_formula());
            if was_formula || is_formula {
                self.update_deps((sheet, r, c), old.as_ref(), cell.as_ref());
            }
            changed.push((sheet, r, c));
            log.push((r, c, old, cell));
        }
        self.recalc(&changed);
        self.changed.extend(changed);
        self.record(Change::Cells { sheet, cells: log });
        self.touch();
    }

    /// A cell after typing `text` into it (keeping its style and note).
    pub fn typed_cell(&mut self, sheet: usize, r: u32, c: u32, text: &str) -> Option<Cell> {
        let old = self.sheets[sheet].cell(r, c).cloned().unwrap_or_default();
        let (input, fmt) = parse_input(text, self.month_first);
        let mut style = old.style;
        if let Some(fmt) = fmt
            && self.style(style).format.is_none()
        {
            let mut s = self.style(style).clone();
            s.format = Some(fmt.into());
            style = self.intern(s);
        }
        let cell = Cell {
            value: match &input {
                Input::Value(v) => v.clone(),
                _ => Value::Empty,
            },
            input,
            style,
            note: old.note,
        };
        (!cell.is_blank()).then_some(cell)
    }

    pub fn set_input(&mut self, sheet: usize, r: u32, c: u32, text: &str) {
        let cell = self.typed_cell(sheet, r, c, text);
        self.write(sheet, vec![(r, c, cell)]);
    }

    pub fn set_value(&mut self, sheet: usize, r: u32, c: u32, v: Value) {
        let old = self.sheets[sheet].cell(r, c).cloned().unwrap_or_default();
        let input = if v.is_empty() {
            Input::Empty
        } else {
            Input::Value(v.clone())
        };
        let cell = Cell {
            input,
            value: v,
            style: old.style,
            note: old.note,
        };
        self.write(sheet, vec![(r, c, (!cell.is_blank()).then_some(cell))]);
    }

    /// Changes the style of every cell in the areas with `f`.
    pub fn restyle(&mut self, sheet: usize, areas: &[Area], f: impl Fn(&mut Style)) {
        let mut cells = Vec::new();
        let mut cache: HashMap<u32, u32> = HashMap::new();
        for a in areas {
            let a = a
                .clamp(self.sheets[sheet].rows, self.sheets[sheet].ncols)
                .unwrap_or(*a);
            if a.cells() > 2_000_000 {
                continue;
            }
            for r in a.r0..=a.r1 {
                for c in a.c0..=a.c1 {
                    let old = self.sheets[sheet].cell(r, c).cloned().unwrap_or_default();
                    let id = match cache.get(&old.style) {
                        Some(&id) => id,
                        None => {
                            let mut st = self.style(old.style).clone();
                            f(&mut st);
                            let id = self.intern(st);
                            cache.insert(old.style, id);
                            id
                        }
                    };
                    if id != old.style {
                        let mut cell = old;
                        cell.style = id;
                        cells.push((r, c, Some(cell)));
                    }
                }
            }
        }
        self.write(sheet, cells);
    }

    // --- Dependencies -------------------------------------------------------

    fn resolve_ref(&self, sheet: usize, r: &formula::Ref) -> Option<(usize, Area)> {
        let s = match &r.sheet {
            Some(name) => self.sheet_index(name)?,
            None => sheet,
        };
        Some((s, r.area))
    }

    fn update_deps(&mut self, pos: Pos, old: Option<&Cell>, new: Option<&Cell>) {
        if let Some(f) = old.and_then(|c| c.formula()) {
            let mut had_range = false;
            for r in f.refs.iter() {
                if let Some((s, a)) = self.resolve_ref(pos.0, r) {
                    if a.is_cell() {
                        if let Some(v) = self.deps.single.get_mut(&(s, a.r0, a.c0)) {
                            v.retain(|p| *p != pos);
                        }
                    } else {
                        had_range = true;
                    }
                }
            }
            if had_range {
                self.deps.ranges.retain(|(_, _, p)| *p != pos);
            }
            self.deps.volatile.remove(&pos);
        }
        if let Some(f) = new.and_then(|c| c.formula()) {
            for r in f.refs.iter() {
                if let Some((s, a)) = self.resolve_ref(pos.0, r) {
                    if a.is_cell() {
                        self.deps
                            .single
                            .entry((s, a.r0, a.c0))
                            .or_default()
                            .push(pos);
                    } else {
                        self.deps.ranges.push((s, a, pos));
                    }
                }
            }
            if f.volatile || f.expr.is_none() {
                self.deps.volatile.insert(pos);
            }
        }
    }

    pub fn rebuild_deps(&mut self) {
        self.deps = Deps::default();
        for si in 0..self.sheets.len() {
            let cells: Vec<(u32, u32)> = self.sheets[si].formulas.iter().copied().collect();
            for (c, r) in cells {
                let cell = self.sheets[si].cell(r, c).cloned();
                self.update_deps((si, r, c), None, cell.as_ref());
            }
        }
    }

    /// Formula cells that read any of `changed`, directly or through other formulas.
    fn dependents(&self, changed: &[(usize, Area)], limit: usize) -> Option<HashSet<Pos>> {
        let mut out: HashSet<Pos> = HashSet::new();
        let mut queue: Vec<(usize, Area)> = changed.to_vec();
        let mut work = 0usize;
        while let Some((s, a)) = queue.pop() {
            if a.cells() <= 64 {
                for r in a.r0..=a.r1 {
                    for c in a.c0..=a.c1 {
                        if let Some(list) = self.deps.single.get(&(s, r, c)) {
                            for &p in list {
                                if out.insert(p) {
                                    queue.push((p.0, Area::cell(p.1, p.2)));
                                }
                            }
                        }
                    }
                }
            } else {
                for (&(ps, pr, pc), list) in &self.deps.single {
                    if ps == s && a.contains(pr, pc) {
                        for &p in list {
                            if out.insert(p) {
                                queue.push((p.0, Area::cell(p.1, p.2)));
                            }
                        }
                    }
                }
            }
            for &(rs, ra, p) in &self.deps.ranges {
                if rs == s && ra.intersects(&a) && out.insert(p) {
                    queue.push((p.0, Area::cell(p.1, p.2)));
                }
            }
            // Array formulas whose spill area changed must try again.
            if let Some(sheet) = self.sheets.get(s) {
                for (&(r, c), area) in &sheet.spill_areas {
                    if area.intersects(&a) && !a.contains(r, c) && out.insert((s, r, c)) {
                        queue.push((s, Area::cell(r, c)));
                    }
                }
            }
            work += self.deps.ranges.len() + 1;
            if work > limit {
                return None;
            }
        }
        Some(out)
    }

    /// Recalculates the formulas affected by changes to these cells.
    pub fn recalc(&mut self, changed: &[Pos]) {
        let areas: Vec<(usize, Area)> = changed
            .iter()
            .map(|&(s, r, c)| (s, Area::cell(r, c)))
            .collect();
        let areas = compact(areas);
        let mut dirty = match self.dependents(&areas, 20_000_000) {
            Some(d) => d,
            None => return self.recalc_all(),
        };
        for &p in changed {
            if self
                .sheets
                .get(p.0)
                .and_then(|s| s.cell(p.1, p.2))
                .is_some_and(|c| c.is_formula())
            {
                dirty.insert(p);
            } else if let Some(s) = self.sheets.get_mut(p.0) {
                // A plain value: its value is its input (and it no longer spills).
                if let Some(cell) = s.cols.get_mut(p.2 as usize).and_then(|m| m.get_mut(&p.1)) {
                    cell.value = match &cell.input {
                        Input::Value(v) => v.clone(),
                        _ => Value::Empty,
                    };
                }
                if let Some(area) = s.spill_areas.remove(&(p.1, p.2)) {
                    clear_spill(s, area, (p.1, p.2));
                }
            }
        }
        dirty.extend(self.deps.volatile.iter().copied());
        self.evaluate(dirty);
    }

    pub fn recalc_all(&mut self) {
        let mut dirty = HashSet::new();
        for (si, s) in self.sheets.iter().enumerate() {
            for &(c, r) in &s.formulas {
                dirty.insert((si, r, c));
            }
        }
        for s in &mut self.sheets {
            s.spill.clear();
            s.spill_areas.clear();
        }
        self.evaluate(dirty);
    }

    /// Evaluates the dirty formulas in dependency order (cycles give #CYCLE!).
    fn evaluate(&mut self, dirty: HashSet<Pos>) {
        let mut pending = dirty;
        for _pass in 0..4 {
            if pending.is_empty() {
                break;
            }
            let order = self.order(&pending);
            let mut spilled: Vec<(usize, Area)> = Vec::new();
            for (p, cyclic) in order {
                let result = if cyclic {
                    Val::V(Value::Error(Error::Cycle))
                } else {
                    self.eval_cell(p)
                };
                if let Some(area) = self.store(p, result) {
                    spilled.push((p.0, area));
                }
            }
            if spilled.is_empty() {
                break;
            }
            let evaluated = pending;
            pending = self.dependents(&spilled, 5_000_000).unwrap_or_default();
            pending.retain(|p| {
                !evaluated.contains(p)
                    || spilled
                        .iter()
                        .any(|(s, a)| *s == p.0 && !a.contains(p.1, p.2))
            });
            pending.retain(|p| {
                !spilled
                    .iter()
                    .any(|(s, a)| *s == p.0 && a.contains(p.1, p.2) && !self.is_anchor(*p))
            });
        }
    }

    fn is_anchor(&self, p: Pos) -> bool {
        self.sheets
            .get(p.0)
            .is_some_and(|s| s.spill_areas.contains_key(&(p.1, p.2)))
    }

    fn eval_cell(&self, p: Pos) -> Val {
        let Some(cell) = self.sheets.get(p.0).and_then(|s| s.cell(p.1, p.2)) else {
            return Val::V(Value::Empty);
        };
        let Some(f) = cell.formula() else {
            return Val::V(cell.value.clone());
        };
        let Some(expr) = &f.expr else {
            return Val::V(Value::Error(Error::Parse));
        };
        let grid = BookGrid(self);
        let ctx = Ctx {
            grid: &grid,
            sheet: p.0,
            row: p.1,
            col: p.2,
            shift: (0, 0),
        };
        ctx.eval(expr)
    }

    /// Stores a formula's result; arrays spill into the cells around. Returns the area whose
    /// spilled values changed, if any.
    fn store(&mut self, p: Pos, result: Val) -> Option<Area> {
        let (si, r, c) = p;
        let grid_val = |book: &Book, v: &Val| -> Option<std::sync::Arc<Vec<Vec<Value>>>> {
            match v {
                Val::A(m) if m.len() > 1 || m.first().is_some_and(|x| x.len() > 1) => {
                    Some(m.clone())
                }
                Val::R(_, a) if !a.is_cell() => {
                    let grid = BookGrid(book);
                    let ctx = Ctx {
                        grid: &grid,
                        sheet: si,
                        row: r,
                        col: c,
                        shift: (0, 0),
                    };
                    Some(ctx.matrix(v))
                }
                _ => None,
            }
        };
        let matrix = grid_val(self, &result);
        let scalar = match &result {
            Val::V(v) => v.clone(),
            Val::R(s, a) if a.is_cell() => self
                .sheets
                .get(*s)
                .map(|sh| sh.value(a.r0, a.c0))
                .unwrap_or(Value::Error(Error::Ref)),
            // A one-cell array (`=SEQUENCE(1)`, a FILTER that kept one value) is that value.
            Val::A(m) => m
                .first()
                .and_then(|row| row.first())
                .cloned()
                .unwrap_or(Value::Empty),
            _ => Value::Empty,
        };
        let sheet = &mut self.sheets[si];
        let old_area = sheet.spill_areas.remove(&(r, c));
        if let Some(a) = old_area {
            clear_spill(sheet, a, (r, c));
        }
        let value = match matrix {
            Some(m) => {
                let rows = m.len() as u32;
                let cols = m.first().map_or(0, |x| x.len()) as u32;
                let area = Area::new(
                    r,
                    c,
                    (r + rows - 1).min(MAX_ROWS - 1),
                    (c + cols - 1).min(MAX_COLS - 1),
                );
                sheet.spill_areas.insert((r, c), area);
                let blocked = (area.r0..=area.r1).any(|rr| {
                    (area.c0..=area.c1).any(|cc| {
                        (rr, cc) != (r, c)
                            && (sheet.cell(rr, cc).is_some_and(|x| x.has_content())
                                || sheet
                                    .spill
                                    .get(cc as usize)
                                    .is_some_and(|m| m.contains_key(&rr)))
                    })
                });
                if blocked {
                    Value::Error(Error::Spill)
                } else {
                    for (dr, row) in m.iter().enumerate() {
                        for (dc, v) in row.iter().enumerate() {
                            if dr == 0 && dc == 0 {
                                continue;
                            }
                            let (rr, cc) = (r + dr as u32, c + dc as u32);
                            if sheet.spill.len() <= cc as usize {
                                sheet.spill.resize_with(cc as usize + 1, BTreeMap::new);
                            }
                            sheet.spill[cc as usize].insert(rr, v.clone());
                        }
                    }
                    sheet.grow(area.r1 + 1, area.c1 + 1);
                    m[0][0].clone()
                }
            }
            None => scalar,
        };
        if let Some(cell) = sheet.cols.get_mut(c as usize).and_then(|m| m.get_mut(&r)) {
            cell.value = value;
        }
        let new_area = sheet.spill_areas.get(&(r, c)).copied();
        match (old_area, new_area) {
            (None, None) => None,
            (Some(a), None) | (None, Some(a)) => Some(a),
            (Some(a), Some(b)) => Some(a.union(&b)),
        }
    }

    /// Topological order of the dirty formulas; `true` marks those in a cycle.
    fn order(&self, dirty: &HashSet<Pos>) -> Vec<(Pos, bool)> {
        let mut state: HashMap<Pos, u8> = HashMap::with_capacity(dirty.len());
        let mut out = Vec::with_capacity(dirty.len());
        let mut cyclic: HashSet<Pos> = HashSet::new();
        let mut sorted: Vec<Pos> = dirty.iter().copied().collect();
        sorted.sort_unstable();
        for &start in &sorted {
            if state.contains_key(&start) {
                continue;
            }
            let mut stack: Vec<(Pos, Vec<Pos>, usize)> =
                vec![(start, self.dirty_precedents(start, dirty), 0)];
            state.insert(start, 1);
            while let Some((node, pre, i)) = stack.last_mut() {
                if *i < pre.len() {
                    let next = pre[*i];
                    *i += 1;
                    match state.get(&next) {
                        None => {
                            state.insert(next, 1);
                            let p = self.dirty_precedents(next, dirty);
                            stack.push((next, p, 0));
                        }
                        Some(1) => {
                            // A cycle: every node on the stack from `next` up.
                            let mut mark = false;
                            for (n, _, _) in stack.iter() {
                                if *n == next {
                                    mark = true;
                                }
                                if mark {
                                    cyclic.insert(*n);
                                }
                            }
                        }
                        _ => {}
                    }
                } else {
                    let node = *node;
                    state.insert(node, 2);
                    out.push(node);
                    stack.pop();
                }
            }
        }
        // Formulas that read a cyclic cell are in the cycle's result too.
        out.into_iter().map(|p| (p, cyclic.contains(&p))).collect()
    }

    fn dirty_precedents(&self, p: Pos, dirty: &HashSet<Pos>) -> Vec<Pos> {
        let Some(cell) = self.sheets.get(p.0).and_then(|s| s.cell(p.1, p.2)) else {
            return Vec::new();
        };
        let Some(f) = cell.formula() else {
            return Vec::new();
        };
        let mut out = Vec::new();
        for r in f.refs.iter() {
            let Some((s, a)) = self.resolve_ref(p.0, r) else {
                continue;
            };
            if a.is_cell() {
                let q = (s, a.r0, a.c0);
                if dirty.contains(&q) {
                    out.push(q);
                }
                // A cell filled by another formula's spill depends on that formula.
                if let Some(anchor) = self.spill_anchor(s, a.r0, a.c0)
                    && dirty.contains(&anchor)
                {
                    out.push(anchor);
                }
            } else {
                let sheet = &self.sheets[s];
                for c in a.c0..=a.c1.min(MAX_COLS - 1) {
                    for &(_, rr) in sheet.formulas.range((c, a.r0)..=(c, a.r1)) {
                        let q = (s, rr, c);
                        if dirty.contains(&q) {
                            out.push(q);
                        }
                    }
                    if c > sheet.cols.len() as u32 {
                        break;
                    }
                }
                for (&(ar, ac), area) in &sheet.spill_areas {
                    if area.intersects(&a) && dirty.contains(&(s, ar, ac)) {
                        out.push((s, ar, ac));
                    }
                }
            }
        }
        out
    }

    fn spill_anchor(&self, s: usize, r: u32, c: u32) -> Option<Pos> {
        let sheet = self.sheets.get(s)?;
        sheet.spill.get(c as usize)?.get(&r)?;
        sheet
            .spill_areas
            .iter()
            .find(|(_, a)| a.contains(r, c))
            .map(|(&(ar, ac), _)| (s, ar, ac))
    }

    /// Evaluates a formula as if it were in cell `(row, col)` of `sheet`, its relative
    /// references moved by `shift` (conditional formats and validation formulas).
    pub fn eval_at(
        &self,
        f: &FormulaCell,
        sheet: usize,
        row: u32,
        col: u32,
        shift: (i64, i64),
    ) -> Value {
        let Some(expr) = &f.expr else {
            return Value::Error(Error::Parse);
        };
        let grid = BookGrid(self);
        let ctx = Ctx {
            grid: &grid,
            sheet,
            row,
            col,
            shift,
        };
        ctx.scalar_of(ctx.eval(expr))
    }

    /// The text of every cell of an area, as shown (for copying).
    pub fn grid(&self) -> impl Grid + '_ {
        BookGrid(self)
    }
}

fn clear_spill(sheet: &mut Sheet, area: Area, anchor: (u32, u32)) {
    for c in area.c0..=area.c1 {
        if let Some(m) = sheet.spill.get_mut(c as usize) {
            for r in area.r0..=area.r1 {
                if (r, c) != anchor {
                    m.remove(&r);
                }
            }
        }
    }
}

/// Merges single cells of the same sheet into their bounding areas when they form a block.
fn compact(areas: Vec<(usize, Area)>) -> Vec<(usize, Area)> {
    if areas.len() <= 64 {
        return areas;
    }
    let mut by_sheet: HashMap<usize, Area> = HashMap::new();
    let mut count: HashMap<usize, u64> = HashMap::new();
    for (s, a) in &areas {
        by_sheet
            .entry(*s)
            .and_modify(|b| *b = b.union(a))
            .or_insert(*a);
        *count.entry(*s).or_default() += 1;
    }
    // When the cells fill most of their bounding box, one area is cheaper to look up.
    if by_sheet.iter().all(|(s, b)| b.cells() <= count[s] * 2) {
        return by_sheet.into_iter().collect();
    }
    areas
}
