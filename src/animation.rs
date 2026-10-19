//! Animations and visual effects: keyframe animations, CSS-like transitions, presence
//! (content that animates in and out when it changes) and the paint effects they drive.
//!
//! Python compiles `widget.animate(...)` and `widget.transition(...)` into plain data
//! (`pyzed.animation._compile`); this module plays it. Everything runs natively: an
//! `Animated` wrapper keeps its timeline in the widget tree and asks for redraws while it
//! moves, so an animation never calls back into Python per frame.
//!
//! - Transforms (`x`, `y`, `scale`) use the renderer's transformations.
//! - `opacity` multiplies a thread-local alpha that every style closure of the render
//!   (containers, buttons, inputs, texts...) applies with [`fade`] while the child draws.
//! - Box paints (`background`, `border_color`, `color`, `radius`, `border_width`, `glow`,
//!   `glow_color`) go to the first box drawn inside (the element's own container or
//!   button), which mixes them with its own values ([`container_style`], [`button_style`]).

use std::cell::{Cell, RefCell};
use std::hash::{Hash, Hasher};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Instant;

use iced::advanced::layout::{self, Layout};
use iced::advanced::renderer;
use iced::advanced::widget::{self, Tree, Widget};
use iced::advanced::{Clipboard, Shell, mouse, overlay};
use iced::border::Radius;
use iced::widget::{button, container};
use iced::{
    Background, Border, Color, Element, Event, Length, Rectangle, Shadow, Size, Theme,
    Transformation, Vector, window,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyString, PyTuple};

use crate::app::Message;
use crate::widget::PyMsg;

// ---------------------------------------------------------------------------
// Global switches
// ---------------------------------------------------------------------------

/// Animations jump to their resting state (`pz.set_reduced_motion(True)`).
static REDUCED_MOTION: AtomicBool = AtomicBool::new(false);
/// Off-screen screenshots draw the resting state, so they don't depend on timing.
static SCREENSHOT: AtomicBool = AtomicBool::new(false);

fn settled() -> bool {
    REDUCED_MOTION.load(Ordering::Relaxed) || SCREENSHOT.load(Ordering::Relaxed)
}

pub fn set_screenshot(on: bool) {
    SCREENSHOT.store(on, Ordering::Relaxed);
}

/// Turns reduced motion on or off: animations show their final state without moving.
#[pyfunction]
pub fn set_reduced_motion(on: bool) {
    REDUCED_MOTION.store(on, Ordering::Relaxed);
}

/// `easing` (a name, ``("cubic_bezier", x1, y1, x2, y2)`` or ``("steps", n)``) at `t` (0 to 1).
#[pyfunction]
pub fn ease(easing: &Bound<'_, PyAny>, t: f32) -> PyResult<f32> {
    Ok(Easing::parse(easing)?.apply(t))
}

/// Whether reduced motion is on.
#[pyfunction]
pub fn reduced_motion() -> bool {
    REDUCED_MOTION.load(Ordering::Relaxed)
}

thread_local! {
    /// The opacity of the `Animated` ancestors being drawn (multiplied).
    static OPACITY: Cell<f32> = const { Cell::new(1.0) };
    /// Box paints waiting for the next container or button drawn.
    static PAINT: RefCell<Option<Paint>> = const { RefCell::new(None) };
}

/// The current opacity multiplier (1 outside animated or translucent widgets).
pub fn opacity() -> f32 {
    OPACITY.with(Cell::get)
}

/// `color` with the current opacity applied.
pub fn fade(color: Color) -> Color {
    let o = opacity();
    if o >= 1.0 {
        color
    } else {
        color.scale_alpha(o)
    }
}

pub fn fade_background(background: Background) -> Background {
    let o = opacity();
    if o >= 1.0 {
        background
    } else {
        background.scale_alpha(o)
    }
}

fn fade_border(border: Border) -> Border {
    Border {
        color: fade(border.color),
        ..border
    }
}

fn fade_shadow(shadow: Shadow) -> Shadow {
    Shadow {
        color: fade(shadow.color),
        ..shadow
    }
}

/// A container style with the pending box paint and the current opacity applied. Every
/// container style closure of the render goes through it.
pub fn container_style(mut style: container::Style, theme: &Theme) -> container::Style {
    if let Some(paint) = take_paint() {
        let mut text = style.text_color;
        paint.apply(
            &mut style.background,
            &mut text,
            &mut style.border,
            &mut style.shadow,
            theme,
        );
        style.text_color = text;
    }
    container::Style {
        text_color: style.text_color.map(fade),
        background: style.background.map(fade_background),
        border: fade_border(style.border),
        shadow: fade_shadow(style.shadow),
        snap: style.snap,
    }
}

/// A button style with the pending box paint and the current opacity applied.
pub fn button_style(mut style: button::Style, theme: &Theme) -> button::Style {
    if let Some(paint) = take_paint() {
        let mut text = Some(style.text_color);
        paint.apply(
            &mut style.background,
            &mut text,
            &mut style.border,
            &mut style.shadow,
            theme,
        );
        style.text_color = text.unwrap_or(style.text_color);
    }
    button::Style {
        background: style.background.map(fade_background),
        text_color: fade(style.text_color),
        border: fade_border(style.border),
        shadow: fade_shadow(style.shadow),
        snap: style.snap,
    }
}

// Opacity for the other built-in widgets' styles (their colors are baked in at draw time).

pub fn fade_text_input(s: iced::widget::text_input::Style) -> iced::widget::text_input::Style {
    iced::widget::text_input::Style {
        background: fade_background(s.background),
        border: fade_border(s.border),
        icon: fade(s.icon),
        placeholder: fade(s.placeholder),
        value: fade(s.value),
        selection: fade(s.selection),
    }
}

pub fn fade_checkbox(s: iced::widget::checkbox::Style) -> iced::widget::checkbox::Style {
    iced::widget::checkbox::Style {
        background: fade_background(s.background),
        icon_color: fade(s.icon_color),
        border: fade_border(s.border),
        text_color: s.text_color.map(fade),
    }
}

pub fn fade_toggler(mut s: iced::widget::toggler::Style) -> iced::widget::toggler::Style {
    s.background = fade_background(s.background);
    s.background_border_color = fade(s.background_border_color);
    s.foreground = fade_background(s.foreground);
    s.foreground_border_color = fade(s.foreground_border_color);
    s.text_color = s.text_color.map(fade);
    s
}

pub fn fade_slider(mut s: iced::widget::slider::Style) -> iced::widget::slider::Style {
    s.rail.backgrounds = (
        fade_background(s.rail.backgrounds.0),
        fade_background(s.rail.backgrounds.1),
    );
    s.rail.border = fade_border(s.rail.border);
    s.handle.background = fade_background(s.handle.background);
    s.handle.border_color = fade(s.handle.border_color);
    s
}

pub fn fade_progress(s: iced::widget::progress_bar::Style) -> iced::widget::progress_bar::Style {
    iced::widget::progress_bar::Style {
        background: fade_background(s.background),
        bar: fade_background(s.bar),
        border: fade_border(s.border),
    }
}

pub fn fade_rule(mut s: iced::widget::rule::Style) -> iced::widget::rule::Style {
    s.color = fade(s.color);
    s
}

pub fn fade_scrollable(mut s: iced::widget::scrollable::Style) -> iced::widget::scrollable::Style {
    for rail in [&mut s.vertical_rail, &mut s.horizontal_rail] {
        rail.background = rail.background.map(fade_background);
        rail.border = fade_border(rail.border);
        rail.scroller.background = fade_background(rail.scroller.background);
        rail.scroller.border = fade_border(rail.scroller.border);
    }
    s.container.background = s.container.background.map(fade_background);
    s.container.text_color = s.container.text_color.map(fade);
    s
}

