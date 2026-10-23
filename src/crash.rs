//! Panics written to a file: an app without a console (a packaged app, Pyzed Design) would
//! otherwise close with no trace of why.
//!
//! `set_crash_file(path)` names the file; the hook installed with the module appends each panic
//! (thread, place, message and backtrace) to it, then runs the hook that was there before, which
//! still prints to stderr.

use std::io::Write;
use std::path::PathBuf;
use std::sync::{Mutex, Once};

use pyo3::prelude::*;

static FILE: Mutex<Option<PathBuf>> = Mutex::new(None);
static INSTALL: Once = Once::new();

/// Installs the panic hook (once per process).
pub(crate) fn install() {
    INSTALL.call_once(|| {
        let previous = std::panic::take_hook();
        std::panic::set_hook(Box::new(move |info| {
            // never panic here, nor wait on a lock a panicking thread may hold
            let path = FILE.try_lock().ok().and_then(|file| file.clone());
            if let Some(path) = path {
                let thread = std::thread::current();
                let message = info
                    .payload()
                    .downcast_ref::<&str>()
                    .map(|s| s.to_string())
                    .or_else(|| info.payload().downcast_ref::<String>().cloned())
                    .unwrap_or_else(|| "(no message)".into());
                let place = info
                    .location()
                    .map(|l| format!("{}:{}:{}", l.file(), l.line(), l.column()))
                    .unwrap_or_default();
                let backtrace = std::backtrace::Backtrace::force_capture();
                if let Ok(mut out) = std::fs::OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(path)
                {
                    let _ = writeln!(
                        out,
                        "Pyzed {} panicked in thread '{}' at {place}:\n{message}\n\n{backtrace}\n",
                        env!("CARGO_PKG_VERSION"),
                        thread.name().unwrap_or("<unnamed>"),
                    );
                }
            }
            previous(info);
        }));
    });
}

/// Writes the panics of the native core to the end of ``path`` (``None`` stops it).
#[pyfunction]
#[pyo3(signature = (path=None))]
pub fn set_crash_file(path: Option<PathBuf>) {
    if let Ok(mut file) = FILE.lock() {
        *file = path;
    }
}
