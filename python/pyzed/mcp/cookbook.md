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


class Notes(pz.App):
    title = "Notes"
    size = (720, 420)

    def __init__(self):
        self.store = Store()

    def sidebar(self):
        return pz.column([
            ui.panel_header("Notes", actions=[ui.icon_button("plus", self.store.add, tooltip="New note")]),
            *[ui.list_item(n.title, icon="file-text", selected=i == self.store.selected,
                           on_press=lambda i=i: setattr(self.store, "selected", i))
              for i, n in enumerate(self.store.notes)],
        ], width=220)

    def content(self):
        note = self.store.notes[self.store.selected]
        return pz.column([ui.heading(note.title, level=2), ui.label(note.body or "Empty", color="text_muted")],
                         spacing=8, padding=20, width="fill")

    def view(self):
        return pz.row([self.sidebar(), ui.divider(vertical=True), self.content()], height="fill")


pz.run(Notes)
```

Docs: `guides/architecture`, `guides/projects`, `blocks/index`.

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

Docs: `guides/animation`, `library/effects`.

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

Docs: `guides/timeline`, `editor/animations-and-effects`.

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
