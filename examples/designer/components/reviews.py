"""Event handlers for the Reviews form.

Each function receives the running ``form`` (controls are attributes: ``form.button1.text``)
and an ``event`` with ``event.sender``, ``event.name`` and ``event.value``.
"""


def ada_rated(form, event):
    """Runs when the card of ada is rated."""
    event.sender.score = event.value
    form.status.text = f"{event.sender.person} now has {event.value} stars"


def grace_rated(form, event):
    """Runs when the card of grace is rated."""
    event.sender.score = event.value
    form.status.text = f"{event.sender.person} now has {event.value} stars"
