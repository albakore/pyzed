---
title: Pages, layouts and templates
description: "Pages as functions or components, the arguments they receive, nested layouts that keep their state, templates that start over, sharing values with provide, and window titles."
sidebar:
  order: 2
---

## Pages

A route file defines a function named like the file. It takes **only the arguments it names**, in
any order:

```python
# app/about/page.py
import pyzed as pz
from pyzed import ui

title = "About"        # the window's title on this page


def page(params, query, router):
    return pz.column([ui.heading("About"), ui.label(f"{len(router.history)} pages visited")])
```

| Argument | What it is |
| --- | --- |
| `params` | the dynamic parts of the address: `{"id": "3"}` |
| `query` | the query string as a dict: `?sort=price` gives `{"sort": "price"}` (`query.get_all("tag")` for repeated keys) |
| `data` | what the file's `load` returned ([Calling the server](/pyzed/routing/data/data-fetching/)) |
| `locals` | what the [middleware](/pyzed/routing/advanced/middleware/) left for this navigation |
| `children` | in layouts and templates: what goes inside |
| `error`, `reset` | in `error.py`: the exception and a function that tries again |
| `router`, `pathname` | the router and the current path |

A page may return any widget, a string (it becomes text) or a list (it becomes a column). The
function can also be called `default`, like `export default`.

### Pages with state

When a page has its own state (a text being typed, a selected tab), make it a component. Its
props get the same values, and its state lives while the page is open:

```python
class Page(pz.Component):
    params: dict = {}
    query: dict = {}
    name = pz.state("")

    def render(self):
        return ui.input(self.name, on_input=lambda v: setattr(self, "name", v))
```

The state starts over when the page's `params` change (`/products/3` to `/products/4`), but not
when only the query does (`?sort=price`).

## Layouts keep their state

`layout.py` wraps every page under its folder and the layouts inside it. It **keeps its state**
while you navigate between them, so a sidebar stays collapsed and a scroll position stays put:

```python
# app/layout.py
import pyzed as pz
from pyzed import ui

title_template = "%s · Shop"     # page titles become "Products · Shop"


class Layout(pz.Component):
    children: list = ()
    collapsed = pz.state(False)      # survives every navigation

    def render(self):
        side = pz.column([
            pz.nav_link("/", "Home", icon="house"),
            pz.nav_link("/products", "Products", icon="shopping-bag"),
        ], width=200, padding=12)
        return pz.row([side if not self.collapsed else None, pz.column(self.children, padding=24)],
                      height="fill")
```

A function works too when the layout has no state: `def layout(children): ...`.

Layouts nest: `app/settings/layout.py` adds tabs inside the root layout, and both stay while you
move between the settings pages.

![Settings: the counter of the template starts over on every tab, the collapsed sidebar of the layout stays collapsed](/pyzed/media/routing/layouts.webp)

## Templates start over

`template.py` is the same as a layout, except that it **starts over** on every navigation: its
components and their state are created again, so an entrance animation plays again and a
counter goes back to zero (in the animation above, "Clicked 2 times" becomes "Clicked 0 times"
on the next tab, while the sidebar stays as it was).

A layout below a dynamic folder (`[id]/layout.py`) starts over when its parameter changes:
each product gets a fresh one.

## Sharing values with what is inside

A layout can share values with every component inside it through `provide`, which components
read with `pz.use_context`:

```python
# app/teams/[team]/layout.py
async def load(params):
    return await api.team(params["team"])


def provide(data):
    return {"team": data}


def layout(children):
    return children
```

```python
# any component below
team = pz.use_context("team")
```

For values the whole app shares (the session, the cart), use a [global store](/pyzed/routing/data/state/).

## Titles

The window's title follows the page:

```python
title = "Products"                 # a fixed title

def title(data):                   # or computed from the page's data
    return data.name

metadata = {"title": "Products"}   # like Next.js' metadata
```

The closest `title_template` above the page shapes it (`"%s · Shop"`), and `default_title` is
used for pages without a title. Without either, the app's own `title` shows.
