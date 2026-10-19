"""Rating: a component designed in Pyzed Design.

The layout is in rating.pzcomp; properties, events and logic are below. Use it like
any component: ``Rating(...)`` in a view, or from the designer's toolbox.
"""

from typing import Annotated

import pyzed as pz
from pyzed.designer import SceneComponent


class Rating(SceneComponent, scene="rating.pzcomp"):
    """Five stars the user can click."""

    value: Annotated[int, pz.Range(0, 5)] = 3  # How many stars are lit
    readonly: bool = False
    clicks: int = pz.state(0, doc="Times the user picked a rating")
    events = {"change": "A star was picked (event.value is the rating)"}

    def star1_click(self, event):
        return self.pick(1)

    def star2_click(self, event):
        return self.pick(2)

    def star3_click(self, event):
        return self.pick(3)

    def star4_click(self, event):
        return self.pick(4)

    def star5_click(self, event):
        return self.pick(5)

    def pick(self, stars):
        """Lights ``stars`` stars and tells the parent."""
        if self.readonly:
            return None
        self.value = stars
        self.clicks += 1
        return self.emit("change", stars)
