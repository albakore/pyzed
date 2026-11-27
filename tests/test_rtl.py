"""Right-to-left layouts (pyzed.bidi): the API, the mirrored layout, text and the text fields."""

import pytest

import pyzed as pz
from pyzed import _core, bidi, i18n, ui

BG = (0x10, 0x10, 0x10)
RED = "#ff0000"
BLUE = "#0000ff"


@pytest.fixture(autouse=True)
def _direction():
    yield
    pz.set_direction("auto")


def _pixels(view, size=(200, 40), direction=None):
    """The RGB rows of ``view`` rendered off-screen (no Pillow needed)."""

    class Shot(pz.App):
        def view(self):
            return pz.container(view(), width="fill", height="fill", bg="#101010")

    Shot.direction = direction
    w, h, rgba, _, _ = _core.screenshot_rgba(Shot(), size=size, scale=1.0, wait=0.0)
    return [[tuple(rgba[(y * w + x) * 4:(y * w + x) * 4 + 3]) for x in range(w)] for y in range(h)]


def _columns(rows, test):
    """The x of every column with a pixel that passes ``test``."""
    return [x for x in range(len(rows[0])) if any(test(row[x]) for row in rows)]


def _red(p):
    return p[0] > 200 and p[1] < 60 and p[2] < 60


def _blue(p):
    return p[2] > 200 and p[0] < 60 and p[1] < 60


def _ink(p):
    return max(abs(a - b) for a, b in zip(p, BG)) > 60


def _boxes():
    return pz.row([pz.container(pz.space(width=20, height=20), bg=RED),
                   pz.container(pz.space(width=20, height=20), bg=BLUE)], spacing=10)


# -- API -------------------------------------------------------------------------------------


def test_rtl_languages():
    assert bidi.is_rtl_language("ar") and bidi.is_rtl_language("he-IL") and bidi.is_rtl_language("fa_IR")
    assert not bidi.is_rtl_language("en") and not bidi.is_rtl_language("es_AR")


def test_auto_follows_the_language():
    assert pz.get_direction() == "ltr"
    i18n.set_language("ar")
    assert pz.get_direction() == "rtl" and pz.is_rtl()
    pz.set_direction("ltr")
    assert pz.get_direction() == "ltr"
    pz.set_direction("rtl")
    i18n.set_language("en")
    assert pz.get_direction() == "rtl"


def test_a_window_uses_its_own_direction_then_the_apps():
    class Main(pz.App):
        direction = "rtl"

    class Other(pz.Window):
        pass

    app, other = Main(), Other()
    other.app = app
    assert app.resolved_direction() == "rtl" and other.resolved_direction() == "rtl"
    other.direction = "ltr"
    assert other.resolved_direction() == "ltr"
    app.set_direction(None)
    assert app.resolved_direction() == "ltr"
    with pytest.raises(ValueError):
        app.set_direction("sideways")


def test_direction_wraps_a_widget():
    assert "direction rtl" in repr(pz.direction(pz.text("x"), "rtl"))
    assert "direction ltr" in repr(pz.text("x").direction("ltr"))
    with pytest.raises(ValueError):
        pz.text("x").direction("up")


def test_view_sees_the_windows_direction():
    seen = []

    class App(pz.App):
        direction = "rtl"

        def view(self):
            seen.append(pz.is_rtl())
            return pz.text("x")

    App().__pyzed_view__()
    assert seen == [True]


def test_arrows_and_chevrons_have_a_mirror_image():
    assert bidi.mirrored_icon("chevron-right") == "chevron-left"
    assert bidi.mirrored_icon("arrow-left") == "arrow-right"
    assert bidi.mirrored_icon("panel-left-close") == "panel-right-close"
    assert bidi.mirrored_icon("undo") == "redo"
    assert bidi.mirrored_icon("house") == "house"


# -- Layout ----------------------------------------------------------------------------------


def test_rows_run_from_the_right():
    ltr = _pixels(_boxes)
    rtl = _pixels(_boxes, direction="rtl")
    assert max(_columns(ltr, _red)) < min(_columns(ltr, _blue)) < 60
    # right to left: the first box (red) is on the right edge, the second one to its left
    assert max(_columns(rtl, _blue)) < min(_columns(rtl, _red))
    assert max(_columns(rtl, _red)) >= 195


