//! Bundled fonts: IBM Plex Sans/Mono (UI and code, like Zed) and Lucide (icons). The italic faces
//! are there for emphasis (Markdown's `*text*`, a theme's italic code): without them it showed upright,
//! or in another family. IBM Plex Sans Arabic and Hebrew (only their own letters) draw those
//! scripts in the same style on every system: Plex Sans has no such letters, so the text engine
//! falls back to them before the system's fonts.

use std::borrow::Cow;
use std::sync::Once;

use pyo3::prelude::*;
use pyo3::types::PyBytes;

const BUNDLED: &[&[u8]] = &[
    include_bytes!("../assets/fonts/IBMPlexSans-Regular.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSans-Medium.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSans-SemiBold.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSans-Bold.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSans-Italic.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSans-BoldItalic.ttf"),
    include_bytes!("../assets/fonts/IBMPlexMono-Regular.ttf"),
    include_bytes!("../assets/fonts/IBMPlexMono-Medium.ttf"),
    include_bytes!("../assets/fonts/IBMPlexMono-Italic.ttf"),
    include_bytes!("../assets/fonts/lucide.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSansArabic-Regular.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSansArabic-Medium.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSansArabic-SemiBold.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSansArabic-Bold.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSansHebrew-Regular.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSansHebrew-Medium.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSansHebrew-SemiBold.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSansHebrew-Bold.ttf"),
];

/// The bundled families tried first for the letters of a script Plex Sans lacks.
const SCRIPT_FALLBACKS: &[(&str, &str)] = &[
    ("Arab", "IBM Plex Sans Arabic"),
    ("Hebr", "IBM Plex Sans Hebrew"),
];

fn load(bytes: Cow<'static, [u8]>) {
    iced::advanced::graphics::text::font_system()
        .write()
        .expect("font system lock")
        .load_font(bytes);
}

pub fn ensure_loaded() {
    static ONCE: Once = Once::new();
    ONCE.call_once(|| {
        for (script, family) in SCRIPT_FALLBACKS {
            iced::advanced::graphics::text::prefer_fallback(script, family);
        }
        for font in BUNDLED {
            load(Cow::Borrowed(font));
        }
    });
}

/// Loads an extra font (a path to a .ttf/.otf file, or its bytes) so widgets can use it
/// by family name, e.g. `text("hi", font="JetBrains Mono")`.
#[pyfunction]
pub fn load_font(source: &Bound<'_, PyAny>) -> PyResult<()> {
    ensure_loaded();
    let bytes = if let Ok(bytes) = source.cast::<PyBytes>() {
        bytes.as_bytes().to_vec()
    } else {
        let path: std::path::PathBuf = source.extract()?;
        std::fs::read(path)?
    };
    load(Cow::Owned(bytes));
    Ok(())
}

/// Makes `"sans"` (the interface) and `"mono"` (code) stand for other loaded or system families; `None`
/// goes back to IBM Plex Sans and Mono. Takes effect on the next frame.
#[pyfunction]
#[pyo3(signature = (ui=None, code=None))]
pub fn set_fonts(ui: Option<&str>, code: Option<&str>) {
    crate::style::set_fonts(ui, code);
}

/// The font families that can be used by name: the bundled ones, those loaded with `load_font` and the
/// system's, sorted and without repeats.
#[pyfunction]
pub fn font_families(py: Python<'_>) -> Vec<String> {
    py.detach(|| {
        ensure_loaded();
        let mut system = iced::advanced::graphics::text::font_system()
            .write()
            .expect("font system lock");
        let mut names: Vec<String> = system
            .raw()
            .db()
            .faces()
            .filter_map(|face| face.families.first().map(|(name, _)| name.clone()))
            .filter(|name| name != crate::style::ICONS)
            .collect();
        names.sort_by_key(|n| n.to_lowercase());
        names.dedup();
        names
    })
}
