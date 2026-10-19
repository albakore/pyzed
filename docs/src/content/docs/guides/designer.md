---
title: Visual designer
description: Build windows by drag and drop, wire their events to Python and run them, like Visual Basic or Qt Designer.
sidebar:
  order: 13
---

Pyzed Designer is a form editor in the spirit of Visual Basic, the WinForms designer in Visual Studio and
Qt Designer, built with Pyzed itself. You draw a window with the mouse, set properties in a grid, double-click a
control to write the code of its event, and press **F5** to run it with all its logic.

```bash
pyzed design login.pzform      # open (or create) a form
pyzed run login.pzform         # run it, no designer needed
pyzed run login.pzform --reload  # ...and update it every time the form or its code is saved
```

![The designer with the login example open](../../../../screenshots/designer.png)

## The window

| Area | What it does |
| --- | --- |
| **Toolbox** (left) | The component library. Click a component, then click on the form to place it at its default size, or drag a rectangle to give it a size. Search filters the list. |
| **Outline** (left) | Every control in z-order (top first). Click to select; the eye and lock buttons hide or lock a control. |
| **Form** (center) | The design surface with a dot grid. Drag to move, use the eight handles to resize, drag on empty space to select with a rubber band. The grip under the bottom-right corner resizes the form. |
| **Properties** (right) | Name, the component's own properties, layout (X, Y, size, anchors) and behavior (visible, enabled, locked). With nothing selected it edits the form: title, size, theme, accent, background, corner radius, font size and grid. |
| **Events** (right) | The events of the selected control (or of the form). Double-click one to create its handler and open it in the code editor. |
| **Code** (bottom) | The source of one handler, or of the whole file (**F7**). **Apply** checks the syntax before touching the file. |

