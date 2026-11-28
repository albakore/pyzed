//! Cell values, errors, coercion rules and dates (serial numbers, like Excel and Sheets).

use std::cmp::Ordering;
use std::sync::Arc;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Error {
    Div0,
    Value,
    Ref,
    Name,
    NA,
    Num,
    Null,
    Cycle,
    Spill,
    /// A formula that could not be read (a typo, an unclosed parenthesis...).
    Parse,
}

impl Error {
    pub fn as_str(self) -> &'static str {
        match self {
            Error::Div0 => "#DIV/0!",
            Error::Value => "#VALUE!",
            Error::Ref => "#REF!",
            Error::Name => "#NAME?",
            Error::NA => "#N/A",
            Error::Num => "#NUM!",
            Error::Null => "#NULL!",
            Error::Cycle => "#CYCLE!",
            Error::Spill => "#SPILL!",
            Error::Parse => "#ERROR!",
        }
    }

    pub fn parse(text: &str) -> Option<Self> {
        Some(match text.to_ascii_uppercase().as_str() {
            "#DIV/0!" => Error::Div0,
            "#VALUE!" => Error::Value,
            "#REF!" => Error::Ref,
            "#NAME?" => Error::Name,
            "#N/A" => Error::NA,
            "#NUM!" => Error::Num,
            "#NULL!" => Error::Null,
            "#CYCLE!" => Error::Cycle,
            "#SPILL!" => Error::Spill,
            "#ERROR!" => Error::Parse,
            _ => return None,
        })
    }

    /// Why the error happened, for the cell's tooltip.
    pub fn describe(self) -> &'static str {
        match self {
            Error::Div0 => "Division by zero.",
            Error::Value => "A value has the wrong type (text where a number was expected?).",
            Error::Ref => "The formula refers to a cell that does not exist (deleted?).",
            Error::Name => "Unknown function or name.",
            Error::NA => "No value available (a lookup found nothing).",
            Error::Num => "The number is not valid for this function.",
            Error::Null => "The ranges do not intersect.",
            Error::Cycle => "Circular reference: the formula depends on itself.",
            Error::Spill => "The result needs more cells, but some of them are not empty.",
            Error::Parse => "The formula could not be read.",
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq)]
pub enum Value {
    #[default]
    Empty,
    Number(f64),
    Text(Arc<str>),
    Bool(bool),
    Error(Error),
}

impl Value {
    pub fn text(s: impl Into<Arc<str>>) -> Self {
        Value::Text(s.into())
    }

    pub fn is_empty(&self) -> bool {
        matches!(self, Value::Empty)
    }

    /// The number this value stands for in arithmetic (`""` and blanks are 0, text is parsed).
    pub fn as_number(&self) -> Result<f64, Error> {
        match self {
            Value::Empty => Ok(0.0),
            Value::Number(n) => Ok(*n),
            Value::Bool(b) => Ok(if *b { 1.0 } else { 0.0 }),
            Value::Text(t) => {
                if t.trim().is_empty() {
                    return Err(Error::Value);
                }
                parse_number(t).map(|(n, _)| n).ok_or(Error::Value)
            }
            Value::Error(e) => Err(*e),
        }
    }

    pub fn as_bool(&self) -> Result<bool, Error> {
        match self {
            Value::Empty => Ok(false),
            Value::Number(n) => Ok(*n != 0.0),
            Value::Bool(b) => Ok(*b),
            Value::Text(t) => match t.to_ascii_uppercase().as_str() {
                "TRUE" => Ok(true),
                "FALSE" => Ok(false),
                _ => Err(Error::Value),
            },
            Value::Error(e) => Err(*e),
        }
    }

    /// The text this value shows in text functions (`CONCAT`, `LEN`, `&`).
    pub fn as_text(&self) -> Result<String, Error> {
        match self {
            Value::Empty => Ok(String::new()),
            Value::Number(n) => Ok(number_text(*n)),
            Value::Text(t) => Ok(t.to_string()),
            Value::Bool(b) => Ok(if *b { "TRUE" } else { "FALSE" }.into()),
            Value::Error(e) => Err(*e),
        }
    }

    /// The value as plain text without errors (errors show their code).
    pub fn display(&self) -> String {
        match self {
            Value::Error(e) => e.as_str().into(),
            other => other.as_text().unwrap_or_default(),
        }
    }

    pub fn error(&self) -> Option<Error> {
        match self {
            Value::Error(e) => Some(*e),
            _ => None,
        }
    }

    fn rank(&self) -> u8 {
        match self {
            Value::Number(_) => 0,
            Value::Text(_) => 1,
            Value::Bool(_) => 2,
            Value::Error(_) => 3,
            Value::Empty => 4,
        }
    }

