---
title: Routes in code
description: "Pyzed routes without folders: a dict of pages for a single-file app, a router inside your own app or one region of it, forms from Pyzed Design as pages, and URLs for the web."
sidebar:
  order: 3
---

## A dict instead of folders

A single-file app can give its routes as a dict. A value is the page, or a dict of the files:

```python
import pyzed as pz
from pyzed import ui


def home():
    return ui.heading("Home")


def user(params):
    return ui.heading(f"User {params['id']}")


def shell(children):
    return pz.row([pz.column([pz.nav_link("/", "Home"), pz.nav_link("/users/1", "Ada")], width=180),
                   pz.column(children, padding=24)])


pz.run(pz.RouterApp({
    "/": {"page": home, "layout": shell},
    "/users/[id]": {"page": user, "load": fetch_user, "loading": spinner, "title": "User"},
}))
```

The keys of a route's dict are the file names (`page`, `layout`, `template`, `loading`,
`error`, `not_found`, `middleware`) plus `load`, `title`, `metadata` and `matcher`.

## A router inside your own app

A router fits in any `pz.App`, or in one region of it (the right side of a split, a tab):

```python
class Mail(pz.App):
    def __init__(self):
        self.router = pz.Router("app", initial="/inbox")

    def view(self):
        return pz.row([sidebar(), self.router.view()])

    def on_key(self, combo):
        return self.router.handle_key(combo) or None     # Alt+Left / Alt+Right
```

## Forms from Pyzed Design

A `page.pzform` made in [Pyzed Design](/pyzed/guides/designer/) works as a page: put it in the
route's folder instead of `page.py`. It is laid out in the space the layouts leave it, and its
handlers can navigate with `pz.use_router().push(...)`.

## On the web

Locations are plain URLs (`/products/3?sort=price#reviews`), so the same `app/` folder maps one
to one to a browser's address bar. `router.url` and `router.location` give the current one, and
`push` accepts any of them.
