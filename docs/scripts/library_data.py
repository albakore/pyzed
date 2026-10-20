"""The component library: one entry per component, read by gen_library.py and library_shots.py.

How to add a component to the library
=====================================

1. Document the function in the API reference first (``api_docs_en.py`` / ``api_docs_es.py``,
   checked by ``gen_api.py --check``): the library's API tables come from there.
2. Add a dict to ``COMPONENTS`` below (the list order does not matter; pages are sorted by name):

   ``slug``      URL and file name: ``library/<slug>.mdx`` and ``assets/library/<slug>.*.png``.
   ``name``      Title of the page and of its gallery card (``"Button"``).
   ``category``  A key of ``CATEGORIES`` (the gallery groups cards by it).
   ``api``       Public names documented on the page, the main one first: ``["pyzed.ui.tree",
                 "pyzed.ui.TreeNode"]``. Every name of ``pyzed.ui.__all__`` must appear in some
                 entry (``gen_library.py --check`` fails otherwise).
   ``blurb``     ``T(en, es)``: one line for the gallery card.
   ``desc``      ``T(en, es)``: the lead paragraph (Markdown).
   ``when``      ``T([...], [...])``: bullets for "When to use".
   ``preview``   ``{"code": ..., "size": (w, h), "fill": False, "start": None}``. ``code`` is shown
                 in the Code tab *and* drawn as the preview, so keep it short and self-contained:
                 ``pz``, ``ui`` and ``draw`` are imported, ``main_view()`` returns a stand-in
                 for the app's view (to draw overlays over), any other free name is a do-nothing
                 callback, and the last expression is the widget. ``size`` defaults to (720, 360);
                 ``fill=True`` draws edge to edge (layouts) instead of centered; ``start`` is code
                 returning a ``pz.Command`` run before the capture (folding, focus...).
   ``usage``     Optional: a fuller snippet (usually an ``App`` showing where the state lives).
                 Defaults to the preview code.
   ``examples``  Optional list of ``{"title": T(...), "text": T(...), "code": ..., "size": (w, h)}``.
                 Each one gets its own image (``"shot": False`` to show only the code; ``size``
                 defaults to (720, 200)).
   ``notes``     Optional ``T(en, es)`` Markdown shown as "Tips".
   ``related``   Optional list of other slugs.
   ``badge``     Optional: ``"new"`` adds a badge in the sidebar and the gallery.
   ``clip``      Optional ``{"name": ..., "alt": T(...), "caption": T(...)}``: a recording of
                 ``docs/public/media/manifest.json`` (made by ``docs/scripts/record.py``) shown
                 under the preview.

   Two more keys are filled from the dicts at the end of this file, keyed by slug, so the
   catalog of variants reads as one list:

   ``plain``     ``PLAIN[slug]``: ``T(en, es)``, one or two sentences without jargon, shown first in an
                 "In plain words" box for readers who don't program.
   ``variants``  ``VARIANTS[slug]``: groups made with ``V(title, items, text=None)``. Each item is
                 ``(caption, code)`` or ``(caption, code, options)``: one shot per item, cropped to the
                 component, with its code under it. ``caption`` is usually the parameter that makes
                 the difference (``'variant="ghost"'``, shown as code) or a ``T(en, es)``. Options:
                 ``size`` (canvas, default (480, 160); grow it when the script warns about the edge),
                 ``fill`` (draw edge to edge on a canvas of ``size``, for overlays and layouts),
                 ``draw`` (a snippet drawn *instead of* ``code``, for states that only a real pointer
                 shows, such as an open tooltip) and ``start`` (as in ``preview``).

3. Render and generate, then build the site::

       python docs/scripts/library_shots.py <slug>     # docs/src/assets/library/<slug>*.png
       python docs/scripts/gen_library.py              # library/*.mdx in every language
       python docs/scripts/gen_library.py --check      # coverage and consistency
       cd docs && npm run build

Prose is Markdown inside MDX: inline code is safe, but write ``{``, ``}`` and ``<`` only inside
backticks (the generator escapes stray ones).
"""

from __future__ import annotations


def T(en, es):
    """A text in English (the site's main language) and Spanish."""
    return {"en": en, "es": es}


def V(title, items, text=None):
    """A group of variants: a ``T`` title, ``(caption, code[, options])`` items and an optional ``T`` text."""
    out = []
    for item in items:
        caption, code, *rest = item
        out.append({"caption": caption, "code": code, **(rest[0] if rest else {})})
    return {"title": title, "text": text, "items": out}


#: Gallery groups, in order: key -> (English title, Spanish title, English intro, Spanish intro).
CATEGORIES = {
    "actions": T("Actions", "Acciones"),
    "display": T("Display", "Visualización"),
    "forms": T("Forms", "Formularios"),
    "feedback": T("Feedback", "Estado y avisos"),
    "data": T("Data", "Datos"),
    "lists": T("Lists and menus", "Listas y menús"),
    "navigation": T("Navigation", "Navegación"),
    "overlays": T("Overlays", "Capas flotantes"),
    "dialogs": T("Dialogs", "Diálogos"),
    "workspace": T("Workspace", "Espacio de trabajo"),
    "code": T("Code and tools", "Código y herramientas"),
    "layout": T("Layout", "Disposición"),
    "content": T("Content", "Contenido"),
}

CATEGORY_INTROS = {
    "actions": T("Buttons and small controls that run something.",
                 "Botones y controles pequeños que ejecutan algo."),
    "display": T("Text, badges, keys, avatars and surfaces.",
                 "Texto, insignias, teclas, avatares y superficies."),
    "forms": T("Controlled inputs: they show your state and report every change.",
               "Controles controlados: muestran tu estado y te avisan de cada cambio."),
    "feedback": T("Progress, loading, notices and empty states.",
                  "Progreso, carga, avisos y estados vacíos."),
    "data": T("Tables, numbers and small charts drawn with the theme colors.",
              "Tablas, cifras y gráficos pequeños con los colores del tema."),
    "lists": T("Rows, file trees, context menus and collapsible sections.",
               "Filas, árboles de archivos, menús contextuales y secciones plegables."),
    "navigation": T("Tabs, breadcrumbs and toolbars.", "Pestañas, migas de pan y barras de herramientas."),
    "overlays": T("Things drawn on top of the UI: layers, modals, palettes and notifications.",
                  "Lo que se dibuja encima de la interfaz: capas, modales, paletas y notificaciones."),
    "dialogs": T("Ready-made dialogs with translated buttons.",
                 "Diálogos listos para usar con los botones traducidos."),
    "workspace": T("The frame of an editor-style window: docks, title bar, status bar and panels.",
                   "El marco de una ventana estilo editor: docks, barra de título, barra de estado y paneles."),
    "code": T("The code editor, a terminal view, a log console and help boxes.",
              "El editor de código, una vista de terminal, una consola de registro y cajas de ayuda."),
    "layout": T("The base layout widgets of `pyzed` (`pz.*`) every component is built with.",
                "Los widgets de disposición de `pyzed` (`pz.*`) con los que se construye todo."),
    "content": T("Base widgets for text, icons, images, Markdown, QR codes and drawing.",
                 "Widgets base para texto, iconos, imágenes, Markdown, códigos QR y dibujo."),
}

COMPONENTS: list[dict] = []


def add(**entry):
    COMPONENTS.append(entry)


# ---------------------------------------------------------------------------------------- actions

add(
    slug="button",
    clip={"name": "hover",
          "alt": T("A pointer moving over Pyzed controls: buttons light up on hover and press, a tooltip appears, "
                   "a switch, a check box and a slider change",
                   "Un puntero pasando sobre controles de Pyzed: los botones se iluminan al pasar y al pulsar, "
                   "aparece un tooltip y cambian un interruptor, una casilla y un deslizador"),
          "caption": T("Hover and press states with a real pointer.",
                       "Estados al pasar el puntero y al pulsar, con un puntero real.")},
    name=T("Button", "Botón"),
    category="actions",
    api=["pyzed.ui.button"],
    blurb=T("The themed button: variants, sizes, icons and shortcuts.",
            "El botón con tema: variantes, tamaños, iconos y atajos."),
    desc=T(
        "Displays a themed button. It reads its colors from the current theme, can carry an "
        "icon and a keyboard shortcut, and comes in several variants and sizes. Any style parameter of "
        "`pz.button` (`bg`, `hover_bg`, `color`, `shadow`, `radius`…) overrides the theme's.",
        "Muestra un botón con el estilo del tema. Toma los colores del tema actual, puede llevar un icono "
        "y un atajo de teclado, y tiene varias variantes y tamaños. Cualquier parámetro de estilo de "
        "`pz.button` (`bg`, `hover_bg`, `color`, `shadow`, `radius`…) reemplaza al del tema.",
    ),
    when=T(
        ["For the main actions of a form, dialog or toolbar.",
         "Use `variant=\"solid\"` for the one primary action and `\"ghost\"` for secondary ones.",
         "For a button with only an icon, use [Icon button](/pyzed/library/icon-button/)."],
        ["Para las acciones principales de un formulario, diálogo o barra.",
         "Usa `variant=\"solid\"` para la acción principal y `\"ghost\"` para las secundarias.",
         "Para un botón con solo un icono, usa [Botón de icono](/pyzed/es/library/icon-button/)."],
    ),
    preview={"code": """pz.row([
    ui.button("Cancel", on_cancel, variant="ghost"),
    ui.button("Save", on_save, icon="save", variant="solid", keys="ctrl-s"),
], spacing=8)"""},
    usage="""class Editor(pz.App):
    def save(self):
        ...

    def view(self):
        return ui.button("Save", self.save, icon="save", keys="ctrl-s")""",
    examples=[
        {"title": T("Full width", "Ancho completo"),
         "text": T("`full_width=True` stretches the button to its container.",
                   "`full_width=True` estira el botón hasta el ancho de su contenedor."),
         "code": """pz.column([
    ui.button("Sign in", on_press, variant="solid", full_width=True),
    ui.button("Create an account", on_press, variant="outline", full_width=True),
], spacing=8, width=320)"""},
    ],
    notes=T(
        "To pass a value to the callback, bind it with a default argument: "
        "`ui.button(name, lambda n=name: self.open(n))`.",
        "Para pasarle un valor al callback, átalo con un argumento por defecto: "
        "`ui.button(nombre, lambda n=nombre: self.abrir(n))`.",
    ),
    related=["icon-button", "split-button", "toggle-group", "tooltip"],
)

add(
    slug="icon-button",
    name=T("Icon button", "Botón de icono"),
    category="actions",
    api=["pyzed.ui.icon_button"],
    blurb=T("A square button with just an icon and an optional tooltip.",
            "Un botón cuadrado con solo un icono y un tooltip opcional."),
    desc=T(
        "A compact square button that shows a [Lucide](https://lucide.dev) icon. "
        "It is ghost by default, so it fits in toolbars, panel headers and tab bars. `tooltip=` adds a "
        "tooltip on hover.",
        "Un botón cuadrado y compacto que muestra un icono de [Lucide](https://lucide.dev). "
        "Es transparente por defecto, así que encaja en barras de herramientas, "
        "cabeceras de panel y barras de pestañas. `tooltip=` añade un tooltip al pasar el ratón.",
    ),
    when=T(
        ["For frequent actions whose icon is obvious (search, settings, close, add).",
         "Always give it a `tooltip` when the icon alone may be ambiguous.",
         "`selected=True` shows a toggled state (a panel that is open, a filter that is on)."],
        ["Para acciones frecuentes con un icono evidente (buscar, ajustes, cerrar, añadir).",
         "Dale siempre un `tooltip` cuando el icono solo pueda ser ambiguo.",
         "`selected=True` muestra un estado activo (un panel abierto, un filtro activado)."],
    ),
    preview={"code": """pz.row([
    ui.icon_button("search", on_search, tooltip="Search"),
    ui.icon_button("settings", on_settings, tooltip="Settings"),
    ui.icon_button("bell", on_notifications, selected=True),
    ui.icon_button("plus", on_new, variant="filled"),
], spacing=6)"""},
    notes=T("Run `pyzed icons` to search the icon names.", "Ejecuta `pyzed icons` para buscar los nombres de iconos."),
    related=["button", "tooltip", "toolbar"],
)

add(
    slug="split-button",
    name=T("Split button", "Botón dividido"),
    category="actions",
    api=["pyzed.ui.split_button"],
    blurb=T("A main action plus an arrow that opens more options.",
            "Una acción principal más una flecha que abre más opciones."),
    desc=T(
        "A button with a separate chevron on the right. `on_press` runs the main "
        "action and `on_menu` usually opens a `ui.menu` inside a `ui.popover` with the alternatives.",
        "Un botón con un chevron separado a la derecha. `on_press` ejecuta la "
        "acción principal y `on_menu` suele abrir un `ui.menu` dentro de un `ui.popover` con las "
        "alternativas.",
    ),
    when=T(
        ["When one action is the usual one but there are a few variations (Run / Run with arguments).",
         "Avoid it when the options are equally important: use a [Select](/pyzed/library/select/)."],
        ["Cuando una acción es la habitual pero hay algunas variantes (Ejecutar / Ejecutar con argumentos).",
         "Evítalo si las opciones son igual de importantes: usa un [Select](/pyzed/es/library/select/)."],
    ),
    preview={"code": """pz.row([
    ui.split_button("Run", on_run, on_menu, icon="play"),
    ui.split_button("Deploy", on_deploy, on_menu, variant="solid"),
], spacing=12)"""},
    usage="""class Runner(pz.App):
    def __init__(self):
        self.menu_open = False

    def view(self):
        button = ui.split_button("Run", self.run, lambda: setattr(self, "menu_open", True), icon="play")
        menu = ui.menu([ui.MenuItem("Run with arguments…", self.run_args),
                        ui.MenuItem("Debug", self.debug, icon="bug")]) if self.menu_open else None
        return ui.popover(button, menu, y=32, on_dismiss=lambda: setattr(self, "menu_open", False))""",
    related=["button", "menu", "popover"],
)

add(
    slug="toggle-group",
    name=T("Toggle group", "Grupo de alternancia"),
    category="actions",
    api=["pyzed.ui.toggle_group"],
    blurb=T("An icon-only segmented control.", "Un control segmentado solo con iconos."),
    desc=T(
        "A row of icon buttons where exactly one is selected, like text alignment in an editor. "
        "`options` are `(value, icon)` pairs and `on_select` receives the chosen value.",
        "Una fila de botones de icono en la que hay exactamente uno seleccionado, como la alineación del "
        "texto en un editor. `options` son pares `(valor, icono)` y `on_select` recibe el valor elegido.",
    ),
    when=T(
        ["For a small set of mutually exclusive modes that have clear icons.",
         "With text labels, use [Segmented](/pyzed/library/segmented/) instead."],
        ["Para un conjunto pequeño de modos excluyentes con iconos claros.",
         "Con etiquetas de texto, usa [Segmentado](/pyzed/es/library/segmented/)."],
    ),
    preview={"code": """pz.row([
    ui.toggle_group([("left", "align-left"), ("center", "align-center"), ("right", "align-right")],
                    "center", on_align),
    ui.toggle_group([("list", "list"), ("grid", "layout-grid")], "grid", on_layout),
], spacing=16)"""},
    usage="""class Toolbar(pz.App):
    def __init__(self):
        self.align = "left"

    def view(self):
        return ui.toggle_group(
            [("left", "align-left"), ("center", "align-center"), ("right", "align-right")],
            self.align, lambda value: setattr(self, "align", value),
        )""",
    related=["segmented", "radio-group", "icon-button"],
)

add(
    slug="chip",
    name=T("Chip", "Chip"),
    category="actions",
    api=["pyzed.ui.chip"],
    blurb=T("A compact tag: clickable as a filter, removable with an ✕.",
            "Una etiqueta compacta: pulsable como filtro y con ✕ para quitarla."),
    desc=T(
        "A small rounded tag. With `on_press` it acts as a filter you can toggle (`selected=True` "
        "highlights it), and with `on_remove` it shows a close button, as in a list of tags.",
        "Una etiqueta pequeña y redondeada. Con `on_press` funciona como un filtro que se activa "
        "(`selected=True` la resalta) y con `on_remove` muestra un botón para quitarla, como en una lista "
        "de etiquetas.",
    ),
    when=T(
        ["For tags, filters and selected values (a multi-select, recipients of a message).",
         "For read-only statuses use a [Badge](/pyzed/library/badge/)."],
        ["Para etiquetas, filtros y valores elegidos (una selección múltiple, destinatarios).",
         "Para estados de solo lectura usa una [Insignia](/pyzed/es/library/badge/)."],
    ),
    preview={"code": """pz.row([
    ui.chip("python", icon="tag", selected=True, on_press=on_filter),
    ui.chip("rust", on_press=on_filter),
    ui.chip("iced", on_remove=on_remove),
    ui.chip("zed", icon="sparkles", on_remove=on_remove),
], spacing=6)"""},
    usage="""class Tags(pz.App):
    def __init__(self):
        self.tags = ["python", "rust", "iced"]

    def view(self):
        return pz.row([ui.chip(t, on_remove=lambda t=t: self.tags.remove(t)) for t in self.tags],
                      spacing=6, wrap=True)""",
    related=["badge", "toggle-group"],
)

# ---------------------------------------------------------------------------------------- display

add(
    slug="label",
    name=T("Label", "Etiqueta"),
    category="display",
    api=["pyzed.ui.label", "pyzed.ui.muted"],
    blurb=T("Text with a theme color, size and weight; `muted` for secondary text.",
            "Texto con color, tamaño y peso del tema; `muted` para texto secundario."),
    desc=T(
        "Text that takes its color from the theme. `color` is a theme token (`\"text\"`, `\"accent\"`, "
        "`\"error\"`…) or a hex color, and `size` is a named step (`\"xs\"` to `\"2xl\"`) or a number. "
        "`ui.muted(...)` is a label with the `\"text_muted\"` color, for secondary text.",
        "Texto que toma el color del tema. `color` es un token del tema (`\"text\"`, `\"accent\"`, "
        "`\"error\"`…) o un color hex, y `size` es un paso con nombre (`\"xs\"` a `\"2xl\"`) o un número. "
        "`ui.muted(...)` es una etiqueta con el color `\"text_muted\"`, para texto secundario.",
    ),
    when=T(
        ["For any text in a themed UI: it follows theme changes, unlike a hard-coded `pz.text`.",
         "Use `ui.muted` for descriptions, hints and metadata.",
         "For titles use [Heading](/pyzed/library/heading/)."],
        ["Para cualquier texto en una interfaz con tema: sigue los cambios de tema, a diferencia de un `pz.text` con colores fijos.",
         "Usa `ui.muted` para descripciones, pistas y metadatos.",
         "Para títulos usa [Encabezado](/pyzed/es/library/heading/)."],
    ),
    preview={"code": """pz.column([
    ui.label("Pyzed draws native UIs with Iced."),
    ui.muted("Secondary text uses the muted color."),
    ui.label("Accent and semibold", color="accent", weight="semibold"),
    ui.label("def mono(): ...", mono=True, size="sm"),
], spacing=8)"""},
    related=["heading", "kbd", "badge"],
)

add(
    slug="heading",
    name=T("Heading", "Encabezado"),
    category="display",
    api=["pyzed.ui.heading"],
    blurb=T("Semibold titles in three levels.", "Títulos en seminegrita en tres niveles."),
    desc=T(
        "A semibold title. `level=1` (default), `2` or `3` pick the size, so headings stay consistent "
        "across screens.",
        "Un título en seminegrita. `level=1` (por defecto), `2` o `3` eligen el tamaño, así los títulos "
        "son coherentes en todas las pantallas.",
    ),
    when=T(
        ["For the title of a page, a dialog section or a settings group.",
         "For a small uppercase list title, use [List header](/pyzed/library/list-header/)."],
        ["Para el título de una página, una sección de un diálogo o un grupo de ajustes.",
         "Para un título pequeño de lista en mayúsculas, usa [Cabecera de lista](/pyzed/es/library/list-header/)."],
    ),
    preview={"code": """pz.column([
    ui.heading("Heading 1"),
    ui.heading("Heading 2", level=2),
    ui.heading("Heading 3", level=3),
    ui.muted("Body text below the headings."),
], spacing=6)"""},
    related=["label", "card"],
)

add(
    slug="badge",
    name=T("Badge", "Insignia"),
    category="display",
    api=["pyzed.ui.badge"],
    blurb=T("A small pill for statuses, versions and counters.",
            "Una pastilla pequeña para estados, versiones y contadores."),
    desc=T(
        "A small pill with text and an optional icon. `tint` picks a semantic color and `variant` is "
        "`\"soft\"` (default), `\"solid\"` or `\"outline\"`.",
        "Una pastilla pequeña con texto y un icono opcional. `tint` elige un color semántico y `variant` "
        "es `\"soft\"` (por defecto), `\"solid\"` o `\"outline\"`.",
    ),
    when=T(
        ["For short read-only statuses: `beta`, `M` (modified), `v0.4`, `3 errors`.",
         "For a round number on top of an icon use [Count badge](/pyzed/library/count-badge/)."],
        ["Para estados cortos de solo lectura: `beta`, `M` (modificado), `v0.4`, `3 errores`.",
         "Para un número redondo encima de un icono usa [Contador](/pyzed/es/library/count-badge/)."],
    ),
    preview={"code": """pz.row([
    ui.badge("accent"),
    ui.badge("success", tint="success"),
    ui.badge("warning", tint="warning"),
    ui.badge("error", tint="error", icon="circle-x"),
], spacing=8)"""},
    related=["count-badge", "indicator", "chip"],
)

add(
    slug="indicator",
    name=T("Indicator", "Indicador"),
    category="display",
    api=["pyzed.ui.indicator"],
    blurb=T("A colored dot for status, presence or unsaved changes.",
            "Un punto de color para estado, presencia o cambios sin guardar."),
    desc=T("A small colored dot. `color` is a theme token or a hex color and `size` its diameter.",
           "Un punto de color pequeño. `color` es un token del tema o un color hex y `size` su diámetro."),
    when=T(
        ["Next to a name to show presence (online, busy) or a state (running, failed).",
         "On a tab or list item to mark unsaved changes."],
        ["Junto a un nombre para mostrar presencia (conectado, ocupado) o un estado (en marcha, falló).",
         "En una pestaña o fila para marcar cambios sin guardar."],
    ),
    preview={"code": """pz.column([
    pz.row([ui.indicator("success"), ui.label("Server running")], spacing=8, align="center"),
    pz.row([ui.indicator("warning"), ui.label("Reconnecting")], spacing=8, align="center"),
    pz.row([ui.indicator("error"), ui.label("Build failed")], spacing=8, align="center"),
    pz.row([ui.indicator(size=10), ui.label("Unsaved changes")], spacing=8, align="center"),
], spacing=10)"""},
    related=["badge", "avatar"],
)

add(
    slug="kbd",
    name=T("Kbd", "Kbd"),
    category="display",
    api=["pyzed.ui.kbd", "pyzed.ui.format_keys"],
    blurb=T("Keyboard shortcuts drawn as keys, with symbols on macOS.",
            "Atajos de teclado dibujados como teclas, con símbolos en macOS."),
    desc=T(
        "Draws a shortcut written as a string (`\"ctrl-shift-p\"`, chords like `\"cmd-k cmd-s\"`) as key caps. "
        "On macOS it uses symbols (⌘⇧P) and words elsewhere; `pyzed.ui.base.KEY_STYLE` forces "
        "`\"symbols\"` or `\"words\"`. `ui.format_keys` returns the labels if you draw them yourself.",
        "Dibuja un atajo escrito como texto (`\"ctrl-shift-p\"`, acordes como `\"cmd-k cmd-s\"`) como "
        "teclas. En macOS usa símbolos (⌘⇧P) y palabras en el resto; `pyzed.ui.base.KEY_STYLE` fuerza "
        "`\"symbols\"` o `\"words\"`. `ui.format_keys` devuelve las etiquetas si quieres dibujarlas tú.",
    ),
    when=T(
        ["In menus, tooltips, palettes and help screens, to teach shortcuts.",
         "Most components already accept `keys=` and draw it for you (button, menu item, tooltip)."],
        ["En menús, tooltips, paletas y pantallas de ayuda, para enseñar atajos.",
         "Muchos componentes ya aceptan `keys=` y lo dibujan por ti (botón, entrada de menú, tooltip)."],
    ),
    preview={"code": """pz.column([
    ui.kbd("ctrl-shift-p"),
    ui.kbd("ctrl-k ctrl-s"),
    pz.row([ui.kbd("escape", size="xs"), ui.kbd("enter", size="xs"), ui.kbd("tab", size="xs")], spacing=8),
], spacing=12, align="center")"""},
    related=["keybinding-hint", "shortcuts", "tooltip"],
)

add(
    slug="avatar",
    name=T("Avatar", "Avatar"),
    category="display",
    api=["pyzed.ui.avatar"],
    blurb=T("A round avatar with initials in a collaborator color.",
            "Un avatar redondo con iniciales en un color de colaborador."),
    desc=T(
        "A circle with initials. `index` picks one of the theme's collaborator (player) colors, so the "
        "same person keeps the same color; `color` sets it directly.",
        "Un círculo con iniciales. `index` elige uno de los colores de colaborador (player) del tema, así "
        "la misma persona conserva su color; `color` lo fija directamente.",
    ),
    when=T(
        ["For the account in the title bar, comment authors or collaborators.",
         "For several people at once use [Facepile](/pyzed/library/facepile/)."],
        ["Para la cuenta en la barra de título, autores de comentarios o colaboradores.",
         "Para varias personas a la vez usa [Facepile](/pyzed/es/library/facepile/)."],
    ),
    preview={"code": """pz.row([
    ui.avatar("AL", index=0),
    ui.avatar("KV", index=1),
    ui.avatar("MZ", index=2, size=28),
    ui.avatar("JD", index=3, size=36),
], spacing=8, align="center")"""},
    related=["facepile", "title-bar"],
)

add(
    slug="tooltip",
    name=T("Tooltip", "Tooltip"),
    category="display",
    api=["pyzed.ui.tooltip", "pyzed.tooltip"],
    blurb=T("A hint shown on hover, optionally with its shortcut.",
            "Una pista que aparece al pasar el ratón, con su atajo opcional."),
    desc=T(
        "Wraps any widget and shows a small themed box next to it while the mouse is over it. "
        "`keys=` adds the shortcut and `position` is `\"top\"`, `\"bottom\"` (default), `\"left\"` or "
        "`\"right\"`. `pz.tooltip` is the unstyled base version.",
        "Envuelve cualquier widget y muestra una caja pequeña con el estilo del tema mientras el ratón está "
        "encima. `keys=` añade el atajo y `position` es `\"top\"`, `\"bottom\"` (por defecto), `\"left\"` o "
        "`\"right\"`. `pz.tooltip` es la versión base sin estilo.",
    ),
    when=T(
        ["On icon buttons and compact controls whose meaning is not obvious.",
         "Don't hide essential information in a tooltip: it is invisible on touch and keyboard use."],
        ["En botones de icono y controles compactos cuyo significado no es evidente.",
         "No escondas información esencial en un tooltip: no se ve al usar el teclado."],
    ),
    preview={"code": """pz.row([
    ui.tooltip(ui.icon_button("save", on_save), "Save", keys="ctrl-s"),
    ui.icon_button("settings", on_settings, tooltip="Settings"),
], spacing=8)""", "size": (720, 200)},
    notes=T(
        "Tooltips only appear on hover, so the preview shows the buttons. `ui.icon_button(..., tooltip=\"Text\")` "
        "is a shortcut for wrapping it in `ui.tooltip`.",
        "Los tooltips solo aparecen al pasar el ratón, así que la vista previa muestra los botones. "
        "`ui.icon_button(..., tooltip=\"Texto\")` es un atajo para envolverlo en `ui.tooltip`.",
    ),
    related=["icon-button", "kbd", "popover"],
)

add(
    slug="divider",
    name=T("Divider", "Divisor"),
    category="display",
    api=["pyzed.ui.divider", "pyzed.rule"],
    blurb=T("A thin line in the theme's border color.", "Una línea fina en el color de borde del tema."),
    desc=T(
        "A one-pixel line in the theme's border color, horizontal by default (`vertical=True` for a "
        "vertical one). `pz.rule` is the base version with your own `color` and `thickness`.",
        "Una línea de un píxel en el color de borde del tema, horizontal por defecto (`vertical=True` "
        "para una vertical). `pz.rule` es la versión base con tu propio `color` y `thickness`.",
    ),
    when=T(
        ["To separate groups in a column or items in a toolbar.",
         "Prefer spacing first; add a divider when groups really need a visual break."],
        ["Para separar grupos en una columna o elementos en una barra.",
         "Prueba primero con espacio; añade un divisor cuando los grupos necesiten un corte visual."],
    ),
    preview={"code": """pz.column([
    ui.label("Account"),
    ui.divider(),
    pz.row([ui.label("Edit"), ui.divider(vertical=True), ui.label("View"),
            ui.divider(vertical=True), ui.label("Help")], spacing=12, height=20),
    ui.divider(),
    ui.muted("Sign out"),
], spacing=10, width=300)"""},
    related=["card", "toolbar"],
)

add(
    slug="card",
    name=T("Card", "Tarjeta"),
    category="display",
    api=["pyzed.ui.card"],
    blurb=T("A bordered surface with an optional title and actions.",
            "Una superficie con borde, título y acciones opcionales."),
    desc=T(
        "A rounded, bordered surface that groups content. `title` and `actions` add a header row; "
        "`padding` and `width` control its box.",
        "Una superficie redondeada con borde que agrupa contenido. `title` y `actions` añaden una fila "
        "de cabecera; `padding` y `width` controlan su caja.",
    ),
    when=T(
        ["To group related content on a page: a summary, a form section, a dashboard tile.",
         "For a dialog over the UI use [Modal](/pyzed/library/modal/)."],
        ["Para agrupar contenido relacionado: un resumen, una sección de formulario, un panel de un dashboard.",
         "Para un diálogo encima de la interfaz usa [Modal](/pyzed/es/library/modal/)."],
    ),
    preview={"code": """ui.card(
    pz.column([
        ui.muted("Pyzed draws the UI with Iced, in Rust."),
        pz.row([pz.hspace(), ui.button("Cancel", on_cancel, variant="ghost"),
                ui.button("OK", on_ok, variant="solid")], spacing=8),
    ], spacing=12),
    title="Card",
    actions=[ui.icon_button("ellipsis", on_menu, size="sm")],
    width=380,
)"""},
    related=["modal", "settings-group", "empty-state"],
)

# ------------------------------------------------------------------------------------------ forms

add(
    slug="input",
    clip={"name": "form-validation",
          "alt": T("A sign-in form: a wrong email is flagged with Enter a valid email, then fixed, and Sign in runs",
                   "Un formulario de inicio de sesión: un email incorrecto se marca con Enter a valid email, se "
                   "corrige y Sign in se ejecuta"),
          "caption": T("Inputs with validation: the email is checked as you type.",
                       "Campos con validación: el email se comprueba mientras escribes.")},
    name=T("Input", "Campo de texto"),
    category="forms",
    api=["pyzed.ui.input"],
    blurb=T("A controlled text field with icon, placeholder and password mode.",
            "Un campo de texto controlado con icono, placeholder y modo contraseña."),
    desc=T(
        "A themed single-line text field. It is **controlled**: it shows `value` and reports "
        "every keystroke to `on_input`, so you store the text in your state and pass it back in `view()`. "
        "`on_submit` runs on Enter.",
        "Un campo de texto de una línea con el estilo del tema. Es **controlado**: muestra `value` y "
        "avisa de cada tecla a `on_input`, así que guardas el texto en tu estado y lo devuelves en "
        "`view()`. `on_submit` se ejecuta al pulsar Enter.",
    ),
    when=T(
        ["For names, paths, search boxes, emails and passwords (`secure=True`).",
         "For multi-line text or code use [Editor](/pyzed/library/editor/).",
         "Give it an `id` to focus it from code with `pz.Command.focus(id)`."],
        ["Para nombres, rutas, búsquedas, correos y contraseñas (`secure=True`).",
         "Para texto de varias líneas o código usa el [Editor](/pyzed/es/library/editor/).",
         "Dale un `id` para enfocarlo desde código con `pz.Command.focus(id)`."],
    ),
    preview={"code": """pz.column([
    ui.input("", on_input, placeholder="Project name"),
    ui.input("ada@example.com", on_input, icon="mail"),
    ui.input("hunter2", on_input, secure=True, icon="lock"),
], spacing=10, width=360)"""},
    usage="""class Form(pz.App):
    def __init__(self):
        self.name = ""

    def view(self):
        return ui.input(self.name, lambda text: setattr(self, "name", text),
                        placeholder="Project name", on_submit=self.create, id="name")

    def on_start(self):
        return pz.Command.focus("name")""",
    related=["search-input", "field", "number-field"],
)

add(
    slug="search-input",
    name=T("Search input", "Campo de búsqueda"),
    category="forms",
    api=["pyzed.ui.search_input"],
    blurb=T("An input with a magnifying glass, for filtering.", "Un campo con lupa, para filtrar."),
    desc=T(
        "An `input` with a magnifying glass icon and `\"Search…\"` as placeholder. It accepts every "
        "other parameter of [`ui.input`](/pyzed/library/input/).",
        "Un `input` con el icono de una lupa y `\"Search…\"` como placeholder. Acepta el resto de "
        "parámetros de [`ui.input`](/pyzed/es/library/input/).",
    ),
    when=T(
        ["At the top of a list, tree or table to filter it as you type.",
         "Pair it with `ui.fuzzy_filter` to rank the best matches first."],
        ["Encima de una lista, árbol o tabla para filtrarla mientras escribes.",
         "Combínalo con `ui.fuzzy_filter` para ordenar primero los mejores resultados."],
    ),
    preview={"code": """pz.column([
    ui.search_input("", on_query),
    ui.search_input("button", on_query, placeholder="Search components…"),
], spacing=10, width=360)"""},
    usage="""class Finder(pz.App):
    def __init__(self):
        self.query = ""
        self.files = ["main.py", "app.py", "theme.py"]

    def view(self):
        matches = ui.fuzzy_filter(self.query, self.files)
        return pz.column([
            ui.search_input(self.query, lambda q: setattr(self, "query", q)),
            *[ui.list_item(name, icon="file") for name, _ in matches],
        ], spacing=6)""",
    related=["input", "picker", "command-palette"],
)

add(
    slug="checkbox",
    name=T("Checkbox", "Casilla"),
    category="forms",
    api=["pyzed.ui.checkbox"],
    blurb=T("A checkbox with an optional label.", "Una casilla de verificación con etiqueta opcional."),
    desc=T(
        "A themed checkbox. `on_toggle` receives the new `bool`; `label` adds clickable text next to it.",
        "Una casilla con los colores del tema. `on_toggle` recibe el nuevo `bool`; `label` añade un "
        "texto pulsable al lado.",
    ),
    when=T(
        ["For options that are applied later (a form you submit) or a list of independent choices.",
         "For a setting that takes effect at once, a [Switch](/pyzed/library/switch/) reads better."],
        ["Para opciones que se aplican después (un formulario que envías) o una lista de opciones independientes.",
         "Para un ajuste que se aplica al momento, un [Interruptor](/pyzed/es/library/switch/) se entiende mejor."],
    ),
    preview={"code": """pz.column([
    ui.checkbox(True, on_toggle, label="Format on save"),
    ui.checkbox(False, on_toggle, label="Show hidden files"),
    ui.checkbox(True, on_toggle, label="Use tabs"),
], spacing=10)"""},
    usage="""class Settings(pz.App):
    def __init__(self):
        self.accepted = False

    def view(self):
        return ui.checkbox(self.accepted, lambda value: setattr(self, "accepted", value),
                           label="I accept the terms")""",
    related=["switch", "radio-group", "field"],
)

add(
    slug="switch",
    name=T("Switch", "Interruptor"),
    category="forms",
    api=["pyzed.ui.switch"],
    blurb=T("An on/off switch for settings that apply at once.", "Un interruptor para ajustes que se aplican al momento."),
    desc=T(
        "An on/off toggle in the theme's accent color. `on_toggle` receives the new `bool`.",
        "Un interruptor de encendido y apagado con el color de acento del tema. `on_toggle` recibe el nuevo `bool`.",
    ),
    when=T(
        ["For settings that take effect immediately (Wi-Fi, autosave, dark mode).",
         "Put it on the right of a [Field](/pyzed/library/field/) to build settings screens."],
        ["Para ajustes que se aplican en el acto (Wi-Fi, autoguardado, modo oscuro).",
         "Ponlo a la derecha de un [Campo de formulario](/pyzed/es/library/field/) para hacer pantallas de ajustes."],
    ),
    preview={"code": """pz.column([
    ui.switch(True, on_toggle, label="Autosave"),
    ui.switch(False, on_toggle, label="Vim mode"),
], spacing=12)"""},
    usage="""class Settings(pz.App):
    def __init__(self):
        self.autosave = True

    def view(self):
        return ui.switch(self.autosave, lambda on: setattr(self, "autosave", on), label="Autosave")""",
    related=["checkbox", "field", "settings-group"],
)

add(
    slug="slider",
    name=T("Slider", "Deslizador"),
    category="forms",
    api=["pyzed.ui.slider"],
    blurb=T("Pick a number in a range by dragging.", "Elige un número de un rango arrastrando."),
    desc=T(
        "A themed slider between `min` and `max` (0 to 1 by default) that moves in `step` increments. "
        "`on_change` receives the new value while dragging.",
        "Un deslizador con los colores del tema entre `min` y `max` (de 0 a 1 por defecto) que avanza "
        "de `step` en `step`. `on_change` recibe el nuevo valor mientras arrastras.",
    ),
    when=T(
        ["For values where the exact number matters less than the feel: volume, opacity, zoom.",
         "When users need to type an exact value, use a [Number field](/pyzed/library/number-field/)."],
        ["Para valores en los que importa más la sensación que el número exacto: volumen, opacidad, zoom.",
         "Cuando haga falta escribir un valor exacto, usa un [Campo numérico](/pyzed/es/library/number-field/)."],
    ),
    preview={"code": """pz.column([
    ui.slider(0.35, on_change),
    ui.slider(70, on_change, min=0, max=100, step=1),
], spacing=18, width=360)"""},
    usage="""class Player(pz.App):
    def __init__(self):
        self.volume = 70

    def view(self):
        return pz.row([
            ui.slider(self.volume, lambda v: setattr(self, "volume", v), min=0, max=100, step=1),
            ui.label(f"{self.volume:.0f}%"),
        ], spacing=12, align="center")""",
    related=["number-field", "progress"],
)

