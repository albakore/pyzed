//! Off-screen recording: drives an app with a scripted pointer and keyboard and a virtual
//! clock, and hands back one RGBA frame per `snap` (docs/scripts/anim_webp.py turns them
//! into animated WebP).
//!
//! `pz.screenshot` boots the app in `iced_test`'s emulator and draws one frame with no
//! pointer. Recording needs what a screenshot leaves out: the pointer's position when the
//! view is drawn (hover states, tooltips), events in between frames (press, release, wheel,
//! keys, typed text) and time that moves by a fixed step per frame, so the result is the
//! same on every machine however long a frame takes to render. This module is a small
//! headless runtime in the shape of `iced_test::Emulator` that keeps those three.
//!
//! The script is a Python generator: Rust sends it the result of the last command and
//! receives the next one, until it returns. Commands are tuples:
//!
//! - `("move", x, y)`: the pointer moves to `(x, y)` (logical pixels).
//! - `("down", button)` / `("up", button)`: `"left"`, `"right"` or `"middle"`.
//! - `("scroll", dx, dy)`: the wheel, in lines (positive `dy` scrolls content up).
//! - `("key", name, modifiers)`: a key press and release (`"Enter"`, `"Tab"`, `"a"`...);
//!   `modifiers` is a string holding any of `ctrl`, `shift`, `alt`, `logo`.
//! - `("type", text)`: types each character of `text`.
//! - `("leave",)`: the pointer leaves the window.
//! - `("advance", seconds)`: the clock moves forward (and a redraw is delivered).
//! - `("snap",)`: draws a frame; the result is its RGBA bytes.
//! - `("probe",)`: the result is `[(kind, text, x, y, w, h), ...]`, the bounds of the texts,
//!   inputs, focusable widgets, scrollables and containers of the view (to aim the pointer).
//! - `("size",)`: the result is the frame size in pixels, `(width, height)`.
//!
//! Creating a renderer (a GPU device and its pipelines) costs more than drawing many frames,
//! above all with a software Vulkan driver, so each thread keeps the renderers it made and
//! every later recording and screenshot on that thread reuses them.

use std::any::Any;
use std::cell::RefCell;
use std::collections::HashMap;
use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use iced::Theme;
use iced_test::core::keyboard;
use iced_test::core::mouse;
use iced_test::core::renderer::{self, Headless};
use iced_test::core::widget::{self, Operation};
use iced_test::core::window;
use iced_test::core::{Event, Rectangle, Size, SmolStr};
use iced_test::program::Program;
use iced_test::runtime::futures::futures::StreamExt;
use iced_test::runtime::futures::futures::channel::mpsc;
use iced_test::runtime::futures::{Executor, Runtime};
use iced_test::runtime::{self, Task, UserInterface, task, user_interface};
use pyo3::exceptions::{PyStopIteration, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList, PyTuple};

// ---------------------------------------------------------------------------
// The clock
// ---------------------------------------------------------------------------

/// While a recording runs, the time that animations, presences, carets and shaders see.
static VIRTUAL: Mutex<Option<Instant>> = Mutex::new(None);

/// The current time: the recording's virtual clock while one runs, the real clock otherwise.
pub fn now() -> Instant {
    VIRTUAL.lock().unwrap().unwrap_or_else(Instant::now)
}

fn set_clock(at: Option<Instant>) {
    *VIRTUAL.lock().unwrap() = at;
}

// ---------------------------------------------------------------------------
// Renderers
// ---------------------------------------------------------------------------

thread_local! {
    /// The renderers this thread made, by backend and default text size.
    static RENDERERS: RefCell<HashMap<(String, u32), Box<dyn Any>>> = RefCell::new(HashMap::new());
}

/// Set when a `pz.shader` is drawn: the CPU renderer shows its fallback instead, so a recording
/// made with it starts again on the GPU renderer.
static SHADER_DRAWN: AtomicBool = AtomicBool::new(false);

