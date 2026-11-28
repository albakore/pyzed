---
title: Páginas, layouts y templates
description: "Páginas como funciones o componentes, los argumentos que reciben, layouts anidados que guardan su estado, templates que empiezan de cero, compartir valores con provide y los títulos de la ventana."
sidebar:
  order: 2
---

## Páginas

Un archivo de ruta define una función con el nombre del archivo. Recibe **solo los argumentos que
nombra**, en cualquier orden:

```python
# app/about/page.py
import pyzed as pz
from pyzed import ui

title = "About"        # el título de la ventana en esta página


def page(params, query, router):
    return pz.column([ui.heading("About"), ui.label(f"{len(router.history)} páginas visitadas")])
```

| Argumento | Qué es |
| --- | --- |
| `params` | las partes dinámicas de la dirección: `{"id": "3"}` |
| `query` | la query string como dict: `?sort=price` da `{"sort": "price"}` (`query.get_all("tag")` para claves repetidas) |
| `data` | lo que devolvió el `load` del archivo ([Llamar al servidor](/pyzed/es/routing/data/data-fetching/)) |
| `locals` | lo que el [middleware](/pyzed/es/routing/advanced/middleware/) dejó para esta navegación |
| `children` | en layouts y templates: lo que va dentro |
| `error`, `reset` | en `error.py`: la excepción y una función que lo reintenta |
| `router`, `pathname` | el router y la ruta actual |

Una página puede devolver cualquier widget, un texto (se vuelve un texto en pantalla) o una lista
(se vuelve una columna). La función también puede llamarse `default`, como `export default`.

### Páginas con estado

Cuando una página tiene estado propio (un texto que se escribe, una pestaña elegida), hazla un
componente. Sus props reciben los mismos valores, y su estado vive mientras la página está
abierta:

```python
class Page(pz.Component):
    params: dict = {}
    query: dict = {}
    name = pz.state("")

    def render(self):
        return ui.input(self.name, on_input=lambda v: setattr(self, "name", v))
```

El estado empieza de cero cuando cambian los `params` de la página (`/products/3` a
`/products/4`), pero no cuando solo cambia la query (`?sort=price`).

## Los layouts guardan su estado

`layout.py` envuelve cada página de su carpeta y los layouts de dentro. **Guarda su estado**
mientras navegas entre ellas, así que una barra lateral sigue plegada y un scroll se queda donde
estaba:

```python
# app/layout.py
import pyzed as pz
from pyzed import ui

title_template = "%s · Shop"     # los títulos quedan como "Products · Shop"


class Layout(pz.Component):
    children: list = ()
    collapsed = pz.state(False)      # sobrevive a cada navegación

    def render(self):
        side = pz.column([
            pz.nav_link("/", "Inicio", icon="house"),
            pz.nav_link("/products", "Productos", icon="shopping-bag"),
        ], width=200, padding=12)
        return pz.row([side if not self.collapsed else None, pz.column(self.children, padding=24)],
                      height="fill")
```

Una función también sirve cuando el layout no tiene estado: `def layout(children): ...`.

Los layouts se anidan: `app/settings/layout.py` añade pestañas dentro del layout raíz, y los dos
se quedan mientras te mueves entre las páginas de ajustes.

![Ajustes: el contador del template empieza de cero en cada pestaña, la barra lateral plegada del layout sigue plegada](/pyzed/media/routing/layouts.webp)

## Los templates empiezan de cero

`template.py` es igual que un layout, salvo que **empieza de cero** en cada navegación: sus
componentes y su estado se crean otra vez, así que una animación de entrada vuelve a sonar y un
contador vuelve a cero (en la animación de arriba, «Clicked 2 times» pasa a «Clicked 0 times» en
la pestaña siguiente, mientras la barra lateral sigue como estaba).

Un layout debajo de una carpeta dinámica (`[id]/layout.py`) empieza de cero cuando cambia su
parámetro: cada producto tiene uno nuevo.

## Compartir valores con lo de dentro

Un layout puede compartir valores con todos los componentes de dentro con `provide`, que los
componentes leen con `pz.use_context`:

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
# cualquier componente de debajo
team = pz.use_context("team")
```

Para valores que comparte toda la app (la sesión, el carrito), usa un
[store global](/pyzed/es/routing/data/state/).

## Títulos

El título de la ventana sigue a la página:

```python
title = "Products"                 # un título fijo

def title(data):                   # o calculado con los datos de la página
    return data.name

metadata = {"title": "Products"}   # como el metadata de Next.js
```

El `title_template` más cercano por encima de la página le da forma (`"%s · Shop"`), y
`default_title` se usa para las páginas sin título. Sin ninguno de los dos, se ve el `title` de
la app.
