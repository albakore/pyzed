//! Spreadsheets: `pz.Workbook` (the data, formulas and formats, all in Rust) and the grid
//! widget that shows and edits it (`ui.spreadsheet`).

pub mod addr;
pub mod display;
pub mod eval;
pub mod format;
pub mod formula;
pub mod functions;
pub mod io;
pub mod model;
pub mod ops;
pub mod value;
pub mod view;

use std::sync::{Arc, Mutex, MutexGuard};

use pyo3::exceptions::{PyIndexError, PyKeyError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyBytes, PyDict, PyFloat, PyInt, PyList, PyString, PyTuple};

use addr::{Area, MAX_COLS, MAX_ROWS};
use model::{
    Book, Cell, Check, CondFormat, CondStyle, FormulaCell, HAlign, Input, Rule, Style, VAlign,
    Validation,
};
use value::Value;

/// The `(min, max)` dates of `validate(date=...)`, each a date, a datetime, a string or `None`.
type DateBounds<'py> = (Option<Bound<'py, PyAny>>, Option<Bound<'py, PyAny>>);

/// A shared handle on a workbook: Python and every view of it see the same data.
pub type Shared = Arc<Mutex<Book>>;

fn color_u32(value: &Bound<'_, PyAny>) -> PyResult<Option<u32>> {
    if value.is_none() {
        return Ok(None);
    }
    let c = crate::style::color(value)?;
    let [r, g, b, a] = c.into_rgba8();
    Ok(Some(
        ((r as u32) << 24) | ((g as u32) << 16) | ((b as u32) << 8) | a as u32,
    ))
}

fn color_text(c: u32) -> String {
    if c & 0xFF == 0xFF {
        format!("#{:06x}", c >> 8)
    } else {
        format!("#{c:08x}")
    }
}

/// A spreadsheet workbook: sheets of cells with values, formulas and formats.
///
/// Read and write cells by address (``book["B2"] = "=SUM(A1:A9)"``; ``book["A1:C3"]`` gives
/// rows of values), format them, sort, filter, undo, and open or save CSV and Excel files.
/// Show it (and edit it) with ``ui.Spreadsheet(book=book)`` or ``pz.sheet(book)``. Addresses may name a sheet
/// (``"Sales!A1"``); without one they use the active sheet. Row and column numbers are
/// 1-based, as in the grid; columns are also accepted as letters (``"C"``).
#[pyclass(module = "pyzed._core", name = "Workbook", frozen)]
pub struct Workbook {
    pub inner: Shared,
}

impl Workbook {
    pub fn lock(&self) -> MutexGuard<'_, Book> {
        self.inner.lock().unwrap_or_else(|e| e.into_inner())
    }

    fn wrap(book: Book) -> Self {
        Self {
            inner: Arc::new(Mutex::new(book)),
        }
    }
}

fn utc_offset(py: Python<'_>) -> i64 {
    py.import("time")
        .and_then(|t| t.call_method0("localtime"))
        .and_then(|lt| lt.getattr("tm_gmtoff"))
        .and_then(|v| v.extract::<i64>())
        .unwrap_or(0)
}

/// Resolves `"Sheet!A1:B3"` to a sheet index and an area.
fn target(book: &Book, text: &str) -> PyResult<(usize, Area)> {
    let (name, rest) = addr::split_sheet(text);
    let sheet = match name {
        Some(n) => book
            .sheet_index(&n)
            .ok_or_else(|| PyKeyError::new_err(format!("no sheet called {n:?}")))?,
        None => book.active,
    };
    let area = addr::parse_area(rest)
        .ok_or_else(|| PyValueError::new_err(format!("invalid cell or range {text:?}")))?;
    Ok((sheet, area))
}

fn sheet_of(book: &Book, sheet: Option<&Bound<'_, PyAny>>) -> PyResult<usize> {
    match sheet {
        None => Ok(book.active),
        Some(s) if s.is_none() => Ok(book.active),
        Some(s) => {
            if let Ok(i) = s.extract::<usize>() {
                if i < book.sheets.len() {
                    return Ok(i);
                }
                return Err(PyIndexError::new_err(format!("no sheet {i}")));
            }
            let name: String = s.extract()?;
            book.sheet_index(&name)
                .ok_or_else(|| PyKeyError::new_err(format!("no sheet called {name:?}")))
        }
    }
}

/// A 1-based column number or letters → 0-based index.
fn col_arg(v: &Bound<'_, PyAny>) -> PyResult<u32> {
    if let Ok(n) = v.extract::<i64>() {
        if n < 1 || n > MAX_COLS as i64 {
            return Err(PyValueError::new_err(format!("column {n} out of range")));
        }
        return Ok(n as u32 - 1);
    }
    let s: String = v.extract()?;
    addr::col_index(&s).ok_or_else(|| PyValueError::new_err(format!("invalid column {s:?}")))
}

fn row_arg(n: i64) -> PyResult<u32> {
    if n < 1 || n > MAX_ROWS as i64 {
        return Err(PyValueError::new_err(format!("row {n} out of range")));
    }
    Ok(n as u32 - 1)
}

fn value_to_py<'py>(
    py: Python<'py>,
    v: &Value,
    date_fmt: Option<&str>,
) -> PyResult<Bound<'py, PyAny>> {
    Ok(match v {
        Value::Empty => py.None().into_bound(py),
        Value::Number(n) => {
            if let Some(code) = date_fmt
                && format::get(code).is_date()
            {
                let (y, m, d) = value::serial_date(*n);
                let dt = py.import("datetime")?;
                if n.fract().abs() < 1e-9 && !code.contains(['h', 'H', 's']) {
                    return dt.getattr("date")?.call1((y, m, d));
                }
                let (hh, mm, ss) = value::serial_time(*n);
                if *n < 1.0 {
                    return dt.getattr("time")?.call1((hh, mm, ss));
                }
                return dt.getattr("datetime")?.call1((y, m, d, hh, mm, ss));
            }
            if n.fract() == 0.0 && n.abs() < 9.0e15 {
                (*n as i64).into_pyobject(py)?.into_any()
            } else {
                PyFloat::new(py, *n).into_any()
            }
        }
        Value::Text(t) => PyString::new(py, t).into_any(),
        Value::Bool(b) => PyBool::new(py, *b).to_owned().into_any(),
        Value::Error(e) => PyString::new(py, e.as_str()).into_any(),
    })
}

