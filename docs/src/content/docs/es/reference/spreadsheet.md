---
title: "Hoja de cálculo (pz.Workbook, ui.Spreadsheet)"
description: "Referencia de la API de la hoja de cálculo de Pyzed: pz.Workbook (celdas, fórmulas, formatos, archivos), la cuadrícula pz.sheet y el componente ui.Spreadsheet."
sidebar:
  order: 10.9
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs_es.py. -->

Una hoja de cálculo como Google Sheets o Excel. `pz.Workbook` guarda los datos y calcula las
fórmulas, `pz.sheet` dibuja la cuadrícula y `ui.Spreadsheet` añade barra de herramientas,
menús y pestañas de hojas. Ver la [sección Hoja de cálculo](/pyzed/es/spreadsheet/).

```python
book = pz.Workbook()
book["A1"], book["A2"], book["A3"] = 2, 3, "=A1*A2"
ui.Spreadsheet(book=book)
```

## Libro

### `Workbook`

```python
class Workbook
```

Un libro de hoja de cálculo: hojas de celdas con valores, fórmulas y formatos. Las celdas se leen y escriben por su dirección (`book["B2"] = "=SUM(A1:A9)"`; `book["A1:C3"]` da filas de valores); además da formato, ordena, filtra, deshace y abre y guarda archivos CSV y Excel. Se muestra (y edita) con `ui.Spreadsheet(book=book)` o `pz.sheet(book)`. Las direcciones pueden nombrar una hoja (`"Ventas!A1"`); sin ella usan la hoja activa. Las filas y columnas empiezan en 1, como en la cuadrícula; las columnas también se aceptan como letras (`"C"`).

| Parámetro | Descripción |
| --- | --- |
| `sheets` | Nombres de las hojas con que empieza (una `"Sheet1"` si no se indica). |

```python
book = pz.Workbook(sheets=["Ventas", "Equipo"])
book["Ventas!B2"] = "=SUM(C2:C9)"
book.format("A1:G1", bold=True, fill="#e8f0fe")
book.save("informe.xlsx")
```

Cada método se explica en [El libro en Python](/pyzed/es/spreadsheet/workbook/), [Formato](/pyzed/es/spreadsheet/formatting/), [Ordenar, filtrar y validar](/pyzed/es/spreadsheet/data/), [Filas, columnas y hojas](/pyzed/es/spreadsheet/structure/) y [Archivos](/pyzed/es/spreadsheet/files/); `help(pz.Workbook)` los lista con su documentación.

**Métodos y propiedades**

#### `Workbook.open`

```python
@staticmethod
Workbook.open(path)
```

Abre un archivo: `.xlsx`, `.xlsm`, `.xls`, `.ods`, `.csv`, `.tsv` o `.txt`.

#### `Workbook.from_bytes`

```python
@staticmethod
Workbook.from_bytes(data)
```

Un libro a partir de los bytes de un archivo de Excel u OpenDocument.

#### `Workbook.from_csv`

```python
@staticmethod
Workbook.from_csv(text, delimiter=None)
```

Un libro con el texto CSV en su hoja (el separador se detecta si no se indica).

#### `Workbook.from_rows`

```python
@staticmethod
Workbook.from_rows(rows, *, header=None, sheet=None)
```

Un libro con filas (listas o dicts; los dicts escriben una fila de cabecera).

#### `Workbook.functions`

```python
@staticmethod
Workbook.functions()
```

Las funciones que pueden usar las fórmulas: `[(nombre, argumentos, descripción), ...]`.

#### `Workbook.column_name`

```python
@staticmethod
Workbook.column_name(col)
```

Las letras de una columna a partir de su número, empezando en 1 (`column_name(28) == "AB"`).

## Mostrarlo

### `Spreadsheet`

```python
class Spreadsheet
```

Un componente: la hoja de cálculo entera, con la cuadrícula y su barra de fórmulas, una barra de herramientas, menús con el clic derecho, una barra de búsqueda, paneles de formato condicional, validación y notas, pestañas de hojas y una barra de estado con la suma de la selección. Todo lo que hace el usuario va a `book`. Ver [El componente Spreadsheet](/pyzed/es/spreadsheet/component/).

