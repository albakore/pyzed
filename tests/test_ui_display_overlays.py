"""States and events of tables, cards, stats, progress bars, settings groups, modals, toasts and empty states."""

from types import SimpleNamespace

import pytest

import pyzed as pz
from pyzed import ui
from ui_tree import install

T = pz.themes.ONE_DARK
ROWS = [{"name": "a"}, {"name": "b"}, {"name": "c"}]


@pytest.fixture
def tree(monkeypatch):
    return install(monkeypatch)


def test_table_multi_selection_double_press_context_and_empty(tree):
    got = []
    table = ui.table(["name"], ROWS, selected=[ROWS[0], ROWS[2]], on_row_double_press=lambda r: got.append(("open", r)),
                     on_row_context=lambda r: got.append(("menu", r)), theme=T)
    build = table.find("virtual_column").args[1]
    first, second = build(0), build(1)
    assert first.kind == "events" and first.find("container").props["bg"] == T.ghost_selected
    assert second.find("container").props["bg"] == "transparent"
    first.props["double_click"]()
    second.props["right_click"]()
    assert got == [("open", ROWS[0]), ("menu", ROWS[1])]
    empty = ui.table(["name"], [], empty="No files yet", theme=T)
    assert "No files yet" in empty.texts() and not empty.find_all("virtual_column")


def test_card_footer_press_selected_elevated(tree):
    card = ui.card(ui.label("x", theme=T), footer=[ui.button("OK", print, theme=T)], on_press=print, selected=True,
                   elevated=True, theme=T)
    assert card.kind == "events" and card.props["click"] is print
    box = card.args[0]
    assert box.props["border_color"] == T.accent and box.props["shadow"] is not None
    assert "OK" in card.texts()


def test_stat_icon_inverse_press(tree):
    stat = ui.stat("Errors", "12", delta=-8.0, inverse=True, icon="bug", on_press=print, theme=T)
    assert stat.kind == "events"
    assert any(n.props.get("color") == T.success for n in stat.find_all("text"))  # a drop is good here


def test_progress_label_value_and_indeterminate(tree):
    bar = ui.progress(0.42, label="Download", show_value=True, theme=T)
    assert bar.texts() == ["Download", "42%"]
    sweeping = ui.progress(None, theme=T)
    assert sweeping.kind == "container" and sweeping.find("row")


def test_settings_group_end(tree):
    group = ui.settings_group("Editor", [ui.label("row", theme=T)], end=ui.button("Reset", print, theme=T), theme=T)
    assert group.texts()[:2] == ["Editor", "Reset"]


def test_modal_sizes_description_scroll_and_escape(tree):
    closed = []
    modal = ui.modal(ui.label("body", theme=T), title="Rename", description="Pick a name", icon="pencil",
                     on_close=lambda: closed.append(1), width="lg", max_height=80, theme=T)
    assert modal.kind == "events"
    surface = modal.args[0]
    assert surface.props["width"] == 640 and surface.find("scrollable")
    assert "Pick a name" in modal.texts()
    modal.props["key_down"](SimpleNamespace(key="a"))
    modal.props["key_down"](SimpleNamespace(key="escape"))
    assert closed == [1]
    assert ui.modal(ui.label("x", theme=T), theme=T).kind == "container"  # nothing to close


def test_toast_progress_and_press(tree):
    toast = ui.toast("Saved", progress=0.5, on_press=print, theme=T)
    assert toast.kind == "events" and toast.find("progress_bar").args[0] == 0.5


def test_empty_state_size_and_count_badge_zero(tree):
    small = ui.empty_state("Nothing", size="sm", height="shrink", theme=T)
    assert small.props["height"] == "shrink"
    assert ui.count_badge(0, show_zero=False, theme=T).kind == "space"
    assert ui.count_badge(0, theme=T).texts() == ["0"]


def test_render_for_real():
    widgets = [ui.table(["name"], ROWS, selected=ROWS[:1], on_row_double_press=print, on_row_context=print),
               ui.table(["name"], [], empty="none"), ui.card("x", on_press=print, selected=True, elevated=True, footer=["a"]),
               ui.stat("x", 1, on_press=print, icon="bug"), ui.progress(None), ui.progress(0.5, show_value=True, label="x"),
               ui.modal("x", on_close=print, width="sm", max_height=40), ui.toast("x", progress=0.3, on_press=print),
               ui.empty_state("x", size="lg"), ui.count_badge(0, show_zero=False)]
    assert all(isinstance(w, pz.Widget) for w in widgets)
