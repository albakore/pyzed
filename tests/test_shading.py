"""pyzed.shading: node graphs (.pzshad) compiled to the WGSL of pz.shader."""

import json
from pathlib import Path

import pytest

import pyzed as pz
from pyzed import shading
from pyzed.shading import GraphError, nodes, types

ROOT = Path(__file__).resolve().parent.parent


def rings() -> shading.Graph:
    g = shading.Graph("rings")
    speed = g.uniform("speed", "float", 1.0, min=0, max=4)
    d = g.circle(radius=g.time()["sin"] * 0.05 + 0.3)
    g.output(g.rgba(g.palette(g.uv()["x"] + speed["value"])["rgb"] * g.fill(d)["mask"], 1.0)["color"])
    return g


def test_every_sidebar_entry_compiles_on_its_own():
    bad = {}
    for preset in nodes.PRESETS:
        g = shading.Graph("probe")
        if preset.type in ("parameter", "get_var", "subgraph", "comment"):  # these need a variable, a file...
            continue
        node = g.add(preset.key)
        outputs = g.ports(g.nodes[node.id])[1]
        if outputs and outputs[0].type != "texture":
            g.output(node[outputs[0].name])
        compiled = g.compile()
        problems = compiled.errors or compiled.check()
        problems.pop("wgsl", None)
        if problems:
            bad[preset.key] = problems
    assert bad == {}
    assert len(nodes.PRESETS) > 120 and len(nodes.TYPES) > 80


def test_a_graph_compiles_to_a_shade_function_and_draws():
    g = rings()
    compiled = g.compile()
    assert compiled.ok and not compiled.check()
    assert "fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32)" in compiled.code
    assert compiled.uses_time
    assert compiled.uniforms == {compiled.names["speed"]: 1.0}
    assert pz.shader(g) is not None


def test_saves_and_loads_the_pzshad_format(tmp_path):
    g = rings()
    path = g.save(tmp_path / "rings")
    assert path.suffix == ".pzshad"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format"] == shading.FORMAT and data["name"] == "rings"
    again = shading.load_graph(path)
    assert again.to_dict() == g.to_dict()
    assert again.compile().code == g.compile().code


def test_mutable_variables_change_without_recompiling_and_constants_are_inlined():
    g = rings()
    shader = shading.Shader(g)
    code = shader.wgsl
    shader["speed"] = 3.0
    assert shader.wgsl == code and shader["speed"] == 3.0
    _, uniforms, _, _ = shader.__pyzed_shader__(None)
    assert 3.0 in uniforms.values()
    g.set_variable("speed", mutable=False, value=2.5)
    compiled = g.compile()
    assert compiled.uniforms == {} and "2.5" in compiled.code


def test_types_widen_and_convert():
    assert types.widest(["float", "vec3"]) == "vec3"
    assert types.convert("x", "float", "vec3") == "vec3<f32>(x)"
    assert types.convert("v", "vec3", "vec4") == "vec4<f32>(v, 1.0)"
    with pytest.raises(TypeError):
        types.convert("t", "texture", "float")
    g = shading.Graph()
    a = g.add("float", 2.0)
    b = g.add("vec3", value=[1.0, 2.0, 3.0])
    m = g.add("math", a, b, op="multiply")
    assert g.output_type(m.id, "result") == "vec3"


def test_connecting_checks_types_and_cycles():
    g = shading.Graph()
    tex = g.add_variable("image", "texture", "")
    assert tex.type == "texture"
    t = g.get("image")
    n = g.add("func", op="sin")
    with pytest.raises(GraphError):
        g.connect(t.id, "value", n.id, "x")
    a = g.add("func", op="cos")
    g.connect(n.id, "result", a.id, "x")
    with pytest.raises(GraphError):
        g.connect(a.id, "result", n.id, "x")