    /// Sort order: numbers, then text (case-insensitive), booleans, errors and blanks last.
    pub fn sort_cmp(&self, other: &Value) -> Ordering {
        match (self, other) {
            (Value::Number(a), Value::Number(b)) => a.partial_cmp(b).unwrap_or(Ordering::Equal),
            (Value::Text(a), Value::Text(b)) => cmp_text(a, b),
            (Value::Bool(a), Value::Bool(b)) => a.cmp(b),
            _ => self.rank().cmp(&other.rank()),
        }
    }
}

pub fn cmp_text(a: &str, b: &str) -> Ordering {
    let la = a.to_lowercase();
    let lb = b.to_lowercase();
    la.cmp(&lb)
}

/// Compares two values the way `=`, `<` and `>` do (text is case-insensitive; blanks match
/// 0, `""` and FALSE).
pub fn compare(a: &Value, b: &Value) -> Ordering {
    use Value::*;
    match (a, b) {
        (Empty, Empty) => Ordering::Equal,
        (Empty, Number(n)) => 0.0f64.partial_cmp(n).unwrap_or(Ordering::Equal),
        (Number(n), Empty) => n.partial_cmp(&0.0).unwrap_or(Ordering::Equal),
        (Empty, Text(t)) => cmp_text("", t),
        (Text(t), Empty) => cmp_text(t, ""),
        (Empty, Bool(b)) => false.cmp(b),
        (Bool(b), Empty) => b.cmp(&false),
        (Number(x), Number(y)) => x.partial_cmp(y).unwrap_or(Ordering::Equal),
        (Text(x), Text(y)) => cmp_text(x, y),
        (Bool(x), Bool(y)) => x.cmp(y),
        // Numbers < text < booleans, as in Excel.
        (Number(_), _) => Ordering::Less,
        (_, Number(_)) => Ordering::Greater,
        (Text(_), Bool(_)) => Ordering::Less,
        (Bool(_), Text(_)) => Ordering::Greater,
        _ => Ordering::Equal,
    }
}

/// A number written the way formulas and cells print it (up to 15 significant digits).
pub fn number_text(n: f64) -> String {
    if n.is_nan() {
        return "#NUM!".into();
    }
    if n == 0.0 {
        return "0".into();
    }
    if n.fract() == 0.0 && n.abs() < 1e15 {
        return format!("{}", n as i64);
    }
    let abs = n.abs();
    if !(1e-9..1e15).contains(&abs) {
        let s = format!("{:.10E}", n);
        // Trim the mantissa's trailing zeros: 1.2340000000E5 -> 1.234E+05
        if let Some((m, e)) = s.split_once('E') {
            let m = m.trim_end_matches('0').trim_end_matches('.');
            let e: i32 = e.parse().unwrap_or(0);
            return format!("{m}E{}{:02}", if e < 0 { '-' } else { '+' }, e.abs());
        }
        return s;
    }
    let digits = 15 - (abs.log10().floor() as i32 + 1);
    let digits = digits.clamp(0, 15) as usize;
    let s = format!("{:.*}", digits, n);
    let s = if s.contains('.') {
        s.trim_end_matches('0').trim_end_matches('.').to_string()
    } else {
        s
    };
    if s == "-0" { "0".into() } else { s }
}

/// What typing a number showed besides the number itself (to pick a format for the cell).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NumberHint {
    Plain,
    Percent,
    Currency(char),
    Thousands,
}

