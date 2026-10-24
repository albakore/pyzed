"""Many recordings at once: jobs with lists of parameters, run in parallel, skipping what didn't change.

A job file is TOML (or JSON with the same shape). Settings in ``[defaults]`` apply to every job;
a job's own settings win. ``theme``, ``size``, ``scale`` and ``fps`` may be lists: the job is
recorded once for every combination (2 themes x 2 scales = 4 recordings). ``formats`` is a list
too, but one recording is encoded to all of them::

    out_dir = "media"                  # relative to this file
    jobs = 4                           # processes (default: one per CPU core)

    [defaults]
    size = [480, 270]
    fps = 20
    formats = ["webp", "png"]
    theme = ["Pyzed Dark", "Pyzed Light"]

    [[job]]
    name = "save-button"
    target = "code:ui.button('Save', None, variant='solid')"
    steps = "hover('Save'); press(); wait(600)"
    crop = "content"

    [[job]]
    name = "counter"
    target = "examples/counter.py:Counter"
    steps = "press('+'); press('+'); wait(400)"
    scale = [1, 2]
    max_bytes = 200_000                # lower the quality until each file fits

Every setting (``Job``'s fields): ``name``, ``target`` (see ``pyzed.recording.targets``), ``steps``
(``hover("Save"); press()``; none and no ``duration``: a still), ``duration`` (ms to film when
there are no steps), ``size`` (``[w, h]`` or ``"WxH"`` in logical pixels; none: the app's window size), ``scale``, ``fps``, ``theme``,
``formats`` (webp, png, gif, apng, mp4, webm), ``out`` (the file name, see below), ``crop``
(``"content"``: what is drawn plus ``margin`` pixels, or ``[x, y, w, h]``), ``margin``, ``pointer``,
``quality`` (0-100), ``max_bytes``, ``max_width`` (scale down wider clips), ``poster`` (also write a
still ``.still.webp`` of the first frame), ``wait`` (seconds a still lets the app start),
``renderer`` (auto, gpu, cpu) and ``method`` (WebP effort 0-6: 4 is ten times faster than 6 for a
file about 2 % bigger).

``out`` names each file: ``{name}``, ``{variant}`` (``.pyzed-light.2x``: one part for every list
that has more than one value), ``{theme}`` (slug), ``{size}``, ``{scale}``, ``{fps}`` and ``{ext}``.
The default is ``{name}{variant}.{ext}``.

The cache (``.pyzed-record-cache.json`` in ``out_dir``) remembers what made each file: a job whose
settings and target file are unchanged since its files were written is skipped (``force`` records
it anyway). It can't see changes in modules the target imports: pass ``force`` then.
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import hashlib
import itertools
import json
import multiprocessing
import os
import re
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple, Union

from .encode import FORMATS, VIDEO, encode, save_poster

__all__ = ["CACHE", "Job", "Task", "expand", "iter_tasks", "load_jobs", "parse_size", "run", "run_task", "save_jobs"]

CACHE = ".pyzed-record-cache.json"
#: The settings a job may give as a list to record every combination.
MATRIX = ("theme", "size", "scale", "fps")


@dataclass
class Job:
    """One thing to record and how (see the module's docs for each setting)."""

    name: str
    target: str
    steps: str = ""
    duration: float = 0
    size: Any = None
    scale: Any = 2.0
    fps: Any = 20
    theme: Any = None
    formats: List[str] = field(default_factory=lambda: ["webp"])
    out: str = "{name}{variant}.{ext}"
    crop: Any = None
    margin: int = 40
    pointer: bool = True
    quality: int = 80
    max_bytes: int = 0
    max_width: int = 0
    poster: bool = False
    wait: float = 0.1
    renderer: str = "auto"
    method: int = 4

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        known = {f.name for f in dataclasses.fields(cls)}
        aliases = {"format": "formats", "steps_text": "steps"}
        clean: Dict[str, Any] = {}
        for k, v in data.items():
            k = aliases.get(k, k)
            if k not in known:
                raise ValueError(f"job {data.get('name', '?')!r}: unknown setting {k!r}")
            clean[k] = v
        if "name" not in clean or "target" not in clean:
            raise ValueError(f"a job needs a name and a target: {data!r}")
        if isinstance(clean.get("formats"), str):
            clean["formats"] = [f.strip() for f in re.split(r"[,\s]+", clean["formats"]) if f.strip()]
        if isinstance(clean.get("steps"), list):
            clean["steps"] = "; ".join(clean["steps"])
        job = cls(**clean)
        for fmt in job.formats:
            if fmt.lower() not in FORMATS:
                raise ValueError(f"job {job.name!r}: unknown format {fmt!r} (use {', '.join(FORMATS)})")
        return job

    @property
    def still(self) -> bool:
        """No steps and no duration: one frame (a screenshot)."""
        return not self.steps.strip() and not self.duration


@dataclass
class Task:
    """One recording: a job with one value for each matrix setting, and the files it writes."""

    job: Job
    theme: Optional[str]
    size: Optional[Tuple[float, float]]
    scale: float
    fps: float
    outputs: Dict[str, str]  # format -> path
    base: str = "."

    @property
    def label(self) -> str:
        parts = [self.job.name]
        if self.theme:
            parts.append(self.theme)
        if self.size:
            parts.append(f"{self.size[0]:g}x{self.size[1]:g}")
        parts.append(f"{self.scale:g}x")
        return " · ".join(parts)

    def cost(self) -> float:
        """A rough size of the work, to start the longest recordings first."""
        w, h = self.size or (800, 600)
        seconds = 0 if self.job.still else self.job.duration / 1000 + 2.5 * bool(self.job.steps.strip())
        return w * h * self.scale * self.scale * max(1.0, seconds * self.fps)

    def key(self) -> str:
        """What made this task's files: its settings and the target's contents."""
        from .. import __version__
        from .targets import fingerprint

        data = dataclasses.asdict(self.job)
        # The target by what it reads, not how it was written (a relative path, the window's absolute one).
        data.pop("target")
        data.update(theme=self.theme, size=self.size, scale=self.scale, fps=self.fps, version=__version__,
                    outputs={f: str(Path(p).resolve()) for f, p in self.outputs.items()},
                    target_hash=fingerprint(self.job.target, Path(self.base)))
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:20]

    def to_dict(self) -> Dict[str, Any]:
        return {"job": dataclasses.asdict(self.job), "theme": self.theme, "size": self.size, "scale": self.scale,
                "fps": self.fps, "outputs": self.outputs, "base": self.base}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Task":
        size = tuple(d["size"]) if d.get("size") else None
        return cls(Job(**d["job"]), d["theme"], size, d["scale"], d["fps"], d["outputs"], d["base"])


