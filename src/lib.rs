//! Native core of Pyzed: a thin, fast bridge between Python and the Iced GUI toolkit.

mod app;
mod fonts;
mod highlighter;
mod render;
mod style;
mod widget;

use pyo3::prelude::*;

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    widget::register(m)?;
    m.add_class::<app::Command>()?;
    m.add_function(wrap_pyfunction!(app::run, m)?)?;
    m.add_function(wrap_pyfunction!(app::screenshot, m)?)?;
    m.add_function(wrap_pyfunction!(app::post, m)?)?;
    m.add_function(wrap_pyfunction!(fonts::load_font, m)?)?;
    m.add("ICED_VERSION", "0.14")?;
    Ok(())
}
