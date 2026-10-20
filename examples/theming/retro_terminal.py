"""A retro terminal theme: green phosphor on black, monospaced and square.

    python examples/theming/retro_terminal.py

- ``Theme.generate`` with a green text color and a green accent.
- ``syntax`` and ``ansi`` recolor code and the terminal to match.
- The global style switches every text to the monospaced font.
"""

import pyzed as pz
from preview import preview

PHOSPHOR = "#33ff66"

RETRO = pz.Theme.generate(
    "Retro Terminal",
    background="#050a05",
    text=PHOSPHOR,
    accent=PHOSPHOR,
    error="#ff5555",
    warning="#ffcc33",
    success=PHOSPHOR,
    radius=0,
    syntax={"keyword": ("#a6ff00", "bold"), "string": "#7dffb0", "comment": ("#1f7a3a", "italic")},
).derive(ansi={"green": PHOSPHOR, "bright_black": "#1f7a3a"})

pz.themes.register(RETRO)


class RetroApp(pz.App):
    title = "Retro terminal"
    size = (720, 640)
    theme = "Retro Terminal"
    style = pz.Style(font="mono", size=13)  # every text in the window is monospaced

    def view(self):
        title = pz.text("> READY_").style(size=26, weight="bold", color="accent")
        return pz.container(pz.column([title, preview("SYSTEM", "All colors come from one green.")], spacing=12),
                            padding=24, width="fill", height="fill")


if __name__ == "__main__":
    pz.run(RetroApp)
