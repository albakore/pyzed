---
title: Keyframes and easing
description: "Write your own Pyzed animations with pz.Animation keyframes (like CSS @keyframes), give each step its own easing, name and save them, and pick easing curves: ease, cubic, back, bounce, spring, Bézier and steps."
sidebar:
  order: 3
---

When no preset does what you want, describe the animation yourself with `pz.Animation`. It works
like a CSS `@keyframes` rule with its timing.

## Keyframes

A **keyframe** says what the widget looks like at one moment of the animation. Pyzed fills in the
moments between keyframes.

![A heart beating and a card wiggling, each with a bar of its keyframes and a playhead going through them](/pyzed/media/animation/keyframes.webp)

```python
beat = pz.Animation({0: {"scale": 1}, "30%": {"scale": 1.25, "easing": "ease_out"}, "45%": {"scale": 1},
                     "60%": {"scale": 1.15}, 1: {"scale": 1}}, duration=1000, repeat="infinite")
heart.animate(beat)

wiggle = pz.Animation([{"x": 0}, {"x": -10}, {"x": 10}, {"x": -6}, {"x": 0}], duration=1000)
card.animate(wiggle, key=self.errors)
```

Frames can be written two ways:

- **A list:** the frames are spread evenly, from the start to the end.
- **A dict:** the key is where the frame sits, from `0` (start) to `1` (end). It can also be
  `"50%"`, `"from"` or `"to"`.

Each frame is a dict of [properties](/pyzed/animation/properties/). A frame can also set its own
`"easing"`: the curve **from that frame to the next one**.

`pz.Animation` takes the same timing as `animate()`: `duration`, `delay`, `easing`, `repeat`,
`direction`, `fill` and `on`. Options given to `animate()` override them.

:::note[Missing values come from the widget]
A property that is missing at the start or at the end goes from or to the widget's own value, so
`{"50%": {"background": "#fbbf24"}}` flashes any widget to yellow and back.
:::

## Naming and saving animations

`pz.define_animation(name, animation)` gives an animation a name, so `animate(name)` works
anywhere in your app, like a preset:

```python
pz.define_animation("wiggle", wiggle)
ui.button("Retry", self.retry).animate("wiggle", key=self.failures)
```

`Animation.to_dict()` and `Animation.from_dict()` turn an animation into JSON-friendly data and
back, to save it in a file or a setting. To save **many** animations that move several widgets
together, use a [timeline clip and a `.pzanim` file](/pyzed/animation/player/#libraries-and-pzanim-files).

## Easing

**Easing** is the shape of the motion: whether it starts slowly, ends softly, overshoots or
bounces. The same move with each curve:

![Nine balls moving the same distance, each with a different easing curve drawn next to it: linear, ease, ease in, ease out cubic, ease in out, ease out back, ease out bounce, spring and steps](/pyzed/media/animation/easing.webp)

| Curve | Feels like | Good for |
| --- | --- | --- |
| `"linear"` | A constant speed. | Spinners, progress, color cycles. |
| `"ease"` | A soft start and a soft end (the CSS default). | Most things. |
| `"ease_in"` | Starts slowly, ends fast. | Things leaving the screen. |
| `"ease_out"`, `"ease_out_cubic"` | Starts fast, ends softly. | Things arriving: menus, toasts, pages. |
| `"ease_in_out"` | Slow, fast, slow. | Moving between two places on screen. |
| `"ease_out_back"` | Goes a little past the end and settles. | Pops, buttons, playful entrances. |
| `"ease_out_bounce"` | Bounces at the end. | Drops, games. |
| `"spring"` | Overshoots and wobbles like a spring. | Toggles, cards that snap into place. |
| `"steps(5)"` | Jumps in 5 steps, no motion between. | Sprite frames, ticking clocks, typing. |

`pz.animation.EASINGS` lists every name: `linear`, `ease`, `ease_in`, `ease_out`, `ease_in_out`,
the `sine`, `quad`, `cubic`, `quart`, `expo`, `circ` and `back` families (each `ease_in_*`,
`ease_out_*` and `ease_in_out_*`), `ease_in_elastic`, `ease_out_elastic`, `ease_in_bounce`,
`ease_out_bounce` and `spring`.

You can also give:

- **A cubic Bézier** `(x1, y1, x2, y2)`, like CSS `cubic-bezier()`: `easing=(0.2, 0.8, 0.2, 1)`.
- **Steps** `"steps(n)"`: `n` jumps instead of a smooth motion.

`pz.animation.ease(easing, t)` evaluates any curve at `t` (from 0 to 1). Use it to animate your own
[canvas](/pyzed/guides/canvas/) drawings with the same curves:

```python
from pyzed import animation

y = 300 - animation.ease("ease_out_bounce", self.t) * 240   # a ball dropping on a canvas
```