def test_a_left_to_right_part_inside_goes_back():
    rtl = _pixels(lambda: pz.column([_boxes().direction("ltr")], width="fill"), direction="rtl")
    # the part sits on the right (the start side) but keeps its own order inside
    assert max(_columns(rtl, _red)) < min(_columns(rtl, _blue))
    assert max(_columns(rtl, _blue)) >= 195


def test_padding_and_alignment_mean_the_start_side():
    def view():
        return pz.container(pz.container(pz.space(width=10, height=10), bg=RED), width="fill", padding=(0, 0, 0, 30),
                            align_x="left")

    assert min(_columns(_pixels(view), _red)) == 30
    assert max(_columns(_pixels(view, direction="rtl"), _red)) == 200 - 30 - 1


def test_progress_bars_and_sliders_grow_from_the_right():
    def bar():
        return pz.progress_bar(0.25, min=0.0, max=1.0, width="fill", height=10, accent=RED, bg="#202020")

    ltr, rtl = _columns(_pixels(bar), _red), _columns(_pixels(bar, direction="rtl"), _red)
    assert min(ltr) < 5 and max(ltr) < 60
    assert max(rtl) > 195 and min(rtl) > 140


def test_arabic_and_hebrew_line_up_on_the_right():
    def view():
        return pz.column([pz.text("مرحبا Pyzed", width="fill"), pz.text("שלום", width="fill")], width="fill")

    ink = _columns(_pixels(view, size=(300, 60), direction="rtl"), _ink)
    assert ink and max(ink) > 280 and min(ink) > 150


def test_text_with_an_alignment_stays_in_its_box():
    # a right-to-left line with an explicit alignment used to be drawn far to the right of its box
    def view():
        return pz.row([pz.text("שלום", align_x="right"), pz.container(pz.space(width=10, height=10), bg=RED)])

    rows = _pixels(view, size=(300, 30))
    ink = [x for x in _columns(rows, _ink) if not _red(rows[10][x])]
    assert max(ink) < min(_columns(rows, _red)) + 12


# -- Text fields -----------------------------------------------------------------------------


def _typing(steps, value=""):
    from pyzed import recording as rec

    class Field(pz.App):
        direction = "rtl"

        def view(self):
            return pz.column([pz.text_input(self.value, on_input=self.set, width=300, size=20)], padding=20)

        def set(self, text):
            self.value = text

    app = Field()
    app.value = value
    rec.record(app, [rec.press("input:0"), *steps(rec)], size=(360, 90), scale=1, fps=10)
    return app.value


def test_typing_right_to_left_and_the_arrows_follow_the_line():
    typed = _typing(lambda rec: [rec.type_text("שלום עולם", cps=100), rec.key("right"), rec.key("right"),
                                 rec.type_text("X", cps=100)])
    # Right goes back in a right-to-left line
    assert typed == "שלום עוXלם"


def test_a_click_puts_the_cursor_where_it_lands_in_non_ascii_text():
    # "שלום" is right-aligned in the field: a click in the empty space on its left puts the cursor at its end,
    # one inside the word between the letters it falls on, one past its right edge at its start
    def click(x):
        return _typing(lambda rec: [rec.press((x, 40)), rec.type_text("X", cps=100)], value="שלום")

    assert click(200) == "שלוםX"
    assert click(310) == "שלXום"
    assert click(330) == "Xשלום"


def test_ui_components_render_right_to_left():
    def view():
        return pz.column([
            ui.breadcrumbs(["الإعدادات", "الحساب"]),
            ui.list_item("الحساب", icon="user", end=pz.icon("chevron-right")),
            ui.input("نور", placeholder="اكتب اسمك"),
            ui.checkbox(True, label="أرسل لي ملخصًا"),
            ui.slider(0.3), ui.progress(0.7),
        ], width="fill", spacing=6)

    rows = _pixels(view, size=(320, 220), direction="rtl")
    assert _columns(rows, _ink)
