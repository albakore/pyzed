---
title: Crear un proyecto
description: "Genera una app de escritorio de Pyzed como proyecto estándar de uv con un comando: la UI en su propia carpeta y ruff, ty y git listos para usar."
---

Pyzed instala el comando `pyzed`. Con [uv](https://docs.astral.sh/uv/) instalado, crea un proyecto completo:

```bash
pyzed new mi-app
cd mi-app
uv run pyzed design     # abre el form principal en el diseñador visual
uv run pyzed run        # ejecuta la app
```

Esto genera un proyecto de uv estándar:

```
mi-app/
├── pyproject.toml     # dependencias (pyzed-ui; ruff y ty para desarrollo) + [tool.pyzed]
├── uv.lock
├── .venv/
├── .git/
├── src/mi_app/        # backend
└── ui/                # forms (.pzform) y sus handlers de eventos (.py)
```

La carpeta de UI separa la interfaz del resto del código, y sus handlers pueden importar el backend, cualquier
módulo del proyecto y todas las dependencias. ¿Ya tienes un proyecto creado con `uv init`? Ejecuta `pyzed init`
dentro. Consulta [Proyectos con uv](/pyzed/es/guides/projects/) para la estructura, los comandos de
dependencias y la pestaña Project del diseñador, y [Compilar y distribuir](/pyzed/es/packaging/build/) para
empaquetar la app en cada plataforma.

## Una app de un solo archivo

Para empezar desde código en lugar del diseñador, `--script` crea un único `main.py` sin uv:

```bash
pyzed new mi-app --script
cd mi-app
python main.py
```

La plantilla ya incluye:

- Un `ui.workspace` con barra de título, panel izquierdo y barra de estado.
- Navegación entre páginas con `ui.list_item`.
- Una paleta de comandos que se abre con <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd>
  y se cierra con <kbd>Esc</kbd>.
- Un botón para alternar entre tema claro y oscuro.

## Buscar iconos

Pyzed incluye los ~2000 iconos de [Lucide](https://lucide.dev). Para buscar nombres:

```bash
pyzed icons folder
# folder, folder-open, folder-git, folder-plus, ...
```

Úsalos con `pz.icon("folder")` o con el parámetro `icon=` de los componentes.

## Ejecutar como módulo

`python -m pyzed` es equivalente al comando `pyzed`:

```bash
python -m pyzed new otra-app
```
