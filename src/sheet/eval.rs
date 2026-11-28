//! Evaluates formulas: operators, references, implicit intersection and arrays.
//! The functions themselves are in `functions.rs`.

use std::sync::Arc;

use super::addr::Area;
use super::formula::{Expr, Ref, RefKind};
use super::value::{self, Error, Value};

/// What a formula can read: cell values and sheet names.
pub trait Grid {
    fn value(&self, sheet: usize, row: u32, col: u32) -> Value;
    fn sheet_index(&self, name: &str) -> Option<usize>;
    /// The used rows and columns of a sheet (whole-column references stop there).
    fn extent(&self, sheet: usize) -> (u32, u32);
    /// Calls `f` with every non-empty cell of `area` (in no particular order).
    fn for_each(&self, sheet: usize, area: Area, f: &mut dyn FnMut(u32, u32, &Value));
    /// Seconds east of UTC, for `NOW()` and `TODAY()`.
    fn utc_offset(&self) -> i64;
    fn sheet_name(&self, sheet: usize) -> String;
    /// Whether the cell holds a formula (`ISFORMULA`).
    fn is_formula(&self, sheet: usize, row: u32, col: u32) -> bool;
}

/// The result of an expression: a value, a reference to cells or an array of values.
#[derive(Debug, Clone)]
pub enum Val {
    V(Value),
    R(usize, Area),
    A(Arc<Vec<Vec<Value>>>),
}

impl From<Value> for Val {
    fn from(v: Value) -> Self {
        Val::V(v)
    }
}

impl From<f64> for Val {
    fn from(n: f64) -> Self {
        Val::V(num(n))
    }
}

impl From<Error> for Val {
    fn from(e: Error) -> Self {
        Val::V(Value::Error(e))
    }
}

impl From<bool> for Val {
    fn from(b: bool) -> Self {
        Val::V(Value::Bool(b))
    }
}

/// A number result, or `#NUM!` for infinities and NaN.
pub fn num(n: f64) -> Value {
    if n.is_finite() {
        Value::Number(if n == 0.0 { 0.0 } else { n })
    } else {
        Value::Error(Error::Num)
    }
}

pub struct Ctx<'a> {
    pub grid: &'a dyn Grid,
    pub sheet: usize,
    pub row: u32,
    pub col: u32,
    /// Added to relative references (conditional formatting formulas are written for the
    /// range's first cell and applied to every cell of it).
    pub shift: (i64, i64),
}

impl<'a> Ctx<'a> {
    pub fn resolve(&self, r: &Ref) -> Result<(usize, Area), Error> {
        let sheet = match &r.sheet {
            Some(name) => self.grid.sheet_index(name).ok_or(Error::Ref)?,
            None => self.sheet,
        };
        let r = if self.shift != (0, 0) {
            r.offset(self.shift.0, self.shift.1).ok_or(Error::Ref)?
        } else {
            r.clone()
        };
        let mut area = r.area;
        if matches!(r.kind, RefKind::Cols | RefKind::Rows) {
            let (rows, cols) = self.grid.extent(sheet);
            match r.kind {
                RefKind::Cols => area.r1 = area.r1.min(rows.max(1) - 1),
                _ => area.c1 = area.c1.min(cols.max(1) - 1),
            }
        }
        Ok((sheet, area))
    }

    pub fn eval(&self, e: &Expr) -> Val {
        match e {
            Expr::Number(n) => Val::V(Value::Number(*n)),
            Expr::Str(s) => Val::V(Value::Text(s.clone())),
            Expr::Bool(b) => Val::V(Value::Bool(*b)),
            Expr::Error(e) => Val::V(Value::Error(*e)),
            Expr::Missing => Val::V(Value::Empty),
            Expr::Name(_) => Val::V(Value::Error(Error::Name)),
            Expr::Ref(r) => match self.resolve(r) {
                Ok((s, a)) => Val::R(s, a),
                Err(e) => e.into(),
            },
            Expr::Neg(a) => self.map1(self.eval(a), |v| {
                v.as_number().map(|n| num(-n)).unwrap_or_else(Value::Error)
            }),
            Expr::Percent(a) => self.map1(self.eval(a), |v| {
                v.as_number()
                    .map(|n| num(n / 100.0))
                    .unwrap_or_else(Value::Error)
            }),
            Expr::Binary(op, a, b) => {
                let a = self.eval(a);
                let b = self.eval(b);
                self.map2(a, b, |x, y| binary(op, x, y))
            }
            Expr::Array(rows) => {
                let out: Vec<Vec<Value>> = rows
                    .iter()
                    .map(|r| r.iter().map(|e| self.scalar_of(self.eval(e))).collect())
                    .collect();
                Val::A(Arc::new(out))
            }
            Expr::Call(name, args) => super::functions::call(self, name, args),
        }
    }

    /// Evaluates and reduces to one value (a range gives the cell in this formula's row or
    /// column: implicit intersection).
    pub fn scalar(&self, e: &Expr) -> Value {
        let v = self.eval(e);
        self.scalar_of(v)
    }

