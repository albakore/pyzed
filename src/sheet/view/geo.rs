//! Where everything is inside the grid widget: the formula bar, the headers, the four panes
//! (frozen rows and columns stay put) and the scrollbars.

use iced::{Point, Rectangle};

use crate::sheet::addr::Area;
use crate::sheet::model::Sheet;

/// Height of the formula bar.
pub const BAR_H: f32 = 32.0;
/// Height of the column headers.
pub const HDR_H: f32 = 24.0;
/// Thickness of the scrollbars.
pub const SCROLL: f32 = 10.0;
/// Width of the name box (the address of the active cell, left of the formula).
pub const NAME_W: f32 = 96.0;
/// Width of the `fx` mark between the name box and the formula.
pub const FX_W: f32 = 30.0;

/// One of the four panes: frozen rows/columns, or the part that scrolls.
#[derive(Debug, Clone, Copy)]
pub struct Pane {
    pub clip: Rectangle,
    pub rows: (u32, u32),
    pub cols: (u32, u32),
}

#[derive(Debug, Clone, Copy)]
pub struct Geo {
    pub bounds: Rectangle,
    pub bar: Option<Rectangle>,
    pub name_box: Rectangle,
    pub input: Rectangle,
    pub corner: Rectangle,
    pub colh: Rectangle,
    pub rowh: Rectangle,
    pub grid: Rectangle,
    pub vbar: Rectangle,
    pub hbar: Rectangle,
    pub fr: u32,
    pub fc: u32,
    pub fw: f32,
    pub fh: f32,
    pub sx: f32,
    pub sy: f32,
    pub rows: u32,
    pub cols: u32,
    pub headers: bool,
}

impl Geo {
    pub fn new(bounds: Rectangle, s: &Sheet, formula_bar: bool, headers: bool) -> Self {
        let mut y = bounds.y;
        let bar = formula_bar.then(|| {
            let r = Rectangle::new(
                Point::new(bounds.x, y),
                iced::Size::new(bounds.width, BAR_H),
            );
            y += BAR_H;
            r
        });
        let bar_r = bar.unwrap_or(Rectangle::new(
            Point::new(bounds.x, bounds.y),
            iced::Size::ZERO,
        ));
        let name_box = Rectangle {
            x: bar_r.x,
            y: bar_r.y,
            width: NAME_W.min(bar_r.width),
            height: bar_r.height,
        };
        let input = Rectangle {
            x: bar_r.x + NAME_W + FX_W,
            y: bar_r.y,
            width: (bar_r.width - NAME_W - FX_W).max(0.0),
            height: bar_r.height,
        };
        let digits = (s.rows.max(1) as f32).log10().floor() + 1.0;
        let (rw, ch) = if headers {
            ((digits * 7.5 + 16.0).max(40.0), HDR_H)
        } else {
            (0.0, 0.0)
        };
        let corner = Rectangle {
            x: bounds.x,
            y,
            width: rw,
            height: ch,
        };
        let gx = bounds.x + rw;
        let gy = y + ch;
        let gw = (bounds.x + bounds.width - SCROLL - gx).max(0.0);
        let gh = (bounds.y + bounds.height - SCROLL - gy).max(0.0);
        let grid = Rectangle {
            x: gx,
            y: gy,
            width: gw,
            height: gh,
        };
        let colh = Rectangle {
            x: gx,
            y,
            width: gw,
            height: ch,
        };
        let rowh = Rectangle {
            x: bounds.x,
            y: gy,
            width: rw,
            height: gh,
        };
        let vbar = Rectangle {
            x: gx + gw,
            y: gy,
            width: SCROLL,
            height: gh,
        };
        let hbar = Rectangle {
            x: gx,
            y: gy + gh,
            width: gw,
            height: SCROLL,
        };
        let fr = s.freeze.0.min(s.rows);
        let fc = s.freeze.1.min(s.ncols);
        let fw = (s.col_axis.offset(fc) as f32).min(gw);
        let fh = (s.row_axis.offset(fr) as f32).min(gh);
        let mut g = Geo {
            bounds,
            bar,
            name_box,
            input,
            corner,
            colh,
            rowh,
            grid,
            vbar,
            hbar,
            fr,
            fc,
            fw,
            fh,
            sx: s.scroll.0,
            sy: s.scroll.1,
            rows: s.rows,
            cols: s.ncols,
            headers,
        };
        let (mx, my) = g.max_scroll(s);
        g.sx = g.sx.clamp(0.0, mx);
        g.sy = g.sy.clamp(0.0, my);
        g
    }

