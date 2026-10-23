//! The iced daemon that drives a Python `App` (Elm architecture: state, update, view).
//!
//! An app owns one or more windows. Every window is a Python object with its own
//! `view()`; messages produced inside a window are routed to that window's `update()`
//! (which, for `pyzed.Window`, forwards to the app by default).

use std::cell::RefCell;
use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use std::sync::{Arc, LazyLock, Mutex};
use std::time::Duration;

use iced::futures::channel::mpsc;
use iced::futures::{Stream, StreamExt, stream};
use iced::keyboard::{self, Key, key::Named};
use iced::widget::{column, container, scrollable, text, text_editor};
use iced::{Color, Element, Font, Length, Point, Size, Subscription, Task, Theme, window};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyCFunction, PyDict, PyList, PyString, PyTuple, PyType};

use crate::fonts;
use crate::render::{self, Caches, Ctx};
use crate::style::sans;
use crate::widget::PyMsg;

pub struct State {
    /// The `App` instance (also the main window).
    app: Py<PyAny>,
    main: Option<window::Id>,
    windows: HashMap<window::Id, Py<PyAny>>,
    /// Where each window is on the screen (its outer top-left corner), when the platform says.
    positions: HashMap<window::Id, Point>,
    /// The window whose message is being handled (commands without a window target it).
    current: Option<window::Id>,
    caches: Caches,
    themes: RefCell<HashMap<Vec<String>, Theme>>,
    /// `pz.frames` callbacks declared by the last `subscriptions()` (window, callback).
    frames: RefCell<Vec<(Option<window::Id>, PyMsg)>>,
    /// The shortest time between frames the active `pz.frames` allow (their `max_fps`).
    frame_interval: std::cell::Cell<f64>,
    /// When the previous frame was delivered (reset when no `pz.frames` is active).
    last_frame: std::cell::Cell<Option<iced::time::Instant>>,
    /// The splash screen (`App.splash`) while it is shown: it closes once the main window opens.
    splash: Option<window::Id>,
}

impl State {
    fn window(&self, id: window::Id) -> &Py<PyAny> {
        self.windows.get(&id).unwrap_or(&self.app)
    }

    fn window_id_of(&self, py: Python<'_>, obj: &Bound<'_, PyAny>) -> Option<window::Id> {
        self.windows
            .iter()
            .find(|(_, w)| w.bind(py).is(obj))
            .map(|(id, _)| *id)
    }

    fn target(&self) -> Option<window::Id> {
        self.current.or(self.main)
    }
}

#[derive(Debug, Clone)]
pub enum Message {
    Py(PyMsg),
    Input(PyMsg, String),
    Toggle(PyMsg, bool),
    Slide(PyMsg, f32),
    Call(PyMsg, PyMsg),
    Point(PyMsg, f32, f32),
    /// A common event (click, drag, focus...) from a widget wrapped with `.on(...)`.
    Event(PyMsg, Box<crate::events::EventData>),
    Editor {
        id: Arc<str>,
        action: text_editor::Action,
        on_change: Option<PyMsg>,
        on_cursor: Option<PyMsg>,
    },
    EditorPage {
        id: Arc<str>,
        down: bool,
        select: bool,
        on_cursor: Option<PyMsg>,
    },
    EditorIndent {
        id: Arc<str>,
        key: crate::editor::EditKey,
        indent: Option<crate::editor::Indent>,
        pairs: bool,
        on_change: Option<PyMsg>,
        on_cursor: Option<PyMsg>,
    },
    EditorFold {
        id: Arc<str>,
        op: crate::editor::FoldOp,
        on_cursor: Option<PyMsg>,
    },
    /// A named editor action (multiple cursors, undo, line operations...).
    EditorAction {
        id: Arc<str>,
        action: crate::editor::EditorAction,
        ctx: Arc<crate::editor::ActionContext>,
    },
    /// Replaces real ranges `(line, column, end_line, end_column)` (0-based) with texts.
    EditorReplace {
        id: Arc<str>,
        edits: Arc<Vec<crate::editor::RangeEdit>>,
    },
    /// Scrolls the editor's scrollable (with this id) to `y` (from the minimap).
    EditorScroll {
        id: String,
        y: f32,
    },
    Scrolled(PyMsg, scrollable::Viewport),
    /// The mouse rests on a word of a code editor (`None`: it left the word).
    Hover(PyMsg, Option<crate::editor::Hit>),
    /// A code editor laid out for the first time with its cursor set: scroll the cursor into view.
    EditorReveal(Arc<str>),
    Key(String),
    /// A key was released (its name without modifiers, e.g. `"left"`).
    KeyUp(String),
    /// The display is about to draw a new frame (`pz.frames`).
    Frame(iced::time::Instant),
    /// Tab or Shift+Tab (`back`) that no widget handled: `on_key` first, then focus moves.
    TabKey(String, bool),
    /// An arrow no widget used, with `App.arrow_focus`: `on_key` first, then the focus moves.
    ArrowKey(String, crate::focus::Direction),
    /// Android's back button: `on_back()` first, then the app goes to the background.
    #[cfg(target_os = "android")]
    BackKey,
    /// The system bars or the soft keyboard moved: the views keep clear of them again.
    #[cfg(target_os = "android")]
    Insets,
    /// A message produced inside the given window.
    Windowed(window::Id, Box<Message>),
    WindowOpened(window::Id),
    /// The splash screen has been shown for its `duration`: open the main window.
    SplashDone,
    CloseRequested(window::Id),
    WindowClosed(window::Id),
    WindowResized(window::Id, Size),
    /// Whether the window is maximized now (asked after it opens or changes size).
    WindowMaximized(window::Id, bool),
    /// The window gained (`true`) or lost the keyboard focus.
    WindowFocused(window::Id, bool),
    /// A press on the border of a window without decorations (`window_edges`).
    DragResize(window::Direction),
    /// A window was opened (with its size) or moved to this screen position (`None` on Wayland).
    WindowPlaced(window::Id, Option<Point>, Option<Size>),
    SystemTheme(iced::theme::Mode),
    /// Files dragged from the system over a window: the hook it calls (`on_file_hover`,
    /// `on_file_drop` or `on_file_leave`) and the file's path (none when the drag leaves).
    FileDrag(&'static str, Option<String>),
    /// What a callback already run by [`quiet`] returned: dispatched like any callback result.
    Done(PyMsg),
    Noop,
}

impl Message {
    fn in_window(self, id: window::Id) -> Message {
        match self {
            Message::Noop | Message::Windowed(..) => self,
            other => Message::Windowed(id, Box::new(other)),
        }
    }
}

// ---------------------------------------------------------------------------
// Quiet messages: callbacks that change nothing on screen skip the rebuild.
// ---------------------------------------------------------------------------

/// `pz.UNCHANGED`: returned by a callback (or `update`) that changed nothing the views show.
#[pyclass(frozen, module = "pyzed", name = "Unchanged")]
pub struct Unchanged;

#[pymethods]
impl Unchanged {
    fn __repr__(&self) -> &'static str {
        "pz.UNCHANGED"
    }
}

fn is_unchanged(value: &Bound<'_, PyAny>) -> bool {
    value.cast::<Unchanged>().is_ok()
}

/// What [`quiet`] needs of the [`State`] to run a callback as `update` would (it runs outside it).
struct Targets {
    app: Py<PyAny>,
    main: Option<window::Id>,
    windows: HashMap<window::Id, Py<PyAny>>,
    positions: HashMap<window::Id, Point>,
}

thread_local! {
    static TARGETS: RefCell<Option<Targets>> = const { RefCell::new(None) };
}

fn sync_targets(py: Python<'_>, state: &State) {
    let targets = Targets {
        app: state.app.clone_ref(py),
        main: state.main,
        windows: state
            .windows
            .iter()
            .map(|(id, obj)| (*id, obj.clone_ref(py)))
            .collect(),
        positions: state.positions.clone(),
    };
    TARGETS.with(|t| *t.borrow_mut() = Some(targets));
}

// ---------------------------------------------------------------------------
// Isolated windows (`Window.isolated`)
// ---------------------------------------------------------------------------

/// The windows whose messages were handled since the last rebuild, the windows that asked to be
/// drawn again (`Window.refresh()`, from any thread, by object address) and whether something
/// whose window is unknown happened (`pz.post`, which also brings async results and lifecycle
/// hooks): then every window is rebuilt.
#[derive(Default)]
struct Touched {
    windows: std::collections::HashSet<window::Id>,
    refreshed: Vec<usize>,
    all: bool,
}

static TOUCHED: LazyLock<Mutex<Touched>> = LazyLock::new(Mutex::default);

/// The last drawing of an isolated window: its root widget and what else it depended on.
struct Drawn {
    root: Py<crate::widget::Widget>,
    epoch: Py<PyAny>,
    palette: Option<Vec<String>>,
}

thread_local! {
    static DRAWN: RefCell<HashMap<window::Id, Drawn>> = RefCell::new(HashMap::new());
    /// The windows `unchanged` let keep their drawing in the rebuild that follows it.
    static KEEP: RefCell<std::collections::HashSet<window::Id>> =
        RefCell::new(std::collections::HashSet::new());
}

fn touch(id: window::Id) {
    TOUCHED.lock().unwrap().windows.insert(id);
}

fn isolated(obj: &Bound<'_, PyAny>) -> bool {
    obj.getattr("isolated")
        .and_then(|v| v.is_truthy())
        .unwrap_or(false)
}

/// What every isolated view depends on besides its window (language, styles, reloaded code).
fn isolation_epoch(py: Python<'_>) -> Option<Py<PyAny>> {
    static EPOCH: pyo3::sync::PyOnceLock<Py<PyAny>> = pyo3::sync::PyOnceLock::new();
    let epoch = EPOCH
        .get_or_try_init(py, || {
            py.import("pyzed.app")
                .and_then(|m| m.getattr("_isolation_epoch"))
                .map(Bound::unbind)
        })
        .ok()?;
    epoch.bind(py).call0().ok().map(Bound::unbind)
}

/// Asked by iced after each update: the isolated windows that no message reached, that did not
/// call `refresh()` and whose theme, language and styles are the same keep their layout and are
/// not redrawn; their `view()` is not called either.
fn unchanged(ids: &[window::Id]) -> Vec<window::Id> {
    let touched = std::mem::take(&mut *TOUCHED.lock().unwrap());
    KEEP.with(|keep| keep.borrow_mut().clear());
    if touched.all || DRAWN.with(|drawn| drawn.borrow().is_empty()) {
        return Vec::new();
    }
    let kept: Vec<window::Id> = Python::attach(|py| {
        let Some(epoch) = isolation_epoch(py) else {
            return Vec::new();
        };
        TARGETS.with(|targets| {
            let targets = targets.borrow();
            let Some(targets) = targets.as_ref() else {
                return Vec::new();
            };
            DRAWN.with(|drawn| {
                let drawn = drawn.borrow();
                ids.iter()
                    .copied()
                    .filter(|id| !touched.windows.contains(id))
                    .filter(|id| {
                        let (Some(last), Some(obj)) = (drawn.get(id), targets.windows.get(id))
                        else {
                            return false;
                        };
                        let obj = obj.bind(py);
                        !touched.refreshed.contains(&(obj.as_ptr() as usize))
                            && isolated(obj)
                            && last.epoch.bind(py).eq(epoch.bind(py)).unwrap_or(false)
                            && palette_key(obj) == last.palette
                    })
                    .collect()
            })
        })
    });
    KEEP.with(|keep| keep.borrow_mut().extend(kept.iter().copied()));
    kept
}

/// The root widget of a window's view: the last one when [`unchanged`] kept it, otherwise a new
/// one from Python (remembered when the window is isolated).
fn view_root(
    py: Python<'_>,
    id: window::Id,
    obj: &Bound<'_, PyAny>,
) -> PyResult<Py<crate::widget::Widget>> {
    if KEEP.with(|keep| keep.borrow_mut().remove(&id))
        && let Some(root) =
            DRAWN.with(|drawn| drawn.borrow().get(&id).map(|d| d.root.clone_ref(py)))
    {
        return Ok(root);
    }
    let method = if obj.hasattr("__pyzed_view__").unwrap_or(false) {
        "__pyzed_view__"
    } else {
        "view"
    };
    let root = obj
        .call_method0(method)
        .and_then(|w| crate::widget::child(&w))?;
    DRAWN.with(|drawn| {
        let mut drawn = drawn.borrow_mut();
        match isolation_epoch(py).filter(|_| isolated(obj)) {
            Some(epoch) => {
                drawn.insert(
                    id,
                    Drawn {
                        root: root.clone_ref(py),
                        epoch,
                        palette: palette_key(obj),
                    },
                );
            }
            None => {
                drawn.remove(&id);
            }
        }
    });
    Ok(root)
}

/// Builds every window again on the next update, isolated ones included (an image finished
/// decoding on a worker thread). Safe from any thread.
pub(crate) fn refresh_all() {
    TOUCHED.lock().unwrap().all = true;
    wake();
}

/// `Window.refresh()`: draws an isolated window again after something outside it changed what
/// it shows. Safe from any thread.
#[pyfunction]
pub fn refresh_window(window: &Bound<'_, PyAny>) {
    TOUCHED
        .lock()
        .unwrap()
        .refreshed
        .push(window.as_ptr() as usize);
    wake();
}

/// The GPU (or `"CPU"`) and the graphics API that draw the windows, once the first one is open.
#[pyfunction]
pub fn renderer_info() -> Option<(String, String)> {
    iced_winit::quiet::graphics()
}

/// One monitor for `pz.monitors()`: its name, place and size on the desktop in logical pixels,
/// scale, refresh rate in hertz and whether it is the primary one.
#[derive(Clone, Debug)]
struct MonitorInfo {
    name: Option<String>,
    position: (f32, f32),
    size: (f32, f32),
    scale: f64,
    refresh_rate: Option<f64>,
    primary: bool,
}

/// The monitors seen when the app started or last asked (`Command.list_monitors`).
static MONITORS: Mutex<Vec<MonitorInfo>> = Mutex::new(Vec::new());

