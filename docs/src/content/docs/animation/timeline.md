---
title: Timeline animations
description: "Animate many widgets and your app's state on one timeline with clips, tracks, keys and method calls, like Godot's AnimationPlayer: interpolation, easing per key, loops and attribute tracks."
sidebar:
  order: 7
---

`animate()` gives one widget its own motion. When **several widgets** have to move together (a title
screen, a cutscene, a HUD reacting to a hit, a guided tour), put them on one **timeline**. A
**clip** holds that timeline and an **animation player** plays it, with play, pause, seek, speed and
queues. Godot's AnimationPlayer works the same way.

![A level-complete screen: the card rises, the title pops, three stars spin in one after another, the score counts up and the Next level button fades in, then the button keeps breathing](/pyzed/media/animation/timeline-intro.webp)

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

The complete example is [`examples/timeline.py`](https://github.com/albakore/pyzed/blob/main/examples/timeline.py).
To make clips without code, use the [Animation panel](/pyzed/editor/animations-and-effects/#timeline-animations)
of Pyzed Design.

## The parts of a timeline

![A card on the left and its clip on the right: a lane per track with its keys, a lane of calls, and a playhead moving from 0 to 2 seconds while the card fades in, rises, the title grows and the score counts](/pyzed/media/animation/timeline-tracks.webp)

| Part | What it is |
| --- | --- |
| **Clip** (`pz.Clip`) | One named timeline: a `length` in seconds, tracks, calls and a loop mode. |
| **Track** (`pz.Track`) | One property changing over time, such as the `y` of the `card`. |
| **Key** (`pz.Key`) | A value at a time on a track. Pyzed fills in the time between keys. |
| **Call** (`pz.Call`) | A method of your app that runs when the playhead passes its time. |
| **Target** | A name, like `"card"`, that widgets join with `.animate(self.player["card"])`. |
| **Playhead** | Where the player is in the clip (`player.position`). |

A clip with no `length` lasts until its last key or call.

### Track paths

A track's path says what it animates:

| Path | Animates |
| --- | --- |
| `"card:opacity"` | A property of every widget that plays the target `card`. |
| `":score"` | An attribute of the app. |
| `":hud.hp"` | An attribute of an attribute (follow the dots). |

**Widget tracks** use the [animatable properties](/pyzed/animation/properties/) (`opacity`, `x`,
`y`, `scale`, `rotate`, `blur`, colors, `radius`, `glow`, `width`, `font_size`...). They play natively
at the display's frame rate, and your code doesn't run meanwhile.

**Attribute tracks** (starting with `:`) change your app's own values, so they can control **any
parameter of any widget**: the text of a label, the value of a progress bar, a size, an icon. Numbers,
colors (`"#rrggbb"`) and tuples of numbers blend between keys; other values (text, booleans) change at
each key. See [attribute tracks and calls](#attribute-tracks-and-calls) below.

### Writing keys

Keys can be written several ways:

```python
pz.Track("card:x", {0: -40, 0.5: 0})                       # {time: value}
pz.Track("card:x", [(0, -40, "ease_out_back"), (0.5, 0)])  # (time, value, easing to the next key)
pz.Track("card:x", [pz.Key(0, -40), pz.Key("500ms", 0)])   # Key objects; times also as "500ms"
```

## Between keys

![Three tracks with the same keys, each with its curve and a ball: linear moves at a steady speed, easing per key overshoots and then eases, discrete jumps from value to value](/pyzed/media/animation/timeline-keys.webp)

- **Easing per key.** A key's `easing` is the curve **to the next key**. Any name of
  [`pz.animation.EASINGS`](/pyzed/animation/keyframes/#easing) works, as do cubic Béziers
  `(x1, y1, x2, y2)` and `"steps(n)"`. The track's `easing` (default `"linear"`) is used for keys that
  don't set one.
- **Discrete.** `interpolation="discrete"` holds each value until the next key, with no motion
  between. Good for sprite frames, texts and on/off switches.
- **Muting.** `enabled=False` keeps the track in the clip without playing it.
- **Before and after the keys.** A widget holds the first key's value before it and the last key's
  value after it, as in Godot.

## Loops

![Three playheads: once stops at the end, loop starts over, pingpong goes back and forth](/pyzed/media/animation/timeline-loops.webp)

| `loop=` | Plays |
| --- | --- |
| `"none"` (default) | Once, and stays on the last frame. |
| `"loop"` | Starts over at the end, forever. |
| `"pingpong"` | Goes to the end and back, forever. |

```python
IDLE = pz.Clip("idle", length=1.2, loop="pingpong", tracks=[
    pz.Track("button:scale", [(0, 1, "ease_in_out_sine"), (1.2, 1.06)]),
])
```

## Attribute tracks and calls

![An upload card whose status text, progress bar and file count come from attribute tracks, while the calls lane fires halfway() and finished() as the playhead passes them](/pyzed/media/animation/timeline-calls.webp)

```python
UPLOAD = pz.Clip("upload", length=2.0, tracks=[
    pz.Track(":progress", [(0, 0, "ease_in_out"), (1.8, 1)]),
    pz.Track(":status", {0: "Uploading…", 0.9: "Almost there", 1.8: "Done"}),   # texts change at each key
    pz.Track(":files", [(0, 0), (1.8, 24)]),
], calls=[pz.Call(0.9, "halfway"), pz.Call(1.8, "finished", "report.pdf")])


class Upload(pz.App):
    def __init__(self):
        self.progress, self.status, self.files = 0.0, "", 0
        self.player = pz.AnimationPlayer(UPLOAD, autoplay="upload")

    def halfway(self):
        ...

    def finished(self, name):
        ...

    def view(self):
        return pz.column([pz.text(self.status), ui.progress(self.progress), pz.text(f"{self.files:.0f} / 24")])
```

`pz.Call(time, method, *args)` calls a method of the app when the clip passes that time. `method`
can also be any function. What it returns is handled like what a callback returns (a `Command`, a
message). Calls run when playing forward, backwards and on every turn of a loop, but not when you
jump with `seek`.

:::note[The owner]
Attribute tracks and calls act on the player's **owner**: the app (or window) whose attribute holds
the player. Pyzed finds it on its own; pass `owner=` to `pz.AnimationPlayer` to choose another object.
:::

Next: [the animation player](/pyzed/animation/player/) plays, pauses, seeks and queues clips, and
saves them in `.pzanim` files.