    /// How far the scrolling part can scroll.
    pub fn max_scroll(&self, s: &Sheet) -> (f32, f32) {
        let w = s.col_axis.offset(self.cols) as f32;
        let h = s.row_axis.offset(self.rows) as f32;
        (
            (w - self.grid.width).max(0.0),
            (h - self.grid.height).max(0.0),
        )
    }

    pub fn x_of(&self, s: &Sheet, c: u32) -> f32 {
        let o = s.col_axis.offset(c) as f32;
        if c < self.fc {
            self.grid.x + o
        } else {
            self.grid.x + o - self.sx
        }
    }

    pub fn y_of(&self, s: &Sheet, r: u32) -> f32 {
        let o = s.row_axis.offset(r) as f32;
        if r < self.fr {
            self.grid.y + o
        } else {
            self.grid.y + o - self.sy
        }
    }

    /// The column under `x` (clamped to the sheet).
    pub fn col_at(&self, s: &Sheet, x: f32) -> u32 {
        let rel = x - self.grid.x;
        if rel < self.fw && self.fc > 0 {
            s.col_axis.index_at(rel.max(0.0) as f64, self.fc)
        } else {
            s.col_axis
                .index_at((rel.max(self.fw) + self.sx) as f64, self.cols.max(1))
        }
    }

    pub fn row_at(&self, s: &Sheet, y: f32) -> u32 {
        let rel = y - self.grid.y;
        if rel < self.fh && self.fr > 0 {
            s.row_axis.index_at(rel.max(0.0) as f64, self.fr)
        } else {
            s.row_axis
                .index_at((rel.max(self.fh) + self.sy) as f64, self.rows.max(1))
        }
    }

    pub fn cell_rect(&self, s: &Sheet, r: u32, c: u32) -> Rectangle {
        Rectangle {
            x: self.x_of(s, c),
            y: self.y_of(s, r),
            width: s.col_axis.size(c),
            height: s.row_axis.size(r),
        }
    }

    pub fn area_rect(&self, s: &Sheet, a: Area) -> Rectangle {
        let x0 = self.x_of(s, a.c0);
        let y0 = self.y_of(s, a.r0);
        let x1 = self.x_of(s, a.c1) + s.col_axis.size(a.c1);
        let y1 = self.y_of(s, a.r1) + s.row_axis.size(a.r1);
        Rectangle {
            x: x0,
            y: y0,
            width: (x1 - x0).max(0.0),
            height: (y1 - y0).max(0.0),
        }
    }

    /// The visible scrolling columns (start, end exclusive).
    pub fn scroll_cols(&self, s: &Sheet) -> (u32, u32) {
        let a = s
            .col_axis
            .index_at((self.fw + self.sx) as f64, self.cols.max(1))
            .max(self.fc);
        let b = s
            .col_axis
            .index_at((self.sx + self.grid.width) as f64, self.cols.max(1))
            + 1;
        (a, b.min(self.cols).max(a))
    }

    pub fn scroll_rows(&self, s: &Sheet) -> (u32, u32) {
        let a = s
            .row_axis
            .index_at((self.fh + self.sy) as f64, self.rows.max(1))
            .max(self.fr);
        let b = s
            .row_axis
            .index_at((self.sy + self.grid.height) as f64, self.rows.max(1))
            + 1;
        (a, b.min(self.rows).max(a))
    }

    /// The panes to draw, frozen corner first.
    pub fn panes(&self, s: &Sheet) -> Vec<Pane> {
        let g = self.grid;
        let rows = self.scroll_rows(s);
        let cols = self.scroll_cols(s);
        let mut out = Vec::with_capacity(4);
        let fr = (0, self.fr);
        let fc = (0, self.fc);
        let top = Rectangle {
            x: g.x,
            y: g.y,
            width: 0.0,
            height: self.fh,
        };
        let left_w = self.fw;
        let right = Rectangle {
            x: g.x + self.fw,
            y: g.y,
            width: (g.width - self.fw).max(0.0),
            height: 0.0,
        };
        let below_y = g.y + self.fh;
        let below_h = (g.height - self.fh).max(0.0);
        // Scrolling part first, frozen parts over it.
        out.push(Pane {
            clip: Rectangle {
                x: right.x,
                y: below_y,
                width: right.width,
                height: below_h,
            },
            rows,
            cols,
        });
        if self.fc > 0 {
            out.push(Pane {
                clip: Rectangle {
                    x: g.x,
                    y: below_y,
                    width: left_w,
                    height: below_h,
                },
                rows,
                cols: fc,
            });
        }
        if self.fr > 0 {
            out.push(Pane {
                clip: Rectangle {
                    x: right.x,
                    y: top.y,
                    width: right.width,
                    height: self.fh,
                },
                rows: fr,
                cols,
            });
        }
        if self.fr > 0 && self.fc > 0 {
            out.push(Pane {
                clip: Rectangle {
                    x: g.x,
                    y: g.y,
                    width: left_w,
                    height: self.fh,
                },
                rows: fr,
                cols: fc,
            });
        }
        out
    }