    pub fn scalar_of(&self, v: Val) -> Value {
        match v {
            Val::V(v) => v,
            Val::A(a) => a
                .first()
                .and_then(|r| r.first())
                .cloned()
                .unwrap_or(Value::Empty),
            Val::R(sheet, a) => {
                if a.is_cell() {
                    self.grid.value(sheet, a.r0, a.c0)
                } else if a.c0 == a.c1
                    && a.r0 <= self.row
                    && self.row <= a.r1
                    && sheet == self.sheet
                {
                    self.grid.value(sheet, self.row, a.c0)
                } else if a.r0 == a.r1
                    && a.c0 <= self.col
                    && self.col <= a.c1
                    && sheet == self.sheet
                {
                    self.grid.value(sheet, a.r0, self.col)
                } else {
                    Value::Error(Error::Value)
                }
            }
        }
    }

    pub fn number(&self, e: &Expr) -> Result<f64, Error> {
        self.scalar(e).as_number()
    }

    pub fn text(&self, e: &Expr) -> Result<String, Error> {
        self.scalar(e).as_text()
    }

    pub fn boolean(&self, e: &Expr) -> Result<bool, Error> {
        self.scalar(e).as_bool()
    }

    /// The values of a result as rows (ranges are read, values become 1x1).
    pub fn matrix(&self, v: &Val) -> Arc<Vec<Vec<Value>>> {
        match v {
            Val::V(v) => Arc::new(vec![vec![v.clone()]]),
            Val::A(a) => a.clone(),
            Val::R(sheet, a) => {
                let mut out = vec![vec![Value::Empty; a.cols() as usize]; a.rows() as usize];
                if a.cells() > 4_000_000 {
                    return Arc::new(vec![vec![Value::Error(Error::Num)]]);
                }
                self.grid.for_each(*sheet, *a, &mut |r, c, v| {
                    out[(r - a.r0) as usize][(c - a.c0) as usize] = v.clone();
                });
                Arc::new(out)
            }
        }
    }

    fn map1(&self, v: Val, f: impl Fn(&Value) -> Value) -> Val {
        match v {
            Val::V(v) => Val::V(f(&v)),
            // A single cell behaves as a value (`=-B1`).
            Val::R(_, a) if a.is_cell() => Val::V(f(&self.scalar_of(v))),
            other => {
                let m = self.matrix(&other);
                Val::A(Arc::new(
                    m.iter().map(|r| r.iter().map(&f).collect()).collect(),
                ))
            }
        }
    }

    /// Applies `f` element by element, broadcasting single values and single rows/columns.
    pub fn map2(&self, a: Val, b: Val, f: impl Fn(&Value, &Value) -> Value) -> Val {
        if let (Val::V(x), Val::V(y)) = (&a, &b) {
            return Val::V(f(x, y));
        }
        // A 1x1 range behaves as a value.
        let single = |v: &Val| matches!(v, Val::R(_, a) if a.is_cell());
        if single(&a) && single(&b)
            || single(&a) && matches!(b, Val::V(_))
            || matches!(a, Val::V(_)) && single(&b)
        {
            let x = self.scalar_of(a);
            let y = self.scalar_of(b);
            return Val::V(f(&x, &y));
        }
        let ma = self.matrix(&a);
        let mb = self.matrix(&b);
        let rows = ma.len().max(mb.len());
        let cols = ma
            .first()
            .map_or(0, |r| r.len())
            .max(mb.first().map_or(0, |r| r.len()));
        let get = |m: &Vec<Vec<Value>>, r: usize, c: usize| -> Value {
            let rr = if m.len() == 1 { 0 } else { r };
            let cc = if m.first().map_or(0, |x| x.len()) == 1 {
                0
            } else {
                c
            };
            m.get(rr)
                .and_then(|x| x.get(cc))
                .cloned()
                .unwrap_or(Value::Error(Error::NA))
        };
        let out = (0..rows)
            .map(|r| {
                (0..cols)
                    .map(|c| f(&get(&ma, r, c), &get(&mb, r, c)))
                    .collect()
            })
            .collect();
        Val::A(Arc::new(out))
    }
}

pub fn binary(op: &str, a: &Value, b: &Value) -> Value {
    if let Value::Error(e) = a {
        return Value::Error(*e);
    }
    if let Value::Error(e) = b {
        return Value::Error(*e);
    }
    let arith = |f: fn(f64, f64) -> Result<f64, Error>| -> Value {
        match (a.as_number(), b.as_number()) {
            (Ok(x), Ok(y)) => match f(x, y) {
                Ok(n) => num(n),
                Err(e) => Value::Error(e),
            },
            (Err(e), _) | (_, Err(e)) => Value::Error(e),
        }
    };
    match op {
        "+" => arith(|x, y| Ok(x + y)),
        "-" => arith(|x, y| Ok(x - y)),
        "*" => arith(|x, y| Ok(x * y)),
        "/" => arith(|x, y| {
            if y == 0.0 {
                Err(Error::Div0)
            } else {
                Ok(x / y)
            }
        }),
        "^" => arith(|x, y| {
            if x == 0.0 && y == 0.0 {
                Err(Error::Num)
            } else {
                Ok(x.powf(y))
            }
        }),
        "&" => match (a.as_text(), b.as_text()) {
            (Ok(x), Ok(y)) => Value::text(x + &y),
            (Err(e), _) | (_, Err(e)) => Value::Error(e),
        },
        _ => {
            let ord = value::compare(a, b);
            use std::cmp::Ordering::*;
            Value::Bool(match op {
                "=" => ord == Equal,
                "<>" => ord != Equal,
                "<" => ord == Less,
                "<=" => ord != Greater,
                ">" => ord == Greater,
                _ => ord != Less,
            })
        }
    }
}
