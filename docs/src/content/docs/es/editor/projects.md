---
title: Proyectos
description: "Crea y abre proyectos de uv en Pyzed Design, busca archivos, gestiona dependencias, ejecuta ruff y ty y crea el repositorio git desde el editor."
sidebar:
  order: 1
---

Una app de Pyzed es un proyecto de [uv](https://docs.astral.sh/uv/) normal: la interfaz vive en `ui/`, el backend
en `src/` y uv gestiona las dependencias. El panel **Proyecto** (dock izquierdo, junto a **Diseño**) muestra los
archivos del proyecto, como el panel de proyecto de Zed o el explorador de VS Code, y el panel **Dependencias** de
al lado gestiona paquetes, herramientas y comprobaciones, todo sin salir del editor. El contexto, la estructura de un proyecto y los comandos `pyzed` equivalentes están en
[Proyectos con uv](/pyzed/es/guides/projects/).

![El panel Proyecto: los archivos y carpetas del proyecto](../../../../../screenshots/designer-project.png)

## Cómo encuentra el editor tu proyecto

Al arrancar, el editor busca un proyecto de Pyzed (un `pyproject.toml` con una tabla `[tool.pyzed]`) en el archivo
que abriste o por encima, o por encima de la carpeta actual. Si lo encuentra:

- **lo abre** en el panel Proyecto, convierte su carpeta en la de trabajo y lo recuerda entre los proyectos
  recientes;
- **lo activa**, para que formularios y manejadores puedan importar los módulos de `ui/`, el paquete de `src/` y
  cualquier dependencia de su `.venv`;
- **descubre sus componentes**: cada `.pzcomp` del proyecto se suma a la caja de herramientas;
- **comprueba sus herramientas** en segundo plano (uv, git, ruff y ty, con sus versiones).

La barra de título muestra entonces el nombre del proyecto antes del archivo: haz clic en él para traer el panel
Proyecto al frente.

## Sin proyecto abierto

Sin proyecto, el panel ofrece **New project** y **Open…**, y lista tus proyectos recientes (clic en uno para
abrirlo).

![El diálogo New project](../../../../../screenshots/editor-new-project.png)

### Nuevo proyecto

| Campo | Qué hace |
| --- | --- |
| **Name** | El nombre del proyecto y de su carpeta. |
| **Location** | La carpeta donde se crea; el diálogo muestra la ruta completa que va a crear. **Browse…** abre el explorador de carpetas: ve hasta una carpeta y pulsa **Choose this folder**. |
| **Backend in src/** | `uv init --package`: un paquete `src/<nombre>/` que se puede importar desde la UI y desde los tests. Apagado da una estructura plana (`uv init --app`). |
| **Git repository** | Ejecuta `git init` y escribe un `.gitignore`. |

**Create** ejecuta uv en segundo plano y luego abre el proyecto nuevo y su formulario principal. La carpeta de
destino tiene que estar vacía o ser ya un proyecto.

### Abrir un proyecto

**Open…** muestra un explorador de carpetas en lugar de un campo de texto:

![El diálogo Open project: lugares, proyectos recientes y las carpetas de la actual](../../../../../screenshots/editor-open-project.png)

- La barra de arriba va a la **carpeta superior** (flecha) o al **inicio**, y cada parte de la ruta se puede
  pulsar. El ojo muestra u oculta las carpetas ocultas.
- El campo de ruta de debajo acepta una carpeta escrita o pegada; <kbd>Enter</kbd> va a ella.
- A la izquierda, los **lugares** habituales (inicio, escritorio, documentos, descargas, los discos) y tus
  proyectos **recientes** (haz clic en uno para abrirlo).
- A la derecha, las carpetas de la actual; haz clic en una para entrar. Las que son proyectos de uv (tienen un
  `pyproject.toml`) llevan la etiqueta **project** y su propio botón **Open**.

**Open**, abajo, abre la carpeta en la que estás cuando es un proyecto. Si el proyecto tiene formulario
principal, se abre en una pestaña.

## El panel del proyecto

### Cabecera

El nombre, la versión y la carpeta del proyecto. A la derecha, la **rama de git** actual, o **Create repository**
cuando la carpeta todavía no es un repositorio (ejecuta `git init` y escribe un `.gitignore`, como Zed), y un
botón de carpeta que abre otro proyecto.

Mientras se ejecuta un comando, una barra con un indicador dice qué está pasando (`Adding httpx`,
`Syncing the environment`...). Los comandos corren en otro hilo, así que puedes seguir diseñando mientras uv
descarga paquetes.

### Archivos

Debajo de la cabecera, los archivos y carpetas del proyecto en árbol, como el panel de proyecto de Zed. Las
carpetas se abren y cierran con un clic (`ui/` y `src/` empiezan abiertas); los archivos se colorean según su
estado en git (modificado, nuevo, borrado, conflicto) y las carpetas toman el color de lo que cambió dentro. Los
entornos virtuales, las cachés y la salida de compilación (`.venv`, `__pycache__`, `build`, `dist`...) no se
muestran; los archivos ocultos como `.gitignore`, sí.

Al hacer clic en un archivo se abre donde corresponde:

| Archivo | Se abre |
| --- | --- |
| `.pzform`, `.pzcomp` | En una pestaña del diseñador. |
| El `.py` de un formulario o componente | Su formulario, con el archivo de código entero en el [panel de código](/pyzed/es/editor/code-editor/). |
| Cualquier otro archivo de texto (`.py`, `.toml`, `.md`, `.json`...) | En una pestaña del panel de código, para editarlo ahí mismo. |
| Imágenes y otros archivos binarios | Con la app del sistema para ese tipo de archivo. |

![Un archivo del proyecto abierto en el panel de código, junto al README](../../../../../screenshots/designer-file-editor.png)

Cada archivo abierto tiene una pestaña en el panel de código, después del código del formulario si está abierto.
El editor resalta la sintaxis según el lenguaje del archivo y tiene buscar y reemplazar
(<kbd>Ctrl</kbd>+<kbd>F</kbd>), ir a una línea (<kbd>Ctrl</kbd>+<kbd>G</kbd>) y todos los atajos de edición; el
autocompletado y los diagnósticos son solo para el código del formulario. Un punto en la pestaña indica cambios sin
guardar: **Save** o <kbd>Ctrl</kbd>+<kbd>S</kbd> (con el foco en el archivo) lo guarda, y al cerrarlo pregunta
antes. Si renombras o borras un archivo en el árbol, su pestaña se actualiza.

La barra sobre el árbol tiene un **buscador** de archivos y carpetas (busca las letras en orden, como el buscador
de archivos de Zed, y el nombre del archivo cuenta más que las carpetas: `crt` encuentra `ui/cart.pzform`),
**New file**, **New folder** (en la carpeta seleccionada), **Collapse all** y **Refresh**. El árbol se recarga solo
al guardar y después de los comandos de uv.

**Clic derecho** sobre un archivo o carpeta (o sobre el espacio vacío bajo el árbol, para la carpeta del
proyecto) abre su menú:

| Opción | Qué hace |
| --- | --- |
| **Open** / **Open with the system app** | Abre el archivo en el editor o con su app predeterminada. |
| **Open in the code editor** | Abre cualquier archivo de texto como texto, también el `.py` de un formulario por separado. |
| **Reveal in file manager** | Lo muestra en Archivos, Finder o el Explorador. |
| **New file…** / **New folder…** | Crea uno en esa carpeta (un archivo nuevo se abre al momento). |
| **Copy path** / **Copy relative path** | Copia la ruta completa o la ruta desde la carpeta del proyecto. |
| **Rename…** | Lo renombra. |
| **Delete…** | Lo borra después de preguntar (una carpeta, con todo lo que tiene); no se puede deshacer. |

### Ir a un archivo

<kbd>Ctrl</kbd>+<kbd>P</kbd> (o **File → Go to file…**) abre una búsqueda sobre todos los archivos y carpetas del
proyecto. Escribe parte de un nombre y pulsa <kbd>Enter</kbd> para el mejor resultado, o haz clic en uno; una
carpeta se muestra en el panel Proyecto.

## El panel Dependencias

Con un proyecto abierto, el dock izquierdo suma un panel **Dependencias** junto a **Proyecto** (si los tres títulos
no caben, los paneles que no se muestran se quedan solo con su icono).

![El panel Dependencias: paquetes, herramientas y la salida de ruff](../../../../../screenshots/designer-dependencies.png)

### Dependencias

| Control | Ejecuta |
| --- | --- |
| Campo **Add package** + **+** (o <kbd>Enter</kbd>) | `uv add <paquetes>`. Escribe varios separados por espacios, o una restricción como `httpx>=0.28`. Marca **dev** para el grupo dev. |
| **Lápiz** en una fila | Abre **Change**: escribe un requisito nuevo (`httpx==0.27.2`, `httpx>=0.28,<1`) y aplícalo. |
| **Flecha arriba** en una fila | Actualiza ese paquete dentro de su restricción. |
| **Papelera** en una fila | `uv remove` del grupo en el que está. |
| **Recargar** en la cabecera de la sección | `uv sync`: hace que `.venv` coincida con `uv.lock`. |
| **Lupa** en la cabecera de la sección | **Check for updates**: busca versiones nuevas; las filas que tienen una muestran `↑versión` en verde (pasa el ratón para ver el cambio). |
| **Flecha arriba** en la cabecera de la sección | Actualiza todos los paquetes. |

Las dependencias de otros grupos muestran su grupo como insignia.

### Herramientas

uv, git, ruff y ty con la versión encontrada, o una insignia roja **missing**. Debajo:

- **Lint** ejecuta `ruff check` en el proyecto.
- **Format** ejecuta `ruff format`.
- **Types** ejecuta `ty check`.

La sección **Output** del final muestra el comando que se ejecutó (`$ ruff check`) y las últimas líneas de su
salida, en rojo si falló. Un comando que falla muestra además una notificación con su última línea.

:::tip
Ruff lee sus reglas de `[tool.ruff]` en `pyproject.toml`, así que **Lint** y los avisos en línea del editor de
código siguen la misma configuración.
:::

## Ejecutar formularios de un proyecto

Cuando el editor corre dentro del entorno del propio proyecto (lo abriste con `uv run pyzed design`), **Ejecutar**
(<kbd>F5</kbd>) ejecuta el formulario en el proceso del editor. Si no (la app independiente, o `pyzed design`
instalado con `uv tool`), **Ejecutar** guarda el formulario y lo arranca con `uv run pyzed run --reload` en el
proyecto, así tiene todas las dependencias de `.venv` y se actualiza al guardar. En los dos casos su salida llega a
la [consola](/pyzed/es/editor/console-and-running/).

## Empaquetar la app

El panel Proyecto no empaqueta apps; usa la línea de comandos en la carpeta del proyecto:

```bash
uv run pyzed build            # una carpeta con el ejecutable para esta plataforma
uv run pyzed build --onefile  # un único archivo
uv run pyzed build --workflow # un workflow de GitHub Actions para Linux, Windows y macOS
```

Ver [Empaquetar y distribuir](/pyzed/es/guides/packaging/).

## La app independiente

**Pyzed Design** también se publica como app independiente para Linux, Windows y macOS: el editor compilado con su
propio Python y el binario de `uv`, sin nada más que instalar. Los proyectos que crea son proyectos de uv normales
con su propio `.venv`, y sus formularios siempre se ejecutan con `uv run`.

:::tip
Si el autocompletado no conoce un paquete que acabas de añadir, pulsa **Restart servers** en los
[ajustes del editor](/pyzed/es/editor/code-editor/#ajustes-del-editor) cuando termine la sincronización: los
servidores de lenguaje leen el `.venv` del proyecto al arrancar.
:::
