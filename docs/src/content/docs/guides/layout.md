---
title: Layout and styling
description: Rows, columns, containers, sizes, padding, alignment and colors.
sidebar:
  order: 2
---

## Rows and columns

![Base widgets: buttons, inputs, sliders, progress and text](../../../assets/components/widgets.png)

```python
pz.column([a, b, c], spacing=8, padding=16)            # vertical
pz.row([a, b, c], spacing=8, align="center")          # horizontal
```

- `children` accepts nested lists and skips `None` and `False`, so you can write
  `self.error and ui.label(self.error, color="error")`.
- A string or a number as a child becomes a `pz.text`.
- `align` aligns children on the cross axis: `"start"`, `"center"`, `"end"`.

## Sizes

`width` and `height` accept:

| Value | Meaning |
| --- | --- |
| `240` | Fixed pixels. |
| `"shrink"` | Just enough for the content. |
| `"fill"` | All available space. |
| `"fill:2"` | A share of the space: two `"fill:1"` and one `"fill:2"` split 25/25/50. |

```python
pz.row([
    pz.container(sidebar, width=240),
    pz.container(content, width="fill"),
])
```

Push items to the edges with a flexible gap:

```python
pz.row([ui.label("Title"), pz.hspace(), ui.button("Close", self.close)])
```

:::caution[Filling children]
A child with `"fill"` (for example, a horizontal `pz.rule()`) makes its column fill too. If you
want the column to shrink, set `width="shrink"` on the column.
:::

## Padding

`padding` accepts `8` (all sides), `(vertical, horizontal)` or `(top, right, bottom, left)`.

## Containers

`pz.container` wraps a child to give it size, alignment and style:

```python
pz.container(
    content,
    padding=(12, 16),
    width="fill",
    max_width=720,
    align_x="center",
    bg="#2f343e",
    border_color="#464b57",
    border_width=1,
    radius=8,
    shadow=("#00000066", (0, 4), 16),   # (color, (dx, dy), blur)
    clip=True,
)
```

`pz.center(content)` centers it in all the available space. `pz.container(None, width=8, height=8, bg=...)`
is a colored rectangle.

## Colors

Colors accept `"#rgb"`, `"#rrggbb"`, `"#rrggbbaa"`, tuples `(r, g, b)` / `(r, g, b, a)` or
`"transparent"`. In `pyzed.ui` components you can also use a theme token (`"accent"`,
`"text_muted"`…). For derived colors:

```python
from pyzed.theme import alpha, mix

alpha(self.resolved_theme().accent, 0.2)            # 20% opacity
mix(self.resolved_theme().editor, "#ffffff", 0.05)  # 5% lighter
```

## Text

```python
pz.text("Hello", size=16, weight="semibold", color="#dce0e5")
pz.text("code", font="mono")
pz.text("a very long line…", wrap=False)
```

Bundled fonts: IBM Plex Sans (`"sans"`, the default), IBM Plex Mono (`"mono"`) and Lucide
(`"icons"`). See [icons and fonts](/pyzed/guides/icons-fonts/).

## Overlays and scrolling

- `pz.stack([below, above])` layers widgets; `pz.opaque(w)` stops clicks from passing through.
- `pz.scrollable(content, direction="vertical" | "horizontal" | "both")` adds scrolling.
  With `anchor_bottom=True` it stays pinned to the end.
- `pz.hover(base, overlay)` shows `overlay` only on mouse hover.
- `pz.mouse_area(w, on_right_press=..., on_double_click=..., cursor="pointer")` detects mouse
  events.
