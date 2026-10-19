from types import SimpleNamespace

import pyzed as pz
from pyzed import ui
from test_layout import _png_column


def picker(**kwargs):
    got = []
    instance = ui.ColorPicker.create(on_change=lambda e: got.append(e.value), **kwargs)
    return instance, got


def at(x, y=0, width=100, height=100, kind="mouse_down", dx=0):
    return SimpleNamespace(x=x, y=y, width=width, height=height, type=kind, dx=dx)


def test_solid_color_with_alpha():
    p, got = picker(value="#ff0000")
    assert p.parts() == ([(0.0, "#ff0000")], None, None, 1.0)
    p.pick_alpha(at(50))
    assert got[-1] == "#ff000080"
    p.pick_sv(at(100, 0))  # top right: full saturation and value, alpha kept
    assert got[-1] == "#ff000080"
    p.pick_hue(at(1 / 3 * 100))
    assert got[-1] == "#00ff0080"
    p.set_alpha_percent(100)
    assert got[-1] == "#00ff00"
    assert isinstance(p.render(), pz.Widget)


def test_typing_hex_ignores_partial_text():
    p, got = picker()
    assert p.type_hex("12") is None and got == []
    p.type_hex("123")
    assert got[-1] == "#112233"
    p.type_hex("zzzzzz")
    assert len(got) == 1


def test_gradient_stops():
    p, got = picker(value="#3b82f6")
    p.set_mode("Gradient")
    g = got[-1]
    assert isinstance(g, pz.Gradient) and len(g.stops) == 2 and g.angle == 90
    p.add_stop(at(50))
    assert len(got[-1].stops) == 3 and p.stop == 1
    p.set_color("#00ff00")
    assert got[-1].stops[1] == (0.5, "#00ff00")
    p.move_stop(1, at(90))
    assert [o for o, _ in got[-1].stops] == [0.0, 0.9, 1.0]
    p.set_angle(375)
    assert got[-1].angle == 15
    p.remove_stop()
    assert len(got[-1].stops) == 2
    assert p.remove_stop() is None  # a gradient keeps two stops
    p.set_mode("Solid")
    assert isinstance(got[-1], str)
    assert isinstance(p.render(), pz.Widget)


def test_masks_make_a_paint():
    p, got = picker(value="#ff0000")
    p.toggle_mask(True)
    paint = got[-1]
    assert isinstance(paint, pz.Paint) and paint.mask.stops == [(0.0, 1.0), (1.0, 0.0)]
    p.add_mask_stop(at(50))
    assert len(got[-1].mask.stops) == 3 and p.mask_stop == 1
    p.set_mask_opacity(0.25)
    assert got[-1].mask.stops[1] == (0.5, 0.25)
    p.set_angle(90)
    assert got[-1].mask.angle == 90
    assert isinstance(p.render(), pz.Widget)
    p.toggle_mask(False)
    assert got[-1] == "#ff0000"


def test_picker_renders_its_value(tmp_path):
    class Demo(pz.App):
        def view(self):
            return pz.container(ui.ColorPicker(value="#ff000080", gradients=False, masks=False), padding=0)

    out = tmp_path / "picker.png"
    pz.screenshot(Demo, out, size=(300, 380), scale=1)
    column = _png_column(out, 255)
    # the saturation/value square is drawn for the picked hue: red in its top right
    assert any(r > 200 and g < 60 and b < 60 for r, g, b, *_ in column)
    swatch = ui.color_swatch(pz.Gradient(["#000", "#fff"]))
    assert isinstance(swatch, pz.Widget)
