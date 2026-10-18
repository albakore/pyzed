---
title: "Iconos"
description: "Iconos de Lucide incluidos y utilidades por tipo de archivo."
sidebar:
  order: 8
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs.py. -->

Pyzed incluye la fuente de [Lucide](https://lucide.dev) (licencia ISC) con unos 2000 iconos.
Busca nombres con `pyzed icons <filtro>` o en la web de Lucide.

## pyzed.icons

### `icon`

```python
icon(name, *, size=16, color=None)
```

Un widget de icono. También está en `pyzed.icon`.

| Parámetro | Descripción |
| --- | --- |
| `name` | Nombre del icono. |
| `size` | Tamaño. |
| `color` | Color (por defecto, el del texto). |

### `glyph`

```python
glyph(name)
```

Devuelve el carácter de un icono, para usarlo en cualquier texto con `font="icons"`. Lanza `ValueError` si no existe.

| Parámetro | Descripción |
| --- | --- |
| `name` | Nombre del icono. |

### `names`

```python
names()
```

Lista ordenada de todos los nombres de iconos.

### `for_file`

```python
for_file(name)
```

Devuelve `(icono, color_o_None)` para un nombre de archivo, como en el panel de proyecto de Zed.

| Parámetro | Descripción |
| --- | --- |
| `name` | Nombre del archivo. |

### `language_for`

```python
language_for(name)
```

Nombre legible del lenguaje de un archivo (`"main.py"` → `"Python"`), útil para la barra de estado.

| Parámetro | Descripción |
| --- | --- |
| `name` | Nombre del archivo. |
