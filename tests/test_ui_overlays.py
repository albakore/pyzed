"""Layers, modals, the command palette, pickers, fuzzy matching and toasts in ``pyzed.ui.overlays``."""

import pytest

import pyzed as pz
from pyzed import ui
from pyzed.ui import overlays as ov
from ui_tree import install

DARK, LIGHT = pz.themes.ONE_DARK, pz.themes.ONE_LIGHT


@pytest.fixture
def tree(monkeypatch):
    return install(monkeypatch)


# --- fuzzy matching -----------------------------------------------------------------------------------------


def test_fuzzy_match_positions_and_misses():
    assert ov.fuzzy_match("", "anything") == (0.0, [])
    assert ov.fuzzy_match("fF", "file finder")[1] == [0, 5]
    assert ov.fuzzy_match("tgl", "toggle")[1] == [0, 2, 4]
    assert ov.fuzzy_match("z", "abc") is None
    assert ov.fuzzy_match("ba", "ab") is None  # order matters
    assert ov.fuzzy_match("open file", "open file")[1] == list(range(4)) + list(range(5, 9))  # spaces are ignored


def test_fuzzy_match_prefers_word_starts_and_runs():
    word_start, _ = ov.fuzzy_match("ws", "workspace: save")
    inside, _ = ov.fuzzy_match("ws", "news")
    assert word_start > inside
    run, _ = ov.fuzzy_match("save", "save all")
    scattered, _ = ov.fuzzy_match("save", "sxaxvxe all")
    assert run > scattered
    short, _ = ov.fuzzy_match("go", "go")
    long, _ = ov.fuzzy_match("go", "go to line in a much longer command")
    assert short > long


def test_fuzzy_filter_keeps_order_without_query_and_sorts_with_it():
    items = ["zed: quit", "editor: save", "workspace: save all"]
    assert [i for i, _ in ov.fuzzy_filter("", items)] == items
    assert [i for i, _ in ov.fuzzy_filter("save", items)] == ["editor: save", "workspace: save all"]
    # ties keep the original order
    assert [i for i, _ in ov.fuzzy_filter("a", ["ab", "ac"])] == ["ab", "ac"]
    commands = [ov.PaletteItem("Open file"), ov.PaletteItem("Close tab")]
    assert ov.fuzzy_filter("tab", commands, key=lambda c: c.label)[0][0] is commands[1]


# --- widgets ------------------------------------------------------------------------------------------------


def test_highlighted_splits_runs(tree):
    plain = ov.highlighted("abc", [], color="#111111", match_color="#ff0000")
    assert plain.kind == "text" and plain.args[0] == "abc"
    runs = ov.highlighted("abcde", [0, 1, 4], color="#111111", match_color="#ff0000").args[0]
    assert [(r.args[0], r.props["color"], r.props["weight"]) for r in runs] == [
        ("ab", "#ff0000", "semibold"),
        ("cd", "#111111", None),
        ("e", "#ff0000", "semibold"),
    ]


def test_layer_without_overlay_is_the_base(tree):
    assert ov.layer("base") == "base"


def test_layer_stacks_a_dismissable_backdrop(tree):
    stack = ov.layer("base", "dialog", on_dismiss="close", backdrop="#00000080", offset=50)
    assert stack.kind == "stack"
    base, shade, top = stack.args[0]
    assert base == "base"
    assert shade.kind == "mouse_area" and shade.props["on_press"] == "close"
    assert shade.args[0].props["bg"] == "#00000080"
    assert top.args[0].kind == "opaque" and top.args[0].args[0] == "dialog"
    assert top.props["padding"] == (50, 16, 16, 16) and top.props["align_y"] == "start"


def test_layer_without_dismiss_or_backdrop(tree):
    _, shade, top = ov.layer("base", "dialog", align_y="center").args[0]
    assert shade.kind == "container" and shade.props["bg"] == "transparent"
    assert top.props["padding"] == 16


def test_modal_header_and_footer(tree):
    dialog = ov.modal("body", title="Rename", on_close="close", footer=["cancel", "ok"], width=400, theme=DARK)
    assert dialog.props["width"] == 400 and dialog.props["bg"] == DARK.elevated
    assert dialog.props["radius"] == DARK.radius + 4
    header, body, footer = dialog.args[0].args[0]
    assert "Rename" in header.texts()
    assert header.find("button").args[1] == "close"
    assert body == "body"
    assert footer.args[0][1:] == ["cancel", "ok"]