add(
    slug="number-field",
    name=T("Number field", "Campo numérico"),
    category="forms",
    api=["pyzed.ui.number_field"],
    blurb=T("A number with −/+ buttons, limits, step and suffix.", "Un número con botones −/+, límites, paso y sufijo."),
    desc=T(
        "A numeric field with − and + buttons. You can also type a value: "
        "`on_change` receives the number already clamped to `min`/`max`, and text that is not a number "
        "is ignored.",
        "Un campo numérico con botones − y +. También se puede escribir "
        "el valor: `on_change` recibe el número ya ajustado a `min`/`max` y el texto que no es un número "
        "se ignora.",
    ),
    when=T(
        ["For exact values with sensible limits: font size, tab width, port, retries.",
         "Use `suffix` for units (`\"px\"`, `\"ms\"`, `\"%\"`)."],
        ["Para valores exactos con límites razonables: tamaño de fuente, ancho de tabulación, puerto, reintentos.",
         "Usa `suffix` para las unidades (`\"px\"`, `\"ms\"`, `\"%\"`)."],
    ),
    preview={"code": """pz.row([
    ui.number_field(14, on_change, min=8, max=32, suffix="px"),
    ui.number_field(4, on_change, min=1, max=8),
    ui.number_field(0.5, on_change, step=0.1, suffix="s", width=140),
], spacing=12)"""},
    usage="""class Settings(pz.App):
    def __init__(self):
        self.font_size = 14

    def view(self):
        return ui.number_field(self.font_size, lambda v: setattr(self, "font_size", v),
                               min=8, max=32, suffix="px")""",
    related=["slider", "input", "field"],
)

add(
    slug="select",
    name=T("Select", "Select"),
    category="forms",
    api=["pyzed.ui.select"],
    blurb=T("A dropdown to choose one option.", "Un desplegable para elegir una opción."),
    desc=T(
        "A dropdown in the theme style. Options are shown with `str()`, so "
        "strings, enums or dataclasses all work, and `on_select` receives the chosen object.",
        "Un desplegable con el estilo del tema. Las opciones se muestran con "
        "`str()`, así que valen cadenas, enums o dataclasses, y `on_select` recibe el objeto elegido.",
    ),
    when=T(
        ["To pick one of many options when there is no room to show them all (language, theme, encoding).",
         "With two to five short options, [Segmented](/pyzed/library/segmented/) or a "
         "[Radio group](/pyzed/library/radio-group/) shows them at a glance."],
        ["Para elegir una entre muchas opciones cuando no caben todas (idioma, tema, codificación).",
         "Con dos a cinco opciones cortas, [Segmentado](/pyzed/es/library/segmented/) o un "
         "[Grupo de radios](/pyzed/es/library/radio-group/) las muestran de un vistazo."],
    ),
    preview={"code": """pz.row([
    ui.select(["Python", "Rust", "TypeScript"], "Rust", on_select, width=180),
    ui.select(["UTF-8", "Latin-1"], None, on_select, placeholder="Encoding…", width=180),
], spacing=12)"""},
    usage="""class Settings(pz.App):
    def __init__(self):
        self.language = "Python"

    def view(self):
        return ui.select(["Python", "Rust", "TypeScript"], self.language,
                         lambda value: setattr(self, "language", value), width=180)""",
    notes=T("The menu opens on click; the preview shows the closed state.",
            "El menú se abre al pulsar; la vista previa muestra el estado cerrado."),
    related=["segmented", "radio-group", "picker"],
)

add(
    slug="radio-group",
    name=T("Radio group", "Grupo de radios"),
    category="forms",
    api=["pyzed.ui.radio_group"],
    blurb=T("Mutually exclusive options as radio buttons.", "Opciones excluyentes como botones de radio."),
    desc=T(
        "A set of radio buttons where one option is selected. `options` are strings or `(value, label)` "
        "pairs; `on_select` receives the value. `horizontal=True` lays them out in a row.",
        "Un conjunto de botones de radio con una opción elegida. `options` son cadenas o pares "
        "`(valor, etiqueta)`; `on_select` recibe el valor. `horizontal=True` los coloca en fila.",
    ),
    when=T(
        ["When the options need a label each and should all be visible (indentation: spaces or tabs).",
         "For many options use a [Select](/pyzed/library/select/)."],
        ["Cuando cada opción necesita su etiqueta y conviene verlas todas (indentación: espacios o tabuladores).",
         "Para muchas opciones usa un [Select](/pyzed/es/library/select/)."],
    ),
    preview={"code": """pz.row([
    ui.radio_group(["Spaces", "Tabs"], "Spaces", on_select),
    ui.radio_group([("lf", "LF"), ("crlf", "CRLF"), ("cr", "CR")], "lf", on_select, horizontal=True),
], spacing=40, align="center")"""},
    usage="""class Settings(pz.App):
    def __init__(self):
        self.indent = "spaces"

    def view(self):
        return ui.radio_group([("spaces", "Spaces"), ("tabs", "Tabs")], self.indent,
                              lambda value: setattr(self, "indent", value))""",
    related=["segmented", "select", "checkbox"],
)

add(
    slug="segmented",
    name=T("Segmented", "Segmentado"),
    category="forms",
    api=["pyzed.ui.segmented"],
    blurb=T("A group of mutually exclusive text buttons.", "Un grupo de botones de texto excluyentes."),
    desc=T(
        "A row of joined buttons where one is selected. `on_select` "
        "receives the chosen option.",
        "Una fila de botones unidos en la que uno está seleccionado. "
        "`on_select` recibe la opción elegida.",
    ),
    when=T(
        ["To switch between two to five views or modes (Day / Week / Month).",
         "For icons only, use a [Toggle group](/pyzed/library/toggle-group/)."],
        ["Para cambiar entre dos y cinco vistas o modos (Día / Semana / Mes).",
         "Solo con iconos, usa un [Grupo de alternancia](/pyzed/es/library/toggle-group/)."],
    ),
    preview={"code": """pz.column([
    ui.segmented(["Editor", "Terminal", "Both"], "Editor", on_select),
    ui.segmented(["Day", "Week", "Month"], "Week", on_select),
], spacing=14, align="center")"""},
    usage="""class Calendar(pz.App):
    def __init__(self):
        self.mode = "Week"

    def view(self):
        return ui.segmented(["Day", "Week", "Month"], self.mode, lambda m: setattr(self, "mode", m))""",
    related=["toggle-group", "radio-group", "tab-bar"],
)

add(
    slug="field",
    name=T("Field", "Campo de formulario"),
    category="forms",
    api=["pyzed.ui.field"],
    blurb=T("A settings row: title and description left, control right.",
            "Una fila de ajustes: título y descripción a la izquierda, control a la derecha."),
    desc=T(
        "A form row like the ones of a settings screen: the title (and an optional description) on the left and any "
        "control on the right. Stack several in a column or a [Settings group](/pyzed/library/settings-group/).",
        "Una fila de formulario como las de una pantalla de ajustes: el título (y una descripción opcional) a la "
        "izquierda y cualquier control a la derecha. Apila varias en una columna o en un "
        "[Grupo de ajustes](/pyzed/es/library/settings-group/).",
    ),
    when=T(
        ["For preferences and forms where each control needs a label and maybe a hint.",
         "It lines up switches, selects and number fields of different widths."],
        ["Para preferencias y formularios en los que cada control necesita una etiqueta y quizá una pista.",
         "Alinea interruptores, selects y campos numéricos de anchos distintos."],
    ),
    preview={"code": """pz.column([
    ui.field("Autosave", ui.switch(True, on_toggle), description="Saves when you switch tabs"),
    ui.field("Format on save", ui.checkbox(False, on_toggle)),
    ui.field("Font size", ui.number_field(14, on_change, suffix="px")),
], spacing=14, width=440)"""},
    related=["settings-group", "switch", "number-field"],
)

add(
    slug="color-picker",
    name=T("Color picker", "Selector de color"),
    category="forms",
    api=["pyzed.ui.ColorPicker", "pyzed.ui.color_swatch", "pyzed.ui.checkerboard"],
    badge="new",
    blurb=T("Pick a color, a gradient or a masked fill; swatches show them.",
            "Elige un color, un degradado o un relleno con máscara; las muestras los enseñan."),
    desc=T(
        "`ui.ColorPicker` is a component that picks a color with alpha, a linear gradient (stops you "
        "add, drag and remove, plus an angle) or a fill with an opacity mask. `on_change` receives an "
        "event whose `value` is a `\"#rrggbb[aa]\"` string, a `pz.Gradient` or a `pz.Paint`, all valid "
        "backgrounds. `ui.color_swatch` shows any of them over a checkerboard.",
        "`ui.ColorPicker` es un componente que elige un color con alfa, un degradado lineal (paradas que "
        "añades, arrastras y quitas, más un ángulo) o un relleno con máscara de opacidad. `on_change` "
        "recibe un evento cuyo `value` es una cadena `\"#rrggbb[aa]\"`, un `pz.Gradient` o un `pz.Paint`, "
        "todos válidos como fondo. `ui.color_swatch` muestra cualquiera de ellos sobre un damero.",
    ),
    when=T(
        ["For theme editors, drawing apps and style properties.",
         "Show a `color_swatch` and open the picker in a [Popover](/pyzed/library/popover/) when it is pressed."],
        ["Para editores de temas, apps de dibujo y propiedades de estilo.",
         "Muestra un `color_swatch` y abre el selector en un [Popover](/pyzed/es/library/popover/) al pulsarlo."],
    ),
    preview={"code": """pz.row([
    ui.ColorPicker(value="#3b82f6cc", on_change=on_change),
    pz.column([
        ui.color_swatch("#3b82f6", size=28),
        ui.color_swatch("#a1c181aa", size=28),
        ui.color_swatch(pz.Gradient(["#f97316", "#7c3aed"], angle=90), size=28),
    ], spacing=8),
], spacing=16)""", "size": (720, 470)},
    usage="""class Styles(pz.App):
    def __init__(self):
        self.fill = "#3b82f6"

    def view(self):
        return pz.row([
            ui.ColorPicker(value=self.fill, on_change=lambda e: setattr(self, "fill", e.value)),
            pz.container(width=120, height=120, bg=self.fill, radius=8),
        ], spacing=16)""",
    related=["popover", "card"],
)

add(
    slug="icon-picker",
    name=T("Icon picker", "Selector de iconos"),
    category="forms",
    api=["pyzed.ui.IconPicker", "pyzed.ui.icon_picker_dialog", "pyzed.ui.icon_grid", "pyzed.icons.search",
         "pyzed.icons.category"],
    badge="new",
    blurb=T("Pick one of the ~2000 Lucide icons from a searchable grid.",
            "Elige uno de los ~2000 iconos de Lucide en una cuadrícula con buscador."),
    desc=T(
        "`ui.IconPicker` is a component with a search box, a category drop-down and a grid of every bundled "
        "Lucide icon. The search matches names and tags (\"person\" finds `user`), Enter picks the first "
        "match and `on_change` receives the icon's name in `event.value`. `ui.icon_picker_dialog` puts it in "
        "a dialog that picks on a click, and `ui.icon_grid` is the bare grid, which only builds the rows in view.",
        "`ui.IconPicker` es un componente con un buscador, un desplegable de categorías y una cuadrícula con "
        "todos los iconos de Lucide incluidos. La búsqueda mira nombres y etiquetas (\"person\" encuentra "
        "`user`), Enter elige la primera coincidencia y `on_change` recibe el nombre del icono en `event.value`. "
        "`ui.icon_picker_dialog` lo pone en un diálogo que elige con un clic, y `ui.icon_grid` es la cuadrícula "
        "sola, que solo construye las filas visibles.",
    ),
    when=T(
        ["To let users choose an icon for a folder, a tag, a shortcut or a toolbar button.",
         "Show the current icon as a button and open `icon_picker_dialog` in a "
         "[Dialog layer](/pyzed/library/dialog-layer/) when it is pressed."],
        ["Para que el usuario elija el icono de una carpeta, una etiqueta, un atajo o un botón de la barra.",
         "Muestra el icono actual como un botón y abre `icon_picker_dialog` en una "
         "[capa de diálogo](/pyzed/es/library/dialog-layer/) al pulsarlo."],
    ),
    preview={"code": """ui.IconPicker(value="rocket", columns=10, height=200, clearable=True, on_change=on_change)""",
             "size": (720, 340)},
    usage="""class Shortcuts(pz.App):
    def __init__(self):
        self.icon = "rocket"
        self.picking = False

    def pick(self, name):
        self.icon, self.picking = name or "circle-dashed", False

    def view(self):
        page = ui.button("Change icon", lambda: setattr(self, "picking", True), icon=self.icon)
        dialog = ui.icon_picker_dialog(self.icon, self.pick, on_close=lambda: setattr(self, "picking", False))
        return ui.dialog_layer(page, dialog if self.picking else None,
                               on_dismiss=lambda: setattr(self, "picking", False))""",
    related=["icon", "dialog-layer", "color-picker"],
)

# --------------------------------------------------------------------------------------- feedback

add(
    slug="progress",
    name=T("Progress", "Progreso"),
    category="feedback",
    api=["pyzed.ui.progress"],
    blurb=T("A thin progress bar in a semantic color.", "Una barra de progreso fina en un color semántico."),
    desc=T(
        "A thin bar that fills from `0` to `max` (1.0 by default). `tint` changes its color and "
        "`height` its thickness.",
        "Una barra fina que se llena de `0` a `max` (1.0 por defecto). `tint` cambia su color y "
        "`height` su grosor.",
    ),
    when=T(
        ["For work whose progress you can measure: downloads, builds, imports.",
         "When you can't measure it, show a [Spinner](/pyzed/library/spinner/)."],
        ["Para trabajos cuyo avance puedes medir: descargas, compilaciones, importaciones.",
         "Cuando no se puede medir, muestra un [Spinner](/pyzed/es/library/spinner/)."],
    ),
    preview={"code": """pz.column([
    ui.progress(0.25),
    ui.progress(0.6, tint="success", height=6),
    ui.progress(37, max=40, tint="warning", height=8),
], spacing=18, width=360)"""},
    usage="""class Download(pz.App):
    def __init__(self):
        self.done, self.total = 0, 1

    def update(self, message):
        self.done, self.total = message  # posted from a worker thread with pz.post((done, total))

    def view(self):
        return ui.progress(self.done, max=self.total)""",
    related=["spinner", "slider", "stat"],
)

add(
    slug="spinner",
    name=T("Spinner", "Spinner"),
    category="feedback",
    api=["pyzed.ui.spinner"],
    blurb=T("A spinning arc for loading states.", "Un arco que gira para los estados de carga."),
    desc=T(
        "A spinning arc. Its angle comes from the app clock, so keep a subscription such as "
        "`pz.every(1 / 30, ...)` active while it is shown or it will not move.",
        "Un arco que gira. Su ángulo sale del reloj de la app, así que mantén una suscripción como "
        "`pz.every(1 / 30, ...)` mientras se muestra o no se moverá.",
    ),
    when=T(
        ["For short waits with an unknown duration: connecting, searching, loading a file.",
         "For long work with known progress use [Progress](/pyzed/library/progress/)."],
        ["Para esperas cortas de duración desconocida: conectando, buscando, cargando un archivo.",
         "Para trabajos largos con avance conocido usa [Progreso](/pyzed/es/library/progress/)."],
    ),
    preview={"code": """pz.row([
    ui.spinner(),
    ui.spinner(size=24, tint="success"),
    pz.row([ui.spinner(size=14), ui.muted("Indexing project…")], spacing=8, align="center"),
], spacing=24, align="center")"""},
    usage="""class Loader(pz.App):
    def __init__(self):
        self.loading = True

    def subscription(self):
        return pz.every(1 / 30, lambda: None) if self.loading else None

    def view(self):
        return ui.spinner() if self.loading else ui.label("Done")""",
    related=["progress", "empty-state"],
)

add(
    slug="callout",
    name=T("Callout", "Aviso"),
    category="feedback",
    api=["pyzed.ui.callout"],
    blurb=T("An inline notice with a title, text and actions.", "Un aviso en línea con título, texto y acciones."),
    desc=T(
        "An inline notice (a callout or banner): an icon, a title, an optional description, action "
        "buttons and a close button with `on_dismiss`. `tint` is `\"info\"` (default), `\"success\"`, "
        "`\"warning\"`, `\"error\"` or any theme token.",
        "Un aviso en línea (un callout o banner): un icono, un título, una descripción opcional, "
        "botones de acción y un botón de cerrar con `on_dismiss`. `tint` es `\"info\"` (por defecto), "
        "`\"success\"`, `\"warning\"`, `\"error\"` o cualquier token del tema.",
    ),
    when=T(
        ["For messages that belong to a place in the UI: a read-only file, a new version, a failed sync.",
         "For short-lived messages, use a [Toast](/pyzed/library/toast/)."],
        ["Para mensajes que pertenecen a un lugar de la interfaz: un archivo de solo lectura, una versión nueva, una sincronización fallida.",
         "Para mensajes pasajeros, usa una [Notificación](/pyzed/es/library/toast/)."],
    ),
    preview={"code": """pz.column([
    ui.callout("A new version is out", "Pyzed 0.4 adds the component designer.", tint="info",
               actions=[ui.button("What's new", on_open, size="sm")], on_dismiss=on_dismiss),
    ui.callout("Could not save", "The file is read-only.", tint="error"),
], spacing=10, width=520)"""},
    related=["toast", "alert", "empty-state"],
)

add(
    slug="toast",
    name=T("Toast", "Notificación"),
    category="overlays",
    api=["pyzed.ui.toast", "pyzed.ui.toasts"],
    blurb=T("Notifications stacked in the bottom-right corner.", "Notificaciones apiladas en la esquina inferior derecha."),
    desc=T(
        "`ui.toast` draws a notification with a title, a message, actions and a close button; `kind` is "
        "`\"info\"`, `\"success\"`, `\"warning\"` or `\"error\"`. `ui.toasts(base, items)` stacks them in "
        "the bottom-right corner over your view.",
        "`ui.toast` dibuja una notificación con título, mensaje, acciones y botón de cerrar; `kind` es "
        "`\"info\"`, `\"success\"`, `\"warning\"` o `\"error\"`. `ui.toasts(base, items)` las apila en la "
        "esquina inferior derecha encima de tu vista.",
    ),
    when=T(
        ["To confirm something that happened in the background (saved, copied, connected).",
         "Messages that need an answer belong in a [Dialog](/pyzed/library/confirm/)."],
        ["Para confirmar algo que pasó en segundo plano (guardado, copiado, conectado).",
         "Los mensajes que necesitan respuesta van en un [Diálogo](/pyzed/es/library/confirm/)."],
    ),
    preview={"code": """pz.column([
    ui.toast("Saved", "main.py was saved.", kind="success", on_dismiss=on_dismiss),
    ui.toast("Update available", "Pyzed 0.4 is on PyPI.", kind="info",
             actions=[ui.button("What's new", on_open, size="sm")], on_dismiss=on_dismiss),
    ui.toast("Could not connect", kind="error", on_dismiss=on_dismiss),
], spacing=8)""", "size": (720, 320)},
    usage="""import threading

class Notes(pz.App):
    def __init__(self):
        self.messages = []

    def notify(self, title):
        self.messages.append(title)
        threading.Timer(3, pz.post, args=(("expire", title),)).start()  # hide it after 3 s

    def update(self, message):
        if message[0] == "expire":
            self.messages.remove(message[1])

    def view(self):
        items = [ui.toast(m, kind="success", on_dismiss=lambda m=m: self.messages.remove(m))
                 for m in self.messages]
        return ui.toasts(self.main_view(), items)""",
    related=["callout", "layer", "alert"],
)

add(
    slug="empty-state",
    name=T("Empty state", "Estado vacío"),
    category="feedback",
    api=["pyzed.ui.empty_state"],
    blurb=T("A centered placeholder for empty lists and searches.", "Un marcador centrado para listas y búsquedas vacías."),
    desc=T(
        "A centered icon, title, description and actions for a place that has nothing to show yet.",
        "Un icono, un título, una descripción y acciones centrados para un lugar que aún no tiene nada que mostrar.",
    ),
    when=T(
        ["For an empty list, a search with no results, or a panel before the first file is opened.",
         "Offer the next step as an action (Create, Clear filters, Open folder)."],
        ["Para una lista vacía, una búsqueda sin resultados o un panel antes de abrir el primer archivo.",
         "Ofrece el siguiente paso como acción (Crear, Quitar filtros, Abrir carpeta)."],
    ),
    preview={"code": """ui.empty_state("No results", "Try a different search.", icon="search",
               actions=[ui.button("Clear filters", on_clear, size="sm")])"""},
    related=["callout", "keybinding-hint", "card"],
)

add(
    slug="count-badge",
    name=T("Count badge", "Contador"),
    category="feedback",
    api=["pyzed.ui.count_badge"],
    blurb=T("A round counter that shows 99+ above its max.", "Un contador redondo que muestra 99+ por encima del máximo."),
    desc=T("A round counter for notifications or problems. Above `max` it shows `99+`.",
           "Un contador redondo para notificaciones o problemas. Por encima de `max` muestra `99+`."),
    when=T(
        ["Next to an icon or tab to show how many unread items or errors there are.",
         "For text statuses use a [Badge](/pyzed/library/badge/)."],
        ["Junto a un icono o pestaña para indicar cuántos elementos sin leer o errores hay.",
         "Para estados de texto usa una [Insignia](/pyzed/es/library/badge/)."],
    ),
    preview={"code": """pz.row([
    ui.count_badge(3),
    ui.count_badge(42, tint="success"),
    ui.count_badge(120, tint="error"),
    pz.row([ui.icon_button("bell", on_press), ui.count_badge(7)], spacing=2, align="center"),
], spacing=16, align="center")"""},
    related=["badge", "indicator", "status-bar"],
)

add(
    slug="keybinding-hint",
    name=T("Keybinding hint", "Pista de atajo"),
    category="feedback",
    api=["pyzed.ui.keybinding_hint"],
    blurb=T("A muted “Open file Ctrl P” hint.", "Una pista discreta tipo “Abrir archivo Ctrl P”."),
    desc=T("A muted hint that pairs an action with its shortcut, for footers and empty states.",
           "Una pista discreta que une una acción con su atajo, para pies y estados vacíos."),
    when=T(
        ["In empty editors and footers, to teach the shortcuts of the most useful actions."],
        ["En editores vacíos y pies de página, para enseñar los atajos de las acciones más útiles."],
    ),
    preview={"code": """pz.column([
    ui.keybinding_hint("Open file", "ctrl-p"),
    ui.keybinding_hint("Command palette", "ctrl-shift-p"),
    ui.keybinding_hint("Toggle terminal", "ctrl-j"),
], spacing=10, align="center")"""},
    related=["kbd", "empty-state", "shortcuts"],
)

# ------------------------------------------------------------------------------------------- data

add(
    slug="table",
    name=T("Table", "Tabla"),
    category="data",
    api=["pyzed.ui.table", "pyzed.ui.Column"],
    blurb=T("A data table with a fixed header, sorting and selection.",
            "Una tabla de datos con cabecera fija, ordenación y selección."),
    desc=T(
        "A data table with a fixed header, optional sorting and row selection. Columns are `ui.Column` "
        "objects whose `key` is a dict key, an attribute name or a function of the row; `render` turns a "
        "value into any widget. The table sorts the rows itself by the column whose **title** is "
        "`sort_by`: you only store that title and the direction.",
        "Una tabla de datos con cabecera fija, ordenación opcional y selección de filas. Las columnas "
        "son objetos `ui.Column` cuyo `key` es una clave de dict, un atributo o una función de la fila; "
        "`render` convierte un valor en cualquier widget. La tabla ordena las filas ella misma por la "
        "columna cuyo **título** es `sort_by`: solo guardas ese título y la dirección.",
    ),
    when=T(
        ["For records with several comparable fields: files, users, processes, results.",
         "For a single column of items, a list of [List items](/pyzed/library/list-item/) is lighter."],
        ["Para registros con varios campos comparables: archivos, usuarios, procesos, resultados.",
         "Para una sola columna de elementos, una lista de [Filas](/pyzed/es/library/list-item/) es más ligera."],
    ),
    preview={"code": """rows = [
    {"name": "render.rs", "lang": "Rust", "lines": 1840},
    {"name": "app.py", "lang": "Python", "lines": 512},
    {"name": "theme.py", "lang": "Python", "lines": 730},
    {"name": "docs.yml", "lang": "YAML", "lines": 64},
]
pz.container(ui.table(
    [ui.Column("File", "name"), ui.Column("Language", "lang", width=120),
     ui.Column("Lines", "lines", width=80, align="end")],
    rows, sort_by="Lines", descending=True, on_sort=on_sort, selected=rows[1], striped=True,
), width=520)"""},
    usage="""class Files(pz.App):
    def __init__(self):
        self.rows = [{"name": "app.py", "lines": 512}, {"name": "theme.py", "lines": 730}]
        self.sort_by, self.descending, self.selected = "Lines", True, None

    def sort(self, title):
        self.descending = not self.descending if self.sort_by == title else False
        self.sort_by = title

    def view(self):
        return ui.table(
            [ui.Column("File", "name"), ui.Column("Lines", "lines", width=80, align="end")],
            self.rows, sort_by=self.sort_by, descending=self.descending, on_sort=self.sort,
            on_row_press=lambda row: setattr(self, "selected", row), selected=self.selected,
        )""",
    examples=[
        {"title": T("Custom cells", "Celdas personalizadas"),
         "text": T("`render` receives the value and returns a widget, here a badge.",
                   "`render` recibe el valor y devuelve un widget, aquí una insignia."),
         "code": """rows = [{"job": "build", "state": "passed"}, {"job": "lint", "state": "failed"},
        {"job": "docs", "state": "running"}]
tint = {"passed": "success", "failed": "error", "running": "warning"}
pz.container(ui.table(
    [ui.Column("Job", "job"),
     ui.Column("State", "state", width=120, render=lambda s: ui.badge(s, tint=tint[s]))],
    rows,
), width=400)""", "size": (720, 200)},
    ],
    related=["list-item", "virtual-list", "stat", "settings-group"],
)

add(
    slug="virtual-list",
    name=T("Virtual list", "Lista virtual"),
    category="lists",
    api=["pyzed.ui.virtual_list", "pyzed.virtual_column"],
    blurb=T("A list that only builds the rows in view, for millions of items.",
            "Una lista que solo construye las filas visibles, para millones de elementos."),
    desc=T(
        "A scrolling list for thousands or millions of items. Only the rows in view are built: "
        "`render(item)` is called when an item scrolls into view, so the list costs the same whatever "
        "its length. Every row has the same `item_height`. `pz.virtual_column` is the building block "
        "underneath (rows by index, inside any `scrollable`), and [Table](/pyzed/library/table/) uses it "
        "for its rows too.",
        "Una lista con scroll para miles o millones de elementos. Solo se construyen las filas visibles: "
        "`render(elemento)` se llama cuando un elemento entra en la vista, así que la lista cuesta lo mismo "
        "sea cual sea su longitud. Todas las filas tienen la misma `item_height`. `pz.virtual_column` es la "
        "pieza de debajo (filas por índice, dentro de cualquier `scrollable`), y la "
        "[Tabla](/pyzed/es/library/table/) también la usa para sus filas.",
    ),
    when=T(
        ["For logs, search results, file lists or any list that can grow past a few hundred rows.",
         "For short lists, a `pz.column` of [List items](/pyzed/library/list-item/) is simpler."],
        ["Para logs, resultados de búsqueda, listas de archivos o cualquier lista que pueda pasar de unos cientos de filas.",
         "Para listas cortas, una `pz.column` de [Filas](/pyzed/es/library/list-item/) es más sencilla."],
    ),
    preview={"code": """files = [f"src/module_{i:06}.py" for i in range(1_000_000)]
pz.container(ui.virtual_list(
    files, lambda f: ui.list_item(f, icon="file-code", selected=f.endswith("02.py")),
    height=240,
), width=420)""", "size": (720, 300)},
    usage="""class Logs(pz.App):
    def __init__(self):
        self.lines = [f"[{i:06}] request handled" for i in range(500_000)]

    def view(self):
        return ui.virtual_list(self.lines, lambda line: pz.text(line, font="mono", size=12),
                               item_height=20, id="logs")""",
    examples=[
        {"title": T("Rows by index", "Filas por índice"),
         "text": T("`pz.virtual_column(count, item, item_height=...)` calls `item(index)`, handy when the rows "
                   "come from an array, a database cursor or a computed value. Scroll it like any `scrollable`: "
                   "row `i` starts at `i * (item_height + spacing)`.",
                   "`pz.virtual_column(count, item, item_height=...)` llama a `item(índice)`, útil cuando las filas "
                   "salen de un array, un cursor de base de datos o un cálculo. Se desplaza como cualquier "
                   "`scrollable`: la fila `i` empieza en `i * (item_height + spacing)`."),
         "code": """pz.container(pz.scrollable(
    pz.virtual_column(10_000_000, lambda i: pz.text(f"{i:>10,}  {i * i:>22,}", font="mono", size=12),
                      item_height=22),
    height=150,
), width=420)""", "size": (720, 200)},
    ],
    notes=T(
        "- Rows are built again when they scroll back into view, so keep `render` cheap or wrap it in "
        "`@pz.memo`.\n"
        "- `items` should be a list or another sequence: other iterables are copied into a list on every `view()`.",
        "- Las filas se vuelven a construir cuando vuelven a la vista, así que mantén `render` ligero o "
        "envuélvelo en `@pz.memo`.\n"
        "- `items` debería ser una lista u otra secuencia: otros iterables se copian a una lista en cada `view()`.",
    ),
    related=["list-item", "table"],
    badge="new",
)

add(
    slug="stat",
    name=T("Stat", "Cifra"),
    category="data",
    api=["pyzed.ui.stat"],
    blurb=T("A dashboard number with change and sparkline.", "Una cifra de dashboard con variación y minigráfico."),
    desc=T(
        "A dashboard tile: a title, a large value, an optional change (`delta`, shown as `+4.2%` in green "
        "or red) and an optional `trend` drawn as a sparkline.",
        "Un panel de dashboard: un título, un valor grande, una variación opcional (`delta`, mostrada como "
        "`+4.2%` en verde o rojo) y una `trend` opcional dibujada como minigráfico.",
    ),
    when=T(["For key numbers at the top of a dashboard or report."],
           ["Para las cifras clave en la parte de arriba de un dashboard o informe."]),
    preview={"code": """pz.row([
    ui.stat("Users", "1,284", delta=12.5, trend=[3, 5, 4, 6, 8, 7, 9], width=200),
    ui.stat("Errors", "37", delta=-8.0, width=200),
    ui.stat("Build time", "1m 12s", width=200),
], spacing=12)"""},
    related=["sparkline", "bar-chart", "donut"],
)

add(
    slug="sparkline",
    name=T("Sparkline", "Minigráfico"),
    category="data",
    api=["pyzed.ui.sparkline"],
    blurb=T("A tiny line chart for trends.", "Un gráfico de líneas diminuto para tendencias."),
    desc=T("A small line chart, filled below the line by default, that shows the shape of a series.",
           "Un gráfico de líneas pequeño, relleno bajo la línea por defecto, que muestra la forma de una serie."),
    when=T(["Inline next to a number or in a table cell, where the trend matters more than the values."],
           ["En línea junto a un número o en una celda, cuando importa más la tendencia que los valores."]),
    preview={"code": """pz.column([
    ui.sparkline([1, 4, 2, 6, 3, 7, 5, 8], width=240, height=48),
    ui.sparkline([8, 6, 7, 4, 5, 3, 2, 1], width=240, height=48, tint="error", fill=False),
], spacing=16)"""},
    related=["stat", "bar-chart"],
)

add(
    slug="bar-chart",
    name=T("Bar chart", "Gráfico de barras"),
    category="data",
    api=["pyzed.ui.bar_chart"],
    blurb=T("A vertical bar chart with labels.", "Un gráfico de barras verticales con etiquetas."),
    desc=T("A vertical bar chart drawn with `pz.canvas` in the theme colors, with optional labels under the bars.",
           "Un gráfico de barras verticales dibujado con `pz.canvas` en los colores del tema, con etiquetas opcionales bajo las barras."),
    when=T(["To compare a handful of values side by side (per day, per category)."],
           ["Para comparar unos pocos valores lado a lado (por día, por categoría)."]),
    preview={"code": """ui.bar_chart([12, 19, 8, 15, 22, 17, 9], labels=["M", "T", "W", "T", "F", "S", "S"],
             width=360, height=180)"""},
    related=["donut", "sparkline", "stat"],
)

add(
    slug="donut",
    name=T("Donut", "Dona"),
    category="data",
    api=["pyzed.ui.donut"],
    blurb=T("A donut chart with a label in the middle.", "Un gráfico de dona con una etiqueta en el centro."),
    desc=T("A donut chart of `values`, with a `label` in the center. `colors` overrides the theme's palette.",
           "Un gráfico de dona con `values` y una `label` en el centro. `colors` reemplaza la paleta del tema."),
    when=T(["To show the parts of a whole (disk usage, languages of a project) with three or four slices."],
           ["Para mostrar las partes de un todo (uso de disco, lenguajes de un proyecto) con tres o cuatro porciones."]),
    preview={"code": """pz.row([
    ui.donut([60, 25, 15], label="60%"),
    ui.donut([45, 35, 20], colors=["#e5c07b", "#c678dd", "#56b6c2"], size=120, thickness=20, label="3"),
], spacing=32, align="center")"""},
    related=["bar-chart", "stat"],
)

add(
    slug="diff-stat",
    name=T("Diff stat", "Resumen de cambios"),
    category="data",
    api=["pyzed.ui.diff_stat"],
    blurb=T("`+12 −3` with GitHub-style blocks.", "`+12 −3` con bloques al estilo de GitHub."),
    desc=T("Lines added and removed, with a row of green and red blocks, as in the git panel of a code editor.",
           "Líneas añadidas y quitadas, con una fila de bloques verdes y rojos, como en el panel de git de un editor de código."),
    when=T(["Next to a file, commit or pull request in a list of changes."],
           ["Junto a un archivo, commit o pull request en una lista de cambios."]),
    preview={"code": """pz.column([
    pz.row([ui.label("render.rs", mono=True), pz.hspace(), ui.diff_stat(42, 9)], align="center"),
    pz.row([ui.label("app.py", mono=True), pz.hspace(), ui.diff_stat(3, 27)], align="center"),
    pz.row([ui.label("README.md", mono=True), pz.hspace(), ui.diff_stat(12, 0)], align="center"),
], spacing=10, width=320)"""},
    related=["badge", "tree"],
)

add(
    slug="facepile",
    name=T("Facepile", "Facepile"),
    category="data",
    api=["pyzed.ui.facepile"],
    blurb=T("Overlapping collaborator avatars with +N.", "Avatares de colaboradores superpuestos con +N."),
    desc=T("Overlapping avatars of collaborators, as in the title bar of a collaborative editor. People beyond `max_shown` are grouped into `+N`.",
           "Avatares superpuestos de colaboradores, como en la barra de título de un editor colaborativo. Los que pasan de `max_shown` se agrupan en `+N`."),
    when=T(["To show who is in a project, a call or a document without listing names."],
           ["Para mostrar quién está en un proyecto, una llamada o un documento sin listar los nombres."]),
    preview={"code": """pz.column([
    ui.facepile(["Ana", "Luis", "Kev", "Marta"]),
    ui.facepile(["Ana", "Luis", "Kev", "Marta", "Sam", "Jo", "Lee", "Max"], size=28, max_shown=4),
], spacing=16, align="center")"""},
    related=["avatar", "title-bar"],
)

add(
    slug="settings-group",
    name=T("Settings group", "Grupo de ajustes"),
    category="data",
    api=["pyzed.ui.settings_group"],
    blurb=T("A titled block of field rows, for settings screens.", "Un bloque con título de filas de ajustes, para pantallas de ajustes."),
    desc=T("A titled block of `ui.field` rows separated by lines, with an optional description, like a settings screen.",
           "Un bloque con título de filas `ui.field` separadas por líneas, con una descripción opcional, como una pantalla de ajustes."),
    when=T(["To organize a preferences screen into sections (Editor, Files, Git…)."],
           ["Para organizar una pantalla de preferencias en secciones (Editor, Archivos, Git…)."]),
    preview={"code": """pz.container(ui.settings_group("Editor", [
    ui.field("Font size", ui.number_field(14, on_change, suffix="px")),
    ui.field("Soft wrap", ui.switch(True, on_toggle)),
    ui.field("Theme", ui.select(["One Dark", "One Light"], "One Dark", on_select, width=150)),
], description="Editor preferences."), width=460)"""},
    related=["field", "accordion", "card"],
)

# ------------------------------------------------------------------------------------------ lists

add(
    slug="list-item",
    name=T("List item", "Fila de lista"),
    category="lists",
    api=["pyzed.ui.list_item"],
    blurb=T("A list row with icon, text and an end slot.", "Una fila de lista con icono, texto y un hueco al final."),
    desc=T(
        "A list row: an icon, the text and `start`/`end` slots for any widget. It "
        "supports `selected`, `focused` (focus border), `disabled`, nesting with `indent`, and "
        "`on_right_press` for a context menu.",
        "Una fila de lista: un icono, el texto y huecos `start`/`end` para "
        "cualquier widget. Admite `selected`, `focused` (borde de foco), `disabled`, anidar con `indent` "
        "y `on_right_press` para un menú contextual.",
    ),
    when=T(
        ["For any vertical list: recent files, search results, settings categories, people.",
         "Use `inset=True` inside panels so the highlight has a margin."],
        ["Para cualquier lista vertical: archivos recientes, resultados, categorías de ajustes, personas.",
         "Usa `inset=True` dentro de paneles para que el resaltado tenga margen."],
    ),
    preview={"code": """pz.column([
    ui.list_item("main.py", on_open, icon="file-code", icon_color="#3572a5", selected=True, inset=True),
    ui.list_item("README.md", on_open, icon="file-text", inset=True, end=ui.badge("M", tint="warning")),
    ui.list_item("Cargo.toml", on_open, icon="file-cog", inset=True, end=ui.kbd("ctrl-1", size="xs")),
    ui.list_item("old.txt", on_open, icon="file", inset=True, disabled=True),
], width=320)"""},
    usage="""class Recent(pz.App):
    def __init__(self):
        self.files = ["main.py", "app.py", "README.md"]
        self.current = "main.py"

    def view(self):
        return pz.column([
            ui.list_item(f, lambda f=f: setattr(self, "current", f), icon="file",
                         selected=f == self.current, inset=True)
            for f in self.files
        ])""",
    related=["list-header", "tree", "menu"],
)

