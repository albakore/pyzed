# Benchmarks: Pyzed and other Python GUI toolkits

Reproducible measurements of Pyzed next to tkinter, CustomTkinter, PySide6 (Qt), Kivy, Dear PyGui, Flet
and Toga. The results and charts are published at
<https://albakore.github.io/pyzed/why/benchmarks/>.

```
benchmarks/
├── run.py            # the harness: runs everything, writes results/<date>.json
├── apps/
│   ├── benchkit.py   # shared plumbing for the bench apps (sizes, colors, stdin "go")
│   └── <toolkit>/
│       ├── bench.py    # N rows (label + button) in a scroll area, above a colored footer
│       ├── counter.py  # reference app: -, + and Reset
│       └── todo.py     # reference app: add, tick off, delete, count
└── results/
    └── <date>.json   # raw samples + medians, machine and versions
```

## Run it

Use a virtual environment of its own (do not install all these toolkits into your project):

```bash
uv venv --python 3.13 .bench && source .bench/bin/activate
uv pip install pyzed-ui pyside6 kivy dearpygui "flet[desktop]" toga customtkinter psutil mss numpy
python benchmarks/run.py                 # all toolkits, 7 launches each (see below for the time)
python benchmarks/run.py --libs pyzed tkinter --runs 3
```

- Use a Python from [python-build-standalone](https://github.com/astral-sh/python-build-standalone) (what
  `uv python install` gives you) or install your distribution's `python3-tk`, so tkinter is available.
- Toga needs GTK and, to build PyGObject, `libgirepository-2.0-dev` and `libcairo2-dev` on Debian/Ubuntu.
- Flet downloads its desktop client to `~/.flet` the first time an app runs.
- Without a `DISPLAY`, the harness starts `Xvfb :97` (1024×768, 24-bit). On a desktop it uses your screen:
  keep the windows uncovered while it runs.
- A full run took about 80 minutes here, most of it Toga's 1,000-row updates (about 37 s each).
- `pyzed-cpu` is the Pyzed bench app started with `ICED_BACKEND=tiny-skia` (Iced's CPU renderer instead of
  wgpu). `--merge` adds the toolkits you measure now to an existing `--out` file.
- `--skip-sizes` skips the install-size step (it creates throwaway virtual environments with `uv`).
- `--refresh results/<date>.json` recounts only the lines of code and the install sizes.

## What is measured

| Metric | How |
| --- | --- |
| **Import** | `import <toolkit>` timed with `perf_counter` inside a fresh interpreter, 10 times after one warm-up (the OS file cache is warm). |
| **First frame** | From `Popen` of `apps/<toolkit>/bench.py N` to the moment the harness sees the app's 40 px footer, painted in a sentinel color, on the screen. The screen is grabbed with `mss` every ~1 ms and a frame counts once 8,000 pixels match (±4 per channel). Includes interpreter start, imports, building N rows and drawing. |
| **Memory** | RSS and USS of the app's process **tree** (Flet draws in a child process) 1 s after the first frame, with `psutil`. |
| **Update** | After the first frame the harness writes `go` to the app's stdin. On each 250 ms timer tick the app prints `T <k> <time.monotonic()>`, rewrites the text of all N labels and flips the footer color in the same update. Latency = monotonic time at which the harness sees the new color minus the app's timestamp. 10 updates per launch. |
| **Install size** | Growth of a fresh `uv venv` after `uv pip install --link-mode=copy <package>` (dependencies included, the uv cache excluded). tkinter: the Tcl/Tk files that ship with the interpreter. Flet: plus its desktop client in `~/.flet/client`. Toga: system GTK libraries are not counted. |
| **Lines of code** | Lines of `counter.py` and `todo.py` that are not blank, comments or the module docstring (counted with `tokenize`). |

Each scenario (10 rows and 1,000 rows) is launched 7 times; the JSON keeps every sample with median,
min, max and standard deviation.

### The bench app

Every `bench.py` builds the same window: 640×480, a scrollable area with N rows of *label + "Open" button*,
one real widget per row (no virtualization, no lazy lists: Kivy uses a `GridLayout` instead of a
`RecycleView`, Flet a scrolling `Column` instead of a `ListView`), and a footer bar. Each one is written the
plain way that toolkit's documentation shows.

## Caveats

- **No GPU.** Unless you run it on a desktop, everything renders in software: Mesa llvmpipe (OpenGL) and
  lavapipe (Vulkan) on the CPU. That penalizes the GPU toolkits (Pyzed, Kivy, Dear PyGui, Flet) and favors
  the ones that draw on the CPU anyway (tkinter, Qt Widgets, GTK). On real hardware the GPU toolkits'
  drawing cost mostly moves off the CPU.
- **The harness shares the CPU.** Grabbing the screen costs about one core while it polls.
- **What "first frame" sees.** The footer is the last widget, but toolkits that draw widget by widget
  (Tk) may show it slightly before every row is painted. GPU toolkits present whole frames.
- **Update latency includes the polling interval** (≈1 ms plus a screen grab) and the app's own redraw
  scheduling; Dear PyGui redraws continuously, so its latency includes waiting for the next frame.
- **Dear PyGui and Flet keep the CPU busy when idle** differently from event-driven toolkits; that is not
  measured here.
- **Not measured:** wxPython (no Linux wheels on PyPI; building it from source was not practical here) and
  NiceGUI (it draws in a web browser, so a desktop window timing would measure the browser; only its
  install size is reported).
- **CustomTkinter has no 1,000-row results.** Its app dies under Xvfb with an X error (BadAlloc or BadValue
  from `CreatePixmap`) once the `CTkScrollableFrame` holds more than about 100 rows, probably because it draws
  every frame on a Tk canvas, so the inner frame becomes one very tall canvas. A real X server may behave
  differently; we report what happened here.
- Line counts depend on style. The apps follow each toolkit's documented idioms; improvements are welcome.