def test_expression_named_values_and_errors_on_their_node():
    g = shading.Graph()
    uv = g.uv()
    g.set_var(uv["x"] * 2.0, name="twice")
    e = g.add("expression", g.get_var(name="twice")["value"], 0.5, code="a * b + 0.25", type="float")
    g.output(g.rgba(g.compose(e["result"], 0.0, 0.0)["vector"], 1.0)["color"])
    assert g.locals() == ["twice"]
    compiled = g.compile()
    assert compiled.ok and not compiled.check()
    g.set_param(e.id, "code", "a * b +")
    errors = g.compile().check()
    assert e.id in errors


def test_textures_and_missing_images(tmp_path):
    from test_layout import _png_column  # noqa: F401 - makes sure the PNG helpers import

    g = shading.Graph()
    g.add_variable("photo", "texture", str(tmp_path / "missing.png"))
    photo = g.get("photo")
    g.output(g.add("sample_texture", photo["value"])["color"])
    compiled = g.compile()
    assert "can't find the image" in compiled.errors[photo.id]  # white instead, and the node says so
    assert pz.shader(g) is not None


def test_subgraphs_use_another_pzshad_as_a_function(tmp_path):
    sub = shading.Graph("glow")
    sub.add_variable("strength", "float", 1.0)
    sub.output(sub.rgba(sub.vec3(value=[1.0, 0.5, 0.2])["value"] * sub.get("strength")["value"], 1.0)["color"])
    sub.save(tmp_path / "glow.pzshad")
    g = shading.Graph("main")
    g.path = tmp_path / "main.pzshad"
    call = g.add("subgraph", path="glow.pzshad")
    assert "strength" in [p.name for p in g.ports(g.nodes[call.id])[0]]
    g.set_input(call.id, "strength", 0.5)
    g.output(call["color"])
    compiled = g.compile()
    assert compiled.ok and not compiled.check()


def test_pz_shader_takes_pzshad_files(tmp_path):
    path = rings().save(tmp_path / "rings.pzshad")
    assert pz.shader(str(path), uniforms={"speed": 2.0}) is not None
    assert pz.shader(path) is not None
    shader = shading.load(path)
    assert shader.name == "rings" and "speed" in shader.variables


def test_the_designer_templates_and_the_demos_compile():
    files = sorted((ROOT / "python/pyzed/designer/templates/shaders").glob("*.pzshad"))
    files += sorted((ROOT / "examples/showcase/shaders").glob("*.pzshad"))
    assert len(files) >= 15
    for path in files:
        compiled = shading.load_graph(path).compile()
        assert compiled.ok and not compiled.check(), path.name


def test_arrange_places_nodes_in_columns():
    g = rings()
    g.arrange()
    xs = {n.type: n.x for n in g.nodes.values()}
    assert xs["uv"] < xs["palette"] < xs["output"]


def test_the_catalog_is_translated():
    from pyzed import i18n
    from pyzed.shading.locale import tr

    previous = i18n.language()
    i18n.set_language("es")
    try:
        assert tr("Noise") == "Ruido"
        missing = [c for c in nodes.CATEGORIES if tr(c) == c and c not in ("Color", "Vector", "Variables", "UV")]
        assert missing == []
    finally:
        i18n.set_language(previous)


def test_the_mcp_shader_tools():
    from pyzed.mcp import shaders

    noise = shaders.list_nodes("perlin")
    assert noise and noise[0]["type"] == "noise" and noise[0]["outputs"][0]["name"] == "value"
    assert {n["category"] for n in shaders.list_nodes(category="Shapes")} == {"Shapes"}
    source = shaders.template("plasma")
    result = shaders.check(source)
    assert result["ok"] and "fn shade" in result["wgsl"] and "speed" in result["uniforms"]
    broken = json.loads(source)
    broken["nodes"].append({"id": "99", "type": "expression", "params": {"code": "a +"}})
    broken["links"].append({"from": "99", "out": "result", "to": next(n["id"] for n in broken["nodes"]
                                                                       if n["type"] == "output"), "in": "alpha"})
    result = shaders.check(json.dumps(broken))
    assert not result["ok"] and "99" in result["errors"]
    with pytest.raises(ValueError):
        shaders.template("nope")
