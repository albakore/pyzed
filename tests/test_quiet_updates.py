"""Callbacks that change nothing on screen return ``pz.UNCHANGED`` (no rebuild), and the caches that keep
big views cheap: resolved styles and virtual List boxes."""

import pyzed as pz
from pyzed import style as pz_style
from pyzed.designer import components, new, surface
from pyzed.designer.app import Designer
from pyzed.designer.model import Control
from pyzed.theme import ONE_DARK, ONE_LIGHT, current, use


def designer(tmp_path):
    app = Designer(new.new_form(tmp_path / "shell", template="sidebar"), language_servers=False)
    app.window_size = (1440, 900)
    app.view()  # draws the form once, as the window does
    return app


def test_unchanged_is_exported():
    assert repr(pz.UNCHANGED) == "pz.UNCHANGED"
    assert "UNCHANGED" in pz.__all__


def test_pointer_moves_over_the_designer_redraw_nothing(tmp_path):
    app = designer(tmp_path)
    assert app.window_moved(300, 300) is pz.UNCHANGED
    assert app.pointer_moved_view(300, 300) is pz.UNCHANGED
    assert app.focus_panel("properties") is pz.UNCHANGED
    assert app.focus == "panel"  # the keys still go to the panel
    app.over_form = True
    app.pointer = (-50.0, -50.0)  # outside every container
    app.shown_grips[id(app.doc)] = surface.grips(app)  # the grip tabs as drawn
    assert app.pointer_moved(-50.0, -50.0) is pz.UNCHANGED
    assert app.pointer == (-50.0, -50.0)


def test_pointer_moves_redraw_while_something_follows_them(tmp_path):
    app = designer(tmp_path)
    app.press_tool("button")
    assert app.window_moved(200, 200) is None  # the carried component follows the pointer
    app.window_release()
    app._start("band")
    assert app.pointer_moved_view(10, 10) is None  # the rubber band follows it
    app.drag = None


def test_pointer_moves_redraw_when_grip_tabs_change(tmp_path):
    app = designer(tmp_path)
    app.over_form = True
    containers = [c for c in app.doc.form.controls if app.doc.form.children(c.name)]
    assert containers, "the sidebar template has containers"
    x, y, w, h = app.rects[containers[0].name]
    app.shown_grips[id(app.doc)] = []  # drawn without tabs
    assert app.pointer_moved(x + w / 2, y + h / 2) is None  # over a container: its tab shows


def test_resolved_styles_are_cached_by_theme_and_named_styles():
    before = current()
    use(ONE_DARK)
    first = pz_style._resolve(None, (), {"hover": {"background": "ghost_hover"}})
    assert pz_style._resolve(None, (), {"hover": {"background": "ghost_hover"}}) is first
    use(ONE_LIGHT)
    light = pz_style._resolve(None, (), {"hover": {"background": "ghost_hover"}})
    assert light is not first and light[1] != first[1]  # tokens resolve with the new theme
    use(ONE_DARK)
    pz_style.define_style("quiet-card", background="#112233")
    one = pz_style._resolve(None, ("quiet-card",), None)
    pz_style.define_style("quiet-card", background="#445566")
    two = pz_style._resolve(None, ("quiet-card",), None)
    assert one[1]["background"] != two[1]["background"]
    use(before)


def test_unhashable_styles_are_resolved_without_cache():
    class Odd:
        __hash__ = None

    key = pz_style._style_key
    try:
        key({"x": Odd()})
    except TypeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("an unhashable value must not make a cache key")


def test_long_list_boxes_only_build_the_rows_in_view():
    ctx = components.RenderContext(ONE_DARK, "Form1")
    built = []
    real = components.ui.list_item

    def counting(item, *args, **kwargs):
        built.append(item)
        return real(item, *args, **kwargs)

    components.ui.list_item = counting
    try:
        items = "\n".join(f"Item {i}" for i in range(components.VIRTUAL_ROWS + 50))
        components.render(Control("list1", "list_box", 0, 0, 200, 300, props={"items": items}), ctx)
        assert built == []  # rows are built by the virtual column as they scroll into view
        components.render(Control("list2", "list_box", 0, 0, 200, 300, props={"items": "a\nb"}), ctx)
        assert built == ["a", "b"]
    finally:
        components.ui.list_item = real