def parse_size(value: Any) -> Optional[Tuple[float, float]]:
    """``[480, 270]``, ``"480x270"`` or ``None`` as ``(480.0, 270.0)``."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        w, _, h = value.lower().partition("x")
        return (float(w), float(h))
    w, h = value
    return (float(w), float(h))


def _values(value: Any, key: str) -> list:
    """The values a matrix setting takes (a list, or one value)."""
    if key == "size":
        if value is None or isinstance(value, str):
            return [value]
        if isinstance(value, (list, tuple)) and value and all(isinstance(v, (int, float)) for v in value):
            return [value]  # one [w, h]
    if isinstance(value, (list, tuple)):
        return list(value) or [None]
    return [value]


def slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def expand(job: Job, out_dir: Union[str, Path] = ".", base: Union[str, Path] = ".") -> List[Task]:
    """The tasks of ``job``: one for every combination of its matrix settings."""
    lists = {k: _values(getattr(job, k), k) for k in MATRIX}
    varying = [k for k in MATRIX if len(lists[k]) > 1]
    tasks = []
    for combo in itertools.product(*(lists[k] for k in MATRIX)):
        values = dict(zip(MATRIX, combo))
        size = parse_size(values["size"])
        scale = float(values["scale"] if values["scale"] is not None else 2.0)
        fps = float(values["fps"] if values["fps"] is not None else 20)
        theme = values["theme"]
        parts = {"theme": slug(theme) if theme else "", "size": f"{size[0]:g}x{size[1]:g}" if size else "",
                 "scale": f"{scale:g}x", "fps": f"{fps:g}fps"}
        variant = "".join(f".{parts[k]}" for k in varying if parts[k])
        outputs = {}
        for fmt in job.formats:
            fmt = fmt.lower()
            ext = "png" if fmt == "apng" else fmt
            name = job.out.format(name=job.name, variant=variant, ext=ext, **parts)
            if fmt == "apng" and job.out.endswith("{ext}"):
                name = name[: -len(ext)] + "apng.png"
            outputs[fmt] = str(Path(out_dir) / name)
        tasks.append(Task(job, theme, size, scale, fps, outputs, str(base)))
    return tasks


def _toml(path: Path) -> Dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            raise RuntimeError("reading TOML on Python 3.10 needs tomli (pip install tomli), or write JSON") from None
    return tomllib.loads(path.read_text(encoding="utf-8"))


def load_jobs(path: Union[str, Path]) -> Tuple[List[Job], Dict[str, Any]]:
    """The jobs of a TOML or JSON job file, and its top-level settings (``out_dir``, ``jobs``)."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else _toml(path)
    defaults = data.get("defaults", {})
    jobs = [Job.from_dict({**defaults, **entry}) for entry in data.get("job", [])]
    names = [j.name for j in jobs]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise ValueError(f"two jobs share a name: {', '.join(dupes)}")
    return jobs, {k: v for k, v in data.items() if k not in ("defaults", "job")}