/// Parses typed numbers: `12`, `-3.5`, `1,234.5`, `1e3`, `50%`, `$12.50`, `(12)` (negative).
pub fn parse_number(text: &str) -> Option<(f64, NumberHint)> {
    let mut s = text.trim();
    if s.is_empty() {
        return None;
    }
    let mut negative = false;
    if s.starts_with('(') && s.ends_with(')') {
        negative = true;
        s = &s[1..s.len() - 1];
    }
    if let Some(rest) = s.strip_prefix('-') {
        negative = !negative;
        s = rest.trim_start();
    } else if let Some(rest) = s.strip_prefix('+') {
        s = rest.trim_start();
    }
    let mut hint = NumberHint::Plain;
    for sym in ['$', '€', '£', '¥'] {
        if let Some(rest) = s.strip_prefix(sym) {
            hint = NumberHint::Currency(sym);
            s = rest.trim_start();
        } else if let Some(rest) = s.strip_suffix(sym) {
            hint = NumberHint::Currency(sym);
            s = rest.trim_end();
        }
    }
    if let Some(rest) = s.strip_prefix('-') {
        negative = !negative;
        s = rest;
    }
    let mut percent = false;
    if let Some(rest) = s.strip_suffix('%') {
        percent = true;
        s = rest.trim_end();
    }
    if s.is_empty() {
        return None;
    }
    let mut cleaned = String::with_capacity(s.len());
    let mut thousands = false;
    let mut seen_dot = false;
    let bytes: Vec<char> = s.chars().collect();
    for (i, &c) in bytes.iter().enumerate() {
        match c {
            '0'..='9' => cleaned.push(c),
            '.' if !seen_dot => {
                seen_dot = true;
                cleaned.push('.');
            }
            ',' if !seen_dot && i > 0 => {
                // Only "1,234" style groups of three digits.
                let group: String = bytes[i + 1..]
                    .iter()
                    .take_while(|c| c.is_ascii_digit())
                    .collect();
                if group.len() != 3 {
                    return None;
                }
                thousands = true;
            }
            'e' | 'E' => {
                cleaned.push('e');
                let rest: String = bytes[i + 1..].iter().collect();
                if rest.is_empty()
                    || !rest
                        .trim_start_matches(['+', '-'])
                        .chars()
                        .all(|c| c.is_ascii_digit())
                    || rest.trim_start_matches(['+', '-']).is_empty()
                {
                    return None;
                }
                cleaned.push_str(&rest);
                break;
            }
            _ => return None,
        }
    }
    if cleaned == "." || cleaned.is_empty() {
        return None;
    }
    let mut n: f64 = cleaned.parse().ok()?;
    if !n.is_finite() {
        return None;
    }
    if negative {
        n = -n;
    }
    if percent {
        n /= 100.0;
        hint = NumberHint::Percent;
    } else if thousands && hint == NumberHint::Plain {
        hint = NumberHint::Thousands;
    }
    Some((n, hint))
}

// ---------------------------------------------------------------------------
// Dates: serial numbers counted in days from 1899-12-30 (1 = 1899-12-31, 45000 = 2023-03-15),
// the same numbers Excel (after 1900-03-01) and Google Sheets use.
// ---------------------------------------------------------------------------

/// Days since 1970-01-01 for a civil date (Howard Hinnant's algorithm).
pub fn days_from_civil(y: i64, m: u32, d: u32) -> i64 {
    let y = if m <= 2 { y - 1 } else { y };
    let era = if y >= 0 { y } else { y - 399 } / 400;
    let yoe = y - era * 400;
    let m = m as i64;
    let doy = (153 * (if m > 2 { m - 3 } else { m + 9 }) + 2) / 5 + d as i64 - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe - 719468
}

pub fn civil_from_days(z: i64) -> (i64, u32, u32) {
    let z = z + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    (if m <= 2 { y + 1 } else { y }, m, d)
}

/// 1970-01-01 as a serial number.
const UNIX_EPOCH: i64 = 25569;

/// The serial number of a date, normalising out-of-range months and days like `DATE` does.
pub fn date_serial(year: i64, month: i64, day: i64) -> f64 {
    let total = year * 12 + (month - 1);
    let (y, m) = (total.div_euclid(12), total.rem_euclid(12) + 1);
    (days_from_civil(y, m as u32, 1) + UNIX_EPOCH + day - 1) as f64
}

/// `(year, month, day)` of a serial number.
pub fn serial_date(serial: f64) -> (i64, u32, u32) {
    civil_from_days(serial.floor() as i64 - UNIX_EPOCH)
}

/// `(hour, minute, second)` of a serial number's fraction.
pub fn serial_time(serial: f64) -> (u32, u32, u32) {
    let secs = ((serial - serial.floor()) * 86400.0).round() as i64;
    let secs = secs.clamp(0, 86399) as u32;
    (secs / 3600, secs / 60 % 60, secs % 60)
}

/// Weekday of a serial number, 0 = Sunday.
pub fn weekday(serial: f64) -> u32 {
    ((serial.floor() as i64 - 1).rem_euclid(7)) as u32
}

pub fn days_in_month(year: i64, month: u32) -> u32 {
    let next = if month == 12 {
        days_from_civil(year + 1, 1, 1)
    } else {
        days_from_civil(year, month + 1, 1)
    };
    (next - days_from_civil(year, month, 1)) as u32
}

/// The current moment as a serial number in local time (`offset` seconds east of UTC).
pub fn now_serial(offset: i64) -> f64 {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
        + offset as f64;
    secs / 86400.0 + UNIX_EPOCH as f64
}

/// What kind of date text was typed (to pick a date format for the cell).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DateHint {
    Date,
    DateTime,
    Time,
}

