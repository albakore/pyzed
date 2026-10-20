"""Descripciones en español de la API pública. Las usa gen_api.py.

Cada entrada: ``"pyzed.nombre": {"desc": ..., "params": {...}, "example": ..., "extra": ...}``.
Los parámetros que no aparecen en ``params`` se buscan en ``COMMON``.
"""

COMMON = {
    "content": "Contenido: un `Widget`, un texto o un número (se convierte en texto).",
    "children": "Lista de hijos. Se aplanan listas anidadas y se ignoran `None` y `False`, así que puedes escribir `cond and widget`.",
    "width": 'Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción).',
    "height": 'Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción).',
    "max_width": "Ancho máximo en píxeles.",
    "max_height": "Alto máximo en píxeles.",
    "padding": "Relleno interior: `8`, `(vertical, horizontal)` o `(arriba, derecha, abajo, izquierda)`.",
    "spacing": "Separación entre hijos, en píxeles.",
    "align": 'Alineación de los hijos en el eje cruzado: `"start"`, `"center"` o `"end"`.',
    "align_x": 'Alineación horizontal: `"start"`/`"left"`, `"center"`, `"end"`/`"right"`.',
    "align_y": 'Alineación vertical: `"start"`/`"top"`, `"center"`, `"end"`/`"bottom"`.',
    "clip": "Recorta el contenido que se sale de los límites.",
    "bg": 'Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`).',
    "color": "Color del texto o del icono.",
    "border_color": "Color del borde.",
    "border_width": "Grosor del borde en píxeles.",
    "radius": "Radio de las esquinas: un número o `(sup_izq, sup_der, inf_der, inf_izq)`.",
    "shadow": "Sombra: `(color, (dx, dy), desenfoque)`.",
    "hover_bg": "Fondo al pasar el ratón.",
    "hover_color": "Color del texto al pasar el ratón.",
    "hover_border_color": "Color del borde al pasar el ratón.",
    "pressed_bg": "Fondo mientras se pulsa.",
    "disabled_color": "Color del texto cuando está deshabilitado.",
    "on_press": "Mensaje o callable que se envía al pulsar. `None` deshabilita el control.",
    "theme": "Tema a usar en lugar del actual (`pyzed.theme.current()`).",
    "id": "Identificador estable para enfocarlo o desplazarlo con un `Command`.",
    "icon": "Nombre de un icono de Lucide (`pyzed icons` los lista).",
    "icon_color": "Color del icono: un token del tema o un color hex.",
    "keys": 'Atajo que se muestra al final, escrito como texto: `"ctrl-s"`, `"cmd-k cmd-s"`.',
    "selected": "Lo marca como seleccionado.",
    "disabled": "Lo deshabilita (ignora los clics).",
    "size": "Tamaño.",
    "label": "Texto de la etiqueta.",
    "title": "Título.",
    "on_dismiss": "Mensaje o callable que se envía al cerrar.",
    "actions": "Widgets extra (normalmente botones) que se muestran como acciones.",
    "start": "Widgets al inicio (izquierda).",
    "end": "Widgets al final (derecha).",
    "accent": "Color de acento (parte activa).",
    "knob_color": "Color del tirador.",
    "check_color": "Color de la marca.",
    "text_size": "Tamaño del texto de la etiqueta.",
    "on_toggle": "Callable que recibe el nuevo `bool` (o mensaje que se envía).",
    "on_change": "Callable que recibe el nuevo valor.",
    "on_select": "Callable que recibe el elemento elegido.",
    "on_input": "Callable que recibe el texto nuevo en cada pulsación.",
    "on_submit": "Mensaje o callable que se envía al pulsar Enter.",
    "placeholder": "Texto de ayuda cuando está vacío.",
    "on_close": "Mensaje o callable que se envía al pulsar la X.",
    "checked": "Estado actual.",
    "value": "Valor actual.",
    "variant": "Variante visual.",
    "tint": 'Color semántico: `"accent"`, `"error"`, `"warning"`, `"success"`, `"info"` o un token.',
    "app": "Una instancia de `App` (o la clase, que se instancia sin argumentos).",
    "path": "Ruta del archivo.",
    "mono": "Usa la fuente monoespaciada (IBM Plex Mono).",
    "indent": "Sangría a la izquierda, en píxeles.",
    "item_height": "Alto de cada fila.",
    "message": "Cualquier valor de Python, o un callable.",
}

_SIZES = '`"xs"`, `"sm"`, `"md"` o `"lg"`.'

