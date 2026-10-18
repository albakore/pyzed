---
title: Projects with uv
description: Create and manage Pyzed apps as standard uv projects, with the UI in its own folder and ruff, ty and git ready.
sidebar:
  order: 14
---

A Pyzed project is a normal [uv](https://docs.astral.sh/uv/) project. The interface lives in its own folder
(`ui/`) and the rest of the code stays where uv puts it, so the frontend and the backend are separated but can
still import each other. Dependencies are managed by uv, [ruff](https://docs.astral.sh/ruff/) lints and formats,
[ty](https://docs.astral.sh/ty/) checks types, and the project starts as a git repository.

## Create a project

```bash
pyzed new shop          # uv init + pyzed-ui + ruff + ty + git
cd shop
uv run pyzed design     # edit ui/main.pzform
uv run pyzed run        # run it
```

```
shop/
├── pyproject.toml     # uv project + [tool.pyzed]
├── uv.lock
├── .venv/             # created by uv sync
├── .python-version
├── .gitignore
├── src/shop/          # backend: plain Python, no UI code
│   └── __init__.py
└── ui/                # frontend: forms and their handlers
    ├── main.pzform
    └── main.py
```

The starter form calls a function of the backend, so you can see the import across folders working:

```python
# ui/main.py
from shop import greeting


def greet_click(form, event):
    form.message.text = greeting(form.name_input.text or "world")
```

| Option | Effect |
| --- | --- |
| `--app` | No `src/`: backend modules go next to `pyproject.toml` (`uv init --app`). |
| `--python 3.12` | Python version of the project (uv downloads it if needed). |
| `--no-git` | Do not create a git repository. |
| `--no-sync` | Only write `pyproject.toml`; do not resolve or install anything (offline). |
| `--script` | The old single-file app (`main.py` + `requirements.txt`), without uv. |

## Add Pyzed to an existing uv project

If you start projects with `uv init`, keep doing it and add the UI afterwards:

```bash
uv init --package shop && cd shop
uvx --from pyzed-ui pyzed init     # or `pyzed init` if pyzed is installed
```

`pyzed init` never touches your code: it adds the `[tool.pyzed]` table, creates `ui/` with a starter form, and
adds `pyzed-ui` (and `ruff`/`ty` as dev dependencies) with `uv add`. Run it in a folder without
`pyproject.toml` and it runs `uv init` first.

```toml
[tool.pyzed]
ui = "ui"                    # the UI folder
main = "ui/main.pzform"      # opened by `pyzed design`/`pyzed run` and started by `pyzed build`
```

## Importing code outside the UI folder

Forms and their handlers can import anything in the project. `pyzed run`, `pyzed design` and `pyzed build`
*activate* the project first, which puts these folders on `sys.path`:

1. `ui/`: helper modules next to the handlers (`from helpers import money`).
2. `src/`: the backend package, even before `uv sync` installs it.
3. The project root: modules next to `pyproject.toml` (`--app` layout).
4. The `.venv` site-packages, when the designer runs on a different interpreter of the same Python version,
   so every dependency installed with `uv add` resolves too.

Anything else (a sibling repository, a shared library) is just another dependency: add it with a path and uv
installs it in editable mode.

```bash
pyzed add --editable ../billing   # uv add --editable ../billing
```

From your own scripts, do the same with `pyzed.project`:

```python
from pyzed import project

project.find().activate()   # the project containing the current folder
```

## Dependencies

Every command runs uv in the project folder and prints its output.

| Command | Runs |
| --- | --- |
| `pyzed add httpx` | `uv add httpx` |
| `pyzed add "httpx==0.27.2"` | Changes the constraint of a package already there. |
| `pyzed add --dev pytest` | `uv add --dev pytest` (`--group docs` for other groups). |
| `pyzed remove httpx` | `uv remove httpx` (finds the group by itself). |
| `pyzed upgrade` | `uv lock --upgrade` + `uv sync` (every package). |
| `pyzed upgrade httpx` | `uv lock --upgrade-package httpx` + `uv sync`. |
| `pyzed sync` | `uv sync`: makes `.venv` match `uv.lock`. |
| `pyzed deps [--outdated]` | Lists direct dependencies with their locked (and newest) versions. |
| `pyzed check [--fix]` | `ruff check` and `ty check` with the project's `.venv`. |

Plain `uv` commands work just as well; Pyzed only reads `pyproject.toml` and `uv.lock`.

## The Project tab of the designer

The designer has a **Project** tab next to the toolbox. It opens the project the form belongs to, or offers
**New project** and **Open…** (with your recent projects) when there is none.

![The Project tab: forms, dependencies, tools and the output of ruff](../../../../screenshots/designer-project.png)

- **Forms**: every `.pzform` in the UI folder; click one to open it.
- **Dependencies**: add a package (tick *dev* for the dev group), change its version (pencil), upgrade it or
  remove it. The toolbar syncs the environment, checks for updates (shown in green) and upgrades everything.
- **Tools**: the versions of uv, git, ruff and ty found. **Lint**, **Format** and **Types** run ruff and ty
  and show their output below.
- **Create repository** (in the header) runs `git init` and writes a `.gitignore`, like Zed. Once there is a
  repository the header shows its branch.

Commands run in the background, so the designer stays responsive while uv downloads packages.

When the designer is not running inside the project's environment (for example the standalone Pyzed Design,
or `pyzed design` installed with `uv tool`), **F5** saves the form and starts it with
`uv run pyzed run --reload`, so it has all the project's dependencies and updates on every save.

## Pyzed Design as a standalone app

Each [release](https://github.com/albakore/pyzed/releases) includes **Pyzed Design** for Linux, Windows and
macOS (`pyzed-design-*.zip`): the designer compiled with its own Python and the `uv` binary. Unzip it and run it;
nothing else needs to be installed. Projects created from it are normal uv projects with their own `.venv`.

To build it yourself on the current platform:

```bash
python -m pip install pyzed-ui pyinstaller uv
python scripts/build_designer.py      # dist/Pyzed Design/ and dist/pyzed-design-<os>-<arch>.zip
```

## From Python

```python
from pyzed import project

shop = project.init("shop", git=True)      # returns a Project
shop.add("httpx")                          # every command returns a Result(code, output)
shop.upgrade("httpx")
print([(d.name, d.locked) for d in shop.dependencies()])
print(shop.check().output, shop.typecheck().output)
shop.git_init()
```

To package the app for each platform, see [Build and distribute](/pyzed/guides/packaging/).
