"""``pyzed.recording`` and ``pyzed record``: stills, clips, formats, job files and batches."""

import json
import shutil
from pathlib import Path

import pytest

import pyzed as pz
from pyzed import _core, recording as rec, ui
from pyzed.recording import batch
from pyzed.recording.cli import standalone

PIL = pytest.importorskip("PIL")


class Counter(pz.App):
    theme = "Pyzed Dark"

    def __init__(self):
        self.count = 0

    def view(self):
        return pz.column([pz.text(str(self.count), size=24),
                          ui.button("Add", self.add, variant="solid")], spacing=12, padding=20)

    def add(self):
        self.count += 1


COUNTER = '''import pyzed as pz
from pyzed import ui


class Counter(pz.App):
    def __init__(self):
        self.count = 0

    def view(self):
        return pz.column([pz.text(str(self.count), size=24), ui.button("Add", self.add)], spacing=12, padding=20)

    def add(self):
        self.count += 1
'''


def test_screenshot_rgba_matches_the_png_screenshot(tmp_path):
    w, h, rgba, renderer, shader = _core.screenshot_rgba(Counter(), size=(200, 120), scale=1.0, wait=0.0)
    assert (w, h) == (200, 120) and len(rgba) == 200 * 120 * 4
    assert renderer in ("wgpu", "tiny-skia") and shader is False
    pz.screenshot(Counter(), tmp_path / "shot.png", size=(200, 120), scale=1.0, wait=0.0)
    from PIL import Image

    with Image.open(tmp_path / "shot.png") as im:
        assert im.convert("RGBA").tobytes() == rgba


def test_renderer_choice():
    assert rec.pick_renderer("cpu") == "cpu"
    assert rec.pick_renderer("gpu") == "gpu"
    assert rec.pick_renderer("auto") in ("cpu", "gpu")
    with pytest.raises(ValueError):
        _core.screenshot_rgba(Counter(), size=(100, 100), renderer="quantum")


def test_a_clip_presses_the_button_and_films_the_change():
    app = Counter()
    take = rec.record(app, [rec.press("Add"), rec.wait(200)], size=(240, 140), scale=1, fps=10)
    assert app.count == 1
    frames = take.images()
    assert len(frames) == len(take.frames) and frames[0].size == (240, 140)
    assert rec.changes(take.images(pointer=False)) > 1
    assert take.duration == pytest.approx(len(frames) / 10)


def test_parse_steps_takes_only_steps_and_plain_values():
    steps = rec.parse_steps("hover('Save'); press()\nwait(300)\n  type_text('hi', cps=20)")
    assert [s.label.split("(")[0] for s in steps] == ["hover", "press", "wait", "type_text"]
    with pytest.raises(ValueError):
        rec.parse_steps("import os")
    with pytest.raises(ValueError):
        rec.parse_steps("__import__('os').system('true')")
    with pytest.raises(ValueError):
        rec.parse_steps("wait(open('x'))")


def test_text_targets_count_in_reading_order():
    app = Counter()
    ctx = rec.Context(app=app, size=(200, 100), scale=1, fps=10)
    found = [("text", "1", 120, 50, 10, 10), ("text", "1", 20, 50, 10, 10), ("text", "1", 70, 10, 10, 10)]
    ctx._probe = found
    ctx.frames.append(rec.Frame(b"", None, False))

    def resolve(target):
        gen = ctx.resolve(target)
        try:
            while True:
                next(gen)
        except StopIteration as stop:
            return stop.value

    assert resolve("1") == (75, 15)
    assert resolve("1#1") == (25, 55)
    assert resolve("1#2") == (125, 55)
    with pytest.raises(LookupError):
        resolve("1#3")


@pytest.mark.parametrize("fmt", ["webp", "gif", "apng", "png"])
def test_encode_writes_every_format(tmp_path, fmt):
    from PIL import Image

    frames = [Image.new("RGB", (40, 30), c) for c in ("red", "red", "blue", "green")]
    info = rec.encode(frames, tmp_path / f"clip.{fmt}", fmt, fps=10)
    assert (tmp_path / f"clip.{fmt}").stat().st_size == info["bytes"] > 0
    if fmt != "png":
        assert info["frames"] == 3  # the repeated red frame is merged
        with Image.open(tmp_path / f"clip.{fmt}") as im:
            assert getattr(im, "n_frames", 1) == 3


