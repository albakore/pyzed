---
title: Rutas en código
description: "Rutas de Pyzed sin carpetas: un dict de páginas para una app de un solo archivo, un router dentro de tu propia app o de una zona, formularios de Pyzed Design como páginas y URLs para la web."
sidebar:
  order: 3
---

## Un dict en vez de carpetas

Una app de un solo archivo puede dar sus rutas como un dict. Un valor es la página, o un dict de
los archivos:

```python
import pyzed as pz
from pyzed import ui


def home():
    return ui.heading("Inicio")


def user(params):
    return ui.heading(f"Usuario {params['id']}")


def shell(children):
    return pz.row([pz.column([pz.nav_link("/", "Inicio"), pz.nav_link("/users/1", "Ada")], width=180),
                   pz.column(children, padding=24)])


pz.run(pz.RouterApp({
    "/": {"page": home, "layout": shell},
    "/users/[id]": {"page": user, "load": fetch_user, "loading": spinner, "title": "Usuario"},
}))
```

Las claves del dict de una ruta son los nombres de archivo (`page`, `layout`, `template`,
`loading`, `error`, `not_found`, `middleware`) más `load`, `title`, `metadata` y `matcher`.

## Un router dentro de tu propia app

Un router cabe en cualquier `pz.App`, o en una zona de ella (el lado derecho de un split, una
pestaña):

```python
class Mail(pz.App):
    def __init__(self):
        self.router = pz.Router("app", initial="/inbox")

    def view(self):
        return pz.row([sidebar(), self.router.view()])

    def on_key(self, combo):
        return self.router.handle_key(combo) or None     # Alt+Izquierda / Alt+Derecha
```

## Formularios de Pyzed Design

Un `page.pzform` hecho en [Pyzed Design](/pyzed/es/guides/designer/) funciona como página:
ponlo en la carpeta de la ruta en lugar de `page.py`. Se coloca en el espacio que le dejan los
layouts, y sus manejadores pueden navegar con `pz.use_router().push(...)`.

## En la web

Las direcciones son URLs normales (`/products/3?sort=price#reviews`), así que la misma carpeta
`app/` corresponde una a una a la barra de direcciones de un navegador. `router.url` y
`router.location` dan la actual, y `push` acepta cualquiera de ellas.
