---
title: SEO y llms.txt
description: "Cómo se optimiza la documentación de Pyzed para buscadores y motores de respuesta con IA: metadatos, tarjetas sociales, JSON-LD, hreflang, sitemap y llms.txt."
sidebar:
  order: 6
---

La documentación está pensada para que la encuentren los buscadores (Google, Bing...) y para que la lean y la
citen los motores de respuesta con IA y los asistentes de programación. Casi todo se genera al compilar a partir
de las propias páginas, así que una página nueva lo recibe gratis. Tu parte es escribir un buen `title` y una
buena `description`.

## Escribir una buena descripción

Cada página necesita una `description` en su frontmatter. Se convierte en la `<meta name="description">`, el
texto bajo el título en los resultados de búsqueda y en las vistas previas al compartir, el resumen de la página
en `llms.txt` y la `description` de sus datos estructurados.

- **Entre 120 y 160 caracteres.** Las más cortas se completan con una frase genérica; las más largas las cortan
  los buscadores.
- **Di qué obtiene el lector**, con las palabras que la gente busca: *GUI de escritorio en Python*, *nativa*,
  *Rust*, *diseñador visual*, *alternativa a tkinter*, el nombre del componente o la función. Úsalas con
  naturalidad, una vez.
- **Única por página**, y traducida (no copiada) en la página en inglés.
- Ponla entre comillas si tiene dos puntos: `description: "Temas de Pyzed: One, Ayu y Gruvbox..."`.

Las páginas de componentes de la biblioteca se generan: su descripción es el `blurb` del componente en
`docs/scripts/library_data.py` más una frase que añade `seo_description()` en `gen_library.py`. Las descripciones
del changelog están en `docs/scripts/sync-changelog.mjs`.

## Qué se genera

| Qué | De dónde sale |
| --- | --- |
| `<title>`, meta description, URL canónica, Open Graph, tarjetas de Twitter y keywords | `docs/src/routeData.ts` ([route middleware](https://starlight.astro.build/guides/route-data/) de Starlight) |
| Imágenes de las tarjetas sociales (1200×630) | `docs/scripts/gen_og.py` escribe `docs/public/og/<sección>[.es].png` y los iconos de la app; vuelve a ejecutarlo si cambian las capturas |
| Datos estructurados JSON-LD | `routeData.ts`: `Organization` y `WebSite` en todas, `SoftwareSourceCode` y `SoftwareApplication` (Pyzed Design, con la versión de `src/generated/release.json`) en la portada, `BreadcrumbList` y `TechArticle` en cada página, `FAQPage` en las [preguntas frecuentes](/pyzed/es/faq/) |
| Alternativas `hreflang` | Starlight, filtradas por `routeData.ts` para que una página solo liste los idiomas a los que está traducida. Una página sin traducir mostrada en español apunta su URL canónica a la inglesa y lleva `noindex` |
| `sitemap-index.xml` | `@astrojs/sitemap` en `astro.config.mjs`, con los dos idiomas y el `<lastmod>` de cada página sacado del historial git de su archivo (el workflow de docs descarga el historial completo; el mismo historial da la fecha de *Última actualización* de cada página) |
| `robots.txt`, `humans.txt`, `.well-known/security.txt`, `manifest.webmanifest` | Archivos estáticos en `docs/public/` |
| `llms.txt`, `llms-full.txt`, `llms-small.txt`, `llms/<sección>.txt`, `es/llms.txt`, `es/llms-full.txt` | Endpoints en `docs/src/pages/`, generados desde la colección de contenido por `docs/src/lib/llms.ts` |
| `<página>.md` (el Markdown de cada página) | `docs/src/pages/[...page].md.ts` |

## llms.txt y páginas en Markdown

[llms.txt](https://llmstxt.org) es un mapa del sitio en Markdown para modelos de lenguaje. Pyzed publica:

- [`/pyzed/es/llms.txt`](https://albakore.github.io/pyzed/es/llms.txt): qué es Pyzed, datos clave y cada página
  con una descripción de una línea, agrupadas por sección. En inglés: [`/pyzed/llms.txt`](https://albakore.github.io/pyzed/llms.txt).
- [`/pyzed/es/llms-full.txt`](https://albakore.github.io/pyzed/es/llms-full.txt): toda la documentación en español
  en un archivo. En inglés: [`/pyzed/llms-full.txt`](https://albakore.github.io/pyzed/llms-full.txt).
- [`/pyzed/llms-small.txt`](https://albakore.github.io/pyzed/llms-small.txt): solo lo necesario para escribir una
  app (empezar, tutoriales, guías, IA y preguntas frecuentes), en inglés.
- `/pyzed/llms/<sección>.txt`: una sección, por ejemplo [`llms/library.txt`](https://albakore.github.io/pyzed/llms/library.txt).
- Cada página en Markdown: cambia la barra final por `.md`, por ejemplo
  [`/pyzed/es/guides/layout.md`](https://albakore.github.io/pyzed/es/guides/layout.md) (`/pyzed/es/index.md` para la
  portada). Cada página HTML lo enlaza con `<link rel="alternate" type="text/markdown">`.

El Markdown se limpia: se quitan el frontmatter, los imports y los componentes MDX, las pestañas y los avisos pasan
a texto, los ejemplos que los tutoriales importan con `?raw` se incluyen como bloques de código, las imágenes
conservan solo su texto alternativo y los enlaces pasan a ser absolutos. Las secciones nuevas aparecen solas; para
darles nombre y lugar en el orden, añádelas a `SECTIONS` en `docs/src/lib/llms.ts`.

Revisa el resultado después de compilar:

```bash
cd docs
npm run build
less dist/es/llms.txt dist/es/guides/layout.md
```

## Otras comprobaciones

- **Un solo `h1` por página.** Starlight muestra el título como `h1`; empieza el contenido en `##`.
- **Texto alternativo en cada imagen**: `![Qué muestra la captura](...)`. Es también lo que leen los asistentes en
  lugar de la imagen.
- **Enlaces internos** con la ruta completa y la base: `/pyzed/es/guides/layout/`.
- **robots.txt** solo funciona en la raíz de un dominio. Mientras la documentación se sirva desde
  `albakore.github.io/pyzed/`, la copia de `docs/public/robots.txt` documenta la política (todos los buscadores y
  rastreadores de IA son bienvenidos); el sitemap también se enlaza desde cada página y se puede enviar en Google
  Search Console y Bing Webmaster Tools.
