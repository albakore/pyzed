"""Writes Pyzed's brand files (the mark, the wordmark, the app icons and the color tokens) to assets/brand.

The python draws the "p": its body is the snake's spine, its head the bowl. Three cuts of it:

* ``BODY`` + ``HEAD`` (with eyes): the mark, from 24 pixels up.
* ``BODY`` + ``HEAD_PLAIN`` (no eyes): the silhouette for 16 to 20 pixels.
* ``WORD_BODY`` + ``WORD_HEAD``: a heavier cut that replaces the "p" of the wordmark; its spine matches the x-height
  of IBM Plex Sans Bold and its tail drops like a descender.

Run it after changing a path or a color (it needs resvg and fontTools only here, not at runtime):

    uv run --with resvg-py --with fonttools python scripts/brand.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "brand"
PACKAGE = ROOT / "python" / "pyzed" / "brand"

BODY = (
    'M34.6 108L35.6 105.3L36.5 102.7L37.3 100L38 97.3L38.6 94.7L39.2 92L39.7 89.3L40.1 86.7L40.4 84L40.7 '
    '81.3L40.9 78.7L41 76L41 73.3L41 70.7L41 68L41 65.3L41 62.7L41 60L41 57.3L41 54.7L41 52L41 49.3L41 '
    '46.7L41 44.1L41 42.8L41.2 41.5L41.4 40.3L41.6 39.1L42 37.9L42.4 36.7L43 35.6L43.5 34.5L44.2 33.4L44.9 '
    '32.4L45.7 31.5L46.6 30.6L47.5 29.7L48.4 28.9L49.4 28.2L50.5 27.5L51.6 27L52.7 26.4L53.9 26L55.1 '
    '25.6L56.3 25.4L57.5 25.2L58.8 25L60 25L61.2 25L62.5 25.2L63.7 25.4L64.9 25.6L66.1 26L67.3 26.4L68.4 '
    '27L69.5 27.5L70.6 28.2L71.6 28.9L72.5 29.7L73.4 30.6L74.3 31.5L75.1 32.4L75.8 33.4L76.5 34.5L77 '
    '35.6L77.6 36.7L78 37.9L78.4 39.1L78.6 40.3L78.8 41.5L79 42.8L79 44L79 45.2L78.8 46.5L78.6 47.7L78.4 '
    '48.9L78 50.1L77.6 51.3L77 52.4L76.5 53.5L75.8 54.6L75.1 55.6L74.3 56.5L73.4 57.4L72.5 58.3L71.6 '
    '59.1L70.6 59.8L69.5 60.5L69.3 60.5L69.2 60.6L69 60.7L68.9 60.8L68.7 60.9L68.5 61L68.2 61.1L68 61.2L67.7 '
    '61.2L67.4 61.2L67.1 61.2L66.8 61.1L66.5 61L66.2 60.8L65.9 60.6L65.7 60.3L65.4 60.1L65.3 59.7L65.1 '
    '59.4L65.1 58.9L65 58L65 57L55 57L55 58L54.9 59.1L55 60.5L55.1 61.9L55.4 63.3L55.8 64.7L56.4 66.1L57.1 '
    '67.4L58 68.7L58.9 69.8L60 70.9L61.3 71.8L62.6 72.7L64 73.3L65.5 73.9L67.1 74.2L68.7 74.4L70.3 74.4L71.9 '
    '74.2L73.5 73.9L75 73.3L76.5 72.6L78.3 71.4L80.1 70.2L81.8 68.8L83.3 67.3L84.8 65.8L86.2 64.1L87.4 '
    '62.3L88.6 60.5L89.6 58.6L90.5 56.6L91.2 54.6L91.9 52.5L92.4 50.4L92.7 48.3L92.9 46.2L93 44L92.9 '
    '41.8L92.7 39.7L92.4 37.6L91.9 35.5L91.2 33.4L90.5 31.4L89.6 29.4L88.6 27.5L87.4 25.7L86.2 23.9L84.8 '
    '22.2L83.3 20.7L81.8 19.2L80.1 17.8L78.3 16.6L76.5 15.4L74.6 14.4L72.6 13.5L70.6 12.8L68.5 12.1L66.4 '
    '11.6L64.3 11.3L62.2 11.1L60 11L57.8 11.1L55.7 11.3L53.6 11.6L51.5 12.1L49.4 12.8L47.4 13.5L45.4 '
    '14.4L43.5 15.4L41.7 16.6L39.9 17.8L38.2 19.2L36.7 20.7L35.2 22.2L33.8 23.9L32.6 25.7L31.4 27.5L30.4 '
    '29.4L29.5 31.4L28.8 33.4L28.1 35.5L27.6 37.6L27.3 39.7L27.1 41.8L27 43.9L27 46.7L27 49.3L27 52L27 '
    '54.7L27 57.3L27 60L27 62.7L27 65.3L27 68L27 70.7L27 73.3L27 76L27.1 78.7L27.3 81.3L27.6 84L27.9 '
    '86.7L28.3 89.3L28.8 92L29.4 94.7L30 97.3L30.7 100L31.5 102.7L32.4 105.3L33.4 108Z'
)
HEAD = (
    'M55 58.5L55 55.2Q55 54 54.2 53.2L51.2 49.6Q50.2 48.4 50.6 46.9L54.6 34.2Q55.3 32 57.6 32L62.4 32Q64.7 '
    '32 65.4 34.2L69.4 46.9Q69.8 48.4 68.8 49.6L65.8 53.2Q65 54 65 55.2L65 58.5Z M52.63 46.44C52.9 43.74 '
    '53.98 40.5 56.41 40.09C58.3 39.83 58.98 41.58 58.3 43.2C57.49 45.09 55.33 46.03 52.63 46.44ZM67.37 '
    '46.44C67.1 43.74 66.02 40.5 63.59 40.09C61.7 39.83 61.02 41.58 61.7 43.2C62.51 45.09 64.67 46.03 67.37 '
    '46.44Z'
)
HEAD_PLAIN = (
    'M55 58.5L55 55.2Q55 54 54.2 53.2L51.2 49.6Q50.2 48.4 50.6 46.9L54.6 34.2Q55.3 32 57.6 32L62.4 32Q64.7 '
    '32 65.4 34.2L69.4 46.9Q69.8 48.4 68.8 49.6L65.8 53.2Q65 54 65 55.2L65 58.5Z'
)
WORD_BODY = (
    'M33 108L35.5 105.3L37.5 102.7L39.2 100L40.5 97.3L41.4 94.7L41.9 92L42 89.3L42 86.7L42 84L42 81.3L42 '
    '78.7L42 76L42 73.3L42 70.7L42 68L42 65.3L42 62.7L42 60L42 57.3L42 54.7L42 52L42 49.3L42 46.7L42 44.1L42 '
    '43L42.1 41.9L42.3 40.9L42.5 39.8L42.8 38.8L43.1 37.8L43.5 36.9L43.9 35.9L44.4 35L45 34.1L45.6 33.3L46.2 '
    '32.4L46.9 31.6L47.6 30.9L48.4 30.2L49.3 29.6L50.1 29L51 28.4L51.9 27.9L52.9 27.5L53.8 27.1L54.8 '
    '26.8L55.8 26.5L56.9 26.3L57.9 26.1L59 26L60 26L61 26L62.1 26.1L63.1 26.3L64.2 26.5L65.2 26.8L66.2 '
    '27.1L67.1 27.5L68.1 27.9L69 28.4L69.9 29L70.7 29.6L71.6 30.2L72.4 30.9L73.1 31.6L73.8 32.4L74.4 33.3L75 '
    '34.1L75.6 35L76.1 35.9L76.5 36.9L76.9 37.8L77.2 38.8L77.5 39.8L77.7 40.9L77.9 41.9L78 43L78 44L78 45L78 '
    '46.1L78 47.2L78 48.3L78 49.4L77.9 50.5L77.8 51.7L77.6 52.8L77.3 54L77 55.2L76.6 56.3L76.1 57.5L75.5 '
    '58.6L74.8 59.6L74 60.6L73.1 61.5L72.1 62.4L71 63L70.8 63.2L70.5 63.4L70.3 63.5L70 63.6L69.7 63.7L69.3 '
    '63.8L69 63.8L68.7 63.8L68.4 63.7L68 63.6L67.7 63.5L67.4 63.3L67.1 63.1L66.8 62.8L66.5 62.6L66.3 '
    '62.2L66.1 61.9L65.9 61.5L65.8 61.1L65.7 60.6L65.6 58.9L65.5 57L54.5 57L54.4 58.9L54.3 60.8L54.3 '
    '62.4L54.5 64L54.8 65.6L55.4 67.1L56.1 68.6L56.9 70L57.9 71.3L59 72.6L60.3 73.7L61.6 74.6L63.1 75.4L64.7 '
    '76.1L66.3 76.6L68 76.9L69.7 77.1L71.4 77.1L73.1 76.9L74.8 76.5L76.4 75.9L78 75.2L79.8 74.1L81.6 73L83.3 '
    '71.8L85.1 70.6L86.7 69.2L88.4 67.8L90 66.3L91.5 64.7L92.9 63L94.3 61.2L95.5 59.3L96.6 57.3L97.6 '
    '55.3L98.4 53.1L99.1 50.9L99.6 48.6L99.9 46.3L100 44L99.9 41.7L99.7 39.4L99.4 37.1L98.9 34.8L98.3 '
    '32.5L97.6 30.3L96.7 28.2L95.7 26L94.6 24L93.4 22L92.1 20.1L90.6 18.3L89.1 16.6L87.4 14.9L85.7 13.4L83.9 '
    '11.9L82 10.6L80 9.4L78 8.3L75.8 7.3L73.7 6.4L71.5 5.7L69.2 5.1L66.9 4.6L64.6 4.3L62.3 4.1L60 4L57.7 '
    '4.1L55.4 4.3L53.1 4.6L50.8 5.1L48.5 5.7L46.3 6.4L44.2 7.3L42 8.3L40 9.4L38 10.6L36.1 11.9L34.3 '
    '13.4L32.6 14.9L30.9 16.6L29.4 18.3L27.9 20.1L26.6 22L25.4 24L24.3 26L23.3 28.2L22.4 30.3L21.7 32.5L21.1 '
    '34.8L20.6 37.1L20.3 39.4L20.1 41.7L20 43.9L20 46.7L20 49.3L20 52L20 54.7L20 57.3L20 60L20 62.7L20 '
    '65.3L20 68L20 70.7L20 73.3L20 76L20 78.7L20 81.3L20 84L20 86.7L20 89.3L20.1 92L20.6 94.7L21.5 97.3L22.8 '
    '100L24.5 102.7L26.5 105.3L29 108Z'
)
WORD_HEAD = (
    'M54.5 58.5L54.5 54.87Q54.5 53.55 53.62 52.67L50.32 48.71Q49.22 47.39 49.66 45.74L54.06 31.77Q54.83 '
    '29.35 57.36 29.35L62.64 29.35Q65.17 29.35 65.94 31.77L70.34 45.74Q70.78 47.39 69.68 48.71L66.38 '
    '52.67Q65.5 53.55 65.5 54.87L65.5 58.5Z M51.89 45.23C52.19 42.26 53.38 38.7 56.05 38.25C58.13 37.96 '
    '58.88 39.89 58.13 41.67C57.24 43.75 54.86 44.78 51.89 45.23ZM68.11 45.23C67.81 42.26 66.62 38.7 63.95 '
    '38.25C61.87 37.96 61.12 39.89 61.87 41.67C62.76 43.75 65.14 44.78 68.11 45.23Z'
)

#: The palette: graphite surfaces in layers like a code editor, indigo for the brand and amber kept for LEDs and
#: displays, in the language of an audio rack's panels. ``pyzed.theme_palettes`` builds the themes from it.
TOKENS = {
    "dark": {
        "name": "Graphite", "background": "#0D0E11", "surface": "#14161B", "panel": "#191C22",
        "raised": "#222630", "border": "#2A2F39", "text": "#E7E9EE", "muted": "#9AA1AE", "faint": "#5C6370",
        "accent": "#8B83FF", "accent_solid": "#5B50F0", "on_accent": "#FFFFFF",
        "accent_tint": "#8B83FF1F", "accent_line": "#8B83FF52",
        "amber": "#F5A524", "amber_text": "#F5B547", "led_off": "#3A3F4A", "green": "#3FCF8E", "pink": "#FF6B9A",
        "lcd": "#07080A", "lcd_line": "#2A2F39", "lcd_text": "#F5B547", "lcd_dim": "#8A6420",
        "canvas": "#101216", "grid": "#262A33", "rack": "#111317",
        "code_keyword": "#B4A9FF", "code_function": "#6FC3FF", "code_string": "#9FD88B", "code_number": "#F5B547",
        "code_comment": "#7C8491",
    },
    "light": {
        "name": "Paper", "background": "#F6F7F9", "surface": "#FFFFFF", "panel": "#F1F3F6",
        "raised": "#E7EAF0", "border": "#DCE0E7", "text": "#14161B", "muted": "#576070", "faint": "#9AA1AE",
        "accent": "#4F46E5", "accent_solid": "#4F46E5", "on_accent": "#FFFFFF",
        "accent_tint": "#EEF0FF", "accent_line": "#C9CCFB",
        "amber": "#F5A524", "amber_text": "#8A5300", "led_off": "#C9CED8", "green": "#12805C", "pink": "#E0457B",
        "lcd": "#14161B", "lcd_line": "#2A2F39", "lcd_text": "#F5B547", "lcd_dim": "#8A6420",
        "canvas": "#EEF0F4", "grid": "#CDD3DC", "rack": "#ECEEF2",
        "code_keyword": "#6D28D9", "code_function": "#0B6BCB", "code_string": "#2F7D32", "code_number": "#9A5B00",
        "code_comment": "#6B7280",
    },
    "typography": {
        "sans": "IBM Plex Sans", "mono": "IBM Plex Mono",
        "display": {"size": 64, "line_height": 68, "weight": 700, "letter_spacing": "-0.03em"},
        "title": {"size": 40, "line_height": 46, "weight": 700, "letter_spacing": "-0.025em"},
        "body": {"size": 16, "line_height": 26, "weight": 400},
        "code": {"size": 13, "weight": 500, "use": "code, kbd and labels"},
        "wordmark": {"weight": 700, "letter_spacing": "-0.045em"},
    },
}

INDIGO, INDIGO_DARK, INK, PAPER = "#4F46E5", "#8B83FF", "#14161B", "#E7E9EE"
GRAPHITE, GRAPHITE_LINE = "#0D0E11", "#2A2F39"


def svg(view_box: str, body: str, *, width: float = 0, height: float = 0, title: str = "Pyzed") -> str:
    size = f' width="{width:g}" height="{height:g}"' if width else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}"{size} role="img">'
            f"<title>{title}</title>{body}</svg>\n")


def mark(color: str, *, plain: bool = False) -> str:
    """The mark's paths in the 0 0 120 120 box."""
    head = HEAD_PLAIN if plain else HEAD
    return (f'<path d="{BODY}" fill="{color}"/>'
            f'<path d="{head}" fill="{color}" fill-rule="evenodd"/>')


