---
title: Carpetas y archivos
description: "La estructura de una app de Pyzed con rutas en carpetas: nombres de archivo especiales, carpetas fijas y dinámicas, catch-alls, grupos, carpetas privadas, orden de coincidencia y los comandos pyzed route."
sidebar:
  order: 1
---

Cada carpeta dentro de `app/` es una parte de la dirección, y los archivos con estos nombres
dentro de una carpeta dicen qué pasa en esa dirección:

| Archivo | Qué hace | Next.js |
| --- | --- | --- |
| `page.py` | lo que muestra la dirección; sin él, la carpeta no es una dirección propia | `page.tsx` |
| `layout.py` | envuelve las páginas de debajo y guarda su estado | `layout.tsx` |
| `template.py` | como un layout, pero empieza de cero en cada navegación | `template.tsx` |
| `loading.py` | se muestra mientras corre un `load` de debajo | `loading.tsx` |
| `error.py` | se muestra cuando algo de debajo falla | `error.tsx` |
| `not_found.py` | se muestra para direcciones que no existen y para `pz.not_found()` | `not-found.tsx` |
| `middleware.py` | corre antes de cada navegación de debajo | `middleware.ts` |
| `page.pzform` | un formulario hecho en [Pyzed Design](/pyzed/es/guides/designer/), usado como página | |

## Nombres de carpeta

| Nombre de carpeta | Coincide con | `params` |
| --- | --- | --- |
| `products` | ese texto exacto | |
| `[id]` | una parte | `{"id": "3"}` |
| `[...slug]` | una parte o más | `{"slug": ["a", "b"]}` |
| `[[...slug]]` | cero partes o más | `{"slug": []}` en `/docs` |
| `(grupo)` | nada: solo organiza | |
| `_privada` | se salta: aquí vive el código de apoyo | |

```text
app/
├── page.py                       /
├── (shop)/                       un grupo: no forma parte de la dirección
│   ├── layout.py                 un layout solo para las páginas de la tienda
│   └── products/
│       ├── page.py               /products
│       └── [id]/page.py          /products/3
├── (marketing)/about/page.py     /about
├── docs/[[...slug]]/page.py      /docs, /docs/guide, /docs/guide/routing
└── _components/                  privada: product_card.py, price.py...
```

Los valores de la dirección siempre son texto: `/products/3` da `params["id"] == "3"`.
Conviértelos donde los uses (`int(params["id"])`).

### Qué carpeta gana

Cuando más de una carpeta podría responder, gana la más concreta, como en Next.js: una carpeta
fija gana a `[id]`, que gana a `[...slug]`, que gana a `[[...slug]]`. Con `products/new/` y
`products/[id]/`, `/products/new` va a la primera y `/products/7` a la segunda.

Dos carpetas que responden a la misma dirección (`(a)/about` y `(b)/about`) son un error, que se
avisa al arrancar la app.

## Código junto a las rutas

La carpeta que contiene `app/` se puede importar desde cualquier archivo de ruta, como `@/` en
Next.js. Deja junto a `app/` el código que no es una ruta:

```text
shop/
├── main.py           arranca el router
├── api.py            llamadas al servidor (se leen en load, se cambian en acciones)
├── state.py          estado global (pz.Store)
├── app/              las rutas
│   └── _components/  piezas de interfaz que solo usan las rutas
└── tests/
```

```python
# app/(shop)/products/[id]/page.py
import api                       # api.py junto a app/
from state import cart           # state.py junto a app/
from app._components.price import price_tag
```

### Archivos dentro de las carpetas de rutas

Una carpeta como `[id]` o `(shop)` no se puede escribir en un `import`, así que importa los
archivos que están junto a una ruta por su propio nombre. Pyzed busca primero junto al archivo de
la ruta y después en cada carpeta superior hasta `app/`, igual que los resuelven Pyright,
basedpyright y ty (los servidores de lenguaje de Zed y VS Code), así que el autocompletado e "ir a
la definición" funcionan sin configurar nada:

```text
app/(shop)/
├── _shared/text.py         lo usan todas las páginas del grupo
└── products/[id]/
    ├── page.py
    └── helpers.py          solo lo usa esta página
```

```python
# app/(shop)/products/[id]/page.py
import helpers                    # helpers.py junto a esta página
from _shared.text import label    # _shared/ en una carpeta superior
```

Cada ruta tiene sus propias copias: dos páginas pueden tener un `helpers.py` cada una sin
mezclarse. Los imports relativos (`from .helpers import x`, `from ..shared import y`) también
funcionan, pero en estas carpetas solo los entiende Pyright; ty los marca como error, así que es
mejor importar por nombre.

`pyzed new --router` además escribe los ajustes de imports en `pyproject.toml`, como hace un
proyecto nuevo de Next.js con su `tsconfig.json`. Pyright, basedpyright, Pylance, ty y Jedi no
necesitan nada; Pyrefly necesita estas líneas, que puedes copiar en un proyecto anterior:

```toml
[tool.pyrefly]
enable-fallback-search-path = true

[tool.pyrefly.errors]
fallback-search-path-relative-import = false
```

## Comandos

`pyzed route add` escribe los archivos de una ruta con código inicial que funciona, y comprueba
el nombre:

```bash
pyzed route add /                                # app/page.py
pyzed route add /products/[id] --load --loading  # page.py con un load async, y loading.py
pyzed route add /docs/[...slug] --load sync      # un load que corre en un hilo de trabajo
pyzed route add "/(shop)/cart" --layout          # comillas: si no, la shell interpreta los ( )
pyzed route add /account --middleware --no-page  # solo middleware.py
```

Opciones: `--layout`, `--template`, `--loading`, `--error`, `--not-found`, `--middleware`,
`--no-page`, `--load [async|sync]`, `--force` (sobrescribe los archivos que existan) y `--app DIR`
(otra carpeta de rutas).

`pyzed route list` muestra cada dirección y los archivos que la responden, como la salida de
`next build`:

```text
Route              Type      Files
/                  ○ static  layout, not_found, page
/cart              ○ static  middleware, layout, not_found, page
/docs/[[...slug]]  λ dynamic layout, not_found, page
/products/[id]     λ dynamic layout, loading, not_found, page

○ static: one address   λ dynamic: [params] in the address
```

Los proyectos nuevos empiezan con `pyzed new NOMBRE --router`: un layout con barra lateral, una
página de inicio, una lista que carga sus datos, una página de detalle con una acción, un store
global, un middleware y los archivos `loading`, `error` y `not_found`.
