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
}

i18n.add("es", {"designer": _ES})
