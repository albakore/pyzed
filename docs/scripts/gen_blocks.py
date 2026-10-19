"""Writes the Blocks pages (docs/src/content/docs/blocks and es/blocks) from examples/blocks/*.py.

    python docs/scripts/gen_blocks.py            # writes the pages
    python docs/scripts/gen_blocks.py --check    # fails if a page is out of date

Each block is a runnable example in examples/blocks; its page shows the screenshots rendered by
docs/scripts/block_shots.py, the components it uses and its full code, copied here so the page, the
per-page Markdown and llms-full.txt carry it. Run this script after changing a block.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLOCKS = ROOT / "examples" / "blocks"
DOCS = ROOT / "docs" / "src" / "content" / "docs"

# name (file in examples/blocks), slug, {lang: (title, description, intro, [features])}, [(library slug, use)]
# The component uses are written in English and Spanish: (slug, use_en, use_es).
DATA = [
    {
        "name": "login", "slug": "login",
        "en": ("Login", "A split sign-in screen for Python desktop apps: brand panel with a gradient, SSO and "
               "passkey buttons, email and password fields with validation.",
               "A two-column sign-in screen: a gradient brand panel with features and a testimonial on a "
               "translucent card, and a form with single sign-on, passkey, email and password, *remember me* and "
               "inline validation.",
               ["Gradient background with `pz.Gradient` and a translucent glass-like card.",
                "Validation on submit: a `ui.callout` shows the error, or the success.",
                "Text links built with `.on(click=..., cursor=\"pointer\")`.",
                "<kbd>Enter</kbd> in the password field signs in."]),
        "es": ("Inicio de sesión", "Pantalla de inicio de sesión para apps de escritorio en Python: panel de marca "
               "con degradado, botones de SSO y passkey, email y contraseña con validación.",
               "Una pantalla de inicio de sesión en dos columnas: un panel de marca con degradado, ventajas y un "
               "testimonio sobre una tarjeta translúcida, y un formulario con inicio de sesión único, passkey, email "
               "y contraseña, *recordarme* y validación en línea.",
               ["Fondo con `pz.Gradient` y una tarjeta translúcida tipo vidrio.",
                "Validación al enviar: un `ui.callout` muestra el error o el éxito.",
                "Enlaces de texto hechos con `.on(click=..., cursor=\"pointer\")`.",
                "<kbd>Enter</kbd> en la contraseña inicia sesión."]),
        "components": [("input", "Email and password", "Email y contraseña"),
                       ("button", "Sign in, SSO and passkey", "Iniciar sesión, SSO y passkey"),
                       ("checkbox", "Keep me signed in", "Mantener la sesión"),
                       ("callout", "Errors and success", "Errores y éxito"),
                       ("avatar", "Testimonial author", "Autora del testimonio"),
                       ("divider", "The “or” separator", "El separador “o”"),
                       ("heading", "Title", "Título"), ("label", "Labels and links", "Etiquetas y enlaces")],
    },
    {
        "name": "dashboard", "slug": "dashboard",
        "en": ("Dashboard", "An analytics dashboard in Python: sidebar navigation, KPI cards with sparklines, a "
               "revenue bar chart with ranges, a traffic donut and a sortable orders table.",
               "An admin dashboard: sidebar navigation with an upgrade card, a header with search and notifications, "
               "four KPI cards with trend lines, a revenue chart with a 7 days / 30 days / 12 months switch, traffic "
               "sources with a donut and a monthly goal, and a sortable table of recent orders.",
               ["`ui.stat` cards: value, change and sparkline in one call.",
                "`ui.bar_chart` and `ui.donut` take plain lists of numbers; colors come from the theme.",
                "Custom cells in `ui.table`: avatars and status badges through `render=`.",
                "Click a column header to sort; the search filters the orders as you type."]),
        "es": ("Panel de control", "Un dashboard de analítica en Python: navegación lateral, tarjetas KPI con "
               "sparklines, gráfico de barras de ingresos, donut de tráfico y tabla de pedidos ordenable.",
               "Un panel de administración: navegación lateral con una tarjeta de mejora de plan, cabecera con "
               "búsqueda y notificaciones, cuatro tarjetas KPI con tendencia, un gráfico de ingresos con selector "
               "7 días / 30 días / 12 meses, fuentes de tráfico con donut y objetivo mensual, y una tabla ordenable "
               "de pedidos recientes.",
               ["Tarjetas `ui.stat`: valor, variación y sparkline en una llamada.",
                "`ui.bar_chart` y `ui.donut` reciben listas de números; los colores salen del tema.",
                "Celdas propias en `ui.table`: avatares y badges de estado con `render=`.",
                "Clic en una cabecera para ordenar; la búsqueda filtra los pedidos al escribir."]),
        "components": [("stat", "KPI cards", "Tarjetas KPI"), ("bar-chart", "Revenue", "Ingresos"),
                       ("donut", "Traffic sources", "Fuentes de tráfico"), ("table", "Recent orders", "Pedidos"),
                       ("card", "Every panel", "Cada panel"), ("segmented", "Date range", "Rango de fechas"),
                       ("list-item", "Navigation", "Navegación"), ("search-input", "Search", "Búsqueda"),
                       ("progress", "Monthly goal", "Objetivo mensual"), ("badge", "Statuses", "Estados"),
                       ("avatar", "Customers", "Clientes"), ("sparkline", "Trends", "Tendencias")],
    },
    {
        "name": "settings", "slug": "settings",
        "en": ("Settings", "A settings page for Python desktop apps: sectioned navigation, profile fields, theme "
               "and accent pickers, notification switches, a save bar and a danger zone with confirmation.",
               "A settings screen in the style of modern desktop apps: a section list on the left and grouped rows on "
               "the right, with profile fields, a language select, light / dark / system theme, accent swatches, a "
               "font size slider, notification switches and a danger zone that asks before deleting.",
               ["`ui.settings_group` + `ui.field`: titled groups of rows with descriptions.",
                "A sticky footer with *unsaved changes* and Save / Discard.",
                "`ui.confirm` inside `ui.dialog_layer` for the destructive action.",
                "Accent swatches with a ring on the selected one."]),
        "es": ("Ajustes", "Una página de ajustes para apps de escritorio en Python: navegación por secciones, "
               "perfil, tema y color de acento, interruptores de notificaciones, barra de guardado y zona de peligro.",
               "Una pantalla de ajustes al estilo de las apps de escritorio modernas: lista de secciones a la "
               "izquierda y filas agrupadas a la derecha, con datos del perfil, idioma, tema claro / oscuro / del "
               "sistema, muestras de acento, tamaño de fuente, interruptores de notificaciones y una zona de peligro "
               "que pide confirmación.",
               ["`ui.settings_group` + `ui.field`: grupos con título y filas con descripción.",
                "Un pie fijo con *cambios sin guardar* y Guardar / Descartar.",
                "`ui.confirm` dentro de `ui.dialog_layer` para la acción destructiva.",
                "Muestras de acento con un anillo en la elegida."]),
        "components": [("settings-group", "Groups of rows", "Grupos de filas"),
                       ("field", "Each setting", "Cada ajuste"), ("input", "Name and email", "Nombre y email"),
                       ("select", "Language", "Idioma"), ("segmented", "Theme", "Tema"),
                       ("color-picker", "Accent swatches", "Muestras de acento"),
                       ("slider", "Font size", "Tamaño de fuente"), ("switch", "Notifications", "Notificaciones"),
                       ("confirm", "Delete account", "Borrar la cuenta"),
                       ("dialog-layer", "The dialog over the page", "El diálogo sobre la página"),
                       ("list-item", "Sections", "Secciones")],
    },
    {
        "name": "data_table", "slug": "data-table",
        "en": ("Data table", "A data table with filters in Python: search, status chips, a role select, sortable "
               "columns, row selection, pagination, CSV export and an invite dialog.",
               "A team members table: filter by name or email, toggle statuses with chips, pick a role, sort by any "
               "column, select rows with checkboxes, page through results, copy them as CSV and invite people "
               "from a dialog.",
               ["Filtering, sorting and paging done in plain Python, so it is easy to swap in a database query.",
                "Two-line cells (avatar, name and email) through `ui.Column(render=...)`.",
                "`pz.Command.copy` puts the CSV on the clipboard.",
                "`ui.prompt` for the invite, with <kbd>Enter</kbd> to send."]),
        "es": ("Tabla de datos", "Una tabla de datos con filtros en Python: búsqueda, chips de estado, filtro de "
               "rol, columnas ordenables, selección de filas, paginación, exportación CSV y diálogo de invitación.",
               "Una tabla de miembros de un equipo: filtra por nombre o email, activa estados con chips, elige un "
               "rol, ordena por cualquier columna, selecciona filas, pasa de página, cópialas como CSV e invita "
               "gente desde un diálogo.",
               ["Filtrado, orden y paginación en Python puro: fácil de cambiar por una consulta a la base de datos.",
                "Celdas de dos líneas (avatar, nombre y email) con `ui.Column(render=...)`.",
                "`pz.Command.copy` deja el CSV en el portapapeles.",
                "`ui.prompt` para invitar, con <kbd>Enter</kbd> para enviar."]),
        "components": [("table", "The table", "La tabla"), ("chip", "Status filters", "Filtros de estado"),
                       ("search-input", "Text filter", "Filtro de texto"), ("select", "Role filter", "Filtro de rol"),
                       ("checkbox", "Row selection", "Selección de filas"), ("badge", "Statuses", "Estados"),
                       ("avatar", "Members", "Miembros"), ("facepile", "Team", "Equipo"),
                       ("prompt", "Invite dialog", "Diálogo de invitación"),
                       ("icon-button", "Pagination and row menu", "Paginación y menú de fila")],
    },
    {
        "name": "chat", "slug": "chat",
        "en": ("Chat", "A team chat UI in Python: channels with unread counts, direct messages with presence, "
               "grouped messages with Markdown, attachments, reactions and a rich composer.",
               "A messenger in the style of Slack or Discord: channels with unread counters, direct messages with "
               "presence dots, a thread that groups consecutive messages, Markdown, file attachments, reactions and "
               "a composer with formatting buttons. For an AI chat that streams answers see "
               "[Building AI apps](/pyzed/ai/ai-apps/).",
               ["Consecutive messages from the same person are grouped under one avatar.",
                "`ui.markdown` renders bold, code and links in messages.",
                "`pz.scrollable(anchor_bottom=True)` keeps the newest message in view.",
                "<kbd>Enter</kbd> sends and scrolls to the end with `pz.Command.scroll_to_end`."]),
        "es": ("Chat", "Una interfaz de chat de equipo en Python: canales con no leídos, mensajes directos con "
               "presencia, mensajes agrupados con Markdown, adjuntos, reacciones y un compositor completo.",
               "Una mensajería al estilo de Slack o Discord: canales con contador de no leídos, mensajes directos con "
               "puntos de presencia, un hilo que agrupa mensajes seguidos, Markdown, adjuntos, reacciones y un "
               "compositor con botones de formato. Para un chat con IA que transmite la respuesta mira "
               "[Crear apps con IA](/pyzed/es/ai/ai-apps/).",
               ["Los mensajes seguidos de la misma persona se agrupan bajo un avatar.",
                "`ui.markdown` muestra negrita, código y enlaces.",
                "`pz.scrollable(anchor_bottom=True)` mantiene visible el último mensaje.",
                "<kbd>Enter</kbd> envía y baja hasta el final con `pz.Command.scroll_to_end`."]),
        "components": [("markdown", "Message text", "Texto de los mensajes"), ("avatar", "People", "Personas"),
                       ("indicator", "Presence", "Presencia"), ("count-badge", "Unread counts", "No leídos"),
                       ("list-item", "Channels and people", "Canales y personas"),
                       ("list-header", "Sidebar sections", "Secciones de la barra"),
                       ("chip", "Reactions", "Reacciones"), ("input", "Composer", "Compositor"),
                       ("facepile", "Channel members", "Miembros del canal"),
                       ("scrollable", "The thread", "El hilo")],
    },
    {
        "name": "file_explorer", "slug": "file-explorer",
        "en": ("File explorer and IDE", "An IDE layout in Python like Zed or VS Code: project tree, editor tabs, "
               "breadcrumbs, a code editor with minimap and git markers, terminal tabs, an outline and a status bar.",
               "A code editor window built with `ui.workspace`: a title bar with project and branch, a filterable "
               "project tree with git status colors, editor tabs and breadcrumbs, the code editor with syntax "
               "highlighting, git markers and a minimap, a terminal with tabs, an outline panel and a status bar.",
               ["`ui.workspace` places the docks; they can be resized by dragging.",
                "`ui.TreeNode.from_paths` builds the tree from a list of paths, with git statuses.",
                "`ui.Tab.for_file` picks the icon and color of each file type.",
                "`ui.terminal` understands ANSI colors."]),
        "es": ("Explorador de archivos e IDE", "Un diseño de IDE en Python como Zed o VS Code: árbol del proyecto, "
               "pestañas, migas de pan, editor con minimapa y marcas de git, terminal, esquema y barra de estado.",
               "Una ventana de editor de código hecha con `ui.workspace`: barra de título con proyecto y rama, árbol "
               "del proyecto filtrable con colores de git, pestañas y migas de pan, el editor con resaltado, marcas "
               "de git y minimapa, una terminal con pestañas, un panel de esquema y la barra de estado.",
               ["`ui.workspace` coloca los paneles; se redimensionan arrastrando.",
                "`ui.TreeNode.from_paths` arma el árbol desde rutas, con estados de git.",
                "`ui.Tab.for_file` elige el icono y el color de cada tipo de archivo.",
                "`ui.terminal` entiende colores ANSI."]),
        "components": [("workspace", "The window layout", "El diseño de la ventana"),
                       ("tree", "Project files", "Archivos del proyecto"), ("tab-bar", "Open files", "Archivos abiertos"),
                       ("breadcrumbs", "Path", "Ruta"), ("editor", "Code", "Código"),
                       ("terminal", "Terminal", "Terminal"), ("title-bar", "Title bar", "Barra de título"),
                       ("status-bar", "Status bar", "Barra de estado"), ("toolbar", "Editor toolbar", "Barra del editor"),
                       ("panel-header", "Panel titles", "Títulos de panel"), ("list-item", "Outline", "Esquema")],
    },
    {
        "name": "onboarding", "slug": "onboarding",
        "en": ("Onboarding wizard", "A multi-step onboarding wizard in Python: a vertical stepper, profile form, "
               "template cards, team invites, a summary and validation between steps.",
               "A four-step setup wizard: a vertical stepper with progress, a profile form, a workspace name with "
               "selectable template cards, team invites and a summary before launching. Each step validates before "
               "moving on.",
               ["The current step is plain state (`self.step`); each step is a method that returns its view.",
                "Selectable cards built from `pz.container(...).style(...).on(click=...)`.",
                "The stepper is drawn with icons, `pz.rule` and theme tokens, so it follows any theme.",
                "Back / Continue / Skip buttons and an error callout."]),
        "es": ("Asistente de bienvenida", "Un asistente de configuración en varios pasos en Python: indicador de "
               "pasos vertical, perfil, tarjetas de plantilla, invitaciones, resumen y validación entre pasos.",
               "Un asistente de cuatro pasos: indicador de pasos vertical con progreso, formulario de perfil, nombre "
               "del espacio con tarjetas de plantilla seleccionables, invitaciones al equipo y un resumen antes de "
               "empezar. Cada paso valida antes de seguir.",
               ["El paso actual es estado simple (`self.step`); cada paso es un método que devuelve su vista.",
                "Tarjetas seleccionables con `pz.container(...).style(...).on(click=...)`.",
                "El indicador de pasos usa iconos, `pz.rule` y tokens del tema, así sigue cualquier tema.",
                "Botones Atrás / Continuar / Omitir y un aviso de error."]),
        "components": [("progress", "Overall progress", "Progreso total"), ("input", "Text fields", "Campos de texto"),
                       ("select", "Role", "Rol"), ("badge", "Step number", "Número de paso"),
                       ("card", "Invites and summary", "Invitaciones y resumen"),
                       ("list-item", "Invited people", "Personas invitadas"),
                       ("empty-state", "No invites yet", "Sin invitaciones"),
                       ("callout", "Validation errors", "Errores de validación"), ("button", "Navigation", "Navegación")],
    },
    {
        "name": "music_player", "slug": "music-player",
        "en": ("Music player", "A music player UI in Python: library sidebar, album header with gradient art, a "
               "track list with an animated equalizer and a player bar with live progress and volume.",
               "A media player: a library sidebar with playlists, an album header with gradient cover art and a "
               "soft shadow, a track list where the playing song shows an animated equalizer, and a player bar with "
               "shuffle, previous, play / pause, next, repeat, a seek bar and volume. The timer is a real "
               "subscription, so the progress moves while it plays.",
               ["`pz.every` drives the playback clock only while playing (`subscriptions()`).",
                "Cover art from `pz.Gradient`, a header that fades out with `pz.Paint(..., mask=pz.Mask([1, 0]))`.",
                "An equalizer made of four small containers whose heights follow the clock.",
                "Rows are `pz.button`s with hover and selected backgrounds from the theme."]),
        "es": ("Reproductor de música", "Una interfaz de reproductor de música en Python: biblioteca, cabecera de "
               "álbum con portada en degradado, lista de canciones con ecualizador animado y barra de reproducción.",
               "Un reproductor: biblioteca con listas, una cabecera de álbum con portada en degradado y sombra, una "
               "lista de canciones donde la que suena muestra un ecualizador animado, y una barra con aleatorio, "
               "anterior, reproducir / pausa, siguiente, repetir, barra de avance y volumen. El reloj es una "
               "suscripción real: el progreso avanza mientras suena.",
               ["`pz.every` mueve el reloj solo mientras suena (`subscriptions()`).",
                "Portada con `pz.Gradient` y una cabecera que se desvanece con `pz.Paint(..., mask=pz.Mask([1, 0]))`.",
                "Un ecualizador de cuatro contenedores cuya altura sigue al reloj.",
                "Las filas son `pz.button` con fondos de hover y selección del tema."]),
        "components": [("slider", "Seek bar and volume", "Avance y volumen"),
                       ("icon-button", "Player controls", "Controles"),
                       ("list-item", "Library and playlists", "Biblioteca y listas"),
                       ("list-header", "Playlists title", "Título de listas"), ("button", "Play / pause", "Reproducir"),
                       ("scrollable", "Album page", "Página del álbum"), ("effects", "Gradients and shadows",
                                                                         "Degradados y sombras")],
    },
    {
        "name": "kanban", "slug": "kanban",
        "en": ("Kanban board", "A kanban board in Python: columns with counters, cards with tags, priorities, due "
               "dates, checklists and assignees, filters and moving cards between columns.",
               "A sprint board: four columns with counters, cards with colored tags, priority arrows, due dates "
               "(today in red), comment counts, checklist progress and assignees, a text filter, an *only mine* "
               "toggle, and buttons to add cards and move the selected one between columns.",
               ["Cards are dataclasses; moving one is changing its `column` field.",
                "The selected card gets an accent border and its move buttons.",
                "Each column scrolls on its own inside a `pz.scrollable`.",
                "A soft shadow on the cards with `.style(shadow=...)`."]),
        "es": ("Tablero kanban", "Un tablero kanban en Python: columnas con contadores, tarjetas con etiquetas, "
               "prioridad, fecha, checklist y responsables, filtros y mover tarjetas entre columnas.",
               "Un tablero de sprint: cuatro columnas con contador, tarjetas con etiquetas de color, flechas de "
               "prioridad, fecha límite (hoy en rojo), comentarios, progreso del checklist y responsables, un filtro "
               "de texto, *solo las mías*, y botones para añadir tarjetas y mover la elegida entre columnas.",
               ["Las tarjetas son dataclasses; moverlas es cambiar su campo `column`.",
                "La tarjeta elegida tiene borde de acento y sus botones para moverla.",
                "Cada columna se desplaza sola dentro de un `pz.scrollable`.",
                "Una sombra suave en las tarjetas con `.style(shadow=...)`."]),
        "components": [("badge", "Tags", "Etiquetas"), ("count-badge", "Column counters", "Contadores"),
                       ("progress", "Checklists", "Checklists"), ("facepile", "Assignees", "Responsables"),
                       ("breadcrumbs", "Location", "Ubicación"), ("search-input", "Filter", "Filtro"),
                       ("icon-button", "Add and move", "Añadir y mover"), ("scrollable", "Columns", "Columnas"),
                       ("button", "Only mine, new task", "Solo las mías, nueva tarea")],
    },
]

TEXT = {
    "en": {
        "run": "Run it", "run_text": "From the repository root:",
        "theme": "The screenshot follows the site's theme: switch between light and dark at the top of the page to "
                 "see the block in One Light and One Dark.",
        "shows": "What it shows", "uses": "Components used", "component": "Component", "for": "Used for",
        "code": "Code",
        "code_text": "The whole block, ready to copy. It only needs `pip install pyzed-ui`.",
        "next": "Make it yours",
        "next_text": "Change `theme` (or `self.theme = pz.themes.get(\"One Dark\").with_accent(\"#e11d48\")`), replace "
                     "the sample data with your own and split pieces into [components](/pyzed/guides/components/) "
                     "when they grow. An AI agent with the [MCP server](/pyzed/ai/mcp/) can read this block with "
                     "`read_example(\"blocks/{name}\")` and adapt it for you.",
        "gen": "{/* Generated by docs/scripts/gen_blocks.py from examples/blocks. Do not edit. */}",
    },
    "es": {
        "run": "Ejecutarlo", "run_text": "Desde la raíz del repositorio:",
        "theme": "La captura sigue el tema del sitio: cambia entre claro y oscuro arriba de la página para ver el "
                 "bloque en One Light y One Dark.",
        "shows": "Qué muestra", "uses": "Componentes que usa", "component": "Componente", "for": "Para",
        "code": "Código",
        "code_text": "El bloque completo, listo para copiar. Solo necesita `pip install pyzed-ui`.",
        "next": "Hazlo tuyo",
        "next_text": "Cambia `theme` (o `self.theme = pz.themes.get(\"One Dark\").with_accent(\"#e11d48\")`), pon tus "
                     "datos en lugar de los de ejemplo y separa piezas en [componentes](/pyzed/es/guides/components/) "
                     "cuando crezcan. Un agente de IA con el [servidor MCP](/pyzed/es/ai/mcp/) puede leer este bloque "
                     "con `read_example(\"blocks/{name}\")` y adaptarlo por ti.",
        "gen": "{/* Generado por docs/scripts/gen_blocks.py desde examples/blocks. No editar. */}",
    },
}

INDEX = {
    "en": ("Blocks", "Ready-made Python desktop UI screens to copy: login, dashboard, settings, data table, chat, "
           "IDE layout, onboarding wizard, music player and kanban, built with Pyzed components.",
           "Overview",
           """Blocks are **complete screens** built from Pyzed's [components](/pyzed/library/), in the spirit of
