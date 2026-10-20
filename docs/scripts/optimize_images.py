"""Recompresses the docs' PNGs losslessly (same pixels, smaller files) and reports what stays heavy.

    uv run --no-project --with pyoxipng python docs/scripts/optimize_images.py            # docs/src/assets, docs/screenshots
    uv run --no-project --with pyoxipng python docs/scripts/optimize_images.py docs/src/assets/shading

Run it after the shot scripts: they write PNGs quickly, not small. The pages still get WebP/AVIF,
which Astro makes from these files at build time; this keeps the repository and the build lighter.
Files over ``--warn`` KB (600 by default) are listed at the end.
"""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = [ROOT / "docs" / "src" / "assets", ROOT / "docs" / "screenshots"]


def _one(path: str, level: int) -> tuple:
    import oxipng

    before = os.path.getsize(path)
    try:
        oxipng.optimize(path, level=level, strip=oxipng.StripChunks.safe())
    except Exception as error:  # a broken file is reported, not fatal
        return path, before, before, str(error)
    return path, before, os.path.getsize(path), None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folders", nargs="*", type=Path, default=DEFAULT)
    parser.add_argument("--level", type=int, default=2, help="oxipng effort, 0-6 (default 2)")
    parser.add_argument("--warn", type=int, default=600, help="list files bigger than this many KB")
    args = parser.parse_args()
    files = sorted(str(p) for folder in args.folders for p in Path(folder).rglob("*.png"))
    total_before = total_after = 0
    with ProcessPoolExecutor() as pool:
        for path, before, after, error in pool.map(_one, files, [args.level] * len(files), chunksize=4):
            total_before += before
            total_after += after
            if error:
                print(f"failed {path}: {error}")
    print(f"{len(files)} PNGs: {total_before / 1e6:.1f} MB -> {total_after / 1e6:.1f} MB")
    heavy = sorted((os.path.getsize(f), f) for f in files if os.path.getsize(f) > args.warn * 1000)
    for size, f in reversed(heavy):
        print(f"  {size / 1000:7.0f} KB  {Path(f).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
