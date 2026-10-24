"""The agent sees the form: screenshots that survive a failing renderer, a compiled designer and wrong colors."""

import os
import subprocess
import sys
import textwrap

import pytest

from pyzed import theme as _theme

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


def test_theme_colors_take_short_names_and_reject_unknown_ones():
    t = _theme.ONE_DARK
    assert t.color("muted") == t.text_muted == t.color("text.muted") == t.color("Text-Muted")
    assert t.color("primary") == t.accent and t.color("danger") == t.error
    assert t.color("red") == t.ansi["red"]
    assert t.color("#123456") == "#123456" and t.color("transparent") == "transparent"
    assert t.find_color("nope") is None and t.find_color("name") is None and t.find_color("radius") is None
    with pytest.raises(ValueError, match="unknown color 'nope'"):
        t.color("nope")


def test_a_control_that_cannot_draw_keeps_the_canvas_drawing():
    from pyzed.designer import components
    from pyzed.designer.model import Control

    bad = Control(name="title", type="label", x=0, y=0, width=120, height=30, props={"color": "nope"})
    ctx = components.RenderContext()
    assert components.render(bad, ctx) is not None  # the error in its place, not an exception
    ctx.live = True
    with pytest.raises(ValueError, match="unknown color"):
        components.render(bad, ctx)


def test_the_agent_is_told_about_wrong_colors():
    from pyzed.designer import agent_tools

    agent_tools._check_props("label", {"color": "muted"})
    agent_tools._check_props("label", {"color": "#ff0000"})
    with pytest.raises(ValueError, match="is not a color"):
        agent_tools._check_props("label", {"color": "grayish"})


def test_screenshots_fall_back_to_a_window_when_the_renderer_fails(monkeypatch):
    from pyzed.designer import agent_tools
    from pyzed.designer.app import Designer
    from pyzed.mcp import preview

    calls = []

    def render(script, *, window=False, **kwargs):
        calls.append(window)
        if not window:
            raise RuntimeError("thread '<unnamed>' panicked at wgpu: no adapter")
        return PNG

    monkeypatch.setattr(preview, "render", render)
    d = Designer()
    assert agent_tools.screenshot_job(d)() == PNG and calls == [False, True]

    def broken(script, *, window=False, **kwargs):  # the form's own error: no window
        calls.append(window)
        raise RuntimeError("Traceback (most recent call last):\n  ...\nNameError: name 'x' is not defined")

    calls.clear()
    monkeypatch.setattr(preview, "render", broken)
    with pytest.raises(RuntimeError, match="NameError"):
        agent_tools.screenshot_job(d)()
    assert calls == [False]


def test_a_compiled_designer_runs_modules_instead_of_opening_again(tmp_path, monkeypatch):
    from pyzed import _frozen

    module = tmp_path / "helper_mod.py"
    module.write_text("import sys\nprint('args', sys.argv[1:])\nsys.exit(int(sys.argv[1]))\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    assert _frozen.wants_module(["-m", "helper_mod", "3"]) and not _frozen.wants_module(["form.pzform"])
    assert _frozen.run_module(["helper_mod", "3"]) == 3
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    from pyzed.mcp import preview

    assert preview.this_python()[0] == [sys.executable]


def test_preview_reports_errors_in_a_file_too(tmp_path):
    from pyzed.mcp import preview

    with pytest.raises(RuntimeError, match="boom"):
        preview.render("raise RuntimeError('boom')")
    out = tmp_path / "shot.png"
    script = tmp_path / "app.py"
    script.write_text("raise RuntimeError('boom')\n")
    python, env = preview.this_python()
    done = subprocess.run([*python, "-m", "pyzed.mcp.preview", str(script), str(out)], capture_output=True,
                          env=env, timeout=60)
    assert done.returncode != 0 and "boom" in (tmp_path / "shot.png.log").read_text()


def test_ctrl_v_attaches_a_copied_image(tmp_path):
    from pyzed import agents
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    d = Designer()
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path))
    assert repr(c.on_paste_key()) == "Command.paste(...)"
    assert c._after_paste("some text") is None  # the box pasted the text: no image
    assert repr(c._after_paste("")) == "Command.paste_image(...)"
    c._paste_key_image(None)
    assert c.attachments == []
    c._paste_key_image(PNG)
    assert [a.data for a in c.attachments] == [PNG]


@pytest.mark.skipif(not (sys.platform in ("win32", "darwin") or os.environ.get("DISPLAY")
                         or os.environ.get("WAYLAND_DISPLAY")), reason="needs a display")
def test_a_window_is_captured(tmp_path):
    from pyzed.mcp import preview

    code = textwrap.dedent("""
        import pyzed as pz

        class A(pz.App):
            title = "capture"
            window_size = (200, 120)

            def view(self):
                return pz.container(pz.text("hi"), bg="#ff0000", width="fill", height="fill")

        pz.run(A)
    """)
    try:
        png = preview.render(code, window=True, timeout=60)
    except RuntimeError as err:  # a display without a GPU driver (CI): nothing to capture there
        pytest.skip(f"no window could be drawn here: {str(err)[-300:]}")
    assert png.startswith(b"\x89PNG")
