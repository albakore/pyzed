---
title: Good practices
description: "How to organize a routed Pyzed app: where each piece of code goes, reading and changing data, global state, middleware, testing pages and keeping the window fast."
sidebar:
  order: 4
---

## Where each thing goes

```text
shop/
├── main.py            only starts the router
├── api.py             every call to the server or the database
├── state.py           the stores: session, cart, preferences
├── app/
│   ├── layout.py      the frame: sidebar, header
│   ├── middleware.py  login checks and redirects
│   ├── _components/   pieces of UI shared by the routes
│   └── products/
│       ├── page.py    what /products shows, and its load
│       └── loading.py
└── tests/
```

| Code | Goes in |
| --- | --- |
| reading from a server or a database | `load`, calling `api.py` |
| a change (save, order, sign in) | a `@pz.action`, calling `api.py` |
| values many pages share | a `pz.Store` in `state.py` |
| a filter, a tab, a page number | the query (`?sort=price`) |
| what a component types or opens | `pz.state` |
| checks before a page | `middleware.py` |
| telling the user something happened | `pz.notify` or a toast |
| helpers only one route uses | a file next to its `page.py`, imported by name (`import helpers`) |

## Data

- **Read in `load`, change in actions.** The page only decides what to show with `data`.
- **One request per need.** Combine what a page needs in one `load` with `asyncio.gather`,
  rather than starting requests from components.
- **Let the cache work.** Don't copy `data` into a store; after an action the page refreshes by
  itself, and `invalidate` marks other pages.
- **Fail loudly.** Raise from `load` (`response.raise_for_status()`): `error.py` shows it with
  "Try again". Use `pz.not_found()` for things that don't exist.

## State

- **One store per subject** (`Session`, `Cart`, `Preferences`), one instance each, in a module.
- **Replace values** (`cart.items = [...]`) instead of changing them in place, or call
  `changed()` after.
- **`persist` only what the user expects to find next time** (preferences, a draft), never
  tokens or passwords: they are saved as plain JSON.

## Speed

- Nothing that waits in a page, a layout or `render()`. The awaits go in `load` or an action.
- Put a heavy piece (a big table, a chart) in a component, so it is only drawn again when its
  inputs change.
- Add `loading.py` where a page takes time, near the page, so the layouts stay put.
- Links prefetch on hover; for an obvious next step, `router.prefetch(href)` it.

## Testing

A router works without a window, so a test can navigate and check what each page shows:

```python
import pyzed as pz

import api


def test_product_page(monkeypatch):
    monkeypatch.setattr(api, "DELAY", 0)
    router = pz.Router("app", initial="/products/3")
    router.view()
    router.wait()                          # the loads
    assert router.title == "4K monitor · Shop"


def test_account_needs_a_session():
    router = pz.Router("app", initial="/account")
    router.view()
    router.wait()
    assert router.pathname == "/login"


def test_add_to_cart():
    add_to_cart.run(api.PRODUCTS[0])       # waits for the action
    assert cart.count == 1
```

`pyzed route list` shows every address and its files, a quick check that the folders say what
you meant.
