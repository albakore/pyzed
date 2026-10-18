"""Keep CHANGELOG.md up to date from the gitmoji commit history.

Uses git-cliff (``pip install git-cliff``) with the configuration in ``cliff.toml``.

    python scripts/changelog.py --preview          # what would go into the next release
    python scripts/changelog.py --update v0.3.0    # add the v0.3.0 section to CHANGELOG.md
    python scripts/changelog.py --notes v0.3.0     # v0.3.0 notes for the GitHub Release

``--update`` keeps hand-written notes: a version that already has a section is left
alone, and whatever is under ``## [Unreleased]`` is merged into the new section.
``--notes`` uses the CHANGELOG.md section when there is one, otherwise it generates it.

PR numbers and authors come from the GitHub API (set ``GITHUB_TOKEN`` to avoid rate
limits); without network access the entries link to the commit instead.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
UNRELEASED = re.compile(r"^## +\[?(?:Unreleased|Sin publicar)\]?[ \t]*$", re.MULTILINE | re.IGNORECASE)
# FastAPI's release-notes order; any other heading (e.g. "### Highlights") goes right
# after the breaking changes.
SECTION_ORDER = [
    "Breaking Changes",
    "Features",
    "Fixes",
    "Refactors",
    "Upgrades",
    "Docs",
    "Translations",
    "Internal",
]
HEADING = re.compile(r"^## ", re.MULTILINE)


def cliff(*args: str) -> str:
    command = ["git", "cliff", "--config", str(ROOT / "cliff.toml"), "--use-native-tls", *args]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        # No network (or rate limited): fall back to commit links without PR data.
        result = subprocess.run(command + ["--offline"], cwd=ROOT, check=True, capture_output=True, text=True)
    return result.stdout


def generated_section(tag: str) -> str:
    """The "## [X.Y.Z] - date" section with the commits from the previous tag to ``tag``."""
    tags = subprocess.run(
        ["git", "tag", "--list", "v[0-9]*", "--sort=-v:refname", "--merged", tag],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    previous = next((t for t in tags if t != tag), None)
    if previous is None:
        # First release: start at the root commit (git-cliff needs an "a..b" range).
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
    """Merge two section bodies, joining "### Subsections" with the same name."""
    blocks: dict[str, list[str]] = {}
    for body in (manual, generated):
        for chunk in re.split(r"(?m)^(?=### )", body.strip()):
            title, _, rest = chunk.partition("\n") if chunk.startswith("### ") else ("", "", chunk)
            if rest.strip() or title:
                blocks.setdefault(title.strip(), []).append(rest.strip())
    def rank(title: str) -> int:
        name = title.removeprefix("###").strip().lower()
        known = [s.lower() for s in SECTION_ORDER]
        return known.index(name) * 2 if name in known else 1

    order = sorted(blocks, key=rank)
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
    group.add_argument("--preview", action="store_true", help="show the unreleased changes")
    group.add_argument("--update", metavar="TAG", help="add that version's section to CHANGELOG.md")
    group.add_argument("--notes", metavar="TAG", help="print that version's release notes")
    args = parser.parse_args(argv)

    if args.preview:
        sys.stdout.write(cliff("--unreleased").strip() + "\n")
    elif args.update:
        changed = update(args.update)
        print(f"CHANGELOG.md: {'added' if changed else 'already had'} the {args.update} section")
    else:
        sys.stdout.write(notes(args.notes) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
