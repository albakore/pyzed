---
title: Editar la documentación
description: Cómo está organizada esta web, cómo previsualizarla y cómo regenerar la referencia y las imágenes.
sidebar:
  order: 9
---

La web está hecha con [Astro Starlight](https://starlight.astro.build) y vive en `docs/`.
Se publica en GitHub Pages en cada push a `main` y en cada release.

```
docs/
├── astro.config.mjs              # barra lateral, tema, idioma
├── screenshots/                  # capturas grandes (examples/screenshots.py)
├── scripts/
│   ├── api_docs.py               # descripciones en español de la API
│   ├── gen_api.py                # genera src/content/docs/reference/*.md
│   ├── component_shots.py        # genera src/assets/components/*.png
│   └── sync-changelog.mjs        # CHANGELOG.md → página de novedades + versión estable
└── src/content/docs/             # las páginas (Markdown / MDX)
```

## Previsualizar

```bash
cd docs
npm install
npm run dev        # http://localhost:4321/pyzed/
```

## Regenerar la referencia y las imágenes

Necesitan Pyzed instalado (`maturin develop --release`):

```bash
python docs/scripts/gen_api.py            # referencia de la API
python docs/scripts/gen_api.py --check    # falla si hay funciones públicas sin documentar
python docs/scripts/component_shots.py    # ilustraciones de componentes
python examples/screenshots.py            # capturas grandes
```

Cuando añadas una función pública, describe sus parámetros en `docs/scripts/api_docs.py` y vuelve
a generar la referencia. La CI ejecuta `gen_api.py --check`.

## Novedades y versiones

La página [Novedades](/pyzed/changelog/) se genera desde `CHANGELOG.md` (raíz del repositorio)
en cada build. Cada versión es un encabezado `## [X.Y.Z] - AAAA-MM-DD`; las que llevan sufijo
(`1.0.0-rc.1`, `0.2.0b1`) se marcan como preliminares. La más reciente sin sufijo aparece como
**última estable** en la cabecera, la portada y la página de novedades.