![Writing the code of a button's click event](../../../../screenshots/designer-code.png)

## Alignment, grid and snapping

- **Snap to grid** (magnet) rounds positions and sizes to the grid step (8 px by default, set per form). Press
  **G** to show or hide the dots.
- **Smart guides** (ruler) snap a moving control to the edges and centers of the others and of the form, and draw a
  red guide line while they line up.
- The toolbar aligns the selection by **left, center, right, top, middle or bottom** edges, **distributes** three or
  more controls evenly, gives them the **same width or height**, **centers** them in the form and changes the
  **z-order**. With one control selected, alignment is relative to the form.
- **Anchors** decide what happens when the running window is resized, like WinForms: anchored to left and right a
  control stretches, anchored only to the right it follows that edge, anchored to neither it stays centered.

![Three controls selected, ready to align](../../../../screenshots/designer-align.png)

### Keyboard

| Keys | Action |
| --- | --- |
| Arrows / Shift+arrows | Nudge by 1 px / one grid step |
| Delete | Delete the selection |
| Ctrl+C, Ctrl+X, Ctrl+V, Ctrl+D | Copy, cut, paste, duplicate |
| Ctrl+A | Select every control |
| Ctrl+Z, Ctrl+Shift+Z | Undo, redo |
| Enter | Open the code of the selected control's main event |
| Escape | Cancel a drag, close a menu, go back to the pointer |
| Ctrl+S, Ctrl+O, Ctrl+N | Save, open, new |
| F5, Shift+F5 | Run the form, close the running form |
| F7 | Edit the whole code file |
| Ctrl+Space | Open the completion list (in the code editor) |

Right-click a control for a context menu with the same actions.

## Look and feel

Each form picks any registered theme (One, Ayu, Gruvbox or your own) and can override its accent color,
background, corner radius and font size. The designer's own theme is independent (top-right selector).

![A form with the Gruvbox Light theme and a custom accent](../../../../screenshots/designer-light.png)

## Files

A form is two files side by side, both meant to be committed:

```
login.pzform   ← layout: JSON, diffs nicely
login.py       ← event handlers: plain Python
```

```mermaid
flowchart LR
    subgraph Designer["pyzed design"]
        T[Toolbox] --> S[Design surface]
        S --> P[Properties]
        S --> E[Events]
        E --> C[Code editor]
    end
    S -- save --> F[(login.pzform)]
    C -- save --> H[(login.py)]
    F --> R["pyzed run / designer.run()"]
    H --> R
    R --> W[Native window rendered by Iced]
```

The `.pzform` file stores the form settings and, for each control, its type, position, size, properties, anchors
and which handler each event calls:

```json
{
  "format": "pyzed.form/1",
  "form": { "name": "login", "title": "Sign in", "width": 440, "height": 400, "theme": "One Dark", "events": { "load": "form_load" } },
  "controls": [
    { "name": "sign_in", "type": "button", "x": 48, "y": 304, "width": 344, "height": 32,
      "props": { "text": "Sign in", "variant": "solid", "icon": "log-in" },
      "events": { "click": "sign_in_click" }, "anchor": ["left", "top"] }
  ]
}
```

## Live updates

Forms work with hot reload (`pyzed.hot_reload`): run them with `pyzed run app.pzform --reload` (or
`designer.run(path, reload=True)`, or `PYZED_RELOAD=1`) and every save of `app.pzform` or `app.py`, from the
designer or from your editor, updates the open window without restarting it. Layout, properties and code are
replaced; what the user typed or picked in each control stays. Inside the designer, **Save** also refreshes the
form opened with **F5**.

## Writing event handlers

Handlers are named `<control>_<event>` and receive the running `form` and an `event`. Controls are attributes of
the form and their properties are attributes of the control; changing them updates the window.

```python
def sign_in_click(form, event):
    if "@" not in form.email.text:
        form.status.text = "Enter a valid email address."
        return form.email.focus()          # handlers may return commands
    form.sign_in.enabled = False
    form.progress.show()
    form.ticker.running = True             # a Timer control starts ticking
```

`event.sender` is the control that raised it, `event.name` the event and `event.value` its value (the new text of a
text box, the state of a check box, the key combo of the form's `key` event...). Handlers can return anything a
Pyzed callback can: a `Command`, a coroutine, a generator. If a handler raises, the error appears at the bottom of
the running window instead of closing it.

```mermaid
sequenceDiagram
    actor User
    participant Iced as Iced (Rust)
    participant RT as FormRuntime
    participant H as login.py
    User->>Iced: clicks "Sign in"
    Iced->>RT: callback for sign_in.click
    RT->>H: sign_in_click(form, event)
    H->>RT: form.status.text = "..."
    RT->>Iced: view() with the new properties
    Iced->>User: redraws the window
```

### Events

Every visible control has `mouse_enter`, `mouse_leave` and `right_click`. On top of that:

| Component | Events |
| --- | --- |
| Button | `click` |
| Label | `click`, `double_click` |
| Text box | `change`, `submit` |
| Text area, Check box, Switch, Radio group, Drop-down, Slider, Number box, List box | `change` |
| Timer (invisible at run time) | `tick` |
| Form | `load`, `close` (return `False` to keep it open), `key`, `resize` |

## Code editor

The code panel is a Python editor backed by two language servers from Astral: **ty** (types, completion,
references) and **ruff** (linting). They run in the form's own project, so completion knows your dependencies.

![Completing a function of the re module, with its signature and docstring](../../../../screenshots/designer-completion.png)

### Completion

- The list opens while you type a name or after a `.`, and **Ctrl+Space** opens it anywhere. **Up**/**Down**
  move, **Enter** or **Tab** insert, **Escape** closes it.
- Each entry has an icon for its kind and a pane with its signature and documentation (the docstring):

  | Icon color | Kind |
  | --- | --- |
  | Purple | Functions and methods |
  | Yellow | Classes, enums, type parameters |
  | Blue | Variables, attributes and properties |
  | Cyan | Constants |
  | Red | Modules |
  | Accent | Controls of the form |

  Private names (`_cache`) are dimmed, carry a lock and are listed after public ones; dunders (`__init__`) come last.
- `form.` lists the controls of the form, `form.email.` the properties of that text box and `event.` the event's
  fields: the designer completes them itself, since a handler's `form` has no type the servers could read.
- Picking a name that is not imported yet (an *auto-import* entry) also adds its `import` at the top of the file.

![form. completes the form's own controls](../../../../screenshots/designer-completion-form.png)

### Your project and its dependencies

The servers start in the folder of the nearest `pyproject.toml` above the form (or `uv.lock`, `setup.py`,
`.git`) and use its `.venv`, which is where `uv sync` installs your dependencies (`$VIRTUAL_ENV` otherwise). The
form's own folder and `src/` are added as import roots, so a UI kept in its own folder still resolves both:

```
myapp/
├── pyproject.toml      ← uv add httpx
├── .venv/              ← uv sync
├── src/myapp/
└── ui/
    ├── login.pzform
    ├── login.py        ← import httpx / from helpers import greet / from myapp import api
    └── helpers.py
```

Install the servers in the project with `uv add --dev ty ruff`, or next to the designer with
`pip install "pyzed-ui[designer]"`. The designer looks in the project's `.venv` first, then in its own environment,
then on `PATH`. Ruff reads its rules from `[tool.ruff]` in `pyproject.toml`.

```mermaid
sequenceDiagram
    participant E as Code editor
    participant A as CodeAssist
    participant I as CodeIntel
    participant T as ty server
    participant R as ruff server
    E->>A: on_change(text), on_cursor(line, col)
    A->>I: update(module, handler, text)
    I->>T: didChange (whole module, handler swapped in)
    I->>R: didChange
    T-->>I: publishDiagnostics
    R-->>I: publishDiagnostics
    A->>I: complete(line, col)
    I->>T: textDocument/completion
    T-->>A: items (via pyzed.post, on the UI thread)
    A->>E: popup, inline errors, code lens
```

The editor shows one handler, but the servers always see the whole module with that handler swapped in, so imports
and helpers at the top of the file are known; positions are translated between the two.

### Diagnostics and code lens

![Inline errors, the problems list and code lens](../../../../screenshots/designer-diagnostics.png)

- The first problem of a line is shown at its end (error lens), and every problem is listed under the editor;
  click one to jump to it. The header counts errors and warnings.
- **Code lens** at the end of each `def` and `class` line shows how many references it has (from ty), how many
  classes implement it, and which events call it (`on sign_in.click`).

### Editor settings

The gear button in the code panel (or the server dots in the status bar) opens the editor settings. They are saved
per user in `designer.json` inside the Pyzed config folder (`%APPDATA%\pyzed`, `~/Library/Application Support/pyzed`
or `~/.config/pyzed`).

![Editor settings with the language servers' status](../../../../screenshots/designer-editor-settings.png)

| Setting | What it does |
| --- | --- |
| Language servers | Turns ty and ruff on or off, shows whether each is ready (and its version), the project root and the Python in use. **Restart servers** after `uv sync`. |
| Theme, font size | The editor can use a different theme from the designer. |
| Line numbers, highlight current line, wrap | Gutter and layout. |
| Show whitespace | Draws spaces as `·` and tabs as `→`. |
| Tab size | Tab inserts spaces, Enter keeps the indentation (one level more after `:`), Backspace removes a level. |
| Autocomplete while typing | Off means the list only opens with Ctrl+Space. |
| Format with ruff on Apply | Runs `ruff format` on the code when you apply it. |
| Code lens, inline diagnostics | Show or hide the notes at the end of lines. |

## Components

Label, Heading, Button, Text box, Text area, Check box, Switch, Radio group, Drop-down, Slider, Number box,
List box, Progress bar, Badge, Image, Icon, Markdown, Spinner, Panel, Divider and Timer.

![Every built-in component](../../../../screenshots/designer-components.png)

To draw your own components, with properties, state, methods and events, use the
[component designer](/pyzed/guides/component-designer/). They join this toolbox when you save them.

Register your own and it shows up in the toolbox:

```python
from pyzed import ui
from pyzed.designer import Component, Prop, register

register(Component(
    type="rating", label="Rating", icon="star", category="Custom", size=(120, 24),
    props=(Prop("value", "number", 3, min=0, max=5),),
    events=("change",),
    render=lambda control, ctx: ui.label("★" * int(control.props["value"])),
))
```

`render` is used both in the designer (inert) and at run time; use `ctx.on(control, "change", "value")` for
callbacks so the same code works in both.

## Scripting forms

Everything the designer does is available from Python, which is handy for generating forms or for tests:

```python
from pyzed import designer
from pyzed.designer import Document

doc = Document(designer.Form(name="hello", title="Hello", width=320, height=140))
doc.add("input", 16, 16, 200, 28)
doc.add("button", 224, 16)
doc.select_all()
doc.align("middle")
handler = doc.wire("button1", "click")
doc.set_handler_source(handler, "def button1_click(form, event):\n    form.button1.text = form.input1.text\n")
doc.save("hello.pzform")

designer.run("hello.pzform")
```

## How it is built

```mermaid
classDiagram
    class Form { controls; events; theme; grid }
    class Control { name; type; x; y; width; height; props; events; anchor }
    class Component { type; props; events; render() }
    class Document { form; code; selection; history; add(); align(); wire() }
    class History { push(); undo(); redo() }
    class Designer { pyzed App: docks and gestures }
    class FormRuntime { dispatch(); view() }
    Form "1" *-- "*" Control
    Control ..> Component : type
    Document --> Form
    Document --> History
    Designer --> Document
    FormRuntime --> Form
```

- `model.py`: the form and its controls, saved as JSON.
- `components.py`: the component library and the `render` shared by designer and runtime.
- `geometry.py`: snapping, alignment, distribution, resizing, anchors and smart guides (pure functions).
- `history.py`: undo/redo as snapshots; repeated edits of one field merge into one step.
- `code.py`: finds, adds, renames and replaces handler functions with `ast` without touching the rest of the file.
- `document.py`: every editing command, with no UI, so it is fully testable.
- `project_panel.py`: the Project tab (uv projects, dependencies, ruff, ty and git; see [Projects with uv](/pyzed/guides/projects/)).
- `surface.py` and `panels.py`: the views; `app.py`: the `Designer` app wiring clicks and keys to the document.
- `scene.py`, `scene_code.py`, `scene_runtime.py` and `scene_panel.py`: the [component designer](/pyzed/guides/component-designer/)
  (the `.pzcomp` model, the class code, `SceneComponent` and the Component panel).
- `runtime.py`: `FormApp` and `FormWindow`, which draw a form and call its handlers.
- `lsp.py`: a small JSON-RPC client for language servers and the detection of the project and its `.venv`.
- `intellisense.py`: `CodeIntel`, which keeps ty and ruff in sync with the open handler, and the completion,
  diagnostics and code lens logic (no UI).
- `code_panel.py`: the code editor's view and `CodeAssist`, its state; `settings.py`: the editor settings.
