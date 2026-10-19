---
title: Teclado y atajos
description: "Atajos de teclado en apps de Pyzed: combinaciones estilo Zed con on_key y cómo mostrar los atajos en menús, botones y el resto de la interfaz."
sidebar:
  order: 8
---

Define `on_key(self, combo)` en tu app para recibir **todas** las teclas pulsadas, como un
keymap global. `combo` es un texto al estilo de Zed:

| Tecla | `combo` |
| --- | --- |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> | `"ctrl-shift-p"` |
| <kbd>Cmd</kbd>+<kbd>S</kbd> (macOS) / <kbd>Win</kbd>+<kbd>S</kbd> | `"cmd-s"` |
| <kbd>Alt</kbd>+<kbd>Z</kbd> | `"alt-z"` |
| <kbd>Esc</kbd> | `"escape"` |
| Flechas | `"up"`, `"down"`, `"left"`, `"right"` |
| Otras | `"enter"`, `"tab"`, `"space"`, `"backspace"`, `"delete"`, `"home"`, `"end"`, `"pageup"`, `"pagedown"`, `"f1"`… |

Los modificadores van siempre en este orden: `ctrl-`, `alt-`, `shift-`, `cmd-`. Las letras llegan
en minúscula.

```python
KEYMAP = {
    "ctrl-shift-p": "abrir_paleta",
    "ctrl-p": "abrir_archivos",
    "ctrl-b": "toggle_left",
    "ctrl-s": "guardar",
}


class App(pz.App):
    def on_key(self, combo):
        # admite Cmd en macOS y Ctrl en el resto con la misma tabla
        accion = KEYMAP.get(combo.replace("cmd-", "ctrl-"))
        if accion:
            return getattr(self, accion)()
```

`on_key` puede devolver lo mismo que un callback: `None`, un `Command` o un mensaje para `update`.

:::note
`on_key` recibe también las teclas que ya procesó un campo con foco (por ejemplo, las letras que
escribes en un `input`). Responde solo a los combos que te interesen, y comprueba el estado si un
atajo solo tiene sentido en cierto contexto (`if self.palette_open and combo == "escape"`).

<kbd>Tab</kbd> y <kbd>Shift</kbd>+<kbd>Tab</kbd> además mueven el foco entre campos cuando
ningún widget las usó; ver [Accesibilidad](/pyzed/es/guides/accessibility/#moverse-entre-campos-con-tab).
:::

## Teclas mantenidas y teclas soltadas

`on_key` se llama una vez por pulsación. Para teclas que
actúan *mientras* se mantienen, define `on_key_up(self, key)`, que recibe cada tecla al soltarla
por su nombre (`"left"`, `"space"`, `"a"`, sin modificadores), o pregunta en cualquier momento
qué teclas están pulsadas:

- `pz.pressed()` devuelve las teclas pulsadas ahora mismo como un `frozenset` de nombres.
- `pz.is_pressed("left", "a")` es `True` mientras se mantenga cualquiera de ellas.

```python
class Juego(pz.App):
    def on_key_up(self, key):
        if key == "space":
            self.cargando = False

    def tick(self, dt):
        if pz.is_pressed("left", "a"):
            self.x -= 200 * dt
```

Las pulsaciones y las teclas soltadas solo se convierten en mensajes cuando la app o alguna de
sus ventanas define `on_key` u `on_key_up`, así que una app sin ellos no se redibuja con cada
tecla. `pz.pressed()` funciona en ambos casos. La [sección de juegos](/pyzed/es/games/#entrada)
los muestra en un bucle de fotogramas, junto con ayudas de `pyzed.game` como `axis` y `vector`.

## Mostrar atajos

- `ui.kbd("ctrl-shift-p")` dibuja las teclas. En macOS usa símbolos (⌃⇧P) y en el resto palabras.
- `ui.button(..., keys="ctrl-s")`, `ui.MenuItem(..., keys=...)`, `ui.PaletteItem(..., keys=...)`
  y `ui.tooltip(..., keys=...)` muestran el atajo junto a la acción.
- Fija el estilo con `pyzed.ui.base.KEY_STYLE = "symbols"` o `"words"`.