pub fn shader_drawn() {
    SHADER_DRAWN.store(true, Ordering::Relaxed);
}

/// `None` (the GPU renderer, or the CPU one when there is no GPU), `"wgpu"` or `"tiny-skia"`.
fn backend_key(backend: Option<&str>) -> PyResult<Option<&'static str>> {
    match backend {
        None | Some("auto") => Ok(None),
        Some("wgpu" | "gpu") => Ok(Some("wgpu")),
        Some("tiny-skia" | "tiny_skia" | "cpu") => Ok(Some("tiny-skia")),
        Some(other) => Err(PyValueError::new_err(format!(
            "unknown renderer {other:?} (use \"auto\", \"gpu\" or \"cpu\")"
        ))),
    }
}

/// A renderer for `backend`: the one this thread kept, or a new one.
fn take_renderer<R: Headless + 'static>(
    backend: Option<&'static str>,
    font_size: f32,
) -> PyResult<R> {
    let key = (backend.unwrap_or("auto").to_owned(), font_size.to_bits());
    if let Some(kept) = RENDERERS.with(|r| r.borrow_mut().remove(&key))
        && let Ok(renderer) = kept.downcast::<R>()
    {
        return Ok(*renderer);
    }
    let font = iced::Font::with_name(crate::style::sans());
    iced_test::runtime::futures::futures::executor::block_on(R::new(
        font,
        font_size.into(),
        backend,
    ))
    .ok_or_else(|| {
        pyo3::exceptions::PyRuntimeError::new_err(format!(
            "no {} renderer on this machine",
            backend.unwrap_or("off-screen")
        ))
    })
}

/// The renderer to draw `program` with (`take_renderer` for its renderer type).
fn renderer_for<P: Program>(
    _program: &P,
    backend: Option<&'static str>,
    font_size: f32,
) -> PyResult<P::Renderer>
where
    P::Renderer: 'static,
{
    take_renderer(backend, font_size)
}

fn keep_renderer<R: 'static>(backend: Option<&'static str>, font_size: f32, renderer: R) {
    let key = (backend.unwrap_or("auto").to_owned(), font_size.to_bits());
    RENDERERS.with(|r| {
        r.borrow_mut().insert(key, Box::new(renderer));
    });
}

// ---------------------------------------------------------------------------
// The driver
// ---------------------------------------------------------------------------

enum Action<M> {
    Runtime(runtime::Action<M>),
}

type DriverRuntime<E, M> = Runtime<E, mpsc::Sender<Action<M>>, Action<M>>;

struct Driver<P: Program> {
    state: P::State,
    runtime: DriverRuntime<P::Executor, P::Message>,
    receiver: mpsc::Receiver<Action<P::Message>>,
    renderer: P::Renderer,
    size: Size,
    window: window::Id,
    cursor: mouse::Cursor,
    clipboard: Clipboard,
    cache: Option<user_interface::Cache>,
    clock: Instant,
    /// The clock moved and the view hasn't seen it yet (the next event or frame delivers it).
    stale: bool,
}

