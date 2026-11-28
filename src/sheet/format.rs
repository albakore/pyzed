//! Number formats: the codes of Excel and Google Sheets (`#,##0.00`, `0%`, `$#,##0`,
//! `yyyy-mm-dd`, `[Red]-0.0`, `0.00E+00`, `"Total: "@`...).

use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock};

use super::value::{self, Value};

#[derive(Debug, Clone)]
enum Part {
    Lit(String),
    /// A run of digit placeholders with the decimal point, exponent...: formatted as a number.
    Number,
    Text,
    Year(usize),
    Month(usize),
    Minute(usize),
    Day(usize),
    Hour(usize),
    Second(usize),
    AmPm,
    ElapsedHours,
}

#[derive(Debug, Clone, Default)]
struct NumberSpec {
    int_min: usize,
    dec_min: usize,
    dec_max: usize,
    thousands: bool,
    percent: u32,
    scale: u32,
    /// Exponent digits (scientific notation) and whether `+` is always shown.
    exp: Option<(usize, bool)>,
}

#[derive(Debug, Clone)]
struct Section {
    color: Option<u32>,
    cond: Option<(String, f64)>,
    parts: Vec<Part>,
    number: Option<NumberSpec>,
    date: bool,
}

#[derive(Debug, Clone)]
pub struct Format {
    sections: Vec<Section>,
    general: bool,
}

fn named_color(name: &str) -> Option<u32> {
    Some(match name.to_ascii_lowercase().as_str() {
        "red" => 0xE5484DFF,
        "green" => 0x30A46CFF,
        "blue" => 0x3E63DDFF,
        "yellow" => 0xD6A000FF,
        "magenta" => 0xD6409FFF,
        "cyan" => 0x12A594FF,
        "black" => 0x000000FF,
        "white" => 0xFFFFFFFF,
        _ => return None,
    })
}

fn parse_section(code: &str) -> Section {
    let chars: Vec<char> = code.chars().collect();
    let mut parts = Vec::new();
    let mut color = None;
    let mut cond = None;
    let mut spec = NumberSpec::default();
    let mut has_number = false;
    let mut date = false;
    let mut i = 0;
    let mut lit = String::new();
    let mut in_decimals = false;
    let mut after_digits_commas = 0u32;
    let flush = |lit: &mut String, parts: &mut Vec<Part>| {
        if !lit.is_empty() {
            parts.push(Part::Lit(std::mem::take(lit)));
        }
    };
    while i < chars.len() {
        let c = chars[i];
        match c {
            '"' => {
                let mut j = i + 1;
                while j < chars.len() && chars[j] != '"' {
                    lit.push(chars[j]);
                    j += 1;
                }
                i = j + 1;
                continue;
            }
            '\\' => {
                if let Some(&n) = chars.get(i + 1) {
                    lit.push(n);
                }
                i += 2;
                continue;
            }
            '_' => {
                lit.push(' ');
                i += 2;
                continue;
            }
            '*' => {
                i += 2;
                continue;
            }
            '[' => {
                let end = chars[i..]
                    .iter()
                    .position(|&c| c == ']')
                    .map(|p| p + i)
                    .unwrap_or(chars.len());
                let inner: String = chars[i + 1..end.min(chars.len())].iter().collect();
                let lower = inner.to_ascii_lowercase();
                if let Some(c) = named_color(&inner) {
                    color = Some(c);
                } else if lower == "h" || lower == "hh" {
                    flush(&mut lit, &mut parts);
                    parts.push(Part::ElapsedHours);
                    date = true;
                } else if let Some(op) = ["<=", ">=", "<>", "<", ">", "="]
                    .iter()
                    .find(|op| inner.starts_with(**op))
                {
                    if let Ok(v) = inner[op.len()..].trim().parse::<f64>() {
                        cond = Some((op.to_string(), v));
                    }
                } else if let Some(hex) = lower.strip_prefix("color") {
                    let _ = hex;
                }
                i = end + 1;
                continue;
            }
            '0' | '#' | '?' | '.' | ',' if !date || matches!(c, '0') && has_number => {
                // A number: gather the whole placeholder run.
                if !has_number {
                    flush(&mut lit, &mut parts);
                    parts.push(Part::Number);
                    has_number = true;
                }
                match c {
                    '0' | '?' => {
                        if after_digits_commas > 0 {
                            spec.thousands = true;
                            after_digits_commas = 0;
                        }
                        if in_decimals {
                            spec.dec_min += 1;
                            spec.dec_max += 1;
                        } else {
                            spec.int_min += 1;
                        }
                    }
                    '#' => {
                        if after_digits_commas > 0 {
                            spec.thousands = true;
                            after_digits_commas = 0;
                        }
                        if in_decimals {
                            spec.dec_max += 1;
                        }
                    }
                    '.' => in_decimals = true,
                    _ => after_digits_commas += 1,
                }
                i += 1;
                continue;
            }
            '%' => {
                spec.percent += 1;
                lit.push('%');
                i += 1;
                continue;
            }
            'E' | 'e' if has_number && matches!(chars.get(i + 1), Some('+') | Some('-')) => {
                let plus = chars[i + 1] == '+';
                let mut j = i + 2;
                let mut digits = 0;
                while j < chars.len() && matches!(chars[j], '0' | '#') {
                    digits += 1;
                    j += 1;
                }
                spec.exp = Some((digits.max(1), plus));
                i = j;
                continue;
            }
            '@' => {
                flush(&mut lit, &mut parts);
                parts.push(Part::Text);
                i += 1;
                continue;
            }
            _ => {}
        }
        let lower = c.to_ascii_lowercase();
        if matches!(lower, 'y' | 'm' | 'd' | 'h' | 's') {
            let mut j = i;
            while j < chars.len() && chars[j].to_ascii_lowercase() == lower {
                j += 1;
            }
            let n = j - i;
            flush(&mut lit, &mut parts);
            date = true;
            parts.push(match lower {
                'y' => Part::Year(n),
                'm' => Part::Month(n),
                'd' => Part::Day(n),
                'h' => Part::Hour(n),
                _ => Part::Second(n),
            });
            i = j;
            continue;
        }
        if (c == 'A' || c == 'a')
            && code[code.char_indices().nth(i).map(|x| x.0).unwrap_or(0)..]
                .to_ascii_uppercase()
                .starts_with("AM/PM")
        {
            flush(&mut lit, &mut parts);
            parts.push(Part::AmPm);
            date = true;
            i += 5;
            continue;
        }
        lit.push(c);
        i += 1;
    }
    flush(&mut lit, &mut parts);
    if after_digits_commas > 0 {
        spec.scale = after_digits_commas;
    }
    // `m` next to hours or seconds means minutes.
    let n = parts.len();
    for k in 0..n {
        if let Part::Month(len) = parts[k] {
            let prev = parts[..k].iter().rev().find(|p| !matches!(p, Part::Lit(_)));
            let next = parts[k + 1..].iter().find(|p| !matches!(p, Part::Lit(_)));
            if matches!(prev, Some(Part::Hour(_) | Part::ElapsedHours))
                || matches!(next, Some(Part::Second(_)))
            {
                parts[k] = Part::Minute(len);
            }
        }
    }
    Section {
        color,
        cond,
        parts,
        number: has_number.then_some(spec),
        date,
    }
}

