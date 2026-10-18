"""Tests for themes, drawing, async helpers, windows, subscriptions and the newer widgets."""

import asyncio
import importlib
import struct
import sys
from pathlib import Path

import pytest

import pyzed as pz
from pyzed import _async, draw, ui

ROOT = Path(__file__).resolve().parent.parent


def png_size(path):
    with open(path, "rb") as f:
        header = f.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", header[16:24])


def rgba_png(width, height):
    """Raw RGBA pixels for ``pz.image(..., size=(w, h))``."""
    return bytes((x * 255 // width, y * 255 // height, 128, 255)[i] for y in range(height) for x in range(width)
                 for i in range(4))


# -- themes -----------------------------------------------------------------


def test_bundled_zed_themes_are_registered():
    names = pz.themes.names()
    for name in ["One Dark", "One Light", "Ayu Dark", "Ayu Light", "Ayu Mirage", "Gruvbox Dark", "Gruvbox Light"]:
        assert name in names
    assert pz.themes.get("ayu dark") is pz.themes.AYU_DARK
    assert pz.themes.AYU_LIGHT.appearance == "light"
    with pytest.raises(KeyError):
        pz.themes.get("No such theme")


def test_theme_from_zed_reads_style_tokens():
    family = {
        "name": "Test family",
        "themes": [{
            "name": "Test Dark",
            "appearance": "dark",
            "style": {
                "background": "#101010ff",
                "editor.background": "#202020ff",
                "text": "#eeeeeeff",
                "text.accent": "#ff8800ff",
                "border": "#333333ff",
                "syntax": {"keyword": {"color": "#ff00ffff"}},
            },
        }],
    }
    theme = pz.Theme.from_zed(family)
    assert theme.name == "Test Dark"
    assert theme.editor.lower().startswith("#202020")
    assert theme.text.lower().startswith("#eeeeee")
    assert theme.syntax["keyword"].lower().startswith("#ff00ff")
    loaded = pz.themes.load_zed(family)
    assert pz.themes.get("Test Dark") is loaded[0]


def test_theme_generate_and_accent():
    dark = pz.Theme.generate("Gen", background="#15171c", text="#e6e6e6", accent="#ff8a65")
    assert dark.appearance == "dark" and dark.accent == "#ff8a65"
    light = pz.Theme.generate("Gen light", background="#fafafa", text="#202020", accent="#3366ff")
    assert light.appearance == "light"
    tinted = dark.with_accent("#00c8ff")
    assert tinted.accent == "#00c8ff" and tinted.background == dark.background


def test_theme_roundtrip_and_save(tmp_path):
    theme = pz.themes.GRUVBOX_DARK
    assert pz.Theme.from_dict(theme.to_dict()) == theme
    path = tmp_path / "theme.json"
    theme.save(path)
    assert pz.Theme.load(path) == theme


def test_auto_theme_follows_system_appearance():
    auto = pz.themes.auto("One Light", "One Dark")
    assert pz.theme.resolve(auto, dark=True).name == "One Dark"
    assert pz.theme.resolve(auto, dark=False).name == "One Light"
    assert pz.theme.resolve("Ayu Mirage", dark=True).name == "Ayu Mirage"


def test_scoped_theme_restores_previous():
    before = pz.theme.current()
    with pz.themes.AYU_LIGHT:
        assert pz.theme.current() is pz.themes.AYU_LIGHT
    assert pz.theme.current() is before


def test_window_resolves_theme_from_app():
    class Main(pz.App):
        theme = "Gruvbox Light"

    class Child(pz.Window):
        pass

    app, child = Main(), Child()
    child.app = app
    assert child.resolved_theme().name == "Gruvbox Light"
    child.theme = pz.themes.AYU_DARK
    assert child.resolved_theme() is pz.themes.AYU_DARK
    assert not child.is_open


# -- drawing ----------------------------------------------------------------


def test_draw_helpers_build_shapes():
    assert draw.rect(0, 0, 10, 10, fill="#fff")["type"] == "rect"
    assert draw.polyline([(0, 0), (1, 1)], closed=True)["ops"][-1] == ("Z",)
    pie = draw.arc(10, 10, 5, 0, 90, pie=True, fill="#f00")
    assert pie["ops"][0] == ("M", 10, 10)
    group = draw.group([draw.circle(0, 0, 1)], x=5, rotation=45)
    assert [s["type"] for s in group] == ["save", "translate", "rotate", "circle", "restore"]


def test_canvas_rejects_unknown_shapes():
    with pytest.raises((ValueError, TypeError, KeyError)):
        pz.canvas([{"type": "hexagon"}], width=10, height=10)


# -- async ------------------------------------------------------------------


def collect(value):
    out = []
    _async.drain(value, out.append)
    return out


def test_drain_handles_every_kind_of_value():
    async def coro():
        await asyncio.sleep(0)
        return "done"

    async def agen():
        for i in range(3):
            await asyncio.sleep(0)
            yield i

    def gen():
        yield "a"
        yield None  # skipped
        yield "b"

    assert collect(coro()) == ["done"]
    assert collect(agen()) == [0, 1, 2]
    assert collect(gen()) == ["a", "b"]
    assert collect("plain") == ["plain"]
    assert collect(None) == []


def test_drain_stops_generators_when_the_app_is_gone():
    closed = []

    def gen():
        try:
            for i in range(100):
                yield i
        finally:
            closed.append(True)

    def emit(item):
        raise RuntimeError("the app has stopped")

    _async.drain(gen(), emit)
    assert closed == [True]


def test_shared_loop_runs_coroutines():
    async def answer():
        return 42

    assert pz.spawn(answer()).result(timeout=5) == 42
    assert pz.asyncio_loop() is pz.asyncio_loop()


# -- subscriptions and commands ---------------------------------------------


def test_subscriptions():
    tick = pz.every(0.5, "tick")
    assert isinstance(tick, pz.Subscription)
    assert "every" in repr(tick)
    with pytest.raises(ValueError):
        pz.every(0, "tick")

    async def feed():
        yield 1

    assert isinstance(pz.listen(feed, key="feed"), pz.Subscription)


def test_commands_build():
    async def work():
        return 1

    pending = work()
    commands = [
        pz.Command.perform(work),
        pz.Command.perform(pending, lambda r: None),
        pz.Command.scroll_to("list", 0, 100),
        pz.Command.copy("text"),
        pz.Command.close_window(),
        pz.Command.batch([pz.Command.exit(), pz.Command.focus("x")]),
    ]
    assert all(isinstance(c, pz.Command) for c in commands)
    pending.close()


# -- widgets ----------------------------------------------------------------


def test_new_widgets_build():
    widgets = [
        pz.image(rgba_png(4, 4), size=(4, 4), width=40, height=40, radius=4),
        pz.image_viewer(rgba_png(4, 4), size=(4, 4)),
        pz.canvas([draw.background("#000"), draw.text(1, 1, "hi")], width=20, height=20, id="c"),
        pz.rich_text([pz.span("bold", weight="bold"), " plain"]),
        pz.markdown("# Title"),
        pz.qr_code("hello"),
        pz.pick_list(["a", "b"], "a", lambda v: None),
        pz.radio("Option", True),
        pz.split(pz.text("a"), pz.text("b"), ratio=0.3),
        pz.pin(pz.text("x"), x=4, y=8),
        pz.grid([pz.text(str(i)) for i in range(4)], columns=2),
        pz.responsive(lambda w, h: pz.text(f"{w}x{h}")),
        pz.container(None, gradient=(90, ["#000", "#fff"])),
        pz.vertical_slider(0, 10, 5),
    ]
    assert all(isinstance(w, pz.Widget) for w in widgets)


def test_table_sorts_rows():
    rows = [{"n": "b", "v": 2}, {"n": "a", "v": 1}, {"n": "c", "v": None}]
    table = ui.table([ui.Column("Name", "n"), ui.Column("Value", "v")], rows, sort_by="Value")
    assert isinstance(table, pz.Widget)
    assert ui.Column("x", lambda r: r["v"] * 2).value(rows[0]) == 4


def test_new_widgets_render(tmp_path):
    class Demo(pz.App):
        size = (900, 600)

        def view(self):
            return pz.row([
                pz.column([
                    ui.select(["One", "Two"], "One", lambda v: None),
                    ui.radio_group(["a", "b"], "a", lambda v: None, horizontal=True),
                    ui.number_field(3, lambda v: None, min=0, max=5),
                    ui.callout("Hello", "World", tint="warning"),
                    pz.row([ui.chip("tag", on_remove=lambda: None), ui.count_badge(7), ui.diff_stat(3, 1),
                            ui.facepile(["AB", "CD", "EF"])]),
                    ui.disclosure("More", ui.label("content"), open=True),
                    ui.table(["n", "v"], [{"n": "a", "v": 1}], height=80),
                    ui.empty_state("Empty"),
                ], spacing=8, width=420),
                pz.column([
                    pz.image(rgba_png(16, 16), size=(16, 16), width=64, height=64),
                    pz.canvas([draw.circle(30, 30, 20, fill="#74ade8")], width=60, height=60),
                    ui.markdown("Some **markdown** and `code`."),
                    pz.qr_code("pyzed", cell_size=3),
                    pz.row([ui.sparkline([1, 3, 2, 4]), ui.donut([1, 2], size=48), ui.spinner()]),
                    ui.bar_chart([1, 2, 3], labels=["a", "b", "c"], width=200, height=80),
                    pz.container(ui.split(pz.text("left"), pz.text("right")), height=60),
                    ui.editor("wrapped", "word " * 80, wrap=True, height="shrink"),
                ], spacing=8, width="fill"),
            ], spacing=16, padding=16)

    out = tmp_path / "new.png"
    Demo().screenshot(out, scale=1)
    assert png_size(out) == (900, 600)


EXAMPLES = sorted(
    [p for p in (ROOT / "examples").glob("*.py") if p.stem not in ("screenshots",)]
    + list((ROOT / "examples" / "tutorial").glob("*.py"))
    + [ROOT / "examples" / "hot_reload" / "main.py"]
)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_examples_render(path, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(path.parent))
    monkeypatch.setenv("HOME", str(tmp_path))  # todos.py stores its list under ~/.config
    module = importlib.import_module(path.stem)
    try:
        apps = [v for v in vars(module).values()
                if isinstance(v, type) and issubclass(v, pz.App) and v.__module__ == path.stem]
        assert apps, f"{path.name} defines no App"
        app_class = apps[-1]
        if path.stem == "todos":
            app = app_class(store=tmp_path / "todos.json")
        else:
            app = app_class()
        out = tmp_path / f"{path.stem}.png"
        app.screenshot(out, scale=1)
        assert out.exists()
    finally:
        sys.modules.pop(path.stem, None)


def read_png(path):
    """Decodes an 8-bit RGBA PNG (what screenshots write) into rows of (r, g, b, a)."""
    import zlib

    data = Path(path).read_bytes()
    pos, idat, width, height = 8, b"", 0, 0
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", body[:10])
            assert (depth, color) == (8, 6)
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw, stride, rows, prev = zlib.decompress(idat), width * 4, [], bytearray(width * 4)
    for y in range(height):
        kind, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - 4] if i >= 4 else 0
            b = prev[i]
            c = prev[i - 4] if i >= 4 else 0
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append([tuple(line[x * 4:x * 4 + 4]) for x in range(width)])
        prev = line
    return rows


