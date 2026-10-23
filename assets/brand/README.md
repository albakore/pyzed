# Pyzed brand

The python draws the "p" and takes its place in the wordmark. Everything here is written by
`scripts/brand.py` (the paths and colors live there); run it again after changing them:

```
uv run --with resvg-py --with fonttools python scripts/brand.py
```

| File | Use |
| --- | --- |
| `pyzed-wordmark.svg`, `pyzed-wordmark-dark.svg` | Main logo on light and dark backgrounds (at least 72 px wide) |
| `pyzed-design.svg`, `pyzed-design-dark.svg` | Pyzed Design lockup |
| `pyzed-mark.svg`, `pyzed-mark-dark.svg` | The mark alone, from 24 px (navbars, title bars) |
| `pyzed-mark-small.svg` | Silhouette without eyes for 16 to 20 px |
| `pyzed-mark-black.svg`, `pyzed-mark-white.svg` | One ink |
| `app-icon.svg`, `app-icon-dark.svg`, `app-icon-*.png` | App icon, indigo and graphite |
| `app-icon-macos.svg` | App icon with macOS's margin (used for `assets/icon.icns`) |
| `favicon.svg` | Favicon that switches to the light indigo in dark mode |
| `tokens.json` | Colors (dark "Graphite", light "Paper") and type scale |

Leave clear space around the mark as wide as its head. Indigo is the brand color (`#4F46E5`
on light, `#8B83FF` on dark, `#5B50F0` for solid fills on dark); amber `#F5A524` is only for LEDs
and displays. Type is IBM Plex Sans (headings 700, subheadings 600, text 400) and IBM Plex Mono
for code, keys and labels.

`assets/icon.ico`, `assets/icon.icns` and `assets/icon.png` are the Pyzed Design icons the
installers use; `python/pyzed/brand/` holds the copies the library shows at runtime.