/// A Python value as cell content: `(input text or value, format for dates)`.
enum Content {
    Typed(String),
    Value(Value, Option<&'static str>),
}

fn content(v: &Bound<'_, PyAny>) -> PyResult<Content> {
    if v.is_none() {
        return Ok(Content::Value(Value::Empty, None));
    }
    if let Ok(b) = v.cast::<PyBool>() {
        return Ok(Content::Value(Value::Bool(b.is_true()), None));
    }
    if v.is_instance_of::<PyInt>() || v.is_instance_of::<PyFloat>() {
        return Ok(Content::Value(eval::num(v.extract::<f64>()?), None));
    }
    if let Ok(s) = v.cast::<PyString>() {
        return Ok(Content::Typed(s.to_cow()?.into_owned()));
    }
    let py = v.py();
    let dt = py.import("datetime")?;
    if v.is_instance(&dt.getattr("datetime")?)? {
        let (y, m, d, hh, mm, ss): (i64, i64, i64, i64, i64, i64) = (
            v.getattr("year")?.extract()?,
            v.getattr("month")?.extract()?,
            v.getattr("day")?.extract()?,
            v.getattr("hour")?.extract()?,
            v.getattr("minute")?.extract()?,
            v.getattr("second")?.extract()?,
        );
        let serial = value::date_serial(y, m, d) + (hh * 3600 + mm * 60 + ss) as f64 / 86400.0;
        return Ok(Content::Value(
            Value::Number(serial),
            Some("yyyy-mm-dd hh:mm"),
        ));
    }
    if v.is_instance(&dt.getattr("date")?)? {
        let (y, m, d): (i64, i64, i64) = (
            v.getattr("year")?.extract()?,
            v.getattr("month")?.extract()?,
            v.getattr("day")?.extract()?,
        );
        return Ok(Content::Value(
            Value::Number(value::date_serial(y, m, d)),
            Some("yyyy-mm-dd"),
        ));
    }
    if v.is_instance(&dt.getattr("time")?)? {
        let (hh, mm, ss): (i64, i64, i64) = (
            v.getattr("hour")?.extract()?,
            v.getattr("minute")?.extract()?,
            v.getattr("second")?.extract()?,
        );
        return Ok(Content::Value(
            Value::Number((hh * 3600 + mm * 60 + ss) as f64 / 86400.0),
            Some("hh:mm"),
        ));
    }
    if let Ok(f) = v.extract::<f64>() {
        return Ok(Content::Value(Value::Number(f), None));
    }
    Ok(Content::Typed(v.str()?.to_cow()?.into_owned()))
}

fn cell_for(
    book: &mut Book,
    sheet: usize,
    r: u32,
    c: u32,
    v: &Bound<'_, PyAny>,
) -> PyResult<Option<Cell>> {
    Ok(match content(v)? {
        Content::Typed(text) => book.typed_cell(sheet, r, c, &text),
        Content::Value(val, fmt) => {
            let old = book.sheets[sheet].cell(r, c).cloned().unwrap_or_default();
            let mut style = old.style;
            if let Some(fmt) = fmt
                && book.style(style).format.is_none()
            {
                let mut st = book.style(style).clone();
                st.format = Some(fmt.into());
                style = book.intern(st);
            }
            let input = if val.is_empty() {
                Input::Empty
            } else {
                Input::Value(val.clone())
            };
            let cell = Cell {
                input,
                value: val,
                style,
                note: old.note,
            };
            (!cell.is_blank()).then_some(cell)
        }
    })
}

fn rule_value(v: Option<&Bound<'_, PyAny>>) -> PyResult<Value> {
    match v {
        None => Ok(Value::Empty),
        Some(v) => Ok(match content(v)? {
            Content::Typed(t) => match model::parse_input(&t, true).0 {
                Input::Value(v) => v,
                _ => Value::text(t),
            },
            Content::Value(v, _) => v,
        }),
    }
}

fn halign(s: &str) -> PyResult<Option<HAlign>> {
    Ok(match s {
        "left" | "start" => Some(HAlign::Left),
        "center" => Some(HAlign::Center),
        "right" | "end" => Some(HAlign::Right),
        "auto" | "general" | "" => None,
        _ => {
            return Err(PyValueError::new_err(format!(
                "invalid align {s:?}: use \"left\", \"center\", \"right\" or \"auto\""
            )));
        }
    })
}

fn valign(s: &str) -> PyResult<Option<VAlign>> {
    Ok(match s {
        "top" => Some(VAlign::Top),
        "middle" | "center" => Some(VAlign::Middle),
        "bottom" => Some(VAlign::Bottom),
        "auto" | "" => None,
        _ => {
            return Err(PyValueError::new_err(format!(
                "invalid valign {s:?}: use \"top\", \"middle\" or \"bottom\""
            )));
        }
    })
}

/// Decimal places of a number format, after adding `delta` (for the toolbar's .0 / .00 buttons).
pub fn adjust_decimals(code: Option<&str>, sample: Option<f64>, delta: i32) -> String {
    let code = code.unwrap_or("General");
    if code.eq_ignore_ascii_case("general") || code.is_empty() {
        let current = sample.map(|n| {
            let t = value::number_text(n);
            t.split_once('.').map_or(0, |(_, d)| d.len() as i32)
        });
        let places = (current.unwrap_or(0) + delta).max(0);
        return if places == 0 {
            "0".into()
        } else {
            format!("0.{}", "0".repeat(places as usize))
        };
    }
    // Change the zeros after the first decimal point of each section.
    let mut out = String::new();
    for (i, sec) in code.split(';').enumerate() {
        if i > 0 {
            out.push(';');
        }
        if let Some(dot) = sec.find('.') {
            let tail = &sec[dot + 1..];
            let zeros = tail.chars().take_while(|c| *c == '0' || *c == '#').count() as i32;
            let n = (zeros + delta).max(0) as usize;
            out.push_str(&sec[..dot]);
            if n > 0 {
                out.push('.');
                out.push_str(&"0".repeat(n));
            }
            out.push_str(&tail[zeros as usize..]);
        } else if delta > 0 {
            // Insert ".0" after the last digit placeholder.
            match sec.rfind(['0', '#']) {
                Some(p) => {
                    out.push_str(&sec[..=p]);
                    out.push('.');
                    out.push_str(&"0".repeat(delta as usize));
                    out.push_str(&sec[p + 1..]);
                }
                None => out.push_str(sec),
            }
        } else {
            out.push_str(sec);
        }
    }
    out
}

#[pymethods]
impl Workbook {
    #[new]
    #[pyo3(signature = (*, sheets=None))]
    fn py_new(py: Python<'_>, sheets: Option<Vec<String>>) -> PyResult<Self> {
        let mut book = Book::new();
        book.utc_offset = utc_offset(py);
        if let Some(names) = sheets.filter(|n| !n.is_empty()) {
            book.sheets = names.iter().map(|n| model::Sheet::new(n)).collect();
        }
        Ok(Self::wrap(book))
    }

    /// Opens a file: ``.xlsx``, ``.xlsm``, ``.xls``, ``.ods``, ``.csv``, ``.tsv`` or ``.txt``.
    #[staticmethod]
    fn open(py: Python<'_>, path: std::path::PathBuf) -> PyResult<Self> {
        let ext = path
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("")
            .to_ascii_lowercase();
        let bytes = py.detach(|| std::fs::read(&path)).map_err(|e| {
            pyo3::exceptions::PyOSError::new_err(format!("{}: {e}", path.display()))
        })?;
        let mut book = match ext.as_str() {
            "csv" | "tsv" | "txt" => {
                let text = String::from_utf8_lossy(&bytes).into_owned();
                let delim = if ext == "tsv" || (ext == "txt" && text.contains('\t')) {
                    '\t'
                } else {
                    sniff(&text)
                };
                let mut b = Book::new();
                let name = path
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .unwrap_or("Sheet1");
                b.sheets[0].name = name
                    .chars()
                    .filter(|c| !"![]*?/\\:".contains(*c))
                    .collect::<String>();
                if b.sheets[0].name.is_empty() {
                    b.sheets[0].name = "Sheet1".into();
                }
                b.load_delimited(0, &text, delim);
                b
            }
            _ => py
                .detach(|| Book::load_excel(bytes))
                .map_err(PyValueError::new_err)?,
        };
        book.utc_offset = utc_offset(py);
        Ok(Self::wrap(book))
    }

    /// A workbook from an Excel or OpenDocument file's bytes.
    #[staticmethod]
    fn from_bytes(py: Python<'_>, data: Vec<u8>) -> PyResult<Self> {
        let mut book = py
            .detach(|| Book::load_excel(data))
            .map_err(PyValueError::new_err)?;
        book.utc_offset = utc_offset(py);
        Ok(Self::wrap(book))
    }

    /// A workbook from CSV (or TSV) text. ``delimiter=None`` guesses it.
    #[staticmethod]
    #[pyo3(signature = (text, delimiter=None))]
    fn from_csv(py: Python<'_>, text: &str, delimiter: Option<char>) -> Self {
        let mut book = Book::new();
        book.utc_offset = utc_offset(py);
        book.load_delimited(0, text, delimiter.unwrap_or_else(|| sniff(text)));
        Self::wrap(book)
    }

    /// A workbook from rows of values (lists, or dicts whose keys become the header row).
    #[staticmethod]
    #[pyo3(signature = (rows, *, header=None, sheet=None))]
    fn from_rows(
        py: Python<'_>,
        rows: &Bound<'_, PyAny>,
        header: Option<Vec<String>>,
        sheet: Option<String>,
    ) -> PyResult<Self> {
        let mut book = Book::new();
        book.utc_offset = utc_offset(py);
        if let Some(name) = sheet {
            book.sheets[0].name = name;
        }
        let wb = Self::wrap(book);
        wb.write_rows(rows, header, 0, 0, 0)?;
        wb.lock().undo.clear();
        Ok(wb)
    }

    /// Saves to ``.xlsx`` or ``.csv``/``.tsv`` (the active sheet), by the file's extension.
    fn save(&self, py: Python<'_>, path: std::path::PathBuf) -> PyResult<()> {
        let ext = path
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("")
            .to_ascii_lowercase();
        let data = match ext.as_str() {
            "csv" => self
                .lock()
                .to_delimited(self.lock().active, ',')
                .into_bytes(),
            "tsv" | "txt" => self
                .lock()
                .to_delimited(self.lock().active, '\t')
                .into_bytes(),
            "xlsx" | "xlsm" => self.lock().save_xlsx().map_err(PyValueError::new_err)?,
            _ => {
                return Err(PyValueError::new_err(format!(
                    "can't save {ext:?} files: use .xlsx, .csv or .tsv"
                )));
            }
        };
        py.detach(|| std::fs::write(&path, data))
            .map_err(|e| pyo3::exceptions::PyOSError::new_err(format!("{}: {e}", path.display())))
    }

    /// The workbook as the bytes of an ``.xlsx`` file.
    fn to_xlsx<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        let data = self.lock().save_xlsx().map_err(PyValueError::new_err)?;
        Ok(PyBytes::new(py, &data))
    }

    /// A sheet (the active one by default) as CSV text, with values as shown.
    #[pyo3(signature = (sheet=None, *, delimiter=','))]
    fn to_csv(&self, sheet: Option<&Bound<'_, PyAny>>, delimiter: char) -> PyResult<String> {
        let b = self.lock();
        let s = sheet_of(&b, sheet)?;
        Ok(b.to_delimited(s, delimiter))
    }

    fn __repr__(&self) -> String {
        let b = self.lock();
        format!(
            "<Workbook sheets={:?} active={:?}>",
            b.sheets.iter().map(|s| s.name.clone()).collect::<Vec<_>>(),
            b.sheet().name
        )
    }

    // --- Cells ---------------------------------------------------------------

