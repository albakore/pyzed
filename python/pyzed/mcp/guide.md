# Pyzed for AI agents

Pyzed builds native desktop GUIs in Python. The widgets are rendered by **Iced** (Rust) through a
compiled extension (`pyzed._core`), and `pyzed.ui` adds ready-made components that look like the
**Zed** editor. Install it with `pip install pyzed-ui` (or `uv add pyzed-ui`) and import it as
`import pyzed as pz`.

## The mental model

Pyzed follows Iced's **Elm architecture**:

1. State lives on your `pz.App` object (`self.*`).
2. `view()` returns a tree of immutable `pz.Widget`s built from that state.
3. User input produces a **message**. A plain value goes to `update(message)`; a **callable** is
   called directly. Either way Pyzed calls `view()` again and Iced redraws.

```python
import pyzed as pz
from pyzed import ui


class Counter(pz.App):
    title = "Counter"
    size = (360, 220)

    def __init__(self):
        self.count = 0

    def update(self, message):          # optional: for plain-value messages
        if message == "reset":
            self.count = 0

    def view(self):                     # required: returns a Widget
        return pz.center(pz.column([
            ui.heading(str(self.count)),
            pz.row([
                ui.button("1", lambda: setattr(self, "count", self.count + 1), icon="plus"),
                ui.button("Reset", "reset", variant="ghost"),
            ], spacing=8),
        ], spacing=16, align="center"))


pz.run(Counter)
```

What a callable returns matters: `None` just redraws, a `pz.Command` (or a list) runs effects
(focus, close, open windows...), a coroutine or generator runs in the background and each result
goes to `update`, and any other value is sent to `update` as a message.

Value-producing controls call the callable with the value: `on_input(text)`, `on_toggle(bool)`,
`on_change(value)`, `on_select(item)`.

## The three layers of the API

| Layer | Where | What |
| --- | --- | --- |
| Widgets | `pz.*` (`pz.column`, `pz.row`, `pz.text`, `pz.container`, `pz.scrollable`, `pz.canvas`...) | Iced primitives: layout, text, inputs, images, canvas. |
| Components | `pz.ui.*` (`ui.button`, `ui.input`, `ui.tree`, `ui.tab_bar`, `ui.command_palette`, `ui.workspace`...) | Zed-style, themeable building blocks. Plain functions returning widgets. |
| Your components | `class X(pz.Component)` | Reusable pieces with props, state, events and a `render()`. They also appear in the designer's toolbox. |

Use the MCP tools `list_components` and `describe_component` to see every name, its signature
and its documentation instead of guessing parameters.

## Layout essentials

- Write layouts like a web page. `pz.box(*children, display=..., gap=..., class_=..., id=...)` is
  the `div`: `display="block"` (the default, one under another), `"flex"` (with `direction`,
  `justify`, `align`, `wrap`), `"grid"` (`columns=3` or `"200 1fr auto"`, `rows`) or `"stack"`;
  `overflow="hidden"`/`"scroll"`; a child styled `position="absolute", top=..., right=...` leaves
  the flow (`z_index` orders it). Boxes take every style property, so a whole screen is boxes.
- `pz.column(children, spacing=8, padding=16, align="center")` stacks vertically,
  `pz.row(...)` horizontally. Children may be nested lists; `None` and `False` are skipped, so
  `self.error and ui.label(self.error, color="error")` is fine. Strings and numbers become text.
- Sizes: pixels (`240`), `"shrink"`, `"fill"` or a share `"fill:2"`.
- `pz.hspace()` / `pz.vspace()` push siblings apart; `pz.center(w)` centers.
- `pz.container(content, padding=..., bg=..., radius=..., width=..., height=...)` boxes content.
- `pz.scrollable(content)` for long content; `pz.stack([...])` overlays; `pz.grid(...)` and
  `pz.flex(...)` for grids and CSS-like flex layouts; `pz.Dock` for dockable panels.

## Styling and themes