/// The monitors as dictionaries (`index`, `name`, `x`, `y`, `width`, `height`, `scale`,
/// `refresh_rate`, `primary`); empty before the first window opens.
#[pyfunction]
pub fn monitors(py: Python<'_>) -> PyResult<Bound<'_, PyList>> {
    monitor_dicts(py, &MONITORS.lock().unwrap())
}

fn monitor_dicts<'py>(py: Python<'py>, list: &[MonitorInfo]) -> PyResult<Bound<'py, PyList>> {
    let out = PyList::empty(py);
    for (index, monitor) in list.iter().enumerate() {
        let item = PyDict::new(py);
        item.set_item("index", index)?;
        item.set_item("name", monitor.name.as_deref())?;
        item.set_item("x", monitor.position.0)?;
        item.set_item("y", monitor.position.1)?;
        item.set_item("width", monitor.size.0)?;
        item.set_item("height", monitor.size.1)?;
        item.set_item("scale", monitor.scale)?;
        item.set_item("refresh_rate", monitor.refresh_rate)?;
        item.set_item("primary", monitor.primary)?;
        out.append(item)?;
    }
    Ok(out)
}

/// Reads the monitors into [`MONITORS`] and calls `then(monitors)` when given.
fn list_monitors(then: Option<PyMsg>) -> Task<Message> {
    window::list_monitors().map(move |list| {
        let infos: Vec<MonitorInfo> = list
            .iter()
            .map(|monitor| {
                let size = monitor.size();
                let position = monitor.position();
                MonitorInfo {
                    name: monitor.name().map(str::to_owned),
                    position: (position.x, position.y),
                    size: (size.width, size.height),
                    scale: monitor.scale_factor(),
                    refresh_rate: monitor
                        .refresh_rate_millihertz()
                        .map(|mhz| f64::from(mhz) / 1000.0),
                    primary: monitor.is_primary(),
                }
            })
            .collect();
        *MONITORS.lock().unwrap() = infos.clone();
        match &then {
            Some(then) => Python::attach(|py| match monitor_dicts(py, &infos) {
                Ok(list) => {
                    let monitors = py
                        .import("pyzed.app")
                        .and_then(|m| m.call_method1("_monitors", (list,)));
                    match monitors {
                        Ok(value) => Message::Call(then.clone(), PyMsg::new(&value)),
                        Err(err) => {
                            err.print(py);
                            Message::Noop
                        }
                    }
                }
                Err(_) => Message::Noop,
            }),
            None => Message::Noop,
        }
    })
}

/// `Window.level` and `Command.set_window_level`: "normal", "top" or "bottom".
fn window_level(level: &str) -> PyResult<window::Level> {
    match level {
        "normal" => Ok(window::Level::Normal),
        "top" | "always_on_top" => Ok(window::Level::AlwaysOnTop),
        "bottom" | "always_on_bottom" => Ok(window::Level::AlwaysOnBottom),
        other => Err(PyValueError::new_err(format!(
            "invalid window level {other:?}: use \"normal\", \"top\" or \"bottom\""
        ))),
    }
}

/// Runs a pointer callback (`on_move`, `on_enter`, `on_exit`...) as soon as its message arrives,
/// before iced rebuilds the windows: if it returns `pz.UNCHANGED` the message is dropped and, when
/// the whole batch was, nothing is rebuilt nor redrawn (a mouse moving over a big view costs
/// nothing). Anything else becomes [`Message::Done`], handled in order by `update`.
fn quiet(message: &mut dyn std::any::Any) -> bool {
    let Some(message) = message.downcast_mut::<Message>() else {
        return false;
    };
    let (window, inner) = match message {
        Message::Windowed(id, inner) => (Some(*id), &mut **inner),
        other => (None, other),
    };
    if !matches!(
        inner,
        Message::Py(_) | Message::Point(..) | Message::Event(..)
    ) {
        return false;
    }
    Python::attach(|py| {
        let found = TARGETS.with(|t| {
            t.borrow().as_ref().map(|targets| {
                let target = window
                    .and_then(|id| targets.windows.get(&id))
                    .unwrap_or(&targets.app)
                    .clone_ref(py);
                let origin = window
                    .or(targets.main)
                    .and_then(|id| targets.positions.get(&id).copied());
                (target, origin)
            })
        });
        let Some((target, origin)) = found else {
            return false;
        };
        let target = target.bind(py);
        let result = match &*inner {
            Message::Py(msg) => dispatch(target, msg.0.bind(py)),
            Message::Point(cb, x, y) => callback(target, cb.0.bind(py), (*x, *y)),
            Message::Event(cb, data) => deliver_event(target, cb.0.bind(py), data, origin),
            _ => return false,
        };
        match result {
            Ok(value) if is_unchanged(&value) => true,
            Ok(value) => {
                *inner = Message::Done(PyMsg::new(&value));
                false
            }
            Err(err) => {
                err.print(py);
                *inner = Message::Noop;
                false
            }
        }
    })
}

// ---------------------------------------------------------------------------
// Commands: values returned from `update()` that ask the runtime to do something.
// ---------------------------------------------------------------------------

enum CommandKind {
    Exit,
    Focus(String),
    /// Next (`true`) or previous field of the current window.
    FocusNext(bool),
    FocusDirection(crate::focus::Direction),
    SelectAll(String),
    SetEditorText(String, String),
    SetEditorCursor(String, usize, usize),
    FoldEditor(String, crate::editor::FoldOp),
    EditorAction(String, crate::editor::EditorAction),
    SelectEditorRanges(String, Vec<crate::editor::TextRange>),
    ReplaceEditorRanges(String, Vec<crate::editor::RangeEdit>),
    Batch(Vec<Py<Command>>),
    ListMonitors(Option<PyMsg>),
    Message(PyMsg),
    Perform(PyMsg, Option<PyMsg>),
    ScrollToEnd(String),
    ScrollTo(String, f32, f32),
    OpenWindow(PyMsg),
    CloseWindow(Option<PyMsg>),
    Window(WindowOp, Option<PyMsg>),
    CopyToClipboard(String),
    ReadClipboard(PyMsg),
    ReadClipboardImage(PyMsg),
    PickFiles(PickFiles),
}

/// What `Command.pick_files` asks the system file dialog for.
#[cfg_attr(target_os = "android", allow(dead_code))]
struct PickFiles {
    then: PyMsg,
    title: Option<String>,
    filters: Vec<(String, Vec<String>)>,
    directory: Option<String>,
    multiple: bool,
    folder: bool,
    /// Asks for a file to save (with this suggested name) instead of picking existing ones.
    save: Option<String>,
}

#[derive(Clone, Copy)]
enum WindowOp {
    Drag,
    DragResize(window::Direction),
    Maximize(bool),
    SystemMenu,
    Minimize,
    ToggleMaximize,
    /// Windowed with `None`; fullscreen on a monitor (maybe exclusive) otherwise.
    Fullscreen(Option<window::Fullscreen>),
    Level(window::Level),
    HideCursor(bool),
    Resize(f32, f32),
    Move(f32, f32),
    Focus,
}

/// Side effects returned from `App.update` (or from a callback): `return Command.focus("search")`.
///
/// Commands are values: build them with the static methods below and return them (or a
/// list of them) from `update`, `on_start`, `on_key` or any widget callback.
#[pyclass(module = "pyzed._core", frozen)]
pub struct Command {
    kind: CommandKind,
}

fn cmd(kind: CommandKind) -> Command {
    Command { kind }
}

#[pymethods]
impl Command {
    /// Closes the application (every window).
    #[staticmethod]
    fn exit() -> Self {
        cmd(CommandKind::Exit)
    }

    /// Focuses the `text_input` (or editor) with the given `id`.
    #[staticmethod]
    fn focus(id: String) -> Self {
        cmd(CommandKind::Focus(id))
    }

    /// Moves the keyboard focus to the next field of the window (what Tab does), wrapping around.
    #[staticmethod]
    fn focus_next() -> Self {
        cmd(CommandKind::FocusNext(true))
    }

    /// Moves the keyboard focus to the previous field of the window (what Shift+Tab does).
    #[staticmethod]
    fn focus_previous() -> Self {
        cmd(CommandKind::FocusNext(false))
    }

    /// Moves the keyboard focus to the nearest field `"up"`, `"down"`, `"left"` or `"right"`
    /// on the screen (TV remotes, rotary knobs; `App.arrow_focus` does it with the arrows).
    #[staticmethod]
    fn focus_direction(direction: &str) -> PyResult<Self> {
        crate::focus::Direction::parse(direction)
            .map(|d| cmd(CommandKind::FocusDirection(d)))
            .ok_or_else(|| {
                PyValueError::new_err(format!(
                    "invalid direction {direction:?}: use \"up\", \"down\", \"left\" or \"right\""
                ))
            })
    }

    /// Focuses the `text_input` with the given `id` and selects all its text.
    #[staticmethod]
    fn select_all(id: String) -> Self {
        cmd(CommandKind::SelectAll(id))
    }

    /// Replaces the contents of the `code_editor` with the given `id`.
    #[staticmethod]
    fn set_editor_text(id: String, text: String) -> Self {
        cmd(CommandKind::SetEditorText(id, text))
    }

    /// Moves the cursor of the `code_editor` with the given `id` (1-based line and column)
    /// and scrolls it into view.
    #[staticmethod]
    fn set_editor_cursor(id: String, line: usize, column: usize) -> Self {
        cmd(CommandKind::SetEditorCursor(id, line, column))
    }

    /// Folds every block of the `code_editor` with the given `id` (`fold=False` unfolds them).
    #[staticmethod]
    #[pyo3(signature = (id, fold=true))]
    fn fold_all(id: String, fold: bool) -> Self {
        use crate::editor::FoldOp;
        cmd(CommandKind::FoldEditor(
            id,
            if fold {
                FoldOp::FoldAll
            } else {
                FoldOp::UnfoldAll
            },
        ))
    }

    /// Folds the block that starts at `line` (1-based) of the `code_editor` with the given
    /// `id` (`fold=False` unfolds it).
    #[staticmethod]
    #[pyo3(signature = (id, line, fold=true))]
    fn fold_line(id: String, line: usize, fold: bool) -> Self {
        cmd(CommandKind::FoldEditor(
            id,
            crate::editor::FoldOp::Line(line.saturating_sub(1), fold),
        ))
    }