def save_jobs(path: Union[str, Path], jobs: Sequence[Job], settings: Optional[Dict[str, Any]] = None) -> None:
    """Writes a job file (JSON, or TOML for a ``.toml`` path) that ``load_jobs`` reads back."""
    path = Path(path)
    defaults = dataclasses.asdict(Job("", ""))
    entries = []
    for job in jobs:
        d = dataclasses.asdict(job)
        entries.append({k: v for k, v in d.items() if k in ("name", "target") or v != defaults[k]})
    data = {**(settings or {}), "job": entries}
    if path.suffix == ".json":
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    path.write_text(_to_toml(data), encoding="utf-8")


def _toml_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    if v is None:
        return '""'
    return json.dumps(str(v), ensure_ascii=False)


def _to_toml(data: Dict[str, Any]) -> str:
    lines = [f"{k} = {_toml_value(v)}" for k, v in data.items() if k != "job" and v is not None]
    for entry in data.get("job", []):
        lines += ["", "[[job]]"] + [f"{k} = {_toml_value(v)}" for k, v in entry.items() if v is not None]
    return "\n".join(lines) + "\n"


# -- running ---------------------------------------------------------------------------------------
def run_task(task: Task) -> Dict[str, Any]:
    """Records one task and writes its files; returns what was written."""
    from . import session
    from .images import crop_box, fit_image
    from .steps import parse_steps, wait
    from .targets import load

    job = task.job
    started = time.time()
    base = Path(task.base)
    make = load(job.target, base)
    themed = getattr(make, "themed", False)  # a form applies the theme itself

    def app() -> Any:
        return make(theme=task.theme) if themed else make()

    theme = None if themed else task.theme
    result: Dict[str, Any] = {"label": task.label, "name": job.name, "files": []}
    if job.still:
        frames = [session.screenshot(app(), size=task.size, scale=task.scale, wait=job.wait, theme=theme,
                                     renderer=job.renderer)]
        renderer = frames[0].info.get("renderer", "")
    else:
        steps = parse_steps(job.steps) if job.steps.strip() else []
        if job.duration:
            steps.append(wait(job.duration))
        made = app()
        size = task.size or tuple(getattr(made, "size", None) or (720, 360))  # the app's own window size
        take = session.record(made, steps, size=size, scale=task.scale, fps=task.fps,
                              theme=theme, renderer=job.renderer)
        frames = take.images(pointer=job.pointer)
        renderer = take.renderer
        if take.shader and renderer == "tiny-skia":
            result["warning"] = "the CPU renderer drew pz.shader's fallback color: record it with the GPU"
        if job.crop == "content":
            box = crop_box(take.images(pointer=False), job.margin)
            frames = [f.crop(box) for f in frames]
    if isinstance(job.crop, (list, tuple)):
        x, y, w, h = (round(v * task.scale) for v in job.crop)
        frames = [f.crop((x, y, x + w, y + h)) for f in frames]
    if job.max_width and frames[0].width > job.max_width:
        width = job.max_width - job.max_width % 2
        frames = [fit_image(f, (width, 10**6)) for f in frames]
    for fmt, out in task.outputs.items():
        info = encode(frames, Path(out), fmt, fps=task.fps, quality=job.quality, target=job.max_bytes,
                      method=job.method)
        result["files"].append({"path": out, "format": fmt, **info})
    if job.poster:
        first = next(iter(task.outputs.values()))
        poster = Path(first).with_suffix(".still.webp")
        save_poster(frames[0], poster)
        result["files"].append({"path": str(poster), "format": "poster", "bytes": poster.stat().st_size})
    result.update(width=frames[0].width, height=frames[0].height, frames=len(frames), renderer=renderer,
                  seconds=round(time.time() - started, 2))
    return result


