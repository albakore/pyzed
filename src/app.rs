//! The iced program that drives a Python `App` (Elm architecture: state, update, view).

use std::cell::RefCell;
use std::collections::HashMap;
use std::sync::{Arc, LazyLock, Mutex};
use std::time::Duration;

use iced::futures::channel::{mpsc, oneshot};
use iced::futures::{Stream, StreamExt, stream};
use iced::keyboard::{self, Key, key::Named};
use iced::widget::{column, container, scrollable, text, text_editor};
use iced::{Color, Element, Font, Length, Size, Subscription, Task, Theme};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyList, PyTuple, PyType};

use crate::fonts;
use crate::render::{self, Ctx, Editors};
use crate::style::{MONO, SANS};
use crate::widget::PyMsg;

pub struct EditorState {
    pub content: text_editor::Content,
}

impl EditorState {
    pub fn new(text: &str) -> Self {
        Self {
            content: text_editor::Content::with_text(text),
        }
    }
}

pub struct State {
    app: Py<PyAny>,
    editors: Editors,
    /// Cursor moves requested for editors that have not been rendered yet.
    pending_cursors: RefCell<HashMap<String, text_editor::Position>>,
    theme: RefCell<Option<(Vec<String>, Theme)>>,
}

#[derive(Debug, Clone)]
pub enum Message {
    Py(PyMsg),
    Input(PyMsg, String),
    Toggle(PyMsg, bool),
    Slide(PyMsg, f32),
    Call(PyMsg, PyMsg),
    Editor {
        id: Arc<str>,
        action: text_editor::Action,
        on_change: Option<PyMsg>,
        on_cursor: Option<PyMsg>,
    },
    Key(String),
    Noop,
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
}

/// Side effects returned from `App.update` (or from a callback): `return Command.focus("search")`.
#[pyclass(module = "pyzed._core", frozen)]
pub struct Command {
    kind: CommandKind,
}

#[pymethods]
impl Command {
    /// Closes the application.
    #[staticmethod]
    fn exit() -> Self {
        Self {
            kind: CommandKind::Exit,
        }
    }

    /// Focuses the `text_input` (or editor) with the given `id`.
    #[staticmethod]
    fn focus(id: String) -> Self {
        Self {
            kind: CommandKind::Focus(id),
        }
    }

    /// Replaces the contents of the `code_editor` with the given `id`.
    #[staticmethod]
    fn set_editor_text(id: String, text: String) -> Self {
        Self {
            kind: CommandKind::SetEditorText(id, text),
        }
    }

    /// Moves the cursor of the `code_editor` with the given `id` (1-based line and column).
    #[staticmethod]
    fn set_editor_cursor(id: String, line: usize, column: usize) -> Self {
        Self {
            kind: CommandKind::SetEditorCursor(id, line, column),
        }
    }

    /// Scrolls the `scrollable` with the given `id` to its end.
    #[staticmethod]
    fn scroll_to_end(id: String) -> Self {
        Self {
            kind: CommandKind::ScrollToEnd(id),
        }
    }

    /// Runs several commands.
    #[staticmethod]
    fn batch(commands: Vec<Py<Command>>) -> Self {
        Self {
            kind: CommandKind::Batch(commands),
        }
    }

    /// Feeds `message` back into `update` on the next tick.
    #[staticmethod]
    fn message(message: &Bound<'_, PyAny>) -> Self {
        Self {
            kind: CommandKind::Message(PyMsg::new(message)),
        }
    }

    /// Runs `function()` in a background thread and calls `then(result)` on the UI thread.
    #[staticmethod]
    #[pyo3(signature = (function, then=None))]
    fn perform(function: &Bound<'_, PyAny>, then: Option<Bound<'_, PyAny>>) -> Self {
        Self {
            kind: CommandKind::Perform(PyMsg::new(function), PyMsg::maybe(&then)),
        }
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
        return Task::none();
    };
    match &command.get().kind {
        CommandKind::Exit => iced::exit(),
        CommandKind::Focus(id) => iced::widget::operation::focus(id.clone()),
        CommandKind::ScrollToEnd(id) => iced::widget::operation::snap_to_end(id.clone()),
        CommandKind::SetEditorText(id, text) => {
            let editors = state.editors.as_mut();
            match editors.get_mut(id) {
                Some(editor) => editor.content = text_editor::Content::with_text(text),
                None => {
                    editors.insert(id.clone(), Box::new(EditorState::new(text)));
                }
            }
            Task::none()
        }
        CommandKind::SetEditorCursor(id, line, column) => {
            let position = text_editor::Position {
                line: line.saturating_sub(1),
                column: column.saturating_sub(1),
            };
            match state.editors.as_mut().get_mut(id) {
                Some(editor) => editor.content.move_to(text_editor::Cursor {
                    position,
                    selection: None,
                }),
                None => {
                    state
                        .pending_cursors
                        .borrow_mut()
                        .insert(id.clone(), position);
                }
            }
            Task::none()
        }
        CommandKind::Batch(commands) => Task::batch(
            commands
                .iter()
                .map(|c| command_task(py, state, c.bind(py).as_any()))
                .collect::<Vec<_>>(),
        ),
        CommandKind::Message(msg) => Task::done(Message::Py(msg.clone())),
        CommandKind::Perform(function, then) => {
            let function = function.clone();
            let then = then.clone();
            let (sender, receiver) = oneshot::channel();
            std::thread::spawn(move || {
                let result = Python::attach(|py| match function.0.bind(py).call0() {
                    Ok(value) => Some(PyMsg::new(&value)),
                    Err(err) => {
                        err.print(py);
                        None
                    }
                });
                let _ = sender.send(result);
            });
            Task::perform(receiver, move |result| match (result, &then) {
                (Ok(Some(value)), Some(then)) => Message::Call(then.clone(), value),
                (Ok(Some(value)), None) => Message::Py(value),
                _ => Message::Noop,
            })
        }
    }
}