- Every color in `pz.ui` comes from the current `Theme`. Prefer theme **tokens**
  (`"accent"`, `"panel"`, `"elevated"`, `"border"`, `"text_muted"`...) over hex colors so the UI
  follows theme switches. `list_themes` shows the themes and tokens.
- `App.theme = "One Dark"` (or `"One Light"`, `pz.themes.auto(...)`, a `pz.Theme`). Zed theme
  JSON files load with `pz.themes.load_zed(path)`.
- `widget.style(background="elevated", radius=10, padding=16, border=(1, "border"))` styles like
  CSS. Reuse styles with `pz.Style(...)` and `pz.define_style("card", ...)`.
- States like CSS: `.style(hover={...}, pressed={...}, focus={...}, transition=120)`.
- `pz.stylesheet({".card": {...}, ".card:hover": {...}, "#main": {...}, "Rating": {...}})` is the CSS
  file; `widget.classes("card", "selected")` (or `class_=`/`id=` on boxes and components) applies it.
- Responsive: `"@media (max_width: 700)"` and breakpoints (`"@md"`) in the stylesheet,
  `.style(media={"max_width: 600": {...}})`, and `pz.media(...)`, `pz.viewport()`,
  `pz.current_breakpoint()` in a view.

## Components (`pz.Component`)

```python
class Rating(pz.Component):
    """Stars the user can click."""

    value: int = 0                                  # props: annotated class attributes
    max: int = 5
    hover: int = pz.state(0)                        # private state
    events = {"change": "A star was picked (event.value)."}
    icon = "star"                                   # toolbox icon in the designer

    def render(self):
        shown = self.hover or self.value
        return pz.row([
            pz.text("★" if i <= shown else "☆", size=20).on(
                click=lambda i=i: self.emit("change", i),
                mouse_enter=lambda i=i: setattr(self, "hover", i),
                mouse_leave=lambda: setattr(self, "hover", 0),
            )
            for i in range(1, self.max + 1)
        ], spacing=2)

# In a view:  Rating(value=self.stars, on_change=lambda e: setattr(self, "stars", e.value))
```

Components nest like HTML elements: a `children: list = ()` prop takes the positional arguments
(`Card(pz.text("Hi"), ui.button(...), title="Inbox")`), a `stylesheet = {"&": {...}, "&:hover": {...}}`
class attribute styles every instance (`&` is the component), and every component takes `style=`,
`class_=`, `id=` and `animate=`. `with pz.provide(user=...):` shares a value with every component
rendered inside, read with `pz.use_context("user")` (or `self.context("user")`).

Calling a component returns a widget. Each declared event becomes an `on_<event>` keyword whose
callback receives a `pz.Event` (`event.value`, `event.sender`). Lifecycle hooks: `setup()`,
`on_mount()`, `on_unmount()`. Use `key=` when components move inside a list.

The `new_component` tool generates this skeleton.

## The visual designer (`.pzform`)

`pyzed design` opens a WinForms-like designer. A form is two files side by side:
`login.pzform` (JSON layout: form settings and controls with type, position, size, props, events)
and `login.py` (event handlers). Handlers are named `<control>_<event>` and receive
`(form, event)`; controls are attributes of the form:

```python
def sign_in_click(form, event):
    form.status.text = f"Hello {form.email.text}"
```

Run a form with `pyzed run login.pzform` (`--reload` for hot reload). `new_form` generates both
files from a list of controls and `validate_form` checks a `.pzform`. The designer's toolbox
types (`button`, `input`, `label`...) are listed by `list_components(kind="designer")`.

Non-visual components (`"visual": false`: `timer`, `shortcut`, `file_watcher`, `process`, `worker`,
`http_request`, `clipboard`, `settings`, `file_dialog`, `notification`) have properties and events
but no position: they sit in the tray under the form and draw nothing when it runs. Handlers call
their methods: `form.process1.start()`, `return form.file_dialog1.show()`,
`form.worker1.run(value)` (its `work` handler runs in a thread; use `progress` and `done` to change
controls), `form.settings1["key"] = value`. In plain code the same objects are `pz.Timer`,
`pz.Shortcut`, `pz.FileWatcher`, `pz.Process`, `pz.Worker`, `pz.HttpRequest`, `pz.Clipboard`,
`pz.Settings`, `pz.FileDialog` and `pz.Notification` (`on_<event>=` handlers, intervals in ms;
add `timer.subscriptions()` to the app's `subscriptions` and call `shortcut.handle(combo)` in
`on_key`). Events from background threads reach handlers on the UI thread.