    /// Runs the editor action `name` (Zed's name in snake case, like `"undo"`,
    /// `"select_next"`, `"move_line_up"` or `"toggle_comments"`) in the `code_editor` with the
    /// given `id`, as if its key was pressed. `Command.editor_actions()` lists them.
    #[staticmethod]
    fn editor_action(id: String, name: &str) -> PyResult<Self> {
        let action = crate::editor::EditorAction::parse(name).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!("unknown editor action {name:?}"))
        })?;
        Ok(cmd(CommandKind::EditorAction(id, action)))
    }

    /// The names of the actions `Command.editor_action` runs.
    #[staticmethod]
    fn editor_actions() -> Vec<&'static str> {
        crate::editor::EditorAction::ALL
            .iter()
            .map(|a| a.name())
            .collect()
    }

    /// Selects ranges of the `code_editor` with the given `id`, one cursor each (the first is
    /// the primary one): `(line, column, end_line, end_column)`, 1-based with exclusive ends.
    #[staticmethod]
    fn select_editor_ranges(id: String, ranges: Vec<crate::editor::TextRange>) -> Self {
        cmd(CommandKind::SelectEditorRanges(id, zero_based(ranges)))
    }

    /// Replaces ranges of the `code_editor` with the given `id` with texts, as one undo step
    /// (it calls the editor's `on_change`): `[((line, column, end_line, end_column), text)]`,
    /// 1-based with exclusive ends.
    #[staticmethod]
    fn replace_editor_ranges(id: String, edits: Vec<crate::editor::RangeEdit>) -> Self {
        let (ranges, texts): (Vec<_>, Vec<_>) = edits.into_iter().unzip();
        let edits = zero_based(ranges).into_iter().zip(texts).collect();
        cmd(CommandKind::ReplaceEditorRanges(id, edits))
    }

    /// Scrolls the `scrollable` with the given `id` to its end.
    #[staticmethod]
    fn scroll_to_end(id: String) -> Self {
        cmd(CommandKind::ScrollToEnd(id))
    }

    /// Scrolls the `scrollable` with the given `id` to an absolute offset in pixels.
    #[staticmethod]
    #[pyo3(signature = (id, x=0.0, y=0.0))]
    fn scroll_to(id: String, x: f32, y: f32) -> Self {
        cmd(CommandKind::ScrollTo(id, x, y))
    }

    /// Runs several commands.
    #[staticmethod]
    fn batch(commands: Vec<Py<Command>>) -> Self {
        cmd(CommandKind::Batch(commands))
    }

    /// Feeds `message` back into `update` on the next tick.
    #[staticmethod]
    fn message(message: &Bound<'_, PyAny>) -> Self {
        cmd(CommandKind::Message(PyMsg::new(message)))
    }

    /// Runs `function()` in the background and calls `then(result)` on the UI thread.
    ///
    /// `function` may be a regular function (run in a worker thread), an `async def`
    /// coroutine function (run on Pyzed's asyncio loop), or return a generator / async
    /// generator, in which case `then` is called once per yielded value. An already
    /// created coroutine or generator (`fetch(url)` rather than `fetch`) works too.
    #[staticmethod]
    #[pyo3(signature = (function, then=None))]
    fn perform(function: &Bound<'_, PyAny>, then: Option<Bound<'_, PyAny>>) -> Self {
        cmd(CommandKind::Perform(
            PyMsg::new(function),
            PyMsg::maybe(&then),
        ))
    }

    /// Opens a new window for the given `pyzed.Window` instance.
    #[staticmethod]
    fn open_window(window: &Bound<'_, PyAny>) -> Self {
        cmd(CommandKind::OpenWindow(PyMsg::new(window)))
    }

    /// Closes `window` (a `pyzed.Window`), or the window that produced the message.
    #[staticmethod]
    #[pyo3(signature = (window=None))]
    fn close_window(window: Option<Bound<'_, PyAny>>) -> Self {
        cmd(CommandKind::CloseWindow(PyMsg::maybe(&window)))
    }

    /// Starts moving the window with the mouse (use it on press of a custom title bar).
    #[staticmethod]
    #[pyo3(signature = (window=None))]
    fn drag_window(window: Option<Bound<'_, PyAny>>) -> Self {
        cmd(CommandKind::Window(WindowOp::Drag, PyMsg::maybe(&window)))
    }

    /// Starts resizing the window with the mouse from one of its edges or corners:
    /// `direction` is "n", "s", "e", "w", "ne", "nw", "se" or "sw" (use it on press of
    /// a custom border; `ui.window_frame` already does).
    #[staticmethod]
    #[pyo3(signature = (direction, window=None))]
    fn drag_resize_window(direction: &str, window: Option<Bound<'_, PyAny>>) -> PyResult<Self> {
        let direction = match direction {
            "n" => window::Direction::North,
            "s" => window::Direction::South,
            "e" => window::Direction::East,
            "w" => window::Direction::West,
            "ne" => window::Direction::NorthEast,
            "nw" => window::Direction::NorthWest,
            "se" => window::Direction::SouthEast,
            "sw" => window::Direction::SouthWest,
            other => {
                return Err(PyValueError::new_err(format!(
                    "invalid direction {other:?}: use \"n\", \"s\", \"e\", \"w\", \"ne\", \"nw\", \"se\" or \"sw\""
                )));
            }
        };
        Ok(cmd(CommandKind::Window(
            WindowOp::DragResize(direction),
            PyMsg::maybe(&window),
        )))
    }

    /// Maximizes the window (or restores it with `maximized=False`).
    #[staticmethod]
    #[pyo3(signature = (maximized=true, window=None))]
    fn maximize_window(maximized: bool, window: Option<Bound<'_, PyAny>>) -> Self {
        cmd(CommandKind::Window(
            WindowOp::Maximize(maximized),
            PyMsg::maybe(&window),
        ))
    }

    /// Shows the system's window menu (move, size, close...) under the pointer.
    /// Only Windows has one; elsewhere it does nothing.
    #[staticmethod]
    #[pyo3(signature = (window=None))]
    fn show_window_menu(window: Option<Bound<'_, PyAny>>) -> Self {
        cmd(CommandKind::Window(
            WindowOp::SystemMenu,
            PyMsg::maybe(&window),
        ))
    }

    /// Minimizes the window.
    #[staticmethod]
    #[pyo3(signature = (window=None))]
    fn minimize_window(window: Option<Bound<'_, PyAny>>) -> Self {
        cmd(CommandKind::Window(
            WindowOp::Minimize,
            PyMsg::maybe(&window),
        ))
    }

    /// Maximizes the window, or restores it if it is already maximized.
    #[staticmethod]
    #[pyo3(signature = (window=None))]
    fn toggle_maximize_window(window: Option<Bound<'_, PyAny>>) -> Self {
        cmd(CommandKind::Window(
            WindowOp::ToggleMaximize,
            PyMsg::maybe(&window),
        ))
    }

    /// Switches the window between fullscreen and windowed mode. `monitor` (an index of
    /// `pz.monitors()`) moves it to that screen; `exclusive=True` takes the screen over with its
    /// own video mode (lower latency on Windows and X11; Wayland keeps a borderless window).
    #[staticmethod]
    #[pyo3(signature = (fullscreen=true, window=None, monitor=None, exclusive=false))]
    fn set_fullscreen(
        fullscreen: bool,
        window: Option<Bound<'_, PyAny>>,
        monitor: Option<usize>,
        exclusive: bool,
    ) -> Self {
        let mode = fullscreen.then_some(window::Fullscreen {
            monitor: monitor.map(window::MonitorIndex),
            exclusive,
        });
        cmd(CommandKind::Window(
            WindowOp::Fullscreen(mode),
            PyMsg::maybe(&window),
        ))
    }

    /// Keeps the window above (`"top"`) or below (`"bottom"`) the others, or back to
    /// `"normal"`.
    #[staticmethod]
    #[pyo3(signature = (level, window=None))]
    fn set_window_level(level: &str, window: Option<Bound<'_, PyAny>>) -> PyResult<Self> {
        Ok(cmd(CommandKind::Window(
            WindowOp::Level(window_level(level)?),
            PyMsg::maybe(&window),
        )))
    }

    /// Hides the pointer over the window whatever the widgets ask (touch panels, kiosks), or
    /// shows it again with `hidden=False`.
    #[staticmethod]
    #[pyo3(signature = (hidden=true, window=None))]
    fn hide_cursor(hidden: bool, window: Option<Bound<'_, PyAny>>) -> Self {
        cmd(CommandKind::Window(
            WindowOp::HideCursor(hidden),
            PyMsg::maybe(&window),
        ))
    }

    /// Asks the system for its monitors and calls `then(monitors)` with a list of
    /// `pz.Monitor` (also kept for `pz.monitors()`).
    #[staticmethod]
    fn list_monitors(then: &Bound<'_, PyAny>) -> Self {
        cmd(CommandKind::ListMonitors(Some(PyMsg::new(then))))
    }

    /// Resizes the window to `width` x `height` logical pixels.
    #[staticmethod]
    #[pyo3(signature = (width, height, window=None))]
    fn resize_window(width: f32, height: f32, window: Option<Bound<'_, PyAny>>) -> Self {
        cmd(CommandKind::Window(
            WindowOp::Resize(width, height),
            PyMsg::maybe(&window),
        ))
    }

    /// Moves the window to the given screen position.
    #[staticmethod]
    #[pyo3(signature = (x, y, window=None))]
    fn move_window(x: f32, y: f32, window: Option<Bound<'_, PyAny>>) -> Self {
        cmd(CommandKind::Window(
            WindowOp::Move(x, y),
            PyMsg::maybe(&window),
        ))
    }

    /// Brings the window to the front and focuses it.
    #[staticmethod]
    #[pyo3(signature = (window=None))]
    fn focus_window(window: Option<Bound<'_, PyAny>>) -> Self {
        cmd(CommandKind::Window(WindowOp::Focus, PyMsg::maybe(&window)))
    }

    /// Copies `text` to the system clipboard.
    #[staticmethod]
    fn copy(text: String) -> Self {
        cmd(CommandKind::CopyToClipboard(text))
    }

    /// Reads the system clipboard and calls `then(text)` (an empty string if it is empty).
    #[staticmethod]
    fn paste(then: &Bound<'_, PyAny>) -> Self {
        cmd(CommandKind::ReadClipboard(PyMsg::new(then)))
    }

    /// Reads an image from the system clipboard (a screenshot, a copied picture) and calls
    /// `then(png)` with its PNG bytes, or `then(None)` when the clipboard holds no image.
    #[staticmethod]
    fn paste_image(then: &Bound<'_, PyAny>) -> Self {
        cmd(CommandKind::ReadClipboardImage(PyMsg::new(then)))
    }

    /// Opens the system's file dialog and calls `then(paths)` with the chosen paths (an empty
    /// list when it is cancelled).
    ///
    /// `filters` is a list of `(name, extensions)` pairs, like `[("Images", ["png", "jpg"])]`;
    /// `directory` is the folder it opens in; `multiple=False` picks one file and `folder=True`
    /// picks folders.
    #[staticmethod]
    #[pyo3(signature = (then, *, title=None, filters=None, directory=None, multiple=true, folder=false))]
    fn pick_files(
        then: &Bound<'_, PyAny>,
        title: Option<String>,
        filters: Option<Vec<(String, Vec<String>)>>,
        directory: Option<String>,
        multiple: bool,
        folder: bool,
    ) -> Self {
        cmd(CommandKind::PickFiles(PickFiles {
            then: PyMsg::new(then),
            title,
            filters: filters.unwrap_or_default(),
            directory,
            multiple,
            folder,
            save: None,
        }))
    }

    /// Opens the system's "Save as" dialog and calls `then(paths)` with the chosen path in a
    /// list (an empty list when it is cancelled).
    ///
    /// `file_name` is the name it suggests; `filters` and `directory` work as in `pick_files`.
    #[staticmethod]
    #[pyo3(signature = (then, *, title=None, filters=None, directory=None, file_name=String::new()))]
    fn save_file(
        then: &Bound<'_, PyAny>,
        title: Option<String>,
        filters: Option<Vec<(String, Vec<String>)>>,
        directory: Option<String>,
        file_name: String,
    ) -> Self {
        cmd(CommandKind::PickFiles(PickFiles {
            then: PyMsg::new(then),
            title,
            filters: filters.unwrap_or_default(),
            directory,
            multiple: false,
            folder: false,
            save: Some(file_name),
        }))
    }

    fn __repr__(&self) -> &'static str {
        match self.kind {
            CommandKind::Exit => "Command.exit()",
            CommandKind::Focus(_) => "Command.focus(...)",
            CommandKind::FocusNext(true) => "Command.focus_next()",
            CommandKind::FocusNext(false) => "Command.focus_previous()",
            CommandKind::FocusDirection(_) => "Command.focus_direction(...)",
            CommandKind::SelectAll(_) => "Command.select_all(...)",
            CommandKind::SetEditorText(..) => "Command.set_editor_text(...)",
            CommandKind::SetEditorCursor(..) => "Command.set_editor_cursor(...)",
            CommandKind::FoldEditor(..) => "Command.fold_line(...)",
            CommandKind::EditorAction(..) => "Command.editor_action(...)",
            CommandKind::SelectEditorRanges(..) => "Command.select_editor_ranges(...)",
            CommandKind::ReplaceEditorRanges(..) => "Command.replace_editor_ranges(...)",
            CommandKind::Batch(_) => "Command.batch(...)",
            CommandKind::ListMonitors(_) => "Command.list_monitors(...)",
            CommandKind::Message(_) => "Command.message(...)",
            CommandKind::Perform(..) => "Command.perform(...)",
            CommandKind::ScrollToEnd(_) => "Command.scroll_to_end(...)",
            CommandKind::ScrollTo(..) => "Command.scroll_to(...)",
            CommandKind::OpenWindow(_) => "Command.open_window(...)",
            CommandKind::CloseWindow(_) => "Command.close_window(...)",
            CommandKind::Window(..) => "Command.<window operation>(...)",
            CommandKind::CopyToClipboard(_) => "Command.copy(...)",
            CommandKind::ReadClipboard(_) => "Command.paste(...)",
            CommandKind::ReadClipboardImage(_) => "Command.paste_image(...)",
            CommandKind::PickFiles(ref p) if p.save.is_some() => "Command.save_file(...)",
            CommandKind::PickFiles(_) => "Command.pick_files(...)",
        }
    }
}

/// Whether `value` is a coroutine, awaitable, generator or async generator.
fn is_deferred(value: &Bound<'_, PyAny>) -> bool {
    // The usual messages and return values (None, strings, numbers, tuples) without the
    // failing attribute lookups below, which each raise and discard an AttributeError.
    if value.is_none()
        || value.is_instance_of::<PyString>()
        || value.is_instance_of::<pyo3::types::PyInt>()
        || value.is_instance_of::<pyo3::types::PyFloat>()
        || value.is_instance_of::<PyTuple>()
        || value.is_instance_of::<PyDict>()
    {
        return false;
    }
    value.hasattr("__await__").unwrap_or(false)
        || value.hasattr("__anext__").unwrap_or(false)
        || (value.hasattr("send").unwrap_or(false) && value.hasattr("__next__").unwrap_or(false))
}

/// Runs `function()` (or awaits / iterates `value`) off the UI thread, turning every
/// produced value into a message.
fn background(source: PyMsg, call: bool, then: Option<PyMsg>) -> Task<Message> {
    let (sender, receiver) = mpsc::unbounded::<Message>();
    let has_then = then.is_some();
    std::thread::spawn(move || {
        Python::attach(|py| {
            let source = source.0.bind(py);
            let value = if call {
                source.call0()
            } else {
                Ok(source.clone())
            };
            let emit = PyCFunction::new_closure(
                py,
                None,
                None,
                move |args: &Bound<'_, PyTuple>, _kwargs: Option<&Bound<'_, PyDict>>| {
                    let item = args.get_item(0)?;
                    let message = match &then {
                        Some(then) => Message::Call(then.clone(), PyMsg::new(&item)),
                        None => Message::Py(PyMsg::new(&item)),
                    };
                    sender
                        .unbounded_send(message)
                        .map_err(|_| PyRuntimeError::new_err("the app has stopped"))
                },
            );
            let result = value.and_then(|value| {
                let emit = emit?;
                // With a `then`, a function that returns nothing still calls it (with None).
                let kwargs = PyDict::new(py);
                kwargs.set_item("keep_none", has_then)?;
                py.import("pyzed._async")?
                    .call_method("drain", (value, emit), Some(&kwargs))
                    .map(|_| ())
            });
            if let Err(err) = result {
                err.print(py);
            }
        });
    });
    Task::stream(receiver)
}

fn resolve_window(py: Python<'_>, state: &State, window: &Option<PyMsg>) -> Option<window::Id> {
    match window {
        Some(w) => state.window_id_of(py, w.0.bind(py)),
        None => state.target(),
    }
}