PAGES = [
    # ------------------------------------------------------------------ App
    {
        "slug": "app",
        "title": "App y ejecución",
        "description": "Referencia de la API de pyzed.App: la clase de aplicación, run, screenshot, post, load_font y las opciones de ventana de una app de escritorio.",
        "order": 1,
        "intro": """
            Todo lo que necesitas para arrancar una aplicación. Ver también la guía de
            [arquitectura](/pyzed/es/guides/architecture/).
        """,
        "sections": [
            ("Aplicación", {
                "pyzed.App": {
                    "desc": """
Clase base de las aplicaciones (arquitectura Elm, como Iced). Sobrescribe `view()` y, si usas
mensajes, `update(message)`. El estado vive en atributos de la instancia.

| Atributo de clase | Por defecto | Descripción |
| --- | --- | --- |
| `title` | `"Pyzed"` | Título de la ventana. Puede ser un callable (o propiedad) que devuelva el texto. |
| `size` | `(1280, 800)` | Tamaño inicial de la ventana. |
| `min_size` | `None` | Tamaño mínimo. |
| `resizable` | `True` | Si se puede redimensionar. |
| `decorations` | `True` | Muestra el marco y los botones del sistema. |
| `scale` | `1.0` | Factor de escala de toda la interfaz. |
| `font_size` | `14` | Tamaño de texto por defecto. |
| `theme` | `themes.ONE_DARK` | Tema actual. Cámbialo en cualquier momento. |

| Método | Descripción |
| --- | --- |
| `view()` | Devuelve el árbol de widgets. Se llama después de cada mensaje. |
| `update(message)` | Recibe los mensajes. Puede devolver un `Command`, una lista de ellos u otro mensaje. |
| `on_start()` | Opcional. Se ejecuta una vez al arrancar; puede devolver un `Command`. |
| `on_key(combo)` | Opcional. Recibe cada tecla como `"ctrl-shift-p"`, `"escape"`, `"up"`… |
| `on_key_up(key)` | Opcional. Recibe las teclas al soltarlas, por nombre (`"left"`, `"space"`). |
| `run()` | Abre la ventana y bloquea hasta que se cierra. |
| `screenshot(path, *, size=None, scale=2.0, wait=0.1)` | Renderiza el estado actual a un PNG sin ventana. |

Si `view()` lanza una excepción, la ventana muestra el traceback en lugar de cerrarse.
""",
                    "no_signature": True,
                },
                "pyzed.run": {
                    "desc": "Ejecuta una app: abre la ventana y bloquea hasta que se cierra. Acepta la clase o una instancia.",
                },
                "pyzed.screenshot": {
                    "desc": "Renderiza `app` fuera de pantalla (sin ventana ni GPU) y guarda un PNG. Útil para tests y documentación.",
                    "params": {
                        "path": "Ruta del PNG de salida.",
                        "size": "Tamaño lógico `(ancho, alto)`. Por defecto, `app.size`.",
                        "scale": "Factor de escala del PNG (2.0 = retina).",
                        "wait": "Segundos que se esperan antes de capturar (para tareas de `on_start`).",
                    },
                    "example": """
                        pz.screenshot(MiApp, "docs/ui.png", size=(800, 600))
                    """,
                },
                "pyzed.post": {
                    "desc": "Envía un mensaje a la app en ejecución desde **cualquier hilo**. Lanza `RuntimeError` si no hay ninguna app corriendo.",
                    "example": """
                        def worker():
                            for i in range(100):
                                time.sleep(0.05)
                                pz.post(("progress", i / 100))

                        threading.Thread(target=worker, daemon=True).start()
                    """,
                },
                "pyzed.load_font": {
                    "desc": 'Carga una fuente extra (ruta a un `.ttf`/`.otf` o sus bytes) para usarla por su nombre de familia: `text("hola", font="JetBrains Mono")`.',
                    "params": {"source": "Ruta del archivo de fuente o `bytes`."},
                },
            }),
        ],
    },
    # ------------------------------------------------------------- Command
    {
        "slug": "command",
        "title": "Command",
        "description": "Referencia de la API de los comandos de Pyzed: los efectos que devuelven update y los callbacks, como enfocar campos, cerrar y tareas en segundo plano.",
        "order": 2,
        "intro": """
            Un `Command` es un efecto que el runtime ejecuta por ti. Devuélvelo desde `update`,
            `on_start`, `on_key` o cualquier callback. También puedes devolver una lista o una
            tupla de comandos. Ver la guía de [comandos y tareas](/pyzed/es/guides/commands/).

            ```python
            from pyzed import Command

            def on_key(self, combo):
                if combo == "ctrl-p":
                    self.finder_open = True
                    return Command.focus("finder")
            ```
        """,
        "sections": [
            ("Métodos estáticos", {
                "pyzed.Command": {
                    "desc": "La clase de los comandos. No se instancia directamente: usa sus métodos estáticos.",
                    "no_signature": True,
                },
                "pyzed.Command.exit": {"desc": "Cierra la aplicación."},
                "pyzed.Command.focus": {
                    "desc": "Enfoca el `text_input` (o editor) con ese `id`.",
                    "params": {"id": "El `id` que pasaste al widget."},
                },
                "pyzed.Command.focus_next": {
                    "desc": "Mueve el foco del teclado al siguiente campo de la ventana, volviendo al primero tras el último (lo que hace Tab).",
                },
                "pyzed.Command.focus_previous": {
                    "desc": "Mueve el foco del teclado al campo anterior de la ventana (lo que hace Shift+Tab).",
                },
                "pyzed.Command.select_all": {
                    "desc": "Da el foco al `text_input` con ese `id` y selecciona todo su texto (lo que se escriba lo reemplaza).",
                    "params": {"id": "El `id` del campo."},
                },
                "pyzed.Command.set_editor_text": {
                    "desc": "Reemplaza el contenido del `code_editor` con ese `id`. Los editores no son controlados: `text` solo es el valor inicial.",
                    "params": {"id": "El `id` del editor.", "text": "El texto nuevo."},
                },
                "pyzed.Command.set_editor_cursor": {
                    "desc": "Mueve el cursor del editor (línea y columna empiezan en 1). Funciona aunque el editor aún no se haya dibujado.",
                    "params": {"id": "El `id` del editor.", "line": "Línea (desde 1).", "column": "Columna (desde 1)."},
                },
                "pyzed.Command.fold_all": {
                    "desc": "Pliega todos los bloques del editor (`fold=False` los despliega). Funciona aunque el editor aún no se haya dibujado.",
                    "params": {"id": "El `id` del editor.", "fold": "`True` para plegar, `False` para desplegar."},
                },
                "pyzed.Command.fold_line": {
                    "desc": "Pliega (o despliega) el bloque que empieza en `line`, según la sangría. Funciona aunque el editor aún no se haya dibujado.",
                    "params": {"id": "El `id` del editor.", "line": "Línea (desde 1) donde empieza el bloque.",
                               "fold": "`True` para plegar, `False` para desplegar."},
                },
                "pyzed.Command.editor_action": {
                    "desc": "Ejecuta una acción del editor con ese `id`, como si se pulsara su atajo: el nombre de la acción de Zed en snake case (`\"undo\"`, `\"select_next\"`, `\"move_line_up\"`, `\"toggle_comments\"`…). Lanza `ValueError` si el nombre no existe.",
                    "params": {"id": "El `id` del editor.", "name": "El nombre de la acción (`Command.editor_actions()` las lista; también vale `\"editor::SelectNext\"`)."},
                },
                "pyzed.Command.editor_actions": {
                    "desc": "Los nombres que acepta `Command.editor_action`.",
                },
                "pyzed.Command.select_editor_ranges": {
                    "desc": "Selecciona rangos del editor, un cursor por rango; el primero es el cursor principal. Despliega lo que los oculta y funciona aunque el editor aún no se haya dibujado.",
                    "params": {"id": "El `id` del editor.", "ranges": "`[(línea, columna, línea_final, columna_final)]`, desde 1, con el final excluido (un rango vacío es un cursor sin selección)."},
                },
                "pyzed.Command.replace_editor_ranges": {
                    "desc": "Reemplaza rangos del editor por textos en un solo paso de deshacer y llama al `on_change` del editor (buscar y reemplazar).",
                    "params": {"id": "El `id` del editor.", "edits": "`[((línea, columna, línea_final, columna_final), texto)]`, desde 1, con el final excluido."},
                },
                "pyzed.Command.scroll_to_end": {
                    "desc": "Desplaza el `scrollable` con ese `id` hasta el final.",
                    "params": {"id": "El `id` del scrollable."},
                },
                "pyzed.Command.batch": {
                    "desc": "Ejecuta varios comandos.",
                    "params": {"commands": "Lista de `Command`."},
                },
                "pyzed.Command.message": {
                    "desc": "Vuelve a enviar `message` a `update` en el siguiente ciclo.",
                },
                "pyzed.Command.perform": {
                    "desc": "Ejecuta `function()` en un hilo en segundo plano y entrega el resultado a `then(resultado)` en el hilo de la interfaz. Sin `then`, el resultado se envía a `update`. Si `function` lanza, se imprime el error.",
                    "params": {
                        "function": "Función sin argumentos que hace el trabajo lento.",
                        "then": "Callable que recibe el resultado (o `None` para enviarlo a `update`).",
                    },
                    "example": """
                        def cargar(self):
                            self.cargando = True
                            return Command.perform(lambda: requests.get(URL).json(), self.recibido)

                        def recibido(self, datos):
                            self.cargando, self.datos = False, datos
                    """,
                },
            }),
        ],
    },
    # ------------------------------------------------------------- Widgets
    {
        "slug": "widgets",
        "title": "Widgets base",
        "description": "Referencia de la API de los widgets nativos de Pyzed: layout, texto, controles, el editor de código, SVG e iconos, renderizados en Rust por Iced.",
        "order": 3,
        "intro": """
            Los widgets base están implementados en Rust y se importan desde `pyzed`. Son los
            ladrillos con los que están hechos los [componentes](/pyzed/es/components/overview/).
            Ver la guía de [layout](/pyzed/es/guides/layout/) para los tamaños, el relleno y los colores.
        """,
        "sections": [
            ("Widget", {
                "pyzed.Widget": {
                    "desc": "Un nodo inmutable del árbol de la interfaz, implementado en Rust. Lo devuelven todas las funciones de widgets y componentes. Donde se espera un hijo también puedes pasar un texto o un número (se convierte en `text`) o `None` (se ignora).\n\nTodo widget tiene `widget.on(...)` (ver [Eventos](/pyzed/es/guides/events/)) y `widget.style(*estilos, **props)`, que le da estilo como CSS: fondo, bordes, radio, sombra, padding, margen, tamaño y la tipografía de todos los textos de dentro. `widget.style_props()` devuelve lo que se fijó. Ver [Estilos](/pyzed/es/theming/styles/).\n\n`widget.animate(*animaciones, **opciones)` reproduce presets o animaciones por keyframes (al aparecer, en hover, al pulsar, con foco, al hacer clic o mientras `active`) y `widget.transition(**props)` anima los cambios de propiedades como una transición CSS. Ver [Animación](/pyzed/es/guides/animation/).",
                    "no_signature": True,
                },
            }),
            ("Layout", {
                "pyzed.column": {
                    "desc": "Apila los hijos en vertical.",
                    "example": 'pz.column([pz.text("Uno"), pz.text("Dos")], spacing=8, padding=16)',
                },
                "pyzed.row": {
                    "desc": "Coloca los hijos en horizontal.",
                    "example": 'pz.row([ui.label("Nombre"), pz.hspace(), ui.button("OK", "ok")], align="center")',
                },
                "pyzed.container": {
                    "desc": "Envuelve un hijo para darle tamaño, alineación, fondo, borde, radio y sombra.",
                    "params": {
                        "content": "El hijo (o `None` para una caja vacía, útil como rectángulo de color).",
                        "center": "Centra el contenido en ambos ejes y ocupa todo el espacio.",
                    },
                },
                "pyzed.center": {
                    "desc": "Centra `content` en todo el espacio disponible. Equivale a `container(content, center=True)`.",
                    "params": {"kwargs": "Cualquier parámetro de `container`."},
                },
                "pyzed.scrollable": {
                    "desc": "Hace desplazable su contenido.",
                    "params": {
                        "direction": '`"vertical"`, `"horizontal"` o `"both"`.',
                        "anchor_bottom": "Mantiene el scroll pegado al final (logs, terminales, chats).",
                        "rail": "Color del carril de la barra.",
                        "scroller": "Color del tirador.",
                        "scroller_hover": "Color del tirador al pasar el ratón.",
                        "scrollbar_width": "Ancho de la barra.",
                        "scroller_width": "Ancho del tirador (por defecto, el de la barra).",
                        "margin": "Margen entre la barra y el contenido.",
                    },
                },
                "pyzed.stack": {
                    "desc": "Superpone los hijos, el último encima. Base de capas, modales y notificaciones.",
                },
                "pyzed.space": {
                    "desc": "Espacio vacío de un tamaño dado.",
                },
                "pyzed.hspace": {
                    "desc": 'Hueco horizontal flexible: empuja a los hermanos de una fila hacia los extremos.',
                },
                "pyzed.vspace": {
                    "desc": "Hueco vertical flexible: empuja a los hermanos de una columna hacia los extremos.",
                },
                "pyzed.rule": {
                    "desc": "Una línea divisoria horizontal (o vertical).",
                    "params": {"vertical": "Línea vertical en lugar de horizontal.", "thickness": "Grosor en píxeles."},
                    "extra": 'Una regla horizontal ocupa todo el ancho. Dentro de una columna que debe encoger, pon `width="shrink"` en la columna.',
                },
            }),
            ("Texto e iconos", {
                "pyzed.text": {
                    "desc": "Un texto.",
                    "params": {
                        "size": "Tamaño de la fuente.",
                        "font": '`"sans"` (IBM Plex Sans), `"mono"`, `"icons"`, `"serif"` o el nombre de una familia cargada con `load_font`.',
                        "weight": '`"thin"`, `"light"`, `"normal"`, `"medium"`, `"semibold"`, `"bold"`, `"black"` o un número (100–900).',
                        "italic": "Cursiva.",
                        "line_height": "Alto de línea relativo al tamaño (1.0, 1.5…).",
                        "wrap": "Ajuste de línea. Con `False` el texto no se parte.",
                    },
                },
                "pyzed.icon": {
                    "desc": "Un icono de [Lucide](https://lucide.dev). `color` por defecto es el color del texto que lo rodea.",
                    "params": {"name": "Nombre del icono (`pyzed icons` los lista).", "size": "Tamaño en píxeles.", "color": "Color."},
                    "example": 'pz.icon("folder", size=16, color="#74ade8")',
                },
                "pyzed.svg": {
                    "desc": "Una imagen SVG.",
                    "params": {
                        "source": "Ruta a un `.svg`, el código SVG como texto (empieza por `<`) o `bytes`.",
                        "color": "Si se indica, tiñe todo el SVG de ese color (útil para iconos monocromos).",
                    },
                },
            }),
            ("Interacción", {
                "pyzed.button": {
                    "desc": "Un botón sin estilo predefinido. Para el botón con tema usa `ui.button`.",
                    "params": {"content": "Contenido del botón."},
                },
                "pyzed.text_input": {
                    "desc": "Un campo de texto controlado: muestra `value` y te avisa de los cambios con `on_input`. Para el campo con tema usa `ui.input`.",
                    "params": {
                        "value": "Texto actual.",
                        "size": "Tamaño de la fuente.",
                        "font": "Familia de la fuente.",
                        "secure": "Oculta el texto (contraseñas).",
                        "icon": "Carácter del icono (usa `pyzed.icons.glyph(nombre)`).",
                        "icon_size": "Tamaño del icono.",
                        "focus_border_color": "Color del borde con el foco.",
                        "placeholder_color": "Color del placeholder.",
                        "selection_color": "Color de la selección.",
                        "icon_color": "Color del icono.",
                    },
                },
                "pyzed.mouse_area": {
                    "desc": "Detecta eventos del ratón sobre su contenido.",
                    "params": {
                        "on_press": "Clic izquierdo (al pulsar).",
                        "on_release": "Al soltar el botón izquierdo.",
                        "on_right_press": "Clic derecho (menús contextuales).",
                        "on_double_click": "Doble clic.",
                        "on_enter": "El ratón entra.",
                        "on_exit": "El ratón sale.",
                        "cursor": '`"pointer"`, `"text"`, `"grab"`, `"grabbing"`, `"crosshair"`, `"not-allowed"`, `"resize-horizontal"`, `"resize-vertical"`, `"move"` o `"default"`.',
                    },
                },
                "pyzed.hover": {
                    "desc": "Muestra `top` encima de `base` solo mientras el ratón está encima (por ejemplo, el botón de cerrar de una pestaña).",
                    "params": {"base": "Widget de abajo.", "top": "Widget que aparece al pasar el ratón."},
                },
                "pyzed.opaque": {
                    "desc": "Hace que un widget bloquee el ratón para lo que está debajo en un `stack`.",
                },
                "pyzed.tooltip": {
                    "desc": "Muestra `tip` junto a `content` al pasar el ratón. `ui.tooltip` añade el estilo del tema.",
                    "params": {
                        "tip": "Contenido del tooltip.",
                        "position": '`"top"`, `"bottom"`, `"left"`, `"right"` o `"cursor"`.',
                        "gap": "Distancia al contenido.",
                    },
                },
            }),
            ("Controles", {
                "pyzed.checkbox": {"desc": "Una casilla de verificación.", "params": {"size": "Tamaño de la casilla."}},
                "pyzed.toggler": {"desc": "Un interruptor encendido/apagado.", "params": {"size": "Alto del interruptor."}},
                "pyzed.slider": {
                    "desc": "Un deslizador entre `min` y `max`.",
                    "params": {"min": "Mínimo.", "max": "Máximo.", "step": "Paso."},
                },
                "pyzed.progress_bar": {
                    "desc": "Una barra de progreso.",
                    "params": {"min": "Mínimo.", "max": "Máximo.", "radius": "Radio de las esquinas."},
                },
            }),
            ("Editor de código", {
                "pyzed.code_editor": {
                    "desc": """
Un editor de código con resaltado de sintaxis, números de línea y marcadores de git, basado en
`text_editor` de Iced. Es **no controlado**: `text` solo es el valor inicial para ese `id`; el
texto, el cursor y el historial viven en Rust. Usa `Command.set_editor_text` para reemplazarlo.
Para el editor con tema usa [`ui.editor`](/pyzed/es/components/code/).
""",
                    "params": {
                        "id": "Identifica el buffer. Reutilízalo para conservar el estado entre renders.",
                        "text": "Texto inicial.",
                        "language": 'Extensión o nombre del lenguaje (`"py"`, `"rs"`, `"json"`…).',
                        "size": "Tamaño de la fuente.",
                        "line_height": "Alto de línea en píxeles.",
                        "font": "Familia (por defecto, monoespaciada).",
                        "syntax": "Mapa de scopes TextMate a colores (lo da `Theme.syntax_scopes()`).",
                        "selection_color": "Color de la selección.",
                        "placeholder_color": "Color del placeholder.",
                        "gutter": "Muestra los números de línea.",
                        "gutter_color": "Color de los números de línea.",
                        "gutter_active_color": "Color del número de la línea del cursor.",
                        "gutter_width": "Ancho del margen (automático por defecto).",
                        "markers": "`{línea: color}` para las marcas de git del margen (líneas desde 1).",
                        "wrap": "Ajuste de línea.",
                        "on_change": "Callable que recibe el texto completo tras cada edición.",
                        "on_cursor": "Callable que recibe `(línea, columna)`, desde 1.",
                        "annotations": '`{línea: "texto"}` o `{línea: ("texto", color)}`: texto virtual al final de la línea (code lens, diagnósticos).',
                        "whitespace": "Dibuja los espacios como `·` y los tabuladores como `→` en este color.",
                        "tab_size": "Tab inserta espacios hasta el siguiente múltiplo; Enter mantiene la sangría; Backspace quita un nivel.",
                        "capture_keys": 'Teclas que el editor deja al `on_key` de la app (`"up"`, `"enter"`…), por ejemplo con una lista de autocompletado abierta.',
                        "auto_close": "Al escribir un paréntesis, corchete, llave o comilla también inserta el de cierre.",
                        "folding": "Flechas de plegado en el margen y Ctrl+Shift+[ / ].",
                        "minimap": "Ancho del minimapa en píxeles (`None`: sin minimapa).",
                        "minimap_thumb": "Color del resaltado del área visible en el minimapa.",
                        "cursor_shape": '`"bar"`, `"block"`, `"underline"` o `"hollow"`.',
                        "cursor_width": "Ancho del cursor de barra.",
                        "cursor_blink": "Si el cursor parpadea.",
                        "cursor_color": "Color del cursor.",
                        "on_zoom": "Callable que recibe `1`, `-1` o `0` con Ctrl+= / Ctrl+- / Ctrl+0 y Ctrl+rueda.",
                        "on_action": "Callable que recibe el nombre de cada acción del editor que se ejecuta (`\"undo\"`, `\"select_next\"`…).",
                        "highlights": "Rangos pintados detrás del texto (resultados de búsqueda): `[(línea, columna, línea_final, columna_final)]`, desde 1, con el final excluido.",
                        "highlight_color": "Color de `highlights`.",
                        "match_brackets": "Remarca el corchete pareja del que está junto al cursor.",
                        "selection_highlight": "Resalta las demás apariciones del texto seleccionado.",
                        "keymap": 'Diccionario `{atajo: acción}` al estilo de Zed; `None` como acción quita una tecla por defecto (`pyzed.ui.editor.keymap_for` crea uno a partir de cambios por acción).',
                        "scrollbar": '`False` oculta las barras de desplazamiento.',
                    },
                },
            }),
        ],
    },
    # ------------------------------------------------------------------ UI
    {
        "slug": "ui",
        "title": "Componentes (pyzed.ui)",
        "description": "Referencia de la API de pyzed.ui: cada componente listo para usar con sus parámetros, valores por defecto y eventos, para apps de escritorio en Python.",
        "order": 4,
        "intro": """
            Firmas y parámetros de todos los componentes. Para verlos con imágenes y ejemplos,
            ve a la sección [Componentes](/pyzed/es/components/overview/).

            Todos son funciones que devuelven un `Widget` y leen sus colores del tema actual.
            Los parámetros de color aceptan un **token** del tema (`"accent"`, `"text_muted"`,
            `"error"`…) o un color hex.
        """,
        "sections": [
            ("Básicos", {
                "pyzed.ui.label": {
                    "desc": "Texto con un color del tema.",
                    "params": {
                        "color": 'Token del tema o color hex. Por defecto `"text"`.',
                        "size": '`"xs"` (11), `"sm"` (12), `"md"` (13.5), `"lg"` (16), `"xl"` (20), `"2xl"` (26) o un número.',
                        "weight": 'Peso: `"medium"`, `"semibold"`, `"bold"`…',
                        "italic": "Cursiva.",
                        "wrap": "Ajuste de línea.",
                        "kwargs": "Se pasan a `pyzed.text`.",
                    },
                },
                "pyzed.ui.muted": {"desc": 'Un `label` con color `"text_muted"`.', "params": {"kwargs": "Los de `label`."}},
                "pyzed.ui.heading": {
                    "desc": "Un título en semibold.",
                    "params": {"level": "1 (26 px), 2 (20 px), 3 (16 px) o 4 (13.5 px).", "kwargs": "Los de `label`."},
                },
                "pyzed.ui.button": {
                    "desc": "Un botón con tema, con variantes, tamaños, un icono y un atajo.",
                    "params": {
                        "content": "Texto o widget.",
                        "icon_position": '`"start"` o `"end"`.',
                        "variant": '`"filled"`, `"ghost"`, `"subtle"`, `"outline"`, `"solid"`, `"tinted"`, o un color semántico: `"accent"`, `"error"`, `"warning"`, `"success"`, `"info"`.',
                        "tint": "Color de las variantes `solid` y `tinted`.",
                        "size": _SIZES,
                        "full_width": "Ocupa todo el ancho.",
                        "style": "Cualquier parámetro de estilo de `pyzed.button` (`bg`, `hover_bg`, `color`…).",
                    },
                },
                "pyzed.ui.icon_button": {
                    "desc": "Un botón cuadrado con solo un icono.",
                    "params": {
                        "name": "Nombre del icono.",
                        "size": _SIZES,
                        "variant": 'Como en `ui.button`. Por defecto `"ghost"`.',
                        "color": "Color del icono.",
                        "tooltip": "Texto del tooltip.",
                    },
                },
                "pyzed.ui.badge": {
                    "desc": "Una píldora pequeña para estados y contadores.",
                    "params": {"variant": '`"soft"`, `"solid"` o `"outline"`.'},
                },
                "pyzed.ui.indicator": {
                    "desc": "Un punto de color (estado, cambios sin guardar, presencia).",
                    "params": {"color": "Token o color.", "size": "Diámetro."},
                },
                "pyzed.ui.kbd": {
                    "desc": 'Dibuja un atajo como teclas: `"ctrl-shift-p"`, `"cmd-k cmd-s"`. En macOS usa símbolos (⌘⇧P) y en el resto palabras.',
                    "params": {"keys": "El atajo.", "size": '`"xs"` o `"sm"`.'},
                },
                "pyzed.ui.format_keys": {
                    "desc": 'Separa un atajo en etiquetas por acorde: `format_keys("ctrl-shift-p") == [["Ctrl", "Shift", "P"]]`. El estilo se controla con `pyzed.ui.base.KEY_STYLE` (`"auto"`, `"symbols"` o `"words"`).',
                    "params": {"keys": "El atajo."},
                },
                "pyzed.ui.avatar": {
                    "desc": "Un avatar redondo con iniciales.",
                    "params": {
                        "initials": "Iniciales (se usan las dos primeras).",
                        "color": "Color de fondo.",
                        "size": "Diámetro.",
                        "index": "Elige un color de colaborador del tema (`theme.players`).",
                    },
                },
                "pyzed.ui.tooltip": {
                    "desc": "Envuelve `content` con un tooltip con el estilo del tema, opcionalmente con su atajo.",
                    "params": {"text": "Texto del tooltip.", "position": '`"top"`, `"bottom"`, `"left"`, `"right"` o `"cursor"`.'},
                },
                "pyzed.ui.divider": {
                    "desc": "Una línea divisoria con el color del tema.",
                    "params": {"vertical": "Vertical en lugar de horizontal."},
                },
                "pyzed.ui.card": {
                    "desc": "Una superficie con borde para agrupar contenido, con título y acciones opcionales.",
                    "params": {"padding": "Relleno interior."},
                },
            }),
            ("Formularios", {
                "pyzed.ui.input": {
                    "desc": "Un campo de texto. El foco, la pérdida de foco y las teclas vienen de los eventos comunes: `.on(focus=..., blur=..., key_down=...)`.",
                    "params": {
                        "value": "Texto actual.",
                        "size": '`"sm"`, `"md"` o `"lg"`.',
                        "secure": "Oculta el texto.",
                        "borderless": "Sin borde ni fondo (como en la paleta de comandos).",
                        "disabled": "Lo atenúa e ignora lo que se escribe.",
                        "readonly": "Se puede seleccionar y copiar, pero no cambiar.",
                        "invalid": "Pinta el borde con el color de error.",
                        "max_length": "Ignora los cambios más largos que esto.",
                        "on_clear": "Muestra una ✕ mientras hay texto; se envía al pulsarla.",
                        "align": 'Alineación del texto: `"start"`, `"center"` o `"end"`.',
                    },
                },
                "pyzed.ui.search_input": {
                    "desc": "Un `input` con icono de lupa.",
                    "params": {"value": "Texto actual.", "kwargs": "Los de `input`."},
                },
                "pyzed.ui.switch": {"desc": "Un interruptor encendido/apagado.", "params": {"size": '`"sm"`, `"md"` o `"lg"`.', "disabled": "Lo atenúa e ignora los clics."}},
                "pyzed.ui.checkbox": {"desc": "Una casilla de verificación. `checked=None` muestra el estado mixto (parte de un grupo marcada); al pulsarla se marca.", "params": {"size": '`"sm"`, `"md"` o `"lg"`.', "disabled": "La atenúa e ignora los clics."}},
                "pyzed.ui.slider": {
                    "desc": "Un deslizador.",
                    "params": {"min": "Mínimo.", "max": "Máximo.", "step": "Paso.", "on_release": "Se envía al terminar de arrastrar (guarda o aplica ahí).", "vertical": "Lo pone de pie.", "disabled": "Lo atenúa.", "show_value": 'Muestra el número al lado: `True`, o un formato como `"{:.0%}"`.'},
                },
                "pyzed.ui.progress": {
                    "desc": "Una barra de progreso fina.",
                    "params": {"max": "Valor máximo.", "height": "Grosor."},
                },
                "pyzed.ui.segmented": {
                    "desc": "Un grupo de botones mutuamente excluyentes.",
                    "params": {"options": "Textos, `(valor, etiqueta)` o `(valor, etiqueta, icono)`.", "selected": "El valor activo.", "size": '`"sm"`, `"md"` o `"lg"`.', "width": '`"fill"` reparte el ancho entre los botones.', "disabled": "`True`, o los valores a desactivar."},
                },
                "pyzed.ui.field": {
                    "desc": "Una fila de formulario: título y descripción a la izquierda, control a la derecha (como una pantalla de ajustes).",
                    "params": {"control": "El control (switch, input…).", "description": "Texto de ayuda.",
                               "error": "Un mensaje de validación que se muestra bajo el título con el color de error (ver `pz.validation_errors`).",
                               "required": "Añade un `*` rojo tras el título.", "vertical": "Pone el control bajo el título."},
                },
            }),
            ("Listas, árbol y menús", {
                "pyzed.ui.list_item": {
                    "desc": "Una fila de lista: icono, texto y un hueco al final.",
                    "params": {
                        "content": "Texto o widget.",
                        "focused": "Dibuja un borde de foco.",
                        "height": "Alto de la fila.",
                        "color": "Color del texto.",
                        "inset": "Con margen y esquinas redondeadas (menús, paletas).",
                        "on_right_press": "Clic derecho.",
                    },
                },
                "pyzed.ui.list_header": {"desc": "Un encabezado de sección para listas."},
                "pyzed.ui.TreeNode": {
                    "desc": 'Un archivo o carpeta para `ui.tree`. Las carpetas tienen `children` (lista). `status` es `"modified"`, `"created"`, `"deleted"`, `"conflict"` o `"ignored"`. `TreeNode.from_paths(paths, status=None)` construye el árbol a partir de rutas como `"src/main.rs"`, con las carpetas primero y el estado de git propagado a las carpetas.',
                    "params": {
                        "name": "Nombre visible.",
                        "children": "Hijos (`None` si es un archivo).",
                        "status": "Estado de git.",
                    },
                },
                "pyzed.ui.tree": {
                    "desc": "Un árbol de archivos plegable, como el panel de proyecto de un editor de código.",
                    "params": {
                        "nodes": "Lista de `TreeNode`.",
                        "expanded": "Conjunto de ids de carpetas abiertas.",
                        "selected": "Id del nodo seleccionado.",
                        "on_toggle": "Se llama con el id de la carpeta pulsada.",
                        "on_select": "Se llama con el id del archivo pulsado.",
                    },
                },
                "pyzed.ui.MenuItem": {
                    "desc": "Una entrada de `ui.menu`.",
                    "params": {"danger": "En rojo (acciones destructivas).", "checked": "Muestra una marca (`True`/`False`) o nada (`None`)."},
                },
                "pyzed.ui.menu": {
                    "desc": "Un menú contextual flotante. Usa `ui.SEPARATOR` entre grupos; un texto suelto es un encabezado.",
                    "params": {"items": "Lista de `MenuItem`, `ui.SEPARATOR` o textos."},
                },
                "pyzed.ui.SEPARATOR": {"desc": "Separador para `ui.menu`.", "no_signature": True},
            }),
            ("Navegación", {
                "pyzed.ui.Tab": {
                    "desc": "Una pestaña. `Tab.for_file(path, **kwargs)` la crea con el nombre y el icono del archivo.",
                    "params": {
                        "dirty": "Cambios sin guardar (muestra un punto).",
                        "preview": "Pestaña de vista previa (en cursiva).",
                        "status": "Estado de git (tiñe el nombre).",
                    },
                },
                "pyzed.ui.tab": {
                    "desc": "Una sola pestaña. Normalmente se usa `tab_bar`.",
                    "params": {"item": "El `Tab`.", "active": "Si es la activa.", "height": "Alto.",
                               "dimmed": "Apaga la etiqueta (la pestaña que se arrastra)."},
                },
                "pyzed.ui.tab_bar": {
                    "desc": "Una fila de pestañas con controles opcionales al principio y al final (navegación, dividir, +). El botón de cerrar aparece en la activa y al pasar el ratón. Las pestañas se pueden arrastrar para reordenarlas o sacarlas de la ventana: ver [Pestañas arrastrables](/pyzed/es/guides/windows/#pestañas-arrastrables-y-ventanas-desprendibles).",
                    "params": {"tabs": "Lista de `Tab`.", "active": "Id de la pestaña activa.", "height": "Alto.",
                               "on_drag": "Se llama con el id de la pestaña cuando empieza a arrastrarse.",
                               "on_drop": "Se llama con el id de la pestaña y el `Event` al soltar la pestaña arrastrada: `event.window_x`/`window_y` (fuera de la ventana si se soltó fuera) y `event.screen`.",
                               "on_drag_over": "Mientras `dragging` tiene valor: se llama con el índice de inserción bajo el puntero, o `None` cuando sale de la barra.",
                               "dragging": "Id de la pestaña que se arrastra (la apaga y activa `on_drag_over`).",
                               "drop_index": "Dibuja la marca de inserción antes de la pestaña de este índice (`len(tabs)`: después de la última)."},
                },
                "pyzed.ui.breadcrumbs": {
                    "desc": "`src › main.rs › fn main`. Las partes pueden ser textos o tuplas `(icono, texto)`.",
                    "params": {"parts": "Las partes.", "separator": "Separador.", "on_press": "Se llama con el índice de la parte pulsada."},
                },
                "pyzed.ui.toolbar": {
                    "desc": "La barra bajo las pestañas: breadcrumbs a la izquierda y acciones del buffer a la derecha.",
                    "params": {"height": "Alto."},
                },
            }),
            ("Workspace", {
                "pyzed.ui.workspace": {
                    "desc": "El layout de una ventana estilo editor: barra de título, docks izquierdo, derecho e inferior, centro y barra de estado. Pasa `None` para ocultar un dock.",
                    "params": {
                        "center": "Contenido central (normalmente pestañas + editor).",
                        "title_bar": "Barra de título (`ui.title_bar`).",
                        "left": "Dock izquierdo.",
                        "right": "Dock derecho.",
                        "bottom": "Dock inferior.",
                        "status_bar": "Barra de estado (`ui.status_bar`).",
                        "left_width": "Ancho del dock izquierdo.",
                        "right_width": "Ancho del dock derecho.",
                        "on_resize": "Se llama con `(side, size)` cuando el usuario termina de cambiar el tamaño de un panel arrastrando su borde interior.",
                        "bottom_height": "Alto del dock inferior.",
                    },
                },
                "pyzed.ui.title_bar": {
                    "desc": "La barra superior: selectores de proyecto y rama a la izquierda, cuenta y acciones a la derecha.",
                    "params": {"center": "Widget centrado.", "height": "Alto."},
                },
                "pyzed.ui.title_button": {
                    "desc": "Un botón compacto para la barra de título (`pyzed ▾`, `main`…).",
                    "params": {"content": "Texto.", "muted": "Texto atenuado.", "chevron": "Añade un ▾."},
                },
                "pyzed.ui.status_bar": {"desc": "La barra de estado inferior.", "params": {"height": "Alto."}},
                "pyzed.ui.status_item": {
                    "desc": "Un icono y/o texto en la barra de estado (diagnósticos, posición del cursor, lenguaje…).",
                    "params": {"content": "Texto.", "tooltip": "Texto del tooltip."},
                },
                "pyzed.ui.panel": {
                    "desc": "Un panel acoplable. `side` decide en qué borde va la línea; con un `width` numérico (`height` para el inferior) ese borde se arrastra para cambiar su tamaño.",
                    "params": {
                        "header": "Cabecera (`ui.panel_header`).", "side": '`"left"`, `"right"` o `"bottom"`.',
                        "resizable": "`False` mantiene el tamaño fijo.", "on_resize": "Se llama con el nuevo tamaño al terminar de arrastrar.",
                        "min_size": "Tamaño mínimo al redimensionar.",
                    },
                },
                "pyzed.ui.panel_header": {"desc": "La cabecera de un panel: icono, título y acciones.", "params": {"height": "Alto."}},
            }),
            ("Marco de ventana", {
                "pyzed.ui.window_frame": {
                    "desc": "El marco entero de una ventana abierta con `frame=\"custom\"`: una barra de título que mueve la ventana (doble clic maximiza, clic derecho abre el menú del sistema en Windows), los botones de minimizar, maximizar y cerrar con el estilo de una plataforma, menús a la izquierda y bordes que cambian el tamaño de la ventana.",
                    "params": {
                        "content": "El contenido de la ventana, bajo la barra de título.",
                        "title": "Título de la barra. Por defecto el `title` de la ventana.",
                        "menus": "Menús a la izquierda de la barra: una lista de `ui.Menu`.",
                        "menu_button": "Muestra los menús tras un botón ☰ (`False` muestra siempre sus nombres).",
                        "start": "Elementos después de los menús (proyecto, rama…).",
                        "center": "Tu propio widget en el centro en lugar del título.",
                        "end": "Elementos antes de los botones de ventana.",
                        "style": '`"macos"`, `"windows"`, `"gnome"`, `"ubuntu"` o `"kde"`. Por defecto el `frame` de la ventana, o el del sistema.',
                        "window": "La ventana sobre la que actúan los botones. Por defecto aquella cuyo `view()` se está ejecutando.",
                        "height": "Alto de la barra. Por defecto el de la plataforma.",
                        "resize_border": "Ancho en píxeles de los bordes que cambian el tamaño de la ventana.",
                        "resize_edges": "`False` deja los bordes de redimensionar a tu cargo (`pz.window_edges`), para ponerlos encima de menús y diálogos.",
                    },
                    "example": 'class Notes(pz.App):\n    frame = "custom"\n\n    def view(self):\n        return ui.window_frame(self.editor(), menus=[ui.Menu("Archivo", [ui.MenuItem("Abrir", self.open)])],\n                               end=[ui.icon_button("settings", self.settings)])',
                },
                "pyzed.ui.window_title_bar": {
                    "desc": "La barra de título de una ventana, sola: botones de ventana con el estilo de `style` (a la izquierda en macOS), elementos `start`, el título y elementos `end`. Sin callbacks solo se muestra, que es como Pyzed Design previsualiza un formulario con el marco de cada plataforma.",
                    "params": {
                        "title": "Título (centrado, o a la izquierda en Windows).",
                        "style": '`"macos"`, `"windows"`, `"gnome"`, `"ubuntu"` o `"kde"` (`None`: el del sistema).',
                        "start": "Elementos al principio.", "center": "Widget en el centro en lugar del título.",
                        "end": "Elementos al final.",
                        "on_drag": "Se llama al arrastrar la parte vacía de la barra (devuelve `Command.drag_window()`).",
                        "on_minimize": "Botón de minimizar.", "on_maximize": "Botón de maximizar y doble clic en la barra.",
                        "on_close": "Botón de cerrar.", "on_menu": "Clic derecho en la barra.",
                        "maximized": "Muestra el símbolo de restaurar.", "focused": "`False` la atenúa como una ventana en segundo plano.",
                        "height": "Alto. Por defecto el de la plataforma.", "border": "Línea bajo la barra.",
                    },
                },
                "pyzed.ui.window_controls": {
                    "desc": "Los botones de minimizar, maximizar y cerrar con el estilo de una plataforma. Un botón sin callback se dibuja pero no hace nada.",
                    "params": {
                        "style": '`"macos"`, `"windows"`, `"gnome"`, `"ubuntu"` o `"kde"` (`None`: el del sistema).',
                        "on_minimize": "Botón de minimizar.", "on_maximize": "Botón de maximizar.", "on_close": "Botón de cerrar.",
                        "maximized": "Muestra el símbolo de restaurar.", "focused": "`False` los atenúa.", "height": "Alto.",
                    },
                },
                "pyzed.ui.Menu": {
                    "desc": "Un menú de la barra de menús de un marco de ventana: un nombre y sus elementos (`ui.MenuItem`, `ui.SEPARATOR` o un texto de cabecera).",
                    "params": {"label": "El nombre del menú.", "items": "Sus elementos: `ui.MenuItem`, `ui.SEPARATOR` o un texto de cabecera."},
                    "example": 'ui.Menu("Archivo", [ui.MenuItem("Abrir…", self.open, keys="ctrl-o"), ui.SEPARATOR, ui.MenuItem("Salir", self.close)])',
                },
                "pyzed.ui.system_platform": {
                    "desc": 'El estilo de los botones de ventana de este sistema: `"macos"`, `"windows"`, `"kde"`, `"ubuntu"` o `"gnome"` (otros escritorios Linux). En WSL es `"windows"`.',
                },
            }),
            ("Overlays", {
                "pyzed.ui.layer": {
                    "desc": "Apila `overlay` sobre `base`. Hacer clic fuera envía `on_dismiss`. Con `overlay=None` devuelve `base` tal cual.",
                    "params": {
                        "base": "La interfaz de debajo.",
                        "overlay": "Lo que flota encima (modal, paleta, menú).",
                        "backdrop": "Color del fondo que oscurece la interfaz.",
                        "offset": "Distancia desde arriba cuando `align_y` es `\"start\"`.",
                    },
                },
                "pyzed.ui.modal": {
                    "desc": "Un diálogo. Úsalo como `overlay` de `ui.layer`.",
                    "params": {"footer": "Botones del pie, alineados a la derecha."},
                },
                "pyzed.ui.PaletteItem": {
                    "desc": "Una entrada de `command_palette` o `picker`.",
                    "params": {"detail": "Texto secundario (por ejemplo, la ruta de un archivo)."},
                },
                "pyzed.ui.command_palette": {
                    "desc": "Una paleta de comandos: filtra `commands` por `query` con búsqueda difusa y muestra sus atajos.",
                    "params": {
                        "query": "Texto buscado.",
                        "on_query": "Callable que recibe el texto nuevo.",
                        "commands": "Lista de `PaletteItem`.",
                        "selected": "Índice resaltado (para navegar con flechas).",
                        "input_id": "Id del campo (para `Command.focus`).",
                        "kwargs": "Los de `picker`.",
                    },
                },
                "pyzed.ui.picker": {
                    "desc": "Una lista con buscador en una superficie flotante. Es la base de la paleta y del buscador de archivos.",
                    "params": {
                        "query": "Texto buscado.",
                        "on_query": "Callable que recibe el texto nuevo.",
                        "items": "Pares `(PaletteItem, posiciones)`, por ejemplo de `fuzzy_filter`.",
                        "selected": "Índice resaltado.",
                        "input_id": "Id del campo.",
                        "empty_text": "Texto cuando no hay resultados.",
                    },
                },
                "pyzed.ui.fuzzy_match": {
                    "desc": "Devuelve `(puntuación, posiciones)` si todas las letras de `query` aparecen en orden en `candidate`; si no, `None`. Premia los inicios de palabra y las letras consecutivas.",
                    "params": {"query": "Texto buscado.", "candidate": "Texto candidato."},
                },
                "pyzed.ui.fuzzy_filter": {
                    "desc": "Filtra y ordena `items` por puntuación difusa. Devuelve `[(item, posiciones), ...]`.",
                    "params": {"query": "Texto buscado.", "items": "Elementos.", "key": "Función que da el texto de cada elemento."},
                },
                "pyzed.ui.highlighted": {
                    "desc": "Texto con los caracteres de `positions` resaltados (coincidencias de la búsqueda difusa).",
                    "params": {"text": "Texto.", "positions": "Índices a resaltar.", "match_color": "Color de las coincidencias.", "weight": "Peso del texto."},
                },
                "pyzed.ui.toast": {
                    "desc": "Una notificación.",
                    "params": {"message": "Texto secundario.", "kind": '`"info"`, `"success"`, `"warning"` o `"error"`.'},
                },
                "pyzed.ui.toasts": {
                    "desc": "Muestra `items` (normalmente `toast(...)`) apilados en la esquina inferior derecha sobre `base`.",
                    "params": {"base": "La interfaz de debajo.", "items": "Lista de toasts."},
                },
            }),
            ("Código", {
                "pyzed.ui.editor": {
                    "desc": "Un editor de código: resaltado con los colores del tema, números de línea y marcadores de git.",
                    "params": {
                        "id": "Identifica el buffer (usa la ruta del archivo).",
                        "text": "Texto inicial.",
                        "language": "Lenguaje. Si falta, se deduce de `path`.",
                        "markers": '`{línea: "created" | "modified" | "deleted"}`.',
                        "on_cursor": "Callable que recibe `(línea, columna)`.",
                        "font_size": "Tamaño de la fuente (por defecto, el del tema).",
                        "font": 'Tipografía: `"mono"` por defecto; `"sans"` hace un cuadro de texto de varias líneas, como el cuadro de mensaje de un chat.',
                        "line_height": "Alto de línea.",
                        "gutter": "Muestra los números de línea.",
                        "wrap": "Ajuste de línea.",
                        "annotations": '`{línea: "texto"}` o `{línea: ("texto", color)}`: texto virtual al final de la línea (code lens, diagnósticos).',
                        "show_whitespace": "Dibuja los espacios como `·` y los tabuladores como `→`.",
                        "tab_size": "Tab inserta espacios hasta el siguiente múltiplo; Enter mantiene la sangría (un nivel más tras `:`); Backspace quita un nivel.",
                        "capture_keys": 'Teclas que el editor deja al `on_key` de la app (`"up"`, `"enter"`…), por ejemplo con una lista de autocompletado abierta.',
                        "auto_close": "Cierra paréntesis, corchetes, llaves y comillas al escribir (y envuelve la selección).",
                        "folding": "Flechas de plegado en el margen; Ctrl+Shift+[ pliega y Ctrl+Shift+] despliega.",
                        "minimap": "`True` (o un ancho en píxeles) muestra un minimapa a la derecha.",
                        "cursor_shape": '`"bar"`, `"block"`, `"underline"` o `"hollow"`.',
                        "cursor_blink": "Si el cursor parpadea.",
                        "cursor_width": "Ancho del cursor de barra.",
                        "cursor_color": "Color del cursor (por defecto, el color de jugador del tema).",
                        "on_zoom": "Callable que recibe `1`, `-1` o `0` con Ctrl+= / Ctrl+- / Ctrl+0 y Ctrl+rueda.",
                        "on_action": "Callable que recibe el nombre de cada acción del editor que se ejecuta (`\"undo\"`, `\"select_next\"`…), por ejemplo para contarlas.",
                        "highlights": "Rangos pintados detrás del texto con el color de búsqueda del tema: `[(línea, columna, línea_final, columna_final)]`, desde 1, con el final excluido.",
                        "match_brackets": "Remarca el corchete pareja del que está junto al cursor (Ctrl+M salta a él).",
                        "selection_highlight": "Resalta las demás apariciones del texto seleccionado (Ctrl+D añade la siguiente como cursor).",
                        "keymap": 'Diccionario `{atajo: acción}` al estilo de Zed (`{"ctrl-shift-d": "duplicate_line_down"}`); `None` como acción quita una tecla por defecto. Créalo a partir de cambios por acción con `pyzed.ui.editor.keymap_for`.',
                        "scrollbar": '`False` oculta las barras de desplazamiento.',
                    },
                },
                "pyzed.ui.language_token": {
                    "desc": 'Devuelve el token de lenguaje del resaltador para una ruta (`"main.rs"` → `"rs"`).',
                },
                "pyzed.ui.terminal": {
                    "desc": "Una vista de terminal de solo lectura con colores ANSI. Se mantiene desplazada al final.",
                    "params": {"lines": "Texto con escapes ANSI o lista de líneas de segmentos `(texto, color)`.", "font_size": "Tamaño de la fuente."},
                },
                "pyzed.ui.ansi": {
                    "desc": "Convierte texto con colores ANSI en líneas de segmentos `(texto, nombre_de_color)`.",
                    "params": {"text": "Texto con escapes ANSI."},
                },
            }),
        ],
    },
    # --------------------------------------------------------------- Theme
    {
        "slug": "theme",
        "title": "Temas",
        "description": "Referencia de la API de Theme en Pyzed: los temas incluidos, los tokens de color, cómo derivar temas propios y utilidades de color.",
        "order": 5,
        "intro": """
            Ver la guía de [temas](/pyzed/es/theming/themes/) para la lista de tokens y cómo crear los tuyos.
        """,
        "sections": [
            ("Theme", {
                "pyzed.Theme": {
                    "desc": "Un tema: un dataclass inmutable con los tokens de color (superficies, bordes, elementos, texto, estado, editor, sintaxis, colores de colaboradores y ANSI) y métricas (`radius`, `radius_sm`, `ui_font_size`, `buffer_font_size`). La propiedad `is_dark` indica si es oscuro.",
                    "no_signature": True,
                },
                "pyzed.Theme.derive": {
                    "desc": "Devuelve una copia con algunos tokens cambiados. Los diccionarios `syntax` y `ansi` se combinan en lugar de reemplazarse.",
                    "params": {"changes": "Tokens a cambiar."},
                    "example": 'oceano = pz.themes.ONE_DARK.derive(name="Océano", accent="#4fb3ff", syntax={"keyword": "#ff79c6"})',
                },
                "pyzed.Theme.color": {
                    "desc": 'Resuelve un token (`"accent"`, `"text_muted"`…) a su color. Los colores hex y `"transparent"` pasan tal cual.',
                    "params": {"name": "Token o color."},
                },
                "pyzed.Theme.tokens": {"desc": "Todos los tokens como diccionario."},
                "pyzed.Theme.syntax_scopes": {"desc": "Traduce los tokens de sintaxis del tema a scopes de TextMate para el resaltador."},
                "pyzed.Theme.palette": {"desc": "La paleta base que se pasa a Iced para sus estilos internos. De uso interno."},
            }),
            ("Temas incluidos", {
                "pyzed.themes": {
                    "desc": "Espacio de nombres con los temas incluidos: `themes.ONE_DARK`, `themes.ONE_LIGHT` y `themes.GRUVBOX_DARK`.",
                    "no_signature": True,
                },
                "pyzed.themes.all": {"desc": "Lista con todos los temas incluidos."},
            }),
            ("Utilidades (pyzed.theme)", {
                "pyzed.theme.current": {"desc": "El tema que usan los componentes cuando no se pasa `theme=`."},
                "pyzed.theme.use": {"desc": "Cambia el tema actual. `App` lo hace antes de cada `view()`, así que normalmente no lo necesitas.", "params": {"theme": "El tema."}},
                "pyzed.theme.alpha": {
                    "desc": "Devuelve `color` con su opacidad multiplicada por `value`.",
                    "params": {"color": "Color hex.", "value": "Factor de 0 a 1."},
                    "example": 'pz.theme.alpha("#74ade8", 0.2)  # "#74ade833"',
                },
                "pyzed.theme.mix": {
                    "desc": "Mezcla dos colores: `amount=0` es `a` y `amount=1` es `b`.",
                    "params": {"a": "Primer color.", "b": "Segundo color.", "amount": "Proporción de `b`."},
                },
            }),
        ],
    },
    # --------------------------------------------------------------- Icons
    {
        "slug": "icons",
        "title": "Iconos",
        "description": "Referencia de la API de pyzed.icons: el conjunto de iconos de Lucide incluido, sus nombres y las utilidades de iconos por tipo de archivo.",
        "order": 6,
        "intro": """
            Pyzed incluye la fuente de [Lucide](https://lucide.dev) (licencia ISC) con unos 2000 iconos.
            Busca nombres con `pyzed icons <filtro>` o en la web de Lucide.
        """,
        "sections": [
            ("pyzed.icons", {
                "pyzed.icons.icon": {
                    "desc": "Un widget de icono. También está en `pyzed.icon`.",
                    "params": {"name": "Nombre del icono.", "size": "Tamaño.", "color": "Color (por defecto, el del texto)."},
                },
                "pyzed.icons.glyph": {
                    "desc": 'Devuelve el carácter de un icono, para usarlo en cualquier texto con `font="icons"`. Lanza `ValueError` si no existe.',
                    "params": {"name": "Nombre del icono."},
                },
                "pyzed.icons.names": {"desc": "Lista ordenada de todos los nombres de iconos."},
                "pyzed.icons.search": {
                    "desc": 'Los iconos que coinciden con una búsqueda por nombre y etiqueta, los mejores primero: nombres exactos, luego los que empiezan por la búsqueda, los que tienen todas las palabras y los encontrados por sus etiquetas (`search("person")` encuentra `user`).',
                    "params": {"query": "Palabras que deben aparecer todas en el nombre o las etiquetas.", "among": "Buscar solo en estos nombres (por defecto, todos los iconos)."},
                    "example": 'icons.search("arrow up")[:3]  # ["arrow-up", "arrow-up-01", "arrow-up-10"]',
                },
                "pyzed.icons.tags": {"desc": 'Las etiquetas de búsqueda de un icono, de Lucide (`tags("user")` es `["person", "account", "contact"]`).',
                                     "params": {"name": "Nombre del icono."}},
                "pyzed.icons.category": {"desc": "Los iconos de una categoría de `CATEGORIES`, ordenados. Un icono puede estar en varias.",
                                         "params": {"key": 'Una clave de `CATEGORIES` (`"arrows"`, `"files"`, `"people"`...).', "among": "Mirar solo estos nombres."}},
                "pyzed.icons.CATEGORIES": {"desc": "Grupos para explorar iconos (flechas, texto, archivos, diseño, multimedia, comunicación, personas, dispositivos, desarrollo, formas, clima, comercio, mapas, estado), cada uno con las palabras de nombres y etiquetas que meten un icono en él.", "no_signature": True},
                "pyzed.icons.for_file": {
                    "desc": 'Devuelve `(icono, color_o_None)` para un nombre de archivo, como en el panel de proyecto de un editor de código.',
                    "params": {"name": "Nombre del archivo."},
                },
                "pyzed.icons.language_for": {
                    "desc": 'Nombre legible del lenguaje de un archivo (`"main.py"` → `"Python"`), útil para la barra de estado.',
                    "params": {"name": "Nombre del archivo."},
                },
            }),
        ],
    },
]