impl<P: Program<Theme = Theme> + 'static> Driver<P> {
    fn new(program: &P, size: Size, clock: Instant, renderer: P::Renderer) -> Self {
        let executor = P::Executor::new().expect("create the recorder's executor");
        let (sender, receiver) = mpsc::channel(256);
        let runtime = Runtime::new(executor, sender);
        let (state, task) = runtime.enter(|| program.boot());
        let mut driver = Self {
            state,
            runtime,
            receiver,
            renderer,
            size,
            window: window::Id::unique(),
            cursor: mouse::Cursor::Unavailable,
            clipboard: Clipboard { content: None },
            cache: Some(user_interface::Cache::default()),
            clock,
            stale: false,
        };
        driver.spawn(task);
        driver.settle(program);
        driver
    }

    fn spawn(&mut self, task: Task<P::Message>) {
        if let Some(stream) = task::into_stream(task) {
            self.runtime.run(stream.map(Action::Runtime).boxed());
        }
    }

    /// Runs what the tasks produced so far (messages, widget operations, the window's id).
    /// Tasks that finish right away (most of them) land within a few milliseconds.
    fn settle(&mut self, program: &P) {
        self.settle_for(program, 3);
    }

    /// Like `settle`, waiting until nothing came for `quiet` milliseconds in a row (0: only
    /// what is already there).
    fn settle_for(&mut self, program: &P, quiet: u32) {
        let mut idle = 0;
        loop {
            match self.receiver.try_recv() {
                Ok(Action::Runtime(action)) => {
                    idle = 0;
                    self.perform(program, action);
                }
                _ => {
                    if idle >= quiet {
                        break;
                    }
                    idle += 1;
                    std::thread::sleep(Duration::from_millis(1));
                }
            }
        }
    }

    fn perform(&mut self, program: &P, action: runtime::Action<P::Message>) {
        match action {
            runtime::Action::Output(message) => self.update(program, vec![message]),
            runtime::Action::Widget(operation) => {
                let mut ui = UserInterface::build(
                    program.view(&self.state, self.window),
                    self.size,
                    self.cache.take().unwrap_or_default(),
                    &mut self.renderer,
                );
                let mut operation = Some(operation);
                while let Some(mut current) = operation.take() {
                    ui.operate(&self.renderer, &mut current);
                    if let widget::operation::Outcome::Chain(next) = current.finish() {
                        operation = Some(next);
                    }
                }
                self.cache = Some(ui.into_cache());
            }
            runtime::Action::Window(action) => {
                use runtime::window::Action as W;
                match action {
                    W::Open(id, _settings, sender) => {
                        self.window = id;
                        let _ = sender.send(id);
                    }
                    W::GetOldest(sender) | W::GetLatest(sender) => {
                        let _ = sender.send(Some(self.window));
                    }
                    W::GetSize(_, sender) => {
                        let _ = sender.send(self.size);
                    }
                    W::GetScaleFactor(_, sender) => {
                        let _ = sender.send(1.0);
                    }
                    _ => {}
                }
            }
            _ => {}
        }
    }

    fn update(&mut self, program: &P, messages: Vec<P::Message>) {
        if messages.is_empty() {
            return;
        }
        let task = self.runtime.enter(|| {
            Task::batch(
                messages
                    .into_iter()
                    .map(|message| program.update(&mut self.state, message)),
            )
        });
        self.spawn(task);
    }

    /// Delivers events to the view, then runs the messages they produced.
    fn events(&mut self, program: &P, events: &[Event]) {
        if self.stale && !matches!(events, [Event::Window(window::Event::RedrawRequested(_))]) {
            self.redraw(program);
        }
        for event in events {
            match event {
                Event::Mouse(mouse::Event::CursorMoved { position }) => {
                    self.cursor = mouse::Cursor::Available(*position);
                }
                Event::Mouse(mouse::Event::CursorLeft) => {
                    self.cursor = mouse::Cursor::Unavailable;
                }
                _ => {}
            }
        }
        let cursor = self.cursor;
        let mut messages = Vec::new();
        let mut ui = UserInterface::build(
            program.view(&self.state, self.window),
            self.size,
            self.cache.take().unwrap_or_default(),
            &mut self.renderer,
        );
        let _ = ui.update(
            events,
            cursor,
            &mut self.renderer,
            &mut self.clipboard,
            &mut messages,
        );
        self.cache = Some(ui.into_cache());
        // Without messages no task started: only pick up what earlier ones sent meanwhile.
        let quiet = if messages.is_empty() { 0 } else { 3 };
        self.update(program, messages);
        self.settle_for(program, quiet);
    }

    fn redraw(&mut self, program: &P) {
        self.stale = false;
        let now = self.clock;
        self.events(
            program,
            &[Event::Window(window::Event::RedrawRequested(now))],
        );
    }

    /// Draws the view with the pointer where it is (hover states) at the current time.
    fn snap(&mut self, program: &P, fallback: &Theme, scale: f32) -> Vec<u8> {
        // Widgets update their status (hovered, pressed, focused) on a redraw.
        self.redraw(program);
        self.draw(program, fallback, scale)
    }

    /// Draws the view as it is, without delivering a redraw first.
    fn draw(&mut self, program: &P, fallback: &Theme, scale: f32) -> Vec<u8> {
        let theme = program
            .theme(&self.state, self.window)
            .unwrap_or_else(|| fallback.clone());
        let style = program.style(&self.state, &theme);
        let cursor = self.cursor;
        let mut ui = UserInterface::build(
            program.view(&self.state, self.window),
            self.size,
            self.cache.take().unwrap_or_default(),
            &mut self.renderer,
        );
        let mut messages = Vec::new();
        let _ = ui.update(
            &[Event::Window(window::Event::RedrawRequested(self.clock))],
            cursor,
            &mut self.renderer,
            &mut self.clipboard,
            &mut messages,
        );
        ui.draw(
            &mut self.renderer,
            &theme,
            &renderer::Style {
                text_color: style.text_color,
            },
            cursor,
        );
        self.cache = Some(ui.into_cache());
        let physical = Size::new(
            (self.size.width * scale).round() as u32,
            (self.size.height * scale).round() as u32,
        );
        let rgba = self
            .renderer
            .screenshot(physical, scale, style.background_color);
        let quiet = if messages.is_empty() { 0 } else { 3 };
        self.update(program, messages);
        self.settle_for(program, quiet);
        rgba
    }

    fn probe(&mut self, program: &P) -> Vec<(String, String, f32, f32, f32, f32)> {
        let mut ui = UserInterface::build(
            program.view(&self.state, self.window),
            self.size,
            self.cache.take().unwrap_or_default(),
            &mut self.renderer,
        );
        let mut probe = Probe::default();
        ui.operate(&self.renderer, &mut probe);
        self.cache = Some(ui.into_cache());
        probe.found
    }
}

