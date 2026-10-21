"""Tests for performance: fast defaults, virtualized columns, lists and tables, and memoized subtrees."""

from dataclasses import dataclass

import pytest

import pyzed as pz
from pyzed import i18n, theme, ui


# -- fast defaults ----------------------------------------------------------------------


def test_import_leaves_heavy_modules_for_later():
    import subprocess
    import sys

    code = (
        "import sys, pyzed;"
        "heavy = ['asyncio', 'importlib.metadata', 'pyzed.designer', 'pyzed.reference', 'pyzed.game'];"
        "print([m for m in heavy if m in sys.modules])"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


def test_lazy_names_still_work():
    import pyzed.dock

    from pyzed import Dock, __version__

    assert Dock is pz.Dock is pyzed.dock.Dock
    assert pz.is_pressed is pz.game.is_pressed
    assert pz.designer.__name__ == "pyzed.designer"
    assert isinstance(__version__, str) and __version__
    assert {"designer", "Dock", "__version__"} <= set(dir(pz))
    with pytest.raises(AttributeError):
        pz.not_a_thing  # noqa: B018


def test_children_accept_any_iterable_and_skip_none_and_false():
    t = pz.text("a")
    nested = pz.column([t, None, False, (t, [t]), (x for x in [t]), "b", 3])
    assert repr(nested) == "<Widget column [6]>"


def test_button_colors_are_cached_per_theme_and_copied():
    from pyzed.ui import base

    first = base._button_colors(theme.ONE_DARK, "accent", None, False)
    first["bg"] = "#000000"  # callers change their copy
    again = base._button_colors(theme.ONE_DARK, "accent", None, False)
    assert again["bg"] != "#000000"
    assert base._button_colors(theme.ONE_LIGHT, "accent", None, False) == base._mix_button_colors(
        theme.ONE_LIGHT, "accent", None, False
    )


def test_plain_buttons_share_their_inside_per_theme():
    from pyzed.ui import base

    base._SHARED.clear()
    ui.button("Open", "a", theme=theme.ONE_DARK)
    ui.button("Open", "b", theme=theme.ONE_DARK, variant="ghost")
    ui.button("Open", "c", theme=theme.ONE_LIGHT)
    ui.button(pz.text("Open"), "d", theme=theme.ONE_DARK)  # widget content: built every time
    ui.button("Save", "e", theme=theme.ONE_DARK, loading=True)  # spinner: built every time
    insides = [key for key in base._SHARED if key[1] == "button_inner"]
    assert len(insides) == 2


def test_button_style_overrides_the_cached_defaults():
    from pyzed.ui import base

    kwargs = base._button_kwargs(theme.ONE_DARK, "filled", None, False, "md", False)
    before = dict(kwargs)
    ui.button("Open", "a", theme=theme.ONE_DARK, radius=12, border_color=None, padding=2)
    ui.icon_button("search", "s", theme=theme.ONE_DARK, tooltip="Search", keys="ctrl-f")
    assert kwargs == before  # the shared defaults are copied, not changed


def test_shared_widgets_follow_the_theme_and_key_style(monkeypatch):
    from pyzed.ui import base

    assert ui.kbd("ctrl-s", theme=theme.ONE_DARK) is ui.kbd("ctrl-s", theme=theme.ONE_DARK)
    assert ui.kbd("ctrl-s", theme=theme.ONE_DARK) is not ui.kbd("ctrl-s", theme=theme.ONE_LIGHT)
    words = ui.kbd("ctrl-s", theme=theme.ONE_DARK)
    monkeypatch.setattr(base, "KEY_STYLE", "symbols")
    assert ui.kbd("ctrl-s", theme=theme.ONE_DARK) is not words


def test_async_drain_handles_every_kind_of_result():
    from pyzed import _async

    async def coro():
        return 2

    async def agen():
        yield 3

    def gen():
        yield 4

    out = []
    for value in (1, coro(), agen(), gen(), None):
        _async.drain(value, out.append)
    assert out == [1, 2, 3, 4]


# -- virtual columns ------------------------------------------------------------------


def test_virtual_column_is_a_widget():
    column = pz.virtual_column(1_000_000, lambda i: pz.text(str(i)), item_height=24)
    assert repr(column) == "<Widget virtual_column [1000000]>"


def test_virtual_column_validates_its_arguments():
    with pytest.raises(TypeError):
        pz.virtual_column(10, "not a function", item_height=24)
    with pytest.raises(ValueError):
        pz.virtual_column(10, lambda i: None, item_height=0)


def test_only_visible_rows_are_built(tmp_path):
    built = []

    class Big(pz.App):
        def view(self):
            def row(i):
                built.append(i)
                return pz.text(f"Row {i}")

            return pz.scrollable(pz.virtual_column(100_000, row, item_height=20), height="fill")

    pz.screenshot(Big, tmp_path / "big.png", size=(300, 200))
    assert built and max(built) < 100


def test_rows_follow_the_scroll_position(tmp_path):
    built = []

    class Scrolled(pz.App):
        def on_start(self):
            return pz.Command.scroll_to("list", 0, 20 * 50_000)

        def view(self):
            def row(i):
                built.append(i)
                return pz.text(f"Row {i}")

            return pz.scrollable(pz.virtual_column(100_000, row, item_height=20), id="list", height="fill")

    pz.screenshot(Scrolled, tmp_path / "scrolled.png", size=(300, 200))
    assert any(50_000 <= i < 50_020 for i in built)


def test_a_failing_row_shows_the_error(tmp_path, capsys):
    class Broken(pz.App):
        def view(self):
            return pz.scrollable(pz.virtual_column(5, lambda i: 1 / 0, item_height=20))

    pz.screenshot(Broken, tmp_path / "broken.png", size=(200, 100))
    assert "ZeroDivisionError" in capsys.readouterr().err


def test_virtual_list_and_table_take_any_iterable(tmp_path):
    items = [f"file {i}.py" for i in range(50_000)]
    rendered = []

    class Lists(pz.App):
        def view(self):
            def render(name):
                rendered.append(name)
                return ui.list_item(name, icon="file")

            return pz.row([
                ui.virtual_list(items, render),
                ui.table(["n"], ({"n": i} for i in range(50_000)), height="fill", striped=True),
            ])

    assert isinstance(ui.virtual_list(items, ui.list_item), pz.Widget)
    pz.screenshot(Lists, tmp_path / "lists.png", size=(500, 300))
    assert 0 < len(rendered) < 200


# -- memo ---------------------------------------------------------------------------


def test_memo_reuses_the_subtree_while_arguments_are_equal():
    calls = []

    @pz.memo
    def sidebar(files, selected=None):
        calls.append(1)
        return pz.column([pz.text(f) for f in files])

    first = sidebar(["a", "b"], selected="a")
    assert sidebar(["a", "b"], selected="a") is first  # lists compare by value
    assert sidebar(["a", "c"], selected="a") is not first
    assert sidebar(["a", "b"], selected="b") is not first
    assert len(calls) == 3
    sidebar.cache_clear()
    sidebar(["a", "b"], selected="a")
    assert len(calls) == 4


def test_memo_compares_other_objects_by_identity():
    class Doc:
        def __init__(self):
            self.lines = []

    @pz.memo
    def lines(doc):
        return len(doc.lines)

    doc = Doc()
    assert lines(doc) == 0
    doc.lines.append("x")
    assert lines(doc) == 0  # mutated in place: still cached
    assert lines(Doc()) == 0 and lines(doc) == 0


def test_memo_hashes_frozen_dataclasses_by_value():
    @dataclass(frozen=True)
    class Item:
        name: str

    calls = []

    @pz.memo
    def label(item):
        calls.append(item)
        return item.name

    label(Item("a"))
    label(Item("a"))
    assert len(calls) == 1


def test_memo_rebuilds_when_the_theme_or_language_changes():
    calls = []

    @pz.memo
    def panel():
        calls.append(1)
        return pz.text("panel")

    before_theme, before_language = theme.current(), i18n.language()
    try:
        panel()
        panel()
        theme.use(pz.themes.ONE_LIGHT if before_theme is not pz.themes.ONE_LIGHT else pz.themes.ONE_DARK)
        panel()
        i18n.set_language("es" if before_language != "es" else "en")
        panel()
    finally:
        theme.use(before_theme)
        i18n.set_language(before_language)
    assert len(calls) == 3


def test_memo_keeps_the_last_maxsize_results():
    calls = []

    @pz.memo(maxsize=2)
    def row(i):
        calls.append(i)
        return i

    for i in (1, 2, 1, 3, 1, 2):
        row(i)
    assert calls == [1, 2, 3, 2]
    with pytest.raises(ValueError):
        pz.memo(maxsize=0)(lambda: None)


def test_clear_memos_and_stats():
    @pz.memo
    def value(x):
        return object()

    first = value(1)
    stats = pz.memo_stats()
    assert value(1) is first
    assert pz.memo_stats()["hits"] == stats["hits"] + 1
    pz.clear_memos()
    assert value(1) is not first
    assert pz.memo_stats()["misses"] == stats["misses"] + 1