def icon(background: str, color: str, *, size: int = 1024, padded: bool = False, plain: bool = False,
         line: str = "") -> str:
    """The app icon: the mark on a rounded square (``padded`` leaves macOS's margin around it)."""
    box = size * 0.805 if padded else size
    offset = (size - box) / 2
    radius = box * 30 / 128
    stroke = f' stroke="{line}" stroke-width="{box / 128:g}"' if line else ""
    inset = box / 256 if line else 0
    glyph = box * 96 / 128 / 120
    body = (f'<rect x="{offset + inset:g}" y="{offset + inset:g}" width="{box - 2 * inset:g}" '
            f'height="{box - 2 * inset:g}" rx="{radius:g}" fill="{background}"{stroke}/>'
            f'<g transform="translate({offset + box / 8:g} {offset + box / 8:g}) scale({glyph:g})">'
            f"{mark(color, plain=plain)}</g>")
    return svg(f"0 0 {size} {size}", body, title="Pyzed")


def wordmark(text_color: str, p_color: str, *, suffix: str = "", suffix_color: str = "") -> str:
    """'pyzed' in IBM Plex Sans Bold with the python as its "p" (and an optional lighter ``suffix``)."""
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont

    def font(name):
        return TTFont(ROOT / "assets" / "fonts" / name)

    def run(face, text, x, spacing):
        glyphs, cmap = face.getGlyphSet(), face.getBestCmap()
        pen, bounds = SVGPathPen(glyphs), BoundsPen(glyphs)
        for char in text:
            name = cmap[ord(char)]
            for target in (pen, bounds):
                glyphs[name].draw(TransformPen(target, (1, 0, 0, -1, x, 0)))
            x += glyphs[name].width + spacing
        return pen.getCommands(), bounds.bounds, x - spacing

    # in font units (1000 per em) around the baseline (y = 0): the "p" is 0.547 em wide, 0.164 em below it
    scale = 547 / 80
    p_body = (f'<g transform="translate(0 -547) scale({scale:g}) translate(-20 -4)" fill="{p_color}">'
              f'<path d="{WORD_BODY}"/><path d="{WORD_HEAD}" fill-rule="evenodd"/></g>')
    bold = font("IBMPlexSans-Bold.ttf")
    word, (_, top, _, bottom), end = run(bold, "yzed", 567, -45)
    body = p_body + f'<path d="{word}" fill="{text_color}"/>'
    if suffix:
        regular = font("IBMPlexSans-Regular.ttf")
        extra, (_, top2, _, bottom2), end = run(regular, suffix, end + 250, -20)
        body += f'<path d="{extra}" fill="{suffix_color}"/>'
        top, bottom = min(top, top2), max(bottom, bottom2)
    top, bottom = min(top, -547), max(bottom, 164)
    return svg(f"0 {top:g} {end:g} {bottom - top:g}", body)


