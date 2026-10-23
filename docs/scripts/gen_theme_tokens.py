"""Writes docs/src/components/theme-tokens.json: the Pyzed Dark and Pyzed Light value of every color token.

    python docs/scripts/gen_theme_tokens.py            # rewrite it
    python docs/scripts/gen_theme_tokens.py --check    # fail if it is out of date

``TokenTable.astro`` reads it to draw the swatches of the Theme tokens page. It loads
``pyzed/theme.py`` on its own (pure Python), so it works without building Pyzed.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "src" / "components" / "theme-tokens.json"


def _theme_module():
    # A stand-in package, so theme.py's relative imports (theme_palettes) resolve
    # without importing pyzed itself and its compiled core.
    package = type(sys)("_pyzed_theme_pkg")
    package.__path__ = [str(ROOT / "python" / "pyzed")]
    sys.modules[package.__name__] = package
    spec = importlib.util.spec_from_file_location(
        "_pyzed_theme_pkg.theme", ROOT / "python" / "pyzed" / "theme.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _color(style) -> str:
    return style if isinstance(style, str) else (style[0] if style else "#00000000")


def tokens() -> dict:
    theme = _theme_module()
    dark, light = theme.themes.get("Pyzed Dark"), theme.themes.get("Pyzed Light")
    out = {k: [v, getattr(light, k)] for k, v in dark.tokens().items() if isinstance(v, str) and v.startswith("#")}
    out.update({f"syntax.{k}": [_color(v), _color(light.syntax.get(k))] for k, v in dark.syntax.items()})
    out.update({f"ansi.{k}": [v, light.ansi.get(k, v)] for k, v in dark.ansi.items()})
    out.update({f"players.{i}": [v, light.players[i]] for i, v in enumerate(dark.players)})
    return out


def main() -> int:
    text = json.dumps(tokens(), indent=1) + "\n"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT.relative_to(ROOT)} is out of date: run python docs/scripts/gen_theme_tokens.py")
            return 1
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
