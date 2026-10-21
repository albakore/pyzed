---
title: Animation
description: "How animation works in Pyzed: animate any widget like the web (presets, keyframes, transitions), move many widgets on one timeline like Godot's AnimationPlayer, and edit clips in Pyzed Design."
sidebar:
  order: 0
  label: Overview
---

Every Pyzed widget can move, fade, grow, turn, blur, glow or change color. This section explains
each part of the animation system, with a moving example for each one.

![A dashboard coming in: the header drops in, the cards rise one after another, a badge pulses and a spinner turns](/pyzed/media/animation/overview.webp)

```python
pz.text("Welcome back").animate("fade_in_down")                  # plays when it appears
pz.row(pz.stagger(cards, "fade_in_up", step=80))                 # one after another
badge.animate("pulse", repeat="infinite")                        # goes on
ui.button("Recording", self.stop).animate("glow_pulse")          # a looping glow
pz.icon("loader-circle").animate("spin")                         # a spinner
```

:::tip[Start here]
New to animations? [Start here: apply and play](/pyzed/animation/start/) shows where `.animate()` goes,
every way to start an animation (when a widget appears, on the pointer, from your code with
`pz.Trigger`, from a timeline) and how the same works in Pyzed Design.
:::

## Three ways to animate

Pick the one that fits what you want to do. They work together, so one app often uses all three.

| You want to... | Use | Page |
| --- | --- | --- |
| Give one widget its own motion: appear, react to the pointer, draw attention, loop. | `widget.animate(...)` | [animate() and triggers](/pyzed/animation/animate/) |
| Move a widget smoothly whenever one of its values changes (open a panel, select a row). | `widget.transition(...)` and style states | [Transitions and states](/pyzed/animation/transitions/) |
| Play a scene where many widgets and your app's values change together, with play, pause and seek. | `pz.AnimationPlayer` and `pz.Clip` | [Timeline animations](/pyzed/animation/timeline/) |

And in [Pyzed Design](/pyzed/editor/animations-and-effects/) you can do the same without code: an
**Animation** section for each control and an **Animation** panel with a timeline for clips.

## How it runs

Python describes an animation once, in `view()`. The Rust side plays it at the display's frame rate,
so **a running animation never calls your code** and doesn't slow your app down. When something
changes (a click, new data), `view()` runs again as usual; animations that didn't change keep going
where they were.

- **Presets** are ready-made animations with a name (`"fade_in_up"`, `"lift"`, `"spin"`). See the
  [preset gallery](/pyzed/animation/presets/).
- **Keyframes** describe your own animation step by step, like CSS `@keyframes`. See
  [Keyframes and easing](/pyzed/animation/keyframes/).
- **Properties** are what an animation can change: position, size, rotation, colors, blur, glow...
  See [Animatable properties](/pyzed/animation/properties/).
- **Effects** such as glass, bloom and glow are style properties that animations can change too.
  See [Effects](/pyzed/animation/effects/).

:::tip[Try them]
Run [`examples/animations.py`](https://github.com/albakore/pyzed/blob/main/examples/animations.py)
for the widget animations and [`examples/timeline.py`](https://github.com/albakore/pyzed/blob/main/examples/timeline.py)
for a timeline. Both are short and commented.
:::

## In this section

| Page | What it explains |
| --- | --- |
| [Start here: apply and play](/pyzed/animation/start/) | Where `.animate()` goes, what starts an animation, how they are named and customized, in each code style and in the editor. |
| [animate() and triggers](/pyzed/animation/animate/) | What plays an animation (appearing, hover, press, focus, click, a flag, a `pz.Trigger`) and its timing options. |
| [Animatable properties](/pyzed/animation/properties/) | Every property an animation can change, and how values work. |
| [Keyframes and easing](/pyzed/animation/keyframes/) | Your own animations with `pz.Animation`, and the curves that shape the motion. |
| [Transitions and states](/pyzed/animation/transitions/) | `transition()`, hover and pressed styles, page changes with `presence`, lists with `stagger`, and window transitions. |
| [Preset gallery](/pyzed/animation/presets/) | All the named animations, playing. |
| [Effects](/pyzed/animation/effects/) | Glass, glow, bloom, blur, rotation and opacity. |
| [Timeline animations](/pyzed/animation/timeline/) | Clips, tracks, keys, loops and method calls on one timeline. |
| [The animation player](/pyzed/animation/player/) | Playing, pausing, seeking and queueing clips, and saving them in `.pzanim` files. |
| [Reduced motion, tests and limits](/pyzed/animation/motion-and-tests/) | Respecting "reduce motion", testing animated views, and what the system can't do. |
