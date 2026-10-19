---
title: Animations and effects
description: "Give controls rotation, blur, glow, bloom, glass and opacity in Pyzed Design, and animate them on appear, hover, press, focus or click."
sidebar:
  order: 5.5
---

Every visual control has two sections in the **Properties** panel, under **Style**: **Effects** and
**Animation**. What you set there is saved in the `.pzform` and plays when the form runs. It is the same
system as [`widget.animate()` and the style effects](/pyzed/guides/animation/) of the library.

![The Effects and Animation sections of a button](../../../../screenshots/editor-motion.png)

## Effects

| Field | What it does |
| --- | --- |
| **Opacity** | How visible the control and everything inside it is (1 is opaque). |
| **Rotation** | Degrees, clockwise, around the center. |
| **Blur** | Blurs the control and everything inside it, in pixels. |
| **Backdrop blur** | Blurs what is behind the box, in pixels. |
| **Glow** | A soft halo around the box. Pick a color (or a theme token such as `accent`); **Glow size** sets how far it spreads. |
| **Bloom** | Light that spills from the bright parts of the control. **Intensity** goes from 0 to 1. |
| **Glass** | A translucent panel that blurs what is behind it, with a light edge. **Tint** colors it and **Strength** sets how much of the tint shows. |

Sub-fields only show while the effect is on. Clear the color (or turn **Glass** off) to remove it.
Effects are style properties (`opacity`, `rotate`, `blur`, `backdrop_blur`, `glow`, `bloom`, `glass`), so they also show in code as
`control.style` and work with **Reset style**. Glass looks best over a colorful background, such as a
panel with a gradient.

## Animation

Each row is one animation: an icon for what plays it, a summary (**Fade in up · 280 ms**, with
**+delay** and **×repeat** when set) and the trigger under it. The **▶** button previews it and the trash
can removes it. Click a row to open its editor:

| Field | Meaning |
| --- | --- |
| **When** | What plays it: **When it appears**, **While hovered**, **While pressed**, **While focused** or **On click**. Hover, press and focus play forward while the condition holds and back when it ends. |
| **Animation** | The preset. The ones that suit the trigger come first (entrances for *appears*, interactions for hover and press, attention seekers for click); the tooltip describes the selected one. |
| **Duration**, **Delay** | Milliseconds. Empty keeps the preset's own timing. |
| **Easing** | How the speed changes along the way (ease, linear, ease out cubic, spring...). |
| **Repeat** | 1, 2, 3, 5 or infinite. |

**Add animation** adds a row (a *Fade in up* when it appears) and opens it. Picking another preset
resets the row's timing to the new preset's. Every change can be undone.

### Previewing

The canvas stays still while you edit, so controls don't move under the mouse. **Preview** (at the
bottom of the section, or **▶** on a row) plays the control's animations once on the canvas, as if it had
just appeared; **Stop** ends the preview. Run the form (**F5**) to see every animation with its real
trigger.

## In code

Animations are saved as plain data on the control:

```json
"animations": [
  {"preset": "fade_in_up"},
  {"preset": "lift", "on": "hover", "duration": 180}
]
```

`Document.set_animations(name, animations)` changes them from a script and `Control.animations` reads
them. To animate a control from its handlers, use the library: `pz.Animation`, `define_animation` and
the [preset list](/pyzed/guides/animation/#presets).
