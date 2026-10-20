"""Layout basics: rows, columns, fill, spacing, padding, alignment and grids.

    python examples/tutorial/layout_basics.py

A small profile page laid out with the four ideas behind every Pyzed layout:

- ``pz.column`` stacks children top to bottom, ``pz.row`` puts them side by side.
- ``spacing`` is the gap between children, ``padding`` the room inside the edge.
- ``width="fill"`` / ``height="fill"`` take the space that is left; ``pz.hspace()`` is an empty
  piece that fills, so it pushes what follows to the end of the row.
- ``pz.grid`` places children in cells of equal width.

Walkthrough: https://albakore.github.io/pyzed/tutorials/basic/layout-basics/
"""

import pyzed as pz
from pyzed import ui


class Profile(pz.App):
    title = "Layout basics"
    size = (720, 500)

    def __init__(self):
        self.follows = False

    def header(self):
        # A row: avatar, a column with two lines, a spacer that fills, then a button at the far right.
        return pz.row([
            ui.avatar("AL", size=48),
            pz.column([ui.heading("Ada Lovelace", level=2), ui.muted("Analyst · London")], spacing=2),
            pz.hspace(),
            ui.button("Following" if self.follows else "Follow", self.toggle_follow,
                      variant="outline" if self.follows else "solid", icon="user-plus"),
        ], spacing=12, align="center")

    def stats(self):
        # A grid: three cells of the same width, whatever the window size.
        return pz.grid([
            ui.stat("Projects", "12", width="fill"),
            ui.stat("Followers", "1,205" if self.follows else "1,204", width="fill"),
            ui.stat("Stars", "86", width="fill"),
        ], columns=3, spacing=12, height=84)  # height: the height of each row

    def about(self):
        # A container with height="fill" grows to take the rest of the window.
        t = self.resolved_theme()
        return pz.container(
            pz.column([
                ui.label("About", weight="semibold"),
                ui.label("Writes the first programs for the Analytical Engine. "
                         "Resize the window: this box grows, the button stays at the right."),
            ], spacing=6),
            padding=16, width="fill", height="fill",
            bg=t.surface, border_color=t.border, border_width=1, radius=t.radius + 2,
        )

    def toggle_follow(self):
        self.follows = not self.follows

    def view(self):
        t = self.resolved_theme()
        return pz.container(
            pz.column([self.header(), self.stats(), self.about()], spacing=16, height="fill"),
            padding=24, width="fill", height="fill", bg=t.background,
        )


if __name__ == "__main__":
    pz.run(Profile)
