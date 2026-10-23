---
title: Devices and screens
description: "Run one Pyzed app on desktops, touch panels, car displays, phones, kiosks and TVs: device profiles, design resolution, touch media queries and focus with the arrow keys."
sidebar:
  order: 6.5
---

The same app can run on a laptop, a touch panel on a wall, a car's dashboard, a phone or a TV.
They differ in how people use them (a mouse, a finger, a remote), in their screens and in how fast
they draw. A **device profile** tells Pyzed which one it runs on, and Pyzed fills in the window
options and rendering settings your app leaves at their defaults.

```python
import pyzed as pz

class Dashboard(pz.App):
    title = "Dashboard"
    device = "automotive"        # fullscreen kiosk, no pointer, arrows move the focus
    design_size = (1920, 720)    # laid out for this screen, scaled to the real one

    def view(self):
        ...
```

## The profiles

| Profile | Used for | What it sets |
| --- | --- | --- |
| `desktop` | Laptops and desktop computers (the default) | Nothing: windows as you declare them. |
| `touch` | Tablets, touch monitors, convertibles | Touch first (`pointer: coarse`), scale 1.15, 44 px targets. |
| `automotive` | Car displays, machine panels | Fullscreen kiosk, hidden pointer, arrow focus, scale 1.25, 64 px targets, medium quality. |
| `mobile` | Phones (the default on Android) | Touch, fullscreen, no pointer, 48 px targets, medium quality. |
| `kiosk` | Points of sale, museum and info panels | Fullscreen kiosk, touch, scale 1.15, paused background animations. |
| `tv` | TVs and set-top boxes | Fullscreen, no pointer, arrow focus, scale 2, medium quality. |

Your own options always win: a profile only fills in what the app's class leaves alone. A
`kiosk = False` in your `App` keeps the window closable on a `kiosk` device.

## Choosing the profile

Pyzed looks, in this order, at:

1. `App.device`: a profile name or a `pz.Device`.
2. The `PYZED_DEVICE` environment variable: handy to try a profile on your computer
   (`PYZED_DEVICE=tv python app.py`).
3. `device = "..."` in `[tool.pyzed.platform.<system>]` of `pyproject.toml` (`linux`, `windows`,
   `macos`, `android`), then in `[tool.pyzed]`.
4. The system: `mobile` on Android, `desktop` elsewhere.

`pz.device()` returns the profile in use and `pz.set_device("touch")` changes it while the app runs.

## Your own profiles

Define profiles in `pyproject.toml`. `extends` names the profile to start from; a table named like
a built-in profile changes it:

```toml
[tool.pyzed]
device = "dashboard"

[tool.pyzed.platform.windows]
device = "desktop"           # the same project on a Windows laptop

[tool.pyzed.device.dashboard]
extends = "automotive"
design_size = [1920, 720]
stretch = "fit"
quality = "low"

[tool.pyzed.device.tv]
scale = 1.5
```

Or in code: `pz.Device("panel", touch=True, kiosk=True, quality="low")`, or
`pz.devices.PROFILES["tv"].replace(scale=1.5)`.

| Field | Meaning |
| --- | --- |
| `touch` | The screen is touched more than clicked: `pz.media("pointer: coarse")` is true. |
| `pointer` | `False` hides the pointer over the windows. |
| `kiosk`, `fullscreen` | The main window opens as a kiosk or fullscreen (see [Screens and kiosks](/pyzed/guides/windows/#screens-and-kiosks)). |
| `arrow_focus` | The arrow keys move the focus (see below). |
| `scale` | Interface scale of the windows that leave `scale` at 1. |
| `min_target` | The smallest comfortable control in logical pixels; read it with `pz.device().min_target` to size your own components. |
| `design_size`, `stretch` | The design resolution (see below). |
| `quality` | `"high"`, `"medium"` or `"low"`: rendering defaults for slower hardware. |
| `reduced_motion` | `True` turns animations off, `None` follows the system. |
| `rendering` | `pz.Rendering` fields on top of the quality level. |

## Quality levels

`quality` fills in the [rendering settings](/pyzed/editor/settings/#rendering) the project leaves
at `"auto"`:

| Quality | Antialiasing | Frame rate | Background windows | Other |
| --- | --- | --- | --- | --- |
| `high` | 4x | the screen's | as focused | |
| `medium` | 2x | 60 | 10 fps | |
| `low` | off | 30 | paused | low GPU memory, low power GPU |

## Design resolution

Panels and car displays have one known screen, and designers draw for it. `design_size` lays the
view out for that size and scales it to the real window, like Godot's stretch modes:

- `stretch = "expand"` (the default) scales until the design fits and lets the view grow into the
  space left, so a wider screen shows more.
- `stretch = "fit"` scales it the same way and keeps the design's size, centered, with bars around it.
- `stretch = "none"` ignores `design_size`.

`pz.viewport()` and media queries see the design's units, so breakpoints keep working.

## Touch, pointer and device in styles

Media queries answer questions about the device, in code and in stylesheets:

```python
padding = 20 if pz.media("pointer: coarse") else 8     # bigger on touch screens

pz.stylesheet({
    "@(pointer: coarse)": {"button": {"padding": [14, 20]}},
    "@(device: tv)": {"text": {"size": 22}},
})
```

`pointer` is `coarse` on touch screens, `none` where nothing points (TVs) and `fine` with a mouse.

## Focus with the arrow keys

TV remotes, rotary knobs and steering wheel pads send arrow keys. With `App.arrow_focus = True`
(on by default in the `tv` and `automotive` profiles), an arrow no control used moves the focus to
the nearest control that way. `on_key` sees the key first; returning something from it keeps the
focus where it is. `Command.focus_direction("left")` does the same from code.

Controls take the focus with `pz.focusable`:

```python
pz.focusable(card, self.open, keys=["enter"])
```

## Linux devices without a desktop

On a car display or a kiosk, run the app as the only program of a kiosk compositor such as
[cage](https://github.com/cage-kiosk/cage), started by the system at boot:

```bash
PYZED_DEVICE=automotive cage -- python app.py
```

There is no desktop, no panel and nothing to close; with `background_fps = 0` the app uses no CPU
while nothing moves.
