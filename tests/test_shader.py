"""pz.shader: WGSL checked in Python, uniforms as functions, the fallback without a GPU."""

import pytest

import pyzed as pz
from test_layout import _png_column

RED = """
fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> {
    return color();
}
"""


def test_invalid_code_raises_with_the_compiler_message():
    with pytest.raises(ValueError, match="invalid shader"):
        pz.shader("fn shade(uv: vec2<f32>) -> f32 { return 1; }")
    with pytest.raises(ValueError, match="define fn shade"):
        pz.shader("fn other() -> f32 { return 1.0; }")
    with pytest.raises(ValueError, match="unknown|no definition|undefined|not found"):
        pz.shader(RED)  # color() is only defined by a uniform


def test_uniforms_become_functions():
    pz.shader(RED, uniforms={"color": "#ff0000"})
    pz.shader(RED.replace("color()", "vec4<f32>(spot(), 0.0, 1.0)"), uniforms={"spot": (0.5, 0.5)})
    with pytest.raises(ValueError, match="at most 32"):
        pz.shader(RED, uniforms={"color": "#ff0000", **{f"u{i}": 1.0 for i in range(32)}})
    with pytest.raises(ValueError, match="not a valid uniform name"):
        pz.shader(RED, uniforms={"bad name": 1.0, "color": "#fff"})
    with pytest.raises(TypeError):
        pz.shader(RED, uniforms={"color": object()})


def test_draws_the_shader_or_its_fallback(tmp_path):
    class Demo(pz.App):
        size = (40, 40)

        def view(self):
            return pz.shader(RED, uniforms={"color": "#ff0000"}, fallback="#0000ff")

    out = tmp_path / "shot.png"
    pz.screenshot(Demo, out, size=(40, 40), scale=1)
    r, g, b = _png_column(out, 20)[20][:3]
    # Red where a GPU draws the shader, blue (the fallback) on the software renderer.
    assert (r > 240 and b < 20) or (b > 240 and r < 20)
