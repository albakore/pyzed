---
title: Timeline animations
description: "Animate many widgets and your app's state on one timeline with clips, tracks, keys and method calls, like Godot's AnimationPlayer, and save them as reusable .pzanim files."
sidebar:
  order: 3.55
---

`animate()` gives one widget its own motion. When several widgets have to move together, such
as a title card, a cutscene, a HUD that reacts to a hit or an onboarding sequence, put them on
one timeline. A **clip** holds that timeline and an **animation player** plays it. Godot's
AnimationPlayer works the same way.

![A level-complete screen played by an AnimationPlayer, with its play, pause, seek and speed controls](../../../assets/tutorials/timeline.png)

```python
import pyzed as pz

INTRO = pz.Clip("intro", length=2.2, tracks=[
    pz.Track("card:opacity", {0: 0, 0.35: 1}),
    pz.Track("card:y", [(0, 40, "ease_out_back"), (0.5, 0)]),
    pz.Track("title:scale", [(0.3, 0.6, "ease_out_back"), (0.7, 1)]),
    pz.Track(":score", [(0.7, 0, "ease_out_cubic"), (1.9, 12_480)]),
], calls=[pz.Call(1.6, "chime")])


class Game(pz.App):
    def __init__(self):
        self.score = 0
        self.player = pz.AnimationPlayer(INTRO, autoplay="intro")

    def chime(self):
        ...

    def view(self):
        return pz.column([
            pz.text("LEVEL COMPLETE").animate(self.player["title"]),
            pz.text(f"{self.score:,.0f}"),
        ]).animate(self.player["card"])
```

The full example is [`examples/timeline.py`](https://github.com/albakore/pyzed/blob/main/examples/timeline.py).

## Clips, tracks and keys

A `pz.Clip` has a `name`, a `length` in seconds, `tracks` and `calls`. The `length` defaults to
the time of its last key or call.

A `pz.Track` changes one property over time. Its path says what it animates:

| Path | Animates |
| --- | --- |
| `"card:opacity"` | A widget property of every widget that plays the `card` target. |
| `":score"` | An attribute of the app. |
| `":hud.hp"` | An attribute of an attribute (follows the dots). |

Widget properties are the ones `animate()` takes: `opacity`, `x`, `y`, `scale`, `rotate`,
`blur`, `background`, `border_color`, `color`, `radius`, `border_width`, `glow`,
`glow_color`, `width`, `height`, `padding` and `font_size`. They play natively at the
display's frame rate, and your code doesn't run while they play.

App attributes can hold anything: numbers, colors (`"#rrggbb"`) and tuples of numbers mix
between keys, and other values (text, booleans) change at each key. Since `view()` reads
them, they can drive **any parameter of any widget**, such as the text of a label, the value
of a progress bar, a size or an icon.

You can write keys in several ways:

```python
pz.Track("card:x", {0: -40, 0.5: 0})                       # {time: value}
pz.Track("card:x", [(0, -40, "ease_out_back"), (0.5, 0)])  # (time, value, easing to the next key)
pz.Track("card:x", [pz.Key(0, -40), pz.Key("500ms", 0)])   # Key objects; times also as "500ms"
```

- **Easing.** Each key's `easing` is the curve to the next key. Every name in
  `pz.animation.EASINGS` works, and so do `(x1, y1, x2, y2)` cubic Béziers and `"steps(n)"`.
  The track's `easing` (default `"linear"`) applies to keys that don't set one.
- **Holding values.** `interpolation="discrete"` holds each value until the next key.
- **Muting.** `enabled=False` keeps a track in the clip without playing it.
- **Before and after the keys.** A widget holds the first key's value before it and the last
  key's value after it, like in Godot.

### Method calls

`pz.Call(time, method, *args)` calls a method of the app when the clip passes `time`.
`method` can also be any callable. Whatever it returns is handled like a callback's return
value (a `Command`, a message). Calls run when playing forward, backward and on every loop,
but not when you `seek` over them.

### Loops

- `loop="none"` plays once and holds the last frame.
- `loop="loop"` starts again from the beginning.
- `loop="pingpong"` goes back and forth.

## The player

```python
self.player = pz.AnimationPlayer(INTRO, IDLE, "ui.pzanim", autoplay="intro",
                                 on_started=..., on_finished=...)
```

Keep the player in an attribute of the app (or a window). It finds its owner there, the object
whose attributes and methods the tracks and calls use, and keeps itself running. Give each
widget its target with `widget.animate(self.player["card"])`. Every widget that uses the same
target follows it.

| Call | Does |
| --- | --- |
| `play(name, speed=1, backwards=False, restart=False)` | Plays a clip, or goes on with the current one. A clip that is already playing keeps going unless `restart`. A finished clip starts again. |
| `play_backwards(name)` | Plays in reverse from the end. |
| `pause()`, `resume()`, `toggle()` | Stops time and goes on. |
| `stop(reset=False)` | Back to the first frame. `reset=True` lets widgets go back to their own values. |
| `seek(seconds)` | Jumps to a time. |
| `advance(seconds)` | Moves time forward by hand, running calls (handy in tests). |
| `queue(name)` | Plays a clip after the current one ends. |
| `speed` | The playback speed of every clip. `play(speed=...)` multiplies it. |

To read the player's state, use `current`, `position`, `length`, `playing`, `paused`,
`finished`, `queued`, `names` and `value(path)`. `on_started(name)` and `on_finished(name)` are
called when a clip starts and ends (looping clips never end).

The player only wakes your app when it must. A clip with attribute tracks updates them up to
`fps` times a second (60 by default). Otherwise the player only wakes for the next call or
for the end of the clip. Widget tracks never need it.

## Libraries and .pzanim files

Clips are immutable values, so you can share and reuse them. An `AnimationLibrary` groups
them and saves them as a `.pzanim` file (JSON) that you can keep with your project and load
in any app:

```python
library = pz.AnimationLibrary([INTRO, IDLE], name="ui")
library.save("ui.pzanim")

player = pz.AnimationPlayer("ui.pzanim")      # clips named "ui/intro", "ui/idle"
player.play("ui/intro")
library = pz.load_animations("ui.pzanim")
```

Clips have helpers to reuse and edit them. Each one returns a new clip:

- `clip.retarget({"card": "panel"})` moves the clip's tracks onto other widgets.
- `clip.animation("card")` turns one target's tracks into a `pz.Animation`. You can play it
  with `animate()` without a player, or name it with `pz.define_animation`.
- `clip.with_key(path, time, value)`, `without_key`, `with_track` and `without_track` edit
  the clip.