/// Splits on `;` outside quotes and brackets.
fn split_sections(code: &str) -> Vec<String> {
    let mut out = vec![String::new()];
    let mut quoted = false;
    let mut bracket = false;
    let mut escape = false;
    for c in code.chars() {
        if escape {
            out.last_mut().unwrap().push(c);
            escape = false;
            continue;
        }
        match c {
            '\\' => escape = true,
            '"' => quoted = !quoted,
            '[' if !quoted => bracket = true,
            ']' if !quoted => bracket = false,
            ';' if !quoted && !bracket => {
                out.push(String::new());
                continue;
            }
            _ => {}
        }
        out.last_mut().unwrap().push(c);
    }
    out
}

impl Format {
    pub fn parse(code: &str) -> Format {
        let trimmed = code.trim();
        if trimmed.is_empty() || trimmed.eq_ignore_ascii_case("general") {
            return Format {
                sections: vec![],
                general: true,
            };
        }
        let sections = split_sections(trimmed)
            .iter()
            .map(|s| parse_section(s))
            .collect();
        Format {
            sections,
            general: false,
        }
    }

    pub fn is_date(&self) -> bool {
        self.sections.first().is_some_and(|s| s.date)
    }

    /// The text of `value` in this format and the format's color (`[Red]`), if any.
    pub fn apply(&self, value: &Value) -> (String, Option<u32>) {
        match value {
            Value::Number(n) if !self.general => self.number(*n),
            Value::Text(t) if !self.general => {
                if let Some(sec) = self.sections.get(3).or_else(|| {
                    self.sections
                        .iter()
                        .find(|s| s.parts.iter().any(|p| matches!(p, Part::Text)))
                }) {
                    let mut out = String::new();
                    for p in &sec.parts {
                        match p {
                            Part::Lit(l) => out.push_str(l),
                            Part::Text => out.push_str(t),
                            _ => {}
                        }
                    }
                    (out, sec.color)
                } else {
                    (t.to_string(), None)
                }
            }
            other => (other.display(), None),
        }
    }