struct Clipboard {
    content: Option<String>,
}

impl iced_test::core::Clipboard for Clipboard {
    fn read(&self, _kind: iced_test::core::clipboard::Kind) -> Option<String> {
        self.content.clone()
    }

    fn write(&mut self, _kind: iced_test::core::clipboard::Kind, contents: String) {
        self.content = Some(contents);
    }
}

/// Collects the bounds of what a script may want to point at.
#[derive(Default)]
struct Probe {
    found: Vec<(String, String, f32, f32, f32, f32)>,
}

impl Probe {
    fn add(&mut self, kind: &str, text: &str, b: Rectangle) {
        self.found
            .push((kind.into(), text.into(), b.x, b.y, b.width, b.height));
    }
}

impl Operation for Probe {
    fn traverse(&mut self, operate: &mut dyn FnMut(&mut dyn Operation<()>)) {
        operate(self);
    }

    fn container(&mut self, _id: Option<&widget::Id>, bounds: Rectangle) {
        self.add("container", "", bounds);
    }

    fn scrollable(
        &mut self,
        _id: Option<&widget::Id>,
        bounds: Rectangle,
        _content_bounds: Rectangle,
        _translation: iced::Vector,
        _state: &mut dyn widget::operation::Scrollable,
    ) {
        self.add("scrollable", "", bounds);
    }

    fn focusable(
        &mut self,
        _id: Option<&widget::Id>,
        bounds: Rectangle,
        _state: &mut dyn widget::operation::Focusable,
    ) {
        self.add("focusable", "", bounds);
    }

    fn text_input(
        &mut self,
        _id: Option<&widget::Id>,
        bounds: Rectangle,
        _state: &mut dyn widget::operation::TextInput,
    ) {
        self.add("input", "", bounds);
    }

