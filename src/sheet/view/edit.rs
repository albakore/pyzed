//! The text being typed into a cell (in the cell or in the formula bar): caret moves,
//! function suggestions, argument hints and references picked with the mouse or arrows.

use crate::sheet::addr::{Area, col_name};
use crate::sheet::formula::{self, Ref, Tok};
use crate::sheet::functions::FUNCTIONS;

/// Functions suggested first when several match what was typed.
const COMMON: &[&str] = &[
    "SUM",
    "AVERAGE",
    "COUNT",
    "COUNTA",
    "IF",
    "IFERROR",
    "VLOOKUP",
    "XLOOKUP",
    "INDEX",
    "MATCH",
    "MAX",
    "MIN",
    "SUMIF",
    "SUMIFS",
    "COUNTIF",
    "COUNTIFS",
    "AVERAGEIF",
    "ROUND",
    "CONCAT",
    "TEXT",
    "TODAY",
    "NOW",
    "DATE",
    "LEFT",
    "RIGHT",
    "MID",
    "LEN",
    "TRIM",
    "UPPER",
    "LOWER",
    "AND",
    "OR",
    "NOT",
    "ABS",
];

/// A reference being picked for a formula (with the arrows or the mouse).
#[derive(Debug, Clone)]
pub struct PointRef {
    /// Where the inserted reference is in the text (bytes).
    pub start: usize,
    pub end: usize,
    pub anchor: (u32, u32),
    pub cur: (u32, u32),
}

#[derive(Debug, Clone)]
pub struct Edit {
    pub sheet: usize,
    pub row: u32,
    pub col: u32,
    pub text: String,
    /// Caret and the other end of the text selection (bytes).
    pub cursor: usize,
    pub anchor: usize,
    /// Typing in the formula bar (instead of the cell).
    pub in_bar: bool,
    /// Started by typing over the cell: the arrows finish the edit (or pick references in a
    /// formula). F2 switches to moving the caret.
    pub enter_mode: bool,
    pub original: String,
    pub point: Option<PointRef>,
    /// The highlighted suggestion.
    pub suggest: usize,
    /// Suggestions closed with Escape (until the next character).
    pub closed: bool,
}

impl Edit {
    pub fn new(sheet: usize, row: u32, col: u32, text: String, enter_mode: bool) -> Self {
        let n = text.len();
        Edit {
            sheet,
            row,
            col,
            original: text.clone(),
            text,
            cursor: n,
            anchor: n,
            in_bar: false,
            enter_mode,
            point: None,
            suggest: 0,
            closed: false,
        }
    }

    pub fn is_formula(&self) -> bool {
        self.text.starts_with('=')
    }

    pub fn selection(&self) -> (usize, usize) {
        (self.cursor.min(self.anchor), self.cursor.max(self.anchor))
    }

    pub fn selected(&self) -> &str {
        let (a, b) = self.selection();
        &self.text[a..b]
    }

    fn delete_selection(&mut self) -> bool {
        let (a, b) = self.selection();
        if a == b {
            return false;
        }
        self.text.replace_range(a..b, "");
        self.cursor = a;
        self.anchor = a;
        true
    }

    /// Types `s` at the caret (over the selected text).
    pub fn insert(&mut self, s: &str) {
        self.delete_selection();
        self.text.insert_str(self.cursor, s);
        self.cursor += s.len();
        self.anchor = self.cursor;
        self.point = None;
        self.closed = false;
        self.suggest = 0;
    }

    pub fn backspace(&mut self, word: bool) {
        self.point = None;
        if self.delete_selection() {
            return;
        }
        let to = if word {
            word_left(&self.text, self.cursor)
        } else {
            prev(&self.text, self.cursor)
        };
        self.text.replace_range(to..self.cursor, "");
        self.cursor = to;
        self.anchor = to;
        self.suggest = 0;
    }

    pub fn delete(&mut self, word: bool) {
        self.point = None;
        if self.delete_selection() {
            return;
        }
        let to = if word {
            word_right(&self.text, self.cursor)
        } else {
            next(&self.text, self.cursor)
        };
        self.text.replace_range(self.cursor..to, "");
    }

