---
title: Basics
description: "Pyzed basics components for Python desktop GUIs: buttons, text, badges, keyboard shortcuts, avatars, tooltips and cards that follow the theme."
sidebar:
  order: 1
---

:::tip[Component library]
Every component now has its own page, with a live preview, examples and its full API, in the
[component library](/pyzed/library/). This page is kept as a summary.
:::

## Buttons

![Buttons](../../../assets/components/buttons.png)

```python
pz.row([
    ui.button("Filled", self.action),
    ui.button("Ghost", self.action, variant="ghost"),
    ui.button("Outline", self.action, variant="outline"),
    ui.button("Solid", self.action, variant="solid"),
    ui.button("Disabled", self.action, disabled=True),
], spacing=8)

ui.button("Error", self.delete, variant="error", icon="trash-2")
ui.button("Save", self.save, icon="save", keys="ctrl-s")
ui.button("lg", self.action, size="lg")

ui.icon_button("settings", self.settings, tooltip="Settings")
ui.icon_button("bell", self.notifications, selected=True)
```

- `variant`: `"filled"` (default), `"ghost"`, `"subtle"`, `"outline"`, `"solid"`, `"tinted"`
  or a semantic color directly (`"accent"`, `"error"`, `"warning"`, `"success"`, `"info"`).
- `size`: `"xs"`, `"sm"`, `"md"`, `"lg"`.
- `icon` + `icon_position="start" | "end"`, `full_width=True`, `selected=True`.
- If `on_press` is `None`, the button is drawn disabled.
- Any style parameter of [`pz.button`](/pyzed/reference/widgets/#button) (`bg`,
  `hover_bg`, `radius`…) overrides the theme's.

## Text

![Text](../../../assets/components/text.png)

```python
ui.heading("Heading 1")
ui.heading("Heading 2", level=2)
ui.label("Normal label")
ui.muted("Muted text")
ui.label("Accent text", color="accent")
ui.label("def mono(): ...", mono=True, size="sm")
```

`size` accepts `"xs"`, `"sm"`, `"md"`, `"lg"`, `"xl"`, `"2xl"` or a number.

## Badges, indicators, shortcuts and avatars

![Badges, indicators, shortcuts and avatars](../../../assets/components/badges.png)

```python
ui.badge("success", tint="success")
ui.badge("error", tint="error", icon="circle-x")
ui.badge("solid", variant="solid")          # "soft" (default), "solid", "outline"

ui.indicator("success")                      # colored dot

ui.kbd("ctrl-shift-p")                       # ⌃⇧P on macOS, Ctrl Shift P elsewhere
ui.kbd("cmd-k cmd-s")                        # chords

ui.avatar("KV", index=1)                     # index picks a collaborator color from the theme
```

Shortcut style is controlled with `pyzed.ui.base.KEY_STYLE`: `"auto"` (default),
`"symbols"` or `"words"`.

## Tooltip

```python
ui.tooltip(ui.icon_button("save", self.save), "Save", keys="ctrl-s", position="bottom")
```

`ui.icon_button(..., tooltip="Text")` is a shortcut for the same thing.

## Card and divider

![Card](../../../assets/components/card.png)

```python
ui.card(
    pz.column([
        ui.muted("Pyzed draws the UI with Iced in Rust."),
        pz.row([pz.hspace(), ui.button("Cancel", self.close, variant="ghost"),
                ui.button("OK", self.accept, variant="solid")], spacing=8),
    ], spacing=12),
    title="Card",
    actions=[ui.icon_button("ellipsis", self.menu, size="sm")],
    width=380,
)

ui.divider()                # horizontal
ui.divider(vertical=True)
```

Full reference: [Components (pyzed.ui)](/pyzed/reference/ui/#basics).
