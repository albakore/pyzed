"""Mantiene CHANGELOG.md (formato Keep a Changelog) a partir de commits convencionales.

Usa git-cliff (``pip install git-cliff``) con la configuración de ``cliff.toml``.

    python scripts/changelog.py --preview          # qué entraría en la próxima versión
    python scripts/changelog.py --update v0.2.0    # añade la sección de v0.2.0 a CHANGELOG.md
    python scripts/changelog.py --notes v0.2.0     # notas de v0.2.0 para la GitHub Release

``--update`` respeta lo escrito a mano: si la versión ya tiene sección no la toca, y lo
que haya bajo ``## [Sin publicar]`` pasa a encabezar la sección nueva. ``--notes`` usa la
sección de CHANGELOG.md si existe y, si no, la genera desde los commits.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
UNRELEASED = re.compile(r"^## +\[?(?:Sin publicar|Unreleased)\]?[ \t]*$", re.MULTILINE | re.IGNORECASE)
HEADING = re.compile(r"^## ", re.MULTILINE)


def cliff(*args: str) -> str:
    result = subprocess.run(
        ["git", "cliff", "--config", str(ROOT / "cliff.toml"), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def generated_section(tag: str) -> str:
    """Sección "## [X.Y.Z] - fecha" con los commits desde el tag anterior hasta ``tag``."""
    tags = subprocess.run(
        ["git", "tag", "--list", "v[0-9]*", "--sort=-v:refname", "--merged", tag],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    previous = next((t for t in tags if t != tag), None)
    if previous is None:
        # Primera versión: desde el commit raíz (git-cliff necesita un rango "a..b").
        previous = subprocess.run(
            ["git", "rev-list", "--max-parents=0", tag], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.split()[0]
    return cliff(f"{previous}..{tag}").strip()


def find_section(text: str, version: str) -> tuple[int, int] | None:
    match = re.search(rf"^## +\[?v?{re.escape(version)}\]?(?:[ \t].*)?$", text, re.MULTILINE)
    if not match:
        return None
    following = HEADING.search(text, match.end())
    return match.start(), following.start() if following else len(text)


def update(tag: str) -> bool:
    version = tag.removeprefix("v")
    text = CHANGELOG.read_text(encoding="utf-8")
    if find_section(text, version):
        return False

    heading, _, body = generated_section(tag).partition("\n")
    unreleased = UNRELEASED.search(text)
    if unreleased:
        following = HEADING.search(text, unreleased.end())
        end = following.start() if following else len(text)
        manual = text[unreleased.end() : end].strip()
        section = heading + "\n\n" + merge(manual, body)
        text = text[: unreleased.end()] + "\n\n" + section + "\n\n" + text[end:].lstrip("\n")
    else:
        first = HEADING.search(text)
        at = first.start() if first else len(text)
        text = text[:at] + heading + "\n\n" + body.strip() + "\n\n" + text[at:]
    CHANGELOG.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    return True


def merge(manual: str, generated: str) -> str:
    """Une dos cuerpos de sección juntando los "### Subsección" con el mismo nombre."""
    blocks: dict[str, list[str]] = {}
    for body in (manual, generated):
        for chunk in re.split(r"(?m)^(?=### )", body.strip()):
            title, _, rest = chunk.partition("\n") if chunk.startswith("### ") else ("", "", chunk)
            if rest.strip() or title:
                blocks.setdefault(title.strip(), []).append(rest.strip())
    order = sorted(blocks, key=lambda title: title != "### Breaking changes")  # estable: el resto en su orden
    return "\n\n".join(
        "\n\n".join(p for p in [title, "\n".join(r for r in blocks[title] if r)] if p) for title in order
    ).strip()


def notes(tag: str) -> str:
    text = CHANGELOG.read_text(encoding="utf-8")
    span = find_section(text, tag.removeprefix("v"))
    section = text[span[0] : span[1]] if span else generated_section(tag)
    return section.partition("\n")[2].strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preview", action="store_true", help="muestra los cambios aún sin publicar")
    group.add_argument("--update", metavar="TAG", help="añade la sección de esa versión a CHANGELOG.md")
    group.add_argument("--notes", metavar="TAG", help="imprime las notas de esa versión")
    args = parser.parse_args(argv)

    if args.preview:
        sys.stdout.write(cliff("--unreleased").strip() + "\n")
    elif args.update:
        changed = update(args.update)
        print(f"CHANGELOG.md: {'añadida' if changed else 'ya tenía'} la sección de {args.update}")
    else:
        sys.stdout.write(notes(args.notes) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