    /// Moves the caret (keeping the selection's other end with `select`).
    pub fn move_to(&mut self, at: usize, select: bool) {
        self.cursor = at.min(self.text.len());
        if !select {
            self.anchor = self.cursor;
        }
        self.point = None;
    }

    pub fn left(&mut self, word: bool, select: bool) {
        let (a, _) = self.selection();
        let at = if !select && self.cursor != self.anchor {
            a
        } else if word {
            word_left(&self.text, self.cursor)
        } else {
            prev(&self.text, self.cursor)
        };
        self.move_to(at, select);
    }

    pub fn right(&mut self, word: bool, select: bool) {
        let (_, b) = self.selection();
        let at = if !select && self.cursor != self.anchor {
            b
        } else if word {
            word_right(&self.text, self.cursor)
        } else {
            next(&self.text, self.cursor)
        };
        self.move_to(at, select);
    }

    /// Start and end of the line the caret is on.
    pub fn line_bounds(&self) -> (usize, usize) {
        let start = self.text[..self.cursor].rfind('\n').map_or(0, |i| i + 1);
        let end = self.text[self.cursor..]
            .find('\n')
            .map_or(self.text.len(), |i| self.cursor + i);
        (start, end)
    }

    // --- Formulas ------------------------------------------------------------

    /// The caret is where a reference can go (after `=`, `(`, `,`, an operator...).
    pub fn can_point(&self) -> bool {
        if !self.is_formula() || self.cursor != self.anchor {
            return false;
        }
        if let Some(p) = &self.point
            && p.end == self.cursor
        {
            return true;
        }
        let before = self.text[..self.cursor].trim_end_matches(' ');
        let after = self.text[self.cursor..].chars().next();
        let ok_after =
            after.is_none_or(|c| !(c.is_alphanumeric() || c == '$' || c == '.' || c == '_'));
        ok_after
            && before
                .chars()
                .next_back()
                .is_some_and(|c| "=(,;+-*/^&<>:{".contains(c))
    }

    /// Puts (or moves) the picked reference `a:b` at the caret.
    pub fn set_point(&mut self, anchor: (u32, u32), cur: (u32, u32), sheet: Option<&str>) {
        let (start, end) = match &self.point {
            Some(p) => (p.start, p.end),
            None => {
                self.delete_selection();
                (self.cursor, self.cursor)
            }
        };
        let area = Area::new(anchor.0, anchor.1, cur.0, cur.1);
        let mut text = String::new();
        if let Some(name) = sheet {
            text.push_str(&crate::sheet::addr::quote_sheet(name));
            text.push('!');
        }
        text.push_str(&area.to_string());
        self.text.replace_range(start..end, &text);
        let end = start + text.len();
        self.cursor = end;
        self.anchor = end;
        self.point = Some(PointRef {
            start,
            end,
            anchor,
            cur,
        });
        self.closed = true;
    }

    /// The references in the formula, with where each one is in the text.
    pub fn refs(&self) -> Vec<(usize, usize, Ref)> {
        if !self.is_formula() {
            return Vec::new();
        }
        let Ok(tokens) = formula::lex(&self.text[1..]) else {
            return Vec::new();
        };
        tokens
            .into_iter()
            .filter_map(|t| match t.tok {
                Tok::Ref(r) => Some((t.start + 1, t.end + 1, r)),
                _ => None,
            })
            .collect()
    }

    /// F4: cycles the reference at the caret through `$A$1`, `A$1`, `$A1` and `A1`.
    pub fn toggle_absolute(&mut self) {
        let refs = self.refs();
        let Some((start, end, r)) = refs
            .into_iter()
            .find(|(s, e, _)| *s <= self.cursor && self.cursor <= *e)
        else {
            return;
        };
        let mut r = r;
        let next = match (r.abs[0], r.abs[1]) {
            (false, false) => [true, true],
            (true, true) => [true, false],
            (true, false) => [false, true],
            (false, true) => [false, false],
        };
        r.abs = [next[0], next[1], next[0], next[1]];
        let text = r.write();
        self.text.replace_range(start..end, &text);
        self.cursor = start + text.len();
        self.anchor = self.cursor;
        self.point = None;
    }

