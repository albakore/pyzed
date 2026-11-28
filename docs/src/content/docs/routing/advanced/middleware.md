---
title: Middleware
description: "middleware.py in Pyzed: login checks, redirects, rewrites and guards that run before a page shows, with matchers, async checks and values passed to the pages."
sidebar:
  order: 1
---

Middleware is code that runs **before every navigation**, before any `load` and before the page
is drawn. It is the place for checks that concern many pages at once: is the user signed in, may
they see this, should this old address go somewhere else?

```python
# app/middleware.py
from state import session

matcher = ["/account/:path*"]           # only these addresses (optional)


def middleware(request):
    if not session.signed_in:
        return request.redirect(f"/login?next={request.pathname}")
    request.locals["user"] = session.user     # the pages can take it as `locals`
```

![The account page is behind a middleware: it goes to the login, then back to the account](/pyzed/media/routing/middleware.webp)

## What it can answer

| Return | What happens |
| --- | --- |
| nothing (`None`) | the next middleware runs, then the page shows |
| `request.redirect("/login")` | goes there instead, replacing the entry (`push=True` keeps the old one in the history) |
| `request.rewrite("/maintenance")` | shows that route, but the address stays the same |
| `False` | stays where it is (an unsaved form, say) |
| `pz.not_found()` | shows the closest `not_found.py` |
| an exception | the closest `error.py` shows it |

`pz.redirect(...)` and `pz.rewrite(...)` work too, returned or raised.

## The request

| Attribute | What it is |
| --- | --- |
| `pathname`, `query`, `hash`, `href` | where it goes: `/account`, `{"tab": "orders"}`... |
| `location`, `previous` | that address, and the current one (`None` at the start) |
| `action` | `"start"`, `"push"`, `"replace"`, `"back"`, `"forward"` or `"refresh"` |
| `route`, `params` | the pattern that answers (`"/products/[id]"`) and its values; `route` is `None` when no page does |
| `locals` | a dict that reaches that page's pages, layouts, `load` and `provide` as `locals` |
| `router` | the router |
| `matches("/admin/:path*")` | whether the address matches a pattern |

## Where it runs

A `middleware.py` runs for every address **below its folder**. With several on the way, the outer
ones run first, so `app/middleware.py` can sign the user in and `app/admin/middleware.py` can
check that they are an admin.

`matcher` narrows a file to some addresses. It takes Next.js' syntax or the folders' own:

| Pattern | Matches |
| --- | --- |
| `/about` | that address |
| `/products/:id` or `/products/[id]` | one part: `/products/3` |
| `/docs/:path*` or `/docs/[[...path]]` | `/docs` and everything below |
| `/docs/:path+` or `/docs/[...path]` | everything below `/docs`, not `/docs` itself |
| `/users/*/posts` | `*` is any one part |
| `/files/**` | anything below |
| `^/v[0-9]+/` | a regular expression, when it starts with `^` |

A list matches any of its patterns, and a function (`matcher = lambda request: ...`) decides on its own.

## Middleware in code

Middleware can also be given to the router. It runs **before** the files:

```python
import pyzed as pz


@pz.middleware(matcher="/admin/:path*")
def admins_only(request):
    if not session.is_admin:
        return request.redirect("/")


def log(request):
    print(request.action, request.href)


class Shop(pz.RouterApp):
    routes = "app"
    middleware = [log, admins_only]       # or: pz.Router("app", middleware=[...])
```

## Waiting for something

`async def middleware` runs off the UI thread, on Pyzed's loop: the current page stays on screen
until it answers. If the user navigates again meanwhile, the newest navigation wins.

```python
async def middleware(request):
    if not await api.token_is_valid(session.token):
        return request.redirect("/login")
```

Keep it short: it delays every navigation it applies to. Data the page shows goes in `load`.

## Examples

```python
# Old addresses
def middleware(request):
    if request.pathname.startswith("/shop/"):
        return request.redirect(request.pathname.replace("/shop/", "/products/", 1))


# Maintenance mode: same address, another page
def middleware(request):
    if settings.maintenance and request.route != "/maintenance":
        return request.rewrite("/maintenance")


# Don't leave a form with unsaved changes
def middleware(request):
    if draft.dirty and request.action != "refresh":
        pz.notify("Unsaved changes", "Save or discard them first")
        return False
```

## Next.js differences

- It runs in the app, not on a server, so it can read the global state (`pz.Store`) directly.
- There is one per folder, not one per project, and they add up from the outside in.
- `locals` replaces passing values in request headers.