add(
    slug="list-header",
    name=T("List header", "Cabecera de lista"),
    category="lists",
    api=["pyzed.ui.list_header"],
    blurb=T("A small section title for lists, with an end slot.", "Un título pequeño de sección para listas, con hueco al final."),
    desc=T("A muted section header for lists, with an optional widget at the end (usually an icon button).",
           "Una cabecera de sección discreta para listas, con un widget opcional al final (normalmente un botón de icono)."),
    when=T(["To split a list into groups (RECENT, PINNED) or to add an action to a list."],
           ["Para dividir una lista en grupos (RECIENTES, FIJADOS) o añadirle una acción."]),
    preview={"code": """pz.column([
    ui.list_header("RECENT", end=ui.icon_button("plus", on_new, size="xs")),
    ui.list_item("main.py", on_open, icon="file-code", inset=True),
    ui.list_item("app.py", on_open, icon="file-code", inset=True),
    ui.list_header("PINNED"),
    ui.list_item("README.md", on_open, icon="file-text", inset=True),
], width=300)"""},
    related=["list-item", "panel-header"],
)

add(
    slug="tree",
    name=T("Tree", "Árbol"),
    category="lists",
    api=["pyzed.ui.tree", "pyzed.ui.TreeNode"],
    blurb=T("A collapsible file tree with icons and git colors.", "Un árbol de archivos plegable con iconos y colores de git."),
    desc=T(
        "A project panel: collapsible folders, an icon per file type and git status colors. "
        "`TreeNode.from_paths(paths, status=...)` builds the nodes, puts folders first and propagates "
        "the git status to the folders that contain changes. Each node's id is its path; you own the "
        "`expanded` set and the `selected` id.",
        "Un panel de proyecto: carpetas plegables, un icono por tipo de archivo y colores de "
        "estado de git. `TreeNode.from_paths(paths, status=...)` crea los nodos, pone las carpetas "
        "primero y propaga el estado de git a las carpetas con cambios. El id de cada nodo es su ruta; "
        "el conjunto `expanded` y el id `selected` son tuyos.",
    ),
    when=T(
        ["For files and any hierarchy: outlines, categories, settings sections.",
         "`status` is `\"modified\"`, `\"created\"`, `\"deleted\"`, `\"conflict\"` or `\"ignored\"`."],
        ["Para archivos y cualquier jerarquía: esquemas, categorías, secciones de ajustes.",
         "`status` es `\"modified\"`, `\"created\"`, `\"deleted\"`, `\"conflict\"` o `\"ignored\"`."],
    ),
    preview={"code": """nodes = ui.TreeNode.from_paths(
    ["src/main.rs", "src/app.rs", "src/ui/button.rs", "src/ui/mod.rs", "tests/app.rs", "Cargo.toml"],
    status={"src/app.rs": "modified", "src/ui/button.rs": "created"},
)
pz.container(ui.tree(nodes, expanded={"src", "src/ui"}, selected="src/app.rs",
                     on_toggle=on_toggle, on_select=on_select), width=280)"""},
    usage="""class Explorer(pz.App):
    def __init__(self):
        self.nodes = ui.TreeNode.from_paths(["src/main.rs", "src/app.rs", "Cargo.toml"])
        self.expanded = {"src"}
        self.selected = None

    def toggle(self, folder):
        self.expanded ^= {folder}

    def view(self):
        return ui.tree(self.nodes, expanded=self.expanded, selected=self.selected,
                       on_toggle=self.toggle, on_select=lambda path: setattr(self, "selected", path))""",
    examples=[
        {"title": T("A real folder", "Una carpeta real"),
         "text": T("Build the paths with `pathlib` and pass them to `from_paths`.",
                   "Crea las rutas con `pathlib` y pásalas a `from_paths`."),
         "code": """from pathlib import Path

root = Path(".")
paths = [p.relative_to(root).as_posix() for p in root.rglob("*")
         if p.is_file() and ".git" not in p.parts]
nodes = ui.TreeNode.from_paths(paths)""", "shot": False},
        {"title": T("Nodes by hand", "Nodos a mano"),
         "text": T("Folders are nodes with `children`.", "Las carpetas son nodos con `children`."),
         "code": """nodes = [
    ui.TreeNode("Inbox", children=[ui.TreeNode("Welcome", id="inbox/1", icon="mail")], id="inbox"),
    ui.TreeNode("Archive", children=[], id="archive"),
    ui.TreeNode("Notes.md", id="notes", icon="notebook-pen"),
]
pz.container(ui.tree(nodes, expanded={"inbox"}, selected="inbox/1"), width=260)""", "size": (720, 180)},
    ],
    related=["list-item", "panel", "workspace"],
)

add(
    slug="menu",
    name=T("Menu", "Menú"),
    category="lists",
    api=["pyzed.ui.menu", "pyzed.ui.MenuItem", "pyzed.ui.SEPARATOR"],
    blurb=T("A context menu with icons, shortcuts and checks.", "Un menú contextual con iconos, atajos y marcas."),
    desc=T(
        "A floating context menu. Items are `ui.MenuItem(label, on_press, icon=, keys=, checked=, "
        "danger=, disabled=)`; `ui.SEPARATOR` draws a line between groups and a plain string is a "
        "header. Show it with a [Popover](/pyzed/library/popover/) or a [Layer](/pyzed/library/layer/).",
        "Un menú contextual flotante. Las entradas son `ui.MenuItem(label, on_press, icon=, keys=, "
        "checked=, danger=, disabled=)`; `ui.SEPARATOR` dibuja una línea entre grupos y una cadena es "
        "una cabecera. Muéstralo con un [Popover](/pyzed/es/library/popover/) o una "
        "[Capa](/pyzed/es/library/layer/).",
    ),
    when=T(
        ["For right-click menus and the options of a split button or an ellipsis button.",
         "Mark destructive actions with `danger=True` and put them last."],
        ["Para menús de clic derecho y las opciones de un botón dividido o de puntos suspensivos.",
         "Marca las acciones destructivas con `danger=True` y ponlas al final."],
    ),
    preview={"code": """ui.menu([
    ui.MenuItem("New file", on_new, icon="file-plus", keys="ctrl-n"),
    ui.MenuItem("New folder", on_new_folder, icon="folder-plus"),
    ui.SEPARATOR,
    "EDIT",
    ui.MenuItem("Copy path", on_copy, keys="ctrl-alt-c"),
    ui.MenuItem("Soft wrap", on_wrap, checked=True),
    ui.SEPARATOR,
    ui.MenuItem("Delete", on_delete, icon="trash-2", danger=True),
])"""},
    related=["popover", "split-button", "list-item"],
)

add(
    slug="accordion",
    name=T("Accordion", "Acordeón"),
    category="lists",
    api=["pyzed.ui.accordion", "pyzed.ui.AccordionSection"],
    blurb=T("Stacked collapsible sections, like the panels of a settings screen.",
            "Secciones plegables apiladas, como los paneles de una pantalla de ajustes."),
    desc=T(
        "Stacked collapsible sections separated by dividers. Sections are `(key, title, content)` tuples "
        "or `ui.AccordionSection` objects (with `icon` and a header `end` widget). You own the open state: "
        "`open` is a set of keys, a `{key: bool}` dict or `True`, and `on_toggle` receives the key.",
        "Secciones plegables apiladas separadas por divisores. Las secciones son tuplas "
        "`(key, title, content)` u objetos `ui.AccordionSection` (con `icon` y un widget `end` en la "
        "cabecera). El estado abierto es tuyo: `open` es un conjunto de claves, un dict `{clave: bool}` o "
        "`True`, y `on_toggle` recibe la clave.",
    ),
    when=T(
        ["For long settings or property panels where users only need a few sections at a time.",
         "For a single collapsible block, use a [Disclosure](/pyzed/library/disclosure/)."],
        ["Para paneles largos de ajustes o propiedades en los que solo hacen falta algunas secciones a la vez.",
         "Para un solo bloque plegable, usa un [Desplegable](/pyzed/es/library/disclosure/)."],
    ),
    preview={"code": """rows = lambda *items: pz.column([ui.field(k, ui.switch(v, on_toggle)) for k, v in items], spacing=8)
pz.container(ui.accordion([
    ("editor", "Editor", rows(("Soft wrap", True), ("Minimap", False))),
    ("files", "Files", rows(("Autosave", True))),
    ("git", "Git", ui.muted("Collapsed sections only show their header.")),
], open={"editor", "files"}, on_toggle=on_toggle,
   icons={"editor": "file-code", "files": "folder", "git": "git-branch"}), width=400)"""},
    usage="""class Settings(pz.App):
    def __init__(self):
        self.open = {"editor"}

    def view(self):
        return ui.accordion(
            [("editor", "Editor", ui.muted("…")), ("files", "Files", ui.muted("…"))],
            open=self.open, on_toggle=lambda key: self.open.symmetric_difference_update({key}),
        )""",
    related=["disclosure", "settings-group"],
)

add(
    slug="disclosure",
    name=T("Disclosure", "Desplegable"),
    category="lists",
    api=["pyzed.ui.disclosure"],
    blurb=T("One collapsible section with an arrow.", "Una sección plegable con flecha."),
    desc=T("A header with an arrow that shows or hides `content`. You own the open state: change it in `on_toggle`.",
           "Una cabecera con una flecha que muestra u oculta `content`. El estado abierto es tuyo: cámbialo en `on_toggle`."),
    when=T(["To hide advanced options or details until they are needed."],
           ["Para esconder opciones avanzadas o detalles hasta que hagan falta."]),
    preview={"code": """pz.column([
    ui.disclosure("Advanced options", ui.muted("Shown while the section is open."), open=True,
                  on_toggle=on_toggle),
    ui.disclosure("Environment variables", ui.muted("Hidden"), open=False, on_toggle=on_toggle,
                  end=ui.badge("3")),
], spacing=10, width=380)"""},
    usage="""class Form(pz.App):
    def __init__(self):
        self.advanced = False

    def view(self):
        return ui.disclosure("Advanced options", self.advanced_options(), open=self.advanced,
                             on_toggle=lambda: setattr(self, "advanced", not self.advanced))""",
    related=["accordion", "card"],
)

# ------------------------------------------------------------------------------------- navigation

add(
    slug="tab-bar",
    name=T("Tab bar", "Barra de pestañas"),
    category="navigation",
    api=["pyzed.ui.tab_bar", "pyzed.ui.Tab", "pyzed.ui.tab"],
    blurb=T("Editor tabs with icons, dirty dots and close buttons.", "Pestañas de editor con iconos, puntos de cambios y botón de cerrar."),
    desc=T(
        "A row of editor tabs with optional controls at the start and end. `ui.Tab.for_file(path)` "
        "creates a tab with the file's name, icon and path as id. `dirty=True` shows a dot that turns "
        "into the close button on hover, `preview=True` draws the name in italics, and `status` tints it "
        "with a git color. `on_select(id)` and `on_close(id)` receive the tab id.",
        "Una fila de pestañas de editor con controles opcionales al principio y al final. "
        "`ui.Tab.for_file(path)` crea una pestaña con el nombre del archivo, su icono y la ruta como id. "
        "`dirty=True` muestra un punto que se convierte en el botón de cerrar al pasar el ratón, "
        "`preview=True` pone el nombre en cursiva y `status` lo tiñe con un color de git. "
        "`on_select(id)` y `on_close(id)` reciben el id de la pestaña.",
    ),
    when=T(["For open documents in an editor, or any set of views the user opens and closes."],
           ["Para los documentos abiertos de un editor, o cualquier conjunto de vistas que se abren y cierran."]),
    preview={"code": """ui.tab_bar(
    [ui.Tab.for_file("src/main.rs"),
     ui.Tab.for_file("src/app.rs", dirty=True, status="modified"),
     ui.Tab.for_file("README.md", preview=True)],
    "src/main.rs", on_select=on_select, on_close=on_close,
    start=[ui.icon_button("arrow-left", on_back, size="sm"),
           ui.icon_button("arrow-right", on_forward, size="sm")],
    end=[ui.icon_button("plus", on_new, size="sm"), ui.icon_button("columns-2", on_split, size="sm")],
)""", "size": (720, 140)},
    usage="""class Editor(pz.App):
    def __init__(self):
        self.open, self.active = ["main.py", "app.py"], "main.py"

    def close(self, path):
        i = self.open.index(path)
        self.open.remove(path)
        if self.active == path:
            self.active = self.open[min(i, len(self.open) - 1)] if self.open else None

    def view(self):
        return ui.tab_bar([ui.Tab.for_file(p) for p in self.open], self.active,
                          on_select=lambda p: setattr(self, "active", p), on_close=self.close)""",
    related=["toolbar", "breadcrumbs", "segmented"],
)

add(
    slug="breadcrumbs",
    name=T("Breadcrumbs", "Migas de pan"),
    category="navigation",
    api=["pyzed.ui.breadcrumbs"],
    blurb=T("`src › main.rs › fn main`, optionally clickable.", "`src › main.rs › fn main`, pulsables si quieres."),
    desc=T("The path to the current location. Parts are strings or `(icon, text)` tuples; `on_press` receives the index of the clicked part.",
           "La ruta hasta la ubicación actual. Las partes son cadenas o tuplas `(icono, texto)`; `on_press` recibe el índice de la parte pulsada."),
    when=T(["Above an editor or a nested view, to show where you are and jump to a parent."],
           ["Encima de un editor o una vista anidada, para mostrar dónde estás y saltar a un nivel superior."]),
    preview={"code": """pz.column([
    ui.breadcrumbs(["src", "ui", "button.rs"]),
    ui.breadcrumbs([("folder", "src"), ("file-code", "main.rs"), "fn main"], on_press=on_press),
    ui.breadcrumbs(["Settings", "Editor", "Font"], separator="/"),
], spacing=14)"""},
    related=["toolbar", "tab-bar"],
)

add(
    slug="toolbar",
    name=T("Toolbar", "Barra de herramientas"),
    category="navigation",
    api=["pyzed.ui.toolbar"],
    blurb=T("The bar under the tabs: breadcrumbs and buffer actions.", "La barra bajo las pestañas: migas de pan y acciones."),
    desc=T("The bar below the tabs of a code editor: widgets at the `start` (usually breadcrumbs) and at the `end` (buffer actions).",
           "La barra bajo las pestañas de un editor de código: widgets al principio (`start`, normalmente migas de pan) y al final (`end`, acciones del buffer)."),
    when=T(["Between the tab bar and the editor, or at the top of any content view."],
           ["Entre la barra de pestañas y el editor, o arriba de cualquier vista de contenido."]),
    preview={"code": """ui.toolbar(
    [ui.breadcrumbs([("file-code", "src"), "main.rs", "fn main"])],
    [ui.icon_button("search", on_search, size="sm"), ui.icon_button("sparkles", on_assist, size="sm")],
)""", "size": (720, 120)},
    related=["tab-bar", "breadcrumbs", "icon-button"],
)

# --------------------------------------------------------------------------------------- overlays

add(
    slug="layer",
    name=T("Layer", "Capa"),
    category="overlays",
    api=["pyzed.ui.layer"],
    blurb=T("Draws an overlay over your view; clicking outside dismisses it.",
            "Dibuja una capa encima de tu vista; al pulsar fuera se cierra."),
    desc=T(
        "Stacks `overlay` on top of `base`. Clicking outside the overlay sends `on_dismiss`, and "
        "`backdrop` dims the view behind it. With `overlay=None` it returns `base` unchanged, so it can "
        "always wrap your view. `align_x`, `align_y` and `offset` place the overlay (by default centered "
        "at the top, like a command palette).",
        "Apila `overlay` encima de `base`. Al pulsar fuera de la capa se envía `on_dismiss`, y "
        "`backdrop` oscurece la vista de detrás. Con `overlay=None` devuelve `base` sin cambios, así que "
        "puede envolver siempre tu vista. `align_x`, `align_y` y `offset` colocan la capa (por defecto "
        "centrada arriba, como una paleta de comandos).",
    ),
    when=T(
        ["To show palettes, pickers, modals and menus above everything else.",
         "For dialogs, [Dialog layer](/pyzed/library/dialog-layer/) already centers them over a dimmed backdrop."],
        ["Para mostrar paletas, buscadores, modales y menús encima de todo.",
         "Para diálogos, [Capa de diálogo](/pyzed/es/library/dialog-layer/) ya los centra sobre un fondo oscurecido."],
    ),
    preview={"code": """ui.layer(
    main_view(),
    ui.picker("", on_query, [(ui.PaletteItem("notes.py", on_open, icon="file-code"), []),
                             (ui.PaletteItem("README.md", on_open, icon="file-text"), [])],
              placeholder="Search files…", width=420),
    on_dismiss=on_close, backdrop="#00000055", offset=40,
)""", "fill": True},
    usage="""class App(pz.App):
    def __init__(self):
        self.finder_open = False

    def view(self):
        overlay = self.finder() if self.finder_open else None
        return ui.layer(self.main_view(), overlay,
                        on_dismiss=lambda: setattr(self, "finder_open", False))""",
    related=["modal", "popover", "dialog-layer"],
)

add(
    slug="modal",
    name=T("Modal", "Modal"),
    category="overlays",
    api=["pyzed.ui.modal"],
    blurb=T("A dialog surface with title, content and footer buttons.", "Una superficie de diálogo con título, contenido y botones al pie."),
    desc=T(
        "A dialog surface with a title, a close button, your content and a footer of buttons. Use it as "
        "the overlay of `ui.layer` or `ui.dialog_layer`. The ready-made [dialogs](/pyzed/library/confirm/) "
        "are built on it.",
        "Una superficie de diálogo con título, botón de cerrar, tu contenido y un pie de botones. Úsala "
        "como capa de `ui.layer` o `ui.dialog_layer`. Los [diálogos](/pyzed/es/library/confirm/) "
        "listos para usar están hechos con ella.",
    ),
    when=T(["For dialogs with your own content: a form, settings, an About box."],
           ["Para diálogos con tu propio contenido: un formulario, ajustes, una caja Acerca de."]),
    preview={"code": """ui.modal(
    ui.muted("notes.py has unsaved changes. Save them before closing?"),
    title="Save changes?",
    on_close=on_close,
    footer=[ui.button("Don't save", on_discard, variant="ghost"), ui.button("Cancel", on_close),
            ui.button("Save", on_save, variant="solid")],
    width=440,
)"""},
    examples=[
        {"title": T("Over the app", "Encima de la app"),
         "text": T("Wrap the view with `ui.dialog_layer` to center it over a dimmed backdrop.",
                   "Envuelve la vista con `ui.dialog_layer` para centrarlo sobre un fondo oscurecido."),
         "code": """ui.dialog_layer(main_view(), ui.modal(
    pz.column([ui.input("", on_input, placeholder="Project name"),
               ui.checkbox(True, on_toggle, label="Create a git repository")], spacing=10),
    title="New project", on_close=on_close,
    footer=[ui.button("Cancel", on_close), ui.button("Create", on_create, variant="solid")],
    width=380,
), on_dismiss=on_close)""", "size": (720, 320), "fill": True},
    ],
    related=["dialog-layer", "layer", "confirm"],
)

add(
    slug="popover",
    name=T("Popover", "Popover"),
    category="overlays",
    api=["pyzed.ui.popover"],
    blurb=T("Floating content at a point: context menus, color pickers.", "Contenido flotante en un punto: menús contextuales, selectores de color."),
    desc=T(
        "Shows `content` (a menu, a card…) over `base` at `(x, y)`. Clicking anywhere else calls "
        "`on_dismiss`; with `content=None` only `base` is shown. For a right-click menu, store the "
        "pointer position with `pz.mouse_area(on_move=...)` and open it from `on_right_press`.",
        "Muestra `content` (un menú, una tarjeta…) encima de `base` en `(x, y)`. Al pulsar en otro sitio "
        "se llama a `on_dismiss`; con `content=None` solo se muestra `base`. Para un menú de clic "
        "derecho, guarda la posición del puntero con `pz.mouse_area(on_move=...)` y ábrelo en "
        "`on_right_press`.",
    ),
    when=T(["For context menus, dropdown panels and pickers anchored to a point or a button."],
           ["Para menús contextuales, paneles desplegables y selectores anclados a un punto o a un botón."]),
    preview={"code": """ui.popover(
    main_view(),
    ui.menu([
        ui.MenuItem("Copy", on_copy, icon="copy", keys="ctrl-c"),
        ui.MenuItem("Paste", on_paste, icon="clipboard", keys="ctrl-v"),
        ui.SEPARATOR,
        ui.MenuItem("Delete", on_delete, icon="trash-2", danger=True),
    ], width=220),
    x=180, y=70, on_dismiss=on_close,
)""", "fill": True},
    usage="""class Canvas(pz.App):
    def __init__(self):
        self.pointer, self.menu_at = (0, 0), None

    def view(self):
        base = pz.mouse_area(self.content(), on_move=lambda x, y: setattr(self, "pointer", (x, y)),
                             on_right_press=lambda: setattr(self, "menu_at", self.pointer))
        menu = ui.menu([ui.MenuItem("Copy", self.copy), ui.MenuItem("Paste", self.paste)])
        x, y = self.menu_at or (0, 0)
        return ui.popover(base, menu if self.menu_at else None, x=x, y=y,
                          on_dismiss=lambda: setattr(self, "menu_at", None))""",
    related=["menu", "layer", "split-button"],
)

add(
    slug="command-palette",
    name=T("Command palette", "Paleta de comandos"),
    category="overlays",
    api=["pyzed.ui.command_palette", "pyzed.ui.PaletteItem"],
    blurb=T("A command palette with fuzzy search and shortcuts.", "Una paleta de comandos con búsqueda difusa y atajos."),
    desc=T(
        "A command palette: it fuzzy-filters `commands` (`ui.PaletteItem(label, on_press, keys=)`) "
        "by `query`, highlights the matched letters and shows each shortcut. You own the query and the "
        "`selected` index; Enter calls `on_submit`.",
        "Una paleta de comandos: filtra `commands` (`ui.PaletteItem(label, on_press, keys=)`) "
        "por `query` con búsqueda difusa, resalta las letras encontradas y muestra cada atajo. La "
        "consulta y el índice `selected` son tuyos; Enter llama a `on_submit`.",
    ),
    when=T(["To make every action reachable from the keyboard (usually with Ctrl+Shift+P)."],
           ["Para que todas las acciones se puedan usar con el teclado (normalmente con Ctrl+Shift+P)."]),
    preview={"code": """ui.command_palette("tog", on_query, [
    ui.PaletteItem("editor: toggle soft wrap", on_wrap, keys="alt-z"),
    ui.PaletteItem("theme selector: toggle", on_theme, keys="ctrl-k ctrl-t"),
    ui.PaletteItem("workspace: toggle left dock", on_left, keys="ctrl-b"),
    ui.PaletteItem("terminal panel: toggle", on_terminal, keys="ctrl-j"),
], selected=0, width=520)"""},
    usage="""class App(pz.App):
    def __init__(self):
        self.open, self.query, self.selected = False, "", 0

    def commands(self):
        return [ui.PaletteItem("editor: toggle soft wrap", self.toggle_wrap, keys="alt-z"),
                ui.PaletteItem("workspace: toggle left dock", self.toggle_left, keys="ctrl-b")]

    def on_key(self, combo):
        if combo == "ctrl-shift-p":
            self.open, self.query, self.selected = True, "", 0
            return pz.Command.focus("command-palette")
        if self.open and combo in ("up", "down"):
            self.selected += 1 if combo == "down" else -1
        elif combo == "escape":
            self.open = False

    def run_selected(self):
        matches = ui.fuzzy_filter(self.query, self.commands(), key=lambda c: c.label)
        if matches:
            self.open = False
            return matches[self.selected % len(matches)][0].on_press()

    def view(self):
        palette = ui.command_palette(self.query, lambda q: setattr(self, "query", q), self.commands(),
                                     selected=self.selected, on_submit=self.run_selected)
        return ui.layer(self.main_view(), palette if self.open else None,
                        on_dismiss=lambda: setattr(self, "open", False))""",
    related=["picker", "layer", "kbd"],
)

add(
    slug="picker",
    name=T("Picker", "Buscador"),
    category="overlays",
    api=["pyzed.ui.picker", "pyzed.ui.fuzzy_filter", "pyzed.ui.fuzzy_match", "pyzed.ui.highlighted"],
    blurb=T("A searchable list on a floating surface, with fuzzy matching.", "Una lista con búsqueda en una superficie flotante, con coincidencia difusa."),
    desc=T(
        "A search box over a list of results on a floating surface: the basis of the command palette "
        "and the file finder. `ui.fuzzy_filter(query, items, key=)` ranks items (best match first) and returns "
        "`[(item, positions), ...]`; pass those pairs to `picker` to highlight the matches. "
        "`ui.fuzzy_match` scores one string and `ui.highlighted` draws one with its matches.",
        "Un buscador sobre una lista de resultados en una superficie flotante: la base de la paleta de "
        "comandos y del buscador de archivos. `ui.fuzzy_filter(query, items, key=)` ordena los elementos "
        "(el mejor primero) y devuelve `[(item, positions), ...]`; pasa esos pares a `picker` para resaltar las "
        "coincidencias. `ui.fuzzy_match` puntúa una cadena y `ui.highlighted` dibuja una con sus coincidencias.",
    ),
    when=T(["For your own finders: files, symbols, branches, projects, emoji."],
           ["Para tus propios buscadores: archivos, símbolos, ramas, proyectos, emoji."]),
    preview={"code": """files = ["src/app.rs", "src/render.rs", "python/pyzed/app.py", "python/pyzed/theme.py", "README.md"]
items = ui.fuzzy_filter("app", [ui.PaletteItem(f, on_open, icon="file-code") for f in files],
                        key=lambda item: item.label)
ui.picker("app", on_query, items, selected=0, placeholder="Search files…", width=480)"""},
    usage="""class Finder(pz.App):
    def __init__(self):
        self.query, self.selected = "", 0
        self.files = ["src/app.rs", "src/render.rs", "README.md"]

    def view(self):
        matches = ui.fuzzy_filter(self.query, self.files)
        items = [(ui.PaletteItem(f, lambda f=f: self.open(f), icon="file"), positions)
                 for f, positions in matches[:50]]
        return ui.picker(self.query, lambda q: setattr(self, "query", q), items,
                         selected=self.selected, placeholder="Search files…")""",
    examples=[
        {"title": T("Highlighting matches", "Resaltar coincidencias"),
         "text": T("`fuzzy_match` returns `(score, positions)` or `None`; `highlighted` paints those positions.",
                   "`fuzzy_match` devuelve `(score, positions)` o `None`; `highlighted` pinta esas posiciones."),
         "code": """t = pz.theme.current()
score, positions = ui.fuzzy_match("tgsw", "editor: toggle soft wrap")
ui.highlighted("editor: toggle soft wrap", positions, color=t.text, match_color=t.accent, size=16)""",
         "size": (720, 120)},
    ],
    related=["command-palette", "search-input", "layer"],
)

# ---------------------------------------------------------------------------------------- dialogs

add(
    slug="dialog-layer",
    name=T("Dialog layer", "Capa de diálogo"),
    category="dialogs",
    api=["pyzed.ui.dialog_layer"],
    badge="new",
    blurb=T("Centers a dialog over your view with a dimmed backdrop.", "Centra un diálogo encima de tu vista con el fondo oscurecido."),
    desc=T(
        "Shows a dialog centered over `base` with a dimmed backdrop; clicking the backdrop calls "
        "`on_dismiss`. With `dialog=None` it returns `base` unchanged, so keep which dialog is open in "
        "your state and always wrap the view with it.",
        "Muestra un diálogo centrado encima de `base` con el fondo oscurecido; al pulsar el fondo se "
        "llama a `on_dismiss`. Con `dialog=None` devuelve `base` sin cambios, así que guarda en tu estado "
        "qué diálogo está abierto y envuelve siempre la vista con ella.",
    ),
    when=T(["Around your whole view, to show any of the dialogs on this page or a `ui.modal`."],
           ["Alrededor de toda tu vista, para mostrar cualquiera de estos diálogos o un `ui.modal`."]),
    preview={"code": """ui.dialog_layer(
    main_view(),
    ui.confirm("Delete notes.py? This can't be undone.", on_delete, on_cancel,
               title="Delete file", danger=True, width=340),
    on_dismiss=on_cancel,
)""", "fill": True},
    usage="""class Files(pz.App):
    def __init__(self):
        self.asking = False

    def close(self):
        self.asking = False

    def view(self):
        dialog = None
        if self.asking:
            dialog = ui.confirm("Delete main.py?", self.delete, self.close, title="Delete file", danger=True)
        return ui.dialog_layer(self.main_view(), dialog, on_dismiss=self.close)""",
    notes=T("Button labels (OK, Cancel, Save…) are translated with [`pyzed.i18n`](/pyzed/guides/i18n/).",
            "Las etiquetas de los botones (Aceptar, Cancelar, Guardar…) se traducen con [`pyzed.i18n`](/pyzed/guides/i18n/)."),
    related=["alert", "confirm", "prompt", "modal"],
)

add(
    slug="alert",
    name=T("Alert", "Alerta"),
    category="dialogs",
    api=["pyzed.ui.alert"],
    badge="new",
    blurb=T("A message with one button.", "Un mensaje con un botón."),
    desc=T("A message with a single OK button. `kind` (`\"info\"`, `\"success\"`, `\"warning\"`, `\"error\"`) adds an icon.",
           "Un mensaje con un solo botón de Aceptar. `kind` (`\"info\"`, `\"success\"`, `\"warning\"`, `\"error\"`) añade un icono."),
    when=T(["To report something the user must acknowledge (an export finished, a file could not be opened)."],
           ["Para avisar de algo que hay que confirmar (una exportación terminó, un archivo no se pudo abrir)."]),
    preview={"code": """ui.dialog_layer(main_view(), ui.alert("The export finished: 128 files were written.", on_close,
                                      title="Export", kind="success", width=360))""", "fill": True},
    related=["confirm", "dialog-layer", "toast"],
)

add(
    slug="confirm",
    name=T("Confirm", "Confirmación"),
    category="dialogs",
    api=["pyzed.ui.confirm"],
    badge="new",
    blurb=T("A yes/no question, red for destructive actions.", "Una pregunta de sí o no, en rojo para acciones destructivas."),
    desc=T("Asks a yes/no question. `danger=True` paints the confirm button red; `confirm_label` and `cancel_label` rename the buttons.",
           "Hace una pregunta de sí o no. `danger=True` pinta de rojo el botón de confirmar; `confirm_label` y `cancel_label` cambian el texto de los botones."),
    when=T(["Before destructive or irreversible actions: delete, overwrite, discard."],
           ["Antes de acciones destructivas o irreversibles: borrar, sobrescribir, descartar."]),
    preview={"code": """ui.dialog_layer(main_view(), ui.confirm(
    "Delete notes.py? This can't be undone.", on_delete, on_cancel,
    title="Delete file", danger=True, confirm_label="Delete", width=360,
))""", "fill": True},
    related=["alert", "choice", "unsaved-changes"],
)

add(
    slug="prompt",
    name=T("Prompt", "Pregunta"),
    category="dialogs",
    api=["pyzed.ui.prompt"],
    badge="new",
    blurb=T("Asks for a line of text.", "Pide una línea de texto."),
    desc=T("Asks for a line of text: a controlled input plus Cancel and OK. Enter or the button calls `on_submit`.",
           "Pide una línea de texto: un campo controlado más Cancelar y Aceptar. Enter o el botón llaman a `on_submit`."),
    when=T(["For quick names: rename a file, name a new branch, save a view."],
           ["Para nombres rápidos: renombrar un archivo, nombrar una rama, guardar una vista."]),
    preview={"code": """ui.dialog_layer(main_view(), ui.prompt(
    "Rename", "notes.py", on_input, on_submit, on_cancel,
    message="New name for the file:", width=360,
))""", "fill": True},
    usage="""class Files(pz.App):
    def __init__(self):
        self.new_name = None

    def view(self):
        dialog = None
        if self.new_name is not None:
            dialog = ui.prompt("Rename", self.new_name, lambda t: setattr(self, "new_name", t),
                               self.rename, lambda: setattr(self, "new_name", None))
        return ui.dialog_layer(self.main_view(), dialog)""",
    related=["confirm", "input", "dialog-layer"],
)

add(
    slug="choice",
    name=T("Choice", "Elección"),
    category="dialogs",
    api=["pyzed.ui.choice"],
    badge="new",
    blurb=T("A message with your own buttons.", "Un mensaje con tus propios botones."),
    desc=T("A message with your own buttons: `options` are `(label, on_press)` pairs and the last one is the main one.",
           "Un mensaje con tus propios botones: `options` son pares `(etiqueta, on_press)` y el último es el principal."),
    when=T(["When a question has more than two answers (Keep both / Replace / Skip)."],
           ["Cuando una pregunta tiene más de dos respuestas (Conservar ambos / Reemplazar / Omitir)."]),
    preview={"code": """ui.dialog_layer(main_view(), ui.choice(
    "notes.py already exists in this folder.",
    [("Keep both", on_keep), ("Skip", on_skip), ("Replace", on_replace)],
    on_cancel, title="File exists", width=420,
))""", "fill": True},
    related=["confirm", "unsaved-changes"],
)

add(
    slug="unsaved-changes",
    name=T("Unsaved changes", "Cambios sin guardar"),
    category="dialogs",
    api=["pyzed.ui.unsaved_changes"],
    badge="new",
    blurb=T("“Save your changes before closing?”", "“¿Guardar los cambios antes de cerrar?”"),
    desc=T("“Save your changes to *name* before closing?” with Don't save, Cancel and Save.",
           "“¿Guardar los cambios de *nombre* antes de cerrar?” con No guardar, Cancelar y Guardar."),
    when=T(["When closing a tab or a window with unsaved edits."],
           ["Al cerrar una pestaña o una ventana con cambios sin guardar."]),
    preview={"code": """ui.dialog_layer(main_view(), ui.unsaved_changes("notes.py", on_save, on_discard, on_cancel))""",
             "fill": True},
    related=["confirm", "choice", "tab-bar"],
)

# -------------------------------------------------------------------------------------- workspace

add(
    slug="workspace",
    name=T("Workspace", "Espacio de trabajo"),
    category="workspace",
    api=["pyzed.ui.workspace"],
    blurb=T("The layout of an editor-style window: title bar, docks, center, status bar.",
            "La disposición de una ventana estilo editor: barra de título, docks, centro y barra de estado."),
    desc=T(
        "Builds the frame of an editor-style window: the title bar on top, docks on the left, right and bottom, "
        "the center and the status bar. Pass `None` to hide a dock (that is how Ctrl+B works); "
        "`left_width`, `right_width` and `bottom_height` set their size and `on_resize` reports drags.",
        "Construye el marco de una ventana estilo editor: la barra de título arriba, docks a la izquierda, a la "
        "derecha y abajo, el centro y la barra de estado. Pasa `None` para ocultar un dock (así funciona "
        "Ctrl+B); `left_width`, `right_width` y `bottom_height` fijan su tamaño y `on_resize` avisa al arrastrar.",
    ),
    when=T(["As the root of editor-like apps: IDEs, note apps, database clients, file managers."],
           ["Como raíz de apps tipo editor: IDEs, apps de notas, clientes de bases de datos, gestores de archivos."]),
    preview={"code": """files = ui.TreeNode.from_paths(["src/main.py", "src/ui.py", "README.md"], status={"src/ui.py": "modified"})
ui.workspace(
    pz.column([
        ui.tab_bar([ui.Tab.for_file("src/main.py")], "src/main.py", on_close=on_close),
        ui.editor("ws-main", "import pyzed as pz\\n\\n\\ndef main():\\n    pz.run(App)\\n", path="main.py"),
    ]),
    title_bar=ui.title_bar([ui.title_button("pyzed", chevron=True),
                            ui.title_button("main", icon="git-branch", muted=True)],
                           [ui.icon_button("bell", on_bell, size="sm"), ui.avatar("KV")]),
    left=pz.column([ui.panel_header("Project", [ui.icon_button("plus", on_new, size="xs")]),
                    ui.tree(files, expanded={"src"}, selected="src/main.py")]),
    bottom=pz.column([ui.panel_header("Terminal", icon="terminal"),
                      ui.terminal("$ python main.py\\n\\x1b[32m✓\\x1b[0m done")]),
    status_bar=ui.status_bar([ui.status_item("0", icon="circle-x"), ui.status_item("1", icon="triangle-alert")],
                             [ui.status_item("Ln 4, Col 8"), ui.status_item("Python")]),
    left_width=200, bottom_height=110,
)""", "size": (880, 440), "fill": True},
    usage="""class Ide(pz.App):
    def __init__(self):
        self.show_left = True

    def on_key(self, combo):
        if combo == "ctrl-b":
            self.show_left = not self.show_left

    def view(self):
        return ui.workspace(
            self.editor_area(),
            title_bar=ui.title_bar([ui.title_button("my-project", chevron=True)]),
            left=self.project_panel() if self.show_left else None,
            status_bar=ui.status_bar([], [ui.status_item("Python")]),
        )""",
    related=["title-bar", "status-bar", "panel", "split"],
)

add(
    slug="title-bar",
    name=T("Title bar", "Barra de título"),
    category="workspace",
    api=["pyzed.ui.title_bar", "pyzed.ui.title_button"],
    blurb=T("The top bar with project and branch pickers.", "La barra superior con los selectores de proyecto y rama."),
    desc=T(
        "The top bar of the window: widgets at the `start` (project and branch pickers), an optional "
        "`center` and widgets at the `end` (account, notifications). `ui.title_button` is the compact "
        "button it uses (`pyzed ▾`, `main`), with `chevron` and `muted` styles.",
        "La barra superior de la ventana: widgets al principio (`start`, selectores de proyecto y rama), "
        "un `center` opcional y widgets al final (`end`, cuenta, notificaciones). `ui.title_button` es "
        "el botón compacto que usa (`pyzed ▾`, `main`), con estilos `chevron` y `muted`.",
    ),
    when=T(["At the top of a `ui.workspace`, or of any window with `decorations=False`."],
           ["Arriba de un `ui.workspace`, o de cualquier ventana con `decorations=False`."]),
    preview={"code": """ui.title_bar(
    [ui.title_button("pyzed", on_projects, chevron=True),
     ui.title_button("main", on_branches, icon="git-branch", muted=True)],
    [ui.facepile(["Ana", "Luis"]), ui.icon_button("bell", on_bell, size="sm"), ui.avatar("KV")],
    center=ui.muted("notes.py"),
)""", "size": (720, 120)},
    related=["workspace", "status-bar", "facepile", "window-frame"],
)

