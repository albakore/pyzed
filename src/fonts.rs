//! Bundled fonts: IBM Plex Sans/Mono (UI and code, like Zed) and Lucide (icons).

use std::borrow::Cow;
use std::sync::Once;

use pyo3::prelude::*;
use pyo3::types::PyBytes;

const BUNDLED: &[&[u8]] = &[
    include_bytes!("../assets/fonts/IBMPlexSans-Regular.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSans-Medium.ttf"),
    include_bytes!("../assets/fonts/IBMPlexSans-SemiBold.ttf"),
    include_bytes!("../assets/fonts/IBMPlexMono-Regular.ttf"),
    include_bytes!("../assets/fonts/IBMPlexMono-Medium.ttf"),
    include_bytes!("../assets/fonts/lucide.ttf"),
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
