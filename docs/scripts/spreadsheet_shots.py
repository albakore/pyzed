"""Records the animated WebP illustrations of the spreadsheet docs (docs/public/media/spreadsheet/*.webp).

    python docs/scripts/spreadsheet_shots.py              # every clip
    python docs/scripts/spreadsheet_shots.py filter       # only the clips whose name contains a word
    python docs/scripts/spreadsheet_shots.py --list

The app is examples/spreadsheet.py, driven off-screen by anim_webp.py. The grid tells a double click by
the wall clock, which runs faster than the clip's, so no clip presses the same cell twice in a row
(a drag starts from the other end instead). The points are cells and
toolbar buttons of that example at 1100x600: columns start at the x of ``EDGES``, rows are 24 px high
from y=136, and the toolbar buttons sit at y=60.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "public" / "media" / "spreadsheet"
os.environ.setdefault("PYZED_CONFIG_DIR", tempfile.mkdtemp(prefix="pyzed-sheet-shots-"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from anim_webp import drag, images, key, leave, press, scroll, type_text, wait  # noqa: E402
from pyzed.recording import session  # noqa: E402
from pyzed.recording.encode import encode_webp  # noqa: E402

#: Each clip should stay under this many bytes.
TARGET = 420_000
SIZE = (1100, 600)
TABS_Y = SIZE[1] - 19


def app_class():
    spec = importlib.util.spec_from_file_location("sheet_example", ROOT / "examples" / "spreadsheet.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SpreadsheetApp


#: The left edge of each column of the example (it widens A and C).
EDGES = {"A": 46, "B": 155, "C": 255, "D": 365, "E": 465, "F": 565, "G": 665, "H": 765, "I": 865, "J": 965}


def cell(ref: str):
    """The center of a cell of the first screen (``"B3"``), with nothing scrolled or resized."""
    left = EDGES[ref[0]]
    right = EDGES.get(chr(ord(ref[0]) + 1), left + 100)
    row = int(ref[1:])
    return ((left + right) / 2, 136 + 24 * (row - 1) + 12)


def corner(ref: str):
    """The fill handle of a cell: its bottom right corner."""
    left = EDGES[ref[0]]
    right = EDGES.get(chr(ord(ref[0]) + 1), left + 100)
    return (right - 1, 136 + 24 * int(ref[1:]) - 1)


def tool(x: float):
    return (x, 60)


def enter(text: str, cps: float = 16):
    return [type_text(text, cps=cps, after=120), key("Enter", after=250)]


def clips():
    return {
        # The front page: a total that updates, a dropdown and a checkbox.
        "overview": [
            wait(400),
            drag(cell("F2"), cell("F9"), ms=600, after=700),
            press(cell("F11"), after=900),
            press((244, cell("B4")[1]), after=500),
            press((205, cell("B4")[1] + 29), after=500),
            press(cell("G4"), after=700),
            press(cell("G6"), after=900),
            leave(), wait(600),
        ],
        # Typing, Enter moving down, and a series dragged with the fill handle.
        "editing": [
            wait(300),
            press(cell("I1"), after=200),
            *enter("Week"),
            *enter("1"),
            *enter("2"),
            drag(cell("I2"), cell("I3"), ms=400, after=300),
            drag(corner("I3"), corner("I9"), ms=900, after=900),
            press(cell("J1"), after=200),
            *enter("Mon"),
            key("Up", after=200),
            drag(corner("J1"), corner("J8"), ms=900, after=900),
            leave(), wait(500),
        ],
        # A formula with suggestions and colored references, filled down.
        "formulas": [
            wait(300),
            press(cell("H1"), after=200),
            *enter("Tax"),
            type_text("=ro", cps=6, after=700),
            type_text("und(F2*0.21, 2)", cps=12, after=600),
            key("Enter", after=400),
            press(cell("H2"), after=200),
            drag(corner("H2"), corner("H9"), ms=900, after=600),
            press(cell("H5"), after=1200),
            leave(), wait(500),
        ],
        # Bold, a fill, currency, borders and a merged title, all from the toolbar.
        "formatting": [
            wait(300),
            press(cell("H2"), after=200),
            *enter("Q1 report"),
            drag(cell("J2"), cell("H2"), ms=500, after=200),
            press(tool(447), after=400),   # merge
            press(tool(274), after=300),   # bold
            press(tool(396), after=400),   # fill color
            press((533, 163), after=500),  # light blue
            press(cell("H4"), after=200),
            *enter("1250.5"),
            *enter("980"),
            *enter("1432.25"),
            drag(cell("H6"), cell("H4"), ms=400, after=300),
            press(tool(70), after=500),    # currency
            press(tool(423), after=400),   # borders
            press((477, 92), after=500),   # all borders
            press(cell("J8"), after=1000),
            leave(), wait(500),
        ],
        # A filter by values from the header's funnel, then a sort from another column's funnel.
        "filter": [
            wait(300),
            press((244, cell("B1")[1]), after=600),
            press((252, 408), after=500),  # West
            press((490, 536), after=800),  # OK
            press((654, cell("F1")[1]), after=600),
            press((700, 188), after=1000),  # Sort Z -> A
            leave(), wait(600),
        ],
        # A column dragged wider, the first column frozen too, scrolling under the header and another sheet.
        "structure": [
            wait(300),
            drag((365, 124), (430, 124), ms=700, after=500),
            press(tool(594), after=500),
            press((644, 230), after=500),  # 1 column (the example already freezes 1 row)
            press(cell("E6"), after=300),
            scroll(6, cell("E8"), ms=900), wait(700),
            scroll(-6, cell("E8"), ms=600), wait(300),
            press((121, TABS_Y), after=900),
            press((63, TABS_Y), after=600),
            leave(), wait(400),
        ],
    }


def record(name: str, steps) -> None:
    out = OUT / f"{name}.webp"
    take = session.record(app_class()(), steps, size=SIZE, scale=1, fps=20, theme="Pyzed Dark")
    frames = images(take)
    data = encode_webp(frames, fps=20, lossless=True)
    if len(data) > TARGET:
        data = encode_webp(frames, fps=20, quality=90)
    out.write_bytes(data)
    print(f"{name}: {frames[0].size[0]}x{frames[0].size[1]}, {len(frames)} frames, {len(data) / 1000:.0f} KB")
    if len(data) > TARGET:
        print(f"  {name} is over {TARGET / 1000:.0f} KB")


def toolbar() -> None:
    """A still of the toolbar, twice the size, for the component page."""
    take = session.record(app_class()(), [wait(100)], size=(1100, 120), scale=2, fps=20, theme="Pyzed Dark")
    frame = images(take, pointer=False)[-1]
    w = frame.size[0]
    still = frame.crop((0, 80, w, 160))
    data = encode_webp([still], fps=1, lossless=True)
    (OUT / "toolbar.webp").write_bytes(data)
    print(f"toolbar: {still.size[0]}x{still.size[1]}, {len(data) / 1000:.0f} KB")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("names", nargs="*", help="only clips whose name contains one of these words")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    found = clips()
    if args.list:
        print("\n".join([*found, "toolbar"]))
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, steps in found.items():
        if args.names and not any(w in name for w in args.names):
            continue
        record(name, steps)
    if not args.names or any(w in "toolbar" for w in args.names):
        toolbar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