    fn __getitem__<'py>(&self, py: Python<'py>, key: &str) -> PyResult<Bound<'py, PyAny>> {
        let (sheet, area) = target(&self.lock(), key)?;
        if area.is_cell() {
            return self.value_at(py, sheet, area.r0, area.c0);
        }
        self.block(py, sheet, area)
    }

    fn __setitem__(&self, key: &str, value: &Bound<'_, PyAny>) -> PyResult<()> {
        self.set(key, value)
    }

    fn __delitem__(&self, key: &str) -> PyResult<()> {
        self.clear(key, "contents")
    }

    /// The value of a cell (formulas give their result; dates give ``datetime.date``).
    fn get<'py>(&self, py: Python<'py>, cell: &str) -> PyResult<Bound<'py, PyAny>> {
        self.__getitem__(py, cell)
    }

    /// Sets a cell, or a range from rows of values. Text is read as if typed: ``"=A1*2"``
    /// is a formula, ``"12%"`` a percentage, ``"2025-03-01"`` a date (``"'12"`` keeps text).
    fn set(&self, cell: &str, value: &Bound<'_, PyAny>) -> PyResult<()> {
        let (sheet, area) = target(&self.lock(), cell)?;
        if !area.is_cell() || value.is_instance_of::<PyList>() || value.is_instance_of::<PyTuple>()
        {
            let rows: Vec<Bound<'_, PyAny>> =
                if value.is_instance_of::<PyList>() || value.is_instance_of::<PyTuple>() {
                    value.try_iter()?.collect::<PyResult<_>>()?
                } else {
                    vec![]
                };
            if rows.is_empty() {
                // One value for the whole range.
                let mut b = self.lock();
                let mut cells = Vec::new();
                let area = area
                    .clamp(
                        b.sheets[sheet].rows.max(area.r1 + 1),
                        b.sheets[sheet].ncols.max(area.c1 + 1),
                    )
                    .unwrap_or(area);
                for r in area.r0..=area.r1 {
                    for c in area.c0..=area.c1 {
                        let cell = cell_for(&mut b, sheet, r, c, value)?;
                        cells.push((r, c, cell));
                    }
                }
                b.write(sheet, cells);
                return Ok(());
            }
            let nested = rows[0].is_instance_of::<PyList>() || rows[0].is_instance_of::<PyTuple>();
            let rows = if nested {
                value.clone()
            } else if area.rows() == 1 && area.cols() > 1 || area.is_cell() {
                // A flat list across a row.
                PyList::new(value.py(), [value.clone()])?.into_any()
            } else {
                // A flat list down a column.
                PyList::new(
                    value.py(),
                    rows.iter()
                        .map(|v| PyList::new(v.py(), [v.clone()]).unwrap()),
                )?
                .into_any()
            };
            return self.write_rows(&rows, None, sheet, area.r0, area.c0);
        }
        let mut b = self.lock();
        let cell = cell_for(&mut b, sheet, area.r0, area.c0, value)?;
        b.write(sheet, vec![(area.r0, area.c0, cell)]);
        Ok(())
    }

    /// Writes rows of values starting at a cell (``"A1"`` by default); dicts write a header row.
    #[pyo3(signature = (rows, at="A1", *, header=None))]
    fn write(
        &self,
        rows: &Bound<'_, PyAny>,
        at: &str,
        header: Option<Vec<String>>,
    ) -> PyResult<()> {
        let (sheet, area) = target(&self.lock(), at)?;
        self.write_rows(rows, header, sheet, area.r0, area.c0)
    }

    /// What a cell holds as typed: ``"=SUM(A1:A3)"``, ``"12.5"``...
    fn formula(&self, cell: &str) -> PyResult<String> {
        let b = self.lock();
        let (sheet, area) = target(&b, cell)?;
        Ok(b.sheets[sheet]
            .cell(area.r0, area.c0)
            .map(|c| c.input_text())
            .unwrap_or_default())
    }

    /// The text a cell shows, in its number format (``"$1,234.50"``, ``"2025-03-01"``).
    fn text(&self, cell: &str) -> PyResult<String> {
        let b = self.lock();
        let (sheet, area) = target(&b, cell)?;
        Ok(ops::shown(&b.sheets[sheet], &b.styles, area.r0, area.c0))
    }

    /// Rows of values of a range (the used range of the active sheet by default).
    #[pyo3(signature = (range=None, *, formulas=false))]
    fn values<'py>(
        &self,
        py: Python<'py>,
        range: Option<&str>,
        formulas: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let (sheet, area) = match range {
            Some(r) => target(&self.lock(), r)?,
            None => {
                let b = self.lock();
                let (rows, cols) = b.sheet().extent();
                if rows == 0 {
                    return Ok(PyList::empty(py).into_any());
                }
                (b.active, Area::new(0, 0, rows - 1, cols - 1))
            }
        };
        if formulas {
            let b = self.lock();
            let s = &b.sheets[sheet];
            let area = clamp_used(s, area);
            let rows = PyList::empty(py);
            for r in area.r0..=area.r1 {
                let row = PyList::empty(py);
                for c in area.c0..=area.c1 {
                    row.append(s.cell(r, c).map(|c| c.input_text()).unwrap_or_default())?;
                }
                rows.append(row)?;
            }
            return Ok(rows.into_any());
        }
        self.block(py, sheet, area)
    }

    /// The rows below a header row as dicts (``{"Name": ..., "Total": ...}``).
    #[pyo3(signature = (range=None))]
    fn records<'py>(&self, py: Python<'py>, range: Option<&str>) -> PyResult<Bound<'py, PyList>> {
        let rows = self.values(py, range, false)?;
        let rows: Vec<Vec<Bound<'py, PyAny>>> = rows.extract()?;
        let out = PyList::empty(py);
        let Some((head, body)) = rows.split_first() else {
            return Ok(out);
        };
        let keys: Vec<String> = head
            .iter()
            .enumerate()
            .map(|(i, k)| {
                if k.is_none() {
                    addr::col_name(i as u32)
                } else {
                    k.str().map(|s| s.to_string()).unwrap_or_default()
                }
            })
            .collect();
        for row in body {
            if row.iter().all(|v| v.is_none()) {
                continue;
            }
            let d = PyDict::new(py);
            for (k, v) in keys.iter().zip(row) {
                d.set_item(k, v)?;
            }
            out.append(d)?;
        }
        Ok(out)
    }

    /// Clears a range: ``what="all"``, ``"contents"`` (keeps the formats) or ``"formats"``.
    #[pyo3(signature = (range, what="all"))]
    fn clear(&self, range: &str, what: &str) -> PyResult<()> {
        if !matches!(what, "all" | "contents" | "formats") {
            return Err(PyValueError::new_err(
                "what must be \"all\", \"contents\" or \"formats\"",
            ));
        }
        let mut b = self.lock();
        let (sheet, area) = target(&b, range)?;
        b.clear(sheet, &[area], what);
        Ok(())
    }

    /// A cell's note (``None``: no note), or sets it with ``text`` (``""`` removes it).
    #[pyo3(signature = (cell, text=None))]
    fn note(&self, cell: &str, text: Option<&str>) -> PyResult<Option<String>> {
        let mut b = self.lock();
        let (sheet, area) = target(&b, cell)?;
        let (r, c) = (area.r0, area.c0);
        match text {
            None => Ok(b.sheets[sheet]
                .cell(r, c)
                .and_then(|c| c.note.as_deref().map(String::from))),
            Some(t) => {
                let mut new = b.sheets[sheet].cell(r, c).cloned().unwrap_or_default();
                new.note = (!t.is_empty()).then(|| t.into());
                b.write(sheet, vec![(r, c, (!new.is_blank()).then_some(new))]);
                Ok(None)
            }
        }
    }

    // --- Formats -------------------------------------------------------------

    /// Formats a range. Colors are ``"#rrggbb"``; ``number_format`` takes Excel codes
    /// (``"#,##0.00"``, ``"0%"``, ``"$#,##0"``, ``"yyyy-mm-dd"``; ``"General"`` resets it);
    /// ``borders`` is ``"all"``, ``"outer"``, ``"inner"``, ``"none"`` or sides like ``"top bottom"``.
    #[pyo3(signature = (range, *, bold=None, italic=None, underline=None, strike=None, color=None, fill=None,
        align=None, valign=None, wrap=None, size=None, mono=None, number_format=None, borders=None, border_color=None))]
    #[allow(clippy::too_many_arguments)]
    fn format(
        &self,
        range: &str,
        bold: Option<bool>,
        italic: Option<bool>,
        underline: Option<bool>,
        strike: Option<bool>,
        color: Option<&Bound<'_, PyAny>>,
        fill: Option<&Bound<'_, PyAny>>,
        align: Option<&str>,
        valign: Option<&str>,
        wrap: Option<bool>,
        size: Option<f32>,
        mono: Option<bool>,
        number_format: Option<&str>,
        borders: Option<&str>,
        border_color: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let mut b = self.lock();
        let (sheet, area) = target(&b, range)?;
        let color = match color {
            Some(c) => Some(color_u32(c)?),
            None => None,
        };
        let fill = match fill {
            Some(c) => Some(color_u32(c)?),
            None => None,
        };
        let border_color = match border_color {
            Some(c) => Some(color_u32(c)?),
            None => None,
        };
        let align = align.map(halign).transpose()?;
        let valign = valign.map(self::valign).transpose()?;
        let number_format = number_format.map(|f| {
            if f.eq_ignore_ascii_case("general") || f.is_empty() {
                None
            } else {
                Some(Arc::<str>::from(f))
            }
        });
        let size = size.map(|s| s.round().clamp(1.0, 400.0) as u16);
        b.grouped(|b| {
            b.restyle(sheet, &[area], |st| {
                if let Some(v) = bold {
                    st.bold = v;
                }
                if let Some(v) = italic {
                    st.italic = v;
                }
                if let Some(v) = underline {
                    st.underline = v;
                }
                if let Some(v) = strike {
                    st.strike = v;
                }
                if let Some(v) = color {
                    st.color = v;
                }
                if let Some(v) = fill {
                    st.fill = v;
                }
                if let Some(v) = align {
                    st.align = v;
                }
                if let Some(v) = valign {
                    st.valign = v;
                }
                if let Some(v) = wrap {
                    st.wrap = v;
                }
                if let Some(v) = size {
                    st.size = Some(v);
                }
                if let Some(v) = mono {
                    st.mono = v;
                }
                if let Some(v) = &number_format {
                    st.format = v.clone();
                }
                if let Some(v) = border_color {
                    st.border_color = v;
                }
            });
            if let Some(spec) = borders {
                apply_borders(b, sheet, area, spec);
            }
        });
        Ok(())
    }

    /// The format of a cell as a dict (only what differs from the default).
    fn style<'py>(&self, py: Python<'py>, cell: &str) -> PyResult<Bound<'py, PyDict>> {
        let b = self.lock();
        let (sheet, area) = target(&b, cell)?;
        let st = b.style(b.sheets[sheet].style_of(area.r0, area.c0)).clone();
        style_dict(py, &st)
    }

    /// Adds or removes decimal places of a range's number format (the toolbar's buttons).
    fn change_decimals(&self, range: &str, delta: i32) -> PyResult<()> {
        let mut b = self.lock();
        let (sheet, area) = target(&b, range)?;
        let st = b.style(b.sheets[sheet].style_of(area.r0, area.c0)).clone();
        let sample = match b.sheets[sheet].value(area.r0, area.c0) {
            Value::Number(n) => Some(n),
            _ => None,
        };
        let code = adjust_decimals(st.format.as_deref(), sample, delta);
        b.restyle(sheet, &[area], |s| s.format = Some(code.as_str().into()));
        Ok(())
    }

    // --- Structure -----------------------------------------------------------

    /// Merges a range into one cell (only the first cell keeps its content).
    fn merge(&self, range: &str) -> PyResult<()> {
        let mut b = self.lock();
        let (sheet, area) = target(&b, range)?;
        b.merge(sheet, area);
        Ok(())
    }

    fn unmerge(&self, range: &str) -> PyResult<()> {
        let mut b = self.lock();
        let (sheet, area) = target(&b, range)?;
        b.unmerge(sheet, area);
        Ok(())
    }

    /// The merged ranges of a sheet.
    #[pyo3(signature = (sheet=None))]
    fn merges(&self, sheet: Option<&Bound<'_, PyAny>>) -> PyResult<Vec<String>> {
        let b = self.lock();
        let s = sheet_of(&b, sheet)?;
        Ok(b.sheets[s].merges.iter().map(|a| a.to_string()).collect())
    }

    /// Keeps the first ``rows`` rows and ``cols`` columns in view while scrolling.
    #[pyo3(signature = (rows=0, cols=0, *, sheet=None))]
    fn freeze(&self, rows: u32, cols: u32, sheet: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, sheet)?;
        b.structural(|b| b.sheets[s].freeze = (rows.min(MAX_ROWS - 1), cols.min(MAX_COLS - 1)));
        Ok(())
    }

    /// The frozen rows and columns of the active sheet.
    #[getter]
    fn frozen(&self) -> (u32, u32) {
        self.lock().sheet().freeze
    }

    /// Inserts ``count`` empty rows before row ``at`` (1-based); formulas adjust.
    #[pyo3(signature = (at, count=1, *, sheet=None))]
    fn insert_rows(&self, at: i64, count: u32, sheet: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, sheet)?;
        b.insert(s, true, row_arg(at)?, count);
        Ok(())
    }

    #[pyo3(signature = (at, count=1, *, sheet=None))]
    fn delete_rows(&self, at: i64, count: u32, sheet: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, sheet)?;
        b.delete(s, true, row_arg(at)?, count);
        Ok(())
    }

    /// Inserts ``count`` empty columns before column ``at`` (a number or letters).
    #[pyo3(signature = (at, count=1, *, sheet=None))]
    fn insert_cols(
        &self,
        at: &Bound<'_, PyAny>,
        count: u32,
        sheet: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, sheet)?;
        b.insert(s, false, col_arg(at)?, count);
        Ok(())
    }

    #[pyo3(signature = (at, count=1, *, sheet=None))]
    fn delete_cols(
        &self,
        at: &Bound<'_, PyAny>,
        count: u32,
        sheet: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, sheet)?;
        b.delete(s, false, col_arg(at)?, count);
        Ok(())
    }

    /// A column's width in pixels, or sets it (``None`` back to the default).
    #[pyo3(signature = (col, width=-1.0, *, sheet=None))]
    fn column_width(
        &self,
        col: &Bound<'_, PyAny>,
        width: Option<f32>,
        sheet: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<f32> {
        let mut b = self.lock();
        let s = sheet_of(&b, sheet)?;
        let c = col_arg(col)?;
        if width != Some(-1.0) {
            b.set_size(s, false, &[c], width);
        }
        Ok(b.sheets[s]
            .col_axis
            .sizes
            .get(&c)
            .copied()
            .unwrap_or(b.sheets[s].col_axis.default))
    }

    /// A row's height in pixels, or sets it (``None`` back to the default).
    #[pyo3(signature = (row, height=-1.0, *, sheet=None))]
    fn row_height(
        &self,
        row: i64,
        height: Option<f32>,
        sheet: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<f32> {
        let mut b = self.lock();
        let s = sheet_of(&b, sheet)?;
        let r = row_arg(row)?;
        if height != Some(-1.0) {
            b.set_size(s, true, &[r], height);
        }
        Ok(b.sheets[s]
            .row_axis
            .sizes
            .get(&r)
            .copied()
            .unwrap_or(b.sheets[s].row_axis.default))
    }

    /// Sets the width of columns to fit their content (approximately, from the text length).
    #[pyo3(signature = (cols=None, *, sheet=None))]
    fn autofit(
        &self,
        cols: Option<Vec<Bound<'_, PyAny>>>,
        sheet: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, sheet)?;
        let list: Vec<u32> = match cols {
            Some(c) => c.iter().map(col_arg).collect::<PyResult<_>>()?,
            None => (0..b.sheets[s].extent().1).collect(),
        };
        let widths: Vec<(u32, f32)> = list
            .iter()
            .map(|&c| (c, view::estimate_width(&b, s, c)))
            .collect();
        b.structural(|b| {
            for (c, w) in widths {
                b.sheets[s].col_axis.sizes.insert(c, w);
            }
            b.sheets[s].col_axis.rebuild();
        });
        Ok(())
    }

    #[pyo3(signature = (rows, *, sheet=None))]
    fn hide_rows(&self, rows: Vec<i64>, sheet: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, sheet)?;
        let idx: Vec<u32> = rows.into_iter().map(row_arg).collect::<PyResult<_>>()?;
        b.set_hidden(s, true, &idx, true);
        Ok(())
    }

    #[pyo3(signature = (rows, *, sheet=None))]
    fn show_rows(&self, rows: Vec<i64>, sheet: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, sheet)?;
        let idx: Vec<u32> = rows.into_iter().map(row_arg).collect::<PyResult<_>>()?;
        b.set_hidden(s, true, &idx, false);
        Ok(())
    }

    #[pyo3(signature = (cols, *, sheet=None))]
    fn hide_cols(
        &self,
        cols: Vec<Bound<'_, PyAny>>,
        sheet: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, sheet)?;
        let idx: Vec<u32> = cols.iter().map(col_arg).collect::<PyResult<_>>()?;
        b.set_hidden(s, false, &idx, true);
        Ok(())
    }

    #[pyo3(signature = (cols, *, sheet=None))]
    fn show_cols(
        &self,
        cols: Vec<Bound<'_, PyAny>>,
        sheet: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, sheet)?;
        let idx: Vec<u32> = cols.iter().map(col_arg).collect::<PyResult<_>>()?;
        b.set_hidden(s, false, &idx, false);
        Ok(())
    }

    /// Sorts the rows of a range by a column (letters or number), or several:
    /// ``by=[("B", False), ("C", True)]`` (``True`` = descending).
    #[pyo3(signature = (range, by, *, descending=false, header=false))]
    fn sort(
        &self,
        range: &str,
        by: &Bound<'_, PyAny>,
        descending: bool,
        header: bool,
    ) -> PyResult<()> {
        let mut b = self.lock();
        let (sheet, area) = target(&b, range)?;
        let keys: Vec<(u32, bool)> = if let Ok(list) = by.cast::<PyList>() {
            list.iter()
                .map(|item| {
                    if let Ok(t) = item.cast::<PyTuple>() {
                        Ok((col_arg(&t.get_item(0)?)?, t.get_item(1)?.extract::<bool>()?))
                    } else {
                        Ok((col_arg(&item)?, descending))
                    }
                })
                .collect::<PyResult<_>>()?
        } else {
            vec![(col_arg(by)?, descending)]
        };
        b.sort(sheet, area, &keys, header);
        Ok(())
    }

    /// Turns on a filter for a range whose first row is the header (``range=None`` turns it off).
    #[pyo3(signature = (range=None, *, sheet=None))]
    fn filter(&self, range: Option<&str>, sheet: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        let mut b = self.lock();
        match range {
            Some(r) => {
                let (s, area) = target(&b, r)?;
                b.set_filter(s, Some(area));
            }
            None => {
                let s = sheet_of(&b, sheet)?;
                b.set_filter(s, None);
            }
        }
        Ok(())
    }

    /// Filters a column: hides rows whose value (as shown) is in ``hide``, and/or keeps the rows
    /// matching ``condition`` (``">100"``, ``"<>done"``, ``"*north*"``). No arguments clears it.
    #[pyo3(signature = (col, *, hide=None, condition=None, sheet=None))]
    fn filter_column(
        &self,
        col: &Bound<'_, PyAny>,
        hide: Option<Vec<String>>,
        condition: Option<String>,
        sheet: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, sheet)?;
        let c = col_arg(col)?;
        if b.sheets[s].filter.is_none() {
            return Err(PyValueError::new_err(
                "the sheet has no filter: call filter(range) first",
            ));
        }
        b.structural(|b| {
            let f = b.sheets[s].filter.as_mut().unwrap();
            match hide {
                Some(h) if !h.is_empty() => {
                    f.hidden.insert(c, h.into_iter().collect());
                }
                _ => {
                    f.hidden.remove(&c);
                }
            }
            match condition {
                Some(cond) if !cond.is_empty() => {
                    f.conditions.insert(c, cond);
                }
                _ => {
                    f.conditions.remove(&c);
                }
            }
        });
        b.apply_filter(s);
        Ok(())
    }

    /// The distinct values of a filter column and whether each is shown: ``[("North", True), ...]``.
    #[pyo3(signature = (col, *, sheet=None))]
    fn filter_values(
        &self,
        col: &Bound<'_, PyAny>,
        sheet: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Vec<(String, bool)>> {
        let b = self.lock();
        let s = sheet_of(&b, sheet)?;
        Ok(b.filter_values(s, col_arg(col)?))
    }

    /// The range of the active sheet's filter (``None`` without one).
    #[getter]
    fn filter_range(&self) -> Option<String> {
        self.lock()
            .sheet()
            .filter
            .as_ref()
            .map(|f| f.area.to_string())
    }

    /// Rows hidden by the filter (1-based).
    #[getter]
    fn filtered_rows(&self) -> Vec<u32> {
        self.lock()
            .sheet()
            .row_axis
            .filtered
            .iter()
            .map(|r| r + 1)
            .collect()
    }

    /// Adds conditional formatting to a range. ``rule``: ``"greater"``, ``"less"``,
    /// ``"greater_equal"``, ``"less_equal"``, ``"equal"``, ``"not_equal"``, ``"between"``,
    /// ``"not_between"`` (with ``value``/``value2``), ``"contains"``, ``"not_contains"``,
    /// ``"starts_with"``, ``"ends_with"`` (text in ``value``), ``"empty"``, ``"not_empty"``,
    /// ``"duplicate"``, ``"unique"``, ``"formula"`` (``value="=$C2>100"``, written for the
    /// range's first cell), ``"color_scale"`` (``colors=[low, (mid,) high]``) or
    /// ``"data_bar"`` (``fill`` is the bar's color).
    #[pyo3(signature = (range, rule, value=None, value2=None, *, color=None, fill=None, bold=None, italic=None, strike=None, underline=None, colors=None))]
    #[allow(clippy::too_many_arguments)]
    fn conditional_format(
        &self,
        range: &str,
        rule: &str,
        value: Option<&Bound<'_, PyAny>>,
        value2: Option<&Bound<'_, PyAny>>,
        color: Option<&Bound<'_, PyAny>>,
        fill: Option<&Bound<'_, PyAny>>,
        bold: Option<bool>,
        italic: Option<bool>,
        strike: Option<bool>,
        underline: Option<bool>,
        colors: Option<Vec<Bound<'_, PyAny>>>,
    ) -> PyResult<()> {
        let mut b = self.lock();
        let (sheet, area) = target(&b, range)?;
        let text = || -> PyResult<String> {
            Ok(value
                .map(|v| v.str().map(|s| s.to_string()))
                .transpose()?
                .unwrap_or_default())
        };
        let cmp = |op: &str| -> PyResult<Rule> {
            Ok(Rule::Compare(
                op.into(),
                rule_value(value)?,
                rule_value(value2)?,
            ))
        };
        let rule = match rule {
            "greater" | ">" => cmp(">")?,
            "less" | "<" => cmp("<")?,
            "greater_equal" | ">=" => cmp(">=")?,
            "less_equal" | "<=" => cmp("<=")?,
            "equal" | "=" | "==" => cmp("=")?,
            "not_equal" | "<>" | "!=" => cmp("<>")?,
            "between" => cmp("between")?,
            "not_between" => cmp("not_between")?,
            "contains" => Rule::TextContains(text()?),
            "not_contains" => Rule::TextNotContains(text()?),
            "starts_with" => Rule::TextStarts(text()?),
            "ends_with" => Rule::TextEnds(text()?),
            "empty" => Rule::Empty,
            "not_empty" => Rule::NotEmpty,
            "duplicate" => Rule::Duplicate,
            "unique" => Rule::Unique,
            "formula" => {
                let src = text()?;
                let src = src.strip_prefix('=').unwrap_or(&src);
                let f = FormulaCell::new(src);
                if f.expr.is_none() {
                    return Err(PyValueError::new_err(format!("invalid formula {src:?}")));
                }
                Rule::Formula(Arc::new(f))
            }
            "color_scale" | "scale" => {
                let cs: Vec<u32> = match colors {
                    Some(c) => c
                        .iter()
                        .map(|c| color_u32(c).map(|c| c.unwrap_or(0xFFFFFFFF)))
                        .collect::<PyResult<_>>()?,
                    None => vec![0xF8696BFF, 0xFFEB84FF, 0x63BE7BFF],
                };
                if !(2..=3).contains(&cs.len()) {
                    return Err(PyValueError::new_err("color_scale takes 2 or 3 colors"));
                }
                Rule::Scale(cs)
            }
            "data_bar" | "bar" => Rule::Bar(match fill.or(color) {
                Some(f) => color_u32(f)?.unwrap_or(0x638EC6FF),
                None => 0x638EC6FF,
            }),
            other => return Err(PyValueError::new_err(format!("unknown rule {other:?}"))),
        };
        let style = CondStyle {
            color: if matches!(rule, Rule::Bar(_)) {
                None
            } else {
                color.map(color_u32).transpose()?.flatten()
            },
            fill: if matches!(rule, Rule::Bar(_)) {
                None
            } else {
                fill.map(color_u32).transpose()?.flatten()
            },
            bold,
            italic,
            strike,
            underline,
        };
        b.structural(|b| {
            b.sheets[sheet]
                .conditional
                .push(CondFormat { area, rule, style })
        });
        Ok(())
    }

    /// Removes the conditional formats that touch a range (all of the sheet's without one).
    #[pyo3(signature = (range=None))]
    fn clear_conditional_formats(&self, range: Option<&str>) -> PyResult<()> {
        let mut b = self.lock();
        let (sheet, area) = match range {
            Some(r) => target(&b, r)?,
            None => (b.active, Area::new(0, 0, MAX_ROWS - 1, MAX_COLS - 1)),
        };
        b.structural(|b| {
            b.sheets[sheet]
                .conditional
                .retain(|cf| !cf.area.intersects(&area))
        });
        Ok(())
    }

    /// The conditional formats of the active sheet: ``[(range, rule), ...]``.
    fn conditional_formats(&self) -> Vec<(String, String)> {
        let b = self.lock();
        b.sheet()
            .conditional
            .iter()
            .map(|cf| {
                let rule = match &cf.rule {
                    Rule::Compare(op, ..) => op.clone(),
                    Rule::TextContains(_) => "contains".into(),
                    Rule::TextNotContains(_) => "not_contains".into(),
                    Rule::TextStarts(_) => "starts_with".into(),
                    Rule::TextEnds(_) => "ends_with".into(),
                    Rule::Empty => "empty".into(),
                    Rule::NotEmpty => "not_empty".into(),
                    Rule::Formula(f) => format!("={}", f.src),
                    Rule::Scale(_) => "color_scale".into(),
                    Rule::Bar(_) => "data_bar".into(),
                    Rule::Duplicate => "duplicate".into(),
                    Rule::Unique => "unique".into(),
                };
                (cf.area.to_string(), rule)
            })
            .collect()
    }

    /// Validates what can go in a range: ``options=[...]`` (a dropdown) or ``source="Sheet2!A1:A9"``
    /// (a dropdown with a range's values), ``number=(min, max)`` (``integer=True`` for whole
    /// numbers), ``date=(min, max)``, ``length=(min, max)``, ``checkbox=True`` (TRUE/FALSE
    /// shown as checkboxes) or ``formula="=B2<=C2"``. ``strict=False`` keeps invalid values but
    /// marks them; ``message`` is shown when a value is refused.
    #[pyo3(signature = (range, *, options=None, source=None, number=None, integer=false, date=None, length=None, checkbox=false, formula=None, strict=true, message=None))]
    #[allow(clippy::too_many_arguments)]
    fn validate(
        &self,
        range: &str,
        options: Option<Vec<String>>,
        source: Option<String>,
        number: Option<(Option<f64>, Option<f64>)>,
        integer: bool,
        date: Option<DateBounds<'_>>,
        length: Option<(Option<usize>, Option<usize>)>,
        checkbox: bool,
        formula: Option<String>,
        strict: bool,
        message: Option<String>,
    ) -> PyResult<()> {
        let mut b = self.lock();
        let (sheet, area) = target(&b, range)?;
        let date_num = |v: &Option<Bound<'_, PyAny>>| -> PyResult<Option<f64>> {
            match v {
                None => Ok(None),
                Some(v) => match content(v)? {
                    Content::Value(Value::Number(n), _) => Ok(Some(n)),
                    Content::Typed(t) => Ok(value::parse_date(&t, b.month_first).map(|d| d.0)),
                    _ => Ok(None),
                },
            }
        };
        let check = if let Some(o) = options {
            Check::List(o)
        } else if let Some(src) = source {
            Check::ListRange(src)
        } else if let Some((min, max)) = number {
            Check::Number { min, max, integer }
        } else if integer {
            Check::Number {
                min: None,
                max: None,
                integer,
            }
        } else if let Some((min, max)) = &date {
            Check::Date {
                min: date_num(min)?,
                max: date_num(max)?,
            }
        } else if let Some((min, max)) = length {
            Check::TextLength { min, max }
        } else if checkbox {
            Check::Checkbox
        } else if let Some(f) = formula {
            let src = f.strip_prefix('=').unwrap_or(&f).to_string();
            let fc = FormulaCell::new(&src);
            if fc.expr.is_none() {
                return Err(PyValueError::new_err(format!("invalid formula {f:?}")));
            }
            Check::Formula(Arc::new(fc))
        } else {
            return Err(PyTypeError::new_err(
                "validate needs options, source, number, date, length, checkbox or formula",
            ));
        };
        let is_checkbox = matches!(check, Check::Checkbox);
        b.structural(|b| {
            let s = &mut b.sheets[sheet];
            s.validations.retain(|v| !(v.area == area));
            s.validations.push(Validation {
                area,
                check,
                strict,
                message,
            });
            if is_checkbox {
                // Empty checkbox cells start unchecked.
                let area = area.clamp(s.rows, s.ncols).unwrap_or(area);
                for r in area.r0..=area.r1.min(area.r0 + 100_000) {
                    for c in area.c0..=area.c1 {
                        if !s.cell(r, c).is_some_and(|x| x.has_content()) {
                            let style = s.style_of(r, c);
                            s.put(
                                r,
                                c,
                                Some(Cell {
                                    input: Input::Value(Value::Bool(false)),
                                    value: Value::Bool(false),
                                    style,
                                    note: None,
                                }),
                            );
                        }
                    }
                }
            }
        });
        Ok(())
    }

    /// Removes the validation rules that touch a range.
    fn clear_validation(&self, range: &str) -> PyResult<()> {
        let mut b = self.lock();
        let (sheet, area) = target(&b, range)?;
        b.structural(|b| {
            b.sheets[sheet]
                .validations
                .retain(|v| !v.area.intersects(&area))
        });
        Ok(())
    }

    /// The dropdown options of a cell (``None`` when it has no dropdown).
    fn options(&self, cell: &str) -> PyResult<Option<Vec<String>>> {
        let b = self.lock();
        let (sheet, area) = target(&b, cell)?;
        Ok(b.dropdown(sheet, area.r0, area.c0))
    }

    /// Whether a cell's value passes its validation rule.
    fn is_valid(&self, cell: &str) -> PyResult<bool> {
        let b = self.lock();
        let (sheet, area) = target(&b, cell)?;
        let v = b.sheets[sheet].value(area.r0, area.c0);
        Ok(b.valid(sheet, area.r0, area.c0, &v))
    }

    // --- Find, copy, fill ---------------------------------------------------------

    /// Addresses of the cells containing ``text`` (``"A1"``, or ``"Sheet2!A1"`` with ``all_sheets``).
    #[pyo3(signature = (text, *, match_case=false, whole_cell=false, formulas=false, all_sheets=false))]
    fn find(
        &self,
        text: &str,
        match_case: bool,
        whole_cell: bool,
        formulas: bool,
        all_sheets: bool,
    ) -> Vec<String> {
        let b = self.lock();
        let hits = b.find(
            text,
            match_case,
            whole_cell,
            formulas,
            (!all_sheets).then_some(b.active),
        );
        hits.into_iter()
            .map(|(s, r, c)| {
                let a = Area::cell(r, c).to_string();
                if all_sheets {
                    format!("{}!{a}", addr::quote_sheet(&b.sheets[s].name))
                } else {
                    a
                }
            })
            .collect()
    }

    /// Replaces ``text`` with ``new`` in every cell (or only in ``cell``); returns how many changed.
    #[pyo3(signature = (text, new, *, match_case=false, whole_cell=false, all_sheets=false, cell=None))]
    fn replace(
        &self,
        text: &str,
        new: &str,
        match_case: bool,
        whole_cell: bool,
        all_sheets: bool,
        cell: Option<&str>,
    ) -> PyResult<usize> {
        let mut b = self.lock();
        let only = match cell {
            Some(c) => {
                let (s, a) = target(&b, c)?;
                Some((s, a.r0, a.c0))
            }
            None => None,
        };
        let sheets = (!all_sheets).then_some(b.active);
        Ok(b.replace(text, new, match_case, whole_cell, sheets, only))
    }

    /// Copies a range (the selection by default): returns its text as TSV, what other
    /// spreadsheets paste. Pasting it back here keeps formulas and formats.
    #[pyo3(signature = (range=None, *, cut=false))]
    fn copy(&self, range: Option<&str>, cut: bool) -> PyResult<String> {
        let mut b = self.lock();
        let (sheet, area) = match range {
            Some(r) => target(&b, r)?,
            None => (b.active, b.sheet().selection.range()),
        };
        Ok(b.copy(sheet, area, cut))
    }

    /// Pastes TSV text (from Google Sheets, Excel or ``copy()``) at a cell (the selection by default).
    #[pyo3(signature = (text, at=None, *, values_only=false))]
    fn paste(&self, text: &str, at: Option<&str>, values_only: bool) -> PyResult<String> {
        let mut b = self.lock();
        let (sheet, area) = match at {
            Some(r) => target(&b, r)?,
            None => (b.active, b.sheet().selection.range()),
        };
        Ok(b.paste(sheet, area, text, values_only).to_string())
    }

    /// Extends ``source`` over ``target`` like the fill handle: series continue, formulas move.
    fn fill(&self, source: &str, target_range: &str) -> PyResult<()> {
        let mut b = self.lock();
        let (sheet, src) = target(&b, source)?;
        let (_, dst) = target(&b, target_range)?;
        b.fill(sheet, src, src.union(&dst));
        Ok(())
    }

    // --- Undo ---------------------------------------------------------------------

    fn undo(&self) -> bool {
        self.lock().undo()
    }

    fn redo(&self) -> bool {
        self.lock().redo()
    }

    #[getter]
    fn can_undo(&self) -> bool {
        self.lock().can_undo()
    }

    #[getter]
    fn can_redo(&self) -> bool {
        self.lock().can_redo()
    }

    /// Runs ``fn()`` so all its changes undo in one step.
    fn batch(&self, py: Python<'_>, f: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        // The lock can't be held while Python runs; record the undo depth instead and merge.
        let start = self.lock().undo.len();
        let out = f.call0()?;
        let mut b = self.lock();
        if b.undo.len() > start + 1 {
            let tail: Vec<model::Change> = b.undo.drain(start..).collect();
            b.grouped(|b| {
                for c in tail {
                    b.push_raw(c);
                }
            });
        }
        let _ = py;
        Ok(out.unbind())
    }

    // --- Sheets ---------------------------------------------------------------------

    /// The sheet names, in order.
    #[getter]
    fn sheets(&self) -> Vec<String> {
        self.lock().sheets.iter().map(|s| s.name.clone()).collect()
    }

    /// The index of the active sheet (the one the grid shows and addresses without a sheet use).
    #[getter]
    fn get_active(&self) -> usize {
        self.lock().active
    }

    #[setter]
    fn set_active(&self, value: &Bound<'_, PyAny>) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, Some(value))?;
        b.active = s;
        b.touch();
        Ok(())
    }

    /// The name of the active sheet.
    #[getter]
    fn sheet(&self) -> String {
        self.lock().sheet().name.clone()
    }

    /// Adds a sheet (named ``Sheet2``... by default) and makes it active; returns its name.
    #[pyo3(signature = (name=None, *, index=None))]
    fn add_sheet(&self, name: Option<&str>, index: Option<usize>) -> String {
        let mut b = self.lock();
        let i = b.add_sheet(name, index);
        b.sheets[i].name.clone()
    }

    fn remove_sheet(&self, sheet: &Bound<'_, PyAny>) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, Some(sheet))?;
        if !b.remove_sheet(s) {
            return Err(PyValueError::new_err("a workbook needs at least one sheet"));
        }
        Ok(())
    }

    fn rename_sheet(&self, sheet: &Bound<'_, PyAny>, name: &str) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, Some(sheet))?;
        b.rename_sheet(s, name).map_err(PyValueError::new_err)
    }

    fn move_sheet(&self, sheet: &Bound<'_, PyAny>, index: usize) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, Some(sheet))?;
        let last = b.sheets.len() - 1;
        b.move_sheet(s, index.min(last));
        Ok(())
    }

    /// Copies a sheet next to it; returns the copy's name.
    fn duplicate_sheet(&self, sheet: &Bound<'_, PyAny>) -> PyResult<String> {
        let mut b = self.lock();
        let s = sheet_of(&b, Some(sheet))?;
        let i = b.duplicate_sheet(s);
        Ok(b.sheets[i].name.clone())
    }

    /// A sheet's tab color (``"#rrggbb"``), or sets it (``None`` removes it).
    #[pyo3(signature = (sheet, color=None))]
    fn tab_color(
        &self,
        sheet: &Bound<'_, PyAny>,
        color: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Option<String>> {
        let mut b = self.lock();
        let s = sheet_of(&b, Some(sheet))?;
        if let Some(c) = color {
            let c = color_u32(c)?;
            b.structural(|b| b.sheets[s].tab_color = c);
        }
        Ok(b.sheets[s].tab_color.map(color_text))
    }

    /// Whether the active sheet shows grid lines.
    #[getter]
    fn get_gridlines(&self) -> bool {
        self.lock().sheet().gridlines
    }

    #[setter]
    fn set_gridlines(&self, on: bool) {
        let mut b = self.lock();
        b.structural(|b| b.sheet_mut().gridlines = on);
    }

    // --- Selection --------------------------------------------------------------

    /// Sum, average, count, smallest and largest number of a range (the selection by
    /// default), as the status bar of Sheets and Excel shows: a dict with ``sum``,
    /// ``average``, ``count`` (cells with a value), ``numbers``, ``min`` and ``max``.
    #[pyo3(signature = (range=None))]
    fn stats<'py>(&self, py: Python<'py>, range: Option<&str>) -> PyResult<Bound<'py, PyDict>> {
        let b = self.lock();
        let (sheet, areas) = match range {
            Some(r) => {
                let (s, a) = target(&b, r)?;
                (s, vec![a])
            }
            None => (b.active, b.sheet().selection.ranges.clone()),
        };
        let (mut sum, mut count, mut numbers) = (0.0f64, 0usize, 0usize);
        let (mut lo, mut hi) = (f64::INFINITY, f64::NEG_INFINITY);
        for a in areas {
            let a = clamp_used(&b.sheets[sheet], a);
            eval::Grid::for_each(&b.grid(), sheet, a, &mut |_, _, v| {
                if v.is_empty() {
                    return;
                }
                count += 1;
                if let Value::Number(n) = v {
                    numbers += 1;
                    sum += n;
                    lo = lo.min(*n);
                    hi = hi.max(*n);
                }
            });
        }
        let d = PyDict::new(py);
        d.set_item("sum", sum)?;
        d.set_item(
            "average",
            if numbers > 0 {
                Some(sum / numbers as f64)
            } else {
                None
            },
        )?;
        d.set_item("count", count)?;
        d.set_item("numbers", numbers)?;
        d.set_item("min", if numbers > 0 { Some(lo) } else { None })?;
        d.set_item("max", if numbers > 0 { Some(hi) } else { None })?;
        Ok(d)
    }

    /// Whether the grid (``pz.sheet``) has the keyboard focus; set it to give it back (after a
    /// toolbar button, for example).
    #[getter]
    fn get_focused(&self) -> bool {
        self.lock().ui.focused
    }

    #[setter]
    fn set_focused(&self, value: bool) {
        let mut b = self.lock();
        b.ui.focused = value;
    }

    /// The cell being typed in (``None`` when nothing is being edited) and its text so far.
    #[getter]
    fn editing(&self) -> Option<(String, String)> {
        let b = self.lock();
        b.ui.edit.as_ref().map(|e| {
            (
                format!(
                    "{}!{}",
                    addr::quote_sheet(&b.sheets[e.sheet].name),
                    Area::cell(e.row, e.col)
                ),
                e.text.clone(),
            )
        })
    }

    /// The selected range of the active sheet (``"B2:D9"``).
    #[getter]
    fn selection(&self) -> String {
        self.lock().sheet().selection.range().to_string()
    }

    /// Every selected range (Ctrl+click adds ranges).
    #[getter]
    fn selections(&self) -> Vec<String> {
        self.lock()
            .sheet()
            .selection
            .ranges
            .iter()
            .map(|a| a.to_string())
            .collect()
    }

    /// The active cell (``"B2"``).
    #[getter]
    fn active_cell(&self) -> String {
        let (r, c) = self.lock().sheet().selection.active;
        Area::cell(r, c).to_string()
    }

    /// Selects a range (and shows it); ``"Sheet2!A1"`` also switches sheets.
    fn select(&self, range: &str) -> PyResult<()> {
        let mut b = self.lock();
        let (sheet, area) = target(&b, range)?;
        b.active = sheet;
        let s = &mut b.sheets[sheet];
        s.grow(area.r1.min(MAX_ROWS - 2) + 2, area.c1.min(MAX_COLS - 2) + 2);
        s.selection = model::Selection {
            ranges: vec![area],
            active: (area.r0, area.c0),
            anchor: (area.r0, area.c0),
        };
        view::request_reveal(&mut b);
        b.touch();
        Ok(())
    }

    // --- Info -----------------------------------------------------------------

    /// The used range of the active sheet (``"A1:F120"``; ``None`` when it is empty).
    #[getter]
    fn used_range(&self) -> Option<String> {
        let b = self.lock();
        let (r, c) = b.sheet().extent();
        (r > 0).then(|| Area::new(0, 0, r - 1, c - 1).to_string())
    }

    /// The rows and columns the grid shows for the active sheet (they grow as you go).
    #[getter]
    fn get_size(&self) -> (u32, u32) {
        let b = self.lock();
        (b.sheet().rows, b.sheet().ncols)
    }

    /// Sets how many rows and columns the grid shows.
    #[pyo3(signature = (rows, cols, *, sheet=None))]
    fn resize(&self, rows: u32, cols: u32, sheet: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        let mut b = self.lock();
        let s = sheet_of(&b, sheet)?;
        b.structural(|b| {
            b.sheets[s].rows = rows.clamp(1, MAX_ROWS);
            b.sheets[s].ncols = cols.clamp(1, MAX_COLS);
        });
        Ok(())
    }

    /// Bumped by every change: compare it to know whether the workbook changed.
    #[getter]
    fn version(&self) -> u64 {
        self.lock().version
    }

    /// The cells changed since the last call (``["A1", "Sheet2!B3"]``), and forgets them.
    fn changes(&self) -> Vec<String> {
        let mut b = self.lock();
        let list = std::mem::take(&mut b.changed);
        let mut seen = std::collections::HashSet::new();
        list.into_iter()
            .filter(|p| seen.insert(*p))
            .map(|(s, r, c)| {
                let a = Area::cell(r, c).to_string();
                if s == b.active {
                    a
                } else {
                    format!(
                        "{}!{a}",
                        addr::quote_sheet(
                            &b.sheets.get(s).map(|x| x.name.clone()).unwrap_or_default()
                        )
                    )
                }
            })
            .collect()
    }

    /// Recalculates every formula (volatile ones like ``NOW()`` and ``RAND()`` change).
    fn recalculate(&self) {
        let mut b = self.lock();
        b.recalc_all();
        b.touch();
    }

    /// Whether the grid refuses edits (the API can still change the workbook).
    #[getter]
    fn get_readonly(&self) -> bool {
        self.lock().readonly
    }

    #[setter]
    fn set_readonly(&self, value: bool) {
        let mut b = self.lock();
        b.readonly = value;
        b.touch();
    }

    /// Typed dates such as ``03/04/2025`` are read month first (``True``, US) or day first.
    #[getter]
    fn get_month_first(&self) -> bool {
        self.lock().month_first
    }

    #[setter]
    fn set_month_first(&self, value: bool) {
        self.lock().month_first = value;
    }

    /// The functions formulas can use: ``[(name, arguments, description), ...]``.
    #[staticmethod]
    fn functions() -> Vec<(&'static str, &'static str, &'static str)> {
        functions::FUNCTIONS.to_vec()
    }

    /// The column letters of a 1-based number (``column_name(28) == "AB"``).
    #[staticmethod]
    fn column_name(col: u32) -> PyResult<String> {
        if col == 0 || col > MAX_COLS {
            return Err(PyValueError::new_err("columns go from 1 to 16384"));
        }
        Ok(addr::col_name(col - 1))
    }
}