    /// Scrolls (in `s.scroll`) so that cell `(r, c)` is visible.
    pub fn reveal(&mut self, s: &mut Sheet, r: u32, c: u32) {
        if c >= self.fc && c < self.cols {
            let x0 = s.col_axis.offset(c) as f32;
            let x1 = x0 + s.col_axis.size(c);
            if x0 < self.fw + self.sx {
                self.sx = x0 - self.fw;
            } else if x1 > self.sx + self.grid.width {
                self.sx = (x1 - self.grid.width).min(x0 - self.fw);
            }
        }
        if r >= self.fr && r < self.rows {
            let y0 = s.row_axis.offset(r) as f32;
            let y1 = y0 + s.row_axis.size(r);
            if y0 < self.fh + self.sy {
                self.sy = y0 - self.fh;
            } else if y1 > self.sy + self.grid.height {
                self.sy = (y1 - self.grid.height).min(y0 - self.fh);
            }
        }
        let (mx, my) = self.max_scroll(s);
        self.sx = self.sx.clamp(0.0, mx);
        self.sy = self.sy.clamp(0.0, my);
        s.scroll = (self.sx, self.sy);
    }

    /// Sets the scroll (clamped) in the geometry and the sheet.
    pub fn scroll_to(&mut self, s: &mut Sheet, sx: f32, sy: f32) {
        let (mx, my) = self.max_scroll(s);
        self.sx = sx.clamp(0.0, mx);
        self.sy = sy.clamp(0.0, my);
        s.scroll = (self.sx, self.sy);
    }

    /// The thumb of the vertical scrollbar.
    pub fn vthumb(&self, s: &Sheet) -> Option<Rectangle> {
        let total = s.row_axis.offset(self.rows) as f32;
        let view = self.grid.height;
        if total <= view + 0.5 || self.vbar.height <= 0.0 {
            return None;
        }
        let track = self.vbar.height;
        let h = (track * view / total).max(24.0).min(track);
        let (_, my) = self.max_scroll(s);
        let y = self.vbar.y + (track - h) * if my > 0.0 { self.sy / my } else { 0.0 };
        Some(Rectangle {
            x: self.vbar.x + 2.0,
            y,
            width: SCROLL - 4.0,
            height: h,
        })
    }

    pub fn hthumb(&self, s: &Sheet) -> Option<Rectangle> {
        let total = s.col_axis.offset(self.cols) as f32;
        let view = self.grid.width;
        if total <= view + 0.5 || self.hbar.width <= 0.0 {
            return None;
        }
        let track = self.hbar.width;
        let w = (track * view / total).max(24.0).min(track);
        let (mx, _) = self.max_scroll(s);
        let x = self.hbar.x + (track - w) * if mx > 0.0 { self.sx / mx } else { 0.0 };
        Some(Rectangle {
            x,
            y: self.hbar.y + 2.0,
            width: w,
            height: SCROLL - 4.0,
        })
    }

    /// The column whose right edge is under `x` in the header (to resize it).
    pub fn col_edge(&self, s: &Sheet, x: f32) -> Option<u32> {
        let c = self.col_at(s, x);
        let right = self.x_of(s, c) + s.col_axis.size(c);
        let left = self.x_of(s, c);
        if (x - right).abs() <= 4.0 {
            Some(c)
        } else if (x - left).abs() <= 4.0 && c > 0 {
            // The previous visible column.
            let mut p = c - 1;
            while p > 0 && s.col_axis.is_hidden(p) {
                p -= 1;
            }
            Some(p)
        } else {
            None
        }
    }

    pub fn row_edge(&self, s: &Sheet, y: f32) -> Option<u32> {
        let r = self.row_at(s, y);
        let bottom = self.y_of(s, r) + s.row_axis.size(r);
        let top = self.y_of(s, r);
        if (y - bottom).abs() <= 3.0 {
            Some(r)
        } else if (y - top).abs() <= 3.0 && r > 0 {
            let mut p = r - 1;
            while p > 0 && s.row_axis.is_hidden(p) {
                p -= 1;
            }
            Some(p)
        } else {
            None
        }
    }
}
