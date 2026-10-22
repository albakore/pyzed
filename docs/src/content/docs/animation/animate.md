---
title: animate() and triggers
description: "widget.animate() in Pyzed: play a preset or your own animation when a widget appears, on hover, press, focus or click, or while a flag is on, with duration, delay, repeat, direction, fill and easing."
sidebar:
  order: 1
---

`widget.animate(...)` gives a widget its own motion. It takes preset names, `pz.Animation` objects
(or lists of them), [property values](/pyzed/animation/properties/) and options:

```python
pz.text("Saved").animate("fade_in_up")                          # plays when it appears
card.animate("lift", on="hover")                                # forward on hover, back on leave
icon.animate("pulse", repeat="infinite")                        # loops
field.animate("shake", key=self.errors)                         # replays when key changes
field.animate("shake", on=self.wrong)                           # plays on self.wrong.fire()
button.animate(on="press", scale=0.96, duration=90)             # your own values
```

:::tip[New to animations?]
[Start here: apply and play](/pyzed/animation/start/) explains in one page where `.animate()` goes and
every way to start an animation, with examples in each code style.
:::

`animate()` returns the widget, so you can chain it after `style()` or call it several times. Each
call adds an animation that keeps its own trigger:

```python
ui.button("Buy", self.buy).animate("fade_in_up").animate("lift", on="hover").animate("shrink", on="press")
```

## Triggers

The `on` option says **what plays the animation**:

![Six cards, one per trigger: mount plays as it appears, hover lifts under the pointer, press shrinks while pressed, focus lights the border, click plays tada and active starts a glow](/pyzed/media/animation/triggers.webp)

| `on` | Plays | Typical use |
| --- | --- | --- |
| `"mount"` (default) | Once, when the widget appears on screen. | Entrances: a page, a toast, a list item. |
| `"hover"` | Forward while the pointer is over the widget, back when it leaves. | Cards and buttons that react. |
| `"press"` | Forward while the mouse button is down on it, back on release. | A button that sinks in. |
| `"focus"` | Forward while it has the keyboard focus, back when it loses it. | Inputs that light up. |
| `"click"` | From the start on every click. | A "liked" pop, a celebration. |
| `"active"` | Forward while `active=True`, back when it becomes `False`. | A recording light, a selected state. |
| `"manual"` | From the start each time `key` changes, never on its own. | A pulse when a counter goes up. |
| a `pz.Trigger` | From the start each time your code calls `fire()`. | A shake on a wrong password, a "saved" check. |

```python
ui.button("Record", self.toggle).animate("glow_pulse", active=self.recording)
```

:::tip[Hover, press and focus go back smoothly]
These triggers don't jump back: if the pointer leaves halfway, the animation reverses from where it
got to. That's why they suit short "interaction" presets such as `lift`, `grow` and `shrink`.
:::

### Playing from your code with `pz.Trigger`

A `pz.Trigger` starts an animation from a handler. Create it once (in `__init__`, or in a component's
`setup()`), give it to `on=` and call `fire()` whenever the animation should play:

```python
class Login(pz.App):
    def __init__(self):
        self.wrong = pz.Trigger()

    def view(self):
        return ui.input(self.password, self.set_password).animate("shake", on=self.wrong)

    def submit(self):
        if not self.check():
            self.wrong.fire()      # shakes now; again from the start if it was still shaking
```

The widget doesn't move when it appears, only on `fire()`. `trigger.count` says how many times it was
fired, and `fire` ignores its arguments, so `ui.button("Again", self.wrong.fire)` works.

### Replaying with `key`

A mount animation plays once. Give it a `key` and it plays again **every time the key changes**:

```python
password.animate("shake", key=self.failed_attempts)      # shakes on each wrong password
ui.button("Copy", self.copy).animate("pulse", key=self.copies)
```

As a mount animation it also plays when the widget first appears. With `on="manual"` it **only** plays
when the key changes (this is what `pz.Trigger` does underneath):

```python
ui.badge(str(self.unread)).animate("pulse", on="manual", key=self.unread)
```

## Timing options

These options override the timing that an animation (or a preset) brings:

![Six balls on six lanes, each with one option: duration, delay, repeat, alternate, reverse and fill none](/pyzed/media/animation/options.webp)

| Option | Values | What it does |
| --- | --- | --- |
| `duration` | Milliseconds, or `"0.3s"` / `"300ms"`. | How long one run takes. |
| `delay` | The same units. | How long to wait before starting. |
| `easing` | A curve name, a Bézier `(x1, y1, x2, y2)` or `"steps(4)"`. | The shape of the motion: see [easing](/pyzed/animation/keyframes/#easing). |
| `repeat` | A number of times, or `"infinite"`. | How many runs in a row. |
| `direction` | `"normal"`, `"reverse"`, `"alternate"`, `"alternate_reverse"`. | `reverse` plays backwards; `alternate` goes there and back on every other run. |
| `fill` | `"both"` (default), `"forwards"`, `"backwards"`, `"none"`. | What shows before the delay and after the end, as in CSS. With `"none"` the widget goes back to its own look when the animation ends. |
| `key` | Any value. | Replays a mount or manual animation when it changes. |
| `active` | `True` or `False`. | Drives an `"active"` animation. |
| `on_start`, `on_end` | A callable or a message. | Sent when the animation starts and when it ends. |

```python
badge.animate("pulse", repeat=3, delay=400)
arrow.animate(pz.Animation({0: {"x": 0}, 1: {"x": 6}}, duration=600), direction="alternate", repeat="infinite")
toast.animate("fade_in_up", on_end=self.toast_shown)
```

## Ready-made or your own

- A **preset name** is the quickest: see the [preset gallery](/pyzed/animation/presets/).
- **Property values** describe a simple animation in place: `animate(opacity=0, y=12)` appears from
  below. See [Animatable properties](/pyzed/animation/properties/).
- A **`pz.Animation`** gives you keyframes, per-frame easing and a name you can reuse anywhere. See
  [Keyframes and easing](/pyzed/animation/keyframes/).
- A **timeline target** from an animation player (`self.player["card"]`) lets one clip move many
  widgets. See [Timeline animations](/pyzed/animation/timeline/).

:::note[Animations restart when a widget comes back]
If a widget leaves the view and comes back (an `if` in `view()`, a new list item), its mount
animation plays again. Use a stable `key`, or [`pz.presence`](/pyzed/animation/transitions/#presence-and-stagger),
to decide when it replays.
:::