impl Workbook {
    fn value_at<'py>(
        &self,
        py: Python<'py>,
        sheet: usize,
        r: u32,
        c: u32,
    ) -> PyResult<Bound<'py, PyAny>> {
        let b = self.lock();
        let s = &b.sheets[sheet];
        let fmt = b.style(s.style_of(r, c)).format.clone();
        value_to_py(py, &s.value(r, c), fmt.as_deref())
    }

    fn block<'py>(&self, py: Python<'py>, sheet: usize, area: Area) -> PyResult<Bound<'py, PyAny>> {
        let b = self.lock();
        let s = &b.sheets[sheet];
        let area = clamp_used(s, area);
        let rows = PyList::empty(py);
        if area.cells() > 50_000_000 {
            return Err(PyValueError::new_err("range too large"));
        }
        for r in area.r0..=area.r1 {
            let row = PyList::empty(py);
            for c in area.c0..=area.c1 {
                let fmt = b.style(s.style_of(r, c)).format.clone();
                row.append(value_to_py(py, &s.value(r, c), fmt.as_deref())?)?;
            }
            rows.append(row)?;
        }
        Ok(rows.into_any())
    }

    fn write_rows(
        &self,
        rows: &Bound<'_, PyAny>,
        header: Option<Vec<String>>,
        sheet: usize,
        r0: u32,
        c0: u32,
    ) -> PyResult<()> {
        let items: Vec<Bound<'_, PyAny>> = rows.try_iter()?.collect::<PyResult<_>>()?;
        let mut b = self.lock();
        let mut cells = Vec::new();
        let mut r = r0;
        let dicts = items.first().is_some_and(|i| i.is_instance_of::<PyDict>());
        let keys: Option<Vec<String>> = if dicts {
            Some(header.clone().unwrap_or_else(|| {
                let mut keys: Vec<String> = Vec::new();
                for i in &items {
                    if let Ok(d) = i.cast::<PyDict>() {
                        for k in d.keys() {
                            let k = k.str().map(|s| s.to_string()).unwrap_or_default();
                            if !keys.contains(&k) {
                                keys.push(k);
                            }
                        }
                    }
                }
                keys
            }))
        } else {
            header.clone()
        };
        if let Some(keys) = &keys {
            for (j, k) in keys.iter().enumerate() {
                let cell = b.typed_cell(sheet, r, c0 + j as u32, &format!("'{k}"));
                cells.push((r, c0 + j as u32, cell));
            }
            r += 1;
        }
        for item in &items {
            if r >= MAX_ROWS {
                break;
            }
            if let (true, Some(keys)) = (dicts, &keys) {
                let d = item.cast::<PyDict>()?;
                for (j, k) in keys.iter().enumerate() {
                    let v = d
                        .get_item(k)?
                        .unwrap_or_else(|| item.py().None().into_bound(item.py()));
                    let cell = cell_for(&mut b, sheet, r, c0 + j as u32, &v)?;
                    cells.push((r, c0 + j as u32, cell));
                }
            } else {
                let values: Vec<Bound<'_, PyAny>> = if item.is_instance_of::<PyString>() {
                    vec![item.clone()]
                } else {
                    item.try_iter()?.collect::<PyResult<_>>()?
                };
                for (j, v) in values.iter().enumerate() {
                    let c = c0 + j as u32;
                    if c >= MAX_COLS {
                        break;
                    }
                    let cell = cell_for(&mut b, sheet, r, c, v)?;
                    cells.push((r, c, cell));
                }
            }
            r += 1;
        }
        b.write(sheet, cells);
        Ok(())
    }
}

