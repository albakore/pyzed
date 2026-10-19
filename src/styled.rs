//! `widget.style(...)`: CSS-like styling for any widget.
//!
//! Python (`pyzed.style._resolve`) merges styles, named styles and keywords into one
//! dict of plain values; this module turns it into a box (background, border, radius,
//! shadow, padding, margin, size, alignment) plus text overrides that every text inside
//! inherits.

use iced::alignment::{Horizontal, Vertical};
use iced::border::Radius;
use iced::font::{Family, Weight};
use iced::widget::container;
use iced::{Color, Element, Font, Length, Padding, Shadow};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};

use crate::app::Message;
use crate::style::{self, Any, BoxStyle, ICONS, SANS};
use crate::widget::{ButtonStyle, Kind, Layout, Widget, new};

/// The box properties a style sets (`None` keeps the widget's own value).
#[derive(Debug, Clone, Default)]
pub struct BoxOverride {
    pub background: Option<Color>,
    pub gradient: Option<iced::Gradient>,
    pub text_color: Option<Color>,
    pub border_color: Option<Color>,
    pub border_width: Option<f32>,
    pub radius: Option<Radius>,
    pub shadow: Option<Shadow>,
}

/// Text properties a style passes down to every text inside it.
#[derive(Debug, Clone, Copy, Default)]
pub struct TextStyle {
    pub color: Option<Color>,
    pub size: Option<f32>,
    pub family: Option<Family>,
    pub weight: Option<Weight>,
    pub italic: Option<bool>,
    pub line_height: Option<f32>,
}

impl TextStyle {
    pub fn is_empty(&self) -> bool {
        self.color.is_none()
            && self.size.is_none()
            && self.family.is_none()
            && self.weight.is_none()
            && self.italic.is_none()
            && self.line_height.is_none()
    }

    /// `self` with the properties `inner` sets replacing ours (the closest style wins).
    pub fn merged(self, inner: &TextStyle) -> TextStyle {
        TextStyle {
            color: inner.color.or(self.color),
            size: inner.size.or(self.size),
            family: inner.family.or(self.family),
            weight: inner.weight.or(self.weight),
            italic: inner.italic.or(self.italic),
            line_height: inner.line_height.or(self.line_height),
        }
    }

    /// The font a text ends up with: `self` overrides, `defaults` fill in a text without
    /// its own font. Icons keep their family (and weight).
    pub fn font(&self, own: Option<Font>, defaults: &TextStyle) -> Option<Font> {
        let own = match own {
            Some(font) => Some(font),
            None => defaults.overlay(None),
        };
        self.overlay(own)
    }

    fn overlay(&self, own: Option<Font>) -> Option<Font> {
        if self.family.is_none() && self.weight.is_none() && self.italic.is_none() {
            return own;
        }
        let base = own.unwrap_or(Font::with_name(SANS));
        if base.family == Family::Name(ICONS) {
            return own;
        }
        Some(Font {
            family: self.family.unwrap_or(base.family),
            weight: self.weight.unwrap_or(base.weight),
            style: match self.italic {
                Some(true) => iced::font::Style::Italic,
                Some(false) => iced::font::Style::Normal,
                None => base.style,
            },
            ..base
        })
    }

    /// The size a text ends up with. Icons keep theirs.
    pub fn size(&self, own: Option<f32>, font: Option<Font>, defaults: &TextStyle) -> Option<f32> {
        if font.is_some_and(|f| f.family == Family::Name(ICONS)) {
            return own;
        }
        self.size.or(own).or(defaults.size)
    }
}

pub struct StyleProps {
    pub child: Py<Widget>,
    /// The resolved properties, kept so a later `style()` call merges with them.
    pub source: Py<PyDict>,
    pub boxed: BoxOverride,
    pub text: TextStyle,
    pub padding: Option<Padding>,
    pub margin: Option<Padding>,
    pub width: Option<Length>,
    pub height: Option<Length>,
    pub max_width: Option<f32>,
    pub max_height: Option<f32>,
    pub align_x: Option<Horizontal>,
    pub align_y: Option<Vertical>,
    pub clip: bool,
    /// The text properties only fill in what texts don't set themselves (`App.style`).
    pub defaults: bool,
    /// `opacity`, `translate` and `scale`: drawn by an `Animated` around the element.
    pub effects: Option<crate::animation::Base>,
}

