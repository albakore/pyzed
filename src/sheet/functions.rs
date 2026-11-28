//! The functions formulas can call (`SUM`, `IF`, `VLOOKUP`, `TEXT`...).

use std::collections::HashSet;
use std::sync::Arc;

use super::addr::{self, Area};
use super::eval::{Ctx, Val, num};
use super::formula::Expr;
use super::value::{self, Error, Value, compare};

/// Every function, with its arguments as shown in the formula hint (`[x]`: optional).
pub const FUNCTIONS: &[(&str, &str, &str)] = &[
    ("ABS", "number", "Absolute value."),
    ("ACOS", "number", "Arccosine, in radians."),
    (
        "AND",
        "logical1, [logical2, ...]",
        "TRUE when every argument is TRUE.",
    ),
    ("ASIN", "number", "Arcsine, in radians."),
    ("ATAN", "number", "Arctangent, in radians."),
    ("ATAN2", "x, y", "Arctangent of y/x, in radians."),
    (
        "AVERAGE",
        "number1, [number2, ...]",
        "Arithmetic mean of the numbers.",
    ),
    (
        "AVERAGEIF",
        "range, criterion, [average_range]",
        "Mean of the cells that match a criterion.",
    ),
    (
        "AVERAGEIFS",
        "average_range, range1, criterion1, ...",
        "Mean of the cells that match every criterion.",
    ),
    (
        "CEILING",
        "number, [significance]",
        "Rounds up to a multiple of significance.",
    ),
    ("CHAR", "number", "The character with this code."),
    (
        "CHOOSE",
        "index, value1, [value2, ...]",
        "The value at a position in the list.",
    ),
    ("CLEAN", "text", "Removes non-printable characters."),
    ("CODE", "text", "The code of the first character."),
    ("COLUMN", "[reference]", "Column number of a reference."),
    ("COLUMNS", "range", "Number of columns."),
    ("CONCAT", "text1, [text2, ...]", "Joins texts."),
    ("CONCATENATE", "text1, [text2, ...]", "Joins texts."),
    ("COS", "angle", "Cosine of an angle in radians."),
    ("COUNT", "value1, [value2, ...]", "How many numbers."),
    (
        "COUNTA",
        "value1, [value2, ...]",
        "How many non-empty values.",
    ),
    ("COUNTBLANK", "range", "How many empty cells."),
    (
        "COUNTIF",
        "range, criterion",
        "How many cells match a criterion (\">5\", \"apple\", \"a*\").",
    ),
    (
        "COUNTIFS",
        "range1, criterion1, [range2, criterion2, ...]",
        "How many rows match every criterion.",
    ),
    ("DATE", "year, month, day", "A date from its parts."),
    (
        "DATEDIF",
        "start_date, end_date, unit",
        "Difference between dates in \"Y\", \"M\", \"D\", \"YM\", \"MD\" or \"YD\".",
    ),
    ("DATEVALUE", "date_text", "The date a text stands for."),
    ("DAY", "date", "Day of the month (1-31)."),
    ("DAYS", "end_date, start_date", "Days between two dates."),
    ("DEGREES", "angle", "Radians to degrees."),
    (
        "EDATE",
        "start_date, months",
        "The date some months before or after.",
    ),
    (
        "EOMONTH",
        "start_date, months",
        "The last day of the month some months away.",
    ),
    (
        "EVEN",
        "number",
        "Rounds away from zero to an even integer.",
    ),
    (
        "EXACT",
        "text1, text2",
        "TRUE when both texts are identical (case-sensitive).",
    ),
    ("EXP", "number", "e raised to a power."),
    ("FACT", "number", "Factorial."),
    ("FALSE", "", "The logical value FALSE."),
    (
        "FILTER",
        "range, include, [if_empty]",
        "The rows of a range where include is TRUE.",
    ),
    (
        "FIND",
        "find_text, within_text, [start]",
        "Position of a text (case-sensitive).",
    ),
    (
        "FLOOR",
        "number, [significance]",
        "Rounds down to a multiple of significance.",
    ),
    ("GCD", "number1, [number2, ...]", "Greatest common divisor."),
    (
        "HLOOKUP",
        "key, range, row_index, [is_sorted]",
        "Looks up a key in the first row and returns a value from another row.",
    ),
    ("HOUR", "time", "Hour (0-23)."),
    (
        "IF",
        "condition, value_if_true, [value_if_false]",
        "One value or another depending on a condition.",
    ),
    (
        "IFERROR",
        "value, value_if_error",
        "The value, or another one if it is an error.",
    ),
    (
        "IFNA",
        "value, value_if_na",
        "The value, or another one if it is #N/A.",
    ),
    (
        "IFS",
        "condition1, value1, [condition2, value2, ...]",
        "The value of the first TRUE condition.",
    ),
    (
        "INDEX",
        "range, row, [column]",
        "The cell at a row and column of a range.",
    ),
    (
        "INDIRECT",
        "reference_text",
        "The reference written in a text (\"B3\", \"Sheet2!A1:A9\").",
    ),
    ("INT", "number", "Rounds down to an integer."),
    ("ISBLANK", "value", "TRUE when the cell is empty."),
    ("ISERR", "value", "TRUE for errors other than #N/A."),
    ("ISERROR", "value", "TRUE for any error."),
    ("ISEVEN", "number", "TRUE for even numbers."),
    (
        "ISFORMULA",
        "reference",
        "TRUE when the cell has a formula.",
    ),
    ("ISLOGICAL", "value", "TRUE for TRUE or FALSE."),
    ("ISNA", "value", "TRUE for #N/A."),
    ("ISNUMBER", "value", "TRUE for numbers."),
    ("ISODD", "number", "TRUE for odd numbers."),
    ("ISTEXT", "value", "TRUE for text."),
    ("LARGE", "range, k", "The k-th largest number."),
    ("LCM", "number1, [number2, ...]", "Least common multiple."),
    ("LEFT", "text, [count]", "The first characters of a text."),
    ("LEN", "text", "Number of characters."),
    ("LN", "number", "Natural logarithm."),
    ("LOG", "number, [base]", "Logarithm (base 10 by default)."),
    ("LOG10", "number", "Base-10 logarithm."),
    ("LOWER", "text", "Lowercase."),
    (
        "MATCH",
        "key, range, [match_type]",
        "Position of a value in a range (1: ≤ sorted, 0: exact, -1: ≥).",
    ),
    ("MAX", "number1, [number2, ...]", "Largest number."),
    (
        "MAXIFS",
        "max_range, range1, criterion1, ...",
        "Largest of the cells that match every criterion.",
    ),
    ("MEDIAN", "number1, [number2, ...]", "Middle number."),
    (
        "MID",
        "text, start, count",
        "Characters from the middle of a text.",
    ),
    ("MIN", "number1, [number2, ...]", "Smallest number."),
    (
        "MINIFS",
        "min_range, range1, criterion1, ...",
        "Smallest of the cells that match every criterion.",
    ),
    ("MINUTE", "time", "Minute (0-59)."),
    (
        "MOD",
        "dividend, divisor",
        "Remainder of a division (with the divisor's sign).",
    ),
    ("MODE", "number1, [number2, ...]", "Most frequent number."),
    ("MONTH", "date", "Month (1-12)."),
    (
        "MROUND",
        "number, multiple",
        "Rounds to the nearest multiple.",
    ),
    ("N", "value", "The value as a number (text is 0)."),
    ("NA", "", "The #N/A error."),
    (
        "NETWORKDAYS",
        "start_date, end_date",
        "Working days (Monday to Friday) between two dates.",
    ),
    ("NOT", "logical", "The opposite of a logical value."),
    ("NOW", "", "The current date and time."),
    ("ODD", "number", "Rounds away from zero to an odd integer."),
    (
        "OFFSET",
        "reference, rows, columns, [height], [width]",
        "A reference moved and resized.",
    ),
    (
        "OR",
        "logical1, [logical2, ...]",
        "TRUE when any argument is TRUE.",
    ),
    ("PERCENTILE", "range, k", "The k-th percentile (0 to 1)."),
    ("PI", "", "π."),
    ("POWER", "base, exponent", "A number raised to a power."),
    (
        "PRODUCT",
        "number1, [number2, ...]",
        "The numbers multiplied together.",
    ),
    ("PROPER", "text", "Capitalizes Each Word."),
    (
        "QUOTIENT",
        "dividend, divisor",
        "Integer part of a division.",
    ),
    ("RADIANS", "angle", "Degrees to radians."),
    ("RAND", "", "A random number between 0 and 1."),
    (
        "RANDBETWEEN",
        "low, high",
        "A random integer between two numbers.",
    ),
    (
        "RANK",
        "value, range, [ascending]",
        "Rank of a number in a list (1 = largest).",
    ),
    (
        "REPLACE",
        "text, position, length, new_text",
        "Replaces part of a text by position.",
    ),
    ("REPT", "text, times", "Repeats a text."),
    ("RIGHT", "text, [count]", "The last characters of a text."),
    (
        "ROUND",
        "number, [places]",
        "Rounds to some decimal places.",
    ),
    ("ROUNDDOWN", "number, [places]", "Rounds towards zero."),
    ("ROUNDUP", "number, [places]", "Rounds away from zero."),
    ("ROW", "[reference]", "Row number of a reference."),
    ("ROWS", "range", "Number of rows."),
    (
        "SEARCH",
        "find_text, within_text, [start]",
        "Position of a text (ignores case, allows * and ?).",
    ),
    ("SECOND", "time", "Second (0-59)."),
    (
        "SEQUENCE",
        "rows, [columns], [start], [step]",
        "An array of consecutive numbers.",
    ),
    ("SIGN", "number", "1, 0 or -1."),
    ("SIN", "angle", "Sine of an angle in radians."),
    ("SMALL", "range, k", "The k-th smallest number."),
    (
        "SORT",
        "range, [column], [ascending], [by_column]",
        "The rows of a range, sorted.",
    ),
    ("SPLIT", "text, delimiter", "Splits a text into cells."),
    ("SQRT", "number", "Square root."),
    (
        "STDEV",
        "number1, [number2, ...]",
        "Standard deviation of a sample.",
    ),
    (
        "STDEV.P",
        "number1, [number2, ...]",
        "Standard deviation of a population.",
    ),
    (
        "STDEV.S",
        "number1, [number2, ...]",
        "Standard deviation of a sample.",
    ),
    (
        "SUBSTITUTE",
        "text, search, replacement, [occurrence]",
        "Replaces a text with another.",
    ),
    ("SUM", "number1, [number2, ...]", "Adds the numbers."),
    (
        "SUMIF",
        "range, criterion, [sum_range]",
        "Adds the cells that match a criterion.",
    ),
    (
        "SUMIFS",
        "sum_range, range1, criterion1, ...",
        "Adds the cells that match every criterion.",
    ),
    (
        "SUMPRODUCT",
        "array1, [array2, ...]",
        "Sum of the products of the arrays.",
    ),
    ("SUMSQ", "number1, [number2, ...]", "Sum of the squares."),
    (
        "SWITCH",
        "expression, case1, value1, [..., default]",
        "The value of the first case equal to the expression.",
    ),
    ("T", "value", "The value if it is text, otherwise \"\"."),
    ("TAN", "angle", "Tangent of an angle in radians."),
    (
        "TEXT",
        "value, format",
        "A number as text in a format (\"0.00\", \"yyyy-mm-dd\").",
    ),
    (
        "TEXTJOIN",
        "delimiter, ignore_empty, text1, [text2, ...]",
        "Joins texts with a delimiter.",
    ),
    ("TIME", "hour, minute, second", "A time from its parts."),
    ("TODAY", "", "Today's date."),
    ("TRANSPOSE", "range", "Rows become columns."),
    ("TRIM", "text", "Removes extra spaces."),
    ("TRUE", "", "The logical value TRUE."),
    ("TRUNC", "number, [places]", "Cuts off the decimals."),
    ("UNIQUE", "range", "The distinct rows of a range."),
    ("UPPER", "text", "Uppercase."),
    ("VALUE", "text", "The number a text stands for."),
    ("VAR", "number1, [number2, ...]", "Variance of a sample."),
    (
        "VAR.P",
        "number1, [number2, ...]",
        "Variance of a population.",
    ),
    ("VAR.S", "number1, [number2, ...]", "Variance of a sample."),
    (
        "VLOOKUP",
        "key, range, column_index, [is_sorted]",
        "Looks up a key in the first column and returns a value from another column.",
    ),
    (
        "WEEKDAY",
        "date, [type]",
        "Day of the week (1 = Sunday by default).",
    ),
    (
        "XLOOKUP",
        "key, lookup_range, result_range, [if_not_found], [match_mode], [search_mode]",
        "Looks up a key and returns the matching item.",
    ),
    (
        "XOR",
        "logical1, [logical2, ...]",
        "TRUE when an odd number of arguments are TRUE.",
    ),
    ("YEAR", "date", "Year."),
];

