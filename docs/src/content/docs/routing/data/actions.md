---
title: "Changing data: actions"
description: "pz.action for saves, orders and sign-ins: pending, result and error for the button, fresh data afterwards, invalidating other pages and running code when it ends."
sidebar:
  order: 2
---

`load` **reads** data. To **change** it (save a form, place an order, sign in) use an action: a
function decorated with `@pz.action`, called from any button. It is Pyzed's version of Next.js'
server actions with `useActionState`.

```python
# app/(shop)/products/[id]/page.py
import pyzed as pz
from pyzed import ui

import api
from state import cart


@pz.action
async def add_to_cart(product):
    await api.place_order([product.id])      # off the UI thread
    cart.add(product.id)                     # the global state: the header's badge updates


def page(data):
    return ui.button("Adding…" if add_to_cart.pending else "Add to cart",
                     lambda: add_to_cart(data), loading=add_to_cart.pending)
```

![Adding to the cart: the button shows it is busy, the cart's badge goes up and a notification confirms it](/pyzed/media/routing/actions.webp)

## What happens when you call it

1. `pending` becomes `True`, so the button can say "Adding…" or show a spinner.
2. The function runs **off the UI thread**: `async def` on Pyzed's loop, a plain `def` in a
   worker thread. The window keeps answering.
3. When it ends, `result` holds what it returned, or `error` the exception it raised.
4. The current page's `load` runs again (`refresh=True`), keeping the old data on screen
   meanwhile, so what the page shows matches the server.

An action is a [`pz.Store`](/pyzed/routing/data/state/): the components that read `pending`,
`result` or `error` draw again by themselves when they change.

| Attribute or call | What it is |
| --- | --- |
| `pending` | `True` while it runs |
| `result` | what the last call returned |
| `error` | the exception of the last call, or `None` |
| `calls` | how many times it was called |
| `action(...)` | starts it and returns a `Future` |
| `action.run(...)` | starts it and waits (tests and scripts) |
| `action.reset()` | clears `result` and `error` |

## Options

```python
@pz.action(refresh=False,                   # don't reload the current page afterwards
           invalidate=["/products", "/products/[id]"],   # mark other pages' data as old
           on_done=lambda result: pz.use_router().push("/orders"),
           on_error=lambda error: pz.notify("Couldn't save", str(error)))
async def save(form):
    ...
```

`on_done(result)` and `on_error(error)` run **on the UI thread**, so they can navigate, change a
component's state or show a notification. Without `on_error`, the error is printed in the
terminal and kept in `error` for the page to show.

`invalidate` takes addresses (`"/products/3"`) or patterns (`"/products/[id]"`, every product):
like Next.js' `revalidatePath`, their data loads again the next time they show.

## Showing errors

```python
def page(data):
    return pz.column([
        ui.button("Save", lambda: save(data), loading=save.pending),
        ui.label(str(save.error), color="danger") if save.error else None,
    ])
```

## A form that signs in

The login page of the example keeps the name in the component's state, signs in with an action
and goes where the [middleware](/pyzed/routing/advanced/middleware/) stopped the user:

```python
# app/login/page.py
def signed_in(next_href):
    pz.use_router().replace(next_href or "/account")


@pz.action(refresh=False, on_done=signed_in)
async def sign_in(name, next_href):
    session.user = await api.sign_in(name)
    return next_href


class Page(pz.Component):
    query: dict = {}
    name = pz.state("Ada")

    def render(self):
        return pz.column([
            ui.input(self.name, on_input=lambda v: setattr(self, "name", v)),
            ui.button("Sign in", lambda: sign_in(self.name, self.query.get("next")),
                      loading=sign_in.pending),
        ])
```

## Good to know

- An action defined at the top of a file is **one for the whole app**: two product pages share
  its `pending`. For one per item, keep the state in the item's component (`pz.state`) or make
  the action inside a component's `setup`.
- Keep the network and the database in `api.py` and call them from actions; the page only
  decides what to show.
- In tests, `add_to_cart.run(product)` waits for the result and raises its error.
