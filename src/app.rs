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
use pyo3::types::{PyCFunction, PyDict, PyList, PyTuple, PyType};

use crate::fonts;
use crate::render::{self, Caches, Ctx};
use crate::style::{MONO, SANS};
use crate::widget::PyMsg;

pub struct State {
    /// The `App` instance (also the main window).
    app: Py<PyAny>,
    main: Option<window::Id>,
    windows: HashMap<window::Id, Py<PyAny>>,
    /// The window whose message is being handled (commands without a window target it).
    current: Option<window::Id>,
    caches: Caches,
    themes: RefCell<HashMap<Vec<String>, Theme>>,
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
        key: crate::editor::IndentKey,
        size: usize,
        on_change: Option<PyMsg>,
        on_cursor: Option<PyMsg>,
    },
    Scrolled(PyMsg, scrollable::Viewport),
    Key(String),
    /// A message produced inside the given window.
    Windowed(window::Id, Box<Message>),
    WindowOpened(window::Id),
    CloseRequested(window::Id),
    WindowClosed(window::Id),
    WindowResized(window::Id, Size),
    SystemTheme(iced::theme::Mode),
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
// Commands: values returned from `update()` that ask the runtime to do something.
// ---------------------------------------------------------------------------

enum CommandKind {
    Exit,
    Focus(String),
    SetEditorText(String, String),
    SetEditorCursor(String, usize, usize),
    Batch(Vec<Py<Command>>),
    Message(PyMsg),
    Perform(PyMsg, Option<PyMsg>),
    ScrollToEnd(String),
    ScrollTo(String, f32, f32),
    OpenWindow(PyMsg),
    CloseWindow(Option<PyMsg>),
    Window(WindowOp, Option<PyMsg>),
    CopyToClipboard(String),
    ReadClipboard(PyMsg),
}

#[derive(Clone, Copy)]
enum WindowOp {
    Drag,
    Minimize,
    ToggleMaximize,
    Fullscreen(bool),
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

    /// Switches the window between fullscreen and windowed mode.
    #[staticmethod]
    #[pyo3(signature = (fullscreen=true, window=None))]
    fn set_fullscreen(fullscreen: bool, window: Option<Bound<'_, PyAny>>) -> Self {
        cmd(CommandKind::Window(
            WindowOp::Fullscreen(fullscreen),
            PyMsg::maybe(&window),
        ))
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

    fn __repr__(&self) -> &'static str {
        match self.kind {
            CommandKind::Exit => "Command.exit()",
            CommandKind::Focus(_) => "Command.focus(...)",
            CommandKind::SetEditorText(..) => "Command.set_editor_text(...)",
            CommandKind::SetEditorCursor(..) => "Command.set_editor_cursor(...)",
            CommandKind::Batch(_) => "Command.batch(...)",
            CommandKind::Message(_) => "Command.message(...)",
            CommandKind::Perform(..) => "Command.perform(...)",
            CommandKind::ScrollToEnd(_) => "Command.scroll_to_end(...)",
            CommandKind::ScrollTo(..) => "Command.scroll_to(...)",
            CommandKind::OpenWindow(_) => "Command.open_window(...)",
            CommandKind::CloseWindow(_) => "Command.close_window(...)",
            CommandKind::Window(..) => "Command.<window operation>(...)",
            CommandKind::CopyToClipboard(_) => "Command.copy(...)",
            CommandKind::ReadClipboard(_) => "Command.paste(...)",
        }
    }
}

/// Whether `value` is a coroutine, awaitable, generator or async generator.
fn is_deferred(value: &Bound<'_, PyAny>) -> bool {
    value.hasattr("__await__").unwrap_or(false)
        || value.hasattr("__anext__").unwrap_or(false)
        || (value.hasattr("send").unwrap_or(false) && value.hasattr("__next__").unwrap_or(false))
}