pub fn apply(
    slf: &Bound<'_, Widget>,
    styles: &Bound<'_, PyTuple>,
    defaults: bool,
    props: Option<&Bound<'_, PyDict>>,
) -> PyResult<Py<Widget>> {
    let py = slf.py();
    let (child, previous) = match &slf.get().kind {
        Kind::Styled(p) => (p.child.clone_ref(py), Some(p.source.clone_ref(py))),
        _ => (slf.clone().unbind(), None),
    };
    let (source, resolved): (Bound<'_, PyDict>, Bound<'_, PyDict>) = py
        .import("pyzed.style")?
        .getattr("_resolve")?
        .call1((previous, styles.clone(), props.cloned()))?
        .extract()?;
    let mut props = parse(child, source.unbind(), &resolved)?;
    props.defaults = defaults;
    new(py, Kind::Styled(Box::new(props)))
}

fn parse(child: Py<Widget>, source: Py<PyDict>, d: &Bound<'_, PyDict>) -> PyResult<StyleProps> {
    let get = |key: &str| -> PyResult<Any<'_>> { Ok(d.get_item(key)?.filter(|v| !v.is_none())) };
    let str_of = |key: &str| -> PyResult<Option<String>> {
        get(key)?.map(|v| v.extract::<String>()).transpose()
    };
    let f32_of =
        |key: &str| -> PyResult<Option<f32>> { get(key)?.map(|v| v.extract::<f32>()).transpose() };
    let radius = get("radius")?;
    let boxed = BoxOverride {
        background: style::opt_color(&get("background")?)?,
        text_color: style::opt_color(&get("color")?)?,
        border_color: style::opt_color(&get("border_color")?)?,
        border_width: f32_of("border_width")?,
        radius: if radius.is_some() {
            Some(style::radius(&radius)?)
        } else {
            None
        },
        shadow: style::shadow(&get("shadow")?)?,
        gradient: style::gradient(&get("gradient")?)?,
    };
    let text = TextStyle {
        color: boxed.text_color,
        size: f32_of("size")?,
        family: str_of("font")?.map(|f| style::family(&f)),
        weight: style::weight(&get("weight")?)?,
        italic: get("italic")?.map(|v| v.extract::<bool>()).transpose()?,
        line_height: f32_of("line_height")?,
    };
    Ok(StyleProps {
        child,
        source,
        boxed,
        text,
        padding: style::opt_padding(&get("padding")?)?,
        margin: style::opt_padding(&get("margin")?)?,
        width: style::opt_length(&get("width")?)?,
        height: style::opt_length(&get("height")?)?,
        max_width: f32_of("max_width")?,
        max_height: f32_of("max_height")?,
        align_x: style::align_x(str_of("align_x")?.as_deref())?,
        align_y: style::align_y(str_of("align_y")?.as_deref())?,
        clip: get("clip")?
            .map(|v| v.extract::<bool>())
            .transpose()?
            .unwrap_or(false),
        defaults: false,
        effects: effects(d)?,
    })
}

fn effects(d: &Bound<'_, PyDict>) -> PyResult<Option<crate::animation::Base>> {
    use crate::animation::{Base, Value};
    let get = |key: &str| -> PyResult<Any<'_>> { Ok(d.get_item(key)?.filter(|v| !v.is_none())) };
    let opacity = get("opacity")?.map(|v| v.extract::<f32>()).transpose()?;
    let scale = get("scale")?.map(|v| v.extract::<f32>()).transpose()?;
    let translate = get("translate")?;
    let float =
        |key: &str| -> PyResult<Option<f32>> { get(key)?.map(|v| v.extract::<f32>()).transpose() };
    let rotate = float("rotate")?;
    let blur = float("blur")?;
    let backdrop_blur = float("backdrop_blur")?;
    let bloom = get("bloom_light")?
        .map(|v| v.extract::<(Bound<'_, PyAny>, f32)>())
        .transpose()?;
    if opacity.is_none()
        && scale.is_none()
        && translate.is_none()
        && rotate.is_none()
        && blur.is_none()
        && backdrop_blur.is_none()
        && bloom.is_none()
    {
        return Ok(None);
    }
    let mut base = Base {
        opacity: opacity.unwrap_or(1.0).clamp(0.0, 1.0),
        scale: scale.unwrap_or(1.0).max(0.0),
        rotate: rotate.unwrap_or(0.0),
        blur: blur.unwrap_or(0.0).max(0.0),
        backdrop_blur: backdrop_blur.unwrap_or(0.0).max(0.0),
        ..Base::default()
    };
    if let Some((color, intensity)) = bloom {
        let tint = if color.is_none() {
            None
        } else {
            Some(style::color(&color)?)
        };
        base.bloom = Some((tint, intensity.clamp(0.0, 1.0)));
    }
    if let Some(r) = get("radius")? {
        let r = style::radius(&Some(r))?;
        base.radius = [r.top_left, r.top_right, r.bottom_right, r.bottom_left];
    }
    if let Some(t) = translate {
        let (x, y): (Bound<'_, PyAny>, Bound<'_, PyAny>) = t.extract()?;
        let value = |v: &Bound<'_, PyAny>| -> PyResult<Value> {
            match v.extract::<(String, f32)>() {
                Ok((_, p)) => Ok(Value::Pct(p)),
                Err(_) => Ok(Value::Num(v.extract()?)),
            }
        };
        base.x = value(&x)?;
        base.y = value(&y)?;
    }
    Ok(Some(base))
}

/// The element with a style's `opacity`, `translate` and `scale` applied.
pub fn effects_of<'a>(element: Element<'a, Message>, props: &StyleProps) -> Element<'a, Message> {
    match props.effects {
        Some(base) => crate::animation::Animated::new(
            element,
            std::sync::Arc::new(crate::animation::Spec {
                base,
                ..Default::default()
            }),
        )
        .into(),
        None => element,
    }
}