# ---------------------------------------------------------------------------
# 0.2: multi-window, async, new widgets and components
# ---------------------------------------------------------------------------

COMMON.update({
    "font": "Fuente del fragmento o del texto (nombre de familia, p. ej. `\"IBM Plex Mono\"`).",
    "weight": "Grosor de la fuente: `\"normal\"`, `\"medium\"`, `\"semibold\"` o `\"bold\"`.",
    "italic": "Si es `True`, el fragmento se dibuja en cursiva.",
    "wrap": "Ajuste de línea / pasa los hijos a una nueva fila cuando no caben.",
    "line_spacing": "Separación entre filas cuando `wrap=True`.",
    "gradient": "Degradado lineal de fondo: `(ángulo, [colores])` o `(ángulo, [(posición, color), ...])`.",
    "on_scroll": "Se llama al desplazar.",
    "on_move": "Se llama con `(x, y)` al mover el ratón.",
    "on_middle_press": "Clic con el botón central.",
    "on_middle_release": "Se suelta el botón central (para desplazar la vista, por ejemplo).",
    "on_release": "Se llama al soltar.",
    "vertical": "Orientación vertical.",
    "content_fit": '`"contain"`, `"cover"`, `"fill"`, `"none"` o `"scale-down"`.',
    "opacity": "Opacidad de 0 a 1.",
    "rotation": "Rotación en grados.",
    "active_line": "Color de fondo de la línea del cursor.",
    "scrollbar_color": "Color de la barra de desplazamiento.",
    "key": "Clave que identifica la suscripción (por defecto, el mensaje o la función).",
    "filter": '`"linear"` (suave) o `"nearest"` (píxeles nítidos, para pixel art).',
    "source": "Ruta del archivo, `bytes` del archivo codificado, o píxeles RGBA crudos con `size=(ancho, alto)`.",
    "description": "Texto secundario.",
    "options": "Lista de opciones.",
    "on_menu": "Mensaje o callable del botón del menú.",
    "handle": "Ancho de la zona que se puede arrastrar.",
    "text_size": "Tamaño del texto.",
})


def _page(slug):
    return next(p for p in PAGES if p["slug"] == slug)


def _section(slug, title, items, before=None):
    page = _page(slug)
    sections = page["sections"]
    for i, (name, existing) in enumerate(sections):
        if name == title:
            existing.update(items)
            return
    index = next((i for i, (n, _) in enumerate(sections) if n == before), len(sections))
    sections.insert(index, (title, items))


# -- App, windows and async ------------------------------------------------
_page("app")["intro"] += """

Ver también [varias ventanas](/pyzed/es/guides/windows/) y [async y suscripciones](/pyzed/es/guides/async/).
"""
_page("app")["sections"][0][1]["pyzed.App"]["desc"] = """
Clase base de las aplicaciones (arquitectura Elm, como Iced). Es también la **ventana
principal**, así que hereda todo lo de [`Window`](#window). Sobrescribe `view()` y, si usas
mensajes, `update(message)`. El estado vive en atributos de la instancia.

| Atributo de clase | Por defecto | Descripción |
| --- | --- | --- |
| `title` | `"Pyzed"` | Título de la ventana. Puede ser un callable (o propiedad) que devuelva el texto. |
| `size` | `(1280, 800)` | Tamaño inicial de la ventana. |
| `font_size` | `14` | Tamaño de texto por defecto. |
| `theme` | `themes.ONE_DARK` | Un `Theme`, el nombre de un tema registrado o `themes.auto(claro, oscuro)`. Cámbialo en cualquier momento. |
| `style` | `None` | El estilo global: un `pz.Style` para toda la ventana. Su color de texto, tamaño, fondo, color de borde y radio se vuelven tokens del tema. Ver [Estilos](/pyzed/es/theming/styles/#el-estilo-global). |
| `system_dark` | `True` | Si el sistema está en modo oscuro (lo actualiza el runtime). |
| `tab_focus` | `True` | Tab y Shift+Tab mueven el foco entre los campos de la ventana. Ver [Accesibilidad](/pyzed/es/guides/accessibility/). |

El resto de opciones de ventana (`min_size`, `resizable`, `decorations`, `scale`…) están en `Window`.

| Método | Descripción |
| --- | --- |
| `view()` | Devuelve el árbol de widgets. Se llama después de cada mensaje. |
| `update(message)` | Recibe los mensajes. Puede devolver un `Command`, una lista de ellos, una corrutina, un generador (normal o async) u otro mensaje. |
| `on_start()` | Opcional. Se ejecuta una vez al arrancar; puede devolver un `Command` o una corrutina. |
| `on_key(combo)` | Opcional. Recibe cada tecla como `"ctrl-shift-p"`, `"escape"`, `"up"`… |
| `on_key_up(key)` | Opcional. Recibe las teclas al soltarlas, por nombre (`"left"`, `"space"`). |
| `subscriptions()` | Opcional. Devuelve las suscripciones activas (`pz.every`, `pz.listen`). Se reevalúa tras cada `update`. |
| `resolved_theme()` | El `Theme` concreto en uso (resuelve nombres y `themes.auto`). |
| `run()` | Abre la ventana y bloquea hasta que la app termina. |
| `screenshot(path, *, size=None, scale=2.0, wait=0.1)` | Renderiza el estado actual a un PNG sin ventana. |

Si `view()` lanza una excepción, la ventana muestra el traceback en lugar de cerrarse.
"""
_section("app", "Ventanas", {
    "pyzed.Window": {
        "desc": """
Una ventana extra con su propio `view()`, título, tamaño y tema. Se abre devolviendo
`ventana.open()` (o `Command.open_window(ventana)`). Dentro, `self.app` es la app, así que las
ventanas comparten estado; los mensajes que produce van a su `update()`, que por defecto los
reenvía a `app.update()`.

| Atributo | Por defecto | Descripción |
| --- | --- | --- |
| `title` | `"Pyzed"` | Texto o callable. |
| `size` | `(800, 600)` | Tamaño inicial. |
| `min_size`, `max_size` | `None` | Límites de tamaño. |
| `position` | `None` | `"center"` o `(x, y)`. |
| `resizable` | `True` | Si se puede redimensionar. |
| `decorations` | `True` | `False` quita el marco del sistema (barra de título propia con `drag()`). |
| `transparent`, `maximized`, `fullscreen` | `False` | Estado inicial. |
| `scale` | `1.0` | Escala de la interfaz. |
| `theme` | `None` | Tema propio; `None` usa el de la app. |
| `style` | `None` | Estilo global propio; `None` usa el de la app. |
| `app` | — | La app dueña de la ventana (se asigna al abrirla). |
| `window_size` | — | Tamaño actual en píxeles lógicos (lo actualiza el runtime). |
| `window_position` | — | Dónde está la ventana en la pantalla, su esquina superior izquierda exterior (lo actualiza el runtime; `None` en Wayland). |

| Método | Descripción |
| --- | --- |
| `view()` | Obligatorio. Devuelve el árbol de widgets de la ventana. |
| `update(message)` | Recibe los mensajes de la ventana (por defecto los reenvía a la app). |
| `open()` / `close()` / `drag()` | Comandos para abrirla, cerrarla o empezar a moverla. |
| `is_open` | Si está abierta. |
| `resolved_theme()` | El `Theme` concreto que usa. |
| `on_open()` | Al abrirse. |
| `on_close()` | Cuando el usuario pide cerrarla; devuelve `False` para impedirlo. |
| `on_resize(width, height)` | Al cambiar de tamaño. |
| `on_key(combo)`, `subscriptions()` | Como en `App`. |
""",
        "no_signature": True,
    },
})
_section("app", "Async y suscripciones", {
    "pyzed.every": {
        "desc": "Una suscripción que envía `message` a `update` cada `seconds` segundos (como `time::every` de Iced). Si `message` es un callable, se llama. Devuélvela desde `subscriptions()`.",
        "params": {"seconds": "Intervalo en segundos (mayor que 0)."},
        "example": """
            def subscriptions(self):
                return [pz.every(1, "tick")] if self.running else []
        """,
    },
    "pyzed.listen": {
        "desc": "Una suscripción que ejecuta `function()` (un generador o generador async) mientras esté activa y envía cada valor que produce a `update`. Ideal para websockets y streams.",
        "params": {"function": "Función generadora (normal o `async def`)."},
        "example": """
            async def feed():
                async for message in websocket:
                    yield message

            def subscriptions(self):
                return [pz.listen(feed)]
        """,
    },
    "pyzed.frames": {
        "desc": "Una suscripción que llama a `callback(dt)` una vez por fotograma (sincronizada con la pantalla, normalmente 60 veces por segundo), con `dt` los segundos desde el fotograma anterior (como mucho 0,25). Pensada para juegos y simulaciones: mueve las cosas `velocidad * dt`. Ver [Crear videojuegos](/pyzed/es/games/).",
        "params": {"callback": "Callable que recibe `dt` (un `float`).",
                   "max_fps": "Tasa máxima donde la pantalla no espera a la sincronización vertical (renderizado por software). 240 por defecto."},
        "example": """
            def subscriptions(self):
                return [] if self.paused else [pz.frames(self.tick)]

            def tick(self, dt):
                self.x += game.axis("left", "right") * 300 * dt
        """,
    },
    "pyzed.pressed": {
        "desc": "Las teclas pulsadas ahora mismo, como un `frozenset` de nombres sin modificadores (`\"left\"`, `\"space\"`, `\"a\"`…). Vacío si no hay ventana abierta. Consúltalo en cada fotograma para movimiento continuo; `on_key` es para pulsaciones puntuales.",
    },
    "pyzed.is_pressed": {
        "desc": "Si alguna de `keys` está pulsada. `held` sustituye a `pressed()` (útil en tests).",
        "params": {"keys": "Nombres de teclas, como `\"left\"`, `\"a\"`.", "held": "Conjunto opcional de teclas en lugar de `pressed()`."},
        "example": """
            if pz.is_pressed("space") and self.cooldown <= 0:
                self.fire()
        """,
    },
    "pyzed.Subscription": {"desc": "Lo que devuelven `every` y `listen`. Se identifica por su `key`: mientras `subscriptions()` siga devolviendo una con la misma clave, sigue en marcha; cuando desaparece, se detiene.", "no_signature": True},
    "pyzed.spawn": {
        "desc": "Programa una corrutina en el loop de asyncio de Pyzed sin esperar su resultado y devuelve un `concurrent.futures.Future`. Para recibir el resultado en la interfaz, devuelve la corrutina desde `update` o usa `Command.perform`.",
        "params": {"awaitable": "La corrutina."},
    },
    "pyzed.asyncio_loop": {"desc": "El loop de asyncio (en un hilo en segundo plano) donde Pyzed ejecuta todas las corrutinas. Se arranca al usarlo por primera vez."},
})

# -- Command ---------------------------------------------------------------------
_win = "La ventana (`pz.Window`). Sin ella, la que produjo el mensaje."
_page("command")["sections"][0][1].update({
    "pyzed.Command.scroll_to": {
        "desc": "Desplaza el `scrollable` con ese `id` a una posición absoluta en píxeles.",
        "params": {"id": "El `id` del scrollable.", "x": "Desplazamiento horizontal.", "y": "Desplazamiento vertical."},
    },
    "pyzed.Command.copy": {"desc": "Copia `text` al portapapeles del sistema.", "params": {"text": "El texto."}},
    "pyzed.Command.paste": {"desc": "Lee el portapapeles y llama a `then(texto)` (cadena vacía si está vacío).", "params": {"then": "Callable que recibe el texto."}},
    "pyzed.Command.paste_image": {"desc": "Lee una imagen del portapapeles (una captura, una imagen copiada) y llama a `then(png)` con sus bytes PNG, o a `then(None)` si el portapapeles no tiene una imagen.", "params": {"then": "Callable que recibe los bytes PNG o `None`."}},
    "pyzed.Command.pick_files": {"desc": "Abre el diálogo de archivos del sistema y llama a `then(rutas)` con las rutas elegidas (una lista vacía si se cancela).", "params": {"then": "Callable que recibe la lista de rutas.", "title": "El título del diálogo.", "filters": "Una lista de pares `(nombre, extensiones)`, como `[(\"Imágenes\", [\"png\", \"jpg\"])]`.", "directory": "La carpeta en la que se abre.", "multiple": "`False` elige un solo archivo.", "folder": "`True` elige carpetas en vez de archivos."}},
})
_page("command")["sections"][0][1]["pyzed.Command.perform"]["desc"] = (
    "Ejecuta `function()` en segundo plano y entrega el resultado a `then(resultado)` en el hilo de la "
    "interfaz. `function` puede ser normal (corre en un hilo) o `async def` (corre en el loop de asyncio de "
    "Pyzed). Si devuelve un generador (normal o async), `then` se llama con cada valor. También acepta una "
    "corrutina o un generador ya creados (`fetch(url)` en lugar de `fetch`). Sin `then`, los resultados van a "
    "`update`. Si `function` lanza, se imprime el error."
)
_section("command", "Ventanas y portapapeles", {
    "pyzed.Command.open_window": {"desc": "Abre una ventana nueva para esa instancia de `pz.Window`.", "params": {"window": "La ventana."}},
    "pyzed.Command.close_window": {"desc": "Cierra la ventana.", "params": {"window": _win}},
    "pyzed.Command.drag_window": {"desc": "Empieza a mover la ventana con el ratón (úsalo al pulsar una barra de título propia).", "params": {"window": _win}},
    "pyzed.Command.minimize_window": {"desc": "Minimiza la ventana.", "params": {"window": _win}},
    "pyzed.Command.toggle_maximize_window": {"desc": "Maximiza la ventana o la restaura si ya lo está.", "params": {"window": _win}},
    "pyzed.Command.maximize_window": {"desc": "Maximiza la ventana, o la restaura con `maximized=False`.", "params": {"maximized": "`False` la restaura.", "window": _win}},
    "pyzed.Command.drag_resize_window": {"desc": "Empieza a cambiar el tamaño de la ventana con el ratón desde un borde o una esquina (para ventanas sin decoraciones del sistema; `ui.window_frame` y `pz.window_edges` ya lo hacen).", "params": {"direction": '`"n"`, `"s"`, `"e"`, `"w"`, `"ne"`, `"nw"`, `"se"` o `"sw"`.', "window": _win}},
    "pyzed.Command.show_window_menu": {"desc": "Muestra el menú de ventana del sistema (mover, tamaño, cerrar…) bajo el puntero. Solo Windows tiene uno.", "params": {"window": _win}},
    "pyzed.Command.set_fullscreen": {"desc": "Pone o quita la pantalla completa.", "params": {"fullscreen": "`True` para pantalla completa.", "window": _win}},
    "pyzed.Command.resize_window": {"desc": "Cambia el tamaño de la ventana (píxeles lógicos).", "params": {"width": "Ancho.", "height": "Alto.", "window": _win}},
    "pyzed.Command.move_window": {"desc": "Mueve la ventana a una posición de la pantalla.", "params": {"x": "Posición horizontal.", "y": "Posición vertical.", "window": _win}},
    "pyzed.Command.focus_window": {"desc": "Trae la ventana al frente y le da el foco.", "params": {"window": _win}},
})

