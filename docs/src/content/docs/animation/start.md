---
title: "Start here: apply and play"
description: "The two things every Pyzed animation needs: which widget it moves (animate() on the widget) and what starts it (a trigger, your code, a timeline). Declarative and imperative examples, in classes, components and plain functions, and the same in Pyzed Design."
sidebar:
  order: 0.5
  label: "Start here: apply and play"
---

Every animation answers two questions:

1. **Which widget moves?** You attach the animation to that widget with `.animate(...)`.
2. **When does it play?** A **trigger** decides: the widget appearing, the pointer, a click, a flag in
   your state, or a line of your code.

This page explains both, with the same example written in the different styles Pyzed supports. The
other pages of this section go deeper into each part.

![A login card: the card rises in when it appears, the button lifts under the pointer, a wrong password makes the field shake and a correct one makes a check pop in](/pyzed/media/animation/start.webp)

## 1. Apply it: `.animate()` on the widget

An animation lives **on the widget it moves**. Call `.animate()` where you build the widget in
`view()`, and use the widget it returns:

```python
def view(self):
    return pz.column([
        pz.text("Welcome back").animate("fade_in_down"),        # this text moves
        ui.button("Sign in", self.sign_in).animate("lift", on="hover"),
    ])
```

`.animate()` works on **every** widget: text, buttons, inputs, containers, rows, icons, images and
your own components (which also take `animate="fade_in"` as an argument). On a container, everything
inside moves with it.

:::caution[Use what `.animate()` returns]
Widgets don't change in place: `.animate()` returns a new widget with the animation. Writing
`title.animate("fade_in")` on its own line does nothing if you then return the old `title`.

```python
title = pz.text("Hello")
title.animate("fade_in")          # ✗ the result is thrown away
title = title.animate("fade_in")  # ✓ keep it (or chain it where you build the widget)
```
:::

You can call `.animate()` several times: each call adds one animation with its own trigger.

```python
ui.button("Buy", self.buy).animate("fade_in_up").animate("lift", on="hover").animate("shrink", on="press")
```

## 2. Start it: the trigger

The `on=` option says what plays the animation. You choose one per `.animate()` call:

| You want it to play... | Write | Plays |
| --- | --- | --- |
| when the widget appears | `.animate("fade_in")` (`on="mount"` is the default) | once, each time the widget shows up |
| while the pointer is over it | `.animate("lift", on="hover")` | forward on enter, back on leave |
| while it is pressed | `.animate("shrink", on="press")` | forward while the button is down |
| while it has the focus | `.animate("glow", on="focus")` | forward while focused |
| on every click on it | `.animate("tada", on="click")` | from the start, each click |
| while a value in your state is true | `.animate("glow_pulse", active=self.recording)` | forward while `True`, back when `False` |
| **when your code says so** | `.animate("shake", on=self.wrong)` + `self.wrong.fire()` | from the start, each `fire()` |
| when a value in your state changes | `.animate("pulse", on="manual", key=self.count)` | from the start, each new `key` |

The first five need nothing else: Pyzed watches the pointer and the keyboard for you. The last three
are how **your code** starts an animation.

### From your code: `pz.Trigger`

A `pz.Trigger` is like a button your code presses. Keep one on the app, give it to `on=` and call
`fire()` in any handler:

```python
class Login(pz.App):
    def __init__(self):
        self.password = ""
        self.wrong = pz.Trigger()        # 1. create it once

    def view(self):
        return pz.column([
            ui.input(self.password, self.set_password, secure=True)
                .animate("shake", on=self.wrong),    # 2. attach: nothing plays yet
            ui.button("Sign in", self.sign_in),
        ], spacing=12)

    def set_password(self, text):
        self.password = text

    def sign_in(self):
        if self.password != "secret":
            self.wrong.fire()            # 3. play it now (again from the start if it was running)
```

Nothing plays when the widget appears: only `fire()` starts it. `fire` ignores its arguments, so it
can be a callback itself: `ui.button("Shake it", self.wrong.fire)`.

`on="manual"` with a `key` does the same without an object: the animation plays each time the key
changes, and never on its own. It is handy with a counter you already have:

```python
ui.badge(str(self.unread)).animate("pulse", on="manual", key=self.unread)   # pulses on each new message
```

