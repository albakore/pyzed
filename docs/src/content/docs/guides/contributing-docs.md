---
title: Editing the documentation
description: How this site is organized, how to preview it, how translations work and how to regenerate the reference and images.
sidebar:
  order: 12
---

The site is built with [Astro Starlight](https://starlight.astro.build) and lives in `docs/`.
It is published to GitHub Pages on every push to `main` and on every release.

```
docs/
├── astro.config.mjs              # sidebar, theme, languages
├── screenshots/                  # large screenshots (examples/screenshots.py)
├── scripts/
│   ├── api_docs_en.py            # English API descriptions
│   ├── api_docs_es.py            # Spanish API descriptions
│   ├── gen_api.py                # generates reference/*.md in both languages
│   ├── component_shots.py        # generates src/assets/components/*.png
│   ├── example_shots.py          # generates example and tutorial screenshots
│   └── sync-changelog.mjs        # CHANGELOG.md → What's new page (both languages) + stable version
└── src/content/docs/             # the pages (Markdown / MDX)
    ├── guides/ ...               # English (default language, site root)
    └── es/                       # Spanish translations, same paths
```

## Preview

```bash
cd docs
npm install
npm run dev        # http://localhost:4321/pyzed/
```

## Languages

The documentation is multilingual. English is the default language and is served at the site
root; each translation lives in a folder named after its locale:

| Language | Files | URL |
| --- | --- | --- |
| English | `src/content/docs/guides/canvas.md` | `/pyzed/guides/canvas/` |
| Spanish | `src/content/docs/es/guides/canvas.md` | `/pyzed/es/guides/canvas/` |

- A translation uses **the same path** as the English page, under `es/`.
- When you add a page, add it in both languages. If a translation is missing, Starlight shows the
  English page with a notice instead of a 404.
- Internal links include the locale: `/pyzed/guides/...` in English pages and `/pyzed/es/guides/...`
  in Spanish ones.
- Relative paths to images and examples have one more `../` in the Spanish files, since they are one
  folder deeper.

## Diagrams

Write diagrams as `mermaid` code blocks; the `astro-mermaid` integration renders them on the page
and follows the light/dark theme:

````md
```mermaid
flowchart LR
    view["App.view()"] --> tree[Widget tree] --> render[render.rs] --> iced[Iced]
```
````

## Regenerating the reference and images

These need Pyzed installed (`maturin develop --release`):

```bash
python docs/scripts/gen_api.py              # API reference, both languages
python docs/scripts/gen_api.py --lang en    # English only (or --lang es)
python docs/scripts/gen_api.py --check      # reports public names without documentation
python docs/scripts/component_shots.py      # component illustrations
python docs/scripts/example_shots.py        # example and tutorial screenshots
python examples/screenshots.py              # large screenshots
```

When you add a public function, describe its parameters in `docs/scripts/api_docs_en.py` and
`docs/scripts/api_docs_es.py`, then regenerate the reference. CI runs `gen_api.py --check`.

## What's new and versions

```mermaid
flowchart LR
    C["Commits (gitmoji)"] --> PR["Pull request"] --> CI["CI: lint, tests, wheels"]
    PR --> MAIN["main"]
    MAIN --> CL["CHANGELOG.md"]
    T["tag vX.Y.Z"] --> R["GitHub Release + PyPI"]
    CL --> S["sync-changelog.mjs"] --> WEB["What's new + version badge"]
    MAIN --> D["docs.yml → GitHub Pages"]
```

`docs/scripts/sync-changelog.mjs` generates the [What's new](/pyzed/changelog/) page in both
languages from `CHANGELOG.md` (repository root) on every build. Each version is a
`## [X.Y.Z] - YYYY-MM-DD` heading; versions with a suffix (`1.0.0-rc.1`, `0.2.0b1`) are marked as
pre-releases. The most recent one without a suffix is shown as the **latest stable** release in the
header, the home page and the What's new page.