shadcn/ui's blocks: open one, run it, copy the code into your app and change what you need. Each block is a single
runnable file in [`examples/blocks/`](https://github.com/albakore/pyzed/tree/main/examples/blocks), tested in CI
in light and dark themes, so the code on these pages always works with the current Pyzed.""",
           """## How to use a block

1. Open its page and look at the screenshot in light and dark (switch the site's theme).
2. Run it: `python examples/blocks/<name>.py`, or copy the **Code** section into a file.
3. Keep what you need. Blocks are ordinary `pz.App` classes: their pieces are methods (`sidebar()`,
   `header()`...) that return widgets, so you can lift one into your own app as is.

## Make them yours

- **Theme.** Set `theme = "Gruvbox Dark"` (or any [theme](/pyzed/guides/theming/)) on the app, or derive one with
  your brand color: `pz.themes.get("One Dark").with_accent("#e11d48")`. Every block uses theme tokens
  (`"accent"`, `"panel"`, `"text_muted"`...), never fixed colors for its surfaces.
- **Data.** The sample data is at the top of each file. Replace it with a database query, an HTTP call or files;
  slow work goes in a coroutine so the window never blocks (see [Async](/pyzed/guides/async/)).
- **Components.** When a piece grows its own state, turn it into a [`pz.Component`](/pyzed/guides/components/)
  so it shows up in Pyzed Design's toolbox too.
- **AI.** With the [MCP server](/pyzed/ai/mcp/) connected, ask your agent: *"Start from the dashboard block and
  make it show our GitHub issues"*. It can read every block with `read_example("blocks/dashboard")`.""",
           "Blocks"),
    "es": ("Bloques", "Pantallas de interfaz de escritorio en Python listas para copiar: login, dashboard, ajustes, "
           "tabla de datos, chat, IDE, asistente de bienvenida, reproductor de música y kanban, con componentes "
           "de Pyzed.",
           "Resumen",
           """Los bloques son **pantallas completas** hechas con los [componentes](/pyzed/es/library/) de Pyzed, en la
línea de los blocks de shadcn/ui: abre uno, ejecútalo, copia el código en tu app y cambia lo que necesites. Cada
bloque es un único archivo ejecutable en
[`examples/blocks/`](https://github.com/albakore/pyzed/tree/main/examples/blocks), probado en CI con tema claro y
oscuro, así que el código de estas páginas siempre funciona con el Pyzed actual.""",
           """## Cómo usar un bloque

1. Abre su página y mira la captura en claro y oscuro (cambia el tema del sitio).
2. Ejecútalo: `python examples/blocks/<nombre>.py`, o copia la sección **Código** en un archivo.
3. Quédate con lo que necesites. Los bloques son clases `pz.App` normales: sus piezas son métodos (`sidebar()`,
   `header()`...) que devuelven widgets, así que puedes llevar uno a tu app tal cual.

## Hazlos tuyos

- **Tema.** Pon `theme = "Gruvbox Dark"` (o cualquier [tema](/pyzed/es/guides/theming/)) en la app, o crea uno con
  el color de tu marca: `pz.themes.get("One Dark").with_accent("#e11d48")`. Todos los bloques usan tokens del tema
  (`"accent"`, `"panel"`, `"text_muted"`...), nunca colores fijos para sus superficies.
- **Datos.** Los datos de ejemplo están al principio de cada archivo. Cámbialos por una consulta a la base de datos,
  una llamada HTTP o archivos; el trabajo lento va en una corrutina para que la ventana nunca se bloquee (mira
  [Async](/pyzed/es/guides/async/)).
- **Componentes.** Cuando una pieza tenga estado propio, conviértela en un
  [`pz.Component`](/pyzed/es/guides/components/) para que también aparezca en la caja de herramientas de Pyzed Design.
- **IA.** Con el [servidor MCP](/pyzed/es/ai/mcp/) conectado, pide a tu agente: *"Parte del bloque de dashboard y
  haz que muestre nuestros issues de GitHub"*. Puede leer cada bloque con `read_example("blocks/dashboard")`.""",
           "Bloques"),
}