def test_merge_keeps_the_total_duration():
    from PIL import Image

    a, b = Image.new("RGB", (4, 4), "red"), Image.new("RGB", (4, 4), "blue")
    images, times = rec.merge([a, a, a, b, b, a], 30)
    assert len(images) == 3 and sum(times) == 200


def test_fit_quality_finds_the_best_quality_that_fits():
    sizes = {q: q * 10 for q in range(0, 101)}
    data, q = rec.fit_quality(lambda q: b"x" * sizes[q], 555, low=40, high=90)
    assert q == 55 and len(data) == 550
    data, q = rec.fit_quality(lambda q: b"x" * sizes[q], 10, low=40, high=90)
    assert q == 40  # nothing fits: the lowest quality


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_video_formats_go_through_ffmpeg(tmp_path):
    from PIL import Image

    frames = [Image.new("RGB", (41, 31), (i * 20, 0, 0)) for i in range(6)]  # odd sizes are cropped to even
    for fmt in ("mp4", "webm"):
        info = rec.encode(frames, tmp_path / f"clip.{fmt}", fmt, fps=12)
        assert info["bytes"] > 0


def test_expand_records_every_combination_and_names_the_files(tmp_path):
    job = batch.Job.from_dict({"name": "card", "target": "code:ui.button('A', None)",
                               "theme": ["Pyzed Dark", "Pyzed Light"], "scale": [1, 2], "size": "200x100",
                               "formats": "webp, png"})
    tasks = batch.expand(job, tmp_path)
    assert len(tasks) == 4
    names = sorted(Path(p).name for t in tasks for p in t.outputs.values())
    assert names[:2] == ["card.pyzed-dark.1x.png", "card.pyzed-dark.1x.webp"]
    assert {t.size for t in tasks} == {(200.0, 100.0)}
    one = batch.expand(batch.Job("card", "code:x", size=[320, 200]), tmp_path)
    assert len(one) == 1 and one[0].size == (320.0, 200.0)
    assert Path(one[0].outputs["webp"]).name == "card.webp"


def test_job_files_reject_unknown_settings_and_formats(tmp_path):
    with pytest.raises(ValueError, match="unknown setting"):
        batch.Job.from_dict({"name": "a", "target": "code:x", "colour": "red"})
    with pytest.raises(ValueError, match="unknown format"):
        batch.Job.from_dict({"name": "a", "target": "code:x", "formats": ["bmp"]})
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps({"job": [{"name": "a", "target": "code:x"}, {"name": "a", "target": "code:y"}]}))
    with pytest.raises(ValueError, match="share a name"):
        batch.load_jobs(path)


def test_job_files_round_trip(tmp_path):
    jobs = [batch.Job("a", "app.py:Main", steps="hover('Save')\npress()", theme=["Pyzed Dark", "One Dark"],
                      size="480x270", formats=["webp", "gif"], crop="content", poster=True)]
    for name in ("jobs.toml", "jobs.json"):
        path = tmp_path / name
        batch.save_jobs(path, jobs, {"out_dir": "media"})
        if name.endswith(".toml"):
            pytest.importorskip("tomllib")
        loaded, settings = batch.load_jobs(path)
        assert loaded == jobs and settings == {"out_dir": "media"}


def test_targets_load_files_modules_and_snippets(tmp_path):
    (tmp_path / "counter_app.py").write_text(COUNTER)
    app = rec.as_app(rec.load("counter_app.py", tmp_path)())
    assert type(app).__name__ == "Counter"
    named = rec.load(f"{tmp_path / 'counter_app.py'}:Counter")()
    assert named.__name__ == "Counter"
    snippet = rec.as_app(rec.load("code:ui.button('Hi', None)")(), "Pyzed Light")
    assert isinstance(snippet, pz.App) and snippet.theme.name == "Pyzed Light"
    with pytest.raises(FileNotFoundError):
        rec.load("missing.py", tmp_path)


