"""A brand theme in light and dark that follows the operating system.

    python examples/theming/brand.py

- ``Theme.generate`` builds a whole theme from a background, a text and an accent color.
- ``derive`` changes a few tokens on top (rounder corners, the brand's own green for success).
- ``themes.register`` gives the themes a name, and ``themes.auto`` picks light or dark like the OS.
"""

import pyzed as pz
from preview import preview

BRAND = "#6d28d9"  # the brand's purple

ACME_LIGHT = pz.Theme.generate(
    "Acme Light", background="#ffffff", text="#1f1b2e", accent=BRAND, radius=10,
).derive(success="#15803d")

ACME_DARK = pz.Theme.generate(
    "Acme Dark", background="#16131f", text="#ece9f5", accent="#a78bfa", radius=10,
).derive(success="#4ade80")

pz.themes.register(ACME_LIGHT)
pz.themes.register(ACME_DARK)


class BrandApp(pz.App):
    title = "Acme"
    size = (720, 580)
    theme = pz.themes.auto("Acme Light", "Acme Dark")  # light or dark, like the system

    def view(self):
        return pz.container(preview("Acme", "A brand theme that follows the system's light or dark mode."),
                            padding=24, width="fill", height="fill")


if __name__ == "__main__":
    pz.run(BrandApp)
