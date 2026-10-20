//! Conversions from loose Python values (strings, numbers, tuples) into iced types.

use std::collections::HashMap;
use std::sync::{LazyLock, Mutex, RwLock};

use iced::alignment::{Horizontal, Vertical};
use iced::border::Radius;
use iced::font::{Family, Weight};
use iced::{Background, Border, Color, Font, Length, Padding, Shadow, Vector};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyString, PyTuple};

pub type Any<'py> = Option<Bound<'py, PyAny>>;

pub const SANS: &str = "IBM Plex Sans";
pub const MONO: &str = "IBM Plex Mono";
pub const ICONS: &str = "lucide";

/// The families `"sans"` and `"mono"` stand for: the bundled IBM Plex ones unless `set_fonts` changed them.
static UI_FONT: RwLock<Option<&'static str>> = RwLock::new(None);
static CODE_FONT: RwLock<Option<&'static str>> = RwLock::new(None);

/// The interface font family (`"sans"`).
pub fn sans() -> &'static str {
    UI_FONT.read().unwrap().unwrap_or(SANS)
}

/// The code font family (`"mono"`).
pub fn mono() -> &'static str {
    CODE_FONT.read().unwrap().unwrap_or(MONO)
}

/// Changes the families `"sans"` and `"mono"` stand for; `None` or `""` goes back to IBM Plex.
pub fn set_fonts(ui: Option<&str>, code: Option<&str>) {
    let pick = |name: Option<&str>| name.filter(|n| !n.is_empty()).map(intern);
    *UI_FONT.write().unwrap() = pick(ui);
    *CODE_FONT.write().unwrap() = pick(code);
}

/// Whether the interface font was changed (text without a font then names it, as the window's default font
/// is fixed when the app starts).
fn custom_ui_font() -> bool {
    UI_FONT.read().unwrap().is_some()
}

/// Interns font family names so they can live in `Font` (which needs `&'static str`).
fn intern(name: &str) -> &'static str {
    static NAMES: LazyLock<Mutex<HashMap<String, &'static str>>> =
        LazyLock::new(|| Mutex::new(HashMap::new()));

    let mut names = NAMES.lock().unwrap();
    if let Some(name) = names.get(name) {
        return name;
    }
    let leaked: &'static str = Box::leak(name.to_owned().into_boxed_str());
    names.insert(name.to_owned(), leaked);
    leaked
}

pub fn color(value: &Bound<'_, PyAny>) -> PyResult<Color> {
    if let Ok(s) = value.cast::<PyString>() {
        let s = s.to_cow()?;
        let s: &str = &s;
        if s == "transparent" {
            return Ok(Color::TRANSPARENT);
        }
        return s
            .parse::<Color>()
            .map_err(|_| PyValueError::new_err(format!("invalid color: {s:?}")));
    }
    if let Ok(t) = value.cast::<PyTuple>() {
        let parts: Vec<f32> = t.extract()?;
        let scale = if parts.iter().take(3).any(|p| *p > 1.0) {
            255.0
        } else {
            1.0
        };
        return match parts.as_slice() {
            [r, g, b] => Ok(Color::from_rgb(r / scale, g / scale, b / scale)),
            [r, g, b, a] => Ok(Color::from_rgba(r / scale, g / scale, b / scale, *a)),
            _ => Err(PyValueError::new_err("color tuples need 3 or 4 components")),
        };
    }
    Err(PyTypeError::new_err(
        "colors must be '#rrggbb[aa]' strings or (r, g, b[, a]) tuples",
    ))
}

pub fn opt_color(value: &Any<'_>) -> PyResult<Option<Color>> {
    match value {
        Some(v) if !v.is_none() => color(v).map(Some),
        _ => Ok(None),
    }
}

/// `None` | number (pixels) | "fill" | "shrink" | "fill:N" (portion)
pub fn length(value: &Bound<'_, PyAny>) -> PyResult<Length> {
    if let Ok(s) = value.cast::<PyString>() {
        let s = s.to_cow()?;
        let s: &str = &s;
        return match s {
            "fill" => Ok(Length::Fill),
            "shrink" => Ok(Length::Shrink),
            _ => {
                if let Some(n) = s.strip_prefix("fill:") {
                    let n: u16 = n
                        .parse()
                        .map_err(|_| PyValueError::new_err(format!("invalid length: {s:?}")))?;
                    Ok(Length::FillPortion(n))
                } else {
                    Err(PyValueError::new_err(format!("invalid length: {s:?}")))
                }
            }
        };
    }
    let px: f32 = value.extract()?;
    Ok(Length::Fixed(px))
}

