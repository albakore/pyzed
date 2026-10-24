"""``pyzed record gui``: a window to build recording jobs, preview them and run the batch.

The jobs on the left, the selected job's settings in the middle, and the preview and the queue on
the right. Recordings run in other processes (``pyzed record batch --json``): the window keeps
responding, a batch can be stopped, and a crash in a recording never takes the window down.
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import pyzed as pz
from pyzed import ui
from pyzed.ui.inputs import browse_path

from .batch import Job, expand, load_jobs, save_jobs
from .encode import FORMATS
from .steps import STEPS, parse_steps
from .targets import _resolve, _split

__all__ = ["RecorderApp", "main"]

CROPS = ["none", "content"]
RENDERERS = ["auto", "gpu", "cpu"]
FILTERS = [("Job files", ["toml", "json"])]


def _sizes(text: str) -> Any:
    """``"480x270, 800x600"`` as a job's ``size`` (one value or a list)."""
    items = [s.strip() for s in text.split(",") if s.strip()]
    if not items:
        return None
    return items if len(items) > 1 else items[0]


def _numbers(text: str) -> Any:
    items = [float(s) for s in text.replace(";", ",").split(",") if s.strip()]
    if not items:
        return None
    return items if len(items) > 1 else items[0]


def _text(value: Any) -> str:
    """A matrix setting as the text its field shows."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)) and value and all(isinstance(v, (int, float)) for v in value) and \
            len(value) == 2 and not isinstance(value[0], bool) and value[0] > 10:
        return f"{value[0]:g}x{value[1]:g}"  # one [w, h]
    if isinstance(value, (list, tuple)):
        return ", ".join(_text(v) for v in value)
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _detect_gpu() -> str:
    """The GPU and renderer recordings use, asked in another process: probing the GPU here would load a
    driver into the window's process."""
    code = ("from pyzed.recording import session as s; g = s.gpu(); "
            "print((f'{g[0]} ({g[1]})' if g else 'no GPU') + ' · ' + s.pick_renderer() + ' renderer')")
    try:
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


