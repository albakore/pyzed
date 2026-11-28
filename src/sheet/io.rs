//! Files: CSV/TSV text, and Excel workbooks (.xlsx to write; .xlsx, .xlsm, .xls and .ods to read).

use std::io::Cursor;

use calamine::{Data, Reader};

use super::addr::{Area, MAX_COLS, MAX_ROWS};
use super::model::{Book, Cell, HAlign, Input, Sheet, Style, VAlign, parse_input};
use super::ops::{parse_delimited, shown};
use super::value::{Error, Value};

fn rgba(c: &calamine::Color) -> u32 {
    ((c.red as u32) << 24) | ((c.green as u32) << 16) | ((c.blue as u32) << 8) | 0xFF
}

impl Book {
    /// Reads delimited text into a sheet, typing each field as if entered by hand.
    pub fn load_delimited(&mut self, sheet: usize, text: &str, delim: char) {
        let rows = parse_delimited(text, delim);
        let month_first = self.month_first;
        let s = &mut self.sheets[sheet];
        for (r, row) in rows.iter().enumerate().take(MAX_ROWS as usize) {
            for (c, field) in row.iter().enumerate().take(MAX_COLS as usize) {
                if field.is_empty() {
                    continue;
                }
                let (input, fmt) = parse_input(field, month_first);
                let value = match &input {
                    Input::Value(v) => v.clone(),
                    _ => Value::Empty,
                };
                let _ = fmt;
                s.put(
                    r as u32,
                    c as u32,
                    Some(Cell {
                        input,
                        value,
                        style: 0,
                        note: None,
                    }),
                );
            }
        }
        // Apply the detected formats (a second pass, once the sheet is filled).
        let fmt_cells: Vec<(u32, u32, &'static str)> = rows
            .iter()
            .enumerate()
            .flat_map(|(r, row)| {
                row.iter().enumerate().filter_map(move |(c, f)| {
                    parse_input(f, month_first)
                        .1
                        .map(|fmt| (r as u32, c as u32, fmt))
                })
            })
            .collect();
        for (r, c, fmt) in fmt_cells {
            let id = self.intern(Style {
                format: Some(fmt.into()),
                ..Default::default()
            });
            self.sheets[sheet].cell_mut(r, c).style = id;
        }
        self.rebuild_deps();
        self.recalc_all();
        self.touch();
    }

    /// The sheet as delimited text, with each value as shown.
    pub fn to_delimited(&self, sheet: usize, delim: char) -> String {
        let s = &self.sheets[sheet];
        let (rows, cols) = s.extent();
        let mut out = String::new();
        for r in 0..rows {
            let fields: Vec<String> = (0..cols)
                .map(|c| {
                    let t = shown(s, &self.styles, r, c);
                    if t.contains([delim, '"', '\n', '\r']) {
                        format!("\"{}\"", t.replace('"', "\"\""))
                    } else {
                        t
                    }
                })
                .collect();
            out.push_str(&fields.join(&delim.to_string()));
            out.push('\n');
        }
        out
    }

    /// Reads an Excel or OpenDocument workbook (from its bytes).
    pub fn load_excel(bytes: Vec<u8>) -> Result<Book, String> {
        let layout = xlsx_layout(&bytes);
        let mut wb =
            calamine::open_workbook_auto_from_rs(Cursor::new(bytes)).map_err(|e| e.to_string())?;
        let names = wb.sheet_names();
        let mut book = Book::new();
        book.sheets.clear();
        for name in &names {
            let mut sheet = Sheet::new(name);
            let range = wb.worksheet_range(name).map_err(|e| e.to_string())?;
            let formulas = wb.worksheet_formula(name).ok();
            let styles = wb.worksheet_style(name).ok();
            let (r0, c0) = range.start().unwrap_or((0, 0));
            for (r, c, data) in range.used_cells() {
                let (r, c) = (r0 + r as u32, c0 + c as u32);
                let value = match data {
                    Data::Int(i) => Value::Number(*i as f64),
                    Data::Float(f) => Value::Number(*f),
                    Data::String(s) => Value::text(s.as_str()),
                    Data::Bool(b) => Value::Bool(*b),
                    Data::DateTime(d) => Value::Number(d.as_f64()),
                    Data::DateTimeIso(s) | Data::DurationIso(s) => Value::text(s.as_str()),
                    Data::Error(e) => {
                        Value::Error(Error::parse(&e.to_string()).unwrap_or(Error::Value))
                    }
                    Data::Empty => Value::Empty,
                };
                sheet.put(
                    r,
                    c,
                    Some(Cell {
                        input: Input::Value(value.clone()),
                        value,
                        style: 0,
                        note: None,
                    }),
                );
            }
            if let Some(f) = formulas {
                let (fr0, fc0) = f.start().unwrap_or((0, 0));
                for (r, c, src) in f.used_cells() {
                    if src.is_empty() {
                        continue;
                    }
                    let (r, c) = (fr0 + r as u32, fc0 + c as u32);
                    let src = src.strip_prefix('=').unwrap_or(src);
                    let (input, _) = parse_input(&format!("={src}"), true);
                    let old = sheet.cell(r, c).cloned().unwrap_or_default();
                    sheet.put(
                        r,
                        c,
                        Some(Cell {
                            input,
                            value: old.value,
                            style: old.style,
                            note: None,
                        }),
                    );
                }
            }
            book.sheets.push(sheet);
            let si = book.sheets.len() - 1;
            if let Some(styles) = styles {
                let mut cells = Vec::new();
                for (r, c, st) in styles.cells() {
                    let mut out = Style::default();
                    if let Some(font) = &st.font {
                        out.bold = matches!(font.weight, calamine::FontWeight::Bold);
                        out.italic = matches!(font.style, calamine::FontStyle::Italic);
                        out.underline = !matches!(font.underline, calamine::UnderlineStyle::None);
                        out.strike = font.strikethrough;
                        out.color = font.color.as_ref().map(rgba).filter(|&c| c != 0x000000FF);
                        out.size = font
                            .size
                            .map(|s| s.round() as u16)
                            .filter(|&s| s != 11 && s != 10);
                    }
                    if let Some(fill) = &st.fill
                        && matches!(fill.pattern, calamine::FillPattern::Solid)
                    {
                        out.fill = fill
                            .foreground_color
                            .as_ref()
                            .or(fill.background_color.as_ref())
                            .map(rgba);
                    }
                    if let Some(al) = &st.alignment {
                        out.align = match al.horizontal {
                            calamine::HorizontalAlignment::Left => Some(HAlign::Left),
                            calamine::HorizontalAlignment::Center
                            | calamine::HorizontalAlignment::CenterContinuous => {
                                Some(HAlign::Center)
                            }
                            calamine::HorizontalAlignment::Right => Some(HAlign::Right),
                            _ => None,
                        };
                        out.valign = match al.vertical {
                            calamine::VerticalAlignment::Top => Some(VAlign::Top),
                            calamine::VerticalAlignment::Center => Some(VAlign::Middle),
                            _ => None,
                        };
                        out.wrap = al.wrap_text;
                    }
                    if let Some(nf) = &st.number_format {
                        let code = nf.format_code.trim();
                        if !code.is_empty() && !code.eq_ignore_ascii_case("general") {
                            out.format = Some(code.replace("\\-", "-").replace("\\ ", " ").into());
                        }
                    }
                    if let Some(b) = &st.borders {
                        let on =
                            |x: &calamine::Border| !matches!(x.style, calamine::BorderStyle::None);
                        out.borders = [on(&b.top), on(&b.right), on(&b.bottom), on(&b.left)];
                        out.border_color = [&b.top, &b.right, &b.bottom, &b.left]
                            .iter()
                            .find_map(|x| x.color.as_ref())
                            .map(rgba);
                    }
                    if out != Style::default() {
                        cells.push((r, c, out));
                    }
                }
                for (r, c, st) in cells {
                    let id = book.intern(st);
                    book.sheets[si].cell_mut(r, c).style = id;
                }
                // Cells created only for their style.
                for m in &mut book.sheets[si].cols {
                    m.retain(|_, cell| !cell.is_blank());
                }
            }
            if let calamine::Sheets::Xlsx(x) = &mut wb {
                for dim in x.merge_cells_by_sheet_name(name).unwrap_or_default() {
                    book.sheets[si].merges.push(Area::new(
                        dim.start.0,
                        dim.start.1,
                        dim.end.0,
                        dim.end.1,
                    ));
                }
            }
            let (rows, cols) = book.sheets[si].extent();
            book.sheets[si].grow(rows + 100, cols + 2);
        }
        if book.sheets.is_empty() {
            book.sheets.push(Sheet::new("Sheet1"));
        }
        for (name, l) in layout {
            if let Some(s) = book.sheets.iter_mut().find(|s| s.name == name) {
                l.apply(s);
            }
        }
        book.rebuild_deps();
        book.recalc_all();
        Ok(book)
    }

    /// The workbook as an .xlsx file: values, formulas (with their results), number formats,
    /// fonts, colors, borders, alignment, merges, sizes, frozen panes and filters.
    pub fn save_xlsx(&self) -> Result<Vec<u8>, String> {
        use rust_xlsxwriter::{
            Color, Format, FormatAlign, FormatBorder, FormatUnderline, Formula, Workbook,
        };
        let mut wb = Workbook::new();
        let mut formats: Vec<Option<Format>> = vec![None; self.styles.len()];
        for (i, st) in self.styles.iter().enumerate() {
            if *st == Style::default() {
                continue;
            }
            let mut f = Format::new();
            if st.bold {
                f = f.set_bold();
            }
            if st.italic {
                f = f.set_italic();
            }
            if st.underline {
                f = f.set_underline(FormatUnderline::Single);
            }
            if st.strike {
                f = f.set_font_strikethrough();
            }
            if let Some(c) = st.color {
                f = f.set_font_color(Color::RGB(c >> 8));
            }
            if let Some(c) = st.fill {
                f = f.set_background_color(Color::RGB(c >> 8));
            }
            if let Some(s) = st.size {
                f = f.set_font_size(s as f64);
            }
            if st.mono {
                f = f.set_font_name("Consolas");
            }
            if let Some(code) = &st.format {
                f = f.set_num_format(code.to_string());
            }
            if st.wrap {
                f = f.set_text_wrap();
            }
            f = match st.align {
                Some(HAlign::Left) => f.set_align(FormatAlign::Left),
                Some(HAlign::Center) => f.set_align(FormatAlign::Center),
                Some(HAlign::Right) => f.set_align(FormatAlign::Right),
                None => f,
            };
            f = match st.valign {
                Some(VAlign::Top) => f.set_align(FormatAlign::Top),
                Some(VAlign::Middle) => f.set_align(FormatAlign::VerticalCenter),
                _ => f,
            };
            if st.borders[0] {
                f = f.set_border_top(FormatBorder::Thin);
            }
            if st.borders[1] {
                f = f.set_border_right(FormatBorder::Thin);
            }
            if st.borders[2] {
                f = f.set_border_bottom(FormatBorder::Thin);
            }
            if st.borders[3] {
                f = f.set_border_left(FormatBorder::Thin);
            }
            if let Some(c) = st.border_color {
                f = f.set_border_color(Color::RGB(c >> 8));
            }
            formats[i] = Some(f);
        }
        let e = |e: rust_xlsxwriter::XlsxError| e.to_string();
        for s in &self.sheets {
            let ws = wb.add_worksheet();
            ws.set_name(&s.name).map_err(e)?;
            for (c, col) in s.cols.iter().enumerate() {
                let c = c as u16;
                for (&r, cell) in col {
                    let fmt = formats.get(cell.style as usize).and_then(|f| f.as_ref());
                    match (&cell.input, fmt) {
                        (Input::Formula(f), fmt) => {
                            let formula = Formula::new(format!("={}", f.src))
                                .set_result(cell.value.display());
                            match fmt {
                                Some(fmt) => ws
                                    .write_formula_with_format(r, c, formula, fmt)
                                    .map_err(e)?,
                                None => ws.write_formula(r, c, formula).map_err(e)?,
                            };
                        }
                        (Input::Value(v), fmt) => {
                            let default = Format::new();
                            let fmt = fmt.unwrap_or(&default);
                            match v {
                                Value::Number(n) => {
                                    ws.write_number_with_format(r, c, *n, fmt).map_err(e)?
                                }
                                Value::Text(t) => {
                                    ws.write_string_with_format(r, c, &**t, fmt).map_err(e)?
                                }
                                Value::Bool(b) => {
                                    ws.write_boolean_with_format(r, c, *b, fmt).map_err(e)?
                                }
                                Value::Error(err) => ws
                                    .write_string_with_format(r, c, err.as_str(), fmt)
                                    .map_err(e)?,
                                Value::Empty => ws.write_blank(r, c, fmt).map_err(e)?,
                            };
                        }
                        (Input::Empty, Some(fmt)) => {
                            ws.write_blank(r, c, fmt).map_err(e)?;
                        }
                        _ => {}
                    }
                }
            }
            for m in &s.merges {
                let fmt = formats
                    .get(s.style_of(m.r0, m.c0) as usize)
                    .and_then(|f| f.clone())
                    .unwrap_or_default();
                let text = shown(s, &self.styles, m.r0, m.c0);
                // merge_range writes the first cell as text; write the real content over it.
                if ws
                    .merge_range(m.r0, m.c0 as u16, m.r1, m.c1 as u16, &text, &fmt)
                    .is_ok()
                    && let Some(cell) = s.cell(m.r0, m.c0)
                {
                    match &cell.input {
                        Input::Formula(f) => {
                            let _ = ws.write_formula_with_format(
                                m.r0,
                                m.c0 as u16,
                                Formula::new(format!("={}", f.src)),
                                &fmt,
                            );
                        }
                        Input::Value(Value::Number(n)) => {
                            let _ = ws.write_number_with_format(m.r0, m.c0 as u16, *n, &fmt);
                        }
                        _ => {}
                    }
                }
            }
            for (&c, &w) in &s.col_axis.sizes {
                ws.set_column_width_pixels(c as u16, w.round() as u32)
                    .map_err(e)?;
            }
            for (&r, &h) in &s.row_axis.sizes {
                ws.set_row_height_pixels(r, h.round() as u32).map_err(e)?;
            }
            for &c in &s.col_axis.hidden {
                ws.set_column_hidden(c as u16).map_err(e)?;
            }
            for &r in s.row_axis.hidden.iter().chain(&s.row_axis.filtered) {
                ws.set_row_hidden(r).map_err(e)?;
            }
            if s.freeze != (0, 0) {
                ws.set_freeze_panes(s.freeze.0, s.freeze.1 as u16)
                    .map_err(e)?;
            }
            if let Some(f) = &s.filter {
                let _ = ws.autofilter(f.area.r0, f.area.c0 as u16, f.area.r1, f.area.c1 as u16);
            }
            if !s.gridlines {
                ws.set_screen_gridlines(false);
            }
            if let Some(c) = s.tab_color {
                ws.set_tab_color(Color::RGB(c >> 8));
            }
            for (c, col) in s.cols.iter().enumerate() {
                for (&r, cell) in col {
                    if let Some(note) = &cell.note {
                        let _ = ws.insert_note(
                            r,
                            c as u16,
                            &rust_xlsxwriter::Note::new(note.to_string()),
                        );
                    }
                }
            }
            for v in &s.validations {
                if let Some(dv) = validation_xlsx(v) {
                    let a = v
                        .area
                        .clamp(s.rows.max(v.area.r0 + 1), s.ncols.max(v.area.c0 + 1))
                        .unwrap_or(v.area);
                    let _ = ws.add_data_validation(a.r0, a.c0 as u16, a.r1, a.c1 as u16, &dv);
                }
            }
            for cf in &s.conditional {
                let a = cf
                    .area
                    .clamp(s.rows.max(cf.area.r0 + 1), s.ncols.max(cf.area.c0 + 1))
                    .unwrap_or(cf.area);
                let _ = conditional_xlsx(ws, a, cf);
            }
        }
        wb.save_to_buffer().map_err(e)
    }
}

/// A validation rule as Excel writes it (checkboxes become a TRUE/FALSE list).
fn validation_xlsx(v: &super::model::Validation) -> Option<rust_xlsxwriter::DataValidation> {
    use super::model::Check;
    use rust_xlsxwriter::{
        DataValidation, DataValidationErrorStyle, DataValidationRule as R, Formula,
    };
    fn bounds<T: rust_xlsxwriter::IntoDataValidationValue + Copy>(
        min: Option<T>,
        max: Option<T>,
    ) -> Option<R<T>> {
        match (min, max) {
            (Some(a), Some(b)) => Some(R::Between(a, b)),
            (Some(a), None) => Some(R::GreaterThanOrEqualTo(a)),
            (None, Some(b)) => Some(R::LessThanOrEqualTo(b)),
            (None, None) => None,
        }
    }
    let dv = DataValidation::new();
    let dv = match &v.check {
        Check::List(options) => dv
            .allow_list_strings(&options.iter().map(String::as_str).collect::<Vec<_>>())
            .ok()?,
        Check::ListRange(src) => dv.allow_list_formula(Formula::new(format!("={src}"))),
        Check::Checkbox => dv.allow_list_strings(&["TRUE", "FALSE"]).ok()?,
        Check::Number {
            min,
            max,
            integer: true,
        } => dv.allow_whole_number(
            bounds(min.map(|x| x as i32), max.map(|x| x as i32))
                .unwrap_or(R::Between(i32::MIN, i32::MAX)),
        ),
        Check::Number { min, max, .. } => {
            dv.allow_decimal_number(bounds(*min, *max).unwrap_or(R::Between(f64::MIN, f64::MAX)))
        }
        Check::TextLength { min, max } => dv.allow_text_length(
            bounds(min.map(|x| x as u32), max.map(|x| x as u32))
                .unwrap_or(R::GreaterThanOrEqualTo(0)),
        ),
        Check::Date { min, max } => {
            let f = |x: Option<f64>| x.map(|n| Formula::new(format!("{n}")));
            let rule = match (f(*min), f(*max)) {
                (Some(a), Some(b)) => R::Between(a, b),
                (Some(a), None) => R::GreaterThanOrEqualTo(a),
                (None, Some(b)) => R::LessThanOrEqualTo(b),
                (None, None) => return None,
            };
            dv.allow_date_formula(rule)
        }
        Check::Formula(f) => dv.allow_custom(Formula::new(format!("={}", f.src))),
    };
    let dv = if v.strict {
        dv
    } else {
        dv.set_error_style(DataValidationErrorStyle::Warning)
    };
    Some(match &v.message {
        Some(m) if !m.is_empty() => dv
            .set_error_message(m.as_str())
            .unwrap_or_else(|_| DataValidation::new()),
        _ => dv,
    })
}

/// Writes a conditional format the way Excel stores it.
fn conditional_xlsx(
    ws: &mut rust_xlsxwriter::Worksheet,
    a: Area,
    cf: &super::model::CondFormat,
) -> Result<(), rust_xlsxwriter::XlsxError> {
    use super::model::Rule;
    use rust_xlsxwriter::{
        Color, ConditionalFormat2ColorScale, ConditionalFormat3ColorScale, ConditionalFormatBlank,
        ConditionalFormatCell, ConditionalFormatCellRule as C, ConditionalFormatDataBar,
        ConditionalFormatDuplicate, ConditionalFormatFormula, ConditionalFormatText,
        ConditionalFormatTextRule as T, Format, FormatUnderline,
    };
    let st = &cf.style;
    let mut f = Format::new();
    if let Some(c) = st.color {
        f = f.set_font_color(Color::RGB(c >> 8));
    }
    if let Some(c) = st.fill {
        f = f.set_background_color(Color::RGB(c >> 8));
    }
    if st.bold == Some(true) {
        f = f.set_bold();
    }
    if st.italic == Some(true) {
        f = f.set_italic();
    }
    if st.strike == Some(true) {
        f = f.set_font_strikethrough();
    }
    if st.underline == Some(true) {
        f = f.set_underline(FormatUnderline::Single);
    }
    let (r0, c0, r1, c1) = (a.r0, a.c0 as u16, a.r1, a.c1 as u16);
    match &cf.rule {
        Rule::Compare(op, v, v2) => {
            let val = |v: &Value| -> rust_xlsxwriter::ConditionalFormatValue {
                match v {
                    Value::Number(n) => (*n).into(),
                    Value::Bool(b) => (*b).into(),
                    other => other.display().into(),
                }
            };
            let (x, y) = (val(v), val(v2));
            let rule = match op.as_str() {
                ">" => C::GreaterThan(x),
                "<" => C::LessThan(x),
                ">=" => C::GreaterThanOrEqualTo(x),
                "<=" => C::LessThanOrEqualTo(x),
                "=" => C::EqualTo(x),
                "<>" => C::NotEqualTo(x),
                "between" => C::Between(x, y),
                _ => C::NotBetween(x, y),
            };
            ws.add_conditional_format(
                r0,
                c0,
                r1,
                c1,
                &ConditionalFormatCell::new().set_rule(rule).set_format(f),
            )?;
        }
        Rule::TextContains(t) => {
            ws.add_conditional_format(
                r0,
                c0,
                r1,
                c1,
                &ConditionalFormatText::new()
                    .set_rule(T::Contains(t.clone()))
                    .set_format(f),
            )?;
        }
        Rule::TextNotContains(t) => {
            ws.add_conditional_format(
                r0,
                c0,
                r1,
                c1,
                &ConditionalFormatText::new()
                    .set_rule(T::DoesNotContain(t.clone()))
                    .set_format(f),
            )?;
        }
        Rule::TextStarts(t) => {
            ws.add_conditional_format(
                r0,
                c0,
                r1,
                c1,
                &ConditionalFormatText::new()
                    .set_rule(T::BeginsWith(t.clone()))
                    .set_format(f),
            )?;
        }
        Rule::TextEnds(t) => {
            ws.add_conditional_format(
                r0,
                c0,
                r1,
                c1,
                &ConditionalFormatText::new()
                    .set_rule(T::EndsWith(t.clone()))
                    .set_format(f),
            )?;
        }
        Rule::Empty => {
            ws.add_conditional_format(
                r0,
                c0,
                r1,
                c1,
                &ConditionalFormatBlank::new().set_format(f),
            )?;
        }
        Rule::NotEmpty => {
            ws.add_conditional_format(
                r0,
                c0,
                r1,
                c1,
                &ConditionalFormatBlank::new().invert().set_format(f),
            )?;
        }
        Rule::Duplicate => {
            ws.add_conditional_format(
                r0,
                c0,
                r1,
                c1,
                &ConditionalFormatDuplicate::new().set_format(f),
            )?;
        }
        Rule::Unique => {
            ws.add_conditional_format(
                r0,
                c0,
                r1,
                c1,
                &ConditionalFormatDuplicate::new().invert().set_format(f),
            )?;
        }
        Rule::Formula(src) => {
            ws.add_conditional_format(
                r0,
                c0,
                r1,
                c1,
                &ConditionalFormatFormula::new()
                    .set_rule(format!("={}", src.src).as_str())
                    .set_format(f),
            )?;
        }
        Rule::Scale(colors) => {
            let c = |i: usize| Color::RGB(colors[i] >> 8);
            if colors.len() == 3 {
                let s = ConditionalFormat3ColorScale::new()
                    .set_minimum_color(c(0))
                    .set_midpoint_color(c(1))
                    .set_maximum_color(c(2));
                ws.add_conditional_format(r0, c0, r1, c1, &s)?;
            } else {
                let s = ConditionalFormat2ColorScale::new()
                    .set_minimum_color(c(0))
                    .set_maximum_color(c(1));
                ws.add_conditional_format(r0, c0, r1, c1, &s)?;
            }
        }
        Rule::Bar(color) => {
            ws.add_conditional_format(
                r0,
                c0,
                r1,
                c1,
                &ConditionalFormatDataBar::new().set_fill_color(Color::RGB(color >> 8)),
            )?;
        }
    }
    Ok(())
}

/// What calamine doesn't read from an .xlsx sheet: column widths, row heights, hidden rows and
/// columns, frozen panes, the filter, gridlines, the tab color and data validation.
#[derive(Default)]
struct Layout {
    cols: Vec<(u32, u32, Option<f32>, bool)>,
    rows: Vec<(u32, Option<f32>, bool)>,
    freeze: (u32, u32),
    filter: Option<Area>,
    gridlines: bool,
    tab_color: Option<u32>,
    validations: Vec<super::model::Validation>,
}

impl Layout {
    fn apply(self, s: &mut Sheet) {
        for (c0, c1, w, hidden) in self.cols {
            for c in c0..=c1.min(c0 + 16_384).min(MAX_COLS - 1) {
                if let Some(w) = w {
                    s.col_axis.sizes.insert(c, w);
                }
                if hidden {
                    s.col_axis.hidden.insert(c);
                }
            }
        }
        for (r, h, hidden) in self.rows {
            if let Some(h) = h {
                s.row_axis.sizes.insert(r, h);
            }
            if hidden {
                s.row_axis.hidden.insert(r);
            }
        }
        s.col_axis.rebuild();
        s.row_axis.rebuild();
        s.freeze = self.freeze;
        if let Some(a) = self.filter {
            s.filter = Some(super::model::Filter {
                area: a,
                ..Default::default()
            });
        }
        s.gridlines = self.gridlines;
        s.tab_color = self.tab_color;
        s.validations.extend(self.validations);
    }
}

/// The value of an attribute in a start tag (`<col min="1" ...>`), unescaped.
fn attr<'a>(tag: &'a str, name: &str) -> Option<std::borrow::Cow<'a, str>> {
    let mut rest = tag;
    while let Some(i) = rest.find(name) {
        let before = rest[..i].chars().last();
        let after = &rest[i + name.len()..];
        if matches!(before, Some(' ' | '\t' | '\n' | '\r')) && after.starts_with("=\"") {
            let v = &after[2..];
            let end = v.find('"')?;
            let v = &v[..end];
            return Some(if v.contains('&') {
                std::borrow::Cow::Owned(
                    v.replace("&lt;", "<")
                        .replace("&gt;", ">")
                        .replace("&quot;", "\"")
                        .replace("&apos;", "'")
                        .replace("&amp;", "&"),
                )
            } else {
                std::borrow::Cow::Borrowed(v)
            });
        }
        rest = after;
    }
    None
}

