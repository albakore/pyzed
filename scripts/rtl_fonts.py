"""Writes the bundled right-to-left fonts: IBM Plex Sans Arabic and Hebrew, cut to their own letters.

IBM Plex Sans (the interface font) has no Arabic or Hebrew letters, so the text engine falls back to these
(``src/fonts.rs`` puts them first for those scripts). They keep only what Plex Sans lacks: the Arabic and Hebrew
blocks and their presentation forms. The zero-width and bidirectional controls (U+200B–U+200F, U+061C,
U+202A–U+202E, U+2066–U+2069) get an empty glyph: Pyzed starts some right-to-left lines with U+200F U+200B, and
Plex Sans has neither.

Run it after a new Plex release (it downloads the npm packages; fontTools is needed only here):

    uv run --with fonttools python scripts/rtl_fonts.py
"""

from __future__ import annotations

import io
import json
import tarfile
import urllib.request
from pathlib import Path

from fontTools import subset
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "fonts"
WEIGHTS = ("Regular", "Medium", "SemiBold", "Bold")
FAMILIES = {
    "Arabic": "U+0600-06FF,U+0750-077F,U+0870-08FF,U+FB50-FDFF,U+FE70-FEFF,U+25CC",
    "Hebrew": "U+0590-05FF,U+FB1D-FB4F,U+25CC",
}
CONTROLS = [0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x061C, *range(0x202A, 0x202F), *range(0x2066, 0x206A)]


def download(family: str) -> dict[str, bytes]:
    """The .woff files of ``@ibm/plex-sans-<family>`` from npm, by weight."""
    package = f"@ibm/plex-sans-{family.lower()}"
    meta = json.load(urllib.request.urlopen(f"https://registry.npmjs.org/{package}"))
    version = meta["dist-tags"]["latest"]
    data = urllib.request.urlopen(meta["versions"][version]["dist"]["tarball"]).read()
    fonts = {}
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for weight in WEIGHTS:
            name = f"package/fonts/complete/woff/IBMPlexSans{family}-{weight}.woff"
            fonts[weight] = tar.extractfile(name).read()
    print(f"{package} {version}")
    return fonts


def add_controls(font: TTFont) -> None:
    """Maps the bidirectional controls to one empty glyph with no advance."""
    name = "bidi.control"
    order = font.getGlyphOrder()
    if name not in order:
        font.setGlyphOrder([*order, name])
        font["glyf"][name] = TTGlyphPen(None).glyph()
        font["hmtx"][name] = (0, 0)
    for table in font["cmap"].tables:
        if table.isUnicode():
            for code in CONTROLS:
                table.cmap.setdefault(code, name)


def main() -> None:
    for family, unicodes in FAMILIES.items():
        for weight, woff in download(family).items():
            options = subset.Options()
            options.layout_features = ["*"]
            options.hinting = False
            # Every name: weights other than Regular and Bold carry their family in the typographic names
            # (IDs 16 and 17), and without them "IBM Plex Sans Arabic" at 500 or 600 was not found.
            options.name_IDs = ["*"]
            options.name_languages = ["*"]
            font = TTFont(io.BytesIO(woff))
            subsetter = subset.Subsetter(options)
            subsetter.populate(unicodes=subset.parse_unicodes(unicodes))
            subsetter.subset(font)
            add_controls(font)
            font.flavor = None  # plain TrueType: the text engine doesn't read WOFF
            path = OUT / f"IBMPlexSans{family}-{weight}.ttf"
            font.save(path)
            print(f"  {path.relative_to(ROOT)} {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
