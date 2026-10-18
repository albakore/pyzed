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