# -- Widgets ----------------------------------------------------------------------
_w = _page("widgets")["sections"]
dict(_w)["Layout"].update({
    "pyzed.grid": {
        "desc": "Coloca los hijos en una rejilla. Con `columns=3` las columnas son iguales (o `max_width` mete tantas como quepan). Con listas de pistas (`columns=[200, \"1fr\", \"auto\"]`, `rows=...`) funciona como un grid de CSS: los números son píxeles, `\"auto\"` se ajusta al contenido y `\"<n>fr\"` reparte el espacio que sobra. Envuelve los hijos en `pz.cell` para colocarlos y hacer que ocupen varias celdas; el resto llena las celdas libres fila a fila. Ver [Layout](/pyzed/es/guides/layout/#rejillas).",
        "params": {
            "columns": "Número de columnas iguales, o pistas: una lista (`[200, \"1fr\", \"auto\"]`) o un texto (`\"200 1fr auto\"`).",
            "rows": "Pistas de las filas, como `columns`. Las filas que no están en la lista son `\"auto\"`.",
            "spacing": "Espacio entre celdas.", "row_spacing": "Espacio entre filas, si es distinto.",
            "height": "Con `columns=<int>`: alto de cada fila. Con pistas: alto de la rejilla.",
            "width": "Con `columns=<int>`: píxeles. Con pistas: ancho de la rejilla (por defecto `\"fill\"`).",
            "aspect_ratio": "Mantiene las celdas en esta proporción ancho/alto (solo con `columns=<int>`).",
            "max_width": "Mete tantas columnas de como mucho este ancho como quepan (solo con `columns=<int>`).",
            "padding": "Espacio alrededor de las celdas.",
            "align_x": "Alineación horizontal de cada elemento en su celda: `\"start\"`, `\"center\"`, `\"end\"`.",
            "align_y": "Alineación vertical de cada elemento en su celda.",
        },
        "example": """
            pz.grid([pz.cell(header, column=0, row=0, column_span=2), sidebar, content],
                    columns=[200, "1fr"], rows=[48, "1fr"], spacing=8, height="fill")
        """,
    },
    "pyzed.cell": {
        "desc": "Coloca un hijo en una rejilla con pistas: su columna y fila (desde 0) y cuántas ocupa. Los hijos sin celda llenan las celdas libres fila a fila. Fuera de una rejilla es solo el hijo.",
        "params": {
            "content": "El widget.", "column": "Índice de columna (desde 0).", "row": "Índice de fila (desde 0).",
            "column_span": "Columnas que ocupa.", "row_span": "Filas que ocupa.",
            "align_x": "Alineación horizontal en la celda.", "align_y": "Alineación vertical en la celda.",
        },
        "example": 'pz.cell(ui.button("Guardar"), column=2, row=3, align_x="end")',
    },
    "pyzed.flex": {
        "desc": "Coloca los hijos a lo largo de un eje, como flexbox de CSS, con `justify` en el eje principal y `align` en el transversal. Usa `pz.flex_item` para que un hijo crezca o tenga un tamaño fijo.",
        "params": {
            "children": "Los widgets, o `pz.flex_item(...)` para hijos con su propio tamaño.",
            "direction": "`\"row\"` o `\"column\"`.",
            "justify": "`\"start\"`, `\"center\"`, `\"end\"`, `\"between\"`, `\"around\"` o `\"evenly\"`. No tiene efecto si algún hijo crece.",
            "align": "Alineación transversal: `\"start\"`, `\"center\"` o `\"end\"`.",
            "gap": "Espacio entre hijos.", "wrap": "Pasa a nuevas líneas (solo filas con `justify=\"start\"`).",
            "padding": "Espacio alrededor de los hijos.", "width": "Ancho.", "height": "Alto.",
        },
        "example": 'pz.flex([logo, titulo, pz.flex_item(buscador, grow=1), avatar], justify="between", align="center", gap=8)',
    },
    "pyzed.flex_item": {
        "desc": "Da tamaño a un hijo de `pz.flex`.",
        "params": {
            "content": "El widget.", "grow": "Parte del espacio libre en el eje principal (`0` mantiene su tamaño natural).",
            "basis": "Un tamaño fijo en píxeles en el eje principal, en lugar de crecer.", "align": "Alineación transversal de este hijo.",
        },
    },
    "pyzed.anchor": {
        "desc": "Coloca un hijo de `pz.anchor_layout` en `x`, `y` con `width` y `height` (en el tamaño de diseño de la disposición) y dice cómo sigue a un cambio de tamaño.",
        "params": {
            "content": "El widget.", "x": "Borde izquierdo en el tamaño de diseño.", "y": "Borde superior en el tamaño de diseño.",
            "width": "Ancho en el tamaño de diseño.", "height": "Alto en el tamaño de diseño.",
            "anchor": "Un preset de `pyzed.anchors.PRESETS` (`\"top_right\"`, `\"bottom_wide\"`, `\"center\"`, `\"full\"`...), palabras (`\"left right bottom\"`) o una tupla de bordes.",
            "min_width": "Ancho mínimo al estirarse (`0`: sin límite).", "min_height": "Alto mínimo al estirarse.",
            "max_width": "Ancho máximo al estirarse (`0`: sin límite).", "max_height": "Alto máximo al estirarse.",
            "pivot": "`(x, y)` de `0` a `1`: el punto que queda fijo cuando un límite lo frena, y alrededor del que gira `rotate`.",
            "rotate": "Grados en sentido horario.",
        },
        "example": 'pz.anchor(ui.button("Cerrar", on_close), x=284, y=252, width=100, height=32, anchor="bottom_right")',
    },
    "pyzed.anchor_layout": {
        "desc": "Coloca libremente hijos hechos con `pz.anchor`, como un formulario diseñado: al cambiar de tamaño, cada hijo mantiene su distancia a los bordes a los que está anclado, se estira entre bordes opuestos y se queda centrado en los demás casos. Los últimos hijos se dibujan encima. Ver [Disposiciones ancladas](/pyzed/es/guides/layout/#disposiciones-ancladas).",
        "params": {"children": "Hijos hechos con `pz.anchor(...)` (`None` se ignora).",
                   "design": "`(ancho, alto)` en el que se colocaron los hijos; por defecto, el más pequeño que los contiene.",
                   "width": "Ancho.", "height": "Alto."},
        "example": """
            pz.anchor_layout([
                pz.anchor(ui.heading("Informe"), x=16, y=12, width=368, height=28, anchor="top_wide"),
                pz.anchor(ui.button("Cerrar", on_close), x=284, y=252, width=100, height=32, anchor="bottom_right"),
            ], design=(400, 300))
        """,
    },
    "pyzed.anchors.place": {
        "desc": "Dónde va una caja diseñada en un padre de tamaño `design` dentro de un padre de tamaño `actual`, siguiendo su anclaje, con límites de tamaño y un pivote. La cuenta detrás de `pz.anchor_layout` y de los formularios diseñados.",
        "params": {"rect": "`(x, y, ancho, alto)` en el tamaño de diseño.", "anchor": "Un preset, palabras o bordes.",
                   "design": "El tamaño de diseño del padre.", "actual": "El tamaño actual del padre.",
                   "min_size": "Límites inferiores `(ancho, alto)` (`0`: ninguno).", "max_size": "Límites superiores `(ancho, alto)` (`0`: ninguno).",
                   "pivot": "El punto que queda fijo cuando un límite frena el estiramiento."},
        "example": 'anchors.place((20, 20, 100, 30), "top_right", design=(400, 300), actual=(600, 300))  # (220, 20, 100, 30)',
    },
    "pyzed.anchors.PRESETS": {"desc": "Los 16 presets de anclaje por nombre (`top_left`, `top_center`, `top_right`, `top_wide`, `center_left`, `center`, `center_right`, `center_wide`, `bottom_left`, `bottom_center`, `bottom_right`, `bottom_wide`, `left_tall`, `center_tall`, `right_tall`, `full`), cada uno con la tupla de bordes a los que ancla.", "no_signature": True},
    "pyzed.anchors.edges": {"desc": "Los bordes de un anclaje dado como nombre de preset, palabras o bordes. Lanza `ValueError` con cualquier otra cosa.", "params": {"anchor": "Lo que se lee."}},
    "pyzed.anchors.preset_of": {"desc": "El nombre del preset que corresponde a un conjunto de bordes (todo conjunto es uno de los 16).", "params": {"edges": "Bordes."}},
    "pyzed.anchors.preset": {"desc": "El preset colocado `horizontal` (`left`, `center`, `right`, `wide`) y `vertical` (`top`, `center`, `bottom`, `tall`).", "params": {"horizontal": "Colocación en el eje x.", "vertical": "Colocación en el eje y."}},
    "pyzed.anchors.axes": {"desc": "La colocación `(horizontal, vertical)` de un conjunto de bordes, como `(\"right\", \"top\")`.", "params": {"edges": "Bordes."}},
    "pyzed.anchors.snap_to": {"desc": "Una caja movida (y redimensionada en los ejes estirados) adonde apunta un anclaje: contra los bordes anclados, centrada o llenando el padre, a `margin` píxeles.", "params": {"anchor": "Un preset, palabras o bordes.", "rect": "La caja.", "parent": "El tamaño del padre.", "margin": "Distancia a los bordes."}},
    "pyzed.anchors.offsets": {"desc": "Las distancias `(izquierda, arriba, derecha, abajo)` de cada lado del padre a una caja.", "params": {"rect": "La caja.", "parent": "El tamaño del padre."}},
    "pyzed.anchors.pivot_offset": {"desc": "La traslación que hace que una rotación y una escala (que giran alrededor del centro de la caja) giren alrededor de `pivot`.", "params": {"size": "El tamaño de la caja.", "pivot": "`(x, y)` de `0` a `1`.", "rotate": "Grados en sentido horario.", "scale": "Factor de escala."}},
    "pyzed.window_edges": {
        "desc": "Envuelve la vista entera de una ventana sin decoraciones del sistema para que pulsar cerca de sus bordes cambie el tamaño de la ventana (las esquinas ocupan el doble). `ui.window_frame` ya lo usa.",
        "params": {"content": "La vista entera de la ventana.", "border": "Ancho en píxeles de la zona que redimensiona.", "enabled": "`False` lo desactiva (para una ventana maximizada)."},
        "example": "pz.window_edges(view, enabled=not self.window_maximized)",
    },
    "pyzed.resizable": {
        "desc": "Un panel cuyo borde `edge` se arrastra para cambiar su tamaño. Conserva el tamaño al que lo arrastra el usuario; `on_resize(size)` se llama al terminar de arrastrar para que puedas guardarlo. Si `size` cambia después, vuelve a ese valor.",
        "params": {
            "content": "El contenido del panel.",
            "edge": "El borde con el asa: `\"right\"` (una barra lateral izquierda), `\"left\"`, `\"top\"` (un panel inferior) o `\"bottom\"`.",
            "size": "Ancho inicial (alto con los bordes top/bottom).",
            "min_size": "Tamaño mínimo.", "max_size": "Tamaño máximo.",
            "on_resize": "Se llama con el nuevo tamaño al terminar de arrastrar.",
            "color": "Color de la línea.", "hover_color": "Color de la línea al pasar el ratón o arrastrar.",
            "thickness": "Grosor de la línea.", "handle": "Ancho de la zona que se puede agarrar.",
            "width": "Ancho con los bordes top/bottom.", "height": "Alto con los bordes left/right.",
        },
        "example": 'pz.row([pz.resizable(barra, edge="right", size=240, on_resize=self.guardar_ancho), editor])',
    },
    "pyzed.split": {
        "desc": "Dos paneles con un divisor que se arrastra. Para el estilo del tema usa `ui.split`.",
        "params": {
            "first": "Primer panel.", "second": "Segundo panel.",
            "ratio": "Proporción del primer panel (0–1). El divisor conserva la proporción a la que lo arrastra el usuario hasta que esto cambia.",
            "on_resize": "Callable que recibe la nueva proporción mientras se arrastra.",
            "vertical": "Apila los paneles arriba/abajo.",
            "min_size": "Tamaño mínimo del primer panel.", "min_size_second": "Tamaño mínimo del segundo panel.",
            "color": "Color del divisor.", "hover_color": "Color del divisor al pasar el ratón o arrastrar.",
            "thickness": "Grosor de la línea.",
        },
    },
    "pyzed.pin": {
        "desc": "Coloca `content` en `(x, y)` dentro de una caja. Úsalo en un `stack` para posicionar popovers y menús contextuales.",
        "params": {"x": "Posición horizontal.", "y": "Posición vertical."},
    },
    "pyzed.responsive": {
        "desc": "Construye su contenido con `function(ancho, alto)` usando el espacio realmente disponible, para que el layout se adapte (por ejemplo, ocultar una barra lateral si la ventana es estrecha).",
        "params": {"function": "Función que recibe `(ancho, alto)` y devuelve un widget."},
    },
})
_section("widgets", "Imágenes y contenido", {
    "pyzed.image": {
        "desc": "Una imagen de mapa de bits (PNG, JPEG, GIF, BMP, WebP…) desde una ruta o `bytes`, o píxeles RGBA crudos.",
        "params": {"radius": "Radio de las esquinas.", "scale": "Escala.", "size": "`(ancho, alto)` cuando `source` son píxeles RGBA crudos."},
        "example": 'pz.image("foto.jpg", width=320, content_fit="cover", radius=8)',
    },
    "pyzed.image_viewer": {
        "desc": "Una imagen que se puede desplazar (arrastrando) y ampliar (rueda del ratón), como el visor de Iced.",
        "params": {"min_scale": "Zoom mínimo.", "max_scale": "Zoom máximo.", "scale_step": "Cuánto cambia el zoom por paso de rueda.", "size": "`(ancho, alto)` para píxeles RGBA crudos."},
    },
    "pyzed.markdown": {
        "desc": "Renderiza Markdown (títulos, listas, bloques de código, citas, tablas, enlaces…). Para los colores del tema usa `ui.markdown`.",
        "params": {"source": "El texto Markdown.", "link_color": "Color de los enlaces.", "code_color": "Color del código.", "code_bg": "Fondo del código.", "on_link": "Callable que recibe la URL al pulsar un enlace."},
    },
    "pyzed.rich_text": {
        "desc": "Texto hecho de fragmentos con estilos distintos. Los textos sueltos son fragmentos sin estilo.",
        "params": {"spans": "Lista de `span(...)` o textos.", "line_height": "Alto de línea."},
        "example": 'pz.rich_text(["Pulsa ", pz.span("aquí", color="#74ade8", underline=True, link=self.abrir), " para abrir."])',
    },
    "pyzed.span": {
        "desc": "Un fragmento con estilo para `rich_text`. Con `link`, al pulsarlo se envía (o se llama) ese valor.",
        "params": {"text": "El texto.", "radius": "Radio del fondo.", "underline": "Subrayado.", "strikethrough": "Tachado.", "link": "Mensaje o callable al pulsarlo."},
    },
    "pyzed.Span": {"desc": "El tipo de los fragmentos que crea `pz.span`.", "no_signature": True},
    "pyzed.qr_code": {
        "desc": "Un código QR que codifica `data`.",
        "params": {"data": "El texto o URL a codificar.", "cell_size": "Tamaño de cada módulo en píxeles."},
    },
    "pyzed.shader": {
        "desc": "Un widget que pinta la GPU con tu función WGSL `fn shade(uv, px, size, time) -> vec4<f32>`, que devuelve el color de cada píxel, o con un grafo de shader hecho de nodos (una ruta `.pzshad` o un `Graph` o `Shader` de [`pyzed.shading`](/pyzed/es/reference/shading/)). Cada entrada de `uniforms` se convierte en una función con su nombre (`{\"speed\": 2}` -> `speed()`); `mouse()` da la posición del puntero. Sin GPU el widget muestra `fallback`. Lanza `ValueError` con el mensaje del compilador si el código no es válido. Ver la guía de [shaders](/pyzed/es/shading/shaders/).",
        "params": {
            "code": "Código WGSL que define `shade` (y las funciones auxiliares que quieras), o una ruta `.pzshad`, un `Graph` o un `Shader`.",
            "uniforms": "Hasta 32 valores con nombre: un número, de 2 a 4 números o un color. Con un `.pzshad`, las variables mutables del shader por nombre.",
            "textures": "Hasta 8 imágenes, `{nombre: ruta}`: cada una se convierte en `nombre(uv)`, el color de la imagen en `uv`.",
            "width": "Ancho (`\"fill\"` por defecto).",
            "height": "Alto (`\"fill\"` por defecto).",
            "animate": "Redibuja en cada frame para que avance `time` (`True`).",
            "time": "Un `time` fijo en segundos, para un fotograma quieto.",
            "fallback": "Color o degradado que se muestra sin GPU.",
        },
    },
    "pyzed.canvas": {
        "desc": "Una superficie de dibujo 2D. `shapes` es una lista creada con [`pyzed.draw`](/pyzed/es/reference/draw/). Los callbacks del ratón reciben coordenadas relativas al canvas. Con un `id`, la geometría se cachea entre frames y solo se recalcula cuando cambian las formas. Ver la guía de [dibujo con canvas](/pyzed/es/guides/canvas/).",
        "params": {
            "shapes": "Lista de formas de `pyzed.draw` (se aceptan listas anidadas).",
            "id": "Activa la caché de geometría.",
            "on_press": "Callable que recibe `(x, y)` al pulsar.",
            "on_release": "Callable que recibe `(x, y)` al soltar.",
            "on_right_press": "Callable que recibe `(x, y)` con clic derecho.",
            "on_scroll": "Callable que recibe `(dx, dy)` en líneas al usar la rueda.",
            "cursor": "Cursor del ratón (`\"crosshair\"`, `\"pointer\"`…).",
        },
    },
}, before="Interacción")
dict(_w)["Controles"].update({
    "pyzed.vertical_slider": {"desc": "Un deslizador vertical (`slider(..., vertical=True)`).", "params": {"min": "Mínimo.", "max": "Máximo.", "kwargs": "Los de `slider`."}},
    "pyzed.pick_list": {
        "desc": "Un desplegable para elegir una de `options`. `on_select(opción)` recibe la elegida. Para el desplegable con tema usa `ui.select`.",
        "params": {
            "selected": "Opción actual.", "handle": "Carácter del icono de la flecha.", "handle_size": "Tamaño de la flecha.",
            "menu_height": "Alto máximo del menú.", "font": "Familia de la fuente.",
            "placeholder_color": "Color del placeholder.", "handle_color": "Color de la flecha.",
            "on_open": "Se envía al abrir el menú.", "on_close": "Se envía al cerrar el menú.",
            "menu_bg": "Fondo del menú.", "menu_color": "Texto del menú.", "menu_border_color": "Borde del menú.",
            "selected_bg": "Fondo de la opción resaltada.", "selected_color": "Texto de la opción resaltada.",
        },
    },
    "pyzed.radio": {
        "desc": "Un botón de radio. Agrupa varios tú mismo (o usa `ui.radio_group`); `on_select` se envía al pulsarlo.",
        "params": {"selected": "Si está marcado.", "on_select": "Mensaje o callable al pulsarlo.", "spacing": "Separación entre el círculo y el texto."},
    },
})
dict(_w)["Interacción"]["pyzed.mouse_area"]["params"]["on_scroll"] = "Callable que recibe `(dx, dy)` en líneas al usar la rueda."
dict(_w)["Layout"]["pyzed.scrollable"]["params"]["on_scroll"] = "Callable que recibe un dict con `x`, `y`, `relative_x`, `relative_y`, `width`, `height`, `content_width` y `content_height`."
dict(_w)["Controles"]["pyzed.slider"]["params"]["on_release"] = "Se envía al soltar el tirador."

# -- UI -----------------------------------------------------------------------------
_section("ui", "Controles", {
    "pyzed.ui.select": {
        "desc": "Un desplegable con el estilo del tema. Las opciones se muestran con `str()`, así que sirven textos, enums, dataclasses o modelos de base de datos; `on_select` recibe el objeto elegido, no su texto.",
        "params": {"selected": "Opción actual.", "size": '`"sm"`, `"md"` o `"lg"`.', "disabled": "Lo atenúa.", "invalid": "Pinta el borde con el color de error.", "on_open": "Se envía al abrir el menú.", "on_close": "Se envía al cerrar el menú."},
    },
    "pyzed.ui.radio_group": {
        "desc": "Opciones mutuamente excluyentes como botones de radio.",
        "params": {"options": "Textos o pares `(valor, etiqueta)`.", "selected": "Valor actual.", "on_select": "Callable que recibe el valor elegido.", "horizontal": "En fila en lugar de columna.", "disabled": "`True`, o los valores a desactivar.", "descriptions": "Asocia valores a una línea atenuada bajo su etiqueta."},
    },
    "pyzed.ui.number_field": {
        "desc": "Un campo numérico con botones −/+. `on_change(valor)` recibe el número ya limitado a `min`/`max`; lo que no se puede leer como número se ignora. Tras pulsarlo, ↑/↓ lo mueven un paso (con Shift, diez) e Inicio/Fin saltan a `min`/`max`.",
        "params": {"min": "Mínimo.", "max": "Máximo.", "step": "Paso de los botones.", "suffix": "Unidad que se muestra al final (`\"px\"`, `\"%\"`…).", "align": 'Dónde va el número entre los botones: `"center"` (por defecto), `"start"` o `"end"`.', "prefix": "Texto antes del número (`\"$\"`…).", "decimals": "Decimales que muestra (por defecto, los de `step`).", "disabled": "Lo atenúa.", "invalid": "Pinta el borde con el color de error.", "on_submit": "Se envía con Enter."},
    },
    "pyzed.ui.split_button": {
        "desc": "Un botón con una flecha aparte para más opciones. `on_press` ejecuta la acción principal y `on_menu` normalmente abre un `ui.menu` en un `ui.popover`.",
        "params": {"content": "Texto del botón.", "variant": "Como en `ui.button`.", "size": _SIZES, "tint": "Como en `ui.button`.", "disabled": "Desactiva las dos mitades.", "tooltip": "Tooltip de la mitad principal."},
    },
    "pyzed.ui.toggle_group": {
        "desc": "Un control segmentado solo con iconos.",
        "params": {"options": "`(valor, nombre_de_icono)` o `(valor, nombre_de_icono, tooltip)`.", "selected": "Valor actual (una colección con `multiple`).", "multiple": "Cada botón activa o desactiva su valor.", "disabled": "`True`, o los valores a desactivar."},
    },
    "pyzed.ui.chip": {
        "desc": "Una etiqueta compacta, opcionalmente pulsable (filtros) y con botón para quitarla.",
        "params": {"content": "Texto.", "on_remove": "Muestra una ✕ que envía esto al pulsarla.", "tint": "Color cuando está seleccionada (un token del tema).", "disabled": "La atenúa e ignora las pulsaciones."},
    },
    "pyzed.ui.disclosure": {
        "desc": "Una sección plegable: cabecera con flecha que muestra u oculta `content`. El estado abierto es tuyo: cámbialo en `on_toggle`.",
        "params": {"title": "Título (texto o widget).", "content": "Contenido.", "open": "Si está abierta.", "on_toggle": "Mensaje o callable al pulsar la cabecera."},
    },
    "pyzed.ui.AccordionSection": {
        "desc": "Una sección de `ui.accordion`: `key`, `title`, `content` y, opcionales, `icon` y un widget `end` en la cabecera.",
    },
    "pyzed.ui.accordion": {
        "desc": "Secciones plegables apiladas y separadas por divisores, como los paneles de una pantalla de ajustes. Cada cabecera ocupa todo el ancho, así que el contenido queda alineado con el resto del panel. El estado abierto es tuyo: cámbialo en `on_toggle`.",
        "params": {"sections": "Elementos `ui.AccordionSection(key, title, content, icon=None, end=None)` (o tuplas `(key, title, content)`).", "open": "El conjunto de ids abiertos, un dict `{id: bool}` o `True` para todos.", "on_toggle": "Se llama con la clave de la cabecera pulsada.", "icons": "`{id: icono}`: un icono de Lucide para cada cabecera.", "spacing": "Espacio alrededor de los divisores entre secciones.", "padding": "Relleno alrededor del contenido de una sección abierta."},
        "example": """
            ui.accordion([
                ui.AccordionSection("layout", "Layout", layout_rows, icon="ruler"),
                ui.AccordionSection("events", "Events", event_rows, icon="zap"),
            ], open=self.open_sections, on_toggle=lambda key: self.open_sections.symmetric_difference_update({key}))
        """,
    },
}, before="Listas, árbol y menús")
_section("ui", "Datos y feedback", {
    "pyzed.ui.callout": {
        "desc": "Un aviso en línea (un callout o banner).",
        "params": {"title": "Título (texto o widget).", "tint": '`"info"`, `"success"`, `"warning"`, `"error"` o `"hint"`: elige el color y el icono.', "on_dismiss": "Añade un botón de cerrar."},
    },
    "pyzed.ui.empty_state": {
        "desc": "Un marcador centrado para listas vacías, búsquedas sin resultados, etc.",
        "params": {"title": "Título."},
    },
    "pyzed.ui.settings_group": {
        "desc": "Un bloque con título de filas `ui.field` separadas por líneas, como una pantalla de ajustes.",
        "params": {"title": "Título del grupo.", "rows": "Las filas (normalmente `ui.field`)."},
    },
    "pyzed.ui.Column": {
        "desc": 'Una columna de `ui.table`. `key` es una clave de dict, un nombre de atributo o una función de la fila; `render` (opcional) convierte el valor en un widget. `width` es `"fill"`, un número o una porción como `"fill:2"`.',
        "params": {"title": "Encabezado (y nombre para ordenar).", "key": "Cómo obtener el valor de cada fila.", "align": '`"start"`, `"center"` o `"end"`.', "render": "Función valor → widget.", "sortable": "Si el encabezado se puede pulsar para ordenar."},
    },
    "pyzed.ui.table": {
        "desc": "Una tabla de datos con encabezado fijo, orden opcional y selección de filas. El orden se hace aquí cuando `sort_by` nombra una columna: pulsar un encabezado llama a `on_sort(título)` y tú cambias `sort_by`/`descending` en tu estado. Las filas están virtualizadas: solo se construyen las visibles, así que cientos de miles de filas se desplazan con fluidez.",
        "params": {
            "columns": "`ui.Column` o claves simples.", "rows": "Dicts u objetos.", "sort_by": "Título de la columna por la que se ordena.",
            "descending": "Orden descendente.", "on_sort": "Callable que recibe el título pulsado.", "on_row_press": "Callable que recibe la fila pulsada.",
            "selected": "La fila resaltada.", "striped": "Filas alternas sombreadas.", "row_height": "Alto de cada fila.",
        },
    },
    "pyzed.ui.stat": {
        "desc": "Un número de panel: título, valor grande, variación opcional (`+4.2%`) y sparkline.",
        "params": {"title": "Título.", "delta": "Variación en %; verde si es positiva, roja si no.", "trend": "Valores para la sparkline."},
    },
    "pyzed.ui.sparkline": {
        "desc": "Un gráfico de línea diminuto para tendencias.",
        "params": {"values": "Valores.", "fill": "Rellena el área bajo la línea."},
    },
    "pyzed.ui.bar_chart": {
        "desc": "Un gráfico de barras vertical con etiquetas opcionales.",
        "params": {"values": "Valores.", "labels": "Etiquetas bajo cada barra."},
    },
    "pyzed.ui.donut": {
        "desc": "Un gráfico de anillo; `label` se dibuja en el centro.",
        "params": {"values": "Valores.", "colors": "Colores (por defecto, los del tema).", "thickness": "Grosor del anillo.", "label": "Texto central."},
    },
    "pyzed.ui.spinner": {
        "desc": "Un arco que gira para estados de carga. Su ángulo sale del reloj, así que mantén una suscripción `pz.every(1/30, ...)` activa mientras se muestra.",
        "params": {"speed": "Vueltas por segundo."},
    },
    "pyzed.ui.count_badge": {
        "desc": "Un contador redondo (notificaciones, problemas…). Muestra `99+` por encima de `max`.",
        "params": {"count": "El número.", "max": "Máximo antes de mostrar `N+`."},
    },
    "pyzed.ui.facepile": {
        "desc": "Avatares superpuestos de colaboradores, como en la barra de título de un editor colaborativo. Los que pasan de `max_shown` se agrupan en `+N`.",
        "params": {"people": "Iniciales o nombres.", "overlap": "Solapamiento en píxeles.", "max_shown": "Cuántos mostrar."},
    },
    "pyzed.ui.diff_stat": {
        "desc": "`+12 −3` con bloques de colores al estilo de GitHub.",
        "params": {"added": "Líneas añadidas.", "removed": "Líneas eliminadas.", "blocks": "Número de bloques."},
    },
    "pyzed.ui.keybinding_hint": {
        "desc": "Una pista atenuada como «Abrir archivo Ctrl P» para pies y estados vacíos.",
        "params": {"text": "Texto."},
    },
    "pyzed.ui.markdown": {
        "desc": "`pz.markdown` con los colores de texto, enlaces y código del tema.",
        "params": {"source": "El texto Markdown.", "on_link": "Callable que recibe la URL al pulsar un enlace."},
    },
    "pyzed.ui.split": {
        "desc": "`pz.split` con el divisor del color de borde del tema (acento al arrastrarlo).",
        "params": {"first": "Primer panel.", "second": "Segundo panel.", "ratio": "Proporción del primero (0–1).", "on_resize": "Callable que recibe la nueva proporción.", "min_size": "Tamaño mínimo de cada panel.", "kwargs": "Los de `pz.split`."},
    },
}, before="Listas, árbol y menús")
dict(_page("ui")["sections"])["Overlays"]["pyzed.ui.popover"] = {
    "desc": "Muestra `content` (un `ui.menu`, una tarjeta…) sobre `base` en `(x, y)`. Hacer clic en cualquier otro sitio llama a `on_dismiss`. Para un menú de clic derecho, guarda la posición del ratón con `mouse_area(on_move=...)` y abre el popover desde `on_right_press` (ver `examples/context_menu.py`).",
    "params": {"base": "La interfaz de debajo.", "content": "Lo que flota (o `None`).", "x": "Posición horizontal.", "y": "Posición vertical."},
}

# -- Theme ------------------------------------------------------------------------------
_t = _page("theme")
_t["sections"][0][1].update({
    "pyzed.Theme.with_accent": {"desc": "Una copia con otro color de acento y todo lo que depende de él (foco, selección, enlaces, botones principales, texto sobre acento).", "params": {"accent": "El color."}},
    "pyzed.Theme.generate": {
        "desc": "Crea un tema completo a partir de unos pocos colores. Superficies, bordes, estados de hover y textos atenuados se mezclan a partir de `background` y `text`; la apariencia se deduce del brillo del fondo si no se indica.",
        "params": {"name": "Nombre.", "background": "Color del editor/fondo.", "text": "Color del texto.", "accent": "Color de acento.", "appearance": '`"dark"` o `"light"`.', "error": "Color de error.", "warning": "Color de aviso.", "success": "Color de éxito.", "syntax": "Colores de sintaxis extra.", "radius": "Radio de las esquinas."},
        "example": 'pz.Theme.generate("Propio", background="#1b1d23", text="#e6e6e6", accent="#ff8a65")',
    },
    "pyzed.Theme.from_zed": {
        "desc": "Lee un tema de un archivo de familia de temas de Zed (`.json`) o un dict. Una familia suele tener varios (Ayu Dark/Light/Mirage); `name` elige uno (por defecto, el primero).",
        "params": {"source": "Ruta, texto JSON o dict.", "name": "Nombre del tema dentro de la familia."},
    },
    "pyzed.Theme.to_dict": {"desc": "Un dict apto para JSON; `Theme.from_dict` lo vuelve a leer."},
    "pyzed.Theme.from_dict": {"desc": "Crea un tema a partir de `to_dict`. Los tokens que falten salen de `base` (One Dark u One Light según `appearance`).", "params": {"data": "Los tokens.", "base": "Tema base."}},
    "pyzed.Theme.save": {"desc": "Guarda el tema como JSON (formato propio de Pyzed).", "params": {"path": "Ruta del archivo."}},
    "pyzed.Theme.load": {"desc": "Lee un tema escrito con `save` (para temas de Zed usa `from_zed`).", "params": {"path": "Ruta del archivo."}},
})
dict(_t["sections"])["Temas incluidos"].update({
    "pyzed.themes.names": {"desc": "Nombres de todos los temas registrados."},
    "pyzed.themes.get": {"desc": "Busca un tema por nombre (sin distinguir mayúsculas). Lanza `KeyError` si no existe.", "params": {"name": "Nombre."}},
    "pyzed.themes.register": {"desc": "Añade (o reemplaza) un tema para poder usarlo por su nombre.", "params": {"theme": "El tema."}},
    "pyzed.themes.load_zed": {"desc": "Carga y registra todos los temas de un archivo de familia de Zed.", "params": {"source": "Ruta, texto JSON o dict."}},
    "pyzed.themes.auto": {"desc": "Un tema que sigue el modo claro/oscuro del sistema.", "params": {"light": "Tema (o nombre) para modo claro.", "dark": "Tema (o nombre) para modo oscuro."}},
    "pyzed.AutoTheme": {"desc": "Lo que devuelve `themes.auto`: un par `(light, dark)`. `pick(dark)` devuelve el que toca.", "no_signature": True},
})
_t["sections"][1][1]["pyzed.themes"]["desc"] = (
    "Espacio de nombres con los temas incluidos (las familias One, Ayu y Gruvbox) y el registro de "
    "temas. Los incluidos también están como atributos: `themes.ONE_DARK`, `themes.ONE_LIGHT`, "
    "`themes.AYU_DARK`, `themes.AYU_LIGHT`, `themes.AYU_MIRAGE`, `themes.GRUVBOX_DARK`, `themes.GRUVBOX_LIGHT`…"
)
dict(_t["sections"])["Utilidades (pyzed.theme)"].update({
    "pyzed.theme.resolve": {"desc": "Convierte un valor de `App.theme` (tema, nombre, `AutoTheme` o `None`) en un `Theme`.", "params": {"value": "El valor.", "dark": "Si el sistema está en modo oscuro."}},
    "pyzed.theme.lighten": {"desc": "Aclara un color.", "params": {"color": "Color hex.", "amount": "Cantidad de 0 a 1."}},
    "pyzed.theme.darken": {"desc": "Oscurece un color.", "params": {"color": "Color hex.", "amount": "Cantidad de 0 a 1."}},
    "pyzed.theme.luminance": {"desc": "Luminancia relativa (WCAG) de un color, de 0 a 1.", "params": {"color": "Color hex."}},
    "pyzed.theme.contrast": {"desc": "Relación de contraste WCAG entre dos colores (1 a 21).", "params": {"a": "Primer color.", "b": "Segundo color."}},
    "pyzed.theme.readable_on": {"desc": "Devuelve `light` u `dark`, el que más contraste tenga sobre `background`.", "params": {"background": "Color de fondo.", "light": "Texto claro.", "dark": "Texto oscuro."}},
})

