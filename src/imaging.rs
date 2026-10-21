//! Small image helpers for Python: the size of a picture and a resized PNG copy of it (used to
//! make app icons and splash screens without Pillow).

use std::io::Cursor;
use std::path::PathBuf;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

/// Decodes `source`: a path to an image file or its bytes.
pub(crate) fn decode(source: &Bound<'_, PyAny>) -> PyResult<image::DynamicImage> {
    let decoded = if let Ok(bytes) = source.cast::<PyBytes>() {
        image::load_from_memory(bytes.as_bytes())
    } else {
        let path: PathBuf = source.extract()?;
        image::open(&path)
    };
    decoded.map_err(|err| PyValueError::new_err(format!("cannot read the image: {err}")))
}

/// The size of the image `source` (a path or the file's bytes), in pixels: `(width, height)`.
#[pyfunction]
pub fn image_size(source: &Bound<'_, PyAny>) -> PyResult<(u32, u32)> {
    let image = decode(source)?;
    Ok((image.width(), image.height()))
}

/// The image `source` (a path or the file's bytes) scaled to exactly `width` × `height` pixels
/// (Lanczos filter) and encoded as PNG.
#[pyfunction]
pub fn resize_image<'py>(
    py: Python<'py>,
    source: &Bound<'py, PyAny>,
    width: u32,
    height: u32,
) -> PyResult<Bound<'py, PyBytes>> {
    if width == 0 || height == 0 {
        return Err(PyValueError::new_err("width and height must be at least 1"));
    }
    let image = decode(source)?;
    let png = py.detach(move || {
        let resized = image.resize_exact(width, height, image::imageops::FilterType::Lanczos3);
        let mut out = Cursor::new(Vec::new());
        resized
            .to_rgba8()
            .write_to(&mut out, image::ImageFormat::Png)
            .map(|_| out.into_inner())
    });
    png.map(|data| PyBytes::new(py, &data))
        .map_err(|err| PyValueError::new_err(format!("cannot encode the image: {err}")))
}