fn command_task(py: Python<'_>, state: &mut State, value: &Bound<'_, PyAny>) -> Task<Message> {
    if value.is_none() {
        return Task::none();
    }
    if let Ok(list) = value.cast::<PyList>() {
        return Task::batch(
            list.iter()
                .map(|v| command_task(py, state, &v))
                .collect::<Vec<_>>(),
        );
    }
    if let Ok(tuple) = value.cast::<PyTuple>()
        && tuple.iter().all(|v| v.cast::<Command>().is_ok())
    {
        return Task::batch(
            tuple
                .iter()
                .map(|v| command_task(py, state, &v))
                .collect::<Vec<_>>(),
        );
    }
    let Ok(command) = value.cast::<Command>() else {
        if is_deferred(value) {
            return background(PyMsg::new(value), false, None);
        }
        return Task::none();
    };
    match &command.get().kind {
        CommandKind::Exit => iced::exit(),
        CommandKind::Focus(id) => iced::widget::operation::focus(id.clone()),
        CommandKind::FocusNext(forward) => match state.current.or(state.main) {
            Some(window) => crate::focus::cycle(window, *forward),
            None => Task::none(),
        },
        CommandKind::FocusDirection(direction) => match state.current.or(state.main) {
            Some(window) => crate::focus::step(window, *direction),
            None => Task::none(),
        },
        CommandKind::SelectAll(id) => Task::batch([
            iced::widget::operation::focus(id.clone()),
            iced::widget::operation::select_all(id.clone()),
        ]),
        CommandKind::ScrollToEnd(id) => iced::widget::operation::snap_to_end(id.clone()),
        CommandKind::ScrollTo(id, x, y) => iced::widget::operation::scroll_to(
            id.clone(),
            scrollable::AbsoluteOffset { x: *x, y: *y },
        ),
        CommandKind::SetEditorText(id, text) => {
            state.caches.set_editor_text(id, text);
            Task::none()
        }
        CommandKind::SetEditorCursor(id, line, column) => {
            let position = text_editor::Position {
                line: line.saturating_sub(1),
                column: column.saturating_sub(1),
            };
            state.caches.set_editor_cursor(id, position)
        }
        CommandKind::FoldEditor(id, op) => state.caches.fold_editor_command(id, *op),
        CommandKind::EditorAction(id, action) => match state.caches.editor_context(id) {
            Some(ctx) => Task::done(Message::EditorAction {
                id: Arc::from(id.as_str()),
                action: *action,
                ctx,
            }),
            None => Task::none(),
        },
        CommandKind::SelectEditorRanges(id, ranges) => {
            state.caches.select_editor_ranges(id, ranges)
        }
        CommandKind::ReplaceEditorRanges(id, edits) => Task::done(Message::EditorReplace {
            id: Arc::from(id.as_str()),
            edits: Arc::new(edits.clone()),
        }),
        CommandKind::Batch(commands) => Task::batch(
            commands
                .iter()
                .map(|c| command_task(py, state, c.bind(py).as_any()))
                .collect::<Vec<_>>(),
        ),
        CommandKind::Message(msg) => Task::done(Message::Py(msg.clone())),
        CommandKind::ListMonitors(then) => list_monitors(then.clone()),
        CommandKind::Perform(function, then) => {
            // A coroutine or generator object (not a function) is drained as is.
            let call = !is_deferred(function.0.bind(py));
            background(function.clone(), call, then.clone())
        }
        CommandKind::OpenWindow(obj) => open_window(py, state, obj.0.bind(py)),
        CommandKind::CloseWindow(obj) => match resolve_window(py, state, obj) {
            Some(id) => close_animated(py, state, id),
            None => Task::none(),
        },
        CommandKind::Window(op, obj) => {
            let Some(id) = resolve_window(py, state, obj) else {
                return Task::none();
            };
            match *op {
                WindowOp::Drag => window::drag(id),
                WindowOp::DragResize(direction) => window::drag_resize(id, direction),
                WindowOp::Maximize(on) => window::maximize(id, on),
                WindowOp::SystemMenu => window::show_system_menu(id),
                WindowOp::Minimize => window::minimize(id, true),
                WindowOp::ToggleMaximize => window::toggle_maximize(id),
                WindowOp::Fullscreen(mode) => window::set_fullscreen(id, mode),
                WindowOp::Level(level) => window::set_level(id, level),
                WindowOp::HideCursor(hidden) => window::set_cursor_hidden(id, hidden),
                WindowOp::Resize(w, h) => window::resize(id, Size::new(w, h)),
                WindowOp::Move(x, y) => window::move_to(id, Point::new(x, y).into()),
                WindowOp::Focus => window::gain_focus(id),
            }
        }
        CommandKind::CopyToClipboard(text) => iced::clipboard::write(text.clone()),
        CommandKind::ReadClipboard(then) => {
            let then = then.clone();
            iced::clipboard::read().map(move |content| {
                Python::attach(|py| {
                    let value = content
                        .unwrap_or_default()
                        .into_pyobject(py)
                        .map(|v| v.into_any());
                    match value {
                        Ok(v) => Message::Call(then.clone(), PyMsg::new(&v)),
                        Err(_) => Message::Noop,
                    }
                })
            })
        }
        CommandKind::ReadClipboardImage(then) => {
            let then = then.clone();
            Task::perform(async { clipboard_png() }, move |png| {
                Python::attach(|py| {
                    let value = match png {
                        Some(data) => PyBytes::new(py, &data).into_any(),
                        None => py.None().into_bound(py),
                    };
                    Message::Call(then.clone(), PyMsg::new(&value))
                })
            })
        }
        // Android has no native file dialog here yet: the callback gets an empty list.
        #[cfg(target_os = "android")]
        CommandKind::PickFiles(pick) => {
            let then = pick.then.clone();
            Task::done(Python::attach(|py| {
                Message::Call(then.clone(), PyMsg::new(PyList::empty(py).as_any()))
            }))
        }
        #[cfg(not(target_os = "android"))]
        CommandKind::PickFiles(pick) => {
            let then = pick.then.clone();
            let mut dialog = rfd::AsyncFileDialog::new();
            if let Some(title) = &pick.title {
                dialog = dialog.set_title(title);
            }
            for (name, extensions) in &pick.filters {
                dialog = dialog.add_filter(name, extensions);
            }
            if let Some(directory) = &pick.directory {
                dialog = dialog.set_directory(directory);
            }
            let (multiple, folder, save) = (pick.multiple, pick.folder, pick.save.clone());
            Task::perform(
                async move {
                    if let Some(name) = save {
                        let dialog = if name.is_empty() {
                            dialog
                        } else {
                            dialog.set_file_name(name)
                        };
                        return dialog
                            .save_file()
                            .await
                            .map(|h| vec![h.path().to_string_lossy().into_owned()])
                            .unwrap_or_default();
                    }
                    let chosen: Vec<rfd::FileHandle> = match (folder, multiple) {
                        (true, true) => dialog.pick_folders().await.unwrap_or_default(),
                        (true, false) => dialog.pick_folder().await.into_iter().collect(),
                        (false, true) => dialog.pick_files().await.unwrap_or_default(),
                        (false, false) => dialog.pick_file().await.into_iter().collect(),
                    };
                    chosen
                        .iter()
                        .map(|h| h.path().to_string_lossy().into_owned())
                        .collect::<Vec<String>>()
                },
                move |paths| {
                    Python::attach(|py| match PyList::new(py, paths) {
                        Ok(list) => Message::Call(then.clone(), PyMsg::new(list.as_any())),
                        Err(_) => Message::Noop,
                    })
                },
            )
        }
    }
}

/// The image on the system clipboard, encoded as PNG (none on Android yet).
#[cfg(target_os = "android")]
fn clipboard_png() -> Option<Vec<u8>> {
    None
}

/// The image on the system clipboard, encoded as PNG.
#[cfg(not(target_os = "android"))]
fn clipboard_png() -> Option<Vec<u8>> {
    let image = arboard::Clipboard::new().ok()?.get_image().ok()?;
    let mut out = Vec::new();
    {
        let mut encoder = png::Encoder::new(&mut out, image.width as u32, image.height as u32);
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        let mut writer = encoder.write_header().ok()?;
        writer.write_image_data(&image.bytes).ok()?;
    }
    Some(out)
}

// ---------------------------------------------------------------------------
// Windows
// ---------------------------------------------------------------------------

fn open_window(py: Python<'_>, state: &mut State, obj: &Bound<'_, PyAny>) -> Task<Message> {
    if state.window_id_of(py, obj).is_some() {
        return Task::none();
    }
    let settings = match window_settings(obj) {
        Ok(settings) => settings,
        Err(err) => {
            err.print(py);
            return Task::none();
        }
    };
    if obj.getattr("app").map(|a| a.is_none()).unwrap_or(true) {
        let _ = obj.setattr("app", state.app.bind(py));
    }
    let (id, task) = window::open(settings);
    state.windows.insert(id, obj.clone().unbind());
    task.map(Message::WindowOpened)
}

/// Runs the app's `on_start` hook and returns the task of the commands it returns.
fn start_task(py: Python<'_>, state: &mut State, app: &Bound<'_, PyAny>) -> Task<Message> {
    match app.hasattr("on_start") {
        Ok(true) => match app.call_method0("on_start") {
            Ok(value) => command_task(py, state, &value),
            Err(err) => {
                err.print(py);
                Task::none()
            }
        },
        _ => Task::none(),
    }
}

/// A task that finishes after `seconds`.
fn after(seconds: f64) -> Task<()> {
    let (sender, receiver) = iced::futures::channel::oneshot::channel::<()>();
    std::thread::spawn(move || {
        std::thread::sleep(Duration::from_secs_f64(seconds));
        let _ = sender.send(());
    });
    Task::future(async move {
        let _ = receiver.await;
    })
}

/// Closes window `id` once its exit transition (``Window.exit_transition``) has played.
fn close_animated(py: Python<'_>, state: &State, id: window::Id) -> Task<Message> {
    let obj = state.window(id).bind(py);
    let seconds = match obj.call_method0("__pyzed_exit__") {
        Ok(value) => value.extract::<f64>().unwrap_or(0.0),
        Err(err) => {
            if !err.is_instance_of::<pyo3::exceptions::PyAttributeError>(py) {
                err.print(py);
            }
            0.0
        }
    };
    if seconds <= 0.0 || crate::animation::reduced_motion() {
        return window::close(id);
    }
    let (sender, receiver) = iced::futures::channel::oneshot::channel::<()>();
    std::thread::spawn(move || {
        std::thread::sleep(Duration::from_secs_f64(seconds));
        let _ = sender.send(());
    });
    Task::future(async move {
        let _ = receiver.await;
    })
    .then(move |_| window::close(id))
}

pub(crate) fn window_settings(obj: &Bound<'_, PyAny>) -> PyResult<window::Settings> {
    // `Window.__pyzed_device__`: fills in what the device profile sets and the window leaves
    match obj.call_method0("__pyzed_device__") {
        Ok(_) => {}
        Err(err) if err.is_instance_of::<pyo3::exceptions::PyAttributeError>(obj.py()) => {}
        Err(err) => return Err(err),
    }
    let attr = |name: &str| obj.getattr(name).ok().filter(|v| !v.is_none());
    let size_of = |name: &str| -> PyResult<Option<Size>> {
        attr(name)
            .map(|v| v.extract::<(f32, f32)>().map(|(w, h)| Size::new(w, h)))
            .transpose()
    };
    let flag = |name: &str, default: bool| -> PyResult<bool> {
        Ok(attr(name)
            .map(|v| v.is_truthy())
            .transpose()?
            .unwrap_or(default))
    };
    let position = match attr("position") {
        None => window::Position::Default,
        Some(v) => match v.extract::<String>() {
            Ok(s) if s == "center" || s == "centered" => window::Position::Centered,
            Ok(s) if s == "default" => window::Position::Default,
            Ok(s) => {
                return Err(PyValueError::new_err(format!(
                    "invalid window position {s:?}: use 'center', 'default' or (x, y)"
                )));
            }
            Err(_) => {
                let (x, y): (f32, f32) = v.extract()?;
                window::Position::Specific(Point::new(x, y).into())
            }
        },
    };
    // `Window.frame`: `None` keeps the system's frame; otherwise Python draws the title bar
    // (`ui.window_frame`) and the system draws none, except on macOS ("overlay"), where
    // its buttons stay over a transparent title bar.
    let frame = match obj.call_method0("__pyzed_frame__") {
        Ok(v) if !v.is_none() => Some(v.extract::<String>()?),
        Ok(_) => None,
        Err(err) if err.is_instance_of::<pyo3::exceptions::PyAttributeError>(obj.py()) => None,
        Err(err) => return Err(err),
    };
    let overlay = frame.as_deref() == Some("overlay");
    // `Window.kiosk`: fullscreen, no frame, above the others and not closed by the user.
    let kiosk = flag("kiosk", false)?;
    let decorations = flag("decorations", true)? && (frame.is_none() || overlay) && !kiosk;
    // `Window.fullscreen`: True (a borderless window over the screen) or "exclusive"
    let fullscreen = attr("fullscreen");
    let exclusive = match &fullscreen {
        Some(v) => match v.extract::<String>() {
            Ok(s) if s == "exclusive" => true,
            Ok(s) if s == "borderless" => false,
            Ok(s) => {
                return Err(PyValueError::new_err(format!(
                    "invalid fullscreen {s:?}: use True, False, \"borderless\" or \"exclusive\""
                )));
            }
            Err(_) => false,
        },
        None => false,
    };
    let fullscreen = kiosk
        || fullscreen
            .map(|v| v.is_truthy())
            .transpose()?
            .unwrap_or(false);
    let level = if flag("always_on_bottom", false)? {
        window::Level::AlwaysOnBottom
    } else if flag("always_on_top", false)? || kiosk {
        window::Level::AlwaysOnTop
    } else {
        window::Level::Normal
    };
    let monitor = attr("monitor")
        .map(|v| v.extract::<usize>())
        .transpose()?
        .map(window::MonitorIndex);
    Ok(window::Settings {
        size: size_of("size")?.unwrap_or(Size::new(1280.0, 800.0)),
        min_size: size_of("min_size")?,
        max_size: size_of("max_size")?,
        position,
        resizable: flag("resizable", true)? && !kiosk,
        closeable: flag("closable", true)? && !kiosk,
        minimizable: flag("minimizable", true)? && !kiosk,
        decorations,
        transparent: flag("transparent", false)?,
        maximized: flag("maximized", false)?,
        fullscreen,
        exclusive_fullscreen: exclusive,
        monitor,
        level,
        exit_on_close_request: false,
        icon: attr("icon").and_then(|v| window_icon(&v)),
        platform_specific: platform_specific(
            frame.is_some(),
            overlay,
            attr("app_id").and_then(|v| v.extract::<String>().ok()),
            flag("skip_taskbar", false)? || kiosk,
        ),
        ..Default::default()
    })
}