// ---------------------------------------------------------------------------
// Update / view
// ---------------------------------------------------------------------------

/// Sends `message` to `app.update`, or calls it when it is a plain callable (lambda, method...).
fn dispatch<'py>(
    app: &Bound<'py, PyAny>,
    message: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    if message.is_callable() && !message.is_instance_of::<PyType>() {
        let result = message.call0()?;
        if result.is_none() || result.cast::<Command>().is_ok() {
            return Ok(result);
        }
        return app.call_method1("update", (result,));
    }
    app.call_method1("update", (message,))
}

/// Calls `callback(*args)` and dispatches whatever it returns.
fn callback<'py>(
    app: &Bound<'py, PyAny>,
    callback: &Bound<'py, PyAny>,
    args: impl pyo3::call::PyCallArgs<'py>,
) -> PyResult<Bound<'py, PyAny>> {
    let result = callback.call1(args)?;
    if result.is_none() || result.cast::<Command>().is_ok() {
        return Ok(result);
    }
    if result.is_callable() && !result.is_instance_of::<PyType>() {
        return dispatch(app, &result);
    }
    app.call_method1("update", (result,))
}

fn update(state: &mut State, message: Message) -> Task<Message> {
    Python::attach(|py| {
        let app = state.app.bind(py).clone();
        let result = match message {
            Message::Noop => return Task::none(),
            Message::Py(msg) => dispatch(&app, msg.0.bind(py)),
            Message::Input(cb, value) => callback(&app, cb.0.bind(py), (value,)),
            Message::Toggle(cb, value) => callback(&app, cb.0.bind(py), (value,)),
            Message::Slide(cb, value) => callback(&app, cb.0.bind(py), (value,)),
            Message::Call(cb, value) => callback(&app, cb.0.bind(py), (value.0.bind(py),)),
            Message::Key(combo) => {
                if app.hasattr("on_key").unwrap_or(false) {
                    match app.call_method1("on_key", (combo,)) {
                        Ok(result) if result.is_none() || result.cast::<Command>().is_ok() => {
                            Ok(result)
                        }
                        Ok(result) => dispatch(&app, &result),
                        Err(err) => Err(err),
                    }
                } else {
                    return Task::none();
                }
            }
            Message::Editor {
                id,
                action,
                on_change,
                on_cursor,
            } => {
                let Some(editor) = state.editors.as_mut().get_mut(&*id) else {
                    return Task::none();
                };
                let before = editor.content.cursor().position;
                let is_edit = action.is_edit();
                editor.content.perform(action);
                let after = editor.content.cursor().position;
                let mut result = Ok(py.None().into_bound(py));
                if is_edit && let Some(cb) = on_change {
                    let text = editor.content.text();
                    result = callback(&app, cb.0.bind(py), (text,));
                }
                if (before != after || is_edit)
                    && let Some(cb) = on_cursor
                    && result.is_ok()
                {
                    result = callback(&app, cb.0.bind(py), (after.line + 1, after.column + 1));
                }
                result
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

fn error_view<'a>(message: String) -> Element<'a, Message> {
    let red = Color::from_rgb8(0xd0, 0x72, 0x77);
    container(
        column![
            text("Python error in view()")
                .size(18)
                .color(red)
                .font(Font::with_name(SANS)),
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

fn format_error(py: Python<'_>, err: &PyErr) -> String {
    let formatted = py.import("traceback").and_then(|tb| {
        tb.call_method1("format_exception", (err.value(py),))
            .and_then(|lines| lines.extract::<Vec<String>>())
    });
    match formatted {
        Ok(lines) => lines.concat(),
        Err(_) => err.to_string(),
    }
}

fn view(state: &State) -> Element<'_, Message> {
    Python::attach(|py| {
        let app = state.app.bind(py);
        let method = if app.hasattr("__pyzed_view__").unwrap_or(false) {
            "__pyzed_view__"
        } else {
            "view"
        };
        let root = app
            .call_method0(method)
            .and_then(|w| crate::widget::child(&w));
        match root {
            Ok(root) => render::build(
                py,
                &root,
                &Ctx {
                    editors: &state.editors,
                    pending_cursors: &state.pending_cursors,
                },
            ),
            Err(err) => {
                err.print(py);
                error_view(format_error(py, &err))
            }
        }
    })
}

fn palette_key(app: &Bound<'_, PyAny>) -> Option<Vec<String>> {
    let palette = app.call_method0("__pyzed_palette__").ok()?;
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

fn theme_of(state: &State) -> Theme {
    Python::attach(|py| {
        let Some(key) = palette_key(state.app.bind(py)) else {
            return Theme::Dark;
        };
        let mut cache = state.theme.borrow_mut();
        if let Some((cached_key, theme)) = cache.as_ref()
            && *cached_key == key
        {
            return theme.clone();
        }
        let theme = build_theme(&key).unwrap_or(Theme::Dark);
        *cache = Some((key, theme.clone()));
        theme
    })
}

fn title(state: &State) -> String {
    Python::attach(|py| {
        let app = state.app.bind(py);
        let Ok(title) = app.getattr("title") else {
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

// ---------------------------------------------------------------------------
// Subscriptions: keyboard shortcuts + messages posted from other threads.
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

fn key_message(event: keyboard::Event) -> Option<Message> {
    let keyboard::Event::KeyPressed { key, modifiers, .. } = event else {
        return None;
    };
    let name = key_name(&key)?;
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
    Some(Message::Key(combo))
}

fn key_event(
    event: iced::Event,
    _status: iced::event::Status,
    _window: iced::window::Id,
) -> Option<Message> {
    match event {
        iced::Event::Keyboard(event) => key_message(event),
        _ => None,
    }
}

fn subscription(_state: &State) -> Subscription<Message> {
    // Every key press is reported (even those a focused input handled), like a global keymap.
    Subscription::batch([
        iced::event::listen_with(key_event),
        Subscription::run(post_stream),
    ])
}

// ---------------------------------------------------------------------------
// Entry points
// ---------------------------------------------------------------------------

struct WindowOptions {
    size: Size,
    min_size: Option<Size>,
    resizable: bool,
    decorations: bool,
    scale: f32,
    font_size: f32,
}

fn window_options(app: &Bound<'_, PyAny>) -> PyResult<WindowOptions> {
    let attr = |name: &str| app.getattr(name).ok().filter(|v| !v.is_none());
    let size = match attr("size") {
        Some(v) => {
            let (w, h): (f32, f32) = v.extract()?;
            Size::new(w, h)
        }
        None => Size::new(1280.0, 800.0),
    };
    let min_size = match attr("min_size") {
        Some(v) => {
            let (w, h): (f32, f32) = v.extract()?;
            Some(Size::new(w, h))
        }
        None => None,
    };
    Ok(WindowOptions {
        size,
        min_size,
        resizable: attr("resizable")
            .map(|v| v.is_truthy())
            .transpose()?
            .unwrap_or(true),
        decorations: attr("decorations")
            .map(|v| v.is_truthy())
            .transpose()?
            .unwrap_or(true),
        scale: attr("scale")
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(1.0),
        font_size: attr("font_size")
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(14.0),
    })
}

fn program(
    app: Py<PyAny>,
    options: WindowOptions,
) -> iced::Application<impl iced::Program<State = State, Message = Message, Theme = Theme>> {
    let scale = options.scale;
    let boot = move || {
        Python::attach(|py| {
            let mut state = State {
                app: app.clone_ref(py),
                editors: Editors::new(),
                pending_cursors: RefCell::new(HashMap::new()),
                theme: RefCell::new(None),
            };
            let bound = app.bind(py);
            let task = match bound.hasattr("on_start") {
                Ok(true) => match bound.call_method0("on_start") {
                    Ok(value) => command_task(py, &mut state, &value),
                    Err(err) => {
                        err.print(py);
                        Task::none()
                    }
                },
                _ => Task::none(),
            };
            (state, task)
        })
    };

    iced::application(boot, update, view)
        .title(title)
        .theme(theme_of)
        .subscription(subscription)
        .scale_factor(move |_| scale)
        .default_font(Font::with_name(SANS))
        .window(iced::window::Settings {
            size: options.size,
            min_size: options.min_size,
            resizable: options.resizable,
            decorations: options.decorations,
            ..Default::default()
        })
        .settings(iced::Settings {
            default_font: Font::with_name(SANS),
            default_text_size: options.font_size.into(),
            antialiasing: true,
            ..Default::default()
        })
}

/// Opens a window and runs `app` until it is closed.
#[pyfunction]
pub fn run(py: Python<'_>, app: Py<PyAny>) -> PyResult<()> {
    fonts::ensure_loaded();
    let options = window_options(app.bind(py))?;
    open_post_channel();
    let result = py.detach(move || program(app, options).run());
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
    let mut options = window_options(app.bind(py))?;
    if let Some((w, h)) = size {
        options.size = Size::new(w, h);
    }
    let viewport = options.size;
    let theme = palette_key(app.bind(py))
        .and_then(|k| build_theme(&k))
        .unwrap_or(Theme::Dark);
    open_post_channel();
    let shot = py.detach(move || {
        let program = program(app, options);
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
