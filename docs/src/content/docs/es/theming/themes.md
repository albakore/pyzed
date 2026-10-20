---
title: Temas
description: "Temas de Pyzed: One, Ayu y Gruvbox en claro y oscuro, los tokens de color de Zed y cómo crear, importar y cambiar temas mientras la app corre."
sidebar:
  order: 3
---

Cada componente de `pyzed.ui` lee sus colores del **tema actual**. Cambiar `self.theme`
restiliza toda la interfaz al instante.

![Temas incluidos](../../../../assets/tutorials/styling.png)

## Elegir un tema

`App.theme` (y `Window.theme`) acepta un `Theme`, el **nombre** de un tema registrado o
`themes.auto(...)` para seguir el modo claro/oscuro del sistema:

```python
class MiApp(pz.App):
    theme = "Ayu Dark"                                   # cualquier nombre de pz.themes.names()
    # theme = pz.themes.ONE_LIGHT                        # o un objeto Theme
    # theme = pz.themes.auto("One Light", "One Dark")    # sigue al sistema

    def alternar_tema(self):
        actual = self.resolved_theme()
        self.theme = "One Light" if actual.is_dark else "One Dark"
```

Pyzed incluye las familias **One**, **Ayu** y **Gruvbox** importadas de Zed (licencia MIT):
`One Dark`, `One Light`, `Ayu Dark`, `Ayu Light`, `Ayu Mirage`, `Gruvbox Dark`,
`Gruvbox Dark Hard`, `Gruvbox Light`… `pz.themes.names()` devuelve la lista exacta y
`pz.themes.get("ayu dark")` busca sin distinguir mayúsculas.

Un selector de temas:

```python
ui.select(pz.themes.names(), self.resolved_theme().name, lambda name: setattr(self, "theme", name))
```

## Leer los colores del tema

Como `self.theme` puede ser un nombre o un `AutoTheme`, usa **`self.resolved_theme()`** para
obtener el `Theme` concreto que se está usando. Sus tokens son atributos:

```python
def view(self):
    t = self.resolved_theme()
    return pz.container(contenido, bg=t.surface, border_color=t.border, radius=t.radius)
```

Dentro de `view()` también puedes usar `pyzed.theme.current()`. Los componentes aceptan
`theme=` para dibujarse con otro tema, y un `Theme` funciona como gestor de contexto para
dibujar un bloque con otro tema:

```python
with pz.themes.get("One Light"):
    vista_previa = ui.card(ui.label("Así se ve en claro"))
```

## Crear un tema

### Cambiar algunos tokens

`Theme.derive()` copia un tema cambiando algunos tokens (los diccionarios `syntax` y `ansi` se
combinan). `with_accent()` cambia el color de acento y todo lo que depende de él (foco,
selección, enlaces, botones principales):

```python
oceano = pz.themes.ONE_DARK.derive(name="Océano", syntax={"keyword": "#ff79c6"}).with_accent("#4fb3ff")
```

Un estilo de sintaxis es un color o una tupla `(color, "italic" | "bold")`.

### Generarlo a partir de tres colores

```python
propio = pz.Theme.generate("Propio", background="#1b1d23", text="#e6e6e6", accent="#ff8a65")
```

Superficies, bordes, estados de hover y textos atenuados se mezclan a partir del fondo y el
texto. La apariencia (claro u oscuro) se deduce del fondo si no pasas `appearance=`. También
acepta `error`, `warning`, `success`, `syntax` y `radius`.

### Importar un tema de Zed

Cualquier tema de la [galería de Zed](https://zed.dev/extensions?filter=themes) funciona:

```python
catppuccin = pz.Theme.from_zed("catppuccin.json", name="Catppuccin Mocha")   # uno
pz.themes.load_zed("catppuccin.json")                                       # todos, registrados por nombre
```

### Registrar, guardar y cargar

```python
pz.themes.register(propio)          # ya se puede usar como theme = "Propio"
propio.save("propio.json")          # formato propio de Pyzed
pz.Theme.load("propio.json")
```

### Utilidades de color

`pyzed.theme` incluye `alpha`, `mix`, `lighten`, `darken`, `luminance`, `contrast` y
`readable_on(fondo)`, que elige texto claro u oscuro según el contraste.

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

`Theme.from_dict(datos)` crea un tema con los tokens que indiques y toma el resto de One Dark u
One Light según `appearance`. Es el formato que escribe `Theme.save()`.
