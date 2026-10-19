"""Renders Pyzed code to a PNG off-screen, for the MCP server's ``screenshot`` tool.

The code runs in a separate process with a time limit. ``pz.run`` is replaced so the script does
not open a window: the app it would have run is captured instead. Without a ``pz.run`` call, the
last ``pz.App`` subclass defined in the code is used, or a top-level ``preview()`` function that
returns a widget (handy for showing a single component).

    python -m pyzed.mcp.preview app.py out.png [width height [scale]]
"""

from __future__ import annotations

import os
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional, Tuple


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
    """Runs the script in ``argv[0]`` with ``pz.run`` captured and saves its screenshot to ``argv[1]``."""
    args = list(sys.argv[1:] if argv is None else argv)
    script, out = args[0], args[1]
    size: Optional[Tuple[int, int]] = (int(args[2]), int(args[3])) if len(args) >= 4 else None
    scale = float(args[4]) if len(args) >= 5 else 1.0
    import pyzed as pz
    import pyzed.app as app_module

    captured: list = []

    def fake_run(app, **_kwargs):
        captured.append(app)

    pz.run = app_module.run = fake_run  # type: ignore
    sys.path.insert(0, str(Path(script).resolve().parent))
    namespace = runpy.run_path(script, run_name="__main__")
    app = _find_app(namespace, captured[-1] if captured else None)
    pz.screenshot(app, out, size=size, scale=scale)
    return 0


def render(source: str, *, size: Optional[Tuple[int, int]] = None, scale: float = 1.0,
           timeout: float = 60.0) -> bytes:
    """Runs ``source`` in a child process and returns the PNG of its app. Raises ``RuntimeError`` on errors."""
    with tempfile.TemporaryDirectory(prefix="pyzed-mcp-") as tmp:
        script = Path(tmp) / "app.py"
        out = Path(tmp) / "shot.png"
        script.write_text(source, encoding="utf-8")
        cmd = [sys.executable, "-m", "pyzed.mcp.preview", str(script), str(out)]
        if size:
            cmd += [str(int(size[0])), str(int(size[1])), str(scale)]
        # The child must import this same pyzed, even when it was found through a relative path.
        import pyzed

        here = str(Path(pyzed.__file__).resolve().parents[1])
        path = os.pathsep.join(p for p in (here, os.environ.get("PYTHONPATH", "")) if p)
        env = {**os.environ, "PYZED_RELOAD": "0", "PYTHONPATH": path}
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=tmp, env=env)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"the code did not finish within {timeout:g} seconds") from None
        if result.returncode != 0 or not out.is_file():
            raise RuntimeError((result.stderr or result.stdout).strip()[-4000:] or "rendering failed")
        return out.read_bytes()


if __name__ == "__main__":
    sys.exit(main())