type R = Result<Val, Error>;

fn err(e: Error) -> Val {
    Val::V(Value::Error(e))
}

fn need(args: &[Expr], min: usize, max: usize) -> Result<(), Error> {
    if args.len() < min || args.len() > max {
        Err(Error::Value)
    } else {
        Ok(())
    }
}

/// Calls `f` with every value of the arguments; `true` marks values that came from cells
/// or arrays (aggregates skip text and booleans there, but convert them when typed directly).
fn each(
    ctx: &Ctx,
    args: &[Expr],
    f: &mut dyn FnMut(&Value, bool) -> Result<(), Error>,
) -> Result<(), Error> {
    for a in args {
        if matches!(a, Expr::Missing) {
            continue;
        }
        match ctx.eval(a) {
            Val::V(v) => f(&v, false)?,
            Val::A(m) => {
                for v in m.iter().flatten() {
                    f(v, true)?;
                }
            }
            Val::R(sheet, area) => {
                let mut res = Ok(());
                ctx.grid.for_each(sheet, area, &mut |_, _, v| {
                    if res.is_ok() {
                        res = f(v, true);
                    }
                });
                res?;
            }
        }
    }
    Ok(())
}

/// The numbers of the arguments, as `SUM` and `AVERAGE` count them.
fn numbers(ctx: &Ctx, args: &[Expr]) -> Result<Vec<f64>, Error> {
    let mut out = Vec::new();
    each(ctx, args, &mut |v, from_cells| {
        match v {
            Value::Number(n) => out.push(*n),
            Value::Error(e) => return Err(*e),
            Value::Empty => {}
            other if !from_cells => out.push(other.as_number()?),
            _ => {}
        }
        Ok(())
    })?;
    Ok(out)
}

fn round_to(n: f64, places: i32, mode: i8) -> f64 {
    let f = 10f64.powi(places);
    let x = n * f;
    // Rounds 2.675 to 2.68 like spreadsheets do, despite its binary representation.
    let x = (x * 1e9).round() / 1e9;
    let r = match mode {
        0 => x.abs().round() * x.signum(),
        1 => x.abs().ceil() * x.signum(),
        _ => x.abs().floor() * x.signum(),
    };
    r / f
}

// ---------------------------------------------------------------------------
// Criteria (COUNTIF, SUMIF...): ">5", "<>x", "a*", "=", 3
// ---------------------------------------------------------------------------

pub struct Criterion {
    op: &'static str,
    value: Value,
    pattern: Option<Vec<char>>,
}

impl Criterion {
    pub fn new(v: &Value) -> Self {
        let Value::Text(t) = v else {
            return Criterion {
                op: "=",
                value: v.clone(),
                pattern: None,
            };
        };
        let mut s: &str = t;
        let mut op = "=";
        for cand in ["<=", ">=", "<>", "<", ">", "="] {
            if let Some(rest) = s.strip_prefix(cand) {
                op = cand;
                s = rest;
                break;
            }
        }
        let value = if s.is_empty() {
            Value::Empty
        } else if let Some((n, _)) = value::parse_number(s) {
            Value::Number(n)
        } else if let Some((n, _)) = value::parse_date(s, true) {
            Value::Number(n)
        } else if s.eq_ignore_ascii_case("TRUE") {
            Value::Bool(true)
        } else if s.eq_ignore_ascii_case("FALSE") {
            Value::Bool(false)
        } else {
            Value::text(s)
        };
        let pattern = match &value {
            Value::Text(t) if (op == "=" || op == "<>") && t.contains(['*', '?']) => {
                Some(t.to_lowercase().chars().collect())
            }
            _ => None,
        };
        Criterion { op, value, pattern }
    }