# -- Draw ---------------------------------------------------------------------------------
_paint = {"fill": "Color de relleno.", "stroke": "Color del trazo.", "width": "Grosor del trazo.", "dash": "Patrón de guiones, p. ej. `[6, 4]`.", "cap": '`"round"`, `"square"` o `"butt"`: forma de los extremos.'}
PAGES.append({
    "slug": "draw",
    "title": "Dibujo (pyzed.draw)",
    "description": "Referencia de la API de pyzed.draw: formas, trazados, texto y transformaciones para dibujar gráficos 2D propios en un pz.canvas de tu app.",
    "order": 7,
    "intro": """
        Las formas de `pyzed.draw` son diccionarios simples que se pasan a [`pz.canvas`](/pyzed/es/reference/widgets/#canvas).
        Los ángulos van en grados y `y` crece hacia abajo. Ver la guía de [dibujo con canvas](/pyzed/es/guides/canvas/).

        ```python
        from pyzed import draw

        pz.canvas([
            draw.background("#1e2127"),
            draw.circle(100, 100, 40, fill="#74ade8"),
            draw.text(100, 180, "Hola", color="#dce0e5", align_x="center"),
        ], width=200, height=200)
        ```
    """,
    "sections": [
        ("Formas", {
            "pyzed.draw.background": {"desc": "Rellena todo el canvas.", "params": {"color": "Color."}},
            "pyzed.draw.rect": {"desc": "Un rectángulo, relleno y/o con trazo.", "params": {**_paint, "x": "Izquierda.", "y": "Arriba.", "w": "Ancho.", "h": "Alto.", "radius": "Radio de las esquinas."}},
            "pyzed.draw.rects": {"desc": "Muchos rectángulos rellenos de un color en una sola forma (rápido para rejillas y barras).", "params": {"items": "Tuplas `(x, y, w, h)`.", "fill": "Color."}},
            "pyzed.draw.circle": {"desc": "Un círculo centrado en `(x, y)`.", "params": {**_paint, "x": "Centro x.", "y": "Centro y.", "r": "Radio."}},
            "pyzed.draw.line": {"desc": "Una línea recta.", "params": {**_paint, "x1": "Inicio x.", "y1": "Inicio y.", "x2": "Fin x.", "y2": "Fin y."}},
            "pyzed.draw.polyline": {"desc": "Une `points` con líneas rectas (`closed=True` cierra la figura).", "params": {**_paint, "points": "Lista de `(x, y)`.", "closed": "Cierra la figura."}},
            "pyzed.draw.polygon": {"desc": "Una figura cerrada que pasa por `points`.", "params": {**_paint, "points": "Lista de `(x, y)`."}},
            "pyzed.draw.arc": {"desc": "Un arco de circunferencia de `start` a `end` grados (0 = las 3 en punto, sentido horario). `pie=True` lo cierra por el centro (porción de tarta).", "params": {**_paint, "x": "Centro x.", "y": "Centro y.", "r": "Radio.", "start": "Ángulo inicial.", "end": "Ángulo final.", "pie": "Cierra por el centro."}},
            "pyzed.draw.path": {
                "desc": "Un trazado libre con operaciones tipo SVG: `(\"M\", x, y)` mover, `(\"L\", x, y)` línea, `(\"Q\", cx, cy, x, y)` curva cuadrática, `(\"C\", c1x, c1y, c2x, c2y, x, y)` curva cúbica, `(\"A\", cx, cy, r, inicio, fin)` arco, `(\"Z\",)` cerrar.",
                "params": {**_paint, "ops": "Lista de operaciones."},
            },
            "pyzed.draw.text": {"desc": "Texto anclado en `(x, y)`; `align_x`/`align_y` eligen qué lado del texto queda en ese punto.", "params": {"x": "Posición x.", "y": "Posición y.", "content": "El texto.", "color": "Color.", "size": "Tamaño.", "font": "Familia.", "weight": "Peso.", "align_x": '`"start"`, `"center"` o `"end"`.', "align_y": '`"top"`, `"center"` o `"bottom"`.'}},
            "pyzed.draw.image": {"desc": "Un mapa de bits (sprite) dibujado en la caja `(x, y, w, h)`. Se decodifica una vez por origen y queda en caché, así que dibujarlo en cada fotograma es barato. Ver [Crear videojuegos](/pyzed/es/games/).", "params": {"source": "Una ruta, bytes de una imagen (PNG, JPEG…) o bytes RGBA con `size`.", "x": "Izquierda.", "y": "Arriba.", "w": "Ancho.", "h": "Alto.", "rotation": "Grados, alrededor de su centro.", "opacity": "De 0 a 1.", "pixelated": "Escalado por vecino más cercano, para pixel art.", "size": "`(ancho, alto)` de los bytes RGBA."}},
        }),
        ("Transformaciones", {
            "pyzed.draw.translate": {"desc": "Desplaza las formas que vienen después.", "params": {"x": "Horizontal.", "y": "Vertical."}},
            "pyzed.draw.rotate": {"desc": "Gira las formas que vienen después alrededor del origen actual.", "params": {"degrees": "Grados."}},
            "pyzed.draw.scale": {"desc": "Escala las formas que vienen después.", "params": {"x": "Factor horizontal.", "y": "Factor vertical (por defecto, igual que `x`)."}},
            "pyzed.draw.save": {"desc": "Guarda la transformación actual (úsalo con `restore`)."},
            "pyzed.draw.restore": {"desc": "Vuelve a la transformación guardada por el último `save`."},
            "pyzed.draw.group": {"desc": "Dibuja `shapes` desplazadas, giradas y escaladas sin afectar a las formas siguientes. Devuelve una lista: expándela con `*`.", "params": {"shapes": "Las formas.", "x": "Desplazamiento x.", "y": "Desplazamiento y.", "rotation": "Grados.", "scale_by": "Escala."}},
        }),
    ],
})
for p in PAGES:
    if p["slug"] == "icons":
        p["order"] = 8


# -- Hot reload, eventos y componentes -----------------------------------------
_page("app")["sections"][0][1]["pyzed.run"].setdefault("params", {}).update({
    "reload": "Hot reload: al guardar un archivo del proyecto se actualiza la ventana sin perder el estado. `None` sigue a `PYZED_RELOAD` (lo define `pyzed dev`).",
    "watch": "Carpetas o archivos extra a vigilar para el hot reload.",
})
_section("app", "Eventos y componentes", {
    "pyzed.on": {
        "desc": "Añade handlers de eventos comunes a un widget; igual que `widget.on(...)`. Eventos: `click`, `double_click`, `right_click`, `middle_click`, `mouse_down`, `mouse_up`, `mouse_enter`, `mouse_leave`, `mouse_move`, `scroll`, `drag_start`, `drag`, `drag_end`, `focus`, `blur`, `key_down`, `key_up`, `resize`. Ver [Eventos](/pyzed/es/guides/events/).",
        "params": {
            "widget": "El widget (un texto se envuelve en un container).",
            "cursor": 'Cursor del ratón sobre el widget, como `"pointer"` o `"grab"`.',
            "handlers": "Pares `evento=handler`. Un handler con un argumento recibe un `pz.Event`; un valor no invocable es un mensaje para `update`; `None` lo quita.",
        },
        "example": """
            pz.container(tarjeta, padding=12).on(click=self.seleccionar, drag=lambda e: self.mover(e.dx, e.dy))
        """,
    },
    "pyzed.Event": {
        "desc": "Lo que pasó, se le pasa a los handlers: `type`, `x`, `y` (relativos al widget), `dx`, `dy` (scroll o movimiento del arrastre), `width`, `height`, `button`, `key`, `shift`, `ctrl`, `alt`, `logo`, `window_x`, `window_y`, `screen_x`, `screen_y` (el puntero en la ventana y en la pantalla), y `value`/`source` en eventos propios.",
    },
    "pyzed.Dock": {
        "desc": "Un espacio de trabajo estilo editor: un `center` con `pz.DockPanel` acoplados a la izquierda, derecha, abajo o arriba. El usuario cambia el tamaño de un lado arrastrando su borde interior y mueve un panel arrastrando su pestaña a una zona de destino (o desde el menú del clic derecho de la pestaña). `on_layout` recibe la disposición como un dict para guardarla; pásala de vuelta en `layout=`. Ver [Layout](/pyzed/es/guides/layout/#paneles-acoplables-y-redimensionables).",
        "params": {
            "args": "Props por posición: `center`, `panels`, `layout`.", "kwargs": "Props y handlers por nombre, además de `key=`.",
            "center": "El área principal.", "panels": "Una lista de `pz.DockPanel`.",
            "layout": "Una disposición guardada (de `on_layout`) para restaurarla.",
            "on_layout": "Se llama con `event.value` = `{positions, sizes, active, hidden}` cuando los paneles se mueven, cambian de tamaño o de pestaña.",
        },
        "example": """
            pz.Dock(center=editor, panels=[
                pz.DockPanel("project", "Proyecto", arbol, icon="folder", side="left"),
                pz.DockPanel("terminal", "Terminal", terminal, icon="terminal", side="bottom"),
            ], layout=self.disposicion, on_layout=lambda e: setattr(self, "disposicion", e.value))
        """,
    },
    "pyzed.DockPanel": {
        "desc": "Un panel para `pz.Dock`.",
        "params": {
            "id": "Id estable (se usa en la disposición guardada).", "title": "Título de la pestaña.", "content": "El widget del panel.",
            "icon": "Icono de Lucide para la pestaña.", "side": 'Lado inicial: `"left"`, `"right"`, `"bottom"` o `"top"`.',
        },
    },
    "pyzed.Component": {
        "desc": "Clase base de los componentes propios, como en React: los atributos de clase anotados son props, los demás atributos son estado que se conserva entre renders, `render()` devuelve widgets y `events` declara eventos propios que se lanzan con `self.emit(nombre, valor)`. Llamar a la clase devuelve un widget. Aparecen en la biblioteca del diseñador. Ver [Componentes propios](/pyzed/es/guides/components/).",
        "example": """
            class Rating(pz.Component):
                value: int = 0
                events = {"change": "Se eligió una estrella."}

                def render(self):
                    return pz.row([pz.text("★").on(click=lambda i=i: self.emit("change", i)) for i in range(1, 6)])

            Rating(value=3, on_change=lambda e: print(e.value))
        """,
    },
    "pyzed.Color": {
        "desc": "Anotación para un prop de componente que guarda un color (un token del tema o `\"#rrggbb\"`): el diseñador muestra un selector de color. En ejecución es un `str` normal.",
        "example": 'tint: pz.Color = "accent"',
    },
    "pyzed.Icon": {
        "desc": "Anotación para un prop de componente que guarda el nombre de un icono de Lucide: el diseñador muestra un selector de icono. En ejecución es un `str` normal.",
        "example": 'mark: pz.Icon = "star"',
    },
    "pyzed.Multiline": {
        "desc": "Anotación para un prop de componente con texto largo: el diseñador muestra un área de texto. En ejecución es un `str` normal.",
        "example": 'notes: pz.Multiline = ""',
    },
    "pyzed.Range": {
        "desc": "Límites de un prop numérico, con `typing.Annotated`: el diseñador muestra un campo numérico limitado a ellos. Ver [Componentes propios](/pyzed/es/guides/components/#en-el-diseñador).",
        "params": {"min": "Valor mínimo.", "max": "Valor máximo.", "step": "Paso de los botones + y -."},
        "example": 'level: Annotated[int, pz.Range(0, 10)] = 3',
    },
    "pyzed.state": {
        "desc": 'Declara una variable de estado privada en la clase de un componente: el padre no puede pasarla y cada instancia empieza con su propia copia del valor (listas y diccionarios son seguros). El diseñador la muestra junto a las props. Ver [Componentes propios](/pyzed/es/guides/components/).',
        "params": {'default': 'Valor inicial, copiado para cada instancia.', 'doc': 'Descripción que muestra el diseñador.'},
        "example": """
            class Counter(pz.Component):
                step: int = 1
                count: int = pz.state(0)
        """,
    },
})
_page("app")["sections"][-1][1]["pyzed.Event"]["params"] = {
    "type": "Nombre del evento.", "x": "X del puntero, relativa al widget.", "y": "Y del puntero, relativa al widget.",
    "dx": "Scroll horizontal (líneas) o movimiento del arrastre.", "dy": "Scroll vertical (líneas) o movimiento del arrastre.",
    "width": "Ancho del widget.", "height": "Alto del widget.", "button": '`"left"`, `"right"`, `"middle"`...',
    "key": 'Combinación de teclas, como `"ctrl-s"`.', "shift": "Shift pulsado.", "ctrl": "Control pulsado.", "alt": "Alt pulsado.",
    "logo": "Tecla Cmd/Windows pulsada.", "value": "Valor de un evento propio.", "source": "Componente que lo emitió.",
    "window_x": "X del puntero en la ventana (fuera de ella si un arrastre se suelta fuera).",
    "window_y": "Y del puntero en la ventana.",
    "screen_x": "X del puntero en la pantalla, o `None` donde la plataforma no dice dónde están las ventanas (Wayland). `event.screen` da `(screen_x, screen_y)`.",
    "screen_y": "Y del puntero en la pantalla, o `None`.",
    "screen": "`(screen_x, screen_y)`, o `None` cuando la plataforma no informa de la posición de las ventanas.",
}
_page("app")["sections"][-1][1]["pyzed.Component"]["params"] = {
    "args": "Props, en el orden en que se declaran.",
    "kwargs": "Props por nombre, handlers `on_<evento>=` (propios, de ciclo de vida o comunes) y `key=` para conservar el estado cuando los elementos se mueven.",
}

# -- Diálogos y traducciones --------------------------------------------------
_section("ui", "Diálogos", {
    "pyzed.ui.dialog_layer": {
        "desc": "Muestra un diálogo centrado sobre `base` con un fondo oscurecido. Con `dialog=None` devuelve `base` sin cambios, así que puede envolver siempre la vista. Ver [Diálogos](/pyzed/es/guides/i18n/#diálogos).",
        "params": {"base": "La interfaz de debajo.", "dialog": "Un diálogo de las funciones de abajo, o `ui.modal`.",
                   "on_dismiss": "Se envía al hacer clic en el fondo."},
        "example": """
            ui.dialog_layer(self.vista_principal(), ui.confirm("¿Eliminar 3 archivos?", self.eliminar, self.cancelar,
                            danger=True) if self.preguntando else None, on_dismiss=self.cancelar)
        """,
    },
    "pyzed.ui.alert": {
        "desc": "Un mensaje con un botón.",
        "params": {"message": "Texto o widget.", "on_close": "El botón y el icono de cerrar.",
                   "kind": '`"info"`, `"success"`, `"warning"` o `"error"` añade un icono.', "ok_label": "Texto del botón (por defecto: Aceptar, traducido)."},
    },
    "pyzed.ui.confirm": {
        "desc": "Hace una pregunta de sí o no.",
        "params": {"message": "Texto o widget.", "on_confirm": "El botón de confirmar.", "on_cancel": "Cancelar, el icono de cerrar.",
                   "danger": "Pinta el botón de rojo y lo llama Eliminar.", "kind": "Añade un icono, como en `alert`.",
                   "confirm_label": "Texto del botón de confirmar.", "cancel_label": "Texto del botón de cancelar."},
    },
    "pyzed.ui.prompt": {
        "desc": "Pide una línea de texto.",
        "params": {"value": "Texto actual.", "on_input": "Recibe cada edición.", "on_submit": "Enter o el botón de aceptar.",
                   "on_cancel": "Cancelar, el icono de cerrar.", "message": "Texto sobre el campo.", "id": "Id del campo (para `Command.focus`).",
                   "submit_label": "Texto del botón de aceptar.", "cancel_label": "Texto del botón de cancelar."},
    },
    "pyzed.ui.choice": {
        "desc": "Un mensaje con tus propios botones.",
        "params": {"options": "Pares `(texto, on_press)`; el último es el botón principal.", "on_cancel": "El icono de cerrar."},
    },
    "pyzed.ui.unsaved_changes": {
        "desc": "«¿Guardar los cambios de *nombre* antes de cerrar?» con No guardar, Cancelar y Guardar.",
        "params": {"name": "Nombre del archivo o documento.", "on_save": "Guardar.", "on_discard": "No guardar.", "on_cancel": "Cancelar."},
    },
}, before="Controles")

_section("app", "Idiomas", {
    "pyzed.t": {
        "desc": "El texto de `key` en el idioma actual, formateado con `values`. Si falta, prueba de `\"es_AR\"` a `\"es\"`, luego el idioma de respaldo y por último devuelve la clave. Ver [Idiomas](/pyzed/es/guides/i18n/).",
        "params": {"key": "Clave con puntos, como `\"menu.open\"`.", "language": "Busca en otro idioma.",
                   "default": "Lo que devuelve si falta la clave (por defecto, la clave).",
                   "values": "Valores para los `{nombre}`; `count=` además elige el plural."},
        "example": """
            i18n.add("es", {"greeting": "¡Hola, {name}!", "files": {"one": "{count} archivo", "other": "{count} archivos"}})
            i18n.set_language("es")
            pz.t("greeting", name="Kev"), pz.t("files", count=3)
        """,
    },
    "pyzed.i18n.add": {"desc": "Añade o reemplaza textos de un idioma. Las tablas anidadas se vuelven claves con puntos; las tablas `{\"one\": ..., \"other\": ...}` son plurales.",
                       "params": {"language": "Código de idioma, como `\"es\"` o `\"pt_BR\"`.", "catalog": "Dict de textos."}},
    "pyzed.i18n.load": {"desc": "Carga todos los `<idioma>.json` y `<idioma>.toml` de `folder`; devuelve los idiomas encontrados.", "params": {"folder": "Carpeta con los catálogos."}},
    "pyzed.i18n.set_language": {"desc": "Cambia el idioma. La app lo muestra en el siguiente render, así que llámalo desde un handler.", "params": {"language": "Código de idioma, como `\"es\"`."}},
    "pyzed.i18n.language": {"desc": "El idioma actual, normalizado (`\"es_ar\"`)."},
    "pyzed.i18n.languages": {"desc": "Los idiomas con catálogo."},
    "pyzed.i18n.set_fallback": {"desc": "El idioma que se usa cuando falta un texto (por defecto `\"en\"`).", "params": {"language": "Código de idioma."}},
    "pyzed.i18n.on_change": {"desc": "Llama a `listener(idioma)` tras cada cambio; devuelve una función que lo quita.", "params": {"listener": "Función que recibe el nuevo idioma."}},
    "pyzed.i18n.system_language": {"desc": "El idioma del sistema operativo (`LANG`, `LC_ALL` o el locale).", "params": {"default": "Lo que devuelve si el sistema no informa ninguno."}},
    "pyzed.i18n.has": {"desc": "Si `key` tiene texto en el idioma o sus respaldos.", "params": {"key": "Clave con puntos.", "language": "Idioma a consultar (por defecto, el actual)."}},
})

_section("ui", "Consola y ayuda", {
    "pyzed.ui.Log": {
        "desc": "Las entradas de un `ui.console`: seguro entre hilos, limitado a `limit` y con las líneas repetidas agrupadas. `write(level, text)` añade una línea; `capture()` (o `with log:`) copia la salida de `print` y los tracebacks; `pipe(stream)` lee la salida de un subproceso en segundo plano; `text()` devuelve todo para copiarlo.",
        "params": {"limit": "Máximo de entradas guardadas.", "on_write": "Se llama tras cada escritura (desde cualquier hilo)."},
        "example": """
            log = ui.Log()
            with log:
                print("hola")           # sigue llegando a la terminal
            ui.console(log.entries, on_clear=log.clear)
        """,
    },
    "pyzed.ui.LogEntry": {"desc": "Una línea de un `ui.Log`: `level`, `text`, `time`, `count` (líneas idénticas seguidas) y `clock` (`HH:MM:SS`).", "params": {"level": "Nivel.", "text": "La línea.", "time": "Cuándo se escribió (`time.time()`).", "count": "Líneas idénticas seguidas."}},
    "pyzed.ui.LOG_LEVELS": {"desc": "Los niveles que colorea `ui.console`, en el orden de sus filtros: info, event, stdout, stderr, warning, error."},
    "pyzed.ui.console": {
        "desc": "Una vista de registro como la consola de las herramientas de desarrollo del navegador: filtro, un botón por nivel con su cuenta, copiar y limpiar, y las entradas en monoespaciada, siempre desplazada a la más nueva.",
        "params": {"entries": "Elementos `ui.LogEntry` (`log.entries`).", "query": "Texto del filtro.", "on_query": "Recibe cada edición del filtro.",
                   "hidden": "Niveles ocultos.", "on_toggle_level": "Se llama con el nivel del botón pulsado.",
                   "on_clear": "Añade el botón Limpiar.", "on_copy": "Añade el botón Copiar.", "actions": "Widgets extra al final de la barra.",
                   "font_size": "Tamaño de las entradas.", "id": "Id del scrollable."},
    },
    "pyzed.ui.shortcuts": {
        "desc": "Una lista de atajos de teclado agrupada y con búsqueda (para un diálogo de atajos).",
        "params": {"groups": "`[(título, [(etiqueta, teclas), ...]), ...]`, teclas como `\"ctrl-s\"`.", "query": "Texto del filtro.", "on_query": "Añade un buscador.", "height": "Alto de la lista."},
    },
    "pyzed.ui.about": {
        "desc": "Un cuadro Acerca de: icono, nombre, versión, una descripción, algunos detalles y botones de enlace.",
        "params": {"name": "Nombre de la app.", "version": "Versión.", "description": "Una o dos frases.", "icon": "Icono de Lucide.",
                   "details": "Filas `(etiqueta, valor)`.", "links": "Botones `(etiqueta, on_press)`."},
    },
}, before="Datos y feedback")

# -- Estilos ------------------------------------------------------------------
_section("widgets", "Estilos", {
    "pyzed.Style": {
        "desc": "Un conjunto reutilizable de propiedades de estilo para `widget.style(...)`, el `style=` de un componente o `App.style`. Combina estilos con `|` (gana el de la derecha). Ver [Estilos](/pyzed/es/theming/styles/).",
        "params": {"styles": "Estilos, dicts o nombres de estilo de partida.",
                   "props": "Propiedades: `background`, `color`, `font`, `weight`, `italic`, `size`, `line_height`, `border_color`, `border_width`, `border` (`(ancho, color)`), `radius`, `shadow`, `padding`, `margin`, `width`, `height`, `max_width`, `max_height`, `align_x`, `align_y`, `clip`. Efectos: `opacity`, `translate` (`(x, y)`, píxeles o `\"50%\"`), `scale`, `glow` (un color, un tamaño o `(color, tamaño)`), `bloom` (un color o `(color, intensidad)`) y `glass` (`True`, un tinte o `{\"tint\", \"strength\"}`). Los colores pueden ser tokens del tema."},
        "example": """
            tarjeta = pz.Style(background="panel", border=(1, "border"), radius=8, padding=12)
            pz.column([...]).style(tarjeta | pz.Style(shadow=("#0006", (0, 4), 12)))
        """,
    },
    "pyzed.define_style": {"desc": "Pone nombre a un estilo para usarlo así: `widget.style(\"card\")`. Lo devuelve.",
                           "params": {"name": "Nombre del estilo.", "styles": "Estilos a combinar.", "props": "Propiedades encima."}},
    "pyzed.set_style": {"desc": "Fija el estilo global de todas las ventanas, por debajo del `style` de cada una. Sin argumentos lo quita.",
                        "params": {"styles": "Estilos a combinar.", "props": "Propiedades encima."}},
    "pyzed.Gradient": {"desc": "Un gradiente lineal para fondos. Los ángulos siguen CSS: 0 arriba, 90 derecha, 180 (por defecto) abajo. Hasta 8 paradas.",
                       "params": {"stops": "Colores, repartidos por igual, o pares `(posición, color)` con posiciones de 0 a 1.", "angle": "Dirección en grados."},
                       "example": 'pz.container(None, height=80).style(background=pz.Gradient(["#f97316", "#7c3aed"], angle=90))'},
    "pyzed.Mask": {"desc": "Una máscara de opacidad para un `Paint`: cuánto se ve el relleno a lo largo de una dirección. Sobre un gradiente sigue su dirección.",
                   "params": {"stops": "Opacidades (0 a 1), repartidas por igual, o pares `(posición, opacidad)`.", "angle": "Dirección cuando el relleno es un color liso."}},
    "pyzed.Paint": {"desc": "Un relleno: un color o un `Gradient` con opacidad general y una `Mask` opcional. Sirve en cualquier fondo.",
                    "params": {"fill": "Un color o un `Gradient`.", "opacity": "De 0 a 1; multiplica el alfa del relleno.", "mask": "Una `pz.Mask`."},
                    "example": 'pz.Paint("#3b82f6", opacity=0.8, mask=pz.Mask([1, 0]))  # se desvanece hacia abajo'},
})