    fn text(&mut self, _id: Option<&widget::Id>, bounds: Rectangle, text: &str) {
        self.add("text", text, bounds);
    }
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

fn button(name: Option<String>) -> PyResult<mouse::Button> {
    Ok(match name.as_deref().unwrap_or("left") {
        "left" => mouse::Button::Left,
        "right" => mouse::Button::Right,
        "middle" => mouse::Button::Middle,
        other => {
            return Err(PyValueError::new_err(format!(
                "unknown mouse button {other:?}"
            )));
        }
    })
}

fn named_key(name: &str) -> Option<keyboard::key::Named> {
    use keyboard::key::Named as N;
    Some(match name.to_ascii_lowercase().as_str() {
        "enter" | "return" => N::Enter,
        "tab" => N::Tab,
        "escape" | "esc" => N::Escape,
        "backspace" => N::Backspace,
        "delete" => N::Delete,
        "space" => N::Space,
        "up" | "arrowup" => N::ArrowUp,
        "down" | "arrowdown" => N::ArrowDown,
        "left" | "arrowleft" => N::ArrowLeft,
        "right" | "arrowright" => N::ArrowRight,
        "home" => N::Home,
        "end" => N::End,
        "pageup" => N::PageUp,
        "pagedown" => N::PageDown,
        _ => return None,
    })
}

fn modifiers(spec: &str) -> keyboard::Modifiers {
    let mut m = keyboard::Modifiers::empty();
    for part in spec.split(['-', '+', ' ', ',']).filter(|p| !p.is_empty()) {
        match part.to_ascii_lowercase().as_str() {
            "ctrl" | "control" => m |= keyboard::Modifiers::CTRL,
            "shift" => m |= keyboard::Modifiers::SHIFT,
            "alt" => m |= keyboard::Modifiers::ALT,
            "logo" | "cmd" | "super" => m |= keyboard::Modifiers::LOGO,
            _ => {}
        }
    }
    m
}

fn key_events(name: &str, mods: keyboard::Modifiers) -> Vec<Event> {
    let (key, text) = match named_key(name) {
        Some(keyboard::key::Named::Space) => (
            keyboard::Key::Named(keyboard::key::Named::Space),
            Some(SmolStr::new(" ")),
        ),
        Some(named) => (keyboard::Key::Named(named), None),
        None => {
            let c = SmolStr::new(name);
            let text = (mods.is_empty() || mods == keyboard::Modifiers::SHIFT).then(|| c.clone());
            (keyboard::Key::Character(c), text)
        }
    };
    let physical = keyboard::key::Physical::Unidentified(keyboard::key::NativeCode::Unidentified);
    let mut events = Vec::new();
    if !mods.is_empty() {
        events.push(Event::Keyboard(keyboard::Event::ModifiersChanged(mods)));
    }
    events.push(Event::Keyboard(keyboard::Event::KeyPressed {
        key: key.clone(),
        modified_key: key.clone(),
        physical_key: physical,
        location: keyboard::Location::Standard,
        modifiers: mods,
        text,
        repeat: false,
    }));
    events.push(Event::Keyboard(keyboard::Event::KeyReleased {
        key: key.clone(),
        modified_key: key,
        physical_key: physical,
        location: keyboard::Location::Standard,
        modifiers: mods,
    }));
    if !mods.is_empty() {
        events.push(Event::Keyboard(keyboard::Event::ModifiersChanged(
            keyboard::Modifiers::empty(),
        )));
    }
    events
}

/// Runs `script` (a generator of commands, see the module's docs) against `program`, drawing
/// with `renderer`, which it hands back.
fn drive<P: Program<Theme = Theme> + 'static>(
    program: &P,
    script: &Py<PyAny>,
    size: Size,
    scale: f32,
    fallback: &Theme,
    renderer: P::Renderer,
) -> (P::Renderer, PyResult<()>) {
    // Far enough ahead of the real clock that nothing measured with it (an input's caret,
    // a double click) lands after the virtual one.
    let start = Instant::now() + Duration::from_secs(3600);
    set_clock(Some(start));
    let mut driver = Driver::new(program, size, start, renderer);
    driver.redraw(program);
    let result = run_script(&mut driver, program, script, size, scale, fallback);
    (driver.renderer, result)
}

