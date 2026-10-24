"""Writes the AI section's design and architecture pages from the guides the MCP server ships.

    python docs/scripts/gen_ai_guides.py            # rewrite them
    python docs/scripts/gen_ai_guides.py --check    # fail if one is out of date

``python/pyzed/mcp/design.md`` and ``architecture.md`` (and their ``.es.md`` translations) are what agents get
from ``get_guide("design")`` and ``get_guide("app-architecture")``; the pages under ``ai/`` show the same text
on the site, so it is also in ``llms.txt``. Edit the guides, then run this script.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDES = ROOT / "python" / "pyzed" / "mcp"
DOCS = ROOT / "docs" / "src" / "content" / "docs"

#: page slug, guide file, sidebar order, then (title, description, note) in English and in Spanish.
PAGES = [
    ("ai/design", "design", 3.2, {
        "en": ("Design rules for agents",
               "UI and UX rules for professional Pyzed desktop apps: patterns, hierarchy, spacing, typography, the "
               "color tokens of Pyzed Dark and Light, states, feedback, forms, accessibility, motion and writing.",
               "AI agents get this page from the MCP server with `get_guide(\"design\")`, and `review_design` checks "
               "code against it. It is just as useful for people."),
        "es": ("Reglas de diseño para agentes",
               "Reglas de UI y UX para apps de escritorio profesionales con Pyzed: patrones, jerarquía, espaciado, "
               "tipografía, los tokens de color de Pyzed Dark y Light, estados, feedback, formularios, "
               "accesibilidad, movimiento y textos.",
               "Los agentes de IA reciben esta página del servidor MCP con `get_guide(\"design\")`, y "
               "`review_design` comprueba el código con ella. Sirve igual para personas."),
    }),
    ("ai/app-architecture", "architecture", 3.4, {
        "en": ("Architecture rules for agents",
               "How to structure large Pyzed apps: project layout, layers and ports, state and messages, components, "
               "effects and services, errors, settings, testing and anti-patterns.",
               "AI agents get this page from the MCP server with `get_guide(\"app-architecture\")`. It is just as "
               "useful for people."),
        "es": ("Reglas de arquitectura para agentes",
               "Cómo estructurar apps grandes con Pyzed: estructura del proyecto, capas y puertos, estado y mensajes, "
               "componentes, efectos y servicios, errores, ajustes, tests y antipatrones.",
               "Los agentes de IA reciben esta página del servidor MCP con `get_guide(\"app-architecture\")`. Sirve "
               "igual para personas."),
    }),
]


def _yaml(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render(guide: str, lang: str, order: float, title: str, description: str, note: str) -> str:
    source = GUIDES / (f"{guide}.md" if lang == "en" else f"{guide}.{lang}.md")
    body = source.read_text(encoding="utf-8")
    first, _, rest = body.partition("\n")
    if first.startswith("# "):  # the page title comes from the frontmatter
        body = rest.lstrip("\n")
    generated = ("Generated from python/pyzed/mcp/" + source.name + " by docs/scripts/gen_ai_guides.py: edit the guide, "
                 "not this page.")
    return (f"---\ntitle: {_yaml(title)}\ndescription: {_yaml(description)}\nsidebar:\n  order: {order:g}\n---\n\n"
            f"<!-- {generated} -->\n\n:::tip\n{note}\n:::\n\n{body}")


def pages() -> dict:
    out = {}
    for slug, guide, order, texts in PAGES:
        for lang, (title, description, note) in texts.items():
            path = DOCS / (slug if lang == "en" else f"{lang}/{slug}")
            out[path.with_suffix(".md")] = render(guide, lang, order, title, description, note)
    return out


def main(argv=None) -> int:
    check = "--check" in (sys.argv[1:] if argv is None else argv)
    stale = []
    for path, text in pages().items():
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == text:
            continue
        if check:
            stale.append(str(path.relative_to(ROOT)))
        else:
            path.write_bytes(text.encode("utf-8"))
            print(f"wrote {path.relative_to(ROOT)}")
    if stale:
        print("out of date (run python docs/scripts/gen_ai_guides.py):\n  " + "\n  ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
