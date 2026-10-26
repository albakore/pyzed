"""Drag and drop (``pyzed.dnd``): the helpers, and real drags played with the off-screen recorder."""

import pytest

import pyzed as pz
from pyzed import _core, dnd, ui


def card(text):
    return pz.container(ui.label(text), padding=8, width="fill").style(background="#3b4252", radius=4)


def run(app, plan, size=(420, 260)):
    """Probes the first frame, then plays ``plan(probe)``."""

    def script():
        probe = yield ("probe",)
        for command in plan(probe):
            yield command

    _core.record(app, script(), size=size, scale=1.0)


def center(probe, name, kind="text"):
    x, y, w, h = next(p[2:] for p in probe if p[0] == kind and p[1] == name)
    return x + w / 2, y + h / 2


def drag(a, b, steps=12, release=True):
    """Press at ``a``, move to ``b`` and let go. The recorder only redraws on input, so every tick moves."""
    out = [("move", *a), ("down", "left")]
    for i in range(1, steps + 1):
        point = (a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps)
        out += [("move", *point), ("advance", 0.03)]
    for _ in range(6):
        out += [("advance", 0.05), ("move", *b)]
    if release:
        out.append(("up", "left"))
        for _ in range(8):
            out += [("advance", 0.05), ("move", *b)]
    return out


# -- helpers -----------------------------------------------------------------------------------

def test_reorder_moves_in_place():
    items = ["a", "b", "c", "d"]
    assert dnd.reorder(items, 0, 2) is items
    assert items == ["b", "c", "a", "d"]
    dnd.reorder(items, 3, 0)
    assert items == ["d", "b", "c", "a"]


def test_move_between_lists_clones_and_ignores_combines():
    lists = {"todo": ["a", "b"], "done": ["c"]}
    moved = dnd.move(lists, dnd.DragEvent(source="a", data="a", from_list="todo", from_index=0, target="done",
                                          index=1))
    assert moved == "a" and lists == {"todo": ["b"], "done": ["c", "a"]}

    template = {"kind": "text"}
    copy = dnd.move(lists, dnd.DragEvent(data=template, target="done", index=0), make=lambda t: dict(t, id=1))
    assert copy == {"kind": "text", "id": 1} and lists["done"][0] is copy

    clone = dnd.move(lists, dnd.DragEvent(from_list="todo", from_index=0, copy=True, target="done", index=0))
    assert clone == "b" and lists["todo"] == ["b"]

    assert dnd.move(lists, dnd.DragEvent(from_list="todo", from_index=0, target="done", combine="c")) is None
    assert lists["todo"] == ["b"]


def test_move_with_one_list_reorders_it():
    items = [1, 2, 3]
    dnd.move(items, dnd.DragEvent(from_list="nums", from_index=0, target="nums", index=2))
    assert items == [2, 3, 1]


def test_drag_event_shortcuts():
    e = dnd.DragEvent(source="card-1", data={"id": 1}, from_list="todo", target="todo", x=3, y=4, item_x=1,
                      item_y=2)
    assert e.item == {"id": 1}
    assert e.within
    assert e.position == (3, 4) and e.item_position == (1, 2)
    assert "card-1" in repr(e)


def test_handlers_take_the_event_or_nothing():
    calls = []
    dnd._adapt(lambda: calls.append("none"))(dnd.DragEvent())
    dnd._adapt(lambda e: calls.append(e.type))(dnd.DragEvent("drop"))
    assert calls == ["none", "drop"]


def test_options_are_checked():
    with pytest.raises(ValueError):
        pz.sortable([], direction="diagonal")
    with pytest.raises(ValueError):
        pz.draggable(pz.space(), "x", preview="cloud")
    assert dnd.current() is None


# -- real drags -----------------------------------------------------------------------------------

class Board(pz.App):
    theme = "One Dark"

    def __init__(self, **options):
        self.lists = {"todo": ["Write", "Test", "Ship"], "done": ["Plan"]}
        self.events = []
        self.options = options

    def drop(self, event):
        self.events.append(event)
        pz.dnd.move(self.lists, event)

    def column(self, name, **extra):
        return pz.sortable(items=self.lists[name], item=card, key=str, id=name, group="board", width=140,
                           on_reorder=self.drop, **{**self.options, **extra})

    def view(self):
        return pz.row([self.column("todo"), self.column("done")], spacing=20, padding=10)


def test_reorder_within_a_list():
    app = Board()
    run(app, lambda p: drag(center(p, "Write"), (center(p, "Ship")[0], center(p, "Ship")[1] + 6)))
    assert app.lists["todo"] == ["Test", "Ship", "Write"]
    event = app.events[-1]
    assert (event.from_list, event.from_index, event.target, event.index) == ("todo", 0, "todo", 2)


