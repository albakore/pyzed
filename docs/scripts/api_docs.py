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
            [arquitectura](/pyzed/guides/architecture/).
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
            tupla de comandos. Ver la guía de [comandos y tareas](/pyzed/guides/commands/).

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
            ladrillos con los que están hechos los [componentes](/pyzed/components/overview/).
            Ver la guía de [layout](/pyzed/guides/layout/) para los tamaños, el relleno y los colores.
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
Para el estilo de Zed usa [`ui.editor`](/pyzed/components/code/).
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
            ve a la sección [Componentes](/pyzed/components/overview/).

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
            Ver la guía de [temas](/pyzed/guides/theming/) para la lista de tokens y cómo crear los tuyos.
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