    fn pick(&self, n: f64) -> (&Section, f64) {
        let s = &self.sections;
        let conditional = s.iter().any(|s| s.cond.is_some());
        if conditional {
            for sec in s.iter().take(3) {
                if let Some((op, v)) = &sec.cond {
                    let ok = match op.as_str() {
                        "<" => n < *v,
                        "<=" => n <= *v,
                        ">" => n > *v,
                        ">=" => n >= *v,
                        "=" => n == *v,
                        _ => n != *v,
                    };
                    if ok {
                        return (sec, n);
                    }
                } else {
                    return (sec, n);
                }
            }
            return (&s[0], n);
        }
        match s.len() {
            0 => unreachable!(),
            1 => (&s[0], n),
            2 => {
                if n < 0.0 {
                    (&s[1], -n)
                } else {
                    (&s[0], n)
                }
            }
            _ => {
                if n < 0.0 {
                    (&s[1], -n)
                } else if n == 0.0 {
                    (&s[2], n)
                } else {
                    (&s[0], n)
                }
            }
        }
    }

    fn number(&self, n: f64) -> (String, Option<u32>) {
        let (sec, mut v) = self.pick(n);
        // With a single section negative numbers get a minus sign in front.
        let mut neg = false;
        if self.sections.len() == 1 && v < 0.0 && !sec.date {
            neg = true;
            v = -v;
        }
        let mut out = String::new();
        if sec.date {
            if v < 0.0 {
                return ("#".repeat(8), sec.color);
            }
            out = format_date(sec, v);
        } else {
            for p in &sec.parts {
                match p {
                    Part::Lit(l) => out.push_str(l),
                    Part::Number => {
                        let spec = sec.number.as_ref().unwrap();
                        out.push_str(&format_number(spec, v));
                    }
                    Part::Text => out.push_str(&value::number_text(v)),
                    _ => {}
                }
            }
            if sec.number.is_none()
                && !sec.parts.iter().any(|p| matches!(p, Part::Text))
                && sec.parts.iter().all(|p| matches!(p, Part::Lit(_)))
                && sec.parts.is_empty()
            {
                out = value::number_text(v);
            }
            if neg && out.chars().any(|c| c.is_ascii_digit() && c != '0') {
                out.insert(0, '-');
            }
        }
        (out, sec.color)
    }
}

fn group(int: &str) -> String {
    let bytes = int.as_bytes();
    let mut out = String::with_capacity(int.len() + int.len() / 3);
    for (i, b) in bytes.iter().enumerate() {
        if i > 0 && (bytes.len() - i).is_multiple_of(3) {
            out.push(',');
        }
        out.push(*b as char);
    }
    out
}

fn format_number(spec: &NumberSpec, v: f64) -> String {
    let mut v = v * 100f64.powi(spec.percent as i32) / 1000f64.powi(spec.scale as i32);
    if let Some((exp_digits, plus)) = spec.exp {
        if v == 0.0 {
            return format!(
                "{:.*}E{}{}",
                spec.dec_max,
                0.0,
                if plus { "+" } else { "" },
                "0".repeat(exp_digits)
            );
        }
        let mut e = v.abs().log10().floor() as i32;
        // One integer digit (or as many as the placeholders ask).
        let int_digits = spec.int_min.max(1) as i32;
        e -= int_digits - 1;
        let mut m = v / 10f64.powi(e);
        let rounded =
            (m * 10f64.powi(spec.dec_max as i32)).round() / 10f64.powi(spec.dec_max as i32);
        if rounded.abs() >= 10f64.powi(int_digits) {
            m = rounded / 10.0;
            e += 1;
        }
        let mant = trim_decimals(&format!("{:.*}", spec.dec_max, m), spec.dec_min);
        let sign = if e < 0 {
            "-"
        } else if plus {
            "+"
        } else {
            ""
        };
        return format!("{mant}E{sign}{:0width$}", e.abs(), width = exp_digits);
    }
    let factor = 10f64.powi(spec.dec_max as i32);
    v = (v * factor).round() / factor;
    let text = format!("{:.*}", spec.dec_max, v);
    let (int, dec) = match text.split_once('.') {
        Some((i, d)) => (i.to_string(), d.to_string()),
        None => (text.clone(), String::new()),
    };
    let mut int = int.trim_start_matches('0').to_string();
    while int.len() < spec.int_min {
        int.insert(0, '0');
    }
    let int = if spec.thousands { group(&int) } else { int };
    let mut dec = dec;
    while dec.len() > spec.dec_min && dec.ends_with('0') {
        dec.pop();
    }
    if spec.dec_max == 0 || dec.is_empty() {
        if spec.dec_max > 0 && spec.dec_min == 0 && int.is_empty() {
            return "0".into();
        }
        return int;
    }
    format!("{int}.{dec}")
}

