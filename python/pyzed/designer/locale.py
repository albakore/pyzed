"""The designer's own texts in other languages (Settings → Language), through ``pyzed.i18n``.

The English text is the key: ``tr("Save as…")`` looks up ``designer.Save as…`` and falls
back to the English text, so a missing translation never shows a raw key. Add a language
with ``i18n.add("fr", {"designer": {"Save": "Enregistrer", ...}})``.
"""

from __future__ import annotations

from typing import Any

from .. import i18n


def tr(text: str, **values: Any) -> str:
    """``text`` in the designer's language (``{name}`` placeholders filled from ``values``)."""
    return i18n.t(f"designer.{text}", default=text, **values)


def apply(language: str) -> None:
    """Switches to ``language`` (``""`` follows the system language)."""
    i18n.set_language(language or i18n.system_language())


_ES = {
    # Menus and command groups
    "File": "Archivo", "Edit": "Editar", "View": "Ver", "Run": "Ejecutar", "Help": "Ayuda",
    "Recent": "Recientes", "Panels": "Paneles", "Menu": "Menú", "Settings": "Ajustes",
    "New form…": "Nuevo formulario…", "Open…": "Abrir…", "Save": "Guardar", "Save as…": "Guardar como…",
    "Settings…": "Ajustes…", "Undo": "Deshacer", "Redo": "Rehacer", "Cut": "Cortar", "Copy": "Copiar",
    "Paste": "Pegar", "Duplicate": "Duplicar", "Delete": "Eliminar", "Select all": "Seleccionar todo",
    "Add control…": "Añadir control…", "Group in a row": "Agrupar en una fila",
    "Group in a column": "Agrupar en una columna", "Group in a grid": "Agrupar en una cuadrícula",
    "Command palette…": "Paleta de comandos…", "Left dock": "Panel izquierdo", "Right dock": "Panel derecho",
    "Bottom dock": "Panel inferior", "Console": "Consola", "Toolbar": "Barra de herramientas",
    "Status bar": "Barra de estado", "Grid": "Cuadrícula", "Snap to grid": "Ajustar a la cuadrícula",
    "Smart guides": "Guías inteligentes", "Show hidden controls": "Mostrar controles ocultos",
    "Reset panel layout": "Restablecer los paneles", "Stop": "Detener", "Edit code file": "Editar el código",
    "Keyboard shortcuts": "Atajos de teclado", "Documentation": "Documentación",
    "Report a problem": "Informar un problema", "About Pyzed Design": "Acerca de Pyzed Design",
    "Canvas": "Lienzo", "Code": "Código", "Move by one pixel": "Mover un píxel",
    "Move by one grid step": "Mover un paso de la cuadrícula", "Open the main event": "Abrir el evento principal",
    "Cancel the current gesture": "Cancelar el gesto actual", "Show completions": "Mostrar sugerencias",
    "Accept completion": "Aceptar la sugerencia", "Close completions": "Cerrar las sugerencias",
    # Toolbar
    "New form or component": "Nuevo formulario o componente", "Open": "Abrir", "Align left": "Alinear a la izquierda",
    "Align centers": "Alinear los centros", "Align right": "Alinear a la derecha", "Align top": "Alinear arriba",
    "Align middles": "Alinear al medio", "Align bottom": "Alinear abajo",
    "Distribute horizontally": "Distribuir horizontalmente", "Distribute vertically": "Distribuir verticalmente",
    "Same width": "Mismo ancho", "Same height": "Mismo alto", "Bring to front": "Traer al frente",
    "Send to back": "Enviar al fondo", "Center in form horizontally": "Centrar horizontalmente en el formulario",
    "Center in form vertically": "Centrar verticalmente en el formulario",
    "Fit selection to grid": "Ajustar la selección a la cuadrícula",
    # Panels and docks
    "Design": "Diseño", "Project": "Proyecto", "Properties": "Propiedades", "Events": "Eventos",
    "Move {panel} to": "Mover {panel} a", "Left": "Izquierda", "Right": "Derecha", "Bottom": "Abajo",
    "Top": "Arriba", "Hide dock": "Ocultar el panel", "Move this panel": "Mover este panel",
    "Toolbox": "Herramientas", "Outline": "Estructura", "Search components…": "Buscar componentes…",
    "Window": "Ventana", "Look": "Aspecto", "Designer": "Diseñador", "Data": "Datos", "Behavior": "Comportamiento",
    "Align": "Alineación", "Spacing and size": "Espaciado y tamaño", "Inside": "Dentro de", "Grow": "Crecer",
    "Column span": "Columnas", "Anchor": "Anclaje", "Position": "Posición",
    # Components
    "Pointer": "Puntero", "Common": "Comunes", "Components": "Componentes", "Containers": "Contenedores",
    "Display": "Presentación", "Navigation": "Navegación", "Avatar": "Avatar", "Badge": "Insignia",
    "Button": "Botón", "Callout": "Aviso", "Card": "Tarjeta", "Chart": "Gráfico", "Check box": "Casilla",
    "Chip": "Etiqueta", "Divider": "Separador", "Drop-down": "Desplegable", "Flex column": "Columna flexible",
    "Flex row": "Fila flexible", "Group box": "Marco", "Heading": "Título", "Image": "Imagen",
    "Key binding": "Atajo", "Label": "Etiqueta de texto", "Link": "Enlace", "List box": "Lista", "Markdown": "Markdown",
    "Number box": "Número", "Panel": "Panel", "Progress bar": "Barra de progreso", "Radio group": "Opciones",
    "Search box": "Buscador", "Segmented": "Segmentado", "Slider": "Deslizador", "Spacer": "Espaciador",
    "Spinner": "Indicador de carga", "Stat": "Métrica", "Switch": "Interruptor", "Tab bar": "Pestañas",
    "Table": "Tabla", "Text area": "Área de texto", "Text box": "Cuadro de texto", "Timer": "Temporizador",
    # Property names
    "Accent": "Acento", "Background": "Fondo", "Corner radius": "Radio de esquina", "Custom accent": "Acento propio",
    "Enabled": "Habilitado", "Font size": "Tamaño de letra", "Grid size": "Tamaño de cuadrícula", "Height": "Alto",
    "Locked": "Bloqueado", "Resizable": "Redimensionable", "Visible": "Visible", "Width": "Ancho",
    "Border": "Borde", "Checked": "Marcado", "Color": "Color", "Columns": "Columnas", "Delta": "Variación",
    "Direction": "Dirección", "Fit": "Ajuste", "Gap": "Separación", "Horizontal": "Horizontal", "Icon": "Icono",
    "Initials": "Iniciales", "Interval (ms)": "Intervalo (ms)", "Items": "Elementos", "Justify": "Justificar",
    "Keys": "Teclas", "Kind": "Tipo", "Labels": "Etiquetas", "Level": "Nivel", "Line numbers": "Números de línea",
    "Max": "Máx.", "Min": "Mín.", "Options": "Opciones", "Padding": "Relleno", "Password": "Contraseña",
    "Placeholder": "Texto de ayuda", "Radius": "Radio", "Row height (0 = share)": "Alto de fila (0 = repartir)",
    "Rows (CSV)": "Filas (CSV)", "Selected": "Seleccionado", "Shadow": "Sombra", "Size": "Tamaño", "Step": "Paso",
    "Striped": "Rayado", "Tabs": "Pestañas", "Text": "Texto", "Tint": "Matiz", "Trend values": "Valores de tendencia",
    "Value": "Valor", "Values": "Valores", "Variant": "Variante", "Vertical": "Vertical", "Weight": "Peso",
    "Wrap": "Ajustar texto",
    # Style section
    "Style": "Estilo", "Text color": "Color del texto", "Font": "Fuente", "Italic": "Cursiva",
    "Line height": "Interlineado", "Border color": "Color del borde", "Border width": "Grosor del borde",
    "Margin": "Margen", "Max width": "Ancho máximo", "Max height": "Alto máximo", "Align content": "Alinear contenido",
    "Align vertically": "Alinear en vertical", "Clip": "Recortar", "From": "Desde", "To": "Hasta", "Fill": "Relleno",
    "Opacity": "Opacidad", "Mask": "Máscara", "Angle": "Ángulo", "Offset": "Desplazamiento", "Blur": "Desenfoque",
    "Reset style": "Restablecer el estilo", "Default": "Por defecto", "Gradient": "Degradado",
    "Fade out": "Desvanecer", "Fade in": "Aparecer", "Sans": "Sans", "Serif": "Serif", "Mono": "Mono",
    "Thin": "Fina", "Light": "Ligera", "Normal": "Normal", "Medium": "Media", "Semibold": "Seminegrita",
    "Bold": "Negrita", "Black": "Gruesa", "On": "Sí", "Off": "No", "Start": "Inicio", "Center": "Centro",
    "End": "Final",
    # List and table editors
    "Rows": "Filas", "Add item": "Añadir elemento", "Item": "Elemento", "Add row": "Añadir fila",
    "Add column": "Añadir columna", "Column": "Columna", "Header": "Encabezado",
    # Events dock
    "Edit code": "Editar el código", "Create handler": "Crear el manejador", "Disconnect": "Desconectar",
    "Double-click an event, or a control on the form, to write its code.":
        "Doble clic en un evento, o en un control del formulario, para escribir su código.",
    # Settings dialog
    "Appearance": "Apariencia", "Theme": "Tema", "Language": "Idioma", "System default": "Idioma del sistema",
    "Language of the designer's menus and panels": "Idioma de los menús y paneles del diseñador",
    "Form canvas": "Lienzo del formulario", "Show grid": "Mostrar la cuadrícula",
    "Align to other controls while dragging": "Alinear con otros controles al arrastrar",
    "Grid size for new forms": "Cuadrícula de los formularios nuevos", "Running": "Ejecución",
    "Save before running": "Guardar antes de ejecutar", "Open the console on Run": "Abrir la consola al ejecutar",
    "Log events in the console": "Registrar los eventos en la consola",
    "Every event the running form handles, with its value": "Cada evento que atiende el formulario, con su valor",
    "Layout": "Disposición", "Reset": "Restablecer",
    "Put every panel back in its default dock and size": "Devuelve cada panel a su sitio y tamaño iniciales",
    "Code editor": "Editor de código", "Editor settings…": "Ajustes del editor…",
    "Font, tabs, completion, language servers": "Fuente, tabulación, sugerencias, servidores de lenguaje",
    "Done": "Listo",
    # New form dialog
    "New form": "Nuevo formulario", "Name": "Nombre", "Title": "Título", "Folder": "Carpeta",
    "Template": "Plantilla", "Create": "Crear", "Cancel": "Cancelar", "Unsaved form": "Formulario sin guardar",
    "{name} already exists": "{name} ya existe", "Pick another name or folder.": "Elige otro nombre o carpeta.",
    "File name and handler prefix": "Nombre del archivo y prefijo de los manejadores",
    "Same as the name": "Igual que el nombre", "Creates {path}": "Crea {path}", "New {kind}": "Nuevo {kind}",
    "Form": "Formulario", "Component": "Componente",
    "New component": "Nuevo componente", "New component…": "Nuevo componente…",
    "A window of your app, with its own handlers.": "Una ventana de tu aplicación, con sus propios manejadores.",
    "A reusable piece, not a window: you place it in forms and in other components.":
        "Una pieza reutilizable, no una ventana: la colocas en formularios y en otros componentes.",
    "A reusable piece for forms and other components, not a window":
        "Una pieza reutilizable para formularios y otros componentes, no una ventana",
    "Class {name}": "Clase {name}", "Inherits from": "Hereda de", "Nothing (a new component)": "Nada (un componente nuevo)",
    "Starts with its controls, properties, events and methods": "Empieza con sus controles, propiedades, eventos y métodos",
    "Create component": "Crear componente", "Component view": "Vista de componente", "Form view": "Vista de formulario",
    "Blank": "En blanco", "An empty window.": "Una ventana vacía.", "Dialog": "Diálogo",
    "A message with OK and Cancel buttons.": "Un mensaje con los botones Aceptar y Cancelar.",
    "Sign in": "Inicio de sesión", "Email and password in a centered column.": "Correo y contraseña en una columna centrada.",
    "Sidebar": "Barra lateral",
    "Navigation on the left and content on the right.": "Navegación a la izquierda y contenido a la derecha.",
    "Labelled options in a grid.": "Opciones con etiqueta en una cuadrícula.",
    # Pickers
    "Add to {name}": "Añadir a {name}", "Add a control to the form": "Añadir un control al formulario",
    "Run a command…": "Ejecutar un comando…",
    # About
    "Version": "Versión", "Platform": "Plataforma", "Source code": "Código fuente",
    "Build windows visually, wire their events to Python and run them.":
        "Diseña ventanas visualmente, conecta sus eventos con Python y ejecútalas.",
    # Console
    "Running…": "Ejecutando…", "Idle": "Inactivo",
    # Context menu
    "View code": "Ver código", "Add inside…": "Añadir dentro…", "Group in a panel": "Agrupar en un panel",
    "Move out of {parent}": "Sacar de {parent}", "Lock": "Bloquear", "Unlock": "Desbloquear",
    # Code panel
    "Problems": "Problemas", "Editor settings": "Ajustes del editor", "Whole file": "Archivo completo",
    "This handler": "Este manejador", "Apply": "Aplicar", "Close": "Cerrar", "Loading…": "Cargando…",
    "↵ insert  esc close": "↵ insertar  esc cerrar", "private": "privado",
    "Language servers": "Servidores de lenguaje", "Types, completion and references": "Tipos, completado y referencias",
    "Linting": "Análisis de estilo", "Restart servers": "Reiniciar servidores",
    "Same as the designer": "Igual que el diseñador", "Ctrl+= and Ctrl+- (or Ctrl+wheel); Ctrl+0 resets":
    "Ctrl+= y Ctrl+- (o Ctrl+rueda); Ctrl+0 restablece", "Highlight current line": "Resaltar la línea actual",
    "Show whitespace": "Mostrar espacios", "Spaces as · and tabs as →": "Espacios como · y tabulaciones como →",
    "Wrap long lines": "Ajustar líneas largas", "Minimap": "Minimapa",
    "Click or drag it to scroll": "Haz clic o arrastra para desplazarte", "Cursor": "Cursor", "Shape": "Forma",
    "Bar": "Barra", "Block": "Bloque", "Underline": "Subrayado", "Hollow": "Hueco", "Blink": "Parpadeo",
    "Editing": "Edición", "Tab size": "Tamaño de tabulación",
    "Tab inserts spaces; Enter keeps the indentation": "Tab inserta espacios; Enter mantiene la sangría",
    "Autocomplete while typing": "Autocompletar al escribir", "Ctrl+Space opens it anytime":
    "Ctrl+Espacio lo abre en cualquier momento", "Auto-close brackets and quotes": "Cerrar paréntesis y comillas",
    "Also wraps the selection and steps over the closing one": "También envuelve la selección y salta el cierre",
    "Code folding": "Plegado de código", "Chevrons in the gutter; Ctrl+Shift+[ and ]":
    "Flechas en el margen; Ctrl+Mayús+[ y ]", "Format with ruff on Apply": "Formatear con ruff al aplicar",
    "Code lens and diagnostics": "Code lens y diagnósticos", "Code lens": "Code lens",
    "References, implementations and wired events": "Referencias, implementaciones y eventos conectados",
    "Inline diagnostics": "Diagnósticos en línea", "Problems at the end of the line": "Problemas al final de la línea",
    # Component descriptions
    "Static text.": "Texto fijo.", "A title.": "Un título.", "Runs code when pressed.": "Ejecuta código al pulsarlo.",
    "Single-line text entry.": "Entrada de texto de una línea.",
    "Multi-line text, with optional syntax highlighting.": "Texto de varias líneas, con resaltado de sintaxis opcional.",
    "An on/off option.": "Una opción de sí o no.", "A toggle, like Zed's settings switches.":
    "Un interruptor, como los de los ajustes de Zed.", "Pick one of several options.": "Elige una de varias opciones.",
    "A drop-down list.": "Una lista desplegable.", "Choose a number by dragging.": "Elige un número arrastrando.",
    "A numeric field with steppers.": "Un campo numérico con botones de paso.",
    "A scrollable list of items.": "Una lista de elementos con desplazamiento.",
    "Shows how far a task has got.": "Muestra cuánto avanzó una tarea.", "A small status label.": "Una etiqueta de estado pequeña.",
    "A picture from a file.": "Una imagen desde un archivo.", "A Lucide icon.": "Un icono de Lucide.",
    "Formatted text.": "Texto con formato.", "An activity indicator.": "Un indicador de actividad.",
    "A surface to group related controls; drop controls on it to put them inside.":
    "Una superficie para agrupar controles relacionados; suelta controles encima para meterlos dentro.",
    "A separator line.": "Una línea separadora.",
    "Lines up the controls inside it side by side, like CSS flexbox.":
    "Alinea sus controles uno al lado del otro, como flexbox en CSS.",
    "Stacks the controls inside it from top to bottom.": "Apila sus controles de arriba abajo.",
    "Places the controls inside it in cells, left to right.": "Coloca sus controles en celdas, de izquierda a derecha.",
    "Empty space that grows to push its neighbours apart in a flex row or column.":
    "Espacio vacío que crece para separar a sus vecinos en una fila o columna.",
    "A titled frame around related controls.": "Un marco con título alrededor de controles relacionados.",
    "A raised surface holding other controls.": "Una superficie elevada que contiene otros controles.",
    "Clickable text.": "Texto en el que se puede hacer clic.", "A text box with a search icon.":
    "Un cuadro de texto con icono de búsqueda.", "Pick one of a few options, side by side.":
    "Elige una de pocas opciones, una al lado de otra.",
    "Tabs; show or hide panels from its change event.": "Pestañas; muestra u oculta paneles desde su evento change.",
    "A compact, clickable tag.": "Una etiqueta compacta y pulsable.", "A highlighted message.": "Un mensaje destacado.",
    "Initials in a circle.": "Iniciales en un círculo.", "Keys shown as key caps.": "Teclas dibujadas como teclas.",
    "A figure with its change and trend.": "Una cifra con su variación y tendencia.",
    "A bar, line or donut chart.": "Un gráfico de barras, líneas o anillo.",
    "Rows and columns from comma-separated text; change gives the row index.":
    "Filas y columnas desde texto separado por comas; change da el índice de la fila.",
    "Runs its tick event periodically. Invisible at run time.":
    "Lanza su evento tick periódicamente. Invisible al ejecutar.",
    # Status bar and Style placeholders
    "{count} selected": "{count} seleccionados", "at {x}, {y}": "en {x}, {y}",
    "Placing {tool}: click or drag on the form": "Colocando {tool}: haz clic o arrastra en el formulario",
    "{count} controls": "{count} controles", "Grid {size}px": "Cuadrícula {size}px", "Snap": "Imán",
    "None": "Ninguno", "Masked": "Con máscara", "token or #rrggbbaa": "token o #rrggbbaa", "none": "ninguna",
    "theme default": "el del tema", "Ln {line}, Col {column}": "Lín {line}, Col {column}",
    # Code lens
    "{count} reference": "{count} referencia", "{count} references": "{count} referencias",
    "{count} implementation": "{count} implementación", "{count} implementations": "{count} implementaciones",
    "on {event}": "en {event}",
    # Updates
    "Check for updates": "Buscar actualizaciones", "What's new": "Novedades",
    "Check for updates automatically": "Buscar actualizaciones automáticamente",
    "Pyzed Design {version} is available": "Pyzed Design {version} está disponible",
    "Open What's new to see the changes and update.": "Abre Novedades para ver los cambios y actualizar.",
    "Pyzed Design is up to date": "Pyzed Design está actualizado",
    "Could not check for updates": "No se pudo buscar actualizaciones",
    "No build for this platform": "No hay versión para esta plataforma",
    "Update downloaded": "Actualización descargada",
    "Restart Pyzed Design to finish.": "Reinicia Pyzed Design para terminar.",
    "The update failed": "La actualización falló", "Restart to update": "Reiniciar para actualizar",
    "Loading the release notes…": "Cargando las notas de la versión…",
    "Could not load the release notes: {error}": "No se pudieron cargar las notas de la versión: {error}",
    "What's new in {version}": "Novedades de {version}", "Update to {version}": "Actualizar a {version}",
    "Downloading update… {percent}%": "Descargando actualización… {percent}%",
    "Installed": "Instalada", "New": "Nueva", "Download and install": "Descargar e instalar",
    "Skip this version": "Omitir esta versión", "or": "o",
    "Upgrade the package to get it:": "Actualiza el paquete para tenerla:",
    "you have {version}": "tienes la {version}", "Open on GitHub": "Abrir en GitHub",
    "No notes for this version.": "Esta versión no tiene notas.",
    # Code editor: the search bar, its shortcut groups and the telemetry settings
    "Invalid pattern": "Patrón no válido", "No results": "Sin resultados", "Toggle replace": "Mostrar reemplazar",
    "Find": "Buscar", "Match case": "Distinguir mayúsculas", "Match whole words": "Palabras completas",
    "Use regular expressions": "Usar expresiones regulares", "Previous match": "Coincidencia anterior",
    "Next match": "Coincidencia siguiente", "Select all matches": "Seleccionar todas las coincidencias",
    "Replace": "Reemplazar", "Replace all": "Reemplazar todo",
    "Current line {line} of {lines} (column {column})": "Línea actual {line} de {lines} (columna {column})",
    "Line or line:column": "Línea o línea:columna",
    "Find and replace": "Buscar y reemplazar", "Next and previous match": "Coincidencia siguiente y anterior",
    "Go to line": "Ir a la línea", "Bigger, smaller and default font": "Letra más grande, más pequeña y normal",
    "Multiple cursors": "Varios cursores", "Add a cursor": "Añadir un cursor",
    "Add a cursor above": "Añadir un cursor arriba", "Add a cursor below": "Añadir un cursor abajo",
    "Select the next match": "Seleccionar la siguiente coincidencia",
    "Select every match": "Seleccionar todas las coincidencias",
    "A cursor on each selected line": "Un cursor en cada línea seleccionada",
    "Undo the last cursor change": "Deshacer el último cambio de cursores", "Back to one cursor": "Volver a un cursor",
    "Lines": "Líneas", "Move line up": "Subir la línea", "Move line down": "Bajar la línea",
    "Duplicate line down": "Duplicar la línea", "Delete line": "Borrar la línea", "Select line": "Seleccionar la línea",
    "Join lines": "Unir líneas", "New line below": "Nueva línea debajo", "New line above": "Nueva línea encima",
    "Indent": "Sangrar", "Outdent": "Quitar sangría", "Toggle comment": "Comentar o descomentar",
    "Go to matching bracket": "Ir al corchete pareja", "Folding": "Plegado", "Fold": "Plegar", "Unfold": "Desplegar",
    "Fold everything": "Plegar todo", "Unfold everything": "Desplegar todo", "Toggle fold": "Plegar o desplegar",
    "Telemetry": "Telemetría", "Collect usage and performance data": "Recopilar datos de uso y rendimiento",
    "Counts of the commands and editor actions you use, and startup, render and command times. Never your code, "
    "texts or file names.": "Cuántas veces usas cada comando y acción del editor, y los tiempos de inicio, dibujo y "
                            "comandos. Nunca tu código, textos ni nombres de archivo.",
    "Kept on this computer only": "Solo se guardan en este equipo", "Last sent {when}": "Último envío: {when}",
    "Sent when the designer closes": "Se envían al cerrar el diseñador", "Could not send: {error}":
        "No se pudieron enviar: {error}",
    "Endpoint": "Destino", "Where to post the data as JSON; leave it empty to send nothing":
        "Dónde enviar los datos como JSON; déjalo vacío para no enviar nada",
    "Collected data": "Datos recopilados",
    "Match brackets": "Remarcar corchetes",
    "Outline the bracket that pairs with the one at the cursor; Ctrl+M jumps to it":
        "Remarca el corchete pareja del que está junto al cursor; Ctrl+M salta a él",
    "Highlight selection matches": "Resaltar coincidencias de la selección",
    "Ctrl+D adds the next one as a cursor, Ctrl+Shift+L all of them":
        "Ctrl+D añade la siguiente como cursor y Ctrl+Shift+L todas",
    # Built-in reference
    "Reference": "Referencia", "Form controls": "Controles del formulario", "Form code": "Código del formulario",
    "Property": "Propiedad", "Type": "Tipo", "Description": "Descripción", "Event": "Evento", "Handler": "Manejador",
    "Methods": "Métodos", "Methods and properties": "Métodos y propiedades", "See": "Ver", "In code": "En código",
    "Read and change them from code as attributes:": "Léelas y cámbialas desde el código como atributos:",
    "The same component in a Pyzed app written in code:": "El mismo componente en una app de Pyzed escrita en código:",
    "The running form: its controls, title, size and windows.":
    "El formulario en ejecución: sus controles, título, tamaño y ventanas.",
    "A control of the running form: its properties and methods.":
    "Un control del formulario en ejecución: sus propiedades y métodos.",
    "What a handler receives besides the form: sender, name and value.":
    "Lo que recibe un manejador además del formulario: emisor, nombre y valor.",
    "Every control is an attribute named like it: `form.button1`. `for control in form` goes through all of them "
    "and `form[\"button1\"]` finds one by name.":
    "Cada control es un atributo con su nombre: `form.button1`. `for control in form` los recorre todos y "
    "`form[\"button1\"]` busca uno por nombre.",
    "Each property of the control reads and writes like an attribute: `form.label1.text = \"Hi\"`. The page of "
    "each control lists its properties.":
    "Cada propiedad del control se lee y se escribe como un atributo: `form.label1.text = \"Hola\"`. La página "
    "de cada control enumera sus propiedades.",
    "The control that raised the event (or the form).": "El control que lanzó el evento (o el formulario).",
    "The event name: click, change...": "El nombre del evento: click, change...",
    "The event's value: the new text, checked state, key combo...":
    "El valor del evento: el texto nuevo, si está marcado, la combinación de teclas...",
    # Fields every control has
    "Horizontal position, in pixels from the left of the form (or of its container).":
    "Posición horizontal, en píxeles desde la izquierda del formulario (o de su contenedor).",
    "Vertical position, in pixels from the top.": "Posición vertical, en píxeles desde arriba.",
    "Width in pixels.": "Ancho en píxeles.", "Height in pixels.": "Alto en píxeles.",
    "Whether the control is shown (`show()` and `hide()` change it).":
    "Si el control se muestra (`show()` y `hide()` lo cambian).",
    "Whether the control reacts to the user.": "Si el control responde al usuario.",
    # Events
    "Runs when {name} is clicked.": "Se ejecuta al hacer clic en {name}.",
    "Runs when {name} is double-clicked.": "Se ejecuta al hacer doble clic en {name}.",
    "Runs when the value of {name} changes (``event.value``).": "Se ejecuta cuando cambia el valor de {name} (``event.value``).",
    "Runs when Enter is pressed in {name}.": "Se ejecuta al pulsar Enter en {name}.",
    "Runs when the user lets go of {name}.": "Se ejecuta cuando el usuario suelta {name}.",
    "Runs every ``interval`` milliseconds while {name} is enabled.":
    "Se ejecuta cada ``interval`` milisegundos mientras {name} está activo.",
    "Runs when the pointer enters {name}.": "Se ejecuta cuando el puntero entra en {name}.",
    "Runs when the pointer leaves {name}.": "Se ejecuta cuando el puntero sale de {name}.",
    "Runs when {name} is right-clicked.": "Se ejecuta al hacer clic derecho en {name}.",
    "Runs once when {name} opens.": "Se ejecuta una vez al abrirse {name}.",
    "Runs when {name} is closing; return False to keep it open.":
    "Se ejecuta cuando {name} se está cerrando; devuelve False para mantenerlo abierto.",
    "Runs on every key press (``event.value`` is a combo such as ``\"ctrl-s\"``).":
    "Se ejecuta con cada tecla (``event.value`` es una combinación como ``\"ctrl-s\"``).",
    "Runs when {name} is resized (``event.value`` is ``(width, height)``).":
    "Se ejecuta cuando {name} cambia de tamaño (``event.value`` es ``(width, height)``).",
    # Property descriptions
    "Where the content sits: start, center or end.": "Dónde se coloca el contenido: al inicio, centrado o al final.",
    "Fill color behind the content (a theme token or a hex color).":
    "Color de relleno detrás del contenido (un token del tema o un color hex).",
    "Draws a border around the panel.": "Dibuja un borde alrededor del panel.",
    "Whether it is on. Changes when the user clicks it (read it in the change event).":
    "Si está activado. Cambia cuando el usuario hace clic (léelo en el evento change).",
    "Text or icon color (a theme token or a hex color).": "Color del texto o del icono (un token del tema o un color hex).",
    "How many columns the cells are laid out in.": "En cuántas columnas se reparten las celdas.",
    "The table: one row per line, cells separated by commas, the first row is the header.":
    "La tabla: una fila por línea, celdas separadas por comas; la primera fila es el encabezado.",
    "The change shown next to the figure (positive is drawn as a rise).":
    "La variación que se muestra junto a la cifra (si es positiva se dibuja como subida).",
    "Whether the children run horizontally (row) or vertically (column).":
    "Si los hijos van en horizontal (fila) o en vertical (columna).",
    "How the picture fills its box: contain, cover, fill or none.":
    "Cómo llena la imagen su caja: contain, cover, fill o none.",
    "Space between the children, in pixels.": "Espacio entre los hijos, en píxeles.",
    "Lays the options out side by side instead of one per line.":
    "Coloca las opciones una al lado de otra en lugar de una por línea.",
    "A Lucide icon name (pick it with the icon button).": "Un nombre de icono de Lucide (elígelo con el botón del icono).",
    "The letters shown in the circle.": "Las letras que se muestran en el círculo.",
    "Milliseconds between two tick events.": "Milisegundos entre dos eventos tick.",
    "The rows of the list, one per line.": "Las filas de la lista, una por línea.",
    "How the children are spread along the main axis: start, center, end or space between.":
    "Cómo se reparten los hijos en el eje principal: inicio, centro, final o espacio entre ellos.",
    "The key combination to draw, such as ctrl-s.": "La combinación de teclas que se dibuja, como ctrl-s.",
    "The chart type: bar, line or donut.": "El tipo de gráfico: barras, líneas o anillo.",
    "The label of each value, one per line.": "La etiqueta de cada valor, una por línea.",
    "The language used to highlight the text (none for plain text).":
    "El lenguaje con el que se resalta el texto (ninguno para texto plano).",
    "The heading size: 1 is the biggest.": "El tamaño del título: 1 es el más grande.",
    "Shows line numbers in a gutter.": "Muestra los números de línea en un margen.",
    "The highest value.": "El valor más alto.", "The lowest value.": "El valor más bajo.",
    "The choices, one per line.": "Las opciones, una por línea.",
    "Space between the border and the children, in pixels.": "Espacio entre el borde y los hijos, en píxeles.",
    "Hint shown while it is empty.": "Pista que se muestra mientras está vacío.",
    "Corner radius, in pixels.": "Radio de las esquinas, en píxeles.",
    "The height of each row of cells (0 sizes them to their content).":
    "La altura de cada fila de celdas (0 las ajusta a su contenido).",
    "Whether the timer is ticking. Set it from code to start or stop it.":
    "Si el temporizador está en marcha. Cámbialo desde el código para iniciarlo o pararlo.",
    "Hides what is typed (for passwords).": "Oculta lo que se escribe (para contraseñas).",
    "The option chosen, by its text. Changes when the user picks one.":
    "La opción elegida, por su texto. Cambia cuando el usuario elige otra.",
    "Draws a drop shadow under the card.": "Dibuja una sombra debajo de la tarjeta.",
    "Text size: small, normal or large.": "Tamaño del texto: pequeño, normal o grande.",
    "Path of the image file, relative to the form.": "Ruta del archivo de imagen, relativa al formulario.",
    "How much one step changes the value.": "Cuánto cambia el valor en cada paso.",
    "Shades every other row.": "Sombrea una fila de cada dos.",
    "The tab titles, one per line.": "Los títulos de las pestañas, uno por línea.",
    "The text shown.": "El texto que se muestra.",
    "Semantic color: accent, success, warning, error or info.": "Color semántico: accent, success, warning, error o info.",
    "The title shown at the top.": "El título que se muestra arriba.",
    "Values drawn as a small line next to the figure, one per line.":
    "Valores dibujados como una pequeña línea junto a la cifra, uno por línea.",
    "The current value. Changes when the user moves it (read it in the change event).":
    "El valor actual. Cambia cuando el usuario lo mueve (léelo en el evento change).",
    "The numbers to plot, separated by commas.": "Los números que se dibujan, separados por comas.",
    "The button style: filled, ghost, outline, solid...": "El estilo del botón: filled, ghost, outline, solid...",
    "Draws the line vertically.": "Dibuja la línea en vertical.",
    "Font weight: normal, medium, semibold or bold.": "Grosor de la fuente: normal, medium, semibold o bold.",
    "Wraps long lines instead of cutting them.": "Parte las líneas largas en lugar de cortarlas.",
    "Whether the chip is selected. Changes when the user clicks it.":
    "Si el chip está seleccionado. Cambia cuando el usuario hace clic.",
    "Index of the selected row (-1 when none). Changes when the user clicks a row.":
    "Índice de la fila seleccionada (-1 si no hay ninguna). Cambia cuando el usuario hace clic en una fila.",
    "The title of the open tab.": "El título de la pestaña abierta.", "Icon size, in pixels.": "Tamaño del icono, en píxeles.",
    "The Lucide icon to draw.": "El icono de Lucide que se dibuja.", "The figure shown, as text.": "La cifra que se muestra, como texto.",
    "How much is done, between 0 and max.": "Cuánto se ha completado, entre 0 y max.",
    "What the user typed; set it from code to change it.": "Lo que escribió el usuario; cámbialo desde el código.",
    "The text in the box: what the user typed, or set it from code.":
    "El texto del cuadro: lo que escribió el usuario, o lo que pongas desde el código.",
    "The Markdown source to show.": "El texto Markdown que se muestra.",
}

i18n.add("es", {"designer": _ES})
