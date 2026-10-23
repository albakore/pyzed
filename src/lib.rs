//! Native core of Pyzed: a thin, fast bridge between Python and the Iced GUI toolkit.

#[cfg(target_os = "android")]
mod android;
mod animation;
mod app;
mod audio;
mod editor;
mod editor_widgets;
mod events;
mod extra;
mod focus;
mod fonts;
mod frame;
mod highlighter;
mod imaging;
mod layout;
mod min_size;
mod popup;
mod recorder;
mod render;
mod scrub;
mod select;
mod selectable;
mod shader;
mod sticky;
mod style;
mod styled;
mod tray;
mod virtualize;
mod widget;

use pyo3::prelude::*;

/// Every view builds and drops thousands of small objects (widget nodes, layout nodes,
/// shaped text); mimalloc handles that churn much faster than the system allocator.
/// Only Rust's allocations use it: Python keeps its own.
#[cfg(not(target_os = "android"))]
#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Scanning the system fonts and parsing the bundled ones takes from a few to a few hundred
    // milliseconds (it grows with the fonts installed). Start it now, so it runs while Python
    // imports the rest of the app; `run` and `screenshot` wait for it before drawing.
    let _ = std::thread::Builder::new()
        .name("pyzed-fonts".into())
        .spawn(fonts::ensure_loaded);
    widget::register(m)?;
    extra::register(m)?;
    shader::register(m)?;
    layout::register(m)?;
    frame::register(m)?;
    focus::register(m)?;
    audio::register(m)?;
    m.add_class::<app::Command>()?;
    m.add_class::<app::PySubscription>()?;
    m.add_function(wrap_pyfunction!(app::every, m)?)?;
    m.add_function(wrap_pyfunction!(app::listen, m)?)?;
    m.add_function(wrap_pyfunction!(app::frames, m)?)?;
    m.add_function(wrap_pyfunction!(app::pressed_keys, m)?)?;
    m.add_function(wrap_pyfunction!(app::run, m)?)?;
    m.add_function(wrap_pyfunction!(imaging::image_size, m)?)?;
    m.add_function(wrap_pyfunction!(imaging::resize_image, m)?)?;
    m.add_function(wrap_pyfunction!(app::screenshot, m)?)?;
    m.add_function(wrap_pyfunction!(recorder::record, m)?)?;
    m.add_function(wrap_pyfunction!(app::post, m)?)?;
    m.add_function(wrap_pyfunction!(tray::tray_set, m)?)?;
    m.add_function(wrap_pyfunction!(tray::tray_remove, m)?)?;
    m.add_function(wrap_pyfunction!(tray::tray_supported, m)?)?;
    m.add("UNCHANGED", Py::new(m.py(), app::Unchanged)?)?;
    m.add_function(wrap_pyfunction!(fonts::load_font, m)?)?;
    m.add_function(wrap_pyfunction!(fonts::set_fonts, m)?)?;
    m.add_function(wrap_pyfunction!(fonts::font_families, m)?)?;
    m.add_function(wrap_pyfunction!(animation::presence, m)?)?;
    m.add_function(wrap_pyfunction!(animation::set_reduced_motion, m)?)?;
    m.add_function(wrap_pyfunction!(animation::reduced_motion, m)?)?;
    m.add_function(wrap_pyfunction!(animation::ease, m)?)?;
    m.add("EASINGS", animation::EASINGS.to_vec())?;
    m.add("ICED_VERSION", "0.14")?;
    Ok(())
}
