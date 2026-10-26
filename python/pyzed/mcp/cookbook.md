# Pyzed cookbook

Short, complete recipes for the features most apps need. Every recipe is a runnable script (it is
rendered in Pyzed's own tests), so you can start from one and change it. Look parameters up with
`describe_component` or `read_reference`, and read the linked page with `read_docs` for the details.

## Structure of a complex app

Big apps are a `pz.App` whose `view()` is split into methods, with the state in plain classes and
the slow work in background tasks. Start from a block (`list_examples(kind="blocks")`) for a
whole screen, and from `pyzed new my_app` for the project (UI in `ui/`, logic in `src/<package>`).

```python
from dataclasses import dataclass, field

import pyzed as pz
from pyzed import ui


@dataclass
class Note:
    title: str
    body: str = ""


@dataclass
class Store:                      # the app's data: plain Python, easy to test
    notes: list = field(default_factory=lambda: [Note("Welcome", "Hello!"), Note("Ideas")])
    selected: int = 0

    def add(self):
        self.notes.append(Note(f"Note {len(self.notes) + 1}"))
        self.selected = len(self.notes) - 1


pz.stylesheet({
    ".sidebar": {"width": 220, "height": "fill"},
    ".content": {"width": "fill", "padding": 20},
    "@media (max_width: 560)": {".sidebar": {"width": 160}},
})


class Notes(pz.App):
    title = "Notes"
    size = (720, 420)

    def __init__(self):
        self.store = Store()

    def sidebar(self):
        return pz.box(
            ui.panel_header("Notes", actions=[ui.icon_button("plus", self.store.add, tooltip="New note")]),
            [ui.list_item(n.title, icon="file-text", selected=i == self.store.selected,
                          on_press=lambda i=i: setattr(self.store, "selected", i))
             for i, n in enumerate(self.store.notes)],
            class_="sidebar", overflow="scroll_y",
        )

    def content(self):
        note = self.store.notes[self.store.selected]
        return pz.box(ui.heading(note.title, level=2), ui.label(note.body or "Empty", color="text_muted"),
                      class_="content", gap=8)

    def view(self):
        return pz.box(self.sidebar(), ui.divider(vertical=True), self.content(), display="flex", height="fill")


pz.run(Notes)
```

Docs: `guides/architecture`, `guides/projects`, `blocks/index`.

## Web-style pages

Pyzed apps can be written like a web page, and this is the default way to lay out a new app:
`pz.box` is the `div` (`display="block"`, `"flex"`, `"grid"` or `"stack"`, with `gap`,
`overflow` and children styled `position="absolute"`), `pz.stylesheet` is the CSS file (classes,
`#id`, a component's name, `:hover`/`:pressed`/`:focus`, `transition` and `@media` rules), and a
`pz.Component` nests like an HTML element: its positional arguments are its `children`, its
`stylesheet` styles it (`&` is the component) and `pz.provide`/`use_context` share values with
everything inside. `pz.media(...)`, `pz.viewport()` and `pz.current_breakpoint()` adapt the view itself.

```python
import pyzed as pz
from pyzed import ui

pz.stylesheet({
    ".page": {"padding": 32, "width": "fill", "height": "fill"},
    ".title": {"size": 26, "weight": "bold"},
    ".muted": {"color": "text_muted"},
    "@media (max_width: 640)": {".page": {"padding": 16}, ".title": {"size": 20}},
})


class Tile(pz.Component):
    """A clickable tile: what it shows comes in as children."""

    name: str = ""
    children: list = ()
    events = {"pick": "The tile was clicked (event.value is its name)."}
    stylesheet = {
        "&": {"background": "panel", "border": (1, "border"), "radius": 10, "padding": 16, "transition": 120},
        "&:hover": {"border_color": "accent", "translate": (0, -2)},
        "&.chosen": {"border": (2, "accent")},
    }

    def render(self):
        mark = ui.label("✓ Chosen").classes("muted") if pz.use_context("chosen") == self.name else None
        return pz.box(*self.children, mark, gap=6).on(click=lambda: self.emit("pick", self.name), cursor="pointer")


class Plans(pz.App):
    title = "Plans"
    size = (860, 480)

    def __init__(self):
        self.chosen = "Pro"

    def tile(self, name, price, text):
        return Tile(
            pz.text(name).style(weight="semibold"),
            pz.text(price).style(size=22, weight="bold"),
            pz.text(text).classes("muted"),
            ui.badge("Popular").style(position="absolute", top=0, right=0) if name == "Pro" else None,
            name=name, class_="chosen" if name == self.chosen else None,
            on_pick=lambda e: setattr(self, "chosen", e.value),
        )

    def view(self):
        plans = [("Free", "$0", "To try it."), ("Pro", "$8", "To ship every week."), ("Team", "$20", "For teams.")]
        with pz.provide(chosen=self.chosen):
            tiles = [self.tile(*plan) for plan in plans]
        return pz.box(
            pz.text("Pick a plan").classes("title"),
            pz.box(tiles, display="grid", columns=1 if pz.media("max_width: 640") else 3, gap=16),
            pz.box(ui.button("Cancel", lambda: None), ui.button(f"Continue with {self.chosen}", lambda: None,
                                                               variant="solid"),
                   display="flex", justify="end", gap=8),
            class_="page", gap=20, overflow="scroll",
        )


pz.run(Plans)
```

Docs: `guides/layout` (boxes), `theming/styles` (states, stylesheets, responsive styles),
`guides/components` (children, context and styles).

## Background work without freezing the UI

A callback that returns a coroutine runs in the background; whatever it returns (or yields) goes
to `update`. `Command.perform` does the same for a blocking function.

```python
import asyncio

import pyzed as pz
from pyzed import ui


class Loader(pz.App):
    title = "Loader"
    size = (360, 200)

    def __init__(self):
        self.status = "Idle"

    async def load(self):
        self.status = "Loading…"
        await asyncio.sleep(0.5)          # an HTTP call, a database query...
        return ("loaded", 42)

    def update(self, message):
        match message:
            case ("loaded", count):
                self.status = f"Loaded {count} items"

    def view(self):
        return pz.center(pz.column([ui.label(self.status), ui.button("Load", self.load, icon="download")],
                                   spacing=12, align="center"))


pz.run(Loader)
```

Docs: `guides/async`, `guides/commands`.

## Forms with validation

`ui.field` shows a label, a hint and an error. With Pydantic, SQLModel or Django forms,
`pz.validation_errors(error)` turns a validation error into `{field: message}`.

```python
import pyzed as pz
from pyzed import ui


class Signup(pz.App):
    title = "Sign up"
    size = (400, 260)

    def __init__(self):
        self.email = ""
        self.errors = {}

    def submit(self):
        self.errors = {} if "@" in self.email else {"email": "Enter a valid email address."}

    def view(self):
        return pz.column([
            ui.field("Email", ui.input(self.email, lambda v: setattr(self, "email", v), placeholder="you@example.com",
                                       on_submit=self.submit), error=self.errors.get("email")),
            ui.button("Create account", self.submit, variant="solid", full_width=True),
        ], spacing=12, padding=24)


pz.run(Signup)
```

Docs: `integrations/overview`, `integrations/pydantic`, `integrations/sqlmodel`, `editor/data-binding`.

## Dates, files and the operating system

`ui.DatePicker`, `ui.DateRangePicker`, `ui.TimePicker` and `ui.Calendar` are components: `on_change`
gets an event whose `value` is a `datetime.date`, a `(start, end)` pair or a `datetime.time`.
`format` takes tokens (`"DD/MM/YYYY"`, `"MMM D, YYYY"`, `"h:mm A"`) or a `strftime` pattern, and
`ui.format_date`/`ui.parse_date` use the same ones. `ui.file_input` opens the system's file dialog,
`ui.DropZone` takes files dropped on the window and `pz.Launcher` opens files and links with the
system's programs.

```python
import datetime

import pyzed as pz
from pyzed import ui


class Trip(pz.App):
    title = "Trip"
    size = (460, 320)

    def __init__(self):
        self.stay = (datetime.date(2026, 10, 5), datetime.date(2026, 10, 9))
        self.leave = datetime.time(9, 30)
        self.ticket = ""
        self.launcher = pz.Launcher()

    def view(self):
        start, end = self.stay
        return pz.column([
            ui.field("Stay", ui.DateRangePicker(value=self.stay, format="DD/MM/YYYY",
                                                on_change=lambda e: setattr(self, "stay", e.value))),
            ui.field("Leave at", ui.TimePicker(value=self.leave, format="h:mm A",
                                               on_change=lambda e: setattr(self, "leave", e.value))),
            ui.field("Ticket", ui.file_input(self.ticket, lambda path: setattr(self, "ticket", path),
                                             filters="PDF: pdf")),
            ui.label(f"{(end - start).days} nights from {ui.format_date(start, 'dddd D MMMM')}"
                     if start and end else "Pick the dates"),
            ui.button("Open ticket", lambda: self.launcher.open(self.ticket), disabled=not self.ticket),
        ], spacing=12, padding=24)


pz.run(Trip)
```

Docs: `library/date-picker`, `library/calendar`, `library/file-input`, `library/drop-zone`, `guides/services`.

## Large data: virtual lists and memoized views

`ui.virtual_list` (and `pz.virtual_column`) only build the rows in view, so a million rows stay
fast. `@pz.memo` reuses a subtree while its arguments don't change; pass everything it reads as
arguments.

```python
import pyzed as pz
from pyzed import ui


@pz.memo
def header(count: int):
    return ui.panel_header(f"{count:,} log lines")


class Logs(pz.App):
    title = "Logs"
    size = (520, 320)

    def __init__(self):
        self.lines = [f"[{i:06}] request handled" for i in range(100_000)]

    def view(self):
        return pz.column([
            header(len(self.lines)),
            ui.virtual_list(self.lines, lambda line: pz.text(line, font="mono", size=12), item_height=20, id="logs"),
        ], height="fill")


pz.run(Logs)
```

Docs: `guides/performance`.

## Animation and effects

Every widget has `animate()` (presets such as `"fade_in_up"`, `"lift"`, `"pulse"`, or values to
animate to) and `transition()` (CSS-like). Effects are style properties: `glow`, `bloom`, `blur`,
`backdrop_blur` and `glass`.

```python
import pyzed as pz
from pyzed import ui


class Effects(pz.App):
    title = "Effects"
    size = (420, 260)

    def __init__(self):
        self.open = True

    def view(self):
        card = pz.column([ui.heading("Glass card", level=3), ui.label("Hover me", color="text_muted")],
                         spacing=4, padding=20)
        return pz.center(pz.column([
            card.style(glass=True, radius=12).animate("fade_in_up").animate("lift", on="hover"),
            ui.button("Toggle", lambda: setattr(self, "open", not self.open)).style(glow="accent"),
            pz.text("Shown").transition(opacity=1 if self.open else 0),
        ], spacing=16, align="center"))


pz.run(Effects)
```

Docs: `animation/index`, `library/effects`.

## Shaders

`pz.shader` paints a widget on the GPU with a WGSL `shade` function. Uniforms become functions
(`speed()`, `tint()`): numbers, tuples of 2 to 4 numbers, hex colors or theme tokens.

```python
import pyzed as pz

WAVES = """
fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> {
    let wave = 0.5 + 0.5 * sin(uv.x * 12.0 + time * speed());
    return vec4<f32>(mix(vec3<f32>(0.1, 0.1, 0.3), tint().rgb, wave), 1.0);
}
"""


class Waves(pz.App):
    title = "Waves"
    size = (420, 240)

    def view(self):
        return pz.shader(WAVES, uniforms={"speed": 2.0, "tint": "accent"}, height="fill")


pz.run(Waves)
```

Docs: `shading/shaders`, `library/shader`.

## Games: a frame loop and held keys

`pz.frames(callback)` calls `callback(dt)` every frame; `pyzed.game` reads held keys
(`game.vector()`, `game.axis(...)`, `pz.is_pressed("space")`) and draws sprites, glows and
particles on a `pz.canvas`.

```python
import pyzed as pz
from pyzed import draw, game


class Ship(pz.App):
    title = "Ship"
    size = (480, 320)

    def __init__(self):
        self.x, self.y = 240, 160

    def subscriptions(self):
        return [pz.frames(self.tick)]

    def tick(self, dt):
        dx, dy = game.vector()             # arrows / WASD, diagonals normalized
        self.x += dx * 300 * dt
        self.y += dy * 300 * dt

    def view(self):
        return pz.canvas([draw.background("#0b0e14"), *game.glow(self.x, self.y, 14, "#22d3ee")],
                         width=480, height=320)


pz.run(Ship)
```

Docs: `games/index`, `games/snake`, `games/breakout`.

## A custom window frame with menus

`frame = "custom"` draws Pyzed's own title bar (or `"macos"`, `"windows"`, `"gnome"`...) and
`frame_menus()` adds Zed-like menus to it.

```python
import pyzed as pz
from pyzed import ui


class Editor(pz.App):
    title = "Editor"
    size = (560, 320)
    frame = "custom"

    def frame_menus(self):
        return [
            ui.Menu("File", [ui.MenuItem("New", lambda: None, keys="ctrl-n"), ui.SEPARATOR,
                             ui.MenuItem("Quit", self.close)]),
            ui.Menu("Help", [ui.MenuItem("About", lambda: None)]),
        ]

    def view(self):
        return pz.center(ui.label("Your app goes here", color="text_muted"))


pz.run(Editor)
```

Docs: `guides/windows`.

## Anchored layouts

`pz.anchor_layout` places children like the designer does: each `pz.anchor(...)` keeps its
distance to the edges it is anchored to when the window is resized.

```python
import pyzed as pz
from pyzed import ui


class Anchored(pz.App):
    title = "Anchors"
    size = (420, 260)

    def view(self):
        return pz.anchor_layout([
            pz.anchor(ui.heading("Title", level=3), x=16, y=16, width=200, height=32),
            pz.anchor(ui.button("Save", lambda: None, variant="solid"), x=300, y=212, width=104, height=32,
                      anchor="bottom_right"),
        ], design=(420, 260))


pz.run(Anchored)
```

Docs: `guides/layout`, `editor/layouts`.

## Timeline animations

Several widgets (or app attributes) moving together, like an intro or a HUD reaction, go on one
timeline: a `pz.Clip` with a `pz.Track` per property, played by a `pz.AnimationPlayer`. A track
path `"card:opacity"` animates every widget that plays the `card` target; `":score"` animates an
app attribute, so anything can be animated. Save clips as a `.pzanim` library (`new_animation`)
and load it with `pz.AnimationPlayer("ui.pzanim")`.

```python
import pyzed as pz
from pyzed import ui

INTRO = pz.Clip("intro", length=1.4, tracks=[
    pz.Track("card:opacity", {0: 0, 0.35: 1}),
    pz.Track("card:y", [(0, 30, "ease_out_back"), (0.5, 0)]),
    pz.Track("title:scale", [(0.3, 0.7, "ease_out_back"), (0.7, 1)]),
    pz.Track(":score", [(0.6, 0, "ease_out_cubic"), (1.4, 12_480)]),
])


class Results(pz.App):
    title = "Results"
    size = (420, 260)

    def __init__(self):
        self.score = 0
        self.player = pz.AnimationPlayer(INTRO, autoplay="intro")

    def view(self):
        return pz.center(pz.column([
            ui.heading("LEVEL COMPLETE", level=2).animate(self.player["title"]),
            ui.label(f"{self.score:,.0f} points", color="text_muted"),
            ui.button("Replay", lambda: self.player.play("intro", restart=True), icon="rotate-ccw"),
        ], spacing=12, align="center", padding=24).style(glass=True, radius=12).animate(self.player["card"]))


pz.run(Results)
```

Docs: `animation/timeline`, `editor/animations-and-effects`.

## Drag and drop

Lists you reorder and move between (a Kanban board), and a trash can. The sortables animate the
gap, the shadow and the drop natively; Python only applies the drop with `pz.dnd.move`. Lists
with the same `group` exchange items; `pull="clone"` makes a palette, `handle=True` drags only by
a `pz.drag_handle`, `combine=True` drops onto items, `keyboard=True` reorders with Alt+arrows.
For free canvases use `pz.droppable(..., snap=8, guides=True)` around `pz.pin`ned
`pz.draggable`s and save `event.item_x`/`event.item_y`; for node wires `pz.draggable(..., preview="wire")`.

```python
import pyzed as pz
from pyzed import ui


class Board(pz.App):
    title = "Board"
    size = (640, 420)

    def __init__(self):
        self.lists = {"todo": ["Design", "Build", "Test"], "done": ["Plan"]}
        self.dragging = False

    def card(self, text):
        t = pz.theme.current()
        return pz.container(ui.label(text), padding=10, width="fill").style(
            background=t.elevated, border_color=t.border, border_width=1, radius=8)

    def column(self, name):
        t = pz.theme.current()
        cards = pz.sortable(items=self.lists[name], item=self.card, key=str, id=name, group="cards",
                            spacing=8, height="fill", on_reorder=lambda e: pz.dnd.move(self.lists, e),
                            on_drag_start=lambda e: setattr(self, "dragging", True),
                            on_drag_end=lambda e: setattr(self, "dragging", False))
        return pz.container(pz.column([ui.label(name.title(), weight="bold"), cards], spacing=10),
                            padding=12, width="fill", height="fill").style(background=t.surface, radius=10)

    def view(self):
        trash = pz.droppable(ui.card(ui.label("Drop here to delete")), "trash", accepts="cards",
                             on_drop=lambda e: self.lists[e.from_list].pop(e.from_index))
        return pz.column([pz.row([self.column("todo"), self.column("done")], spacing=12, height="fill"),
                          trash if self.dragging else ui.muted("Drag the cards")], spacing=12, padding=16)


pz.run(Board)
```

Docs: `dnd/index`, `dnd/basics/sortable`, `dnd/guides/free-canvas`, `dnd/tutorials/kanban`.

## States of components

Components carry their own states: buttons take `loading`, `disabled`, `selected`, `tooltip`
and `size`; icon buttons an `indicator` dot and `keys`; inputs `invalid`, `readonly`,
`max_length` and `on_clear`. Show a state instead of building it by hand.

```python
import asyncio

import pyzed as pz
from pyzed import ui


class Save(pz.App):
    title = "Save"
    size = (420, 220)

    def __init__(self):
        self.name = ""
        self.saving = False

    async def save(self):
        self.saving = True
        await asyncio.sleep(1)
        return "saved"

    def update(self, message):
        if message == "saved":
            self.saving = False

    def view(self):
        return pz.column([
            pz.row([ui.heading("Profile", level=3), pz.space(width="fill"),
                    ui.icon_button("bell", lambda: None, tooltip="Notifications", indicator="accent")],
                   align="center"),
            ui.input(self.name, lambda v: setattr(self, "name", v), placeholder="Name", invalid=not self.name,
                     max_length=40, on_clear=lambda: setattr(self, "name", "")),
            ui.button("Save", self.save, variant="solid", loading=self.saving, disabled=not self.name,
                      tooltip="Save the profile", keys="ctrl-s"),
        ], spacing=12, padding=20)


pz.run(Save)
```

Docs: `components/basics`, `components/forms`, `components/controls`.
