//! Linux (and the BSDs): `org.freedesktop.Notifications` over the session bus.
//!
//! One connection is opened on first use, with a thread per signal: `ActionInvoked` (a click on
//! the notification is the `default` action, a button is its id) and `NotificationClosed`.

use super::{Event, Sink, Spec};
use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use zbus::blocking::{Connection, Proxy};
use zbus::zvariant::Value;

const SERVICE: &str = "org.freedesktop.Notifications";
const PATH: &str = "/org/freedesktop/Notifications";

#[derive(Default)]
struct State {
    /// The server's number of each notification shown, by Python's number.
    server_ids: HashMap<u64, u32>,
    /// The events' sinks, by the server's number.
    sinks: HashMap<u32, Sink>,
}

fn state() -> &'static Mutex<State> {
    static STATE: OnceLock<Mutex<State>> = OnceLock::new();
    STATE.get_or_init(Default::default)
}

/// The session bus, opened (and its listeners started) once; `None` without one.
fn connection() -> Option<&'static Connection> {
    static CONNECTION: OnceLock<Option<Connection>> = OnceLock::new();
    CONNECTION
        .get_or_init(|| {
            let connection = Connection::session().ok()?;
            listen(&connection);
            Some(connection)
        })
        .as_ref()
}

fn proxy(connection: &Connection) -> zbus::Result<Proxy<'static>> {
    Proxy::new(connection, SERVICE, PATH, SERVICE)
}

fn sink_of(server_id: u32) -> Option<Sink> {
    state().lock().unwrap().sinks.get(&server_id).cloned()
}

/// Starts the threads that hand clicks, buttons and closes to Python.
fn listen(connection: &Connection) {
    let actions = connection.clone();
    std::thread::Builder::new()
        .name("pyzed-notify-actions".into())
        .spawn(move || {
            let Ok(proxy) = proxy(&actions) else { return };
            let Ok(signals) = proxy.receive_signal("ActionInvoked") else {
                return;
            };
            for message in signals {
                let Ok((server_id, key)) = message.body().deserialize::<(u32, String)>() else {
                    continue;
                };
                if let Some(sink) = sink_of(server_id) {
                    sink(if key == "default" {
                        Event::Click
                    } else {
                        Event::Action(key)
                    });
                }
            }
        })
        .ok();
    let closes = connection.clone();
    std::thread::Builder::new()
        .name("pyzed-notify-closed".into())
        .spawn(move || {
            let Ok(proxy) = proxy(&closes) else { return };
            let Ok(signals) = proxy.receive_signal("NotificationClosed") else {
                return;
            };
            for message in signals {
                let Ok((server_id, reason)) = message.body().deserialize::<(u32, u32)>() else {
                    continue;
                };
                let sink = {
                    let mut state = state().lock().unwrap();
                    state.server_ids.retain(|_, id| *id != server_id);
                    state.sinks.remove(&server_id)
                };
                if let Some(sink) = sink {
                    sink(Event::Closed(match reason {
                        1 => "expired",
                        2 => "dismissed",
                        3 => "closed",
                        _ => "unknown",
                    }));
                }
            }
        })
        .ok();
}

pub(super) fn show(id: u64, spec: Spec, sink: Sink) -> Result<(), String> {
    let connection = connection().ok_or("there is no D-Bus session bus")?;
    let proxy = proxy(connection).map_err(|e| e.to_string())?;
    let replaces = state()
        .lock()
        .unwrap()
        .server_ids
        .get(&id)
        .copied()
        .unwrap_or(0);
    // a click on the notification itself is the "default" action, shown without a button
    let mut actions: Vec<&str> = vec!["default", ""];
    for (action, label) in &spec.actions {
        actions.push(action);
        actions.push(label);
    }
    let mut hints: HashMap<&str, Value<'_>> = HashMap::new();
    hints.insert("urgency", Value::U8(spec.urgency));
    match spec.sound.as_deref() {
        None => {
            hints.insert("suppress-sound", Value::Bool(true));
        }
        Some("default") => {
            hints.insert("sound-name", Value::from("message-new-instant"));
        }
        Some(name) => {
            hints.insert("sound-name", Value::from(name));
        }
    }
    if let Some(image) = spec.image.as_deref() {
        hints.insert("image-path", Value::from(image));
    }
    if let Some(entry) = spec.app_id.as_deref() {
        hints.insert("desktop-entry", Value::from(entry));
    }
    let app_icon = spec.icon.as_deref().unwrap_or("");
    let server_id: u32 = proxy
        .call(
            "Notify",
            &(
                spec.app_name.as_str(),
                replaces,
                app_icon,
                spec.title.as_str(),
                spec.body.as_str(),
                actions,
                hints,
                spec.timeout_ms,
            ),
        )
        .map_err(|e| e.to_string())?;
    let mut state = state().lock().unwrap();
    if replaces != 0 && replaces != server_id {
        state.sinks.remove(&replaces);
    }
    state.server_ids.insert(id, server_id);
    state.sinks.insert(server_id, sink);
    Ok(())
}

pub(super) fn close(id: u64) {
    let Some(server_id) = state().lock().unwrap().server_ids.get(&id).copied() else {
        return;
    };
    if let Some(connection) = connection()
        && let Ok(proxy) = proxy(connection)
    {
        let _: zbus::Result<()> = proxy.call("CloseNotification", &(server_id,));
    }
}

pub(super) fn supported() -> bool {
    let Some(connection) = connection() else {
        return false;
    };
    let Ok(bus) = zbus::blocking::fdo::DBusProxy::new(connection) else {
        return false;
    };
    let name = SERVICE.try_into().unwrap();
    if bus.name_has_owner(name).unwrap_or(false) {
        return true;
    }
    // a server that starts on the first notification (D-Bus activation)
    bus.list_activatable_names()
        .map(|names| names.iter().any(|n| n.as_str() == SERVICE))
        .unwrap_or(false)
}

pub(super) fn capabilities() -> Vec<String> {
    let Some(connection) = connection() else {
        return Vec::new();
    };
    let Ok(proxy) = proxy(connection) else {
        return Vec::new();
    };
    proxy
        .call::<_, _, Vec<String>>("GetCapabilities", &())
        .unwrap_or_default()
}