_section("ui", "Selector de color", {
    "pyzed.ui.ColorPicker": {
        "desc": "Un componente para elegir un color con alfa, un gradiente lineal (paradas que se añaden, arrastran y quitan, más un ángulo) o un relleno con máscara de opacidad. `on_change` recibe un texto `\"#rrggbb[aa]\"`, un `pz.Gradient` o un `pz.Paint`, todos válidos como `background`. Devuelve el valor elegido en `value`. Ver [Estilos](/pyzed/es/theming/styles/#selector-de-color).",
        "params": {"value": "Un color, token del tema, `pz.Gradient` o `pz.Paint`.", "alpha": "Muestra la barra y el campo de alfa.",
                   "gradients": "Muestra el cambio Sólido/Gradiente.", "masks": "Muestra el editor de máscara.",
                   "swatches": "Colores rápidos (por defecto: el acento y los colores de estado del tema).", "on_change": "Recibe `event.value`."},
        "example": """
            ui.ColorPicker(value=self.fill, on_change=lambda e: setattr(self, "fill", e.value))
        """,
    },
    "pyzed.ui.color_swatch": {"desc": "Un cuadrito que muestra un color, gradiente o pintura sobre un damero.",
                              "params": {"value": "Qué mostrar.", "size": "Lado en píxeles.", "on_press": "Lo hace pulsable."}},
    "pyzed.ui.checkerboard": {"desc": "Un damero claro/oscuro para dibujar bajo colores translúcidos.",
                              "params": {"width": "Ancho.", "height": "Alto.", "size": "Tamaño de celda."}},
})

_section("ui", "Selector de iconos", {
    "pyzed.ui.IconPicker": {
        "desc": "Un componente para elegir un icono de Lucide: un buscador (nombres y etiquetas), un desplegable de categorías y una cuadrícula que solo construye las filas visibles. Enter elige la primera coincidencia. `on_change` recibe el nombre del icono (`\"\"` si se quita); devuélvelo en `value`. Ver la página [Selector de iconos](/pyzed/es/library/icon-picker/).",
        "params": {"value": "El nombre del icono elegido.", "columns": "Iconos por fila.", "height": "Alto de la cuadrícula.",
                   "clearable": "Muestra un botón que quita el icono.", "autofocus": "Da el foco al buscador al aparecer.",
                   "on_change": "Recibe `event.value`."},
        "example": """
            ui.IconPicker(value=self.icon, on_change=lambda e: setattr(self, "icon", e.value))
        """,
    },
    "pyzed.ui.icon_picker_dialog": {
        "desc": "Un diálogo con un `IconPicker` que elige con un clic; úsalo como diálogo de `ui.dialog_layer`. El buscador recibe el foco.",
        "params": {"value": "El icono actual.", "on_pick": "Se llama con el nombre del icono pulsado (`\"\"` si se quita).",
                   "on_close": "El botón de cerrar.", "title": "Por defecto: \"Elegir un icono\", traducido.", "columns": "Iconos por fila.",
                   "clearable": "Muestra el botón \"Sin icono\".", "key": "Clave del componente, para varios selectores en una vista.",
                   "theme": "Tema."},
        "example": """
            ui.dialog_layer(page, ui.icon_picker_dialog(self.icon, self.pick, on_close=self.close) if self.picking else None,
                            on_dismiss=self.close)
        """,
    },
    "pyzed.ui.icon_grid": {
        "desc": "La cuadrícula de iconos sola, virtualizada: solo se construyen las filas visibles, así que miles de iconos cuestan lo mismo que unos pocos.",
        "params": {"names": "Nombres de iconos, en orden.", "on_pick": "Se llama con el nombre pulsado.", "selected": "El nombre resaltado.",
                   "columns": "Iconos por fila.", "cell": "Lado de cada celda en píxeles.", "height": "Alto de la cuadrícula.",
                   "id": "Id del desplazable, para `Command.scroll_to`.", "theme": "Tema."},
    },
})

# -- Todo lo demás, descrito por los docstrings del código ---------------------
# Las entradas con "docstring": True no muestran tabla de parámetros (se describen en el texto);
# en español cada una necesita su "desc", traducción del docstring completo.
_D = {"docstring": True}


def _d(desc, **extra):
    """Una entrada ``docstring`` con su traducción (sangría quitada)."""
    import inspect

    return {**_D, "desc": inspect.cleandoc(desc), **extra}


_section("app", "Hot reload", {
    "pyzed.hot_reload.enable": _d("Inicia el hot reload para `app` (una instancia de `App` en marcha) y devuelve el reloader."),
    "pyzed.hot_reload.current": _d("El `Reloader` activo, o `None` cuando el hot reload está apagado."),
    "pyzed.hot_reload.is_reloading": _d("`True` mientras una recarga vuelve a ejecutar los módulos."),
    "pyzed.hot_reload.enabled_by_env": _d("Si `PYZED_RELOAD` pide hot reload (`1`, `true`, `yes` u `on`)."),
    "pyzed.hot_reload.Reloader": _d("""
        Vigila los archivos del proyecto y recarga el código modificado en una app en marcha.

        `app` es la instancia de `App` en marcha. `paths` son carpetas o archivos extra que
        vigilar; por defecto se vigila la carpeta del módulo que define la clase de la app.
        `interval` es cada cuántos segundos se comprueba si hay cambios.

        La mayoría de los programas nunca crean uno a mano: lo hace `pz.run(app, reload=True)`.
    """),
    "pyzed.hot_reload.ReloadError": _d("Lo lanza `view()` mientras la última recarga haya fallado; la ventana muestra su mensaje."),
}, before="Idiomas")
_section("app", "Eventos y componentes", {
    "pyzed.component.State": _d("El valor por defecto de una variable de estado declarada en la clase (ver `state`)."),
    "pyzed.component.StateInfo": _d("Una variable de estado declarada con `pz.state`: su nombre, anotación, valor por defecto y descripción."),
    "pyzed.component.PropInfo": _d("Una prop: su nombre, anotación de tipo (puede ser un texto) y valor por defecto."),
    "pyzed.component.find": _d("La clase de componente registrada como `type_name` (ver `Component.type_name`)."),
    "pyzed.component.registered": _d("Todas las subclases de `Component` definidas hasta ahora que deben aparecer en el diseñador."),
    "pyzed.component.render_pass": _d("""
        Registra los componentes renderizados mientras `owner` (una ventana) ejecuta su `view()`.

        Los componentes que no se vuelven a renderizar se desmontan al final. El runtime lo hace
        en cada ventana; úsalo tú solo para renderizar componentes fuera de una ventana.
    """),
    "pyzed.events.EventInfo": _d("La documentación de un evento: su grupo y qué informa."),
    "pyzed.events.accepts_argument": _d("""
        Si `handler` recibe el evento: tiene un parámetro posicional obligatorio o `*args`.

        Los parámetros con valor por defecto no cuentan, así que `lambda i=i: ...` se llama sin nada.
        La respuesta se guarda en caché por función.
    """),
})
_section("app", "Eventos y componentes", {
    "pyzed.component.LIFECYCLE_EVENTS": {"desc": "Los nombres de los eventos de ciclo de vida que lanza todo componente (`mount`, `unmount`...).", "no_signature": True},
    "pyzed.events.CATALOG": {"desc": "Todos los nombres de evento que conoce Pyzed, con su `EventInfo` (qué lo lanza y qué contiene `event.value`).", "no_signature": True},
    "pyzed.events.COMMON": {"desc": "Los eventos que acepta todo widget con `widget.on(...)` (clic, hover, foco, teclas...).", "no_signature": True},
})
_section("app", "Idiomas", {
    "pyzed.i18n.normalize": _d('`"es-AR"`, `"es_AR.UTF-8"` -> `"es_ar"`.'),
})
_section("widgets", "Layout", {
    "pyzed.layout.FlexItem": _d("Un hijo de `pz.flex` con su propio tamaño; se crea con `pz.flex_item`."),
})
_section("app", "Referencia integrada", {
    "pyzed.reference.Browser": _d("""
        Lo que muestra un visor de la referencia: el texto buscado, la página abierta y el historial atrás/adelante.

        `ui.reference_browser(browser)` lo dibuja; sus botones y enlaces llaman a los métodos de abajo.
    """),
    "pyzed.reference.Entry": _d("Una página de la referencia, tal como la muestran los resultados de búsqueda y la lista de clases."),
    "pyzed.reference.Page": _d("Una página completa: la entrada a la que pertenece y su cuerpo en Markdown."),
    "pyzed.reference.Provider": _d("""
        Una sección de la referencia que viene de otro sitio que no son las páginas de la API de la librería.

        `entries(lang)` lista sus páginas, `page(id, lang)` construye una (`None` si el id no es suyo)
        y `lookup(symbol)` convierte un nombre escrito en código en uno de sus ids.
    """),
    "pyzed.reference.register": _d("Añade una sección a la referencia (reemplaza la que tenga el mismo `name`)."),
    "pyzed.reference.entries": _d("Todas las páginas de la referencia, en el orden de la lista de clases (primero los controles del diseñador, luego la librería)."),
    "pyzed.reference.sections": _d("La lista de clases: `[(sección, [(grupo, [entradas]), ...]), ...]` en orden."),
    "pyzed.reference.search": _d("""
        Las entradas que coinciden con `query`: primero los nombres exactos, luego los que empiezan por él y después el resto.

        Cada palabra debe aparecer en el título, el grupo o el resumen (`"tab bar"` encuentra `ui.tab_bar`).
    """),
    "pyzed.reference.page": _d("La página con `id` (`KeyError` si no existe)."),
    "pyzed.reference.lookup": _d('El id de la página sobre un nombre escrito en código (`"pz.text"`, `"ui.button"`, `"Theme"`...).'),
    "pyzed.reference.languages": _d("Los idiomas en los que están las descripciones de la API."),
    "pyzed.reference.tables_as_lists": _d("""
        Tablas de Markdown convertidas en listas (`- primera celda: las otras celdas`).

        Para visores cuyas tablas no parten las celdas largas, como `ui.reference_browser` en una pestaña estrecha.
        Los bloques de código no se tocan.
    """),
    "pyzed.reference.display_name": _d('`"pyzed.text"` -> `"pz.text"`, `"pyzed.ui.button"` -> `"ui.button"`.'),
    "pyzed.reference.summary": _d("La primera frase de un texto Markdown, sin formato (para listas y resultados de búsqueda)."),
})
_section("ui", "Consola y ayuda", {
    "pyzed.ui.reference_browser": _d("""
        La referencia integrada, como la de Godot: una lista de clases con búsqueda junto a la página abierta.

        `browser` es un `pyzed.reference.Browser` (guárdalo en el estado de tu app); al hacer clic en entradas,
        enlaces y en los botones atrás/adelante cambia. `on_open_url(url)` recibe los enlaces que salen de la
        referencia (la web, GitHub...):

        ```python
        self.help = reference.Browser("pyzed.ui.button")
        ...
        ui.reference_browser(self.help, on_open_url=abrir_en_navegador)
        ```
    """),
})
_section("widgets", "Estilos", {
    "pyzed.style.global_style": _d("El estilo fijado con `set_style` (`None` si no hay)."),
    "pyzed.style.named_styles": _d("Los estilos definidos con `define_style`, por nombre."),
    "pyzed.style.apply_global": _d("`view` con el estilo global de una ventana: las propiedades de texto completan lo que los textos no fijan."),
    "pyzed.style.themed": _d("`theme` con el color de texto, el fondo, el color de borde, el tamaño y el radio de un estilo global."),
    "pyzed.style.to_hex": _d('Cualquier color como `"#rrggbb"` o `"#rrggbbaa"` (con los tokens del tema resueltos).'),
    "pyzed.style.paint_from_dict": _d("Reconstruye un `Gradient` o un `Paint` guardado con `to_dict()`."),
})

PAGES.append({
    "slug": "designer",
    "title": "Diseñador visual (pyzed.designer)",
    "description": "Referencia de la API de pyzed.designer: ejecuta, abre y crea formularios desde código Python, y registra componentes y plantillas de la caja de herramientas.",
    "order": 10,
    "intro": """
        `pyzed.designer` es el lado en código del [diseñador visual](/pyzed/es/editor/): ejecuta archivos
        `.pzform`, abre formularios como ventanas, crea formularios en código y amplía la caja de herramientas con
        tus propios componentes y plantillas. Los [componentes diseñados](/pyzed/es/editor/component-designer/)
        (`.pzcomp`) también se cargan desde aquí.

        ```python
        from pyzed import designer

        designer.run("ui/main.pzform", reload=True)
        ```
    """,
    "sections": [
        ("Ejecutar formularios", {
            "pyzed.designer.run": _d("""
                Ejecuta el formulario de `path` con toda la lógica conectada en el diseñador.

                `reload=True` activa el hot reload: guardar el formulario (desde el diseñador o a mano)
                o su módulo de handlers actualiza la ventana en marcha sin reiniciarla. `None`
                sigue a `PYZED_RELOAD`, como `pz.run`.
            """),
            "pyzed.designer.load": _d("Lee un archivo `.pzform`."),
            "pyzed.designer.open_form": _d("""
                Carga un `.pzform` y sus handlers en una `FormApp` lista para `run()` o `screenshot()`.

                Si el formulario pertenece a un proyecto (ver `pyzed.project`), primero se activa el proyecto
                para que sus handlers puedan importar el backend y los paquetes de su `.venv`.
            """),
            "pyzed.designer.open_window": _d("Un `Command` que abre `form` en una ventana nueva (los argumentos son los de `form_window`)."),
            "pyzed.designer.form_window": _d("""
                Una `FormWindow` para `form` (una ruta o nombre de `.pzform`, o un `Form`), lista para abrirse.

                Un formulario cargado de un archivo recibe su módulo de handlers; un `Form` creado en código usa
                `handlers` (un dict de funciones). `data` llega al formulario nuevo como `form.data`.
            """),
            "pyzed.designer.new_form": _d("""
                Crea `path` (se añade `.pzform` si falta) y su módulo de handlers a partir de `template`.

                El formulario toma el nombre del archivo (`order-details.pzform` -> `OrderDetails`).

                Devuelve la ruta del formulario. Lanza `FileExistsError` si ya existe, salvo con `overwrite`.
            """),
            "pyzed.designer.save": _d("Escribe `form` en `path` (se añade `.pzform` cuando no tiene extensión)."),
            "pyzed.designer.open_document": _d("Abre un `.pzform` como `Document` o un `.pzcomp` como `SceneDocument`."),
            "pyzed.designer.design": _d("Abre el diseñador visual, opcionalmente sobre un archivo `.pzform` (que se crea al guardar por primera vez)."),
        }),
        ("Formularios y controles", {
            "pyzed.designer.Form": _d("""
                Una ventana diseñada visualmente: sus ajustes, sus controles (en orden z) y sus eventos.

                `theme` es cualquier nombre de tema registrado; `accent`, `radius` y `font_size`
                lo ajustan sin escribir un archivo de tema. `style` es el estilo global del formulario
                (`pz.Style.to_dict()`), aplicado a toda la ventana. `grid` es el paso de ajuste del diseñador.
            """),
            "pyzed.designer.Control": _d("""
                Un componente colocado en un formulario.

                `x`, `y`, `width` y `height` están en píxeles lógicos relativos al área cliente del
                formulario, o a la esquina superior izquierda de `parent` cuando el control está dentro de un
                contenedor (un panel, un group box, una fila flex...). `props` guarda las propiedades propias
                del componente (`text`, `checked`...) y `events` asocia nombres de evento (`"click"`) a
                nombres de función handler. `layout` guarda opciones que lee el layout del padre, como
                `grow` en una fila flex o `span` en una grid. `style` guarda propiedades de estilo tipo CSS
                (`pz.Style.to_dict()`: fondo, borde, radio, fuente...) que se dibujan por encima de las props.
            """),
            "pyzed.designer.Event": _d("Lo que recibe un handler además del formulario: quién lo lanzó, qué evento y su valor."),
            "pyzed.designer.FormApp": _d("""
                Un formulario como ventana principal de la aplicación.

                `path` (lo fija `open_form`) es el archivo `.pzform`; con el hot reload activo, guardarlo
                o guardar su módulo de handlers actualiza la ventana en marcha.
            """),
            "pyzed.designer.FormWindow": _d("Un formulario en una ventana extra (`form.open(...)`, `designer.open_window` y la vista previa del diseñador)."),
            "pyzed.designer.Document": _d("""
                Un formulario abierto en el diseñador.

                `code` es el texto del módulo de handlers, guardado en memoria y escrito junto al
                formulario al hacer `save`. `selection` guarda nombres de controles, el principal primero.
            """),
        }),
        ("Enlace de datos y validación", {
            "pyzed.designer.binding.check": _d("""
                El mensaje de la primera regla que `value` incumple, o `None` si las cumple todas.

                `required` (una casilla marcada para casillas e interruptores), `min_length`, `max_length`, `pattern`
                (una expresión regular que todo el texto debe cumplir), `min` y `max`. `message`, si está, sustituye
                el mensaje predeterminado. Los valores vacíos solo incumplen `required`.
            """),
            "pyzed.designer.binding.translate": _d('`value` con los textos `@clave` buscados en el idioma actual (o el indicado); las listas se traducen elemento a elemento y `@@` representa una `@` literal.'),
            "pyzed.designer.binding.read": _d('El campo en `path` de `data` (dicts, listas y objetos), o `default` si falta.'),
            "pyzed.designer.binding.write": _d('Fija el campo en `path` de `data`, creando por el camino los dicts que falten.'),
            "pyzed.designer.binding.has": _d('Si `data` tiene un campo en `path`.'),
            "pyzed.designer.binding.evaluate": _d('El valor de `bind` para `data`: el campo si es una ruta, si no la expresión de Python evaluada sobre los campos de los datos. Lanza un error si falta el campo o la expresión es incorrecta.'),
            "pyzed.designer.binding.bound_prop": _d('La propiedad que enlaza un control de tipo `type_` (`None` si no se puede enlazar).'),
            "pyzed.designer.binding.two_way": _d('Si un control de tipo `type_` escribe en los datos lo que cambia el usuario.'),
            "pyzed.designer.binding.rules_for": _d('Las reglas de validación que tienen sentido para `type_` (ninguna para los controles de visualización).'),
            "pyzed.designer.binding.load_texts": _d('Carga los catálogos de traducción del formulario en `path`: `locales/` junto a él y en las carpetas superiores, hasta la raíz del proyecto. Devuelve los idiomas encontrados.'),
            "pyzed.designer.binding.BIND_PROPS": {"desc": "La propiedad que enlaza cada tipo de control y si el usuario la edita (en los dos sentidos): `{tipo: (propiedad, dos_sentidos)}`.", "no_signature": True},
        }),
        ("Caja de herramientas", {
            "pyzed.designer.Component": _d("Una entrada de la caja de herramientas: cómo se ve, se comporta y se configura un control de este `type`."),
            "pyzed.designer.Prop": _d("""
                Una propiedad que se muestra en la rejilla de propiedades del diseñador.

                `kind` elige el editor: text, multiline, number, bool, color, choice (de
                `choices`), list (un elemento por línea), rows (filas separadas por comas, la primera es la
                cabecera) o icon (un nombre de icono de Lucide).
            """),
            "pyzed.designer.RenderContext": _d("""
                Lo que necesita el `render` de un componente: el tema y una forma de lanzar eventos.

                `live` es `False` en el diseñador, donde los callbacks son marcadores inertes para que
                los controles se vean habilitados pero no hagan nada.
            """),
            "pyzed.designer.register": _d("Añade (o reemplaza) un componente en la caja de herramientas."),
            "pyzed.designer.component": _d("Devuelve el componente registrado para `type_`; lanza `KeyError` con la lista de tipos conocidos."),
            "pyzed.designer.all_components": _d("Devuelve todos los componentes registrados, en orden de registro."),
            "pyzed.designer.categories": _d("Devuelve los componentes registrados agrupados por `category` (secciones de la caja de herramientas), en orden de registro."),
            "pyzed.designer.Template": _d("Un punto de partida para formularios nuevos."),
            "pyzed.designer.register_template": _d("Añade (o reemplaza, por nombre) una plantilla del diálogo \"Nuevo formulario\"; la devuelve."),
            "pyzed.designer.templates": _d("Devuelve las plantillas de formulario registradas, en orden de registro."),
        }),
        ("Componentes diseñados", {
            "pyzed.designer.new_component": _d("""
                Un componente diseñado nuevo (aún sin guardar; llama a `save()`): su escena y una clase vacía.

                `extends` es el `.pzcomp` de un componente del que heredar: la clase nueva deriva
                de él y empieza con sus controles, propiedades, eventos y métodos.
            """),
            "pyzed.designer.load_component": _d("""
                Importa la clase del componente guardado en `path` (de nuevo, para recoger los cambios).

                Definir la clase la registra en la caja de herramientas, reemplazando una versión anterior. Devuelve
                la clase, o `None` (con el motivo en `errors`) si su código falla al importarse.
            """),
            "pyzed.designer.import_component": _d("""
                La clase del componente diseñado guardado en `scene`, para heredar de ella.

                Una ruta relativa es relativa al módulo que la llama, así que un componente puede extender
                otro que esté a su lado:

                ```python
                Rating = import_component("rating.pzcomp")

                class BigRating(Rating, scene="big_rating.pzcomp"):
                    ...
                ```

                La clase se importa una vez y se reutiliza hasta que cambia su código.
            """),
            "pyzed.designer.discover": _d("""
                Importa todos los componentes diseñados bajo `root` (por defecto, la carpeta actual).

                Los componentes pueden usarse entre sí, así que una importación fallida se reintenta cuando
                los demás ya cargaron (`errors` guarda lo que siga fallando).
            """),
            "pyzed.designer.SceneDocument": _d("""
                Un componente abierto en el diseñador: su escena, el código de su clase, la selección y el deshacer.

                Funcionan todos los comandos de `Document` (colocar, mover, alinear controles...). Los eventos
                de los controles se convierten en métodos de la clase (`def ok_click(self, event)`), y los
                eventos propios del componente son sus métodos de ciclo de vida (`setup`, `on_mount`...).
                Las propiedades y los eventos personalizados se leen de la clase y se escriben de vuelta en ella.
            """),
            "pyzed.designer.Scene": _d("""
                El layout de un componente diseñado: un `Form` cuyo `name` es el nombre de la clase.

                `bindings` asocia un nombre de control a `{propiedad del control: expresión}`; la
                expresión (normalmente una propiedad del componente, como `value`, o cualquier expresión de
                Python sobre ellas, como `f"{value} stars"`) se evalúa en cada render.
            """),
            "pyzed.designer.SceneComponent": _d("""
                Clase base de los componentes creados en el modo componente del diseñador.

                `scene` es el archivo `.pzcomp` con el layout, relativo al módulo. La etiqueta, el icono,
                la categoría, la descripción y el tamaño por defecto en la caja de herramientas salen de la escena
                salvo que la clase los fije.
            """),
            "pyzed.designer.render": _d("Dibuja `control` a su tamaño (con sus props, o los valores por defecto del componente si faltan)."),
        }),
        ("Ayudas de layout", {
            "pyzed.designer.align": _d("""
                Alinea controles en `edge` (left, center, right, top, middle, bottom).

                Con `to` (p. ej. el rectángulo del formulario) se alinean a él; si no, a los límites de la
                selección, o al formulario cuando se pasa un solo control mediante `to`.
            """),
            "pyzed.designer.distribute": _d('Reparte tres o más controles con el mismo espacio en `"horizontal"` o `"vertical"`.'),
            "pyzed.designer.same_size": _d('Da a todos los controles el `"width"`, `"height"` o `"both"` de `reference` (el primero).'),
            "pyzed.designer.snap": _d("Redondea `value` al múltiplo más cercano de `grid` (sin cambios si está desactivado)."),
            "pyzed.designer.smart_guides": _d("""
                Ajusta un rectángulo en movimiento a los bordes y centros de `others` y del formulario.

                Devuelve `(dx, dy, lines)`: la corrección a aplicar y las líneas guía a dibujar
                (como cajas finas `(x1, y1, x2, y2)`), como las guías de alineación de Figma o Qt Designer.
            """),
            "pyzed.designer.anchored": _d("""
                Dónde va un control cuando su formulario pasa del tamaño `design` al tamaño `actual`.

                Como los anclajes de WinForms: un borde anclado al formulario mantiene su distancia a ese
                lado; anclado a ambos lados se estira; anclado a ninguno mantiene su posición
                relativa (los controles centrados siguen centrados).
            """),
        }),
        ("App del diseñador", {
            "pyzed.designer.Designer": _d("El editor visual de formularios.", members=False),
            "pyzed.designer.EditorSettings": _d(
                "Los ajustes del editor de código del diseñador (un dataclass): `theme`, `font_size`, `tab_size`, "
                "`show_whitespace`, `wrap`, `line_numbers`, `highlight_line`, `autocomplete`, `code_lens`, "
                "`inline_diagnostics`, `format_on_apply`, `auto_close`, `folding`, `minimap`, `cursor_shape`, "
                "`cursor_blink`, `ty` y `ruff`."
            ),
            "pyzed.designer.History": _d("Instantáneas de un formulario: `push` tras una edición, y luego `undo`/`redo` para moverse entre ellas."),
            "pyzed.designer.theme_for": _d("El tema con el que se ejecuta un formulario: su tema base más los ajustes de acento, radio, fuente y fondo."),
            "pyzed.designer.COMMON_EVENTS": {"desc": "Los eventos que cualquier control puede manejar en el panel Eventos del diseñador.", "no_signature": True},
            "pyzed.designer.FORM_EVENTS": {"desc": "Los eventos del propio formulario (`load`, `close`, `resize`, `key`...).", "no_signature": True},
        }),
    ],
})

