---
title: Ajustes
description: "Las preferencias de Pyzed Design y de su editor de código: buscador, perfiles, ajustes por proyecto, restaurar valores por defecto, el renderizador del proyecto (GPU o CPU), dónde se guardan los ajustes y cómo traducir el diseñador visual."
sidebar:
  order: 13
---

**Ajustes** (<kbd>Ctrl</kbd>+<kbd>,</kbd>, el engranaje a la derecha de la barra de título, o el menú ☰) reúne en un
solo diálogo todas las preferencias del diseñador y de su editor de código. Los cambios se aplican al momento y se
guardan enseguida; **Listo** cierra el diálogo.

![El diálogo de ajustes](../../../../assets/editor/settings.png)

- **El índice** de la izquierda agrupa las páginas: *Diseñador* (General, Fuentes y tamaño, Lienzo del formulario,
  Ejecución, Logs y errores, Telemetría), *Editor de código* (Apariencia, Cursor, Edición, Borrado, Desplazamiento
  y ajuste de línea, Code lens y diagnósticos, Servidores de lenguaje) y, con un proyecto abierto, *Proyecto*
  (Renderizado). Un número junto a una página cuenta sus ajustes cambiados.
- **Buscar ajustes…** (tiene el foco al abrir el diálogo) encuentra un ajuste por su nombre o su ayuda, en inglés o
  en tu idioma, en todas las páginas.
- **Un punto** tras el nombre de un ajuste indica que no tiene su valor por defecto; el botón **↺** a su derecha lo
  restaura.
- **Restablecer todo** devuelve todos los ajustes del perfil a su valor por defecto. Pide una segunda pulsación, así
  un clic no te hace perder tus ajustes.
- **Abrir el archivo de ajustes** abre el JSON donde escribe la página.

![Buscar en los ajustes](../../../../assets/editor/settings-search.png)

## Perfiles

Un perfil es un conjunto completo de preferencias entre los que puedes cambiar, como los perfiles de VS Code: uno
para el día a día, otro con fuentes grandes para presentar, otro para la pantalla pequeña del portátil... La lista
**Perfil** de arriba a la derecha cambia de uno a otro y lo aplica al momento (tema, fuentes, tamaños, opciones del
editor).

| Botón | Qué hace |
| --- | --- |
| **+** | Un perfil nuevo, copia del que usas, con el nombre que escribas. |
| **✎** | Renombra el perfil en uso. |
| **🗑** | Elimina el perfil en uso y vuelve a *Por defecto*, que no se puede renombrar ni eliminar. |

Los perfiles solo guardan preferencias: la disposición de los paneles, los archivos recientes y el
[keymap](/pyzed/es/editor/keymap/) son los mismos en todos.

![Un perfil con dos ajustes cambiados](../../../../assets/editor/settings-profiles.png)

## Ajustes del proyecto

Con un proyecto abierto, **Usuario | Proyecto** arriba dice adónde van tus cambios:

- **Usuario**: tus ajustes, en el perfil activo. Valen para todos los proyectos.
- **Proyecto**: los ajustes propios del proyecto, guardados en `.pyzed/settings.json` dentro del proyecto, como el
  `.zed/settings.json` de Zed. Mandan sobre los del usuario mientras el proyecto está abierto y viajan con él (sube
  el archivo al repositorio para que los tenga cualquiera que lo abra).

En el ámbito Proyecto el punto marca los ajustes que define el proyecto y **↺** los quita para que vuelva a valer el
del usuario; **Quitar los ajustes del proyecto** los quita todos. En el ámbito Usuario, un ajuste que define el
proyecto muestra *El proyecto define el suyo*. Algunos ajustes son solo del usuario (la ventana de bienvenida, el
marco de ventana, las actualizaciones, el archivo de logs).

![El ámbito Proyecto: el proyecto usa tabulación de 2](../../../../assets/editor/settings-project.png)

```json
{
  "editor": { "tab_size": 2, "hard_tabs": false, "format_on_apply": true },
  "designer": { "grid": 4, "snap": true }
}
```

## Renderizado

