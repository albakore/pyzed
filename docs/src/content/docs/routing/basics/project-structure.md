---
title: Folders and files
description: "The project structure of a Pyzed app with routes in folders: special file names, static and dynamic folders, catch-alls, groups, private folders, matching order and the pyzed route commands."
sidebar:
  order: 1
---

Every folder inside `app/` is a part of the address, and the files with these names inside a
folder say what happens at that address:

| File | What it does | Next.js |
| --- | --- | --- |
| `page.py` | what the address shows; without it, the folder is not an address of its own | `page.tsx` |
| `layout.py` | wraps the pages below it and keeps its state | `layout.tsx` |
| `template.py` | like a layout, but starts over on every navigation | `template.tsx` |
| `loading.py` | shown while a `load` below it runs | `loading.tsx` |
| `error.py` | shown when something below it fails | `error.tsx` |
| `not_found.py` | shown for addresses that don't exist and for `pz.not_found()` | `not-found.tsx` |
| `middleware.py` | runs before every navigation below it | `middleware.ts` |
| `page.pzform` | a form made in [Pyzed Design](/pyzed/guides/designer/), used as the page | |

## Folder names

| Folder name | Matches | `params` |
| --- | --- | --- |
| `products` | that exact text | |
| `[id]` | one part | `{"id": "3"}` |
| `[...slug]` | one part or more | `{"slug": ["a", "b"]}` |
| `[[...slug]]` | zero parts or more | `{"slug": []}` on `/docs` |
| `(group)` | nothing: it only organizes | |
| `_private` | skipped: helpers live here | |

```text
app/
├── page.py                       /
├── (shop)/                       a group: not part of the address
│   ├── layout.py                 a layout only for the shop's pages
│   └── products/
│       ├── page.py               /products
│       └── [id]/page.py          /products/3
├── (marketing)/about/page.py     /about
├── docs/[[...slug]]/page.py      /docs, /docs/guide, /docs/guide/routing
└── _components/                  private: product_card.py, price.py...
```

Values in the address are always text: `/products/3` gives `params["id"] == "3"`. Convert them
where you use them (`int(params["id"])`).

### Which folder wins

When more than one folder could answer, the most specific wins, as in Next.js: a static folder
wins over `[id]`, which wins over `[...slug]`, which wins over `[[...slug]]`. With
`products/new/` and `products/[id]/`, `/products/new` goes to the first one and `/products/7` to
the second.

Two folders that answer the same address (`(a)/about` and `(b)/about`) are an error, reported
when the app starts.

## Code next to the routes

The folder that holds `app/` is importable from every route file, like `@/` in Next.js. Keep the
code that is not a route next to `app/`:

```text
shop/
├── main.py           starts the router
├── api.py            calls to the server (read in load, changed in actions)
├── state.py          global state (pz.Store)
├── app/              the routes
│   └── _components/  pieces of UI only the routes use
└── tests/
```

```python
# app/(shop)/products/[id]/page.py
import api                       # api.py next to app/
from state import cart           # state.py next to app/
from app._components.price import price_tag
```

## Commands

`pyzed route add` writes the files of a route with working starter code, and checks the name:

```bash
pyzed route add /                                # app/page.py
pyzed route add /products/[id] --load --loading  # page.py with an async load, and loading.py
pyzed route add /docs/[...slug] --load sync      # a load that runs in a worker thread
pyzed route add "/(shop)/cart" --layout          # quotes: the shell reads ( ) otherwise
pyzed route add /account --middleware --no-page  # only middleware.py
```

Options: `--layout`, `--template`, `--loading`, `--error`, `--not-found`, `--middleware`,
`--no-page`, `--load [async|sync]`, `--force` (overwrite files that exist) and `--app DIR`
(another routes folder).

`pyzed route list` shows every address and the files that answer it, like Next.js' build output:

```text
Route              Type      Files
/                  ○ static  layout, not_found, page
/cart              ○ static  middleware, layout, not_found, page
/docs/[[...slug]]  λ dynamic layout, not_found, page
/products/[id]     λ dynamic layout, loading, not_found, page

○ static: one address   λ dynamic: [params] in the address
```

New projects start from `pyzed new NAME --router`: a layout with a sidebar, a home page, a list
that loads its data, a detail page with an action, a global store, a middleware and the
`loading`, `error` and `not_found` files.