## Projects and the CLI

- `pyzed new my_app` creates a uv project (ruff, ty, git) with the UI in `ui/`;
  `pyzed new my_app --script` creates a single `main.py`.
- `pyzed dev main.py` runs with hot reload. `pyzed design` and `pyzed run` work on forms.
- `pyzed add/remove/upgrade/sync/deps` manage dependencies through uv, `pyzed check` runs ruff and
  ty, `pyzed build` packages the app with PyInstaller.
- `pyzed icons <filter>` lists the bundled Lucide icons (`search_icons` does the same).

## Beyond the basics

Each of these has a recipe in `get_guide("cookbook")` and a topic in `list_guides`:

- **Animation and effects**: `.animate("fade_in_up")`, `.transition(opacity=...)`, `pz.stagger`,
  `pz.presence`; style effects `glow`, `bloom`, `blur`, `backdrop_blur` and `glass`.
- **Timeline animations**: `pz.Clip` + `pz.Track` played by `pz.AnimationPlayer` (like Godot),
  for several widgets or app attributes at once; clips are saved as `.pzanim` libraries.
- **Shaders**: `pz.shader(wgsl, uniforms={...})` paints a widget on the GPU.
- **Games**: `pz.frames(callback)` for a frame loop, held keys with `pz.is_pressed` and
  `pyzed.game` (`vector`, `axis`, `glow`, `Particles`) on a `pz.canvas`.
- **Large data**: `ui.virtual_list` / `pz.virtual_column` build only the visible rows; `@pz.memo`
  reuses a subtree while its arguments are the same.
- **Windows**: `frame = "custom"` (or `"macos"`, `"windows"`...) draws Pyzed's own title bar, with
  `frame_menus()` returning `ui.Menu` / `ui.MenuItem`; `pz.window_edges` adds resize borders.
- **Anchored layouts**: `pz.anchor_layout` with `pz.anchor(widget, x=, y=, width=, height=, anchor=)`,
  like the designer.
- **Forms and backends**: `ui.field(..., error=)` and `pz.validation_errors(error)` for Pydantic,
  SQLModel or Django errors; `list_examples(kind="integrations")` has FastAPI, SQLAlchemy, SQLModel
  and Django projects.
- **The code editor**: `ui.editor` with Zed-like key bindings (`editor_keymap`).

`search_reference` and `read_reference` cover every module, class and function, including
`pyzed.updater`, `pyzed.forms`, `pyzed.accessibility` and `pyzed.game`.

## Building a whole app

Start with `plan_app(description)`: it names the blocks, examples, components and guides to read
and the steps. With the project tools the server works in a folder and in the project's own
environment (`project_info` shows the entry file, the `.venv` and whether it is WSL):
`create_project`, `start_live_preview` (a real window with hot reload, so the user watches the app
while you write it), `write_files` (it checks what it writes), `add_dependency`, `check_project`,
`run_tests` and `screenshot_project`. A project always has one entry: its `script` or its main
form; forms (`.pzform`), components (`.pzcomp`), shaders (`.pzshad`) and animations (`.pzanim`) are
files of the project.
Keep the state and logic in plain classes in the package (`src/<package>`), views or forms in
`ui/`, tests in `tests/`, and loop write, check, test and look until all are clean. The
`build_project` prompt lists these steps.

## Where to read more

The `read_docs` tool returns any page of the official documentation
(https://albakore.github.io/pyzed/); `list_docs` lists them, and `read_example` returns the code
of the example apps. Read `pyzed://best-practices` (or `get_guide("best-practices")`) before
writing a non-trivial app.