/// What `window_settings` makes of a `pyzed.Window`, for the tests.
#[pyfunction]
pub fn window_options<'py>(
    py: Python<'py>,
    window: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyDict>> {
    let settings = window_settings(window)?;
    let out = PyDict::new(py);
    out.set_item("fullscreen", settings.fullscreen)?;
    out.set_item("exclusive", settings.exclusive_fullscreen)?;
    out.set_item("monitor", settings.monitor.map(|index| index.0))?;
    out.set_item(
        "level",
        match settings.level {
            window::Level::Normal => "normal",
            window::Level::AlwaysOnTop => "top",
            window::Level::AlwaysOnBottom => "bottom",
        },
    )?;
    out.set_item("decorations", settings.decorations)?;
    out.set_item("resizable", settings.resizable)?;
    out.set_item("closable", settings.closeable)?;
    out.set_item("minimizable", settings.minimizable)?;
    Ok(out)
}

/// The icon of a window (`Window.icon`: a path to an image or its bytes), at most 256 pixels wide; a
/// file that cannot be read is reported and the window keeps the system's icon.
fn window_icon(value: &Bound<'_, PyAny>) -> Option<window::Icon> {
    let image = match crate::imaging::decode(value) {
        Ok(image) => image,
        Err(err) => {
            eprintln!("pyzed: window icon: {err}");
            return None;
        }
    };
    let image = if image.width() > 256 || image.height() > 256 {
        image.thumbnail(256, 256)
    } else {
        image
    };
    let rgba = image.to_rgba8();
    let (width, height) = rgba.dimensions();
    window::icon::from_rgba(rgba.into_raw(), width, height).ok()
}

#[cfg(target_os = "macos")]
fn platform_specific(
    _custom: bool,
    overlay: bool,
    _app_id: Option<String>,
    _skip_taskbar: bool,
) -> window::settings::PlatformSpecific {
    window::settings::PlatformSpecific {
        title_hidden: overlay,
        titlebar_transparent: overlay,
        fullsize_content_view: overlay,
    }
}

#[cfg(target_os = "windows")]
fn platform_specific(
    custom: bool,
    _overlay: bool,
    _app_id: Option<String>,
    skip_taskbar: bool,
) -> window::settings::PlatformSpecific {
    window::settings::PlatformSpecific {
        // the drop shadow and rounded corners of Windows 11 for windows without decorations
        undecorated_shadow: custom,
        skip_taskbar,
        ..Default::default()
    }
}

/// On Linux, `Window.app_id` names the app to the desktop (it should match the `.desktop` file),
/// which takes the icon of the taskbar and the dock from there on Wayland.
#[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "android")))]
fn platform_specific(
    _custom: bool,
    _overlay: bool,
    app_id: Option<String>,
    _skip_taskbar: bool,
) -> window::settings::PlatformSpecific {
    window::settings::PlatformSpecific {
        application_id: app_id.unwrap_or_default(),
        ..Default::default()
    }
}

#[cfg(target_os = "android")]
fn platform_specific(
    _custom: bool,
    _overlay: bool,
    _app_id: Option<String>,
    _skip_taskbar: bool,
) -> window::settings::PlatformSpecific {
    window::settings::PlatformSpecific
}

// ---------------------------------------------------------------------------
// Update / view
// ---------------------------------------------------------------------------

/// Returned values that the runtime handles itself instead of passing them to `update`.
fn is_final(value: &Bound<'_, PyAny>) -> bool {
    value.is_none()
        || is_unchanged(value)
        || value.cast::<Command>().is_ok()
        || value.cast::<PyList>().is_ok()
        || is_deferred(value)
}

/// Sends `message` to `target.update`, or calls it when it is a plain callable (lambda, method...).
fn dispatch<'py>(
    target: &Bound<'py, PyAny>,
    message: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    if is_final(message) {
        return Ok(message.clone());
    }
    if message.is_callable() && !message.is_instance_of::<PyType>() {
        let result = message.call0()?;
        if is_final(&result) {
            return Ok(result);
        }
        return target.call_method1("update", (result,));
    }
    target.call_method1("update", (message,))
}

/// Calls `callback(*args)` and dispatches whatever it returns.
fn callback<'py>(
    target: &Bound<'py, PyAny>,
    callback: &Bound<'py, PyAny>,
    args: impl pyo3::call::PyCallArgs<'py>,
) -> PyResult<Bound<'py, PyAny>> {
    let result = callback.call1(args)?;
    if is_final(&result) {
        return Ok(result);
    }
    dispatch(target, &result)
}

/// Builds a `pyzed.Event` and hands it to the handler (see `pyzed.events._deliver`).
fn deliver_event<'py>(
    target: &Bound<'py, PyAny>,
    handler: &Bound<'py, PyAny>,
    data: &crate::events::EventData,
    origin: Option<Point>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let kwargs = PyDict::new(py);
    kwargs.set_item("x", data.x)?;
    kwargs.set_item("y", data.y)?;
    kwargs.set_item("window_x", data.window_x)?;
    kwargs.set_item("window_y", data.window_y)?;
    if let Some(origin) = origin {
        kwargs.set_item("screen_x", origin.x + data.window_x)?;
        kwargs.set_item("screen_y", origin.y + data.window_y)?;
    }
    kwargs.set_item("button", data.button)?;
    kwargs.set_item("dx", data.dx)?;
    kwargs.set_item("dy", data.dy)?;
    kwargs.set_item("width", data.width)?;
    kwargs.set_item("height", data.height)?;
    kwargs.set_item("key", data.key.as_deref())?;
    kwargs.set_item("shift", data.modifiers.shift())?;
    kwargs.set_item("ctrl", data.modifiers.control())?;
    kwargs.set_item("alt", data.modifiers.alt())?;
    kwargs.set_item("logo", data.modifiers.logo())?;
    let result = py
        .import("pyzed.events")?
        .getattr("_deliver")?
        .call((handler, data.kind.name()), Some(&kwargs))?;
    if is_final(&result) {
        return Ok(result);
    }
    dispatch(target, &result)
}

fn call_hook<'py>(
    target: &Bound<'py, PyAny>,
    name: &str,
    args: impl pyo3::call::PyCallArgs<'py>,
) -> Option<PyResult<Bound<'py, PyAny>>> {
    if !target.hasattr(name).unwrap_or(false) {
        return None;
    }
    Some(
        target
            .call_method1(name, args)
            .and_then(|result| dispatch(target, &result)),
    )
}

/// Reports an editor change to Python (`on_change(text)`, then `on_cursor(line, column)`).
fn zero_based(ranges: Vec<crate::editor::TextRange>) -> Vec<crate::editor::TextRange> {
    ranges
        .into_iter()
        .map(|(a, b, c, d)| {
            (
                a.saturating_sub(1),
                b.saturating_sub(1),
                c.saturating_sub(1),
                d.saturating_sub(1),
            )
        })
        .collect()
}

fn editor_outcome(
    py: Python<'_>,
    state: &mut State,
    target: &Bound<'_, PyAny>,
    outcome: crate::editor::Outcome,
    on_change: Option<PyMsg>,
    on_cursor: Option<PyMsg>,
) -> Task<Message> {
    editor_outcome_with(py, state, target, outcome, on_change, on_cursor, None)
}

fn editor_outcome_with(
    py: Python<'_>,
    state: &mut State,
    target: &Bound<'_, PyAny>,
    outcome: crate::editor::Outcome,
    on_change: Option<PyMsg>,
    on_cursor: Option<PyMsg>,
    on_action: Option<PyMsg>,
) -> Task<Message> {
    let clipboard = match outcome.clipboard.clone() {
        Some(text) => iced::clipboard::write(text),
        None => Task::none(),
    };
    let mut result = Ok(py.None().into_bound(py));
    if outcome.edited
        && let Some(cb) = on_change
    {
        result = callback(target, cb.0.bind(py), (outcome.text.clone(),));
    }
    if outcome.cursor_moved
        && let Some(cb) = on_cursor
        && result.is_ok()
    {
        let (line, column) = outcome.cursor;
        result = callback(target, cb.0.bind(py), (line + 1, column + 1));
    }
    if let (Some(name), Some(cb)) = (outcome.action, on_action)
        && result.is_ok()
    {
        // A command returned by `on_change` or `on_cursor` wins over this one.
        let previous = result;
        result = callback(target, cb.0.bind(py), (name,));
        if let Ok(value) = &previous
            && !value.is_none()
        {
            result = previous;
        }
    }
    let scroll = Task::batch([outcome.scroll, clipboard]);
    match result {
        Ok(value) => Task::batch([scroll, command_task(py, state, &value)]),
        Err(err) => {
            err.print(py);
            scroll
        }
    }
}

fn update(state: &mut State, message: Message) -> Task<Message> {
    crate::tray::flush();
    let task = handle(state, message);
    Python::attach(|py| sync_targets(py, state));
    task
}

