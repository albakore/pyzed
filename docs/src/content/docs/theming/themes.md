---
title: Themes
description: "Pyzed themes: One, Ayu and Gruvbox in light and dark, Zed's color tokens, and how to create, import and switch themes at runtime."
sidebar:
  order: 3
---

Every `pyzed.ui` component reads its colors from the **current theme**. Changing `self.theme`
restyles the whole interface instantly.

![Bundled themes](../../../assets/tutorials/styling.png)

## Choosing a theme

`App.theme` (and `Window.theme`) accepts a `Theme`, the **name** of a registered theme or
`themes.auto(...)` to follow the system's light/dark mode:

```python
class MyApp(pz.App):
    theme = "Ayu Dark"                                   # any name from pz.themes.names()
    # theme = pz.themes.ONE_LIGHT                        # or a Theme object
    # theme = pz.themes.auto("One Light", "One Dark")    # follows the system

    def toggle_theme(self):
        current = self.resolved_theme()
        self.theme = "One Light" if current.is_dark else "One Dark"
```

Pyzed bundles the **One**, **Ayu** and **Gruvbox** families imported from Zed (MIT license):
`One Dark`, `One Light`, `Ayu Dark`, `Ayu Light`, `Ayu Mirage`, `Gruvbox Dark`,
`Gruvbox Dark Hard`, `Gruvbox Light`… `pz.themes.names()` returns the exact list and
`pz.themes.get("ayu dark")` looks one up case-insensitively.

A theme picker:

```python
ui.select(pz.themes.names(), self.resolved_theme().name, lambda name: setattr(self, "theme", name))
```

## Reading theme colors

Since `self.theme` can be a name or an `AutoTheme`, use **`self.resolved_theme()`** to get the
concrete `Theme` in use. Its tokens are attributes:

```python
def view(self):
    t = self.resolved_theme()
    return pz.container(content, bg=t.surface, border_color=t.border, radius=t.radius)
```

Inside `view()` you can also use `pyzed.theme.current()`. Components accept `theme=` to draw
with another theme, and a `Theme` works as a context manager to draw a block with another theme:

```python
with pz.themes.get("One Light"):
    preview = ui.card(ui.label("This is how it looks in light mode"))
```

## Creating a theme

### Changing a few tokens

`Theme.derive()` copies a theme with some tokens changed (the `syntax` and `ansi` dictionaries
are merged). `with_accent()` changes the accent color and everything that depends on it (focus,
selection, links, primary buttons):

```python
ocean = pz.themes.ONE_DARK.derive(name="Ocean", syntax={"keyword": "#ff79c6"}).with_accent("#4fb3ff")
```

A syntax style is a color or a `(color, "italic" | "bold")` tuple.

### Generating one from three colors

```python
custom = pz.Theme.generate("Custom", background="#1b1d23", text="#e6e6e6", accent="#ff8a65")
```

Surfaces, borders, hover states and muted text are blended from the background and the text.
The appearance (light or dark) is inferred from the background unless you pass `appearance=`.
It also accepts `error`, `warning`, `success`, `syntax` and `radius`.

### Importing a Zed theme

Any theme from the [Zed gallery](https://zed.dev/extensions?filter=themes) works:

```python
catppuccin = pz.Theme.from_zed("catppuccin.json", name="Catppuccin Mocha")   # one
pz.themes.load_zed("catppuccin.json")                                       # all, registered by name
```

### Registering, saving and loading

```python
pz.themes.register(custom)         # now usable as theme = "Custom"
custom.save("custom.json")          # Pyzed's own format
pz.Theme.load("custom.json")
```

### Color utilities

`pyzed.theme` includes `alpha`, `mix`, `lighten`, `darken`, `luminance`, `contrast` and
`readable_on(background)`, which picks light or dark text based on contrast.

## Tokens

Names follow Zed's theme schema.

| Group | Tokens |
| --- | --- |
| Surfaces | `background`, `surface`, `elevated`, `editor`, `title_bar`, `status_bar`, `tab_bar`, `tab_active`, `tab_inactive`, `panel`, `terminal` |
| Borders | `border`, `border_variant`, `border_focused`, `border_selected` |
| Elements | `element`, `element_hover`, `element_active`, `element_selected` (filled buttons) |
| Ghost elements | `ghost_hover`, `ghost_active`, `ghost_selected` (list rows, borderless buttons) |
| Text and icons | `text`, `text_muted`, `text_placeholder`, `text_disabled`, `text_accent`, `icon`, `icon_muted`, `accent`, `on_accent` |
| Status | `error`, `warning`, `success`, `info`, `hint` |
| Git | `created`, `modified`, `deleted`, `conflict`, `ignored` |
| Editor | `editor_text`, `line_number`, `line_number_active`, `active_line`, `selection`, `scrollbar`, `scrollbar_hover`, `search_match`, `shadow` |
| Syntax | `syntax`: `primary`, `comment`, `comment.doc`, `keyword`, `function`, `type`, `string`, `string.escape`, `number`, `boolean`, `constant`, `property`, `attribute`, `operator`, `variable`, `variable.special`, `punctuation`, `punctuation.bracket`, `tag`, `title`, `link_uri`… |
| Collaborators | `players`: avatar colors (`ui.avatar(index=...)`). |
| Terminal | `ansi`: `black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`, `bright_black`, `dim`. |
| Metrics | `radius`, `radius_sm`, `ui_font_size`, `buffer_font_size` |
| Metadata | `name`, `appearance` (`"dark"` or `"light"`) |

`theme.tokens()` returns them all as a dictionary and `theme.color("text_muted")` resolves a name.

## A theme from scratch

`Theme.from_dict(data)` creates a theme with the tokens you specify and takes the rest from One
Dark or One Light depending on `appearance`. It is the format that `Theme.save()` writes.