    /// The function name being typed at the caret: where it starts and what was typed.
    pub fn typed_function(&self) -> Option<(usize, String)> {
        if !self.is_formula() || self.closed || self.cursor != self.anchor {
            return None;
        }
        let before = &self.text[..self.cursor];
        let start = before
            .char_indices()
            .rev()
            .take_while(|(_, c)| c.is_ascii_alphanumeric() || *c == '.' || *c == '_')
            .last()
            .map(|(i, _)| i)?;
        let word = &before[start..];
        if !word.chars().next().is_some_and(|c| c.is_ascii_alphabetic()) {
            return None;
        }
        let prior = before[..start].trim_end_matches(' ').chars().next_back();
        if !prior.is_some_and(|c| "=(,;+-*/^&<>{".contains(c)) {
            return None;
        }
        if self.text[self.cursor..].starts_with('(') {
            return None;
        }
        // A reference (A1, AB12) being typed is not a function.
        if crate::sheet::addr::parse_cell(word).is_some()
            && word.chars().any(|c| c.is_ascii_digit())
        {
            return None;
        }
        Some((start, word.to_ascii_uppercase()))
    }

    /// Functions whose name starts with what is being typed.
    pub fn suggestions(&self) -> Vec<&'static (&'static str, &'static str, &'static str)> {
        let Some((_, word)) = self.typed_function() else {
            return Vec::new();
        };
        let mut out: Vec<_> = FUNCTIONS
            .iter()
            .filter(|f| f.0.starts_with(word.as_str()))
            .collect();
        if out.len() == 1 && out[0].0 == word {
            // Fully typed: the argument hint takes over once `(` is typed.
            return out;
        }
        // The most used functions first (SUM before SUBSTITUTE), then the shorter names.
        out.sort_by_key(|f| {
            (
                COMMON
                    .iter()
                    .position(|c| *c == f.0)
                    .unwrap_or(COMMON.len()),
                f.0.len(),
                f.0,
            )
        });
        out.truncate(8);
        out
    }

    /// Replaces the typed name with `name(`.
    pub fn accept(&mut self, name: &str) {
        if let Some((start, _)) = self.typed_function() {
            self.text
                .replace_range(start..self.cursor, &format!("{name}("));
            self.cursor = start + name.len() + 1;
            self.anchor = self.cursor;
            self.suggest = 0;
            self.point = None;
        }
    }

    /// The function call the caret is in and which of its arguments.
    pub fn current_call(&self) -> Option<(String, usize)> {
        if !self.is_formula() {
            return None;
        }
        let mut stack: Vec<(String, usize)> = Vec::new();
        let mut word_start: Option<usize> = None;
        let mut in_str = false;
        let text = &self.text[..self.cursor];
        for (i, ch) in text.char_indices() {
            if in_str {
                if ch == '"' {
                    in_str = false;
                }
                continue;
            }
            match ch {
                '"' => {
                    in_str = true;
                    word_start = None;
                }
                '(' => {
                    let name = word_start
                        .map(|s| text[s..i].to_ascii_uppercase())
                        .unwrap_or_default();
                    stack.push((name, 0));
                    word_start = None;
                }
                ')' => {
                    stack.pop();
                    word_start = None;
                }
                ',' | ';' => {
                    if let Some(top) = stack.last_mut() {
                        top.1 += 1;
                    }
                    word_start = None;
                }
                c if c.is_ascii_alphanumeric() || c == '.' || c == '_' => {
                    if word_start.is_none() {
                        word_start = Some(i);
                    }
                }
                _ => word_start = None,
            }
        }
        stack.into_iter().rev().find(|(n, _)| !n.is_empty())
    }

    /// The text to store: a formula gets its missing `)` closed, like Sheets and Excel do.
    pub fn final_text(&self) -> String {
        let mut t = self.text.clone();
        if t.starts_with('=') {
            let mut depth = 0i32;
            let mut in_str = false;
            for ch in t.chars() {
                match ch {
                    '"' => in_str = !in_str,
                    '(' if !in_str => depth += 1,
                    ')' if !in_str => depth -= 1,
                    _ => {}
                }
            }
            if in_str {
                t.push('"');
            }
            for _ in 0..depth.max(0) {
                t.push(')');
            }
        }
        t
    }
}

