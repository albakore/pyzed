"""Renders the Theme cookbook captures (docs/src/assets/theming/*.png) from examples/theming.

    python docs/scripts/theming_shots.py            # all of them
    python docs/scripts/theming_shots.py pastel     # only some

They are drawn off-screen with ``App.screenshot`` (no window or GPU needed), at 1.5x and
saved as PNG; Astro serves them as AVIF/WebP in the page.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "src" / "assets" / "theming"
sys.path.insert(0, str(ROOT / "examples" / "theming"))

import pyzed as pz  # noqa: E402

# capture name -> (module, app class, theme to force or None)
SHOTS = {
    "brand-dark": ("brand", "BrandApp", "Acme Dark"),
    "brand-light": ("brand", "BrandApp", "Acme Light"),
    "high-contrast-dark": ("high_contrast", "HighContrastApp", None),
    "retro-terminal-dark": ("retro_terminal", "RetroApp", None),
    "glassy-dark-dark": ("glassy_dark", "GlassyApp", None),
    "pastel-light": ("pastel", "PastelApp", None),
    "mixed-dark": ("mixed", "MixedApp", None),
}


class BundledThemes(pz.App):
    """Every bundled theme, each drawing the same small card."""

    size = (1180, 800)

    def tile(self, name):
        from pyzed import ui

        t = pz.themes.get(name)
        with t:
            body = pz.column([
                pz.row([ui.label(name, weight="semibold"), pz.hspace(), ui.badge("dark" if t.is_dark else "light")],
                       align="center"),
                pz.row([ui.button("Primary", lambda: None, variant="solid", size="sm"),
                        ui.button("Filled", lambda: None, size="sm"),
                        ui.button("Ghost", lambda: None, variant="ghost", size="sm")], spacing=6),
                ui.input("Text field", lambda _v: None, size="sm"),
                pz.row([ui.badge("ok", tint="success"), ui.badge("warn", tint="warning"),
                        ui.badge("error", tint="error"), pz.hspace(), ui.switch(True, lambda _v: None)],
                       spacing=4, align="center"),
            ], spacing=10)
            return pz.container(body, padding=14, width="fill").style(
                background="editor", border=(1, "border"), radius=10)

    def view(self):
        names = pz.themes.names()
        names += [None] * (-len(names) % 4)  # an even grid: blank cells finish the last row
        rows = [pz.row([self.tile(n) if n else pz.container(width="fill") for n in names[i:i + 4]], spacing=14)
                for i in range(0, len(names), 4)]
        return pz.container(pz.column(rows, spacing=14), padding=20, width="fill", height="fill").style(
            background="#16181d")


class ButtonVariants(pz.App):
    """The button variants and tints in One Dark."""

    size = (760, 170)

    def view(self):
        from pyzed import ui

        def row(items):
            return pz.row(items, spacing=8, align="center")

        noop = lambda: None  # noqa: E731
        return pz.container(pz.column([
            row([ui.button(v.capitalize(), noop, variant=v) for v in ("filled", "solid", "tinted", "outline", "ghost",
                                                                      "subtle")]),
            row([ui.button(t.capitalize(), noop, variant="solid", tint=t) for t in ("accent", "success", "warning",
                                                                                 "error", "info")]),
            row([ui.button(s.upper(), noop, size=s) for s in ("xs", "sm", "md", "lg")]
                + [ui.badge("soft"), ui.badge("solid", variant="solid"), ui.badge("outline", variant="outline")]),
        ], spacing=14), padding=20, width="fill", height="fill")


EXTRA = {"bundled-themes-dark": BundledThemes, "button-variants-dark": ButtonVariants}


def main(names: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, cls in EXTRA.items():
        if names and not any(n in name for n in names):
            continue
        app = cls()
        path = OUT / f"{name}.png"
        app.screenshot(str(path), size=app.size, scale=1.5)
        print(f"Wrote {path.relative_to(ROOT)}")
    for name, (module, cls, theme) in SHOTS.items():
        if names and not any(n in name for n in names):
            continue
        app = getattr(importlib.import_module(module), cls)()
        if theme:
            app.theme = theme
        path = OUT / f"{name}.png"
        app.screenshot(str(path), size=app.size, scale=1.5)
        print(f"Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