pub fn opt_length(value: &Any<'_>) -> PyResult<Option<Length>> {
    match value {
        Some(v) if !v.is_none() => length(v).map(Some),
        _ => Ok(None),
    }
}

/// number | (vertical, horizontal) | (top, right, bottom, left)
pub fn padding(value: &Bound<'_, PyAny>) -> PyResult<Padding> {
    if let Ok(t) = value.cast::<PyTuple>() {
        let parts: Vec<f32> = t.extract()?;
        return match parts.as_slice() {
            [v, h] => Ok(Padding {
                top: *v,
                bottom: *v,
                left: *h,
                right: *h,
            }),
            [t, r, b, l] => Ok(Padding {
                top: *t,
                right: *r,
                bottom: *b,
                left: *l,
            }),
            _ => Err(PyValueError::new_err("padding tuples need 2 or 4 values")),
        };
    }
    let all: f32 = value.extract()?;
    Ok(Padding::new(all))
}

pub fn opt_padding(value: &Any<'_>) -> PyResult<Option<Padding>> {
    match value {
        Some(v) if !v.is_none() => padding(v).map(Some),
        _ => Ok(None),
    }
}

/// number | (top_left, top_right, bottom_right, bottom_left)
pub fn radius(value: &Any<'_>) -> PyResult<Radius> {
    let Some(value) = value.as_ref().filter(|v| !v.is_none()) else {
        return Ok(Radius::default());
    };
    if let Ok(t) = value.cast::<PyTuple>() {
        let p: Vec<f32> = t.extract()?;
        return match p.as_slice() {
            [tl, tr, br, bl] => Ok(Radius {
                top_left: *tl,
                top_right: *tr,
                bottom_right: *br,
                bottom_left: *bl,
            }),
            _ => Err(PyValueError::new_err("radius tuples need 4 values")),
        };
    }
    let r: f32 = value.extract()?;
    Ok(Radius::from(r))
}

pub fn align_x(value: Option<&str>) -> PyResult<Option<Horizontal>> {
    Ok(match value {
        None => None,
        Some("start" | "left") => Some(Horizontal::Left),
        Some("center") => Some(Horizontal::Center),
        Some("end" | "right") => Some(Horizontal::Right),
        Some(other) => {
            return Err(PyValueError::new_err(format!(
                "invalid alignment: {other:?}"
            )));
        }
    })
}

pub fn align_y(value: Option<&str>) -> PyResult<Option<Vertical>> {
    Ok(match value {
        None => None,
        Some("start" | "top") => Some(Vertical::Top),
        Some("center") => Some(Vertical::Center),
        Some("end" | "bottom") => Some(Vertical::Bottom),
        Some(other) => {
            return Err(PyValueError::new_err(format!(
                "invalid alignment: {other:?}"
            )));
        }
    })
}

pub fn font(family: Option<&str>, weight: &Any<'_>, italic: bool) -> PyResult<Option<Font>> {
    if family.is_none() && weight.as_ref().is_none_or(|w| w.is_none()) && !italic {
        return Ok(custom_ui_font().then(|| Font::with_name(sans())));
    }
    Ok(Some(Font {
        family: self::family(family.unwrap_or("sans")),
        weight: self::weight(weight)?.unwrap_or(Weight::Normal),
        style: if italic {
            iced::font::Style::Italic
        } else {
            iced::font::Style::Normal
        },
        ..Font::DEFAULT
    }))
}

/// `"sans"`, `"mono"`, `"icons"`, `"serif"` or a loaded family name.
pub fn family(name: &str) -> Family {
    match name {
        "sans" => Family::Name(sans()),
        "mono" | "monospace" => Family::Name(mono()),
        "icons" => Family::Name(ICONS),
        "serif" => Family::Serif,
        other => Family::Name(intern(other)),
    }
}

/// `"thin"`...`"black"` or a CSS number (100-900).
pub fn weight(value: &Any<'_>) -> PyResult<Option<Weight>> {
    let Some(w) = value.as_ref().filter(|w| !w.is_none()) else {
        return Ok(None);
    };
    if let Ok(s) = w.cast::<PyString>() {
        return Ok(Some(match &*s.to_cow()? {
            "thin" => Weight::Thin,
            "light" => Weight::Light,
            "normal" | "regular" => Weight::Normal,
            "medium" => Weight::Medium,
            "semibold" => Weight::Semibold,
            "bold" => Weight::Bold,
            "black" => Weight::Black,
            other => {
                return Err(PyValueError::new_err(format!("invalid weight: {other:?}")));
            }
        }));
    }
    Ok(Some(match w.extract::<u16>()? {
        0..=150 => Weight::Thin,
        151..=350 => Weight::Light,
        351..=450 => Weight::Normal,
        451..=550 => Weight::Medium,
        551..=650 => Weight::Semibold,
        651..=850 => Weight::Bold,
        _ => Weight::Black,
    }))
}

