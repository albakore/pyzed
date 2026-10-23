"""Edit tab order: the order Tab moves the keyboard focus through a form's fields, as in Qt Designer.

**Edit → Edit tab order** turns the canvas into a numbering mode: every field that can take the
keyboard (text boxes, checks, selects, sliders, your own components...) shows its place in a badge,
and clicking the fields one after another numbers them 1, 2, 3... The fields not clicked keep their
order after the clicked ones. Esc or the command again goes back to editing. The order is saved in
the ``.pzform`` (``Form.tab_order``) and the running form follows it (``runtime``); a form without
one goes through its fields in the order they are drawn.
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any, List, Optional

from .. import _core, ui
from ..icons import icon as _icon
from ..theme import Theme
from . import components as _components
from . import roles as _roles
from .locale import tr
from .model import Form

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Roles of the controls that take the keyboard focus (a custom component may hold fields).
FOCUS_ROLES = frozenset({"input", "custom"})
BADGE = 20.0

_sessions = itertools.count(1)


def eligible(form: Form) -> List[str]:
    """The names of the visual controls of ``form`` that can take the keyboard focus, in drawing order."""
    out = []
    for control, _depth in form.walk():
        spec = _components.spec(control.type)
        if spec.visual and spec.container is None and _roles.of(spec) in FOCUS_ROLES:
            out.append(control.name)
    return out


def sequence(form: Form) -> List[str]:
    """The fields of ``form`` in the order Tab goes through them."""
    return form.tab_sequence(eligible(form))


class TabOrderEditor:
    """The tab order mode of the canvas: on or off, and the fields clicked since it was turned on."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.active = False
        self.clicked: List[str] = []
        self._group = ""

    def toggle(self) -> None:
        """Turns the mode on (the numbering starts again from 1) or off."""
        if self.active:
            return self.stop()
        d = self.d
        d.tool = None
        d.menu = None
        self.active = True
        self.clicked = []
        self._group = f"tab-order:{next(_sessions)}"  # one undo step for the whole session
        d.focus = "canvas"
        d.notify(tr("Click the fields in the order Tab should visit them"), tr("Press Esc when you are done"),
                 kind="info", seconds=4)
        return None

    def stop(self) -> None:
        self.active = False
        self.clicked = []

    def click(self, name: str) -> None:
        """Gives the field ``name`` the next number: the fields clicked so far, then it, then the rest."""
        doc = self.d.doc
        if name not in eligible(doc.form):
            return
        self.clicked = [n for n in self.clicked if n != name] + [name]
        rest = [n for n in sequence(doc.form) if n not in self.clicked]
        doc.set_tab_order(self.clicked + rest, group=self._group)

    def reset(self) -> None:
        """Forgets the saved order: Tab follows the drawing order again."""
        self.clicked = []
        self.d.doc.set_tab_order([], group=self._group)

    def number(self, name: str) -> Optional[int]:
        """The place of field ``name`` in the tab order (from 1), or ``None`` if Tab does not visit it."""
        order = sequence(self.d.doc.form)
        return order.index(name) + 1 if name in order else None


def badge(number: int, picked: bool, t: Theme) -> Any:
    """The round number shown over a field in tab order mode (filled once clicked in this session)."""
    return _core.container(
        _core.text(str(number), size=11, color=t.background if picked else t.accent, weight="bold"),
        width=BADGE, height=BADGE, center=True, radius=BADGE / 2,
        bg=t.accent if picked else t.background, border_color=t.accent, border_width=1.5,
    )


def banner(d: "Designer", t: Theme) -> Any:
    """The chip at the top of the form while numbering: what to do, Reset and Done."""
    editor = d.tab_editor
    return _core.container(
        _core.row([_icon("list-ordered", size=13, color=t.accent),
                   ui.label(tr("Tab order: click the fields in order"), size="xs", weight="medium", theme=t,
                            wrap=False),
                   ui.button(tr("Reset"), editor.reset, variant="ghost", size="xs", theme=t,
                             disabled=not d.doc.form.tab_order),
                   ui.button(tr("Done"), editor.stop, size="xs", theme=t)],
                  spacing=6, align="center"),
        padding=(2, 2, 2, 8), radius=t.radius, bg=t.elevated, border_color=t.accent, border_width=1,
    )
