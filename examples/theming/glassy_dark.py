"""A glassy dark look: a gradient behind the window and a frosted panel on top.

    python examples/theming/glassy_dark.py

- The global style paints the window with a ``pz.Gradient``.
- ``glass`` turns a container into a translucent panel that blurs what is behind it.
- The theme itself is One Dark with a cyan accent (``with_accent``) and rounder corners.
"""

import pyzed as pz
from preview import preview

GLASSY = pz.themes.ONE_DARK.derive(name="Glassy Dark", radius=14, radius_sm=10).with_accent("#22d3ee")
pz.themes.register(GLASSY)

NIGHT = pz.Gradient(["#0f172a", "#312e81", "#701a75"], angle=135)


class GlassyApp(pz.App):
    title = "Glassy dark"
    size = (760, 650)
    theme = "Glassy Dark"
    style = pz.Style(background=NIGHT)  # paints the whole window

    def view(self):
        panel = pz.container(preview("Glassy", "A frosted panel over a gradient."), width="fill").style(
            glass={"tint": "#ffffff", "strength": 0.08, "blur": 24}, radius=20, padding=24,
            border=(1, "#ffffff22"))
        return pz.container(panel, padding=28, width="fill", height="fill")


if __name__ == "__main__":
    pz.run(GlassyApp)
