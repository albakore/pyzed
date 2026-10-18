"""Command line helpers: ``pyzed new <name>`` and ``pyzed icons [filter]``."""

from __future__ import annotations

import argparse
import re
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


def icons(pattern: str = "") -> int:
    from .icons import names

    for name in names():
        if pattern in name:
            print(name)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="pyzed", description="Pyzed: fast GUIs for Python powered by Iced")
    sub = parser.add_subparsers(dest="command", required=True)
    p_new = sub.add_parser("new", help="create a new app from a template")
    p_new.add_argument("name")
    p_icons = sub.add_parser("icons", help="list the bundled Lucide icon names")
    p_icons.add_argument("filter", nargs="?", default="")
    args = parser.parse_args(argv)
    if args.command == "new":
        return new(args.name)
    return icons(args.filter)


if __name__ == "__main__":
    sys.exit(main())
