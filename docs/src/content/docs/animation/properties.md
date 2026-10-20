---
title: Animatable properties
description: "Every property a Pyzed animation can change: opacity, position, scale, rotation, blur, colors, radius, border, glow, size, padding and font size, with their units and how property values animate."
sidebar:
  order: 2
---

An animation changes one or more **properties** of a widget. The same names work everywhere: in
`animate()`, `transition()`, `pz.Animation` keyframes and timeline tracks.

![Twelve cards, each one moving one property back and forth: opacity, x, y, scale, rotate, blur, background, border color, radius, glow, width and font size](/pyzed/media/animation/properties.webp)

| Property | Values | Notes |
| --- | --- | --- |
| `opacity` | `0` (invisible) to `1`. | Fades the widget and everything inside it. |
| `x`, `y` | Pixels, or `"50%"` of the widget's own size. | Moves it without moving its neighbours. |
| `scale` | A number: `1` is its size, `0.5` half, `1.2` a fifth bigger. | Around its center. |
| `rotate` | Degrees clockwise, or `"0.25turn"`, `"1.5rad"`, `"90deg"`. | Around its center. |
| `blur` | Pixels. | Blurs the widget and everything inside it. |
| `background`, `border_color`, `color`, `glow_color` | `"#rrggbb"`, `"#rrggbbaa"` or a theme token (`"accent"`, `"elevated"`...). | Colors blend smoothly. `color` changes the text inside. |
| `radius`, `border_width`, `glow` | Pixels. | `glow` is the size of the halo around the box. |
| `width`, `height` | Pixels. | **Change the layout**: the widgets around it move. |
| `padding` | Pixels. | Inside a container or button (all four sides follow); elsewhere it adds space around. Changes the layout. |
| `font_size` | Pixels. | Every text inside. Changes the layout. |

`pz.animation.PROPERTIES` lists them in code.

:::tip[Prefer x, y, scale and opacity for big views]
`width`, `height`, `padding` and `font_size` lay the view out again on every frame while they move.
That's fine for a sidebar or a title, but for a large page `x`, `y`, `scale` and `opacity` are
cheaper and look the same.
:::

## Property values as an animation

Without a preset, the values you pass **are** the animation. What they mean depends on the trigger:

| Trigger | The widget... |
| --- | --- |
| `mount` | **starts** from those values and settles on its own look: `animate(opacity=0, y=12)` appears from below. |
| `hover`, `press`, `focus`, `active` | **goes to** those values while the condition holds, and back after. |
| `click` | goes to those values and back, on every click. |

```python
pz.text("Hi").animate(opacity=0, y=12, duration=250)            # appears from below
card.animate(on="hover", scale=1.03, background="elevated")      # grows and lightens on hover
button.animate(on="press", scale=0.96, duration=90)              # sinks in while pressed
icon.animate(on="click", rotate=360, duration=500)               # a full turn on each click
```

The default duration is 300 ms for `mount` and `click`, and 150 ms for `hover`, `press` and `focus`.

## Values that come from the widget

A property you don't give at the start or the end of an animation goes **from or to the widget's
own value**. So an animation can change the background of any button without knowing its color:

```python
flash = pz.Animation({"50%": {"background": "#fbbf24"}}, duration=400)   # to yellow and back
```

That's also why a `mount` animation can end on "the widget's own look": the last frame leaves the
property out.

## More examples

```python
icon.animate("spin")                                             # a loading spinner
card.animate(on="hover", rotate=-3, scale=1.02)                  # tilts on hover
sidebar.transition(width=240 if self.open else 56, duration=200) # the content beside it reflows
title.transition(font_size=28 if self.big else 16)
status.animate(on="active", active=self.online, background="#14532d", border_color="#22c55e")
```
