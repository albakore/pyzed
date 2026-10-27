---
title: Keymap
description: "Cambia cualquier atajo de teclado de Pyzed Design, como el keymap de Zed: un editor de keymap con búsqueda y conflictos, y un archivo keymap.json con contextos."
sidebar:
  order: 12.5
---

Todas las teclas de Pyzed Design salen de un solo keymap, como en Zed: los menús, la paleta de comandos, el lienzo,
el árbol del proyecto, el panel de código y el propio editor de código. Puedes cambiar cualquiera, dar más teclas a
una acción, quitarlas y volver a las de fábrica, desde una ventana o editando un archivo.

## El editor de keymap

Ábrelo con **Archivo → Editor de keymap**, <kbd>Ctrl</kbd>+<kbd>K</kbd> <kbd>Ctrl</kbd>+<kbd>S</kbd> (una tras otra),
**Ajustes → Atajos de teclado** o **Ajustes del editor → Atajos de teclado**.

![El editor de keymap buscando "save": Guardar con sus teclas de fábrica y Guardar como con teclas cambiadas](../../../../assets/editor/keymap-editor.png)

Cada fila es una acción con una de sus teclas:

- **Acción**: su nombre y el que tiene en `keymap.json` (`workspace::SaveAs`).
- **Teclas**: las teclas que la ejecutan, o un guion si no tiene.
- **Contexto**: dónde funcionan las teclas (mira [Contextos](#contextos)).
- **Origen**: **Predeterminada**, o **Usuario** para las teclas que pusiste tú.

Escribe en el buscador para filtrar por nombre, teclas o contexto. **Cambiadas** muestra solo las acciones que
cambiaste y **Conflictos** las teclas que ejecutan dos acciones en el mismo lugar.

### Cambiar teclas

1. Haz clic en el lápiz de una fila (o en **+** para darle otra tecla más a la acción).
2. Pulsa las teclas nuevas. Para un acorde, pulsa dos una tras otra, como <kbd>Ctrl</kbd>+<kbd>K</kbd> y luego <kbd>Ctrl</kbd>+<kbd>G</kbd>.
3. Elige el contexto si deben funcionar en otro lugar.
4. Pulsa <kbd>Intro</kbd> (o la marca) para guardar, o <kbd>Escape</kbd> para cancelar.

![Grabando Ctrl+K Ctrl+G para Ir a la línea en el panel de código](../../../../assets/editor/keymap-editor-recording.png)

Mientras grabas, la línea sobre la lista avisa si esas teclas ya ejecutan otra acción en ese contexto.

:::tip
La papelera quita las teclas, la flecha devuelve las teclas de fábrica de la acción y **Restablecer todo** devuelve
todas.
:::

### Conflictos

Cuando las mismas teclas ejecutan dos acciones en el mismo contexto, las dos filas lo dicen. Gana la última: la tuya
sobre la de fábrica. La fila de la acción que se ejecuta dice **Reemplaza a**, y la otra **Tapada por**.

![Ctrl+D asignado a Cuadrícula en el lienzo, tapando a Duplicar](../../../../assets/editor/keymap-editor-conflicts.png)

## Contextos

Un contexto es la parte del diseñador que tiene el teclado. Las teclas se buscan desde el contexto más interno hasta
**Workspace**, así que las mismas teclas pueden hacer cosas distintas en sitios distintos: <kbd>Ctrl</kbd>+<kbd>N</kbd>
es **Nuevo formulario** en cualquier lado, pero **Nuevo archivo** en el árbol del proyecto.

| Contexto | Dónde | Dentro de |
| --- | --- | --- |
| `Workspace` | En todo el diseñador | (el más externo) |
| `Canvas` | El lienzo del formulario, tras hacer clic en el formulario o en un control | Workspace |
| `ProjectPanel` | El árbol del proyecto | Workspace |
| `CodePanel` | El panel de código: autocompletado, buscar, ir a la línea, ajuste de línea | Workspace |
| `Editor` | El texto del editor de código | CodePanel |

:::note
Un acorde puede empezar con cualquier tecla, como el <kbd>Ctrl</kbd>+<kbd>X</kbd> <kbd>U</kbd> de Emacs. Dentro del
editor, la primera tecla de un acorde solo espera la segunda: <kbd>Ctrl</kbd>+<kbd>K</kbd> <kbd>Ctrl</kbd>+<kbd>S</kbd>
abre el editor de keymap también desde el código.
:::

## Atajos base

¿Vienes de otro editor? Como el `base_keymap` de Zed, **Ajustes → Editor de código → Atajos y Vim → Atajos base**
pone los atajos de ese editor sobre los de fábrica (que son los de VS Code y Zed), y los tuyos siguen yendo encima:

| Atajos base | Algunos de sus atajos |
| --- | --- |
| **VS Code** (por defecto) | Los de fábrica: <kbd>Ctrl</kbd>+<kbd>D</kbd> siguiente coincidencia, <kbd>Alt</kbd>+<kbd>↑</kbd> mover línea, <kbd>F12</kbd> definición. |
| **JetBrains** | <kbd>Ctrl</kbd>+<kbd>D</kbd> duplicar, <kbd>Ctrl</kbd>+<kbd>Y</kbd> borrar línea, <kbd>Ctrl</kbd>+<kbd>W</kbd> ampliar selección, <kbd>Ctrl</kbd>+<kbd>B</kbd> definición, <kbd>Mayús</kbd>+<kbd>F6</kbd> renombrar, <kbd>Alt</kbd>+<kbd>Enter</kbd> arreglos rápidos, <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>L</kbd> formatear, <kbd>F2</kbd> problema siguiente. |
| **Sublime Text** | <kbd>Ctrl</kbd>+<kbd>Mayús</kbd>+<kbd>D</kbd> duplicar, <kbd>Ctrl</kbd>+<kbd>Mayús</kbd>+<kbd>↑</kbd> mover línea, <kbd>Ctrl</kbd>+<kbd>J</kbd> unir líneas, <kbd>Ctrl</kbd>+<kbd>K</kbd> <kbd>Ctrl</kbd>+<kbd>U</kbd> mayúsculas, <kbd>Ctrl</kbd>+<kbd>B</kbd> ejecutar. |
| **Atom** | <kbd>Ctrl</kbd>+<kbd>↑</kbd> mover línea, <kbd>Ctrl</kbd>+<kbd>Mayús</kbd>+<kbd>D</kbd> duplicar, <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>[</kbd> plegar. |
| **TextMate** | <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>↑</kbd> mover línea, <kbd>Ctrl</kbd>+<kbd>Mayús</kbd>+<kbd>L</kbd> seleccionar línea, <kbd>Ctrl</kbd>+<kbd>R</kbd> ejecutar. |
| **Emacs** | <kbd>Ctrl</kbd>+<kbd>F</kbd>/<kbd>B</kbd>/<kbd>N</kbd>/<kbd>P</kbd> mover, <kbd>Ctrl</kbd>+<kbd>A</kbd>/<kbd>E</kbd> inicio y final de línea, <kbd>Ctrl</kbd>+<kbd>K</kbd> cortar la línea, <kbd>Ctrl</kbd>+<kbd>W</kbd>/<kbd>Alt</kbd>+<kbd>W</kbd>/<kbd>Ctrl</kbd>+<kbd>Y</kbd> cortar, copiar, pegar, <kbd>Ctrl</kbd>+<kbd>Espacio</kbd> marca, <kbd>Ctrl</kbd>+<kbd>X</kbd> <kbd>U</kbd> deshacer, <kbd>Ctrl</kbd>+<kbd>X</kbd> <kbd>Ctrl</kbd>+<kbd>S</kbd> guardar, <kbd>Alt</kbd>+<kbd>X</kbd> paleta de comandos. |

El editor de keymap y la referencia de atajos muestran los atajos base en uso, y **Restablecer** devuelve los suyos,
no los de VS Code.

## Modo Vim

El **modo Vim** (Ajustes → Editor de código → Atajos y Vim, o *Activar o desactivar el modo Vim* en la paleta de
comandos) edita como Vim, igual que el `vim_mode` de Zed. La barra de estado muestra el modo (`NORMAL`,
`-- INSERT --`, `-- VISUAL --`) y el cursor es un bloque fuera del modo Insertar.

- **Movimientos**: `h` `j` `k` `l`, `w` `b` `e` (y `W` `B` `E`), `0` `^` `$`, `gg` `G`, `{` `}`, `%`, `f` `t` `F`
  `T` con `;` y `,`, y repeticiones (`3w`, `5j`).
- **Operadores**: `d` `c` `y` `>` `<`, `gc` (comentar), `g~` `gu` `gU` (mayúsculas), doblados para líneas enteras
  (`dd`, `cc`, `yy`, `gcc`), con movimientos y objetos de texto: `iw` `aw`, `i"` `a'`, `i(` `ab`, `i{` `aB`, `i[`,
  `i<`, `ip`.
- **Comandos**: `i` `a` `I` `A` `o` `O`, `v` `V`, `x` `X` `s` `S` `D` `C` `Y`, `p` `P`, `u` y <kbd>Ctrl</kbd>+<kbd>R</kbd>,
  `J`, `~`, `r`, `.` (repetir), `*` `#`, `/` `?` `n` `N` (la barra de búsqueda), `K` (tarjeta de información), `gd`
  (definición), <kbd>Ctrl</kbd>+<kbd>O</kbd>/<kbd>I</kbd> (atrás y adelante), <kbd>Ctrl</kbd>+<kbd>D</kbd>/<kbd>U</kbd>/<kbd>F</kbd>/<kbd>B</kbd>,
  `zz`, `zc` `zo` `za` `zM` `zR` (pliegues).
- **La línea de comandos** (`:`): `:w`, `:q`, `:wq` y `:x`, `:42` (ir a la línea), `:s/viejo/nuevo/g` en la línea,
  `:%s/viejo/nuevo/g` en todas (con `\1` y `&` en el reemplazo), `:noh`, `:set wrap` y `:set number`.

Lo que copias y borras va al portapapeles del sistema, así que `p` pega también lo que copiaste en otra app.


## El archivo keymap.json

Tus cambios se guardan en `keymap.json`, junto a los ajustes del diseñador:

| Sistema | Carpeta |
| --- | --- |
| Windows | `%APPDATA%\pyzed` |
| macOS | `~/Library/Application Support/pyzed` |
| Linux | `~/.config/pyzed` (o `$XDG_CONFIG_HOME/pyzed`) |

`PYZED_CONFIG_DIR` cambia la carpeta. **Editar keymap.json** en el editor de keymap lo abre en el panel de código, y
se aplica en cuanto lo guardas.

Usa el formato de Zed: una lista de bloques, cada uno con un `context` y sus `bindings` de teclas a una acción. `null`
quita una tecla de fábrica. Se admiten comentarios (`//`) y comas finales.

```json
// Atajos de Pyzed Design
[
  {
    "context": "Workspace",
    "bindings": {
      "ctrl-alt-s": "workspace::SaveAs",
      "ctrl-shift-s": null
    }
  },
  {
    "context": "Editor",
    "bindings": {
      "ctrl-alt-d": "editor::DuplicateLineDown",
      "ctrl-d": null
    }
  },
  {
    "context": "Canvas",
    "bindings": {
      "ctrl-k ctrl-g": "workspace::Grid"
    }
  }
]
```

- **Las teclas** se escriben como en Zed: modificadores `ctrl`, `alt`, `shift` (`cmd` y `super` cuentan como `ctrl`)
  unidos con `-` a una tecla (`a`, `f2`, `enter`, `space`, `up`, `pageup`...). Un acorde son dos teclas separadas por
  un espacio.
- **Las acciones** se escriben `espacio::Acción`: `workspace::` para los comandos de los menús, `canvas::`,
  `project_panel::`, `code_panel::` y `editor::`. El editor de keymap muestra el nombre de cada acción.

:::caution
Si el archivo tiene un error (una acción, teclas o contexto desconocidos), el resto sigue funcionando y el editor de
keymap muestra los problemas arriba.
:::

En versiones anteriores, las teclas del editor de código se guardaban en `"keymap"` dentro de `designer.json`. El
diseñador las pasa a `keymap.json` la primera vez que arranca.

## En tus propias apps

El componente editor de código acepta el mismo tipo de keymap: `ui.editor(keymap={"ctrl-alt-d": "duplicate_line_down",
"ctrl-d": None})`. Mira [el componente editor de código](/pyzed/es/components/code/#varios-cursores-y-los-atajos-de-zed).
