---
title: Compilar y distribuir
description: "Empaqueta una app de Pyzed como ejecutable independiente para Windows, macOS y Linux, al estilo de PyInstaller, con código y datos fuera de la UI."
sidebar:
  order: 15
---

`pyzed build` convierte un [proyecto de Pyzed](/pyzed/es/guides/projects/) en una app que funciona en equipos sin
Python: una carpeta (o un único archivo) con el intérprete, `pyzed-ui`, tus dependencias, tu backend y tus forms.
Usa [PyInstaller](https://pyinstaller.org) por debajo, dentro del entorno del propio proyecto, así que no hay
que instalar nada de forma global.

```bash
uv run pyzed build
```

| Plataforma | Resultado | Cómo se ejecuta |
| --- | --- | --- |
| Windows | `dist\Tienda\Tienda.exe` (o `dist\Tienda.exe` con `--onefile`) | Doble clic, o distribuye la carpeta en un zip o un instalador. |
| macOS | `dist/Tienda.app` | Ábrela; fírmala y notarízala para distribuirla (abajo). |
| Linux | `dist/Tienda/Tienda` (o `dist/Tienda` con `--onefile`) | `./Tienda`; si quieres, empaquétala en un AppImage, .deb o Flatpak. |

:::caution[Una compilación por plataforma]
PyInstaller no hace compilación cruzada: compila la app de Windows en Windows, la de macOS en macOS y la de Linux
en Linux. Una matriz de CI hace las tres por ti ([abajo](#compilar-todas-las-plataformas-en-ci)). Para Linux,
compila en la distribución más antigua que quieras soportar, porque la app se enlaza con su glibc.
:::

## Qué se incluye

Los forms cargan sus handlers desde archivos `.py` en tiempo de ejecución, así que PyInstaller no puede seguir sus
imports por sí solo. `pyzed build` cubre ese hueco:

- **La carpeta de UI** se copia como datos, con su estructura (`ui/main.pzform`, `ui/main.py`, módulos
  auxiliares...).
- **Cada módulo que importa la UI** (leído de `ui/**/*.py` con `ast`) se pasa como hidden import, así el backend
  de `src/`, los módulos junto a `pyproject.toml` y los paquetes de terceros entran con todas sus dependencias.
- **El paquete del propio proyecto** (`src/<nombre>`) se incluye entero, también los módulos importados de forma
  dinámica.
- `ui/`, `src/` y la raíz del proyecto se añaden a la ruta de búsqueda de PyInstaller.
- Un pequeño lanzador abre el form principal (`[tool.pyzed] main`) desde el paquete.

El código de fuera del proyecto, como una librería compartida en una carpeta hermana, se incluye como cualquier
otra dependencia una vez instalado en el entorno:

```bash
pyzed add --editable ../facturacion     # y luego `from facturacion import factura` en un handler
```

## Opciones

Las opciones de la línea de comandos tienen prioridad sobre `[tool.pyzed.build]` en `pyproject.toml`:

```bash
pyzed build --onefile      # un único ejecutable en lugar de una carpeta
pyzed build --console      # mantiene la ventana de consola (útil para ver tracebacks)
pyzed build --name Tienda  # nombre del ejecutable
pyzed build --dry-run      # muestra el comando de PyInstaller y termina
```

```toml
[tool.pyzed.build]
name = "Tienda"                          # nombre del ejecutable o del bundle (por defecto, el del proyecto)
onefile = false                          # un archivo autoextraíble en lugar de una carpeta
windowed = true                          # sin ventana de consola en Windows y macOS
icon = "assets/icon.ico"                 # .ico en Windows, .icns en macOS
include = ["assets", "data/precios.csv"] # archivos y carpetas extra, con la misma ruta relativa en el paquete
hidden-imports = ["tienda.plugins.csv"]  # módulos importados con importlib o por nombre
collect = ["babel"]                      # paquetes a incluir enteros: código, datos y binarios
args = ["--noupx"]                       # cualquier otra cosa, se pasa tal cual a PyInstaller
```

Los archivos de `include` quedan bajo la raíz del paquete. Encuéntralos desde tu código con:

```python
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
precios = ROOT / "data" / "precios.csv"
```

Los archivos intermedios van a `build/pyzed/` y el resultado a `dist/`; ambos están en el `.gitignore` de los
proyectos nuevos.

## Compilar todas las plataformas en CI

```bash
pyzed build --workflow     # escribe .github/workflows/build.yml
```

El workflow ejecuta `uv sync --locked` y `uv run pyzed build` en `ubuntu-latest`, `windows-latest` y
`macos-latest` cuando subes un tag `v*` (o al lanzarlo a mano), y guarda cada `dist/` como artefacto descargable.
Edítalo para adjuntar los archivos a una GitHub Release o para firmarlos.

## Firmar y notarizar

Las apps sin firmar funcionan, pero el sistema operativo avisa al usuario la primera vez:

- **macOS**: firma la `.app` con tu Developer ID y notarízala; si no, Gatekeeper la bloquea.

  ```bash
  codesign --deep --force --options runtime --sign "Developer ID Application: Tú (TEAMID)" dist/Tienda.app
  ditto -c -k --keepParent dist/Tienda.app Tienda.zip
  xcrun notarytool submit Tienda.zip --apple-id tu@example.com --team-id TEAMID --wait
  xcrun stapler staple dist/Tienda.app
  ```

- **Windows**: SmartScreen avisa de los ejecutables sin firmar. Fírmalos con `signtool sign /fd SHA256 /a
  dist\Tienda\Tienda.exe` y un certificado de firma de código. Los falsos positivos de los antivirus son más
  habituales con `--onefile`; mejor la compilación en carpeta y un instalador (Inno Setup, WiX).
- **Linux**: no hace falta firmar. Asegúrate de que el equipo de destino tiene las librerías de escritorio
  habituales (X11 o Wayland, y `libxkbcommon`).

## Problemas frecuentes

| Síntoma | Solución |
| --- | --- |
| `ModuleNotFoundError` al arrancar la app | Un módulo importado por nombre o con `importlib`: añádelo a `hidden-imports`, o su paquete a `collect`. Compila con `--console` para ver el traceback. |
| Falta un archivo de datos de una dependencia | Añade el paquete a `collect`. |
| Faltan tus propios archivos | Añádelos a `include` y búscalos desde `sys._MEIPASS` como arriba. |
| La ventana sale en blanco en una máquina virtual | Sin GPU: arráncala con `WGPU_BACKEND=gl` o usa el renderizador por software (`WGPU_BACKEND=dx12` en Linux fuerza tiny-skia). |
| La app ocupa mucho | Excluye lo que no uses con `args = ["--exclude-module", "tkinter"]` y deja las herramientas de compilación en el grupo dev. |

## Otras herramientas

`pyzed build --dry-run` muestra el comando exacto de PyInstaller, que puedes adaptar a otros empaquetadores.
[Nuitka](https://nuitka.net) compila Python a C y puede generar binarios más pequeños y rápidos; ejecútalo desde
el entorno del proyecto con las mismas ideas: incluye la carpeta de UI como datos y los módulos que importa.

```bash
uv run --with nuitka python -m nuitka --standalone --include-data-dir=ui=ui \
  --include-package=tienda --include-package=pyzed --include-package-data=pyzed build/pyzed/tienda_launcher.py
```

(`build/pyzed/tienda_launcher.py` lo escribe `pyzed build --dry-run`.)
