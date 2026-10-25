"""Renders the thumbnails of the example gallery of Pyzed Design into ``examples/thumbnails``.

    python scripts/example_thumbnails.py [id ...]

Each sample of ``pyzed.designer.samples.CATALOG`` is started off-screen and captured at
800x500 (the integrations need their packages installed: ``uv pip install sqlmodel httpx
sqlalchemy aiosqlite "fastapi[standard]" "pydantic[email]"``). Run it again after changing an example's look.
"""

from __future__ import annotations

import os
import runpy
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Sequence

import pyzed as pz
from pyzed.designer import samples
from pyzed.designer.runtime import open_form

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
SIZE = (800, 500)
SCALE = 1.0
#: Arguments some examples need to show something without hardware (the webcam's test pattern).
ARGS = {"webcam": ["test"], "iot_serial_monitor": ["--demo"], "iot_network_scanner": ["--demo"]}
#: Frames (at 60 per second) a game plays before the capture, so its first frame is not empty.
FRAMES = {"menus": 120, "asteroids": 120, "dodge": 120}


def app_of(script: Path, args: Sequence[str] = ()) -> pz.App:
    """Runs ``script`` as ``__main__`` with ``pz.run`` and ``App.run`` caught; returns the app it starts."""
    caught = []

    def catch(app, *args, **kwargs):
        caught.append(app() if isinstance(app, type) else app)

    def catch_method(self, *args, **kwargs):
        caught.append(self)

    saved = (pz.run, pz.App.run, sys.argv)
    pz.run, pz.App.run, sys.argv = catch, catch_method, [str(script), *args]
    sys.path.insert(0, str(script.parent))
    try:
        runpy.run_path(str(script), run_name="__main__")
    finally:
        pz.run, pz.App.run, sys.argv = saved
        sys.path.remove(str(script.parent))
        for name, module in list(sys.modules.items()):  # the next example may have modules of the same name
            if str(getattr(module, "__file__", "") or "").startswith(str(script.parent)):
                del sys.modules[name]
    if not caught:
        raise SystemExit(f"{script}: it does not start an app")
    return caught[0]


def render(sample: samples.Sample, out: Path) -> None:
    source = EXAMPLES / sample.path
    with tempfile.TemporaryDirectory() as tmp:
        cwd = Path.cwd()
        try:
            if sample.category == "Designer":
                app = open_form(source / sample.entry)
            elif sample.is_folder:
                folder = Path(tmp) / source.name
                shutil.copytree(source, folder)
                os.chdir(folder)  # databases and files are created in the copy
                app = app_of(folder / sample.script, ARGS.get(sample.id, ()))
            else:
                app = app_of(source, ARGS.get(sample.id, ()))
            for _ in range(FRAMES.get(sample.id, 0)):
                app.tick(1 / 60)
            app.screenshot(out, size=SIZE, scale=SCALE, wait=0.6)
        finally:
            os.chdir(cwd)


def main() -> int:
    wanted = set(sys.argv[1:])
    folder = EXAMPLES / samples.THUMBNAILS
    folder.mkdir(exist_ok=True)
    for sample in samples.CATALOG:
        if wanted and sample.id not in wanted:
            continue
        out = EXAMPLES / sample.thumbnail
        try:
            render(sample, out)
        except Exception as err:  # noqa: BLE001 - report and go on with the others
            print(f"{sample.id}: {type(err).__name__}: {err}")
            continue
        print(f"{sample.id}: {out.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
