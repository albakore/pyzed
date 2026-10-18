import struct

import pytest

import pyzed as pz
from pyzed import ui
from pyzed.cli import main as cli_main


def png_size(path):
    with open(path, "rb") as f:
        header = f.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", header[16:24])


def test_widgets_build_a_tree():
    tree = pz.column(
        [
            pz.text("hello", size=14, color="#ff0000"),
            "plain strings become text",
            None,
            [pz.row([pz.icon("folder"), pz.space(width="fill")])],
            pz.container(pz.button("ok", on_press="msg"), padding=(4, 8), bg=(40, 44, 51), radius=6),
        ],
        spacing=8,
    )
    assert isinstance(tree, pz.Widget)
    assert "column [4]" in repr(tree)


@pytest.mark.parametrize("color", ["#zzz", "red-ish", (1, 2)])
def test_invalid_colors_raise(color):
    with pytest.raises((ValueError, TypeError)):
        pz.text("x", color=color)


def test_invalid_length_raises():
    with pytest.raises(ValueError):
        pz.container("x", width="huge")


def test_theme_helpers():
    assert pz.theme.alpha("#ffffff", 0.5) == "#ffffff80"
    assert pz.theme.mix("#000000", "#ffffff", 0.5) == "#808080"
    custom = pz.themes.ONE_DARK.derive(name="Mine", accent="#ff00ff", syntax={"keyword": "#00ff00"})
    assert custom.accent == "#ff00ff"
    assert custom.syntax["keyword"] == "#00ff00"
    assert custom.syntax["string"] == pz.themes.ONE_DARK.syntax["string"]
    assert "comment, punctuation.definition.comment" in custom.syntax_scopes()


def test_fuzzy_filter_orders_by_score():
    items = ["workspace: toggle left dock", "file finder: toggle", "zed: quit"]
    result = [item for item, _ in ui.fuzzy_filter("toggle", items)]
    assert "zed: quit" not in result
    assert set(result) == {"workspace: toggle left dock", "file finder: toggle"}
    assert ui.fuzzy_match("xyz", "abc") is None


def test_tree_from_paths_sorts_folders_first_and_bubbles_status():
    nodes = ui.TreeNode.from_paths(["README.md", "src/main.rs", "src/lib.rs"], {"src/main.rs": "modified"})
    assert [n.name for n in nodes] == ["src", "README.md"]
    assert nodes[0].status == "modified"
    assert [c.name for c in nodes[0].children] == ["lib.rs", "main.rs"]


def test_key_formatting():
    ui.base.KEY_STYLE = "words"
    assert ui.format_keys("ctrl-shift-p") == [["Ctrl", "Shift", "P"]]
    assert ui.format_keys("ctrl-k ctrl-s") == [["Ctrl", "K"], ["Ctrl", "S"]]


def test_components_render(tmp_path):
    class Demo(pz.App):
        size = (800, 500)

        def view(self):
            return ui.workspace(
                pz.column([
                    ui.tab_bar([ui.Tab.for_file("a.py"), ui.Tab.for_file("b.rs", dirty=True)], "a.py"),
                    ui.editor("a.py", "def hello():\n    return 42\n", path="a.py", markers={1: "created"}),
                ]),
                title_bar=ui.title_bar([ui.title_button("demo", chevron=True)], [ui.avatar("PZ")]),
                left=ui.tree(ui.TreeNode.from_paths(["a.py", "b.rs"]), expanded=set()),
                bottom=ui.terminal("\x1b[32mok\x1b[0m done"),
                status_bar=ui.status_bar([ui.status_item("1:1")]),
            )

    out = tmp_path / "demo.png"
    Demo().screenshot(out, scale=1)
    assert png_size(out) == (800, 500)


def test_view_errors_render_an_error_screen(tmp_path):
    class Broken(pz.App):
        size = (300, 200)

        def view(self):
            raise RuntimeError("boom")

    out = tmp_path / "broken.png"
    Broken().screenshot(out, scale=1)
    assert png_size(out) == (300, 200)


def test_cli_new(tmp_path, capsys):
    target = tmp_path / "my-app"
    assert cli_main(["new", str(target)]) == 0
    source = (target / "main.py").read_text()
    assert 'title = "My App"' in source
    compile(source, "main.py", "exec")
