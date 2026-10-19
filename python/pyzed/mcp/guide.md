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
                ui.button("+1", lambda: setattr(self, "count", self.count + 1), icon="plus"),
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

## Projects and the CLI

- `pyzed new my_app` creates a uv project (ruff, ty, git) with the UI in `ui/`;
  `pyzed new my_app --script` creates a single `main.py`.
- `pyzed dev main.py` runs with hot reload. `pyzed design` and `pyzed run` work on forms.
- `pyzed add/remove/upgrade/sync/deps` manage dependencies through uv, `pyzed check` runs ruff and
  ty, `pyzed build` packages the app with PyInstaller.
- `pyzed icons <filter>` lists the bundled Lucide icons (`search_icons` does the same).

## Where to read more

The `read_docs` tool returns any page of the official documentation
(https://albakore.github.io/pyzed/); `list_docs` lists them, and `read_example` returns the code
of the example apps. Read `pyzed://best-practices` (or `get_guide("best-practices")`) before
writing a non-trivial app.