# -- Métodos y propiedades ------------------------------------------------------
# El texto de cada miembro de clase en "Métodos y propiedades" (en inglés sale del docstring).
_section("widgets", "Animación", {
    "pyzed.Animation": _d("""
        Una animación por keyframes, como una regla CSS `@keyframes` con su timing.

        `keyframes` es una lista de frames `{propiedad: valor}` (repartidos por igual; un frame puede
        fijar `offset` y `easing`) o un dict de offsets (`0` a `1`, `"50%"`, `"from"`, `"to"`) a
        frames. Una propiedad que falte al principio o al final sale del valor propio del widget o
        vuelve a él, y `None` nombra ese valor explícitamente:

        ```python
        pz.Animation([{"opacity": 0, "y": 12}, {"opacity": 1, "y": 0}], duration=250)
        pz.Animation({0: {"scale": 1}, "50%": {"scale": 1.1}, 1: {"scale": 1}}, repeat="infinite")
        ```

        Los demás campos son los valores por defecto que sobrescriben las opciones de `animate()`.
        `category` y `description` dicen a los editores dónde y cómo mostrar un preset.
    """),
    "pyzed.define_animation": _d("""
        Da nombre a una animación para que `animate(nombre)` la reproduzca; la devuelve.

        `define_animation("wiggle", [{"x": 0}, {"x": -4}, {"x": 4}, {"x": 0}], duration=300)`
    """),
    "pyzed.presence": _d("""
        Muestra `content` y, cuando cambia `key`, anima la salida del contenido anterior (`exit`)
        mientras entra el nuevo (`enter`), como transiciones entre páginas:

        ```python
        pz.presence(self.vista_pagina(), key=self.pagina, enter="slide_in_right", exit="fade_out")
        ```

        `id` distingue unas presences de otras (por defecto es el lugar desde donde se llama, así que
        da uno cuando la misma línea crea varias). `duration` y `easing` sobrescriben los de ambas animaciones.
    """),
    "pyzed.stagger": _d("""
        `items` con la misma animación, cada uno empezando `step` milisegundos después del anterior
        (una lista que entra en cascada):

        ```python
        pz.column(pz.stagger([fila(i) for i in items], "fade_in_up", step=30))
        ```
    """),
    "pyzed.set_reduced_motion": _d("""
        Apaga el movimiento (`True`) o lo vuelve a encender: las animaciones muestran al instante su estado de reposo.

        Por defecto Pyzed sigue el ajuste de accesibilidad "reducir movimiento" del sistema (se lee al
        arrancar la app, ver `pyzed.system_reduced_motion`). `True` o `False` lo reemplazan (por ejemplo
        desde los ajustes de tu app, o en tests) y `None` vuelve a seguir al sistema. La variable de
        entorno `PYZED_REDUCED_MOTION` (`1` o `0`) también lo reemplaza.
    """),
    "pyzed.system_reduced_motion": _d("Si el sistema pide a las apps reducir el movimiento (`None` si no se sabe)."),
    "pyzed.animation.reduced_motion": _d("Si el movimiento reducido está encendido."),
    "pyzed.animation.animation": _d("La animación llamada `name` (un preset o una definida con `define_animation`)."),
    "pyzed.animation.presets": _d("Las animaciones con nombre (todas, o una `category`: entrance, exit, attention, interaction, loop)."),
    "pyzed.animation.ease": _d("""
        `easing` en `t` (0 a 1), la curva que usan las animaciones: `ease("ease_out", 0.5)`.

        Útil para animar tus propios dibujos (`pz.canvas`) con las mismas curvas.
    """),
    "pyzed.animation.window_animations": _d("La animación que reproduce una ventana al abrirse (o cerrarse), según su `transition` y `exit_transition` (una lista vacía si no tiene)."),
    "pyzed.animation.PRESETS": {"desc": "Todas las animaciones con nombre (los presets incluidos y los añadidos con `define_animation`), asociadas a su `Animation`. Ver [la lista de presets](/pyzed/es/guides/animation/#presets).", "no_signature": True},
    "pyzed.animation.CATEGORIES": {"desc": "Categorías de presets: `entrance` (entrada), `exit` (salida), `attention` (atención), `interaction` (interacción) y `loop` (bucle).", "no_signature": True},
    "pyzed.animation.EASINGS": {"desc": "Nombres de easing (`linear`, `ease`, `ease_out_cubic`, `ease_out_back`, `spring`...). `animate()` también acepta Béziers cúbicas `(x1, y1, x2, y2)` y `\"steps(n)\"`.", "no_signature": True},
    "pyzed.animation.TRIGGERS": {"desc": "Qué reproduce una animación: `mount`, `hover`, `press`, `focus`, `click` y `active`.", "no_signature": True},
    "pyzed.animation.PROPERTIES": {"desc": "Las propiedades que cambian las animaciones y transiciones: `opacity`, `x`, `y`, `scale`, `background`, `border_color`, `color`, `radius`, `border_width`, `glow` y `glow_color`.", "no_signature": True},
    "pyzed.animation.WINDOW_TRANSITIONS": {"desc": "Nombres para `Window.transition` (`fade`, `zoom`, `pop`, `slide_up`, `slide_down`, `slide_left`, `slide_right`) asociados a sus presets `(apertura, cierre)`.", "no_signature": True},
})

MEMBERS = {
    # Referencia integrada
    "pyzed.reference.Browser.open": "Muestra la página `id` (devuelve `False` si no existe).",
    "pyzed.reference.Browser.open_symbol": "Muestra la página sobre un nombre escrito en código; devuelve si encontró una.",
    "pyzed.reference.Browser.back": "Vuelve a la página anterior.",
    "pyzed.reference.Browser.forward": "Va a la página siguiente después de volver atrás.",
    "pyzed.reference.Browser.set_query": "Cambia el texto buscado.",
    "pyzed.reference.Browser.toggle": "Pliega o despliega una sección de la lista de clases.",
    "pyzed.reference.Browser.results": "Las entradas que coinciden con el texto buscado.",
    "pyzed.reference.Browser.page": "La página mostrada (`None` antes de abrir una).",
    "pyzed.reference.Browser.follow": "Gestiona un enlace de una página: los internos abren su página; si no, devuelve la URL que hay que abrir.",
    "pyzed.reference.Page.id": "El id de la entrada.",
    "pyzed.reference.Page.title": "El título de la entrada.",
    "pyzed.Theme.is_dark": "Si el aspecto del tema es oscuro.",
    "pyzed.AutoTheme.pick": "Devuelve el tema oscuro si `dark` es verdadero; si no, el claro.",
    # App y Window
    "pyzed.App.subscriptions": "Temporizadores y streams que deben estar activos ahora mismo (se reevalúa tras cada update).",
    "pyzed.App.run": "Abre la ventana y bloquea hasta que la app termina.",
    "pyzed.App.screenshot": "Renderiza el estado actual fuera de pantalla (sin GPU ni display) en un PNG.",
    "pyzed.Window.view": "Devuelve el widget raíz de la ventana; las subclases deben sobrescribirlo.",
    "pyzed.Window.update": "Gestiona un mensaje producido en esta ventana (por defecto lo reenvía a la app).",
    "pyzed.Window.on_close": "Se llama cuando el usuario pide cerrar la ventana. Devuelve `False` para mantenerla abierta.",
    "pyzed.Window.is_open": "Si la ventana está abierta ahora.",
    "pyzed.Window.open": "Un comando que abre esta ventana: `return settings.open()`.",
    "pyzed.Window.close": "Un comando que cierra esta ventana: `on_press=self.close`.",
    "pyzed.Window.drag": "Un comando que empieza a mover la ventana (para barras de título propias).",
    "pyzed.Window.minimize": "Un comando que minimiza la ventana.",
    "pyzed.Window.toggle_maximize": "Un comando que maximiza la ventana, o la restaura si está maximizada.",
    "pyzed.Window.frame_menus": "Los menús a la izquierda de la barra de título de un marco propio (`frame = \"custom\"`): una lista de `ui.Menu`.",
    "pyzed.Window.resolved_theme": "El tema concreto que usa ahora esta ventana (con los colores y tamaños de su estilo global).",
    "pyzed.Window.resolved_style": "El estilo global de esta ventana: `pz.set_style` con su propio `style` (o el de la app) encima.",
    "pyzed.Event.position": "`(x, y)`.",
    "pyzed.Event.size": "`(width, height)`.",
    "pyzed.Event.screen": "`(screen_x, screen_y)`, o `None` cuando la plataforma no informa de dónde están las ventanas.",
    # Dock
    "pyzed.Dock.side_of": "Devuelve el lado en que está acoplado un panel: su posición guardada si es válida, si no `panel.side`.",
    "pyzed.Dock.groups": "Devuelve los paneles agrupados por lado (están todos los lados, quizá con una lista vacía).",
    "pyzed.Dock.snapshot": "Devuelve la disposición como un dict simple (`positions`, `sizes`, `active`, `hidden`).",
    "pyzed.Dock.changed": "Emite `layout` con la instantánea actual.",
    "pyzed.Dock.move": "Acopla un panel en otro lado y lo hace la pestaña activa allí.",
    "pyzed.Dock.select": "Hace de `panel_id` la pestaña activa en `side` (un clic en la pestaña) y emite `layout`.",
    "pyzed.Dock.toggle": "Muestra u oculta un lado entero.",
    "pyzed.Dock.resized": "Guarda el nuevo `size` (en píxeles) de `side` tras arrastrar su borde y emite `layout`.",
    "pyzed.Dock.start_drag": "Empieza a arrastrar la pestaña de un panel: aparecen las zonas de soltar y se cierra el menú de la pestaña.",
    "pyzed.Dock.end_drag": "Termina el arrastre de una pestaña y oculta las zonas de soltar, recordando el panel para un `drop` tardío.",
    "pyzed.Dock.drop": "Mueve el panel arrastrado a `side` al soltarlo en esa zona; no hace nada si no hay ninguno.",
    "pyzed.Dock.tab": "Construye la pestaña de un panel en la cabecera de un lado.",
    "pyzed.Dock.move_menu": "Construye el menú contextual que mueve `panel` a cualquier lado distinto de `side`.",
    "pyzed.Dock.side_view": "Construye un lado: una cabecera con las pestañas de los paneles sobre el contenido del panel activo.",
    "pyzed.Dock.drop_zones": "Construye las cuatro zonas de soltar (una por lado) que se muestran sobre el dock mientras se arrastra una pestaña.",
    # Component
    "pyzed.Component.create": "Una instancia suelta (sin renderizar ni ciclo de vida), útil en tests: `c.render()`.",
    "pyzed.Component.setup": "Se llama una vez antes del primer render (las props ya están puestas): inicializa aquí el estado.",
    "pyzed.Component.render": "Devuelve los widgets de este componente (se llama en cada render).",
    "pyzed.Component.on_mount": "Se llama tras el primer render; puede devolver un `Command` o un mensaje.",
    "pyzed.Component.on_unmount": "Se llama cuando el componente deja de renderizarse.",
    "pyzed.Component.emit": "Lanza el evento personalizado `name`: llama al handler que el padre pasó como `on_<name>`.",
    "pyzed.Component.handles": "Si el padre pasó un handler para el evento personalizado `name`.",
    "pyzed.Component.describe": "El primer párrafo del docstring (se muestra en el diseñador).",
    "pyzed.Component.designer_spec": "Este componente como entrada de la caja de herramientas del diseñador (`pyzed.designer.Component`).",
    "pyzed.component.PropInfo.required": "Si la prop no tiene valor por defecto y hay que pasarla.",
    # Hot reload
    "pyzed.hot_reload.Reloader.watch": "Llama a `callback(path)` en el hilo de la UI cada vez que cambia `path`.",
    "pyzed.hot_reload.Reloader.project_modules": "Los módulos cargados cuyos archivos pertenecen al proyecto, por ruta de archivo.",
    "pyzed.hot_reload.Reloader.scan": "Revisa una vez cada archivo vigilado y devuelve los que cambiaron.",
    "pyzed.hot_reload.Reloader.start": "Arranca el hilo vigilante y hace de este el reloader actual.",
    "pyzed.hot_reload.Reloader.stop": "Deja de vigilar archivos.",
    "pyzed.hot_reload.Reloader.reload": "Recarga ahora el código de los archivos de `changed` (llámalo en el hilo de la UI).",
    # Estilos
    "pyzed.Style.get": "Devuelve el valor de una propiedad (se aceptan alias), o `default` si no está fijada.",
    "pyzed.Style.merge": "Un estilo nuevo con `styles` y `props` encima de este.",
    "pyzed.Style.without": "Un estilo nuevo sin estas propiedades.",
    "pyzed.Style.text": "Solo las propiedades de texto (lo que un estilo pasa a los textos de dentro).",
    "pyzed.Style.to_dict": "Las propiedades en formato apto para JSON (los gradientes y pinturas pasan a ser dicts).",
    "pyzed.Style.from_dict": "Crea un estilo a partir de datos hechos con `to_dict` (se aceptan alias).",
    "pyzed.Gradient.to_value": '`(angle, [(offset, "#rrggbbaa"), ...])`, la forma que los widgets aceptan como `gradient=`.',
    "pyzed.Gradient.to_dict": 'Devuelve el gradiente como datos listos para JSON: `{"type": "linear", "angle", "stops"}`.',
    "pyzed.Mask.at": "Devuelve la opacidad (0 a 1) en `offset` (0 a 1), interpolando entre paradas.",
    "pyzed.Mask.to_dict": 'Devuelve la máscara como datos listos para JSON: `{"angle", "stops"}`.',
    "pyzed.Paint.resolve": "`(color, gradient)`: lo que dibuja un contenedor (uno de los dos es `None`).",
    "pyzed.Paint.to_dict": "Devuelve la pintura como datos listos para JSON: `fill`, `opacity` y `mask` cuando la hay.",
    # pyzed.ui
    "pyzed.ui.Log.write": "Añade una línea con nivel `level` y llama a `on_write`.",
    "pyzed.ui.Log.clear": "Quita todas las entradas.",
    "pyzed.ui.Log.counts": "Devuelve cuántas líneas hay por nivel, contando las repeticiones plegadas.",
    "pyzed.ui.Log.text": "Todo como texto plano (para copiar).",
    "pyzed.ui.Log.capturing": "Si `sys.stdout`/`sys.stderr` se están copiando al log.",
    "pyzed.ui.Log.capture": "Copia `sys.stdout`/`sys.stderr` al log (siguen llegando a la terminal).",
    "pyzed.ui.Log.release": "Deja de capturar y restaura los streams originales.",
    "pyzed.ui.Log.pipe": "Lee una tubería de un subproceso (bytes o texto) línea a línea hacia el log, en un hilo en segundo plano.",
    "pyzed.ui.LogEntry.clock": "La hora local de la entrada como `HH:MM:SS`.",
    "pyzed.ui.Column.value": "Devuelve el valor de esta columna para `row`: `key(row)`, un elemento de dict o un atributo.",
    "pyzed.ui.TreeNode.is_folder": "Si el nodo es una carpeta (tiene una lista `children`, aunque esté vacía).",
    "pyzed.ui.TreeNode.from_paths": 'Crea un árbol a partir de rutas del estilo `"src/main.rs"`. Las carpetas van primero.',
    "pyzed.ui.TreeNode.sort": "Ordena los hijos recursivamente: primero las carpetas, luego por nombre sin distinguir mayúsculas.",
    "pyzed.ui.Tab.for_file": "Una pestaña para el archivo `path`: su nombre como etiqueta y el icono y color de archivo correspondientes.",
    # ColorPicker
    # IconPicker
    "pyzed.ui.IconPicker.set_query": "Filtra la cuadrícula por `text` (nombres y etiquetas).",
    "pyzed.ui.IconPicker.set_group": "Muestra solo los iconos de la categoría `key` (`\"\"` para todos).",
    "pyzed.ui.IconPicker.matches": "Los iconos que se muestran: los de la categoría elegida que coinciden con la búsqueda, los mejores primero.",
    "pyzed.ui.IconPicker.pick": "Selecciona `name` y emite `change`.",
    "pyzed.ui.IconPicker.on_mount": "Desplaza la cuadrícula hasta el icono elegido y, con `autofocus`, da el foco al buscador.",
    "pyzed.ui.ColorPicker.parts": "`(stops, angle, mask, opacity)`: una sola parada y sin ángulo para un color liso.",
    "pyzed.ui.ColorPicker.build": "Convierte `(stops, angle, mask, opacity)` de nuevo en un color, un `Gradient` o un `Paint`.",
    "pyzed.ui.ColorPicker.publish": "Fija el valor a partir de las partes, descarta el texto hex a medio escribir y emite `change`.",
    "pyzed.ui.ColorPicker.current": "Devuelve el color hex que se está editando (el de la parada seleccionada).",
    "pyzed.ui.ColorPicker.set_color": "Cambia el color de la parada seleccionada por `color` y publica el resultado.",
    "pyzed.ui.ColorPicker.hsva": "Devuelve el color editado como `(h, s, v, a)`, cada uno de 0 a 1.",
    "pyzed.ui.ColorPicker.pick_sv": "Fija la saturación y el valor al pulsar o arrastrar en el área de saturación/valor.",
    "pyzed.ui.ColorPicker.pick_hue": "Fija el tono al pulsar o arrastrar en la barra de tono.",
    "pyzed.ui.ColorPicker.pick_alpha": "Fija el alfa al pulsar o arrastrar en la barra de alfa.",
    "pyzed.ui.ColorPicker.type_hex": "Gestiona lo que se escribe en el campo hex: aplica el texto en cuanto es un color hex válido.",
    "pyzed.ui.ColorPicker.set_alpha_percent": "Fija el alfa desde el campo de porcentaje (0 a 100).",
    "pyzed.ui.ColorPicker.set_mode": 'Cambia entre `"Solid"` y `"Gradient"`.',
    "pyzed.ui.ColorPicker.set_angle": "Fija el ángulo del gradiente en grados (o el de la máscara, sobre un color liso).",
    "pyzed.ui.ColorPicker.select_stop": "Selecciona para editar la parada del gradiente en `index`.",
    "pyzed.ui.ColorPicker.move_stop": "Mueve una parada del gradiente adonde se pulsa la barra o según el `dx` de un arrastre.",
    "pyzed.ui.ColorPicker.add_stop": "Añade una parada del gradiente donde se hace clic en la barra, con el color que el gradiente tiene ahí.",
    "pyzed.ui.ColorPicker.remove_stop": "Quita la parada del gradiente seleccionada (un gradiente conserva al menos dos).",
    "pyzed.ui.ColorPicker.toggle_mask": "Con `on` añade una máscara que va de opaco a transparente; si no, quita la máscara.",
    "pyzed.ui.ColorPicker.select_mask_stop": "Selecciona para editar la parada de la máscara en `index`.",
    "pyzed.ui.ColorPicker.move_mask_stop": "Mueve una parada de la máscara adonde se pulsa la barra o según el `dx` de un arrastre, manteniendo las paradas ordenadas.",
    "pyzed.ui.ColorPicker.add_mask_stop": "Añade una parada de la máscara donde se hace clic en la barra, con la opacidad que la máscara tiene ahí (como mucho 8).",
    "pyzed.ui.ColorPicker.set_mask_opacity": "Fija la opacidad de la parada de la máscara seleccionada (0 a 1).",
    "pyzed.ui.ColorPicker.remove_mask_stop": "Quita la parada de la máscara seleccionada (una máscara conserva al menos dos).",
    "pyzed.ui.ColorPicker.marker": "Un tirador redondo de color `color` centrado en `(x, y)`.",
    "pyzed.ui.ColorPicker.area": "Una franja redondeada de capas apiladas que informa de dónde se pulsa y se arrastra.",
    "pyzed.ui.ColorPicker.sv_area": "El cuadrado de saturación/valor del tono actual, con un marcador en el color actual.",
    "pyzed.ui.ColorPicker.hue_bar": "La barra de tono arcoíris con un marcador en el tono actual.",
    "pyzed.ui.ColorPicker.alpha_bar": "La barra de alfa (sobre un damero) con un marcador en el alfa actual.",
    "pyzed.ui.ColorPicker.stops_bar": "Una barra que previsualiza `preview` con un tirador arrastrable por cada punto `(offset, value)`.",
    # designer.Form y Control
    "pyzed.designer.Form.get": "Devuelve el control llamado `name`, o `None` si no hay ninguno.",
    "pyzed.designer.Form.names": "Devuelve los nombres de todos los controles, en orden z.",
    "pyzed.designer.Form.children": "Los controles directamente dentro de `name` (el propio formulario con `None`), en orden z.",
    "pyzed.designer.Form.descendants": "Todos los controles dentro de `name`, a cualquier profundidad (los padres antes que sus hijos).",
    "pyzed.designer.Form.ancestors": "Los contenedores que contienen a `name`, del más cercano al más lejano.",
    "pyzed.designer.Form.walk": "`(control, depth)` en orden de dibujo: cada control y luego lo que contiene.",
    "pyzed.designer.Form.is_inside": "Si el control `name` está dentro de `container`, a cualquier profundidad.",
    "pyzed.designer.Form.unique_name": "El primer `base1`, `base2`... libre (al estilo de Visual Basic).",
    "pyzed.designer.Form.add": "Añade `control` (encima del orden z) y lo devuelve.",
    "pyzed.designer.Form.remove": "Quita controles y todo lo que contienen.",
    "pyzed.designer.Form.rename": "Renombra un control y devuelve el nombre usado en realidad (único y válido).",
    "pyzed.designer.Form.reorder": 'Mueve controles al frente (`"front"`) o al fondo (`"back"`) del orden z.',
    "pyzed.designer.Form.to_dict": 'Devuelve el formulario como datos listos para JSON: `{"format", "form": ajustes, "controls": [...]}`.',
    "pyzed.designer.Form.from_dict": "Crea un formulario a partir de `data` guardados (ver `to_dict`), ignorando ajustes desconocidos y reparando padres rotos; lanza `ValueError` si no es un formulario de Pyzed.",
    "pyzed.designer.Form.to_json": "Devuelve el formulario como texto JSON indentado (el contenido de un archivo `.pzform`).",
    "pyzed.designer.Form.from_json": "Crea un formulario a partir del texto JSON `text` de un archivo `.pzform`.",
    "pyzed.designer.Form.copy": "Devuelve una copia profunda del formulario y sus controles.",
    "pyzed.designer.Control.min_size": "El `(ancho, alto)` mínimo cuando el control se estira (0: sin límite).",
    "pyzed.designer.Control.max_size": "El `(ancho, alto)` máximo cuando el control se estira (0: sin límite).",
    "pyzed.designer.Control.pivot": "El punto `(x, y)` de 0 a 1 alrededor del que giran la rotación y la escala, y que se queda quieto cuando un límite de tamaño frena el estiramiento.",
    "pyzed.designer.Control.rect": "El `(x, y, width, height)` del control, relativo a su padre (o al formulario).",
    "pyzed.designer.Control.to_dict": "Devuelve el control como datos listos para JSON; `parent`, `layout` y `style` vacíos se omiten.",
    "pyzed.designer.Control.from_dict": "Crea un control a partir de `data` guardados, ignorando claves desconocidas y anclajes no válidos.",
    "pyzed.designer.Control.copy": "Devuelve una copia profunda del control.",
    "pyzed.designer.FormApp.on_start": "Vigila el formulario y su módulo de handlers para el hot reload (si está activo) y luego lanza `load`.",
    "pyzed.designer.FormWindow.on_open": "Lanza el evento `load` del formulario al abrirse la ventana.",
    # designer.Document
    "pyzed.designer.Document.open": "Carga en un documento nuevo el formulario de `path` y el texto de su módulo de handlers (si el archivo existe).",
    "pyzed.designer.Document.code_path": "Dónde se guarda el módulo de handlers, o `None` mientras el formulario no tenga archivo.",
    "pyzed.designer.Document.display_name": "El nombre que se muestra para el documento: su nombre de archivo, o `<nombre del formulario>.pzform` si no está guardado.",
    "pyzed.designer.Document.save": "Escribe el formulario y su módulo de handlers; devuelve la ruta del formulario.",
    "pyzed.designer.Document.commit": "Guarda un paso de deshacer tras una edición (`group` une ediciones repetidas de un mismo campo).",
    "pyzed.designer.Document.undo": "Retrocede un paso; devuelve `False` si no había nada que deshacer.",
    "pyzed.designer.Document.redo": "Rehace un paso deshecho; devuelve `False` si no había nada que rehacer.",
    "pyzed.designer.Document.selected": "Los controles seleccionados, el principal primero (se saltan los nombres que ya no existen).",
    "pyzed.designer.Document.primary": "El control seleccionado principal (el primero), o `None` si no hay nada seleccionado.",
    "pyzed.designer.Document.select": "Selecciona los controles `names` (un nombre, varios, o `None` para ninguno); los nombres desconocidos se ignoran.",
    "pyzed.designer.Document.select_all": "Selecciona todos los controles del formulario.",
    "pyzed.designer.Document.is_selected": "Si el control `name` está seleccionado.",
    "pyzed.designer.Document.add": "Coloca un control nuevo de tipo `type_` (ajustado a la cuadrícula) y lo selecciona.",
    "pyzed.designer.Document.rects": "El rectángulo absoluto de cada control (ver `layout.resolve`).",
    "pyzed.designer.Document.can_contain": "Si el control `name` puede moverse dentro de `container` (`None` es el formulario, que admite cualquiera): debe ser un contenedor distinto del propio control y que no esté dentro de él.",
    "pyzed.designer.Document.reparent": "Mueve controles dentro de `parent` (o al formulario con `None`), dejándolos donde están.",
    "pyzed.designer.Document.wrap": "Mete controles (por defecto, la selección) dentro de un contenedor nuevo de tipo `type_` que los rodea.",
    "pyzed.designer.Document.move_out": "Saca un control de su contenedor y lo pasa al padre de ese contenedor.",
    "pyzed.designer.Document.parent_size": "El tamaño del padre del control `name` (su contenedor o el formulario).",
    "pyzed.designer.Document.set_anchor": "Ancla el control `name` con un preset, palabras o bordes; con `move=True` también lo lleva a ese sitio, a `margin` píxeles del borde.",
    "pyzed.designer.Document.set_offset": "Fija la distancia de un lado (`left`, `top`, `right`, `bottom`) del control `name` al de su padre.",
    "pyzed.designer.Document.set_pivot": "Fija el pivote del control `name` (de 0 a 1 en cada eje).",
    "pyzed.designer.Document.reflow": "Tras cambiar el tamaño del formulario (`parent` `None`) o del contenedor `parent` desde `size`, mueve y dimensiona lo que hay dentro según sus anclajes (salvo con `follow_anchors` desactivado).",
    "pyzed.designer.Document.set_layout": "Fija una opción que lee el layout del padre (`grow`, `span`).",
    "pyzed.designer.Document.delete": "Quita los controles seleccionados (y lo que contienen); devuelve los nombres quitados.",
    "pyzed.designer.Document.copy": "Copia la selección, con lo que haya dentro de los contenedores seleccionados.",
    "pyzed.designer.Document.cut": "Copia la selección al portapapeles y la borra; devuelve cuántos controles se copiaron.",
    "pyzed.designer.Document.paste": "Añade copias del portapapeles (desplazadas `offset`) sin sus eventos; conservan su nombre si está libre en este formulario.",
    "pyzed.designer.Document.clipboard": "Los controles copiados (como datos de `Control.to_dict()`), compartidos por todos los documentos.",
    "pyzed.designer.Document.clipboard_text": "Los controles copiados como JSON para el portapapeles del sistema, para que otro formulario, otra ventana de Pyzed Design o un archivo de texto puedan tomarlos (ver `paste_text`).",
    "pyzed.designer.Document.parse_clipboard": "Los controles del texto del portapapeles escrito por `clipboard_text`, o `None` si contiene otra cosa. Se descartan los controles de un tipo que este Pyzed no conoce.",
    "pyzed.designer.Document.paste_text": "Pega los controles del texto del portapapeles del sistema (ver `clipboard_text`); devuelve los nombres nuevos, o `None` si el texto no contiene controles de Pyzed.",
    "pyzed.designer.Document.set_bind": "Enlaza el control `name` al campo (o, en los controles de visualización, a la expresión) `bind` de `form.data`; `None` o `\"\"` lo desenlaza.",
    "pyzed.designer.Document.set_rule": "Fija la regla de validación `rule` (`required`, `min_length`, `pattern`...) del control `name`; `None`, `\"\"` o `False` la quita.",
    "pyzed.designer.Document.duplicate": "Pega al momento una copia de la selección sin tocar el portapapeles; devuelve los nombres nuevos.",
    "pyzed.designer.Document.size": "El `(width, height)` del formulario en píxeles.",
    "pyzed.designer.Document.nudge": "Mueve `dx`, `dy` píxeles los controles seleccionados (los que no coloca un layout), sin salirse de su contenedor cuando comparten uno; los empujones repetidos se unen en un solo paso de deshacer.",
    "pyzed.designer.Document.align": "Alinea los controles seleccionados en `edge` (ver `geometry.align`): entre sí, o al formulario con `to_form` o cuando solo hay un control seleccionado.",
    "pyzed.designer.Document.center": "Centra la selección (como grupo) en el formulario.",
    "pyzed.designer.Document.distribute": "Reparte los controles seleccionados con el mismo espacio a lo largo de `axis` (ver `geometry.distribute`).",
    "pyzed.designer.Document.same_size": "Da a los controles seleccionados el ancho, el alto o ambos (`which`) del principal.",
    "pyzed.designer.Document.snap_to_grid": "Ajusta a la cuadrícula del formulario los controles seleccionados (o todos si no hay selección).",
    "pyzed.designer.Document.reorder": "Mueve los controles seleccionados en el orden z (`where`: ver `Form.reorder`).",
    "pyzed.designer.Document.set_rect": "Fija la posición y el tamaño del control `name` a partir de `rect` `(x, y, width, height)`, redondeados a píxeles enteros; las ediciones con el mismo `group` se unen en un paso de deshacer.",
    "pyzed.designer.Document.set_prop": "Fija la propiedad `key` del control `name` a `value` (las ediciones repetidas se unen en un paso de deshacer).",
    "pyzed.Animation.properties": "Las propiedades que cambian los keyframes, en orden de aparición.",
    "pyzed.Animation.total": "Milisegundos del principio al final (`inf` si se repite para siempre).",
    "pyzed.Animation.with_options": "Una copia con otro timing o disparador (`duration`, `easing`, `on`...).",
    "pyzed.Animation.compile": "Los datos simples que reproduce la parte nativa (los usa `animate()`).",
    "pyzed.Animation.to_dict": "Datos listos para JSON (`Animation.from_dict` los vuelve a leer).",
    "pyzed.Animation.from_dict": "Reconstruye una animación guardada con `to_dict`.",
    "pyzed.designer.Document.set_animations": "Fija la lista de animaciones del control `name` (dicts con `preset` y, opcionalmente, `on`, `duration`, `delay`, `easing` y `repeat`); las ediciones con el mismo `group` se unen en un paso de deshacer.",
    "pyzed.designer.Document.set_style": "Fija una propiedad de estilo de un control, o del estilo global del formulario si `name` es `None`; `None` la quita.",
    "pyzed.designer.Document.clear_style": "Quita todas las propiedades de estilo de un control (o del estilo global del formulario).",
    "pyzed.designer.Document.set_field": "Fija un atributo de `Control` (x, y, width, height, visible, enabled, locked, anchor).",
    "pyzed.designer.Document.toggle_anchor": "Añade `edge` a los anclajes del control `name`, o lo quita si ya estaba.",
    "pyzed.designer.Document.set_form": "Fija el atributo `key` del formulario (un `name` nuevo se convierte antes en un identificador válido).",
    "pyzed.designer.Document.rename": "Renombra un control, su entrada en la selección y los handlers que siguen la convención de nombres.",
    "pyzed.designer.Document.owner": "El nombre visible y el mapa de eventos de un control, o del formulario si `name` es `None`.",
    "pyzed.designer.Document.events_of": "Devuelve los eventos del control `name`, o los del formulario si `name` es `None`.",
    "pyzed.designer.Document.wire": "Conecta `event` a un handler (creando su esqueleto si hace falta) y devuelve el nombre de la función.",
    "pyzed.designer.Document.unwire": "Desconecta `event`; con `delete_code` también quita el esqueleto si no se ha tocado.",
    "pyzed.designer.Document.handler_source": "Devuelve el código de `handler`, o un esqueleto nuevo si aún no existe.",
    "pyzed.designer.Document.set_handler_source": "Reemplaza el código de un handler (lanza `SyntaxError` y no cambia nada si no es válido).",
    "pyzed.designer.Document.set_code": "Reemplaza todo el texto del módulo de handlers y marca el documento como modificado.",
    # designer: caja de herramientas
    "pyzed.designer.Component.default_event": "El evento que se abre al hacer doble clic en el control en el diseñador.",
    "pyzed.designer.Component.all_events": "Los eventos propios del control seguidos, en los componentes visuales, de los eventos de ratón comunes.",
    "pyzed.designer.Component.defaults": "Devuelve un dict nuevo con el valor por defecto de cada propiedad, por nombre.",
    "pyzed.designer.Component.prop": "Devuelve la propiedad llamada `name`, o `None` si el componente no la tiene.",
    "pyzed.designer.Component.create": "Un control nuevo de este tipo con las propiedades por defecto.",
    "pyzed.designer.Prop.title": "La etiqueta que se muestra en la rejilla de propiedades: `label`, o el nombre con espacios en lugar de guiones bajos.",
    "pyzed.designer.RenderContext.on": "Un callback para `event`; si se da `prop`, el valor también se guarda ahí.",
    "pyzed.designer.RenderContext.key": "Un id estable para widgets con estado interno (editores, campos de texto).",
    # designer: componentes diseñados
    "pyzed.designer.SceneDocument.scene": "La escena del componente (el `form` del documento, tipado como `Scene`).",
    "pyzed.designer.SceneDocument.base_file": "El `.pzcomp` que extiende este componente, o `None`.",
    "pyzed.designer.SceneDocument.base": "La escena que extiende este componente, con todo lo que ella misma hereda (`None` si no hay).",
    "pyzed.designer.SceneDocument.inherited": "`True` para un control que viene del componente base.",
    "pyzed.designer.SceneDocument.own_scene": "Lo que guarda el `.pzcomp` propio de este componente: sus controles y los heredados que cambió.",
    "pyzed.designer.SceneDocument.set_base": "Hace que este componente herede del guardado en `path` (`None` no hereda de nada).",
    "pyzed.designer.SceneDocument.base_info": "Las clases de las que hereda este componente (la más cercana primero) como `(nombre del archivo de escena, info de la clase)`.",
    "pyzed.designer.SceneDocument.all_members": "Las propiedades de este componente y las que hereda (los bindings pueden usar ambas).",
    "pyzed.designer.SceneDocument.info": "La clase tal como se analizó por última vez (el último análisis correcto mientras el código tenga un error de sintaxis).",
    "pyzed.designer.SceneDocument.code_ok": "Si el código de la clase se puede analizar ahora (si no, `info` recurre al último análisis correcto).",
    "pyzed.designer.SceneDocument.members": "Las propiedades y el estado privado del componente tal como se declaran en su clase, en orden (una copia).",
    "pyzed.designer.SceneDocument.member": "Devuelve la propiedad o el estado declarado llamado `name`, o `None`.",
    "pyzed.designer.SceneDocument.unique_member": "Devuelve `base` (convertido en identificador), o `base2`, `base3`... si ya lo usa un miembro, método, control o nombre reservado.",
    "pyzed.designer.SceneDocument.add_member": "Declara una propiedad nueva (`public=False` la convierte en estado privado).",
    "pyzed.designer.SceneDocument.update_member": "Cambia una propiedad (`name`, `type`, `default`, `public`, `description`); devuelve su nombre.",
    "pyzed.designer.SceneDocument.set_member_source": "Pone como valor por defecto de la propiedad `name` la expresión de Python `source` (`[1, 2]`, `Point(x=1)`...).",
    "pyzed.designer.SceneDocument.remove_member": "Quita la propiedad `name` de la clase.",
    "pyzed.designer.SceneDocument.move_member": "Mueve la propiedad `name` `offset` posiciones en el orden de declaración de la clase (dentro de los límites).",
    "pyzed.designer.SceneDocument.custom_events": "Los eventos que declara el componente, como `{nombre: descripción}` (una copia).",
    "pyzed.designer.SceneDocument.add_event": "Declara un evento nuevo llamado `name` (hecho único) con `description`; devuelve su nombre.",
    "pyzed.designer.SceneDocument.update_event": "Renombra el evento `name` a `new_name` (si es válido y está libre) y/o cambia su `description`, manteniendo su posición; devuelve el nombre del evento. Lanza `KeyError` si no existe.",
    "pyzed.designer.SceneDocument.remove_event": "Quita de la clase el evento declarado `name`.",
    "pyzed.designer.SceneDocument.set_class_name": "Renombra la clase del componente (convertido en un nombre de clase válido) en el código y la escena; devuelve el nombre nuevo.",
    "pyzed.designer.SceneDocument.set_description": "Fija la descripción del componente, también como docstring de su clase.",
    "pyzed.designer.SceneDocument.set_scene": "Fija cómo aparece el componente en la caja de herramientas (`label`, `icon`, `category`) o su tamaño.",
    "pyzed.designer.SceneDocument.set_binding": "Hace que `prop` de `control` siga a `expression` (`None` o `\"\"` quita el binding).",
    "pyzed.designer.SceneDocument.add_method": "Añade a la clase un método reutilizable (no un handler de evento); devuelve su nombre.",
    "pyzed.designer.Scene.class_name": "El nombre de la clase del componente (el `name` de la escena).",
    "pyzed.designer.Scene.bound": "Devuelve los bindings de `control` como `{propiedad: expresión}` (vacío si no tiene).",
    "pyzed.designer.SceneComponent.scene_path": "Devuelve el archivo `.pzcomp` al que está ligada la clase, o `None`.",
    "pyzed.designer.SceneComponent.scene_model": "La escena tal como está guardada (o previsualizada por el diseñador), o `None`.",
    "pyzed.designer.SceneComponent.ctx": "Un contexto de render para esta instancia, con el tema de su escena (lo que necesita `ControlProxy.focus()`).",
    # designer: app del diseñador
    "pyzed.designer.EditorSettings.to_dict": "Devuelve los ajustes como un dict listo para JSON.",
    "pyzed.designer.EditorSettings.from_dict": "Crea los ajustes a partir de `data` guardados, con los valores por defecto para los que falten o no sean válidos, y limitando el tamaño de tabulación, el de fuente y la forma del cursor a valores válidos.",
    "pyzed.designer.History.push": "Guarda el estado actual del formulario; devuelve `False` si nada cambió.",
    "pyzed.designer.History.reset": "Olvida todos los pasos de deshacer y rehacer y empieza de nuevo desde el estado actual de `form`.",
    "pyzed.designer.History.can_undo": "Si hay un paso que deshacer.",
    "pyzed.designer.History.can_redo": "Si hay un paso deshecho que rehacer.",
    "pyzed.designer.History.undo": "Retrocede una instantánea; devuelve el formulario anterior (un objeto nuevo) o `None` si no hay.",
    "pyzed.designer.History.redo": "Avanza una instantánea; devuelve el formulario restaurado (un objeto nuevo) o `None` si no hay.",
}


