"""ProfileCard: a component designed in Pyzed Design.

The layout is in profile_card.pzcomp; properties, events and logic are below. Use it like
any component: ``ProfileCard(...)`` in a view, or from the designer's toolbox.
"""

import pyzed as pz
from pyzed.designer import SceneComponent


class ProfileCard(SceneComponent, scene="profile_card.pzcomp"):
    """A person with a rating."""

    person: str = "Ada Lovelace"
    job: str = "Mathematician"
    score: int = 4
    tint: pz.Color = "text_muted"  # Color of the role line
    events = {"rated": "The rating changed (event.value is the new score)"}

    def stars_change(self, event):
        """The inner Rating raised change."""
        self.score = event.value
        return self.emit("rated", event.value)

    def rate(self, stars):
        """Sets the rating from code, as a click on the stars would."""
        return self.stars.pick(stars)
