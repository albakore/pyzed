---
title: Proyectos
description: Crea y abre proyectos de uv, gestiona dependencias, ejecuta ruff y ty y crea el repositorio git desde el panel Proyecto.
sidebar:
  order: 1
---

Una app de Pyzed es un proyecto de [uv](https://docs.astral.sh/uv/) normal: la interfaz vive en `ui/`, el backend
en `src/` y uv gestiona las dependencias. El panel **Proyecto** (dock izquierdo, junto a **Diseño**) hace todo eso
sin salir del editor. El contexto, la estructura de un proyecto y los comandos `pyzed` equivalentes están en
[Proyectos con uv](/pyzed/es/guides/projects/).

![El panel Proyecto: formularios, dependencias, herramientas y la salida de ruff](../../../../../screenshots/designer-project.png)

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
| **Location** | La carpeta donde se crea; el diálogo muestra la ruta completa que va a crear. |
| **Backend in src/** | `uv init --package`: un paquete `src/<nombre>/` que se puede importar desde la UI y desde los tests. Apagado da una estructura plana (`uv init --app`). |
| **Git repository** | Ejecuta `git init` y escribe un `.gitignore`. |

**Create** ejecuta uv en segundo plano y luego abre el proyecto nuevo y su formulario principal. La carpeta de
destino tiene que estar vacía o ser ya un proyecto.

### Abrir un proyecto

Escribe (o pega) una carpeta que tenga un `pyproject.toml` y pulsa <kbd>Enter</kbd> u **Open**, o elige uno de los
proyectos recientes de la lista. Si el proyecto tiene formulario principal, se abre en una pestaña.

## El panel del proyecto

### Cabecera

El nombre, la versión y la carpeta del proyecto. A la derecha, la **rama de git** actual, o **Create repository**
cuando la carpeta todavía no es un repositorio (ejecuta `git init` y escribe un `.gitignore`, como Zed).

Mientras se ejecuta un comando, una barra con un indicador dice qué está pasando (`Adding httpx`,
`Syncing the environment`...). Los comandos corren en otro hilo, así que puedes seguir diseñando mientras uv
descarga paquetes.

### Formularios

Todos los `.pzform` de la carpeta de UI del proyecto. Haz clic en uno para abrirlo en una pestaña; el abierto está
resaltado. El icono de carpeta al final de la sección abre otro proyecto.

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
