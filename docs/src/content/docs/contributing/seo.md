---
title: SEO and llms.txt
description: "How the Pyzed docs are optimized for search engines and AI answer engines: meta tags, social cards, JSON-LD, hreflang, sitemap, robots.txt and llms.txt."
sidebar:
  order: 6
---

The documentation is built to be found by search engines (Google, Bing...) and to be read and cited by AI
answer engines and coding assistants. Almost everything is generated at build time from the pages themselves, so
a new page gets it for free. Your part is to write a good `title` and `description`.

## Writing a good description

Every page needs a `description` in its frontmatter. It becomes the `<meta name="description">`, the text under
the title in search results and social previews, the summary of the page in `llms.txt` and the `description`
of its structured data.

- **120 to 160 characters.** Shorter ones get padded with a generic sentence; longer ones are cut by search
  engines.
- **Say what the reader gets**, with the words people search for: *Python desktop GUI*, *native*, *Rust*,
  *visual designer*, *tkinter alternative*, the component or feature name. Use them naturally, once.
- **Unique per page**, and translated (not copied) in the Spanish page.
- Quote it when it contains a colon: `description: "Pyzed themes: One, Ayu and Gruvbox..."`.

Component pages in the library are generated: their description is the component's `blurb` from
`docs/scripts/library_data.py` plus a sentence added by `seo_description()` in `gen_library.py`. The changelog
descriptions live in `docs/scripts/sync-changelog.mjs`.

## What is generated

| What | Where it comes from |
| --- | --- |
| `<title>`, meta description, canonical URL, Open Graph and Twitter cards, keywords | `docs/src/routeData.ts` (Starlight [route middleware](https://starlight.astro.build/guides/route-data/)) |
| Social card images (1200×630) | `docs/scripts/gen_og.py` writes `docs/public/og/<section>[.es].png` and the app icons; re-run it after changing screenshots |
| JSON-LD structured data | `routeData.ts`: `Organization` and `WebSite` everywhere, `SoftwareSourceCode` and `SoftwareApplication` (Pyzed Design, with the version from `src/generated/release.json`) on the home page, `BreadcrumbList` and `TechArticle` on every docs page, `FAQPage` on the [FAQ](/pyzed/faq/) |
| `hreflang` alternates | Starlight, filtered by `routeData.ts` so a page only lists the languages it is really translated to. An untranslated page shown in Spanish points its canonical URL to the English one and is `noindex` |
| `sitemap-index.xml` | `@astrojs/sitemap` in `astro.config.mjs`, with both languages and each page's `<lastmod>` from the git history of its file (the docs workflow checks out the whole history; the same history gives the *Last updated* date of every page) |
| `robots.txt`, `humans.txt`, `.well-known/security.txt`, `manifest.webmanifest` | Static files in `docs/public/` |
| `llms.txt`, `llms-full.txt`, `llms-small.txt`, `llms/<section>.txt`, `es/llms.txt`, `es/llms-full.txt` | Endpoints in `docs/src/pages/`, built from the content collection by `docs/src/lib/llms.ts` |
| `<page>.md` (raw Markdown of every page) | `docs/src/pages/[...page].md.ts` |

## llms.txt and Markdown pages

[llms.txt](https://llmstxt.org) is a plain Markdown map of a site for language models. Pyzed publishes:

- [`/pyzed/llms.txt`](https://albakore.github.io/pyzed/llms.txt): what Pyzed is, key facts, and every page
  with a one-line description, grouped by section. Spanish: [`/pyzed/es/llms.txt`](https://albakore.github.io/pyzed/es/llms.txt).
- [`/pyzed/llms-full.txt`](https://albakore.github.io/pyzed/llms-full.txt): the whole English documentation in
  one file. Spanish: [`/pyzed/es/llms-full.txt`](https://albakore.github.io/pyzed/es/llms-full.txt).
- [`/pyzed/llms-small.txt`](https://albakore.github.io/pyzed/llms-small.txt): only what is needed to write an
  app (getting started, tutorials, guides, AI, FAQ).
- `/pyzed/llms/<section>.txt`: one section, for example [`llms/library.txt`](https://albakore.github.io/pyzed/llms/library.txt).
- Every page as Markdown: replace the trailing slash with `.md`, for example
  [`/pyzed/guides/layout.md`](https://albakore.github.io/pyzed/guides/layout.md) (`/pyzed/index.md` for the home page).
  Each HTML page links to it with `<link rel="alternate" type="text/markdown">`.

The Markdown is cleaned up: frontmatter, imports and MDX components are removed, tabs and asides become plain
text, the example files that tutorials import with `?raw` are inlined as code blocks, images keep only their alt
text, and links become absolute. New sections appear automatically; to give one a name and a place in the order,
add it to `SECTIONS` in `docs/src/lib/llms.ts`.

Check the result after building:

```bash
cd docs
npm run build
less dist/llms.txt dist/guides/layout.md
```

## Other checks

- **One `h1` per page.** Starlight renders the title as the `h1`; start the content at `##`.
- **Alt text for every image**: `![What the screenshot shows](...)`. It is also what assistants read in place of the image.
- **Internal links** use the full path with the base: `/pyzed/guides/layout/` (`/pyzed/es/...` in Spanish).
- **robots.txt** only works at the root of a host. While the docs are served from `albakore.github.io/pyzed/`,
  the copy in `docs/public/robots.txt` documents the policy (all search engines and AI crawlers are welcome); the
  sitemap is also linked from every page, and can be submitted in Google Search Console and Bing Webmaster Tools.

## Getting indexed

Search engines only show pages they know about, and a new project has no links pointing to it yet. Two things
happen on every deploy of `main` (`.github/workflows/docs.yml`):

- **IndexNow.** `docs/scripts/indexnow.py` hashes every page in the sitemap, publishes the hashes as
  `page-hashes.json` and, once the site is deployed, sends the pages that differ from the live copy to
  [IndexNow](https://www.indexnow.org). Bing (which also feeds ChatGPT search, Copilot and DuckDuckGo), Yandex,
  Seznam, Naver and Yep then crawl them within hours. The key is the file `docs/public/<key>.txt`; it is public by
  design.
- **Ownership checks.** The repository variables `GOOGLE_SITE_VERIFICATION`, `BING_SITE_VERIFICATION` and
  `YANDEX_VERIFICATION` (*Settings → Secrets and variables → Actions → Variables*) become the
  `google-site-verification`, `msvalidate.01` and `yandex-verification` meta tags of every page.

To register the site once:

1. In [Google Search Console](https://search.google.com/search-console), add the URL-prefix property
   `https://albakore.github.io/pyzed/`, choose **HTML tag** and save the `content` value as the
   `GOOGLE_SITE_VERIFICATION` variable. Re-run the **Docs** workflow, verify, and submit
   `https://albakore.github.io/pyzed/sitemap-index.xml` under **Sitemaps**.
2. In [Bing Webmaster Tools](https://www.bing.com/webmasters), import the site from Search Console (or use the
   `BING_SITE_VERIFICATION` variable the same way) and submit the same sitemap.
3. Give the project links search engines trust: the repository's **About → Website** pointing to the docs and
   topics such as `python`, `gui`, `desktop-app`, `rust`, `iced`; the PyPI page (its links come from
   `[project.urls]` in `pyproject.toml`); and posts or listings that link to the docs.

Pyzed shares its import name with the `pyzed` module of the Stereolabs ZED SDK, so the docs say clearly that
the package is `pyzed-ui` and name what people search for: *Python GUI*, *desktop app*, *Rust*, *Iced*.