/// An area limited to what the sheet uses (whole columns stop at the last row with data).
fn clamp_used(s: &model::Sheet, area: Area) -> Area {
    let (rows, cols) = s.extent();
    let rows = rows.max(area.r0 + 1);
    let cols = cols.max(area.c0 + 1);
    if area.whole_cols() || area.whole_rows() || area.r1 >= rows || area.c1 >= cols {
        let r1 = if area.whole_cols() || area.r1 >= MAX_ROWS - 1 {
            area.r1.min(rows - 1)
        } else {
            area.r1
        };
        let c1 = if area.whole_rows() || area.c1 >= MAX_COLS - 1 {
            area.c1.min(cols - 1)
        } else {
            area.c1
        };
        return Area::new(area.r0, area.c0, r1.max(area.r0), c1.max(area.c0));
    }
    area
}

fn sniff(text: &str) -> char {
    let line = text.lines().next().unwrap_or("");
    let count = |c: char| line.matches(c).count();
    [',', ';', '\t', '|']
        .into_iter()
        .max_by_key(|&c| count(c))
        .filter(|&c| count(c) > 0)
        .unwrap_or(',')
}

fn style_dict<'py>(py: Python<'py>, st: &Style) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    if st.bold {
        d.set_item("bold", true)?;
    }
    if st.italic {
        d.set_item("italic", true)?;
    }
    if st.underline {
        d.set_item("underline", true)?;
    }
    if st.strike {
        d.set_item("strike", true)?;
    }
    if let Some(c) = st.color {
        d.set_item("color", color_text(c))?;
    }
    if let Some(c) = st.fill {
        d.set_item("fill", color_text(c))?;
    }
    if let Some(a) = st.align {
        d.set_item(
            "align",
            match a {
                HAlign::Left => "left",
                HAlign::Center => "center",
                HAlign::Right => "right",
            },
        )?;
    }
    if let Some(a) = st.valign {
        d.set_item(
            "valign",
            match a {
                VAlign::Top => "top",
                VAlign::Middle => "middle",
                VAlign::Bottom => "bottom",
            },
        )?;
    }
    if st.wrap {
        d.set_item("wrap", true)?;
    }
    if let Some(s) = st.size {
        d.set_item("size", s)?;
    }
    if st.mono {
        d.set_item("mono", true)?;
    }
    if let Some(f) = &st.format {
        d.set_item("number_format", &**f)?;
    }
    if st.borders.iter().any(|b| *b) {
        let names = ["top", "right", "bottom", "left"];
        let sides: Vec<&str> = st
            .borders
            .iter()
            .zip(names)
            .filter(|(b, _)| **b)
            .map(|(_, n)| n)
            .collect();
        d.set_item("borders", sides.join(" "))?;
    }
    if let Some(c) = st.border_color {
        d.set_item("border_color", color_text(c))?;
    }
    Ok(d)
}