pub fn fade_pick_list(mut s: iced::widget::pick_list::Style) -> iced::widget::pick_list::Style {
    s.text_color = fade(s.text_color);
    s.placeholder_color = fade(s.placeholder_color);
    s.handle_color = fade(s.handle_color);
    s.background = fade_background(s.background);
    s.border = fade_border(s.border);
    s
}

pub fn fade_radio(mut s: iced::widget::radio::Style) -> iced::widget::radio::Style {
    s.background = fade_background(s.background);
    s.dot_color = fade(s.dot_color);
    s.border_color = fade(s.border_color);
    s.text_color = s.text_color.map(fade);
    s
}

fn take_paint() -> Option<Paint> {
    PAINT.with(|p| p.borrow_mut().take())
}

// ---------------------------------------------------------------------------
// Values, properties and easings
// ---------------------------------------------------------------------------

/// A keyframe value. `Base` is the element's own value (the style's, or the identity for
/// transforms), so `animate(on="hover", scale=1.05)` goes from whatever it was.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Value {
    Base,
    Num(f32),
    /// A fraction of the element's own width (for `x`) or height (for `y`).
    Pct(f32),
    Color(Color),
}

impl Value {
    fn parse(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        if value.is_none() {
            return Ok(Value::Base);
        }
        if let Ok(s) = value.cast::<PyString>() {
            return crate::style::color(s.as_any()).map(Value::Color);
        }
        if let Ok(t) = value.cast::<PyTuple>()
            && t.len() == 2
            && t.get_item(0)?.extract::<String>().is_ok_and(|k| k == "pct")
        {
            return Ok(Value::Pct(t.get_item(1)?.extract()?));
        }
        Ok(Value::Num(value.extract()?))
    }