fn handle(state: &mut State, message: Message) -> Task<Message> {
    state.caches.prune();
    if let Message::Windowed(id, inner) = message {
        touch(id);
        let previous = state.current.replace(id);
        let task = handle(state, *inner);
        state.current = previous;
        return if Some(id) == state.main {
            task
        } else {
            task.map(move |m| m.in_window(id))
        };
    }
    if state.current.is_none()
        && let Some(main) = state.main
    {
        touch(main);
    }
    Python::attach(|py| {
        let target = match state.current {
            Some(id) => state.window(id).bind(py).clone(),
            None => state.app.bind(py).clone(),
        };
        let result = match message {
            Message::Noop | Message::Windowed(..) => return Task::none(),
            Message::Py(msg) => dispatch(&target, msg.0.bind(py)),
            Message::Done(value) => Ok(value.0.bind(py).clone()),
            Message::Input(cb, value) => callback(&target, cb.0.bind(py), (value,)),
            Message::Toggle(cb, value) => callback(&target, cb.0.bind(py), (value,)),
            Message::Slide(cb, value) => callback(&target, cb.0.bind(py), (value,)),
            Message::Point(cb, x, y) => callback(&target, cb.0.bind(py), (x, y)),
            Message::Call(cb, value) => callback(&target, cb.0.bind(py), (value.0.bind(py),)),
            Message::Event(cb, data) => {
                let origin = state
                    .target()
                    .and_then(|id| state.positions.get(&id).copied());
                deliver_event(&target, cb.0.bind(py), &data, origin)
            }
            Message::Key(combo) => {
                let main = state.app.bind(py).clone();
                match call_hook(&target, "on_key", (combo.clone(),)) {
                    Some(result) => result,
                    None if !target.is(&main) => match call_hook(&main, "on_key", (combo,)) {
                        Some(result) => result,
                        None => return Task::none(),
                    },
                    None => return Task::none(),
                }
            }
            Message::FileDrag(hook, path) => {
                let main = state.app.bind(py).clone();
                let Ok(args) = PyTuple::new(py, path) else {
                    return Task::none();
                };
                match call_hook(&target, hook, args.clone()) {
                    Some(result) => result,
                    None if !target.is(&main) => match call_hook(&main, hook, args) {
                        Some(result) => result,
                        None => return Task::none(),
                    },
                    None => return Task::none(),
                }
            }
            Message::KeyUp(name) => {
                let main = state.app.bind(py).clone();
                match call_hook(&target, "on_key_up", (name.clone(),)) {
                    Some(result) => result,
                    None if !target.is(&main) => match call_hook(&main, "on_key_up", (name,)) {
                        Some(result) => result,
                        None => return Task::none(),
                    },
                    None => return Task::none(),
                }
            }
            Message::Frame(now) => return frame_tick(py, state, now),
            #[cfg(target_os = "android")]
            Message::BackKey => {
                let main = state.app.bind(py).clone();
                let owner = if target.hasattr("on_back").unwrap_or(false) {
                    Some(&target)
                } else if main.hasattr("on_back").unwrap_or(false) {
                    Some(&main)
                } else {
                    None
                };
                let handled = owner.map(|owner| {
                    owner.call_method0("on_back").and_then(|value| {
                        let declined = value.is_instance_of::<pyo3::types::PyBool>()
                            && !value.is_truthy().unwrap_or(true);
                        if declined {
                            Ok(None)
                        } else {
                            dispatch(owner, &value).map(Some)
                        }
                    })
                });
                match handled {
                    Some(Ok(Some(value))) => return command_task(py, state, &value),
                    Some(Err(err)) => err.print(py),
                    _ => {}
                }
                crate::android::move_to_back();
                return Task::none();
            }
            // Nothing to do: the views read the new insets when they are built again.
            #[cfg(target_os = "android")]
            Message::Insets => return Task::none(),
            Message::ArrowKey(combo, direction) => {
                let main = state.app.bind(py).clone();
                let hooked = match call_hook(&target, "on_key", (combo.clone(),)) {
                    None if !target.is(&main) => call_hook(&main, "on_key", (combo,)),
                    other => other,
                };
                match hooked {
                    Some(Ok(value)) if !value.is_none() => return command_task(py, state, &value),
                    Some(Err(err)) => err.print(py),
                    _ => {}
                }
                return match state.current.or(state.main) {
                    Some(window) => crate::focus::step(window, direction),
                    None => Task::none(),
                };
            }
            Message::TabKey(combo, back) => {
                let main = state.app.bind(py).clone();
                let hooked = match call_hook(&target, "on_key", (combo.clone(),)) {
                    None if !target.is(&main) => call_hook(&main, "on_key", (combo,)),
                    other => other,
                };
                match hooked {
                    // `on_key` handled Tab itself (it returned a message or a command).
                    Some(Ok(value)) if !value.is_none() => return command_task(py, state, &value),
                    Some(Err(err)) => err.print(py),
                    _ => {}
                }
                let enabled = |obj: &Bound<'_, PyAny>| {
                    obj.getattr("tab_focus")
                        .and_then(|v| v.is_truthy())
                        .unwrap_or(true)
                };
                return match state.current.or(state.main) {
                    Some(window) if enabled(&target) && enabled(&main) => {
                        crate::focus::cycle(window, !back)
                    }
                    _ => Task::none(),
                };
            }
            Message::Editor {
                id,
                action,
                on_change,
                on_cursor,
            } => {
                let Some(outcome) = state.caches.perform_editor(&id, action) else {
                    return Task::none();
                };
                // Ctrl+click names an action (go to definition) for `on_action`.
                let on_action = outcome
                    .action
                    .and_then(|_| state.caches.editor_context(&id))
                    .and_then(|ctx| ctx.on_action.clone());
                return editor_outcome_with(
                    py, state, &target, outcome, on_change, on_cursor, on_action,
                );
            }
            Message::EditorIndent {
                id,
                key,
                indent,
                pairs,
                on_change,
                on_cursor,
            } => {
                let Some(outcome) = state.caches.key_editor(&id, key, indent, pairs) else {
                    return Task::none();
                };
                return editor_outcome(py, state, &target, outcome, on_change, on_cursor);
            }
            Message::EditorFold { id, op, on_cursor } => {
                let Some(outcome) = state.caches.fold_editor(&id, op) else {
                    return Task::none();
                };
                return editor_outcome(py, state, &target, outcome, None, on_cursor);
            }
            Message::EditorAction { id, action, ctx } => {
                let Some(outcome) = state.caches.run_editor(&id, action, &ctx) else {
                    return Task::none();
                };
                let ctx = (*ctx).clone();
                return editor_outcome_with(
                    py,
                    state,
                    &target,
                    outcome,
                    ctx.on_change,
                    ctx.on_cursor,
                    ctx.on_action,
                );
            }
            Message::EditorReplace { id, edits } => {
                let Some(ctx) = state.caches.editor_context(&id) else {
                    return Task::none();
                };
                let Some(outcome) = state.caches.replace_editor_ranges(&id, &edits) else {
                    return Task::none();
                };
                let ctx = (*ctx).clone();
                return editor_outcome(py, state, &target, outcome, ctx.on_change, ctx.on_cursor);
            }
            Message::EditorReveal(id) => return state.caches.center_editor(&id),
            Message::EditorScroll { id, y } => {
                return iced::widget::operation::scroll_to(
                    id,
                    scrollable::AbsoluteOffset {
                        x: None,
                        y: Some(y),
                    },
                );
            }
            Message::EditorPage {
                id,
                down,
                select,
                on_cursor,
            } => {
                let Some(outcome) = state.caches.page_editor(&id, down, select) else {
                    return Task::none();
                };
                let scroll = outcome.scroll;
                let result = match on_cursor {
                    Some(cb) if outcome.cursor_moved => {
                        let (line, column) = outcome.cursor;
                        callback(&target, cb.0.bind(py), (line + 1, column + 1))
                    }
                    _ => Ok(py.None().into_bound(py)),
                };
                return match result {
                    Ok(value) => Task::batch([scroll, command_task(py, state, &value)]),
                    Err(err) => {
                        err.print(py);
                        scroll
                    }
                };
            }
            Message::Hover(cb, hit) => match hit {
                Some(hit) => {
                    let info = PyDict::new(py);
                    let _ = info.set_item("line", hit.line + 1);
                    let _ = info.set_item("column", hit.column + 1);
                    let _ = info.set_item("start", hit.start + 1);
                    let _ = info.set_item("end", hit.end + 1);
                    let _ = info.set_item("x", hit.x);
                    let _ = info.set_item("y", hit.y);
                    let _ = info.set_item("height", hit.height);
                    callback(&target, cb.0.bind(py), (info,))
                }
                None => callback(&target, cb.0.bind(py), (py.None(),)),
            },
            Message::Scrolled(cb, viewport) => {
                let info = PyDict::new(py);
                let offset = viewport.absolute_offset();
                let relative = viewport.relative_offset();
                let bounds = viewport.bounds();
                let content = viewport.content_bounds();
                let _ = info.set_item("x", offset.x);
                let _ = info.set_item("y", offset.y);
                let _ = info.set_item("relative_x", relative.x);
                let _ = info.set_item("relative_y", relative.y);
                let _ = info.set_item("width", bounds.width);
                let _ = info.set_item("height", bounds.height);
                let _ = info.set_item("content_width", content.width);
                let _ = info.set_item("content_height", content.height);
                callback(&target, cb.0.bind(py), (info,))
            }
            Message::WindowOpened(id) => {
                let obj = state.window(id).bind(py).clone();
                let _ = obj.setattr("_pyzed_window_open", true);
                let hook = run_hook(py, state, call_hook(&obj, "on_open", ()));
                let splash = match state.splash {
                    Some(splash) if Some(id) == state.main => {
                        state.splash = None;
                        window::close(splash)
                    }
                    _ => Task::none(),
                };
                let cursor = if obj
                    .getattr("hide_cursor")
                    .and_then(|v| v.is_truthy())
                    .unwrap_or(false)
                {
                    window::set_cursor_hidden(id, true)
                } else {
                    Task::none()
                };
                return Task::batch([ask_maximized(id), hook, splash, cursor, list_monitors(None)]);
            }
            Message::SplashDone => {
                if state.main.is_some() || state.splash.is_none() {
                    return Task::none();
                }
                let app = state.app.bind(py).clone();
                let open = open_window(py, state, &app);
                state.main = state.window_id_of(py, &app);
                let start = start_task(py, state, &app);
                return Task::batch([open, start]);
            }
            Message::CloseRequested(id) => {
                let obj = state.window(id).bind(py).clone();
                // a kiosk is closed by the app (`Command.close_window`), never by the user
                if obj
                    .getattr("kiosk")
                    .and_then(|v| v.is_truthy())
                    .unwrap_or(false)
                {
                    return Task::none();
                }
                let allowed = match obj.call_method0("on_close") {
                    Ok(value) => {
                        !(value.is_instance_of::<pyo3::types::PyBool>()
                            && !value.is_truthy().unwrap_or(true))
                    }
                    Err(err) => {
                        if !err.is_instance_of::<pyo3::exceptions::PyAttributeError>(py) {
                            err.print(py);
                        }
                        true
                    }
                };
                return if allowed {
                    close_animated(py, state, id)
                } else {
                    Task::none()
                };
            }
            Message::WindowClosed(id) => {
                state.positions.remove(&id);
                if let Some(obj) = state.windows.remove(&id) {
                    let _ = obj.bind(py).setattr("_pyzed_window_open", false);
                }
                if Some(id) == state.main || state.windows.is_empty() {
                    return iced::exit();
                }
                return Task::none();
            }
            Message::WindowResized(id, size) => {
                let obj = state.window(id).bind(py).clone();
                // the scale the size was measured with, for `design_size`
                let _ = obj.setattr("_pyzed_size_scale", scale_factor(state, id));
                let _ = obj.setattr("window_size", (size.width, size.height));
                let hook = run_hook(
                    py,
                    state,
                    call_hook(&obj, "on_resize", (size.width, size.height)),
                );
                return Task::batch([ask_maximized(id), hook]);
            }
            Message::WindowMaximized(id, maximized) => {
                if let Some(obj) = state.windows.get(&id) {
                    let _ = obj.bind(py).setattr("window_maximized", maximized);
                }
                return Task::none();
            }
            Message::WindowFocused(id, focused) => {
                if let Some(obj) = state.windows.get(&id) {
                    let _ = obj.bind(py).setattr("window_focused", focused);
                }
                return Task::none();
            }
            Message::DragResize(direction) => {
                return match state.target() {
                    Some(id) => window::drag_resize(id, direction),
                    None => Task::none(),
                };
            }
            Message::WindowPlaced(id, at, size) => {
                let obj = state.window(id).bind(py).clone();
                if let Some(at) = at {
                    state.positions.insert(id, at);
                    let _ = obj.setattr("window_position", (at.x, at.y));
                }
                if let Some(size) = size {
                    let _ = obj.setattr("_pyzed_size_scale", scale_factor(state, id));
                    let _ = obj.setattr("window_size", (size.width, size.height));
                }
                return Task::none();
            }
            Message::SystemTheme(mode) => {
                let dark = !matches!(mode, iced::theme::Mode::Light);
                let _ = state.app.bind(py).setattr("system_dark", dark);
                return Task::none();
            }
        };
        match result {
            Ok(value) => command_task(py, state, &value),
            Err(err) => {
                err.print(py);
                Task::none()
            }
        }
    })
}

/// Asks whether window `id` is maximized, for `Window.window_maximized`.
fn ask_maximized(id: window::Id) -> Task<Message> {
    window::is_maximized(id).map(move |maximized| Message::WindowMaximized(id, maximized))
}

/// The command returned by a hook (`on_open`, `on_resize`...), if it has one.
fn run_hook(
    py: Python<'_>,
    state: &mut State,
    result: Option<PyResult<Bound<'_, PyAny>>>,
) -> Task<Message> {
    match result {
        Some(Ok(value)) => command_task(py, state, &value),
        Some(Err(err)) => {
            err.print(py);
            Task::none()
        }
        None => Task::none(),
    }
}

/// Calls every `pz.frames` callback with the seconds since the previous frame.
fn frame_tick(py: Python<'_>, state: &mut State, mut now: iced::time::Instant) -> Task<Message> {
    // Without vsync (software rendering) frames would come back to back and spin the
    // CPU: wait out the rest of the shortest frame time `max_fps` allows.
    if let Some(last) = state.last_frame.get() {
        let early = state.frame_interval.get() - now.saturating_duration_since(last).as_secs_f64();
        if early > 0.0 {
            py.detach(|| std::thread::sleep(Duration::from_secs_f64(early)));
            now = iced::time::Instant::now();
        }
    }
    // A long pause (a dragged window, a breakpoint) must not make the game jump ahead.
    let dt = state
        .last_frame
        .get()
        .map(|last| now.saturating_duration_since(last).as_secs_f64())
        .unwrap_or(1.0 / 60.0)
        .min(0.25);
    state.last_frame.set(Some(now));
    let callbacks = state.frames.borrow().clone();
    let mut tasks = Vec::new();
    for (window, cb) in callbacks {
        let target = match window {
            Some(id) => state.window(id).bind(py).clone(),
            None => state.app.bind(py).clone(),
        };
        let next = window.or(state.current);
        let previous = std::mem::replace(&mut state.current, next);
        match callback(&target, cb.0.bind(py), (dt,)) {
            Ok(value) => {
                let task = command_task(py, state, &value);
                tasks.push(match window {
                    Some(id) if Some(id) != state.main => task.map(move |m| m.in_window(id)),
                    _ => task,
                });
            }
            Err(err) => err.print(py),
        }
        state.current = previous;
    }
    Task::batch(tasks)
}

fn error_view<'a>(title: &'static str, message: String) -> Element<'a, Message> {
    let red = Color::from_rgb8(0xd0, 0x72, 0x77);
    container(
        column![
            text(title)
                .size(18)
                .color(red)
                .font(Font::with_name(crate::style::sans())),
            scrollable(
                text(message)
                    .size(13)
                    .font(Font::with_name(crate::style::mono()))
                    .color(Color::from_rgb8(0xdc, 0xe0, 0xe5))
            )
            .height(Length::Fill),
        ]
        .spacing(12),
    )
    .padding(24)
    .width(Length::Fill)
    .height(Length::Fill)
    .style(|_| container::Style {
        background: Some(Color::from_rgb8(0x28, 0x2c, 0x33).into()),
        ..Default::default()
    })
    .into()
}

pub fn format_error(py: Python<'_>, err: &PyErr) -> String {
    let formatted = py.import("traceback").and_then(|tb| {
        tb.call_method1("format_exception", (err.value(py),))
            .and_then(|lines| lines.extract::<Vec<String>>())
    });
    match formatted {
        Ok(lines) => lines.concat(),
        Err(_) => err.to_string(),
    }
}

fn view(state: &State, id: window::Id) -> Element<'_, Message> {
    let element = Python::attach(|py| {
        let obj = state.window(id).bind(py);
        match view_root(py, id, obj) {
            Ok(root) => {
                crate::selectable::begin_frame();
                crate::focus::Scope::new(id, render::build(py, &root, Ctx::new(&state.caches)))
                    .into()
            }
            Err(err) => {
                let reload_failed = err
                    .get_type(py)
                    .name()
                    .is_ok_and(|name| name == "ReloadError");
                if reload_failed {
                    // The reloader already printed the traceback; show it as is.
                    let message = err.value(py).to_string();
                    error_view("Reload failed: fix the code and save again", message)
                } else {
                    err.print(py);
                    error_view("Python error in view()", format_error(py, &err))
                }
            }
        }
    });
    #[cfg(target_os = "android")]
    let element = keep_clear(state, id, element);
    if state.windows.contains_key(&id) && Some(id) != state.main {
        element.map(move |m| m.in_window(id))
    } else {
        element
    }
}

/// Pads the window's content clear of the status bar, the camera cutout, the navigation bar and
/// the soft keyboard, unless the window draws under them (`safe_area = False`).
#[cfg(target_os = "android")]
fn keep_clear<'a>(
    state: &State,
    id: window::Id,
    element: Element<'a, Message>,
) -> Element<'a, Message> {
    let keep = Python::attach(|py| {
        state
            .window(id)
            .bind(py)
            .getattr("safe_area")
            .and_then(|v| v.is_truthy())
            .unwrap_or(true)
    });
    if !keep {
        return element;
    }
    let scale = scale_factor(state, id).max(0.1);
    let [top, right, bottom, left] = crate::android::current_insets().map(|v| v / scale);
    container(element)
        .padding(iced::Padding {
            top,
            right,
            bottom,
            left,
        })
        .into()
}

/// Watches the insets (Android tells a NativeActivity nothing when they change).
#[cfg(target_os = "android")]
fn insets_stream() -> impl Stream<Item = Message> {
    let (sender, receiver) = mpsc::unbounded::<Message>();
    std::thread::spawn(move || {
        loop {
            if crate::android::insets_changed() && sender.unbounded_send(Message::Insets).is_err() {
                break;
            }
            std::thread::sleep(Duration::from_millis(200));
        }
    });
    receiver
}

/// The parts of the screen the system draws over, in logical pixels: `(top, right, bottom, left)`
/// (the status and navigation bars, the camera cutout and the soft keyboard; zeros on a desktop).
#[pyfunction]
pub fn safe_area() -> (f32, f32, f32, f32) {
    #[cfg(target_os = "android")]
    {
        let [top, right, bottom, left] = crate::android::current_insets();
        (top, right, bottom, left)
    }
    #[cfg(not(target_os = "android"))]
    (0.0, 0.0, 0.0, 0.0)
}

pub(crate) fn palette_key(obj: &Bound<'_, PyAny>) -> Option<Vec<String>> {
    let palette = obj.call_method0("__pyzed_palette__").ok()?;
    palette.extract::<Vec<String>>().ok()
}