**Proyecto → Renderizado** elige cómo dibuja sus ventanas la app del proyecto. Se guarda en el `pyproject.toml`
del proyecto, así que vale cuando el diseñador ejecuta el proyecto, cuando lo ejecutas con `pz.run` o
`pyzed run`, y en la [app exportada](/pyzed/es/editor/exporting/).

| Ajuste | Opciones | Qué hace |
| --- | --- | --- |
| **Renderizador** | Auto, GPU, CPU | *Auto* (por defecto) usa la GPU si hay una de verdad y el renderizador por CPU si no (máquinas virtuales, escritorios remotos). *GPU* la usa siempre: la necesitan los [shaders](/pyzed/es/shading/shaders/). *CPU* (tiny-skia) arranca antes, usa menos memoria y funciona en todas partes. |
| **API gráfica** | Auto, Vulkan, Metal, DirectX 12, OpenGL | La API de la GPU. *Auto* prueba Vulkan, Metal o DirectX 12 y después OpenGL. |
| **GPU** | Auto, Rápida, Ahorra batería | En portátiles con dos GPU: la dedicada o la integrada. |
| **Nombre de la GPU** | Cualquiera, o parte de un nombre | Elige la GPU por su nombre (`nvidia`, `intel`, `radeon`) cuando el equipo tiene varias; Intro lo guarda. |
| **Vsync** | Auto, Activado, Desactivado | *Activado* espera a la pantalla (sin cortes); *Desactivado* dibuja lo más rápido posible (para medir rendimiento). |
| **Modo de presentación** | Auto, Fifo, Relajado, Mailbox, Inmediato | Manda sobre Vsync. *Mailbox* guarda solo el frame más nuevo (poca latencia sin cortes), *Inmediato* muestra cada frame al momento (la menor latencia, puede cortar), *Fifo* espera a la pantalla (menos consumo). Un modo que el sistema no tiene vuelve a vsync activado o desactivado. |
| **Antialiasing** | Auto, Desactivado, 2x, 4x, 8x, 16x | Suaviza los bordes de los dibujos de canvas, gráficos y curvas. *Auto* es 4x; *Desactivado* ahorra trabajo de GPU en equipos modestos. |
| **Latencia de frames** | Auto, 1, 2, 3 | Frames que la GPU puede preparar antes de la pantalla. 1 (por defecto) responde antes a la entrada; 2 o 3 suavizan escenas pesadas en GPU lentas. |
| **Memoria de GPU** | Auto, Poca, Rendimiento | *Poca* (por defecto) reserva en bloques pequeños que libera pronto; *Rendimiento* guarda bloques grandes para reservar menos veces. |
| **Frames por segundo máximos** | Pantalla, 30, 60, 90, 120, 144 | Los frames por segundo máximos de las animaciones. Clics, teclas y contenido nuevo se dibujan siempre al momento. |
| **Frames en segundo plano** | Igual, Pausa, 5, 15, 30 | Lo mismo para ventanas sin el foco; *Pausa* detiene sus animaciones hasta que lo recuperan. |

![El renderizador del proyecto](../../../../assets/editor/settings-rendering.png)

```toml
[tool.pyzed.rendering]
renderer = "gpu"         # "auto", "gpu" o "cpu"
gpu_api = "vulkan"       # "auto", "vulkan", "metal", "dx12" o "gl"
gpu = "intel"            # parte del nombre de la GPU, cuando hay varias
power = "low"            # "auto", "high" o "low"
vsync = "off"            # "auto", "on" u "off"
present = "mailbox"      # "auto", "fifo", "fifo_relaxed", "mailbox" o "immediate"
antialiasing = "8x"      # "auto", "off", "2x", "4x", "8x" o "16x"
frame_latency = "2"      # "auto", "1", "2" o "3"
memory = "performance"   # "auto", "low" o "performance"
max_fps = 30             # 0 sigue a la pantalla
background_fps = 0       # 0 pausa las animaciones de las ventanas sin el foco
```

En código, `App.rendering` hace lo mismo para una app y manda sobre `pyproject.toml`:

```python
class Game(pz.App):
    rendering = pz.Rendering(renderer="gpu", vsync="off")
```