    fn hash_into(&self, h: &mut impl Hasher) {
        match self {
            Value::Base => 0u8.hash(h),
            Value::Num(n) => (1u8, n.to_bits()).hash(h),
            Value::Pct(n) => (2u8, n.to_bits()).hash(h),
            Value::Color(c) => (3u8, c.into_rgba8()).hash(h),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Prop {
    Opacity,
    X,
    Y,
    Scale,
    Background,
    BorderColor,
    Color,
    Radius,
    BorderWidth,
    Glow,
    GlowColor,
}

impl Prop {
    fn parse(name: &str) -> PyResult<Self> {
        Ok(match name {
            "opacity" => Prop::Opacity,
            "x" => Prop::X,
            "y" => Prop::Y,
            "scale" => Prop::Scale,
            "background" => Prop::Background,
            "border_color" => Prop::BorderColor,
            "color" => Prop::Color,
            "radius" => Prop::Radius,
            "border_width" => Prop::BorderWidth,
            "glow" => Prop::Glow,
            "glow_color" => Prop::GlowColor,
            _ => {
                return Err(PyValueError::new_err(format!(
                    "unknown animated property {name:?}"
                )));
            }
        })
    }

    fn is_paint(self) -> bool {
        !matches!(self, Prop::Opacity | Prop::X | Prop::Y | Prop::Scale)
    }
}

/// A timing function, like CSS `animation-timing-function`.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Easing {
    Linear,
    Bezier(f32, f32, f32, f32),
    Steps(u32),
    Named(Curve),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Curve {
    InSine,
    OutSine,
    InOutSine,
    InQuad,
    OutQuad,
    InOutQuad,
    InCubic,
    OutCubic,
    InOutCubic,
    InQuart,
    OutQuart,
    InOutQuart,
    InExpo,
    OutExpo,
    InOutExpo,
    InCirc,
    OutCirc,
    InOutCirc,
    InBack,
    OutBack,
    InOutBack,
    InElastic,
    OutElastic,
    InBounce,
    OutBounce,
    Spring,
}

/// The easing names Python accepts (besides `cubic_bezier` and `steps`).
pub const EASINGS: &[&str] = &[
    "linear",
    "ease",
    "ease_in",
    "ease_out",
    "ease_in_out",
    "ease_in_sine",
    "ease_out_sine",
    "ease_in_out_sine",
    "ease_in_quad",
    "ease_out_quad",
    "ease_in_out_quad",
    "ease_in_cubic",
    "ease_out_cubic",
    "ease_in_out_cubic",
    "ease_in_quart",
    "ease_out_quart",
    "ease_in_out_quart",
    "ease_in_expo",
    "ease_out_expo",
    "ease_in_out_expo",
    "ease_in_circ",
    "ease_out_circ",
    "ease_in_out_circ",
    "ease_in_back",
    "ease_out_back",
    "ease_in_out_back",
    "ease_in_elastic",
    "ease_out_elastic",
    "ease_in_bounce",
    "ease_out_bounce",
    "spring",
];

impl Easing {
    pub fn parse(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        if value.is_none() {
            return Ok(Easing::Bezier(0.25, 0.1, 0.25, 1.0));
        }
        if let Ok(t) = value.cast::<PyTuple>() {
            let kind: String = t.get_item(0)?.extract()?;
            return match kind.as_str() {
                "cubic_bezier" => {
                    let (_, a, b, c, d): (String, f32, f32, f32, f32) = t.extract()?;
                    Ok(Easing::Bezier(a.clamp(0.0, 1.0), b, c.clamp(0.0, 1.0), d))
                }
                "steps" => {
                    let (_, n): (String, u32) = t.extract()?;
                    Ok(Easing::Steps(n.max(1)))
                }
                _ => Err(PyValueError::new_err(format!("unknown easing {kind:?}"))),
            };
        }
        let name: String = value.extract()?;
        use Curve::*;
        Ok(match name.as_str() {
            "linear" => Easing::Linear,
            "ease" => Easing::Bezier(0.25, 0.1, 0.25, 1.0),
            "ease_in" => Easing::Bezier(0.42, 0.0, 1.0, 1.0),
            "ease_out" => Easing::Bezier(0.0, 0.0, 0.58, 1.0),
            "ease_in_out" => Easing::Bezier(0.42, 0.0, 0.58, 1.0),
            other => Easing::Named(match other {
                "ease_in_sine" => InSine,
                "ease_out_sine" => OutSine,
                "ease_in_out_sine" => InOutSine,
                "ease_in_quad" => InQuad,
                "ease_out_quad" => OutQuad,
                "ease_in_out_quad" => InOutQuad,
                "ease_in_cubic" => InCubic,
                "ease_out_cubic" => OutCubic,
                "ease_in_out_cubic" => InOutCubic,
                "ease_in_quart" => InQuart,
                "ease_out_quart" => OutQuart,
                "ease_in_out_quart" => InOutQuart,
                "ease_in_expo" => InExpo,
                "ease_out_expo" => OutExpo,
                "ease_in_out_expo" => InOutExpo,
                "ease_in_circ" => InCirc,
                "ease_out_circ" => OutCirc,
                "ease_in_out_circ" => InOutCirc,
                "ease_in_back" => InBack,
                "ease_out_back" => OutBack,
                "ease_in_out_back" => InOutBack,
                "ease_in_elastic" => InElastic,
                "ease_out_elastic" => OutElastic,
                "ease_in_bounce" => InBounce,
                "ease_out_bounce" => OutBounce,
                "spring" => Spring,
                _ => {
                    return Err(PyValueError::new_err(format!(
                        "unknown easing {name:?}; available: {}, cubic_bezier and steps",
                        EASINGS.join(", ")
                    )));
                }
            }),
        })
    }

    /// Eases `t` (0 to 1). Some curves overshoot outside 0..1 on purpose (back, elastic, spring).
    pub fn apply(self, t: f32) -> f32 {
        let t = t.clamp(0.0, 1.0);
        match self {
            Easing::Linear => t,
            Easing::Steps(n) => ((t * n as f32).floor() / n as f32).min(1.0),
            Easing::Bezier(x1, y1, x2, y2) => bezier(x1, y1, x2, y2, t),
            Easing::Named(curve) => curve.apply(t),
        }
    }

    fn hash_into(&self, h: &mut impl Hasher) {
        match self {
            Easing::Linear => 0u8.hash(h),
            Easing::Bezier(a, b, c, d) => {
                (1u8, a.to_bits(), b.to_bits(), c.to_bits(), d.to_bits()).hash(h)
            }
            Easing::Steps(n) => (2u8, *n).hash(h),
            Easing::Named(c) => (3u8, *c).hash(h),
        }
    }
}

impl Curve {
    fn apply(self, t: f32) -> f32 {
        use Curve::*;
        use std::f32::consts::PI;
        const C1: f32 = 1.70158;
        const C2: f32 = C1 * 1.525;
        const C3: f32 = C1 + 1.0;
        if t <= 0.0 || t >= 1.0 {
            return t;
        }
        match self {
            InSine => 1.0 - (t * PI / 2.0).cos(),
            OutSine => (t * PI / 2.0).sin(),
            InOutSine => -((PI * t).cos() - 1.0) / 2.0,
            InQuad => t * t,
            OutQuad => 1.0 - (1.0 - t) * (1.0 - t),
            InOutQuad => {
                if t < 0.5 {
                    2.0 * t * t
                } else {
                    1.0 - (-2.0 * t + 2.0).powi(2) / 2.0
                }
            }
            InCubic => t.powi(3),
            OutCubic => 1.0 - (1.0 - t).powi(3),
            InOutCubic => {
                if t < 0.5 {
                    4.0 * t.powi(3)
                } else {
                    1.0 - (-2.0 * t + 2.0).powi(3) / 2.0
                }
            }
            InQuart => t.powi(4),
            OutQuart => 1.0 - (1.0 - t).powi(4),
            InOutQuart => {
                if t < 0.5 {
                    8.0 * t.powi(4)
                } else {
                    1.0 - (-2.0 * t + 2.0).powi(4) / 2.0
                }
            }
            InExpo => 2f32.powf(10.0 * t - 10.0),
            OutExpo => 1.0 - 2f32.powf(-10.0 * t),
            InOutExpo => {
                if t < 0.5 {
                    2f32.powf(20.0 * t - 10.0) / 2.0
                } else {
                    (2.0 - 2f32.powf(-20.0 * t + 10.0)) / 2.0
                }
            }
            InCirc => 1.0 - (1.0 - t * t).sqrt(),
            OutCirc => (1.0 - (t - 1.0).powi(2)).sqrt(),
            InOutCirc => {
                if t < 0.5 {
                    (1.0 - (1.0 - (2.0 * t).powi(2)).sqrt()) / 2.0
                } else {
                    ((1.0 - (-2.0 * t + 2.0).powi(2)).sqrt() + 1.0) / 2.0
                }
            }
            InBack => C3 * t.powi(3) - C1 * t * t,
            OutBack => 1.0 + C3 * (t - 1.0).powi(3) + C1 * (t - 1.0).powi(2),
            InOutBack => {
                if t < 0.5 {
                    ((2.0 * t).powi(2) * ((C2 + 1.0) * 2.0 * t - C2)) / 2.0
                } else {
                    ((2.0 * t - 2.0).powi(2) * ((C2 + 1.0) * (t * 2.0 - 2.0) + C2) + 2.0) / 2.0
                }
            }
            InElastic => {
                let c4 = (2.0 * PI) / 3.0;
                -(2f32.powf(10.0 * t - 10.0)) * ((t * 10.0 - 10.75) * c4).sin()
            }
            OutElastic => {
                let c4 = (2.0 * PI) / 3.0;
                2f32.powf(-10.0 * t) * ((t * 10.0 - 0.75) * c4).sin() + 1.0
            }
            InBounce => 1.0 - bounce_out(1.0 - t),
            OutBounce => bounce_out(t),
            Spring => 1.0 - (-6.0 * t).exp() * (12.0 * t).cos(),
        }
    }
}

fn bounce_out(t: f32) -> f32 {
    const N1: f32 = 7.5625;
    const D1: f32 = 2.75;
    if t < 1.0 / D1 {
        N1 * t * t
    } else if t < 2.0 / D1 {
        let t = t - 1.5 / D1;
        N1 * t * t + 0.75
    } else if t < 2.5 / D1 {
        let t = t - 2.25 / D1;
        N1 * t * t + 0.9375
    } else {
        let t = t - 2.625 / D1;
        N1 * t * t + 0.984375
    }
}

/// CSS `cubic-bezier(x1, y1, x2, y2)` at `x` (solved with Newton steps, then bisection).
fn bezier(x1: f32, y1: f32, x2: f32, y2: f32, x: f32) -> f32 {
    let curve = |a: f32, b: f32, t: f32| {
        let u = 1.0 - t;
        3.0 * u * u * t * a + 3.0 * u * t * t * b + t * t * t
    };
    let slope = |a: f32, b: f32, t: f32| {
        let u = 1.0 - t;
        3.0 * u * u * a + 6.0 * u * t * (b - a) + 3.0 * t * t * (1.0 - b)
    };
    let mut t = x;
    for _ in 0..8 {
        let err = curve(x1, x2, t) - x;
        if err.abs() < 1e-5 {
            return curve(y1, y2, t);
        }
        let d = slope(x1, x2, t);
        if d.abs() < 1e-6 {
            break;
        }
        t -= err / d;
    }
    let (mut lo, mut hi) = (0.0f32, 1.0f32);
    t = x;
    for _ in 0..30 {
        let v = curve(x1, x2, t);
        if (v - x).abs() < 1e-5 {
            break;
        }
        if v < x {
            lo = t;
        } else {
            hi = t;
        }
        t = (lo + hi) / 2.0;
    }
    curve(y1, y2, t)
}

fn lerp(a: f32, b: f32, t: f32) -> f32 {
    a + (b - a) * t
}

fn mix(a: Color, b: Color, t: f32) -> Color {
    Color {
        r: lerp(a.r, b.r, t),
        g: lerp(a.g, b.g, t),
        b: lerp(a.b, b.b, t),
        a: lerp(a.a, b.a, t),
    }
}

// ---------------------------------------------------------------------------
// Animation specs (parsed from `pyzed.animation._compile`)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Trigger {
    /// Plays when the element appears (and again when its `key` changes).
    Mount,
    /// Plays forward while the pointer is over the element, backward when it leaves.
    Hover,
    /// Plays forward while the element is pressed.
    Press,
    /// Plays forward while the element has focus (clicked, until a click elsewhere).
    Focus,
    /// Plays from the start on every click.
    Click,
    /// Plays forward while `active=True`.
    Active,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Direction {
    Normal,
    Reverse,
    Alternate,
    AlternateReverse,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Fill {
    None,
    Forwards,
    Backwards,
    Both,
}

#[derive(Debug, Clone)]
struct Keyframe {
    offset: f32,
    value: Value,
    /// The easing from this keyframe to the next (the animation's when `None`).
    easing: Option<Easing>,
}

#[derive(Debug, Clone)]
struct Track {
    prop: Prop,
    frames: Vec<Keyframe>,
}

/// One `animate(...)` call.
#[derive(Debug, Clone)]
pub struct Anim {
    trigger: Trigger,
    key: Option<String>,
    active: bool,
    duration: f32,
    delay: f32,
    iterations: f32,
    direction: Direction,
    fill: Fill,
    easing: Easing,
    tracks: Vec<Track>,
    on_start: Option<PyMsg>,
    on_end: Option<PyMsg>,
    /// Hash of everything but `key`, `active` and callbacks: a new spec restarts the run.
    signature: u64,
}

impl Anim {
    pub fn parse(d: &Bound<'_, PyDict>) -> PyResult<Self> {
        let get = |k: &str| -> PyResult<Option<Bound<'_, PyAny>>> {
            Ok(d.get_item(k)?.filter(|v| !v.is_none()))
        };
        let string = |k: &str, default: &str| -> PyResult<String> {
            Ok(get(k)?
                .map(|v| v.extract::<String>())
                .transpose()?
                .unwrap_or_else(|| default.to_owned()))
        };
        let number = |k: &str, default: f32| -> PyResult<f32> {
            Ok(get(k)?
                .map(|v| v.extract::<f32>())
                .transpose()?
                .unwrap_or(default))
        };
        let trigger = match string("trigger", "mount")?.as_str() {
            "mount" => Trigger::Mount,
            "hover" => Trigger::Hover,
            "press" => Trigger::Press,
            "focus" => Trigger::Focus,
            "click" => Trigger::Click,
            "active" => Trigger::Active,
            other => {
                return Err(PyValueError::new_err(format!(
                    "unknown animation trigger {other:?}"
                )));
            }
        };
        let direction = match string("direction", "normal")?.as_str() {
            "normal" => Direction::Normal,
            "reverse" => Direction::Reverse,
            "alternate" => Direction::Alternate,
            "alternate_reverse" => Direction::AlternateReverse,
            other => {
                return Err(PyValueError::new_err(format!(
                    "unknown animation direction {other:?}"
                )));
            }
        };
        let fill = match string("fill", "both")?.as_str() {
            "none" => Fill::None,
            "forwards" => Fill::Forwards,
            "backwards" => Fill::Backwards,
            "both" => Fill::Both,
            other => {
                return Err(PyValueError::new_err(format!(
                    "unknown animation fill {other:?}"
                )));
            }
        };
        let easing = match get("easing")? {
            Some(e) => Easing::parse(&e)?,
            None => Easing::parse(&py_none(d.py()))?,
        };
        let mut tracks = Vec::new();
        if let Some(list) = get("tracks")? {
            for item in list.cast::<PyList>()?.iter() {
                let (prop, frames): (String, Bound<'_, PyList>) = item.extract()?;
                let mut out = Vec::new();
                for frame in frames.iter() {
                    let frame = frame.cast::<PyTuple>()?;
                    let offset: f32 = frame.get_item(0)?.extract()?;
                    let value = Value::parse(&frame.get_item(1)?)?;
                    let easing = match frame.len() > 2 {
                        true => {
                            let e = frame.get_item(2)?;
                            if e.is_none() {
                                None
                            } else {
                                Some(Easing::parse(&e)?)
                            }
                        }
                        false => None,
                    };
                    out.push(Keyframe {
                        offset: offset.clamp(0.0, 1.0),
                        value,
                        easing,
                    });
                }
                out.sort_by(|a, b| a.offset.total_cmp(&b.offset));
                if !out.is_empty() {
                    tracks.push(Track {
                        prop: Prop::parse(&prop)?,
                        frames: out,
                    });
                }
            }
        }
        let iterations = match get("iterations")? {
            Some(v) => {
                let n: f32 = v.extract()?;
                if n.is_nan() || n <= 0.0 { 1.0 } else { n }
            }
            None => 1.0,
        };
        let mut anim = Anim {
            trigger,
            key: get("key")?
                .map(|v| v.str().map(|s| s.to_string()))
                .transpose()?,
            active: get("active")?
                .map(|v| v.is_truthy())
                .transpose()?
                .unwrap_or(false),
            duration: (number("duration", 300.0)? / 1000.0).max(0.0),
            delay: (number("delay", 0.0)? / 1000.0).max(0.0),
            iterations,
            direction,
            fill,
            easing,
            tracks,
            on_start: get("on_start")?.map(|v| PyMsg::new(&v)),
            on_end: get("on_end")?.map(|v| PyMsg::new(&v)),
            signature: 0,
        };
        anim.signature = anim.compute_signature(0);
        Ok(anim)
    }

    fn compute_signature(&self, salt: u64) -> u64 {
        let mut h = std::collections::hash_map::DefaultHasher::new();
        salt.hash(&mut h);
        (self.trigger as u8).hash(&mut h);
        self.duration.to_bits().hash(&mut h);
        self.delay.to_bits().hash(&mut h);
        self.iterations.to_bits().hash(&mut h);
        (self.direction as u8, self.fill as u8).hash(&mut h);
        self.easing.hash_into(&mut h);
        for track in &self.tracks {
            track.prop.hash(&mut h);
            for f in &track.frames {
                f.offset.to_bits().hash(&mut h);
                f.value.hash_into(&mut h);
                if let Some(e) = f.easing {
                    e.hash_into(&mut h);
                }
            }
        }
        h.finish()
    }

    /// The same animation, restarted whenever `salt` changes (presence keys, window state).
    pub fn salted(mut self, salt: &str) -> Self {
        let mut h = std::collections::hash_map::DefaultHasher::new();
        salt.hash(&mut h);
        self.signature = self.compute_signature(h.finish());
        self
    }

    /// Seconds from the start until the animation ends (infinite when it repeats forever).
    pub fn total(&self) -> f32 {
        self.delay + self.duration * self.iterations
    }

    fn state_based(&self) -> bool {
        matches!(
            self.trigger,
            Trigger::Hover | Trigger::Press | Trigger::Focus | Trigger::Active
        )
    }

    fn looping(&self) -> bool {
        self.iterations > 1.0
    }

    /// The keyframe position (0 to 1) of iteration `index` at `fraction` of it.
    fn directed(&self, index: f32, fraction: f32) -> f32 {
        let odd = (index as u64) % 2 == 1;
        match self.direction {
            Direction::Normal => fraction,
            Direction::Reverse => 1.0 - fraction,
            Direction::Alternate => {
                if odd {
                    1.0 - fraction
                } else {
                    fraction
                }
            }
            Direction::AlternateReverse => {
                if odd {
                    fraction
                } else {
                    1.0 - fraction
                }
            }
        }
    }

    /// Where a time-based run is `elapsed` seconds after it started: the keyframe position,
    /// or `None` when the animation doesn't apply (before the delay or after the end with
    /// no fill). The flag says whether the run is over.
    fn at_time(&self, elapsed: f32) -> (Option<f32>, bool) {
        let local = elapsed - self.delay;
        if local < 0.0 {
            let fills = matches!(self.fill, Fill::Backwards | Fill::Both);
            return (fills.then(|| self.directed(0.0, 0.0)), false);
        }
        let total = self.duration * self.iterations;
        if self.duration <= 0.0 || (self.iterations.is_finite() && local >= total) {
            if !matches!(self.fill, Fill::Forwards | Fill::Both) {
                return (None, true);
            }
            let iterations = if self.iterations.is_finite() {
                self.iterations
            } else {
                1.0
            };
            let last = (iterations.ceil() - 1.0).max(0.0);
            let fraction = iterations - last;
            return (Some(self.directed(last, fraction)), true);
        }
        let index = (local / self.duration).floor();
        let fraction = (local - index * self.duration) / self.duration;
        (Some(self.directed(index, fraction)), false)
    }

    /// A track's value at keyframe position `p`, as the two keyframes around it and how far
    /// (eased) we are between them.
    fn sample(&self, track: &Track, p: f32) -> (Value, Value, f32) {
        let frames = &track.frames;
        let first = &frames[0];
        if frames.len() == 1 || p <= first.offset {
            // An implicit `Base` keyframe at 0 when the first one starts later.
            if p < first.offset && first.offset > 0.0 {
                let t = p / first.offset;
                return (Value::Base, first.value, self.easing.apply(t));
            }
            return (first.value, first.value, 0.0);
        }
        for pair in frames.windows(2) {
            let (a, b) = (&pair[0], &pair[1]);
            if p <= b.offset {
                let span = b.offset - a.offset;
                let t = if span <= 0.0 {
                    1.0
                } else {
                    (p - a.offset) / span
                };
                let easing = a.easing.unwrap_or(self.easing);
                return (a.value, b.value, easing.apply(t));
            }
        }
        let last = frames.last().unwrap();
        if last.offset < 1.0 {
            let t = (p - last.offset) / (1.0 - last.offset);
            return (last.value, Value::Base, self.easing.apply(t));
        }
        (last.value, last.value, 0.0)
    }
}

fn py_none(py: Python<'_>) -> Bound<'_, PyAny> {
    py.None().into_bound(py)
}

/// One property of `transition(...)`: animates to `value` whenever it changes.
#[derive(Debug, Clone)]
pub struct TransitionSpec {
    prop: Prop,
    value: Value,
    duration: f32,
    delay: f32,
    easing: Easing,
}

impl TransitionSpec {
    pub fn same_prop(&self, other: &TransitionSpec) -> bool {
        self.prop == other.prop
    }

    pub fn parse(d: &Bound<'_, PyDict>) -> PyResult<Self> {
        let item = |k: &str| d.get_item(k).ok().flatten().filter(|v| !v.is_none());
        let prop: String = d
            .get_item("prop")?
            .ok_or_else(|| PyValueError::new_err("transition without a property"))?
            .extract()?;
        Ok(Self {
            prop: Prop::parse(&prop)?,
            value: match item("value") {
                Some(v) => Value::parse(&v)?,
                None => Value::Base,
            },
            duration: item("duration")
                .map(|v| v.extract::<f32>())
                .transpose()?
                .unwrap_or(200.0)
                .max(0.0)
                / 1000.0,
            delay: item("delay")
                .map(|v| v.extract::<f32>())
                .transpose()?
                .unwrap_or(0.0)
                .max(0.0)
                / 1000.0,
            easing: match item("easing") {
                Some(e) => Easing::parse(&e)?,
                None => Easing::parse(&py_none(d.py()))?,
            },
        })
    }
}

/// Values set without animating (`style(opacity=..., translate=..., scale=...)`).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Base {
    pub opacity: f32,
    pub x: Value,
    pub y: Value,
    pub scale: f32,
}

impl Default for Base {
    fn default() -> Self {
        Self {
            opacity: 1.0,
            x: Value::Num(0.0),
            y: Value::Num(0.0),
            scale: 1.0,
        }
    }
}

/// Everything an `Animated` node carries (shared with the elements built from it).
#[derive(Debug, Clone, Default)]
pub struct Spec {
    pub anims: Vec<Anim>,
    pub transitions: Vec<TransitionSpec>,
    pub base: Base,
}

impl Spec {
    pub fn has_paint(&self) -> bool {
        self.anims
            .iter()
            .any(|a| a.tracks.iter().any(|t| t.prop.is_paint()))
            || self.transitions.iter().any(|t| t.prop.is_paint())
    }

    /// The longest finite time any of the animations runs (for exit animations).
    pub fn longest(&self) -> f32 {
        self.anims
            .iter()
            .map(Anim::total)
            .filter(|t| t.is_finite())
            .fold(0.0, f32::max)
    }
}

/// Parses the dicts `pyzed.animation._compile` returns.
pub fn parse_anims(list: &Bound<'_, PyAny>) -> PyResult<Vec<Anim>> {
    let mut out = Vec::new();
    for item in list.try_iter()? {
        out.push(Anim::parse(item?.cast::<PyDict>()?)?);
    }
    Ok(out)
}

pub fn parse_transitions(list: &Bound<'_, PyAny>) -> PyResult<Vec<TransitionSpec>> {
    let mut out = Vec::new();
    for item in list.try_iter()? {
        out.push(TransitionSpec::parse(item?.cast::<PyDict>()?)?);
    }
    Ok(out)
}

// ---------------------------------------------------------------------------
// Paint: box properties handed to the first container or button drawn
// ---------------------------------------------------------------------------

/// A value between `a` and `b` (`None` = the box's own value), weighted by `w` over the
/// box's own value (looping state animations blend in and out with it).
#[derive(Debug, Clone, Copy)]
struct Mix<T> {
    a: Option<T>,
    b: Option<T>,
    t: f32,
    w: f32,
}

impl Mix<Color> {
    fn resolve(&self, own: Option<Color>) -> Color {
        // A box without that color fades in from the same color, fully transparent.
        let own = own
            .or(self.b.or(self.a).map(|c| Color { a: 0.0, ..c }))
            .unwrap_or(Color::TRANSPARENT);
        let value = mix(self.a.unwrap_or(own), self.b.unwrap_or(own), self.t);
        mix(own, value, self.w)
    }
}

impl Mix<f32> {
    fn resolve(&self, own: f32) -> f32 {
        let value = lerp(self.a.unwrap_or(own), self.b.unwrap_or(own), self.t);
        lerp(own, value, self.w)
    }
}

#[derive(Debug, Clone, Copy, Default)]
pub struct Paint {
    background: Option<Mix<Color>>,
    border_color: Option<Mix<Color>>,
    text_color: Option<Mix<Color>>,
    radius: Option<Mix<f32>>,
    border_width: Option<Mix<f32>>,
    glow: Option<Mix<f32>>,
    glow_color: Option<Mix<Color>>,
}

impl Paint {
    fn is_empty(&self) -> bool {
        self.background.is_none()
            && self.border_color.is_none()
            && self.text_color.is_none()
            && self.radius.is_none()
            && self.border_width.is_none()
            && self.glow.is_none()
            && self.glow_color.is_none()
    }

    fn set(&mut self, prop: Prop, a: Value, b: Value, t: f32, w: f32) {
        let color = |v: Value| match v {
            Value::Color(c) => Some(c),
            _ => None,
        };
        let number = |v: Value| match v {
            Value::Num(n) | Value::Pct(n) => Some(n),
            _ => None,
        };
        let c = Mix {
            a: color(a),
            b: color(b),
            t,
            w,
        };
        let n = Mix {
            a: number(a),
            b: number(b),
            t,
            w,
        };
        match prop {
            Prop::Background => self.background = Some(c),
            Prop::BorderColor => self.border_color = Some(c),
            Prop::Color => self.text_color = Some(c),
            Prop::GlowColor => self.glow_color = Some(c),
            Prop::Radius => self.radius = Some(n),
            Prop::BorderWidth => self.border_width = Some(n),
            Prop::Glow => self.glow = Some(n),
            Prop::Opacity | Prop::X | Prop::Y | Prop::Scale => {}
        }
    }

    fn apply(
        &self,
        background: &mut Option<Background>,
        text: &mut Option<Color>,
        border: &mut Border,
        shadow: &mut Shadow,
        theme: &Theme,
    ) {
        if let Some(m) = self.background {
            let own = match background {
                Some(Background::Color(c)) => Some(*c),
                _ => None,
            };
            *background = Some(Background::Color(m.resolve(own)));
        }
        if let Some(m) = self.text_color {
            *text = Some(m.resolve(*text));
        }
        if let Some(m) = self.border_color {
            let own = (border.width > 0.0).then_some(border.color);
            border.color = m.resolve(own);
            if border.width <= 0.0 && self.border_width.is_none() {
                border.width = 1.0;
            }
        }
        if let Some(m) = self.border_width {
            border.width = m.resolve(border.width).max(0.0);
        }
        if let Some(m) = self.radius {
            let r = border.radius;
            let corner = |own: f32| m.resolve(own).max(0.0);
            border.radius = Radius {
                top_left: corner(r.top_left),
                top_right: corner(r.top_right),
                bottom_right: corner(r.bottom_right),
                bottom_left: corner(r.bottom_left),
            };
        }
        if self.glow.is_some() || self.glow_color.is_some() {
            let accent = theme.extended_palette().primary.base.color;
            let own_glow = (shadow.offset == Vector::ZERO).then_some(shadow.blur_radius);
            let blur = self
                .glow
                .map(|m| m.resolve(own_glow.unwrap_or(0.0)))
                .unwrap_or(shadow.blur_radius)
                .max(0.0);
            let own_color = (shadow.color.a > 0.0).then_some(shadow.color);
            let color = match self.glow_color {
                Some(m) => m.resolve(own_color),
                None => own_color.unwrap_or(Color { a: 0.8, ..accent }),
            };
            *shadow = Shadow {
                color,
                offset: Vector::ZERO,
                blur_radius: blur,
            };
        }
    }
}

// ---------------------------------------------------------------------------
// The `Animated` widget
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Default)]
struct Run {
    signature: u64,
    key: Option<String>,
    /// When a time-based run (or a looping state run) started.
    start: Option<Instant>,
    /// Waiting for the next frame to start.
    pending: bool,
    /// Keyframe position of a single-iteration state run (moves toward 0 or 1).
    progress: f32,
    /// How much a looping state run shows (blends in and out).
    weight: f32,
    started: bool,
    ended: bool,
    was_on: bool,
}

#[derive(Debug, Clone)]
struct TransitionState {
    prop: Prop,
    from: Value,
    to: Value,
    start: Option<Instant>,
    pending: bool,
    duration: f32,
    delay: f32,
    easing: Easing,
}

#[derive(Debug, Default)]
struct State {
    now: Option<Instant>,
    last: Option<Instant>,
    hovered: bool,
    pressed: bool,
    focused: bool,
    runs: Vec<Run>,
    transitions: Vec<TransitionState>,
    /// The element's last size (resolves `%` values when a transition starts).
    size: Size,
}

impl State {
    fn new(spec: &Spec) -> Self {
        let mut state = State::default();
        state.reconcile(spec);
        for (run, anim) in state.runs.iter_mut().zip(&spec.anims) {
            if anim.trigger == Trigger::Active && anim.active {
                // Already active when it appears: start from the end, like a CSS state.
                run.progress = 1.0;
                run.weight = 1.0;
                run.was_on = true;
                run.pending = anim.looping();
            }
        }
        state
    }

    /// Matches the runs and transitions to a (possibly new) spec.
    fn reconcile(&mut self, spec: &Spec) {
        let mut runs = Vec::with_capacity(spec.anims.len());
        for (i, anim) in spec.anims.iter().enumerate() {
            let mut run = self
                .runs
                .get(i)
                .filter(|r| r.signature == anim.signature)
                .cloned()
                .unwrap_or_else(|| Run {
                    signature: anim.signature,
                    key: anim.key.clone(),
                    pending: anim.trigger == Trigger::Mount,
                    ..Run::default()
                });
            if run.key != anim.key {
                run.key = anim.key.clone();
                if !anim.state_based() {
                    run.start = None;
                    run.pending = true;
                    run.started = false;
                    run.ended = false;
                }
            }
            runs.push(run);
        }
        self.runs = runs;

        let mut transitions = Vec::with_capacity(spec.transitions.len());
        for t in &spec.transitions {
            let previous = self.transitions.iter().find(|s| s.prop == t.prop).cloned();
            let state = match previous {
                Some(mut s) if s.to != t.value => {
                    s.from = self.transition_value(&s);
                    s.to = t.value;
                    s.start = None;
                    s.pending = true;
                    s.duration = t.duration;
                    s.delay = t.delay;
                    s.easing = t.easing;
                    s
                }
                Some(s) => s,
                None => TransitionState {
                    prop: t.prop,
                    from: t.value,
                    to: t.value,
                    start: None,
                    pending: false,
                    duration: t.duration,
                    delay: t.delay,
                    easing: t.easing,
                },
            };
            transitions.push(state);
        }
        self.transitions = transitions;
    }

    /// Eased progress (0 to 1) of a transition.
    fn transition_t(&self, s: &TransitionState) -> f32 {
        if settled() {
            return 1.0;
        }
        let (Some(start), Some(now)) = (s.start, self.now) else {
            return if s.pending || s.from != s.to {
                0.0
            } else {
                1.0
            };
        };
        if s.duration <= 0.0 {
            return 1.0;
        }
        let local = now.saturating_duration_since(start).as_secs_f32() - s.delay;
        s.easing.apply((local / s.duration).clamp(0.0, 1.0))
    }

    /// The value a transition shows right now (so a new target starts from there).
    fn transition_value(&self, s: &TransitionState) -> Value {
        let t = self.transition_t(s);
        if t >= 1.0 {
            return s.to;
        }
        if t <= 0.0 {
            return s.from;
        }
        let size = self.size;
        let px = |v: Value, along: f32| match v {
            Value::Pct(p) => Some(p * along),
            Value::Num(n) => Some(n),
            _ => None,
        };
        let along = if s.prop == Prop::Y {
            size.height
        } else {
            size.width
        };
        match (s.from, s.to) {
            (Value::Color(a), Value::Color(b)) => Value::Color(mix(a, b, t)),
            (a, b) => match (px(a, along), px(b, along)) {
                (Some(a), Some(b)) => Value::Num(lerp(a, b, t)),
                _ => s.to,
            },
        }
    }

    fn transitions_running(&self) -> bool {
        self.transitions
            .iter()
            .any(|s| s.pending || (s.from != s.to && self.transition_t(s) < 1.0))
    }
}

/// What an `Animated` draws with this frame.
struct Frame {
    opacity: f32,
    x: f32,
    y: f32,
    scale: f32,
    paint: Paint,
}

/// Wraps an element and plays its animations, transitions and effects.
pub struct Animated<'a, Renderer> {
    content: Element<'a, Message, Theme, Renderer>,
    spec: Arc<Spec>,
}

impl<'a, Renderer> Animated<'a, Renderer> {
    pub fn new(content: impl Into<Element<'a, Message, Theme, Renderer>>, spec: Arc<Spec>) -> Self {
        Self {
            content: content.into(),
            spec,
        }
    }