pub(crate) fn build_theme(key: &[String]) -> Option<Theme> {
    let color = |i: usize| key.get(i).and_then(|c| c.parse::<Color>().ok());
    let palette = iced::theme::Palette {
        background: color(0)?,
        text: color(1)?,
        primary: color(2)?,
        success: color(3)?,
        warning: color(4).unwrap_or(Color::from_rgb8(0xde, 0xc1, 0x84)),
        danger: color(5)?,
    };
    Some(Theme::custom(
        key.get(6).cloned().unwrap_or_else(|| "pyzed".into()),
        palette,
    ))
}

fn theme_of(state: &State, id: window::Id) -> Option<Theme> {
    Python::attach(|py| {
        let Some(key) = palette_key(state.window(id).bind(py)) else {
            return Some(Theme::Dark);
        };
        let mut cache = state.themes.borrow_mut();
        if let Some(theme) = cache.get(&key) {
            return Some(theme.clone());
        }
        let theme = build_theme(&key).unwrap_or(Theme::Dark);
        cache.insert(key, theme.clone());
        Some(theme)
    })
}

fn title(state: &State, id: window::Id) -> String {
    Python::attach(|py| {
        let obj = state.window(id).bind(py);
        let Ok(title) = obj.getattr("title") else {
            return "Pyzed".to_owned();
        };
        let title = if title.is_callable() {
            title.call0()
        } else {
            Ok(title)
        };
        title
            .and_then(|t| t.extract::<String>())
            .unwrap_or_else(|_| "Pyzed".to_owned())
    })
}

fn scale_factor(state: &State, id: window::Id) -> f32 {
    Python::attach(|py| {
        let obj = state.window(id).bind(py);
        // `Window.__pyzed_scale__`: `scale`, times the fit of `design_size` when it has one
        match obj.call_method0("__pyzed_scale__") {
            Ok(value) => value.extract::<f32>(),
            Err(_) => obj.getattr("scale").and_then(|s| s.extract::<f32>()),
        }
        .unwrap_or(1.0)
    })
}

// ---------------------------------------------------------------------------
// Subscriptions: keyboard, window events, timers, streams and messages posted
// from other threads.
// ---------------------------------------------------------------------------

static POST: LazyLock<Mutex<Option<mpsc::UnboundedSender<Message>>>> =
    LazyLock::new(|| Mutex::new(None));
static POST_RECEIVER: LazyLock<Mutex<Option<mpsc::UnboundedReceiver<Message>>>> =
    LazyLock::new(|| Mutex::new(None));

pub(crate) fn open_post_channel() {
    let (sender, receiver) = mpsc::unbounded();
    *POST.lock().unwrap() = Some(sender);
    *POST_RECEIVER.lock().unwrap() = Some(receiver);
}

/// Whether `pz.run` is running the app's event loop (not a screenshot or a recording).
static RUNNING: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
/// The thread `pz.run` runs the event loop on.
static APP_THREAD: std::sync::OnceLock<std::thread::ThreadId> = std::sync::OnceLock::new();

/// Whether the app's event loop is running.
#[allow(dead_code)]
pub(crate) fn running() -> bool {
    RUNNING.load(std::sync::atomic::Ordering::SeqCst)
}

/// Whether this is the thread of the app's event loop.
#[allow(dead_code)]
pub(crate) fn on_app_thread() -> bool {
    APP_THREAD.get() == Some(&std::thread::current().id())
}

/// Makes the running app update once (with nothing to do); whether an app was running.
pub(crate) fn wake() -> bool {
    POST.lock()
        .unwrap()
        .as_ref()
        .is_some_and(|sender| sender.unbounded_send(Message::Noop).is_ok())
}

pub(crate) fn close_post_channel() {
    *POST.lock().unwrap() = None;
}

fn post_stream() -> impl Stream<Item = Message> {
    match POST_RECEIVER.lock().unwrap().take() {
        // A posted message may change what any window shows (isolated ones included); `wake`
        // only asks for an update.
        Some(receiver) => receiver
            .inspect(|message| {
                if !matches!(message, Message::Noop) {
                    TOUCHED.lock().unwrap().all = true;
                }
            })
            .boxed(),
        None => stream::pending().boxed(),
    }
}

/// Sends a message to the running app from any thread (e.g. a worker thread).
#[pyfunction]
pub fn post(message: &Bound<'_, PyAny>) -> PyResult<()> {
    let guard = POST.lock().unwrap();
    let sender = guard
        .as_ref()
        .ok_or_else(|| PyRuntimeError::new_err("no app is running"))?;
    sender
        .unbounded_send(Message::Py(PyMsg::new(message)))
        .map_err(|_| PyRuntimeError::new_err("the app has stopped"))
}

fn key_name(key: &Key) -> Option<String> {
    Some(match key.as_ref() {
        Key::Character(c) => c.to_lowercase(),
        Key::Named(named) => match named {
            Named::Enter => "enter".into(),
            Named::Escape => "escape".into(),
            Named::Tab => "tab".into(),
            Named::Space => "space".into(),
            Named::Backspace => "backspace".into(),
            Named::Delete => "delete".into(),
            Named::ArrowUp => "up".into(),
            Named::ArrowDown => "down".into(),
            Named::ArrowLeft => "left".into(),
            Named::ArrowRight => "right".into(),
            Named::Home => "home".into(),
            Named::End => "end".into(),
            Named::PageUp => "pageup".into(),
            Named::PageDown => "pagedown".into(),
            // Android's back button
            Named::BrowserBack => "back".into(),
            Named::Shift | Named::Control | Named::Alt | Named::Super | Named::Meta => return None,
            other => format!("{other:?}").to_lowercase(),
        },
        Key::Unidentified => return None,
    })
}

/// A key press as a Zed-style combo such as `"ctrl-shift-p"` (`None` for lone modifiers).
pub fn key_combo(key: &Key, modifiers: keyboard::Modifiers) -> Option<String> {
    let name = key_name(key)?;
    let mut combo = String::new();
    if modifiers.control() {
        combo.push_str("ctrl-");
    }
    if modifiers.alt() {
        combo.push_str("alt-");
    }
    if modifiers.shift() {
        combo.push_str("shift-");
    }
    if modifiers.logo() {
        combo.push_str("cmd-");
    }
    combo.push_str(&name);
    Some(combo)
}

/// The keys held down right now, by name without modifiers (`pz.pressed()`).
static PRESSED: LazyLock<Mutex<std::collections::BTreeSet<String>>> =
    LazyLock::new(|| Mutex::new(std::collections::BTreeSet::new()));

/// Which key hooks the app and its windows define (`on_key`, `on_key_up`), refreshed with the
/// subscriptions after every update. A key message nobody listens to would still rebuild every
/// window's view, so presses and releases only become messages when a hook will receive them
/// (typing in a field then rebuilds the view once per key instead of three times).
static KEY_HOOKS: std::sync::atomic::AtomicU8 = std::sync::atomic::AtomicU8::new(0);
const ON_KEY: u8 = 1;
const ON_KEY_UP: u8 = 2;
/// `App.arrow_focus`: the arrow keys no widget used move the focus.
const ARROW_FOCUS: u8 = 4;

fn key_hooks(obj: &Bound<'_, PyAny>) -> u8 {
    let has = |name: &str| obj.hasattr(name).unwrap_or(false);
    let arrows = obj
        .getattr("arrow_focus")
        .and_then(|v| v.is_truthy())
        .unwrap_or(false);
    (if has("on_key") { ON_KEY } else { 0 })
        | (if has("on_key_up") { ON_KEY_UP } else { 0 })
        | (if arrows { ARROW_FOCUS } else { 0 })
}

fn key_message(event: keyboard::Event) -> Option<Message> {
    let hooks = KEY_HOOKS.load(std::sync::atomic::Ordering::Relaxed);
    match event {
        keyboard::Event::KeyPressed { key, modifiers, .. } if hooks & ON_KEY != 0 => {
            key_combo(&key, modifiers).map(Message::Key)
        }
        keyboard::Event::KeyReleased { key, .. } if hooks & ON_KEY_UP != 0 => {
            key_name(&key).map(Message::KeyUp)
        }
        _ => None,
    }
}

/// Keeps `PRESSED` up to date (a window losing focus never sees the releases).
fn track_keys(event: &iced::Event) {
    let mut pressed = PRESSED.lock().unwrap();
    match event {
        iced::Event::Keyboard(keyboard::Event::KeyPressed { key, .. }) => {
            if let Some(name) = key_name(key) {
                pressed.insert(name);
            }
        }
        iced::Event::Keyboard(keyboard::Event::KeyReleased { key, .. }) => {
            if let Some(name) = key_name(key) {
                pressed.remove(&name);
            }
        }
        iced::Event::Window(window::Event::Unfocused) => pressed.clear(),
        _ => {}
    }
}

/// The names of the keys held down right now, such as `["left", "space"]`.
///
/// Modifiers are left out (read them from the combo `on_key` receives). Games poll
/// this every frame instead of counting presses and releases.
#[pyfunction]
pub fn pressed_keys() -> Vec<String> {
    PRESSED.lock().unwrap().iter().cloned().collect()
}

/// Where a window is on the screen and how big: reported when it opens, and each time it moves
/// (positions are not reported on Wayland). Also whether it has the keyboard focus, and the
/// files dragged onto it from the system (one message per file).
fn window_moved(
    event: iced::Event,
    _status: iced::event::Status,
    window: window::Id,
) -> Option<Message> {
    match event {
        iced::Event::Window(window::Event::Opened { position, size }) => {
            Some(Message::WindowPlaced(window, position, Some(size)))
        }
        iced::Event::Window(window::Event::Moved(at)) => {
            Some(Message::WindowPlaced(window, Some(at), None))
        }
        iced::Event::Window(window::Event::FileHovered(path)) => Some(
            Message::FileDrag("on_file_hover", Some(path.to_string_lossy().into_owned()))
                .in_window(window),
        ),
        iced::Event::Window(window::Event::FileDropped(path)) => Some(
            Message::FileDrag("on_file_drop", Some(path.to_string_lossy().into_owned()))
                .in_window(window),
        ),
        iced::Event::Window(window::Event::FilesHoveredLeft) => {
            Some(Message::FileDrag("on_file_leave", None).in_window(window))
        }
        iced::Event::Window(window::Event::Focused) => Some(Message::WindowFocused(window, true)),
        iced::Event::Window(window::Event::Unfocused) => {
            Some(Message::WindowFocused(window, false))
        }
        _ => None,
    }
}

/// Set by a focused control (a select, `focusable`) that used the key being pressed, so the
/// key does not also reach `on_key`.
static KEY_CLAIMED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

/// Marks the key being pressed as used by the focused control (see `KEY_CLAIMED`).
pub fn claim_key() {
    KEY_CLAIMED.store(true, std::sync::atomic::Ordering::Relaxed);
}

fn key_event(
    event: iced::Event,
    status: iced::event::Status,
    window: window::Id,
) -> Option<Message> {
    track_keys(&event);
    if matches!(
        event,
        iced::Event::Keyboard(keyboard::Event::KeyPressed { .. })
    ) && KEY_CLAIMED.swap(false, std::sync::atomic::Ordering::Relaxed)
    {
        return None;
    }
    match event {
        #[cfg(target_os = "android")]
        iced::Event::Keyboard(keyboard::Event::KeyPressed {
            key: Key::Named(Named::BrowserBack),
            ..
        }) => Some(Message::BackKey.in_window(window)),
        // Tab that no widget used (a code editor indents with it) moves the focus.
        iced::Event::Keyboard(keyboard::Event::KeyPressed {
            key: Key::Named(Named::Tab),
            modifiers,
            ..
        }) if status == iced::event::Status::Ignored
            && !(modifiers.control() || modifiers.alt() || modifiers.logo()) =>
        {
            let combo = if modifiers.shift() {
                "shift-tab"
            } else {
                "tab"
            };
            Some(Message::TabKey(combo.into(), modifiers.shift()).in_window(window))
        }
        // with `App.arrow_focus`, the arrows no widget used move the focus (remotes, knobs)
        iced::Event::Keyboard(keyboard::Event::KeyPressed {
            key:
                Key::Named(
                    named @ (Named::ArrowUp
                    | Named::ArrowDown
                    | Named::ArrowLeft
                    | Named::ArrowRight),
                ),
            modifiers,
            ..
        }) if status == iced::event::Status::Ignored
            && modifiers.is_empty()
            && KEY_HOOKS.load(std::sync::atomic::Ordering::Relaxed) & ARROW_FOCUS != 0 =>
        {
            let (combo, direction) = match named {
                Named::ArrowUp => ("up", crate::focus::Direction::Up),
                Named::ArrowDown => ("down", crate::focus::Direction::Down),
                Named::ArrowLeft => ("left", crate::focus::Direction::Left),
                _ => ("right", crate::focus::Direction::Right),
            };
            Some(Message::ArrowKey(combo.into(), direction).in_window(window))
        }
        iced::Event::Keyboard(event) => key_message(event).map(|m| m.in_window(window)),
        _ => None,
    }
}

/// A timer or stream declared by `App.subscriptions()`.
enum SubscriptionKind {
    Every { interval: Duration, message: PyMsg },
    Stream { function: PyMsg },
    Frames { function: PyMsg, max_fps: f64 },
}

/// A long-running source of messages, returned from `App.subscriptions()`.
///
/// Subscriptions are identified by their `key`: as long as `subscriptions()` keeps
/// returning one with the same key it keeps running; when it disappears it stops.
#[pyclass(module = "pyzed._core", name = "Subscription", frozen)]
pub struct PySubscription {
    key: String,
    kind: SubscriptionKind,
}

#[pymethods]
impl PySubscription {
    fn __repr__(&self) -> String {
        match &self.kind {
            SubscriptionKind::Every { interval, .. } => {
                format!("<Subscription every {:?} key={:?}>", interval, self.key)
            }
            SubscriptionKind::Stream { .. } => format!("<Subscription stream key={:?}>", self.key),
            SubscriptionKind::Frames { .. } => format!("<Subscription frames key={:?}>", self.key),
        }
    }

