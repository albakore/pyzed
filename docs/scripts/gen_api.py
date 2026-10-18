"""Genera la referencia de la API (docs/src/content/docs/reference/*.md) a partir del paquete instalado.

    maturin develop --release
    python docs/scripts/gen_api.py           # escribe las páginas
    python docs/scripts/gen_api.py --check   # falla si hay funciones públicas sin documentar

Las firmas salen de ``inspect`` (también las de Rust, que PyO3 expone), así que siempre coinciden con
el código. Las descripciones en español viven en ``api_docs.py``; si falta alguna se usa el docstring
y ``--check`` lo avisa.
"""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "src" / "content" / "docs" / "reference"
sys.path.insert(0, str(HERE))

import pyzed  # noqa: E402
from api_docs import COMMON, PAGES  # noqa: E402


def resolve(path: str):
    obj = pyzed
    for part in path.split(".")[1:]:
        obj = getattr(obj, part)
    return obj


def signature(name: str, obj) -> str:
    short = name.rsplit(".", 1)[-1]
    if inspect.isclass(obj) and dataclasses.is_dataclass(obj):
        fields = []
        for f in dataclasses.fields(obj):
            if f.default is not dataclasses.MISSING:
                fields.append(f"{f.name}={f.default!r}")
            elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
                fields.append(f"{f.name}={f.default_factory()!r}")
            else:
                fields.append(f.name)
        return f"@dataclass\nclass {short}({', '.join(fields)})"
    if inspect.isclass(obj):
        return f"class {short}"
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return f"{short}(...)"
    params = []
    for p in sig.parameters.values():
        text = str(p.replace(annotation=inspect.Parameter.empty))
        params.append(text)
    # Los marcadores "*" de keyword-only se reconstruyen a partir de la firma.
    rendered, seen_star = [], False
    for p, text in zip(sig.parameters.values(), params):
        if p.kind is inspect.Parameter.KEYWORD_ONLY and not seen_star:
            rendered.append("*")
            seen_star = True
        if p.kind is inspect.Parameter.VAR_POSITIONAL:
            seen_star = True
        rendered.append(text)
    one_line = f"{short}({', '.join(rendered)})"
    if len(one_line) <= 88:
        return one_line
    return f"{short}(\n" + "".join(f"    {r},\n" for r in rendered) + ")"


def param_names(obj):
    if inspect.isclass(obj) and dataclasses.is_dataclass(obj):
        return [f.name for f in dataclasses.fields(obj)]
    try:
        return [p for p in inspect.signature(obj).parameters if p not in ("self", "cls")]
    except (TypeError, ValueError):
        return []


def first_paragraph(doc: str | None) -> str:
    if not doc:
        return ""
    return inspect.cleandoc(doc).split("\n\n")[0].replace("\n", " ")


def render_item(name: str, entry: dict, missing: list) -> str:
    obj = resolve(name)
    short = name.rsplit(".", 1)[-1]
    out = [f"### `{short}`\n"]
    if not entry.get("no_signature"):
        out.append(f"```python\n{signature(name, obj)}\n```\n")
    description = entry.get("desc")
    if not description:
        description = first_paragraph(getattr(obj, "__doc__", None))
        missing.append(name)
    out.append(description.strip() + "\n")
    params = entry.get("params", {})
    rows = []
    for p in ([] if entry.get("no_signature") and not params else param_names(obj)):
        if p.startswith("*"):
            continue
        text = params.get(p) or COMMON.get(p)
        if text is None:
            missing.append(f"{name}({p})")
            continue
        rows.append(f"| `{p}` | {text} |")
    if rows:
        out.append("| Parámetro | Descripción |\n| --- | --- |\n" + "\n".join(rows) + "\n")
    if entry.get("example"):
        out.append(f"```python\n{inspect.cleandoc(entry['example'])}\n```\n")
    if entry.get("extra"):
        out.append(inspect.cleandoc(entry["extra"]) + "\n")
    return "\n".join(out)


def undocumented_exports(documented: set) -> list:
    missing = []
    for module, prefix in ((pyzed, "pyzed"), (pyzed.ui, "pyzed.ui")):
        for export in getattr(module, "__all__", []):
            obj = getattr(module, export)
            if inspect.ismodule(obj) or export in ("theme", "icons", "ui"):
                continue
            if f"{prefix}.{export}" not in documented:
                missing.append(f"{prefix}.{export}")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="only report undocumented names")
    args = parser.parse_args()

    missing: list = []
    documented = set()
    pages = {}
    for page in PAGES:
        body = [
            "---",
            f"title: {json.dumps(page['title'], ensure_ascii=False)}",
            f"description: {json.dumps(page['description'], ensure_ascii=False)}",
            "sidebar:",
            f"  order: {page['order']}",
            "---",
            "",
            "<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs.py. -->",
            "",
            inspect.cleandoc(page.get("intro", "")),
            "",
        ]
        for section, items in page["sections"]:
            body.append(f"## {section}\n")
            for name, entry in items.items():
                documented.add(name)
                body.append(render_item(name, entry, missing))
        pages[page["slug"]] = "\n".join(body).rstrip() + "\n"

    missing += undocumented_exports(documented)
    if args.check:
        for m in missing:
            print(f"sin documentar: {m}")
        return 1 if missing else 0

    OUT.mkdir(parents=True, exist_ok=True)
    for slug, text in pages.items():
        (OUT / f"{slug}.md").write_text(text, encoding="utf-8")
    print(f"wrote {len(pages)} pages to {OUT}")
    for m in missing:
        print(f"aviso: sin documentar: {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