def test_modal_without_header_or_footer(tree):
    header, body, footer = ov.modal("body").args[0].args[0]
    assert header is None and body == "body" and footer is None


def test_picker_rows(tree):
    pressed = object()
    items = [(ov.PaletteItem("Open file", pressed, keys="ctrl-o", icon="file", detail="workspace"), [0]),
             (ov.PaletteItem("Close"), [])]
    surface = ov.picker("o", "query", items, selected=1, width=500, max_height=200, theme=DARK)
    assert surface.props["width"] == 500 and surface.props["clip"] is True
    search = surface.find("text_input")
    assert search.args[0] == "o" and search.props["on_input"] == "query" and search.props["id"] == "picker"
    rows = surface.find_all("button", lambda n: n.props.get("height") == 30)
    assert [r.args[1] for r in rows] == [pressed, None]
    assert rows[0].props["bg"] == "transparent" and rows[1].props["bg"] == DARK.ghost_selected
    assert "workspace" in rows[0].texts() and "O" in rows[0].texts()  # the key binding's caps
    assert surface.find("container", lambda n: n.props.get("max_height") == 200)


def test_picker_shows_the_empty_text(tree):
    surface = ov.picker("zzz", None, [], empty_text="Nothing here", theme=DARK)
    assert "Nothing here" in surface.texts()


def test_command_palette_filters_commands(tree):
    commands = [ov.PaletteItem("editor: save"), ov.PaletteItem("zed: quit"), ov.PaletteItem("workspace: save all")]
    palette = ov.command_palette("save", "query", commands, theme=DARK)
    rows = palette.find_all("button", lambda n: n.props.get("height") == 30)
    assert len(rows) == 2
    assert "quit" not in " ".join(palette.texts())


def test_picker_shadow_follows_the_theme(tree):
    dark = ov.picker("", None, [], theme=DARK).props["shadow"][0]
    light = ov.picker("", None, [], theme=LIGHT).props["shadow"][0]
    assert dark != light


@pytest.mark.parametrize("kind, icon", [("info", "info"), ("success", "circle-check"), ("warning", "triangle-alert"),
                                        ("error", "circle-x")])
def test_toast_kinds(tree, kind, icon):
    from pyzed.icons import glyph

    card = ov.toast("Saved", kind=kind, theme=DARK)
    mark = card.find("text", lambda n: n.props.get("font") == "icons")
    assert mark.args[0] == glyph(icon) and mark.props["color"] == DARK.color(kind)
    assert card.find_all("button") == []


def test_toast_message_actions_and_dismiss(tree):
    card = ov.toast("Update ready", "Restart to apply", actions=["restart"], on_dismiss="dismiss", width=300,
                    theme=DARK)
    assert card.props["width"] == 300
    assert {"Update ready", "Restart to apply"} <= set(card.texts())
    assert card.find("row", lambda n: n.args[0] == ["restart"])
    assert card.find("button").args[1] == "dismiss"


def test_toasts_stack_in_the_corner(tree):
    assert ov.toasts("base", []) == "base"
    stack = ov.toasts("base", ["a", "b"], spacing=4)
    base, corner = stack.args[0]
    assert base == "base"
    assert corner.props["align_x"] == corner.props["align_y"] == "end"
    column = corner.args[0]
    assert column.props["spacing"] == 4 and [n.args[0] for n in column.args[0]] == ["a", "b"]


def test_overlays_are_exported_from_ui():
    assert ui.command_palette is ov.command_palette and ui.PaletteItem is ov.PaletteItem and ui.toasts is ov.toasts


def test_overlays_render(tmp_path):
    class Demo(pz.App):
        size = (520, 320)

        def view(self):
            commands = [ui.PaletteItem("editor: save", keys="ctrl-s"), ui.PaletteItem("zed: quit")]
            base = ui.toasts(ui.label("editor"), [ui.toast("Saved", kind="success")])
            return ui.layer(base, ui.command_palette("sa", lambda q: None, commands), on_dismiss="close")

    out = tmp_path / "overlays.png"
    Demo().screenshot(out, scale=1)
    assert out.stat().st_size > 0