def files() -> dict:
    tight = "22 6 76 108"
    return {
        "pyzed-mark.svg": svg(tight, mark(INDIGO)),
        "pyzed-mark-dark.svg": svg(tight, mark(INDIGO_DARK)),
        "pyzed-mark-black.svg": svg(tight, mark(INK)),
        "pyzed-mark-white.svg": svg(tight, mark("#FFFFFF")),
        "pyzed-mark-small.svg": svg("0 0 120 120", mark(INDIGO, plain=True)),
        "pyzed-wordmark.svg": wordmark(INK, INDIGO),
        "pyzed-wordmark-dark.svg": wordmark(PAPER, INDIGO_DARK),
        "pyzed-design.svg": wordmark(INK, INDIGO, suffix="design", suffix_color="#576070"),
        "pyzed-design-dark.svg": wordmark(PAPER, INDIGO_DARK, suffix="design", suffix_color="#9AA1AE"),
        "app-icon.svg": icon(INDIGO, "#FFFFFF"),
        "app-icon-dark.svg": icon(GRAPHITE, INDIGO_DARK, line=GRAPHITE_LINE),
        "app-icon-macos.svg": icon(INDIGO, "#FFFFFF", padded=True),
        "favicon.svg": svg("8 8 104 104", (
            "<style>path{fill:#4F46E5}@media (prefers-color-scheme: dark){path{fill:#8B83FF}}</style>"
            f'<path d="{BODY}"/><path d="{HEAD}" fill-rule="evenodd"/>')),
    }


