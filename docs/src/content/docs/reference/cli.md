---
title: CLI
description: "Every pyzed command-line command: create projects, manage dependencies, run and build apps, generate icons and start the MCP server."
sidebar:
  order: 9
---

Installing Pyzed adds the `pyzed` command (also available as `python -m pyzed`). Commands that work on a project
look for the nearest `pyproject.toml` from the current folder up. See [Projects with uv](/pyzed/guides/projects/).

## Projects

### `pyzed new <name>`

Creates a uv project in a new folder: `uv init --package`, the `[tool.pyzed]` table, `ui/main.pzform` with its
handlers, `pyzed-ui` as a dependency, `ruff` and `ty` as dev dependencies, and a git repository.

| Option | Effect |
| --- | --- |
| `--app` | Backend next to `pyproject.toml` instead of in `src/` (`uv init --app`). |
| `--python VERSION` | Python version of the project. |
| `--no-git` | No git repository. |
| `--no-sync` | Only write `pyproject.toml` (no resolving or installing). |
| `--script` | A single `main.py` with a workspace, sidebar and command palette, plus `requirements.txt`; no uv. |

### `pyzed init [path]`

Adds Pyzed to the uv project at `path` (default: the current folder), with the same options as `new` except
`--script`. If there is no `pyproject.toml`, it runs `uv init` first. Existing code is not modified.

## Dependencies

| Command | Does |
| --- | --- |
| `pyzed add PACKAGE...` | `uv add`. A constraint (`"httpx==0.27.2"`) changes the version of a package already there. `--dev`, `--group NAME`, `--editable` (local paths). |
| `pyzed remove PACKAGE...` | `uv remove`, in the group the package is in. |
| `pyzed upgrade [PACKAGE...]` | Upgrades the given packages (every one when none is given) within their constraints and syncs. |
| `pyzed sync` | `uv sync`. |
| `pyzed deps [--outdated]` | Lists direct dependencies, their group and locked version (`--outdated`: only those with a newer release). |
| `pyzed check [--fix]` | `ruff check` and `ty check`; exits with 1 if either fails. |

## Running

| Command | Does |
| --- | --- |
| `pyzed design [form or folder]` | Opens the [visual designer](/pyzed/editor/). Inside a project and without a form, opens its main form. |
| `pyzed run [form] [--reload]` | Runs a form with its handlers; default: the project's main form. `--reload` updates the window on save. |
| `pyzed dev script.py [--watch PATH]` | Runs a script with hot reload: saving a file updates the open window. |

## `pyzed build`

Packages the project for the current platform with PyInstaller. See [Build and distribute](/pyzed/guides/packaging/).

| Option | Effect |
| --- | --- |
| `--onefile` | A single executable instead of a folder. |
| `--console` | Keep the console window. |
| `--name NAME` | Name of the executable. |
| `--dry-run` | Print the PyInstaller command. |
| `--workflow` | Write `.github/workflows/build.yml`, which builds on Linux, Windows and macOS. |

## `pyzed icons [filter]`

Lists the names of the bundled Lucide icons that contain `filter`.

```bash
pyzed icons arrow
```

## `pyzed mcp`

Runs the [MCP server for AI agents](/pyzed/guides/mcp/) over stdio, until the client disconnects. It needs the
`mcp` extra: `pip install "pyzed-ui[mcp]"`.

| Option | Effect |
| --- | --- |
| `--transport streamable-http` | Serve over HTTP instead of stdio. |
| `--allow-code` | Offer `screenshot` and the project tools over HTTP too (they are always on over stdio). |
| `--root PATH` | The folder the project tools work in (by default the current one). |