add(
    slug="window-frame",
    name=T("Window frame", "Marco de ventana"),
    category="workspace",
    api=["pyzed.ui.window_frame", "pyzed.ui.Menu", "pyzed.ui.window_title_bar", "pyzed.ui.window_controls",
         "pyzed.ui.system_platform"],
    blurb=T("Your own title bar, window buttons and menus.",
            "Tu propia barra de título, botones de ventana y menús."),
    desc=T(
        "Draws the whole frame of a window opened without system decorations (`frame = \"custom\"`): a "
        "title bar that moves the window (double click maximizes), the minimize, maximize and close "
        "buttons in the style of a platform, menus on the left (`ui.Menu`) and borders that "
        "resize the window. `ui.window_title_bar` is the bar alone, `ui.window_controls` the three buttons "
        "and `ui.system_platform()` says which style this system uses.",
        "Dibuja el marco completo de una ventana abierta sin decoraciones del sistema (`frame = \"custom\"`): "
        "una barra de título que mueve la ventana (doble clic la maximiza), los botones de minimizar, "
        "maximizar y cerrar con el estilo de una plataforma, menús a la izquierda (`ui.Menu`) "
        "y bordes que cambian el tamaño de la ventana. `ui.window_title_bar` es la barra sola, "
        "`ui.window_controls` los tres botones y `ui.system_platform()` dice qué estilo usa este sistema.",
    ),
    when=T(["For apps that want a modern editor-like window: menus and pickers in the title bar instead of the system's frame. "
            "See [Window frames](/pyzed/guides/windows/#window-frames-your-own-title-bar).",
            "With no callbacks, `ui.window_title_bar` and `ui.window_controls` only show: use them to preview "
            "a window in the frame of each platform."],
           ["Para apps que quieren una ventana como la de un editor moderno: menús y selectores en la barra de título en lugar "
            "del marco del sistema. Mira [Marcos de ventana](/pyzed/guides/windows/#marcos-de-ventana-tu-propia-barra-de-título).",
            "Sin callbacks, `ui.window_title_bar` y `ui.window_controls` solo se muestran: úsalos para previsualizar "
            "una ventana con el marco de cada plataforma."]),
    preview={"code": """ui.window_frame(
    ui.editor("frame-main", "import pyzed as pz\\n\\npz.run(App)\\n", path="main.py"),
    title="notes.py",
    menus=[ui.Menu("File", [ui.MenuItem("Open…", on_open, keys="ctrl-o")]),
           ui.Menu("Edit", [ui.MenuItem("Undo", on_undo, keys="ctrl-z")])],
    start=[ui.title_button("pyzed", on_projects, chevron=True)],
    style="windows",
)""", "size": (720, 240), "fill": True},
    usage="""class Notes(pz.App):
    title = "Notes"
    frame = "custom"  # or "macos", "windows", "gnome", "ubuntu", "kde"

    def view(self):
        return ui.window_frame(
            self.editor(),
            menus=[ui.Menu("File", [ui.MenuItem("Open…", self.open, keys="ctrl-o"), ui.SEPARATOR,
                                    ui.MenuItem("Quit", self.close)])],
            start=[ui.title_button("pyzed", chevron=True)],
            end=[ui.button("Run", self.run, icon="play", size="sm")],
        )""",
    notes=T(
        "With only menus, define `frame_menus()` on the window and skip `ui.window_frame`: the runtime "
        "frames the view for you. `style` defaults to the window's `frame`, or this system's style.",
        "Si solo necesitas menús, define `frame_menus()` en la ventana y no llames a `ui.window_frame`: el "
        "entorno de ejecución enmarca la vista por ti. `style` toma por defecto el `frame` de la ventana, "
        "o el estilo de este sistema.",
    ),
    related=["title-bar", "workspace", "menu"],
    badge="new",
)

add(
    slug="status-bar",
    name=T("Status bar", "Barra de estado"),
    category="workspace",
    api=["pyzed.ui.status_bar", "pyzed.ui.status_item"],
    blurb=T("The bottom bar: diagnostics, cursor position, language.", "La barra inferior: diagnósticos, posición del cursor, lenguaje."),
    desc=T(
        "The bottom bar with items at the `start` and `end`. `ui.status_item` shows an icon and/or "
        "text, can be pressed, `selected` (a dock that is open) and carry a `tooltip` with `keys`.",
        "La barra inferior con elementos al principio (`start`) y al final (`end`). `ui.status_item` "
        "muestra un icono y/o texto, se puede pulsar, marcar como `selected` (un dock abierto) y llevar "
        "un `tooltip` con `keys`.",
    ),
    when=T(["For always-visible state: errors and warnings, cursor position, language, git branch."],
           ["Para el estado siempre visible: errores y avisos, posición del cursor, lenguaje, rama de git."]),
    preview={"code": """ui.status_bar(
    [ui.status_item(icon="panel-left", on_press=on_toggle, selected=True, tooltip="Project panel", keys="ctrl-b"),
     ui.status_item("0", icon="circle-x"), ui.status_item("2", icon="triangle-alert", icon_color="warning")],
    [ui.status_item("Ln 12, Col 8"), ui.status_item("UTF-8"), ui.status_item("Python", icon="file-code")],
)""", "size": (720, 120)},
    related=["workspace", "title-bar", "count-badge"],
)

add(
    slug="panel",
    name=T("Panel", "Panel"),
    category="workspace",
    api=["pyzed.ui.panel"],
    blurb=T("A dockable, resizable side panel.", "Un panel lateral acoplable y redimensionable."),
    desc=T(
        "A dockable panel with an optional header. `side` decides which edge gets the border line; with "
        "a numeric `width` (`height` for the bottom) that edge can be dragged to resize it, and "
        "`on_resize` reports the new size.",
        "Un panel acoplable con una cabecera opcional. `side` decide qué borde lleva la línea; con un "
        "`width` numérico (`height` para el de abajo) ese borde se puede arrastrar para cambiar el "
        "tamaño, y `on_resize` informa del nuevo tamaño.",
    ),
    when=T(["When you build your own layout instead of `ui.workspace`: sidebars, inspectors, outlines."],
           ["Cuando montas tu propia disposición en lugar de `ui.workspace`: barras laterales, inspectores, esquemas."]),
    preview={"code": """pz.row([
    ui.panel(
        pz.column([ui.list_item("Inbox", on_open, icon="inbox", selected=True, inset=True),
                   ui.list_item("Archive", on_open, icon="archive", inset=True)]),
        header=ui.panel_header("Mail", [ui.icon_button("plus", on_new, size="xs")], icon="mail"),
        width=220, side="left",
    ),
    pz.container(ui.muted("Content"), center=True, width="fill", height="fill"),
], height="fill")""", "fill": True},
    related=["panel-header", "workspace", "split"],
)

add(
    slug="panel-header",
    name=T("Panel header", "Cabecera de panel"),
    category="workspace",
    api=["pyzed.ui.panel_header"],
    blurb=T("Icon, title and actions on top of a dock.", "Icono, título y acciones encima de un dock."),
    desc=T("The header of a dock or panel: an optional icon, the title and action buttons on the right.",
           "La cabecera de un dock o panel: un icono opcional, el título y botones de acción a la derecha."),
    when=T(["At the top of every dock (Project, Outline, Terminal) to name it and hold its actions."],
           ["Arriba de cada dock (Proyecto, Esquema, Terminal) para nombrarlo y poner sus acciones."]),
    preview={"code": """pz.column([
    ui.panel_header("Project", [ui.icon_button("plus", on_new, size="xs"),
                                ui.icon_button("ellipsis", on_menu, size="xs")]),
    ui.panel_header("Terminal", [ui.icon_button("x", on_close, size="xs")], icon="terminal"),
], spacing=12, width=320)"""},
    related=["panel", "list-header"],
)

add(
    slug="split",
    name=T("Split", "División"),
    category="workspace",
    api=["pyzed.ui.split", "pyzed.split"],
    blurb=T("Two panes with a draggable divider.", "Dos paneles con un divisor que se arrastra."),
    desc=T(
        "Separates two widgets with a draggable divider in the theme's border color (accent while "
        "dragging). The `ratio` is yours: store it in `on_resize(ratio)`. `vertical=True` stacks the "
        "panes. `pz.split` is the base version with configurable `color`, `hover_color`, `thickness` "
        "and `handle`.",
        "Separa dos widgets con un divisor que se arrastra, en el color de borde del tema (acento "
        "mientras se arrastra). El `ratio` es tuyo: guárdalo en `on_resize(ratio)`. `vertical=True` "
        "apila los paneles. `pz.split` es la versión base con `color`, `hover_color`, `thickness` y "
        "`handle` configurables.",
    ),
    when=T(["For side-by-side editors, a preview next to its source, or an editor above a terminal.",
            "For one resizable side panel, [Resizable](/pyzed/library/resizable/) is simpler."],
           ["Para editores lado a lado, una vista previa junto a su código o un editor encima de una terminal.",
            "Para un solo panel lateral redimensionable, [Redimensionable](/pyzed/es/library/resizable/) es más simple."]),
    preview={"code": """t = pz.theme.current()
pane = lambda title, bg: pz.container(ui.label(title), padding=12, width="fill", height="fill", bg=bg)
ui.split(pane("Left", t.panel),
         ui.split(pane("Top", t.editor), pane("Bottom", t.background), vertical=True),
         ratio=0.4, on_resize=on_resize)""", "fill": True},
    usage="""class Panes(pz.App):
    def __init__(self):
        self.ratio = 0.3

    def view(self):
        return ui.split(self.sidebar(), self.editor(), ratio=self.ratio,
                        on_resize=lambda r: setattr(self, "ratio", r))""",
    related=["resizable", "panel", "workspace"],
)

# ------------------------------------------------------------------------------------------- code

add(
    slug="editor",
    name=T("Editor", "Editor"),
    category="code",
    api=["pyzed.ui.editor", "pyzed.ui.language_token", "pyzed.code_editor"],
    blurb=T("A full code editor: highlighting, folding, minimap, git markers.",
            "Un editor de código completo: resaltado, plegado, minimapa, marcas de git."),
    desc=T(
        "A code editor with syntax highlighting in the theme colors (100+ languages), line numbers, git "
        "markers, auto-closing pairs, folding, a minimap and font zoom. It is **uncontrolled**: the text, "
        "cursor and undo history live in Rust, tied to `id`, and `text` is only the initial value. "
        "`on_change` receives the full text and `on_cursor` the `(line, column)`. `pz.code_editor` is the "
        "base widget without the theme.",
        "Un editor de código con resaltado de sintaxis en los colores del tema (más de 100 lenguajes), "
        "números de línea, marcas de git, cierre automático de pares, plegado, minimapa y zoom de fuente. "
        "Es **no controlado**: el texto, el cursor y el historial viven en Rust, ligados al `id`, y `text` "
        "solo es el valor inicial. `on_change` recibe el texto completo y `on_cursor` la `(línea, columna)`. "
        "`pz.code_editor` es el widget base sin tema.",
    ),
    when=T(
        ["For code, configuration files, logs you can edit, or any long text.",
         "Use the file path as `id`: each file keeps its cursor and history when you switch tabs.",
         "To replace the text from code, return `pz.Command.set_editor_text(id, text)`."],
        ["Para código, archivos de configuración, registros editables o cualquier texto largo.",
         "Usa la ruta del archivo como `id`: cada archivo conserva su cursor e historial al cambiar de pestaña.",
         "Para reemplazar el texto desde código, devuelve `pz.Command.set_editor_text(id, text)`."],
    ),
    preview={"code": """code = '''import pyzed as pz
from pyzed import ui


class Counter(pz.App):
    def __init__(self):
        self.count = 0

    def view(self):
        return ui.button(f"Clicks: {self.count}", self.increment)
'''
pz.container(ui.editor("counter.py", code, path="counter.py", markers={7: "modified", 10: "created"}),
             width=620, height=290)""", "size": (720, 360)},
    usage="""from pathlib import Path

class Editor(pz.App):
    def __init__(self):
        self.path = "main.py"
        self.text = Path(self.path).read_text()

    def save(self):
        Path(self.path).write_text(self.text)

    def view(self):
        return ui.editor(self.path, self.text, path=self.path,
                         on_change=lambda text: setattr(self, "text", text))""",
    examples=[
        {"title": T("Folding, code lens and minimap", "Plegado, code lens y minimapa"),
         "text": T("Blocks fold by indentation (Ctrl+Shift+[ and ]), `annotations` adds a code lens above a "
                   "line and `minimap=True` draws the overview on the right.",
                   "Los bloques se pliegan por indentación (Ctrl+Shift+[ y ]), `annotations` añade un code "
                   "lens encima de una línea y `minimap=True` dibuja la vista general a la derecha."),
         "code": """code = '''import pyzed as pz
from pyzed import ui


class Counter(pz.App):
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1

    def view(self):
        return ui.button(f"Clicks: {self.count}", self.increment)
'''
pz.container(ui.editor("lens.py", code, path="counter.py", minimap=True, annotations={5: "1 reference"}),
             width=680, height=290)""", "size": (720, 340),
         "start": "pz.Command.batch([pz.Command.fold_line('lens.py', n) for n in (6, 9)])"},
        {"title": T("Cursor and whitespace", "Cursor y espacios"),
         "text": T("`cursor_shape` is `\"bar\"`, `\"block\"`, `\"underline\"` or `\"hollow\"`; "
                   "`show_whitespace=True` draws spaces and tabs; `wrap=True` wraps long lines.",
                   "`cursor_shape` es `\"bar\"`, `\"block\"`, `\"underline\"` o `\"hollow\"`; "
                   "`show_whitespace=True` dibuja espacios y tabuladores; `wrap=True` parte las líneas largas."),
         "code": """pz.container(ui.editor("ws.py", "def greet(name):\\n    return f'Hello, {name}'\\n",
                       path="ws.py", cursor_shape="block", show_whitespace=True, font_size=15),
             width=620, height=120)""", "size": (720, 170)},
    ],
    related=["terminal", "console", "workspace"],
)

add(
    slug="terminal",
    name=T("Terminal", "Terminal"),
    category="code",
    api=["pyzed.ui.terminal", "pyzed.ui.ansi"],
    blurb=T("A read-only terminal view with ANSI colors.", "Una vista de terminal de solo lectura con colores ANSI."),
    desc=T(
        "A read-only view that understands ANSI colors and stays scrolled to the end. Feed it the output "
        "of a process you run (for example with `subprocess` in a thread and `pz.post`). It also accepts "
        "lines of `(text, color)` segments; `ui.ansi(text)` converts ANSI text into those segments.",
        "Una vista de solo lectura que entiende los colores ANSI y se queda al final. Pásale la salida de "
        "un proceso que ejecutes (por ejemplo con `subprocess` en un hilo y `pz.post`). También acepta "
        "líneas de segmentos `(texto, color)`; `ui.ansi(text)` convierte texto ANSI en esos segmentos.",
    ),
    when=T(["To show build output, test runs, server logs or any command's output."],
           ["Para mostrar la salida de una compilación, tests, registros de un servidor o cualquier comando."]),
    preview={"code": """out = ("$ pytest -q\\n\\x1b[32m........................\\x1b[0m\\n\\x1b[32m24 passed\\x1b[0m in 1.21s\\n"
       "$ maturin develop --release\\n\\x1b[2m   Compiling pyzed v0.4.0\\x1b[0m\\n"
       "\\x1b[32m✓\\x1b[0m Installed pyzed-0.4.0\\n$ ")
pz.container(ui.terminal(out), width=560, height=190)"""},
    related=["console", "editor"],
)

add(
    slug="console",
    name=T("Console", "Consola"),
    category="code",
    api=["pyzed.ui.console", "pyzed.ui.Log", "pyzed.ui.LogEntry", "pyzed.ui.LogSelection", "pyzed.ui.LOG_LEVELS"],
    blurb=T("A dev-tools style log with levels, filter, copy and clear.", "Un registro estilo dev tools con niveles, filtro, copiar y limpiar."),
    desc=T(
        "`ui.Log` collects entries (thread-safe, capped at `limit`, repeated lines folded) and can "
        "capture `print` and tracebacks. `ui.console` shows them like a browser's dev tools console: a "
        "filter box, one toggle per level with its count, copy and clear. Levels are `debug`, `info`, "
        "`event`, `stdout`, `stderr`, `warning` and `error` (`ui.LOG_LEVELS`). With a `ui.LogSelection` "
        "the lines can be selected (click, Shift+click, Ctrl+click) and a selected line shows its "
        "`detail` (a traceback); `on_context` opens your menu on right click, and `sources` adds a "
        "dropdown to show the lines of one source.",
        "`ui.Log` reúne entradas (seguro entre hilos, con un tope de `limit`, líneas repetidas agrupadas) "
        "y puede capturar `print` y las trazas de error. `ui.console` las muestra como la consola de las "
        "dev tools de un navegador: un filtro, un interruptor por nivel con su cuenta, copiar y limpiar. "
        "Los niveles son `debug`, `info`, `event`, `stdout`, `stderr`, `warning` y `error` "
        "(`ui.LOG_LEVELS`). Con un `ui.LogSelection` las líneas se pueden seleccionar (clic, Shift+clic, "
        "Ctrl+clic) y una línea seleccionada muestra su `detail` (un traceback); `on_context` abre tu menú "
        "con el clic derecho y `sources` añade un desplegable para ver las líneas de un origen.",
    ),
    when=T(["For a debug panel in your app, or to show what a background job is doing."],
           ["Para un panel de depuración en tu app, o para mostrar lo que hace una tarea en segundo plano."]),
    preview={"code": """log = ui.Log()
log.write("info", "Loaded ui/main.pzform")
log.write("event", "button1.click")
log.write("stdout", "Saving 3 files…")
log.write("warning", "settings.json not found, using defaults")
log.write("error", "ValueError: invalid literal for int()")
pz.container(ui.console(log.entries, on_clear=on_clear, on_copy=on_copy, on_query=on_query),
             width=600, height=220)"""},
    usage="""class Debug(pz.App):
    def __init__(self):
        self.log = ui.Log(on_write=lambda: pz.post("log"))  # redraw when a line arrives
        self.log.capture()                                   # also collect print() and stderr
        self.query, self.hidden = "", set()

    def view(self):
        return ui.console(self.log.entries, query=self.query,
                          on_query=lambda q: setattr(self, "query", q),
                          hidden=self.hidden, on_toggle_level=lambda lvl: self.hidden.symmetric_difference_update({lvl}),
                          on_clear=self.log.clear, on_copy=lambda: pz.Command.copy(self.log.text()))""",
    related=["terminal", "editor"],
)

add(
    slug="markdown",
    name=T("Markdown", "Markdown"),
    category="code",
    api=["pyzed.ui.markdown", "pyzed.markdown"],
    blurb=T("Renders Markdown with the theme's colors.", "Muestra Markdown con los colores del tema."),
    desc=T(
        "Renders Markdown (headings, lists, code blocks, quotes, tables, links) with the theme's text, "
        "link and code colors. `on_link(url)` receives clicked links. `pz.markdown` is the base widget "
        "with explicit colors.",
        "Muestra Markdown (títulos, listas, bloques de código, citas, tablas, enlaces) con los colores de "
        "texto, enlace y código del tema. `on_link(url)` recibe los enlaces pulsados. `pz.markdown` es "
        "el widget base con colores explícitos.",
    ),
    when=T(["For READMEs, release notes, help pages and chat messages."],
           ["Para READMEs, notas de versión, páginas de ayuda y mensajes de chat."]),
    preview={"code": """ui.markdown('''## Release notes

Pyzed **0.4** adds the *component designer*, `pyzed build` and [styles](https://iced.rs).

- Track grids and flex
- Ready-made dialogs
''', width=460, on_link=on_link)"""},
    related=["rich-text", "text"],
)

add(
    slug="shortcuts",
    name=T("Shortcuts", "Atajos"),
    category="code",
    api=["pyzed.ui.shortcuts"],
    blurb=T("A searchable list of key bindings, grouped.", "Una lista de atajos agrupada y con búsqueda."),
    desc=T("A searchable, grouped list of key bindings for a Keyboard shortcuts dialog. `groups` are `(title, [(action, keys), ...])` pairs.",
           "Una lista de atajos agrupada y con búsqueda para un diálogo de Atajos de teclado. `groups` son pares `(título, [(acción, teclas), ...])`."),
    when=T(["Inside a `ui.modal` opened from a Help menu or with Ctrl+K Ctrl+S."],
           ["Dentro de un `ui.modal` que se abre desde el menú Ayuda o con Ctrl+K Ctrl+S."]),
    preview={"code": """pz.container(ui.shortcuts([
    ("File", [("Save", "ctrl-s"), ("Open file", "ctrl-p")]),
    ("View", [("Command palette", "ctrl-shift-p"), ("Toggle left dock", "ctrl-b")]),
], on_query=on_query, height=240), width=420)"""},
    related=["kbd", "keybinding-hint", "about"],
)

add(
    slug="about",
    name=T("About", "Acerca de"),
    category="code",
    api=["pyzed.ui.about"],
    blurb=T("An About box with icon, version, details and links.", "Una caja Acerca de con icono, versión, detalles y enlaces."),
    desc=T("An About box: an icon, the app name and version, a description, a few `(label, value)` details and link buttons.",
           "Una caja Acerca de: un icono, el nombre y la versión de la app, una descripción, algunos detalles `(etiqueta, valor)` y botones de enlace."),
    when=T(["In a `ui.modal` opened from the Help menu."], ["En un `ui.modal` que se abre desde el menú Ayuda."]),
    preview={"code": """ui.about("Notes", "1.2.0", "A small notes app built with Pyzed.", icon="notebook-pen",
         details=[("Python", "3.12"), ("Pyzed", "0.4")],
         links=[("Website", on_website), ("GitHub", on_github)])"""},
    related=["modal", "shortcuts"],
)

add(
    slug="reference-browser",
    name=T("Reference browser", "Visor de referencia"),
    category="code",
    api=["pyzed.ui.reference_browser"],
    blurb=T("Built-in, searchable docs like Godot's: a class list next to the open page.",
            "Documentación integrada con buscador, como la de Godot: una lista de clases junto a la página abierta."),
    desc=T("The built-in reference: a searchable class list (the library, your components and any section you "
           "`reference.register`) next to the page that is open, with back and forward, internal links and an "
           "Open online button. Keep a `pyzed.reference.Browser` in your state; the browser changes it. Links that "
           "leave the reference go to `on_open_url`. See [Built-in reference](/pyzed/editor/reference/).",
           "La referencia integrada: una lista de clases con buscador (la librería, tus componentes y las secciones "
           "que añadas con `reference.register`) junto a la página abierta, con atrás y adelante, enlaces internos y "
           "un botón Abrir en la web. Guarda un `pyzed.reference.Browser` en tu estado; el visor lo cambia. Los "
           "enlaces que salen de la referencia van a `on_open_url`. Ver [Referencia integrada](/pyzed/es/editor/reference/)."),
    when=T(["In a Help tab or window of an app built on Pyzed, so its users can read the API offline.",
            "With your own `reference.Provider` sections, as your app's help."],
           ["En una pestaña o ventana de Ayuda de una app hecha con Pyzed, para leer la API sin conexión.",
            "Con tus propias secciones `reference.Provider`, como la ayuda de tu app."]),
    preview={"code": """from pyzed import reference

help = reference.Browser("pyzed.ui.button")
ui.reference_browser(help, on_open_url=open_in_browser, sidebar_width=230)""", "size": (900, 520), "fill": True},
    related=["shortcuts", "about", "markdown"],
)

# ----------------------------------------------------------------------------------------- layout
# Base widgets of ``pyzed``. ``box`` (a small labeled tile) keeps the snippets short.

_BOX = 'box = lambda text, w=90, h=44: pz.container(ui.label(text), center=True, width=w, height=h, bg=pz.theme.current().element, radius=6)\n'

add(
    slug="row",
    name=T("Row", "Fila"),
    category="layout",
    api=["pyzed.row"],
    blurb=T("Lays out children horizontally.", "Coloca los hijos en horizontal."),
    desc=T(
        "Lays out its children horizontally, with `spacing` between them and `align` on the cross axis. "
        "`wrap=True` moves children that don't fit to the next line. Lists are flattened and `None`/`False` "
        "are skipped, so `cond and widget` works.",
        "Coloca sus hijos en horizontal, con `spacing` entre ellos y `align` en el eje cruzado. "
        "`wrap=True` pasa a la línea siguiente los hijos que no caben. Las listas se aplanan y se ignoran "
        "`None`/`False`, así que `cond and widget` funciona.",
    ),
    when=T(["For toolbars, button groups, form rows: anything side by side.",
            "Push items apart with `pz.hspace()` between them."],
           ["Para barras, grupos de botones, filas de formulario: todo lo que va lado a lado.",
            "Separa elementos con `pz.hspace()` entre ellos."]),
    preview={"code": _BOX + """pz.column([
    pz.row([box("A"), box("B"), box("C")], spacing=8),
    pz.row([box("Start"), pz.hspace(), box("End")], spacing=8, width=420),
    pz.row([box("tall", h=70), box("center"), box("end")], spacing=8, align="center"),
], spacing=14)"""},
    examples=[
        {"title": T("Wrapping", "Salto de línea"),
         "text": T("With `wrap=True` children flow onto new lines, like tags.",
                   "Con `wrap=True` los hijos pasan a nuevas líneas, como etiquetas."),
         "code": """pz.container(pz.row([ui.chip(t) for t in ["python", "rust", "iced", "zed", "desktop", "gui",
                                             "async", "themes", "canvas", "markdown"]],
                     spacing=6, wrap=True, line_spacing=6), width=360)""", "size": (720, 160)},
    ],
    related=["column", "flex", "spacing"],
)

add(
    slug="column",
    name=T("Column", "Columna"),
    category="layout",
    api=["pyzed.column"],
    blurb=T("Stacks children vertically.", "Apila los hijos en vertical."),
    desc=T(
        "Stacks its children vertically, with `spacing`, `padding`, `align` on the cross axis and an "
        "optional `max_width`. Like `row`, nested lists are flattened and `None`/`False` are ignored.",
        "Apila sus hijos en vertical, con `spacing`, `padding`, `align` en el eje cruzado y un "
        "`max_width` opcional. Como `row`, las listas anidadas se aplanan y se ignoran `None`/`False`.",
    ),
    when=T(["For forms, lists, page content and most `view()` roots."],
           ["Para formularios, listas, contenido de páginas y la raíz de casi cualquier `view()`."]),
    preview={"code": _BOX + """pz.row([
    pz.column([box("1"), box("2"), box("3")], spacing=8),
    pz.column([box("wide", w=160), box("center"), box("end")], spacing=8, align="center"),
    pz.column([box("top"), pz.vspace(), box("bottom")], spacing=8, height=170),
], spacing=32)"""},
    related=["row", "scrollable", "spacing"],
)

add(
    slug="container",
    name=T("Container", "Contenedor"),
    category="layout",
    api=["pyzed.container", "pyzed.center"],
    blurb=T("Size, padding, alignment, background, border and shadow for one child.",
            "Tamaño, relleno, alineación, fondo, borde y sombra para un hijo."),
    desc=T(
        "Wraps one child to give it a size, padding and alignment, and to draw a background (color or "
        "gradient), a border, rounded corners and a shadow. `pz.center(child)` is a container that "
        "centers its child in all the available space.",
        "Envuelve un hijo para darle tamaño, relleno y alineación, y para dibujar un fondo (color o "
        "degradado), un borde, esquinas redondeadas y una sombra. `pz.center(child)` es un contenedor "
        "que centra su hijo en todo el espacio disponible.",
    ),
    when=T(["Whenever a widget needs a box: cards, colored areas, fixed sizes, centering."],
           ["Siempre que un widget necesite una caja: tarjetas, zonas de color, tamaños fijos, centrar."]),
    preview={"code": """t = pz.theme.current()
pz.row([
    pz.container(ui.label("padding + bg"), padding=16, bg=t.element, radius=8),
    pz.container(ui.label("border"), padding=16, border_color=t.accent, border_width=2, radius=8),
    pz.container(ui.label("shadow", color="#ffffff"), padding=16, radius=12,
                 gradient=(135, ["#7c3aed", "#3b82f6"]),
                 shadow=("#00000066", (0, 6), 18)),
], spacing=16, align="center")"""},
    examples=[
        {"title": T("Centering", "Centrar"),
         "text": T("`pz.center` (or `center=True`) centers the child in the space it gets.",
                   "`pz.center` (o `center=True`) centra el hijo en el espacio que recibe."),
         "code": """pz.container(pz.center(ui.label("centered")), width=360, height=120,
             border_color=pz.theme.current().border, border_width=1, radius=8)""", "size": (720, 180)},
    ],
    related=["card", "stack", "row"],
)

add(
    slug="stack",
    name=T("Stack", "Pila"),
    category="layout",
    api=["pyzed.stack", "pyzed.pin"],
    blurb=T("Layers children on top of each other; `pin` places one at x, y.",
            "Superpone los hijos; `pin` coloca uno en x, y."),
    desc=T(
        "Layers its children on top of each other, the last one on top: the basis of layers, modals and "
        "notifications. `pz.pin(child, x=, y=)` places a child at a position inside the stack.",
        "Superpone sus hijos, el último encima de todos: la base de capas, modales y notificaciones. "
        "`pz.pin(child, x=, y=)` coloca un hijo en una posición dentro de la pila.",
    ),
    when=T(["For badges over icons, overlays, and positioning things freely."],
           ["Para insignias encima de iconos, capas y para colocar cosas libremente."]),
    preview={"code": """t = pz.theme.current()
pz.stack([
    pz.container(width=320, height=180, bg=t.element, radius=10),
    pz.pin(pz.container(ui.label("pinned at 24, 24"), padding=10, bg=t.panel, radius=6,
                        border_color=t.border, border_width=1), x=24, y=24),
    pz.pin(ui.count_badge(3), x=290, y=8),
    pz.pin(pz.container(ui.label("on top", color="#ffffff"), padding=10, bg=t.accent, radius=6), x=150, y=110),
], width=320, height=180)"""},
    related=["layer", "popover", "container"],
)

add(
    slug="grid",
    name=T("Grid", "Cuadrícula"),
    category="layout",
    api=["pyzed.grid", "pyzed.cell"],
    badge="new",
    blurb=T("Equal columns, or CSS-like tracks with spans.", "Columnas iguales, o pistas como en CSS con expansión."),
    desc=T(
        "Lays out children in a grid. With `columns=3` the columns are equal, and `max_width` fits as many "
        "as possible. With track lists (`columns=[200, \"1fr\", \"auto\"]`) it works like a CSS grid, and "
        "`pz.cell(child, column=, row=, column_span=, row_span=)` places a child explicitly.",
        "Coloca los hijos en una cuadrícula. Con `columns=3` las columnas son iguales, y `max_width` mete "
        "tantas como quepan. Con listas de pistas (`columns=[200, \"1fr\", \"auto\"]`) funciona como un "
        "grid de CSS, y `pz.cell(child, column=, row=, column_span=, row_span=)` coloca un hijo a mano.",
    ),
    when=T(["For galleries, dashboards and page layouts with a header, sidebar and content."],
           ["Para galerías, dashboards y maquetas de página con cabecera, barra lateral y contenido."]),
    preview={"code": _BOX + """pz.container(pz.grid([box(str(i), w="fill") for i in range(1, 9)], columns=4, spacing=8), width=440)"""},
    examples=[
        {"title": T("Tracks and spans", "Pistas y expansión"),
         "text": T("Numbers are pixels, `\"1fr\"` shares the free space and `\"auto\"` fits the content.",
                   "Los números son píxeles, `\"1fr\"` reparte el espacio libre y `\"auto\"` se ajusta al contenido."),
         "code": _BOX + """pz.container(pz.grid([
    pz.cell(box("header", w="fill"), column=0, row=0, column_span=2),
    pz.cell(box("sidebar", w="fill", h="fill"), column=0, row=1),
    pz.cell(box("content", w="fill", h="fill"), column=1, row=1),
], columns=[120, "1fr"], rows=[44, 110], spacing=8), width=440)""", "size": (720, 220)},
    ],
    related=["flex", "row", "column"],
)

add(
    slug="flex",
    name=T("Flex", "Flex"),
    category="layout",
    api=["pyzed.flex", "pyzed.flex_item"],
    badge="new",
    blurb=T("CSS flexbox: justify, align, gap, wrap and grow.", "Flexbox de CSS: justify, align, gap, wrap y grow."),
    desc=T(
        "Lays children out along one axis like CSS flexbox: `justify` on the main axis (`start`, "
        "`center`, `end`, `between`, `around`, `evenly`), `align` on the cross axis, `gap` and `wrap`. "
        "`pz.flex_item(child, grow=, basis=)` makes a child grow or gives it a base size.",
        "Coloca los hijos en un eje como el flexbox de CSS: `justify` en el eje principal (`start`, "
        "`center`, `end`, `between`, `around`, `evenly`), `align` en el eje cruzado, `gap` y `wrap`. "
        "`pz.flex_item(child, grow=, basis=)` hace crecer a un hijo o le da un tamaño base.",
    ),
    when=T(["When `row`/`column` are not enough: even distribution, growing items, wrapping cards."],
           ["Cuando `row`/`column` no bastan: reparto uniforme, elementos que crecen, tarjetas que saltan de línea."]),
    preview={"code": _BOX + """pz.column([
    pz.flex([box("A"), box("B"), box("C")], justify="between", width=440),
    pz.flex([box("fixed"), pz.flex_item(box("grows", w="fill"), grow=1), box("fixed")], gap=8, width=440),
    pz.flex([box("A"), box("B")], justify="center", gap=8, width=440),
], spacing=14)"""},
    related=["grid", "row"],
)

add(
    slug="scrollable",
    name=T("Scrollable", "Desplazable"),
    category="layout",
    api=["pyzed.scrollable"],
    blurb=T("Scrolls content that doesn't fit.", "Desplaza el contenido que no cabe."),
    desc=T(
        "Makes its content scrollable vertically, horizontally or `\"both\"`. Give it an `id` to scroll "
        "from code (`pz.Command.scroll_to`), `anchor_bottom=True` to stick to the end (chats, logs), and "
        "style the rail and scroller with the theme or your own colors.",
        "Hace que su contenido se pueda desplazar en vertical, en horizontal o en `\"both\"`. Dale un "
        "`id` para desplazarlo desde código (`pz.Command.scroll_to`), `anchor_bottom=True` para quedarse "
        "al final (chats, registros), y personaliza el carril y la barra con el tema o tus colores.",
    ),
    when=T(["For long lists, documents and any content taller than its space."],
           ["Para listas largas, documentos y cualquier contenido más alto que su espacio."]),
    preview={"code": """pz.container(pz.scrollable(
    pz.column([ui.list_item(f"Item {i}", on_open, icon="file", inset=True) for i in range(1, 30)]),
    height=220,
), width=300)"""},
    related=["column", "list-item"],
)

add(
    slug="resizable",
    name=T("Resizable", "Redimensionable"),
    category="layout",
    api=["pyzed.resizable"],
    badge="new",
    blurb=T("A panel whose edge can be dragged to resize it.", "Un panel cuyo borde se arrastra para cambiar su tamaño."),
    desc=T(
        "A panel whose `edge` (`\"left\"`, `\"right\"`, `\"top\"` or `\"bottom\"`) can be dragged to resize "
        "it, between `min_size` and `max_size`. It keeps the size the user drags it to; `on_resize(size)` "
        "is called when the drag ends so you can save it.",
        "Un panel cuyo `edge` (`\"left\"`, `\"right\"`, `\"top\"` o `\"bottom\"`) se puede arrastrar para "
        "cambiar su tamaño, entre `min_size` y `max_size`. Conserva el tamaño que elige el usuario; "
        "`on_resize(size)` se llama al soltar para que puedas guardarlo.",
    ),
    when=T(["For one resizable sidebar or bottom panel next to fixed content."],
           ["Para una barra lateral o un panel inferior redimensionable junto a contenido fijo."]),
    preview={"code": """t = pz.theme.current()
pz.row([
    pz.resizable(pz.container(ui.label("Drag my right edge"), padding=12, width="fill", height="fill", bg=t.panel),
                 edge="right", size=260, min_size=160, color=t.border, hover_color=t.accent),
    pz.container(ui.muted("Content"), center=True, width="fill", height="fill"),
], height="fill")""", "fill": True},
    related=["split", "panel"],
)

add(
    slug="spacing",
    name=T("Space", "Espacio"),
    category="layout",
    api=["pyzed.space", "pyzed.hspace", "pyzed.vspace"],
    blurb=T("Fixed gaps and flexible spacers.", "Huecos fijos y separadores flexibles."),
    desc=T(
        "`pz.space(width, height)` is an empty box of a given size. `pz.hspace()` and `pz.vspace()` are "
        "flexible gaps that take the free space, pushing their siblings to the edges of a row or column.",
        "`pz.space(width, height)` es una caja vacía de un tamaño dado. `pz.hspace()` y `pz.vspace()` son "
        "huecos flexibles que ocupan el espacio libre y empujan a sus hermanos a los extremos de una fila "
        "o columna.",
    ),
    when=T(["To push actions to the right of a toolbar, or a footer to the bottom of a panel."],
           ["Para llevar acciones a la derecha de una barra, o un pie al fondo de un panel."]),
    preview={"code": _BOX + """pz.column([
    pz.row([box("left"), pz.hspace(), box("right")], width=440),
    pz.row([box("a"), pz.space(width=60), box("60 px later", w=140)]),
], spacing=16)"""},
    related=["row", "column", "divider"],
)

add(
    slug="responsive",
    name=T("Responsive", "Responsivo"),
    category="layout",
    api=["pyzed.responsive"],
    blurb=T("Builds its content from the space actually available.", "Construye su contenido según el espacio disponible."),
    desc=T(
        "Calls `function(width, height)` with the space it really gets and shows what it returns, so the "
        "layout can adapt: hide a sidebar when the window is narrow, change the number of columns…",
        "Llama a `function(width, height)` con el espacio que recibe de verdad y muestra lo que devuelve, "
        "así la disposición se adapta: ocultar una barra lateral si la ventana es estrecha, cambiar el "
        "número de columnas…",
    ),
    when=T(["For layouts that must work both in a small and a large window."],
           ["Para disposiciones que deben funcionar en una ventana pequeña y en una grande."]),
    preview={"code": _BOX + """pz.container(pz.responsive(lambda w, h: pz.center(pz.column([
    ui.muted(f"{w:.0f} × {h:.0f} px available"),
    pz.row([box("1"), box("2"), box("3"), box("4")], spacing=8) if w > 400 else
    pz.column([box("1"), box("2")], spacing=8),
], spacing=10, align="center"))), width=480, height=150)"""},
    related=["grid", "flex"],
)

