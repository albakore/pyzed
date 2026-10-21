---
title: CLI
description: "Todos los comandos de la CLI pyzed: crea proyectos, gestiona dependencias, ejecuta y compila apps, genera iconos e inicia el servidor MCP."
sidebar:
  order: 9
---

Al instalar Pyzed se añade el comando `pyzed` (también disponible como `python -m pyzed`). Los comandos que
trabajan sobre un proyecto buscan el `pyproject.toml` más cercano desde la carpeta actual hacia arriba. Consulta
[Proyectos con uv](/pyzed/es/guides/projects/).

## Proyectos

### `pyzed new <nombre>`

Crea un proyecto de uv en una carpeta nueva: `uv init --package`, la tabla `[tool.pyzed]`, `ui/main.pzform` con
sus handlers, `pyzed-ui` como dependencia, `ruff` y `ty` como dependencias de desarrollo y un repositorio git.

| Opción | Efecto |
| --- | --- |
| `--app` | Backend junto a `pyproject.toml` en lugar de en `src/` (`uv init --app`). |
| `--python VERSIÓN` | Versión de Python del proyecto. |
| `--no-git` | Sin repositorio git. |
| `--no-sync` | Solo escribe `pyproject.toml` (no resuelve ni instala nada). |
| `--script` | Un único `main.py` con workspace, barra lateral y paleta de comandos, más `requirements.txt`; sin uv. |

### `pyzed init [ruta]`

Añade Pyzed al proyecto de uv en `ruta` (por defecto, la carpeta actual), con las mismas opciones que `new`
salvo `--script`. Si no hay `pyproject.toml`, ejecuta antes `uv init`. No modifica el código existente.

## Dependencias

| Comando | Hace |
| --- | --- |
| `pyzed add PAQUETE...` | `uv add`. Una restricción (`"httpx==0.27.2"`) cambia la versión de un paquete que ya está. `--dev`, `--group NOMBRE`, `--editable` (rutas locales). |
| `pyzed remove PAQUETE...` | `uv remove`, en el grupo donde esté el paquete. |
| `pyzed upgrade [PAQUETE...]` | Actualiza esos paquetes (todos si no se indica ninguno) dentro de sus restricciones y sincroniza. |
| `pyzed sync` | `uv sync`. |
| `pyzed deps [--outdated]` | Lista las dependencias directas, su grupo y la versión fijada (`--outdated`: solo las que tienen una versión más nueva). |
| `pyzed check [--fix]` | `ruff check` y `ty check`; termina con 1 si alguno falla. |

## Ejecutar

| Comando | Hace |
| --- | --- |
| `pyzed design [form o carpeta]` | Abre el [diseñador visual](/pyzed/es/editor/). Dentro de un proyecto y sin form, abre su form principal. |
| `pyzed run [form] [--reload]` | Ejecuta un form con sus handlers; por defecto, el form principal del proyecto. `--reload` actualiza la ventana al guardar. |
| `pyzed dev script.py [--watch RUTA]` | Ejecuta un script con hot reload: al guardar un archivo se actualiza la ventana abierta. |

## `pyzed build`

Empaqueta el proyecto para la plataforma actual con PyInstaller o Nuitka. Consulta [Cómo funciona la compilación](/pyzed/es/packaging/build/)
y, en Pyzed Design, [Exportar tu aplicación](/pyzed/es/editor/exporting/).

| Opción | Efecto |
| --- | --- |
| `--backend pyinstaller\|nuitka` | El empaquetador (por defecto: `backend` en `pyproject.toml`, si no PyInstaller). |
| `--onefile` | Un único ejecutable en lugar de una carpeta. |
| `--console` | Mantiene la ventana de consola. |
| `--name NOMBRE` | Nombre del ejecutable. |
| `--archive zip\|tar.gz` | Además comprime la aplicación, con el nombre que busca el actualizador (`shop-windows-x86_64.zip`). |
| `--target DESTINO` | Falla si este equipo no compila `DESTINO` (`windows-x64`, `macos-arm64`, `linux-x64`...); lo usa la CI. |
| `--dry-run` | Muestra el comando del empaquetador. |
| `--workflow` | Escribe `.github/workflows/build.yml`, que compila cada destino de `targets` en GitHub Actions. |

## `pyzed icons [filtro]`

Lista los nombres de los iconos de Lucide incluidos que contienen `filtro`.

```bash
pyzed icons arrow
```

## `pyzed mcp`

Arranca el [servidor MCP para agentes de IA](/pyzed/es/guides/mcp/) por stdio, hasta que el cliente se
desconecta. Necesita el extra `mcp`: `pip install "pyzed-ui[mcp]"`.

| Opción | Efecto |
| --- | --- |
| `--transport streamable-http` | Sirve por HTTP en lugar de stdio. |
| `--allow-code` | Ofrece `screenshot` y las herramientas de proyecto también por HTTP (por stdio siempre están). |
| `--root RUTA` | La carpeta donde trabajan las herramientas de proyecto (por defecto, la actual). |