fn run_script<P: Program<Theme = Theme> + 'static>(
    driver: &mut Driver<P>,
    program: &P,
    script: &Py<PyAny>,
    size: Size,
    scale: f32,
    fallback: &Theme,
) -> PyResult<()> {
    let mut result: Py<PyAny> = Python::attach(|py| py.None());
    loop {
        let command = Python::attach(|py| -> PyResult<Option<Py<PyAny>>> {
            match script.bind(py).call_method1("send", (result.bind(py),)) {
                Ok(c) => Ok(Some(c.unbind())),
                Err(e) if e.is_instance_of::<PyStopIteration>(py) => Ok(None),
                Err(e) => Err(e),
            }
        })?;
        let Some(command) = command else { break };
        let (kind, args) = Python::attach(|py| -> PyResult<(String, Py<PyTuple>)> {
            let tuple = command.bind(py).cast::<PyTuple>()?.clone();
            let kind: String = tuple.get_item(0)?.extract()?;
            Ok((kind, tuple.get_slice(1, tuple.len()).unbind()))
        })?;
        let arg = |i: usize| -> PyResult<Option<Py<PyAny>>> {
            Python::attach(|py| {
                let a = args.bind(py);
                Ok(if i < a.len() {
                    Some(a.get_item(i)?.unbind())
                } else {
                    None
                })
            })
        };
        let f = |i: usize| -> PyResult<f32> {
            Python::attach(|py| match arg(i)? {
                Some(v) => v.bind(py).extract::<f32>(),
                None => Ok(0.0),
            })
        };
        let s = |i: usize| -> PyResult<Option<String>> {
            Python::attach(|py| match arg(i)? {
                Some(v) if !v.bind(py).is_none() => Ok(Some(v.bind(py).extract::<String>()?)),
                _ => Ok(None),
            })
        };
        let mut out: Py<PyAny> = Python::attach(|py| py.None());
        match kind.as_str() {
            "move" => {
                let position = iced::Point::new(f(0)?, f(1)?);
                driver.events(
                    program,
                    &[Event::Mouse(mouse::Event::CursorMoved { position })],
                );
            }
            "leave" => driver.events(program, &[Event::Mouse(mouse::Event::CursorLeft)]),
            "down" => {
                let b = button(s(0)?)?;
                driver.events(program, &[Event::Mouse(mouse::Event::ButtonPressed(b))]);
            }
            "up" => {
                let b = button(s(0)?)?;
                driver.events(program, &[Event::Mouse(mouse::Event::ButtonReleased(b))]);
            }
            "scroll" => {
                let delta = mouse::ScrollDelta::Lines { x: f(0)?, y: f(1)? };
                driver.events(
                    program,
                    &[Event::Mouse(mouse::Event::WheelScrolled {
                        delta,
                        phase: mouse::ScrollPhase::Moved,
                    })],
                );
            }
            "key" => {
                let name = s(0)?.ok_or_else(|| PyValueError::new_err("key needs a name"))?;
                let mods = modifiers(&s(1)?.unwrap_or_default());
                driver.events(program, &key_events(&name, mods));
            }
            "type" => {
                let text = s(0)?.unwrap_or_default();
                for c in text.chars() {
                    driver.events(
                        program,
                        &key_events(&c.to_string(), keyboard::Modifiers::empty()),
                    );
                }
            }
            "advance" => {
                let seconds = f(0)?.max(0.0);
                driver.clock += Duration::from_secs_f32(seconds);
                set_clock(Some(driver.clock));
                // The next event or frame delivers the redraw (a frame right after, the usual
                // case, would otherwise build the view once more).
                driver.stale = true;
            }
            "snap" => {
                let rgba = driver.snap(program, fallback, scale);
                out = Python::attach(|py| PyBytes::new(py, &rgba).into_any().unbind());
            }
            "probe" => {
                let found = driver.probe(program);
                out = Python::attach(|py| -> PyResult<Py<PyAny>> {
                    Ok(PyList::new(py, found)?.into_any().unbind())
                })?;
            }
            "size" => {
                let w = (size.width * scale).round() as u32;
                let h = (size.height * scale).round() as u32;
                out = Python::attach(|py| -> PyResult<Py<PyAny>> {
                    Ok((w, h).into_pyobject(py)?.into_any().unbind())
                })?;
            }
            other => {
                return Err(PyValueError::new_err(format!(
                    "unknown recorder command {other:?}"
                )));
            }
        }
        result = out;
    }
    Ok(())
}