def test_move_to_another_list():
    app = Board()
    run(app, lambda p: drag(center(p, "Test"), (center(p, "Plan")[0], center(p, "Plan")[1] + 8)))
    assert app.lists == {"todo": ["Write", "Ship"], "done": ["Plan", "Test"]}


def test_a_short_press_is_a_click_not_a_drag():
    app = Board()
    run(app, lambda p: drag(center(p, "Write"), (center(p, "Write")[0] + 2, center(p, "Write")[1] + 1)))
    assert app.events == [] and app.lists["todo"] == ["Write", "Test", "Ship"]


def test_escape_cancels():
    app = Board()

    def plan(p):
        b = (center(p, "Plan")[0], center(p, "Plan")[1] + 8)
        out = drag(center(p, "Write"), b, release=False) + [("key", "Escape", "")]
        for _ in range(6):
            out += [("advance", 0.05), ("move", *b)]
        return out + [("up", "left"), ("move", *b)]

    run(app, plan)
    assert app.events == [] and app.lists["todo"] == ["Write", "Test", "Ship"]


def test_conditions_reject_drops():
    app = Board(can_drop=lambda e: e.data != "Test", max_items=3)
    plan = lambda p: drag(center(p, "Test"), (center(p, "Plan")[0], center(p, "Plan")[1] + 8))  # noqa: E731
    run(app, plan)
    assert app.lists["done"] == ["Plan"]


def test_clone_keeps_the_original():
    class Palette(Board):
        def view(self):
            return pz.row([self.column("todo", pull="clone", sort=False), self.column("done")], spacing=20,
                          padding=10)

    app = Palette()
    run(app, lambda p: drag(center(p, "Ship"), (center(p, "Plan")[0], center(p, "Plan")[1] + 8)))
    assert app.lists == {"todo": ["Write", "Test", "Ship"], "done": ["Plan", "Ship"]}
    assert app.events[-1].copy


def test_drag_only_by_the_handle():
    class Handles(Board):
        def view(self):
            item = lambda t: pz.row([pz.drag_handle(ui.label("::")), card(t)], spacing=4)  # noqa: E731
            return pz.sortable(items=self.lists["todo"], item=item, key=str, id="todo", handle=True, width=160,
                               on_reorder=self.drop)

    app = Handles()
    end = lambda p: (center(p, "Ship")[0], center(p, "Ship")[1] + 6)  # noqa: E731
    run(app, lambda p: drag(center(p, "Write"), end(p)))
    assert app.lists["todo"] == ["Write", "Test", "Ship"]
    handle = lambda p: next(center([q], "::") for q in p if q[0] == "text" and q[1] == "::")  # noqa: E731
    run(app, lambda p: drag(handle(p), end(p)))
    assert app.lists["todo"] == ["Test", "Ship", "Write"]


def test_combine_onto_an_item():
    class Files(Board):
        def view(self):
            return pz.sortable(items=["a.txt", "b.txt", "Docs", "c.txt"], item=card, key=str, id="files",
                               combine=True, width=150, on_reorder=self.events.append)

    app = Files()
    run(app, lambda p: drag(center(p, "a.txt"), (center(p, "Docs")[0], center(p, "Docs")[1] + 2), steps=24))
    assert app.events and app.events[-1].combine == "Docs"


def test_draggable_onto_a_droppable_with_a_grid():
    class Canvas(pz.App):
        theme = "One Dark"

        def __init__(self):
            self.drops = []

        def view(self):
            tool = pz.draggable(card("Box"), "box", data="rect", type="shape", source="keep")
            area = pz.droppable(pz.container(ui.label("Area"), width=240, height=180), "area", accepts="shape",
                                snap=10, on_drop=self.drops.append)
            nope = pz.droppable(pz.container(ui.label("Other"), width=80, height=40), "other", accepts="file",
                                on_drop=self.drops.append)
            return pz.row([pz.column([tool, nope], spacing=10, width=100), area], spacing=20, padding=10)

    app = Canvas()
    run(app, lambda p: drag(center(p, "Box"), center(p, "Other")))
    assert app.drops == []
    run(app, lambda p: drag(center(p, "Box"), (center(p, "Area")[0] + 13, center(p, "Area")[1] + 7)))
    (event,) = app.drops
    assert (event.source, event.data, event.target) == ("box", "rect", "area")
    assert event.item_x % 10 == 0 and event.item_y % 10 == 0


def test_keyboard_moves_the_focused_item():
    class Keys(Board):
        def view(self):
            return pz.sortable(items=self.lists["todo"], item=card, key=str, id="todo", keyboard=True, width=140,
                               on_reorder=self.drop)

    app = Keys()
    run(app, lambda p: [("move", *center(p, "Write")), ("down", "left"), ("up", "left"), ("key", "ArrowDown", "alt"),
                        ("move", 0, 0)])
    assert app.lists["todo"] == ["Test", "Write", "Ship"]
