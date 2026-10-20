"""The off-screen recorder (``pyzed._core.record``) that docs/scripts/anim_webp.py films clips with."""

import pyzed as pz
from pyzed import _core, ui


class Form(pz.App):
    theme = "One Dark"

    def __init__(self):
        self.text = ""
        self.on = False
        self.clicks = 0

    def view(self):
        return pz.column([
            ui.button("Save", self.save, variant="solid"),
            ui.switch(self.on, lambda v: setattr(self, "on", v), label="Wi-Fi"),
            ui.input(self.text, lambda v: setattr(self, "text", v), placeholder="Name"),
        ], spacing=12, padding=20)

    def save(self):
        self.clicks += 1


def run(app, commands, size=(300, 200)):
    """Plays ``commands`` and returns what each one answered."""
    answers = []

    def script():
        for command in commands:
            answers.append((yield command))

    _core.record(app, script(), size=size, scale=1.0)
    return answers


def test_snap_returns_rgba_frames_of_the_requested_size():
    size, frame = run(Form(), [("size",), ("snap",)])
    assert size == (300, 200)
    assert len(frame) == 300 * 200 * 4


def test_hover_changes_the_frame_and_a_click_reaches_the_app():
    app = Form()
    probe, *_ = run(app, [("probe",), ("snap",)])
    x, y, w, h = next(p[2:] for p in probe if p[0] == "text" and p[1] == "Save")
    still, hovered = [a for a in run(app, [("snap",), ("move", x + w / 2, y + h / 2), ("snap",)]) if a]
    assert still != hovered
    run(app, [("move", x + w / 2, y + h / 2), ("down", "left"), ("up", "left")])
    assert app.clicks == 1


def test_typing_and_toggling_update_the_state():
    app = Form()
    probe = run(app, [("probe",)])[0]
    x, y, _, h = next(p[2:] for p in probe if p[0] == "input")
    run(app, [("move", x + 10, y + h / 2), ("down",), ("up",), ("type", "Ada"), ("key", "Backspace"), ("type", "!")])
    assert app.text == "Ad!"
    run(app, [("move", 40, 70), ("down",), ("up",)])
    assert app.on is True


def test_the_clock_advances_only_when_told():
    frames = run(Form(), [("snap",), ("snap",), ("advance", 0.25), ("snap",)])
    assert frames[0] == frames[1]


def test_unknown_commands_raise():
    try:
        run(Form(), [("fly",)])
    except ValueError as err:
        assert "fly" in str(err)
    else:
        raise AssertionError("expected a ValueError")