def _code(name: str) -> str:
    code = (BLOCKS / f"{name}.py").read_text(encoding="utf-8")
    if "```" in code:
        raise SystemExit(f"examples/blocks/{name}.py contains ``` and can't go in a fenced block")
    return code.rstrip("\n")


def page(block: dict, lang: str, order: int) -> str:
    title, description, intro, features = block[lang]
    t = TEXT[lang]
    prefix = "/pyzed/es" if lang == "es" else "/pyzed"
    up = "../../../../" if lang == "es" else "../../../"
    rows = "\n".join(f"| [{slug.replace('-', ' ').capitalize()}]({prefix}/library/{slug}/) | "
                     f"{use_en if lang == 'en' else use_es} |" for slug, use_en, use_es in block["components"])
    feats = "\n".join(f"- {f}" for f in features)
    return f"""---
title: {json.dumps(title, ensure_ascii=False)}
description: {json.dumps(description, ensure_ascii=False)}
sidebar:
  order: {order}
---

{t["gen"]}

import BlockShot from '{up}components/blocks/BlockShot.astro';

{intro}

<BlockShot name="{block["name"]}" alt={json.dumps(title, ensure_ascii=False)} />

{t["theme"]}

## {t["run"]}

{t["run_text"]}

```bash
python examples/blocks/{block["name"]}.py
```

## {t["shows"]}

{feats}

## {t["uses"]}

| {t["component"]} | {t["for"]} |
| --- | --- |
{rows}

## {t["code"]}

{t["code_text"]}

```python title="examples/blocks/{block["name"]}.py"
{_code(block["name"])}
```

## {t["next"]}

{t["next_text"].replace("{name}", block["name"])}
"""


