"""TeamCard: a component designed in Pyzed Designer.

The layout is in team_card.pzcomp; properties, events and logic are below. Use it like
any component: ``TeamCard(...)`` in a view, or from the designer's toolbox.
"""

from pyzed.designer import import_component


ProfileCard = import_component("profile_card.pzcomp")


class TeamCard(ProfileCard, scene="team_card.pzcomp"):
    """A profile card that also shows the team."""

    team: str = "Analytical Engine"

    def stars_change(self, event):
        """Does what a ProfileCard does, and the badge turns green with five stars."""
        result = super().stars_change(event)
        self.team_label.tint = "success" if event.value == 5 else "accent"
        return result
