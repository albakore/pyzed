//! Windows 10 and 11: toasts through WinRT, with their buttons.
//!
//! A toast needs the AppUserModelID of an installed app. An app packaged with `pyzed build`
//! can pass its own (`app_id`); otherwise the toast is shown as PowerShell's, which every Windows
//! has, so a script needs nothing installed.

use super::{Event, Sink, Spec};
use std::path::Path;
use tauri_winrt_notification::{Duration, IconCrop, Scenario, Sound, Toast, ToastDismissalReason};

pub(super) fn show(_id: u64, spec: Spec, sink: Sink) -> Result<(), String> {
    let app_id = spec
        .app_id
        .clone()
        .unwrap_or_else(|| Toast::POWERSHELL_APP_ID.to_string());
    let mut toast = Toast::new(&app_id).title(&spec.title).text1(&spec.body);
    if let Some(icon) = spec.icon.as_deref() {
        toast = toast.icon(Path::new(icon), IconCrop::Square, "");
    }
    if let Some(image) = spec.image.as_deref() {
        toast = toast.image(Path::new(image), "");
    }
    for (action, label) in &spec.actions {
        toast = toast.add_button(label, action);
    }
    toast = toast.sound(match spec.sound.as_deref() {
        None => None,
        Some("default") => Some(Sound::Default),
        Some(name) => Some(name.parse().unwrap_or(Sound::Default)),
    });
    toast = toast.duration(if spec.timeout_ms == 0 || spec.timeout_ms > 7000 {
        Duration::Long
    } else {
        Duration::Short
    });
    if spec.urgency >= 2 && !spec.actions.is_empty() {
        // stays on screen until the user answers (a reminder needs a button)
        toast = toast.scenario(Scenario::Reminder);
    }
    let clicked = sink.clone();
    toast = toast.on_activated(move |action| {
        clicked(match action {
            Some(action) if !action.is_empty() => Event::Action(action),
            _ => Event::Click,
        });
        Ok(())
    });
    toast = toast.on_dismissed(move |reason| {
        sink(Event::Closed(match reason {
            Some(ToastDismissalReason::UserCanceled) => "dismissed",
            Some(ToastDismissalReason::TimedOut) => "expired",
            Some(ToastDismissalReason::ApplicationHidden) => "closed",
            _ => "unknown",
        }));
        Ok(())
    });
    toast.show().map_err(|e| e.to_string())
}

/// Toasts can't be taken back with this API: they leave on their own.
pub(super) fn close(_id: u64) {}

pub(super) fn supported() -> bool {
    true
}

pub(super) fn capabilities() -> Vec<String> {
    ["actions", "body", "icon", "image", "sound"]
        .into_iter()
        .map(String::from)
        .collect()
}
