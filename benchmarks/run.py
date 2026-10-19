"""Measures Pyzed against other Python GUI toolkits and writes benchmarks/results/<date>.json.

    python benchmarks/run.py                      # everything that is installed
    python benchmarks/run.py --libs pyzed tkinter --runs 3
    python benchmarks/run.py --skip-sizes         # no throwaway venvs for install sizes
    python benchmarks/run.py --refresh benchmarks/results/<date>.json   # recount lines and sizes only

Run it with the interpreter of a virtual environment where the toolkits are installed
(see benchmarks/README.md). Toolkits that cannot be imported are skipped and listed in
the output's "skipped" section. Without a DISPLAY, an Xvfb server is started.

What is measured (see README.md for the details and the caveats):

* import: seconds to import the toolkit in a fresh interpreter;
* first_frame: seconds from launching the app's process to its first frame on screen
  (the harness watches the screen for the footer's sentinel color);
* rss / uss: memory of the app's process tree 1 s after its first frame;
* update: seconds from the app changing its state (all row labels and the footer color)
  to the new footer color being on screen;
* loc: lines of code of the same reference apps (apps/<toolkit>/counter.py and todo.py);
* install: megabytes a fresh virtual environment grows by when the toolkit is installed.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import importlib.metadata as md
import io
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import tokenize
from pathlib import Path

HERE = Path(__file__).resolve().parent
APPS = HERE / "apps"
sys.path.insert(0, str(APPS))
from benchkit import A, color  # noqa: E402

#: name -> (module to import, distributions to report, pip spec for the install size)
LIBS = {
    "pyzed": ("pyzed", ["pyzed-ui"], "pyzed-ui"),
    "tkinter": ("tkinter", [], None),
    "customtkinter": ("customtkinter", ["customtkinter"], "customtkinter"),
    "pyside6": ("PySide6.QtWidgets", ["PySide6"], "pyside6-essentials"),
    "kivy": ("kivy.app", ["Kivy"], "kivy"),
    "dearpygui": ("dearpygui.dearpygui", ["dearpygui"], "dearpygui"),
    "flet": ("flet", ["flet", "flet-desktop"], "flet[desktop]"),
    "toga": ("toga", ["toga", "toga-gtk"], "toga"),
}
#: Same app and package as another entry, run with extra environment variables.
#: pyzed-cpu: Pyzed forced onto its CPU renderer (tiny-skia), what it falls back to without a GPU driver.
VARIANTS = {"pyzed-cpu": ("pyzed", {"ICED_BACKEND": "tiny-skia"})}
LIBS["pyzed-cpu"] = LIBS["pyzed"][:2] + (None,)

#: Install sizes only: NiceGUI draws in a browser, so it has no desktop window to time here.
SIZE_ONLY = {"nicegui": "nicegui"}

PIXELS = 8000  # sentinel pixels that count as "the footer is on screen" (it has ~25,000)
TOLERANCE = 4  # per-channel difference allowed (GL paths may round colors by one or two)
ENV = {**os.environ, "KIVY_NO_CONSOLELOG": "1", "KIVY_NO_ARGS": "1", "PYTHONDONTWRITEBYTECODE": "0"}


# -- helpers -----------------------------------------------------------------
def summary(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return {
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "n": len(values),
        "samples": values,
    }


def version(dist):
    try:
        return md.version(dist)
    except md.PackageNotFoundError:
        return None


def importable(module):
    code = f"import {module}"
    return subprocess.run([sys.executable, "-c", code], env=ENV, capture_output=True).returncode == 0


def kill_tree(proc):
    import psutil

    try:
        parent = psutil.Process(proc.pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except psutil.NoSuchProcess:
        pass
    try:
        proc.wait(5)
    except subprocess.TimeoutExpired:
        pass


def memory(pid):
    """RSS and USS (MB) of a process and all its children (Flet runs its window in a child)."""
    import psutil

    rss = uss = 0
    procs = [psutil.Process(pid)]
    procs += procs[0].children(recursive=True)
    for p in procs:
        try:
            info = p.memory_full_info()
            rss += info.rss
            uss += info.uss
        except psutil.Error:
            pass
    return rss / 2**20, uss / 2**20


# -- screen watching ------------------------------------------------------------
class Screen:
    def __init__(self):
        import mss
        import numpy

        self.np = numpy
        self.sct = mss.MSS()
        self.full = self.sct.monitors[0]

    def count(self, rgb, region=None):
        np = self.np
        shot = np.asarray(self.sct.grab(region or self.full))  # BGRA
        bgr = np.array(rgb[::-1], dtype=np.int16)
        near = np.all(np.abs(shot[:, :, :3].astype(np.int16) - bgr) <= TOLERANCE, axis=2)
        return int(near.sum()), near

    def wait(self, rgb, timeout, region=None, proc=None):
        """Polls the screen until `rgb` covers PIXELS pixels; returns (monotonic time, region).

        Gives up early (returning None) if `proc` exits."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if proc is not None and proc.poll() is not None:
                return None, region
            n, near = self.count(rgb, region)
            now = time.monotonic()
            if n >= PIXELS:
                if region is None:
                    ys, xs = self.np.nonzero(near)
                    region = {"left": int(xs.min()), "top": int(ys.min()),
                              "width": int(xs.max() - xs.min() + 1), "height": int(ys.max() - ys.min() + 1)}
                return now, region
            time.sleep(0.001)
        return None, region