:::note[`key` with or without `on="manual"`]
A plain `key` (`.animate("shake", key=self.errors)`) also replays when the key changes, but as a
**mount** animation it plays once when the widget appears too. Add `on="manual"` (or use a
`pz.Trigger`) when it should only play on a change.
:::

### Stopping a loop

A looping animation (`repeat="infinite"`, or a loop preset such as `spin`) runs while the widget has
it. To stop it, stop asking for it in `view()`:

```python
icon = pz.icon("loader-circle")
if self.loading:
    icon = icon.animate("spin")
```

Or use `active=`, which also plays it back out smoothly: `.animate("glow_pulse", active=self.loading)`.

## 3. Name it: what you can pass to `.animate()`

The first argument says **which** animation plays. It can be:

| You pass | Example | Where it comes from |
| --- | --- | --- |
| A preset name | `"fade_in_up"`, `"lift"`, `"spin"` | The [preset gallery](/pyzed/animation/presets/): more than 50 ready-made animations, in five groups (entrance, exit, attention, interaction, loop). |
| A name you defined | `"wiggle"` | `pz.animation.define_animation("wiggle", ...)`, once, anywhere before `view()` runs. |
| A `pz.Animation` | `pz.Animation([{"x": 0}, {"x": 8}])` | Your own keyframes, used in place. See [Keyframes and easing](/pyzed/animation/keyframes/). |
| Property values | `.animate(opacity=0, y=12)` | A quick animation from (or to) these values. See [Animatable properties](/pyzed/animation/properties/). |
| A timeline target | `self.player["card"]` | One part of a clip that moves many widgets. See [Timeline animations](/pyzed/animation/timeline/). |

Preset names are lowercase words joined by `_`, and they read like what they do: `fade_in_left`,
`slide_out_down`, `rubber_band`. To list them from Python:

```python
from pyzed import animation
print(list(animation.presets()))              # every name
print(list(animation.presets("entrance")))    # one group
print(animation.animation("pop_in").description, animation.animation("pop_in").duration)
```

## 4. Customize it

Every preset brings its own timing; the options of `.animate()` change it just for that widget:

```python
card.animate("fade_in_up", duration=600, delay=200, easing="ease_out_back")
badge.animate("pulse", repeat=3)
arrow.animate("nudge_right", on="hover", duration=120)
```

When the change should apply **everywhere**, define your own animation once and use its name:

```python
from pyzed.animation import define_animation

define_animation("slow_rise", [{"opacity": 0, "y": 40}, {"opacity": 1, "y": 0}],
                 duration=900, easing="ease_out_cubic")
define_animation("fade_in_up", pz.animation.animation("fade_in_up").with_options(duration=500))  # your own default

pz.text("Hello").animate("slow_rise")
```

