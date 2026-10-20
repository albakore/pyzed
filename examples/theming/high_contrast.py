"""A high-contrast theme for readers who need strong colors and clear edges.

    python examples/theming/high_contrast.py

- ``Theme.from_dict`` starts from One Dark and replaces only the tokens you list.
- ``pz.theme.contrast`` checks the WCAG contrast ratio of two colors (7:1 or more is "AAA").
- A global ``style`` makes every text bigger.
"""

import pyzed as pz
from preview import preview

HIGH_CONTRAST = pz.Theme.from_dict({
    "name": "High Contrast",
    "appearance": "dark",
    # surfaces: pure black, panels a touch lighter so they stay visible
    "background": "#000000", "surface": "#0a0a0a", "elevated": "#141414", "editor": "#000000",
    "panel": "#0a0a0a", "title_bar": "#000000", "status_bar": "#000000",
    # strong white borders
    "border": "#ffffff", "border_variant": "#bdbdbd",
    # text: white, and muted text that is still very readable
    "text": "#ffffff", "text_muted": "#e0e0e0", "text_placeholder": "#c2c2c2", "text_disabled": "#9e9e9e",
    "icon": "#ffffff", "icon_muted": "#e0e0e0",
    # buttons and list rows
    "element": "#1f1f1f", "element_hover": "#333333", "element_active": "#4d4d4d",
    "ghost_hover": "#262626", "ghost_active": "#3d3d3d", "ghost_selected": "#3d3d3d",
    # status colors that stay readable on black
    "error": "#ff6b6b", "warning": "#ffd600", "success": "#5cff8a", "info": "#6bc8ff",
    # square corners
    "radius": 0, "radius_sm": 0,
}).with_accent("#ffd600")  # yellow focus rings, selection and primary buttons

pz.themes.register(HIGH_CONTRAST)


def report(theme):
    """Prints the contrast ratio of the main text colors against the background."""
    for token in ("text", "text_muted", "accent", "error"):
        ratio = pz.theme.contrast(theme.color(token), theme.background)
        print(f"{token:>10} on background: {ratio:4.1f}:1")


class HighContrastApp(pz.App):
    title = "High contrast"
    size = (720, 580)
    theme = "High Contrast"
    style = pz.Style(size=15)  # every text that does not set its own size

    def view(self):
        return pz.container(preview("High contrast", "Black, white and yellow, with square corners."),
                            padding=24, width="fill", height="fill")


if __name__ == "__main__":
    report(HIGH_CONTRAST)
    pz.run(HighContrastApp)
