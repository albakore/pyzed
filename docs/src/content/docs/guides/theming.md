---
title: Temas
description: Los temas incluidos, los tokens de color de Zed y cómo crear y cambiar temas.
sidebar:
  order: 3
---

Cada componente de `pyzed.ui` lee sus colores del **tema actual**. Cambiar `self.theme`
restiliza toda la interfaz al instante.

| One Dark | One Light |
| --- | --- |
| ![One Dark](../../../../screenshots/components-dark.png) | ![One Light](../../../../screenshots/components-light.png) |

## Elegir un tema

```python
class MiApp(pz.App):
    theme = pz.themes.ONE_LIGHT          # ONE_DARK (por defecto), ONE_LIGHT, GRUVBOX_DARK

    def alternar_tema(self):
        self.theme = pz.themes.ONE_LIGHT if self.theme.is_dark else pz.themes.ONE_DARK
```

`pz.themes.all()` devuelve la lista de temas incluidos, útil para un selector:

```python
ui.segmented([t.name for t in pz.themes.all()], self.theme.name,
              lambda name: setattr(self, "theme", next(t for t in pz.themes.all() if t.name == name)))
```

## Crear un tema

`Theme.derive()` copia un tema cambiando algunos tokens. Los diccionarios `syntax` y `ansi` se
combinan con los del tema base:

```python
oceano = pz.themes.ONE_DARK.derive(
    name="Océano",
    accent="#4fb3ff",
    text_accent="#4fb3ff",
    border_focused="#4fb3ff",
    syntax={"keyword": "#ff79c6", "string": ("#a6e3a1", "italic")},
    radius=8,
)
```

Un estilo de sintaxis es un color o una tupla `(color, "italic" | "bold")`.

## Usar los colores del tema en tu código

Dentro de `view()`, `self.theme` es el tema actual. Sus tokens son atributos:

```python
pz.container(contenido, bg=self.theme.surface, border_color=self.theme.border, radius=self.theme.radius)
```

Fuera de la app, `pyzed.theme.current()` devuelve el tema activo. Los componentes también aceptan
`theme=` para dibujarse con otro tema.

## Tokens

Los nombres siguen el esquema de temas de Zed.

| Grupo | Tokens |
| --- | --- |
| Superficies | `background`, `surface`, `elevated`, `editor`, `title_bar`, `status_bar`, `tab_bar`, `tab_active`, `tab_inactive`, `panel`, `terminal` |
| Bordes | `border`, `border_variant`, `border_focused`, `border_selected` |
| Elementos | `element`, `element_hover`, `element_active`, `element_selected` (botones con fondo) |
| Elementos fantasma | `ghost_hover`, `ghost_active`, `ghost_selected` (filas de lista, botones sin fondo) |
| Texto e iconos | `text`, `text_muted`, `text_placeholder`, `text_disabled`, `text_accent`, `icon`, `icon_muted`, `accent`, `on_accent` |
| Estado | `error`, `warning`, `success`, `info`, `hint` |
| Git | `created`, `modified`, `deleted`, `conflict`, `ignored` |
| Editor | `editor_text`, `line_number`, `line_number_active`, `active_line`, `selection`, `scrollbar`, `scrollbar_hover`, `search_match`, `shadow` |
| Sintaxis | `syntax`: `primary`, `comment`, `comment.doc`, `keyword`, `function`, `type`, `string`, `string.escape`, `number`, `boolean`, `constant`, `property`, `attribute`, `operator`, `variable`, `variable.special`, `punctuation`, `punctuation.bracket`, `tag`, `title`, `link_uri`… |
| Colaboradores | `players`: colores para avatares (`ui.avatar(index=...)`). |
| Terminal | `ansi`: `black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`, `bright_black`, `dim`. |
| Métricas | `radius`, `radius_sm`, `ui_font_size`, `buffer_font_size` |
| Metadatos | `name`, `appearance` (`"dark"` o `"light"`) |

`theme.tokens()` devuelve todos como diccionario y `theme.color("text_muted")` resuelve un nombre.

## Un tema desde cero

Si no quieres partir de uno existente, crea un `pz.Theme(...)` pasando **todos** los tokens
obligatorios. Lo más práctico es copiar `ONE_DARK` o `ONE_LIGHT` de
[`python/pyzed/theme.py`](https://github.com/albakore/pyzed/blob/main/python/pyzed/theme.py) y
cambiar los valores.