    #[getter]
    fn key(&self) -> &str {
        &self.key
    }
}

fn default_key(value: &Bound<'_, PyAny>) -> PyResult<String> {
    if let Ok(name) = value.getattr("__qualname__") {
        return name.extract();
    }
    Ok(value.repr()?.to_cow()?.into_owned())
}

/// Sends `message` to `update` every `seconds` (like Iced's `time::every`).
#[pyfunction]
#[pyo3(signature = (seconds, message, *, key=None))]
pub fn every(
    seconds: f64,
    message: &Bound<'_, PyAny>,
    key: Option<String>,
) -> PyResult<PySubscription> {
    if seconds.is_nan() || seconds <= 0.0 {
        return Err(PyValueError::new_err("seconds must be positive"));
    }
    Ok(PySubscription {
        key: format!(
            "every:{seconds}:{}",
            match key {
                Some(k) => k,
                None => default_key(message)?,
            }
        ),
        kind: SubscriptionKind::Every {
            interval: Duration::from_secs_f64(seconds),
            message: PyMsg::new(message),
        },
    })
}

/// Runs `function()` for as long as the subscription is active and sends every value it
/// yields to `update`. `function` may be a generator function or an `async def` generator.
#[pyfunction]
#[pyo3(signature = (function, *, key=None))]
pub fn listen(function: &Bound<'_, PyAny>, key: Option<String>) -> PyResult<PySubscription> {
    Ok(PySubscription {
        key: format!(
            "stream:{}",
            match key {
                Some(k) => k,
                None => default_key(function)?,
            }
        ),
        kind: SubscriptionKind::Stream {
            function: PyMsg::new(function),
        },
    })
}

/// Calls `callback(dt)` once per displayed frame (usually 60 times a second, in sync
/// with the screen), with `dt` the seconds since the previous one. Made for games and
/// simulations: move things by `speed * dt` and they go equally fast at any frame rate.
///
/// `max_fps` caps the rate where the display does not wait for vsync (software rendering).
#[pyfunction]
#[pyo3(signature = (callback, *, key=None, max_fps=240.0))]
pub fn frames(
    callback: &Bound<'_, PyAny>,
    key: Option<String>,
    max_fps: f64,
) -> PyResult<PySubscription> {
    if max_fps.is_nan() || max_fps <= 0.0 {
        return Err(PyValueError::new_err("max_fps must be positive"));
    }
    if !callback.is_callable() {
        return Err(pyo3::exceptions::PyTypeError::new_err(
            "frames() needs a callable that takes dt",
        ));
    }
    Ok(PySubscription {
        key: format!(
            "frames:{}",
            match key {
                Some(k) => k,
                None => default_key(callback)?,
            }
        ),
        kind: SubscriptionKind::Frames {
            function: PyMsg::new(callback),
            max_fps,
        },
    })
}

#[derive(Clone)]
struct Recipe {
    key: String,
    window: Option<window::Id>,
    every: Option<(Duration, PyMsg)>,
    stream: Option<PyMsg>,
    frame: Option<(PyMsg, f64)>,
}

impl Hash for Recipe {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.key.hash(state);
        self.window.hash(state);
    }
}

fn recipe_stream(recipe: &Recipe) -> impl Stream<Item = Message> + use<> {
    let (sender, receiver) = mpsc::unbounded::<Message>();
    let window = recipe.window;
    let wrap = move |m: Message| match window {
        Some(id) => m.in_window(id),
        None => m,
    };
    if let Some((interval, message)) = recipe.every.clone() {
        std::thread::spawn(move || {
            loop {
                std::thread::sleep(interval);
                if sender
                    .unbounded_send(wrap(Message::Py(message.clone())))
                    .is_err()
                {
                    break;
                }
            }
        });
    } else if let Some(function) = recipe.stream.clone() {
        let task_sender = sender.clone();
        std::thread::spawn(move || {
            Python::attach(|py| {
                let emit = PyCFunction::new_closure(
                    py,
                    None,
                    None,
                    move |args: &Bound<'_, PyTuple>, _kwargs: Option<&Bound<'_, PyDict>>| {
                        let item = args.get_item(0)?;
                        task_sender
                            .unbounded_send(wrap(Message::Py(PyMsg::new(&item))))
                            .map_err(|_| PyRuntimeError::new_err("subscription stopped"))
                    },
                );
                let result = emit.and_then(|emit| {
                    let value = function.0.bind(py).call0()?;
                    py.import("pyzed._async")?
                        .call_method1("drain", (value, emit))
                        .map(|_| ())
                });
                if let Err(err) = result
                    && !err.is_instance_of::<PyRuntimeError>(py)
                {
                    err.print(py);
                }
            });
            drop(sender);
        });
    }
    receiver
}

fn python_subscriptions(
    py: Python<'_>,
    obj: &Bound<'_, PyAny>,
    window: Option<window::Id>,
) -> Vec<Recipe> {
    let value = if obj.hasattr("subscriptions").unwrap_or(false) {
        match obj.call_method0("subscriptions") {
            Ok(v) => v,
            Err(err) => {
                err.print(py);
                return Vec::new();
            }
        }
    } else {
        pyo3::types::PyList::empty(py).into_any()
    };
    // Animation players kept in the object's attributes add theirs.
    let value = match py
        .import("pyzed.animation_player")
        .and_then(|m| m.getattr("_player_subscriptions"))
        .and_then(|f| f.call1((obj,)))
    {
        Ok(players) if players.len().is_ok_and(|n| n > 0) => {
            pyo3::types::PyList::new(py, [value, players]).map_or_else(
                |err| {
                    err.print(py);
                    py.None().into_bound(py)
                },
                |l| l.into_any(),
            )
        }
        Ok(_) => value,
        Err(err) => {
            err.print(py);
            value
        }
    };
    let items = match crate::widget::flatten(&value) {
        Ok(items) => items,
        Err(err) => {
            err.print(py);
            return Vec::new();
        }
    };
    items
        .iter()
        .filter_map(|item| item.cast::<PySubscription>().ok().map(|s| s.get()))
        .map(|s| match &s.kind {
            SubscriptionKind::Every { interval, message } => Recipe {
                key: s.key.clone(),
                window,
                every: Some((*interval, message.clone())),
                stream: None,
                frame: None,
            },
            SubscriptionKind::Stream { function } => Recipe {
                key: s.key.clone(),
                window,
                every: None,
                stream: Some(function.clone()),
                frame: None,
            },
            SubscriptionKind::Frames { function, max_fps } => Recipe {
                key: s.key.clone(),
                window,
                every: None,
                stream: None,
                frame: Some((function.clone(), *max_fps)),
            },
        })
        .collect()
}

fn subscription(state: &State) -> Subscription<Message> {
    let mut subscriptions = vec![
        // Every key press is reported (even those a focused input handled), like a global keymap.
        iced::event::listen_with(key_event),
        Subscription::run(post_stream),
        window::close_requests().map(Message::CloseRequested),
        window::close_events().map(Message::WindowClosed),
        window::resize_events().map(|(id, size)| Message::WindowResized(id, size)),
        iced::event::listen_with(window_moved),
        iced::system::theme_changes().map(Message::SystemTheme),
    ];
    #[cfg(target_os = "android")]
    subscriptions.push(Subscription::run(insets_stream));
    Python::attach(|py| {
        let mut recipes = python_subscriptions(py, state.app.bind(py), None);
        let mut hooks = key_hooks(state.app.bind(py));
        for (id, obj) in &state.windows {
            hooks |= key_hooks(obj.bind(py));
            if Some(*id) != state.main {
                recipes.extend(python_subscriptions(py, obj.bind(py), Some(*id)));
            }
        }
        KEY_HOOKS.store(hooks, std::sync::atomic::Ordering::Relaxed);
        let (frames, recipes): (Vec<_>, Vec<_>) =
            recipes.into_iter().partition(|r| r.frame.is_some());
        if frames.is_empty() {
            state.last_frame.set(None);
        } else {
            // One frame clock for all of them, so they advance together.
            subscriptions.push(window::frames().map(Message::Frame));
        }
        let fastest = frames
            .iter()
            .filter_map(|r| r.frame.as_ref().map(|(_, fps)| *fps))
            .fold(0.0, f64::max);
        state
            .frame_interval
            .set(if fastest > 0.0 { 1.0 / fastest } else { 0.0 });
        *state.frames.borrow_mut() = frames
            .into_iter()
            .filter_map(|r| Some((r.window, r.frame?.0)))
            .collect();
        subscriptions.extend(
            recipes
                .into_iter()
                .map(|recipe| Subscription::run_with(recipe, recipe_stream)),
        );
    });
    Subscription::batch(subscriptions)
}

// ---------------------------------------------------------------------------
// Entry points
// ---------------------------------------------------------------------------

pub(crate) fn daemon(
    app: Py<PyAny>,
    font_size: f32,
    headless: bool,
) -> iced::Daemon<impl iced::Program<State = State, Message = Message, Theme = Theme>> {
    let boot = move || {
        Python::attach(|py| {
            let mut state = State {
                app: app.clone_ref(py),
                main: None,
                windows: HashMap::new(),
                positions: HashMap::new(),
                current: None,
                caches: Caches::default(),
                themes: RefCell::new(HashMap::new()),
                frames: RefCell::new(Vec::new()),
                frame_interval: std::cell::Cell::new(0.0),
                last_frame: std::cell::Cell::new(None),
                splash: None,
            };
            let bound = app.bind(py).clone();
            // The off-screen emulator can't answer theme queries; screenshots keep `system_dark`.
            let theme = if headless {
                Task::none()
            } else {
                iced::system::theme().map(Message::SystemTheme)
            };
            // `App.splash`: a window shown first, for at least its `duration`; the main window
            // opens (and `on_start` runs) after it, so a slow start keeps the splash on screen.
            let splash = bound.getattr("splash").ok().filter(|v| !v.is_none());
            if let (Some(splash), false) = (splash, headless) {
                let open = open_window(py, &mut state, &splash);
                state.splash = state.window_id_of(py, &splash);
                if state.splash.is_some() {
                    let seconds = splash
                        .getattr("duration")
                        .and_then(|v| v.extract::<f64>())
                        .unwrap_or(1.0)
                        .clamp(0.0, 60.0);
                    let done = after(seconds).map(|_| Message::SplashDone);
                    return (state, Task::batch([open, theme, done]));
                }
            }
            let open = open_window(py, &mut state, &bound);
            state.main = state.windows.keys().next().copied();
            let start = start_task(py, &mut state, &bound);
            sync_targets(py, &state);
            (state, Task::batch([open, theme, start]))
        })
    };

    iced_winit::quiet::set_filter(quiet);
    iced_winit::quiet::set_unchanged(unchanged);
    iced::daemon(boot, update, view)
        .title(title)
        .theme(theme_of)
        .subscription(subscription)
        .scale_factor(scale_factor)
        .settings(iced::Settings {
            default_font: Font::with_name(sans()),
            default_text_size: font_size.into(),
            antialiasing: true,
            ..Default::default()
        })
}

pub(crate) fn font_size(app: &Bound<'_, PyAny>) -> PyResult<f32> {
    match app.getattr("font_size").ok().filter(|v| !v.is_none()) {
        Some(v) => v.extract(),
        None => Ok(14.0),
    }
}

/// Opens the app's window and runs it until it is closed.
#[pyfunction]
pub fn run(py: Python<'_>, app: Py<PyAny>) -> PyResult<()> {
    static STARTED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
    if STARTED.swap(true, std::sync::atomic::Ordering::SeqCst) {
        // winit can only create one event loop per process.
        return Err(PyRuntimeError::new_err(
            "pz.run() can only be called once per process; open more windows with Command.open_window",
        ));
    }
    py.detach(fonts::ensure_loaded);
    window_settings(app.bind(py))?;
    let size = font_size(app.bind(py))?;
    open_post_channel();
    let _ = APP_THREAD.set(std::thread::current().id());
    RUNNING.store(true, std::sync::atomic::Ordering::SeqCst);
    if crate::tray::pending() {
        wake(); // tray icons asked for before the event loop show on its first update
    }
    let result = py.detach(move || daemon(app, size, false).run());
    RUNNING.store(false, std::sync::atomic::Ordering::SeqCst);
    crate::tray::clear();
    *POST.lock().unwrap() = None;
    result.map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

/// Renders `app` off-screen (no window, no GPU needed) and saves it as a PNG.
#[pyfunction]
#[pyo3(signature = (app, path, *, size=None, scale=2.0, wait=0.1))]
pub fn screenshot(
    py: Python<'_>,
    app: Py<PyAny>,
    path: std::path::PathBuf,
    size: Option<(f32, f32)>,
    scale: f32,
    wait: f64,
) -> PyResult<()> {
    py.detach(fonts::ensure_loaded);
    let settings = window_settings(app.bind(py))?;
    let viewport = size.map(|(w, h)| Size::new(w, h)).unwrap_or(settings.size);
    let font_size = font_size(app.bind(py))?;
    let theme = palette_key(app.bind(py))
        .and_then(|k| build_theme(&k))
        .unwrap_or(Theme::Dark);
    open_post_channel();
    // Media queries see the screenshot's size.
    let style = py.import("pyzed.style")?;
    style.setattr("_screen", (viewport.width, viewport.height))?;
    // Animations show their resting state, so a screenshot doesn't depend on timing.
    crate::animation::set_screenshot(true);
    let shot = py.detach(move || {
        let program = daemon(app, font_size, true);
        iced_test::screenshot(
            &program,
            &theme,
            viewport,
            scale,
            Duration::from_secs_f64(wait),
        )
    });
    *POST.lock().unwrap() = None;
    crate::animation::set_screenshot(false);
    style.setattr("_screen", py.None())?;

    let file = std::fs::File::create(&path)?;
    let mut encoder = png::Encoder::new(
        std::io::BufWriter::new(file),
        shot.size.width,
        shot.size.height,
    );
    encoder.set_color(png::ColorType::Rgba);
    encoder.set_depth(png::BitDepth::Eight);
    let mut writer = encoder
        .write_header()
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    writer
        .write_image_data(&shot.rgba)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(())
}