# ---------------------------------------------------------------------------------------- content

add(
    slug="text",
    name=T("Text", "Texto"),
    category="content",
    api=["pyzed.text"],
    blurb=T("A piece of text with size, color, font and weight.", "Un texto con tamaño, color, fuente y peso."),
    desc=T(
        "The base text widget: `size`, `color`, `font`, `weight`, `italic`, `line_height`, alignment and "
        "wrapping. In a themed UI prefer [Label](/pyzed/library/label/), which takes its color from the theme.",
        "El widget base de texto: `size`, `color`, `font`, `weight`, `italic`, `line_height`, alineación y "
        "ajuste de línea. En una interfaz con tema mejor usa [Etiqueta](/pyzed/es/library/label/), que "
        "toma el color del tema.",
    ),
    when=T(["For text with explicit styles, or custom fonts loaded with `pz.load_font`."],
           ["Para texto con estilos explícitos, o fuentes propias cargadas con `pz.load_font`."]),
    preview={"code": """pz.column([
    pz.text("Pyzed", size=36, weight="bold", color="#74ade8"),
    pz.text("Fast, modern desktop UIs in Python.", size=16, color="#a9afbc"),
    pz.text("IBM Plex Mono, italic", font="IBM Plex Mono", italic=True, color="#e5c07b"),
], spacing=6, align="center")"""},
    related=["label", "rich-text", "icon"],
)

add(
    slug="icon",
    name=T("Icon", "Icono"),
    category="content",
    api=["pyzed.icon", "pyzed.svg"],
    blurb=T("Lucide icons by name, and SVG images.", "Iconos de Lucide por nombre e imágenes SVG."),
    desc=T(
        "`pz.icon(name)` draws one of the 1,500+ [Lucide](https://lucide.dev) icons; `color` defaults to "
        "the surrounding text color. `pz.svg(source)` draws any SVG from a path or bytes, tinted with "
        "`color` if you want.",
        "`pz.icon(name)` dibuja uno de los más de 1.500 iconos de [Lucide](https://lucide.dev); `color` "
        "toma por defecto el color del texto. `pz.svg(source)` dibuja cualquier SVG desde una ruta o "
        "bytes, teñido con `color` si quieres.",
    ),
    when=T(["Inside buttons, list rows and headers. Run `pyzed icons` to search the names."],
           ["Dentro de botones, filas y cabeceras. Ejecuta `pyzed icons` para buscar los nombres."]),
    preview={"code": """pz.row([
    pz.icon("sparkles", size=28, color="#e5c07b"),
    pz.icon("git-branch", size=28, color="#a1c181"),
    pz.icon("folder-open", size=28, color="#74ade8"),
    pz.icon("bug", size=28, color="#d07277"),
    pz.icon("terminal", size=28, color="#c678dd"),
    pz.svg("logo.svg", width=40, height=40),
], spacing=20, align="center")"""},
    related=["icon-button", "image"],
)

add(
    slug="image",
    name=T("Image", "Imagen"),
    category="content",
    api=["pyzed.image", "pyzed.image_viewer"],
    blurb=T("Bitmaps with fit, opacity, radius; a pan-and-zoom viewer.", "Imágenes con ajuste, opacidad y radio; un visor con zoom."),
    desc=T(
        "`pz.image(source)` shows a PNG, JPEG, GIF, WebP, BMP… from a path, `bytes`, or raw RGBA pixels "
        "with `size=(w, h)`. Options: `content_fit` (`\"contain\"`, `\"cover\"`, `\"fill\"`, `\"none\"`, "
        "`\"scale_down\"`), `filter` (`\"linear\"` or `\"nearest\"`), `opacity`, `radius`, `rotation` and "
        "`scale`. `pz.image_viewer` adds pan (drag) and zoom (wheel).",
        "`pz.image(source)` muestra un PNG, JPEG, GIF, WebP, BMP… desde una ruta, `bytes` o píxeles RGBA "
        "con `size=(w, h)`. Opciones: `content_fit` (`\"contain\"`, `\"cover\"`, `\"fill\"`, `\"none\"`, "
        "`\"scale_down\"`), `filter` (`\"linear\"` o `\"nearest\"`), `opacity`, `radius`, `rotation` y "
        "`scale`. `pz.image_viewer` añade desplazamiento (arrastrar) y zoom (rueda).",
    ),
    when=T(["For screenshots, avatars, thumbnails and photo viewers."],
           ["Para capturas, avatares, miniaturas y visores de fotos."]),
    preview={"code": """pz.row([
    pz.image("photo.png", width=300, height=180, content_fit="cover", radius=10),
    pz.image("photo.png", width=140, height=180, content_fit="contain", opacity=0.5),
], spacing=16, align="center")"""},
    related=["icon", "qr-code"],
)

add(
    slug="rich-text",
    name=T("Rich text", "Texto enriquecido"),
    category="content",
    api=["pyzed.rich_text", "pyzed.span"],
    blurb=T("One block of text mixing colors, weights and links.", "Un bloque de texto que mezcla colores, pesos y enlaces."),
    desc=T(
        "Combines `pz.span(text, color=, size=, font=, weight=, italic=, bg=, underline=, strikethrough=, "
        "link=)` fragments into a single block of text that wraps as a whole. Clicking a span with `link` "
        "sends that value.",
        "Combina fragmentos `pz.span(text, color=, size=, font=, weight=, italic=, bg=, underline=, "
        "strikethrough=, link=)` en un único bloque de texto que se ajusta como un todo. Al pulsar un "
        "fragmento con `link` se envía ese valor.",
    ),
    when=T(["For inline highlights, mentions, search matches and short formatted messages."],
           ["Para resaltados en línea, menciones, coincidencias de búsqueda y mensajes cortos con formato."]),
    preview={"code": """pz.rich_text([
    pz.span("rich_text "),
    pz.span("mixes ", color="#e5c07b"),
    pz.span("styles", weight="bold", underline=True),
    pz.span(" on one line, with "),
    pz.span(" code ", font="IBM Plex Mono", bg="#3b414d", radius=4),
    pz.span(" and "),
    pz.span("links", color="#74ade8", underline=True, link="https://iced.rs"),
], size=18, width=460)"""},
    related=["text", "markdown"],
)

add(
    slug="qr-code",
    name=T("QR code", "Código QR"),
    category="content",
    api=["pyzed.qr_code"],
    blurb=T("A QR code for any text or URL.", "Un código QR para cualquier texto o URL."),
    desc=T("Draws a QR code that encodes `data`. `cell_size` sets the size of each module; `color` and `bg` change its colors.",
           "Dibuja un código QR que codifica `data`. `cell_size` fija el tamaño de cada módulo; `color` y `bg` cambian sus colores."),
    when=T(["To pass a link, a Wi-Fi password or a pairing code to a phone."],
           ["Para pasar un enlace, una contraseña de Wi-Fi o un código de emparejamiento a un móvil."]),
    preview={"code": """pz.row([
    pz.qr_code("https://albakore.github.io/pyzed/", cell_size=5),
    pz.qr_code("pyzed", cell_size=5, color="#74ade8", bg="#282c33"),
], spacing=24, align="center")"""},
    related=["image", "canvas"],
)

add(
    slug="canvas",
    name=T("Canvas", "Lienzo"),
    category="content",
    api=["pyzed.canvas"],
    blurb=T("2D drawing with shapes, paths, text and mouse events.", "Dibujo 2D con formas, trazos, texto y eventos de ratón."),
    desc=T(
        "A 2D drawing surface. `shapes` is a list made with [`pyzed.draw`](/pyzed/reference/draw/) "
        "(rectangles, circles, arcs, paths, text, images…). Mouse callbacks receive coordinates relative "
        "to the canvas; with an `id` the geometry is cached between frames. The charts of this library "
        "are drawn with it.",
        "Una superficie de dibujo 2D. `shapes` es una lista hecha con [`pyzed.draw`](/pyzed/reference/draw/) "
        "(rectángulos, círculos, arcos, trazos, texto, imágenes…). Los callbacks del ratón reciben "
        "coordenadas relativas al lienzo; con un `id` la geometría se guarda entre fotogramas. Los "
        "gráficos de esta biblioteca están dibujados con él.",
    ),
    when=T(["For charts, games, diagrams, drawing apps and custom widgets."],
           ["Para gráficos, juegos, diagramas, apps de dibujo y widgets propios."]),
    preview={"code": """pz.canvas([
    draw.rect(10, 10, 120, 80, fill="#74ade8", radius=8),
    draw.circle(200, 50, 40, fill="#a1c181"),
    draw.arc(300, 50, 40, 0, 270, stroke="#e5c07b", width=8, cap="round"),
    draw.polygon([(360, 90), (400, 10), (440, 90)], fill="#d07277"),
    draw.line(10, 120, 440, 120, stroke="#5d636f", width=2, dash=[6, 4]),
    draw.text(225, 150, "pz.canvas + pyzed.draw", color="#a9afbc", size=16, align_x="center"),
], width=450, height=170)"""},
    related=["bar-chart", "donut", "stack"],
)

add(
    slug="animation",
    name=T("Animation", "Animación"),
    category="content",
    api=["pyzed.Animation", "pyzed.stagger", "pyzed.presence", "pyzed.define_animation",
         "pyzed.set_reduced_motion"],
    badge="new",
    blurb=T("Presets, keyframes and transitions for any widget.",
            "Presets, keyframes y transiciones para cualquier widget."),
    desc=T(
        "Every widget has `animate()` and `transition()`. `animate` plays one of 47 presets or a "
        "`pz.Animation` when the widget appears, on hover, press, focus, click or while `active`; "
        "`transition` animates property changes like CSS. `pz.stagger` cascades a list in and "
        "`pz.presence` animates content in and out when it changes. Everything runs natively, without "
        "calling Python per frame. See the [Animation guide](/pyzed/animation/).",
        "Todo widget tiene `animate()` y `transition()`. `animate` reproduce uno de los 47 presets o una "
        "`pz.Animation` cuando el widget aparece, en hover, al pulsar, con foco, al hacer clic o mientras "
        "`active`; `transition` anima los cambios de propiedades como CSS. `pz.stagger` hace entrar una "
        "lista en cascada y `pz.presence` anima la entrada y salida del contenido cuando cambia. Todo se "
        "reproduce de forma nativa, sin llamar a Python en cada fotograma. Ver la "
        "[guía de animación](/pyzed/es/animation/).",
    ),
    when=T(
        ["To show that something appeared, changed or needs attention: a toast, a new row, an error shake.",
         "For hover and press feedback on cards and custom buttons.",
         "For page and tab transitions with `pz.presence`."],
        ["Para mostrar que algo apareció, cambió o necesita atención: un aviso, una fila nueva, la sacudida de un error.",
         "Para la respuesta en hover y al pulsar de tarjetas y botones propios.",
         "Para transiciones entre páginas y pestañas con `pz.presence`."],
    ),
    preview={"code": """pz.column(pz.stagger([
    ui.card(ui.label(name), width=320).animate("lift", on="hover")
    for name in ("fade_in_up", "lift on hover", "stagger")
], "fade_in_up", step=60), spacing=10)"""},
    usage="""class Inbox(pz.App):
    errors = 0
    page = 0

    def view(self):
        return pz.column([
            ui.input(self.query, self.search).animate("shake", key=self.errors),
            pz.presence(self.page_view(), key=self.page, enter="fade_in_right", exit="fade_out"),
            ui.button("Record", self.record).animate("glow_pulse", active=self.recording),
        ], spacing=12)""",
    notes=T(
        "Screenshots and `pz.set_reduced_motion(True)` show every animation at rest, so tests are stable. "
        "Respect users who turn motion off.",
        "Las capturas y `pz.set_reduced_motion(True)` muestran cada animación en reposo, así que los tests "
        "son estables. Respeta a quien apaga el movimiento.",
    ),
    related=["effects", "card", "toast"],
)

add(
    slug="shader",
    name=T("Shader", "Shader"),
    category="content",
    api=["pyzed.shader"],
    badge="new",
    blurb=T("A widget painted on the GPU by your own WGSL code.",
            "Un widget pintado en la GPU por tu propio código WGSL."),
    desc=T(
        "`pz.shader` runs a function you write in WGSL, `fn shade(uv, px, size, time) -> vec4<f32>`, for "
        "every pixel of the widget, every frame, on the GPU: animated backgrounds, plasma, fire or a radar "
        "sweep cost Python nothing. Each entry of `uniforms` becomes a WGSL function of the same name, and "
        "`mouse()` gives the pointer. Without a GPU the widget shows `fallback`. See the "
        "[Shaders guide](/pyzed/shading/shaders/) and the [showcase](/pyzed/showcase/).",
        "`pz.shader` ejecuta una función que escribes en WGSL, `fn shade(uv, px, size, time) -> vec4<f32>`, "
        "para cada píxel del widget, en cada fotograma, en la GPU: fondos animados, plasma, fuego o el barrido "
        "de un radar no le cuestan nada a Python. Cada entrada de `uniforms` se convierte en una función WGSL "
        "con el mismo nombre, y `mouse()` da la posición del puntero. Sin GPU el widget muestra `fallback`. "
        "Ver la [guía de shaders](/pyzed/es/shading/shaders/) y las [demos](/pyzed/es/showcase/).",
    ),
    when=T(
        ["For animated backgrounds behind glass panels, menus and HUDs.",
         "For game visuals and effects that would be too slow to draw from Python every frame."],
        ["Para fondos animados detrás de paneles de cristal, menús y HUDs.",
         "Para gráficos y efectos de juegos que serían demasiado lentos de dibujar desde Python en cada fotograma."],
    ),
    preview={"code": '''pz.shader("""
fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> {
    let wave = 0.5 + 0.5 * sin(uv.x * 12.0 + uv.y * 4.0 + time * speed());
    return vec4<f32>(mix(vec3<f32>(0.08, 0.09, 0.2), tint().rgb, wave), 1.0);
}
""", uniforms={"speed": 2.0, "tint": "#c678dd"}, width=640, height=240, time=0.5,
    fallback=pz.Gradient(["#14172f", "#c678dd"], angle=0))''', "size": (720, 300)},
    notes=T(
        "Shaders need the GPU renderer. Always pass a `fallback` that looks right on its own: it is what "
        "the software renderer and machines without a GPU draw.",
        "Los shaders necesitan el renderizador de GPU. Pasa siempre un `fallback` que se vea bien por sí "
        "solo: es lo que dibujan el renderizador por software y los equipos sin GPU.",
    ),
    related=["effects", "canvas", "animation"],
)

add(
    slug="effects",
    name=T("Effects", "Efectos"),
    category="content",
    api=["pyzed.Style"],
    badge="new",
    blurb=T("Glow, bloom, glass and opacity as style properties.",
            "Glow, bloom, glass y opacidad como propiedades de estilo."),
    desc=T(
        "Visual effects are [style](/pyzed/theming/styles/) properties: `glow` (a soft halo), `bloom` (a wide, "
        "bright spill of light), `glass` (a translucent, frosted panel), `opacity`, and `translate` and "
        "`scale`, which move or scale the drawing without changing the layout. Animations can change "
        "`glow` too.",
        "Los efectos visuales son propiedades de [estilo](/pyzed/es/theming/styles/): `glow` (un halo suave), "
        "`bloom` (un resplandor amplio y brillante), `glass` (un panel translúcido y esmerilado), `opacity`, "
        "y `translate` y `scale`, que desplazan o escalan el dibujo sin cambiar el layout. Las animaciones "
        "también pueden cambiar `glow`.",
    ),
    when=T(
        ["To highlight the primary action or a live state (recording, connected).",
         "For floating panels over colorful backgrounds (glass)."],
        ["Para destacar la acción principal o un estado en vivo (grabando, conectado).",
         "Para paneles flotantes sobre fondos coloridos (glass)."],
    ),
    preview={"code": """pz.container(pz.row([
    pz.container(ui.label("Glass"), width=150, height=70, padding=14).style(glass=True, radius=12),
    pz.container(ui.label("Glow"), width=150, height=70, padding=14).style(
        background="#0b1220", radius=12, glow=("#22d3ee", 18)),
    pz.container(ui.label("Bloom"), width=150, height=70, padding=14).style(
        background="#1a0b16", radius=12, bloom=("#f472b6", 0.8)),
    pz.container(ui.label("Opacity"), width=150, height=70, padding=14).style(
        background="#0b1220", radius=12, opacity=0.5),
], spacing=24), padding=32).style(
    background=pz.Gradient(["#0f172a", "#312e81", "#0e7490"], angle=90), radius=14)""", "size": (820, 220)},
    related=["animation", "card"],
)

# --------------------------------------------------------------------------- base interaction pages
# ``pz.*`` widgets that have no themed counterpart get their own page; the others are documented on
# the page of the ``ui`` component built on them (``pz.button`` on Button, ``pz.toggler`` on Switch...).

add(
    slug="mouse-area",
    name=T("Mouse area", "Área de ratón"),
    category="actions",
    api=["pyzed.mouse_area", "pyzed.hover", "pyzed.opaque"],
    blurb=T("Makes any widget react to clicks, hover, drags and the wheel.",
            "Hace que cualquier widget reaccione a clics, hover, arrastres y la rueda."),
    desc=T(
        "`pz.mouse_area` wraps any widget and reports what the mouse does over it: presses (left, right, "
        "middle, double click), entering and leaving, moving (`on_move(x, y)`) and the wheel "
        "(`on_scroll(dx, dy)`); `cursor` changes the pointer. `pz.hover(base, top)` shows `top` over `base` "
        "only while the pointer is over it, and `pz.opaque` stops clicks from reaching what is under a "
        "widget in a `stack`.",
        "`pz.mouse_area` envuelve cualquier widget y avisa de lo que hace el ratón encima: pulsaciones "
        "(izquierda, derecha, central, doble clic), entrar y salir, moverse (`on_move(x, y)`) y la rueda "
        "(`on_scroll(dx, dy)`); `cursor` cambia el puntero. `pz.hover(base, top)` muestra `top` encima de "
        "`base` solo mientras el puntero está encima, y `pz.opaque` impide que los clics lleguen a lo que hay "
        "debajo de un widget en un `stack`.",
    ),
    when=T(
        ["To make a card, an image or a custom drawing clickable without turning it into a button.",
         "For right-click menus (`on_right_press`), drag gestures (`on_move`) and zoom with the wheel.",
         "`pz.hover` for actions that appear on hover, like the close button of a tab."],
        ["Para que una tarjeta, una imagen o un dibujo propio se puedan pulsar sin convertirlos en botón.",
         "Para menús de clic derecho (`on_right_press`), gestos de arrastre (`on_move`) y zoom con la rueda.",
         "`pz.hover` para acciones que aparecen al pasar el ratón, como el botón de cerrar de una pestaña."],
    ),
    preview={"code": """pz.mouse_area(
    ui.card(pz.row([pz.icon("folder", size=20), ui.label("Open project…")], spacing=10, align="center"),
            width=280),
    on_press=on_open, on_right_press=on_menu, cursor="pointer",
)"""},
    usage="""class Board(pz.App):
    def __init__(self):
        self.pointer = (0, 0)
        self.zoom = 1.0

    def view(self):
        return pz.mouse_area(
            self.drawing(),
            on_move=lambda x, y: setattr(self, "pointer", (x, y)),
            on_scroll=lambda dx, dy: setattr(self, "zoom", max(0.1, self.zoom + dy * 0.1)),
            on_double_click=self.reset, cursor="crosshair",
        )""",
    notes=T(
        "Hover and pointer states only exist with a real mouse, so the previews draw them as they look; "
        "see the animated clips in [Showcase](/pyzed/showcase/) for the real thing.",
        "Los estados de hover y del puntero solo existen con un ratón real, así que las vistas previas los "
        "dibujan tal como se ven; mira los clips animados del [Showcase](/pyzed/es/showcase/) para verlos en marcha.",
    ),
    related=["button", "popover", "stack"],
)

add(
    slug="anchor-layout",
    name=T("Anchor layout", "Disposición anclada"),
    category="layout",
    api=["pyzed.anchor_layout", "pyzed.anchor", "pyzed.anchors.place"],
    blurb=T("Free positions like a form designer, with anchors that follow resizes.",
            "Posiciones libres como en un diseñador de formularios, con anclas que siguen al redimensionar."),
    desc=T(
        "Places children at exact positions, the way a visual form designer does, and says how each one "
        "follows a resize: `pz.anchor(child, x=, y=, width=, height=, anchor=)` keeps the distance to the "
        "edges it is anchored to, stretches between opposite edges and stays centered otherwise. Presets "
        "such as `\"top_right\"`, `\"bottom_wide\"`, `\"center\"` or `\"full\"` cover the usual cases. "
        "`pyzed.anchors.place` is the math behind it, for your own layouts.",
        "Coloca los hijos en posiciones exactas, como un diseñador visual de formularios, y dice cómo sigue "
        "cada uno un cambio de tamaño: `pz.anchor(child, x=, y=, width=, height=, anchor=)` mantiene la "
        "distancia a los bordes a los que está anclado, se estira entre bordes opuestos y si no se queda "
        "centrado. Presets como `\"top_right\"`, `\"bottom_wide\"`, `\"center\"` o `\"full\"` cubren los "
        "casos habituales. `pyzed.anchors.place` es la cuenta que hay detrás, para tus propias disposiciones.",
    ),
    when=T(
        ["For forms drawn in Pyzed Design (it is what the Form view generates) or ported from Visual Basic, "
         "Qt Designer or WinForms.",
         "For game HUDs and overlays where things stick to corners.",
         "For forms that grow and shrink with the window, prefer `row`, `column` and `grid`."],
        ["Para formularios dibujados en Pyzed Design (es lo que genera la vista de Formulario) o traídos de "
         "Visual Basic, Qt Designer o WinForms.",
         "Para HUDs de juegos y capas en las que las cosas se pegan a las esquinas.",
         "Para formularios que crecen y encogen con la ventana, mejor `row`, `column` y `grid`."],
    ),
    preview={"code": """t = pz.theme.current()
pz.container(pz.anchor_layout([
    pz.anchor(ui.heading("Report", level=3), x=16, y=12, width=200, height=28, anchor="top_left"),
    pz.anchor(ui.icon_button("x", on_close), x=356, y=12, width=28, height=28, anchor="top_right"),
    pz.anchor(ui.input("", on_input, placeholder="Search…"), x=16, y=56, width=368, height=30,
              anchor="top_wide"),
    pz.anchor(ui.button("Close", on_close, variant="solid"), x=284, y=172, width=100, height=30,
              anchor="bottom_right"),
], design=(400, 216)), width=400, height=216, bg=t.panel, border_color=t.border, border_width=1, radius=8)"""},
    usage="""class Report(pz.App):
    def view(self):
        return pz.anchor_layout([
            pz.anchor(ui.heading("Report"), x=16, y=12, width=368, height=28, anchor="top_wide"),
            pz.anchor(self.table(), x=16, y=48, width=368, height=196, anchor="full"),
            pz.anchor(ui.button("Close", self.close), x=284, y=252, width=100, height=32,
                      anchor="bottom_right"),
        ], design=(400, 300))""",
    notes=T(
        "`design` is the size the positions were measured in; when the layout gets more or less room, each "
        "child moves or stretches from there. Try it live: drag the window corner of a form in Pyzed Design.",
        "`design` es el tamaño en el que se midieron las posiciones; cuando la disposición tiene más o menos "
        "espacio, cada hijo se mueve o se estira desde ahí. Pruébalo en vivo: arrastra la esquina de un "
        "formulario en Pyzed Design.",
    ),
    related=["stack", "grid", "container"],
    badge="new",
)

# Base widgets documented on the page of the component built on them.
_BASE_APIS = {
    "button": ["pyzed.button"],
    "input": ["pyzed.text_input"],
    "checkbox": ["pyzed.checkbox"],
    "switch": ["pyzed.toggler"],
    "slider": ["pyzed.slider", "pyzed.vertical_slider"],
    "progress": ["pyzed.progress_bar"],
    "select": ["pyzed.pick_list"],
    "radio-group": ["pyzed.radio"],
}

# ------------------------------------------------------------------------------------- plain words
# One or two sentences per component for readers who don't program: what it is, as you'd see it.

PLAIN = {
    "button": T("A button is something you click to make the app do something: save, send, open, delete.",
                "Un botón es algo que pulsas para que la app haga algo: guardar, enviar, abrir, borrar."),
    "icon-button": T("A small button with just a picture (a magnifying glass, a gear) instead of words.",
                     "Un botón pequeño con solo un dibujo (una lupa, un engranaje) en lugar de palabras."),
    "split-button": T("A button with two parts: the big part does the usual thing, the little arrow shows other ways to do it.",
                      "Un botón con dos partes: la grande hace lo habitual y la flechita muestra otras formas de hacerlo."),
    "toggle-group": T("A row of icon buttons where only one can be on, like choosing left, center or right alignment.",
                      "Una fila de botones con iconos en la que solo uno puede estar activo, como elegir alinear a la izquierda, al centro o a la derecha."),
    "chip": T("A small rounded tag. Click it to turn a filter on or off, or press its ✕ to remove it.",
              "Una etiqueta pequeña y redondeada. Púlsala para activar o quitar un filtro, o pulsa su ✕ para quitarla."),
    "mouse-area": T("An invisible layer that lets anything (a picture, a card, a drawing) notice clicks and the mouse.",
                    "Una capa invisible que permite que cualquier cosa (una imagen, una tarjeta, un dibujo) note los clics y el ratón."),
    "label": T("Plain text on the screen, in the colors of the current theme.",
               "Texto normal en la pantalla, con los colores del tema actual."),
    "heading": T("A title: bigger, bolder text that names a page or a section.",
                 "Un título: texto más grande y en negrita que nombra una página o una sección."),
    "badge": T("A tiny colored pill with a word or two, like “beta” or “3 errors”.",
               "Una pastilla de color diminuta con una o dos palabras, como “beta” o “3 errores”."),
    "indicator": T("A small colored dot that tells a state at a glance: green is fine, red is a problem.",
                   "Un puntito de color que indica un estado de un vistazo: verde es que va bien, rojo que hay un problema."),
    "kbd": T("Draws keyboard keys, so people learn the shortcut: Ctrl + S.",
             "Dibuja teclas del teclado para que la gente aprenda el atajo: Ctrl + S."),
    "avatar": T("A circle with someone's initials, in their own color.",
                "Un círculo con las iniciales de alguien, en su propio color."),
    "tooltip": T("A little box with a hint that appears when you rest the mouse on something.",
                 "Una cajita con una pista que aparece cuando dejas el ratón encima de algo."),
    "divider": T("A thin line that separates groups of things.", "Una línea fina que separa grupos de cosas."),
    "card": T("A box with a border that keeps related things together, like a card on a table.",
              "Una caja con borde que mantiene juntas las cosas relacionadas, como una ficha sobre una mesa."),
    "input": T("A box where people type one line of text: a name, an email, a password.",
               "Una caja donde la gente escribe una línea de texto: un nombre, un correo, una contraseña."),
    "search-input": T("A text box with a magnifying glass, for typing what you are looking for.",
                      "Una caja de texto con una lupa, para escribir lo que buscas."),
    "checkbox": T("A square you tick to say yes to an option.", "Un cuadrado que marcas para decir que sí a una opción."),
    "switch": T("An on/off switch, like a light switch, for settings that change right away.",
                "Un interruptor de encendido y apagado, como el de la luz, para ajustes que cambian al momento."),
    "slider": T("A bar with a knob you drag to pick an amount, like a volume control.",
                "Una barra con un botón que arrastras para elegir una cantidad, como el control del volumen."),
    "number-field": T("A box with a number and − / + buttons to make it smaller or bigger.",
                      "Una caja con un número y botones − / + para hacerlo más pequeño o más grande."),
    "select": T("A box that opens a list so you can pick one option from it.",
                "Una caja que abre una lista para que elijas una opción."),
    "radio-group": T("A few round options where picking one unpicks the others.",
                     "Unas cuantas opciones redondas en las que elegir una desmarca las demás."),
    "segmented": T("A row of joined buttons where exactly one is chosen, like Day / Week / Month in a calendar.",
                   "Una fila de botones unidos en la que hay exactamente uno elegido, como Día / Semana / Mes en un calendario."),
    "field": T("A row of a form: the name of a setting on the left and its control on the right.",
               "Una fila de un formulario: el nombre de un ajuste a la izquierda y su control a la derecha."),
    "color-picker": T("A palette to choose a color, its transparency, or a blend of colors.",
                      "Una paleta para elegir un color, su transparencia o una mezcla de colores."),
    "icon-picker": T("A searchable grid of little pictures to choose an icon from.",
                     "Una cuadrícula de dibujitos con buscador para elegir un icono."),
    "progress": T("A bar that fills up to show how much of a task is done.",
                  "Una barra que se llena para mostrar cuánto falta de una tarea."),
    "spinner": T("A spinning circle that says “wait, I'm working on it”.",
                 "Un círculo que gira y dice “espera, estoy en ello”."),
    "callout": T("A colored box inside the page with a message: a tip, a warning or an error.",
                 "Una caja de color dentro de la página con un mensaje: un consejo, un aviso o un error."),
    "toast": T("A small notification that pops up in a corner and goes away by itself.",
               "Una notificación pequeña que aparece en una esquina y se va sola."),
    "empty-state": T("What a screen shows when there is nothing in it yet, with a hint of what to do next.",
                     "Lo que muestra una pantalla cuando aún no tiene nada, con una pista de qué hacer después."),
    "count-badge": T("A little round number, like the count of unread messages on an app icon.",
                     "Un numerito redondo, como el número de mensajes sin leer en el icono de una app."),
    "keybinding-hint": T("A quiet line that teaches a shortcut: “Open file  Ctrl P”.",
                         "Una línea discreta que enseña un atajo: “Abrir archivo  Ctrl P”."),
    "table": T("Rows and columns of data, like a spreadsheet you can sort by clicking a column.",
               "Filas y columnas de datos, como una hoja de cálculo que ordenas pulsando una columna."),
    "virtual-list": T("A list that stays fast even with millions of rows, because it only draws what you see.",
                      "Una lista que sigue siendo rápida con millones de filas, porque solo dibuja lo que ves."),
    "stat": T("A big number with its name and whether it went up or down, like on a dashboard.",
              "Un número grande con su nombre y si subió o bajó, como en un panel de control."),
    "sparkline": T("A tiny line chart that shows if something is going up or down.",
                   "Un gráfico de líneas diminuto que muestra si algo sube o baja."),
    "bar-chart": T("A chart of bars to compare a few amounts.", "Un gráfico de barras para comparar unas pocas cantidades."),
    "donut": T("A ring cut into colored slices that shows the parts of a whole.",
               "Un anillo dividido en porciones de colores que muestra las partes de un todo."),
    "diff-stat": T("How many lines were added (green) and removed (red) in a change.",
                   "Cuántas líneas se añadieron (verde) y se quitaron (rojo) en un cambio."),
    "facepile": T("A row of overlapping avatars that shows who is here.",
                  "Una fila de avatares superpuestos que muestra quién está."),
    "settings-group": T("A titled block of settings, like a section of a preferences window.",
                        "Un bloque de ajustes con título, como una sección de una ventana de preferencias."),
    "list-item": T("One row of a list: an icon, a name and maybe something on the right.",
                   "Una fila de una lista: un icono, un nombre y quizá algo a la derecha."),
    "list-header": T("A small title above a group of rows.", "Un título pequeño encima de un grupo de filas."),
    "tree": T("A list of folders you can open and close, like the files of a project.",
              "Una lista de carpetas que puedes abrir y cerrar, como los archivos de un proyecto."),
    "menu": T("The list of options that appears when you right-click or press a “more” button.",
              "La lista de opciones que aparece al hacer clic derecho o pulsar un botón de “más”."),
    "accordion": T("Several sections stacked up, each one opens or closes when you click its title.",
                   "Varias secciones apiladas; cada una se abre o se cierra al pulsar su título."),
    "disclosure": T("A section with a little arrow that shows or hides extra details.",
                    "Una sección con una flechita que muestra u oculta detalles extra."),
    "tab-bar": T("The tabs at the top of an editor, one per open document.",
                 "Las pestañas de arriba de un editor, una por documento abierto."),
    "breadcrumbs": T("Shows where you are, step by step: Folder › Subfolder › File.",
                     "Muestra dónde estás, paso a paso: Carpeta › Subcarpeta › Archivo."),
    "toolbar": T("A thin bar with the actions of what you are looking at.",
                 "Una barra fina con las acciones de lo que estás viendo."),
    "layer": T("Puts something on top of the screen, like a search box, and closes it if you click outside.",
               "Pone algo encima de la pantalla, como un buscador, y lo cierra si pulsas fuera."),
    "modal": T("A window inside the window that asks for your attention before you go on.",
               "Una ventana dentro de la ventana que pide tu atención antes de seguir."),
    "popover": T("A small floating box that appears next to where you clicked, like a right-click menu.",
                 "Una cajita flotante que aparece junto a donde pulsaste, como un menú de clic derecho."),
    "command-palette": T("A search box for every action of the app: type what you want to do and press Enter.",
                         "Un buscador de todas las acciones de la app: escribe lo que quieres hacer y pulsa Enter."),
    "picker": T("A floating search box with a list of results that narrows as you type.",
                "Un buscador flotante con una lista de resultados que se reduce mientras escribes."),
    "dialog-layer": T("Darkens the app and shows a dialog in the middle, so the question can't be missed.",
                      "Oscurece la app y muestra un diálogo en el centro, para que la pregunta no pase desapercibida."),
    "alert": T("A message box with a single OK button.", "Una caja de mensaje con un solo botón de Aceptar."),
    "confirm": T("Asks “are you sure?” before doing something that can't be undone.",
                 "Pregunta “¿seguro?” antes de hacer algo que no se puede deshacer."),
    "prompt": T("A small box that asks you to type something, like a new name for a file.",
                "Una cajita que te pide escribir algo, como un nombre nuevo para un archivo."),
    "choice": T("A question with several possible answers, each one a button.",
                "Una pregunta con varias respuestas posibles, cada una un botón."),
    "unsaved-changes": T("The “Save your changes before closing?” question.",
                         "La pregunta “¿Guardar los cambios antes de cerrar?”."),
    "workspace": T("The whole layout of an editor-like window: bar on top, side panels, the main area and a bar at the bottom.",
                   "Toda la disposición de una ventana tipo editor: barra arriba, paneles laterales, la zona principal y una barra abajo."),
    "title-bar": T("The bar at the very top of the window, with the project name and quick buttons.",
                   "La barra de lo más alto de la ventana, con el nombre del proyecto y botones rápidos."),
    "window-frame": T("Draws the window's own top bar, with its menus and minimize / maximize / close buttons.",
                      "Dibuja la barra superior de la propia ventana, con sus menús y los botones de minimizar, maximizar y cerrar."),
    "status-bar": T("The thin bar at the bottom of the window with small facts: errors, line number, language.",
                    "La barra fina de abajo de la ventana con datos pequeños: errores, número de línea, lenguaje."),
    "panel": T("A side area of the window, like the file list on the left, that you can make wider or narrower.",
               "Una zona lateral de la ventana, como la lista de archivos de la izquierda, que puedes ensanchar o estrechar."),
    "panel-header": T("The title row of a side panel, with its buttons.", "La fila de título de un panel lateral, con sus botones."),
    "split": T("Two areas side by side (or one above the other) with a line you drag to resize them.",
               "Dos zonas lado a lado (o una encima de otra) con una línea que arrastras para cambiar su tamaño."),
    "editor": T("A box for writing code, with colors, line numbers and everything a programmer expects.",
                "Una caja para escribir código, con colores, números de línea y todo lo que espera un programador."),
    "terminal": T("Shows the text a program prints, with its colors, like a terminal window.",
                  "Muestra el texto que imprime un programa, con sus colores, como una ventana de terminal."),
    "console": T("A list of messages from the app (info, warnings, errors) that you can filter and copy.",
                 "Una lista de mensajes de la app (información, avisos, errores) que puedes filtrar y copiar."),
    "markdown": T("Shows formatted text (titles, lists, links) written in the simple Markdown format.",
                  "Muestra texto con formato (títulos, listas, enlaces) escrito en el formato sencillo Markdown."),
    "shortcuts": T("A searchable list of all the keyboard shortcuts of an app.",
                   "Una lista con buscador de todos los atajos de teclado de una app."),
    "about": T("The “About this app” box: name, version and links.", "La caja “Acerca de esta app”: nombre, versión y enlaces."),
    "reference-browser": T("A help window with the documentation inside the app, searchable and offline.",
                           "Una ventana de ayuda con la documentación dentro de la app, con buscador y sin conexión."),
    "row": T("Puts things side by side, from left to right.", "Pone las cosas una al lado de la otra, de izquierda a derecha."),
    "column": T("Puts things one under the other, from top to bottom.", "Pone las cosas una debajo de la otra, de arriba abajo."),
    "container": T("A box around one thing, to give it a size, a margin, a background or a border.",
                   "Una caja alrededor de una cosa, para darle un tamaño, un margen, un fondo o un borde."),
    "stack": T("Puts things on top of each other, like sheets of paper.", "Pone las cosas unas encima de otras, como hojas de papel."),
    "grid": T("Arranges things in rows and columns, like tiles on a wall.", "Ordena las cosas en filas y columnas, como azulejos en una pared."),
    "flex": T("Spreads things along a line: packed together, evenly spaced, or with one that grows.",
              "Reparte las cosas a lo largo de una línea: juntas, con el mismo espacio o con una que crece."),
    "scrollable": T("Lets you scroll content that doesn't fit, with a scroll bar.",
                    "Te deja desplazar el contenido que no cabe, con una barra de desplazamiento."),
    "resizable": T("A panel with an edge you can drag to make it bigger or smaller.",
                   "Un panel con un borde que puedes arrastrar para hacerlo más grande o más pequeño."),
    "spacing": T("Empty space: a fixed gap, or a spring that pushes things apart.",
                 "Espacio vacío: un hueco fijo, o un muelle que separa las cosas."),
    "responsive": T("Changes the layout depending on how much room there is, like a phone versus a monitor.",
                    "Cambia la disposición según el espacio que haya, como un móvil frente a un monitor."),
    "anchor-layout": T("Places things exactly where you put them, and says which corner each one sticks to when the window grows.",
                       "Coloca las cosas justo donde las pones y dice a qué esquina se pega cada una cuando la ventana crece."),
    "text": T("Text with any size, color and font you choose.", "Texto con el tamaño, el color y la fuente que elijas."),
    "icon": T("Small pictures (a folder, a bell, a gear) from a library of more than 1,500.",
              "Dibujos pequeños (una carpeta, una campana, un engranaje) de una biblioteca de más de 1.500."),
    "image": T("Shows a picture from a file: a photo, a logo, a screenshot.",
               "Muestra una imagen de un archivo: una foto, un logo, una captura."),
    "rich-text": T("A sentence where some words are bold, colored or links.",
                   "Una frase en la que algunas palabras van en negrita, de color o son enlaces."),
    "qr-code": T("A square barcode a phone camera can read, for sharing a link.",
                 "Un código de barras cuadrado que lee la cámara de un móvil, para compartir un enlace."),
    "canvas": T("A blank sheet to draw shapes, lines and text on, for charts and games.",
                "Una hoja en blanco para dibujar formas, líneas y texto, para gráficos y juegos."),
    "animation": T("Makes things move: fade in, slide, bounce or glow, without extra work.",
                   "Hace que las cosas se muevan: aparecer, deslizarse, rebotar o brillar, sin trabajo extra."),
    "shader": T("A surface painted by the graphics card, for moving backgrounds and visual effects.",
                "Una superficie pintada por la tarjeta gráfica, para fondos en movimiento y efectos visuales."),
    "effects": T("Glows, frosted glass and transparency you can add to any box.",
                 "Brillos, cristal esmerilado y transparencia que puedes añadir a cualquier caja."),
}