def test_a_batch_records_in_parallel_and_skips_what_did_not_change(tmp_path):
    (tmp_path / "counter_app.py").write_text(COUNTER)
    jobs = [batch.Job("counter", "counter_app.py", steps="press('Add'); wait(100)", size="200x120", scale=1,
                      fps=10, formats=["webp", "png"], theme=["Pyzed Dark", "Pyzed Light"], crop="content"),
            batch.Job("still", "counter_app.py", size="200x120", scale=1, formats=["png"])]
    tasks = list(batch.iter_tasks(jobs, tmp_path / "out", tmp_path))
    cache = tmp_path / "out" / batch.CACHE
    seen = []
    results = batch.run(tasks, jobs=2, cache=cache, progress=seen.append)
    assert len(results) == len(seen) == 3
    assert not [r for r in results if r.get("error")], results
    files = sorted(p.name for p in (tmp_path / "out").glob("*.*") if p.name != batch.CACHE)
    assert files == ["counter.pyzed-dark.png", "counter.pyzed-dark.webp", "counter.pyzed-light.png",
                     "counter.pyzed-light.webp", "still.png"]
    again = batch.run(tasks, jobs=1, cache=cache)
    assert all(r.get("skipped") for r in again)
    (tmp_path / "counter_app.py").write_text(COUNTER.replace("size=24", "size=26"))
    changed = batch.run(tasks, jobs=1, cache=cache)
    assert not any(r.get("skipped") for r in changed)


def test_a_failing_job_is_reported_and_the_batch_goes_on(tmp_path):
    jobs = [batch.Job("bad", "code:ui.button('A', None)", steps="press('Nope')", size="120x80", scale=1),
            batch.Job("good", "code:ui.button('A', None)", size="120x80", scale=1, formats=["png"])]
    results = {r["name"]: r for r in batch.run(list(batch.iter_tasks(jobs, tmp_path, tmp_path)), jobs=1)}
    assert "LookupError" in results["bad"]["error"]
    assert not results["good"].get("error") and Path(results["good"]["files"][0]["path"]).exists()


def test_the_command_line(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "counter_app.py").write_text(COUNTER)
    assert standalone(["shot", "counter_app.py", "-o", "shot.png", "--size", "200x120", "--scale", "1",
                       "--jobs", "1"]) == 0
    assert (tmp_path / "shot.png").exists()
    assert standalone(["clip", "counter_app.py", "--steps", "press('Add')", "-f", "webp,gif", "--size", "200x120",
                       "--scale", "1", "--fps", "10", "--theme", "Pyzed Dark,Pyzed Light", "--jobs", "1"]) == 0
    assert {p.name for p in tmp_path.glob("counter_app.*.*")} == {
        "counter_app.pyzed-dark.webp", "counter_app.pyzed-dark.gif", "counter_app.pyzed-light.webp",
        "counter_app.pyzed-light.gif"}
    (tmp_path / "jobs.json").write_text(json.dumps({"out_dir": "out", "job": [
        {"name": "c", "target": "counter_app.py", "size": "200x120", "scale": 1, "formats": ["png"]}]}))
    capsys.readouterr()
    assert standalone(["batch", "jobs.json", "--json", "--jobs", "1"]) == 0
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["name"] == "c" and line["total"] == 1 and (tmp_path / "out" / "c.png").exists()
    assert standalone(["batch", "jobs.json", "--dry-run"]) == 0
    assert "1 recordings" in capsys.readouterr().out


def test_the_window_builds_and_previews_jobs(tmp_path):
    from pyzed.recording.gui import RecorderApp

    app = RecorderApp(str(tmp_path / "jobs.toml"))
    app.add_job()
    assert len(app.jobs) == 2 and app.selected == 1 and app.dirty
    app.toggle_theme("Pyzed Light")
    app.toggle_theme("One Dark")
    assert app.job.theme == ["Pyzed Light", "One Dark"]
    app.set_matrix("scale", "1, 2")
    assert app.job.scale == [1.0, 2.0]
    app.toggle_format("gif")
    assert app.job.formats == ["webp", "gif"]
    pz.screenshot(app, tmp_path / "gui.png", size=(1240, 780), scale=1, wait=0.0)
    app.save(str(tmp_path / "jobs.json"))
    loaded, _ = batch.load_jobs(tmp_path / "jobs.json")
    assert loaded == app.jobs
