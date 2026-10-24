"""``pyzed record``: screenshots and clips from the command line, one or a whole batch."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .batch import CACHE, Job, expand, iter_tasks, load_jobs, run
from .encode import FORMATS

__all__ = ["add_parser", "main"]


def _list(value: Optional[str]) -> Optional[List[str]]:
    if value is None:
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


def _matrix(value: Optional[str], kind=str) -> Any:
    """``"Pyzed Dark,Pyzed Light"`` as a list (one value stays a value)."""
    items = _list(value)
    if not items:
        return None
    values = [kind(v) for v in items]
    return values if len(values) > 1 else values[0]


def add_parser(sub: Any) -> None:
    """Adds ``record`` and its subcommands to the ``pyzed`` command line."""
    p = sub.add_parser("record", help="screenshots and clips of an app, off-screen (one, a batch, or a window)",
                       description="Records screenshots and clips of Pyzed apps off-screen: no window, display "
                                   "or GPU needed.")
    rsub = p.add_subparsers(dest="record_command", required=True)

    def common(q: Any, still: bool) -> None:
        q.add_argument("target", help="app.py[:App], package.module:App, a .pzform/.pzcomp, or code:<snippet>")
        q.add_argument("-o", "--out", help="the file to write, or a name with {name} {variant} {theme} {size} "
                                           "{scale} {fps} {ext} (default: {name}{variant}.{ext})")
        q.add_argument("-f", "--formats", default="png" if still else "webp",
                       help=f"comma-separated: {', '.join(FORMATS)}")
        q.add_argument("--size", help="WxH in logical pixels; several, comma-separated, record each one")
        q.add_argument("--scale", default="2", help="pixels per logical pixel (comma-separated for several)")
        q.add_argument("--theme", help='"Pyzed Dark", "Pyzed Light"... (comma-separated for several)')
        q.add_argument("--renderer", choices=("auto", "gpu", "cpu"), default="auto",
                       help="auto: the GPU when there is one (a software one too); cpu: 2-3x faster than a software GPU, for drafts (blur and glow differ a little)")
        q.add_argument("--name", help="the {name} in file names (default: the target's file name)")
        q.add_argument("--jobs", type=int, default=0, help="processes (default: one per core)")
        q.add_argument("--json", action="store_true", help="print one JSON line per recording")

    shot = rsub.add_parser("shot", help="a screenshot (PNG, WebP...)")
    common(shot, True)
    shot.add_argument("--wait", type=float, default=0.1, help="seconds the app runs before the shot")

    clip = rsub.add_parser("clip", help="an animated clip (WebP, GIF, APNG, MP4, WebM)")
    common(clip, False)
    clip.add_argument("--steps", default="", help="""steps separated by ';': hover("Save"); press(); wait(600)""")
    clip.add_argument("--duration", type=float, default=0, help="milliseconds to film (after the steps)")
    clip.add_argument("--fps", default="20", help="frames per second (comma-separated for several)")
    clip.add_argument("--crop", action="store_true", help="trim to what is drawn plus --margin pixels")
    clip.add_argument("--margin", type=int, default=40)
    clip.add_argument("--no-pointer", action="store_true", help="don't draw the pointer")
    clip.add_argument("--quality", type=int, default=80, help="0-100")
    clip.add_argument("--max-bytes", type=int, default=0, help="lower the quality until each file fits")
    clip.add_argument("--max-width", type=int, default=0, help="scale down clips wider than this (pixels)")
    clip.add_argument("--poster", action="store_true", help="also write the first frame as .still.webp")
    clip.add_argument("--method", type=int, default=4, help="WebP effort 0-6 (6: ~10x slower, ~2%% smaller)")

    batch = rsub.add_parser("batch", help="every job of a TOML or JSON job file, in parallel")
    batch.add_argument("file")
    batch.add_argument("only", nargs="*", help="only the jobs whose name contains one of these")
    batch.add_argument("--jobs", type=int, default=None, help="processes (default: the file's, or one per core)")
    batch.add_argument("--out-dir", help="where files go (default: the file's out_dir, next to it)")
    batch.add_argument("--force", action="store_true", help="record again what the cache says is up to date")
    batch.add_argument("--dry-run", action="store_true", help="list the recordings and their files, record nothing")
    batch.add_argument("--json", action="store_true", help="print one JSON line per recording")

    gui = rsub.add_parser("gui", help="a window to build jobs, preview them and run the batch")
    gui.add_argument("file", nargs="?", help="a job file to open (created when saved)")

    rsub.add_parser("info", help="which renderer recordings use on this machine")


def _report(result: Dict[str, Any], as_json: bool, index: int, total: int) -> None:
    if as_json:
        print(json.dumps({"index": index, "total": total, **{k: v for k, v in result.items() if k != "traceback"}}),
              flush=True)
        return
    head = f"[{index}/{total}] {result['label']}"
    if result.get("error"):
        print(f"{head}: FAILED {result['error']}", file=sys.stderr, flush=True)
        if os.environ.get("PYZED_DEBUG"):
            print(result.get("traceback", ""), file=sys.stderr)
        return
    if result.get("skipped"):
        print(f"{head}: up to date", flush=True)
        return
    files = ", ".join(f"{Path(f['path']).name} {f.get('bytes', 0) / 1000:.0f} KB" for f in result["files"])
    print(f"{head}: {result['width']}x{result['height']}, {result['frames']} frames, {result['seconds']:.1f}s "
          f"({result['renderer']}) -> {files}", flush=True)
    if result.get("warning"):
        print(f"  warning: {result['warning']}", flush=True)


def _run(tasks: list, jobs: int, as_json: bool, cache: Optional[Path] = None, force: bool = False) -> int:
    total = len(tasks)
    count = [0]
    started = time.time()

    def progress(result: Dict[str, Any]) -> None:
        count[0] += 1
        _report(result, as_json, count[0], total)

    results = run(tasks, jobs=jobs, force=force, cache=cache, progress=progress)
    failed = sum(1 for r in results if r.get("error"))
    if not as_json:
        skipped = sum(1 for r in results if r.get("skipped"))
        print(f"{total - failed - skipped} recorded, {skipped} up to date, {failed} failed "
              f"in {time.time() - started:.1f}s")
    return 1 if failed else 0


def _single(args: Any, still: bool) -> int:
    target = args.target
    name = args.name or ("snippet" if target.startswith("code:") else Path(target.partition(":")[0]).stem or "app")
    formats = _list(args.formats) or ["png"]
    out = args.out or "{name}{variant}.{ext}"
    out_dir = "."
    if "{" not in out:
        path = Path(out)
        out_dir = str(path.parent)
        if len(formats) == 1 and path.suffix.lstrip(".").lower() in (formats[0], "png"):
            out = path.stem + "{variant}" + path.suffix
        else:
            out = path.stem + "{variant}.{ext}"
    settings: Dict[str, Any] = dict(name=name, target=target, formats=formats, out=out,
                                    size=_matrix(args.size), scale=_matrix(args.scale, float),
                                    theme=_matrix(args.theme), renderer=args.renderer)
    if still:
        settings["wait"] = args.wait
    else:
        settings.update(steps=args.steps, duration=args.duration or (0 if args.steps else 2000),
                        fps=_matrix(args.fps, float), crop="content" if args.crop else None, margin=args.margin,
                        pointer=not args.no_pointer, quality=args.quality, max_bytes=args.max_bytes,
                        max_width=args.max_width, poster=args.poster, method=args.method)
    job = Job.from_dict({k: v for k, v in settings.items() if v is not None})
    return _run(expand(job, out_dir, "."), args.jobs, args.json)


def main(args: Any) -> int:
    """Runs ``pyzed record <subcommand>`` with the parsed ``args``."""
    command = args.record_command
    if command == "info":
        from .session import gpu, pick_renderer

        found = gpu()
        print(f"GPU: {found[0]} ({found[1]})" if found else "GPU: none")
        print(f"recordings draw with: {pick_renderer('auto')} renderer")
        if found and found[1] == "cpu":
            print("the GPU is a software one: --renderer cpu is 2-3x faster for drafts (blur and glow differ a little)")
        return 0
    if command == "gui":
        from .gui import main as gui_main

        return gui_main(args.file)
    if command in ("shot", "clip"):
        return _single(args, command == "shot")
    path = Path(args.file)
    jobs, settings = load_jobs(path)
    base = path.parent
    out_dir = Path(args.out_dir) if args.out_dir else base / settings.get("out_dir", ".")
    tasks = list(iter_tasks(jobs, out_dir, base, args.only))
    if args.dry_run:
        for task in tasks:
            print(f"{task.label}: {', '.join(task.outputs.values())}")
        print(f"{len(tasks)} recordings")
        return 0
    workers = args.jobs if args.jobs is not None else int(settings.get("jobs", 0))
    return _run(tasks, workers, args.json, cache=out_dir / CACHE, force=args.force)


def standalone(argv: Optional[List[str]] = None) -> int:
    """``python -m pyzed.recording``: the same as ``pyzed record``."""
    parser = argparse.ArgumentParser(prog="pyzed")
    add_parser(parser.add_subparsers(dest="command", required=True))
    return main(parser.parse_args(["record", *(sys.argv[1:] if argv is None else argv)]))
