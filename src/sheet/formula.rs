//! Formulas: tokens, the expression tree and reference rewriting.
//!
//! The lexer keeps the source spans of every token, so moving a formula (copy, fill,
//! inserting rows) rewrites only its references and leaves the rest as the user typed it.

use std::sync::Arc;

use super::addr::{self, Area, MAX_COLS, MAX_ROWS};
use super::value::Error;

/// A cell or range reference as written: `B3`, `$A$1:B$9`, `Sheet2!A:A`, `3:3`.
#[derive(Debug, Clone, PartialEq)]
pub struct Ref {
    pub sheet: Option<Arc<str>>,
    pub area: Area,
    /// `$` marks: (r0, c0, r1, c1).
    pub abs: [bool; 4],
    /// `A:C` or `2:4`.
    pub kind: RefKind,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RefKind {
    Cell,
    Range,
    Cols,
    Rows,
}

impl Ref {
    /// The reference moved by `(dr, dc)` (its `$` parts stay); `None` when it falls off the sheet.
    pub fn offset(&self, dr: i64, dc: i64) -> Option<Ref> {
        let mv = |v: u32, d: i64, abs: bool, max: u32| -> Option<u32> {
            if abs {
                return Some(v);
            }
            let n = v as i64 + d;
            (n >= 0 && n < max as i64).then_some(n as u32)
        };
        let mut out = self.clone();
        match self.kind {
            RefKind::Cols => {
                out.area.c0 = mv(self.area.c0, dc, self.abs[1], MAX_COLS)?;
                out.area.c1 = mv(self.area.c1, dc, self.abs[3], MAX_COLS)?;
            }
            RefKind::Rows => {
                out.area.r0 = mv(self.area.r0, dr, self.abs[0], MAX_ROWS)?;
                out.area.r1 = mv(self.area.r1, dr, self.abs[2], MAX_ROWS)?;
            }
            _ => {
                out.area.r0 = mv(self.area.r0, dr, self.abs[0], MAX_ROWS)?;
                out.area.c0 = mv(self.area.c0, dc, self.abs[1], MAX_COLS)?;
                out.area.r1 = mv(self.area.r1, dr, self.abs[2], MAX_ROWS)?;
                out.area.c1 = mv(self.area.c1, dc, self.abs[3], MAX_COLS)?;
            }
        }
        Some(out)
    }