    fn condition(&self, anim: &Anim, state: &State) -> bool {
        match anim.trigger {
            Trigger::Hover => state.hovered,
            Trigger::Press => state.pressed,
            Trigger::Focus => state.focused,
            Trigger::Active => anim.active,
            Trigger::Mount | Trigger::Click => true,
        }
    }

    /// The keyframe position and weight an animation shows (`None`: not applied).
    fn position(&self, anim: &Anim, run: &Run, state: &State) -> Option<(f32, f32)> {
        if settled() {
            return match anim.trigger {
                Trigger::Mount if anim.iterations.is_finite() => {
                    anim.at_time(f32::MAX).0.map(|p| (p, 1.0))
                }
                Trigger::Mount | Trigger::Click => None,
                _ if anim.looping() => None,
                _ => self
                    .condition(anim, state)
                    .then(|| (anim.directed(0.0, 1.0), 1.0)),
            };
        }
        if anim.state_based() {
            if anim.looping() {
                if run.weight <= 0.0 {
                    return None;
                }
                let elapsed = match (run.start, state.now) {
                    (Some(start), Some(now)) => now.saturating_duration_since(start).as_secs_f32(),
                    _ => 0.0,
                };
                return anim.at_time(elapsed).0.map(|p| (p, run.weight));
            }
            if run.progress <= 0.0 {
                return None;
            }
            return Some((anim.directed(0.0, run.progress), 1.0));
        }
        match (run.start, state.now) {
            (Some(start), Some(now)) => {
                let elapsed = now.saturating_duration_since(start).as_secs_f32();
                anim.at_time(elapsed).0.map(|p| (p, 1.0))
            }
            // Not started yet: a mount animation shows its first frame (no flash of the
            // final state); a click animation waits for a click.
            _ if anim.trigger == Trigger::Mount && run.pending => {
                anim.at_time(-1.0).0.map(|p| (p, 1.0))
            }
            _ => None,
        }
    }

