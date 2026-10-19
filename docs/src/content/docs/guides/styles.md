---
title: Styles
description: Style any widget like CSS, reuse styles and set the app's global style.
sidebar:
  order: 3
---

Every widget has a `style()` method that styles it like CSS: background, borders, radius,
shadow, padding, margin, size and typography.

![Styled buttons, a card and a masked gradient](../../../assets/tutorials/styles.png)

```python
ui.button("Save", self.save).style(radius=0, border=(2, "#ef4444"))
pz.text("Title").style(size=20, weight="bold", color="accent")
pz.column([...]).style(background="panel", padding=16, radius=10, shadow=("#00000055", (0, 6), 18))
```

On a button or a container, `style()` changes the widget itself (a square button stays a
button). Other widgets get a box around them that carries the style.

## Properties

| Property | Values |
| --- | --- |
| `background` | A color, a `pz.Gradient` or a `pz.Paint`. |
| `color` | Text color. |
| `font` | `"sans"`, `"mono"`, `"serif"` or a family loaded with `pz.load_font`. |
| `weight` | `"light"`, `"normal"`, `"medium"`, `"semibold"`, `"bold"`… or 100–900. |
| `italic`, `size`, `line_height` | Typography. |
| `border_color`, `border_width` | The border; `border=(width, color)` sets both. |
| `radius` | A number, or `(top_left, top_right, bottom_right, bottom_left)`. |
| `shadow` | `(color, (x, y), blur)`. |
| `padding`, `margin` | A number, `(vertical, horizontal)` or `(top, right, bottom, left)`. |
| `width`, `height` | Pixels, `"fill"`, `"shrink"` or `"fill:N"`; `max_width`, `max_height` in pixels. |
| `align_x`, `align_y` | Where the content sits inside the box. |
| `clip` | Clips the content to the box. |
| `opacity`, `translate`, `scale` | Fades, moves or scales how the widget is drawn, without changing the layout. |
| `glow`, `bloom`, `glass` | Visual effects: a halo, a bright spill of light and a frosted panel. See [Animation and effects](/pyzed/guides/animation/#effects). |

Colors can be hex strings (with alpha, `"#3b82f680"`), `(r, g, b[, a])` tuples or theme tokens
such as `"accent"`, `"panel"` or `"text_muted"`, so styles follow theme switches.

Text properties apply to **every text inside** the styled widget, including the labels of
`pyzed.ui` components. The closest style wins.

## Reusing styles

```python
card = pz.Style(background="elevated", border=(1, "border"), radius=10, padding=16)
pz.column([...]).style(card)
pz.column([...]).style(card | pz.Style(shadow=("#0006", (0, 4), 12)))   # the right side wins

pz.define_style("pill", radius=999, padding=(4, 12), size=12, weight="semibold")
pz.text("new").style("pill", background="accent")
```

`widget.style(a, b, color=...)` merges in order, and calling `style()` again merges with what
the widget already has. Passing `None` for a property removes it. `Style.to_dict()` and
`Style.from_dict()` turn a style into JSON-friendly data and back.

Components take `style=` too: `Rating(value=3, style="card")`.

## Gradients, opacity and masks

```python
sunset = pz.Gradient(["#f97316", "#db2777", "#7c3aed"], angle=120)
box.style(background=sunset)
box.style(background=pz.Paint("success", opacity=0.2))              # a translucent token
box.style(background=pz.Paint(sunset, mask=pz.Mask([1, 0.15])))     # fades out
```

- `pz.Gradient(stops, angle=180)`: colors spread evenly, or `(offset, color)` pairs. Angles
  follow CSS (0 up, 90 right). Up to 8 stops.
- `pz.Mask(stops)`: opacities along the fill's direction (on a plain color, along its own
  `angle`).
- `pz.Paint(fill, opacity=, mask=)`: a color or gradient with an overall opacity and a mask.

## Color picker

`ui.ColorPicker` edits any of these: a color with alpha, a gradient (click the bar to add a
stop, drag stops, trash removes the selected one) or a mask. It sends back a hex string, a
`pz.Gradient` or a `pz.Paint`, ready for `background`:

```python
ui.ColorPicker(value=self.fill, on_change=lambda e: setattr(self, "fill", e.value))
```

![The color picker editing a gradient](../../../assets/tutorials/color-picker.png)

`alpha=False`, `gradients=False` and `masks=False` hide those parts; `swatches=[...]` sets the
quick colors. `ui.color_swatch(value)` shows a value as a small square. See
[`examples/color_picker.py`](https://github.com/albakore/pyzed/blob/main/examples/color_picker.py).

## The global style

`App.style` styles the whole window, and `pz.set_style(...)` sets a style for every window
(each window's `style` goes on top of it):

```python
class MyApp(pz.App):
    style = pz.Style(font="serif", size=15, color="#e6e1cf", radius=2)
```

Its text properties fill in what texts don't set themselves, and its `color`, `size`,
`background`, `border_color` and `radius` also become the theme's `text`, `ui_font_size`,
`background`, `border` and `radius` tokens, so `pyzed.ui` components follow them. Change
`self.style` at any time to restyle the app. For other theme colors, derive a theme:
`self.theme = themes.get("One Dark").with_accent("#ff6b6b")` (see [Themes](/pyzed/guides/theming/)).

See [`examples/styles.py`](https://github.com/albakore/pyzed/blob/main/examples/styles.py).
