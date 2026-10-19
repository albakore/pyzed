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

BG = (24, 26, 31)
PANEL = (40, 44, 52)
TEXT = (220, 224, 232)
MUTED = (150, 158, 172)
BLUE = (116, 173, 232)
GREEN = (161, 193, 129)

FONTS = {
    "bold": ["/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "medium": ["/usr/share/fonts/opentype/inter/Inter-Medium.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "regular": ["/usr/share/fonts/opentype/inter/Inter-Regular.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONTS[kind]:
        if Path(path).exists():
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
    """The Pyzed logo (docs/src/assets/logo.svg) drawn with Pillow."""
    s = size / 64
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([2 * s, 2 * s, 62 * s, 62 * s], radius=14 * s, fill=(47, 52, 62))
    w = round(6 * s)
    d.line([(18 * s, 20 * s), (46 * s, 20 * s), (22 * s, 44 * s), (46 * s, 44 * s)], fill=BLUE, width=w, joint="curve")
    for x, y in [(18, 20), (46, 44)]:
        d.ellipse([(x - 3) * s, (y - 3) * s, (x + 3) * s, (y + 3) * s], fill=BLUE)
    d.ellipse([43 * s, 16 * s, 51 * s, 24 * s], fill=GREEN)
    return im


def card(shot: str, eyebrow: str, title: str, tagline: str) -> Image.Image:
    im = Image.new("RGB", (W, H), BG)
    # Soft blue glow in the top-right corner.
    glow = Image.new("RGB", (W, H), BG)
    ImageDraw.Draw(glow).ellipse([700, -350, 1500, 450], fill=(38, 58, 84))
    im = Image.blend(im, glow.filter(ImageFilter.GaussianBlur(120)), 1.0)

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
    border = Image.new("RGB", (src.width + 2, src.height + 2), (70, 76, 88))
    bmask = Image.new("L", border.size, 0)
    ImageDraw.Draw(bmask).rounded_rectangle([0, 0, border.width - 1, border.height - 1], radius=15, fill=255)
    im.paste(border, (x - 1, y - 1), bmask)
    im.paste(src, (x, y), mask)

    d = ImageDraw.Draw(im)
    lg = logo(64)
    im.paste(lg, (64, 56), lg)
    d.text((144, 64), "Pyzed", font=font("bold", 44), fill=TEXT)

    d.text((64, 170), eyebrow.upper(), font=font("medium", 20), fill=BLUE)
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
    d.text((64, H - 64), "albakore.github.io/pyzed", font=font("medium", 20), fill=GREEN)
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
        icon = logo(size * 4).resize((size, size), Image.LANCZOS)
        if name == "apple-touch-icon.png":  # iOS draws its own rounded corners: no transparency.
            flat = Image.new("RGB", (size, size), (47, 52, 62))
            flat.paste(icon, (0, 0), icon)
            icon = flat
        icon.save(DOCS / "public" / name, optimize=True)
        print(DOCS / "public" / name)


if __name__ == "__main__":
    main()
