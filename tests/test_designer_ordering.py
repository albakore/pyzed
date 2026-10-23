"""The z-order commands (bring forward, send backward, to the front and back) and the tab order editor."""

import pyzed as pz
from pyzed.designer import commands, keymap, surface, tab_order
from pyzed.designer.app import Designer
from pyzed.designer.document import Document
from pyzed.designer.model import Control, Form
from pyzed.designer.runtime import FormApp


def _stacked() -> Form:
    form = Form(width=400, height=300)
    form.add(Control(name="a", type="panel", x=0, y=0, width=100, height=100))
    form.add(Control(name="b", type="panel", x=50, y=50, width=100, height=100))
    form.add(Control(name="far", type="panel", x=300, y=200, width=50, height=50))
    form.add(Control(name="c", type="panel", x=60, y=60, width=100, height=100))
    form.add(Control(name="inner", type="label", x=4, y=4, width=40, height=20, parent="a"))
    return form


def _order(form: Form) -> list:
    return [c.name for c in form.controls if c.parent is None]


def test_one_step_forward_and_backward_passes_the_next_overlapping_sibling():
    form = _stacked()
    form.reorder(["a"], "forward")
    assert _order(form) == ["b", "a", "far", "c"]
    form.reorder(["a"], "forward")  # "far" does not overlap it: it goes past "c"
    assert _order(form) == ["b", "far", "c", "a"]
    form.reorder(["a"], "forward")  # already in front
    assert _order(form) == ["b", "far", "c", "a"]
    form.reorder(["a"], "backward")
    assert _order(form) == ["b", "far", "a", "c"]
    form.reorder(["c"], "back")
    assert _order(form) == ["c", "b", "far", "a"]
    form.reorder(["c"], "front")
    assert _order(form) == ["b", "far", "a", "c"]
    assert [c.name for c in form.children("a")] == ["inner"]  # what it holds goes with it


def test_z_order_commands_have_figma_keys_and_one_undo_step_each():
    d = Designer(language_servers=False)
    d.doc = Document(_stacked())
    d.doc.select("a")
    for action, keys in (("bring_forward", "ctrl-]"), ("send_backward", "ctrl-["),
                         ("bring_to_front", "ctrl-shift-]"), ("send_to_back", "ctrl-shift-[")):
        assert commands.BY_ID[action].keys == keys
        assert keymap.shown_keys(action)
    commands.run("bring_to_front", d)
    assert _order(d.doc.form)[-1] == "a"
    d.on_key("ctrl-[")
    assert _order(d.doc.form) == ["b", "far", "a", "c"]
    d.undo()
    assert _order(d.doc.form)[-1] == "a"


def _fields() -> Form:
    form = Form(width=400, height=300)
    form.add(Control(name="heading", type="label", x=10, y=10, width=200, height=24))
    form.add(Control(name="email", type="input", x=10, y=40, width=200, height=28))
    form.add(Control(name="ok", type="button", x=10, y=200, width=80, height=32))
    form.add(Control(name="box", type="panel", x=220, y=40, width=160, height=120))
    form.add(Control(name="user", type="input", x=10, y=10, width=140, height=28, parent="box"))
    form.add(Control(name="agree", type="checkbox", x=10, y=80, width=200, height=24))
    return form


def test_tab_order_lists_the_fields_and_is_saved_in_the_pzform():
    form = _fields()
    assert tab_order.eligible(form) == ["email", "user", "agree"]  # no labels, buttons or containers
    assert tab_order.sequence(form) == ["email", "user", "agree"]
    form.set_tab_order(["agree", "missing", "agree", "email"])
    assert form.tab_order == ["agree", "email"]
    assert tab_order.sequence(form) == ["agree", "email", "user"]  # the rest in drawing order
    data = form.to_dict()
    assert data["form"]["tab_order"] == ["agree", "email"]
    again = Form.from_dict(data)
    assert again.tab_order == ["agree", "email"]
    again.rename("email", "mail")
    assert again.tab_order == ["agree", "mail"]
    again.remove(["agree"])
    assert again.tab_order == ["mail"]
    assert "tab_order" not in Form().to_dict()["form"]  # forms without one stay as they were


def test_numbering_the_fields_by_clicking_them():
    d = Designer(language_servers=False)
    d.doc = Document(_fields())
    commands.run("tab_order", d)
    assert d.tab_order_mode and commands.BY_ID["tab_order"].checked(d)
    surface.form_surface(d, d.theme_obj)  # the badges and the banner draw
    d.press_control("agree")
    d.press_control("user")
    d.press_control("heading")  # not a field: nothing happens
    assert d.doc.form.tab_order == ["agree", "user", "email"]
    assert d.tab_editor.number("email") == 3
    assert d.doc.selection == []  # numbering does not select or move
    d.press_control("agree")  # clicked again: it goes after the others clicked
    assert d.doc.form.tab_order == ["user", "agree", "email"]
    d.on_key("escape")
    assert not d.tab_order_mode
    d.undo()  # the whole session is one undo step
    assert d.doc.form.tab_order == []
    commands.run("tab_order", d)
    d.press_control("email")
    d.tab_editor.reset()
    assert d.doc.form.tab_order == []


def test_the_running_form_gives_each_listed_control_its_tab_index(monkeypatch):
    form = _fields()
    form.set_tab_order(["agree", "email"])
    seen = {}
    real = pz._core.focusable

    def focusable(content, *args, tab_index=None, **kwargs):
        if tab_index is not None:
            seen[len(seen)] = tab_index
        return real(content, *args, tab_index=tab_index, **kwargs)

    monkeypatch.setattr(pz._core, "focusable", focusable)
    app = FormApp(form, {})
    app.view()
    assert sorted(seen.values()) == [1, 2]
    assert app.runtime._tab_index == {"agree": 1, "email": 2}
