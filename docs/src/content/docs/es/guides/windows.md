---
title: Varias ventanas
description: "Varias ventanas en Pyzed: abre, cierra, mueve, redimensiona y controla ventanas de escritorio nativas desde Python con pz.Window, cada una con su tema."
sidebar:
  order: 6
---

Una app puede tener tantas ventanas como quieras. La ventana principal es tu `App`; las demás son
subclases de `pz.Window`, cada una con su `view()`, título, tamaño y tema.

![Varias ventanas](../../../../assets/tutorials/multi-window.png)

```python
import pyzed as pz
from pyzed import ui


class Settings(pz.Window):
    title = "Ajustes"
    size = (420, 300)
    theme = "One Light"                # opcional: por defecto usa el de la app

    def view(self):
        return pz.container(
            pz.column([
                ui.heading("Ajustes", level=2),
                ui.field("Autoguardado", ui.switch(self.app.autosave, self.app.set_autosave)),
                ui.button("Cerrar", self.close),
            ], spacing=12),
            padding=20,
        )


class Main(pz.App):
    def __init__(self):
        self.autosave = True
        self.settings = Settings()

    def set_autosave(self, value):
        self.autosave = value

    def open_settings(self):
        if not self.settings.is_open:
            return self.settings.open()
        return pz.Command.focus_window(self.settings)

    def view(self):
        return pz.center(ui.button("Abrir ajustes", self.open_settings, icon="settings"))


pz.run(Main)
```

## Cómo funciona

```mermaid
flowchart LR
    subgraph APP["App (estado compartido)"]
        ST[("self.*")]
    end
    M["Ventana principal"] -->|view| ST
    W1["Window A"] -->|"view / self.app"| ST
    W2["Window B"] -->|"view / self.app"| ST
    M -->|"return Window().open()"| W1
    W1 -->|"eventos"| U["update()"]
    W2 -->|"eventos"| U
    M -->|"eventos"| U
    U --> ST
```

- `ventana.open()` (o `Command.open_window(ventana)`) devuelve el comando que la abre.
- `self.app` apunta a la app dentro de cada ventana, así que **comparten estado**: los callbacks
  como `self.app.guardar` funcionan directamente.
- Los mensajes que se producen en una ventana van a su `update()`, que por defecto los reenvía a
  `app.update()`.
- `ventana.is_open` indica si está abierta. Cerrar la ventana principal termina la app.

## Opciones

Atributos de clase o de instancia:

