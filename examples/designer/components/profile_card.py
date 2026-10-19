"""ProfileCard: a component designed in Pyzed Designer.

The layout is in profile_card.pzcomp; properties, events and logic are below. Use it like
any component: ``ProfileCard(...)`` in a view, or from the designer's toolbox.
"""

from pyzed.designer import SceneComponent


class ProfileCard(SceneComponent, scene="profile_card.pzcomp"):
    """A person with a rating."""

    person: str = "Ada Lovelace"
    job: str = "Mathematician"
    score: int = 4
    events = {"rated": "The rating changed (event.value is the new score)"}

    def stars_change(self, event):
        """The inner Rating raised change."""
        self.score = event.value
        return self.emit("rated", event.value)
