---
title: Navigating
description: "Links, sidebar links, the router's push, replace, back and forward, history keys, relative addresses and the hooks that read the current address."
sidebar:
  order: 3
---

![Clicking through the store: links, a product that loads, Alt+Left to go back](/pyzed/media/routing/navigation.webp)

## Links

```python
pz.link("/products/3", "See the monitor")          # text in the accent color
pz.link("/products/3", ui.card(...))               # any widget
pz.link("?sort=price", "Cheapest first", replace=True)
pz.link(("/users/[id]", {"id": user.id}), user.name)
pz.nav_link("/settings", "Settings", icon="settings")   # a sidebar row, selected while active
```

A link starts the page's `load` when the mouse is over it (`prefetch=False` turns it off), so the
page often shows at once when clicked.

`pz.nav_link` is selected while its address is the current page or one of its parents:
`/settings` stays selected on `/settings/profile`. `exact=True` selects it only on its own
address.

## From code

`pz.use_router()` gives the router, in a page, a component or an event handler:

```python
def save():
    api.save(form)
    pz.use_router().push("/orders")
```

| Call | Does |
| --- | --- |
| `push(href)` | goes there and adds a history entry |
| `replace(href)` | goes there instead of the current entry |
| `back()`, `forward()`, `go(n)` | moves in the history (`can_go_back`, `can_go_forward`) |
| `refresh()` | loads the current data again, keeping the old one on screen meanwhile |
| `prefetch(href)` | starts a page's `load` before going there |
| `invalidate(*hrefs)` | marks pages' data as old ([Actions](/pyzed/routing/data/actions/)) |
| `is_active(href, exact=False)` | whether `href` is the current page or one of its parents |
| `href("/users/[id]", id=7)` | builds `/users/7` |
| `routes()` | every page pattern: `["/", "/products", "/products/[id]"]` |
| `listen(callback)` | calls `callback(location)` after every navigation |
| `url`, `location`, `pathname`, `query`, `params`, `history`, `title` | where it is |

Relative addresses work like in a browser: `"reviews"`, `"../"` and `"?page=2"`.

## Reading where you are

`pz.use_pathname()`, `pz.use_params()` and `pz.use_search_params()` read the address, like their
Next.js namesakes:

```python
class SortMenu(pz.Component):
    def render(self):
        query = pz.use_search_params()
        router = pz.use_router()
        return ui.segmented(["name", "price"], query.get("sort", "name"),
                            lambda v: router.replace(f"?sort={v}"))
```

Keeping a filter or a tab in the query (`?sort=price`) instead of a component's state means the
back button goes back to it, and the page can be opened at that state from a link or a
notification.

## Keys and buttons

Alt+Left and Alt+Right (Cmd+[ and Cmd+] on macOS), the mouse's back and forward buttons and
Android's back button move in the history. `RouterApp` does it for you; a router inside your own
app needs `def on_key(self, combo): return self.router.handle_key(combo) or None`.

`on_navigate(location)` on a `RouterApp` runs after every navigation (to log it, say).