The full list of options (`duration`, `delay`, `easing`, `repeat`, `direction`, `fill`, `on_start`,
`on_end`...) is in [animate() and triggers](/pyzed/animation/animate/#timing-options), and keyframes,
easing curves and per-frame easing are in [Keyframes and easing](/pyzed/animation/keyframes/).

## The same animation in different styles

Pyzed lets you organize your code in several ways. Animations work the same in all of them, because
they always end up on a widget returned by a view.

### Declarative: the view follows your state

You keep values in your state and `view()` decides which animations the widgets have. You never
"start" anything: you change the state and the screen follows. This is the style to reach for first.

```python
class Player(pz.App):
    def __init__(self):
        self.playing = False
        self.liked = 0

    def view(self):
        return pz.row([
            ui.icon_button("pause" if self.playing else "play", self.toggle)
                .animate("glow_pulse", active=self.playing),              # glows while playing
            ui.icon_button("heart", self.like)
                .animate("heartbeat", on="manual", key=self.liked),       # beats on every like
            pz.text(f"{self.liked} likes").transition(opacity=1 if self.liked else 0.4),
        ], spacing=8, align="center")

    def toggle(self):
        self.playing = not self.playing

    def like(self):
        self.liked += 1
```

### Imperative: your code starts it

You keep "play" handles and call them from handlers, like `button.play()` in other toolkits. In Pyzed
these handles are `pz.Trigger` (one widget animation) and `pz.AnimationPlayer` (a whole clip):

```python
class Checkout(pz.App):
    def __init__(self):
        self.error = pz.Trigger()
        self.done = pz.Trigger()
        self.player = pz.AnimationPlayer("checkout.pzanim")     # clips saved from Pyzed Design or code

    def view(self):
        return pz.column([
            ui.input(self.card, self.set_card).animate("shake", on=self.error),
            pz.icon("circle-check", size=32).animate("pop_in", on=self.done),
            pz.text("Thanks!").animate(self.player["thanks"]),
            ui.button("Pay", self.pay),
        ])

    def pay(self):
        if not self.valid():
            self.error.fire()
            return
        self.done.fire()
        self.player.play("celebrate")
```

### In a component

A `pz.Component` keeps its own state, so its triggers live with it (create them in `setup()`):

```python
class CopyButton(pz.Component):
    text: str = ""

    def setup(self):
        self.copied = pz.Trigger()

    def copy(self):
        self.copied.fire()
        return pz.Command.copy(self.text)

    def render(self):
        return pz.row([
            ui.button("Copy", self.copy, icon="copy"),
            pz.text("Copied!").animate("fade_in_up", on=self.copied),
        ], spacing=8, align="center")
```

Every component also takes `animate=` when you place it: `CopyButton(text=link, animate="fade_in")`.

### With plain functions

Pieces of a view can be plain functions that receive values and return widgets. Pass them the state
(and the triggers) they need: the animation goes on the widget they return.

```python
def status_dot(online: bool) -> pz.Widget:
    dot = pz.container(width=10, height=10).style(background="success" if online else "text_muted", radius=5)
    return dot.animate("breathe", active=online)


def notification(text: str, index: int) -> pz.Widget:
    return ui.callout("New", text).animate("fade_in_left", delay=index * 60)


class Inbox(pz.App):
    def view(self):
        return pz.column([
            pz.row([status_dot(self.online), pz.text("Inbox")], spacing=6, align="center"),
            *[notification(text, i) for i, text in enumerate(self.messages)],
        ], spacing=8)
```

## In Pyzed Design

The editor builds the same animations without code, and shows the line to call when code should
start them.

### One control: the Animation section

Select a control and open **Properties → Animation**. **Add animation** adds a row; click it to choose
**When** it plays and **which** animation (the presets above):

| When (in the editor) | Same as in code |
| --- | --- |
| When it appears | `on="mount"` |
| While hovered / pressed / focused | `on="hover"` / `"press"` / `"focus"` |
| On click | `on="click"` |
| **When played from code** | `on=pz.Trigger()` |

A row set to **When played from code** waits for your handlers. The row shows the exact line, with a
copy button:

```python
def sign_in_click(form, event):
    if not check(form.password.text):
        form.password.play_animation()               # plays its "When played from code" animations
```

`play_animation()` also takes any preset, `pz.Animation` or values, even for a control without rows,
and `stop_animation()` stops what it started (a loop, for example):

```python
form.badge.play_animation("pulse", repeat=3)
form.card.play_animation(scale=1.05, duration=200)   # to these values and back
form.spinner.play_animation("spin")
form.spinner.stop_animation()
```

### Many controls at once: clips

The **Animation** panel (**View → Animation**) edits **clips**: timelines that move several controls
together. A clip starts in one of two ways, and the panel says which one applies:

- turn on **⚡ Play when the form opens** (autoplay), or
- call it from a handler: `form.animations.play("intro")` (the panel shows this line with a copy button).

See [Animations and effects in Pyzed Design](/pyzed/editor/animations-and-effects/) for every field of
the editor, and [The animation player](/pyzed/animation/player/) for `play`, `pause`, `seek` and
friends.

## Cheat sheet

| I want to... | Library | Pyzed Design |
| --- | --- | --- |
| Animate a widget when it appears | `w.animate("fade_in_up")` | Animation → When it appears |
| React to the pointer | `w.animate("lift", on="hover")` | Animation → While hovered |
| Play on a click on it | `w.animate("tada", on="click")` | Animation → On click |
| Play from a handler | `on=self.t` + `self.t.fire()` | When played from code + `form.x.play_animation()` |
| Play while a flag is on | `w.animate("glow_pulse", active=flag)` | A loop set to When played from code + `play_animation()` / `stop_animation()` |
| Change a value smoothly | `w.transition(opacity=...)` | Style states (hover, pressed) |
| Move many widgets together | `pz.AnimationPlayer` + `player["target"]` | Animation panel (clips) |
| Start a clip | `player.play("intro")` | ⚡ autoplay or `form.animations.play("intro")` |
| Make my own animation | `pz.Animation([...])`, `define_animation` | A clip with tracks and keys |