/// Parses typed dates and times: `2024-03-15`, `15/03/2024` (or `03/15/2024` with
/// `month_first`), `2024-03-15 14:30`, `14:30`, `2:30 PM`.
pub fn parse_date(text: &str, month_first: bool) -> Option<(f64, DateHint)> {
    let s = text.trim();
    if s.is_empty() || s.len() > 32 {
        return None;
    }
    let (date_part, time_part) = match s.split_once([' ', 'T']) {
        Some((d, t)) if d.contains(['-', '/']) => (Some(d), Some(t.trim())),
        _ if s.contains(['-', '/']) => (Some(s), None),
        _ => (None, Some(s)),
    };
    let mut serial = 0.0;
    let mut hint = DateHint::Time;
    if let Some(d) = date_part {
        let sep = if d.contains('-') { '-' } else { '/' };
        let parts: Vec<&str> = d.split(sep).collect();
        if parts.len() != 3
            || parts
                .iter()
                .any(|p| p.is_empty() || !p.bytes().all(|b| b.is_ascii_digit()))
        {
            return None;
        }
        let nums: Vec<i64> = parts.iter().map(|p| p.parse().unwrap_or(0)).collect();
        let (y, m, dd) = if parts[0].len() == 4 {
            (nums[0], nums[1], nums[2])
        } else if parts[2].len() == 4 || parts[2].len() == 2 {
            let y = if parts[2].len() == 2 {
                2000 + nums[2]
            } else {
                nums[2]
            };
            if month_first {
                (y, nums[0], nums[1])
            } else {
                (y, nums[1], nums[0])
            }
        } else {
            return None;
        };
        if !(1..=12).contains(&m)
            || dd < 1
            || dd > days_in_month(y, m as u32) as i64
            || !(1000..=9999).contains(&y)
        {
            return None;
        }
        serial = date_serial(y, m, dd);
        hint = DateHint::Date;
    }
    if let Some(t) = time_part {
        if t.is_empty() {
            return (hint == DateHint::Date).then_some((serial, hint));
        }
        let upper = t.to_ascii_uppercase();
        let (clock, pm) = if let Some(c) = upper.strip_suffix("PM") {
            (c.trim().to_string(), Some(true))
        } else if let Some(c) = upper.strip_suffix("AM") {
            (c.trim().to_string(), Some(false))
        } else {
            (upper.clone(), None)
        };
        let parts: Vec<&str> = clock.split(':').collect();
        if parts.len() < 2 || parts.len() > 3 || parts.iter().any(|p| p.is_empty()) {
            return None;
        }
        let h: u32 = parts[0].parse().ok()?;
        let m: u32 = parts[1].parse().ok()?;
        let sec: f64 = parts.get(2).map(|p| p.parse().ok()).unwrap_or(Some(0.0))?;
        let h = match pm {
            Some(true) if h < 12 => h + 12,
            Some(false) if h == 12 => 0,
            _ => h,
        };
        if h > 23 || m > 59 || !(0.0..60.0).contains(&sec) {
            return None;
        }
        serial += (h as f64 * 3600.0 + m as f64 * 60.0 + sec) / 86400.0;
        hint = if hint == DateHint::Date {
            DateHint::DateTime
        } else {
            DateHint::Time
        };
    }
    Some((serial, hint))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn numbers() {
        assert_eq!(
            parse_number("1,234.5"),
            Some((1234.5, NumberHint::Thousands))
        );
        assert_eq!(parse_number("50%"), Some((0.5, NumberHint::Percent)));
        assert_eq!(
            parse_number("$12.50"),
            Some((12.5, NumberHint::Currency('$')))
        );
        assert_eq!(parse_number("-$3"), Some((-3.0, NumberHint::Currency('$'))));
        assert_eq!(parse_number("1e3"), Some((1000.0, NumberHint::Plain)));
        assert_eq!(parse_number("abc"), None);
        assert_eq!(parse_number("1,23"), None);
        assert_eq!(number_text(0.1 + 0.2), "0.3");
        assert_eq!(number_text(1.0 / 3.0), "0.333333333333333");
        assert_eq!(number_text(12.0), "12");
    }

    #[test]
    fn dates() {
        assert_eq!(date_serial(2023, 3, 15), 45000.0);
        assert_eq!(serial_date(45000.0), (2023, 3, 15));
        assert_eq!(date_serial(1900, 3, 1), 61.0);
        assert_eq!(
            parse_date("2024-01-15", false).unwrap().0,
            date_serial(2024, 1, 15)
        );
        assert_eq!(
            parse_date("15/01/2024", false).unwrap().0,
            date_serial(2024, 1, 15)
        );
        assert_eq!(
            parse_date("01/15/2024", true).unwrap().0,
            date_serial(2024, 1, 15)
        );
        assert!((parse_date("12:30", false).unwrap().0 - 0.5208333).abs() < 1e-6);
        assert_eq!(weekday(45000.0), 3); // 2023-03-15 was a Wednesday
    }
}
