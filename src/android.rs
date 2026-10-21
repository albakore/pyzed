//! Android (a prototype): the app is a NativeActivity. Its `android_main` unpacks the bundle the
//! APK carries (Python's standard library, Pyzed and the app), starts an embedded Python with
//! Pyzed's core built in, and runs the app's `main.py` as `__main__`.

use std::fs;
use std::io::{self, Cursor, Read};
use std::path::{Path, PathBuf};

use iced_winit::android::AndroidApp;
use pyo3::prelude::*;

use crate::_core;

/// The asset with everything Python needs: `python/` (the standard library and its compiled
/// modules), `site-packages/` (Pyzed and the app's dependencies) and `app/` (the app itself).
const BUNDLE: &std::ffi::CStr = c"pyzed-bundle.zip";

#[unsafe(no_mangle)]
fn android_main(app: AndroidApp) {
    iced_winit::android::set_app(app.clone());
    let Some(files) = app.internal_data_path() else {
        return;
    };
    let report = files.join("last-error.txt");
    let _ = fs::remove_file(&report);
    if let Err(err) = unpack(&app, &files) {
        let _ = fs::write(&report, format!("could not unpack {BUNDLE:?}: {err}"));
        return;
    }
    let tmp = files.join("tmp");
    let _ = fs::create_dir_all(&tmp);
    // SAFETY: nothing else runs yet, so no other thread reads the environment.
    unsafe {
        std::env::set_var("PYTHONHOME", files.join("python"));
        std::env::set_var("HOME", &files);
        std::env::set_var("TMPDIR", &tmp);
    }
    pyo3::append_to_inittab!(_core);
    Python::initialize();
    let result = Python::attach(|py| run(py, &files));
    if let Err(err) = result {
        let text = Python::attach(|py| {
            let traceback = py
                .import("traceback")
                .and_then(|m| m.call_method1("format_exception", (err.value(py),)))
                .and_then(|lines| lines.str())
                .map(|s| s.to_string());
            traceback.unwrap_or_else(|_| err.to_string())
        });
        let _ = fs::write(&report, text);
    }
}

fn run(py: Python<'_>, files: &Path) -> PyResult<()> {
    let sys = py.import("sys")?;
    let path = sys.getattr("path")?;
    for folder in ["app", "site-packages"] {
        path.call_method1("insert", (0, files.join(folder)))?;
    }
    // The core is built into this library, not a file next to `pyzed/`.
    sys.getattr("modules")?
        .set_item("pyzed._core", py.import("_core")?)?;
    let main = files.join("app").join("main.py");
    py.import("runpy")?
        .call_method1("run_path", (main, py.None(), "__main__"))
        .map(|_| ())
}

/// Unpacks the bundle into `files` when it is not there yet, or when the APK carries another one.
fn unpack(app: &AndroidApp, files: &Path) -> io::Result<()> {
    let mut asset = app
        .asset_manager()
        .open(BUNDLE)
        .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "no bundle in the APK"))?;
    let mut data = Vec::new();
    asset.read_to_end(&mut data)?;
    let stamp: PathBuf = files.join(".bundle-size");
    if fs::read_to_string(&stamp).ok().as_deref() == Some(&data.len().to_string()) {
        return Ok(());
    }
    for folder in ["python", "site-packages", "app"] {
        let _ = fs::remove_dir_all(files.join(folder));
    }
    zip::ZipArchive::new(Cursor::new(data.as_slice()))
        .and_then(|mut archive| archive.extract(files))
        .map_err(io::Error::other)?;
    fs::write(stamp, data.len().to_string())
}
