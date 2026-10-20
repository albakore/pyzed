---
title: Preset gallery
description: "Every named animation preset in Pyzed, playing: entrances, exits, attention seekers, hover and press feedback, and loops, with their durations and when to use them."
sidebar:
  order: 5
---

A **preset** is a ready-made animation with a name. Pass the name to `animate()`:

```python
dialog.animate("pop_in")
card.animate("lift", on="hover")
pz.icon("loader-circle").animate("spin")
```

Options change a preset's timing without changing the preset: `animate("fade_in_up", duration=600, delay=200)`.
`pz.animation.presets(category)` lists them in code, each with its `description`, and
`pz.define_animation` adds [your own](/pyzed/animation/keyframes/#naming-and-saving-animations).

## Entrance

Play once when the widget appears (`on="mount"`). Use them for pages, dialogs, toasts and list items.

![Fifteen cards appearing, each with an entrance preset](/pyzed/media/animation/presets-entrance.webp)

| Preset | What it does | Duration |
| --- | --- | --- |
| `fade_in` | Fades in. | 280 ms |
| `fade_in_up` | Fades in while rising. | 280 ms |
| `fade_in_down` | Fades in while dropping. | 280 ms |
| `fade_in_left` | Fades in from the left. | 280 ms |
| `fade_in_right` | Fades in from the right. | 280 ms |
| `slide_in_up` | Slides in from below its own height. | 280 ms |
| `slide_in_down` | Slides in from above. | 280 ms |
| `slide_in_left` | Slides in from the left. | 280 ms |
| `slide_in_right` | Slides in from the right. | 280 ms |
| `zoom_in` | Grows in from slightly smaller. | 280 ms |
| `pop_in` | Pops in with a small overshoot. | 320 ms |
| `bounce_in` | Bounces in from small. | 600 ms |
| `drop_in` | Falls into place with a bounce. | 520 ms |
| `blur_in` | Comes into focus, like a lens. | 360 ms |
| `rotate_in` | Turns in from a quarter turn. | 420 ms |

## Exit

The reverse: the widget leaves. Use them as `exit=` of [`pz.presence`](/pyzed/animation/transitions/#presence-and-stagger), as a window's `exit_transition`, or before you remove something.

![Thirteen cards leaving, each with an exit preset](/pyzed/media/animation/presets-exit.webp)

| Preset | What it does | Duration |
| --- | --- | --- |
| `fade_out` | Fades out. | 220 ms |
| `fade_out_up` | Fades out while rising. | 220 ms |
| `fade_out_down` | Fades out while dropping. | 220 ms |
| `fade_out_left` | Fades out to the left. | 220 ms |
| `fade_out_right` | Fades out to the right. | 220 ms |
| `slide_out_up` | Slides out upwards. | 220 ms |
| `slide_out_down` | Slides out downwards. | 220 ms |
| `slide_out_left` | Slides out to the left. | 220 ms |
| `slide_out_right` | Slides out to the right. | 220 ms |
| `zoom_out` | Shrinks away. | 220 ms |
| `pop_out` | Swells a little, then pops away. | 260 ms |
| `blur_out` | Goes out of focus. | 260 ms |
| `rotate_out` | Turns away a quarter turn. | 320 ms |

## Attention

A short nudge to look here. Replay them with `key` (`animate("shake", key=self.errors)`) or `on="click"`.

![Ten cards, each playing an attention preset](/pyzed/media/animation/presets-attention.webp)

| Preset | What it does | Duration |
| --- | --- | --- |
| `pulse` | Grows and shrinks once. | 600 ms |
| `heartbeat` | Two quick beats. | 1000 ms |
| `shake` | Shakes sideways (wrong input). | 450 ms |
| `wobble` | Wobbles and settles. | 800 ms |
| `bounce` | Jumps twice. | 900 ms |
| `flash` | Blinks twice. | 800 ms |
| `rubber_band` | Stretches and snaps back. | 800 ms |
| `tada` | A celebratory pop with a wiggle. | 900 ms |
| `swing` | Swings like a hanging sign. | 900 ms |
| `glow_flash` | A burst of glow around the box. | 700 ms |

## Interaction

Feedback for hover, press and focus: they go forward while the pointer is on the widget and back after. Their default trigger is in the table.

![Eight cards going into their hover or press look and back](/pyzed/media/animation/presets-interaction.webp)

| Preset | What it does | Duration | Trigger |
| --- | --- | --- | --- |
| `lift` | Rises with a soft glow (for cards and buttons). | 160 ms | `hover` |
| `grow` | Grows a little. | 160 ms | `hover` |
| `shrink` | Presses in (for press). | 90 ms | `press` |
| `dim` | Fades a little. | 160 ms | `hover` |
| `glow` | Glows around the box. | 200 ms | `hover` |
| `bloom` | A strong, wide glow that blooms out of the box. | 260 ms | `hover` |
| `nudge_right` | Moves a little to the right (links, chevrons). | 140 ms | `hover` |
| `tilt` | Tilts a little (stickers, cards). | 180 ms | `hover` |

## Loop

Motion that goes on forever (`repeat="infinite"`): status lights, spinners, things that float.

![Seven cards with looping presets: float, breathe, blink, glow pulse, throb, drift and spin](/pyzed/media/animation/presets-loop.webp)

| Preset | What it does | Duration |
| --- | --- | --- |
| `float` | Floats up and down. | 2400 ms |
| `breathe` | Slowly fades and shrinks, like breathing. | 3000 ms |
| `blink` | Blinks (status lights, cursors). | 1000 ms |
| `glow_pulse` | The glow swells and fades (recording, live). | 1600 ms |
| `throb` | Pulses forever (notifications). | 1200 ms |
| `drift` | Drifts sideways. | 3000 ms |
| `spin` | Turns forever (spinners, loading icons). | 1000 ms |