/// Drives `app` off-screen with `script`, a generator of commands (see the module's docs).
/// `renderer` is `"auto"` (the GPU, or the CPU without one), `"gpu"` or `"cpu"`. Returns the
/// name of the renderer that drew it, and whether a `pz.shader` was drawn (the CPU renderer
/// shows its fallback).
#[pyfunction]
#[pyo3(signature = (app, script, *, size, scale=2.0, renderer=None))]
pub fn record(
    py: Python<'_>,
    app: Py<PyAny>,
    script: Py<PyAny>,
    size: (f32, f32),
    scale: f32,
    renderer: Option<String>,
) -> PyResult<(String, bool)> {
    let backend = backend_key(renderer.as_deref())?;
    py.detach(crate::fonts::ensure_loaded);
    let font_size = crate::app::font_size(app.bind(py))?;
    let theme = crate::app::palette_key(app.bind(py))
        .and_then(|k| crate::app::build_theme(&k))
        .unwrap_or(Theme::Dark);
    let viewport = Size::new(size.0, size.1);
    crate::app::open_post_channel();
    let style = py.import("pyzed.style")?;
    style.setattr("_screen", (viewport.width, viewport.height))?;
    // Animations play (a screenshot shows them at rest).
    crate::animation::set_screenshot(false);
    SHADER_DRAWN.store(false, Ordering::Relaxed);
    let result = py.detach(move || {
        let program = crate::app::daemon(app, font_size, true);
        let renderer = renderer_for(&program, backend, font_size)?;
        let name = renderer.name();
        let (renderer, result) = drive(&program, &script, viewport, scale, &theme, renderer);
        keep_renderer(backend, font_size, renderer);
        result.map(|()| name)
    });
    set_clock(None);
    crate::app::close_post_channel();
    style.setattr("_screen", py.None())?;
    result.map(|name| (name, SHADER_DRAWN.load(Ordering::Relaxed)))
}

/// Renders `app` off-screen as `pz.screenshot` does and returns `(width, height, rgba,
/// renderer, shader)` instead of writing a PNG: `renderer` is as for `record`, and so are the
/// last two.
#[pyfunction]
#[pyo3(signature = (app, *, size=None, scale=2.0, wait=0.1, renderer=None))]
pub fn screenshot_rgba(
    py: Python<'_>,
    app: Py<PyAny>,
    size: Option<(f32, f32)>,
    scale: f32,
    wait: f64,
    renderer: Option<String>,
) -> PyResult<(u32, u32, Py<PyBytes>, String, bool)> {
    SHADER_DRAWN.store(false, Ordering::Relaxed);
    let (w, h, rgba, name) = shoot(py, app, size, scale, wait, renderer.as_deref())?;
    let shader = SHADER_DRAWN.load(Ordering::Relaxed);
    Ok((w, h, PyBytes::new(py, &rgba).unbind(), name, shader))
}

