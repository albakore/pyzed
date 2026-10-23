//! System tray icons (`pyzed.TrayIcon`): an icon with a tooltip and a menu in the taskbar's
//! notification area (Windows), the menu bar (macOS) or the panel (Linux).
//!
//! Linux speaks StatusNotifierItem over D-Bus (`ksni`), the protocol KDE, Cinnamon, XFCE and
//! GNOME's AppIndicator extension show, so it needs no GTK. Windows and macOS use their own tray
//! through `tray-icon`; there an icon can only be made on the app's thread once its event loop
//! runs, so one asked for earlier waits until the app's next update.
//!
//! Python gives each icon a number and a callback, `on_event(event, value)`: `("click", None)`,
//! `("double_click", None)` (Windows) or `("menu", item_id)`.

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

/// An entry of a tray menu.
#[derive(Clone, Debug, PartialEq)]
pub(crate) enum Item {
    Action {
        id: String,
        text: String,
        enabled: bool,
    },
    Check {
        id: String,
        text: String,
        enabled: bool,
        checked: bool,
    },
    Submenu {
        text: String,
        enabled: bool,
        items: Vec<Item>,
    },
    Separator,
}

/// An image in RGBA, 8 bits per channel.
#[derive(Clone, Debug, PartialEq)]
pub(crate) struct Rgba {
    width: u32,
    height: u32,
    data: Vec<u8>,
}

/// Everything a tray icon shows.
pub(crate) struct Spec {
    tooltip: String,
    title: String,
    icon: Rgba,
    menu: Vec<Item>,
    on_event: Py<PyAny>,
}

/// Reads a menu from Python: a list of `(kind, id, text, enabled, checked, items)` tuples whose
/// kind is `"item"`, `"check"`, `"submenu"` or `"separator"`.
fn items(list: &Bound<'_, PyAny>) -> PyResult<Vec<Item>> {
    let mut out = Vec::new();
    for entry in list.try_iter()? {
        let entry = entry?;
        let (kind, id, text, enabled, checked, children): (
            String,
            String,
            String,
            bool,
            bool,
            Bound<'_, PyAny>,
        ) = entry.extract()?;
        out.push(match kind.as_str() {
            "separator" => Item::Separator,
            "check" => Item::Check {
                id,
                text,
                enabled,
                checked,
            },
            "submenu" => Item::Submenu {
                text,
                enabled,
                items: items(&children)?,
            },
            _ => Item::Action { id, text, enabled },
        });
    }
    Ok(out)
}

/// The icon to show: the picture `source` (a path or the file's bytes) at most 64 pixels wide, or
/// a plain dot when there is none.
fn icon(source: Option<&Bound<'_, PyAny>>) -> PyResult<Rgba> {
    let Some(source) = source else {
        return Ok(dot());
    };
    let image = crate::imaging::decode(source)?;
    let image = if image.width() > 64 || image.height() > 64 {
        image.thumbnail(64, 64)
    } else {
        image
    };
    let rgba = image.to_rgba8();
    let (width, height) = rgba.dimensions();
    Ok(Rgba {
        width,
        height,
        data: rgba.into_raw(),
    })
}

/// A blue dot, for an icon given no picture (a tray icon must show something).
fn dot() -> Rgba {
    const SIZE: u32 = 32;
    let mut data = Vec::with_capacity((SIZE * SIZE * 4) as usize);
    let center = (SIZE as f32 - 1.0) / 2.0;
    for y in 0..SIZE {
        for x in 0..SIZE {
            let distance = ((x as f32 - center).powi(2) + (y as f32 - center).powi(2)).sqrt();
            let alpha = (center - 1.0 - distance + 0.5).clamp(0.0, 1.0);
            data.extend_from_slice(&[0x3b, 0x82, 0xf6, (alpha * 255.0) as u8]);
        }
    }
    Rgba {
        width: SIZE,
        height: SIZE,
        data,
    }
}

/// Hands an event of a tray icon to its Python callback.
fn emit(on_event: &Py<PyAny>, event: &str, value: Option<&str>) {
    Python::attach(|py| {
        if let Err(err) = on_event.call1(py, (event, value)) {
            err.print(py);
        }
    });
}