# ----------------------------------------------------------------------------------------- variants
# One shot per item, cropped to the component. Captions that look like code (``variant="ghost"``) are
# shown as code: they are the one argument that makes the difference.

_VARIANT = T("Variant", "Variante")
_SIZE = T("Size", "Tamaño")
_STATE = T("State", "Estado")
_COLOR = T("Color", "Color")
_TINT = T("Tint", "Tinte")
_KIND = T("Kind", "Tipo")
_CONTENT = T("Content", "Contenido")
_OPTIONS = T("Options", "Opciones")
_BASE = T("Base widget", "Widget base")
_BASE_TEXT = T("The `pz.*` widget underneath: no theme, every color and size is yours.",
               "El widget `pz.*` de debajo: sin tema, todos los colores y tamaños son tuyos.")
_HOVER = T("Drawn as the pointer shows it: tooltips only open on hover.",
           "Dibujado tal como lo muestra el puntero: los tooltips solo se abren al pasar el ratón.")

_MD = '"import pyzed as pz\\n\\n\\ndef main():\\n    pz.run(App)\\n"'
_PY = '''"class Counter(pz.App):\\n    count = 0\\n\\n    def view(self):\\n        return ui.button('Add', self.add)"'''

VARIANTS = {
    # ------------------------------------------------------------------------------------ actions
    "button": [
        V(_VARIANT, [
            ('variant="filled"', 'ui.button("Filled", on_press)'),
            ('variant="ghost"', 'ui.button("Ghost", on_press, variant="ghost")'),
            ('variant="subtle"', 'ui.button("Subtle", on_press, variant="subtle")'),
            ('variant="outline"', 'ui.button("Outline", on_press, variant="outline")'),
            ('variant="solid"', 'ui.button("Solid", on_press, variant="solid")'),
            ('variant="tinted"', 'ui.button("Tinted", on_press, variant="tinted")'),
        ], T("`filled` is the default; use `solid` for the one main action of a screen.",
             "`filled` es la de por defecto; usa `solid` para la única acción principal de una pantalla.")),
        V(T("Semantic colors", "Colores semánticos"), [
            ('variant="accent"', 'ui.button("Upgrade", on_press, variant="accent", icon="sparkles")'),
            ('variant="success"', 'ui.button("Done", on_press, variant="success", icon="check")'),
            ('variant="warning"', 'ui.button("Careful", on_press, variant="warning", icon="triangle-alert")'),
            ('variant="error"', 'ui.button("Delete", on_press, variant="error", icon="trash-2")'),
            ('variant="info"', 'ui.button("Details", on_press, variant="info", icon="info")'),
            ('variant="solid", tint="error"', 'ui.button("Delete forever", on_press, variant="solid", tint="error")'),
        ], T("A color name as `variant` gives a tinted button; `tint=` colors a `solid` one.",
             "Un nombre de color como `variant` da un botón teñido; `tint=` colorea uno `solid`.")),
        V(_SIZE, [
            ('size="xs"', 'ui.button("Extra small", on_press, size="xs")'),
            ('size="sm"', 'ui.button("Small", on_press, size="sm")'),
            ('size="md"', 'ui.button("Medium", on_press, size="md")'),
            ('size="lg"', 'ui.button("Large", on_press, size="lg")'),
        ]),
        V(_CONTENT, [
            ('icon="save"', 'ui.button("Save", on_press, icon="save")'),
            ('icon_position="end"', 'ui.button("Next", on_press, icon="arrow-right", icon_position="end")'),
            ('keys="ctrl-s"', 'ui.button("Save", on_press, icon="save", keys="ctrl-s")'),
            ('icon_color="success"', 'ui.button("Online", on_press, icon="circle", icon_color="success")'),
            (T("Icon only", "Solo icono"), 'ui.button(icon="plus", on_press=on_press)'),
        ]),
        V(_STATE, [
            ('selected=True', 'ui.button("Selected", on_press, selected=True)'),
            ('disabled=True', 'ui.button("Disabled", on_press, disabled=True)'),
            (T("No on_press", "Sin on_press"), 'ui.button("Not wired yet")'),
            ('full_width=True', 'pz.container(ui.button("Sign in", on_press, variant="solid", full_width=True), width=280)'),
        ], T("A button without `on_press` is drawn disabled, so unfinished actions look unfinished.",
             "Un botón sin `on_press` se dibuja deshabilitado, así las acciones sin terminar lo parecen.")),
        V(T("Style overrides", "Estilo propio"), [
            ('shadow=', 'ui.button("Lifted", on_press, variant="solid", shadow=("#00000066", (0, 4), 12))'),
            ('bg=, color=', 'ui.button("Custom", on_press, bg="#c678dd", hover_bg="#d08ae6", color="#ffffff")'),
            ('border_color=', 'ui.button("Gold border", on_press, variant="outline", border_color="#e5c07b")'),
            ('radius=999', 'ui.button("Pill", on_press, variant="solid", radius=999)'),
        ], T("The style arguments of `pz.button` (`bg`, `hover_bg`, `pressed_bg`, `color`, `border_color`, `shadow`, `radius`, `padding`) replace the theme's values for that button only.",
             "Los argumentos de estilo de `pz.button` (`bg`, `hover_bg`, `pressed_bg`, `color`, `border_color`, `shadow`, `radius`, `padding`) reemplazan los valores del tema solo en ese botón.")),
        V(_BASE, [
            ('pz.button', 'pz.button("pz.button", on_press, padding=(6, 14), bg="#3a7bc8", color="#ffffff", radius=6)'),
            (T("Any content", "Cualquier contenido"),
             'pz.button(pz.row([pz.icon("heart", size=14), pz.text("Like")], spacing=6, align="center"), on_press,\n'
             '          padding=(6, 12), bg="#c678dd22", color="#c678dd", border_color="#c678dd", border_width=1, radius=999)'),
        ], _BASE_TEXT),
    ],
    "icon-button": [
        V(_SIZE, [
            ('size="xs"', 'ui.icon_button("star", on_press, size="xs")'),
            ('size="sm"', 'ui.icon_button("star", on_press, size="sm")'),
            ('size="md"', 'ui.icon_button("star", on_press, size="md")'),
            ('size="lg"', 'ui.icon_button("star", on_press, size="lg")'),
        ]),
        V(_VARIANT, [
            ('variant="ghost"', 'ui.icon_button("settings", on_press)'),
            ('variant="filled"', 'ui.icon_button("settings", on_press, variant="filled")'),
            ('variant="outline"', 'ui.icon_button("settings", on_press, variant="outline")'),
            ('variant="solid"', 'ui.icon_button("settings", on_press, variant="solid")'),
            ('variant="tinted"', 'ui.icon_button("settings", on_press, variant="tinted")'),
        ]),
        V(_COLOR, [
            ('color="accent"', 'ui.icon_button("sparkles", on_press, color="accent")'),
            ('color="success"', 'ui.icon_button("circle-check", on_press, color="success")'),
            ('color="warning"', 'ui.icon_button("triangle-alert", on_press, color="warning")'),
            ('color="error"', 'ui.icon_button("trash-2", on_press, color="error", variant="outline")'),
        ]),
        V(_STATE, [
            ('selected=True', 'ui.icon_button("panel-left", on_press, selected=True)'),
            ('disabled=True', 'ui.icon_button("lock", on_press, disabled=True)'),
            ('tooltip="Search"', 'ui.icon_button("search", on_press, tooltip="Search")',
             {"draw": 'shown_tooltip(ui.icon_button("search", on_press), "Search")'}),
        ], _HOVER),
    ],
    "split-button": [
        V(_VARIANT, [
            ('variant="filled"', 'ui.split_button("Run", on_run, on_menu, icon="play")'),
            ('variant="ghost"', 'ui.split_button("Run", on_run, on_menu, icon="play", variant="ghost")'),
            ('variant="outline"', 'ui.split_button("Run", on_run, on_menu, icon="play", variant="outline")'),
            ('variant="solid"', 'ui.split_button("Deploy", on_deploy, on_menu, icon="rocket", variant="solid")'),
        ]),
        V(_SIZE, [
            ('size="sm"', 'ui.split_button("Build", on_build, on_menu, size="sm")'),
            ('size="md"', 'ui.split_button("Build", on_build, on_menu, size="md")'),
            ('size="lg"', 'ui.split_button("Build", on_build, on_menu, size="lg")'),
        ]),
        V(_CONTENT, [
            (T("Text only", "Solo texto"), 'ui.split_button("Merge", on_merge, on_menu)'),
            ('icon="git-merge"', 'ui.split_button("Merge", on_merge, on_menu, icon="git-merge")'),
        ]),
    ],
    "toggle-group": [
        V(_OPTIONS, [
            (T("Two options", "Dos opciones"), 'ui.toggle_group([("list", "list"), ("grid", "layout-grid")], "list", on_select)'),
            (T("Three options", "Tres opciones"),
             'ui.toggle_group([("left", "align-left"), ("center", "align-center"), ("right", "align-right")],\n'
             '                "center", on_select)'),
            (T("Four options", "Cuatro opciones"),
             'ui.toggle_group([("b", "bold"), ("i", "italic"), ("u", "underline"), ("s", "strikethrough")],\n'
             '                "b", on_select)'),
        ]),
        V(T("Selection", "Selección"), [
            ('selected="left"', 'ui.toggle_group([("left", "align-left"), ("center", "align-center"), ("right", "align-right")],\n                "left", on_select)'),
            ('selected="right"', 'ui.toggle_group([("left", "align-left"), ("center", "align-center"), ("right", "align-right")],\n                "right", on_select)'),
            ('selected=None', 'ui.toggle_group([("left", "align-left"), ("center", "align-center"), ("right", "align-right")],\n                None, on_select)'),
        ]),
    ],
    "chip": [
        V(_KIND, [
            (T("Static", "Estático"), 'ui.chip("python")'),
            ('on_press=', 'ui.chip("rust", on_press=on_filter)'),
            ('selected=True', 'ui.chip("python", on_press=on_filter, selected=True)'),
            ('on_remove=', 'ui.chip("iced", on_remove=on_remove)'),
        ]),
        V(_CONTENT, [
            ('icon="tag"', 'ui.chip("design", icon="tag")'),
            (T("Icon and remove", "Icono y quitar"), 'ui.chip("ada@example.com", icon="user", on_remove=on_remove)'),
            (T("Selected with icon", "Elegido con icono"), 'ui.chip("favorites", icon="star", selected=True, on_press=on_filter)'),
        ]),
    ],
    "mouse-area": [
        V(T("Cursor", "Cursor"), [
            ('cursor="pointer"', 'pz.mouse_area(ui.card(ui.label("Click me"), width=180), on_press=on_open, cursor="pointer")'),
            ('cursor="grab"', 'pz.mouse_area(ui.card(ui.label("Drag me"), width=180), on_move=on_drag, cursor="grab")'),
            ('cursor="crosshair"', 'pz.mouse_area(pz.canvas([draw.circle(60, 40, 24, fill="#74ade8")], width=120, height=80),\n              on_press=on_pick, cursor="crosshair")'),
        ], T("The pointer shape is only visible with a real mouse; the shot shows the wrapped widget.",
             "La forma del puntero solo se ve con un ratón real; la captura muestra el widget envuelto.")),
        V(T("Hover content", "Contenido en hover"), [
            (T("At rest", "En reposo"), 'pz.hover(ui.list_item("notes.py", on_open, icon="file-text"),\n         pz.container(ui.icon_button("x", on_close, size="xs"), align_x="end", width="fill"))',
             {"draw": 'pz.container(ui.list_item("notes.py", on_open, icon="file-text"), width=240)'}),
            (T("With the pointer over it", "Con el puntero encima"), 'pz.hover(ui.list_item("notes.py", on_open, icon="file-text"),\n         pz.container(ui.icon_button("x", on_close, size="xs"), align_x="end", width="fill"))',
             {"draw": 'pz.container(pz.stack([ui.list_item("notes.py", on_open, icon="file-text", selected=True),\n    pz.container(ui.icon_button("x", on_close, size="xs"), align_x="end", align_y="center", width="fill", height=26)]), width=240)'}),
        ], T("`pz.hover` only draws its `top` while the pointer is over it: here, the close button of a row.",
             "`pz.hover` solo dibuja su `top` mientras el puntero está encima: aquí, el botón de cerrar de una fila.")),
    ],
    # ------------------------------------------------------------------------------------ display
    "label": [
        V(_SIZE, [
            ('size="xs"', 'ui.label("Extra small", size="xs")'),
            ('size="sm"', 'ui.label("Small", size="sm")'),
            ('size="md"', 'ui.label("Medium", size="md")'),
            ('size="lg"', 'ui.label("Large", size="lg")'),
            ('size="xl"', 'ui.label("Extra large", size="xl")'),
            ('size="2xl"', 'ui.label("Huge", size="2xl")'),
        ], T("Named sizes follow the theme's font size; a number is a size in pixels.",
             "Los tamaños con nombre siguen el tamaño de fuente del tema; un número es un tamaño en píxeles.")),
        V(_COLOR, [
            ('color="text"', 'ui.label("Text")'),
            ('ui.muted', 'ui.muted("Muted text")'),
            ('color="accent"', 'ui.label("Accent", color="accent")'),
            ('color="success"', 'ui.label("Success", color="success")'),
            ('color="warning"', 'ui.label("Warning", color="warning")'),
            ('color="error"', 'ui.label("Error", color="error")'),
            ('color="#c678dd"', 'ui.label("Any hex color", color="#c678dd")'),
        ]),
        V(T("Weight and style", "Peso y estilo"), [
            ('weight="normal"', 'ui.label("Normal", weight="normal", size="lg")'),
            ('weight="medium"', 'ui.label("Medium", weight="medium", size="lg")'),
            ('weight="semibold"', 'ui.label("Semibold", weight="semibold", size="lg")'),
            ('weight="bold"', 'ui.label("Bold", weight="bold", size="lg")'),
            ('italic=True', 'ui.label("Italic", italic=True, size="lg")'),
            ('mono=True', 'ui.label("def mono(): ...", mono=True)'),
        ]),
    ],
    "heading": [
        V(T("Level", "Nivel"), [
            ('level=1', 'ui.heading("Project settings")'),
            ('level=2', 'ui.heading("Project settings", level=2)'),
            ('level=3', 'ui.heading("Project settings", level=3)'),
            ('level=4', 'ui.heading("Project settings", level=4)'),
        ]),
        V(_COLOR, [
            ('color="accent"', 'ui.heading("Welcome back", level=2, color="accent")'),
            (T("With a muted line", "Con una línea discreta"), 'pz.column([ui.heading("Billing", level=2), ui.muted("Invoices and payment methods.")], spacing=4)'),
        ]),
    ],
    "badge": [
        V(_TINT, [
            ('tint="accent"', 'ui.badge("accent")'),
            ('tint="success"', 'ui.badge("passed", tint="success")'),
            ('tint="warning"', 'ui.badge("pending", tint="warning")'),
            ('tint="error"', 'ui.badge("failed", tint="error")'),
            ('tint="info"', 'ui.badge("info", tint="info")'),
            ('tint="#c678dd"', 'ui.badge("custom", tint="#c678dd")'),
        ]),
        V(_VARIANT, [
            ('variant="soft"', 'ui.badge("soft")'),
            ('variant="solid"', 'ui.badge("solid", variant="solid")'),
            ('variant="outline"', 'ui.badge("outline", variant="outline")'),
        ]),
        V(T("With an icon", "Con icono"), [
            ('icon="sparkles"', 'ui.badge("new", icon="sparkles")'),
            ('icon="circle-x"', 'ui.badge("3 errors", tint="error", icon="circle-x")'),
            ('variant="solid", icon=', 'ui.badge("verified", tint="success", variant="solid", icon="check")'),
        ]),
    ],
    "indicator": [
        V(_COLOR, [
            ('"accent"', 'ui.indicator()'),
            ('"success"', 'ui.indicator("success")'),
            ('"warning"', 'ui.indicator("warning")'),
            ('"error"', 'ui.indicator("error")'),
            ('"text_muted"', 'ui.indicator("text_muted")'),
            ('"#c678dd"', 'ui.indicator("#c678dd")'),
        ]),
        V(_SIZE, [
            ('size=6', 'ui.indicator("success", size=6)'),
            ('size=10', 'ui.indicator("success", size=10)'),
            ('size=14', 'ui.indicator("success", size=14)'),
        ]),
        V(T("Next to text", "Junto a un texto"), [
            (T("Online", "Conectado"), 'pz.row([ui.indicator("success"), ui.label("Ana is online")], spacing=8, align="center")'),
            (T("Unsaved", "Sin guardar"), 'pz.row([ui.label("notes.py"), ui.indicator(size=8)], spacing=6, align="center")'),
        ]),
    ],
    "kbd": [
        V(T("Keys", "Teclas"), [
            (T("One key", "Una tecla"), 'ui.kbd("enter")'),
            (T("Combination", "Combinación"), 'ui.kbd("ctrl-shift-p")'),
            (T("Chord", "Acorde"), 'ui.kbd("ctrl-k ctrl-s")'),
            (T("Special keys", "Teclas especiales"), 'pz.row([ui.kbd("escape"), ui.kbd("tab"), ui.kbd("backspace"), ui.kbd("up")], spacing=6)'),
        ], T("Write shortcuts as `\"ctrl-s\"`; on macOS `ctrl` becomes ⌃ and `cmd` ⌘ automatically.",
             "Escribe los atajos como `\"ctrl-s\"`; en macOS `ctrl` pasa a ⌃ y `cmd` a ⌘ solo.")),
        V(_SIZE, [
            ('size="xs"', 'ui.kbd("ctrl-p", size="xs")'),
            ('size="sm"', 'ui.kbd("ctrl-p", size="sm")'),
        ]),
    ],
    "avatar": [
        V(T("Collaborator color", "Color de colaborador"), [
            ('index=0', 'ui.avatar("AL", index=0)'),
            ('index=1', 'ui.avatar("KV", index=1)'),
            ('index=2', 'ui.avatar("MZ", index=2)'),
            ('index=3', 'ui.avatar("JD", index=3)'),
            ('index=4', 'ui.avatar("SR", index=4)'),
            ('index=5', 'ui.avatar("PB", index=5)'),
        ]),
        V(_SIZE, [
            ('size=18', 'ui.avatar("KV", size=18)'),
            ('size=22', 'ui.avatar("KV", size=22)'),
            ('size=32', 'ui.avatar("KV", size=32)'),
            ('size=48', 'ui.avatar("KV", size=48)'),
        ]),
        V(_COLOR, [
            ('color="#c678dd"', 'ui.avatar("PZ", color="#c678dd", size=32)'),
            ('color="#e5c07b"', 'ui.avatar("UI", color="#e5c07b", size=32)'),
        ]),
    ],
    "tooltip": [
        V(T("Position", "Posición"), [
            ('position="bottom"', 'ui.tooltip(ui.icon_button("save", on_save), "Save")',
             {"draw": 'shown_tooltip(ui.icon_button("save", on_save), "Save")'}),
            ('position="top"', 'ui.tooltip(ui.icon_button("save", on_save), "Save", position="top")',
             {"draw": 'shown_tooltip(ui.icon_button("save", on_save), "Save", position="top")'}),
            ('position="right"', 'ui.tooltip(ui.icon_button("save", on_save), "Save", position="right")',
             {"draw": 'shown_tooltip(ui.icon_button("save", on_save), "Save", position="right")'}),
            ('position="left"', 'ui.tooltip(ui.icon_button("save", on_save), "Save", position="left")',
             {"draw": 'shown_tooltip(ui.icon_button("save", on_save), "Save", position="left")'}),
        ], _HOVER),
        V(_CONTENT, [
            ('keys="ctrl-s"', 'ui.tooltip(ui.button("Save", on_save), "Save the file", keys="ctrl-s")',
             {"draw": 'shown_tooltip(ui.button("Save", on_save), "Save the file", keys="ctrl-s")'}),
            ('icon_button(tooltip=)', 'ui.icon_button("settings", on_settings, tooltip="Settings")',
             {"draw": 'shown_tooltip(ui.icon_button("settings", on_settings), "Settings")'}),
        ], _HOVER),
    ],
    "divider": [
        V(T("Direction", "Dirección"), [
            (T("Horizontal", "Horizontal"), 'pz.column([ui.label("Account"), ui.divider(), ui.label("Sign out")], spacing=8, width=220)'),
            ('vertical=True', 'pz.row([ui.label("Edit"), ui.divider(vertical=True), ui.label("View")], spacing=10, height=18)'),
        ]),
        V(_COLOR, [
            ('color="accent"', 'pz.container(ui.divider(color="accent"), width=220)'),
            ('pz.rule(thickness=3)', 'pz.container(pz.rule(color="#e5c07b", thickness=3), width=220)'),
        ]),
    ],
    "card": [
        V(_CONTENT, [
            (T("Content only", "Solo contenido"), 'ui.card(ui.muted("A bordered surface."), width=260)'),
            ('title=', 'ui.card(ui.muted("Three files changed."), title="Changes", width=260)'),
            ('title=, actions=', 'ui.card(ui.muted("Three files changed."), title="Changes",\n        actions=[ui.icon_button("ellipsis", on_menu, size="sm")], width=260)'),
        ]),
        V(T("Padding", "Relleno"), [
            ('padding=8', 'ui.card(ui.label("Compact"), padding=8)'),
            ('padding=16', 'ui.card(ui.label("Default"))'),
            ('padding=28', 'ui.card(ui.label("Roomy"), padding=28)'),
        ]),
    ],
    # -------------------------------------------------------------------------------------- forms
    "input": [
        V(_CONTENT, [
            ('placeholder=', 'ui.input("", on_input, placeholder="Project name", width=260)'),
            (T("With a value", "Con valor"), 'ui.input("Pyzed", on_input, width=260)'),
            ('icon="mail"', 'ui.input("ada@example.com", on_input, icon="mail", width=260)'),
            ('secure=True', 'ui.input("hunter2", on_input, secure=True, icon="lock", width=260)'),
        ]),
        V(_SIZE, [
            ('size="sm"', 'ui.input("Small", on_input, size="sm", width=260)'),
            ('size="md"', 'ui.input("Medium", on_input, size="md", width=260)'),
            ('size="lg"', 'ui.input("Large", on_input, size="lg", width=260)'),
        ]),
        V(T("Style", "Estilo"), [
            ('borderless=True', 'ui.input("Borderless", on_input, borderless=True, width=260)'),
            ('mono=True', 'ui.input("SELECT * FROM users", on_input, mono=True, width=260)'),
            (T("Read-only (no on_input)", "Solo lectura (sin on_input)"), 'ui.input("Can\'t edit me", width=260)'),
        ]),
        V(T("Validation", "Validación"), [
            (T("With an error", "Con un error"), 'ui.field("Email", ui.input("ada@", on_input, width=220), error="Enter a valid email")'),
        ], T("Show errors with [Field](/pyzed/library/field/)'s `error=`, next to the input.",
             "Muestra los errores con `error=` de [Campo de formulario](/pyzed/es/library/field/), junto al campo.")),
        V(_BASE, [
            ('pz.text_input', 'pz.text_input("", placeholder="pz.text_input", on_input=on_input, width=260, padding=8,\n              radius=8, border_color="#c678dd", focus_border_color="#e5c07b")'),
        ], _BASE_TEXT),
    ],
    "search-input": [
        V(_CONTENT, [
            (T("Empty", "Vacío"), 'ui.search_input("", on_query, width=260)'),
            (T("With a query", "Con búsqueda"), 'ui.search_input("button", on_query, width=260)'),
            ('placeholder=', 'ui.search_input("", on_query, placeholder="Search components…", width=260)'),
        ]),
        V(_SIZE, [
            ('size="sm"', 'ui.search_input("", on_query, size="sm", width=260)'),
            ('size="lg"', 'ui.search_input("", on_query, size="lg", width=260)'),
            ('borderless=True', 'ui.search_input("", on_query, borderless=True, width=260)'),
        ]),
    ],
    "checkbox": [
        V(_STATE, [
            ('checked=True', 'ui.checkbox(True, on_toggle, label="Format on save")'),
            ('checked=False', 'ui.checkbox(False, on_toggle, label="Format on save")'),
            (T("Read-only (no on_toggle)", "Solo lectura (sin on_toggle)"), 'ui.checkbox(True, label="Managed by your admin")'),
        ]),
        V(_CONTENT, [
            (T("No label", "Sin etiqueta"), 'ui.checkbox(True, on_toggle)'),
            (T("A list of options", "Una lista de opciones"), 'pz.column([ui.checkbox(True, on_toggle, label="Python"),\n           ui.checkbox(False, on_toggle, label="Rust"),\n           ui.checkbox(True, on_toggle, label="TypeScript")], spacing=8)'),
        ]),
        V(_BASE, [
            ('pz.checkbox', 'pz.checkbox(True, "pz.checkbox", on_toggle=on_toggle, accent="#c678dd", size=18)'),
        ], _BASE_TEXT),
    ],
    "switch": [
        V(_STATE, [
            (T("On", "Activado"), 'ui.switch(True, on_toggle, label="Autosave")'),
            (T("Off", "Desactivado"), 'ui.switch(False, on_toggle, label="Autosave")'),
            (T("Read-only (no on_toggle)", "Solo lectura (sin on_toggle)"), 'ui.switch(True, label="Sync (managed)")'),
            (T("No label", "Sin etiqueta"), 'ui.switch(True, on_toggle)'),
        ]),
        V(_BASE, [
            ('pz.toggler', 'pz.toggler(True, "pz.toggler", on_toggle=on_toggle, accent="#a1c181", size=22)'),
        ], _BASE_TEXT),
    ],
    "slider": [
        V(T("Value", "Valor"), [
            ('0.0', 'ui.slider(0.0, on_change, width=240)'),
            ('0.35', 'ui.slider(0.35, on_change, width=240)'),
            ('1.0', 'ui.slider(1.0, on_change, width=240)'),
        ]),
        V(T("Range and step", "Rango y paso"), [
            ('min=0, max=100, step=1', 'ui.slider(70, on_change, min=0, max=100, step=1, width=240)'),
            ('step=10', 'pz.column([ui.slider(40, on_change, min=0, max=100, step=10, width=240),\n           ui.muted("40 %")], spacing=6, align="center")'),
        ]),
        V(_BASE, [
            ('pz.slider', 'pz.slider(0, 100, 60, on_change=on_change, width=240, accent="#e5c07b", knob_color="#ffffff")'),
            ('pz.vertical_slider', 'pz.vertical_slider(0, 100, 60, on_change=on_change, height=120, accent="#56b6c2")'),
        ], _BASE_TEXT),
    ],
    "number-field": [
        V(_OPTIONS, [
            (T("Plain", "Simple"), 'ui.number_field(4, on_change, min=1, max=8)'),
            ('suffix="px"', 'ui.number_field(14, on_change, min=8, max=32, suffix="px")'),
            ('step=0.1', 'ui.number_field(0.5, on_change, step=0.1, suffix="s", width=140)'),
            ('align="start"', 'ui.number_field(8080, on_change, min=1, max=65535, align="start", width=140)'),
        ]),
        V(T("Limits", "Límites"), [
            (T("At the minimum", "En el mínimo"), 'ui.number_field(1, on_change, min=1, max=8)'),
            (T("At the maximum", "En el máximo"), 'ui.number_field(8, on_change, min=1, max=8)'),
        ], T("At a limit its button is dimmed and the value can't go further.",
             "En un límite su botón se atenúa y el valor no puede ir más allá.")),
    ],
    "select": [
        V(_STATE, [
            (T("With a value", "Con valor"), 'ui.select(["Python", "Rust", "TypeScript"], "Rust", on_select, width=200)'),
            ('placeholder=', 'ui.select(["UTF-8", "Latin-1"], None, on_select, placeholder="Encoding…", width=200)'),
            (T("Read-only (no on_select)", "Solo lectura (sin on_select)"), 'ui.select(["One Dark"], "One Dark", width=200)'),
        ]),
        V(_SIZE, [
            ('size="sm"', 'ui.select(["Python", "Rust"], "Python", on_select, size="sm", width=200)'),
            ('size="md"', 'ui.select(["Python", "Rust"], "Python", on_select, size="md", width=200)'),
            ('size="lg"', 'ui.select(["Python", "Rust"], "Python", on_select, size="lg", width=200)'),
        ]),
        V(_BASE, [
            ('pz.pick_list', 'pz.pick_list(["Small", "Medium", "Large"], "Medium", on_select, width=200,\n             bg="#2b2140", color="#e9d5ff", border_color="#c678dd", radius=8)'),
        ], _BASE_TEXT),
    ],
    "radio-group": [
        V(T("Direction", "Dirección"), [
            (T("Vertical", "Vertical"), 'ui.radio_group(["Spaces", "Tabs"], "Spaces", on_select)'),
            ('horizontal=True', 'ui.radio_group(["LF", "CRLF", "CR"], "LF", on_select, horizontal=True)'),
            ('spacing=16', 'ui.radio_group(["Small", "Medium", "Large"], "Medium", on_select, horizontal=True, spacing=16)'),
        ]),
        V(_OPTIONS, [
            (T("(value, label) pairs", "Pares (valor, etiqueta)"), 'ui.radio_group([("lf", "Unix (LF)"), ("crlf", "Windows (CRLF)")], "crlf", on_select)'),
            (T("Nothing selected", "Nada elegido"), 'ui.radio_group(["Yes", "No"], None, on_select, horizontal=True)'),
        ]),
        V(_BASE, [
            ('pz.radio', 'pz.row([pz.radio("Cats", True, on_select, accent="#e5c07b"),\n        pz.radio("Dogs", False, on_select, accent="#e5c07b")], spacing=16)'),
        ], _BASE_TEXT),
    ],
    "segmented": [
        V(_OPTIONS, [
            (T("Two options", "Dos opciones"), 'ui.segmented(["Code", "Preview"], "Code", on_select)'),
            (T("Three options", "Tres opciones"), 'ui.segmented(["Day", "Week", "Month"], "Week", on_select)'),
            (T("Five options", "Cinco opciones"), 'ui.segmented(["XS", "S", "M", "L", "XL"], "M", on_select)'),
        ]),
        V(T("Selection", "Selección"), [
            (T("First", "Primera"), 'ui.segmented(["Editor", "Terminal", "Both"], "Editor", on_select)'),
            (T("Last", "Última"), 'ui.segmented(["Editor", "Terminal", "Both"], "Both", on_select)'),
        ]),
    ],
    "field": [
        V(T("Control", "Control"), [
            (T("Switch", "Interruptor"), 'pz.container(ui.field("Autosave", ui.switch(True, on_toggle)), width=380)'),
            (T("Number field", "Campo numérico"), 'pz.container(ui.field("Font size", ui.number_field(14, on_change, suffix="px")), width=380)'),
            (T("Select", "Select"), 'pz.container(ui.field("Theme", ui.select(["One Dark", "One Light"], "One Dark", on_select, width=150)), width=380)'),
            (T("Input", "Campo de texto"), 'pz.container(ui.field("Name", ui.input("Pyzed", on_input, width=180)), width=380)'),
        ]),
        V(T("Help and errors", "Ayuda y errores"), [
            ('description=', 'pz.container(ui.field("Autosave", ui.switch(True, on_toggle), description="Saves when you switch tabs"), width=380)'),
            ('error=', 'pz.container(ui.field("Port", ui.number_field(80, on_change), error="Ports below 1024 need admin rights"), width=380)'),
        ]),
    ],
    "color-picker": [
        V(_OPTIONS, [
            (T("Everything", "Todo"), 'ui.ColorPicker(value="#3b82f6cc", on_change=on_change)', {"size": (420, 480)}),
            ('alpha=False, gradients=False, masks=False', 'ui.ColorPicker(value="#a1c181", alpha=False, gradients=False, masks=False,\n               on_change=on_change)', {"size": (420, 480)}),
            ('swatches=[...]', 'ui.ColorPicker(value="#e5c07b", gradients=False, masks=False,\n               swatches=["#e06c75", "#e5c07b", "#98c379", "#61afef", "#c678dd"], on_change=on_change)', {"size": (420, 520)}),
        ]),
        V(T("Swatches", "Muestras"), [
            (T("Color", "Color"), 'ui.color_swatch("#3b82f6", size=32)'),
            (T("With alpha", "Con alfa"), 'ui.color_swatch("#a1c181aa", size=32)'),
            ('pz.Gradient', 'ui.color_swatch(pz.Gradient(["#f97316", "#7c3aed"], angle=90), size=32)'),
            ('ui.checkerboard', 'ui.checkerboard(96, 48, size=8)'),
        ], T("A swatch draws any color, gradient or paint over a checkerboard, so transparency shows.",
             "Una muestra dibuja cualquier color, degradado o relleno sobre un damero, para que se vea la transparencia.")),
    ],
    "icon-picker": [
        V(T("Picker", "Selector"), [
            ('columns=8', 'ui.IconPicker(value="rocket", columns=8, height=180, on_change=on_change)', {"size": (480, 300)}),
            ('clearable=True', 'ui.IconPicker(value="heart", columns=8, height=180, clearable=True, on_change=on_change)', {"size": (480, 300)}),
        ]),
        V(T("Building blocks", "Piezas"), [
            ('ui.icon_grid', 'ui.icon_grid(pz.icons.search("arrow")[:24], on_pick, selected="arrow-right", columns=8, height=110)', {"size": (480, 200)}),
            ('ui.icon_picker_dialog', 'ui.icon_picker_dialog("rocket", on_pick, on_close=on_close, columns=8)', {"size": (520, 520)}),
        ]),
    ],
    # ----------------------------------------------------------------------------------- feedback
    "progress": [
        V(T("Value", "Valor"), [
            ('0.1', 'ui.progress(0.1, width=240)'),
            ('0.5', 'ui.progress(0.5, width=240)'),
            ('1.0', 'ui.progress(1.0, width=240)'),
            ('37, max=40', 'ui.progress(37, max=40, width=240)'),
        ]),
        V(_TINT, [
            ('tint="success"', 'ui.progress(0.7, tint="success", width=240)'),
            ('tint="warning"', 'ui.progress(0.7, tint="warning", width=240)'),
            ('tint="error"', 'ui.progress(0.7, tint="error", width=240)'),
        ]),
        V(T("Thickness", "Grosor"), [
            ('height=2', 'ui.progress(0.6, height=2, width=240)'),
            ('height=4', 'ui.progress(0.6, height=4, width=240)'),
            ('height=10', 'ui.progress(0.6, height=10, width=240)'),
        ]),
        V(_BASE, [
            ('pz.progress_bar', 'pz.progress_bar(64, max=100, width=240, height=12, accent="#c678dd", bg="#c678dd33", radius=6)'),
        ], _BASE_TEXT),
    ],
    "spinner": [
        V(_SIZE, [
            ('size=12', 'ui.spinner(size=12)'),
            ('size=16', 'ui.spinner()'),
            ('size=24', 'ui.spinner(size=24)'),
            ('size=36', 'ui.spinner(size=36)'),
        ]),
        V(_TINT, [
            ('tint="success"', 'ui.spinner(size=24, tint="success")'),
            ('tint="warning"', 'ui.spinner(size=24, tint="warning")'),
            ('tint="text_muted"', 'ui.spinner(size=24, tint="text_muted")'),
        ]),
        V(T("With text", "Con texto"), [
            (T("Inline", "En línea"), 'pz.row([ui.spinner(size=14), ui.muted("Indexing project…")], spacing=8, align="center")'),
            (T("In a button", "En un botón"), 'ui.button(pz.row([ui.spinner(size=12, tint="text"), pz.text("Saving")], spacing=6, align="center"))'),
        ]),
    ],
    "callout": [
        V(_TINT, [
            ('tint="info"', 'pz.container(ui.callout("Heads up", "Pyzed 0.5 is out."), width=380)'),
            ('tint="success"', 'pz.container(ui.callout("Synced", "All changes are saved.", tint="success"), width=380)'),
            ('tint="warning"', 'pz.container(ui.callout("Unsaved changes", "Save before closing.", tint="warning"), width=380)'),
            ('tint="error"', 'pz.container(ui.callout("Could not save", "The file is read-only.", tint="error"), width=380)'),
            ('tint="accent"', 'pz.container(ui.callout("Tip", "Ctrl+Shift+P opens the palette.", tint="accent", icon="lightbulb"), width=380)'),
        ], T("Each tint picks a matching icon; `icon=` chooses another.",
             "Cada tinte elige un icono acorde; `icon=` elige otro.")),
        V(_CONTENT, [
            (T("Title only", "Solo título"), 'pz.container(ui.callout("Read-only file"), width=380)'),
            ('actions=', 'pz.container(ui.callout("A new version is out", "Restart to update.",\n                        actions=[ui.button("Restart", on_restart, size="sm")]), width=380)'),
            ('on_dismiss=', 'pz.container(ui.callout("Welcome!", "Open a folder to start.", on_dismiss=on_dismiss), width=380)'),
        ]),
    ],
    "toast": [
        V(_KIND, [
            ('kind="info"', 'ui.toast("Update available", "Pyzed 0.5 is on PyPI.")'),
            ('kind="success"', 'ui.toast("Saved", "main.py was saved.", kind="success")'),
            ('kind="warning"', 'ui.toast("Low disk space", "2 GB left.", kind="warning")'),
            ('kind="error"', 'ui.toast("Could not connect", "Check your network.", kind="error")'),
        ]),
        V(_CONTENT, [
            (T("Title only", "Solo título"), 'ui.toast("Copied to clipboard", kind="success")'),
            ('actions=, on_dismiss=', 'ui.toast("Update available", "Restart to install it.",\n         actions=[ui.button("Restart", on_restart, size="sm")], on_dismiss=on_dismiss)'),
            ('icon="music"', 'ui.toast("Now playing", "Lo-fi beats", icon="music", width=280)'),
        ]),
    ],
    "empty-state": [
        V(_CONTENT, [
            (T("Title only", "Solo título"), 'ui.empty_state("No notifications")', {"size": (420, 200)}),
            (T("With a description", "Con descripción"), 'ui.empty_state("No results", "Try a different search.", icon="search")', {"size": (420, 220)}),
            ('actions=', 'ui.empty_state("No projects yet", "Create one to get started.", icon="folder-plus",\n               actions=[ui.button("New project", on_new, variant="solid", size="sm")])', {"size": (420, 260)}),
        ]),
    ],
    "count-badge": [
        V(T("Count", "Cuenta"), [
            ('3', 'ui.count_badge(3)'),
            ('42', 'ui.count_badge(42)'),
            ('120', 'ui.count_badge(120)'),
            ('max=9', 'ui.count_badge(12, max=9)'),
        ], T("Above `max` it shows `max+`.", "Por encima de `max` muestra `max+`.")),
        V(_TINT, [
            ('tint="success"', 'ui.count_badge(5, tint="success")'),
            ('tint="warning"', 'ui.count_badge(5, tint="warning")'),
            ('tint="error"', 'ui.count_badge(5, tint="error")'),
        ]),
        V(T("Next to an icon", "Junto a un icono"), [
            (T("Notifications", "Notificaciones"), 'pz.row([ui.icon_button("bell", on_press), ui.count_badge(7)], spacing=2, align="center")'),
        ]),
    ],
    "keybinding-hint": [
        V(T("Examples", "Ejemplos"), [
            (T("One key", "Una tecla"), 'ui.keybinding_hint("Search", "/")'),
            (T("Combination", "Combinación"), 'ui.keybinding_hint("Command palette", "ctrl-shift-p")'),
            (T("Chord", "Acorde"), 'ui.keybinding_hint("Keyboard shortcuts", "ctrl-k ctrl-s")'),
        ]),
    ],
}