    pub fn matches(&self, v: &Value) -> bool {
        if let Some(p) = &self.pattern {
            let text = match v {
                Value::Text(t) => t.to_lowercase(),
                Value::Empty => String::new(),
                _ => return self.op == "<>",
            };
            let m = wildcard(p, &text.chars().collect::<Vec<_>>());
            return if self.op == "=" { m } else { !m };
        }
        match (&self.value, v) {
            (Value::Empty, v) => {
                let blank =
                    matches!(v, Value::Empty) || matches!(v, Value::Text(t) if t.is_empty());
                return if self.op == "<>" { !blank } else { blank };
            }
            (Value::Number(_), Value::Text(_)) | (Value::Text(_), Value::Number(_))
                if self.op != "<>" =>
            {
                return false;
            }
            (_, Value::Empty) if self.op != "<>" => return false,
            _ => {}
        }
        if let (Value::Number(_), Value::Text(_)) = (&self.value, v) {
            return true; // "<>5" matches text
        }
        let ord = compare(v, &self.value);
        use std::cmp::Ordering::*;
        match self.op {
            "=" => ord == Equal,
            "<>" => ord != Equal,
            "<" => ord == Less,
            "<=" => ord != Greater,
            ">" => ord == Greater,
            _ => ord != Less,
        }
    }
}

/// `*` and `?` wildcards; `~` escapes them.
pub fn wildcard(p: &[char], t: &[char]) -> bool {
    let (mut pi, mut ti) = (0, 0);
    let (mut star, mut mark) = (None, 0);
    while ti < t.len() {
        if pi < p.len() && p[pi] == '~' && pi + 1 < p.len() {
            if p[pi + 1] == t[ti] {
                pi += 2;
                ti += 1;
                continue;
            }
        } else if pi < p.len() && (p[pi] == '?' || p[pi] == t[ti]) {
            pi += 1;
            ti += 1;
            continue;
        } else if pi < p.len() && p[pi] == '*' {
            star = Some(pi);
            mark = ti;
            pi += 1;
            continue;
        }
        if let Some(s) = star {
            pi = s + 1;
            mark += 1;
            ti = mark;
        } else {
            return false;
        }
    }
    while pi < p.len() && p[pi] == '*' {
        pi += 1;
    }
    pi == p.len()
}

/// Cells matching every (range, criterion) pair: their positions in the first range's shape.
fn matching(ctx: &Ctx, pairs: &[Expr]) -> Result<(usize, usize, Vec<bool>), Error> {
    if !pairs.len().is_multiple_of(2) || pairs.is_empty() {
        return Err(Error::Value);
    }
    let mut shape = None;
    let mut mask: Vec<bool> = Vec::new();
    for pair in pairs.chunks(2) {
        let range = ctx.eval(&pair[0]);
        let m = ctx.matrix(&range);
        let crit = Criterion::new(&ctx.scalar(&pair[1]));
        let rows = m.len();
        let cols = m.first().map_or(0, |r| r.len());
        match shape {
            None => {
                shape = Some((rows, cols));
                mask = vec![true; rows * cols];
            }
            Some(s) if s != (rows, cols) => return Err(Error::Value),
            _ => {}
        }
        for (r, row) in m.iter().enumerate() {
            for (c, v) in row.iter().enumerate() {
                if mask[r * cols + c] && !crit.matches(v) {
                    mask[r * cols + c] = false;
                }
            }
        }
    }
    let (rows, cols) = shape.unwrap();
    Ok((rows, cols, mask))
}

fn masked(m: &[Vec<Value>], rows: usize, cols: usize, mask: &[bool]) -> Result<Vec<f64>, Error> {
    if m.len() != rows || m.first().map_or(0, |r| r.len()) != cols {
        return Err(Error::Value);
    }
    let mut out = Vec::new();
    for (r, row) in m.iter().enumerate() {
        for (c, v) in row.iter().enumerate() {
            if mask[r * cols + c] {
                match v {
                    Value::Number(n) => out.push(*n),
                    Value::Error(e) => return Err(*e),
                    _ => {}
                }
            }
        }
    }
    Ok(out)
}

// ---------------------------------------------------------------------------
// Lookups
// ---------------------------------------------------------------------------

fn same_kind(a: &Value, b: &Value) -> bool {
    matches!(
        (a, b),
        (Value::Number(_), Value::Number(_))
            | (Value::Text(_), Value::Text(_))
            | (Value::Bool(_), Value::Bool(_))
    )
}

fn exact(key: &Value, v: &Value, wild: bool) -> bool {
    if wild
        && let Value::Text(k) = key
        && k.contains(['*', '?'])
    {
        let p: Vec<char> = k.to_lowercase().chars().collect();
        return matches!(v, Value::Text(t) if wildcard(&p, &t.to_lowercase().chars().collect::<Vec<_>>()));
    }
    same_kind(key, v) && compare(key, v) == std::cmp::Ordering::Equal
}

/// Position of `key` in `list`: exact (0), largest ≤ key (1), smallest ≥ key (-1).
fn find(key: &Value, list: &[Value], mode: i32, wild: bool, reverse: bool) -> Option<usize> {
    let order: Box<dyn Iterator<Item = usize>> = if reverse {
        Box::new((0..list.len()).rev())
    } else {
        Box::new(0..list.len())
    };
    if mode == 0 {
        for i in order {
            if exact(key, &list[i], wild) {
                return Some(i);
            }
        }
        return None;
    }
    let mut best: Option<usize> = None;
    for i in order {
        let v = &list[i];
        if !same_kind(key, v) {
            continue;
        }
        let ord = compare(v, key);
        if ord == std::cmp::Ordering::Equal {
            return Some(i);
        }
        let ok = if mode > 0 {
            ord == std::cmp::Ordering::Less
        } else {
            ord == std::cmp::Ordering::Greater
        };
        if ok {
            best = match best {
                Some(b) => {
                    let better = compare(v, &list[b]);
                    if (mode > 0 && better == std::cmp::Ordering::Greater)
                        || (mode < 0 && better == std::cmp::Ordering::Less)
                    {
                        Some(i)
                    } else {
                        Some(b)
                    }
                }
                None => Some(i),
            };
        }
    }
    best
}

fn column_of(m: &[Vec<Value>], c: usize) -> Vec<Value> {
    m.iter()
        .map(|r| r.get(c).cloned().unwrap_or_default())
        .collect()
}

fn flat(m: &[Vec<Value>]) -> Result<Vec<Value>, Error> {
    if m.len() == 1 {
        Ok(m[0].clone())
    } else if m.first().map_or(0, |r| r.len()) == 1 {
        Ok(column_of(m, 0))
    } else {
        Err(Error::NA)
    }
}

fn arr(rows: Vec<Vec<Value>>) -> Val {
    if rows.is_empty() || rows[0].is_empty() {
        return err(Error::Value);
    }
    Val::A(Arc::new(rows))
}

// ---------------------------------------------------------------------------

fn stats(xs: &[f64], sample: bool) -> Result<f64, Error> {
    let n = xs.len() as f64;
    if xs.is_empty() || (sample && xs.len() < 2) {
        return Err(Error::Div0);
    }
    let mean = xs.iter().sum::<f64>() / n;
    let ss: f64 = xs.iter().map(|x| (x - mean).powi(2)).sum();
    Ok(ss / if sample { n - 1.0 } else { n })
}

fn percentile(mut xs: Vec<f64>, k: f64) -> Result<f64, Error> {
    if xs.is_empty() || !(0.0..=1.0).contains(&k) {
        return Err(Error::Num);
    }
    xs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let pos = k * (xs.len() - 1) as f64;
    let lo = pos.floor() as usize;
    let hi = pos.ceil() as usize;
    Ok(xs[lo] + (xs[hi] - xs[lo]) * (pos - lo as f64))
}

fn gcd(a: f64, b: f64) -> f64 {
    let (mut a, mut b) = (a.abs().floor(), b.abs().floor());
    while b > 0.0 {
        let t = a % b;
        a = b;
        b = t;
    }
    a
}