/// `"all"`, `"outer"`, `"inner"`, `"none"` or sides (`"top bottom"`) over an area.
pub fn apply_borders(b: &mut Book, sheet: usize, area: Area, spec: &str) {
    let spec = spec.to_ascii_lowercase();
    let words: Vec<&str> = spec.split_whitespace().collect();
    let has = |w: &str| words.contains(&w);
    let area = area
        .clamp(b.sheets[sheet].rows, b.sheets[sheet].ncols)
        .unwrap_or(area);
    if area.cells() > 1_000_000 {
        return;
    }
    for r in area.r0..=area.r1 {
        for c in area.c0..=area.c1 {
            let top = r == area.r0;
            let bottom = r == area.r1;
            let left = c == area.c0;
            let right = c == area.c1;
            let sides = if has("none") {
                Some([false; 4])
            } else if has("all") {
                Some([true; 4])
            } else if has("outer") {
                Some([top, right, bottom, left])
            } else if has("inner") {
                Some([!top, !right, !bottom, !left])
            } else {
                None
            };
            let explicit = [
                has("top") && top,
                has("right") && right,
                has("bottom") && bottom,
                has("left") && left,
            ];
            b.restyle(sheet, &[Area::cell(r, c)], |st| match sides {
                Some(s) if has("none") => st.borders = s,
                Some(s) => {
                    for (side, on) in st.borders.iter_mut().zip(s) {
                        *side |= on;
                    }
                }
                None => {
                    for (side, on) in st.borders.iter_mut().zip(explicit) {
                        *side |= on;
                    }
                }
            });
        }
    }
}