    pub fn write(&self) -> String {
        let mut s = String::new();
        if let Some(sheet) = &self.sheet {
            s.push_str(&addr::quote_sheet(sheet));
            s.push('!');
        }
        let d = |abs: bool| if abs { "$" } else { "" };
        let a = self.area;
        match self.kind {
            RefKind::Cell => {
                s += &format!(
                    "{}{}{}{}",
                    d(self.abs[1]),
                    addr::col_name(a.c0),
                    d(self.abs[0]),
                    a.r0 + 1
                )
            }
            RefKind::Range => {
                s += &format!(
                    "{}{}{}{}:{}{}{}{}",
                    d(self.abs[1]),
                    addr::col_name(a.c0),
                    d(self.abs[0]),
                    a.r0 + 1,
                    d(self.abs[3]),
                    addr::col_name(a.c1),
                    d(self.abs[2]),
                    a.r1 + 1
                )
            }
            RefKind::Cols => {
                s += &format!(
                    "{}{}:{}{}",
                    d(self.abs[1]),
                    addr::col_name(a.c0),
                    d(self.abs[3]),
                    addr::col_name(a.c1)
                )
            }
            RefKind::Rows => {
                s += &format!(
                    "{}{}:{}{}",
                    d(self.abs[0]),
                    a.r0 + 1,
                    d(self.abs[2]),
                    a.r1 + 1
                )
            }
        }
        s
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum Tok {
    Number(f64),
    Str(String),
    Bool(bool),
    Error(Error),
    Ref(Ref),
    /// A function name (followed by `(`) or a name.
    Ident(String),
    Op(&'static str),
    LParen,
    RParen,
    Comma,
    Semicolon,
    LBrace,
    RBrace,
    Space,
    /// A reference that no longer exists (`#REF!` written in place of a deleted cell).
    BadRef,
}

#[derive(Debug, Clone)]
pub struct Token {
    pub tok: Tok,
    pub start: usize,
    pub end: usize,
}

fn is_ident_char(c: char) -> bool {
    c.is_alphanumeric() || c == '_' || c == '.'
}

/// Splits a formula's text (without the leading `=`) into tokens.
const ERRORS: [&str; 10] = [
    "#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#N/A", "#NUM!", "#NULL!", "#CYCLE!", "#SPILL!",
    "#ERROR!",
];

pub fn lex(src: &str) -> Result<Vec<Token>, String> {
    let chars: Vec<(usize, char)> = src.char_indices().collect();
    let n = chars.len();
    let at = |i: usize| chars.get(i).map(|c| c.1);
    let pos = |i: usize| chars.get(i).map(|c| c.0).unwrap_or(src.len());
    let mut out = Vec::new();
    let mut i = 0;
    while i < n {
        let c = chars[i].1;
        let start = pos(i);
        let push = |out: &mut Vec<Token>, tok, end_i: usize| {
            out.push(Token {
                tok,
                start,
                end: pos(end_i),
            });
        };
        if c.is_whitespace() {
            let mut j = i;
            while j < n && chars[j].1.is_whitespace() {
                j += 1;
            }
            push(&mut out, Tok::Space, j);
            i = j;
            continue;
        }
        match c {
            '"' => {
                let mut s = String::new();
                let mut j = i + 1;
                loop {
                    match at(j) {
                        None => return Err("unclosed text".into()),
                        Some('"') if at(j + 1) == Some('"') => {
                            s.push('"');
                            j += 2;
                        }
                        Some('"') => {
                            j += 1;
                            break;
                        }
                        Some(ch) => {
                            s.push(ch);
                            j += 1;
                        }
                    }
                }
                push(&mut out, Tok::Str(s), j);
                i = j;
                continue;
            }
            '(' => {
                push(&mut out, Tok::LParen, i + 1);
                i += 1;
                continue;
            }
            ')' => {
                push(&mut out, Tok::RParen, i + 1);
                i += 1;
                continue;
            }
            ',' => {
                push(&mut out, Tok::Comma, i + 1);
                i += 1;
                continue;
            }
            ';' => {
                push(&mut out, Tok::Semicolon, i + 1);
                i += 1;
                continue;
            }
            '{' => {
                push(&mut out, Tok::LBrace, i + 1);
                i += 1;
                continue;
            }
            '}' => {
                push(&mut out, Tok::RBrace, i + 1);
                i += 1;
                continue;
            }
            '+' | '-' | '*' | '/' | '^' | '&' | '%' | '=' => {
                let op = match c {
                    '+' => "+",
                    '-' => "-",
                    '*' => "*",
                    '/' => "/",
                    '^' => "^",
                    '&' => "&",
                    '%' => "%",
                    _ => "=",
                };
                push(&mut out, Tok::Op(op), i + 1);
                i += 1;
                continue;
            }
            '<' | '>' => {
                let (op, len) = match (c, at(i + 1)) {
                    ('<', Some('=')) => ("<=", 2),
                    ('<', Some('>')) => ("<>", 2),
                    ('>', Some('=')) => (">=", 2),
                    ('<', _) => ("<", 1),
                    _ => (">", 1),
                };
                push(&mut out, Tok::Op(op), i + len);
                i += len;
                continue;
            }
            '#' => {
                let rest = &src[start..];
                let code = ERRORS
                    .iter()
                    .find(|code| {
                        rest.len() >= code.len() && rest[..code.len()].eq_ignore_ascii_case(code)
                    })
                    .ok_or_else(|| format!("unknown error {rest}"))?;
                let j = i + code.chars().count();
                if code.eq_ignore_ascii_case("#REF!") {
                    push(&mut out, Tok::BadRef, j);
                } else {
                    push(&mut out, Tok::Error(Error::parse(code).unwrap()), j);
                }
                i = j;
                continue;
            }
            _ => {}
        }
        // Numbers (and row ranges such as 2:5).
        if c.is_ascii_digit() || (c == '.' && at(i + 1).is_some_and(|d| d.is_ascii_digit())) {
            // A row range: digits ':' digits.
            if let Some((r, len)) = lex_ref(&chars, i, None) {
                push(&mut out, Tok::Ref(r), i + len);
                i += len;
                continue;
            }
            let mut j = i;
            while j < n && (chars[j].1.is_ascii_digit() || chars[j].1 == '.') {
                j += 1;
            }
            if j < n && (chars[j].1 == 'e' || chars[j].1 == 'E') {
                let mut k = j + 1;
                if k < n && (chars[k].1 == '+' || chars[k].1 == '-') {
                    k += 1;
                }
                if k < n && chars[k].1.is_ascii_digit() {
                    while k < n && chars[k].1.is_ascii_digit() {
                        k += 1;
                    }
                    j = k;
                }
            }
            let text = &src[start..pos(j)];
            let v: f64 = text.parse().map_err(|_| format!("bad number {text}"))?;
            push(&mut out, Tok::Number(v), j);
            i = j;
            continue;
        }
        // Quoted sheet names: 'My sheet'!A1
        if c == '\'' {
            let mut name = String::new();
            let mut j = i + 1;
            loop {
                match at(j) {
                    None => return Err("unclosed sheet name".into()),
                    Some('\'') if at(j + 1) == Some('\'') => {
                        name.push('\'');
                        j += 2;
                    }
                    Some('\'') => {
                        j += 1;
                        break;
                    }
                    Some(ch) => {
                        name.push(ch);
                        j += 1;
                    }
                }
            }
            if at(j) != Some('!') {
                return Err("expected ! after the sheet name".into());
            }
            j += 1;
            if at(j) == Some('#') {
                // 'Sheet'!#REF!
                let k = j + 5.min(n - j);
                push(&mut out, Tok::BadRef, k);
                i = k;
                continue;
            }
            let (r, len) = lex_ref(&chars, j, Some(name.into()))
                .ok_or("expected a reference after the sheet name")?;
            push(&mut out, Tok::Ref(r), j + len);
            i = j + len;
            continue;
        }
        if c.is_alphabetic() || c == '_' || c == '$' {
            // A reference, possibly after Sheet!
            if let Some((r, len)) = lex_ref(&chars, i, None) {
                // `LOG10(` is a function, not a cell.
                if at(i + len) != Some('(')
                    && at(i + len) != Some('!')
                    && !at(i + len).is_some_and(is_ident_char)
                {
                    push(&mut out, Tok::Ref(r), i + len);
                    i += len;
                    continue;
                }
            }
            let mut j = i;
            while j < n && (is_ident_char(chars[j].1) || chars[j].1 == '$') {
                j += 1;
            }
            let word: String = chars[i..j].iter().map(|c| c.1).collect();
            if at(j) == Some('!') {
                let k = j + 1;
                if at(k) == Some('#') {
                    let e = k + 5.min(n - k);
                    push(&mut out, Tok::BadRef, e);
                    i = e;
                    continue;
                }
                let (r, len) = lex_ref(&chars, k, Some(word.into()))
                    .ok_or("expected a reference after the sheet name")?;
                push(&mut out, Tok::Ref(r), k + len);
                i = k + len;
                continue;
            }
            let upper = word.to_ascii_uppercase();
            let tok = match upper.as_str() {
                "TRUE" if at(j) != Some('(') => Tok::Bool(true),
                "FALSE" if at(j) != Some('(') => Tok::Bool(false),
                _ => Tok::Ident(upper),
            };
            push(&mut out, tok, j);
            i = j;
            continue;
        }
        return Err(format!("unexpected character {c:?}"));
    }
    Ok(out)
}

/// Reads a reference starting at `chars[i]`: returns it and how many characters it took.
/// One endpoint of a reference: its column and row (each with its `$`), and where it ends.
type RefPart = (Option<(u32, bool)>, Option<(u32, bool)>, usize);

fn lex_ref(chars: &[(usize, char)], i: usize, sheet: Option<Arc<str>>) -> Option<(Ref, usize)> {
    let n = chars.len();
    let at = |k: usize| chars.get(k).map(|c| c.1);
    // One endpoint: $?LETTERS$?DIGITS, or only letters (columns), or only digits (rows).
    let part = |k0: usize| -> Option<RefPart> {
        let mut k = k0;
        let mut col = None;
        let col_abs = at(k) == Some('$');
        if col_abs {
            k += 1;
        }
        let ls = k;
        while k < n && chars[k].1.is_ascii_alphabetic() {
            k += 1;
        }
        if k > ls {
            let name: String = chars[ls..k].iter().map(|c| c.1).collect();
            col = Some((addr::col_index(&name)?, col_abs));
        } else if col_abs {
            // `$5` (a row) only makes sense in `$5:$9`.
            k = k0;
        }
        let row_abs = at(k) == Some('$');
        let ks = k;
        if row_abs {
            k += 1;
        }
        let ds = k;
        while k < n && chars[k].1.is_ascii_digit() {
            k += 1;
        }
        let mut row = None;
        if k > ds {
            let digits: String = chars[ds..k].iter().map(|c| c.1).collect();
            let r: u32 = digits.parse().ok()?;
            if r == 0 || r > MAX_ROWS {
                return None;
            }
            row = Some((r - 1, row_abs));
        } else {
            k = ks;
        }
        if col.is_none() && row.is_none() {
            return None;
        }
        Some((col, row, k - k0))
    };
    let (c0, r0, len0) = part(i)?;
    let after = i + len0;
    if at(after) == Some(':')
        && let Some((c1, r1, len1)) = part(after + 1)
    {
        let len = len0 + 1 + len1;
        let mk = |kind, area: Area, abs| {
            Some((
                Ref {
                    sheet: sheet.clone(),
                    area,
                    abs,
                    kind,
                },
                len,
            ))
        };
        match (c0, r0, c1, r1) {
            (Some(c0), Some(r0), Some(c1), Some(r1)) => {
                let area = Area::new(r0.0, c0.0, r1.0, c1.0);
                // Keep the `$` of each corner after sorting them.
                let (ra, rb) = if r0.0 <= r1.0 {
                    (r0.1, r1.1)
                } else {
                    (r1.1, r0.1)
                };
                let (ca, cb) = if c0.0 <= c1.0 {
                    (c0.1, c1.1)
                } else {
                    (c1.1, c0.1)
                };
                return mk(RefKind::Range, area, [ra, ca, rb, cb]);
            }
            (Some(c0), None, Some(c1), None) => {
                return mk(
                    RefKind::Cols,
                    Area::new(0, c0.0, MAX_ROWS - 1, c1.0),
                    [false, c0.1, false, c1.1],
                );
            }
            (None, Some(r0), None, Some(r1)) => {
                return mk(
                    RefKind::Rows,
                    Area::new(r0.0, 0, r1.0, MAX_COLS - 1),
                    [r0.1, false, r1.1, false],
                );
            }
            _ => {}
        }
    }
    match (c0, r0) {
        (Some(c), Some(r)) => Some((
            Ref {
                sheet,
                area: Area::cell(r.0, c.0),
                abs: [r.1, c.1, r.1, c.1],
                kind: RefKind::Cell,
            },
            len0,
        )),
        _ => None,
    }
}

// ---------------------------------------------------------------------------
// Expression tree
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    Number(f64),
    Str(Arc<str>),
    Bool(bool),
    Error(Error),
    Ref(Ref),
    /// An argument left empty: `IF(A1,,2)`.
    Missing,
    Neg(Box<Expr>),
    Percent(Box<Expr>),
    Binary(&'static str, Box<Expr>, Box<Expr>),
    Call(Arc<str>, Vec<Expr>),
    /// A name that is not a function (defined names, or a typo: #NAME?).
    Name(Arc<str>),
    Array(Vec<Vec<Expr>>),
}

struct Parser {
    toks: Vec<Tok>,
    i: usize,
}

impl Parser {
    fn peek(&self) -> Option<&Tok> {
        self.toks.get(self.i)
    }

    fn next(&mut self) -> Option<Tok> {
        let t = self.toks.get(self.i).cloned();
        self.i += 1;
        t
    }

    fn expr(&mut self) -> Result<Expr, String> {
        self.comparison()
    }

    fn comparison(&mut self) -> Result<Expr, String> {
        let mut lhs = self.concat()?;
        while let Some(Tok::Op(op @ ("=" | "<>" | "<" | "<=" | ">" | ">="))) = self.peek() {
            let op = *op;
            self.i += 1;
            let rhs = self.concat()?;
            lhs = Expr::Binary(op, Box::new(lhs), Box::new(rhs));
        }
        Ok(lhs)
    }

    fn concat(&mut self) -> Result<Expr, String> {
        let mut lhs = self.additive()?;
        while let Some(Tok::Op("&")) = self.peek() {
            self.i += 1;
            let rhs = self.additive()?;
            lhs = Expr::Binary("&", Box::new(lhs), Box::new(rhs));
        }
        Ok(lhs)
    }

    fn additive(&mut self) -> Result<Expr, String> {
        let mut lhs = self.term()?;
        while let Some(Tok::Op(op @ ("+" | "-"))) = self.peek() {
            let op = *op;
            self.i += 1;
            let rhs = self.term()?;
            lhs = Expr::Binary(op, Box::new(lhs), Box::new(rhs));
        }
        Ok(lhs)
    }

    fn term(&mut self) -> Result<Expr, String> {
        let mut lhs = self.power()?;
        while let Some(Tok::Op(op @ ("*" | "/"))) = self.peek() {
            let op = *op;
            self.i += 1;
            let rhs = self.power()?;
            lhs = Expr::Binary(op, Box::new(lhs), Box::new(rhs));
        }
        Ok(lhs)
    }

    fn power(&mut self) -> Result<Expr, String> {
        let mut lhs = self.unary()?;
        while let Some(Tok::Op("^")) = self.peek() {
            self.i += 1;
            let rhs = self.unary()?;
            lhs = Expr::Binary("^", Box::new(lhs), Box::new(rhs));
        }
        Ok(lhs)
    }

    fn unary(&mut self) -> Result<Expr, String> {
        match self.peek() {
            Some(Tok::Op("-")) => {
                self.i += 1;
                Ok(Expr::Neg(Box::new(self.unary()?)))
            }
            Some(Tok::Op("+")) => {
                self.i += 1;
                self.unary()
            }
            _ => self.postfix(),
        }
    }

    fn postfix(&mut self) -> Result<Expr, String> {
        let mut e = self.primary()?;
        while let Some(Tok::Op("%")) = self.peek() {
            self.i += 1;
            e = Expr::Percent(Box::new(e));
        }
        Ok(e)
    }

    fn primary(&mut self) -> Result<Expr, String> {
        match self.next() {
            Some(Tok::Number(n)) => Ok(Expr::Number(n)),
            Some(Tok::Str(s)) => Ok(Expr::Str(s.into())),
            Some(Tok::Bool(b)) => Ok(Expr::Bool(b)),
            Some(Tok::Error(e)) => Ok(Expr::Error(e)),
            Some(Tok::BadRef) => Ok(Expr::Error(Error::Ref)),
            Some(Tok::Ref(r)) => Ok(Expr::Ref(r)),
            Some(Tok::LParen) => {
                let e = self.expr()?;
                match self.next() {
                    Some(Tok::RParen) => Ok(e),
                    _ => Err("missing )".into()),
                }
            }
            Some(Tok::LBrace) => {
                let mut rows = vec![vec![]];
                loop {
                    let item = self.unary()?;
                    rows.last_mut().unwrap().push(item);
                    match self.next() {
                        Some(Tok::Comma) => {}
                        Some(Tok::Semicolon) => rows.push(vec![]),
                        Some(Tok::RBrace) => break,
                        _ => return Err("missing }".into()),
                    }
                }
                Ok(Expr::Array(rows))
            }
            Some(Tok::Ident(name)) => {
                if let Some(Tok::LParen) = self.peek() {
                    self.i += 1;
                    let mut args = Vec::new();
                    if let Some(Tok::RParen) = self.peek() {
                        self.i += 1;
                        return Ok(Expr::Call(name.into(), args));
                    }
                    loop {
                        match self.peek() {
                            Some(Tok::Comma | Tok::Semicolon) => args.push(Expr::Missing),
                            Some(Tok::RParen) => {
                                args.push(Expr::Missing);
                                self.i += 1;
                                break;
                            }
                            _ => args.push(self.expr()?),
                        }
                        match self.next() {
                            Some(Tok::Comma | Tok::Semicolon) => {
                                if let Some(Tok::RParen) = self.peek() {
                                    args.push(Expr::Missing);
                                    self.i += 1;
                                    break;
                                }
                            }
                            Some(Tok::RParen) => break,
                            _ => return Err(format!("missing ) after the arguments of {name}")),
                        }
                    }
                    Ok(Expr::Call(name.into(), args))
                } else {
                    Ok(Expr::Name(name.into()))
                }
            }
            Some(t) => Err(format!("unexpected {t:?}")),
            None => Err("the formula ends too soon".into()),
        }
    }
}

/// Parses a formula (without the leading `=`).
pub fn parse(src: &str) -> Result<Expr, String> {
    let toks: Vec<Tok> = lex(src)?
        .into_iter()
        .map(|t| t.tok)
        .filter(|t| *t != Tok::Space)
        .collect();
    if toks.is_empty() {
        return Err("empty formula".into());
    }
    let mut p = Parser { toks, i: 0 };
    let e = p.expr()?;
    if p.i < p.toks.len() {
        return Err(format!("unexpected {:?}", p.toks[p.i]));
    }
    Ok(e)
}

/// A typed formula (without `=`) the way spreadsheets show it: references, function names and
/// `TRUE`/`FALSE` in capitals (`sum(a1:b2)` becomes `SUM(A1:B2)`); text in quotes is kept.
pub fn normalize(src: &str) -> String {
    let Ok(tokens) = lex(src) else {
        return src.to_string();
    };
    let mut out = String::with_capacity(src.len());
    let mut last = 0;
    for (i, t) in tokens.iter().enumerate() {
        let new = match &t.tok {
            Tok::Ref(r) => Some(r.write()),
            Tok::Bool(b) => Some(if *b {
                "TRUE".to_string()
            } else {
                "FALSE".to_string()
            }),
            Tok::Ident(name) if matches!(tokens.get(i + 1).map(|x| &x.tok), Some(Tok::LParen)) => {
                Some(name.to_uppercase())
            }
            _ => None,
        };
        if let Some(new) = new {
            out.push_str(&src[last..t.start]);
            out.push_str(&new);
            last = t.end;
        }
    }
    out.push_str(&src[last..]);
    out
}

/// Rewrites every reference of a formula (without `=`) with `f`; `None` writes `#REF!`.
pub fn rewrite_refs(src: &str, mut f: impl FnMut(&Ref) -> Option<Ref>) -> String {
    let Ok(tokens) = lex(src) else {
        return src.to_string();
    };
    let mut out = String::with_capacity(src.len());
    let mut last = 0;
    for t in tokens {
        if let Tok::Ref(r) = &t.tok {
            out.push_str(&src[last..t.start]);
            match f(r) {
                Some(new) => out.push_str(&new.write()),
                None => {
                    if let Some(sheet) = &r.sheet {
                        out.push_str(&addr::quote_sheet(sheet));
                        out.push('!');
                    }
                    out.push_str("#REF!");
                }
            }
            last = t.end;
        }
    }
    out.push_str(&src[last..]);
    out
}

/// The references a formula reads (for the dependency graph and highlighting).
pub fn collect_refs(e: &Expr, out: &mut Vec<Ref>) {
    match e {
        Expr::Ref(r) => out.push(r.clone()),
        Expr::Neg(a) | Expr::Percent(a) => collect_refs(a, out),
        Expr::Binary(_, a, b) => {
            collect_refs(a, out);
            collect_refs(b, out);
        }
        Expr::Call(_, args) => args.iter().for_each(|a| collect_refs(a, out)),
        Expr::Array(rows) => rows.iter().flatten().for_each(|a| collect_refs(a, out)),
        _ => {}
    }
}

/// Functions whose result changes without their inputs changing.
pub fn is_volatile(e: &Expr) -> bool {
    match e {
        Expr::Call(name, args) => {
            matches!(
                &**name,
                "NOW" | "TODAY" | "RAND" | "RANDBETWEEN" | "RANDARRAY" | "INDIRECT" | "OFFSET"
            ) || args.iter().any(is_volatile)
        }
        Expr::Neg(a) | Expr::Percent(a) => is_volatile(a),
        Expr::Binary(_, a, b) => is_volatile(a) || is_volatile(b),
        Expr::Array(rows) => rows.iter().flatten().any(is_volatile),
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses() {
        assert!(parse("SUM(A1:B2, 3) * -2^2 & \"x\"").is_ok());
        assert!(parse("IF(A1>0,,1)").is_ok());
        assert!(parse("'My sheet'!A1 + Sheet2!B:B").is_ok());
        assert!(parse("LOG10(100)").is_ok());
        assert!(parse("SUM(1:3)").is_ok());
        assert!(parse("{1,2;3,4}").is_ok());
        assert!(parse("1+").is_err());
    }

    #[test]
    fn rewrites() {
        let s = rewrite_refs("A1+$B$2*SUM(C1:C3)", |r| r.offset(1, 1));
        assert_eq!(s, "B2+$B$2*SUM(D2:D4)");
        let s = rewrite_refs("A1 + 1", |_| None);
        assert_eq!(s, "#REF! + 1");
    }
}
