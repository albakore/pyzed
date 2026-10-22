"""Type hints that pick the property editor of a component's prop in the designer, like Godot's export hints.

    from typing import Annotated, Literal

    import pyzed as pz


    class Badge(pz.Component):
        text: str = "New"
        notes: pz.Multiline = ""                      # a text area
        tint: pz.Color = "accent"                     # a color picker (a theme token or #rrggbb)
        icon: pz.Icon = "star"                        # an icon name, with a preview
        logo: pz.FilePath = ""                        # a path, with a button to browse for the file
        output: pz.FolderPath = ""                    # a folder, with a button to browse for it
        size: Literal["sm", "md", "lg"] = "md"        # a drop-down
        level: Annotated[int, pz.Range(0, 10)] = 3    # a number between 0 and 10

At run time the values are plain ``str``/``int``/``float``: the hints only tell the
designer which editor to show.
"""

from __future__ import annotations

from dataclasses import dataclass


class Color(str):
    """A color property: a theme token (``"accent"``, ``"error"``...) or ``"#rrggbb"``."""


class Icon(str):
    """An icon property: a Lucide icon name (``"star"``)."""


class Multiline(str):
    """A text property edited in a text area (several lines)."""


class FilePath(str):
    """A file path property: a text field with a button that opens the system's file dialog."""


class FolderPath(str):
    """A folder path property: a text field with a button that opens the system's folder dialog."""


@dataclass(frozen=True)
class Range:
    """Limits of a number property: ``Annotated[int, pz.Range(0, 10)]`` (``step`` defaults to 1)."""

    min: float
    max: float
    step: float = 1
