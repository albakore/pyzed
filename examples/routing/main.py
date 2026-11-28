"""A small store with routes in folders, like Next.js' App Router.

    python examples/routing/main.py

Every folder of ``app/`` is a part of the URL:

- ``layout.py`` draws the sidebar around every page and keeps its state while you navigate.
- ``(shop)`` is a group: it organizes the folders but is not part of the URL.
- ``products/[id]`` is dynamic (``/products/3``); its ``load`` runs in the background while
  ``loading.py`` shows a skeleton, and ``pz.not_found()`` shows ``not_found.py``.
- ``docs/[[...slug]]`` takes any number of parts (``/docs``, ``/docs/guide/routing``).
- ``settings/template.py`` starts over on every tab, its ``layout.py`` doesn't.
- ``middleware.py`` sends ``/account`` to ``/login`` until you sign in (``state.session``).
- ``api.py`` is the pretend server: pages read it in ``load``; "Add to cart" changes it with a
  ``pz.action``, updates the global cart (``state.py``) and shows a desktop notification.

Alt+Left / Alt+Right and the mouse's side buttons go back and forward.
"""

import pyzed as pz


class Store(pz.RouterApp):
    routes = "app"
    title = "Pyzed Store"
    size = (1040, 680)


if __name__ == "__main__":
    pz.run(Store)