fn trim_decimals(text: &str, min: usize) -> String {
    match text.split_once('.') {
        Some((i, d)) => {
            let mut d = d.to_string();
            while d.len() > min && d.ends_with('0') {
                d.pop();
            }
            if d.is_empty() {
                i.to_string()
            } else {
                format!("{i}.{d}")
            }
        }
        None => text.to_string(),
    }
}

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
const DAYS: [&str; 7] = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
];

fn format_date(sec: &Section, v: f64) -> String {
    let (y, mo, d) = value::serial_date(v);
    let (h, mi, s) = value::serial_time(v);
    let ampm = sec.parts.iter().any(|p| matches!(p, Part::AmPm));
    let mut out = String::new();
    for p in &sec.parts {
        match p {
            Part::Lit(l) => out.push_str(l),
            Part::Year(n) => {
                if *n <= 2 {
                    out += &format!("{:02}", y % 100)
                } else {
                    out += &format!("{y:04}")
                }
            }
            Part::Month(n) => match n {
                1 => out += &mo.to_string(),
                2 => out += &format!("{mo:02}"),
                3 => out += &MONTHS[mo as usize - 1][..3],
                5 => out += &MONTHS[mo as usize - 1][..1],
                _ => out += MONTHS[mo as usize - 1],
            },
            Part::Minute(n) => {
                if *n >= 2 {
                    out += &format!("{mi:02}")
                } else {
                    out += &mi.to_string()
                }
            }
            Part::Day(n) => match n {
                1 => out += &d.to_string(),
                2 => out += &format!("{d:02}"),
                3 => out += &DAYS[value::weekday(v) as usize][..3],
                _ => out += DAYS[value::weekday(v) as usize],
            },
            Part::Hour(n) => {
                let hh = if ampm {
                    if h % 12 == 0 { 12 } else { h % 12 }
                } else {
                    h
                };
                if *n >= 2 {
                    out += &format!("{hh:02}")
                } else {
                    out += &hh.to_string()
                }
            }
            Part::Second(n) => {
                if *n >= 2 {
                    out += &format!("{s:02}")
                } else {
                    out += &s.to_string()
                }
            }
            Part::AmPm => out += if h < 12 { "AM" } else { "PM" },
            Part::ElapsedHours => out += &((v * 24.0).floor() as i64).to_string(),
            Part::Number | Part::Text => {}
        }
    }
    out
}

/// Parsed formats, shared by every workbook (cells reuse a handful of codes).
fn cache() -> &'static Mutex<HashMap<String, Arc<Format>>> {
    static CACHE: OnceLock<Mutex<HashMap<String, Arc<Format>>>> = OnceLock::new();
    CACHE.get_or_init(Default::default)
}

pub fn get(code: &str) -> Arc<Format> {
    let mut c = cache().lock().unwrap();
    if let Some(f) = c.get(code) {
        return f.clone();
    }
    if c.len() > 4096 {
        c.clear();
    }
    let f = Arc::new(Format::parse(code));
    c.insert(code.to_string(), f.clone());
    f
}

/// Formats a value with a format code (`None` or `"General"`: as typed).
pub fn format(value: &Value, code: Option<&str>) -> (String, Option<u32>) {
    match code {
        Some(code) if !code.is_empty() => get(code).apply(value),
        _ => (value.display(), None),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn f(v: f64, code: &str) -> String {
        format(&Value::Number(v), Some(code)).0
    }

    #[test]
    fn numbers() {
        assert_eq!(f(1234.567, "#,##0.00"), "1,234.57");
        assert_eq!(f(1234.5, "0"), "1235");
        assert_eq!(f(0.256, "0.0%"), "25.6%");
        assert_eq!(f(-5.0, "0.00"), "-5.00");
        assert_eq!(f(-5.0, "0.00;(0.00)"), "(5.00)");
        assert_eq!(f(1234.5, "$#,##0.00"), "$1,234.50");
        assert_eq!(f(12345.0, "0.00E+00"), "1.23E+04");
        assert_eq!(f(0.5, "#.##"), ".5");
        assert_eq!(f(3.0, "0.##"), "3");
        assert_eq!(f(1500000.0, "#,##0,,\"M\""), "2M");
    }

    #[test]
    fn dates() {
        assert_eq!(f(45000.0, "yyyy-mm-dd"), "2023-03-15");
        assert_eq!(f(45000.0, "dd/mm/yyyy"), "15/03/2023");
        assert_eq!(f(45000.75, "hh:mm"), "18:00");
        assert_eq!(f(45000.75, "h:mm AM/PM"), "6:00 PM");
        assert_eq!(f(45000.0, "d mmm yyyy"), "15 Mar 2023");
        assert_eq!(f(45000.0, "dddd"), "Wednesday");
    }
}
