//! Desktop notifications (`pz.notify`): the system's own notifications, with buttons and clicks.
//!
//! Linux speaks the freedesktop notification protocol over D-Bus (what GNOME, KDE, Cinnamon, XFCE,
//! dunst and mako show), Windows shows toasts through WinRT and macOS uses the Notification
//! Center. Python gives each notification a number and a callback, `on_event(event, value)`:
//! `("click", None)`, `("action", action_id)` or `("closed", reason)`, where the reason is
//! `"expired"`, `"dismissed"`, `"closed"` or `"unknown"`.

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::sync::Arc;

#[path = "notify/spec.rs"]
mod spec;
pub(crate) use spec::{Event, Sink, Spec};

#[cfg(target_os = "linux")]
#[path = "notify/linux.rs"]
mod platform;
#[cfg(target_os = "macos")]
#[path = "notify/macos.rs"]
mod platform;
#[cfg(target_os = "windows")]
#[path = "notify/windows.rs"]
mod platform;
#[cfg(not(any(target_os = "linux", target_os = "macos", target_os = "windows")))]
#[path = "notify/none.rs"]
mod platform;

/// Shows notification `id` (or updates it, when it is already shown). Raises `RuntimeError` when
/// the system can't show it, so Python falls back to its own way.
#[pyfunction]
#[pyo3(signature = (id, on_event, title, body = String::new(), *, icon = None, image = None,
    actions = Vec::new(), urgency = 1, sound = Some("default".to_string()), timeout_ms = -1,
    app_name = String::new(), app_id = None))]
#[allow(clippy::too_many_arguments)]
pub fn notify_show(
    py: Python<'_>,
    id: u64,
    on_event: Py<PyAny>,
    title: String,
    body: String,
    icon: Option<String>,
    image: Option<String>,
    actions: Vec<(String, String)>,
    urgency: u8,
    sound: Option<String>,
    timeout_ms: i32,
    app_name: String,
    app_id: Option<String>,
) -> PyResult<()> {
    let spec = Spec {
        title,
        body,
        icon,
        image,
        actions,
        urgency: urgency.min(2),
        sound,
        timeout_ms,
        app_name,
        app_id,
    };
    let sink: Sink = Arc::new(move |event: Event| {
        Python::attach(|py| {
            let (name, value) = match &event {
                Event::Click => ("click", None),
                Event::Action(action) => ("action", Some(action.as_str())),
                Event::Closed(reason) => ("closed", Some(*reason)),
            };
            if let Err(err) = on_event.call1(py, (name, value)) {
                err.print(py);
            }
        });
    });
    // without the GIL: the listening thread may be waiting for it to hand over an event
    py.detach(|| platform::show(id, spec, sink))
        .map_err(PyRuntimeError::new_err)
}

/// Removes notification `id` from the screen (nothing when it is gone, or where the system
/// doesn't let apps close them).
#[pyfunction]
pub fn notify_close(py: Python<'_>, id: u64) {
    py.detach(|| platform::close(id));
}

/// Whether this system can show native notifications (on Linux, whether a notification server
/// runs or can be started).
#[pyfunction]
pub fn notify_supported(py: Python<'_>) -> bool {
    py.detach(platform::supported)
}

/// What the system's notifications can do: `"actions"`, `"body"`, `"body-markup"`, `"icon"`,
/// `"image"`, `"sound"`, `"persistence"`... (the freedesktop names, filled in on Windows and macOS).
#[pyfunction]
pub fn notify_capabilities(py: Python<'_>) -> Vec<String> {
    py.detach(platform::capabilities)
}