_ROWS = '[{"name": "app.py", "lines": 512}, {"name": "theme.py", "lines": 730}, {"name": "ui.py", "lines": 1290}]'
_COLS = '[ui.Column("File", "name"), ui.Column("Lines", "lines", width=80, align="end")]'
_PATHS = '["src/main.rs", "src/app.rs", "src/ui/mod.rs", "src/ui/button.rs", "Cargo.toml"]'
_FRAME = {"size": (440, 220), "fill": True}

VARIANTS.update({
    # --------------------------------------------------------------------------------------- data
    "table": [
        V(_OPTIONS, [
            (T("Plain", "Simple"), 'pz.container(ui.table(' + _COLS + ',\n                      ' + _ROWS + '), width=320)', {"size": (480, 200)}),
            ('striped=True', 'pz.container(ui.table(' + _COLS + ',\n                      ' + _ROWS + ', striped=True), width=320)', {"size": (480, 200)}),
            ('selected=', 'rows = ' + _ROWS + '\npz.container(ui.table(' + _COLS + ', rows, selected=rows[1]), width=320)', {"size": (480, 200)}),
            ('sort_by=, descending=True', 'pz.container(ui.table(' + _COLS + ',\n                      ' + _ROWS + ', sort_by="Lines", descending=True,\n                      on_sort=on_sort), width=320)', {"size": (480, 200)}),
            ('row_height=24', 'pz.container(ui.table(' + _COLS + ',\n                      ' + _ROWS + ', row_height=24), width=320)', {"size": (480, 200)}),
        ]),
        V(T("Cells", "Celdas"), [
            ('render=', 'rows = [{"job": "build", "state": "passed"}, {"job": "lint", "state": "failed"}]\n'
                        'tint = {"passed": "success", "failed": "error"}\n'
                        'pz.container(ui.table([ui.Column("Job", "job"),\n'
                        '                       ui.Column("State", "state", width=110, render=lambda s: ui.badge(s, tint=tint[s]))],\n'
                        '                      rows), width=320)', {"size": (480, 180)}),
            ('key=lambda', 'people = [("Ana", 31), ("Luis", 27)]\n'
                           'pz.container(ui.table([ui.Column("Name", lambda p: p[0]),\n'
                           '                       ui.Column("Age", lambda p: p[1], width=70, align="end")], people), width=320)',
             {"size": (480, 160)}),
        ]),
    ],
    "virtual-list": [
        V(_OPTIONS, [
            (T("A million rows", "Un millón de filas"), 'pz.container(ui.virtual_list([f"row {i:,}" for i in range(1_000_000)],\n                             lambda r: ui.list_item(r, icon="file"), height=150), width=260)', {"size": (480, 220)}),
            ('item_height=20', 'pz.container(ui.virtual_list([f"[{i:06}] request handled" for i in range(100_000)],\n                             lambda line: pz.text(line, font="mono", size=12), item_height=20, height=150),\n             width=260)', {"size": (480, 220)}),
            ('spacing=6', 'pz.container(ui.virtual_list(list(range(10_000)), lambda i: ui.card(ui.label(f"Card {i}"), padding=8),\n                             item_height=40, spacing=6, height=150), width=260)', {"size": (480, 220)}),
        ]),
    ],
    "stat": [
        V(_CONTENT, [
            (T("Value only", "Solo valor"), 'ui.stat("Build time", "1m 12s", width=190)'),
            ('delta=12.5', 'ui.stat("Users", "1,284", delta=12.5, width=190)'),
            ('delta=-8.0', 'ui.stat("Errors", "37", delta=-8.0, width=190)'),
            ('trend=[...]', 'ui.stat("Revenue", "$9.4k", delta=4.2, trend=[3, 5, 4, 6, 8, 7, 9], width=190)'),
        ]),
    ],
    "sparkline": [
        V(_OPTIONS, [
            (T("Filled", "Relleno"), 'ui.sparkline([1, 4, 2, 6, 3, 7, 5, 8], width=200, height=40)'),
            ('fill=False', 'ui.sparkline([1, 4, 2, 6, 3, 7, 5, 8], width=200, height=40, fill=False)'),
            ('tint="error"', 'ui.sparkline([8, 6, 7, 4, 5, 3, 2, 1], width=200, height=40, tint="error")'),
            ('tint="success"', 'ui.sparkline([2, 3, 3, 5, 6, 8, 9, 12], width=200, height=40, tint="success")'),
        ]),
        V(_SIZE, [
            ('width=80, height=20', 'ui.sparkline([3, 5, 2, 6, 4, 7], width=80, height=20)'),
            ('width=280, height=64', 'ui.sparkline([3, 5, 2, 6, 4, 7, 5, 9, 6, 8], width=280, height=64)'),
        ]),
    ],
    "bar-chart": [
        V(_OPTIONS, [
            ('labels=', 'ui.bar_chart([12, 19, 8, 15, 22], labels=["M", "T", "W", "T", "F"], width=240, height=120)', {"size": (480, 200)}),
            (T("No labels", "Sin etiquetas"), 'ui.bar_chart([4, 8, 6, 9, 3, 7, 5, 10], width=240, height=100)', {"size": (480, 180)}),
            ('tint="success"', 'ui.bar_chart([5, 9, 7, 12], labels=["Q1", "Q2", "Q3", "Q4"], width=240, height=120, tint="success")', {"size": (480, 200)}),
            ('tint="warning"', 'ui.bar_chart([30, 12, 18], labels=["cpu", "io", "net"], width=240, height=120, tint="warning")', {"size": (480, 200)}),
        ]),
    ],
    "donut": [
        V(_OPTIONS, [
            (T("Default", "Por defecto"), 'ui.donut([60, 25, 15], label="60%")'),
            ('colors=', 'ui.donut([45, 35, 20], colors=["#e5c07b", "#c678dd", "#56b6c2"], label="3")'),
            ('thickness=6', 'ui.donut([70, 30], thickness=6, label="70%")'),
            ('size=140, thickness=24', 'ui.donut([40, 30, 20, 10], size=140, thickness=24)', {"size": (480, 220)}),
            ('size=110, label="82%"', 'ui.donut([82, 18], size=110, label="82%")', {"size": (480, 200)}),
        ]),
    ],
    "diff-stat": [
        V(_OPTIONS, [
            (T("Mostly added", "Casi todo añadido"), 'ui.diff_stat(42, 3)'),
            (T("Mostly removed", "Casi todo quitado"), 'ui.diff_stat(2, 57)'),
            (T("Only added", "Solo añadido"), 'ui.diff_stat(12, 0)'),
            ('blocks=10', 'ui.diff_stat(120, 40, blocks=10)'),
        ]),
    ],
    "facepile": [
        V(_OPTIONS, [
            (T("Two people", "Dos personas"), 'ui.facepile(["Ana", "Luis"])'),
            (T("Five people", "Cinco personas"), 'ui.facepile(["Ana", "Luis", "Kev", "Marta", "Sam"])'),
            ('max_shown=3', 'ui.facepile(["Ana", "Luis", "Kev", "Marta", "Sam", "Jo", "Lee"], max_shown=3)'),
            ('size=32, overlap=10', 'ui.facepile(["Ana", "Luis", "Kev", "Marta"], size=32, overlap=10)'),
        ]),
    ],
    "settings-group": [
        V(_OPTIONS, [
            (T("Without description", "Sin descripción"), 'pz.container(ui.settings_group("Files", [\n    ui.field("Autosave", ui.switch(True, on_toggle)),\n    ui.field("Trim whitespace", ui.checkbox(False, on_toggle)),\n]), width=380)', {"size": (480, 200)}),
            ('description=', 'pz.container(ui.settings_group("Git", [\n    ui.field("Inline blame", ui.switch(False, on_toggle)),\n], description="Shown in the editor gutter."), width=380)', {"size": (480, 180)}),
        ]),
    ],
    # -------------------------------------------------------------------------------------- lists
    "list-item": [
        V(_CONTENT, [
            (T("Text", "Texto"), 'pz.container(ui.list_item("README.md", on_open), width=240)'),
            ('icon=', 'pz.container(ui.list_item("README.md", on_open, icon="file-text"), width=240)'),
            ('icon_color=', 'pz.container(ui.list_item("main.py", on_open, icon="file-code", icon_color="#3572a5"), width=240)'),
            ('end=', 'pz.container(ui.list_item("app.py", on_open, icon="file-code", end=ui.badge("M", tint="warning")), width=240)'),
            ('start=', 'pz.container(ui.list_item("Buy milk", on_open, start=ui.checkbox(True, on_toggle)), width=240)'),
            ('color="error"', 'pz.container(ui.list_item("Delete project", on_open, icon="trash-2", color="error"), width=240)'),
        ]),
        V(_STATE, [
            ('selected=True', 'pz.container(ui.list_item("main.py", on_open, icon="file-code", selected=True), width=240)'),
            ('focused=True', 'pz.container(ui.list_item("main.py", on_open, icon="file-code", focused=True), width=240)'),
            ('disabled=True', 'pz.container(ui.list_item("old.txt", on_open, icon="file", disabled=True), width=240)'),
            ('inset=True', 'pz.container(ui.list_item("main.py", on_open, icon="file-code", selected=True, inset=True), width=240)'),
            ('indent=24', 'pz.container(ui.list_item("button.rs", on_open, icon="file-code", indent=24), width=240)'),
        ]),
    ],
    "list-header": [
        V(_OPTIONS, [
            (T("Title", "Título"), 'pz.container(ui.list_header("RECENT"), width=240)'),
            ('end=', 'pz.container(ui.list_header("PINNED", end=ui.icon_button("plus", on_new, size="xs")), width=240)'),
            (T("Counter at the end", "Contador al final"), 'pz.container(ui.list_header("CHANGES", end=ui.count_badge(4)), width=240)'),
        ]),
    ],
    "tree": [
        V(T("Expanded", "Desplegado"), [
            (T("Collapsed", "Plegado"), 'nodes = ui.TreeNode.from_paths(' + _PATHS + ')\npz.container(ui.tree(nodes, expanded=set()), width=240)', {"size": (480, 200)}),
            ('expanded={"src"}', 'nodes = ui.TreeNode.from_paths(' + _PATHS + ')\npz.container(ui.tree(nodes, expanded={"src"}), width=240)', {"size": (480, 220)}),
            ('expanded={"src", "src/ui"}', 'nodes = ui.TreeNode.from_paths(' + _PATHS + ')\npz.container(ui.tree(nodes, expanded={"src", "src/ui"}, selected="src/ui/button.rs"), width=240)', {"size": (480, 260)}),
        ]),
        V(T("Git status", "Estado de git"), [
            ('status=', 'nodes = ui.TreeNode.from_paths(["src/app.rs", "src/new.rs", "src/old.rs", "build.log"],\n    status={"src/app.rs": "modified", "src/new.rs": "created", "src/old.rs": "deleted", "build.log": "ignored"})\npz.container(ui.tree(nodes, expanded={"src"}), width=240)', {"size": (480, 220)}),
            ('"conflict"', 'nodes = ui.TreeNode.from_paths(["merge.py", "ok.py"], status={"merge.py": "conflict"})\npz.container(ui.tree(nodes, expanded=set()), width=240)'),
        ]),
        V(T("Density", "Densidad"), [
            ('item_height=20, indent=10', 'nodes = ui.TreeNode.from_paths(' + _PATHS + ')\npz.container(ui.tree(nodes, expanded={"src", "src/ui"}, item_height=20, indent=10), width=240)', {"size": (480, 240)}),
            ('item_height=30, indent=20', 'nodes = ui.TreeNode.from_paths(' + _PATHS + ')\npz.container(ui.tree(nodes, expanded={"src"}, item_height=30, indent=20), width=240)', {"size": (480, 260)}),
        ]),
    ],
    "menu": [
        V(T("Items", "Entradas"), [
            (T("Plain", "Simple"), 'ui.menu([ui.MenuItem("Open", on_open), ui.MenuItem("Rename", on_rename),\n         ui.MenuItem("Duplicate", on_duplicate)], width=200)', {"size": (480, 180)}),
            ('icon=, keys=', 'ui.menu([ui.MenuItem("Copy", on_copy, icon="copy", keys="ctrl-c"),\n         ui.MenuItem("Paste", on_paste, icon="clipboard", keys="ctrl-v")], width=220)', {"size": (480, 160)}),
            ('checked=', 'ui.menu([ui.MenuItem("Soft wrap", on_wrap, checked=True),\n         ui.MenuItem("Minimap", on_minimap, checked=False)], width=200)', {"size": (480, 160)}),
            ('danger=True', 'ui.menu([ui.MenuItem("Rename", on_rename), ui.SEPARATOR,\n         ui.MenuItem("Delete", on_delete, icon="trash-2", danger=True)], width=200)', {"size": (480, 180)}),
            ('disabled=True', 'ui.menu([ui.MenuItem("Undo", on_undo, keys="ctrl-z"),\n         ui.MenuItem("Redo", on_redo, keys="ctrl-shift-z", disabled=True)], width=220)', {"size": (480, 160)}),
        ]),
        V(T("Groups", "Grupos"), [
            (T("Headers and separators", "Cabeceras y separadores"), 'ui.menu(["FILE", ui.MenuItem("New", on_new, keys="ctrl-n"), ui.SEPARATOR,\n         "EDIT", ui.MenuItem("Find", on_find, keys="ctrl-f")], width=220)', {"size": (480, 220)}),
        ]),
    ],
    "accordion": [
        V(T("Open sections", "Secciones abiertas"), [
            (T("All closed", "Todas cerradas"), 'pz.container(ui.accordion([("a", "Editor", ui.muted("…")), ("b", "Files", ui.muted("…")),\n                           ("c", "Git", ui.muted("…"))], open=set(), on_toggle=on_toggle), width=320)', {"size": (480, 200)}),
            ('open={"a"}', 'pz.container(ui.accordion([("a", "Editor", ui.muted("Font, wrapping, minimap.")),\n                           ("b", "Files", ui.muted("…"))], open={"a"}, on_toggle=on_toggle), width=320)', {"size": (480, 200)}),
            ('open=True', 'pz.container(ui.accordion([("a", "Editor", ui.muted("Font, wrapping.")),\n                           ("b", "Files", ui.muted("Autosave."))], open=True, on_toggle=on_toggle), width=320)', {"size": (480, 220)}),
        ]),
        V(_CONTENT, [
            ('icons=', 'pz.container(ui.accordion([("e", "Editor", ui.muted("…")), ("g", "Git", ui.muted("…"))], open=set(),\n                          icons={"e": "file-code", "g": "git-branch"}, on_toggle=on_toggle), width=320)', {"size": (480, 180)}),
            ('AccordionSection(end=)', 'pz.container(ui.accordion([ui.AccordionSection("p", "Problems", ui.muted("…"), icon="circle-x",\n                                              end=ui.count_badge(3, tint="error"))],\n                          open=set(), on_toggle=on_toggle), width=320)', {"size": (480, 160)}),
        ]),
    ],
    "disclosure": [
        V(_STATE, [
            ('open=False', 'pz.container(ui.disclosure("Advanced options", ui.muted("…"), open=False, on_toggle=on_toggle), width=300)'),
            ('open=True', 'pz.container(ui.disclosure("Advanced options", ui.muted("Shown while open."), open=True,\n                           on_toggle=on_toggle), width=300)'),
            ('end=', 'pz.container(ui.disclosure("Environment", ui.muted("…"), open=False, on_toggle=on_toggle,\n                           end=ui.badge("3")), width=300)'),
        ]),
    ],
    # --------------------------------------------------------------------------------- navigation
    "tab-bar": [
        V(T("Tabs", "Pestañas"), [
            (T("Active and inactive", "Activa e inactiva"), 'pz.container(ui.tab_bar([ui.Tab.for_file("main.rs"), ui.Tab.for_file("app.rs")], "main.rs",\n                        on_close=on_close), width=400)', {"size": (480, 120)}),
            ('dirty=True', 'pz.container(ui.tab_bar([ui.Tab.for_file("main.rs"), ui.Tab.for_file("notes.md", dirty=True)], "main.rs",\n                        on_close=on_close), width=400)', {"size": (480, 120)}),
            ('preview=True', 'pz.container(ui.tab_bar([ui.Tab.for_file("README.md", preview=True)], "README.md", on_close=on_close), width=400)', {"size": (480, 120)}),
            ('status="modified"', 'pz.container(ui.tab_bar([ui.Tab.for_file("app.py", status="modified"),\n                         ui.Tab.for_file("new.py", status="created")], "app.py", on_close=on_close), width=400)', {"size": (480, 120)}),
            ('Tab(icon=)', 'pz.container(ui.tab_bar([ui.Tab("home", "Home", icon="house"), ui.Tab("logs", "Logs", icon="scroll-text")],\n                        "home", on_select=on_select), width=400)', {"size": (480, 120)}),
        ]),
        V(T("Controls", "Controles"), [
            ('start=, end=', 'pz.container(ui.tab_bar([ui.Tab.for_file("main.rs")], "main.rs", on_close=on_close,\n                        start=[ui.icon_button("arrow-left", on_back, size="sm")],\n                        end=[ui.icon_button("plus", on_new, size="sm")]), width=400)', {"size": (480, 120)}),
            ('ui.tab(dimmed=True)', 'pz.row([ui.tab(ui.Tab.for_file("main.rs"), active=True),\n        ui.tab(ui.Tab.for_file("app.rs"), active=False, dimmed=True)])', {"size": (480, 120)}),
        ]),
    ],
    "breadcrumbs": [
        V(_OPTIONS, [
            (T("Text", "Texto"), 'ui.breadcrumbs(["src", "ui", "button.rs"])'),
            (T("With icons", "Con iconos"), 'ui.breadcrumbs([("folder", "src"), ("file-code", "main.rs"), "fn main"])'),
            ('separator="/"', 'ui.breadcrumbs(["Settings", "Editor", "Font"], separator="/")'),
            ('on_press=', 'ui.breadcrumbs(["Home", "Projects", "pyzed"], on_press=on_press)'),
        ]),
    ],
    "toolbar": [
        V(_CONTENT, [
            (T("Start only", "Solo al principio"), 'pz.container(ui.toolbar([ui.breadcrumbs(["src", "main.rs"])]), width=400)', {"size": (480, 120)}),
            (T("End only", "Solo al final"), 'pz.container(ui.toolbar([], [ui.icon_button("search", on_search, size="sm"),\n                            ui.icon_button("sparkles", on_assist, size="sm")]), width=400)', {"size": (480, 120)}),
            ('height=40', 'pz.container(ui.toolbar([ui.label("Preview")], [ui.button("Publish", on_publish, size="sm", variant="solid")],\n                        height=40), width=400)', {"size": (480, 120)}),
        ]),
    ],
    # ----------------------------------------------------------------------------------- overlays
    "layer": [
        V(T("Placement", "Posición"), [
            (T("Top (default)", "Arriba (por defecto)"), 'ui.layer(main_view(), ui.card(ui.label("Overlay"), width=200), on_dismiss=on_close)', _FRAME),
            ('align_y="center"', 'ui.layer(main_view(), ui.card(ui.label("Overlay"), width=200), align_y="center",\n         on_dismiss=on_close)', _FRAME),
            ('align_x="end", align_y="end"', 'ui.layer(main_view(), ui.card(ui.label("Overlay"), width=200), align_x="end", align_y="end",\n         offset=16, on_dismiss=on_close)', _FRAME),
        ]),
        V(T("Backdrop", "Fondo"), [
            ('backdrop="#00000088"', 'ui.layer(main_view(), ui.card(ui.label("Overlay"), width=200), backdrop="#00000088",\n         align_y="center", on_dismiss=on_close)', _FRAME),
            ('overlay=None', 'ui.layer(main_view(), None)', _FRAME),
        ], T("With `overlay=None` the layer returns your view unchanged.",
             "Con `overlay=None` la capa devuelve tu vista sin cambios.")),
    ],
    "modal": [
        V(_CONTENT, [
            (T("Content only", "Solo contenido"), 'ui.modal(ui.muted("Your trial ends in 3 days."), width=320)', {"size": (480, 200)}),
            ('title=, on_close=', 'ui.modal(ui.muted("Your trial ends in 3 days."), title="Trial", on_close=on_close, width=320)', {"size": (480, 200)}),
            ('footer=', 'ui.modal(ui.muted("Discard the draft?"), title="Draft", on_close=on_close, width=320,\n         footer=[ui.button("Cancel", on_close), ui.button("Discard", on_discard, variant="error")])', {"size": (480, 240)}),
        ]),
    ],
    "popover": [
        V(_CONTENT, [
            (T("A menu", "Un menú"), 'ui.popover(main_view(), ui.menu([ui.MenuItem("Copy", on_copy, icon="copy"),\n                                    ui.MenuItem("Paste", on_paste, icon="clipboard")], width=180),\n           x=60, y=40, on_dismiss=on_close)', {"size": (440, 220), "fill": True}),
            (T("A card", "Una tarjeta"), 'ui.popover(main_view(), ui.card(ui.muted("Any widget fits here."), title="Popover", width=220),\n           x=120, y=40, on_dismiss=on_close)', {"size": (440, 220), "fill": True}),
        ]),
    ],
    "command-palette": [
        V(T("Query", "Búsqueda"), [
            (T("Empty", "Vacía"), 'ui.command_palette("", on_query, [\n    ui.PaletteItem("file: new", on_new, keys="ctrl-n"),\n    ui.PaletteItem("file: open", on_open, keys="ctrl-o"),\n    ui.PaletteItem("theme selector: toggle", on_theme),\n], width=420)', {"size": (480, 240)}),
            ('query="op"', 'ui.command_palette("op", on_query, [\n    ui.PaletteItem("file: new", on_new, keys="ctrl-n"),\n    ui.PaletteItem("file: open", on_open, keys="ctrl-o"),\n    ui.PaletteItem("workspace: open recent", on_recent, keys="ctrl-r"),\n], width=420)', {"size": (480, 240)}),
            ('selected=1', 'ui.command_palette("", on_query, [\n    ui.PaletteItem("file: new", on_new, keys="ctrl-n"),\n    ui.PaletteItem("file: open", on_open, keys="ctrl-o"),\n    ui.PaletteItem("file: save", on_save, keys="ctrl-s"),\n], selected=1, width=420)', {"size": (480, 240)}),
        ]),
    ],
    "picker": [
        V(T("Results", "Resultados"), [
            (T("With matches", "Con coincidencias"), 'files = ["src/app.rs", "src/render.rs", "app.py"]\nitems = ui.fuzzy_filter("app", [ui.PaletteItem(f, on_open, icon="file-code") for f in files],\n                        key=lambda item: item.label)\nui.picker("app", on_query, items, width=380)', {"size": (480, 220)}),
            ('empty_text=', 'ui.picker("zzz", on_query, [], empty_text="No files match", width=380)', {"size": (480, 160)}),
            ('PaletteItem(detail=)', 'ui.picker("", on_query, [(ui.PaletteItem("main", on_open, icon="git-branch", detail="2 hours ago"), []),\n                        (ui.PaletteItem("docs", on_open, icon="git-branch", detail="yesterday"), [])], width=380)', {"size": (480, 200)}),
        ]),
        V(T("Highlight", "Resaltado"), [
            ('ui.highlighted', 't = pz.theme.current()\nscore, positions = ui.fuzzy_match("tgsw", "editor: toggle soft wrap")\nui.highlighted("editor: toggle soft wrap", positions, color=t.text, match_color=t.accent, size=15)'),
        ]),
    ],
    # ------------------------------------------------------------------------------------ dialogs
    "dialog-layer": [
        V(T("Dialog", "Diálogo"), [
            ('ui.alert', 'ui.dialog_layer(main_view(), ui.alert("Export finished.", on_close, kind="success", width=280))', {"size": (480, 260), "fill": True}),
            ('ui.modal', 'ui.dialog_layer(main_view(), ui.modal(ui.muted("Any content."), title="Modal", on_close=on_close,\n                                       width=280), on_dismiss=on_close)', {"size": (480, 260), "fill": True}),
            ('dialog=None', 'ui.dialog_layer(main_view(), None)', {"size": (480, 260), "fill": True}),
        ]),
    ],
    "alert": [
        V(_KIND, [
            ('kind=None', 'ui.alert("The file was moved to the trash.", on_close, width=320)', {"size": (480, 200)}),
            ('kind="info"', 'ui.alert("A new version is available.", on_close, kind="info", width=320)', {"size": (480, 200)}),
            ('kind="success"', 'ui.alert("128 files were exported.", on_close, kind="success", title="Export", width=320)', {"size": (480, 200)}),
            ('kind="warning"', 'ui.alert("The disk is almost full.", on_close, kind="warning", width=320)', {"size": (480, 200)}),
            ('kind="error"', 'ui.alert("notes.py could not be opened.", on_close, kind="error", title="Error", width=320)', {"size": (480, 200)}),
        ]),
        V(_OPTIONS, [
            ('ok_label="Got it"', 'ui.alert("Shortcuts changed in this version.", on_close, ok_label="Got it", width=320)', {"size": (480, 200)}),
        ]),
    ],
    "confirm": [
        V(_KIND, [
            (T("Normal", "Normal"), 'ui.confirm("Close all tabs?", on_confirm, on_cancel, title="Close tabs", width=320)', {"size": (480, 200)}),
            ('danger=True', 'ui.confirm("Delete notes.py?", on_delete, on_cancel, title="Delete file", danger=True,\n           confirm_label="Delete", width=320)', {"size": (480, 200)}),
            ('kind="warning"', 'ui.confirm("Overwrite the existing file?", on_confirm, on_cancel, kind="warning", width=320)', {"size": (480, 200)}),
            ('confirm_label=, cancel_label=', 'ui.confirm("Push 3 commits to main?", on_push, on_cancel, confirm_label="Push",\n           cancel_label="Not now", width=320)', {"size": (480, 200)}),
        ]),
    ],
    "prompt": [
        V(_CONTENT, [
            (T("Title only", "Solo título"), 'ui.prompt("New branch", "", on_input, on_submit, on_cancel, placeholder="feature/…", width=340)', {"size": (480, 220)}),
            ('message=', 'ui.prompt("Rename", "notes.py", on_input, on_submit, on_cancel, message="New name for the file:",\n          width=340)', {"size": (480, 240)}),
            ('submit_label=', 'ui.prompt("Save view", "My view", on_input, on_submit, on_cancel, submit_label="Save", width=340)', {"size": (480, 220)}),
        ]),
    ],
    "choice": [
        V(_OPTIONS, [
            (T("Two answers", "Dos respuestas"), 'ui.choice("Open the project in…", [("This window", on_here), ("New window", on_new)],\n          on_cancel, width=360)', {"size": (480, 200)}),
            (T("Three answers", "Tres respuestas"), 'ui.choice("notes.py already exists.", [("Keep both", on_keep), ("Skip", on_skip),\n          ("Replace", on_replace)], on_cancel, title="File exists", width=400)', {"size": (480, 200)}),
        ]),
    ],
    "unsaved-changes": [
        V(_OPTIONS, [
            (T("A file", "Un archivo"), 'ui.unsaved_changes("notes.py", on_save, on_discard, on_cancel)', {"size": (520, 220)}),
            ('width=360', 'ui.unsaved_changes("report.pzform", on_save, on_discard, on_cancel, width=360)', {"size": (480, 240)}),
        ]),
    ],
    # ---------------------------------------------------------------------------------- workspace
    "workspace": [
        V(T("Docks", "Docks"), [
            (T("Center and status bar", "Centro y barra de estado"), 'ui.workspace(main_view(), status_bar=ui.status_bar([], [ui.status_item("Python")]))', {"size": (480, 240), "fill": True}),
            ('left=', 'ui.workspace(main_view(), left=pz.column([ui.panel_header("Project"),\n             ui.list_item("main.py", icon="file-code", selected=True, inset=True)]), left_width=150)', {"size": (480, 240), "fill": True}),
            ('bottom=', 'ui.workspace(main_view(), bottom=pz.column([ui.panel_header("Terminal", icon="terminal"),\n             ui.terminal("$ python main.py")]), bottom_height=90)', {"size": (480, 240), "fill": True}),
            ('right=', 'ui.workspace(main_view(), right=pz.column([ui.panel_header("Outline"), ui.list_item("class Notes", icon="box")]),\n             right_width=150)', {"size": (480, 240), "fill": True}),
            ('title_bar=', 'ui.workspace(main_view(), title_bar=ui.title_bar([ui.title_button("pyzed", chevron=True)],\n                                                  [ui.avatar("KV")]))', {"size": (480, 240), "fill": True}),
        ]),
    ],
    "title-bar": [
        V(T("Title buttons", "Botones de título"), [
            (T("Plain", "Simple"), 'ui.title_button("pyzed", on_projects)'),
            ('chevron=True', 'ui.title_button("pyzed", on_projects, chevron=True)'),
            ('muted=True, icon=', 'ui.title_button("main", on_branches, icon="git-branch", muted=True)'),
        ]),
        V(T("Bar", "Barra"), [
            ('start=', 'pz.container(ui.title_bar([ui.title_button("pyzed", chevron=True)]), width=420)'),
            ('center=', 'pz.container(ui.title_bar([], [], center=ui.muted("notes.py — Notes")), width=420)'),
            ('end=', 'pz.container(ui.title_bar([], [ui.icon_button("bell", on_bell, size="sm"), ui.avatar("KV")]), width=420)'),
        ]),
    ],
    "window-frame": [
        V(T("Platform style", "Estilo de plataforma"), [
            ('style="windows"', 'pz.container(ui.window_title_bar("notes.py", style="windows"), width=420)'),
            ('style="macos"', 'pz.container(ui.window_title_bar("notes.py", style="macos"), width=420)'),
            ('style="gnome"', 'pz.container(ui.window_title_bar("notes.py", style="gnome"), width=420)'),
            ('style="kde"', 'pz.container(ui.window_title_bar("notes.py", style="kde"), width=420)'),
            ('style="ubuntu"', 'pz.container(ui.window_title_bar("notes.py", style="ubuntu"), width=420)'),
        ]),
        V(_STATE, [
            ('focused=False', 'pz.container(ui.window_title_bar("notes.py", style="windows", focused=False), width=420)'),
            ('maximized=True', 'ui.window_controls("windows", maximized=True)'),
            ('ui.window_controls("macos")', 'ui.window_controls("macos")'),
        ]),
    ],
    "status-bar": [
        V(T("Items", "Elementos"), [
            (T("Text", "Texto"), 'ui.status_item("Ln 12, Col 8")'),
            ('icon=', 'ui.status_item("Python", icon="file-code")'),
            ('icon_color="warning"', 'ui.status_item("2", icon="triangle-alert", icon_color="warning")'),
            ('selected=True', 'ui.status_item(icon="panel-left", on_press=on_toggle, selected=True)'),
            ('color="accent"', 'ui.status_item("main", icon="git-branch", color="accent")'),
        ]),
        V(T("Bar", "Barra"), [
            ('start=, end=', 'pz.container(ui.status_bar([ui.status_item("0", icon="circle-x")],\n                           [ui.status_item("UTF-8"), ui.status_item("Python")]), width=420)'),
        ]),
    ],
    "panel": [
        V(T("Side", "Lado"), [
            ('side="left"', 'pz.row([ui.panel(ui.list_item("Inbox", icon="inbox", inset=True), header=ui.panel_header("Mail"),\n                 width=160, side="left"), pz.container(width="fill")], height="fill")', {"size": (440, 200), "fill": True}),
            ('side="right"', 'pz.row([pz.container(width="fill"), ui.panel(ui.muted("Properties"), header=ui.panel_header("Inspector"),\n                                          width=160, side="right")], height="fill")', {"size": (440, 200), "fill": True}),
            ('side="bottom"', 'pz.column([pz.container(height="fill"), ui.panel(ui.terminal("$ ls"), header=ui.panel_header("Terminal"),\n                                             height=100, side="bottom")], width="fill")', {"size": (440, 200), "fill": True}),
        ]),
    ],
    "panel-header": [
        V(_CONTENT, [
            (T("Title", "Título"), 'pz.container(ui.panel_header("Project"), width=280)'),
            ('icon=', 'pz.container(ui.panel_header("Terminal", icon="terminal"), width=280)'),
            ('actions=', 'pz.container(ui.panel_header("Project", [ui.icon_button("plus", on_new, size="xs"),\n                                     ui.icon_button("ellipsis", on_menu, size="xs")]), width=280)'),
            ('height=40', 'pz.container(ui.panel_header("Outline", height=40), width=280)'),
        ]),
    ],
    "split": [
        V(T("Direction", "Dirección"), [
            (T("Side by side", "Lado a lado"), 't = pz.theme.current()\nui.split(pz.container(ui.label("A"), padding=10, width="fill", height="fill", bg=t.panel),\n         pz.container(ui.label("B"), padding=10, width="fill", height="fill"), on_resize=on_resize)', {"size": (440, 180), "fill": True}),
            ('vertical=True', 't = pz.theme.current()\nui.split(pz.container(ui.label("Top"), padding=10, width="fill", height="fill", bg=t.panel),\n         pz.container(ui.label("Bottom"), padding=10, width="fill", height="fill"), vertical=True)', {"size": (440, 180), "fill": True}),
            ('ratio=0.25', 't = pz.theme.current()\nui.split(pz.container(ui.label("25%"), padding=10, width="fill", height="fill", bg=t.panel),\n         pz.container(ui.label("75%"), padding=10, width="fill", height="fill"), ratio=0.25)', {"size": (440, 180), "fill": True}),
        ]),
    ],
    # --------------------------------------------------------------------------------------- code
    "editor": [
        V(T("Language", "Lenguaje"), [
            ('path="counter.py"', 'pz.container(ui.editor("v-py", ' + _PY + ', path="counter.py"), width=470, height=110)', {"size": (540, 180)}),
            ('language="rust"', 'pz.container(ui.editor("v-rs", "fn main() {\\n    println!(\\"hi\\");\\n}\\n", language="rust"),\n             width=420, height=90)', {"size": (480, 160)}),
            ('language="json"', 'pz.container(ui.editor("v-json", \'{\\n  "name": "notes",\\n  "version": 2\\n}\\n\', language="json"),\n             width=420, height=110)', {"size": (480, 170)}),
        ]),
        V(_OPTIONS, [
            ('gutter=False', 'pz.container(ui.editor("v-g", ' + _PY + ', path="a.py", gutter=False), width=470, height=110)', {"size": (540, 180)}),
            ('markers=', 'pz.container(ui.editor("v-m", ' + _PY + ', path="a.py", markers={2: "created", 5: "modified"}),\n             width=470, height=110)', {"size": (540, 180)}),
            ('minimap=True', 'pz.container(ui.editor("v-mm", ' + _PY + ', path="a.py", minimap=True), width=470, height=124)', {"size": (540, 180)}),
            ('show_whitespace=True', 'pz.container(ui.editor("v-ws", ' + _PY + ', path="a.py", show_whitespace=True), width=470, height=110)', {"size": (540, 180)}),
            ('placeholder=', 'pz.container(ui.editor("v-ph", "", placeholder="Write something…"), width=420, height=60)', {"size": (480, 130)}),
            ('font_size=16', 'pz.container(ui.editor("v-fs", "print(\\"big\\")\\n", path="a.py", font_size=16), width=420, height=60)', {"size": (480, 130)}),
        ]),
    ],
    "terminal": [
        V(_CONTENT, [
            (T("Plain text", "Texto plano"), 'pz.container(ui.terminal("$ ls\\nmain.py  notes.md  pyproject.toml\\n$ "), width=380, height=80)', {"size": (480, 150)}),
            (T("ANSI colors", "Colores ANSI"), 'pz.container(ui.terminal("\\x1b[32m✓\\x1b[0m 24 passed  \\x1b[33m!\\x1b[0m 1 warning  \\x1b[31m✗\\x1b[0m 0 failed"),\n             width=380, height=50)', {"size": (480, 120)}),
            ('font_size=16', 'pz.container(ui.terminal("$ python main.py\\nHello", font_size=16), width=380, height=70)', {"size": (480, 140)}),
            (T("(text, color) segments", "Segmentos (texto, color)"), 'pz.container(ui.terminal([[("ok ", "#a1c181"), ("build", None)], [("err ", "#d07277"), ("lint", None)]]),\n             width=380, height=60)', {"size": (480, 130)}),
        ]),
    ],
    "console": [
        V(_OPTIONS, [
            (T("All levels", "Todos los niveles"), 'log = ui.Log()\nfor level in ui.LOG_LEVELS:\n    log.write(level, f"{level} message")\npz.container(ui.console(log.entries, on_clear=on_clear), width=520, height=220)', {"size": (600, 280)}),
            ('hidden={"info", "event"}', 'log = ui.Log()\nfor level in ui.LOG_LEVELS:\n    log.write(level, f"{level} message")\npz.container(ui.console(log.entries, hidden={"info", "event"}, on_toggle_level=on_toggle),\n             width=520, height=200)', {"size": (600, 260)}),
            ('query="error"', 'log = ui.Log()\nlog.write("info", "started")\nlog.write("error", "ValueError: bad input")\npz.container(ui.console(log.entries, query="error", on_query=on_query), width=520, height=140)', {"size": (600, 200)}),
        ]),
    ],
    "markdown": [
        V(T("Elements", "Elementos"), [
            (T("Headings and emphasis", "Títulos y énfasis"), 'ui.markdown("## Title\\nSome **bold** and *italic* text.", width=320)'),
            (T("Lists", "Listas"), 'ui.markdown("- Fast\\n- Native\\n- Pythonic\\n\\n1. Install\\n2. Run", width=320)', {"size": (480, 220)}),
            (T("Code", "Código"), 'ui.markdown("Run `pyzed new`:\\n\\n```python\\nimport pyzed as pz\\n```", width=320)', {"size": (480, 200)}),
            (T("Quote and link", "Cita y enlace"), 'ui.markdown("> Desktop UIs in Python.\\n\\nSee [the docs](https://albakore.github.io/pyzed/).", width=320, on_link=on_link)'),
            (T("Table", "Tabla"), 'ui.markdown("| Key | Action |\\n| --- | --- |\\n| ctrl-s | Save |\\n| ctrl-p | Open |", width=320)', {"size": (480, 200)}),
        ]),
    ],
    "shortcuts": [
        V(_OPTIONS, [
            (T("Grouped", "Agrupados"), 'pz.container(ui.shortcuts([("File", [("Save", "ctrl-s"), ("Open", "ctrl-o")])], on_query=on_query, height=130),\n             width=360)', {"size": (480, 220)}),
            ('query="pal"', 'pz.container(ui.shortcuts([("View", [("Command palette", "ctrl-shift-p"), ("Zoom in", "ctrl-=")])],\n                          query="pal", on_query=on_query, height=110), width=360)', {"size": (480, 200)}),
        ]),
    ],
    "about": [
        V(_CONTENT, [
            (T("Name and version", "Nombre y versión"), 'ui.about("Notes", "1.2.0")', {"size": (480, 220)}),
            ('details=', 'ui.about("Notes", "1.2.0", "A small notes app.", icon="notebook-pen",\n         details=[("Python", "3.12"), ("Pyzed", "0.4")])', {"size": (480, 300)}),
            ('links=', 'ui.about("Notes", "1.2.0", icon="notebook-pen", links=[("Website", on_web), ("GitHub", on_gh)])', {"size": (480, 260)}),
        ]),
    ],
    "reference-browser": [
        V(T("Pages", "Páginas"), [
            (T("A component", "Un componente"), 'from pyzed import reference\n\nui.reference_browser(reference.Browser("pyzed.ui.badge"), sidebar_width=200)', {"size": (720, 380), "fill": True}),
            (T("A layout widget", "Un widget de disposición"), 'from pyzed import reference\n\nui.reference_browser(reference.Browser("pyzed.row"), sidebar_width=200)', {"size": (720, 380), "fill": True}),
        ]),
    ],
})