/// Shows tray icon `id` with `tooltip`, `title` (next to the icon where the system shows one),
/// `icon` (a path or bytes, or `None` for a plain dot) and `menu`, or updates it when it is
/// already shown. Raises `RuntimeError` when this system has no tray to show it in.
#[pyfunction]
#[pyo3(signature = (id, on_event, tooltip = String::new(), title = String::new(), icon = None, menu = None))]
pub fn tray_set(
    py: Python<'_>,
    id: u64,
    on_event: Py<PyAny>,
    tooltip: String,
    title: String,
    icon: Option<Bound<'_, PyAny>>,
    menu: Option<Bound<'_, PyAny>>,
) -> PyResult<()> {
    let menu = match menu {
        Some(menu) => items(&menu)?,
        None => Vec::new(),
    };
    let spec = Spec {
        tooltip,
        title,
        icon: self::icon(icon.as_ref())?,
        menu,
        on_event,
    };
    // without the GIL: the tray's own thread may be waiting for it to hand over an event
    py.detach(|| platform::set(id, spec))
        .map_err(PyRuntimeError::new_err)
}

/// Removes tray icon `id` (nothing when it is not shown).
#[pyfunction]
pub fn tray_remove(py: Python<'_>, id: u64) {
    py.detach(|| platform::remove(id));
}

/// Whether this system can show tray icons (on Linux, whether a StatusNotifierItem host such as
/// KDE's panel, Cinnamon's or GNOME's AppIndicator extension is running).
#[pyfunction]
pub fn tray_supported(py: Python<'_>) -> bool {
    py.detach(platform::supported)
}

/// Shows the icons that waited for the event loop (Windows and macOS); the app calls it on each
/// update.
pub(crate) fn flush() {
    platform::flush();
}

/// Whether some icon waits for the event loop, so the app should wake up to show it.
pub(crate) fn pending() -> bool {
    platform::pending()
}

/// Removes every icon (the app stopped).
pub(crate) fn clear() {
    platform::clear();
}

#[allow(dead_code)]
fn unsupported() -> String {
    "this system has no tray to show icons in".into()
}

// -- Linux: StatusNotifierItem over D-Bus ---------------------------------------------
#[cfg(target_os = "linux")]
mod platform {
    use super::{Item, Spec, emit};

    use ksni::blocking::{Handle, TrayMethods};
    use std::collections::HashMap;
    use std::sync::{LazyLock, Mutex};

    static TRAYS: LazyLock<Mutex<HashMap<u64, Handle<Tray>>>> =
        LazyLock::new(|| Mutex::new(HashMap::new()));

    struct Tray {
        id: u64,
        spec: Spec,
    }

    impl ksni::Tray for Tray {
        fn id(&self) -> String {
            format!("pyzed-{}-{}", std::process::id(), self.id)
        }

        fn title(&self) -> String {
            if self.spec.title.is_empty() {
                self.spec.tooltip.clone()
            } else {
                self.spec.title.clone()
            }
        }

        fn icon_pixmap(&self) -> Vec<ksni::Icon> {
            let icon = &self.spec.icon;
            // ARGB32 in network byte order
            let mut data = Vec::with_capacity(icon.data.len());
            for pixel in icon.data.chunks_exact(4) {
                data.extend_from_slice(&[pixel[3], pixel[0], pixel[1], pixel[2]]);
            }
            vec![ksni::Icon {
                width: icon.width as i32,
                height: icon.height as i32,
                data,
            }]
        }

        fn tool_tip(&self) -> ksni::ToolTip {
            ksni::ToolTip {
                title: self.spec.tooltip.clone(),
                ..Default::default()
            }
        }

        fn activate(&mut self, _x: i32, _y: i32) {
            emit(&self.spec.on_event, "click", None);
        }

        fn menu(&self) -> Vec<ksni::MenuItem<Self>> {
            menu(&self.spec.menu)
        }
    }

    fn menu(items: &[Item]) -> Vec<ksni::MenuItem<Tray>> {
        use ksni::menu::{CheckmarkItem, StandardItem, SubMenu};

        items
            .iter()
            .map(|item| match item {
                Item::Action { id, text, enabled } => {
                    let id = id.clone();
                    StandardItem {
                        label: text.clone(),
                        enabled: *enabled,
                        activate: Box::new(move |tray: &mut Tray| {
                            emit(&tray.spec.on_event, "menu", Some(&id));
                        }),
                        ..Default::default()
                    }
                    .into()
                }
                Item::Check {
                    id,
                    text,
                    enabled,
                    checked,
                } => {
                    let id = id.clone();
                    CheckmarkItem {
                        label: text.clone(),
                        enabled: *enabled,
                        checked: *checked,
                        activate: Box::new(move |tray: &mut Tray| {
                            emit(&tray.spec.on_event, "menu", Some(&id));
                        }),
                        ..Default::default()
                    }
                    .into()
                }
                Item::Submenu {
                    text,
                    enabled,
                    items,
                } => SubMenu {
                    label: text.clone(),
                    enabled: *enabled,
                    submenu: menu(items),
                    ..Default::default()
                }
                .into(),
                Item::Separator => ksni::MenuItem::Separator,
            })
            .collect()
    }

