---
title: The animation player
description: "pz.AnimationPlayer plays Pyzed timeline clips: play, pause, resume, stop, seek, play backwards, speed, queues and events, and saves reusable clips in .pzanim libraries."
sidebar:
  order: 8
---

`pz.AnimationPlayer` plays the [clips](/pyzed/animation/timeline/) you give it, one at a time, and
gives each widget its part with `player["target"]`.

```python
self.player = pz.AnimationPlayer(INTRO, IDLE, "ui.pzanim", autoplay="intro",
                                 on_started=..., on_finished=...)
```

- **Sources:** clips, lists of clips, [libraries](#libraries-and-pzanim-files) or paths of
  `.pzanim` files.
- **Where to keep it:** in an attribute of the app (or of a window). There it finds its **owner**, the
  object whose attributes and methods the tracks and calls use, and keeps itself running.
- **Targets:** `widget.animate(self.player["card"])` gives a widget the `card` target. Every widget
  that uses the same target follows it.

## Controls

![The level-complete screen driven by the player: play, pause, seek to 0.5 s, play backwards, then play at double speed, with the call shown at the top and the controls following](/pyzed/media/animation/timeline-player.webp)

| Call | What it does |
| --- | --- |
| `play(name, speed=1, backwards=False, restart=False)` | Plays a clip, or goes on with the current one. A clip that is already playing goes on unless `restart`; a finished one starts over. |
| `play_backwards(name)` | Plays it backwards from the end. |
| `pause()`, `resume()`, `toggle()` | Stops the time and starts it again. |
| `stop(reset=False)` | Goes back to the first frame and clears the queue. With `reset=True` the widgets go back to their own values. |
| `seek(seconds)` | Jumps to a time. Calls between don't run. |
| `advance(seconds)` | Moves the time by hand and runs the calls on the way (handy in tests). |
| `queue(name)`, `clear_queue()` | Plays a clip when the current one ends. |
| `speed` | The playback speed of every clip (`2` is twice as fast). `play(speed=...)` multiplies it. |

```python
def replay(self):
    self.player.play("intro", restart=True)
    self.player.queue("idle")            # loops after the intro

def set_speed(self, label):
    self.player.speed = float(label.rstrip("×"))
```

## State and events

| Read | Gives |
| --- | --- |
| `current` | The name of the clip playing or paused (`None` when stopped). |
| `position`, `length` | Where the playhead is and how long the clip is, in seconds. |
| `playing`, `paused`, `finished` | What the player is doing. |
| `queued` | The clips waiting to play. |
| `names`, `has(name)`, `clip(name)` | The clips it knows. |
| `value(path)` | The value the current clip gives a path right now: `player.value(":score")`. |

`on_started(name)` and `on_finished(name)` are called when a clip starts and when it ends (looping
clips never end). A slider bound to `position` and `seek` makes a scrubber:

```python
ui.slider(p.position, p.seek, min=0, max=p.length, step=0.01)
```

:::tip[It only wakes your app when needed]
Widget tracks play natively and never need your code. A clip with attribute tracks updates them up
to `fps` times a second (60 by default, `pz.AnimationPlayer(..., fps=30)` for less). Without them,
the player only wakes up for the next call or the end of the clip.
:::

## Libraries and .pzanim files

Clips are immutable values, so you can share them between players and apps. An
`AnimationLibrary` groups them and saves them in a `.pzanim` file (JSON) that you can keep in your
project and load in any app:

```python
library = pz.AnimationLibrary([INTRO, IDLE], name="ui")
library.save("ui.pzanim")

player = pz.AnimationPlayer("ui.pzanim")      # clips named "ui/intro", "ui/idle"
player.play("ui/intro")
library = pz.load_animations("ui.pzanim")
```

A library also has `add`, `remove`, `rename` and `names`. Forms made in Pyzed Design keep their clips
inside the `.pzform`; see the [Animation panel](/pyzed/editor/animations-and-effects/#timeline-animations).

## Reusing clips

![The same bouncing clip on three widgets: played on its own target, retargeted to another widget, and turned into a pz.Animation](/pyzed/media/animation/timeline-reuse.webp)

Clip methods return a **new** clip, so the original stays as it is:

- `clip.retarget({"card": "panel"})` moves the clip's tracks to other targets.
- `clip.animation("card")` turns one target's tracks into a `pz.Animation`. Play it with `animate()`
  without a player, or give it a name with `pz.define_animation`.
- `clip.with_key(path, time, value)`, `without_key`, `with_track` and `without_track` edit it.
- `clip.to_dict()` and `pz.Clip.from_dict()` turn it into JSON-friendly data and back.