# -- measurements ------------------------------------------------------------------
def measure_import(module, runs):
    code = f"import time; t = time.perf_counter(); import {module}; print(time.perf_counter() - t)"
    out = []
    subprocess.run([sys.executable, "-c", code], env=ENV, capture_output=True)  # warm the file cache
    for _ in range(runs):
        r = subprocess.run([sys.executable, "-c", code], env=ENV, capture_output=True, text=True)
        out.append(float(r.stdout.strip().splitlines()[-1]))
    return summary(out)


def measure_app(name, rows, updates, screen):
    """One launch of apps/<name>/bench.py: first frame, memory and update latencies."""
    folder, extra = VARIANTS.get(name, (name, {}))
    app = APPS / folder / "bench.py"
    env = {**ENV, "BENCH_UPDATES": str(updates), **extra}
    stamps, lock = {}, threading.Lock()
    t0 = time.monotonic()
    proc = subprocess.Popen([sys.executable, str(app), str(rows)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env)

    def read():
        for line in proc.stdout:
            parts = line.split()
            if len(parts) == 3 and parts[0] == "T":
                with lock:
                    stamps[int(parts[1])] = float(parts[2])

    threading.Thread(target=read, daemon=True).start()
    result = {"first_frame": None, "rss": None, "uss": None, "update": []}
    try:
        seen, region = screen.wait(A, 120, proc=proc)
        if seen is None:
            return result
        result["first_frame"] = seen - t0
        time.sleep(1.0)
        result["rss"], result["uss"] = memory(proc.pid)
        _, region = screen.wait(A, 30, proc=proc)  # find the footer again, in case the layout moved it
        proc.stdin.write("go\n")
        proc.stdin.flush()
        for k in range(1, updates + 1):
            seen, _ = screen.wait(color(k), 60, region, proc)
            if seen is None:
                break
            for _ in range(500):
                with lock:
                    sent = stamps.get(k)
                if sent is not None:
                    break
                time.sleep(0.01)
            if sent is not None:
                result["update"].append(seen - sent)
    finally:
        result["crashed"] = proc.poll() is not None
        kill_tree(proc)
        time.sleep(0.3)
    return result


def measure_install(spec):
    """MB that a fresh virtual environment grows by when `spec` is installed with uv."""
    uv = shutil.which("uv")
    if uv is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        venv = Path(tmp) / "venv"
        py = f"{sys.version_info.major}.{sys.version_info.minor}"
        subprocess.run([uv, "venv", "-q", "--python", py, str(venv)], check=True)
        base = du(venv)
        env = {**os.environ, "VIRTUAL_ENV": str(venv)}
        r = subprocess.run([uv, "pip", "install", "-q", "--link-mode=copy", spec], env=env, capture_output=True)
        if r.returncode:
            return None
        return (du(venv) - base) / 2**20


def install_sizes(name):
    """install_mb, plus install_extra_mb for what a toolkit downloads on first run (Flet's client)."""
    if name == "tkinter":
        return {"install_mb": tk_size()}
    if name in VARIANTS:
        return {}
    out = {"install_mb": measure_install(LIBS[name][2])}
    if name == "flet":
        client = Path.home() / ".flet" / "client"
        out["install_extra_mb"] = du(client) / 2**20 if client.exists() else None
    return out


def tk_size():
    """Size of the Tcl/Tk runtime that ships with this Python (tkinter is in the standard library)."""
    import sysconfig

    total = 0
    stdlib = Path(sysconfig.get_paths()["stdlib"])
    libdir = Path(sysconfig.get_config_var("LIBDIR") or stdlib.parent)
    for path in [stdlib / "tkinter", *stdlib.parent.glob("tcl*"), *stdlib.parent.glob("tk*"),
                 *stdlib.parent.glob("itcl*"), *stdlib.parent.glob("thread*"),
                 *libdir.glob("libtcl*"), *libdir.glob("libtk*"),
                 *(stdlib / "lib-dynload").glob("_tkinter*")]:
        total += du(path)
    return total / 2**20


def du(path):
    path = Path(path)
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file() and not p.is_symlink())


def loc(path):
    """Lines with code: no blank lines, comments or the module docstring."""
    if not path.exists():
        return None
    source = path.read_text()
    skip = set()
    tree = ast.parse(source)
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        skip.update(range(tree.body[0].lineno, tree.body[0].end_lineno + 1))
    lines = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                        tokenize.ENDMARKER):
            continue
        lines.update(range(tok.start[0], tok.end[0] + 1))
    return len(lines - skip)