def index(lang: str) -> str:
    title, description, label, intro, rest, _ = INDEX[lang]
    prefix = "/pyzed/es" if lang == "es" else "/pyzed"
    up = "../../../../" if lang == "es" else "../../../"
    items = [{"slug": b["slug"], "shot": b["name"], "name": b[lang][0], "blurb": b[lang][1].split(":")[0] + "."}
             for b in DATA]
    t = TEXT[lang]
    return f"""---
title: {json.dumps(title, ensure_ascii=False)}
description: {json.dumps(description, ensure_ascii=False)}
sidebar:
  order: 0
  label: {json.dumps(label, ensure_ascii=False)}
---

{t["gen"]}

import BlockGallery from '{up}components/blocks/BlockGallery.astro';

{intro}

<BlockGallery base="{prefix}/blocks/" items={{{json.dumps(items, ensure_ascii=False)}}} />

{rest}
"""


def outputs() -> dict:
    out = {}
    missing = sorted({p.stem for p in BLOCKS.glob("*.py")} - {b["name"] for b in DATA})
    if missing:
        raise SystemExit(f"examples/blocks without a page in gen_blocks.py: {', '.join(missing)}")
    for lang in ("en", "es"):
        base = DOCS / ("es/blocks" if lang == "es" else "blocks")
        out[base / "index.mdx"] = index(lang)
        for order, block in enumerate(DATA, start=1):
            out[base / f"{block['slug']}.mdx"] = page(block, lang, order)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if a page is out of date")
    args = parser.parse_args()
    stale = []
    for path, text in outputs().items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(path.relative_to(ROOT).as_posix())
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print("wrote", path.relative_to(ROOT))
    if stale:
        print("out of date (run python docs/scripts/gen_blocks.py):\n  " + "\n  ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
