---
title: Build and distribute
description: "Package a Pyzed app as a standalone executable for Windows, macOS and Linux, PyInstaller style, including code and data outside the UI folder."
sidebar:
  order: 15
---

`pyzed build` turns a [Pyzed project](/pyzed/guides/projects/) into an app that runs on machines without Python:
a folder (or a single file) with the interpreter, `pyzed-ui`, your dependencies, your backend and your forms. It
uses [PyInstaller](https://pyinstaller.org) underneath, inside the project's own environment, so nothing has to be
installed globally.

```bash
uv run pyzed build
```

| Platform | Result | Run it |
| --- | --- | --- |
| Windows | `dist\Shop\Shop.exe` (or `dist\Shop.exe` with `--onefile`) | Double-click, or ship the folder in a zip/installer. |
| macOS | `dist/Shop.app` | Open it; sign and notarize it to distribute (below). |
| Linux | `dist/Shop/Shop` (or `dist/Shop` with `--onefile`) | `./Shop`; wrap it in an AppImage, .deb or Flatpak if you like. |

:::caution[One build per platform]
PyInstaller does not cross-compile: build the Windows app on Windows, the macOS app on macOS and the Linux app on
Linux. A CI matrix does all three for you ([below](#build-every-platform-in-ci)). For Linux, build on the oldest
distribution you want to support, because the app links against its glibc.
:::

## What gets bundled

Forms load their handlers from `.py` files at runtime, so PyInstaller cannot follow their imports by itself.
`pyzed build` fills the gaps:

- **The UI folder** is shipped as data, keeping its layout (`ui/main.pzform`, `ui/main.py`, helper modules...).
- **Every module imported by the UI** (read from `ui/**/*.py` with `ast`) is passed as a hidden import, so the
  backend in `src/`, modules next to `pyproject.toml` and third-party packages are bundled with all their
  dependencies.
- **The project's own package** (`src/<name>`) is collected whole, including modules imported dynamically.
- `ui/`, `src/` and the project root are added to PyInstaller's search path.
- A small launcher opens the main form (`[tool.pyzed] main`) from the bundle.

Code outside the project, such as a shared library in a sibling folder, is bundled like any other dependency
once it is installed in the environment:

```bash
pyzed add --editable ../billing     # then `from billing import invoice` in a handler
```

## Options

Command line flags win over `[tool.pyzed.build]` in `pyproject.toml`:

```bash
pyzed build --onefile      # a single executable instead of a folder
pyzed build --console      # keep the console window (useful to see tracebacks)
pyzed build --name Shop    # name of the executable
pyzed build --dry-run      # print the PyInstaller command and stop
```

```toml
[tool.pyzed.build]
name = "Shop"                          # executable / bundle name (default: the project name)
onefile = false                        # one self-extracting file instead of a folder
windowed = true                        # no console window on Windows and macOS
icon = "assets/icon.ico"               # .ico on Windows, .icns on macOS
include = ["assets", "data/prices.csv"]  # extra files and folders, same relative path in the bundle
hidden-imports = ["shop.plugins.csv"]  # modules imported with importlib or by name
collect = ["babel"]                    # packages to ship whole: code, data files and binaries
args = ["--noupx"]                     # anything else, passed to PyInstaller as is
```

Files listed in `include` end up under the bundle root. Find them from your code with:

```python
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
prices = ROOT / "data" / "prices.csv"
```

The intermediate files go to `build/pyzed/` and the result to `dist/`; both are in the `.gitignore` of new
projects.

## Build every platform in CI

```bash
pyzed build --workflow     # writes .github/workflows/build.yml
```

The workflow runs `uv sync --locked` and `uv run pyzed build` on `ubuntu-latest`, `windows-latest` and
`macos-latest` when you push a `v*` tag (or start it by hand), and keeps each `dist/` as a downloadable artifact.
Edit it to attach the files to a GitHub Release or to sign them.

## Signing and notarizing

Unsigned apps work, but the operating system warns the user the first time:

- **macOS**: sign the `.app` with your Developer ID and notarize it, otherwise Gatekeeper blocks it.

  ```bash
  codesign --deep --force --options runtime --sign "Developer ID Application: You (TEAMID)" dist/Shop.app
  ditto -c -k --keepParent dist/Shop.app Shop.zip
  xcrun notarytool submit Shop.zip --apple-id you@example.com --team-id TEAMID --wait
  xcrun stapler staple dist/Shop.app
  ```

- **Windows**: SmartScreen warns about unsigned executables. Sign them with `signtool sign /fd SHA256 /a
  dist\Shop\Shop.exe` and a code signing certificate. Antivirus false positives are more common with
  `--onefile`; prefer the folder build and an installer (Inno Setup, WiX).
- **Linux**: no signing needed. Make sure the target has the usual desktop libraries (X11 or Wayland, and
  `libxkbcommon`).

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ModuleNotFoundError` when the app starts | A module imported by name or with `importlib`: add it to `hidden-imports`, or its package to `collect`. Build with `--console` to see the traceback. |
| A data file of a dependency is missing | Add the package to `collect`. |
| Your own files are missing | Add them to `include` and resolve them from `sys._MEIPASS` as above. |
| The window is blank on a virtual machine | No GPU: start it with `WGPU_BACKEND=gl` or use the software renderer (`WGPU_BACKEND=dx12` on Linux forces tiny-skia). |
| The app is large | Exclude what you do not need with `args = ["--exclude-module", "tkinter"]`, and keep build-only tools in the dev group. |

## Other tools

`pyzed build --dry-run` prints the exact PyInstaller command, which you can adapt to other packagers.
[Nuitka](https://nuitka.net) compiles Python to C and can produce smaller, faster binaries; run it from the
project environment with the same ideas: include the UI folder as data and the modules it imports.

```bash
uv run --with nuitka python -m nuitka --standalone --include-data-dir=ui=ui \
  --include-package=shop --include-package=pyzed --include-package-data=pyzed build/pyzed/shop_launcher.py
```

(`build/pyzed/shop_launcher.py` is written by `pyzed build --dry-run`.)