/// The start tags `<name ...>` of an XML text, with what follows each up to its end tag.
fn tags<'a>(xml: &'a str, name: &str) -> Vec<(&'a str, &'a str)> {
    let open = format!("<{name}");
    let close = format!("</{name}>");
    let mut out = Vec::new();
    let mut i = 0;
    while let Some(k) = xml[i..].find(&open) {
        let start = i + k;
        let after = xml[start + open.len()..].chars().next();
        if !matches!(after, Some(' ' | '>' | '/' | '\n' | '\r' | '\t')) {
            i = start + open.len();
            continue;
        }
        let Some(end) = xml[start..].find('>') else {
            break;
        };
        let tag = &xml[start..start + end + 1];
        let body = if tag.ends_with("/>") {
            ""
        } else {
            let from = start + end + 1;
            match xml[from..].find(&close) {
                Some(e) => &xml[from..from + e],
                None => "",
            }
        };
        out.push((tag, body));
        i = start + end + 1;
    }
    out
}

fn xml_text(body: &str, name: &str) -> Option<String> {
    tags(body, name).first().map(|(_, b)| {
        b.replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", "\"")
            .replace("&apos;", "'")
            .replace("&amp;", "&")
    })
}

/// Reads the layout of every sheet of an .xlsx file by name (empty for other formats).
fn xlsx_layout(bytes: &[u8]) -> Vec<(String, Layout)> {
    use std::io::Read;
    let Ok(mut zip) = zip::ZipArchive::new(Cursor::new(bytes)) else {
        return Vec::new();
    };
    let mut read = |path: &str| -> Option<String> {
        let mut f = zip.by_name(path).ok()?;
        let mut s = String::new();
        f.read_to_string(&mut s).ok()?;
        Some(s)
    };
    let (Some(workbook), Some(rels)) =
        (read("xl/workbook.xml"), read("xl/_rels/workbook.xml.rels"))
    else {
        return Vec::new();
    };
    let targets: std::collections::HashMap<String, String> = tags(&rels, "Relationship")
        .into_iter()
        .filter_map(|(t, _)| Some((attr(t, "Id")?.into_owned(), attr(t, "Target")?.into_owned())))
        .collect();
    let mut out = Vec::new();
    for (t, _) in tags(&workbook, "sheet") {
        let (Some(name), Some(id)) = (attr(t, "name"), attr(t, "r:id")) else {
            continue;
        };
        let Some(target) = targets.get(id.as_ref()) else {
            continue;
        };
        let path = match target.strip_prefix('/') {
            Some(abs) => abs.to_string(),
            None => format!("xl/{target}"),
        };
        let Some(xml) = read(&path) else { continue };
        out.push((name.into_owned(), sheet_layout(&xml)));
    }
    out
}