    pub(super) fn set(id: u64, spec: Spec) -> Result<(), String> {
        let mut trays = TRAYS.lock().unwrap();
        let mut spec = Some(spec);
        if let Some(handle) = trays.get(&id) {
            if handle
                .update(|tray: &mut Tray| tray.spec = spec.take().unwrap())
                .is_some()
            {
                return Ok(());
            }
            trays.remove(&id); // its service stopped: start a new one
        }
        let spec = spec.take().unwrap();
        let handle = Tray { id, spec }.spawn().map_err(|err| match err {
            ksni::Error::Watcher(_) | ksni::Error::WontShow => format!(
                "the desktop shows no tray icons ({err}); on GNOME, the AppIndicator extension adds them"
            ),
            err => format!("cannot show the tray icon: {err}"),
        })?;
        trays.insert(id, handle);
        Ok(())
    }

    pub(super) fn remove(id: u64) {
        let handle = TRAYS.lock().unwrap().remove(&id);
        if let Some(handle) = handle {
            handle.shutdown().wait();
        }
    }

    pub(super) fn supported() -> bool {
        let Ok(connection) = zbus::blocking::Connection::session() else {
            return false;
        };
        let Ok(proxy) = zbus::blocking::fdo::DBusProxy::new(&connection) else {
            return false;
        };
        proxy
            .name_has_owner("org.kde.StatusNotifierWatcher".try_into().unwrap())
            .unwrap_or(false)
    }

    pub(super) fn flush() {}

    pub(super) fn pending() -> bool {
        false
    }

    pub(super) fn clear() {
        let handles: Vec<_> = TRAYS.lock().unwrap().drain().map(|(_, h)| h).collect();
        for handle in handles {
            handle.shutdown().wait();
        }
    }
}

// -- Windows and macOS: the system's own tray --------------------------------------------------------
#[cfg(any(target_os = "windows", target_os = "macos"))]
mod platform {
    use super::{Item, Spec, emit};

    use pyo3::prelude::*;
    use std::cell::RefCell;
    use std::collections::HashMap;
    use std::sync::{LazyLock, Mutex, Once};
    use tray_icon::menu::{
        CheckMenuItem, Menu, MenuEvent, MenuId, MenuItem, PredefinedMenuItem, Submenu,
    };
    use tray_icon::{MouseButton, MouseButtonState, TrayIcon, TrayIconBuilder, TrayIconEvent};

    /// What each icon is waiting to show (`None` to be removed), until the event loop runs.
    type Pending = Vec<(u64, Option<Spec>)>;
    static PENDING: LazyLock<Mutex<Pending>> = LazyLock::new(|| Mutex::new(Vec::new()));
    /// The callback of each icon, which the system's event handlers look up.
    static CALLBACKS: LazyLock<Mutex<HashMap<u64, Py<PyAny>>>> =
        LazyLock::new(|| Mutex::new(HashMap::new()));
    static HANDLERS: Once = Once::new();

    thread_local! {
        static TRAYS: RefCell<HashMap<u64, TrayIcon>> = RefCell::new(HashMap::new());
    }

    fn callback(id: u64) -> Option<Py<PyAny>> {
        Python::attach(|py| {
            CALLBACKS
                .lock()
                .unwrap()
                .get(&id)
                .map(|cb| cb.clone_ref(py))
        })
    }

    fn install_handlers() {
        HANDLERS.call_once(|| {
            TrayIconEvent::set_event_handler(Some(|event: TrayIconEvent| {
                let (id, name) = match &event {
                    TrayIconEvent::Click {
                        id,
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } => (id, "click"),
                    TrayIconEvent::DoubleClick {
                        id,
                        button: MouseButton::Left,
                        ..
                    } => (id, "double_click"),
                    _ => return,
                };
                if let Some(cb) = id.0.parse().ok().and_then(callback) {
                    emit(&cb, name, None);
                }
            }));
            MenuEvent::set_event_handler(Some(|event: MenuEvent| {
                // menu ids are "<icon>:<item>"
                let Some((icon, item)) = event.id.0.split_once(':') else {
                    return;
                };
                if let Some(cb) = icon.parse().ok().and_then(callback) {
                    emit(&cb, "menu", Some(item));
                }
            }));
        });
    }

    fn menu(id: u64, items: &[Item]) -> Menu {
        let menu = Menu::new();
        for item in items {
            append(id, item, &|entry| {
                let _ = menu.append(entry);
            });
        }
        menu
    }

