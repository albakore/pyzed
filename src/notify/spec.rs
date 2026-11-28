//! What a notification shows and what can happen to it, shared by every system's implementation.

// Android and other systems have no notification server here: they only fail, so most of this is unused.
#![cfg_attr(
    not(any(target_os = "linux", target_os = "macos", target_os = "windows")),
    allow(dead_code)
)]

use std::sync::Arc;

/// Everything a notification shows.
#[derive(Clone, Debug, Default)]
pub(crate) struct Spec {
    pub title: String,
    pub body: String,
    /// A path to the app's icon for this notification.
    pub icon: Option<String>,
    /// A path to a bigger picture shown inside it (where the system shows one).
    pub image: Option<String>,
    /// `(id, label)` of each button.
    pub actions: Vec<(String, String)>,
    /// 0 low, 1 normal, 2 critical.
    pub urgency: u8,
    /// `None` silent, `Some("default")` the system's sound, or a sound's name.
    pub sound: Option<String>,
    /// Milliseconds on screen: -1 the system's default, 0 until dismissed.
    pub timeout_ms: i32,
    /// The name the notification server shows (Linux; Windows and macOS take it from `app_id`).
    #[cfg_attr(not(target_os = "linux"), allow(dead_code))]
    pub app_name: String,
    /// The app's identity: the desktop entry on Linux, the AppUserModelID on Windows and the
    /// bundle identifier on macOS.
    pub app_id: Option<String>,
}

/// What happened to a notification.
#[derive(Clone, Debug, PartialEq)]
pub(crate) enum Event {
    Click,
    Action(String),
    Closed(&'static str),
}

/// Where a notification's events go.
pub(crate) type Sink = Arc<dyn Fn(Event) + Send + Sync>;