fn sheet_layout(xml: &str) -> Layout {
    use super::model::{Check, Validation};
    let mut l = Layout {
        gridlines: true,
        ..Default::default()
    };
    let num = |t: &str, n: &str| attr(t, n).and_then(|v| v.parse::<f64>().ok());
    let on = |t: &str, n: &str| attr(t, n).is_some_and(|v| v == "1" || v == "true");
    for (t, _) in tags(xml, "col") {
        let (Some(min), Some(max)) = (num(t, "min"), num(t, "max")) else {
            continue;
        };
        if min < 1.0 {
            continue;
        }
        // Excel stores widths in characters of the default font (7 px each), padding included.
        let width = if on(t, "customWidth") || attr(t, "width").is_some() {
            num(t, "width").map(|w| (w * 7.0 + 0.5).floor() as f32)
        } else {
            None
        };
        l.cols
            .push((min as u32 - 1, max as u32 - 1, width, on(t, "hidden")));
    }
    for (t, _) in tags(xml, "row") {
        let Some(r) = num(t, "r") else { continue };
        if r < 1.0 {
            continue;
        }
        let height = if on(t, "customHeight") {
            num(t, "ht").map(|h| (h * 4.0 / 3.0).round() as f32)
        } else {
            None
        };
        let hidden = on(t, "hidden");
        if height.is_some() || hidden {
            l.rows.push((r as u32 - 1, height, hidden));
        }
    }
    if let Some((t, _)) = tags(xml, "pane").first()
        && attr(t, "state").is_some_and(|s| s.starts_with("frozen"))
    {
        l.freeze = (
            num(t, "ySplit").unwrap_or(0.0) as u32,
            num(t, "xSplit").unwrap_or(0.0) as u32,
        );
    }
    if let Some((t, _)) = tags(xml, "sheetView").first() {
        l.gridlines = attr(t, "showGridLines").is_none_or(|v| v != "0" && v != "false");
    }
    if let Some((t, _)) = tags(xml, "tabColor").first()
        && let Some(rgb) = attr(t, "rgb")
        && let Ok(argb) = u32::from_str_radix(&rgb, 16)
    {
        l.tab_color = Some(((argb & 0xFFFFFF) << 8) | 0xFF);
    }
    if let Some((t, _)) = tags(xml, "autoFilter").first()
        && let Some(r) = attr(t, "ref")
        && let Ok(a) = crate::sheet::addr::parse_area(&r).ok_or(())
    {
        l.filter = Some(a);
    }
    for (t, body) in tags(xml, "dataValidation") {
        let Some(sqref) = attr(t, "sqref") else {
            continue;
        };
        let f1 = xml_text(body, "formula1").unwrap_or_default();
        let f2 = xml_text(body, "formula2");
        let n = |s: &str| s.trim().parse::<f64>().ok();
        let op = attr(t, "operator")
            .map(|o| o.into_owned())
            .unwrap_or_else(|| "between".into());
        let bounds = |a: Option<f64>, b: Option<f64>| -> (Option<f64>, Option<f64>) {
            match op.as_str() {
                "greaterThan" | "greaterThanOrEqual" => (a, None),
                "lessThan" | "lessThanOrEqual" => (None, a),
                "equal" => (a, a),
                _ => (a, b),
            }
        };
        let check = match attr(t, "type").as_deref() {
            Some("list") => {
                if let Some(inner) = f1.strip_prefix('"').and_then(|x| x.strip_suffix('"')) {
                    let items: Vec<String> =
                        inner.split(',').map(|x| x.trim().to_string()).collect();
                    if items.len() == 2
                        && items.iter().all(|x| {
                            x.eq_ignore_ascii_case("TRUE") || x.eq_ignore_ascii_case("FALSE")
                        })
                    {
                        Check::Checkbox
                    } else {
                        Check::List(items)
                    }
                } else {
                    Check::ListRange(f1.trim_start_matches('=').to_string())
                }
            }
            Some(kind @ ("whole" | "decimal")) => {
                let (min, max) = bounds(n(&f1), f2.as_deref().and_then(n));
                Check::Number {
                    min,
                    max,
                    integer: kind == "whole",
                }
            }
            Some("date") => {
                let (min, max) = bounds(n(&f1), f2.as_deref().and_then(n));
                Check::Date { min, max }
            }
            Some("textLength") => {
                let (min, max) = bounds(n(&f1), f2.as_deref().and_then(n));
                Check::TextLength {
                    min: min.map(|x| x as usize),
                    max: max.map(|x| x as usize),
                }
            }
            Some("custom") => {
                let src = f1.trim_start_matches('=').to_string();
                let fc = super::model::FormulaCell::new(&src);
                if fc.expr.is_none() {
                    continue;
                }
                Check::Formula(std::sync::Arc::new(fc))
            }
            _ => continue,
        };
        let strict = attr(t, "errorStyle").is_none_or(|s| s == "stop");
        let message = attr(t, "error").map(|m| m.into_owned());
        for part in sqref.split_whitespace() {
            if let Ok(area) = crate::sheet::addr::parse_area(part).ok_or(()) {
                l.validations.push(Validation {
                    area,
                    check: check.clone(),
                    strict,
                    message: message.clone(),
                });
            }
        }
    }
    l
}