_B = _BOX  # every layout snippet starts with ``box = ...``, a small labeled tile

VARIANTS.update({
    # ------------------------------------------------------------------------------------- layout
    "row": [
        V(T("Spacing", "Espaciado"), [
            ('spacing=0', _B + 'pz.row([box("A"), box("B"), box("C")])'),
            ('spacing=8', _B + 'pz.row([box("A"), box("B"), box("C")], spacing=8)'),
            ('spacing=24', _B + 'pz.row([box("A"), box("B"), box("C")], spacing=24)'),
        ]),
        V(T("Cross-axis alignment", "Alineación cruzada"), [
            ('align="start"', _B + 'pz.row([box("tall", h=70), box("B"), box("C")], spacing=8, align="start")'),
            ('align="center"', _B + 'pz.row([box("tall", h=70), box("B"), box("C")], spacing=8, align="center")'),
            ('align="end"', _B + 'pz.row([box("tall", h=70), box("B"), box("C")], spacing=8, align="end")'),
        ]),
        V(_OPTIONS, [
            ('pz.hspace()', _B + 'pz.row([box("Start"), pz.hspace(), box("End")], width=320)'),
            ('wrap=True', 'pz.container(pz.row([ui.chip(t) for t in ["python", "rust", "iced", "desktop", "gui", "async", "themes"]],\n                    spacing=6, wrap=True, line_spacing=6), width=260)'),
        ]),
    ],
    "column": [
        V(T("Cross-axis alignment", "Alineación cruzada"), [
            ('align="start"', _B + 'pz.column([box("wide", w=160), box("B"), box("C")], spacing=8, align="start")', {"size": (480, 220)}),
            ('align="center"', _B + 'pz.column([box("wide", w=160), box("B"), box("C")], spacing=8, align="center")', {"size": (480, 220)}),
            ('align="end"', _B + 'pz.column([box("wide", w=160), box("B"), box("C")], spacing=8, align="end")', {"size": (480, 220)}),
        ]),
        V(_OPTIONS, [
            ('spacing=16', _B + 'pz.column([box("1"), box("2")], spacing=16)', {"size": (480, 200)}),
            ('pz.vspace()', _B + 'pz.column([box("top"), pz.vspace(), box("bottom")], height=170)', {"size": (480, 240)}),
            ('padding=16', _B + 'pz.container(pz.column([box("1"), box("2")], spacing=8, padding=16),\n             border_color=pz.theme.current().border, border_width=1, radius=8)', {"size": (480, 220)}),
        ]),
    ],
    "container": [
        V(T("Box", "Caja"), [
            ('padding=, bg=', 'pz.container(ui.label("padding + bg"), padding=16, bg=pz.theme.current().element, radius=8)'),
            ('border_color=, border_width=', 'pz.container(ui.label("border"), padding=16, border_color=pz.theme.current().accent,\n             border_width=2, radius=8)'),
            ('radius=999', 'pz.container(ui.label("pill"), padding=(6, 16), bg=pz.theme.current().element, radius=999)'),
        ]),
        V(T("Paint", "Pintura"), [
            ('gradient=', 'pz.container(ui.label("gradient", color="#ffffff"), padding=16, radius=10,\n             gradient=(135, ["#7c3aed", "#3b82f6"]))'),
            ('shadow=', 'pz.container(ui.label("shadow"), padding=16, radius=10, bg=pz.theme.current().elevated,\n             shadow=("#00000066", (0, 6), 18))'),
        ]),
        V(T("Alignment", "Alineación"), [
            ('center=True', 'pz.container(ui.label("centered"), center=True, width=220, height=90,\n             border_color=pz.theme.current().border, border_width=1, radius=8)'),
            ('align_x="end", align_y="end"', 'pz.container(ui.label("bottom right"), align_x="end", align_y="end", padding=8,\n             width=220, height=90, border_color=pz.theme.current().border, border_width=1, radius=8)'),
        ]),
    ],
    "stack": [
        V(_OPTIONS, [
            (T("Layers", "Capas"), 't = pz.theme.current()\npz.stack([pz.container(width=180, height=100, bg=t.element, radius=10),\n          pz.container(ui.label("on top"), center=True, width=180, height=100)])'),
            ('pz.pin(x=, y=)', 't = pz.theme.current()\npz.stack([pz.container(width=180, height=100, bg=t.element, radius=10),\n          pz.pin(ui.count_badge(3), x=150, y=8)], width=180, height=100)'),
            (T("Badge over an icon", "Insignia sobre un icono"), 'pz.stack([pz.container(ui.icon_button("bell", on_press, size="lg"), padding=6),\n          pz.pin(ui.indicator("error", size=8), x=24, y=6)], width=40, height=40)'),
        ]),
    ],
    "grid": [
        V(T("Columns", "Columnas"), [
            ('columns=2', _B + 'pz.container(pz.grid([box(str(i), w="fill") for i in range(1, 5)], columns=2, spacing=8, height=44), width=220)', {"size": (480, 200)}),
            ('columns=3', _B + 'pz.container(pz.grid([box(str(i), w="fill") for i in range(1, 7)], columns=3, spacing=8, height=44), width=300)', {"size": (480, 200)}),
            ('columns=4', _B + 'pz.container(pz.grid([box(str(i), w="fill") for i in range(1, 9)], columns=4, spacing=8, height=44), width=380)', {"size": (480, 200)}),
        ]),
        V(T("Tracks", "Pistas"), [
            ('columns=[100, "1fr"]', _B + 'pz.container(pz.grid([box("100 px", w="fill"), box("1fr", w="fill")], columns=[100, "1fr"], spacing=8),\n             width=340, height=44)'),
            ('column_span=2', _B + 'pz.container(pz.grid([pz.cell(box("header", w="fill"), column=0, row=0, column_span=2),\n                      pz.cell(box("a", w="fill"), column=0, row=1),\n                      pz.cell(box("b", w="fill"), column=1, row=1)], columns=["1fr", "1fr"], spacing=8),\n             width=300, height=96)', {"size": (480, 200)}),
        ]),
    ],
    "flex": [
        V(T("Justify", "Justificar"), [
            ('justify="start"', _B + 'pz.flex([box("A"), box("B")], justify="start", gap=8, width=360)'),
            ('justify="center"', _B + 'pz.flex([box("A"), box("B")], justify="center", gap=8, width=360)'),
            ('justify="end"', _B + 'pz.flex([box("A"), box("B")], justify="end", gap=8, width=360)'),
            ('justify="between"', _B + 'pz.flex([box("A"), box("B"), box("C")], justify="between", width=360)'),
            ('justify="around"', _B + 'pz.flex([box("A"), box("B"), box("C")], justify="around", width=360)'),
            ('justify="evenly"', _B + 'pz.flex([box("A"), box("B"), box("C")], justify="evenly", width=360)'),
        ]),
        V(T("Grow", "Crecer"), [
            ('flex_item(grow=1)', _B + 'pz.flex([box("fixed"), pz.flex_item(box("grows", w="fill"), grow=1), box("fixed")], gap=8, width=360)'),
            ('wrap=True', _B + 'pz.flex([box(str(i)) for i in range(1, 7)], gap=8, wrap=True, width=300)', {"size": (480, 200)}),
        ]),
    ],
    "scrollable": [
        V(T("Direction", "Dirección"), [
            (T("Vertical", "Vertical"), 'pz.container(pz.scrollable(pz.column([ui.list_item(f"Item {i}", icon="file", inset=True)\n                                       for i in range(1, 30)]), height=130), width=240)', {"size": (480, 200)}),
            ('direction="horizontal"', 'pz.container(pz.scrollable(pz.container(pz.row([ui.chip(f"tag {i}") for i in range(1, 25)], spacing=6),\n                                        padding=(0, 0, 14, 0)),\n                           direction="horizontal"), width=300)'),
        ]),
    ],
    "resizable": [
        V(T("Edge", "Borde"), [
            ('edge="right"', 't = pz.theme.current()\npz.row([pz.resizable(pz.container(ui.label("Sidebar"), padding=10, width="fill", height="fill", bg=t.panel),\n                     edge="right", size=150, color=t.border), pz.container(width="fill")], height="fill")', _FRAME),
            ('edge="left"', 't = pz.theme.current()\npz.row([pz.container(width="fill"), pz.resizable(pz.container(ui.label("Inspector"), padding=10, width="fill",\n        height="fill", bg=t.panel), edge="left", size=150, color=t.border)], height="fill")', _FRAME),
            ('edge="top"', 't = pz.theme.current()\npz.column([pz.container(height="fill"), pz.resizable(pz.container(ui.label("Console"), padding=10, width="fill",\n           height="fill", bg=t.panel), edge="top", size=80, color=t.border)], width="fill")', _FRAME),
        ]),
    ],
    "spacing": [
        V(_OPTIONS, [
            ('pz.hspace()', _B + 'pz.row([box("left"), pz.hspace(), box("right")], width=320)'),
            ('pz.space(width=60)', _B + 'pz.row([box("a"), pz.space(width=60), box("b")])'),
            ('pz.vspace()', _B + 'pz.column([box("top"), pz.vspace(), box("bottom")], height=150)', {"size": (480, 220)}),
        ]),
    ],
    "responsive": [
        V(T("Available width", "Ancho disponible"), [
            ('width=200', _B + 'pz.container(pz.responsive(lambda w, h: pz.row([box("1"), box("2"), box("3")], spacing=8)\n             if w > 300 else pz.column([box("1"), box("2")], spacing=8)), width=200, height=110)', {"size": (480, 180)}),
            ('width=400', _B + 'pz.container(pz.responsive(lambda w, h: pz.row([box("1"), box("2"), box("3")], spacing=8)\n             if w > 300 else pz.column([box("1"), box("2")], spacing=8)), width=400, height=60)'),
        ], T("The same code, given two widths: the layout changes by itself.",
             "El mismo código con dos anchos: la disposición cambia sola.")),
    ],
    "anchor-layout": [
        V(T("Presets", "Presets"), [
            (preset, 't = pz.theme.current()\npz.container(pz.anchor_layout([pz.anchor(ui.badge("' + preset + '"), x=10, y=10, width=90, height=24,\n                                         anchor="' + preset + '")], design=(110, 44)),\n             width=260, height=110, border_color=t.border, border_width=1, radius=8)')
            for preset in ("top_left", "top_right", "bottom_left", "bottom_right", "center")
        ], T("Each layout was designed at 110 × 44 and drawn at 260 × 110: the badge keeps its distance to the "
             "edges it is anchored to.",
             "Cada disposición se diseñó a 110 × 44 y se dibuja a 260 × 110: la insignia mantiene su distancia a "
             "los bordes a los que está anclada.")),
        V(T("Stretching", "Estirar"), [
            (preset, 't = pz.theme.current()\npz.container(pz.anchor_layout([pz.anchor(pz.container(width="fill", height="fill", bg=t.accent, radius=4),\n                                         x=10, y=10, width=90, height=24, anchor="' + preset + '")], design=(110, 44)),\n             width=260, height=110, border_color=t.border, border_width=1, radius=8)')
            for preset in ("top_wide", "bottom_wide", "left_tall", "center_wide", "full")
        ]),
    ],
    # ------------------------------------------------------------------------------------ content
    "text": [
        V(_SIZE, [
            ('size=12', 'pz.text("Size 12", size=12)'),
            ('size=18', 'pz.text("Size 18", size=18)'),
            ('size=32', 'pz.text("Size 32", size=32)'),
        ]),
        V(T("Font and weight", "Fuente y peso"), [
            ('weight="bold"', 'pz.text("Bold", size=18, weight="bold")'),
            ('weight="light"', 'pz.text("Light", size=18, weight="light")'),
            ('italic=True', 'pz.text("Italic", size=18, italic=True)'),
            ('font="mono"', 'pz.text("Monospace 0123", size=16, font="mono")'),
        ]),
        V(T("Color and wrapping", "Color y ajuste"), [
            ('color="#e5c07b"', 'pz.text("Golden text", size=18, color="#e5c07b")'),
            ('width=, align_x="center"', 'pz.container(pz.text("A long sentence that wraps over several lines, centered.", align_x="center"),\n             width=220)'),
            ('line_height=1.8', 'pz.container(pz.text("Taller lines are easier to read in long paragraphs.", line_height=1.8),\n             width=220)'),
        ]),
    ],
    "icon": [
        V(_SIZE, [
            ('size=12', 'pz.icon("sparkles", size=12)'),
            ('size=16', 'pz.icon("sparkles", size=16)'),
            ('size=24', 'pz.icon("sparkles", size=24)'),
            ('size=40', 'pz.icon("sparkles", size=40)'),
        ]),
        V(_COLOR, [
            ('color="#a1c181"', 'pz.icon("git-branch", size=24, color="#a1c181")'),
            ('color="#d07277"', 'pz.icon("bug", size=24, color="#d07277")'),
            ('color="#74ade8"', 'pz.icon("folder-open", size=24, color="#74ade8")'),
        ]),
        V(T("SVG", "SVG"), [
            ('pz.svg("logo.svg")', 'pz.svg("logo.svg", width=48, height=48)'),
            ('color="#e5c07b"',
             'shapes = (\'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">\'\n'
             '          \'<circle cx="7" cy="7" r="5"/><rect x="12" y="12" width="10" height="10" rx="2"/></svg>\')\n'
             'pz.svg(shapes, width=48, height=48, color="#e5c07b")'),
        ], T("`color` paints every visible pixel of the SVG in one color and keeps the transparent ones, like an "
             "icon tint. An SVG with a filled background, such as `logo.svg`, becomes a plain tile.",
             "`color` pinta cada píxel visible del SVG de un color y deja los transparentes, como el tinte de un "
             "icono. Un SVG con fondo relleno, como `logo.svg`, queda como una placa lisa.")),
    ],
    "image": [
        V(T("Fit", "Ajuste"), [
            ('content_fit="cover"', 'pz.image("photo.png", width=200, height=110, content_fit="cover")', {"size": (480, 200)}),
            ('content_fit="contain"', 'pz.image("photo.png", width=200, height=110, content_fit="contain")', {"size": (480, 200)}),
            ('content_fit="fill"', 'pz.image("photo.png", width=200, height=110, content_fit="fill")', {"size": (480, 200)}),
        ]),
        V(T("Look", "Aspecto"), [
            ('radius=16', 'pz.image("photo.png", width=200, height=110, content_fit="cover", radius=16)', {"size": (480, 200)}),
            ('opacity=0.4', 'pz.image("photo.png", width=200, height=110, content_fit="cover", opacity=0.4)', {"size": (480, 200)}),
            ('rotation=8', 'pz.image("photo.png", width=200, height=110, content_fit="cover", radius=10, rotation=8)', {"size": (480, 200)}),
        ], T("`rotation` is in degrees, clockwise; the corners of a rotated image may reach outside its box.",
             "`rotation` va en grados, en sentido horario; las esquinas de una imagen girada pueden salir de su caja.")),
    ],
    "rich-text": [
        V(T("Span styles", "Estilos de span"), [
            ('weight="bold"', 'pz.rich_text([pz.span("Some "), pz.span("bold", weight="bold"), pz.span(" text")], size=16)'),
            ('italic=True', 'pz.rich_text([pz.span("Some "), pz.span("italic", italic=True), pz.span(" text")], size=16)'),
            ('color=', 'pz.rich_text([pz.span("Some "), pz.span("colored", color="#e5c07b"), pz.span(" text")], size=16)'),
            ('underline=True', 'pz.rich_text([pz.span("Some "), pz.span("underlined", underline=True), pz.span(" text")], size=16)'),
            ('strikethrough=True', 'pz.rich_text([pz.span("Some "), pz.span("struck", strikethrough=True), pz.span(" text")], size=16)'),
            ('bg=, radius=', 'pz.rich_text([pz.span("Run "), pz.span(" pyzed new ", font="mono", bg="#3b414d", color="#e6e6e6", radius=4)], size=16)'),
            ('link=', 'pz.rich_text([pz.span("Read "), pz.span("the docs", color="#74ade8", underline=True, link="https://iced.rs")], size=16)'),
            ('size=', 'pz.rich_text([pz.span("small ", size=12), pz.span("big", size=24, weight="bold")])'),
        ]),
    ],
    "qr-code": [
        V(_OPTIONS, [
            ('cell_size=3', 'pz.qr_code("https://albakore.github.io/pyzed/", cell_size=3)', {"size": (480, 220)}),
            ('cell_size=5', 'pz.qr_code("pyzed", cell_size=5)', {"size": (480, 220)}),
            ('color=, bg=', 'pz.qr_code("pyzed", cell_size=5, color="#74ade8", bg="#1e2228")', {"size": (480, 220)}),
        ]),
    ],
    "canvas": [
        V(T("Shapes", "Formas"), [
            ('draw.rect', 'pz.canvas([draw.rect(10, 10, 140, 70, fill="#74ade8", radius=10)], width=160, height=90)'),
            ('draw.circle', 'pz.canvas([draw.circle(50, 45, 36, fill="#a1c181")], width=100, height=90)'),
            ('draw.arc', 'pz.canvas([draw.arc(50, 45, 34, 0, 270, stroke="#e5c07b", width=8, cap="round")], width=100, height=90)'),
            ('draw.polygon', 'pz.canvas([draw.polygon([(10, 80), (50, 10), (90, 80)], fill="#d07277")], width=100, height=90)'),
            ('draw.line(dash=)', 'pz.canvas([draw.line(10, 45, 190, 45, stroke="#c678dd", width=3, dash=[8, 5])], width=200, height=90)'),
            ('draw.text', 'pz.canvas([draw.text(100, 45, "pyzed.draw", color="#74ade8", size=20, align_x="center",\n                     align_y="center")], width=200, height=90)'),
        ]),
    ],
    "shader": [
        V(T("Uniforms", "Uniforms"), [
            (f'tint="{tint}"', 'pz.shader("""\nfn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> {\n    let wave = 0.5 + 0.5 * sin(uv.x * 12.0 + uv.y * 4.0 + time * 2.0);\n    return vec4<f32>(mix(vec3<f32>(0.08, 0.09, 0.2), tint().rgb, wave), 1.0);\n}\n""", uniforms={"tint": "' + tint + '"}, width=260, height=110, time=0.5,\n    fallback=pz.Gradient(["#14172f", "' + tint + '"], angle=0))', {"size": (480, 200)})
            for tint in ("#c678dd", "#56b6c2", "#e5c07b")
        ], T("Each capture is one frame at `time=0.5`; run the example to see it move. Without a GPU the widget draws its `fallback`.",
             "Cada captura es un fotograma con `time=0.5`; ejecuta el ejemplo para verlo moverse. Sin GPU el widget dibuja su `fallback`.")),
    ],
    "effects": [
        V(T("Effects", "Efectos"), [
            (prop, 'pz.container(pz.container(ui.label("' + label + '"), width=130, height=60, padding=12).style(' + style + '),\n             padding=24).style(background=pz.Gradient(["#0f172a", "#312e81", "#0e7490"], angle=90), radius=12)',
             {"size": (480, 200)})
            for prop, label, style in (
                ("glass=True", "Glass", "glass=True, radius=12"),
                ("glow=", "Glow", 'background="#0b1220", radius=12, glow=("#22d3ee", 18)'),
                ("bloom=", "Bloom", 'background="#1a0b16", radius=12, bloom=("#f472b6", 0.8)'),
                ("opacity=0.5", "Opacity", 'background="#0b1220", radius=12, opacity=0.5'),
                ("scale=1.15", "Scale", 'background="#0b1220", radius=12, scale=1.15'),
                ("translate=", "Translate", 'background="#0b1220", radius=12, translate=(16, 8)'),
            )
        ]),
    ],
})

# States, sizes and events added to the form controls.
_STATES = T("States and events", "Estados y eventos")
_MORE = {
    "input": V(_STATES, [
        ('disabled=True', 'ui.input("Locked", on_input, disabled=True, width=220)'),
        ('readonly=True', 'ui.input("Copy me, not edit me", on_input, readonly=True, width=220)'),
        ('invalid=True', 'ui.input("ada@", on_input, invalid=True, width=220)'),
        ('on_clear=', 'ui.input("pyzed", on_input, on_clear=on_clear, width=220)'),
        ('max_length=8', 'ui.input("12345678", on_input, max_length=8, width=220)'),
        ('align="center"', 'ui.input("centered", on_input, align="center", width=220)'),
    ], T("Focus, blur and keys come from the common events: `.on(focus=..., blur=..., key_down=...)`.",
         "El foco, la pérdida de foco y las teclas vienen de los eventos comunes: `.on(focus=..., blur=..., key_down=...)`.")),
    "checkbox": V(_STATES, [
        (T("Mixed (checked=None)", "Mixto (checked=None)"), 'ui.checkbox(None, on_toggle, label="Some files")'),
        ('disabled=True', 'ui.checkbox(True, on_toggle, label="Locked", disabled=True)'),
        ('size="sm"', 'ui.checkbox(True, on_toggle, label="Small", size="sm")'),
        ('size="lg"', 'ui.checkbox(True, on_toggle, label="Large", size="lg")'),
    ]),
    "switch": V(_STATES, [
        ('disabled=True', 'ui.switch(True, on_toggle, label="Locked", disabled=True)'),
        ('size="sm"', 'ui.switch(True, on_toggle, label="Small", size="sm")'),
        ('size="lg"', 'ui.switch(True, on_toggle, label="Large", size="lg")'),
    ]),
    "slider": V(_STATES, [
        ('show_value=True', 'ui.slider(70, on_change, min=0, max=100, step=1, show_value=True, width=240)'),
        ('show_value="{:.0%}"', 'ui.slider(0.35, on_change, show_value="{:.0%}", width=240)'),
        ('vertical=True', 'ui.slider(6, on_change, min=0, max=10, step=1, vertical=True, height=110, show_value=True)', {"size": (480, 180)}),
        ('disabled=True', 'ui.slider(0.6, on_change, disabled=True, width=240)'),
    ], T("`on_release` runs when the drag ends: save or apply there instead of on every move.",
         "`on_release` se ejecuta al terminar de arrastrar: guarda o aplica ahí en lugar de en cada movimiento.")),
    "number-field": V(_STATES, [
        ('prefix="$", decimals=2', 'ui.number_field(9.5, on_change, step=0.5, prefix="$", decimals=2, width=150)'),
        ('invalid=True', 'ui.number_field(70000, on_change, invalid=True, width=150)'),
        ('disabled=True', 'ui.number_field(4, on_change, min=1, max=8, disabled=True)'),
    ], T("Once clicked, ↑/↓ step it (Shift: ten steps) and Home/End jump to `min`/`max`.",
         "Tras pulsarlo, ↑/↓ lo mueven un paso (con Shift, diez) e Inicio/Fin saltan a `min`/`max`.")),
    "select": V(_STATES, [
        ('disabled=True', 'ui.select(["One Dark"], "One Dark", on_select, disabled=True, width=200)'),
        ('invalid=True', 'ui.select(["UTF-8", "Latin-1"], None, on_select, placeholder="Encoding…", invalid=True, width=200)'),
    ], T("`on_open` and `on_close` run when the menu opens and closes.",
         "`on_open` y `on_close` se ejecutan al abrir y cerrar el menú.")),
    "radio-group": V(_STATES, [
        ('disabled={"CR"}', 'ui.radio_group(["LF", "CRLF", "CR"], "LF", on_select, horizontal=True, disabled={"CR"})'),
        ('descriptions=', 'ui.radio_group(["Spaces", "Tabs"], "Spaces", on_select,\n               descriptions={"Spaces": "Indent with 4 spaces", "Tabs": "One tab per level"})'),
    ]),
    "segmented": V(_STATES, [
        (T("With icons", "Con iconos"), 'ui.segmented([("list", "List", "list"), ("grid", "Grid", "layout-grid")], "grid", on_select)'),
        ('width="fill"', 'ui.segmented(["Day", "Week", "Month"], "Week", on_select, width=320)'),
        ('disabled={"Month"}', 'ui.segmented(["Day", "Week", "Month"], "Day", on_select, disabled={"Month"})'),
        ('size="sm"', 'ui.segmented(["Code", "Preview"], "Code", on_select, size="sm")'),
    ]),
    "toggle-group": V(_STATES, [
        ('multiple=True', 'ui.toggle_group([("b", "bold"), ("i", "italic"), ("u", "underline")], {"b", "u"}, on_select, multiple=True)'),
        ('disabled={"right"}', 'ui.toggle_group([("left", "align-left"), ("center", "align-center"), ("right", "align-right")],\n                "left", on_select, disabled={"right"})'),
    ], T("A third item in an option adds a tooltip: `(value, icon, tooltip)`.",
         "Un tercer elemento en una opción añade un tooltip: `(valor, icono, tooltip)`.")),
    "chip": V(_STATES, [
        ('tint="error"', 'ui.chip("Failing", on_press=on_press, selected=True, tint="error")'),
        ('disabled=True', 'ui.chip("Archived", on_press=on_press, on_remove=on_remove, disabled=True)'),
    ]),
    "split-button": V(_STATES, [
        ('tint="success"', 'ui.split_button("Deploy", on_press, on_menu, tint="success")'),
        ('disabled=True', 'ui.split_button("Run", on_press, on_menu, disabled=True)'),
    ]),
    "field": V(_STATES, [
        ('required=True', 'pz.container(ui.field("Name", ui.input("", on_input, width=180), required=True), width=380)'),
        ('vertical=True', 'pz.container(ui.field("Email", ui.input("ada@", on_input, invalid=True), vertical=True, required=True,\n                      error="Enter a valid email"), width=320)', {"size": (480, 180)}),
    ]),
}
for _slug, _group in _MORE.items():
    _groups = VARIANTS.setdefault(_slug, [])
    _at = len(_groups) - 1 if _groups and _groups[-1]["title"] == _BASE else len(_groups)
    _groups.insert(_at, _group)

_MORE = {
    "button": V(_STATES, [
        ('loading=True', 'ui.button("Saving", on_press, icon="save", loading=True)'),
        ('tooltip=', 'ui.button("Save", on_press, tooltip="Writes the file")',
         {"draw": 'shown_tooltip(ui.button("Save", on_press, keys="ctrl-s"), "Writes the file")'}),
    ]),
    "icon-button": V(_STATES, [
        ('indicator="accent"', 'ui.icon_button("bell", on_press, indicator="accent")'),
        ('tint="error"', 'ui.icon_button("trash-2", on_press, tint="error")'),
        ('loading=True', 'ui.icon_button("refresh-cw", on_press, loading=True)'),
        ('keys=', 'ui.icon_button("search", on_press, tooltip="Search", keys="ctrl-f")'),
    ]),
    "badge": V(_STATES, [
        ('size="sm"', 'ui.badge("beta", size="sm")'),
        ('size="lg"', 'ui.badge("Pro", size="lg", icon="star")'),
        ('on_press=', 'ui.badge("3 issues", tint="warning", on_press=on_press)'),
    ]),
    "avatar": V(_STATES, [
        ('status="online"', 'ui.avatar("KK", status="online", size=32)'),
        ('status="away"', 'ui.avatar("AL", status="away", index=2, size=32)'),
        ('status="busy"', 'ui.avatar("MZ", status="busy", index=4, size=32)'),
    ], T("`image=` shows a picture instead of the initials and `tooltip=` names the person on hover.",
         "`image=` muestra una foto en lugar de las iniciales y `tooltip=` nombra a la persona al pasar el ratón.")),
    "divider": V(_STATES, [
        ('label="or"', 'pz.container(ui.divider(label="or"), width=300)'),
        ('spacing=12', 'pz.column([ui.label("Above"), ui.divider(spacing=12), ui.label("Below")], width=300)'),
    ]),
    "list-item": V(_STATES, [
        ('description=', 'pz.container(ui.list_item("main.py", on_press, icon="file", description="src/app"), width=300)'),
        ('on_double_press=', 'pz.container(ui.list_item("Rename me", on_press, icon="pencil", on_double_press=on_rename), width=300)'),
    ], T("`on_right_press` opens a context menu and `tooltip=` shows on hover.",
         "`on_right_press` abre un menú contextual y `tooltip=` aparece al pasar el ratón.")),
    "tree": V(_STATES, [
        (T("Multiple selection and focus", "Selección múltiple y foco"),
         'pz.container(ui.tree(ui.TreeNode.from_paths(["src/app.py", "src/ui.py", "README.md"]), expanded={"src"},\n                     selected={"src/app.py", "README.md"}, focused="src/ui.py", on_open=on_open,\n                     on_context=on_context), width=300)', {"size": (480, 200)}),
    ], T("`on_open(id)` runs on a double click of a file and `on_context(id)` on a right click.",
         "`on_open(id)` se ejecuta con un doble clic en un archivo y `on_context(id)` con un clic derecho.")),
    "menu": V(_STATES, [
        (T("Descriptions and a submenu", "Descripciones y un submenú"),
         'ui.menu([ui.MenuItem("Share", on_press, icon="share", submenu=True),\n         ui.MenuItem("Rename", on_press, description="F2 also works")])', {"size": (480, 180)}),
        ('max_height=140', 'ui.menu([ui.MenuItem(f"Recent {i}", on_press) for i in range(10)], max_height=140)', {"size": (480, 200)}),
    ]),
    "tab-bar": V(_STATES, [
        ('pinned=True', 'ui.tab_bar([ui.Tab("app", "app.py", icon="file", pinned=True), ui.Tab("ui", "ui.py", icon="file")],\n           "ui", on_close=on_close, on_context=on_context, on_new=on_new)', {"size": (480, 120)}),
    ], T("A middle click closes a tab, `on_context(id)` runs on a right click and `on_new` on a double click of the empty space.",
         "Un clic central cierra una pestaña, `on_context(id)` se ejecuta con un clic derecho y `on_new` con un doble clic en el espacio vacío.")),
    "breadcrumbs": V(_STATES, [
        ('max_items=3', 'ui.breadcrumbs(["pyzed", "python", "pyzed", "ui", "lists.py"], max_items=3, on_press=on_press, on_more=on_more)'),
    ]),
    "toolbar": V(_STATES, [
        ('center=', 'pz.container(ui.toolbar([ui.breadcrumbs(["src", "app.py"])], [ui.icon_button("play", on_press)],\n                        center=ui.muted("Running…", size="sm")), width=440)'),
    ]),
}
for _slug, _group in _MORE.items():
    _groups = VARIANTS.setdefault(_slug, [])
    _at = len(_groups) - 1 if _groups and _groups[-1]["title"] == _BASE else len(_groups)
    _groups.insert(_at, _group)

_ROWS = '[{"name": "app.py", "size": 4}, {"name": "ui.py", "size": 12}, {"name": "README.md", "size": 2}]'
_MORE = {
    "table": V(_STATES, [
        (T("Multiple selection", "Selección múltiple"), f'rows = {_ROWS}\nui.table(["name", "size"], rows, selected=[rows[0], rows[2]], on_row_press=on_press,\n         on_row_double_press=on_open, on_row_context=on_context, height=130)', {"size": (480, 200)}),
        ('empty=', 'ui.table(["name", "size"], [], empty="No files yet", height=100)', {"size": (480, 160)}),
    ], T("`on_row_double_press(row)` opens a row and `on_row_context(row)` shows a context menu.",
         "`on_row_double_press(fila)` abre una fila y `on_row_context(fila)` muestra un menú contextual.")),
    "card": V(_STATES, [
        ('selected=True', 'ui.card(ui.muted("Python app with a window"), title="Desktop app", on_press=on_press,\n        selected=True, width=260)'),
        ('footer=, elevated=True', 'ui.card(ui.muted("3 files changed"), title="Commit", footer=[ui.button("Push", on_press)],\n        elevated=True, width=260)', {"size": (480, 200)}),
    ]),
    "stat": V(_STATES, [
        ('icon=, inverse=True', 'ui.stat("Errors", "12", delta=-8.0, inverse=True, icon="bug", width=180)'),
        ('on_press=', 'ui.stat("Users", "1,204", delta=4.2, icon="users", on_press=on_press, width=180)'),
    ], T("With `inverse=True` a drop is good news (green), for errors or latency.",
         "Con `inverse=True` una bajada es una buena noticia (verde), para errores o latencia.")),
    "progress": V(_STATES, [
        ('label=, show_value=True', 'pz.container(ui.progress(0.42, label="Downloading", show_value=True), width=300)'),
        (T("Indeterminate (value=None)", "Indeterminada (value=None)"), 'pz.container(ui.progress(None, label="Indexing"), width=300)'),
    ]),
    "settings-group": V(_STATES, [
        ('end=', 'pz.container(ui.settings_group("Editor", [ui.field("Wrap lines", ui.switch(True, on_toggle))],\n                               end=ui.button("Reset", on_press, size="sm", variant="ghost")), width=420)', {"size": (480, 180)}),
    ]),
    "modal": V(_STATES, [
        ('description=, icon=, width="sm"', 'ui.modal(ui.input("notes.md", on_input), title="Rename", description="Choose a new name",\n         icon="pencil", on_close=on_close, width="sm", footer=[ui.button("Rename", on_press, variant="solid")])', {"size": (480, 240)}),
    ], T("`max_height=` scrolls long content, and Escape sends `on_close` while the dialog has focus.",
         "`max_height=` desplaza el contenido largo, y Escape envía `on_close` mientras el diálogo tiene el foco.")),
    "toast": V(_STATES, [
        ('progress=0.6', 'ui.toast("Uploading", "notes.md", kind="info", progress=0.6, on_dismiss=on_close)'),
        ('on_press=', 'ui.toast("Build failed", "Click to see the log", kind="error", on_press=on_press)'),
    ]),
    "empty-state": V(_STATES, [
        ('size="sm", height="shrink"', 'ui.empty_state("No results", "Try another search", icon="search", size="sm", height="shrink")'),
        ('size="lg"', 'ui.empty_state("No projects", "Create one to start", icon="folder", size="lg", height=220)', {"size": (480, 260)}),
    ]),
    "count-badge": V(_STATES, [
        ('show_zero=False', 'pz.row([ui.icon_button("bell", on_press), ui.count_badge(0, show_zero=False)], align="center")'),
    ], T("With `show_zero=False` it draws nothing at 0 but keeps its place in the layout.",
         "Con `show_zero=False` no dibuja nada en 0 pero mantiene su lugar en el diseño.")),
}
for _slug, _group in _MORE.items():
    _groups = VARIANTS.setdefault(_slug, [])
    _at = len(_groups) - 1 if _groups and _groups[-1]["title"] == _BASE else len(_groups)
    _groups.insert(_at, _group)

# The animation presets only show while they play; see the clips on the Showcase pages.
for _entry in COMPONENTS:
    _entry["api"] = _entry["api"] + [n for n in _BASE_APIS.get(_entry["slug"], ()) if n not in _entry["api"]]
    _entry["plain"] = PLAIN.get(_entry["slug"])
    _entry["variants"] = VARIANTS.get(_entry["slug"], [])