/// Box styling shared by containers, tooltips and buttons.
#[derive(Debug, Clone, Default)]
pub struct BoxStyle {
    pub background: Option<Color>,
    pub text_color: Option<Color>,
    pub border_color: Option<Color>,
    pub border_width: f32,
    pub radius: Radius,
    pub shadow: Option<Shadow>,
    pub gradient: Option<iced::Gradient>,
}

impl BoxStyle {
    pub fn is_empty(&self) -> bool {
        self.background.is_none()
            && self.text_color.is_none()
            && self.border_color.is_none()
            && self.border_width == 0.0
            && self.radius == Radius::default()
            && self.shadow.is_none()
            && self.gradient.is_none()
    }

    pub fn border(&self) -> Border {
        Border {
            color: self.border_color.unwrap_or(Color::TRANSPARENT),
            width: self.border_width,
            radius: self.radius,
        }
    }

    pub fn container(&self) -> iced::widget::container::Style {
        iced::widget::container::Style {
            text_color: self.text_color,
            background: match self.gradient {
                Some(g) => Some(Background::Gradient(g)),
                None => self.background.map(Background::Color),
            },
            border: self.border(),
            shadow: self.shadow.unwrap_or_default(),
            ..Default::default()
        }
    }
}

/// `(color, (x, y), blur)` shadow tuples.
pub fn shadow(value: &Any<'_>) -> PyResult<Option<Shadow>> {
    let Some(value) = value.as_ref().filter(|v| !v.is_none()) else {
        return Ok(None);
    };
    let t = value.cast::<PyTuple>()?;
    if t.len() != 3 {
        return Err(PyValueError::new_err(
            "shadow must be (color, (x, y), blur)",
        ));
    }
    let (x, y): (f32, f32) = t.get_item(1)?.extract()?;
    Ok(Some(Shadow {
        color: color(&t.get_item(0)?)?,
        offset: Vector::new(x, y),
        blur_radius: t.get_item(2)?.extract()?,
    }))
}

pub fn box_style(
    bg: &Any<'_>,
    text_color: &Any<'_>,
    border_color: &Any<'_>,
    border_width: f32,
    radius_value: &Any<'_>,
    shadow_value: &Any<'_>,
) -> PyResult<BoxStyle> {
    Ok(BoxStyle {
        background: opt_color(bg)?,
        text_color: opt_color(text_color)?,
        border_color: opt_color(border_color)?,
        border_width,
        radius: radius(radius_value)?,
        shadow: shadow(shadow_value)?,
        gradient: None,
    })
}

/// `(angle_degrees, [color, ...])` or `(angle_degrees, [(offset, color), ...])`.
///
/// The angle follows CSS: 0 points up and 90 points right.
pub fn gradient(value: &Any<'_>) -> PyResult<Option<iced::Gradient>> {
    let Some(value) = value.as_ref().filter(|v| !v.is_none()) else {
        return Ok(None);
    };
    let t = value.cast::<PyTuple>().map_err(|_| {
        PyTypeError::new_err(
            "gradient must be (angle, [colors]) or (angle, [(offset, color), ...])",
        )
    })?;
    if t.len() != 2 {
        return Err(PyValueError::new_err("gradient must be (angle, stops)"));
    }
    let angle: f32 = t.get_item(0)?.extract()?;
    let stops: Vec<Bound<'_, PyAny>> = t.get_item(1)?.try_iter()?.collect::<PyResult<_>>()?;
    if stops.len() < 2 {
        return Err(PyValueError::new_err("a gradient needs at least two stops"));
    }
    let mut linear = iced::gradient::Linear::new(iced::Radians(angle.to_radians()));
    let last = (stops.len() - 1) as f32;
    for (i, stop) in stops.iter().enumerate() {
        let (offset, c) = match stop.cast::<PyTuple>() {
            Ok(pair) if pair.len() == 2 && pair.get_item(0)?.extract::<f32>().is_ok() => (
                pair.get_item(0)?.extract::<f32>()?,
                color(&pair.get_item(1)?)?,
            ),
            _ => (i as f32 / last, color(stop)?),
        };
        linear = linear.add_stop(offset.clamp(0.0, 1.0), c);
    }
    Ok(Some(iced::Gradient::Linear(linear)))
}