class RecorderApp(pz.App):
    title = "Pyzed Recorder"
    size = (1240, 780)
    min_size = (900, 560)

    def __init__(self, path: Optional[str] = None):
        self.path = path
        self.jobs: List[Job] = []
        self.settings: Dict[str, Any] = {"out_dir": "media"}
        self.selected = 0
        self.workers = 0
        self.force = False
        self.dirty = False
        self.error: Optional[str] = None
        self.running: Optional[subprocess.Popen] = None
        self.results: Dict[str, Dict[str, Any]] = {}
        self.total = 0
        self.done = 0
        self.preview: Optional[str] = None
        self.previewing = False
        self.gpu = ""
        if path and Path(path).exists():
            self.jobs, self.settings = load_jobs(path)
        if not self.jobs:
            self.jobs = [Job("my-clip", "code:ui.button('Save', None, variant='solid')",
                             steps="hover('Save'); press(); wait(600)", size="360x160", crop="content")]

    # -- state -------------------------------------------------------------------------------------
    @property
    def job(self) -> Job:
        return self.jobs[self.selected]

    @property
    def base(self) -> Path:
        return Path(self.path).resolve().parent if self.path else Path.cwd()

    def on_start(self) -> Any:
        return pz.Command.perform(_detect_gpu, self.got_gpu)

    def got_gpu(self, text: str) -> None:
        self.gpu = text

    def set(self, name: str, value: Any) -> None:
        self.jobs[self.selected] = dataclasses.replace(self.job, **{name: value})
        self.dirty = True
        self.error = None

    def set_matrix(self, name: str, text: str) -> None:
        try:
            value = _sizes(text) if name in ("size", "theme") else _numbers(text)
        except ValueError:
            self.error = f"{name}: numbers separated by commas"
            return
        self.set(name, value)

    def toggle_theme(self, name: str) -> None:
        themes = self.job.theme
        themes = [] if themes is None else ([themes] if isinstance(themes, str) else list(themes))
        themes = [t for t in themes if t != name] if name in themes else themes + [name]
        self.set("theme", None if not themes else themes if len(themes) > 1 else themes[0])

    def toggle_format(self, fmt: str) -> None:
        formats = [f for f in self.job.formats if f != fmt] if fmt in self.job.formats else self.job.formats + [fmt]
        self.set("formats", formats or ["webp"])

    def add_job(self) -> None:
        names = {j.name for j in self.jobs}
        n = len(self.jobs) + 1
        while f"job-{n}" in names:
            n += 1
        self.jobs.append(dataclasses.replace(self.job, name=f"job-{n}"))
        self.selected = len(self.jobs) - 1
        self.dirty = True

    def remove_job(self) -> None:
        if len(self.jobs) > 1:
            del self.jobs[self.selected]
            self.selected = min(self.selected, len(self.jobs) - 1)
            self.dirty = True

    def save(self, path: Optional[str] = None) -> Any:
        self.path = path or self.path
        if not self.path:
            return browse_path(self.save, save=True, file_name="jobs.toml", filters=FILTERS)
        save_jobs(self.path, self.jobs, self.settings)
        self.dirty = False
        return None

    def open(self, path: Optional[str] = None) -> Any:
        if not path:
            return browse_path(self.open, filters=FILTERS)
        try:
            self.jobs, self.settings = load_jobs(path)
        except Exception as err:  # a broken file: say why, keep what is open
            self.error = f"{Path(path).name}: {err}"
            return None
        self.path, self.selected, self.dirty, self.results = path, 0, False, {}
        return None

    def problems(self, job: Job) -> Optional[str]:
        """What is wrong with ``job``'s settings, or ``None``."""
        if job.steps.strip():
            try:
                parse_steps(job.steps)
            except (ValueError, SyntaxError) as err:
                return f"steps: {err}"
        return None

    # -- running -----------------------------------------------------------------------------------
    def _job_file(self, jobs: List[Job], folder: str) -> str:
        path = os.path.join(folder, "jobs.json")
        settings = dict(self.settings)
        settings["out_dir"] = str((self.base / settings.get("out_dir", ".")).resolve())
        save_jobs(path, [dataclasses.replace(j, target=self._absolute(j.target)) for j in jobs], settings)
        return path

    def _absolute(self, target: str) -> str:
        """``target`` with its file made absolute (the batch runs from a temporary folder)."""
        if target.startswith("code:"):
            return target
        path, attr = _split(target)
        p = _resolve(path, self.base)
        if not p.exists():  # a module name
            return target
        return str(p.resolve()) + (f":{attr}" if attr else "")

    def run_all(self) -> None:
        if self.running:
            return
        bad = next((f"{j.name}: {p}" for j in self.jobs if (p := self.problems(j))), None)
        if bad:
            self.error = bad
            return
        folder = tempfile.mkdtemp(prefix="pyzed-recorder-")
        args = ["batch", self._job_file(self.jobs, folder), "--json"]
        if self.workers:
            args += ["--jobs", str(self.workers)]
        if self.force:
            args.append("--force")
        self.results, self.done, self.error = {}, 0, None
        self.total = sum(len(expand(j)) for j in self.jobs)
        self._spawn(args, "result")

    def preview_job(self) -> None:
        """Records the selected job once (its first theme, size and scale) as a PNG and shows it."""
        if self.previewing:
            return
        job = self.job
        problem = self.problems(job)
        if problem:
            self.error = problem
            return
        first = expand(job)[0]
        folder = tempfile.mkdtemp(prefix="pyzed-preview-")
        still = dataclasses.replace(job, theme=first.theme, size=list(first.size) if first.size else None,
                                    scale=first.scale, fps=first.fps, formats=["png"], max_bytes=0, poster=False,
                                    out="preview.png", target=self._absolute(job.target))
        path = os.path.join(folder, "jobs.json")
        save_jobs(path, [still], {"out_dir": folder})
        self.previewing, self.error = True, None
        self._spawn(["batch", path, "--json", "--force", "--jobs", "1"], "preview")

    def _spawn(self, args: List[str], kind: str) -> None:
        cmd = [sys.executable, "-m", "pyzed.recording", *args]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(self.base))
        if kind == "result":
            self.running = proc

        def read() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                try:
                    pz.post((kind, json.loads(line)))
                except ValueError:
                    pass
            err = proc.stderr.read() if proc.stderr else ""
            proc.wait()
            pz.post((kind + "-end", proc.returncode, err.strip().splitlines()[-1:] if err.strip() else []))

        threading.Thread(target=read, daemon=True).start()

    def stop(self) -> None:
        if self.running:
            self.running.terminate()

    def update(self, message: Any) -> None:
        kind = message[0]
        if kind == "result":
            data = message[1]
            self.results[data["label"]] = data
            self.done = len(self.results)
        elif kind == "result-end":
            self.running = None
            if message[1] not in (0, 1) and message[2]:
                self.error = message[2][0]
        elif kind == "preview":
            data = message[1]
            if data.get("error"):
                self.error = data["error"]
            elif data.get("files"):
                self.preview = data["files"][0]["path"]
        elif kind == "preview-end":
            self.previewing = False
            if message[1] not in (0, 1) and message[2]:
                self.error = message[2][0]

    # -- view --------------------------------------------------------------------------------------
    def job_list(self) -> Any:
        rows = []
        for i, job in enumerate(self.jobs):
            count = len(expand(job))
            rows.append(ui.list_item(job.name, (lambda i=i: setattr(self, "selected", i)), icon="clapperboard",
                                     selected=i == self.selected, end=ui.muted(f"{count}×", size="sm")))
        header = ui.panel_header("Jobs", [ui.icon_button("plus", self.add_job, tooltip="New job (a copy of this one)"),
                                          ui.icon_button("trash-2", self.remove_job, tooltip="Delete job")])
        return pz.column([header, pz.scrollable(pz.column(rows, spacing=1, padding=4), height="fill")],
                         width=220, height="fill")

    def form(self) -> Any:
        job = self.job
        themes = [job.theme] if isinstance(job.theme, str) else list(job.theme or [])
        theme_chips = pz.row([ui.chip(name, on_press=(lambda n=name: self.toggle_theme(n)), selected=name in themes)
                              for name in pz.themes.names()], spacing=4, wrap=True, line_spacing=4)
        format_chips = pz.row([ui.chip(f, on_press=(lambda f=f: self.toggle_format(f)), selected=f in job.formats)
                               for f in FORMATS], spacing=4, wrap=True)
        what = ui.settings_group("What", [
            ui.field("Name", ui.input(job.name, lambda v: self.set("name", v), width=260)),
            ui.field("Target", ui.input(job.target, lambda v: self.set("target", v), width=360),
                     description="app.py:App, module:App, a .pzform, or code:<snippet>"),
            ui.field("Steps", pz.container(ui.editor(f"steps-{self.selected}", job.steps, language="python",
                                                     on_change=lambda v: self.set("steps", v), gutter=False,
                                                     height=96), width="fill", height=96),
                     description="one per line: " + ", ".join(sorted(STEPS)) + " · none and no duration: a still",
                     vertical=True),
            ui.field("Duration", ui.number_field(job.duration, lambda v: self.set("duration", v), min=0, step=100,
                                                 suffix="ms")),
        ])
        how = ui.settings_group("Every combination of", [
            ui.field("Themes", theme_chips, vertical=True),
            ui.field("Sizes", ui.input(_text(job.size), lambda v: self.set_matrix("size", v), width=260,
                                       placeholder="480x270, 800x600 (empty: the app's)")),
            ui.field("Scales", ui.input(_text(job.scale), lambda v: self.set_matrix("scale", v), width=160)),
            ui.field("FPS", ui.input(_text(job.fps), lambda v: self.set_matrix("fps", v), width=160)),
        ])
        output = ui.settings_group("Output", [
            ui.field("Formats", format_chips, description="MP4 and WebM need ffmpeg"),
            ui.field("File name", ui.input(job.out, lambda v: self.set("out", v), width=260),
                     description="{name} {variant} {theme} {size} {scale} {fps} {ext}"),
            ui.field("Crop", ui.select(CROPS, job.crop if isinstance(job.crop, str) else "none",
                                       lambda v: self.set("crop", None if v == "none" else v), width=160)),
            ui.field("Pointer", ui.switch(job.pointer, lambda v: self.set("pointer", v))),
            ui.field("Quality", ui.number_field(job.quality, lambda v: self.set("quality", int(v)), min=1, max=100)),
            ui.field("Max size", ui.number_field(job.max_bytes / 1000, lambda v: self.set("max_bytes", int(v * 1000)),
                                                 min=0, step=50, suffix="KB"), description="0: no limit"),
            ui.field("Max width", ui.number_field(job.max_width, lambda v: self.set("max_width", int(v)), min=0,
                                                  step=80, suffix="px"), description="0: as recorded"),
            ui.field("Poster", ui.switch(job.poster, lambda v: self.set("poster", v)),
                     description="also a still .webp of the first frame"),
            ui.field("Renderer", ui.select(RENDERERS, job.renderer, lambda v: self.set("renderer", v), width=160),
                     description="auto: the GPU (a software one too) · cpu: faster drafts"),
        ])
        body = pz.column([what, how, output], spacing=16, padding=16, width="fill")
        return pz.scrollable(body, height="fill", width="fill")

    def side(self) -> Any:
        t = self.resolved_theme()
        if self.preview and Path(self.preview).exists():
            shown = pz.image(self.preview, width="fill", height=240, content_fit="contain", background=False)
        else:
            shown = ui.empty_state("No preview", "Record the selected job once, or pick a recording in the queue.",
                                   icon="image", height=240)
        preview = pz.column([
            ui.panel_header("Preview", [ui.icon_button("loader" if self.previewing else "eye", self.preview_job,
                                                       tooltip="Preview the selected job")]),
            pz.container(shown, padding=8, width="fill", bg=t.editor),
        ])
        rows = []
        for task in (t_ for job in self.jobs for t_ in expand(job)):
            result = self.results.get(task.label)
            if result is None:
                end = ui.spinner(size=12) if self.running else ui.muted("waiting", size="sm")
                icon, color = "circle-dashed", t.icon_muted
            elif result.get("error"):
                end, icon, color = ui.badge("failed", tint="error", size="sm"), "circle-x", t.error
            elif result.get("skipped"):
                end, icon, color = ui.muted("up to date", size="sm"), "circle-check", t.icon_muted
            else:
                kb = sum(f.get("bytes", 0) for f in result["files"]) / 1000
                end = ui.muted(f"{result['seconds']:.1f}s · {kb:.0f} KB", size="sm")
                icon, color = "circle-check", t.success
            shown = next((f["path"] for f in (result or {}).get("files", [])
                          if f.get("format") in ("png", "webp", "gif", "poster")), None)
            rows.append(ui.list_item(task.label, (lambda p=shown: setattr(self, "preview", p)) if shown else None,
                                     icon=icon, icon_color=color, end=end, selected=bool(shown) and shown == self.preview))
        queue = pz.column([
            ui.panel_header(f"Queue · {self.done}/{self.total}" if self.total else "Queue", []),
            ui.progress(self.done / self.total if self.total else 0) if self.running or self.done else None,
            pz.scrollable(pz.column(rows, spacing=1, padding=4), height="fill"),
        ], height="fill")
        return pz.column([preview, queue], width=400, height="fill")

    def view(self) -> Any:
        t = self.resolved_theme()
        name = Path(self.path).name if self.path else "untitled"
        bar = ui.toolbar(
            [ui.button("Open", self.open, icon="folder-open", variant="ghost", size="sm"),
             ui.button("Save", self.save, icon="save", variant="ghost", size="sm"),
             ui.muted(name + (" •" if self.dirty else ""), size="sm")],
            [ui.muted("Processes (0: one per core)", size="sm"),
             ui.number_field(self.workers, lambda v: setattr(self, "workers", int(v)), min=0, max=64, width=80),
             ui.checkbox(self.force, lambda v: setattr(self, "force", v), label="Record all again"),
             ui.button("Stop", self.stop, icon="square", variant="outline", size="sm") if self.running else
             ui.button("Record all", self.run_all, icon="play", variant="solid", size="sm")],
            height=44,
        )
        status = ui.status_bar(
            [ui.status_item(self.gpu or "detecting the GPU…", icon="cpu")],
            [ui.status_item(f"{sum(len(expand(j)) for j in self.jobs)} recordings", icon="film")],
        )
        message = ui.callout(self.error, tint="error", on_dismiss=lambda: setattr(self, "error", None)) \
            if self.error else None
        middle = pz.column([message, self.form()], height="fill", width="fill")
        body = pz.row([self.job_list(), pz.rule(vertical=True), middle, pz.rule(vertical=True), self.side()],
                      height="fill")
        return pz.container(pz.column([bar, pz.rule(), body, status]), width="fill", height="fill", bg=t.panel)


def main(path: Optional[str] = None) -> int:
    pz.run(RecorderApp(path))
    return 0
