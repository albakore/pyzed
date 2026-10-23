---
title: Brand
description: "The Pyzed brand: the python logo and wordmark, app icons, the Graphite and Paper color palettes, IBM Plex type and how the docs site uses them."
sidebar:
  order: 7
---

The python draws the "p" of Pyzed and takes its place in the wordmark. Its back matches the x-height of IBM Plex
Sans and its tail drops like a descender. The logo files, the app icons and the color tokens live in
[`assets/brand`](https://github.com/albakore/pyzed/tree/main/assets/brand); `scripts/brand.py` writes all of them
from the same paths and colors.

## Logo

| File | Use |
| --- | --- |
| `pyzed-wordmark.svg`, `pyzed-wordmark-dark.svg` | The main logo, on light and dark backgrounds (at least 72 px wide) |
| `pyzed-design.svg`, `pyzed-design-dark.svg` | The Pyzed Design lockup |
| `pyzed-mark.svg`, `pyzed-mark-dark.svg` | The mark alone, from 24 px (navbars, title bars) |
| `pyzed-mark-small.svg` | A silhouette without eyes, for 16 to 20 px |
| `pyzed-mark-black.svg`, `pyzed-mark-white.svg` | One ink |
| `app-icon.svg`, `app-icon-dark.svg` | The app icon, indigo and graphite |

Leave clear space around the mark as wide as its head, and never stretch, rotate or recolor it outside the
palette below.

## Color

Graphite surfaces in layers, like a code editor. Indigo is the brand; amber is only for LEDs and displays, with
the panel language of an audio rack. Dark ("Graphite") is the default; light ("Paper") keeps the same hierarchy.

| Token | Graphite (dark) | Paper (light) |
| --- | --- | --- |
| Background | `#0D0E11` | `#F6F7F9` |
| Surface | `#14161B` | `#FFFFFF` |
| Panel | `#191C22` | `#F1F3F6` |
| Raised | `#222630` | `#E7EAF0` |
| Border | `#2A2F39` | `#DCE0E7` |
| Text | `#E7E9EE` | `#14161B` |
| Secondary text | `#9AA1AE` | `#576070` |
| Indigo | `#8B83FF` | `#4F46E5` |
| Solid indigo (buttons) | `#5B50F0` | `#4F46E5` |
| Amber LED | `#F5A524` | `#F5A524` |

`assets/brand/tokens.json` has every token, including the display (LCD), canvas grid and code colors.

## Type

**IBM Plex Sans** for everything you read: headings 700, subheadings 600, text 400. It is the same family the
Pyzed components use. **IBM Plex Mono** for code, keys, labels and eyebrows.

## On this site

- The colors are CSS variables in `docs/src/styles/custom.css`: Starlight's `--sl-color-*` plus `--pz-brand`,
  `--pz-surface`, `--pz-led`, `--pz-lcd` and the rest for the components in `docs/src/components`.
- The wordmark in the header is `src/components/brand/Wordmark.astro`; `Mark.astro` draws the mark inline so it
  takes the color of the text around it. Their paths are copied from `scripts/brand.py`.
- Code blocks use two Expressive Code themes made from the brand's code colors, in `docs/src/styles/code`.
- The favicon is `assets/brand/favicon.svg`; `python docs/scripts/gen_og.py` draws the social cards and the PNG
  icons from the app icon.
