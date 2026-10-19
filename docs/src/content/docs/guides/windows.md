---
title: Multiple windows
description: Open, close and control windows with pz.Window.
sidebar:
  order: 6
---

An app can have as many windows as you want. The main window is your `App`; the others are
subclasses of `pz.Window`, each with its own `view()`, title, size and theme.

![Multiple windows](../../../assets/tutorials/multi-window.png)

```python
import pyzed as pz
from pyzed import ui


class Settings(pz.Window):
    title = "Settings"
    size = (420, 300)
    theme = "One Light"                # optional: defaults to the app's theme

    def view(self):
        return pz.container(
            pz.column([
                ui.heading("Settings", level=2),
                ui.field("Autosave", ui.switch(self.app.autosave, self.app.set_autosave)),
                ui.button("Close", self.close),
            ], spacing=12),
            padding=20,
        )


class Main(pz.App):
    def __init__(self):
        self.autosave = True
        self.settings = Settings()

    def set_autosave(self, value):
        self.autosave = value

    def open_settings(self):
        if not self.settings.is_open:
            return self.settings.open()
        return pz.Command.focus_window(self.settings)

    def view(self):
        return pz.center(ui.button("Open settings", self.open_settings, icon="settings"))


pz.run(Main)
```

## How it works

```mermaid
flowchart LR
    subgraph APP["App (shared state)"]
        ST[("self.*")]
    end
    M["Main window"] -->|view| ST
    W1["Window A"] -->|"view / self.app"| ST
    W2["Window B"] -->|"view / self.app"| ST
    M -->|"return Window().open()"| W1
    W1 -->|"events"| U["update()"]
    W2 -->|"events"| U
    M -->|"events"| U
    U --> ST
```

- `window.open()` (or `Command.open_window(window)`) returns the command that opens it.
- `self.app` points to the app inside each window, so they **share state**: callbacks like
  `self.app.save` work directly.
- Messages produced in a window go to its `update()`, which by default forwards them to
  `app.update()`.
- `window.is_open` tells whether it is open. Closing the main window ends the app.

## Options

Class or instance attributes:

| Attribute | Description |
| --- | --- |
| `title` | Text or callable. |
| `size`, `min_size`, `max_size` | Sizes in logical pixels. |
| `position` | `"center"` or `(x, y)`. |
| `resizable`, `decorations` | `decorations=False` removes the system frame (custom title bar). |
| `transparent`, `maximized`, `fullscreen` | Initial state. |
| `scale` | Interface scale. |
| `theme` | A `Theme`, a name or `themes.auto(...)`. `None` uses the app's theme. |
| `transition`, `exit_transition` | How it animates when it opens and closes: `"fade"`, `"zoom"`, `"pop"`, `"slide_up"`... a preset or a `pz.Animation`. See [Animation](/pyzed/guides/animation/#window-transitions). |

`window_size` holds the current size (updated by the runtime).

## Hooks

| Method | When it is called |
| --- | --- |
| `on_open()` | When it opens. |
| `on_close()` | When the user asks to close it. Return `False` to keep it open (for example, to ask whether to save). |
| `on_resize(width, height)` | When it is resized. |
| `on_key(combo)` | Key presses while that window is focused. |

## Window commands

They all accept the window as the last argument; without it they act on the window that produced
the message.

| Command | Effect |
| --- | --- |
| `Command.open_window(w)` / `w.open()` | Opens the window. |
| `Command.close_window(w)` / `w.close()` | Closes it. |
| `Command.drag_window(w)` / `w.drag()` | Starts moving it with the mouse (for custom title bars). |
| `Command.minimize_window(w)` | Minimizes it. |
| `Command.toggle_maximize_window(w)` | Maximizes or restores it. |
| `Command.set_fullscreen(True, w)` | Fullscreen. |
| `Command.resize_window(width, height, w)` | Resizes it. |
| `Command.move_window(x, y, w)` | Moves it. |
| `Command.focus_window(w)` | Brings it to the front. |

### Custom title bar

```python
class Frameless(pz.App):
    decorations = False

    def view(self):
        bar = pz.mouse_area(
            ui.title_bar([ui.title_button("My app")], [ui.icon_button("x", self.close)]),
            on_press=self.drag,
            on_double_click=lambda: pz.Command.toggle_maximize_window(),
        )
        return pz.column([bar, self.content()])
```

:::note
`pz.run()` can only be called once per process (a winit limitation). For more windows, use
`pz.Window`.
:::