    fn append(id: u64, item: &Item, add: &dyn Fn(&dyn tray_icon::menu::IsMenuItem)) {
        let item_id = |item: &str| MenuId(format!("{id}:{item}"));
        match item {
            Item::Action {
                id: item,
                text,
                enabled,
            } => add(&MenuItem::with_id(item_id(item), text, *enabled, None)),
            Item::Check {
                id: item,
                text,
                enabled,
                checked,
            } => add(&CheckMenuItem::with_id(
                item_id(item),
                text,
                *enabled,
                *checked,
                None,
            )),
            Item::Submenu {
                text,
                enabled,
                items,
            } => {
                let submenu = Submenu::new(text, *enabled);
                for child in items {
                    append(id, child, &|entry| {
                        let _ = submenu.append(entry);
                    });
                }
                add(&submenu);
            }
            Item::Separator => add(&PredefinedMenuItem::separator()),
        }
    }

    fn show(id: u64, spec: Spec) -> Result<(), String> {
        install_handlers();
        let icon = tray_icon::Icon::from_rgba(spec.icon.data, spec.icon.width, spec.icon.height)
            .map_err(|err| err.to_string())?;
        let menu = menu(id, &spec.menu);
        Python::attach(|py| {
            CALLBACKS
                .lock()
                .unwrap()
                .insert(id, spec.on_event.clone_ref(py))
        });
        let title = (!spec.title.is_empty()).then_some(spec.title);
        TRAYS.with_borrow_mut(|trays| {
            if let Some(tray) = trays.get(&id) {
                tray.set_icon(Some(icon)).map_err(|err| err.to_string())?;
                tray.set_tooltip(Some(&spec.tooltip))
                    .map_err(|err| err.to_string())?;
                tray.set_title(title.as_ref());
                tray.set_menu(Some(Box::new(menu)));
                return Ok(());
            }
            let mut builder = TrayIconBuilder::new()
                .with_id(id.to_string())
                .with_icon(icon)
                .with_tooltip(&spec.tooltip)
                .with_menu(Box::new(menu))
                .with_menu_on_left_click(false);
            if let Some(title) = &title {
                builder = builder.with_title(title);
            }
            let tray = builder.build().map_err(|err| err.to_string())?;
            trays.insert(id, tray);
            Ok(())
        })
    }

    fn hide(id: u64) {
        TRAYS.with_borrow_mut(|trays| trays.remove(&id));
        CALLBACKS.lock().unwrap().remove(&id);
    }

    /// Whether the icon can be made now: on the app's thread while its event loop runs.
    fn ready() -> bool {
        crate::app::running() && crate::app::on_app_thread()
    }

    pub(super) fn set(id: u64, spec: Spec) -> Result<(), String> {
        if ready() {
            return show(id, spec);
        }
        PENDING.lock().unwrap().push((id, Some(spec)));
        crate::app::wake();
        Ok(())
    }

    pub(super) fn remove(id: u64) {
        if ready() {
            hide(id);
        } else {
            PENDING.lock().unwrap().push((id, None));
            crate::app::wake();
        }
    }

    pub(super) fn supported() -> bool {
        true
    }

    pub(super) fn flush() {
        let pending: Vec<_> = PENDING.lock().unwrap().drain(..).collect();
        for (id, spec) in pending {
            match spec {
                Some(spec) => {
                    let on_event = Python::attach(|py| spec.on_event.clone_ref(py));
                    if let Err(err) = show(id, spec) {
                        let message = format!("cannot show the tray icon: {err}");
                        emit(&on_event, "failed", Some(&message));
                    }
                }
                None => hide(id),
            }
        }
    }

    pub(super) fn pending() -> bool {
        !PENDING.lock().unwrap().is_empty()
    }

    pub(super) fn clear() {
        PENDING.lock().unwrap().clear();
        TRAYS.with_borrow_mut(|trays| trays.clear());
        CALLBACKS.lock().unwrap().clear();
    }
}

// -- Android and the rest: no tray -------------------------------------------------------------------
#[cfg(not(any(target_os = "linux", target_os = "windows", target_os = "macos")))]
mod platform {
    use super::Spec;

    pub(super) fn set(_id: u64, _spec: Spec) -> Result<(), String> {
        Err(super::unsupported())
    }

    pub(super) fn remove(_id: u64) {}

    pub(super) fn supported() -> bool {
        false
    }

    pub(super) fn flush() {}

    pub(super) fn pending() -> bool {
        false
    }

    pub(super) fn clear() {}
}
