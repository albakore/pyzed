---
title: Código
description: El editor de código con resaltado y marcadores de git, y la vista de terminal.
sidebar:
  order: 7
---

## Editor

![Editor de código](../../../../assets/components/editor.png)

```python
ui.editor(
    "counter.py",                      # id del buffer
    codigo,                            # texto inicial
    path="counter.py",                 # deduce el lenguaje
    markers={6: "modified", 7: "created", 10: "created"},
    on_change=self.cambiado,           # recibe el texto completo
    on_cursor=self.cursor,             # recibe (línea, columna), desde 1
)
```

- **No controlado.** El texto, el cursor, la selección y el historial de deshacer viven en Rust,
  asociados al `id`. `text` solo se usa la primera vez que aparece ese `id`. Para reemplazar el
  contenido devuelve `Command.set_editor_text(id, texto)`.
- **Un buffer por archivo.** Usa la ruta como `id`: al cambiar de pestaña cada archivo conserva su
  cursor y su historial.
- **Resaltado.** Más de 100 lenguajes (gramáticas de syntect / two-face) con los colores de
  sintaxis del tema. El lenguaje se deduce de `path` o se pasa con `language="rs"`.
- **Marcadores de git.** `markers` asigna a cada línea `"created"`, `"modified"` o `"deleted"`.
- **Cursor.** `Command.set_editor_cursor(id, línea, columna)` mueve el cursor, incluso antes del
  primer dibujado.

```python
def guardar(self):
    Path(self.activa).write_text(self.textos[self.activa])
    self.sucios.discard(self.activa)

def cambiado(self, texto):
    self.textos[self.activa] = texto
    self.sucios.add(self.activa)
```

- **Líneas largas.** Con `wrap=False` (por defecto) el editor se desplaza en horizontal y los
  números de línea quedan fijos a la izquierda. Con `wrap=True` las líneas se ajustan y el número
  aparece en la primera fila de cada línea, como en Zed.
- **Línea activa.** La línea del cursor se resalta y el scroll sigue al cursor (también con
  <kbd>RePág</kbd>/<kbd>AvPág</kbd>).

### Editar como en Zed

![Bloques plegados, code lens y el minimapa](../../../../assets/components/editor-features.png)

```python
ui.editor(
    "app.py", codigo, path="app.py",
    minimap=True,                  # o un ancho en píxeles
    cursor_shape="block",          # "bar" (por defecto), "block", "underline", "hollow"
    on_zoom=self.zoom,             # 1, -1 o 0 con Ctrl+= / Ctrl+- / Ctrl+0 y Ctrl+rueda
    font_size=self.tamano,
)

def zoom(self, paso):
    self.tamano = 14 if paso == 0 else self.tamano + paso
```

- **Cierre automático** (`auto_close=True`, por defecto). Al escribir `(`, `[`, `{`, `"`, `'` o
  `` ` `` también se inserta el de cierre y el cursor queda en medio. Con una selección, el par la
  envuelve. Escribir un cierre que ya está a continuación lo salta, <kbd>Retroceso</kbd> dentro de
  un par vacío borra los dos y <kbd>Enter</kbd> entre llaves abre una línea con sangría. Las
  comillas no se cierran dentro de palabras (`don't`), pero sí tras un prefijo de cadena (`f"`, `rb'`).
- **Plegado** (`folding=True`, por defecto). Los bloques se pliegan según la sangría: pasa el ratón
  por el margen para ver las flechas y haz clic en una para plegar su bloque. Una línea plegada
  termina en `⋯` (haz clic para desplegarla). <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>[</kbd> pliega
  el bloque más interno alrededor del cursor y <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>]</kbd> lo
  despliega. `Command.fold_line(id, línea)` y `Command.fold_all(id)` lo hacen desde código. Los
  números de línea, `markers`, `annotations`, `on_change`, `on_cursor` y `set_editor_cursor` siguen
  usando las líneas reales; editar una línea plegada o mover el cursor dentro de un pliegue lo despliega.
- **Minimapa.** `minimap=True` dibuja el código en miniatura a la derecha con el área visible
  resaltada; haz clic para saltar, arrastra para desplazarte o usa la rueda encima.
- **Zoom de fuente.** El editor pasa <kbd>Ctrl</kbd>+<kbd>=</kbd>, <kbd>Ctrl</kbd>+<kbd>-</kbd>,
  <kbd>Ctrl</kbd>+<kbd>0</kbd> y <kbd>Ctrl</kbd>+rueda a `on_zoom`; cambia `font_size` en respuesta.
- **Cursor.** `cursor_shape`, `cursor_blink`, `cursor_width` (de la barra) y `cursor_color` (por
  defecto, el color de jugador del tema), como la opción `cursor_shape` de Zed.

## Terminal

![Terminal](../../../../assets/components/terminal.png)

```python
salida = "$ pytest -q\n\x1b[32m24 passed\x1b[0m in 1.21s\n$ "
ui.terminal(salida, id="term")
```

Es una vista de **solo lectura** que entiende los colores ANSI y se mantiene desplazada al final.
Pásale la salida de un proceso que ejecutes tú (por ejemplo con `subprocess` en un hilo y
`pz.post`). También acepta una lista de líneas de segmentos `(texto, color)`, donde el color es
un nombre ANSI (`"green"`, `"red"`, `"dim"`…) o un token del tema.

`ui.ansi(texto)` hace la conversión a segmentos por si quieres dibujarlos a tu manera.

Referencia completa: [Código](/pyzed/es/reference/ui/#código).