/// Runs `function()` (or awaits / iterates `value`) off the UI thread, turning every
/// produced value into a message.
fn background(source: PyMsg, call: bool, then: Option<PyMsg>) -> Task<Message> {
    let (sender, receiver) = mpsc::unbounded::<Message>();
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
                py.import("pyzed._async")?
                    .call_method1("drain", (value, emit))
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
        CommandKind::Batch(commands) => Task::batch(
            commands
                .iter()
                .map(|c| command_task(py, state, c.bind(py).as_any()))
                .collect::<Vec<_>>(),
        ),
        CommandKind::Message(msg) => Task::done(Message::Py(msg.clone())),
        CommandKind::Perform(function, then) => {
            // A coroutine or generator object (not a function) is drained as is.
            let call = !is_deferred(function.0.bind(py));
            background(function.clone(), call, then.clone())
        }
        CommandKind::OpenWindow(obj) => open_window(py, state, obj.0.bind(py)),
        CommandKind::CloseWindow(obj) => match resolve_window(py, state, obj) {
            Some(id) => window::close(id),
            None => Task::none(),
        },
        CommandKind::Window(op, obj) => {
            let Some(id) = resolve_window(py, state, obj) else {
                return Task::none();
            };
            match *op {
                WindowOp::Drag => window::drag(id),
                WindowOp::Minimize => window::minimize(id, true),
                WindowOp::ToggleMaximize => window::toggle_maximize(id),
                WindowOp::Fullscreen(on) => window::set_mode(
                    id,
                    if on {
                        window::Mode::Fullscreen
                    } else {
                        window::Mode::Windowed
                    },
                ),
                WindowOp::Resize(w, h) => window::resize(id, Size::new(w, h)),
                WindowOp::Move(x, y) => window::move_to(id, Point::new(x, y)),
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
    }
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

fn window_settings(obj: &Bound<'_, PyAny>) -> PyResult<window::Settings> {
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
                window::Position::Specific(Point::new(x, y))
            }
        },
    };
    Ok(window::Settings {
        size: size_of("size")?.unwrap_or(Size::new(1280.0, 800.0)),
        min_size: size_of("min_size")?,
        max_size: size_of("max_size")?,
        position,
        resizable: flag("resizable", true)?,
        decorations: flag("decorations", true)?,
        transparent: flag("transparent", false)?,
        maximized: flag("maximized", false)?,
        fullscreen: flag("fullscreen", false)?,
        exit_on_close_request: false,
        ..Default::default()
    })
}

// ---------------------------------------------------------------------------
// Update / view
// ---------------------------------------------------------------------------