| Parámetro | Descripción |
| --- | --- |
| `book` | El `pz.Workbook` que muestra y edita (uno nuevo y vacío si es `None`). Guárdalo en tu app para que sus datos sobrevivan a las reconstrucciones de la vista. |
| `toolbar` | Muestra la barra de herramientas. |
| `formula_bar` | Muestra el cuadro de nombres y la barra de fórmulas. |
| `tabs` | Muestra las pestañas de hojas y la barra de estado. |
| `headers` | Muestra las letras de columna y los números de fila. |
| `readonly` | Se puede seleccionar, copiar y buscar, pero no cambiar nada. |
| `text_size` | Tamaño en píxeles del texto de 10 pt. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `on_change` | Recibe `event.value` con `action`, `range` y `sheet` cuando el usuario cambia algo. |
| `on_select` | Recibe `event.value` con `range` y `sheet` cuando cambia la selección. |

```python
ui.Spreadsheet(book=self.book, on_change=lambda e: print(e.value.action, e.value.range))
```

### `sheet`

```python
sheet(
    book,
    *,
    colors=None,
    text_size=13.0,
    formula_bar=True,
    headers=True,
    width=None,
    height=None,
    readonly=False,
    on_change=None,
    on_select=None,
    on_context=None,
    on_dropdown=None,
    on_filter=None,
    on_find=None,
    on_invalid=None,
    on_edit=None,
)
```

La cuadrícula de la hoja de cálculo sola: celdas, cabeceras y barra de fórmulas, con selección, edición, fórmulas, el controlador de relleno, copiar y pegar y los atajos de Sheets y Excel. Solo dibuja las celdas visibles. No dibuja menús: sus eventos dicen dónde pulsó el usuario. Ver [La cuadrícula sola](/pyzed/es/spreadsheet/grid/).

| Parámetro | Descripción |
| --- | --- |
| `book` | El `pz.Workbook` que muestra. |
| `colors` | Un dict de colores (`background`, `grid`, `header`, `text`, `accent`, `selection`...); `ui.sheet_colors(theme)` crea uno a partir de un tema. |
| `text_size` | Tamaño en píxeles del texto de 10 pt. |
| `formula_bar` | Muestra el cuadro de nombres y la barra de fórmulas. |
| `headers` | Muestra las letras de columna y los números de fila. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `readonly` | Solo seleccionar y copiar. |
| `on_change` | Recibe un dict cuando el usuario cambia celdas, formatos o la estructura: `action` (`"edit"`, `"paste"`, `"fill"`, `"clear"`, `"format"`, `"sort"`, `"undo"`...), `range` y `sheet`. |
| `on_select` | Recibe un dict cuando cambia la selección (lee `book.selection`). |
| `on_context` | Recibe, con un clic derecho, `kind` (`"cell"`, `"row"` o `"column"`), `cell`, `x` e `y` (relativas a la cuadrícula): muestra ahí un menú. |
| `on_dropdown` | Se llama cuando debe abrirse la lista de una celda: `cell`, `options`, `x`, `y`, `width`. |
| `on_filter` | Se llama al pulsar un botón de filtro de la cabecera: `column`, `x`, `y`. |
| `on_find` | Se llama con Ctrl+F o Ctrl+H: `mode` (`"find"` o `"replace"`). |
| `on_invalid` | Se llama cuando un valor escrito incumple una validación estricta: `cell`, `value`, `message`. |
| `on_edit` | Se llama cuando empieza o termina la escritura en una celda: `editing`. |

```python
pz.sheet(self.book, formula_bar=False, on_change=lambda e: print(e["action"], e["range"]))
```

### `sheet_colors`

```python
sheet_colors(theme=None)
```

Los colores que `ui.Spreadsheet` da a su cuadrícula para un tema, como el dict que recibe `pz.sheet(colors=...)`.

| Parámetro | Descripción |
| --- | --- |
| `theme` | Un tema (el actual si no se indica). |