Los ajustes se convierten en las variables de entorno que leen Iced y wgpu (`ICED_BACKEND`, `WGPU_BACKEND`,
`WGPU_ADAPTER_NAME`, `WGPU_POWER_PREF`, `ICED_PRESENT_MODE`, `ICED_MSAA`, `ICED_FRAME_LATENCY`, `ICED_MEMORY`,
`ICED_MAX_FPS`, `ICED_BACKGROUND_FPS`); una que definas tú sigue mandando, así que una app ya instalada se puede
ajustar sin tocar su código. Mientras un proyecto elige su propio
renderizador, Ejecutar arranca siempre el formulario en su propio proceso, porque la ventana del diseñador ya tiene
el suyo.

## Apariencia

| Ajuste | Qué hace |
| --- | --- |
| **Tema** | El tema del editor (One Dark, One Light, Ayu, Gruvbox...). Los formularios conservan su propio tema. |
| **Idioma** | *Idioma del sistema*, English o Español: el idioma de los menús y paneles. |
| **Barra de herramientas** | Muestra u oculta la barra de herramientas. |
| **Barra de estado** | Muestra u oculta la barra de estado. |
| **Ventana de bienvenida** | Abre la [ventana de bienvenida](/pyzed/es/editor/examples/) al iniciar (activada por defecto). |
| **Marco de ventana propio** | Activado por defecto: Pyzed Design dibuja su propia barra de título y botones de ventana, con el estilo de tu sistema. Desactívalo para usar el marco del sistema (se aplica la próxima vez que se abre). |
| **Marco de la vista previa** | El marco de ventana que el lienzo muestra alrededor del formulario: el de este sistema, macOS, Windows 11, GNOME, Ubuntu o KDE Plasma. |

## Fuentes y tamaño