/// Reads the colors of `pz.sheet(colors=...)` (keys as in `view::Colors`).
fn sheet_colors(colors: Option<&Bound<'_, PyDict>>) -> PyResult<view::Colors> {
    let mut out = view::Colors::default();
    let Some(d) = colors else { return Ok(out) };
    for (k, v) in d.iter() {
        let key: String = k.extract()?;
        if key == "refs" {
            let mut list = Vec::new();
            for item in v.try_iter()? {
                list.push(crate::style::color(&item?)?);
            }
            if !list.is_empty() {
                out.refs = list;
            }
            continue;
        }
        let c = crate::style::color(&v)?;
        let slot = match key.as_str() {
            "background" => &mut out.background,
            "grid" => &mut out.grid,
            "header" => &mut out.header,
            "header_text" => &mut out.header_text,
            "header_active" => &mut out.header_active,
            "header_active_text" => &mut out.header_active_text,
            "text" => &mut out.text,
            "muted" => &mut out.muted,
            "accent" => &mut out.accent,
            "selection" => &mut out.selection,
            "frozen" => &mut out.frozen,
            "editor" => &mut out.editor,
            "border" => &mut out.border,
            "error" => &mut out.error,
            "note" => &mut out.note,
            "popup" => &mut out.popup,
            "popup_text" => &mut out.popup_text,
            "popup_selected" => &mut out.popup_selected,
            _ => {
                return Err(PyValueError::new_err(format!(
                    "unknown sheet color: {key:?}"
                )));
            }
        };
        *slot = c;
    }
    Ok(out)
}

