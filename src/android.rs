//! Android (a prototype): the app is a NativeActivity. Its `android_main` unpacks the bundle the
//! APK carries (Python's standard library, Pyzed and the app), starts an embedded Python with
//! Pyzed's core built in, and runs the app's `main.py` as `__main__`.

use std::ffi::{CStr, CString, c_char, c_int};
use std::fs;
use std::io::{self, Cursor, Read};
use std::path::{Path, PathBuf};

use iced_winit::android::AndroidApp;
use pyo3::prelude::*;

use crate::_core;

/// The asset with everything Python needs: `python/` (the standard library and its compiled
/// modules), `site-packages/` (Pyzed and the app's dependencies) and `app/` (the app itself).
const BUNDLE: &std::ffi::CStr = c"pyzed-bundle.zip";

unsafe extern "C" {
    fn __android_log_write(priority: i32, tag: *const c_char, text: *const c_char) -> i32;
    // Python's initialization configuration, which the stable ABI PyO3 builds against leaves out.
    fn PyConfig_InitPythonConfig(config: *mut PyConfig);
    fn Py_InitializeFromConfig(config: *const PyConfig) -> PyStatus;
    fn PyConfig_Clear(config: *mut PyConfig);
    fn PyStatus_Exception(status: PyStatus) -> c_int;
}

/// Room for a `PyConfig`, whose fields change between Python versions (about 400 bytes in 3.13).
#[repr(C, align(16))]
struct PyConfig([u8; 4096]);

#[repr(C)]
#[derive(Clone, Copy)]
struct PyStatus {
    kind: c_int,
    func: *const c_char,
    err_msg: *const c_char,
    exitcode: c_int,
}

/// Starts Python like `Py_Initialize`, but returns its error instead of aborting the process.
fn start_python() -> Result<(), String> {
    // SAFETY: the config is initialized by Python before use and cleared after; the strings in a
    // failed status are static.
    unsafe {
        let mut config = PyConfig([0; 4096]);
        PyConfig_InitPythonConfig(&mut config);
        let status = Py_InitializeFromConfig(&config);
        PyConfig_Clear(&mut config);
        if PyStatus_Exception(status) != 0 {
            let text = |p: *const c_char| {
                if p.is_null() {
                    String::new()
                } else {
                    CStr::from_ptr(p).to_string_lossy().into_owned()
                }
            };
            return Err(format!("{}: {}", text(status.func), text(status.err_msg)));
        }
        // Like PyO3's own start: other threads take the GIL when they need it.
        pyo3::ffi::PyEval_SaveThread();
    }
    Ok(())
}

/// Writes a line to the system log (`adb logcat -s pyzed`).
fn log(error: bool, text: &str) {
    let text = CString::new(text.replace('\0', "")).unwrap_or_default();
    // SAFETY: both strings are valid and end in a NUL. 4 is INFO and 6 is ERROR.
    unsafe { __android_log_write(if error { 6 } else { 4 }, c"pyzed".as_ptr(), text.as_ptr()) };
}

/// Logs `text` as an error and keeps it in `last-error.txt`.
fn fail(report: &Path, text: &str) {
    log(true, text);
    let _ = fs::write(report, text);
}

#[unsafe(no_mangle)]
fn android_main(app: AndroidApp) {
    iced_winit::android::set_app(app.clone());
    let Some(files) = app.internal_data_path() else {
        log(true, "the app has no files folder");
        return;
    };
    let report = files.join("last-error.txt");
    let _ = fs::remove_file(&report);
    let hook_report = report.clone();
    std::panic::set_hook(Box::new(move |info| {
        fail(&hook_report, &format!("panic: {info}"))
    }));
    log(
        false,
        &format!("unpacking the app into {}", files.display()),
    );
    if let Err(err) = unpack(&app, &files) {
        fail(&report, &format!("could not unpack {BUNDLE:?}: {err}"));
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
    log(false, "starting Python");
    if let Err(err) = start_python() {
        fail(&report, &format!("could not start Python: {err}"));
        return;
    }
    log(false, "running app/main.py");
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
        fail(&report, &text);
    } else {
        log(false, "the app finished");
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