    fn frame(&self, state: &State, bounds: Rectangle) -> Frame {
        let base = &self.spec.base;
        let px = |v: Value, along: f32| match v {
            Value::Num(n) => n,
            Value::Pct(p) => p * along,
            _ => 0.0,
        };
        let mut frame = Frame {
            opacity: base.opacity,
            x: px(base.x, bounds.width),
            y: px(base.y, bounds.height),
            scale: base.scale,
            paint: Paint::default(),
        };
        let apply = |prop: Prop, a: Value, b: Value, t: f32, w: f32, frame: &mut Frame| {
            if prop.is_paint() {
                frame.paint.set(prop, a, b, t, w);
                return;
            }
            let (identity, along) = match prop {
                Prop::Opacity | Prop::Scale => (1.0, 0.0),
                Prop::X => (0.0, bounds.width),
                _ => (0.0, bounds.height),
            };
            let resolve = |v: Value| match v {
                Value::Base | Value::Color(_) => identity,
                v => px(v, along),
            };
            let value = lerp(identity, lerp(resolve(a), resolve(b), t), w);
            match prop {
                Prop::Opacity => frame.opacity *= value.clamp(0.0, 1.0),
                Prop::Scale => frame.scale *= value.max(0.0),
                Prop::X => frame.x += value,
                Prop::Y => frame.y += value,
                _ => {}
            }
        };
        for (anim, run) in self.spec.anims.iter().zip(&state.runs) {
            let Some((p, w)) = self.position(anim, run, state) else {
                continue;
            };
            for track in &anim.tracks {
                let (a, b, t) = anim.sample(track, p);
                apply(track.prop, a, b, t, w, &mut frame);
            }
        }
        for s in &state.transitions {
            let t = state.transition_t(s);
            if !s.prop.is_paint() && s.from == s.to && matches!(s.to, Value::Base) {
                continue;
            }
            // Transitions set the value (they don't stack on the identity like animations).
            if s.prop.is_paint() {
                frame.paint.set(s.prop, s.from, s.to, t, 1.0);
            } else {
                let along = if s.prop == Prop::Y {
                    bounds.height
                } else {
                    bounds.width
                };
                let identity = if matches!(s.prop, Prop::Opacity | Prop::Scale) {
                    1.0
                } else {
                    0.0
                };
                let resolve = |v: Value| match v {
                    Value::Base | Value::Color(_) => identity,
                    v => px(v, along),
                };
                let value = lerp(resolve(s.from), resolve(s.to), t);
                match s.prop {
                    Prop::Opacity => frame.opacity *= value.clamp(0.0, 1.0),
                    Prop::Scale => frame.scale *= value.max(0.0),
                    Prop::X => frame.x += value,
                    Prop::Y => frame.y += value,
                    _ => {}
                }
            }
        }
        frame
    }

