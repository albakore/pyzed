//! macOS: the Notification Center, with a button or a menu of them.
//!
//! Each notification waits for its answer on a thread of its own. A script run with `python`
//! has no bundle of its own, so the notification is shown as the terminal's (or Finder's) unless
//! `app_id` names the bundle identifier of the packaged app.

use super::{Event, Sink, Spec};
use mac_notification_sys::{MainButton, Notification, NotificationResponse};
use std::sync::Once;

pub(super) fn show(_id: u64, spec: Spec, sink: Sink) -> Result<(), String> {
    static APPLICATION: Once = Once::new();
    APPLICATION.call_once(|| {
        let bundle = spec.app_id.clone().unwrap_or_else(|| {
            let terminal = std::env::var("__CFBundleIdentifier").ok();
            terminal.unwrap_or_else(|| {
                mac_notification_sys::get_bundle_identifier_or_default("Terminal")
            })
        });
        let _ = mac_notification_sys::set_application(&bundle);
    });
    std::thread::Builder::new()
        .name("pyzed-notify".into())
        .spawn(move || {
            let labels: Vec<&str> = spec
                .actions
                .iter()
                .map(|(_, label)| label.as_str())
                .collect();
            let mut notification = Notification::new();
            notification
                .title(&spec.title)
                .message(&spec.body)
                .wait_for_click(true);
            match labels.as_slice() {
                [] => {}
                [one] => {
                    notification.main_button(MainButton::SingleAction(one));
                }
                many => {
                    notification.main_button(MainButton::DropdownActions("Options", many));
                }
            }
            match spec.sound.as_deref() {
                None => {}
                Some("default") => {
                    notification.default_sound();
                }
                Some(name) => {
                    notification.sound(name);
                }
            }
            if let Some(icon) = spec.icon.as_deref() {
                notification.app_icon(icon);
            }
            if let Some(image) = spec.image.as_deref() {
                notification.content_image(image);
            }
            let event = match notification.send() {
                Ok(NotificationResponse::Click) => Event::Click,
                Ok(NotificationResponse::ActionButton(label)) => {
                    let id = spec
                        .actions
                        .iter()
                        .find(|(_, l)| *l == label)
                        .map(|(id, _)| id.clone())
                        .unwrap_or(label);
                    Event::Action(id)
                }
                Ok(NotificationResponse::CloseButton(_)) => Event::Closed("dismissed"),
                Ok(_) => Event::Closed("unknown"),
                Err(_) => Event::Closed("unknown"),
            };
            sink(event);
        })
        .map(|_| ())
        .map_err(|e| e.to_string())
}

/// The Notification Center keeps delivered notifications until the user clears them.
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