| Atributo | Descripción |
| --- | --- |
| `title` | Texto o callable. |
| `size`, `min_size`, `max_size` | Tamaños en píxeles lógicos. |
| `position` | `"center"` o `(x, y)`. |
| `resizable`, `decorations` | `decorations=False` quita el marco del sistema por completo. |
| `frame` | `"custom"` dibuja la barra de título, los botones de ventana y los menús en Pyzed (ver [Marcos de ventana](#marcos-de-ventana-tu-propia-barra-de-título)). |
| `transparent`, `maximized`, `fullscreen` | Estado inicial. |
| `scale` | Escala de la interfaz. |
| `theme` | Un `Theme`, un nombre o `themes.auto(...)`. `None` usa el de la app. |
| `transition`, `exit_transition` | Cómo se anima al abrirse y al cerrarse: `"fade"`, `"zoom"`, `"pop"`, `"slide_up"`... un preset o una `pz.Animation`. Ver [Animación](/pyzed/es/guides/animation/#transiciones-de-ventana). |

`window_size` contiene el tamaño actual y `window_position` dónde está la ventana en la pantalla (los actualiza el runtime; la posición es `None` en Wayland). `window_maximized` y `window_focused` dicen si está maximizada y si tiene el foco del teclado.

## Ganchos

| Método | Cuándo se llama |
| --- | --- |
| `on_open()` | Al abrirse. |
| `on_close()` | Cuando el usuario pide cerrarla. Devuelve `False` para mantenerla abierta (por ejemplo, para preguntar si guardar). |
| `on_resize(ancho, alto)` | Al cambiar de tamaño. |
| `on_key(combo)` | Teclas pulsadas con esa ventana enfocada. |

## Comandos de ventana

Todos aceptan la ventana como último argumento; sin él actúan sobre la ventana que produjo el
mensaje.

| Comando | Efecto |
| --- | --- |
| `Command.open_window(w)` / `w.open()` | Abre la ventana. |
| `Command.close_window(w)` / `w.close()` | La cierra. |
| `Command.drag_window(w)` / `w.drag()` | Empieza a moverla con el ratón (para barras de título propias). |
| `Command.minimize_window(w)` / `w.minimize()` | La minimiza. |
| `Command.toggle_maximize_window(w)` / `w.toggle_maximize()` | Maximiza o restaura. |
| `Command.maximize_window(True, w)` | La maximiza (`False` la restaura). |
| `Command.drag_resize_window("se", w)` | Empieza a cambiar su tamaño desde un borde o una esquina (para marcos propios). |
| `Command.show_window_menu(w)` | Muestra el menú de ventana del sistema (solo Windows). |
| `Command.set_fullscreen(True, w)` | Pantalla completa. |
| `Command.resize_window(ancho, alto, w)` | Cambia el tamaño. |
| `Command.move_window(x, y, w)` | La mueve. |
| `Command.focus_window(w)` | La trae al frente. |

### Marcos de ventana: tu propia barra de título

`frame = "custom"` cambia el marco del sistema por uno dibujado por Pyzed, como el de Zed: una barra de título
que mueve la ventana (doble clic la maximiza), los botones de minimizar, maximizar y cerrar con el estilo del
sistema, menús a la izquierda y bordes que cambian el tamaño de la ventana. `frame_menus()` devuelve los menús.

![Marcos de ventana de cada plataforma](../../../../assets/tutorials/window-frames.png)

```python
class Notas(pz.App):
    title = "Notas"
    frame = "custom"          # o "macos", "windows", "gnome", "ubuntu", "kde"

    def frame_menus(self):
        return [
            ui.Menu("Archivo", [ui.MenuItem("Abrir…", self.abrir, keys="ctrl-o"), ui.SEPARATOR,
                                ui.MenuItem("Salir", self.close)]),
            ui.Menu("Editar", [ui.MenuItem("Deshacer", self.deshacer, keys="ctrl-z")]),
        ]

    def view(self):
        return self.editor()
```

Los menús quedan tras un botón ☰, como en Zed: un clic abre el primero y muestra el nombre de todos, y al
pasar el puntero a otro nombre se abre ese. Para poner más cosas en la barra (un selector de proyecto, un botón
Ejecutar), llama tú a `ui.window_frame` en `view()`; así la ventana no se enmarca dos veces:

```python
def view(self):
    return ui.window_frame(
        self.editor(),
        menus=self.frame_menus(),
        start=[ui.title_button("pyzed", chevron=True)],
        end=[ui.button("Ejecutar", self.ejecutar, icon="play", size="sm")],
    )
```

| Valor de `frame` | Qué obtienes |
| --- | --- |
| `None` (por defecto) o `"system"` | El marco del sistema. |
| `"custom"` o `True` | La barra de título de Pyzed con los botones del sistema. En macOS el sistema sigue dibujando sus semáforos sobre la barra. |
| `"macos"`, `"windows"`, `"gnome"`, `"ubuntu"`, `"kde"` | Los botones de esa plataforma en cualquier sistema. |

`window_maximized` y `window_focused` dicen si la ventana está maximizada y tiene el foco (los actualiza el
runtime), así que el botón de maximizar muestra el símbolo de restaurar y la barra se atenúa en segundo plano.
Maximizada, la ventana no tiene borde para cambiar su tamaño.

Las piezas también funcionan por separado: `ui.window_title_bar` es la barra sola (sin callbacks solo se
muestra, que es como Pyzed Design previsualiza los formularios), `ui.window_controls` los tres botones y
`pz.window_edges` los bordes que cambian el tamaño de una ventana sin decoraciones. Para una barra hecha desde
cero, usa los comandos `Command.drag_window`, `Command.drag_resize_window`, `Command.toggle_maximize_window` y
`Command.show_window_menu`.

**Notas por plataforma.** En Windows la ventana conserva la sombra y las esquinas redondeadas del sistema.
Wayland mueve y redimensiona la ventana igual que X11 (lo hace el compositor). En WSL Pyzed usa X11 y
`"custom"` dibuja botones de Windows, el escritorio donde aparece la ventana. `ui.system_platform()` dice qué
estilo elige `"custom"`.

### Pestañas arrastrables y ventanas desprendibles

Las pestañas de `ui.tab_bar` se pueden arrastrar. `on_drag(id)` avisa de que empezó un arrastre; mientras
`dragging` nombra la pestaña, `on_drag_over(index)` informa del punto de inserción bajo el puntero (o `None`
fuera de la fila) y `drop_index` dibuja la marca ahí. `on_drop(id, event)` llega al soltarla, con el puntero en la
ventana (`event.window_x`, `event.window_y`, fuera de ella si se soltó fuera) y en la pantalla (`event.screen`).
El `window_position` y el `window_size` de cada ventana dicen dónde está, así que puedes abrir la pestaña en una
ventana nueva o apilarla en la ventana que hay bajo el puntero:

```python
class Detached(pz.Window):
    size = (640, 420)

    def __init__(self, name, position):
        self.name = self.title = name
        if position is not None:
            self.position = position

    def view(self):
        return ui.tab_bar([ui.Tab.for_file(self.name)], self.name)


class Editor(pz.App):
    def __init__(self):
        self.files, self.active = ["main.py", "app.py", "README.md"], "main.py"
        self.dragging, self.over = None, None

    def start(self, name):
        self.dragging = name

    def hover(self, index):
        self.over = index

    def drop(self, name, event):
        over, self.dragging, self.over = self.over, None, None
        if over is not None:  # soltada en la fila: reordenar
            i = self.files.index(name)
            self.files.insert(over - (over > i), self.files.pop(i))
            return None
        width, height = self.window_size or self.size
        if 0 <= event.window_x < width and 0 <= event.window_y < height:
            return None  # soltada dentro de la ventana, fuera de la fila
        self.files.remove(name)
        self.active = self.files[0] if self.files else None
        where = (event.screen_x - 80, event.screen_y - 12) if event.screen else None
        return Detached(name, where).open()

    def view(self):
        return ui.tab_bar([ui.Tab.for_file(f) for f in self.files], self.active,
                          on_select=lambda f: setattr(self, "active", f),
                          on_drag=self.start, on_drop=self.drop, on_drag_over=self.hover,
                          dragging=self.dragging, drop_index=self.over)
```

Para apilar una pestaña en otra de tus ventanas, compara `event.screen` con el `window_position` y el
`window_size` de esa ventana. Wayland no les dice a las apps dónde están sus ventanas: ahí `event.screen` y
`window_position` son `None`, así que ofrece también un comando de menú (Pyzed Design tiene **Mover la pestaña a
una ventana nueva** y **Mover la pestaña a la ventana principal**).

:::note
`pz.run()` solo puede llamarse una vez por proceso (limitación de winit). Para más ventanas,
usa `pz.Window`.
:::