fn add_months(serial: f64, months: i64, end: bool) -> f64 {
    let (y, m, d) = value::serial_date(serial);
    let total = y * 12 + m as i64 - 1 + months;
    let (ny, nm) = (total.div_euclid(12), (total.rem_euclid(12) + 1) as u32);
    let last = value::days_in_month(ny, nm);
    let day = if end { last } else { d.min(last) };
    value::date_serial(ny, nm as i64, day as i64)
}

fn random() -> f64 {
    use std::cell::Cell;
    thread_local!(static SEED: Cell<u64> = Cell::new({
        let t = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_nanos() as u64).unwrap_or(1);
        t | 1
    }));
    SEED.with(|s| {
        let mut x = s.get();
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        s.set(x);
        (x >> 11) as f64 / (1u64 << 53) as f64
    })
}

pub fn call(ctx: &Ctx, name: &str, args: &[Expr]) -> Val {
    match call_inner(ctx, name, args) {
        Ok(v) => v,
        Err(e) => err(e),
    }
}

fn call_inner(ctx: &Ctx, name: &str, args: &[Expr]) -> R {
    let a = args;
    let n = |i: usize| -> Result<f64, Error> { ctx.number(&a[i]) };
    let opt_n = |i: usize, d: f64| -> Result<f64, Error> {
        match a.get(i) {
            None | Some(Expr::Missing) => Ok(d),
            Some(e) => ctx.number(e),
        }
    };
    let t = |i: usize| -> Result<String, Error> { ctx.text(&a[i]) };
    let math1 = |f: fn(f64) -> f64| -> R {
        need(a, 1, 1)?;
        Ok(num(f(n(0)?)).into())
    };
    Ok(match name {
        // --- Math --------------------------------------------------------
        "SUM" => numbers(ctx, a)?.iter().sum::<f64>().into(),
        "PRODUCT" => numbers(ctx, a)?.iter().product::<f64>().into(),
        "SUMSQ" => numbers(ctx, a)?.iter().map(|x| x * x).sum::<f64>().into(),
        "ABS" => math1(f64::abs)?,
        "SQRT" => {
            need(a, 1, 1)?;
            let x = n(0)?;
            if x < 0.0 {
                return Err(Error::Num);
            }
            x.sqrt().into()
        }
        "EXP" => math1(f64::exp)?,
        "LN" | "LOG10" | "LOG" => {
            need(a, 1, if name == "LOG" { 2 } else { 1 })?;
            let x = n(0)?;
            let base = if name == "LN" {
                std::f64::consts::E
            } else {
                opt_n(1, 10.0)?
            };
            if x <= 0.0 || base <= 0.0 || base == 1.0 {
                return Err(Error::Num);
            }
            (x.ln() / base.ln()).into()
        }
        "PI" => std::f64::consts::PI.into(),
        "SIN" => math1(f64::sin)?,
        "COS" => math1(f64::cos)?,
        "TAN" => math1(f64::tan)?,
        "ASIN" => math1(f64::asin)?,
        "ACOS" => math1(f64::acos)?,
        "ATAN" => math1(f64::atan)?,
        "ATAN2" => {
            need(a, 2, 2)?;
            let (x, y) = (n(0)?, n(1)?);
            if x == 0.0 && y == 0.0 {
                return Err(Error::Div0);
            }
            y.atan2(x).into()
        }
        "DEGREES" => math1(f64::to_degrees)?,
        "RADIANS" => math1(f64::to_radians)?,
        "SIGN" => math1(|x| {
            if x > 0.0 {
                1.0
            } else if x < 0.0 {
                -1.0
            } else {
                0.0
            }
        })?,
        "INT" => math1(f64::floor)?,
        "EVEN" => math1(|x| {
            let r = (x.abs() / 2.0).ceil() * 2.0;
            r * x.signum()
        })?,
        "ODD" => math1(|x| {
            let mut r = x.abs().ceil();
            if r % 2.0 == 0.0 {
                r += 1.0;
            }
            r * if x < 0.0 { -1.0 } else { 1.0 }
        })?,
        "FACT" => {
            need(a, 1, 1)?;
            let x = n(0)?.floor();
            if x < 0.0 {
                return Err(Error::Num);
            }
            if x > 170.0 {
                return Err(Error::Num);
            }
            (1..=x as u64).map(|v| v as f64).product::<f64>().into()
        }
        "ROUND" | "ROUNDUP" | "ROUNDDOWN" | "TRUNC" => {
            need(a, 1, 2)?;
            let places = opt_n(1, 0.0)? as i32;
            let mode = match name {
                "ROUND" => 0,
                "ROUNDUP" => 1,
                _ => 2,
            };
            round_to(n(0)?, places, mode).into()
        }
        "MROUND" => {
            need(a, 2, 2)?;
            let (x, m) = (n(0)?, n(1)?);
            if m == 0.0 {
                return Ok(0.0.into());
            }
            if x.signum() != m.signum() && x != 0.0 {
                return Err(Error::Num);
            }
            ((x / m).round() * m).into()
        }
        "CEILING" | "FLOOR" => {
            need(a, 1, 2)?;
            let x = n(0)?;
            let s = opt_n(1, if x < 0.0 { -1.0 } else { 1.0 })?;
            if s == 0.0 {
                return Ok(0.0.into());
            }
            let q = x / s;
            let q = (q * 1e9).round() / 1e9;
            (if name == "CEILING" {
                q.ceil()
            } else {
                q.floor()
            } * s)
                .into()
        }
        "MOD" => {
            need(a, 2, 2)?;
            let (x, y) = (n(0)?, n(1)?);
            if y == 0.0 {
                return Err(Error::Div0);
            }
            (x - y * (x / y).floor()).into()
        }
        "QUOTIENT" => {
            need(a, 2, 2)?;
            let (x, y) = (n(0)?, n(1)?);
            if y == 0.0 {
                return Err(Error::Div0);
            }
            (x / y).trunc().into()
        }
        "POWER" => {
            need(a, 2, 2)?;
            Val::V(super::eval::binary(
                "^",
                &Value::Number(n(0)?),
                &Value::Number(n(1)?),
            ))
        }
        "GCD" => numbers(ctx, a)?.into_iter().fold(0.0, gcd).into(),
        "LCM" => numbers(ctx, a)?
            .into_iter()
            .fold(1.0, |acc, x| {
                let x = x.abs().floor();
                if x == 0.0 || acc == 0.0 {
                    0.0
                } else {
                    acc * x / gcd(acc, x)
                }
            })
            .into(),
        "RAND" => random().into(),
        "RANDBETWEEN" => {
            need(a, 2, 2)?;
            let (lo, hi) = (n(0)?.ceil(), n(1)?.floor());
            if hi < lo {
                return Err(Error::Num);
            }
            (lo + (random() * (hi - lo + 1.0)).floor()).into()
        }
        "SUMPRODUCT" => {
            if a.is_empty() {
                return Err(Error::Value);
            }
            let ms: Vec<_> = a.iter().map(|e| ctx.matrix(&ctx.eval(e))).collect();
            let rows = ms[0].len();
            let cols = ms[0].first().map_or(0, |r| r.len());
            if ms
                .iter()
                .any(|m| m.len() != rows || m.first().map_or(0, |r| r.len()) != cols)
            {
                return Err(Error::Value);
            }
            let mut total = 0.0;
            for r in 0..rows {
                for c in 0..cols {
                    let mut p = 1.0;
                    for m in &ms {
                        p *= match &m[r][c] {
                            Value::Number(x) => *x,
                            Value::Bool(b) if a.len() == 1 => *b as i32 as f64,
                            Value::Error(e) => return Err(*e),
                            _ => 0.0,
                        };
                    }
                    total += p;
                }
            }
            total.into()
        }
        // --- Statistics --------------------------------------------------
        "AVERAGE" => {
            let xs = numbers(ctx, a)?;
            if xs.is_empty() {
                return Err(Error::Div0);
            }
            (xs.iter().sum::<f64>() / xs.len() as f64).into()
        }
        "MIN" => numbers(ctx, a)?
            .into_iter()
            .reduce(f64::min)
            .unwrap_or(0.0)
            .into(),
        "MAX" => numbers(ctx, a)?
            .into_iter()
            .reduce(f64::max)
            .unwrap_or(0.0)
            .into(),
        "MEDIAN" => {
            let xs = numbers(ctx, a)?;
            percentile(xs, 0.5).map_err(|_| Error::Num)?.into()
        }
        "PERCENTILE" | "PERCENTILE.INC" => {
            need(a, 2, 2)?;
            percentile(numbers(ctx, &a[..1])?, n(1)?)?.into()
        }
        "MODE" | "MODE.SNGL" => {
            let xs = numbers(ctx, a)?;
            let mut best = None;
            let mut count = 1;
            for (i, x) in xs.iter().enumerate() {
                let c = xs[i..].iter().filter(|y| *y == x).count();
                if c > count {
                    count = c;
                    best = Some(*x);
                }
            }
            best.ok_or(Error::NA)?.into()
        }
        "STDEV" | "STDEV.S" => stats(&numbers(ctx, a)?, true)?.sqrt().into(),
        "STDEV.P" | "STDEVP" => stats(&numbers(ctx, a)?, false)?.sqrt().into(),
        "VAR" | "VAR.S" => stats(&numbers(ctx, a)?, true)?.into(),
        "VAR.P" | "VARP" => stats(&numbers(ctx, a)?, false)?.into(),
        "LARGE" | "SMALL" => {
            need(a, 2, 2)?;
            let mut xs = numbers(ctx, &a[..1])?;
            let k = n(1)?.ceil() as usize;
            if k == 0 || k > xs.len() {
                return Err(Error::Num);
            }
            xs.sort_by(|x, y| x.partial_cmp(y).unwrap());
            if name == "LARGE" {
                xs[xs.len() - k]
            } else {
                xs[k - 1]
            }
            .into()
        }
        "RANK" | "RANK.EQ" => {
            need(a, 2, 3)?;
            let x = n(0)?;
            let xs = numbers(ctx, &a[1..2])?;
            if !xs.contains(&x) {
                return Err(Error::NA);
            }
            let asc = opt_n(2, 0.0)? != 0.0;
            (1 + xs
                .iter()
                .filter(|y| if asc { **y < x } else { **y > x })
                .count())
            .to_owned() as f64
        }
        .into(),
        "COUNT" => {
            let mut c = 0usize;
            each(ctx, a, &mut |v, from_cells| {
                match v {
                    Value::Number(_) => c += 1,
                    Value::Text(t) if !from_cells && value::parse_number(t).is_some() => c += 1,
                    Value::Bool(_) if !from_cells => c += 1,
                    _ => {}
                }
                Ok(())
            })?;
            (c as f64).into()
        }
        "COUNTA" => {
            let mut c = 0usize;
            each(ctx, a, &mut |v, _| {
                if !v.is_empty() {
                    c += 1;
                }
                Ok(())
            })?;
            (c as f64).into()
        }
        "COUNTBLANK" => {
            need(a, 1, 1)?;
            let m = ctx.matrix(&ctx.eval(&a[0]));
            m.iter()
                .flatten()
                .filter(|v| {
                    matches!(v, Value::Empty) || matches!(v, Value::Text(t) if t.is_empty())
                })
                .count()
                .to_owned() as f64
        }
        .into(),
        "COUNTIF" => {
            need(a, 2, 2)?;
            let (_, _, mask) = matching(ctx, a)?;
            (mask.iter().filter(|m| **m).count() as f64).into()
        }
        "COUNTIFS" => {
            let (_, _, mask) = matching(ctx, a)?;
            (mask.iter().filter(|m| **m).count() as f64).into()
        }
        "SUMIF" | "AVERAGEIF" => {
            need(a, 2, 3)?;
            let (rows, cols, mask) = matching(ctx, &a[..2])?;
            let target = a
                .get(2)
                .filter(|e| !matches!(e, Expr::Missing))
                .unwrap_or(&a[0]);
            let target = match ctx.eval(target) {
                // A smaller sum range grows to the criteria range's size, like Excel.
                Val::R(s, area) => Val::R(
                    s,
                    Area::new(
                        area.r0,
                        area.c0,
                        area.r0 + rows as u32 - 1,
                        area.c0 + cols as u32 - 1,
                    ),
                ),
                other => other,
            };
            let xs = masked(&ctx.matrix(&target), rows, cols, &mask)?;
            if name == "SUMIF" {
                xs.iter().sum::<f64>().into()
            } else if xs.is_empty() {
                return Err(Error::Div0);
            } else {
                (xs.iter().sum::<f64>() / xs.len() as f64).into()
            }
        }
        "SUMIFS" | "AVERAGEIFS" | "MAXIFS" | "MINIFS" => {
            if a.len() < 3 {
                return Err(Error::Value);
            }
            let (rows, cols, mask) = matching(ctx, &a[1..])?;
            let xs = masked(&ctx.matrix(&ctx.eval(&a[0])), rows, cols, &mask)?;
            match name {
                "SUMIFS" => xs.iter().sum::<f64>().into(),
                "MAXIFS" => xs.into_iter().reduce(f64::max).unwrap_or(0.0).into(),
                "MINIFS" => xs.into_iter().reduce(f64::min).unwrap_or(0.0).into(),
                _ => {
                    if xs.is_empty() {
                        return Err(Error::Div0);
                    }
                    (xs.iter().sum::<f64>() / xs.len() as f64).into()
                }
            }
        }
        // --- Logic -------------------------------------------------------
        "TRUE" => true.into(),
        "FALSE" => false.into(),
        "IF" => {
            need(a, 2, 3)?;
            let cond = ctx.eval(&a[0]);
            if !matches!(cond, Val::V(_)) && !matches!(&cond, Val::R(_, ar) if ar.is_cell()) {
                // An array condition: IF applied to each element.
                let yes = ctx.eval(&a[1]);
                let no = a
                    .get(2)
                    .map(|e| ctx.eval(e))
                    .unwrap_or(Val::V(Value::Bool(false)));
                let picked = ctx.map2(cond, yes, |c, y| match c.as_bool() {
                    Ok(true) => y.clone(),
                    Ok(false) => Value::Empty,
                    Err(e) => Value::Error(e),
                });
                return Ok(ctx.map2(
                    picked,
                    no,
                    |p, n| if p.is_empty() { n.clone() } else { p.clone() },
                ));
            }
            let c = ctx.scalar_of(cond).as_bool()?;
            if c {
                ctx.eval(&a[1])
            } else if let Some(e) = a.get(2) {
                if matches!(e, Expr::Missing) {
                    Val::V(Value::Number(0.0))
                } else {
                    ctx.eval(e)
                }
            } else {
                false.into()
            }
        }
        "IFS" => {
            if a.len() < 2 || !a.len().is_multiple_of(2) {
                return Err(Error::Value);
            }
            for pair in a.chunks(2) {
                if ctx.boolean(&pair[0])? {
                    return Ok(ctx.eval(&pair[1]));
                }
            }
            return Err(Error::NA);
        }
        "SWITCH" => {
            if a.len() < 3 {
                return Err(Error::Value);
            }
            let x = ctx.scalar(&a[0]);
            if let Value::Error(e) = x {
                return Err(e);
            }
            let rest = &a[1..];
            for pair in rest.chunks(2) {
                if pair.len() == 1 {
                    return Ok(ctx.eval(&pair[0]));
                }
                let v = ctx.scalar(&pair[0]);
                if same_kind(&x, &v) && compare(&x, &v) == std::cmp::Ordering::Equal {
                    return Ok(ctx.eval(&pair[1]));
                }
            }
            return Err(Error::NA);
        }
        "IFERROR" | "IFNA" => {
            need(a, 2, 2)?;
            let v = ctx.eval(&a[0]);
            let check = |v: &Value| match v {
                Value::Error(Error::NA) => true,
                Value::Error(_) => name == "IFERROR",
                _ => false,
            };
            match &v {
                Val::V(x) if check(x) => ctx.eval(&a[1]),
                Val::R(_, ar) if ar.is_cell() && check(&ctx.scalar_of(v.clone())) => {
                    ctx.eval(&a[1])
                }
                Val::A(_) => {
                    let fallback = ctx.scalar(&a[1]);
                    let m = ctx.matrix(&v);
                    Val::A(Arc::new(
                        m.iter()
                            .map(|r| {
                                r.iter()
                                    .map(|x| {
                                        if check(x) {
                                            fallback.clone()
                                        } else {
                                            x.clone()
                                        }
                                    })
                                    .collect()
                            })
                            .collect(),
                    ))
                }
                _ => v,
            }
        }
        "AND" | "OR" | "XOR" => {
            let mut vals = Vec::new();
            each(ctx, a, &mut |v, from_cells| {
                match v {
                    Value::Empty => {}
                    Value::Text(_) if from_cells => {}
                    other => vals.push(other.as_bool()?),
                }
                Ok(())
            })?;
            if vals.is_empty() {
                return Err(Error::Value);
            }
            match name {
                "AND" => vals.iter().all(|b| *b),
                "OR" => vals.iter().any(|b| *b),
                _ => vals.iter().filter(|b| **b).count() % 2 == 1,
            }
            .into()
        }
        "NOT" => {
            need(a, 1, 1)?;
            (!ctx.boolean(&a[0])?).into()
        }
        "CHOOSE" => {
            if a.len() < 2 {
                return Err(Error::Value);
            }
            let i = n(0)?.floor() as usize;
            if i < 1 || i >= a.len() {
                return Err(Error::Value);
            }
            ctx.eval(&a[i])
        }
        // --- Information -------------------------------------------------
        "ISBLANK" => matches!(ctx.scalar(&a[0]), Value::Empty).into(),
        "ISNUMBER" => matches!(ctx.scalar(&a[0]), Value::Number(_)).into(),
        "ISTEXT" => matches!(ctx.scalar(&a[0]), Value::Text(_)).into(),
        "ISLOGICAL" => matches!(ctx.scalar(&a[0]), Value::Bool(_)).into(),
        "ISERROR" => matches!(ctx.scalar(&a[0]), Value::Error(_)).into(),
        "ISERR" => matches!(ctx.scalar(&a[0]), Value::Error(e) if e != Error::NA).into(),
        "ISNA" => matches!(ctx.scalar(&a[0]), Value::Error(Error::NA)).into(),
        "ISEVEN" => (n(0)?.trunc() % 2.0 == 0.0).into(),
        "ISODD" => (n(0)?.trunc() % 2.0 != 0.0).into(),
        "ISFORMULA" => match ctx.eval(&a[0]) {
            Val::R(s, ar) => ctx.grid.is_formula(s, ar.r0, ar.c0).into(),
            _ => return Err(Error::Value),
        },
        "N" => match ctx.scalar(&a[0]) {
            Value::Number(x) => x.into(),
            Value::Bool(b) => (b as i32 as f64).into(),
            Value::Error(e) => return Err(e),
            _ => 0.0.into(),
        },
        "T" => match ctx.scalar(&a[0]) {
            Value::Text(t) => Val::V(Value::Text(t)),
            Value::Error(e) => return Err(e),
            _ => Val::V(Value::text("")),
        },
        "NA" => return Err(Error::NA),
        "ROW" | "COLUMN" => {
            if a.is_empty() || matches!(a[0], Expr::Missing) {
                return Ok((if name == "ROW" { ctx.row } else { ctx.col } as f64 + 1.0).into());
            }
            match ctx.eval(&a[0]) {
                Val::R(_, ar) => (if name == "ROW" { ar.r0 } else { ar.c0 } as f64 + 1.0).into(),
                _ => return Err(Error::Value),
            }
        }
        "ROWS" | "COLUMNS" => {
            need(a, 1, 1)?;
            let v = ctx.eval(&a[0]);
            let (r, c) = match &v {
                Val::R(_, ar) => (ar.rows() as usize, ar.cols() as usize),
                Val::A(m) => (m.len(), m.first().map_or(0, |x| x.len())),
                Val::V(_) => (1, 1),
            };
            (if name == "ROWS" { r } else { c } as f64).into()
        }
        // --- Text --------------------------------------------------------
        "LEN" => (t(0)?.chars().count() as f64).into(),
        "LOWER" => Val::V(Value::text(t(0)?.to_lowercase())),
        "UPPER" => Val::V(Value::text(t(0)?.to_uppercase())),
        "PROPER" => {
            let mut out = String::new();
            let mut start = true;
            for ch in t(0)?.chars() {
                if ch.is_alphabetic() {
                    if start {
                        out.extend(ch.to_uppercase());
                    } else {
                        out.extend(ch.to_lowercase());
                    }
                    start = false;
                } else {
                    out.push(ch);
                    start = true;
                }
            }
            Val::V(Value::text(out))
        }
        "TRIM" => Val::V(Value::text(
            t(0)?.split_whitespace().collect::<Vec<_>>().join(" "),
        )),
        "CLEAN" => Val::V(Value::text(
            t(0)?
                .chars()
                .filter(|c| !c.is_control())
                .collect::<String>(),
        )),
        "LEFT" | "RIGHT" => {
            need(a, 1, 2)?;
            let s: Vec<char> = t(0)?.chars().collect();
            let k = opt_n(1, 1.0)?;
            if k < 0.0 {
                return Err(Error::Value);
            }
            let k = (k as usize).min(s.len());
            let out: String = if name == "LEFT" {
                s[..k].iter().collect()
            } else {
                s[s.len() - k..].iter().collect()
            };
            Val::V(Value::text(out))
        }
        "MID" => {
            need(a, 3, 3)?;
            let s: Vec<char> = t(0)?.chars().collect();
            let start = n(1)?;
            let len = n(2)?;
            if start < 1.0 || len < 0.0 {
                return Err(Error::Value);
            }
            let st = (start as usize - 1).min(s.len());
            let en = (st + len as usize).min(s.len());
            Val::V(Value::text(s[st..en].iter().collect::<String>()))
        }
        "CONCAT" | "CONCATENATE" => {
            let mut out = String::new();
            each(ctx, a, &mut |v, _| {
                out += &v.as_text()?;
                Ok(())
            })?;
            Val::V(Value::text(out))
        }
        "TEXTJOIN" => {
            if a.len() < 3 {
                return Err(Error::Value);
            }
            let delim = t(0)?;
            let skip = ctx.boolean(&a[1])?;
            let mut parts = Vec::new();
            each(ctx, &a[2..], &mut |v, _| {
                let s = v.as_text()?;
                if !(skip && s.is_empty()) {
                    parts.push(s);
                }
                Ok(())
            })?;
            Val::V(Value::text(parts.join(&delim)))
        }
        "SUBSTITUTE" => {
            need(a, 3, 4)?;
            let (s, old, new) = (t(0)?, t(1)?, t(2)?);
            if old.is_empty() {
                return Ok(Val::V(Value::text(s)));
            }
            match a.get(3) {
                Some(e) if !matches!(e, Expr::Missing) => {
                    let k = ctx.number(e)? as usize;
                    if k == 0 {
                        return Err(Error::Value);
                    }
                    match s.match_indices(&old).nth(k - 1) {
                        Some((i, _)) => Val::V(Value::text(format!(
                            "{}{}{}",
                            &s[..i],
                            new,
                            &s[i + old.len()..]
                        ))),
                        None => Val::V(Value::text(s)),
                    }
                }
                _ => Val::V(Value::text(s.replace(&old, &new))),
            }
        }
        "REPLACE" => {
            need(a, 4, 4)?;
            let s: Vec<char> = t(0)?.chars().collect();
            let start = (n(1)? as usize).max(1) - 1;
            let len = n(2)?.max(0.0) as usize;
            let st = start.min(s.len());
            let en = (st + len).min(s.len());
            let mut out: String = s[..st].iter().collect();
            out += &t(3)?;
            out.extend(&s[en..]);
            Val::V(Value::text(out))
        }
        "FIND" | "SEARCH" => {
            need(a, 2, 3)?;
            let (needle, hay) = (t(0)?, t(1)?);
            let start = opt_n(2, 1.0)? as usize;
            let hay_chars: Vec<char> = hay.chars().collect();
            if start < 1 || start > hay_chars.len() + 1 {
                return Err(Error::Value);
            }
            if name == "FIND" {
                let tail: String = hay_chars[start - 1..].iter().collect();
                match tail.find(&needle) {
                    Some(i) => (tail[..i].chars().count() as f64 + start as f64).into(),
                    None => return Err(Error::Value),
                }
            } else {
                let p: Vec<char> = format!("{}*", needle.to_lowercase()).chars().collect();
                let lower: Vec<char> = hay.to_lowercase().chars().collect();
                for i in start - 1..=lower.len() {
                    if wildcard(&p, &lower[i..]) {
                        return Ok(((i + 1) as f64).into());
                    }
                }
                return Err(Error::Value);
            }
        }
        "REPT" => {
            need(a, 2, 2)?;
            let k = n(1)?;
            if !(0.0..=32767.0).contains(&k) {
                return Err(Error::Value);
            }
            Val::V(Value::text(t(0)?.repeat(k as usize)))
        }
        "EXACT" => (t(0)? == t(1)?).into(),
        "CHAR" => {
            let c = char::from_u32(n(0)? as u32).ok_or(Error::Value)?;
            Val::V(Value::text(c.to_string()))
        }
        "CODE" => (t(0)?.chars().next().ok_or(Error::Value)? as u32 as f64).into(),
        "VALUE" => {
            let v = ctx.scalar(&a[0]);
            match v {
                Value::Number(x) => x.into(),
                Value::Text(s) => {
                    if let Some((x, _)) = value::parse_number(&s) {
                        x.into()
                    } else if let Some((x, _)) = value::parse_date(&s, true) {
                        x.into()
                    } else {
                        return Err(Error::Value);
                    }
                }
                Value::Empty => 0.0.into(),
                Value::Error(e) => return Err(e),
                _ => return Err(Error::Value),
            }
        }
        "TEXT" => {
            need(a, 2, 2)?;
            let v = ctx.scalar(&a[0]);
            if let Value::Error(e) = v {
                return Err(e);
            }
            let v = match &v {
                Value::Text(s) => value::parse_number(s)
                    .map(|x| Value::Number(x.0))
                    .unwrap_or(v.clone()),
                _ => v,
            };
            Val::V(Value::text(super::format::format(&v, Some(&t(1)?)).0))
        }
        "SPLIT" => {
            need(a, 2, 2)?;
            let (s, d) = (t(0)?, t(1)?);
            if d.is_empty() {
                return Err(Error::Value);
            }
            let parts: Vec<Value> = s
                .split(|c| d.contains(c))
                .filter(|p| !p.is_empty())
                .map(|p| match value::parse_number(p) {
                    Some((x, _)) => Value::Number(x),
                    None => Value::text(p),
                })
                .collect();
            arr(vec![parts])
        }
        // --- Dates -------------------------------------------------------
        "TODAY" => (value::now_serial(ctx.grid.utc_offset()).floor()).into(),
        "NOW" => value::now_serial(ctx.grid.utc_offset()).into(),
        "DATE" => {
            need(a, 3, 3)?;
            let mut y = n(0)?.floor() as i64;
            if y < 1900 {
                y += 1900;
            }
            value::date_serial(y, n(1)?.floor() as i64, n(2)?.floor() as i64).into()
        }
        "TIME" => {
            need(a, 3, 3)?;
            let secs = n(0)? * 3600.0 + n(1)? * 60.0 + n(2)?;
            if secs < 0.0 {
                return Err(Error::Num);
            }
            ((secs / 86400.0).fract()).into()
        }
        "DATEVALUE" => {
            let s = t(0)?;
            value::parse_date(&s, true)
                .map(|x| x.0.floor())
                .ok_or(Error::Value)?
                .into()
        }
        "YEAR" => (value::serial_date(n(0)?).0 as f64).into(),
        "MONTH" => (value::serial_date(n(0)?).1 as f64).into(),
        "DAY" => (value::serial_date(n(0)?).2 as f64).into(),
        "HOUR" => (value::serial_time(n(0)?).0 as f64).into(),
        "MINUTE" => (value::serial_time(n(0)?).1 as f64).into(),
        "SECOND" => (value::serial_time(n(0)?).2 as f64).into(),
        "WEEKDAY" => {
            need(a, 1, 2)?;
            let wd = value::weekday(n(0)?) as f64; // 0 = Sunday
            match opt_n(1, 1.0)? as i32 {
                1 => wd + 1.0,
                2 => (wd + 6.0) % 7.0 + 1.0,
                3 => (wd + 6.0) % 7.0,
                _ => return Err(Error::Num),
            }
            .into()
        }
        "DAYS" => {
            need(a, 2, 2)?;
            (n(0)?.floor() - n(1)?.floor()).into()
        }
        "EDATE" | "EOMONTH" => {
            need(a, 2, 2)?;
            add_months(n(0)?, n(1)?.trunc() as i64, name == "EOMONTH").into()
        }
        "DATEDIF" => {
            need(a, 3, 3)?;
            let (s, e) = (n(0)?.floor(), n(1)?.floor());
            if s > e {
                return Err(Error::Num);
            }
            let (y1, m1, d1) = value::serial_date(s);
            let (y2, m2, d2) = value::serial_date(e);
            let months = (y2 - y1) * 12 + m2 as i64 - m1 as i64 - if d2 < d1 { 1 } else { 0 };
            match t(2)?.to_ascii_uppercase().as_str() {
                "D" => e - s,
                "M" => months as f64,
                "Y" => (months / 12) as f64,
                "YM" => (months % 12) as f64,
                "MD" => {
                    let prev = add_months(e, -1, false);
                    if d2 >= d1 {
                        (d2 - d1) as f64
                    } else {
                        e - value::date_serial(
                            value::serial_date(prev).0,
                            value::serial_date(prev).1 as i64,
                            d1 as i64,
                        )
                    }
                }
                "YD" => {
                    let anniv = value::date_serial(y2, m1 as i64, d1 as i64);
                    let anniv = if anniv > e {
                        value::date_serial(y2 - 1, m1 as i64, d1 as i64)
                    } else {
                        anniv
                    };
                    e - anniv
                }
                _ => return Err(Error::Num),
            }
            .into()
        }
        "NETWORKDAYS" => {
            need(a, 2, 2)?;
            let (s, e) = (n(0)?.floor() as i64, n(1)?.floor() as i64);
            let (lo, hi, sign) = if s <= e { (s, e, 1.0) } else { (e, s, -1.0) };
            let mut count = 0;
            for d in lo..=hi {
                let wd = value::weekday(d as f64);
                if wd != 0 && wd != 6 {
                    count += 1;
                }
            }
            (count as f64 * sign).into()
        }
        // --- Lookup and references --------------------------------------
        "VLOOKUP" | "HLOOKUP" => {
            need(a, 3, 4)?;
            let key = ctx.scalar(&a[0]);
            if let Value::Error(e) = key {
                return Err(e);
            }
            let table = ctx.eval(&a[1]);
            let m = ctx.matrix(&table);
            let idx = n(2)?.floor() as usize;
            let sorted = match a.get(3) {
                None | Some(Expr::Missing) => true,
                Some(e) => ctx.boolean(e)?,
            };
            let vertical = name == "VLOOKUP";
            let (keys, width) = if vertical {
                (column_of(&m, 0), m.first().map_or(0, |r| r.len()))
            } else {
                (m.first().cloned().unwrap_or_default(), m.len())
            };
            if idx < 1 || idx > width {
                return Err(if idx < 1 { Error::Value } else { Error::Ref });
            }
            let i =
                find(&key, &keys, if sorted { 1 } else { 0 }, !sorted, false).ok_or(Error::NA)?;
            Val::V(if vertical {
                m[i][idx - 1].clone()
            } else {
                m[idx - 1][i].clone()
            })
        }
        "MATCH" => {
            need(a, 2, 3)?;
            let key = ctx.scalar(&a[0]);
            let list = flat(&ctx.matrix(&ctx.eval(&a[1])))?;
            let mode = opt_n(2, 1.0)?.signum() as i32;
            let i = find(&key, &list, mode, mode == 0, false).ok_or(Error::NA)?;
            ((i + 1) as f64).into()
        }
        "XLOOKUP" => {
            need(a, 3, 6)?;
            let key = ctx.scalar(&a[0]);
            let look = flat(&ctx.matrix(&ctx.eval(&a[1])))?;
            let result = ctx.eval(&a[2]);
            let mode = opt_n(4, 0.0)? as i32;
            let reverse = opt_n(5, 1.0)? < 0.0;
            let found = match mode {
                0 => find(&key, &look, 0, false, reverse),
                2 => find(&key, &look, 0, true, reverse),
                -1 => find(&key, &look, 1, false, reverse),
                1 => find(&key, &look, -1, false, reverse),
                _ => return Err(Error::Value),
            };
            let Some(i) = found else {
                return match a.get(3) {
                    Some(e) if !matches!(e, Expr::Missing) => Ok(ctx.eval(e)),
                    _ => Err(Error::NA),
                };
            };
            match result {
                Val::R(s, ar) => {
                    if ar.c0 == ar.c1 || look.len() as u32 == ar.rows() && ar.rows() > 1 {
                        Val::R(
                            s,
                            Area::new(ar.r0 + i as u32, ar.c0, ar.r0 + i as u32, ar.c1),
                        )
                    } else {
                        Val::R(
                            s,
                            Area::new(ar.r0, ar.c0 + i as u32, ar.r1, ar.c0 + i as u32),
                        )
                    }
                }
                other => {
                    let m = ctx.matrix(&other);
                    let v = flat(&m)?;
                    Val::V(v.get(i).cloned().ok_or(Error::NA)?)
                }
            }
        }
        "INDEX" => {
            need(a, 2, 3)?;
            let src = ctx.eval(&a[0]);
            let r = n(1)?.floor() as i64;
            let c = opt_n(2, 0.0)?.floor() as i64;
            match src {
                Val::R(s, ar) => {
                    let (rows, cols) = (ar.rows() as i64, ar.cols() as i64);
                    let (r, c) = if rows == 1 && a.len() == 2 {
                        (1, r)
                    } else {
                        (r, c)
                    };
                    if r < 0 || c < 0 || r > rows || c > cols {
                        return Err(Error::Ref);
                    }
                    let (r0, r1) = if r == 0 {
                        (ar.r0, ar.r1)
                    } else {
                        (ar.r0 + r as u32 - 1, ar.r0 + r as u32 - 1)
                    };
                    let (c0, c1) = if c == 0 {
                        (ar.c0, ar.c1)
                    } else {
                        (ar.c0 + c as u32 - 1, ar.c0 + c as u32 - 1)
                    };
                    Val::R(s, Area::new(r0, c0, r1, c1))
                }
                other => {
                    let m = ctx.matrix(&other);
                    let (r, c) = if m.len() == 1 && a.len() == 2 {
                        (1, r)
                    } else {
                        (r, c.max(1))
                    };
                    let row = m.get((r.max(1) - 1) as usize).ok_or(Error::Ref)?;
                    Val::V(
                        row.get((c.max(1) - 1) as usize)
                            .cloned()
                            .ok_or(Error::Ref)?,
                    )
                }
            }
        }
        "OFFSET" => {
            need(a, 3, 5)?;
            let Val::R(s, ar) = ctx.eval(&a[0]) else {
                return Err(Error::Value);
            };
            let r0 = ar.r0 as i64 + n(1)? as i64;
            let c0 = ar.c0 as i64 + n(2)? as i64;
            let h = opt_n(3, ar.rows() as f64)? as i64;
            let w = opt_n(4, ar.cols() as f64)? as i64;
            if r0 < 0 || c0 < 0 || h < 1 || w < 1 {
                return Err(Error::Ref);
            }
            Val::R(
                s,
                Area::new(
                    r0 as u32,
                    c0 as u32,
                    (r0 + h - 1) as u32,
                    (c0 + w - 1) as u32,
                ),
            )
        }
        "INDIRECT" => {
            let text = t(0)?;
            let (sheet, rest) = addr::split_sheet(&text);
            let area = addr::parse_area(rest).ok_or(Error::Ref)?;
            let s = match sheet {
                Some(name) => ctx.grid.sheet_index(&name).ok_or(Error::Ref)?,
                None => ctx.sheet,
            };
            let (rows, cols) = ctx.grid.extent(s);
            let area = if area.whole_cols() || area.whole_rows() {
                area.clamp(rows.max(1), cols.max(1)).ok_or(Error::Ref)?
            } else {
                area
            };
            Val::R(s, area)
        }
        // --- Dynamic arrays (their results spill into the cells below/right) ---
        "SEQUENCE" => {
            need(a, 1, 4)?;
            let rows = n(0)? as i64;
            let cols = opt_n(1, 1.0)? as i64;
            let start = opt_n(2, 1.0)?;
            let step = opt_n(3, 1.0)?;
            if rows < 1 || cols < 1 || rows * cols > 1_000_000 {
                return Err(Error::Value);
            }
            arr((0..rows)
                .map(|r| {
                    (0..cols)
                        .map(|c| num(start + step * (r * cols + c) as f64))
                        .collect()
                })
                .collect())
        }
        "TRANSPOSE" => {
            need(a, 1, 1)?;
            let m = ctx.matrix(&ctx.eval(&a[0]));
            let cols = m.first().map_or(0, |r| r.len());
            arr((0..cols)
                .map(|c| m.iter().map(|r| r[c].clone()).collect())
                .collect())
        }
        "UNIQUE" => {
            need(a, 1, 1)?;
            let m = ctx.matrix(&ctx.eval(&a[0]));
            let mut seen = HashSet::new();
            let rows: Vec<Vec<Value>> = m
                .iter()
                .filter(|r| {
                    seen.insert(
                        r.iter()
                            .map(|v| v.display().to_lowercase())
                            .collect::<Vec<_>>()
                            .join("\u{1}"),
                    )
                })
                .filter(|r| !r.iter().all(|v| v.is_empty()))
                .cloned()
                .collect();
            arr(rows)
        }
        "SORT" => {
            need(a, 1, 4)?;
            let m = ctx.matrix(&ctx.eval(&a[0]));
            let col = opt_n(1, 1.0)? as usize;
            let asc = opt_n(2, 1.0)? > 0.0;
            let by_col = match a.get(3) {
                None | Some(Expr::Missing) => false,
                Some(e) => ctx.boolean(e)?,
            };
            let mut rows: Vec<Vec<Value>> = if by_col {
                let cols = m.first().map_or(0, |r| r.len());
                (0..cols)
                    .map(|c| m.iter().map(|r| r[c].clone()).collect())
                    .collect()
            } else {
                m.to_vec()
            };
            rows.retain(|r| !r.iter().all(|v| v.is_empty()));
            if col < 1 || rows.first().is_some_and(|r| col > r.len()) {
                return Err(Error::Value);
            }
            rows.sort_by(|x, y| {
                let o = x[col - 1].sort_cmp(&y[col - 1]);
                if asc { o } else { o.reverse() }
            });
            if by_col {
                let cols = rows.first().map_or(0, |r| r.len());
                rows = (0..cols)
                    .map(|c| rows.iter().map(|r| r[c].clone()).collect())
                    .collect();
            }
            arr(rows)
        }
        "FILTER" => {
            need(a, 2, 3)?;
            let m = ctx.matrix(&ctx.eval(&a[0]));
            let inc = ctx.matrix(&ctx.eval(&a[1]));
            let keep: Vec<bool> = if inc.len() == m.len() {
                inc.iter()
                    .map(|r| r.first().is_some_and(|v| v.as_bool().unwrap_or(false)))
                    .collect()
            } else if inc.len() == 1 && inc[0].len() == m.first().map_or(0, |r| r.len()) {
                // Filtering columns.
                let flags: Vec<bool> = inc[0]
                    .iter()
                    .map(|v| v.as_bool().unwrap_or(false))
                    .collect();
                let rows: Vec<Vec<Value>> = m
                    .iter()
                    .map(|r| {
                        r.iter()
                            .zip(&flags)
                            .filter(|(_, k)| **k)
                            .map(|(v, _)| v.clone())
                            .collect()
                    })
                    .collect();
                return Ok(if rows.first().is_none_or(|r| r.is_empty()) {
                    empty_result(ctx, a.get(2))
                } else {
                    arr(rows)
                });
            } else {
                return Err(Error::Value);
            };
            let rows: Vec<Vec<Value>> = m
                .iter()
                .zip(keep)
                .filter(|(_, k)| *k)
                .map(|(r, _)| r.clone())
                .collect();
            if rows.is_empty() {
                empty_result(ctx, a.get(2))
            } else {
                arr(rows)
            }
        }
        _ => return Err(Error::Name),
    })
}

fn empty_result(ctx: &Ctx, fallback: Option<&Expr>) -> Val {
    match fallback {
        Some(e) if !matches!(e, Expr::Missing) => ctx.eval(e),
        _ => err(Error::Value),
    }
}