    /// Advances the timelines to `now`; publishes start and end events. Returns whether
    /// anything still moves.
    fn tick(&self, state: &mut State, now: Instant, shell: &mut Shell<'_, Message>) -> bool {
        let dt = state
            .last
            .map(|last| now.saturating_duration_since(last).as_secs_f32())
            .unwrap_or(0.0)
            .min(0.1);
        state.last = Some(now);
        state.now = Some(now);
        let mut moving = false;
        for i in 0..state.runs.len() {
            let Some(anim) = self.spec.anims.get(i) else {
                break;
            };
            let on = self.condition(anim, state);
            let run = &mut state.runs[i];
            if anim.state_based() {
                if anim.looping() {
                    if on && !run.was_on {
                        run.start = Some(now);
                        run.ended = false;
                        if let Some(msg) = &anim.on_start {
                            shell.publish(Message::Py(msg.clone()));
                        }
                    }
                    if run.pending {
                        run.pending = false;
                        run.start = Some(now);
                    }
                    let blend = anim.duration.clamp(0.05, 0.25);
                    let target = if on { 1.0 } else { 0.0 };
                    let step = dt / blend;
                    run.weight = if run.weight < target {
                        (run.weight + step).min(target)
                    } else {
                        (run.weight - step).max(target)
                    };
                    let finished = anim.iterations.is_finite()
                        && run.start.is_some_and(|s| {
                            now.saturating_duration_since(s).as_secs_f32() >= anim.total()
                        });
                    moving |= run.weight != target || (on && !finished);
                } else {
                    if on && !run.was_on {
                        if let Some(msg) = &anim.on_start {
                            shell.publish(Message::Py(msg.clone()));
                        }
                        run.ended = false;
                    }
                    let target = if on { 1.0 } else { 0.0 };
                    let step = if anim.duration <= 0.0 {
                        1.0
                    } else {
                        dt / anim.duration
                    };
                    let before = run.progress;
                    run.progress = if before < target {
                        (before + step).min(target)
                    } else {
                        (before - step).max(target)
                    };
                    if on && run.progress >= 1.0 && !run.ended {
                        run.ended = true;
                        if let Some(msg) = &anim.on_end {
                            shell.publish(Message::Py(msg.clone()));
                        }
                    }
                    moving |= run.progress != target;
                }
                run.was_on = on;
                continue;
            }
            if run.pending {
                run.pending = false;
                run.start = Some(now);
                run.started = false;
                run.ended = false;
            }
            let Some(start) = run.start else {
                continue;
            };
            let elapsed = now.saturating_duration_since(start).as_secs_f32();
            if !run.started && elapsed >= anim.delay {
                run.started = true;
                if let Some(msg) = &anim.on_start {
                    shell.publish(Message::Py(msg.clone()));
                }
            }
            let (_, done) = anim.at_time(elapsed);
            if done {
                if !run.ended {
                    run.ended = true;
                    if let Some(msg) = &anim.on_end {
                        shell.publish(Message::Py(msg.clone()));
                    }
                }
            } else {
                moving = true;
            }
        }
        for s in &mut state.transitions {
            if s.pending {
                s.pending = false;
                s.start = Some(now);
            }
        }
        moving || state.transitions_running()
    }
}

impl<Renderer> Widget<Message, Theme, Renderer> for Animated<'_, Renderer>
where
    Renderer: iced::advanced::Renderer,
{
    fn tag(&self) -> widget::tree::Tag {
        widget::tree::Tag::of::<State>()
    }

    fn state(&self) -> widget::tree::State {
        widget::tree::State::new(State::new(&self.spec))
    }

    fn children(&self) -> Vec<Tree> {
        vec![Tree::new(&self.content)]
    }

    fn diff(&self, tree: &mut Tree) {
        tree.state.downcast_mut::<State>().reconcile(&self.spec);
        tree.diff_children(std::slice::from_ref(&self.content));
    }

    fn size(&self) -> Size<Length> {
        self.content.as_widget().size()
    }

    fn size_hint(&self) -> Size<Length> {
        self.content.as_widget().size_hint()
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        self.content
            .as_widget_mut()
            .layout(&mut tree.children[0], renderer, limits)
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        self.content
            .as_widget_mut()
            .operate(&mut tree.children[0], layout, renderer, operation);
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        viewport: &Rectangle,
    ) {
        self.content.as_widget_mut().update(
            &mut tree.children[0],
            event,
            layout,
            cursor,
            renderer,
            clipboard,
            shell,
            viewport,
        );
        let state = tree.state.downcast_mut::<State>();
        let bounds = layout.bounds();
        state.size = bounds.size();
        let over = cursor.is_over(bounds) && cursor.is_over(*viewport);
        let mut changed = false;
        match event {
            Event::Mouse(mouse::Event::CursorMoved { .. } | mouse::Event::CursorLeft) => {
                if over != state.hovered {
                    state.hovered = over;
                    changed = true;
                }
            }
            Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left)) => {
                if over {
                    state.pressed = true;
                    changed = true;
                }
                if over != state.focused {
                    state.focused = over;
                    changed = true;
                }
            }
            Event::Mouse(mouse::Event::ButtonReleased(mouse::Button::Left)) => {
                if state.pressed {
                    state.pressed = false;
                    changed = true;
                    if over {
                        for (run, anim) in state.runs.iter_mut().zip(&self.spec.anims) {
                            if anim.trigger == Trigger::Click {
                                run.pending = true;
                                run.start = None;
                            }
                        }
                    }
                }
            }
            Event::Window(window::Event::RedrawRequested(now)) => {
                if self.tick(state, *now, shell) {
                    shell.request_redraw();
                } else {
                    state.last = None;
                }
                return;
            }
            _ => {}
        }
        let waiting =
            state.runs.iter().any(|r| r.pending) || state.transitions.iter().any(|t| t.pending);
        if changed || waiting {
            shell.request_redraw();
        }
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
        renderer: &Renderer,
    ) -> mouse::Interaction {
        self.content.as_widget().mouse_interaction(
            &tree.children[0],
            layout,
            cursor,
            viewport,
            renderer,
        )
    }

    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut Renderer,
        theme: &Theme,
        style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        let state = tree.state.downcast_ref::<State>();
        let bounds = layout.bounds();
        let frame = self.frame(state, bounds);
        if frame.opacity <= 0.001 || frame.scale <= 0.001 {
            return;
        }
        let outer = opacity();
        OPACITY.with(|o| o.set(outer * frame.opacity));
        let previous =
            (!frame.paint.is_empty()).then(|| PAINT.with(|p| p.borrow_mut().replace(frame.paint)));
        let style = renderer::Style {
            text_color: style.text_color.scale_alpha(frame.opacity),
        };
        let child = &tree.children[0];
        if frame.x == 0.0 && frame.y == 0.0 && frame.scale == 1.0 {
            self.content
                .as_widget()
                .draw(child, renderer, theme, &style, layout, cursor, viewport);
        } else {
            let center = bounds.center();
            let transformation = Transformation::translate(center.x + frame.x, center.y + frame.y)
                * Transformation::scale(frame.scale)
                * Transformation::translate(-center.x, -center.y);
            // What the viewport covers in the child's own (untransformed) coordinates.
            let visible = *viewport * transformation.inverse();
            renderer.with_transformation(transformation, |renderer| {
                self.content
                    .as_widget()
                    .draw(child, renderer, theme, &style, layout, cursor, &visible);
            });
        }
        OPACITY.with(|o| o.set(outer));
        if let Some(previous) = previous {
            PAINT.with(|p| *p.borrow_mut() = previous);
        }
    }

    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &Renderer,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<overlay::Element<'b, Message, Theme, Renderer>> {
        self.content.as_widget_mut().overlay(
            &mut tree.children[0],
            layout,
            renderer,
            viewport,
            translation,
        )
    }
}

