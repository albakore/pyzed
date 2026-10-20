"""Live previews for the MCP server: the app the agent is building, open in a real window with hot reload.

``start(root, target)`` runs a script with ``pyzed dev`` (or a form, component or shader graph with
``pyzed run --reload``) in the project's own environment, so every file the agent writes shows up in the
window as soon as it is saved, and the user watches the app take shape. ``status`` returns what it printed
(tracebacks included) and ``stop`` closes it. Previews end with the server.
"""

from __future__ import annotations

import atexit
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from . import projects

#: Characters of output ``status`` returns at most.
OUTPUT_LIMIT = 6000


@dataclass
class Preview:
    target: str
    command: List[str]
    process: subprocess.Popen
    log: Path
    started: float = field(default_factory=time.time)

    @property
    def running(self) -> bool:
        return self.process.poll() is None

    def output(self) -> str:
        try:
            text = self.log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return text if len(text) <= OUTPUT_LIMIT else "…" + text[-OUTPUT_LIMIT:]

    def info(self) -> Dict[str, Any]:
        return {"target": self.target, "running": self.running, "exit_code": self.process.poll(),
                "seconds": round(time.time() - self.started, 1), "output": self.output()}

    def stop(self) -> None:
        if self.running:
            self.process.terminate()
            try:
                self.process.wait(5)
            except subprocess.TimeoutExpired:
                self.process.kill()


_previews: Dict[str, Preview] = {}
_logs = tempfile.TemporaryDirectory(prefix="pyzed-live-")


def command(root: Path, target: str = "") -> List[str]:
    """The command that shows ``target`` with hot reload (by default the project's entry)."""
    path = projects._target(root, target)
    python, _ = projects.launcher(root, projects._rel(root, path.parent))
    if path.suffix == ".py":
        return [*python, "-m", "pyzed", "dev", str(path)]
    return [*python, "-m", "pyzed", "run", str(path), "--reload"]


def start(root: Path, target: str = "", *, cmd: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Opens ``target`` in a window with hot reload; a preview of the same file already open is replaced.
    Waits a moment so a crash on start is reported right away."""
    path = projects._target(root, target)
    rel = projects._rel(root, path)
    if rel in _previews:
        _previews.pop(rel).stop()
    cmd = list(cmd) if cmd is not None else command(root, rel)
    _, env = projects.launcher(root, projects._rel(root, path.parent))
    env = {**env, "PYZED_RELOAD": "1", "PYTHONUNBUFFERED": "1"}
    log = Path(_logs.name) / (rel.replace("/", "_") + ".log")
    with open(log, "wb") as out:
        process = subprocess.Popen(cmd, cwd=str(path.parent), env=env, stdout=out, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL)
    preview = _previews[rel] = Preview(rel, cmd, process, log)
    try:
        process.wait(2)
    except subprocess.TimeoutExpired:
        pass
    result = preview.info()
    result["note"] = ("The window is open: files you write now update it on save. Call live_preview_status "
                      "after changes to read errors.") if preview.running else "It stopped: read output and fix it."
    return result


def status(target: str = "") -> List[Dict[str, Any]]:
    """Every open preview (or the one of ``target``) with whether it runs and what it printed."""
    return [p.info() for rel, p in _previews.items() if not target or rel == target]


def stop(target: str = "") -> Dict[str, Any]:
    """Closes the preview of ``target``, or every preview."""
    names = [rel for rel in _previews if not target or rel == target]
    for rel in names:
        _previews.pop(rel).stop()
    return {"stopped": names}


@atexit.register
def _stop_all() -> None:
    for preview in list(_previews.values()):
        preview.stop()
    _previews.clear()
    if os.name != "nt":  # Windows may still hold the log files open for a moment
        _logs.cleanup()