/// A container's or button's layout with a style's size and padding on top.
pub fn layout(own: &Layout, over: Option<&StyleProps>) -> Layout {
    let Some(o) = over else {
        return own.clone();
    };
    Layout {
        width: o.width.or(own.width),
        height: o.height.or(own.height),
        padding: o.padding.or(own.padding),
        max_width: o.max_width.or(own.max_width),
        max_height: o.max_height.or(own.max_height),
    }
}

/// A box style with a style's properties on top.
pub fn boxed(own: &BoxStyle, over: Option<&StyleProps>) -> BoxStyle {
    let Some(o) = over.map(|o| &o.boxed) else {
        return own.clone();
    };
    let replaces_background = o.background.is_some() || o.gradient.is_some();
    BoxStyle {
        background: if replaces_background {
            o.background
        } else {
            own.background
        },
        gradient: if replaces_background {
            o.gradient
        } else {
            own.gradient
        },
        text_color: o.text_color.or(own.text_color),
        border_color: o.border_color.or(own.border_color),
        border_width: o.border_width.unwrap_or(own.border_width),
        radius: o.radius.unwrap_or(own.radius),
        shadow: o.shadow.or(own.shadow),
    }
}

/// A button style with a style's properties on top. A new background or text color also
/// replaces the hover ones, so the button keeps the color it was given.
pub fn button(own: ButtonStyle, over: &StyleProps) -> ButtonStyle {
    let o = &over.boxed;
    let replaces_background = o.background.is_some() || o.gradient.is_some();
    ButtonStyle {
        base: boxed(&own.base, Some(over)),
        hover_background: if replaces_background {
            None
        } else {
            own.hover_background
        },
        pressed_background: if replaces_background {
            None
        } else {
            own.pressed_background
        },
        hover_text_color: o.text_color.or(own.hover_text_color),
        hover_border_color: o.border_color.or(own.hover_border_color),
        disabled_text_color: own.disabled_text_color,
    }
}

/// Any other widget: a container around it carries the style.
pub fn wrap<'a>(element: Element<'a, Message>, props: &StyleProps) -> Element<'a, Message> {
    let mut c = container(element).clip(props.clip);
    if let Some(w) = props.width {
        c = c.width(w);
    }
    if let Some(h) = props.height {
        c = c.height(h);
    }
    if let Some(p) = props.padding {
        c = c.padding(p);
    }
    if let Some(m) = props.max_width {
        c = c.max_width(m);
    }
    if let Some(m) = props.max_height {
        c = c.max_height(m);
    }
    if let Some(a) = props.align_x {
        c = c.align_x(a);
    }
    if let Some(a) = props.align_y {
        c = c.align_y(a);
    }
    let style = boxed(&BoxStyle::default(), Some(props)).container();
    c.style(move |theme| crate::animation::container_style(style, theme))
        .into()
}

/// The margin: space around the styled box, which keeps the box's fill sizes.
pub fn margin<'a>(element: Element<'a, Message>, props: &StyleProps) -> Element<'a, Message> {
    let Some(m) = props.margin else {
        return element;
    };
    let mut outer = container(element).padding(m);
    if let Some(w) = props.width.filter(|w| !matches!(w, Length::Fixed(_))) {
        outer = outer.width(w);
    }
    if let Some(h) = props.height.filter(|h| !matches!(h, Length::Fixed(_))) {
        outer = outer.height(h);
    }
    outer.into()
}
