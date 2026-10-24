"""``python -m module`` for a compiled Pyzed Design.

In the compiled designer ``sys.executable`` is the designer itself, so the helpers it starts with
``[sys.executable, "-m", ...]`` (screenshots of forms, the MCP server, its bridge for agents) would
open another editor instead. Its entry point hands such a command line to ``run_module``, which runs
the module like Python does.
"""

from __future__ import annotations

import os
import runpy
import sys
from typing import List, Optional


def wants_module(argv: Optional[List[str]] = None) -> bool:
    """Whether the command line is ``-m module [args...]``."""
    args = sys.argv[1:] if argv is None else argv
    return len(args) >= 2 and args[0] == "-m"


def run_module(args: List[str]) -> int:
    """Runs ``args[0]`` as ``__main__`` with ``args[1:]`` as its arguments; returns the exit code."""
    _standard_streams()
    name, sys.argv = args[0], [args[0], *args[1:]]
    try:
        runpy.run_module(name, run_name="__main__", alter_sys=True)
    except SystemExit as done:
        code = done.code
        if code is None or isinstance(code, int):
            return code or 0
        print(code, file=sys.stderr)
        return 1
    return 0


def _standard_streams() -> None:
    """A windowed app has no ``sys.stdout``/``sys.stderr``; use the pipes its parent handed it, if any."""
    for fd, name in ((1, "stdout"), (2, "stderr")):
        if getattr(sys, name) is not None:
            continue
        try:
            stream = open(fd, "w", encoding="utf-8", errors="replace", closefd=False)  # noqa: SIM115
        except OSError:
            stream = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
        setattr(sys, name, stream)