def test_image_cover_and_radius_stay_inside_their_box(tmp_path):
    red = bytes((255, 0, 0, 255)) * (200 * 100)

    class Demo(pz.App):
        size = (200, 100)

        def view(self):
            return pz.container(
                pz.row([
                    pz.image(red, size=(200, 100), width=50, height=50, content_fit="cover"),
                    pz.space(width=50),
                    pz.image(red, size=(200, 100), width=50, height=50, content_fit="cover", radius=25),
                ]),
                padding=25, width="fill", height="fill", bg="#0000ff",
            )

    out = tmp_path / "clip.png"
    Demo().screenshot(out, scale=1)
    px = read_png(out)
    assert px[50][50][:3] == (255, 0, 0)   # inside the first image
    assert px[50][90][:3] == (0, 0, 255)   # right of it: the 2x wide image must not spill
    assert px[50][150][:3] == (255, 0, 0)  # center of the round image
    assert px[26][126][:3] == (0, 0, 255)  # its top-left corner is cut off


def test_images_from_files_render_on_first_frame(tmp_path):
    source = tmp_path / "big.png"
    # A large PNG (over 2 MB of pixels) that wgpu would otherwise upload in the background.
    width, height = 1024, 600
    import zlib

    raw = b"".join(b"\x00" + bytes((0, 200, 0, 255)) * width for _ in range(height))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    source.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
                       + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

    class Demo(pz.App):
        size = (100, 100)

        def view(self):
            return pz.image(str(source), width="fill", height="fill", content_fit="cover")

    out = tmp_path / "file.png"
    Demo().screenshot(out, scale=1)
    assert read_png(out)[50][50][:3] == (0, 200, 0)
