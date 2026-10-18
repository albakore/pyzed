"""Command line helpers: ``pyzed new``, ``pyzed dev``, ``pyzed design``, ``pyzed run`` and ``pyzed icons``."""

from __future__ import annotations

import argparse
import os
import re
import runpy
import sys
from pathlib import Path


def new(name: str) -> int:
    target = Path(name)
    if target.exists() and any(target.iterdir()):
        print(f"error: {target} already exists and is not empty", file=sys.stderr)
        return 1
    target.mkdir(parents=True, exist_ok=True)
    title = re.sub(r"[-_]+", " ", target.name).strip().title() or "My App"
    template = (Path(__file__).parent / "templates" / "app.py.tmpl").read_text(encoding="utf-8")
    (target / "main.py").write_text(template.format(name=title), encoding="utf-8")
    (target / "requirements.txt").write_text("pyzed\n", encoding="utf-8")
    print(f"Created {target}/main.py\n\n  cd {target}\n  python main.py\n")
    return 0


def dev(script: str, args: list, watch: list) -> int:
    """Runs ``script`` like ``python script`` with hot reload on.

    Saving any ``.py`` file next to the script (or in a ``--watch`` folder) updates the
    running window without restarting it.
    """
    path = Path(script)
    if not path.is_file():
        print(f"error: {script} not found", file=sys.stderr)
        return 1
    os.environ["PYZED_RELOAD"] = "1"
    if watch:
        os.environ["PYZED_WATCH"] = os.pathsep.join(str(Path(w).resolve()) for w in watch)
    sys.argv = [str(path), *args]
    sys.path.insert(0, str(path.resolve().parent))
    runpy.run_path(str(path), run_name="__main__")
    return 0


def icons(pattern: str = "") -> int:
    from .icons import names

    for name in names():
        if pattern in name:
            print(name)
    return 0


def design(path=None) -> int:
    from .designer import design as open_designer

    open_designer(path)
    return 0


def run_form(path: str, reload: bool = False) -> int:
    from .designer import run

    if not Path(path).exists():
        print(f"error: {path} does not exist", file=sys.stderr)
        return 1
    run(path, reload=reload or None)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="pyzed", description="Pyzed: fast GUIs for Python powered by Iced")
    sub = parser.add_subparsers(dest="command", required=True)
    p_new = sub.add_parser("new", help="create a new app from a template")
    p_new.add_argument("name")
    p_dev = sub.add_parser("dev", help="run a script with hot reload (changes show up when you save)")
    p_dev.add_argument("script")
    p_dev.add_argument("--watch", action="append", default=[], metavar="PATH", help="also watch this folder or file")
    p_dev.add_argument("args", nargs=argparse.REMAINDER, help="arguments passed to the script")
    p_design = sub.add_parser("design", help="open the visual form designer")
    p_design.add_argument("form", nargs="?", help="a .pzform file (created on first save if missing)")
    p_run = sub.add_parser("run", help="run a form made with the designer")
    p_run.add_argument("form")
    p_run.add_argument("--reload", action="store_true", help="update the window when the form or its code is saved")
    p_icons = sub.add_parser("icons", help="list the bundled Lucide icon names")
    p_icons.add_argument("filter", nargs="?", default="")
    args = parser.parse_args(argv)
    if args.command == "new":
        return new(args.name)
    if args.command == "dev":
        return dev(args.script, args.args, args.watch)
    if args.command == "design":
        return design(args.form)
    if args.command == "run":
        return run_form(args.form, args.reload)
    return icons(args.filter)


if __name__ == "__main__":
    sys.exit(main())
