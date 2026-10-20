"""Which groups of files a change touches, for the CI jobs that only run when their files change.

    python scripts/ci_changes.py BASE HEAD rust='src/**,Cargo.toml' code='!docs/**,!**.md'

Prints ``group=true`` or ``group=false`` for each group (CI appends it to ``$GITHUB_OUTPUT``). It
compares the two commits with ``git diff``, so it sees every changed file: GitHub's path filters and
the pull request files API stop at the first 300, which made big pull requests skip their tests.

A group matches a changed file when the file matches one of its patterns (any file, if it only has
``!`` patterns) and none of its ``!`` patterns. ``*`` also matches ``/``, so ``docs/**`` is the whole
folder. Every group is ``true`` when the diff can't be computed (a new branch, a missing commit).
"""

from __future__ import annotations

import subprocess
import sys
from fnmatch import fnmatchcase
from typing import Dict, List, Optional, Sequence


def changed_files(base: str, head: str) -> Optional[List[str]]:
    """The files that differ between ``base`` and ``head``, or ``None`` when git can't tell."""
    if not base or set(base) == {"0"}:
        return None
    subprocess.run(["git", "fetch", "-q", "--depth=1", "origin", base], check=False)
    result = subprocess.run(["git", "diff", "--name-only", base, head], capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        return None
    return [line for line in result.stdout.splitlines() if line]


def matches(path: str, patterns: Sequence[str]) -> bool:
    include = [p for p in patterns if not p.startswith("!")]
    exclude = [p[1:] for p in patterns if p.startswith("!")]
    return (not include or any(fnmatchcase(path, p) for p in include)) and \
        not any(fnmatchcase(path, p) for p in exclude)


def groups(files: Optional[Sequence[str]], specs: Dict[str, List[str]]) -> Dict[str, bool]:
    if files is None:
        return {name: True for name in specs}
    return {name: any(matches(f, patterns) for f in files) for name, patterns in specs.items()}


def main(argv: Sequence[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    base, head, *rest = argv
    specs = {}
    for spec in rest:
        name, _, patterns = spec.partition("=")
        specs[name] = [p.strip() for p in patterns.split(",") if p.strip()]
    files = changed_files(base, head)
    print(f"{'all' if files is None else len(files)} changed files", file=sys.stderr)
    for name, value in groups(files, specs).items():
        print(f"{name}={str(value).lower()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