/// The GPU an off-screen renderer would draw with: `(name, kind)`, where `kind` is
/// `"discrete"`, `"integrated"`, `"virtual"`, `"cpu"` (a software driver such as lavapipe or
/// llvmpipe, slower than the CPU renderer) or `"other"`; `None` without one.
#[pyfunction]
pub fn offscreen_gpu(py: Python<'_>) -> Option<(String, String)> {
    use iced_wgpu::wgpu;
    py.detach(|| {
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor {
            backends: wgpu::Backends::from_env().unwrap_or(wgpu::Backends::PRIMARY),
            flags: wgpu::InstanceFlags::empty(),
            ..wgpu::InstanceDescriptor::default()
        });
        let adapter = iced_test::runtime::futures::futures::executor::block_on(
            instance.request_adapter(&wgpu::RequestAdapterOptions {
                power_preference: wgpu::PowerPreference::HighPerformance,
                force_fallback_adapter: false,
                compatible_surface: None,
            }),
        )
        .ok()?;
        let info = adapter.get_info();
        let kind = match info.device_type {
            wgpu::DeviceType::DiscreteGpu => "discrete",
            wgpu::DeviceType::IntegratedGpu => "integrated",
            wgpu::DeviceType::VirtualGpu => "virtual",
            wgpu::DeviceType::Cpu => "cpu",
            wgpu::DeviceType::Other => "other",
        };
        Some((info.name, kind.to_owned()))
    })
}

/// One still frame of `app` after `wait` seconds of real time (its start tasks run), drawn with
/// no pointer and animations at rest, with a renderer this thread keeps.
pub(crate) fn shoot(
    py: Python<'_>,
    app: Py<PyAny>,
    size: Option<(f32, f32)>,
    scale: f32,
    wait: f64,
    renderer: Option<&str>,
) -> PyResult<(u32, u32, Vec<u8>, String)> {
    let backend = backend_key(renderer)?;
    py.detach(crate::fonts::ensure_loaded);
    let settings = crate::app::window_settings(app.bind(py))?;
    let viewport = size.map(|(w, h)| Size::new(w, h)).unwrap_or(settings.size);
    let font_size = crate::app::font_size(app.bind(py))?;
    let theme = crate::app::palette_key(app.bind(py))
        .and_then(|k| crate::app::build_theme(&k))
        .unwrap_or(Theme::Dark);
    crate::app::open_post_channel();
    // Media queries see the screenshot's size.
    let style = py.import("pyzed.style")?;
    style.setattr("_screen", (viewport.width, viewport.height))?;
    // Animations show their resting state, so a screenshot doesn't depend on timing.
    crate::animation::set_screenshot(true);
    let shot = py.detach(move || {
        let program = crate::app::daemon(app, font_size, true);
        let renderer = renderer_for(&program, backend, font_size)?;
        let name = renderer.name();
        let mut driver = Driver::new(&program, viewport, Instant::now(), renderer);
        let started = Instant::now();
        let wait = Duration::from_secs_f64(wait.max(0.0));
        while started.elapsed() < wait {
            driver.settle_for(&program, 1);
        }
        driver.clock = Instant::now();
        driver.redraw(&program);
        let rgba = driver.draw(&program, &theme, scale);
        keep_renderer(backend, font_size, driver.renderer);
        Ok::<_, PyErr>((rgba, name))
    });
    crate::app::close_post_channel();
    crate::animation::set_screenshot(false);
    style.setattr("_screen", py.None())?;
    let (rgba, name) = shot?;
    let w = (viewport.width * scale).round() as u32;
    let h = (viewport.height * scale).round() as u32;
    Ok((w, h, rgba, name))
}

/// Drops the renderers this thread kept (they hold a GPU device and its memory).
#[pyfunction]
pub fn release_renderers() {
    RENDERERS.with(|r| r.borrow_mut().clear());
}
