"""Renders Pyzed code to a PNG off-screen, for the MCP server's ``screenshot`` tool.

The code runs in a separate process with a time limit. ``pz.run`` is replaced so the script does
not open a window: the app it would have run is captured instead. Without a ``pz.run`` call, the
last ``pz.App`` subclass defined in the code is used, or a top-level ``preview()`` function that
returns a widget (handy for showing a single component).

    python -m pyzed.mcp.preview app.py out.png [width height [scale]]
    python -m pyzed.mcp.preview --window app.py out.png [width height]

``--window`` opens the app in a real window for a moment instead and captures what it shows
(``Command.capture_window``): the fallback when the off-screen renderer fails on a machine.
"""

from __future__ import annotations

import os
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _find_app(namespace: dict, captured: Optional[Any]) -> Any:
    import pyzed as pz

    if captured is not None:
        return captured
    apps = [v for v in namespace.values() if isinstance(v, type) and issubclass(v, pz.App) and v is not pz.App]
    if apps:
        return apps[-1]
    preview = namespace.get("preview")
    if callable(preview):
        class Preview(pz.App):
            def view(self):
                return pz.container(preview(), padding=16, width="fill", height="fill",
                                    bg=self.resolved_theme().background)

        return Preview
    raise SystemExit("error: the code defines no pz.App subclass and no preview() function returning a widget")


def main(argv=None) -> int:
    """Runs the script in ``argv[0]`` with ``pz.run`` captured and saves its screenshot to ``argv[1]``.

    Errors are also written next to the picture (``out.png.log``), for parents that cannot read this
    process's output (a compiled Pyzed Design on Windows has none)."""
    args = list(sys.argv[1:] if argv is None else argv)
    window = "--window" in args
    args = [a for a in args if a != "--window"]
    script, out = args[0], args[1]
    try:
        return _main(script, out, args[2:], window)
    except BaseException as err:
        if isinstance(err, SystemExit) and not err.code:
            raise
        _log_error(out)
        raise


def _log_error(out: str) -> None:
    import traceback

    text = traceback.format_exc()
    try:
        Path(out + ".log").write_text(text, encoding="utf-8")
    except OSError:
        pass
    if sys.stderr is not None:
        sys.stderr.write(text)


def _main(script: str, out: str, rest: List[str], window: bool) -> int:
    size: Optional[Tuple[int, int]] = (int(rest[0]), int(rest[1])) if len(rest) >= 2 else None
    scale = float(rest[2]) if len(rest) >= 3 else 1.0
    if window:  # the window must open here, not as a Windows program from WSL
        os.environ["PYZED_WINDOWS"] = "0"
    import pyzed as pz
    import pyzed.app as app_module

    captured: list = []
    real_run = app_module.run

    def fake_run(app, **_kwargs):
        captured.append(app)

    pz.run = app_module.run = fake_run  # type: ignore
    sys.path.insert(0, str(Path(script).resolve().parent))
    namespace = runpy.run_path(script, run_name="__main__")
    app = _find_app(namespace, captured[-1] if captured else None)
    if isinstance(app, type):
        app = app()
    # The window shows a view() error instead of the UI; report it so the caller sees it as text.
    try:
        app.__pyzed_view__()
    except Exception:
        _log_error(out)
        return 3
    if window:
        return _capture_window(app, out, real_run)
    pz.screenshot(app, out, size=size, scale=scale)
    return 0


def _capture_window(app: Any, out: str, run: Any, wait: float = 1.5) -> int:
    """Opens ``app`` in its window, captures it once it has drawn (after ``wait`` seconds, so its load event
    and first frames are done) into ``out`` and closes it."""
    import time

    import pyzed as pz

    started = getattr(app, "on_start", None)

    def save(png: Optional[bytes]) -> Any:
        if png:
            Path(out).write_bytes(bytes(png))
        else:
            Path(out + ".log").write_text("the window could not be captured", encoding="utf-8")
        return pz.Command.exit()

    def on_start() -> Any:
        first = started() if callable(started) else None
        later = pz.Command.perform(lambda: time.sleep(wait), lambda _: pz.Command.capture_window(save))
        return [first, later] if first is not None else later

    app.on_start = on_start
    run(app, reload=False)
    return 0 if Path(out).is_file() else 4


