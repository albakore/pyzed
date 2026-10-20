"""Undo and redo for the designer, as a stack of form snapshots.

Forms are small (a few dozen controls), so storing whole snapshots is simpler and
more robust than recording inverse operations, and makes every edit undoable
without extra code.
"""

from __future__ import annotations

from typing import List, Optional

from .model import Form


class History:
    """Snapshots of a form: ``push`` after an edit, then ``undo``/``redo`` to move through them."""

    def __init__(self, form: Form, limit: int = 200) -> None:
        self.limit = limit
        self._past: List[str] = []
        self._future: List[str] = []
        self._current = form.to_json()
        self._group: Optional[str] = None
        self._kind = type(form)  # snapshots come back as the same kind (a Form or a component Scene)

    def push(self, form: Form, group: Optional[str] = None) -> bool:
        """Records the form's current state; returns ``False`` if nothing changed.

        Consecutive pushes with the same ``group`` (e.g. every keystroke in one text
        property) merge into a single undo step.
        """
        snapshot = form.to_json()
        if snapshot == self._current:
            return False
        if group is None or group != self._group or not self._past:
            self._past.append(self._current)
            del self._past[: -self.limit]
        self._group = group
        self._current = snapshot
        self._future.clear()
        return True

    @property
    def steps(self) -> int:
        """How many undo steps there are (a mark for ``merge``)."""
        return len(self._past)

    def merge(self, mark: int) -> None:
        """Makes every step recorded since ``mark`` (``steps`` before a batch of edits) a single undo step."""
        del self._past[mark + 1:]
        self._group = None

    def reset(self, form: Form) -> None:
        """Forgets all undo and redo steps and starts again from ``form``'s current state."""
        self._group = None
        self._past.clear()
        self._future.clear()
        self._current = form.to_json()

    @property
    def can_undo(self) -> bool:
        """Whether there is a step to undo."""
        return bool(self._past)

    @property
    def can_redo(self) -> bool:
        """Whether there is an undone step to redo."""
        return bool(self._future)

    def undo(self) -> Optional[Form]:
        """Steps back one snapshot; returns the previous form (a new object) or ``None`` if there is none."""
        if not self._past:
            return None
        self._group = None
        self._future.append(self._current)
        self._current = self._past.pop()
        return self._kind.from_json(self._current)

    def redo(self) -> Optional[Form]:
        """Steps forward one snapshot; returns the restored form (a new object) or ``None`` if there is
        none."""
        if not self._future:
            return None
        self._group = None
        self._past.append(self._current)
        self._current = self._future.pop()
        return self._kind.from_json(self._current)
