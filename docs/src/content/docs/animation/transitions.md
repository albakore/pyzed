---
title: Transitions and states
description: "Animate changes in Pyzed like CSS: widget.transition() moves to new values, hover and pressed style states animate, pz.presence swaps pages with enter and exit animations, pz.stagger cascades lists, and windows open with transitions."
sidebar:
  order: 4
---

An animation plays on its own. A **transition** plays when something changes: a panel opens, a row
gets selected, the page changes. You only set the new value; Pyzed animates the way there.

## transition()

`widget.transition(**props)` sets property values and **animates every change** to them, like a
CSS `transition`. Change the values in `view()` and the widget moves to them:

![A sidebar narrows to icons and widens again when the Menu button is clicked, the cards beside it reflow, and the selected row's color slides to another row](/pyzed/media/animation/transition.webp)

```python
def view(self):
    sidebar = pz.column(items).transition(width=220 if self.open else 64, duration=220,
                                          easing="ease_out_cubic")
    label.transition(opacity=1 if self.open else 0)
    row.transition(background="accent" if selected else "panel", duration=260)
```

- `duration` (default 200 ms), `delay` and `easing` (default `"ease_out"`) apply to every
  property.
- A property can have its own timing: `transition(scale={"value": 1.1, "duration": 90, "easing": "spring"})`.
- The first time the widget appears it shows the values at once; only later changes animate.

:::tip[transition() or animate()?]
Use `transition()` for a value that follows your app's state (open or closed, selected or not).
Use `animate()` for motion that plays by itself (an entrance, a hover effect, a loop).
:::

## Style states, like CSS

A [style](/pyzed/theming/styles/) can say how a widget looks while the pointer is over it (`hover`),
while it's pressed (`pressed`) and while it has the keyboard focus (`focus`). Add `transition` and
the change animates, like CSS `:hover` with `transition`:

![Three widgets reacting to the pointer: a button changes color and rises, an outline button turns red, a card grows a little with a colored border](/pyzed/media/animation/states.webp)

```python
ui.button("Save", self.save).style(
    background="accent", radius=6,
    hover={"background": "#4f8cff", "translate": (0, -1)},
    pressed={"scale": 0.97},
    transition=120,                      # milliseconds, "0.2s", True or {"duration", "easing", "delay"}
)
```

A state can change `background`, `color`, `border_color`, `border_width`, `radius`, `opacity`,
`translate`, `scale`, `rotate` and `blur`. None of these move the widgets around, so hovering never
shifts the layout. See [Styles](/pyzed/theming/styles/#states-and-transitions) for stylesheets and
named styles.

## Presence and stagger

`pz.presence(content, key)` animates content **in and out** when `key` changes. The old content
stays on screen while it leaves, so pages, tabs and wizard steps can cross over:

![Three tabs: clicking one slides the old page out to the left while the new one comes in from the right, and its rows cascade in](/pyzed/media/animation/presence.webp)

```python
pz.presence(self.page_view(), key=self.page, enter="fade_in_right", exit="fade_out_left")
```

`enter` and `exit` take presets or `pz.Animation` objects. Give it an `id` when one line of code
makes several presences (it defaults to the caller's file and line).

`pz.stagger(items, animation, step=40)` gives each item the same animation, each one starting
`step` milliseconds after the previous, so a list cascades in:

```python
pz.column(pz.stagger([row(item) for item in self.items], "fade_in_up", step=30))
```

## Window transitions

A window animates when it opens and closes. Set `transition` (a name from
`pz.animation.WINDOW_TRANSITIONS`, a preset or a `pz.Animation`) and, optionally, `exit_transition`:

![Three windows opening with zoom, pop and slide up, then closing](/pyzed/media/animation/windows.webp)

```python
class Settings(pz.Window):
    transition = "zoom"            # fade, zoom, pop, slide_up, slide_down, slide_left, slide_right
    exit_transition = "fade_out"
```

The window stays open until its exit animation ends. The app's main window takes the same
attributes. See [Windows](/pyzed/guides/windows/).
