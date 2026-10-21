"""A stand-in for ``pyzed._core`` that records the widget tree the ``ui`` components build.

Real widgets are opaque Rust objects; with the ``ui_tree`` fixture every ``_core.<widget>(...)`` call made
by ``pyzed.ui`` returns a :class:`Node` instead, so tests can look at the structure, the colors and sizes
the components pick, and call the callbacks they wire up.
"""

from __future__ import annotations

import sys
from typing import Any, Callable, Iterator, List, Optional


class Node:
    """One ``_core`` call: the widget ``kind`` with its positional ``args`` and keyword ``props``."""

    def __init__(self, kind: str, args: tuple, props: dict) -> None:
        self.kind = kind
        self.args = args
        self.props = props

    def __repr__(self) -> str:
        return f"<Node {self.kind}>"

    def on(self, cursor: Any = None, **handlers: Any) -> "Node":
        """``widget.on(...)``: an ``events`` node around this one, holding the handlers."""
        return Node("events", (self,), {"cursor": cursor, **handlers})

    def children(self) -> Iterator["Node"]:
        for value in (*self.args, *self.props.values()):
            yield from _nodes(value)

    def walk(self) -> Iterator["Node"]:
        """This node and every node under it, depth first."""
        yield self
        for child in self.children():
            yield from child.walk()

    def find_all(self, kind: Optional[str] = None, where: Optional[Callable[["Node"], bool]] = None) -> List["Node"]:
        return [n for n in self.walk() if (kind is None or n.kind == kind) and (where is None or where(n))]

    def find(self, kind: Optional[str] = None, where: Optional[Callable[["Node"], bool]] = None) -> "Node":
        found = self.find_all(kind, where)
        assert found, f"no {kind or 'node'} found under {self!r}"
        return found[0]

    def texts(self) -> List[str]:
        """The strings shown by the ``text`` nodes under this one, in order."""
        return [n.args[0] for n in self.find_all("text") if n.args and isinstance(n.args[0], str)]

    def button_with(self, text: str) -> "Node":
        """The button whose content shows ``text``."""
        return self.find("button", lambda n: text in Node("_", n.args[:1], {}).texts())


def _nodes(value: Any) -> Iterator[Node]:
    if isinstance(value, Node):
        yield value
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _nodes(item)


class FakeCore:
    """Answers any ``_core.<name>(...)`` with a :class:`Node`; ``Widget`` is :class:`Node`."""

    Widget = Node

    def __getattr__(self, name: str) -> Callable[..., Node]:
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *args, **props: Node(name, args, props)


def install(monkeypatch) -> FakeCore:
    """Swaps ``_core`` for a :class:`FakeCore` in ``pyzed.icons`` and every ``pyzed.ui`` module."""
    import pyzed.ui  # noqa: F401 - loads the submodules

    fake = FakeCore()
    for name, module in list(sys.modules.items()):
        if (name == "pyzed.icons" or name.startswith("pyzed.ui.")) and hasattr(module, "_core"):
            monkeypatch.setattr(module, "_core", fake)
    # Widgets shared between calls were built with the real core: start an empty cache.
    monkeypatch.setattr(sys.modules["pyzed.ui.base"], "_SHARED", {})
    return fake
