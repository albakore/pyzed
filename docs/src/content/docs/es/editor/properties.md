---
title: Propiedades
description: "La grilla de propiedades de Pyzed Design sección por sección: el formulario, un control, varios controles a la vez y los editores de listas y tablas."
sidebar:
  order: 3
---

El panel **Propiedades** (dock derecho) edita lo que esté seleccionado. Su contenido cambia con la selección:

| Selección | El panel muestra |
| --- | --- |
| Nada | El propio **formulario**: ventana, aspecto, estilo global y ajustes del diseñador. En un componente, el [panel Component](/pyzed/es/editor/component-designer/#el-panel-component). |
| Un control | Su nombre, **Posición** primero, luego sus propiedades por grupo, **Comportamiento**, su estilo (**Texto**, **Relleno**, **Borde**, **Espaciado**), **Efectos** y **Animación**. |
| Varios controles | Herramientas para alinear, distribuir e igualar tamaños. |

Cada sección se pliega: haz clic en su cabecera. Las secciones plegadas se recuerdan mientras el editor está
abierto, así que puedes dejar solo las que usas. Cada cambio es un paso de deshacer, y escribir en un campo se junta
en un solo paso.

### Campos numéricos

Todos los números del panel funcionan como en Figma:

- **Arrástralo de lado**: pulsa sobre el número y mueve el ratón a la izquierda o a la derecha para bajarlo o
  subirlo. Los pasos pequeños (opacidad, interlineado) avanzan despacio, para que puedas afinar.
- **Doble clic** para escribir un valor; <kbd>Enter</kbd> lo confirma. Un solo clic pone el cursor en el campo, y
  <kbd>↑</kbd> / <kbd>↓</kbd> suman o restan un paso.
- La letra o unidad dentro del campo (**X**, **W**, **px**, **°**) dice qué es el número.

En tus propias apps es el mismo [`ui.number_field`](/pyzed/es/library/number-field/): `drag=False` desactiva el
arrastre y `steppers=False` oculta los botones `−`/`+`.

## Un control

![Las propiedades de una tabla: el editor de filas](../../../../../screenshots/editor-rows.png)

### Cabecera y nombre

Arriba del panel están el icono del componente, su tipo y una descripción de una línea. Debajo, **Nombre** es el
identificador del control: el atributo que usas en el código (`form.email`) y el prefijo de sus manejadores. Escribe
un nombre nuevo y pulsa <kbd>Enter</kbd> para renombrarlo; los manejadores que siguen la convención de nombres
(`email_change`) se renombran también en el archivo de código. El editor ajusta los nombres para que sean válidos y
únicos.

El botón del **libro** a la derecha de la cabecera (<kbd>Shift</kbd>+<kbd>F1</kbd>) abre la página del control en la
[referencia integrada](/pyzed/es/editor/reference/): cada propiedad con su tipo y valor por defecto, sus eventos y sus
métodos. Pasa el ratón por la etiqueta de una propiedad para ver una descripción de una línea.

### Las secciones propias del componente

Cada componente agrupa sus propiedades en secciones **Apariencia**, **Datos**, **Disposición** o
**Comportamiento** (una sección con el mismo nombre que una del propio panel, como **Comportamiento**, se junta con
ella). El tipo de una propiedad decide su editor:

| Tipo | Editor | Ejemplo |
| --- | --- | --- |
| Texto | Un campo de texto. | El `text` de un botón, el `placeholder` de un campo. |
| Multilínea | Un pequeño editor de código con ajuste de línea. | El `text` de un área de texto o de un markdown. |
| Número | Un campo numérico que se arrastra o se escribe, con límites. | `min`, `max`, `step` de un deslizador. |
| Archivo, carpeta | Un campo y un botón de **carpeta** que abre el diálogo de archivos del sistema (ver abajo). | El `source` de una imagen, el `file` de un shader, el `path` de un vigilante de archivos. |
| Interruptor | Un switch de encendido y apagado. | `checked`, `secure`, `wrap`. |
| Opción | Hasta cuatro opciones cortas lado a lado como un control segmentado; las listas más largas, como desplegable. | El `variant` de un botón, el `size` de una etiqueta. |
| Color | Una muestra y un campo para un token del tema (`accent`, `text_muted`) o `#hex`. | El `color` de una etiqueta. |
| Icono | Una vista previa, un campo para un nombre de icono de [Lucide](https://lucide.dev) y un botón **…**: pulsa la vista previa o **…** para elegirlo en el diálogo de iconos (ver abajo). | El `icon` de un botón. |
| Lista | Un campo por elemento (ver abajo). | Las `options` de un desplegable, los `items` de una lista, las `tabs` de una barra de pestañas. |
| Filas | Una pequeña hoja de cálculo (ver abajo). | Los `data` de una tabla. |

Pasa el ratón por el nombre de una propiedad para leer qué hace, cuando tiene ayuda. La
[biblioteca de componentes](/pyzed/es/library/) documenta cada propiedad de cada componente.

Los controles que guardan un valor muestran además **Enlazar a** y sus reglas de validación (**Obligatorio**,
**Longitud mínima**, **Patrón**...) en la sección **Datos**: consulta
[Enlace de datos y validación](/pyzed/es/editor/data-binding/).

### Archivos y carpetas

Toda propiedad que guarda un archivo o una carpeta tiene un botón de **carpeta** al final. Abre el diálogo del
sistema (filtrado por tipo: imágenes, sonidos, fuentes, shaders, archivos de datos...) y escribe la ruta por ti. Un
archivo dentro de tu proyecto se escribe **relativo al proyecto** (`assets/logo.png`), así el proyecto sigue
funcionando si lo mueves. También puedes escribir la ruta a mano.

Vale para las propiedades de los componentes (`source`, `file`, `path`, `directory`...), para cualquier propiedad de
texto cuyo nombre indique una ruta (`icon_path`, `output_dir`, `cwd`...), para las
[propiedades de tus componentes](/pyzed/es/editor/component-designer/) de tipo `pz.FilePath` o `pz.FolderPath`, y
para los campos de carpeta de los diálogos del editor. En tus propias apps el mismo campo es `ui.path_input`.

### El diálogo de iconos

Al pulsar la vista previa de una propiedad de icono o su botón **…** se abre **Elegir un icono**: un buscador, un
desplegable de categorías y una cuadrícula con todos los iconos incluidos. La búsqueda mira los nombres y las
etiquetas de Lucide (en inglés: "person" encuentra `user`, "trash" encuentra `trash-2`), Enter elige la primera
coincidencia y un clic en un icono fija la propiedad y cierra el diálogo. El icono en uso aparece resaltado y abajo,
junto al número de coincidencias; **×** deja la propiedad sin icono.

![El diálogo de iconos abierto desde la propiedad Icono de un botón](../../../../../screenshots/editor-icon-picker.png)

El mismo diálogo elige el **Icon** de un [componente diseñado](/pyzed/es/editor/component-designer/) y el valor por
defecto de sus propiedades de icono. En tus propias apps es [`ui.IconPicker`](/pyzed/es/library/icon-picker/).

### El editor de listas

![Los elementos de una lista, un campo por elemento](../../../../../screenshots/editor-items.png)

Las listas tienen un campo numerado por elemento, con botones para **subirlo**, **bajarlo** y **quitarlo**, y
**Añadir elemento** al final. El icono de página a la derecha del título de la propiedad cambia a **Edit as text**:
un elemento por línea en un pequeño editor, cómodo para pegar una lista larga. El icono de lista vuelve
(**Edit item by item**).

### El editor de filas

Los datos de una tabla son una pequeña hoja de cálculo. La primera fila (marcada con **H**) es la cabecera; las
demás están numeradas. **Añadir fila** y **Añadir columna** la amplían, la **×** al final de una fila la quita y la
**×** sobre una columna quita la columna (una tabla conserva al menos una). Se desplaza de lado cuando la tabla es
más ancha que el panel. Como con las listas, el icono de página cambia a texto plano: una fila por línea y las celdas
separadas por comas.

### Estilo: Texto, Relleno, Borde, Espaciado

El estilo del control se reparte en cuatro secciones cortas, con las mismas propiedades que
[`pz.Style`](/pyzed/es/theming/styles/). Los campos vacíos mantienen el aspecto propio del componente, y
**Restablecer el estilo** al final los borra todos. Ver [Estilos y temas](/pyzed/es/editor/styles-and-themes/).

| Sección | Campos |
| --- | --- |
| **Texto** | **Fuente** (familia y peso), **Tamaño** (tamaño de letra e interlineado), **Color**, **Cursiva**. |
| **Relleno** | El fondo: un color, un degradado o una máscara. |
| **Borde** | **Color**, **Ancho** y **Esquinas** (un radio, o uno por esquina con el botón de **enlace**). |
| **Espaciado** | El **modelo de caja**, **Alinear contenido**, **Tamaño máximo** y **Recortar contenido**. |

El modelo de caja se dibuja como en el navegador: un anillo exterior ámbar para el **margen** (espacio fuera del
control) y uno interior verde para el **relleno** o padding (espacio entre su borde y su contenido), con un número
por lado. Arrastra o haz doble clic en cualquiera. **Alinear contenido** es una caja de 3×3: haz clic en un punto
para llevar el contenido a esa esquina, a ese lado o al centro.

La sombra está en **Efectos**, junto a la opacidad, el resplandor, el bloom y el cristal; **Efectos** y **Animación**
se explican en [Animaciones y efectos](/pyzed/es/editor/animations-and-effects/).

### Posición

**Posición** es siempre la primera sección. Para un control colocado libremente (en el formulario, o en un panel,
un group box o una tarjeta):

| Campo | Significado |
| --- | --- |
| **Dentro de** | Solo dentro de un contenedor: el nombre del contenedor (clic para seleccionarlo) y un botón para **sacarlo**. |
| **Alineación** | Seis botones que llevan el control al borde izquierdo, al centro, al borde derecho, arriba, al medio o abajo de su contenedor (o del formulario). |
| **Posición** | **X** e **Y**, respecto al formulario o al contenedor. |
| **Tamaño** | **W** (ancho) y **H** (alto) en píxeles. |
| **L · T**, **R · B** | Aparecen en Posición y Tamaño en lugar de X y W (o Y y H) cuando el control se estira en ese eje: sus distancias a los lados del contenedor. Al cambiar una, el lado opuesto se queda donde está. |
| **Rotación** | Grados en sentido horario, alrededor del pivote (el mismo valor que el `rotate` del estilo). |
| **Anclaje** | El preset de anclaje, dibujado como una caja en un marco, y su nombre (`Arriba · Izquierda`). Púlsalo para abrir la cuadrícula de 4×4 presets (ver abajo). |

**Más opciones** al final muestra los campos que se usan menos:

| Campo | Significado |
| --- | --- |
| **Tamaño mínimo**, **Tamaño máximo** | Límites del ancho y el alto cuando el control se estira (`0`: sin límite), para que un panel estirado se detenga en un ancho legible. |
| **Pivote** | El punto alrededor del que el control gira y escala, y que queda fijo cuando un límite de tamaño frena el estiramiento: `0 0` es la esquina de arriba a la izquierda, `0.5 0.5` (por defecto) el centro, `1 1` la esquina de abajo a la derecha. |

![La sección Posición con los presets de anclaje abiertos](../../../../../screenshots/editor-anchors.png)

Para un hijo de un **auto layout** (una fila o columna flex, o una grilla) la sección cambia, porque lo coloca su
contenedor: **Ancho** y **Alto** dicen cada uno **Fijo** (mantiene ese tamaño) o **Llenar** (ocupa el sitio que deja
el contenedor), **Crecer** reparte el espacio libre entre los hijos que llenan, y en una grilla **Columnas** dice
cuántas celdas ocupa. Estos hijos no tienen X ni Y: arrástralos para reordenarlos. Ver
[Disposición y contenedores](/pyzed/es/editor/layouts/).

### Auto layout

Una fila, columna flex o grilla muestra una sección **Auto layout**, como en Figma:

| Campo | Significado |
| --- | --- |
| **Dirección** | Uno al lado del otro (fila) o uno debajo del otro (columna). Una grilla muestra **Columnas** en su lugar. |
| **Alineación** | Una caja de 3×3: haz clic donde quieres los hijos dentro del contenedor (izquierda, centro o derecha; arriba, medio o abajo). |
| **Separación** | Espacio entre los hijos, o **Espacio entre**, **Espacio alrededor** o **Espacio uniforme** para repartirlos en el sitio libre. Una grilla tiene separación y alto de fila. |
| **Relleno** | Espacio entre el borde del contenedor y sus hijos: horizontal y vertical, o uno por lado con el botón del **cuadrado**. |
| **Llenar a lo ancho** | Los hijos se estiran al alto del contenedor (en una fila) o a su ancho (en una columna). |

Selecciona algunos controles y pulsa <kbd>Shift</kbd>+<kbd>A</kbd> (**Añadir auto layout**) para envolverlos en una
fila o una columna, deducida de cómo están colocados. <kbd>Ctrl</kbd>+<kbd>G</kbd> los agrupa en un panel invisible
sin moverlos, y <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>G</kbd> saca los hijos de un grupo o layout y lo quita,
manteniendo su sitio y su tamaño.

Los presets son los anclajes de Unity, Unreal y Godot. Las columnas dicen cómo sigue el control al ancho
(**Izquierda**, **Centro**, **Derecha** o **Estirar**) y las filas cómo sigue al alto (**Arriba**, **Centro**,
**Abajo** o **Estirar**); la última celda, **Estirar · Estirar**, llena el contenedor. Elegir un preset solo cambia
cómo sigue el control a un cambio de tamaño; activa **Moverlo también allí** para pegarlo además a los bordes a los
que está anclado (centrado, o llenando el contenedor en los ejes estirados). Por dentro, un preset es un conjunto de
bordes, como en WinForms:

| Anclajes | Cuando la ventana crece |
| --- | --- |
| Izquierda + Arriba (por defecto) | El control se queda donde está. |
| Izquierda + Derecha | Se estira en horizontal. |
| Solo derecha | Se mueve con el borde derecho. |
| Ni izquierda ni derecha | Se queda centrado en horizontal. |
| Arriba + Abajo, solo abajo, ninguno | Lo mismo, en vertical. |

### Comportamiento

| Campo | Significado |
| --- | --- |
| **Visible** | Los controles ocultos no se muestran al ejecutar (`form.status.show()` los vuelve a mostrar). |
| **Habilitado** | Los controles deshabilitados se dibujan en gris e ignoran al usuario. |
| **Bloqueado** | Solo en diseño: el control no se puede mover ni redimensionar en el lienzo. |

## Varios controles

Con dos o más controles seleccionados, el panel muestra **Align** (bordes izquierdos, centros, bordes derechos,
bordes superiores, medios, bordes inferiores) y **Spacing and size** (distribuir en horizontal o en vertical, mismo
ancho, mismo alto). Funcionan como los
[botones de la barra de herramientas](/pyzed/es/editor/toolbox-and-canvas/#alinear-distribuir-e-igualar-tamaños).

## El formulario

Haz clic en un hueco del lienzo, o en la primera fila de la estructura, para editar el propio formulario.

| Sección | Campo | Significado |
| --- | --- | --- |
| **Ventana** | **Nombre** | El nombre del formulario: el nombre del archivo y el prefijo de los manejadores del formulario. |
| | **Título** | El título de la ventana. |
| | **Ancho**, **Alto** | El tamaño de la ventana (también con el tirador bajo el lienzo). |
| | **Redimensionable** | Si el usuario puede cambiar el tamaño de la ventana en ejecución. |
| **Aspecto** | **Tema** | Cualquier tema registrado: One Dark, One Light, Ayu, Gruvbox... o el tuyo. |
| | **Acento** | Siete colores de acento predefinidos y **×** para el del tema. |
| | **Acento propio** | Cualquier acento `#rrggbb`. |
| | **Fondo** | Un color para el fondo de la ventana (`theme default` si está vacío). |
| | **Radio de esquina** | El radio de todos los controles (0 a 24). |
| | **Tamaño de letra** | El tamaño base del texto de la ventana. |
| **Estilo** | | El **estilo global** de la ventana: fuente, color del texto, peso, tamaño e interlineado para todo texto que no fije los suyos; fondo, color del borde, radio y relleno de la ventana. |
| **Diseñador** | **Tamaño de cuadrícula** | El paso de cuadrícula de este formulario. |

El aspecto del formulario es independiente del tema del propio editor: un formulario puede ser claro mientras
diseñas en un editor oscuro.