impl<'a, Renderer> From<Animated<'a, Renderer>> for Element<'a, Message, Theme, Renderer>
where
    Renderer: iced::advanced::Renderer + 'a,
{
    fn from(animated: Animated<'a, Renderer>) -> Self {
        Element::new(animated)
    }
}

// ---------------------------------------------------------------------------
// Presence: the old content animates out while the new one animates in
// ---------------------------------------------------------------------------

/// Two stacked children: the content leaving (drawn, ticking, but deaf to input) and the
/// current one. The current one decides the size.
pub struct Presence<'a, Renderer> {
    leaving: Element<'a, Message, Theme, Renderer>,
    current: Element<'a, Message, Theme, Renderer>,
}

impl<'a, Renderer> Presence<'a, Renderer> {
    pub fn new(
        leaving: impl Into<Element<'a, Message, Theme, Renderer>>,
        current: impl Into<Element<'a, Message, Theme, Renderer>>,
    ) -> Self {
        Self {
            leaving: leaving.into(),
            current: current.into(),
        }
    }
}

impl<Renderer> Widget<Message, Theme, Renderer> for Presence<'_, Renderer>
where
    Renderer: iced::advanced::Renderer,
{
    fn children(&self) -> Vec<Tree> {
        vec![Tree::new(&self.leaving), Tree::new(&self.current)]
    }

    fn diff(&self, tree: &mut Tree) {
        tree.diff_children(&[&self.leaving, &self.current]);
    }

    fn size(&self) -> Size<Length> {
        self.current.as_widget().size()
    }

    fn size_hint(&self) -> Size<Length> {
        self.current.as_widget().size_hint()
    }

    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        let current = self
            .current
            .as_widget_mut()
            .layout(&mut tree.children[1], renderer, limits);
        let size = current.size();
        let leaving = self.leaving.as_widget_mut().layout(
            &mut tree.children[0],
            renderer,
            &layout::Limits::new(Size::ZERO, size),
        );
        layout::Node::with_children(size, vec![leaving, current])
    }

    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &Renderer,
        operation: &mut dyn widget::Operation,
    ) {
        let current = layout.children().nth(1).unwrap();
        self.current
            .as_widget_mut()
            .operate(&mut tree.children[1], current, renderer, operation);
    }

    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        viewport: &Rectangle,
    ) {
        let mut children = layout.children();
        let (leaving, current) = (children.next().unwrap(), children.next().unwrap());
        if let Event::Window(window::Event::RedrawRequested(_)) = event {
            self.leaving.as_widget_mut().update(
                &mut tree.children[0],
                event,
                leaving,
                mouse::Cursor::Unavailable,
                renderer,
                clipboard,
                shell,
                viewport,
            );
        }
        self.current.as_widget_mut().update(
            &mut tree.children[1],
            event,
            current,
            cursor,
            renderer,
            clipboard,
            shell,
            viewport,
        );
    }

    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
        renderer: &Renderer,
    ) -> mouse::Interaction {
        let current = layout.children().nth(1).unwrap();
        self.current.as_widget().mouse_interaction(
            &tree.children[1],
            current,
            cursor,
            viewport,
            renderer,
        )
    }

    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut Renderer,
        theme: &Theme,
        style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        let mut children = layout.children();
        let (leaving, current) = (children.next().unwrap(), children.next().unwrap());
        self.leaving.as_widget().draw(
            &tree.children[0],
            renderer,
            theme,
            style,
            leaving,
            mouse::Cursor::Unavailable,
            viewport,
        );
        self.current.as_widget().draw(
            &tree.children[1],
            renderer,
            theme,
            style,
            current,
            cursor,
            viewport,
        );
    }

    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &Renderer,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<overlay::Element<'b, Message, Theme, Renderer>> {
        let current = layout.children().nth(1).unwrap();
        self.current.as_widget_mut().overlay(
            &mut tree.children[1],
            current,
            renderer,
            viewport,
            translation,
        )
    }
}

