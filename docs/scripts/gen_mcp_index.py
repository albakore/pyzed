"""Regenerates python/pyzed/mcp/docs_index.json: the docs pages, examples and API descriptions of the MCP server.

    python docs/scripts/gen_mcp_index.py            # writes the index
    python docs/scripts/gen_mcp_index.py --check    # fails if it is out of date

The MCP server ships only this index; the pages themselves are read from a source checkout or from
GitHub at the installed version's tag. Run it after adding, renaming or retitling a page or an example.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "src" / "content" / "docs"
EXAMPLES = ROOT / "examples"
OUT = ROOT / "python" / "pyzed" / "mcp" / "docs_index.json"
#: Example scripts that are tooling, not examples.
SKIP_EXAMPLES = {"screenshots"}


def _frontmatter(text: str) -> dict:
    match = re.match(r"^---\n(.*?)\n---", text, re.S)
    out = {}
    for line in (match.group(1).splitlines() if match else []):
        key, sep, value = line.partition(":")
        if sep and not line.startswith(" "):
            out[key.strip()] = value.strip().strip("'\"")
    return out


def docs() -> list:
    pages = []
    for path in sorted(DOCS.rglob("*.md*")):
        rel = path.relative_to(DOCS)
        if rel.parts[0] == "es" or path.suffix not in (".md", ".mdx"):
            continue
        if rel.as_posix() == "changelog.md":  # written from CHANGELOG.md by the site build, not in git
            continue
        meta = _frontmatter(path.read_text(encoding="utf-8"))
        slug = rel.with_suffix("").as_posix()
        pages.append({"slug": slug, "title": meta.get("title", slug), "description": meta.get("description", ""),
                      "path": path.relative_to(ROOT).as_posix()})
    return pages


def _summary(path: Path) -> str:
    if path.suffix == ".py":
        doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or ""
        return doc.split("\n\n", 1)[0].replace("\n", " ").strip()
    return "A form made with the visual designer (.pzform layout)."


def examples() -> list:
    found = [p for p in sorted(EXAMPLES.glob("*.py")) if p.stem not in SKIP_EXAMPLES]
    found += sorted(EXAMPLES.glob("tutorial/*.py")) + sorted(EXAMPLES.glob("designer/*.py"))
    found += sorted(EXAMPLES.glob("designer/*.pzform"))
    out = []
    for path in found:
        rel = path.relative_to(EXAMPLES)
        name = rel.with_suffix("").as_posix() if path.suffix == ".py" else rel.as_posix()
        out.append({"name": name, "summary": _summary(path), "path": path.relative_to(ROOT).as_posix()})
    return out


def api() -> dict:
    """The hand-written API descriptions (api_docs_en.py), so widgets implemented in Rust are documented too."""
    namespace: dict = {}
    path = ROOT / "docs" / "scripts" / "api_docs_en.py"
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    entries = {}
    for page in namespace["PAGES"]:
        for _title, items in page["sections"]:
            for name, entry in items.items():
                entries[name] = {k: v for k, v in entry.items() if k in ("desc", "params", "example", "extra")}
    return {"common": namespace["COMMON"], "entries": entries}


def build() -> str:
    data = {"docs": docs(), "examples": examples(), "api": api()}
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the index is out of date")
    args = parser.parse_args()
    text = build()
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT.relative_to(ROOT)} is out of date: run python docs/scripts/gen_mcp_index.py", file=sys.stderr)
            return 1
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
