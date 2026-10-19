---
title: "Iconos"
description: "Iconos de Lucide incluidos y utilidades por tipo de archivo."
sidebar:
  order: 8
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs_es.py. -->

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

### `search`

```python
search(query, among=None)
```

Los iconos que coinciden con una búsqueda por nombre y etiqueta, los mejores primero: nombres exactos, luego los que empiezan por la búsqueda, los que tienen todas las palabras y los encontrados por sus etiquetas (`search("person")` encuentra `user`).

| Parámetro | Descripción |
| --- | --- |
| `query` | Palabras que deben aparecer todas en el nombre o las etiquetas. |
| `among` | Buscar solo en estos nombres (por defecto, todos los iconos). |

```python
icons.search("arrow up")[:3]  # ["arrow-up", "arrow-up-01", "arrow-up-10"]
```

### `tags`

```python
tags(name)
```

Las etiquetas de búsqueda de un icono, de Lucide (`tags("user")` es `["person", "account", "contact"]`).

| Parámetro | Descripción |
| --- | --- |
| `name` | Nombre del icono. |

### `category`

```python
category(key, among=None)
```

Los iconos de una categoría de `CATEGORIES`, ordenados. Un icono puede estar en varias.

| Parámetro | Descripción |
| --- | --- |
| `key` | Una clave de `CATEGORIES` (`"arrows"`, `"files"`, `"people"`...). |
| `among` | Mirar solo estos nombres. |

### `CATEGORIES`

Grupos para explorar iconos (flechas, texto, archivos, diseño, multimedia, comunicación, personas, dispositivos, desarrollo, formas, clima, comercio, mapas, estado), cada uno con las palabras de nombres y etiquetas que meten un icono en él.

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
