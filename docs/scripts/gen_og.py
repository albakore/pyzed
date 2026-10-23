"""Generate the 1200x630 social cards (Open Graph / Twitter) in docs/public/og/ and the app icons.

One card per site section and language, composed with Pillow from the screenshots already in
the docs. ``src/routeData.ts`` picks the card for each page from its slug.

    python docs/scripts/gen_og.py

Re-run it when the screenshots or the taglines change; the PNGs are committed.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

DOCS = Path(__file__).resolve().parent.parent
OUT = DOCS / "public" / "og"
W, H = 1200, 630

# The brand's dark palette ("Graphite", assets/brand/tokens.json).
BG = (13, 14, 17)
BORDER = (42, 47, 57)
TEXT = (231, 233, 238)
MUTED = (154, 161, 174)
INDIGO = (139, 131, 255)
INDIGO_SOLID = (79, 70, 229)
AMBER = (245, 181, 71)
LED = (245, 165, 36)

BRAND = DOCS.parent / "assets" / "brand"
FONT_DIR = DOCS.parent / "assets" / "fonts"
FONTS = {
    "bold": [FONT_DIR / "IBMPlexSans-Bold.ttf", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")],
    "regular": [FONT_DIR / "IBMPlexSans-Regular.ttf", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")],
    "mono": [FONT_DIR / "IBMPlexMono-Medium.ttf", Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")],
}


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONTS[kind]:
        if path.exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


# key: (screenshot, {lang: (eyebrow, title, tagline)})
CARDS = {
    "default": ("screenshots/designer.png", {
        "en": ("Python desktop GUI framework", "Native desktop apps in pure Python",
               "Rendered by Rust (Iced) · Zed-style components · visual designer · Windows, macOS, Linux"),
        "es": ("Framework de GUI de escritorio para Python", "Apps de escritorio nativas en Python puro",
               "Renderizado en Rust (Iced) · componentes estilo Zed · diseñador visual · Windows, macOS, Linux"),
    }),
    "design": ("screenshots/designer-component.png", {
        "en": ("Pyzed Design", "Drag-and-drop visual designer for Python",
               "Draw forms and components, wire events to Python, run them with F5"),
        "es": ("Pyzed Design", "Diseñador visual de arrastrar y soltar para Python",
               "Dibuja formularios y componentes, conecta eventos a Python y ejecútalos con F5"),
    }),
    "library": ("screenshots/components-dark.png", {
        "en": ("Component library", "90+ Zed-style UI components",
               "Buttons, tables, trees, editors, charts, dialogs, palettes - with previews and code"),
        "es": ("Biblioteca de componentes", "Más de 90 componentes de UI estilo Zed",
               "Botones, tablas, árboles, editores, gráficos, diálogos y paletas, con vista previa y código"),
    }),
    "guides": ("src/assets/tutorials/effects.png", {
        "en": ("Guides", "Layout, styles, animation and effects",
               "Glow, bloom, glass, blur, themes, async, windows, packaging and testing"),
        "es": ("Guías", "Layout, estilos, animación y efectos",
               "Glow, bloom, glass, desenfoque, temas, async, ventanas, empaquetado y tests"),
    }),
    "tutorials": ("src/assets/tutorials/mini-editor.png", {
        "en": ("Tutorials", "Build real desktop apps step by step",
               "From a first window to a Zed-like code editor, in pure Python"),
        "es": ("Tutoriales", "Crea apps de escritorio reales paso a paso",
               "De una primera ventana a un editor de código como Zed, en Python puro"),
    }),
    "ai": ("screenshots/designer-agent.png", {
        "en": ("AI agents", "AI-native Python GUI development",
               "Agent panel, MCP server, llms.txt and pyzed.agents for model-powered apps"),
        "es": ("Agentes de IA", "Desarrollo de GUI en Python pensado para la IA",
               "Panel del agente, servidor MCP, llms.txt y pyzed.agents para apps con modelos"),
    }),
    "why": ("screenshots/designer-code.png", {
        "en": ("Why Pyzed", "A modern alternative to tkinter, Kivy and PyQt",
               "GPU-rendered, native, fast to start - built for a new generation of Python developers"),
        "es": ("Por qué Pyzed", "Una alternativa moderna a tkinter, Kivy y PyQt",
               "Renderizado por GPU, nativo y rápido, pensado para una nueva generación de desarrolladores"),
    }),
}


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def logo(size: int) -> Image.Image:
    """The Pyzed app icon (assets/brand/app-icon-1024.png, made by scripts/brand.py) at ``size`` pixels."""
    return Image.open(BRAND / "app-icon-1024.png").convert("RGBA").resize((size, size), Image.LANCZOS)


def card(shot: str, eyebrow: str, title: str, tagline: str) -> Image.Image:
    im = Image.new("RGB", (W, H), BG)
    # The dotted grid of the designer's canvas, behind the screenshot.
    grid = ImageDraw.Draw(im)
    for gx in range(560, W, 24):
        for gy in range(8, H, 24):
            grid.ellipse([gx - 1, gy - 1, gx + 1, gy + 1], fill=(38, 42, 51))

    # Screenshot, tilted out of the right edge.
    src = Image.open(DOCS / shot).convert("RGB")
    sw = 760
    src = src.resize((sw, round(src.height * sw / src.width)), Image.LANCZOS)
    mask = Image.new("L", src.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, src.width - 1, src.height - 1], radius=14, fill=255)
    shadow = Image.new("L", (src.width + 80, src.height + 80), 0)
    ImageDraw.Draw(shadow).rounded_rectangle([40, 50, src.width + 40, src.height + 50], radius=18, fill=170)
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    x, y = 600, 205
    im.paste((0, 0, 0), (x - 40, y - 40), shadow)
    border = Image.new("RGB", (src.width + 2, src.height + 2), BORDER)
    bmask = Image.new("L", border.size, 0)
    ImageDraw.Draw(bmask).rounded_rectangle([0, 0, border.width - 1, border.height - 1], radius=15, fill=255)
    im.paste(border, (x - 1, y - 1), bmask)
    im.paste(src, (x, y), mask)

    d = ImageDraw.Draw(im)
    lg = logo(60)
    im.paste(lg, (64, 58), lg)
    d.text((140, 62), "pyzed", font=font("bold", 44), fill=TEXT)

    d.text((64, 170), eyebrow.upper(), font=font("mono", 19), fill=INDIGO)
    y = 206
    tf = font("bold", 50)
    for line in wrap(d, title, tf, 500)[:4]:
        d.text((64, y), line, font=tf, fill=TEXT)
        y += 60
    y += 14
    gf = font("regular", 23)
    for line in wrap(d, tagline, gf, 500)[:4]:
        d.text((64, y), line, font=gf, fill=MUTED)
        y += 32
    d.ellipse([64, H - 57, 74, H - 47], fill=LED)
    d.text((86, H - 64), "albakore.github.io/pyzed", font=font("mono", 19), fill=AMBER)
    return im


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for key, (shot, langs) in CARDS.items():
        for lang, (eyebrow, title, tagline) in langs.items():
            name = f"{key}.png" if lang == "en" else f"{key}.{lang}.png"
            img = card(shot, eyebrow, title, tagline)
            img = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
            img.save(OUT / name, optimize=True)
            print(OUT / name)
    # App icons for manifest.webmanifest and iOS home screens.
    for size, name in [(192, "icon-192.png"), (512, "icon-512.png"), (180, "apple-touch-icon.png")]:
        icon = logo(size)
        if name == "apple-touch-icon.png":  # iOS draws its own rounded corners: no transparency.
            flat = Image.new("RGB", (size, size), INDIGO_SOLID)
            flat.paste(icon, (0, 0), icon)
            icon = flat
        icon.save(DOCS / "public" / name, optimize=True)
        print(DOCS / "public" / name)


if __name__ == "__main__":
    main()