impl<'a, Renderer> From<Presence<'a, Renderer>> for Element<'a, Message, Theme, Renderer>
where
    Renderer: iced::advanced::Renderer + 'a,
{
    fn from(presence: Presence<'a, Renderer>) -> Self {
        Element::new(presence)
    }
}

/// What `pz.presence(...)` remembers between renders: the key shown and the content that
/// is leaving, until its exit animation ends.
pub struct PresenceEntry {
    pub key: String,
    pub current: Py<crate::widget::Widget>,
    pub exit: Arc<Spec>,
    pub leaving: Option<(Py<crate::widget::Widget>, String, Arc<Spec>, Instant)>,
}

/// Shows `content` and animates it when `key` changes: the old content plays `exit`
/// while the new one plays `enter` (compiled by ``pyzed.animation.presence``).
#[pyfunction]
#[pyo3(signature = (content, *, id, key, enter, exit))]
pub fn presence(
    py: Python<'_>,
    content: &Bound<'_, PyAny>,
    id: String,
    key: String,
    enter: &Bound<'_, PyAny>,
    exit: &Bound<'_, PyAny>,
) -> PyResult<Py<crate::widget::Widget>> {
    let spec = |list: &Bound<'_, PyAny>| -> PyResult<Arc<Spec>> {
        Ok(Arc::new(Spec {
            anims: parse_anims(list)?,
            ..Spec::default()
        }))
    };
    crate::widget::new(
        py,
        crate::widget::Kind::Presence(Box::new(PresenceProps {
            id,
            key,
            child: crate::widget::child(content)?,
            enter: spec(enter)?,
            exit: spec(exit)?,
        })),
    )
}

/// The `presence` node built from Python.
pub struct PresenceProps {
    pub id: String,
    pub key: String,
    pub child: Py<crate::widget::Widget>,
    pub enter: Arc<Spec>,
    pub exit: Arc<Spec>,
}