/// Returned values that the runtime handles itself instead of passing them to `update`.
fn is_final(value: &Bound<'_, PyAny>) -> bool {
    value.is_none()
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
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let kwargs = PyDict::new(py);
    kwargs.set_item("x", data.x)?;
    kwargs.set_item("y", data.y)?;
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
fn editor_outcome(
    py: Python<'_>,
    state: &mut State,
    target: &Bound<'_, PyAny>,
    outcome: crate::editor::Outcome,
    on_change: Option<PyMsg>,
    on_cursor: Option<PyMsg>,
) -> Task<Message> {
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
    let scroll = outcome.scroll;
    match result {
        Ok(value) => Task::batch([scroll, command_task(py, state, &value)]),
        Err(err) => {
            err.print(py);
            scroll
        }
    }
}

fn update(state: &mut State, message: Message) -> Task<Message> {
    state.caches.prune();
    if let Message::Windowed(id, inner) = message {
        let previous = state.current.replace(id);
        let task = update(state, *inner);
        state.current = previous;
        return if Some(id) == state.main {
            task
        } else {
            task.map(move |m| m.in_window(id))
        };
    }
    Python::attach(|py| {
        let target = match state.current {
            Some(id) => state.window(id).bind(py).clone(),
            None => state.app.bind(py).clone(),
        };
        let result = match message {
            Message::Noop | Message::Windowed(..) => return Task::none(),
            Message::Py(msg) => dispatch(&target, msg.0.bind(py)),
            Message::Input(cb, value) => callback(&target, cb.0.bind(py), (value,)),
            Message::Toggle(cb, value) => callback(&target, cb.0.bind(py), (value,)),
            Message::Slide(cb, value) => callback(&target, cb.0.bind(py), (value,)),
            Message::Point(cb, x, y) => callback(&target, cb.0.bind(py), (x, y)),
            Message::Call(cb, value) => callback(&target, cb.0.bind(py), (value.0.bind(py),)),
            Message::Event(cb, data) => deliver_event(&target, cb.0.bind(py), &data),
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
            Message::Editor {
                id,
                action,
                on_change,
                on_cursor,
            } => {
                let Some(outcome) = state.caches.perform_editor(&id, action) else {
                    return Task::none();
                };
                return editor_outcome(py, state, &target, outcome, on_change, on_cursor);
            }
            Message::EditorIndent {
                id,
                key,
                size,
                on_change,
                on_cursor,
            } => {
                let Some(outcome) = state.caches.indent_editor(&id, key, size) else {
                    return Task::none();
                };
                return editor_outcome(py, state, &target, outcome, on_change, on_cursor);
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
                match call_hook(&obj, "on_open", ()) {
                    Some(result) => result,
                    None => return Task::none(),
                }
            }
            Message::CloseRequested(id) => {
                let obj = state.window(id).bind(py).clone();
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
                    window::close(id)
                } else {
                    Task::none()
                };
            }
            Message::WindowClosed(id) => {
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
                let _ = obj.setattr("window_size", (size.width, size.height));
                match call_hook(&obj, "on_resize", (size.width, size.height)) {
                    Some(result) => result,
                    None => return Task::none(),
                }
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

fn error_view<'a>(title: &'static str, message: String) -> Element<'a, Message> {
    let red = Color::from_rgb8(0xd0, 0x72, 0x77);
    container(
        column![
            text(title).size(18).color(red).font(Font::with_name(SANS)),
            scrollable(
                text(message)
                    .size(13)
                    .font(Font::with_name(MONO))
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
        let method = if obj.hasattr("__pyzed_view__").unwrap_or(false) {
            "__pyzed_view__"
        } else {
            "view"
        };
        let root = obj
            .call_method0(method)
            .and_then(|w| crate::widget::child(&w));
        match root {
            Ok(root) => render::build(py, &root, Ctx::new(&state.caches)),
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
    if state.windows.contains_key(&id) && Some(id) != state.main {
        element.map(move |m| m.in_window(id))
    } else {
        element
    }
}

fn palette_key(obj: &Bound<'_, PyAny>) -> Option<Vec<String>> {
    let palette = obj.call_method0("__pyzed_palette__").ok()?;
    palette.extract::<Vec<String>>().ok()
}

fn build_theme(key: &[String]) -> Option<Theme> {
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
        state
            .window(id)
            .bind(py)
            .getattr("scale")
            .and_then(|s| s.extract::<f32>())
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

fn open_post_channel() {
    let (sender, receiver) = mpsc::unbounded();
    *POST.lock().unwrap() = Some(sender);
    *POST_RECEIVER.lock().unwrap() = Some(receiver);
}

fn post_stream() -> impl Stream<Item = Message> {
    match POST_RECEIVER.lock().unwrap().take() {
        Some(receiver) => receiver.boxed(),
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

fn key_message(event: keyboard::Event) -> Option<Message> {
    let keyboard::Event::KeyPressed { key, modifiers, .. } = event else {
        return None;
    };
    key_combo(&key, modifiers).map(Message::Key)
}

fn key_event(
    event: iced::Event,
    _status: iced::event::Status,
    window: window::Id,
) -> Option<Message> {
    match event {
        iced::Event::Keyboard(event) => key_message(event).map(|m| m.in_window(window)),
        _ => None,
    }
}

/// A timer or stream declared by `App.subscriptions()`.
enum SubscriptionKind {
    Every { interval: Duration, message: PyMsg },
    Stream { function: PyMsg },
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

#[derive(Clone)]
struct Recipe {
    key: String,
    window: Option<window::Id>,
    every: Option<(Duration, PyMsg)>,
    stream: Option<PyMsg>,
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
    if !obj.hasattr("subscriptions").unwrap_or(false) {
        return Vec::new();
    }
    let value = match obj.call_method0("subscriptions") {
        Ok(v) => v,
        Err(err) => {
            err.print(py);
            return Vec::new();
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
            },
            SubscriptionKind::Stream { function } => Recipe {
                key: s.key.clone(),
                window,
                every: None,
                stream: Some(function.clone()),
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
        iced::system::theme_changes().map(Message::SystemTheme),
    ];
    Python::attach(|py| {
        let mut recipes = python_subscriptions(py, state.app.bind(py), None);
        for (id, obj) in &state.windows {
            if Some(*id) != state.main {
                recipes.extend(python_subscriptions(py, obj.bind(py), Some(*id)));
            }
        }
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

fn daemon(
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
                current: None,
                caches: Caches::default(),
                themes: RefCell::new(HashMap::new()),
            };
            let bound = app.bind(py).clone();
            let open = open_window(py, &mut state, &bound);
            state.main = state.windows.keys().next().copied();
            let start = match bound.hasattr("on_start") {
                Ok(true) => match bound.call_method0("on_start") {
                    Ok(value) => command_task(py, &mut state, &value),
                    Err(err) => {
                        err.print(py);
                        Task::none()
                    }
                },
                _ => Task::none(),
            };
            // The off-screen emulator can't answer theme queries; screenshots keep `system_dark`.
            let theme = if headless {
                Task::none()
            } else {
                iced::system::theme().map(Message::SystemTheme)
            };
            (state, Task::batch([open, theme, start]))
        })
    };

    iced::daemon(boot, update, view)
        .title(title)
        .theme(theme_of)
        .subscription(subscription)
        .scale_factor(scale_factor)
        .settings(iced::Settings {
            default_font: Font::with_name(SANS),
            default_text_size: font_size.into(),
            antialiasing: true,
            ..Default::default()
        })
}

fn font_size(app: &Bound<'_, PyAny>) -> PyResult<f32> {
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
    fonts::ensure_loaded();
    window_settings(app.bind(py))?;
    let size = font_size(app.bind(py))?;
    open_post_channel();
    let result = py.detach(move || daemon(app, size, false).run());
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
    fonts::ensure_loaded();
    let settings = window_settings(app.bind(py))?;
    let viewport = size.map(|(w, h)| Size::new(w, h)).unwrap_or(settings.size);
    let font_size = font_size(app.bind(py))?;
    let theme = palette_key(app.bind(py))
        .and_then(|k| build_theme(&k))
        .unwrap_or(Theme::Dark);
    open_post_channel();
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