| Ajuste | Qué hace |
| --- | --- |
| **Fuente de la interfaz** | La fuente de los menús, paneles, diálogos y propiedades. *Por defecto* es IBM Plex Sans; la lista tiene las fuentes incluidas, las del sistema y las cargadas con `pz.load_font`. |
| **Tamaño de la interfaz** | Agranda o achica todo el editor, del 75% al 150%, ventanas de paneles incluidas. **Ver → Ampliar la interfaz**, **Reducir la interfaz** y **Restablecer el zoom de la interfaz** hacen lo mismo en pasos del 5%; dales teclas en el [editor de atajos](/pyzed/es/editor/keymap/). |
| **Fuente del código** | La fuente del editor de código y del resto del código. *Por defecto* es IBM Plex Mono. |
| **Tamaño de la fuente del código** | De 8 a 32 puntos, el mismo ajuste que en los [ajustes del editor de código](/pyzed/es/editor/code-editor/#ajustes-del-editor). |
| **Interlineado del código** | Compacto, Normal o Amplio. |

Cada cambio se ve al momento, sin reiniciar, y se guarda para la próxima vez.

:::tip
Una fuente monoespaciada mantiene alineadas las columnas del código: elige una para **Fuente del código** (su
nombre suele decir *Mono* o *Code*). Para la interfaz se ve mejor una fuente con pesos normal, medio y seminegrita.
:::

## Lienzo del formulario

| Ajuste | Qué hace |
| --- | --- |
| **Mostrar la cuadrícula** | La cuadrícula de puntos del lienzo (también <kbd>G</kbd>). |
| **Ajustar a la cuadrícula** | Redondea posiciones y tamaños a la cuadrícula. |
| **Guías inteligentes** | Alinea con otros controles al arrastrar. |
| **Ojo de la estructura** | **Oculto al ejecutar** (lo normal): el ojo apaga Visible; el control tampoco se ve en el lienzo, salvo mientras está seleccionado. **Oculto solo en el editor**: el ojo lo oculta solo en el lienzo y al ejecutar el formulario se sigue viendo. |
| **Mostrar todos los controles ocultos** | Dibuja atenuados todos los controles con Visible apagado. Apagado (lo normal), un control oculto solo aparece mientras él o algo dentro de él está seleccionado. |
| **Cuadrícula de los formularios nuevos** | El paso de cuadrícula (2 a 64) que reciben los formularios y componentes que creas. Luego cada formulario conserva el suyo en Propiedades. |

## Ejecución

| Ajuste | Qué hace |
| --- | --- |
| **Guardar antes de ejecutar** | <kbd>F5</kbd> guarda antes el documento. |
| **Abrir la consola al ejecutar** | Trae la consola al frente cuando arranca un formulario. |
| **Registrar los eventos en la consola** | Escribe cada evento que atiende el formulario en ejecución, con su valor y su manejador. |
| **Modo restringido** | Pregunta antes de instalar los paquetes de un proyecto que no creaste, importar sus componentes o ejecutarlo ([modo restringido](/pyzed/es/editor/projects/#modo-restringido)). Activado por defecto; solo tus propios ajustes pueden apagarlo. |

## Gestores de paquetes

**Gestor de paquetes de los proyectos** es el que los crea e instala sus paquetes. Los proyectos de Pyzed son proyectos de uv (`pyproject.toml` y `uv.lock`), así que por ahora es uv; la página se arma a partir de un registro de gestores de paquetes, así que los nuevos aparecen aquí con sus propios ajustes.

Cada gestor de paquetes tiene su grupo. Arriba, el grupo lista cada ejecutable que Pyzed encuentra, con su versión y su ruta, y marca el que está **En uso**:

- **Incluido con Pyzed**: el que trae Pyzed Design. Solo cambia cuando se actualiza el editor.
- **El de este equipo**: uno instalado por su cuenta (para uv, en el `PATH` o en `~/.local/bin`). **Instalar** lo instala (el instalador oficial de uv) y **Actualizar** lo actualiza (`uv self update`), aparte del editor.
- **Ruta personalizada**: cualquier otro ejecutable.

| Ajuste | Qué hace |
| --- | --- |
| **Ejecutable que se usa** | *Automático* usa el de este equipo si está instalado; si no, el incluido. Las demás opciones eligen uno; si falta, Pyzed vuelve a *Automático* para que los proyectos sigan funcionando. |
| **Ruta del ejecutable personalizado** | Aparece con *Ruta personalizada*. <kbd>Intro</kbd> la guarda. |

Los valores por defecto de uv:

| Ajuste | Qué hace |
| --- | --- |
| **Python de los proyectos nuevos** | La versión de Python que piden los proyectos nuevos, como `3.13` (`uv init --python`). Vacío: la más reciente que uv encuentre o instale. |
| **Índice de paquetes** | Otro índice en lugar de PyPI, como el espejo de una empresa (`UV_DEFAULT_INDEX`). |
| **Más índices de paquetes** | Índices donde buscar también, separados por espacios (`UV_INDEX`). |
| **Permitir versiones preliminares** | Versiones preliminares de todos los paquetes (`UV_PRERELEASE=allow`). |
| **Sin conexión** | Solo los paquetes ya descargados, sin red (`UV_OFFLINE`). |
| **Cómo se instalan los paquetes** | Copiar, enlaces duros, enlaces simbólicos o clonar (`UV_LINK_MODE`). Copiar es lo más seguro entre unidades. |

Se aplican a cada comando que ejecuta el editor: crear un proyecto, la pestaña Dependencias, Ejecutar y la exportación. Son tus propios ajustes, nunca los de un proyecto: lo que necesite un proyecto va en su `pyproject.toml` (`[tool.uv]`). La pestaña Dependencias dice qué uv se usa junto a su versión.

## Logs y errores

| Ajuste | Qué hace |
| --- | --- |
| **Mostrar un diálogo con los errores** | Abre el [diálogo de error](/pyzed/es/editor/console-and-running/#cuando-falla-el-propio-editor) cuando algo falla. Apagado, los errores solo van al panel Logs. |
| **Escribir un archivo de log** | Escribe además los [logs](/pyzed/es/editor/console-and-running/#el-panel-logs) en `logs/pyzed-design.log`, en la carpeta de configuración de Pyzed (se aplica al reiniciar). |

## Más

El final del índice enlaza con el resto:

| Elemento | Qué hace |
| --- | --- |
| **Atajos de teclado** | El [editor de keymap](/pyzed/es/editor/keymap/): cambia las teclas de cualquier acción. |
| **Agentes de IA** | Los [ajustes del agente](/pyzed/es/editor/ai-agents/#ajustes): proveedores de modelos, claves e inicio de sesión con el navegador, modelo predeterminado, esfuerzo y permisos. |
| **Restablecer los paneles** | Devuelve cada panel a su dock y tamaño iniciales. |

## Telemetría

El diseñador puede guardar datos de uso y rendimiento para ayudar a mejorarlo, pero solo si la activas: viene
**desactivada**. En **Ajustes → Telemetría**, *Recopilar datos de uso y rendimiento* registra:

- cuántas veces usas cada comando y cada acción del editor (`command.save`, `editor.select_next`…);
- cuánto tarda el diseñador en arrancar, en dibujar un fotograma y en ejecutar cada comando (cantidad, total,
  máximo y un histograma);
- el número de sesiones y su duración.

Nunca registra tu código, textos, nombres de formularios o de archivos, ni rutas. Los datos se guardan en
`telemetry.json` en la carpeta de configuración de Pyzed; **Ver** lo abre y **Borrar** lo vacía (y cambia el id
aleatorio de la instalación).

Nada sale de tu equipo salvo que además indiques un **Destino**: entonces el diseñador envía allí los datos como
JSON al cerrarse y vuelve a contar desde cero. Si el envío falla, se reintenta la próxima vez.
`PYZED_TELEMETRY=0` desactiva la telemetría digan lo que digan los ajustes.

```json
{"schema": 1, "installation": "4f0c…", "app": "pyzed-designer", "version": "0.4.0", "os": "linux",
 "arch": "x86_64", "python": "3.13", "since": "…", "until": "…", "sessions": 3,
 "counters": {"command.save": 12, "editor.select_next": 7},
 "timings": {"render": {"count": 840, "total_ms": 2210.4, "max_ms": 41.2, "buckets": [690, 120, 25, 5, 0, 0, 0, 0]}}}
```

Los `buckets` cuentan duraciones de hasta 4, 8, 16, 33, 50, 100 y 250 ms, y las más largas.

## Dónde se guardan

Todo lo que recuerda el editor va a un único archivo, `designer.json`, en la carpeta de ajustes de Pyzed:

| Plataforma | Carpeta |
| --- | --- |
| Windows | `%APPDATA%\pyzed` |
| macOS | `~/Library/Application Support/pyzed` |
| Linux | `$XDG_CONFIG_HOME/pyzed` o `~/.config/pyzed` |

Define `PYZED_CONFIG_DIR` para usar otra carpeta (útil para una instalación portátil o para tests). El archivo tiene
dos secciones: `"designer"` (tema, idioma, valores del lienzo, barra de herramientas y de estado, opciones de
ejecución, archivos recientes, y en qué dock está cada panel, qué docks están ocultos y sus tamaños) y `"editor"`
(el editor de código). Ambas guardan el perfil activo; `"profile"` lo nombra y `"profiles"` guarda los demás (solo lo
que difiere de los valores por defecto). Los ajustes propios de un proyecto están en su `.pyzed/settings.json`. Los
valores no válidos se ignoran y se usan los de por defecto, así que un archivo editado a
mano no puede romper el editor.

```json
{
  "designer": { "theme": "One Light", "language": "es", "ui_font": "Inter", "ui_scale": 1.1, "grid": 8, "snap": true, "console_on_run": true,
                "docks": { "events": "left" }, "sizes": { "right": 360 }, "recent": ["/home/ada/shop/ui/main.pzform"] },
  "editor": { "font_family": "JetBrains Mono", "font_size": 15, "tab_size": 4, "minimap": false, "cursor_shape": "block", "format_on_apply": true }
}
```

## Traducir el editor

La interfaz del editor se traduce con [`pz.t`](/pyzed/es/guides/i18n/). El inglés y el español vienen incluidos;
añade un catálogo bajo la clave `designer` para traducirlo a otro idioma. El ajuste **Idioma** ofrece los incluidos;
para otro idioma, deja que el editor siga al sistema o pon `"language"` en la sección `designer` de
`designer.json`.

Las cadenas que faltan se muestran en inglés, así que una traducción parcial ya funciona.
