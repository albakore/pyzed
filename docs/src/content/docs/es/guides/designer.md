---
title: Diseñador visual
description: Crea ventanas arrastrando componentes, conecta sus eventos a Python y ejecútalas, como en Visual Basic o Qt Designer.
sidebar:
  order: 13
---

Pyzed Designer es un editor de formularios al estilo de Visual Basic, el diseñador de WinForms de Visual Studio y
Qt Designer, hecho con el propio Pyzed. Dibujas la ventana con el ratón, ajustas propiedades en una grilla, haces
doble clic en un control para escribir el código de su evento y pulsas **F5** para ejecutarla con toda su lógica.

```bash
pyzed design login.pzform      # abre (o crea) un formulario
pyzed run login.pzform         # lo ejecuta, sin el diseñador
pyzed run login.pzform --reload  # ...y lo actualiza cada vez que se guarda el formulario o su código
```

![El diseñador con el ejemplo de inicio de sesión](../../../../../screenshots/designer.png)

## La ventana

| Zona | Qué hace |
| --- | --- |
| **Toolbox** (izquierda) | La biblioteca de componentes. Haz clic en uno y luego en el formulario para colocarlo con su tamaño por defecto, o arrastra un rectángulo para darle tamaño. La búsqueda filtra la lista. |
| **Outline** (izquierda) | Todos los controles en árbol: los contenedores muestran sus hijos (se pliegan con la flecha). Clic para seleccionar; el ojo y el candado ocultan o bloquean un control, **+** añade un control dentro de un contenedor y el clic derecho abre un menú. |
| **Formulario** (centro) | La superficie de diseño con grilla de puntos. Arrastra para mover, usa las ocho asas para redimensionar y arrastra en un hueco para seleccionar con un rectángulo. El tirador de la esquina inferior derecha cambia el tamaño del formulario. |
| **Properties** (derecha) | Nombre y luego las propiedades en secciones plegables: los grupos propios del componente, posición (X, Y, tamaño, anclajes, o crecer y columnas dentro de un flex o una grilla) y comportamiento (visible, habilitado, bloqueado). Sin selección edita el formulario: título, tamaño, tema, acento, fondo, radio de esquinas, tamaño de letra y grilla. |
| **Events** (derecha) | Los eventos del control seleccionado (o del formulario). Doble clic en uno crea su handler y lo abre en el editor de código. |
| **Código** (abajo) | El código de un handler, o del archivo entero (**F7**). **Apply** comprueba la sintaxis antes de tocar el archivo. |
| **Consola** (abajo) | Lo que imprime el formulario en ejecución, los eventos que atiende y sus errores (ver [Consola de depuración](#consola-de-depuración)). |

La barra de título tiene el menú principal (☰: Archivo y Ejecutar), **Ejecutar** y **Detener**, los menús **Ver** y
**Ayuda** y el engranaje de **Ajustes**. Cada panel se puede mover a otro dock y cada dock cambiar de tamaño; ver
[Paneles](#paneles).

![Escribiendo el código del clic de un botón](../../../../../screenshots/designer-code.png)

## Alineación, grilla y snapping

- **Ajustar a la grilla** (imán) redondea posiciones y tamaños al paso de la grilla (8 px por defecto, configurable
  por formulario). **G** muestra u oculta los puntos.
- **Guías inteligentes** (regla) pegan el control que mueves a los bordes y centros de los demás y del formulario, y
  dibujan una línea roja mientras coinciden.
- La barra de herramientas alinea la selección por bordes **izquierdo, centro, derecho, superior, medio o inferior**,
  **distribuye** tres o más controles por igual, les da el **mismo ancho o alto**, los **centra** en el formulario y
  cambia el **orden Z**. Con un solo control, la alineación es respecto al formulario.
- Los **anclajes** deciden qué pasa al redimensionar la ventana en ejecución, como en WinForms: anclado a izquierda y
  derecha el control se estira, anclado solo a la derecha sigue ese borde, sin anclajes queda centrado.

![Tres controles seleccionados, listos para alinear](../../../../../screenshots/designer-align.png)

### Teclado

| Teclas | Acción |
| --- | --- |
| Arrows / Shift+arrows | Mover 1 px / un paso de grilla |
| Delete | Borrar la selección |
| Ctrl+C, Ctrl+X, Ctrl+V, Ctrl+D | Copiar, cortar, pegar, duplicar |
| Ctrl+A | Seleccionar todo |
| Ctrl+Z, Ctrl+Shift+Z | Deshacer, rehacer |
| Enter | Abrir el código del evento principal del control |
| Escape | Cancelar un arrastre, cerrar un menú, volver al puntero |
| Ctrl+S, Ctrl+Shift+S, Ctrl+O, Ctrl+N, Ctrl+Shift+N | Guardar, guardar como, abrir, nuevo formulario, nuevo componente |
| Ctrl+Shift+P | Paleta de comandos |
| Ctrl+Shift+A | Añadir un control (lista con búsqueda) |
| Ctrl+B, Ctrl+Alt+B, Ctrl+J | Mostrar u ocultar los docks izquierdo, derecho e inferior |
| Ctrl+Shift+Y | Consola |
| Ctrl+, | Ajustes |
| F1 | Atajos de teclado |
| F5, Shift+F5 | Ejecutar el formulario, cerrarlo |
| F7 | Editar el archivo de código completo |
| Ctrl+Espacio | Abrir la lista de autocompletado (en el editor de código) |
| Ctrl+= / Ctrl+- / Ctrl+0, Ctrl+rueda | Fuente más grande, más pequeña o por defecto en el editor de código |
| Ctrl+Shift+[ / Ctrl+Shift+] | Plegar / desplegar el bloque del cursor (en el editor de código) |

Clic derecho en un control abre un menú contextual con las mismas acciones.

## Contenedores y layouts

Algunos componentes contienen otros controles. Suelta un control sobre uno (se ilumina mientras arrastras) para
meterlo dentro, arrástralo fuera para devolverlo al formulario, o selecciona varios y usa **Editar → Agrupar en una
fila / columna / cuadrícula**.

| Contenedor | Cómo coloca a sus hijos |
| --- | --- |
| **Panel**, **Marco**, **Tarjeta** | Libremente, como el formulario: las posiciones son relativas al contenedor y los anclajes siguen sus bordes. |
| **Fila flexible**, **Columna flexible** | Uno tras otro con **separación**, **relleno**, **justificar** (inicio, centro, final, espacio entre) y **alineación** (estirar, inicio, centro, final). **Crecer** en un hijo reparte el espacio libre; un **Espaciador** empuja a los siguientes al final. |
| **Grilla** | En **columnas** del mismo ancho, fila por fila, con **separación** y **alto de fila** (0 reparte el alto). **Columnas** en un hijo lo hace más ancho. |

Los hijos de un flex o una grilla aparecen en su orden en el outline; arrástralos ahí, o en el formulario, para
reordenarlos. Mover o redimensionar un contenedor mueve a sus hijos, y copiar, pegar y borrar los incluyen.

![Un formulario con barra lateral: una columna flexible y sus hijos](../../../../../screenshots/designer-layout.png)

## Menús, ajustes y paleta de comandos

- **☰ (Archivo)**: nuevo formulario, abrir, guardar, guardar como, recientes, ajustes, y Ejecutar, Detener y Editar
  el código.
- **Ver**: la paleta de comandos, los docks, la consola, la barra de herramientas y la de estado, grilla, snapping,
  guías inteligentes, controles ocultos, restablecer los paneles, y dónde está cada panel.
- **Ayuda**: atajos de teclado (con búsqueda), la documentación, informar un problema y Acerca de.
- **Ajustes** (Ctrl+,): tema e idioma del diseñador, barras de herramientas y de estado, valores por defecto del
  lienzo, qué hace Ejecutar (guardar antes, abrir la consola, registrar eventos) y un enlace a los ajustes del editor
  de código. Se guardan en `designer.json`, en la carpeta de ajustes de Pyzed (`PYZED_CONFIG_DIR` la cambia).
- La **paleta de comandos** (Ctrl+Shift+P) ejecuta cualquiera de estas acciones por nombre; **Añadir control**
  (Ctrl+Shift+A) hace lo mismo con los componentes, dentro del contenedor seleccionado.

El idioma del diseñador (inglés o español) sigue al del sistema o al elegido en Ajustes, y usa
[`pz.t`](/pyzed/es/guides/i18n/): añade un catálogo bajo la clave `designer` para traducirlo a otro idioma.

![El menú Ver](../../../../../screenshots/designer-menu.png)

## Paneles

Diseño (herramientas y estructura), Proyecto, Propiedades, Eventos, Código y Consola son paneles en cuatro docks:
izquierdo, derecho, inferior y superior. Cada dock muestra un panel a la vez, con una pestaña por panel. El botón de
dock junto a las pestañas mueve el panel a otro dock, la × oculta el dock (Ctrl+B, Ctrl+Alt+B y Ctrl+J lo vuelven a
mostrar) y el borde que da al formulario lo redimensiona. La disposición se recuerda; **Ver → Restablecer los
paneles** la devuelve a la inicial.

## Consola de depuración

**Ejecutar** (F5) abre el panel Consola, que muestra lo que imprime el formulario, cada evento que atiende con su
valor y el handler que llama, y el traceback de cualquier error, sin salir del diseñador. Filtra por texto, oculta
niveles con los botones, copia todo o límpialo. Los formularios que se ejecutan con `uv run` (un proyecto con
dependencias que el diseñador no tiene) también envían su salida. En Ajustes decides si Ejecutar abre la consola y
si se registran los eventos.

![La consola tras unos clics y un error](../../../../../screenshots/designer-console.png)

## Estética

Cada formulario elige cualquier tema registrado (One, Ayu, Gruvbox o el tuyo) y puede cambiar el color de acento,
el fondo, el radio de las esquinas y el tamaño de letra. El tema del propio diseñador es independiente
(**Ajustes**).

![Un formulario con el tema Gruvbox Light y acento propio](../../../../../screenshots/designer-light.png)

## Archivos

Un formulario son dos archivos juntos, pensados para versionarse:

```
login.pzform   ← diseño: JSON, diffs legibles
login.py       ← handlers de eventos: Python normal
```

```mermaid
flowchart LR
    subgraph Designer["pyzed design"]
        T[Toolbox] --> S[Superficie de diseño]
        S --> P[Properties]
        S --> E[Events]
        E --> C[Editor de código]
    end
    S -- save --> F[(login.pzform)]
    C -- save --> H[(login.py)]
    F --> R["pyzed run / designer.run()"]
    H --> R
    R --> W[Ventana nativa dibujada por Iced]
```

El `.pzform` guarda la configuración del formulario y, por cada control, su tipo, posición, tamaño, propiedades,
anclajes y qué handler llama cada evento:

```json
{
  "format": "pyzed.form/1",
  "form": { "name": "login", "title": "Sign in", "width": 440, "height": 400, "theme": "One Dark", "events": { "load": "form_load" } },
  "controls": [
    { "name": "sign_in", "type": "button", "x": 48, "y": 304, "width": 344, "height": 32,
      "props": { "text": "Sign in", "variant": "solid", "icon": "log-in" },
      "events": { "click": "sign_in_click" }, "anchor": ["left", "top"] }
  ]
}
```

## Cambios en vivo

Los formularios funcionan con hot reload (`pyzed.hot_reload`): ejecútalos con `pyzed run app.pzform --reload` (o
`designer.run(ruta, reload=True)`, o `PYZED_RELOAD=1`) y cada vez que guardes `app.pzform` o `app.py`, desde el
diseñador o desde tu editor, la ventana abierta se actualiza sin reiniciarse. Se reemplazan el diseño, las
propiedades y el código; lo que el usuario escribió o eligió en cada control se mantiene. Dentro del diseñador,
**Guardar** también refresca el formulario abierto con **F5**.

## Escribir handlers de eventos

Los handlers se llaman `<control>_<evento>` y reciben el `form` en ejecución y un `event`. Los controles son
atributos del formulario y sus propiedades atributos del control; al cambiarlas se actualiza la ventana.

```python
def sign_in_click(form, event):
    if "@" not in form.email.text:
        form.status.text = "Enter a valid email address."
        return form.email.focus()          # los handlers pueden devolver comandos
    form.sign_in.enabled = False
    form.progress.show()
    form.ticker.running = True             # un control Timer empieza a contar
```

`event.sender` es el control que lo lanzó, `event.name` el evento y `event.value` su valor (el texto nuevo de una caja
de texto, el estado de una casilla, la combinación de teclas del evento `key` del formulario...). Pueden devolver lo
mismo que cualquier callback de Pyzed: un `Command`, una corrutina, un generador. Si un handler lanza una excepción,
el error aparece abajo en la ventana en vez de cerrarla.

```mermaid
sequenceDiagram
    actor Usuario
    participant Iced as Iced (Rust)
    participant RT as FormRuntime
    participant H as login.py
    Usuario->>Iced: clic en "Sign in"
    Iced->>RT: callback de sign_in.click
    RT->>H: sign_in_click(form, event)
    H->>RT: form.status.text = "..."
    RT->>Iced: view() con las propiedades nuevas
    Iced->>Usuario: redibuja la ventana
```

### Eventos

Todo control visible tiene `mouse_enter`, `mouse_leave` y `right_click`. Además:

| Componente | Eventos |
| --- | --- |
| Button | `click` |
| Label | `click`, `double_click` |
| Text box | `change`, `submit` |
| Text area, Check box, Switch, Radio group, Drop-down, Slider, Number box, List box | `change` |
| Timer (invisible al ejecutar) | `tick` |
| Formulario | `load`, `close` (devuelve `False` para no cerrar), `key`, `resize` |

## Editor de código

El panel de código es un editor de Python respaldado por dos servidores de lenguaje de Astral: **ty** (tipos,
autocompletado, referencias) y **ruff** (lint). Se ejecutan en el proyecto del formulario, así que el
autocompletado conoce tus dependencias.

![Autocompletando una función del módulo re, con su firma y su docstring](../../../../../screenshots/designer-completion.png)

### Autocompletado

- La lista se abre mientras escribes un nombre o después de un `.`, y **Ctrl+Espacio** la abre en cualquier
  lugar. **Arriba**/**Abajo** para moverte, **Enter** o **Tab** para insertar, **Escape** para cerrarla.
- Cada entrada tiene un icono según su tipo y un panel con su firma y su documentación (el docstring):

  | Color del icono | Tipo |
  | --- | --- |
  | Morado | Funciones y métodos |
  | Amarillo | Clases, enums, parámetros de tipo |
  | Azul | Variables, atributos y propiedades |
  | Cian | Constantes |
  | Rojo | Módulos |
  | Acento | Controles del formulario |

  Los nombres privados (`_cache`) se ven atenuados, llevan un candado y van después de los públicos; los dunders
  (`__init__`) van al final.
- `form.` lista los controles del formulario, `form.email.` las propiedades de esa caja de texto y `event.` los
  campos del evento: los completa el propio diseñador, porque el `form` de un handler no tiene un tipo que los
  servidores puedan leer.
- Si eliges un nombre que todavía no está importado (una entrada de *auto-import*), también se añade su `import`
  al principio del archivo.

![form. completa los controles del propio formulario](../../../../../screenshots/designer-completion-form.png)

### Tu proyecto y sus dependencias

Los servidores arrancan en la carpeta del `pyproject.toml` más cercano por encima del formulario (o `uv.lock`,
`setup.py`, `.git`) y usan su `.venv`, que es donde `uv sync` instala tus dependencias (si no, `$VIRTUAL_ENV`). La
carpeta del formulario y `src/` se añaden como raíces de importación, así que una UI en su propia carpeta resuelve
las dos cosas:

```
miapp/
├── pyproject.toml      ← uv add httpx
├── .venv/              ← uv sync
├── src/miapp/
└── ui/
    ├── login.pzform
    ├── login.py        ← import httpx / from helpers import greet / from miapp import api
    └── helpers.py
```

Instala los servidores en el proyecto con `uv add --dev ty ruff`, o junto al diseñador con
`pip install "pyzed-ui[designer]"`. El diseñador los busca primero en el `.venv` del proyecto, después en su propio
entorno y por último en el `PATH`. Ruff lee sus reglas de `[tool.ruff]` en `pyproject.toml`.

```mermaid
sequenceDiagram
    participant E as Editor de código
    participant A as CodeAssist
    participant I as CodeIntel
    participant T as Servidor ty
    participant R as Servidor ruff
    E->>A: on_change(texto), on_cursor(línea, col)
    A->>I: update(módulo, handler, texto)
    I->>T: didChange (módulo entero con el handler dentro)
    I->>R: didChange
    T-->>I: publishDiagnostics
    R-->>I: publishDiagnostics
    A->>I: complete(línea, col)
    I->>T: textDocument/completion
    T-->>A: elementos (con pyzed.post, en el hilo de la UI)
    A->>E: lista, errores en línea, code lens
```

El editor muestra un handler, pero los servidores siempre ven el módulo entero con ese handler dentro, así que
conocen los imports y las funciones auxiliares del principio del archivo; las posiciones se traducen entre ambos.

### Diagnósticos y code lens

![Errores en línea, la lista de problemas y code lens](../../../../../screenshots/designer-diagnostics.png)

- El primer problema de cada línea se muestra al final de la línea (error lens) y todos aparecen en una lista bajo
  el editor; haz clic en uno para ir a él. La cabecera cuenta errores y advertencias.
- El **code lens** al final de cada línea `def` y `class` muestra cuántas referencias tiene (según ty), cuántas
  clases lo implementan y qué eventos lo llaman (`on sign_in.click`).

### Configuración del editor

El botón del engranaje del panel de código (o los puntos de los servidores en la barra de estado) abre la
configuración del editor. Se guarda por usuario en `designer.json`, dentro de la carpeta de configuración de Pyzed
(`%APPDATA%\pyzed`, `~/Library/Application Support/pyzed` o `~/.config/pyzed`).

![Configuración del editor con el estado de los servidores de lenguaje](../../../../../screenshots/designer-editor-settings.png)

| Opción | Qué hace |
| --- | --- |
| Servidores de lenguaje | Activa o desactiva ty y ruff, muestra si cada uno está listo (y su versión), la raíz del proyecto y el Python que se usa. **Restart servers** después de `uv sync`. |
| Tema, tamaño de fuente | El editor puede usar un tema distinto del diseñador. Ctrl+= / Ctrl+- (o Ctrl+rueda) cambian el tamaño y Ctrl+0 lo restablece. |
| Números de línea, resaltar la línea actual, ajuste de línea | Margen y disposición. |
| Mostrar espacios | Dibuja los espacios como `·` y los tabuladores como `→`. |
| Minimapa | El código en miniatura a la derecha; haz clic o arrástralo para desplazarte. |
| Forma del cursor, parpadeo | Barra, bloque, subrayado o hueco, como en Zed. |
| Tamaño de tabulación | Tab inserta espacios, Enter mantiene la sangría (un nivel más después de `:`) y Retroceso quita un nivel. |
| Autocompletar al escribir | Desactivado, la lista solo se abre con Ctrl+Espacio. |
| Cerrar paréntesis y comillas | Escribir `(`, `[`, `{` o una comilla inserta su pareja (o envuelve la selección); escribir el cierre lo salta. |
| Plegado de código | Las flechas del margen pliegan bloques; Ctrl+Shift+[ y Ctrl+Shift+] pliegan y despliegan en el cursor. |
| Formatear con ruff al aplicar | Ejecuta `ruff format` sobre el código al pulsar Apply. |
| Code lens, diagnósticos en línea | Muestran u ocultan las notas al final de las líneas. |

![El archivo completo con dos handlers plegados y el minimapa](../../../../../screenshots/designer-code-folding.png)

## Componentes

**Comunes**: Label, Heading, Button, Text box, Text area, Check box, Switch, Radio group, Drop-down, Slider, Number
box, List box, Link y Search box. **Contenedores**: Panel, Group box, Card. **Layout**: Flex row, Flex column, Grid,
Spacer. **Navegación**: Tab bar, Segmented. **Presentación**: Progress bar, Badge, Chip, Callout, Avatar, Key
binding, Stat, Chart, Table, Image, Icon, Markdown, Spinner, Divider y Timer.

![Todos los componentes incluidos](../../../../../screenshots/designer-components.png)

Para dibujar tus propios componentes, con propiedades, estado, métodos y eventos, usa el
[diseñador de componentes](/pyzed/es/guides/component-designer/). Se suman a esta biblioteca al guardarlos.

Registra los tuyos y aparecen en la toolbox:

```python
from pyzed import ui
from pyzed.designer import Component, Prop, register

register(Component(
    type="rating", label="Rating", icon="star", category="Custom", size=(120, 24),
    props=(Prop("value", "number", 3, min=0, max=5),),
    events=("change",),
    render=lambda control, ctx: ui.label("★" * int(control.props["value"])),
))
```

`render` se usa en el diseñador (inerte) y al ejecutar; usa `ctx.on(control, "change", "value")` para los
callbacks y el mismo código sirve en ambos.

## Formularios desde código

Todo lo que hace el diseñador está disponible desde Python, útil para generar formularios o para tests:

```python
from pyzed import designer
from pyzed.designer import Document

doc = Document(designer.Form(name="hello", title="Hello", width=320, height=140))
doc.add("input", 16, 16, 200, 28)
doc.add("button", 224, 16)
doc.select_all()
doc.align("middle")
handler = doc.wire("button1", "click")
doc.set_handler_source(handler, "def button1_click(form, event):\n    form.button1.text = form.input1.text\n")
doc.save("hello.pzform")

designer.run("hello.pzform")
```

### Formularios nuevos y otras ventanas

**☰ → Nuevo formulario** (Ctrl+N) pide nombre, título y carpeta y ofrece plantillas: en blanco, diálogo (Aceptar
y Cancelar ya conectados), inicio de sesión, barra lateral y ajustes. En código, `designer.new_form(ruta,
template="dialog")` crea el formulario y su módulo de handlers (en un proyecto, `project.find().new_form("settings")`
lo pone en `ui/`), y `designer.register_template(...)` añade tus propias plantillas al diálogo. Desde un handler, `form.open(...)`
abre otro formulario en una ventana nueva; el nombre se busca junto al formulario actual y
luego en la carpeta `ui/` del proyecto. Lo que pases como `data` llega como `form.data`:

```python
designer.new_form("ui/details.pzform", title="Detalles")

def details_button_click(form, event):
    return form.open("details", data=form.order_id.text)

# details.py
def form_load(form, event):
    form.title = f"Pedido {form.data}"
```

`designer.open_window(form_o_ruta, data=...)` devuelve el mismo `Command` desde cualquier app,
y también acepta un `designer.Form` construido en código (con `handlers={"nombre": función}`).

![El diálogo Nuevo formulario con sus plantillas](../../../../../screenshots/designer-new.png)

## Cómo está hecho

```mermaid
classDiagram
    class Form { controls; events; theme; grid }
    class Control { name; type; x; y; width; height; props; events; anchor }
    class Component { type; props; events; render() }
    class Document { form; code; selection; history; add(); align(); wire() }
    class History { push(); undo(); redo() }
    class Designer { pyzed App: docks and gestures }
    class FormRuntime { dispatch(); view() }
    Form "1" *-- "*" Control
    Control ..> Component : type
    Document --> Form
    Document --> History
    Designer --> Document
    FormRuntime --> Form
```

- `model.py`: el formulario y sus controles, guardados como JSON.
- `components.py`: la biblioteca de componentes y el `render` compartido por diseñador y runtime.
- `geometry.py`: snapping, alineación, distribución, redimensionado, anclajes y guías (funciones puras).
- `history.py`: deshacer/rehacer con instantáneas; las ediciones seguidas de un campo cuentan como un paso.
- `code.py`: busca, añade, renombra y reemplaza handlers con `ast` sin tocar el resto del archivo.
- `document.py`: todos los comandos de edición, sin UI, así que se puede testear entero.
- `project_panel.py`: la pestaña Project (proyectos de uv, dependencias, ruff, ty y git; consulta [Proyectos con uv](/pyzed/es/guides/projects/)).
- `surface.py` y `panels.py`: las vistas; `app.py`: la app `Designer` que traduce clics y teclas al documento.
- `scene.py`, `scene_code.py`, `scene_runtime.py` y `scene_panel.py`: el [diseñador de componentes](/pyzed/es/guides/component-designer/)
  (el modelo `.pzcomp`, el código de la clase, `SceneComponent` y el panel Component).
- `runtime.py`: `FormApp` y `FormWindow`, que dibujan un formulario y llaman a sus handlers.
- `lsp.py`: un pequeño cliente JSON-RPC para servidores de lenguaje y la detección del proyecto y su `.venv`.
- `intellisense.py`: `CodeIntel`, que mantiene ty y ruff sincronizados con el handler abierto, y la lógica de
  autocompletado, diagnósticos y code lens (sin UI).
- `code_panel.py`: la vista del editor de código y `CodeAssist`, su estado; `settings.py`: la configuración del editor.
