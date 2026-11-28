//! A1 addresses: cells (`B3`, `$B$3`), ranges (`A1:C10`), whole columns (`A:C`) and rows (`2:5`).

/// The most rows and columns a sheet can have (the same as Excel).
pub const MAX_ROWS: u32 = 1_048_576;
pub const MAX_COLS: u32 = 16_384;

/// A rectangle of cells, inclusive on both ends (0-based).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Area {
    pub r0: u32,
    pub c0: u32,
    pub r1: u32,
    pub c1: u32,
}

impl Area {
    pub fn cell(row: u32, col: u32) -> Self {
        Self {
            r0: row,
            c0: col,
            r1: row,
            c1: col,
        }
    }

    pub fn new(r0: u32, c0: u32, r1: u32, c1: u32) -> Self {
        Self {
            r0: r0.min(r1),
            c0: c0.min(c1),
            r1: r0.max(r1),
            c1: c0.max(c1),
        }
    }

    pub fn contains(&self, row: u32, col: u32) -> bool {
        row >= self.r0 && row <= self.r1 && col >= self.c0 && col <= self.c1
    }

    pub fn intersects(&self, other: &Area) -> bool {
        self.r0 <= other.r1 && other.r0 <= self.r1 && self.c0 <= other.c1 && other.c0 <= self.c1
    }

    pub fn intersection(&self, other: &Area) -> Option<Area> {
        self.intersects(other).then(|| Area {
            r0: self.r0.max(other.r0),
            c0: self.c0.max(other.c0),
            r1: self.r1.min(other.r1),
            c1: self.c1.min(other.c1),
        })
    }

    pub fn union(&self, other: &Area) -> Area {
        Area {
            r0: self.r0.min(other.r0),
            c0: self.c0.min(other.c0),
            r1: self.r1.max(other.r1),
            c1: self.c1.max(other.c1),
        }
    }

    pub fn rows(&self) -> u32 {
        self.r1 - self.r0 + 1
    }

    pub fn cols(&self) -> u32 {
        self.c1 - self.c0 + 1
    }

    pub fn is_cell(&self) -> bool {
        self.r0 == self.r1 && self.c0 == self.c1
    }

    pub fn cells(&self) -> u64 {
        self.rows() as u64 * self.cols() as u64
    }

    /// Clamps the area to the first `rows` x `cols` cells (for whole columns and rows).
    pub fn clamp(&self, rows: u32, cols: u32) -> Option<Area> {
        if rows == 0 || cols == 0 || self.r0 >= rows || self.c0 >= cols {
            return None;
        }
        Some(Area {
            r0: self.r0,
            c0: self.c0,
            r1: self.r1.min(rows - 1),
            c1: self.c1.min(cols - 1),
        })
    }

    pub fn whole_cols(&self) -> bool {
        self.r0 == 0 && self.r1 >= MAX_ROWS - 1
    }

    pub fn whole_rows(&self) -> bool {
        self.c0 == 0 && self.c1 >= MAX_COLS - 1
    }
}

impl std::fmt::Display for Area {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        if self.whole_cols() {
            write!(f, "{}:{}", col_name(self.c0), col_name(self.c1))
        } else if self.whole_rows() {
            write!(f, "{}:{}", self.r0 + 1, self.r1 + 1)
        } else if self.is_cell() {
            write!(f, "{}{}", col_name(self.c0), self.r0 + 1)
        } else {
            write!(
                f,
                "{}{}:{}{}",
                col_name(self.c0),
                self.r0 + 1,
                col_name(self.c1),
                self.r1 + 1
            )
        }
    }
}

/// `0` → `A`, `25` → `Z`, `26` → `AA`.
pub fn col_name(mut col: u32) -> String {
    let mut out = Vec::new();
    loop {
        out.push(b'A' + (col % 26) as u8);
        if col < 26 {
            break;
        }
        col = col / 26 - 1;
    }
    out.reverse();
    String::from_utf8(out).unwrap()
}