def _safe_run(data: Dict[str, Any]) -> Dict[str, Any]:
    task = Task.from_dict(data)
    try:
        return run_task(task)
    except Exception as err:  # reported with the task, the batch goes on
        return {"label": task.label, "name": task.job.name, "error": f"{type(err).__name__}: {err}",
                "traceback": traceback.format_exc(), "files": []}


def _worker_init(cwd: str, threads: int) -> None:
    os.chdir(cwd)
    # lavapipe draws with one thread per core: with a process per core, one thread each is faster.
    os.environ.setdefault("LP_NUM_THREADS", str(threads))
    os.environ.setdefault("PYZED_CONFIG_DIR", os.path.join(cwd, ".pyzed-record-config"))


def _read_cache(path: Path) -> Dict[str, str]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def run(tasks: Sequence[Task], *, jobs: int = 0, force: bool = False, cache: Optional[Union[str, Path]] = None,
        progress: Optional[Callable[[Dict[str, Any]], None]] = None) -> List[Dict[str, Any]]:
    """Runs ``tasks`` in ``jobs`` processes (0: one per CPU core; 1: in this process) and returns each
    one's result. ``cache`` is the cache file (``None``: no cache). ``progress(result)`` is called as
    each task ends, skipped ones included (``"skipped": True``)."""
    cache_path = Path(cache) if cache else None
    known = _read_cache(cache_path) if cache_path else {}
    results: List[Dict[str, Any]] = []
    todo: List[Tuple[Task, str]] = []
    for task in tasks:
        key = task.key() if cache_path else ""
        if not force and cache_path and all(known.get(str(Path(p).resolve())) == key and Path(p).exists()
                                            for p in task.outputs.values()):
            result = {"label": task.label, "name": task.job.name, "skipped": True, "files": [
                {"path": p, "format": f} for f, p in task.outputs.items()]}
            results.append(result)
            if progress:
                progress(result)
            continue
        if any(f in VIDEO for f in task.outputs):
            import shutil

            if shutil.which("ffmpeg") is None:
                result = {"label": task.label, "name": task.job.name, "files": [],
                          "error": "MP4 and WebM need ffmpeg on the PATH"}
                results.append(result)
                if progress:
                    progress(result)
                continue
        todo.append((task, key))
    todo.sort(key=lambda tk: -tk[0].cost())
    cores = os.cpu_count() or 1
    workers = min(jobs or cores, max(1, len(todo)))

    def done(result: Dict[str, Any], key: str) -> None:
        if cache_path and not result.get("error"):
            for f in result["files"]:
                known[str(Path(f["path"]).resolve())] = key
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(known, indent=0, sort_keys=True), encoding="utf-8")
        results.append(result)
        if progress:
            progress(result)

    if workers <= 1:
        for task, key in todo:
            done(_safe_run(task.to_dict()), key)
        return results
    ctx = multiprocessing.get_context("spawn")
    threads = max(1, cores // workers)
    with concurrent.futures.ProcessPoolExecutor(workers, mp_context=ctx, initializer=_worker_init,
                                                initargs=(os.getcwd(), threads)) as pool:
        futures = {pool.submit(_safe_run, task.to_dict()): (task, key) for task, key in todo}
        for future in concurrent.futures.as_completed(futures):
            task, key = futures[future]
            try:
                result = future.result()
            except Exception as err:  # the worker died (a crash in native code)
                result = {"label": task.label, "name": task.job.name, "files": [],
                          "error": f"the recording process stopped: {err}"}
            done(result, key)
    return results


def iter_tasks(jobs: Sequence[Job], out_dir: Union[str, Path], base: Union[str, Path],
               only: Sequence[str] = ()) -> Iterator[Task]:
    """The tasks of ``jobs`` (only those whose name contains one of ``only``, when given)."""
    for job in jobs:
        if only and not any(o in job.name for o in only):
            continue
        yield from expand(job, out_dir, base)