def render(source: str, *, size: Optional[Tuple[int, int]] = None, scale: float = 1.0,
           timeout: float = 60.0, window: bool = False, python: Optional[Sequence[str]] = None,
           env: Optional[Dict[str, str]] = None) -> bytes:
    """Runs ``source`` in a child process and returns the PNG of its app. Raises ``RuntimeError`` on errors.

    ``window=True`` opens the app in a real window for a moment and captures it instead of rendering it
    off-screen; ``python`` and ``env`` work as in ``render_file``."""
    with tempfile.TemporaryDirectory(prefix="pyzed-mcp-") as tmp:
        script = Path(tmp) / "app.py"
        script.write_text(source, encoding="utf-8")
        return _render(script, Path(tmp), size=size, scale=scale, timeout=timeout, window=window, python=python,
                       env=env)


def render_file(path, *, size: Optional[Tuple[int, int]] = None, scale: float = 1.0, timeout: float = 60.0,
                python: Optional[Sequence[str]] = None, env: Optional[Dict[str, str]] = None) -> bytes:
    """Like ``render`` for a script on disk, run from its own folder so its imports and files resolve.

    ``python`` is the command that starts the interpreter (by default this one, with this same pyzed), such as
    ``["uv", "run", "--project", root, "python"]`` to use a project's own environment, and ``env`` its variables."""
    path = Path(path).resolve()
    return _render(path, path.parent, size=size, scale=scale, timeout=timeout, python=python, env=env)


def this_python() -> Tuple[List[str], Dict[str, str]]:
    """The command and environment that run this interpreter with this same pyzed importable.

    In a compiled Pyzed Design ``sys.executable`` is the designer itself, which runs ``-m module``
    like Python does (see ``pyzed._frozen``) instead of opening another editor."""
    if getattr(sys, "frozen", False):
        return [sys.executable], {**os.environ}
    import pyzed

    # The child must import this same pyzed, even when it was found through a relative path.
    here = str(Path(pyzed.__file__).resolve().parents[1])
    path = os.pathsep.join(p for p in (here, os.environ.get("PYTHONPATH", "")) if p)
    return [sys.executable], {**os.environ, "PYTHONPATH": path}


def _render(script: Path, cwd: Path, *, size, scale: float, timeout: float, window: bool = False,
            python: Optional[Sequence[str]] = None, env: Optional[Dict[str, str]] = None) -> bytes:
    if python is None:
        python, env = this_python()
    env = {**(env if env is not None else os.environ), "PYZED_RELOAD": "0", "PYTHONUNBUFFERED": "1"}
    env.pop("PYZED_DESIGNER_RUN", None)
    with tempfile.TemporaryDirectory(prefix="pyzed-mcp-") as tmp:
        out = Path(tmp) / "shot.png"
        cmd = [*python, "-m", "pyzed.mcp.preview", *(["--window"] if window else []), str(script), str(out)]
        if size:
            cmd += [str(int(size[0])), str(int(size[1])), str(scale)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout,
                                    cwd=tmp, env=env, stdin=subprocess.DEVNULL,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"the code did not finish within {timeout:g} seconds") from None
        except OSError as err:
            raise RuntimeError(f"could not start {python[0]}: {err}") from None
        if result.returncode != 0 or not out.is_file():
            log = Path(f"{out}.log")
            detail = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
            detail = detail or result.stderr or result.stdout
            raise RuntimeError(detail.strip()[-4000:] or f"rendering failed (exit code {result.returncode})")
        return out.read_bytes()


if __name__ == "__main__":
    sys.exit(main())