/// `A` → `0`, `AA` → `26` (case-insensitive). `None` past `XFD`.
pub fn col_index(name: &str) -> Option<u32> {
    if name.is_empty() || name.len() > 3 {
        return None;
    }
    let mut n: u32 = 0;
    for b in name.bytes() {
        let b = b.to_ascii_uppercase();
        if !b.is_ascii_uppercase() {
            return None;
        }
        n = n * 26 + (b - b'A' + 1) as u32;
    }
    (1..=MAX_COLS).contains(&n).then(|| n - 1)
}

/// Splits `"$B$12"` into its column, row and `$` marks.
pub fn parse_cell(text: &str) -> Option<(u32, u32, bool, bool)> {
    let s = text.trim();
    let bytes = s.as_bytes();
    let mut i = 0;
    let col_abs = bytes.first() == Some(&b'$');
    if col_abs {
        i += 1;
    }
    let start = i;
    while i < bytes.len() && bytes[i].is_ascii_alphabetic() {
        i += 1;
    }
    let col = col_index(&s[start..i])?;
    let row_abs = bytes.get(i) == Some(&b'$');
    if row_abs {
        i += 1;
    }
    let digits = &s[i..];
    if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) || digits.len() > 7 {
        return None;
    }
    let row: u32 = digits.parse().ok()?;
    (1..=MAX_ROWS)
        .contains(&row)
        .then_some((row - 1, col, row_abs, col_abs))
}

/// Parses `"B3"`, `"A1:C10"`, `"A:C"` or `"2:5"` (without a sheet name).
pub fn parse_area(text: &str) -> Option<Area> {
    let s = text.trim().replace('$', "");
    if let Some((a, b)) = s.split_once(':') {
        if let (Some((r0, c0, ..)), Some((r1, c1, ..))) = (parse_cell(a), parse_cell(b)) {
            return Some(Area::new(r0, c0, r1, c1));
        }
        if let (Some(c0), Some(c1)) = (col_index(a), col_index(b)) {
            return Some(Area::new(0, c0, MAX_ROWS - 1, c1));
        }
        if let (Ok(r0), Ok(r1)) = (a.parse::<u32>(), b.parse::<u32>())
            && r0 >= 1
            && r1 >= 1
            && r0 <= MAX_ROWS
            && r1 <= MAX_ROWS
        {
            return Some(Area::new(r0 - 1, 0, r1 - 1, MAX_COLS - 1));
        }
        return None;
    }
    if let Some((r, c, ..)) = parse_cell(&s) {
        return Some(Area::cell(r, c));
    }
    if let Some(c) = col_index(&s) {
        return Some(Area::new(0, c, MAX_ROWS - 1, c));
    }
    None
}

/// Splits `"Sheet 2!A1:B3"` / `"'My sheet'!A1"` into the sheet name and the area text.
pub fn split_sheet(text: &str) -> (Option<String>, &str) {
    match text.rfind('!') {
        Some(i) => {
            let name = text[..i].trim();
            let name = name
                .strip_prefix('\'')
                .and_then(|n| n.strip_suffix('\''))
                .map(|n| n.replace("''", "'"))
                .unwrap_or_else(|| name.to_string());
            (Some(name), &text[i + 1..])
        }
        None => (None, text),
    }
}

/// A sheet name as written in a formula: quoted when it has spaces or symbols.
pub fn quote_sheet(name: &str) -> String {
    let plain = !name.is_empty()
        && name
            .chars()
            .all(|c| c.is_alphanumeric() || c == '_' || c == '.')
        && !name.chars().next().unwrap().is_ascii_digit()
        && parse_cell(name).is_none();
    if plain {
        name.to_string()
    } else {
        format!("'{}'", name.replace('\'', "''"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names() {
        assert_eq!(col_name(0), "A");
        assert_eq!(col_name(25), "Z");
        assert_eq!(col_name(26), "AA");
        assert_eq!(col_name(16383), "XFD");
        assert_eq!(col_index("xfd"), Some(16383));
        assert_eq!(col_index("XFE"), None);
        assert_eq!(parse_cell("$B$3"), Some((2, 1, true, true)));
        assert_eq!(parse_area("A1:C2").unwrap().to_string(), "A1:C2");
        assert_eq!(parse_area("B:C").unwrap().to_string(), "B:C");
        assert_eq!(parse_area("2:4").unwrap().to_string(), "2:4");
    }
}
