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
    "keys": 'Atajo que se muestra al final, al estilo de Zed: `"ctrl-s"`, `"cmd-k cmd-s"`.',
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
        "description": "La clase App, run, screenshot, post y load_font.",
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
        "description": "Efectos secundarios que devuelven update y los callbacks.",
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
                "pyzed.Command.set_editor_text": {
                    "desc": "Reemplaza el contenido del `code_editor` con ese `id`. Los editores no son controlados: `text` solo es el valor inicial.",
                    "params": {"id": "El `id` del editor.", "text": "El texto nuevo."},
                },
                "pyzed.Command.set_editor_cursor": {
                    "desc": "Mueve el cursor del editor (línea y columna empiezan en 1). Funciona aunque el editor aún no se haya dibujado.",
                    "params": {"id": "El `id` del editor.", "line": "Línea (desde 1).", "column": "Columna (desde 1)."},
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
        "description": "Los widgets nativos de pyzed: layout, texto, controles, editor, svg e iconos.",
        "order": 3,
        "intro": """
            Los widgets base están implementados en Rust y se importan desde `pyzed`. Son los
            ladrillos con los que están hechos los [componentes](/pyzed/es/components/overview/).
            Ver la guía de [layout](/pyzed/es/guides/layout/) para los tamaños, el relleno y los colores.
        """,
        "sections": [
            ("Widget", {
                "pyzed.Widget": {
                    "desc": "Un nodo inmutable del árbol de la interfaz, implementado en Rust. Lo devuelven todas las funciones de widgets y componentes. Donde se espera un hijo también puedes pasar un texto o un número (se convierte en `text`) o `None` (se ignora).",
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
                    "desc": "Un botón sin estilo predefinido. Para el botón de Zed usa `ui.button`.",
                    "params": {"content": "Contenido del botón."},
                },
                "pyzed.text_input": {
                    "desc": "Un campo de texto controlado: muestra `value` y te avisa de los cambios con `on_input`. Para el estilo de Zed usa `ui.input`.",
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
                    "desc": "Muestra `tip` junto a `content` al pasar el ratón. `ui.tooltip` añade el estilo de Zed.",
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
Para el estilo de Zed usa [`ui.editor`](/pyzed/es/components/code/).
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
                    },
                },
            }),
        ],
    },
    # ------------------------------------------------------------------ UI
    {
        "slug": "ui",
        "title": "Componentes (pyzed.ui)",
        "description": "Referencia de todos los componentes al estilo de Zed.",
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
                    "desc": "El botón de Zed.",
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
                    "desc": "Un botón cuadrado con solo un icono (el `IconButton` de Zed).",
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
                    "desc": "Envuelve `content` con un tooltip al estilo de Zed, opcionalmente con su atajo.",
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
                    "desc": "Un campo de texto.",
                    "params": {
                        "value": "Texto actual.",
                        "size": '`"sm"`, `"md"` o `"lg"`.',
                        "secure": "Oculta el texto.",
                        "borderless": "Sin borde ni fondo (como en la paleta de comandos).",
                    },
                },
                "pyzed.ui.search_input": {
                    "desc": "Un `input` con icono de lupa.",
                    "params": {"value": "Texto actual.", "kwargs": "Los de `input`."},
                },
                "pyzed.ui.switch": {"desc": "Un interruptor encendido/apagado."},
                "pyzed.ui.checkbox": {"desc": "Una casilla de verificación."},
                "pyzed.ui.slider": {
                    "desc": "Un deslizador.",
                    "params": {"min": "Mínimo.", "max": "Máximo.", "step": "Paso."},
                },
                "pyzed.ui.progress": {
                    "desc": "Una barra de progreso fina.",
                    "params": {"max": "Valor máximo.", "height": "Grosor."},
                },
                "pyzed.ui.segmented": {
                    "desc": "Un grupo de botones mutuamente excluyentes (el `ToggleButtonGroup` de Zed).",
                    "params": {"options": "Lista de opciones (textos).", "selected": "La opción activa."},
                },
                "pyzed.ui.field": {
                    "desc": "Una fila de formulario: título y descripción a la izquierda, control a la derecha (como los ajustes de Zed).",
                    "params": {"control": "El control (switch, input…).", "description": "Texto de ayuda."},
                },
            }),
            ("Listas, árbol y menús", {
                "pyzed.ui.list_item": {
                    "desc": "Una fila de lista (el `ListItem` de Zed): icono, texto y un hueco al final.",
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
                    "desc": "Un árbol de archivos plegable (el panel de proyecto de Zed).",
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
                    "params": {"item": "El `Tab`.", "active": "Si es la activa.", "height": "Alto."},
                },
                "pyzed.ui.tab_bar": {
                    "desc": "Una fila de pestañas con controles opcionales al principio y al final (navegación, dividir, +). El botón de cerrar aparece en la activa y al pasar el ratón.",
                    "params": {"tabs": "Lista de `Tab`.", "active": "Id de la pestaña activa.", "height": "Alto."},
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
                    "desc": "El layout de una ventana de Zed: barra de título, docks izquierdo, derecho e inferior, centro y barra de estado. Pasa `None` para ocultar un dock.",
                    "params": {
                        "center": "Contenido central (normalmente pestañas + editor).",
                        "title_bar": "Barra de título (`ui.title_bar`).",
                        "left": "Dock izquierdo.",
                        "right": "Dock derecho.",
                        "bottom": "Dock inferior.",
                        "status_bar": "Barra de estado (`ui.status_bar`).",
                        "left_width": "Ancho del dock izquierdo.",
                        "right_width": "Ancho del dock derecho.",
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
                    "desc": "Un panel acoplable. `side` decide en qué borde va la línea.",
                    "params": {"header": "Cabecera (`ui.panel_header`).", "side": '`"left"`, `"right"` o `"bottom"`.'},
                },
                "pyzed.ui.panel_header": {"desc": "La cabecera de un panel: icono, título y acciones.", "params": {"height": "Alto."}},
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
                    "desc": "La paleta de comandos de Zed: filtra `commands` por `query` con búsqueda difusa y muestra sus atajos.",
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
                    "desc": "El editor de código de Zed: resaltado con los colores del tema, números de línea y marcadores de git.",
                    "params": {
                        "id": "Identifica el buffer (usa la ruta del archivo).",
                        "text": "Texto inicial.",
                        "language": "Lenguaje. Si falta, se deduce de `path`.",
                        "markers": '`{línea: "created" | "modified" | "deleted"}`.',
                        "on_cursor": "Callable que recibe `(línea, columna)`.",
                        "font_size": "Tamaño de la fuente (por defecto, el del tema).",
                        "line_height": "Alto de línea.",
                        "gutter": "Muestra los números de línea.",
                        "wrap": "Ajuste de línea.",
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
        "description": "Theme, los temas incluidos y las utilidades de color.",
        "order": 5,
        "intro": """
            Ver la guía de [temas](/pyzed/es/guides/theming/) para la lista de tokens y cómo crear los tuyos.
        """,
        "sections": [
            ("Theme", {
                "pyzed.Theme": {
                    "desc": "Un tema: un dataclass inmutable con los tokens de color de Zed (superficies, bordes, elementos, texto, estado, editor, sintaxis, colores de colaboradores y ANSI) y métricas (`radius`, `radius_sm`, `ui_font_size`, `buffer_font_size`). La propiedad `is_dark` indica si es oscuro.",
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
                "pyzed.Theme.syntax_scopes": {"desc": "Traduce los tokens de sintaxis de Zed a scopes de TextMate para el resaltador."},
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
        "description": "Iconos de Lucide incluidos y utilidades por tipo de archivo.",
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
                "pyzed.icons.for_file": {
                    "desc": 'Devuelve `(icono, color_o_None)` para un nombre de archivo, como en el panel de proyecto de Zed.',
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
| `system_dark` | `True` | Si el sistema está en modo oscuro (lo actualiza el runtime). |

El resto de opciones de ventana (`min_size`, `resizable`, `decorations`, `scale`…) están en `Window`.

| Método | Descripción |
| --- | --- |
| `view()` | Devuelve el árbol de widgets. Se llama después de cada mensaje. |
| `update(message)` | Recibe los mensajes. Puede devolver un `Command`, una lista de ellos, una corrutina, un generador (normal o async) u otro mensaje. |
| `on_start()` | Opcional. Se ejecuta una vez al arrancar; puede devolver un `Command` o una corrutina. |
| `on_key(combo)` | Opcional. Recibe cada tecla como `"ctrl-shift-p"`, `"escape"`, `"up"`… |
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
| `app` | — | La app dueña de la ventana (se asigna al abrirla). |
| `window_size` | — | Tamaño actual en píxeles lógicos (lo actualiza el runtime). |

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
    "pyzed.Command.set_fullscreen": {"desc": "Pone o quita la pantalla completa.", "params": {"fullscreen": "`True` para pantalla completa.", "window": _win}},
    "pyzed.Command.resize_window": {"desc": "Cambia el tamaño de la ventana (píxeles lógicos).", "params": {"width": "Ancho.", "height": "Alto.", "window": _win}},
    "pyzed.Command.move_window": {"desc": "Mueve la ventana a una posición de la pantalla.", "params": {"x": "Posición horizontal.", "y": "Posición vertical.", "window": _win}},
    "pyzed.Command.focus_window": {"desc": "Trae la ventana al frente y le da el foco.", "params": {"window": _win}},
})

# -- Widgets ----------------------------------------------------------------------
_w = _page("widgets")["sections"]
dict(_w)["Layout"].update({
    "pyzed.grid": {
        "desc": "Coloca los hijos en una rejilla con un número fijo de `columns`, o tantas columnas de como mucho `max_width` como quepan.",
        "params": {"columns": "Número de columnas.", "height": "Alto de cada fila.", "aspect_ratio": "Mantiene las celdas en esta proporción ancho/alto."},
        "example": "pz.grid([card(p) for p in photos], max_width=220, spacing=8, aspect_ratio=1)",
    },
    "pyzed.split": {
        "desc": "Dos paneles con un divisor que se arrastra. Para el estilo del tema usa `ui.split`.",
        "params": {
            "first": "Primer panel.", "second": "Segundo panel.",
            "ratio": "Proporción del primer panel (0–1).",
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
        "desc": "Un desplegable para elegir una de `options`. `on_select(opción)` recibe la elegida. Para el estilo de Zed usa `ui.select`.",
        "params": {
            "selected": "Opción actual.", "handle": "Carácter del icono de la flecha.", "handle_size": "Tamaño de la flecha.",
            "menu_height": "Alto máximo del menú.", "font": "Familia de la fuente.",
            "placeholder_color": "Color del placeholder.", "handle_color": "Color de la flecha.",
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
        "desc": "Un desplegable con el estilo del tema (el `DropdownMenu` de Zed). Las opciones se muestran con `str()`, así que sirven textos, enums o dataclasses.",
        "params": {"selected": "Opción actual.", "size": '`"sm"`, `"md"` o `"lg"`.'},
    },
    "pyzed.ui.radio_group": {
        "desc": "Opciones mutuamente excluyentes como botones de radio.",
        "params": {"options": "Textos o pares `(valor, etiqueta)`.", "selected": "Valor actual.", "on_select": "Callable que recibe el valor elegido.", "horizontal": "En fila en lugar de columna."},
    },
    "pyzed.ui.number_field": {
        "desc": "Un campo numérico con botones −/+ (el `NumericStepper` de Zed). `on_change(valor)` recibe el número ya limitado a `min`/`max`; lo que no se puede leer como número se ignora.",
        "params": {"min": "Mínimo.", "max": "Máximo.", "step": "Paso de los botones.", "suffix": "Unidad que se muestra al final (`\"px\"`, `\"%\"`…)."},
    },
    "pyzed.ui.split_button": {
        "desc": "Un botón con una flecha aparte para más opciones (el `SplitButton` de Zed). `on_press` ejecuta la acción principal y `on_menu` normalmente abre un `ui.menu` en un `ui.popover`.",
        "params": {"content": "Texto del botón.", "variant": "Como en `ui.button`.", "size": _SIZES},
    },
    "pyzed.ui.toggle_group": {
        "desc": "Un control segmentado solo con iconos.",
        "params": {"options": "Pares `(valor, nombre_de_icono)`.", "selected": "Valor actual."},
    },
    "pyzed.ui.chip": {
        "desc": "Una etiqueta compacta, opcionalmente pulsable (filtros) y con botón para quitarla.",
        "params": {"content": "Texto.", "on_remove": "Muestra una ✕ que envía esto al pulsarla."},
    },
    "pyzed.ui.disclosure": {
        "desc": "Una sección plegable: cabecera con flecha que muestra u oculta `content`. El estado abierto es tuyo: cámbialo en `on_toggle`.",
        "params": {"title": "Título (texto o widget).", "content": "Contenido.", "open": "Si está abierta.", "on_toggle": "Mensaje o callable al pulsar la cabecera."},
    },
}, before="Listas, árbol y menús")
_section("ui", "Datos y feedback", {
    "pyzed.ui.callout": {
        "desc": "Un aviso en línea (el `Callout`/`Banner` de Zed).",
        "params": {"title": "Título (texto o widget).", "tint": '`"info"`, `"success"`, `"warning"`, `"error"` o `"hint"`: elige el color y el icono.', "on_dismiss": "Añade un botón de cerrar."},
    },
    "pyzed.ui.empty_state": {
        "desc": "Un marcador centrado para listas vacías, búsquedas sin resultados, etc.",
        "params": {"title": "Título."},
    },
    "pyzed.ui.settings_group": {
        "desc": "Un bloque con título de filas `ui.field` separadas por líneas (la interfaz de ajustes de Zed).",
        "params": {"title": "Título del grupo.", "rows": "Las filas (normalmente `ui.field`)."},
    },
    "pyzed.ui.Column": {
        "desc": 'Una columna de `ui.table`. `key` es una clave de dict, un nombre de atributo o una función de la fila; `render` (opcional) convierte el valor en un widget. `width` es `"fill"`, un número o `("fill", 2)`.',
        "params": {"title": "Encabezado (y nombre para ordenar).", "key": "Cómo obtener el valor de cada fila.", "align": '`"start"`, `"center"` o `"end"`.', "render": "Función valor → widget.", "sortable": "Si el encabezado se puede pulsar para ordenar."},
    },
    "pyzed.ui.table": {
        "desc": "Una tabla de datos con encabezado fijo, orden opcional y selección de filas. El orden se hace aquí cuando `sort_by` nombra una columna: pulsar un encabezado llama a `on_sort(título)` y tú cambias `sort_by`/`descending` en tu estado.",
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
        "desc": "Avatares superpuestos de colaboradores, como en la barra de título de Zed. Los que pasan de `max_shown` se agrupan en `+N`.",
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
    "Espacio de nombres con los temas incluidos (las familias One, Ayu y Gruvbox de Zed) y el registro de "
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
    "description": "Formas, texto y transformaciones para pz.canvas.",
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