def _appicon():
    # loaded from its file: importing pyzed would need the compiled core
    spec = importlib.util.spec_from_file_location("_appicon", ROOT / "python" / "pyzed" / "_appicon.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    import resvg_py

    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in files().items():
        (OUT / name).write_text(text, encoding="utf-8")
    (OUT / "tokens.json").write_text(json.dumps(TOKENS, indent=2) + "\n", encoding="utf-8")

    def png(text: str, size: int) -> bytes:
        return bytes(resvg_py.svg_to_bytes(svg_string=text, width=size, height=size))

    full, padded = icon(INDIGO, "#FFFFFF"), icon(INDIGO, "#FFFFFF", padded=True)
    small = icon(INDIGO, "#FFFFFF", plain=True)  # the eyes blur below 24 pixels
    for size in (1024, 512, 256):
        (OUT / f"app-icon-{size}.png").write_bytes(png(full, size))
    appicon = _appicon()
    ico = {size: png(small if size < 24 else full, size) for size in appicon.ICO_SIZES}
    icns = {size: png(padded, size) for _, size in appicon.ICNS_TYPES}
    (ROOT / "assets" / "icon.ico").write_bytes(appicon.ico(ico))
    (ROOT / "assets" / "icon.icns").write_bytes(appicon.icns(icns))
    (ROOT / "assets" / "icon.png").write_bytes(png(full, 512))
    # what the library itself shows: the window icon of Pyzed Design and the marks of its title bar and welcome
    PACKAGE.mkdir(parents=True, exist_ok=True)
    (PACKAGE / "icon.png").write_bytes(png(full, 256))
    for name in ("pyzed-mark.svg", "pyzed-mark-dark.svg", "pyzed-wordmark.svg", "pyzed-wordmark-dark.svg"):
        (PACKAGE / name).write_text((OUT / name).read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Wrote {len(files()) + 4} files to {OUT.relative_to(ROOT)} and the icons to assets/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
