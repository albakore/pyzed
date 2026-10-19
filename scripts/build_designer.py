"""Builds Pyzed Design as a standalone app for this platform (with PyInstaller).

The app bundles Python, pyzed-ui and the ``uv`` binary, so it can create and manage
projects (``uv init``, ``uv add``...) on machines with nothing else installed. Each
project keeps its own environment in ``.venv``; forms run there through ``uv run``.

    python -m pip install pyzed-ui pyinstaller uv
    python scripts/build_designer.py            # -> dist/Pyzed Design[.app|.exe] and a .zip

Run it on each OS (the release workflow does it on Linux, Windows and macOS).
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

NAME = "Pyzed Design"
ROOT = Path(__file__).resolve().parent.parent

ENTRY = '''"""Pyzed Design: the visual designer and project manager of Pyzed."""

import sys

from pyzed.designer import design

if __name__ == "__main__":
    design(sys.argv[1] if len(sys.argv) > 1 else None)
'''


def uv_binary() -> str:
    try:
        from uv import find_uv_bin  # type: ignore[import-not-found]

        return find_uv_bin()
    except ImportError:
        found = shutil.which("uv")
        if not found:
            sys.exit("error: install uv first (python -m pip install uv)")
        return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "dist"), help="output folder")
    parser.add_argument("--no-zip", action="store_true", help="do not zip the result")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    work = ROOT / "build" / "designer"
    work.mkdir(parents=True, exist_ok=True)
    entry = work / "pyzed_design.py"
    entry.write_text(ENTRY, encoding="utf-8")
    icon = ROOT / "assets" / ("icon.icns" if sys.platform == "darwin" else "icon.ico")
    command = [
        sys.executable, "-m", "PyInstaller", str(entry), "--name", NAME, "--noconfirm", "--clean", "--windowed",
        "--distpath", str(out), "--workpath", str(work), "--specpath", str(work),
        "--collect-all", "pyzed",
        # uv goes next to the executable, where pyzed.project.find_uv() looks for it
        "--add-binary", f"{uv_binary()}{os.pathsep}.",
    ]
    # the Agent panel's optional dependencies (Claude's SDK and the system keychain), when installed
    for package in ("anthropic", "keyring"):
        if importlib.util.find_spec(package):
            command += ["--collect-all", package]
    if icon.exists():
        command += ["--icon", str(icon)]
    if sys.platform == "darwin":
        command += ["--osx-bundle-identifier", "dev.pyzed.design"]
    print(" ".join(command))
    subprocess.run(command, check=True)
    if not args.no_zip:
        from pyzed import updater

        # the same name the designer's updater looks for in each release
        bundle = out / (f"{NAME}.app" if sys.platform == "darwin" else NAME)
        archive = str(out / updater.asset_name("pyzed-design"))
        if sys.platform == "darwin":
            # ditto keeps the bundle's symlinks and signature, which the updater unpacks with ditto too
            subprocess.run(["ditto", "-c", "-k", "--keepParent", str(bundle), archive], check=True)
        else:
            archive = shutil.make_archive(archive[:-4], "zip", bundle.parent, bundle.name)
        print(f"Wrote {archive}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