/// The argument hint of a function: its name, the arguments split, and its description.
pub fn hint(name: &str) -> Option<(&'static str, Vec<&'static str>, &'static str)> {
    let f = FUNCTIONS.iter().find(|f| f.0 == name)?;
    let args = if f.1.is_empty() {
        Vec::new()
    } else {
        f.1.split(", ").collect()
    };
    Some((f.0, args, f.2))
}

/// The argument to highlight for argument `i` (the last one repeats for `...`).
pub fn hint_arg(args: &[&str], i: usize) -> Option<usize> {
    if args.is_empty() {
        return None;
    }
    if i < args.len() {
        if args[i].contains("...") && i > 0 {
            Some(i - 1)
        } else {
            Some(i)
        }
    } else if args.last().is_some_and(|a| a.contains("...")) {
        Some(args.len().saturating_sub(2))
    } else {
        None
    }
}

pub fn prev(text: &str, i: usize) -> usize {
    text[..i].char_indices().next_back().map_or(0, |(j, _)| j)
}

pub fn next(text: &str, i: usize) -> usize {
    text[i..]
        .chars()
        .next()
        .map_or(text.len(), |c| i + c.len_utf8())
}

fn is_word(c: char) -> bool {
    c.is_alphanumeric() || c == '_'
}

pub fn word_left(text: &str, i: usize) -> usize {
    let mut j = i;
    let chars: Vec<(usize, char)> = text[..i].char_indices().collect();
    let mut k = chars.len();
    while k > 0 && !is_word(chars[k - 1].1) {
        k -= 1;
        j = chars[k].0;
    }
    while k > 0 && is_word(chars[k - 1].1) {
        k -= 1;
        j = chars[k].0;
    }
    j
}

pub fn word_right(text: &str, i: usize) -> usize {
    let mut j = i;
    let mut it = text[i..].char_indices().peekable();
    while let Some(&(k, c)) = it.peek() {
        if is_word(c) {
            break;
        }
        j = i + k + c.len_utf8();
        it.next();
    }
    while let Some(&(k, c)) = it.peek() {
        if !is_word(c) {
            break;
        }
        j = i + k + c.len_utf8();
        it.next();
    }
    j
}

/// A1 address of a cell.
pub fn address(r: u32, c: u32) -> String {
    format!("{}{}", col_name(c), r + 1)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn typing_and_words() {
        let mut e = Edit::new(0, 0, 0, String::new(), true);
        e.insert("=su");
        assert_eq!(e.typed_function().unwrap().1, "SU");
        assert!(e.suggestions().iter().any(|f| f.0 == "SUM"));
        e.accept("SUM");
        assert_eq!(e.text, "=SUM(");
        assert!(e.can_point());
        e.set_point((0, 0), (2, 0), None);
        assert_eq!(e.text, "=SUM(A1:A3");
        e.set_point((0, 0), (3, 1), None);
        assert_eq!(e.text, "=SUM(A1:B4");
        assert_eq!(e.current_call().unwrap(), ("SUM".to_string(), 0));
        e.insert(",");
        assert_eq!(e.current_call().unwrap().1, 1);
        assert_eq!(e.final_text(), "=SUM(A1:B4,)");
        assert_eq!(word_left("hello world", 11), 6);
        assert_eq!(word_right("hello world", 0), 5);
    }

    #[test]
    fn f4_cycles() {
        let mut e = Edit::new(0, 0, 0, "=A1+B2".into(), false);
        e.cursor = 2;
        e.anchor = 2;
        e.toggle_absolute();
        assert_eq!(e.text, "=$A$1+B2");
        e.toggle_absolute();
        assert_eq!(e.text, "=A$1+B2");
    }
}