/// The spreadsheet grid of a :class:`Workbook` (the cells only; ``ui.Spreadsheet`` adds the
/// toolbar, the menus and the sheet tabs).
///
/// It draws only the visible cells, so a sheet can have a million rows. Click, drag, Shift
/// and Ctrl select; typing or a double click edits; the keyboard shortcuts of Sheets and
/// Excel work (copy and paste, undo, Ctrl+arrows, F2, F4, Ctrl+D, Alt+=...).
///
/// - `on_change(event)`: cells changed (``event["action"]``: ``"edit"``, ``"paste"``,
///   ``"fill"``, ``"clear"``, ``"undo"``, ``"redo"``, ``"format"``, ``"resize"``, ``"filter"``;
///   ``event["range"]``).
/// - `on_select(event)`: the selection changed.
/// - `on_context(event)`: right click (``kind``: ``"cell"``, ``"row"`` or ``"column"``; ``x``, ``y``).
/// - `on_dropdown(event)`: a cell's dropdown opened (``cell``, ``options``, ``x``, ``y``, ``width``).
/// - `on_filter(event)`: a filter button was clicked (``column``, ``x``, ``y``).
/// - `on_find(event)`: Ctrl+F or Ctrl+H (``mode``: ``"find"`` or ``"replace"``).
/// - `on_invalid(event)`: a value broke a strict validation rule (``cell``, ``value``, ``message``).
/// - `on_edit(event)`: typing started or ended (``editing``).
#[pyfunction]
#[pyo3(signature = (book, *, colors=None, text_size=13.0, formula_bar=true, headers=true, width=None, height=None, readonly=false, on_change=None, on_select=None, on_context=None, on_dropdown=None, on_filter=None, on_find=None, on_invalid=None, on_edit=None))]
#[allow(clippy::too_many_arguments)]
pub fn sheet(
    py: Python<'_>,
    book: &Workbook,
    colors: Option<&Bound<'_, PyDict>>,
    text_size: f32,
    formula_bar: bool,
    headers: bool,
    width: crate::style::Any<'_>,
    height: crate::style::Any<'_>,
    readonly: bool,
    on_change: crate::style::Any<'_>,
    on_select: crate::style::Any<'_>,
    on_context: crate::style::Any<'_>,
    on_dropdown: crate::style::Any<'_>,
    on_filter: crate::style::Any<'_>,
    on_find: crate::style::Any<'_>,
    on_invalid: crate::style::Any<'_>,
    on_edit: crate::style::Any<'_>,
) -> PyResult<Py<crate::widget::Widget>> {
    use crate::widget::PyMsg;
    let len = |v: &crate::style::Any<'_>| -> PyResult<iced::Length> {
        match v {
            Some(v) if !v.is_none() => crate::style::length(v),
            _ => Ok(iced::Length::Fill),
        }
    };
    let props = view::SheetProps {
        book: book.inner.clone(),
        colors: sheet_colors(colors)?,
        text_size,
        formula_bar,
        headers,
        width: len(&width)?,
        height: len(&height)?,
        readonly,
        on_change: PyMsg::maybe(&on_change),
        on_select: PyMsg::maybe(&on_select),
        on_context: PyMsg::maybe(&on_context),
        on_dropdown: PyMsg::maybe(&on_dropdown),
        on_filter: PyMsg::maybe(&on_filter),
        on_find: PyMsg::maybe(&on_find),
        on_invalid: PyMsg::maybe(&on_invalid),
        on_edit: PyMsg::maybe(&on_edit),
    };
    crate::widget::new(py, crate::widget::Kind::Sheet(Arc::new(props)))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Workbook>()?;
    m.add_function(wrap_pyfunction!(sheet, m)?)?;
    Ok(())
}
