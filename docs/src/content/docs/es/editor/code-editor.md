---
title: Editor de código
description: El editor de Python de Pyzed Design - autocompletado, diagnósticos, code lens, plegado, minimapa, servidores de lenguaje, teclas y ajustes.
sidebar:
  order: 7
---

El panel **Código** (dock inferior) es un editor de Python al estilo de Zed, respaldado por dos servidores de
lenguaje de Astral: **ty** (tipos, autocompletado, referencias) y **ruff** (lint y formato). Aparece cuando abres un
manejador y se va cuando lo cierras.

![Escribiendo el código del evento click de un botón](../../../../../screenshots/designer-code.png)

## Qué edita

El editor muestra **un manejador** o **el archivo de código entero**:

| Modo | Cómo llegar | Título |
| --- | --- | --- |
| Un manejador | Doble clic en un control o en un evento, <kbd>Enter</kbd> con un control seleccionado, **View code**, un método del [panel Component](/pyzed/es/editor/component-designer/#el-panel-component). | `login.py › sign_in_click()` |
| Archivo entero | <kbd>F7</kbd>, **Editar el código** (barra de herramientas, menú ☰, paleta), o **Whole file** en la cabecera. | `login.py` |

**Whole file** y **This handler** en la cabecera cambian entre los dos. En modo manejador solo ves la función, pero
los servidores de lenguaje siempre ven el módulo entero con ese manejador dentro, así que el autocompletado y los
diagnósticos conocen los imports y las funciones auxiliares del principio del archivo.

## La cabecera

La cabecera del panel está en inglés:

| Elemento | Hace |
| --- | --- |
| Título | El archivo de código y, en modo manejador, la función. |
| **Problems** (`2 · 1`) | Errores y avisos del código; clic para mostrar u ocultar la lista de problemas. Una marca de verificación indica que no hay ninguno. |
| **Engranaje** | Abre los [ajustes del editor](#ajustes-del-editor). |
| **Whole file / This handler** | Cambia de modo. |
| **Apply** | Comprueba la sintaxis, escribe el código en el documento y, con *Format with ruff on Apply* activo, lo formatea. |
| **×** | Cierra el editor (antes aplica el código). |

Tu código se aplica solo al documento cada vez que cambias de manejador, de modo o de pestaña, guardas o ejecutas;
**Apply** sirve para comprobarlo (y formatearlo) en el momento. Si el código no se puede analizar, una línea roja
bajo el editor dice dónde (`Line 3: invalid syntax`), y guardar, ejecutar o cambiar esperan a que lo arregles.

## Escribir código

- **Resaltado de sintaxis** de Python, con el tema del editor (o uno propio, ver los ajustes).
- **Sangría**: <kbd>Tab</kbd> inserta espacios (el *Tab size*), <kbd>Enter</kbd> mantiene la sangría de la línea y
  añade un nivel después de `:`, <kbd>Retroceso</kbd> dentro de la sangría quita un nivel entero.
- **Paréntesis y comillas**: escribir `(`, `[`, `{`, `"` o `'` inserta su pareja, envuelve la selección si la hay,
  y escribir el carácter de cierre lo salta en lugar de duplicarlo.
- **Margen**: números de línea (siguen a las líneas ajustadas) y la línea actual resaltada.
- **Plegado**: los chevrons del margen pliegan y despliegan bloques (funciones, clases, `if`...);
  <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>[</kbd> pliega el bloque más interior alrededor del cursor y
  <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>]</kbd> lo despliega.
- **Minimapa**: el código en miniatura a la derecha; haz clic o arrastra en él para desplazarte.
- **Métodos de entrada**: los métodos de entrada (IME) de chino, japonés y coreano funcionan: el texto que se
  está componiendo se dibuja en el cursor y el texto confirmado se inserta en cada cursor.
- **Espacios en blanco**: opcionalmente dibuja los espacios como `·` y los tabuladores como `→`.
- **Zoom**: <kbd>Ctrl</kbd>+<kbd>=</kbd>, <kbd>Ctrl</kbd>+<kbd>-</kbd> o <kbd>Ctrl</kbd>+rueda cambian el tamaño de
  letra; <kbd>Ctrl</kbd>+<kbd>0</kbd> lo restablece. El tamaño se guarda.
- La vista se **desplaza** para mantener el cursor visible, como Zed, y se desplaza de lado en las líneas largas
  salvo con *Wrap* activo.

![El archivo entero con dos manejadores plegados y el minimapa](../../../../../screenshots/designer-code-folding.png)

### Teclas en el editor

| Teclas | Acción |
| --- | --- |
| Flechas, <kbd>Inicio</kbd>, <kbd>Fin</kbd> | Mover el cursor. |
| <kbd>Ctrl</kbd>+<kbd>←</kbd> / <kbd>→</kbd> | Mover por palabras. |
| <kbd>Ctrl</kbd>+<kbd>Inicio</kbd> / <kbd>Fin</kbd> | Principio o final del código. |
| <kbd>RePág</kbd> / <kbd>AvPág</kbd> | Una página arriba o abajo. |
| <kbd>Shift</kbd> + cualquiera de las anteriores | Ampliar la selección. |
| <kbd>Ctrl</kbd>+<kbd>A</kbd> | Seleccionar todo. |
| <kbd>Ctrl</kbd>+<kbd>C</kbd> / <kbd>X</kbd> / <kbd>V</kbd> | Copiar, cortar, pegar. |
| <kbd>Tab</kbd> | Sangrar (insertar espacios). |
| <kbd>Ctrl</kbd>+<kbd>Espacio</kbd> | Abrir la lista de sugerencias. |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>[</kbd> / <kbd>]</kbd> | Plegar / desplegar en el cursor. |
| <kbd>Ctrl</kbd>+<kbd>=</kbd> / <kbd>-</kbd> / <kbd>0</kbd> | Letra más grande, más pequeña, por defecto. |
| <kbd>Ctrl</kbd>+<kbd>Z</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd> | Deshacer, rehacer (lo escrito seguido es un solo paso). |
| <kbd>Ctrl</kbd>+<kbd>F</kbd> / <kbd>H</kbd> / <kbd>G</kbd> | Buscar, reemplazar, ir a la línea (ver abajo). |
| <kbd>Esc</kbd> | Volver a un cursor, cerrar la lista de sugerencias, o salir del editor. |

En macOS, <kbd>Cmd</kbd> funciona donde aquí pone <kbd>Ctrl</kbd>. Los comandos globales del editor
(<kbd>F5</kbd>, <kbd>Ctrl</kbd>+<kbd>S</kbd>, <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd>...) funcionan mientras
escribes; los atajos del lienzo (<kbd>Supr</kbd>, flechas, <kbd>Ctrl</kbd>+<kbd>D</kbd>) no, así que escribir nunca
mueve un control.

## Buscar, reemplazar y varios cursores

![Buscar (Ctrl+F) con cada form.status seleccionado como cursor](../../../../../screenshots/designer-code-multicursor.png)

- <kbd>Ctrl</kbd>+<kbd>F</kbd> abre la barra de búsqueda con la palabra bajo el cursor; las coincidencias se
  resaltan en el código y la barra las cuenta. <kbd>Enter</kbd> o <kbd>F3</kbd> van a la siguiente,
  <kbd>Shift</kbd>+<kbd>F3</kbd> a la anterior y <kbd>Alt</kbd>+<kbd>Enter</kbd> pone un cursor en cada una. Los
  botones distinguen mayúsculas, buscan palabras completas o usan una expresión regular.
- <kbd>Ctrl</kbd>+<kbd>H</kbd> muestra también el campo de reemplazo: **Reemplazar** cambia la coincidencia actual y
  **Reemplazar todo** todas, en un solo paso de deshacer. Con una expresión regular, `\1` en el reemplazo inserta un
  grupo.
- <kbd>Ctrl</kbd>+<kbd>G</kbd> va a una línea (`42`) o a una línea y columna (`42:8`).
- El editor tiene los cursores múltiples y los atajos de edición de Zed: <kbd>Alt</kbd>+clic,
  <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>↑</kbd>/<kbd>↓</kbd>, <kbd>Ctrl</kbd>+<kbd>D</kbd>,
  <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>L</kbd>, <kbd>Alt</kbd>+<kbd>↑</kbd>/<kbd>↓</kbd> para mover líneas,
  <kbd>Ctrl</kbd>+<kbd>/</kbd> para comentar, <kbd>Ctrl</kbd>+<kbd>Z</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd>
  y más. La lista completa está en
  [el componente editor de código](/pyzed/es/components/code/#varios-cursores-y-los-atajos-de-zed) o con
  <kbd>F1</kbd> en el diseñador.

## Autocompletado

![Completando una función del módulo re, con su firma y su docstring](../../../../../screenshots/designer-completion.png)

- La lista se abre mientras escribes un nombre o después de un `.` (no en comentarios ni cadenas), y
  <kbd>Ctrl</kbd>+<kbd>Espacio</kbd> la abre en cualquier sitio. Desactiva *Autocomplete while typing* para abrirla
  solo con las teclas.
- <kbd>↑</kbd>/<kbd>↓</kbd> se mueven (dando la vuelta), <kbd>RePág</kbd>/<kbd>AvPág</kbd> saltan nueve filas,
  <kbd>Enter</kbd> o <kbd>Tab</kbd> insertan, <kbd>Esc</kbd> cierra; un clic también inserta. El pie muestra la
  posición (`3/42`).
- Al seguir escribiendo la lista se filtra: primero los nombres que empiezan por lo escrito, luego los que contienen
  las letras en orden (`gtx` encuentra `get_text`).
- Cada entrada tiene un icono según su tipo y, junto a la lista, un panel con su **firma** y su **documentación**
  (el docstring, como Markdown).

  | Color del icono | Tipo |
  | --- | --- |
  | Morado | Funciones y métodos |
  | Amarillo | Clases, enums, parámetros de tipo |
  | Azul | Variables, atributos y propiedades |
  | Cian | Constantes |
  | Rojo | Módulos |
  | Acento | Controles del formulario |

- Los nombres **privados** (`_cache`) salen atenuados, con un candadito, después de los públicos; los dunders
  (`__init__`) van al final.
- **Auto-import**: elegir un nombre que aún no está importado añade también su `import` al principio del archivo,
  incluso en modo manejador.
- La lista se abre bajo la palabra, o encima cuando hay más sitio ahí.

### Los nombres propios del formulario

El `form` y el `event` de un manejador no tienen un tipo que los servidores puedan leer, así que el editor los
completa por su cuenta:

| Escribes | Obtienes |
| --- | --- |
| `form.` | Todos los controles del formulario, más `title`, `name`, `size`, `window` y `close()`. |
| `form.email.` | Las propiedades de ese control, con sus tipos, más `name`, `type`, `visible`, `enabled`, `show()`, `hide()` y `focus()`. |
| `event.` | `sender`, `name` y `value`. |

![form. completa los controles del propio formulario](../../../../../screenshots/designer-completion-form.png)

## Ayuda contextual

<kbd>Shift</kbd>+<kbd>F1</kbd> abre la [referencia integrada](/pyzed/es/editor/reference/) en el nombre bajo el
cursor: `form.email` o `form.email.text` abre la página del tipo del control, `form` y `event` abren las páginas del
código del formulario, y los nombres de la librería (`pz.text`, `ui.button`, `Theme`) abren su página de la API. Si
no hay coincidencia, busca el nombre en la referencia.

## Diagnósticos y code lens

![Errores en línea, la lista de problemas y code lens](../../../../../screenshots/designer-diagnostics.png)

- **Diagnósticos en línea** (error lens): el problema más grave de cada línea se escribe al final de ella, en rojo
  los errores, en amarillo los avisos y en azul la información.
- **Lista de problemas**: bajo el editor, cada problema con su línea y columna, mensaje y origen (`ruff (F401)`,
  `ty`). Haz clic en uno para saltar a él. El botón de la cabecera muestra los recuentos y oculta o muestra la
  lista.
- **Code lens** al final de cada línea `def` y `class`: cuántas **referencias** tiene (de ty, o contadas por nombre
  con ty apagado), cuántas clases **implementan** una clase y qué eventos **llaman** a un manejador
  (`on sign_in.click`).

## Servidores de lenguaje

Los servidores arrancan en la carpeta del marcador de proyecto más cercano por encima del archivo de código
(`pyproject.toml`, `uv.lock`, `setup.py`, `.git`) y usan su `.venv` (donde `uv sync` instala tus dependencias), o
`$VIRTUAL_ENV`. La carpeta del código y `src/` se añaden como raíces de import, así que una UI en su propia carpeta
resuelve las dos cosas:

```
myapp/
├── pyproject.toml      ← uv add httpx
├── .venv/              ← uv sync
├── src/myapp/
└── ui/
    ├── login.pzform
    ├── login.py        ← import httpx / from helpers import greet / from myapp import api
    └── helpers.py
```

El editor busca `ty` y `ruff` primero en el `.venv` del proyecto, luego junto al editor y luego en el `PATH`.
Instálalos con `uv add --dev ty ruff` en el proyecto, o con `pip install "pyzed-ui[designer]"` junto al editor. Ruff
lee sus reglas de `[tool.ruff]` en `pyproject.toml`.

Con el editor de código abierto, la barra de estado muestra un punto por servidor: verde cuando está **listo**,
amarillo mientras **arranca**, rojo si **falta** o ha fallado. Pasa el ratón para ver los detalles; haz clic para
abrir los ajustes del editor.

```mermaid
sequenceDiagram
    participant E as Editor de código
    participant A as CodeAssist
    participant I as CodeIntel
    participant T as servidor ty
    participant R as servidor ruff
    E->>A: on_change(text), on_cursor(line, col)
    A->>I: update(module, handler, text)
    I->>T: didChange (el módulo entero, con el manejador dentro)
    I->>R: didChange
    T-->>I: publishDiagnostics
    R-->>I: publishDiagnostics
    A->>I: complete(line, col)
    I->>T: textDocument/completion
    T-->>A: items (vía pyzed.post, en el hilo de la UI)
    A->>E: lista, errores en línea, code lens
```

## Ajustes del editor

Los abren el **engranaje** de la cabecera del panel de código, los puntos de los servidores en la barra de estado o
**Ajustes → Editor de código → Ajustes del editor…**. Se guardan por usuario, en el mismo `designer.json` que los
[ajustes del editor](/pyzed/es/editor/settings/). El diálogo está en inglés.

![Ajustes del editor con el estado de los servidores de lenguaje](../../../../../screenshots/designer-editor-settings.png)

| Grupo | Ajuste | Qué hace |
| --- | --- | --- |
| Language servers | **ty**, **ruff** | Enciende o apaga cada servidor. Cada fila muestra su estado y versión. Debajo: la raíz del proyecto y el Python en uso. |
| | **Restart servers** (pie) | Reinicia los dos; úsalo después de `uv sync` o de instalarlos. |
| Appearance | **Theme** | *Same as the designer* (el del editor), o cualquier tema solo para el código. |
| | **Font size** | De 8 a 32 (también <kbd>Ctrl</kbd>+<kbd>=</kbd>/<kbd>-</kbd>/<kbd>0</kbd> y <kbd>Ctrl</kbd>+rueda). |
| | **Line numbers**, **Highlight current line** | El margen y la franja de la línea actual. |
| | **Show whitespace** | Espacios como `·`, tabuladores como `→`. |
| | **Wrap long lines** | Ajuste de línea en lugar de desplazamiento horizontal. |
| | **Minimap** | El código en miniatura a la derecha. |
| Cursor | **Shape** | Barra, bloque, subrayado o hueco (Bar, Block, Underline, Hollow), como Zed. |
| | **Blink** | Si el cursor parpadea. |
| Editing | **Tab size** | De 1 a 8 espacios por nivel. |
| | **Autocomplete while typing** | Apagado: la lista solo se abre con <kbd>Ctrl</kbd>+<kbd>Espacio</kbd>. |
| | **Auto-close brackets and quotes** | Parejas, envolver la selección y saltar el cierre. |
| | **Code folding** | Los chevrons y las teclas de plegado. |
| | **Format with ruff on Apply** | Ejecuta `ruff format` sobre el código al pulsar Apply. |
| | **Match brackets** | Remarca el corchete pareja del que está junto al cursor (<kbd>Ctrl</kbd>+<kbd>M</kbd> salta a él). |
| | **Highlight selection matches** | Resalta los demás sitios con el texto seleccionado. |
| Code lens and diagnostics | **Code lens** | Referencias, implementaciones y eventos conectados al final de las definiciones. |
| | **Inline diagnostics** | Problemas al final de la línea. |