# -- environment ------------------------------------------------------------------
def machine():
    cpu = "unknown"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    mesa = None
    try:
        out = subprocess.run(["dpkg-query", "-W", "-f=${Version}", "libgl1-mesa-dri"], capture_output=True, text=True)
        mesa = out.stdout.strip() or None
    except OSError:
        pass
    try:
        import tkinter

        tk = tkinter.Tcl().eval("info patchlevel")
    except Exception:  # noqa: BLE001
        tk = None
    import psutil

    return {
        "os": platform.platform(),
        "cpu": cpu,
        "cores": os.cpu_count(),
        "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "python": platform.python_version(),
        "python_build": sys.version,
        "display": "Xvfb (X virtual framebuffer, no GPU); OpenGL/Vulkan through Mesa llvmpipe/lavapipe",
        "mesa": mesa,
        "tk": tk,
    }


def start_xvfb():
    if os.environ.get("DISPLAY"):
        return None
    display = ":97"
    proc = subprocess.Popen(["Xvfb", display, "-screen", "0", "1024x768x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.environ["DISPLAY"] = display
    ENV["DISPLAY"] = display
    time.sleep(1.0)
    return proc


# -- main ----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--libs", nargs="*", default=list(LIBS))
    parser.add_argument("--runs", type=int, default=7, help="launches per toolkit and size (default 7)")
    parser.add_argument("--import-runs", type=int, default=10)
    parser.add_argument("--rows", type=int, nargs="*", default=[10, 1000])
    parser.add_argument("--updates", type=int, default=10, help="state changes timed per launch")
    parser.add_argument("--skip-sizes", action="store_true")
    parser.add_argument("--refresh", type=Path, metavar="RESULTS",
                        help="only recount lines of code and install sizes into an existing results file")
    parser.add_argument("--merge", action="store_true",
                        help="add the toolkits measured now to the existing --out file instead of replacing it")
    parser.add_argument("--out", type=Path, default=HERE / "results" / f"{dt.date.today()}.json")
    args = parser.parse_args()
    if args.refresh:
        result = json.loads(args.refresh.read_text())
        for name, entry in result["libs"].items():
            if name not in VARIANTS:
                entry["loc"] = {app: loc(APPS / name / f"{app}.py") for app in ("counter", "todo")}
                entry.update(install_sizes(name))
        result["size_only"] = {name: {"install_mb": measure_install(spec), "versions": {name: version(name)}}
                               for name, spec in SIZE_ONLY.items()}
        args.refresh.write_text(json.dumps(result, indent=2))
        return

    xvfb = start_xvfb()
    if not os.environ.get("XDG_RUNTIME_DIR"):
        runtime = Path(tempfile.mkdtemp(prefix="xdg-"))
        runtime.chmod(0o700)
        os.environ["XDG_RUNTIME_DIR"] = ENV["XDG_RUNTIME_DIR"] = str(runtime)
    screen = Screen()
    settings = vars(args) | {"out": os.path.relpath(args.out, HERE.parent)}
    out = {"date": str(dt.date.today()), "machine": machine(), "settings": settings,
           "libs": {}, "skipped": {}}
    try:
        for name in args.libs:
            module, dists, spec = LIBS[name]
            if not importable(module):
                out["skipped"][name] = f"`import {module}` failed in this environment"
                print(f"skip {name}", flush=True)
                continue
            print(f"== {name}", flush=True)
            entry = {
                "versions": {d: version(d) for d in dists} or {"tk": out["machine"]["tk"]},
                "import": measure_import(module, args.import_runs),
                "loc": {app: loc(APPS / name / f"{app}.py") for app in ("counter", "todo")} if name not in VARIANTS
                else {},
                "apps": {},
            }
            for rows in args.rows:
                runs = [measure_app(name, rows, args.updates, screen) for _ in range(args.runs)]
                entry["apps"][str(rows)] = {
                    "first_frame": summary([r["first_frame"] for r in runs]),
                    "rss": summary([r["rss"] for r in runs]),
                    "uss": summary([r["uss"] for r in runs]),
                    "update": summary([u for r in runs for u in r["update"]]),
                    "failed_runs": sum(r["first_frame"] is None for r in runs),
                    "crashed_runs": sum(r["crashed"] for r in runs),
                }
                ff = entry["apps"][str(rows)]["first_frame"]
                up = entry["apps"][str(rows)]["update"]
                print(f"   rows={rows} first_frame={ff and round(ff['median'], 3)} "
                      f"update={up and round(up['median'], 4)}", flush=True)
            if not args.skip_sizes:
                entry.update(install_sizes(name))
            out["libs"][name] = entry
        if not args.skip_sizes:
            out["size_only"] = {name: {"install_mb": measure_install(spec), "versions": {name: version(name)}}
                                for name, spec in SIZE_ONLY.items()}
    finally:
        if xvfb is not None:
            xvfb.terminate()
    if args.merge and args.out.exists():
        old = json.loads(args.out.read_text())
        old["libs"].update(out["libs"])
        old["skipped"].update(out["skipped"])
        out = old
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
