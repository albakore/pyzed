"""The Shader view of Pyzed Design: .pzshad files edited as node graphs."""

import json

import pytest

from pyzed import _core, shading
from pyzed.designer import dialogs, shader_editor
from pyzed.designer.app import Designer
from pyzed.designer.shader_doc import ShaderDocument, new_shader, templates
from pyzed.shading import layout as L


@pytest.fixture
def responsive(monkeypatch):
    """Builds responsive views right away, at a fixed size, so the canvas is part of the view."""
    monkeypatch.setattr(_core, "responsive", lambda build, **_: build(1000.0, 700.0))


def designer(tmp_path, graph=None) -> Designer:
    path = tmp_path / "glow.pzshad"
    (graph or shading.new("glow")).save(path)
    return Designer(path, language_servers=False)


def test_opens_a_pzshad_in_the_shader_view(tmp_path, responsive):
    d = designer(tmp_path)
    assert isinstance(d.doc, ShaderDocument) and shader_editor.is_shader(d)
    for tab in ("graph", "preview", "code"):
        d.doc.tab = tab
        assert d.view() is not None
    assert d.doc.fit_pending is False  # fitted once the canvas knew its size


def test_panels_show_the_sidebar_outline_and_properties(tmp_path, responsive):
    d = designer(tmp_path)
    doc = d.doc
    doc.add_variable("float", name="speed", value=1.0)
    t = d.theme_obj
    assert shader_editor.design_panel(d, t) is not None
    for node_id in list(doc.graph.nodes):
        doc.select(node_id)
        assert shader_editor.properties(d, t) is not None
    doc.select_variable("speed")
    assert shader_editor.properties(d, t) is not None
    assert shader_editor.events(d, t) is not None


def test_a_click_in_the_sidebar_adds_a_node_and_a_drag_drops_it(tmp_path):
    d = designer(tmp_path)
    ed = d.shading
    before = len(d.doc.graph.nodes)
    ed.press_preset("noise")
    d.window_release()
    assert len(d.doc.graph.nodes) == before + 1
    ed.press_preset("func:sin")
    d.window_moved(300, 300)
    ed.enter()
    ed.moved(400, 300)
    d.window_release()
    node = d.doc.graph.nodes[d.doc.selection[0]]
    assert node.type == "func" and node.params["op"] == "sin"
    assert d.doc.undo() and len(d.doc.graph.nodes) == before + 1


def test_dragging_from_an_output_to_an_input_wires_them(tmp_path):
    d = designer(tmp_path)
    doc, ed = d.doc, d.shading
    g = doc.graph
    a = doc.add_node("uv", (0, 0))
    b = doc.add_node("func:sin", (300, 0))
    ed.press_port(a, "x", True)
    ed.over = True
    ed.moved(*doc.to_view(*L.port_position(g, g.nodes[b], "x", False)))
    ed.release()
    link = doc.graph.link_into(b, "x")
    assert link is not None and (link.src, link.out) == (a, "x")
    # pressing the connected input picks the wire up again
    ed.press_port(b, "x", False)
    assert doc.graph.link_into(b, "x") is None and ed.drag["mode"] == "wire"


def test_dropping_a_wire_on_empty_space_opens_the_search_and_wires_the_pick(tmp_path):
    d = designer(tmp_path)
    doc, ed = d.doc, d.shading
    a = doc.add_node("uv", (0, 0))
    ed.press_port(a, "uv", True)
    ed.over = True
    ed.moved(700, 500)
    ed.release()
    assert ed.search is not None and ed.search["wire"] == (a, "uv", True)
    ed.set_search("twirl")
    results = ed.search_results()
    assert results and results[0].type == "twirl"
    ed.pick(results[0])
    twirl = doc.selection[0]
    assert doc.graph.link_into(twirl, "uv").src == a


def test_variables_drop_as_parameter_nodes_and_rename_everywhere(tmp_path):
    d = designer(tmp_path)
    doc, ed = d.doc, d.shading
    doc.add_variable("float", name="speed")
    ed.press_variable("speed")
    d.window_moved(50, 50)
    d.window_moved(200, 200)
    ed.over = True
    d.window_release()
    node = doc.graph.nodes[doc.selection[0]]
    assert node.type == "parameter" and node.params["name"] == "speed"
    assert doc.set_variable("speed", name="pace") is None
    assert node.params["name"] == "pace"


def test_copy_paste_undo_and_keys(tmp_path):
    d = designer(tmp_path)
    doc = d.doc
    n = len(doc.graph.nodes)
    doc.select_all()
    d.focus = "canvas"
    d.on_key("ctrl-d")
    assert len(doc.graph.nodes) == 2 * n - 1  # there is only one Output
    d.on_key("ctrl-z")
    assert len(doc.graph.nodes) == n
    doc.select(doc.graph.output_node.id)
    d.on_key("delete")
    assert doc.graph.output_node is None
    d.on_key("ctrl-z")
    assert doc.graph.output_node is not None


def test_saves_what_was_edited(tmp_path):
    d = designer(tmp_path)
    d.doc.add_node("noise", (0, 200))
    d.save()
    data = json.loads((tmp_path / "glow.pzshad").read_text(encoding="utf-8"))
    assert any(n["type"] == "noise" for n in data["nodes"])
    assert not d.doc.dirty


def test_new_shader_from_a_template(tmp_path, monkeypatch, responsive):
    monkeypatch.chdir(tmp_path)
    d = designer(tmp_path)
    d.new("shader")
    assert d.new_state["kind"] == "shader" and d.new_state["name"].startswith("shader")
    assert dialogs.new_form(d, d.theme_obj) is not None
    names = [name for name, _, _ in templates()]
    assert names[0] == "blank" and "plasma" in names
    d.set_new("template", "plasma")
    d.set_new("folder", str(tmp_path))
    d.create_new_shader()
    assert isinstance(d.doc, ShaderDocument) and d.doc.graph.variable("speed") is not None
    assert (tmp_path / f"{d.new_state['name']}.pzshad").is_file()
    assert new_shader("x", template="clouds").graph.variable("cover") is not None


def test_errors_show_on_their_node(tmp_path, responsive):
    d = designer(tmp_path)
    doc = d.doc
    e = doc.add_node("expression", (0, 300), code="a +")
    doc.connect(e, "result", doc.graph.output_node.id, "alpha")
    assert e in doc.diagnostics()
    assert d.view() is not None
