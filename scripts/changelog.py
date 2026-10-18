"""Genera CHANGELOG.md y un resumen JSON de releases para la web de docs.

Usa git-cliff (``pip install git-cliff``) con la configuración de ``cliff.toml``.

    python scripts/changelog.py                    # reescribe CHANGELOG.md
    python scripts/changelog.py --json releases.json
    python scripts/changelog.py --notes v0.2.0     # notas de una sola release

La última versión estable (tag sin sufijo de pre-release) se marca en
CHANGELOG.md y en el campo ``latest_stable`` del JSON.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/albakore/pyzed"
STABLE_TAG = re.compile(r"^v?\d+\.\d+\.\d+$")
STABLE_MARK = " · Última versión estable"

GROUPS = {
    "Nuevas funciones": "features",
    "Mejoras": "improvements",
    "Correcciones": "fixes",
    "Documentación": "docs",
    "Tests": "tests",
    "Build y CI": "build",
    "Mantenimiento": "chore",
    "Otros cambios": "other",
}


def cliff(*args: str) -> str:
    result = subprocess.run(
        ["git", "cliff", "--config", str(ROOT / "cliff.toml"), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def is_stable(version: str | None) -> bool:
    return bool(version) and bool(STABLE_TAG.match(version))


def latest_stable(releases: list[dict]) -> str | None:
    # git-cliff ordena de la más nueva a la más vieja.
    return next((r["version"] for r in releases if is_stable(r["version"])), None)


def mark_stable(markdown: str, version: str | None) -> str:
    if not version:
        return markdown
    heading = f"## [{version.removeprefix('v')}]("
    lines = markdown.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(heading):
            lines[i] = line + STABLE_MARK
            break
    return "\n".join(lines) + "\n"


def summarize(releases: list[dict]) -> dict:
    stable = latest_stable(releases)
    out = []
    for release in releases:
        version = release["version"]
        sections: dict[str, list[dict]] = {}
        for commit in release["commits"]:
            key = "breaking" if commit["breaking"] else GROUPS.get(_group(commit), "other")
            message = commit["breaking_description"] if commit["breaking"] and commit["breaking_description"] else commit["message"]
            sections.setdefault(key, []).append(
                {
                    "message": message.splitlines()[0],
                    "scope": commit["scope"],
                    "commit": commit["id"],
                    "url": f"{REPO_URL}/commit/{commit['id']}",
                }
            )
        timestamp = release.get("timestamp") or 0
        out.append(
            {
                "version": version.removeprefix("v") if version else None,
                "tag": version,
                "date": datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat() if timestamp else None,
                "prerelease": bool(version) and not is_stable(version),
                "latest_stable": version is not None and version == stable,
                "url": f"{REPO_URL}/releases/tag/{version}" if version else None,
                "sections": sections,
            }
        )
    return {"latest_stable": stable.removeprefix("v") if stable else None, "releases": out}


def _group(commit: dict) -> str:
    # El grupo lleva un comentario HTML para ordenar: "<!-- 0 -->Nuevas funciones".
    return re.sub(r"<!--.*?-->", "", commit.get("group") or "").strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default=str(ROOT / "CHANGELOG.md"), help="ruta del CHANGELOG (por defecto CHANGELOG.md)")
    parser.add_argument("--json", metavar="PATH", help="escribe además un resumen JSON de todas las releases")
    parser.add_argument("--notes", metavar="TAG", help="imprime solo las notas de esa release y sale")
    parser.add_argument("--tag", metavar="TAG", help="trata los commits sin publicar como esta release (aún sin tag)")
    args = parser.parse_args(argv)

    extra = ["--tag", args.tag] if args.tag else []

    if args.notes:
        sys.stdout.write(_notes_for(args.notes).strip() + "\n")
        return 0

    releases = json.loads(cliff("--context", *extra))
    stable = latest_stable(releases)
    Path(args.output).write_text(mark_stable(cliff(*extra), stable), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(summarize(releases), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


def _notes_for(tag: str) -> str:
    heading = f"## [{tag.removeprefix('v')}]("
    for block in re.split(r"(?m)^(?=## \[)", cliff("--strip", "header")):
        if block.startswith(heading):
            return block.split("\n", 1)[1]
    raise SystemExit(f"no existe la release {tag}")


if __name__ == "__main__":
    raise SystemExit(main())