# -- Muchos datos: virtualización y memoización -----------------------------
_section("widgets", "Muchos datos", {
    "pyzed.virtual_column": {
        "desc": "Una columna de `count` filas de la misma altura que solo construye las filas visibles: `item(índice)` se llama cuando la fila entra en la vista, y las que salen se descartan. Una columna de un millón de filas cuesta lo mismo que una de cincuenta. Ponla dentro de un `scrollable` (se virtualiza contra el área visible del más cercano, o de la ventana).",
        "params": {
            "count": "Número de filas.",
            "item": "Función que recibe el índice de una fila y devuelve su widget.",
            "item_height": "Altura de cada fila, en píxeles.",
            "spacing": "Espacio entre filas, en píxeles.",
            "overscan": "Filas extra construidas por encima y por debajo de las visibles, para que el scroll rápido no deje huecos.",
        },
        "example": """rows = load_logs()          # una lista con 500 000 entradas

pz.scrollable(
    pz.virtual_column(len(rows), lambda i: pz.text(rows[i]), item_height=20),
    id="logs", height="fill",
)""",
    },
    "pyzed.memo": {
        "desc": "Decorador que guarda lo que devuelve una función de la vista según sus argumentos, para que el siguiente `view()` reutilice el mismo árbol de widgets mientras no cambien. Pasa como argumentos todo lo que usa el subárbol. Las listas, dicts y sets se comparan por contenido y otros objetos no hashables por identidad; el tema y el idioma actuales siempre forman parte de la clave. `funcion.cache_clear()` vacía su caché.",
        "params": {
            "function": "La función a memoizar (al usarlo como `@pz.memo`).",
            "maxsize": "Cuántos resultados guardar por función (se descartan los usados hace más tiempo).",
        },
        "example": """@pz.memo
def sidebar(files: tuple, selected: str):
    return pz.column([ui.list_item(f, selected=f == selected) for f in files])""",
    },
    "pyzed.clear_memos": {"desc": "Vacía la caché de todas las funciones `@pz.memo`."},
    "pyzed.memo_stats": {"desc": "Devuelve `{\"hits\": n, \"misses\": m}`: cuántas llamadas a funciones memoizadas se respondieron desde la caché y cuántas construyeron su resultado."},
})
_section("ui", "Listas, árbol y menús", {
    "pyzed.ui.virtual_list": {
        "desc": "Una lista con scroll que solo construye las filas visibles, para miles o millones de elementos. `render(elemento)` devuelve el widget de un elemento y se llama cuando entra en la vista. Todas las filas tienen la misma altura.",
        "params": {
            "items": "Los elementos: una lista o cualquier secuencia (otros iterables se convierten en lista).",
            "render": "Función que recibe un elemento y devuelve su widget.",
            "item_height": "Altura de cada fila, en píxeles.",
            "overscan": "Filas extra construidas por encima y por debajo de las visibles.",
            "on_scroll": "Callable que recibe el viewport del scroll, como en `pz.scrollable`.",
        },
    },
})
_section("app", "Formularios y validación", {
    "pyzed.validation_errors": {
        "desc": "Convierte un error de validación en `{campo: mensaje}`, listo para `ui.field(..., error=)`. Acepta un `ValidationError` de Pydantic o SQLModel, un `ValidationError` de Django, el JSON de una respuesta 422 de FastAPI (`{\"detail\": [...]}`) o su lista `detail`. Los campos anidados se unen con puntos y los errores que no son de ningún campo usan la clave `\"\"`. Se guarda solo el primer mensaje de cada campo. Mira [Integraciones](/pyzed/es/integrations/overview/#errores-de-validación-en-cada-campo).",
        "params": {"error": "El error, o el JSON de la respuesta."},
        "example": """try:
    item = ItemIn.model_validate(self.draft)
except ValidationError as error:
    self.errors = pz.validation_errors(error)

ui.field("Precio", ui.input(self.draft["price"], self.set_price), error=self.errors.get("price"))""",
    },
})

# -- Juegos ---------------------------------------------------------------------------------
_G = {"docstring": True, "members": False}
PAGES.append({
    "slug": "game",
    "title": "Juegos (pyzed.game)",
    "description": "Referencia de la API de pyzed.game: teclas mantenidas, movimiento, colisiones, sprites de píxeles, partículas y temblor de pantalla para juegos en un pz.canvas.",
    "order": 11,
    "intro": """
        `pyzed.game` reúne pequeñas ayudas para juegos en tiempo real: teclas mantenidas, movimiento,
        colisiones, sprites de píxeles, partículas y temblor de pantalla. Son Python puro sobre
        [`pyzed.draw`](/pyzed/es/reference/draw/), así que también funcionan en capturas y tests. Mira
        [Crear videojuegos](/pyzed/es/games/) para ver ejemplos completos.

        ```python
        from pyzed import draw, game

        def tick(self, dt):                      # pz.frames(self.tick) en subscriptions()
            self.x += game.axis(("left", "a"), ("right", "d")) * 300 * dt
            self.chispas.update(dt)

        def view(self):
            return pz.canvas([draw.background("#0b0e14"), *game.glow(self.x, 200, 18, "#74ade8"),
                              *self.chispas.shapes()], width=400, height=300)
        ```
    """,
    "sections": [
        ("Teclado", {
            "pyzed.game.pressed": {**_G, "desc": 'Las teclas pulsadas ahora mismo, como un `frozenset` de nombres sin modificadores (`"left"`, `"space"`, `"a"`…). También está disponible como `pz.pressed()`.'},
            "pyzed.game.is_pressed": {**_G, "desc": "Si alguna de las teclas de `keys` está pulsada (`held` sustituye a `pressed()`, para tests). También está disponible como `pz.is_pressed()`."},
            "pyzed.game.axis": {**_G, "desc": '`-1`, `0` o `1` a partir de dos grupos de teclas: `axis(("left", "a"), ("right", "d"))`.'},
            "pyzed.game.vector": {**_G, "desc": "Una dirección `(x, y)` de longitud 0 o 1 a partir de cuatro grupos de teclas (flechas y WASD por defecto); las diagonales se normalizan."},
        }),
        ("Cálculo", {
            "pyzed.game.clamp": {**_G, "desc": "`value` limitado a `[low, high]`."},
            "pyzed.game.lerp": {**_G, "desc": "El valor que está a una fracción `t` del camino de `a` a `b` (`t` de 0 a 1)."},
        }),
        ("Colisiones", {
            "pyzed.game.Rect": {**_G, "desc": "Una caja alineada con los ejes (`x`, `y` es la esquina superior izquierda) con `left`, `right`, `top`, `bottom`, `center`, `overlaps(other)`, `contains(x, y)`, `moved(dx, dy)` y `shape(**paint)` (un `draw.rect`)."},
            "pyzed.game.circle_rect": {**_G, "desc": "Dónde choca un círculo con un `Rect`: la dirección hacia la que empujarlo `(nx, ny)`, o `None`. Una pelota rebota con `if nx: vx = abs(vx) * nx` y `if ny: vy = abs(vy) * ny`."},
        }),
        ("Dibujo", {
            "pyzed.game.rgba": {**_G, "desc": '`color` (`"#rrggbb[aa]"` o una tupla) como una tupla `(r, g, b, a)` con `alpha` aplicado.'},
            "pyzed.game.glow": {**_G, "desc": "Una luz suave: círculos translúcidos que crecen alrededor de `(x, y)` (bloom en un lienzo). `strength` es la opacidad del halo interior; `core=False` omite el círculo sólido."},
            "pyzed.game.sprite": {**_G, "desc": "Pixel art a partir de texto: cada carácter de `rows` es un píxel con el color de `palette` (los caracteres que no están son transparentes). Una forma por color, así que un sprite sigue siendo barato sea cual sea su tamaño."},
        }),
        ("Efectos", {
            "pyzed.game.Particles": {**_G, "desc": "Chispas, humo, explosiones: puntos de vida corta que se mueven, caen y se desvanecen. Llama a `burst(x, y, …)` cuando pase algo, a `update(dt)` en cada fotograma y dibuja `shapes()`; `gravity`, `drag` y `limit` los ajustan."},
            "pyzed.game.Shake": {**_G, "desc": "Temblor de pantalla: `kick(8)` al recibir un golpe, `update(dt)` en cada fotograma, y empieza las formas del lienzo con `*shake.shapes()` (un translate) para que todo se mueva a la vez."},
        }),
    ],
})

# -- Grafos de shaders -----------------------------------------------------------------------
_S = {"docstring": True, "members": False}
_SM = {"docstring": True, "members": False}
PAGES.append({
    "slug": "shading",
    "title": "Grafos de shaders (pyzed.shading)",
    "description": "Referencia de la API de pyzed.shading: carga grafos de shaders .pzshad, cambia sus variables y crea grafos de nodos en código que se compilan al WGSL de pz.shader.",
    "order": 11.5,
    "intro": """
        `pyzed.shading` es el sistema de shaders por nodos que hay detrás de la
        [vista de shaders](/pyzed/es/shading/shader-designer/) del diseñador: grafos `.pzshad` de nodos que se
        compilan al WGSL de [`pz.shader`](/pyzed/es/reference/widgets/). Mira
        [Grafos de shaders](/pyzed/es/shading/shader-graphs/) para un recorrido.

        ```python
        from pyzed import shading

        fuego = shading.load("shaders/fuego.pzshad")
        fuego["speed"] = 2.0                       # una variable mutable: no recompila
        pz.shader(fuego, width=320, height=200)    # o pz.shader("shaders/fuego.pzshad")
        ```
    """,
    "sections": [
        ("Usar shaders", {
            "pyzed.shading.load": {**_S, "desc": "El `Shader` de un archivo `.pzshad`, en caché por ruta (`fresh=True` lo vuelve a leer). Se recarga solo cuando el archivo cambia."},
            "pyzed.shading.Shader": {**_SM, "desc": "Un grafo de shader listo para dibujar, con sus propios valores de las variables: `shader[\"speed\"] = 2`, `shader.set(...)`, `shader.variables`, `shader.wgsl` y `shader.widget(...)`. `pz.shader` lo acepta directamente."},
            "pyzed.shading.widget": {**_S, "desc": "Un widget `pz.shader` para una ruta `.pzshad`, un `Graph` o un `Shader`."},
        }),
        ("Crear grafos", {
            "pyzed.shading.Graph": {**_SM, "desc": "Un grafo de shader: variables, nodos y las conexiones entre ellos. Llama a un tipo de nodo sobre él para añadirlo (`g.noise(scale=4)`, `g.sin(x)`), elige salidas con `nodo[\"nombre\"]` y combínalas con aritmética. `save`, `compile`, `arrange`, `connect` y los métodos de variables lo editan."},
            "pyzed.shading.new": {**_S, "desc": "Un grafo nuevo con UV alimentando un degradado hacia el nodo Output: la plantilla Blank del diseñador."},
            "pyzed.shading.load_graph": {**_S, "desc": "El `Graph` de un archivo `.pzshad`, para editarlo."},
            "pyzed.shading.Variable": {**_S, "desc": "Una variable de un shader: `name`, `type` (float, int, bool, vec2, vec3, vec4, color, texture), `value`, `mutable` (un uniform) o constante, `min`, `max`, `step` y `description`."},
            "pyzed.shading.Node": {**_S, "desc": "Un nodo de un grafo: su `type`, su posición, `inputs` (valores fijos de las entradas sin conectar), `params` (ajustes), `title` y si se muestra su `preview`."},
            "pyzed.shading.NodeRef": {**_S, "desc": "Lo que devuelve `Graph.add`: `ref[\"puerto\"]` es una salida para conectar en otro sitio; la aritmética usa su primera salida."},
            "pyzed.shading.GraphError": {**_S, "desc": "Se lanza con conexiones imposibles (tipos, ciclos), tipos de nodo desconocidos y nombres de variable no válidos."},
        }),
        ("Compilar", {
            "pyzed.shading.compile": {**_S, "desc": "Compila un grafo (o la salida de un nodo, para su vista previa) a WGSL: el código `Compiled`, uniforms, texturas y problemas por nodo."},
            "pyzed.shading.Compiled": {**_S, "desc": "El resultado de `compile`: `code`, `uniforms`, `textures`, `names` (el uniform de cada variable), `errors` por id de nodo, `uses_time`, y `check()`, que ejecuta el compilador de la GPU y pone sus mensajes en el nodo que escribió la línea."},
        }),
        ("El catálogo de nodos", {
            "pyzed.shading.register": {**_S, "desc": "Añade un tipo de nodo propio al catálogo (y a la barra Shading del diseñador)."},
            "pyzed.shading.NodeType": {**_S, "desc": "Un tipo de nodo: id, título, categoría, entradas, salidas, ajustes y cómo escribe su WGSL."},
            "pyzed.shading.Preset": {**_S, "desc": "Una entrada de la barra Shading: un tipo de nodo con algunos ajustes (`func:sin` es el nodo Function con sin)."},
        }),
    ],
})


def _entry(name):
    """La entrada que documenta ``name``, esté donde esté en ``PAGES``."""
    for page in PAGES:
        for _title, items in page["sections"]:
            if name in items:
                return items[name]
    raise KeyError(name)


def _params(name, **params):
    _entry(name).setdefault("params", {}).update(params)


# Estados y eventos de botones, avatares, listas, árboles, menús, pestañas y migas de pan.
_params("pyzed.ui.button", loading="Muestra un spinner en lugar del icono e ignora las pulsaciones (mantén una suscripción `pz.every(1/30, ...)` mientras gira).",
        tooltip="Texto que aparece al pasar el ratón.")
_params("pyzed.ui.icon_button", keys="Atajo que se muestra en el tooltip.", tint='Lo colorea (`"error"`, `"accent"`…).',
        loading="Cambia el icono por un spinner e ignora las pulsaciones.", indicator="Añade un punto de este color arriba a la derecha (sin leer, cambios…).")
_params("pyzed.ui.badge", size='`"sm"`, `"md"` o `"lg"`.', on_press="La hace pulsable.")
_params("pyzed.ui.avatar", image="Una imagen (ruta o bytes) en lugar de las iniciales.",
        status='Punto de presencia: `"online"`, `"away"`, `"busy"`, `"offline"` o un color.', tooltip="Texto al pasar el ratón (el nombre de la persona).")
_params("pyzed.ui.divider", label='Texto atenuado en el centro de una línea horizontal (`"o"`, una fecha…).', spacing="Espacio a ambos lados de la línea.")
_params("pyzed.ui.list_item", description="Una segunda línea atenuada (la fila crece a 40 px salvo que fijes `height`).",
        on_double_press="Se envía con un doble clic (abrir, renombrar…).", tooltip="Texto al pasar el ratón.")
_params("pyzed.ui.tree", selected="Un id o una colección de ids (selección múltiple).", on_open="Recibe el id del archivo al que se hace doble clic.",
        on_context="Recibe el id de la fila en la que se hace clic derecho (muestra un `ui.menu` ahí).", focused="Resalta el borde de la fila en la que está el teclado.")
_params("pyzed.ui.MenuItem", description="Una segunda línea atenuada.", submenu="Termina la fila con una flecha; abre el siguiente menú al lado en `on_press`.")
_params("pyzed.ui.menu", max_height="Desplaza un menú más alto que esto.")
_params("pyzed.ui.Tab", pinned="Muestra solo el icono, no tiene botón de cerrar y va primera en `tab_bar`.", tooltip="Texto al pasar el ratón (la ruta completa…).")
_params("pyzed.ui.tab_bar", on_context="Recibe el id de la pestaña en la que se hace clic derecho.", on_new="Se envía con un doble clic en el espacio vacío tras las pestañas.")
_params("pyzed.ui.breadcrumbs", max_items="Conserva la primera parte y las últimas y muestra `…` en lugar del resto.", on_more="Hace pulsable el `…`.")
_params("pyzed.ui.toolbar", center="Se mantiene en el centro de la barra sean cuales sean los anchos de los lados.")
