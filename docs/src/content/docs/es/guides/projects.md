---
title: Proyectos con uv
description: "Crea y gestiona apps de escritorio de Pyzed como proyectos estándar de uv, con la UI en su propia carpeta y ruff, ty y git listos desde el principio."
sidebar:
  order: 14
---

Un proyecto de Pyzed es un proyecto de [uv](https://docs.astral.sh/uv/) normal. La interfaz vive en su propia
carpeta (`ui/`) y el resto del código queda donde lo pone uv, así el frontend y el backend están separados pero
pueden importarse entre sí. Las dependencias las gestiona uv, [ruff](https://docs.astral.sh/ruff/) revisa y da
formato, [ty](https://docs.astral.sh/ty/) comprueba los tipos y el proyecto nace como repositorio git.

## Crear un proyecto

```bash
pyzed new tienda          # uv init + pyzed-ui + ruff + ty + git
cd tienda
uv run pyzed design       # edita ui/main.pzform
uv run pyzed run          # ejecútalo
```

```
tienda/
├── pyproject.toml     # proyecto de uv + [tool.pyzed]
├── uv.lock
├── .venv/             # lo crea uv sync
├── .python-version
├── .gitignore
├── src/tienda/        # backend: Python normal, sin código de UI
│   └── __init__.py
└── ui/                # frontend: forms y sus handlers
    ├── main.pzform
    └── main.py
```

El form inicial llama a una función del backend, para que veas funcionar el import entre carpetas:

```python
# ui/main.py
from tienda import greeting


def greet_click(form, event):
    form.message.text = greeting(form.name_input.text or "world")
```

| Opción | Efecto |
| --- | --- |
| `--app` | Sin `src/`: los módulos del backend van junto a `pyproject.toml` (`uv init --app`). |
| `--python 3.12` | Versión de Python del proyecto (uv la descarga si hace falta). |
| `--no-git` | No crea un repositorio git. |
| `--no-sync` | Solo escribe `pyproject.toml`; no resuelve ni instala nada (sin conexión). |
| `--script` | La app de un solo archivo de antes (`main.py` + `requirements.txt`), sin uv. |

## Añadir Pyzed a un proyecto de uv existente

Si empiezas tus proyectos con `uv init`, sigue haciéndolo y añade la UI después:

```bash
uv init --package tienda && cd tienda
uvx --from pyzed-ui pyzed init     # o `pyzed init` si tienes pyzed instalado
```

`pyzed init` no toca tu código: añade la tabla `[tool.pyzed]`, crea `ui/` con un form inicial y añade `pyzed-ui`
(y `ruff`/`ty` como dependencias de desarrollo) con `uv add`. Si lo ejecutas en una carpeta sin `pyproject.toml`,
primero ejecuta `uv init`.

```toml
[tool.pyzed]
ui = "ui"                    # la carpeta de la UI
main = "ui/main.pzform"      # lo abren `pyzed design`/`pyzed run` y lo arranca `pyzed build`
```

## Importar código de fuera de la carpeta de UI

Los forms y sus handlers pueden importar cualquier cosa del proyecto. `pyzed run`, `pyzed design` y `pyzed build`
*activan* antes el proyecto, lo que añade estas carpetas a `sys.path`:

1. `ui/`: módulos auxiliares junto a los handlers (`from helpers import money`).
2. `src/`: el paquete del backend, incluso antes de que `uv sync` lo instale.
3. La raíz del proyecto: módulos junto a `pyproject.toml` (estructura `--app`).
4. El site-packages de `.venv`, cuando el diseñador corre en otro intérprete de la misma versión de Python, para
   que también se resuelvan todas las dependencias instaladas con `uv add`.

Cualquier otra cosa (un repositorio hermano, una librería compartida) es una dependencia más: añádela con su
ruta y uv la instala en modo editable.

```bash
pyzed add --editable ../facturacion   # uv add --editable ../facturacion
```

Desde tus propios scripts, haz lo mismo con `pyzed.project`:

```python
from pyzed import project

project.find().activate()   # el proyecto que contiene la carpeta actual
```

## Dependencias

Cada comando ejecuta uv en la carpeta del proyecto y muestra su salida.

| Comando | Ejecuta |
| --- | --- |
| `pyzed add httpx` | `uv add httpx` |
| `pyzed add "httpx==0.27.2"` | Cambia la restricción de un paquete que ya está. |
| `pyzed add --dev pytest` | `uv add --dev pytest` (`--group docs` para otros grupos). |
| `pyzed remove httpx` | `uv remove httpx` (encuentra el grupo solo). |
| `pyzed upgrade` | `uv lock --upgrade` + `uv sync` (todos los paquetes). |
| `pyzed upgrade httpx` | `uv lock --upgrade-package httpx` + `uv sync`. |
| `pyzed sync` | `uv sync`: deja `.venv` igual que `uv.lock`. |
| `pyzed deps [--outdated]` | Lista las dependencias directas con su versión fijada (y la más nueva). |
| `pyzed check [--fix]` | `ruff check` y `ty check` con el `.venv` del proyecto. |

Los comandos de `uv` funcionan igual de bien; Pyzed solo lee `pyproject.toml` y `uv.lock`.

## La pestaña Project del diseñador

El diseñador tiene una pestaña **Project** junto a la caja de herramientas. Abre el proyecto al que pertenece el
form o, si no hay ninguno, ofrece **New project** y **Open…** (un explorador de carpetas con tus proyectos
recientes).

![La pestaña Project: los archivos y carpetas del proyecto](../../../../../screenshots/designer-project.png)

- **Project** muestra los archivos del proyecto en árbol, como Zed o VS Code, coloreados según git. Busca archivos y
  carpetas desde su barra o con <kbd>Ctrl</kbd>+<kbd>P</kbd>; con clic derecho tienes nuevo archivo, nueva carpeta,
  renombrar, borrar, copiar la ruta y mostrar en el gestor de archivos. Los forms y componentes se abren en el
  diseñador; los demás archivos, con la app del sistema.
- **Dependencies**, una pestaña propia al lado: añade un paquete (marca *dev* para el grupo de desarrollo), cambia
  su versión (lápiz), actualízalo o quítalo. Su barra sincroniza el entorno, busca actualizaciones (se ven en verde)
  y actualiza todo. Debajo, **Tools** muestra las versiones de uv, git, ruff y ty; **Lint**, **Format** y **Types**
  ejecutan ruff y ty y muestran su salida.
- **Create repository** (en la cabecera) ejecuta `git init` y escribe un `.gitignore`, como Zed. Cuando ya hay
  repositorio, la cabecera muestra su rama.

Los comandos corren en segundo plano, así el diseñador sigue respondiendo mientras uv descarga paquetes.

Cuando el diseñador no corre dentro del entorno del proyecto (por ejemplo Pyzed Design compilado, o `pyzed
design` instalado con `uv tool`), **F5** guarda el form y lo arranca con `uv run pyzed run --reload`, así tiene
todas las dependencias del proyecto y se actualiza al guardar.

## Pyzed Design como app independiente

Cada [release](https://github.com/albakore/pyzed/releases) incluye **Pyzed Design** para Linux, Windows y macOS
(`pyzed-design-*.zip`): el diseñador compilado con su propio Python y el binario de `uv`. Descomprímelo y
ejecútalo; no hace falta instalar nada más. Los proyectos que crees desde él son proyectos de uv normales con su
propio `.venv`.

Para compilarlo tú mismo en la plataforma actual:

```bash
python -m pip install pyzed-ui pyinstaller uv
python scripts/build_designer.py      # dist/Pyzed Design/ y dist/pyzed-design-<so>-<arq>.zip
```

### Actualizaciones

Como Zed, Pyzed Design consulta GitHub una vez al día por si hay una versión nueva (se desactiva en
**Ayuda → Buscar actualizaciones automáticamente**, o se consulta ya con **Ayuda → Buscar actualizaciones**).
Si la hay, la barra de estado muestra **Actualizar a X.Y.Z**: abre una pestaña **Novedades** con las notas de la
versión y un botón **Descargar e instalar**. La descarga de tu plataforma se verifica con el SHA-256 de la
release y se descomprime en segundo plano; luego **Reiniciar para actualizar** cierra la app, cambia su carpeta
(el `.app` en macOS) por la nueva y la vuelve a abrir. Tras actualizar, la pestaña Novedades se abre sola con las
notas de la versión nueva, y **Ayuda → Novedades** las muestra cuando quieras. **Omitir esta versión** oculta
una actualización hasta que salga otra más nueva.

**Ayuda → Recibir versiones preliminares** cambia al canal preliminar, que también recibe las pre-releases
(`X.Y.Z-rc.N`). Los instaladores ([Descargar](/pyzed/es/download/#cómo-se-instala)) dejan la app en una carpeta
tuya, así que puede reemplazarse a sí misma; si no, descarga otra vez el instalador o el zip nuevo. Cuando el diseñador se ejecuta desde Python (`pip` o `uv`), la pestaña muestra el comando que actualiza el
paquete.

Tus propias apps compiladas pueden usar el mismo actualizador, `pyzed.updater`:

```python
from pyzed import updater

release = updater.latest("yo/mi-app")              # la GitHub Release más nueva
if updater.is_newer(release.version, "1.0.0"):
    asset = release.asset_for(updater.asset_name("mi-app"))   # mi-app-<so>-<arq>.zip
    app = updater.extract(updater.download(asset))
    updater.replace_on_exit(app)                    # y cierra; arranca la versión nueva
```

## Desde Python

```python
from pyzed import project

tienda = project.init("tienda", git=True)    # devuelve un Project
tienda.add("httpx")                          # cada comando devuelve un Result(code, output)
tienda.upgrade("httpx")
print([(d.name, d.locked) for d in tienda.dependencies()])
print(tienda.check().output, tienda.typecheck().output)
tienda.git_init()
```

Para empaquetar la app en cada plataforma, consulta [Compilar y distribuir](/pyzed/es/packaging/build/).
