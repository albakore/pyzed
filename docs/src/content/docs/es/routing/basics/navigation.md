---
title: Navegar
description: "Enlaces, enlaces de barra lateral, push, replace, back y forward del router, teclas del historial, direcciones relativas y los hooks que leen la dirección actual."
sidebar:
  order: 3
---

![Recorriendo la tienda: enlaces, un producto que carga, Alt+Izquierda para volver](/pyzed/media/routing/navigation.webp)

## Enlaces

```python
pz.link("/products/3", "Ver el monitor")           # texto en el color de acento
pz.link("/products/3", ui.card(...))               # cualquier widget
pz.link("?sort=price", "Más baratos primero", replace=True)
pz.link(("/users/[id]", {"id": user.id}), user.name)
pz.nav_link("/settings", "Ajustes", icon="settings")   # una fila de barra lateral, seleccionada mientras está activa
```

Un enlace empieza el `load` de su página cuando el ratón pasa por encima (`prefetch=False` lo
desactiva), así que a menudo la página aparece al instante al hacer clic.

`pz.nav_link` está seleccionado mientras su dirección es la página actual o una de sus padres:
`/settings` sigue seleccionado en `/settings/profile`. `exact=True` lo selecciona solo en su
propia dirección.

## Desde el código

`pz.use_router()` da el router, en una página, un componente o un manejador de eventos:

```python
def save():
    api.save(form)
    pz.use_router().push("/orders")
```

| Llamada | Hace |
| --- | --- |
| `push(href)` | va allí y añade una entrada al historial |
| `replace(href)` | va allí en lugar de la entrada actual |
| `back()`, `forward()`, `go(n)` | se mueve por el historial (`can_go_back`, `can_go_forward`) |
| `refresh()` | vuelve a cargar los datos actuales, dejando los viejos en pantalla mientras tanto |
| `prefetch(href)` | empieza el `load` de una página antes de ir |
| `invalidate(*hrefs)` | marca como viejos los datos de unas páginas ([Acciones](/pyzed/es/routing/data/actions/)) |
| `is_active(href, exact=False)` | si `href` es la página actual o una de sus padres |
| `href("/users/[id]", id=7)` | construye `/users/7` |
| `routes()` | cada patrón de página: `["/", "/products", "/products/[id]"]` |
| `listen(callback)` | llama a `callback(location)` tras cada navegación |
| `url`, `location`, `pathname`, `query`, `params`, `history`, `title` | dónde está |

Las direcciones relativas funcionan como en un navegador: `"reviews"`, `"../"` y `"?page=2"`.

## Leer dónde estás

`pz.use_pathname()`, `pz.use_params()` y `pz.use_search_params()` leen la dirección, como sus
equivalentes de Next.js:

```python
class SortMenu(pz.Component):
    def render(self):
        query = pz.use_search_params()
        router = pz.use_router()
        return ui.segmented(["name", "price"], query.get("sort", "name"),
                            lambda v: router.replace(f"?sort={v}"))
```

Guardar un filtro o una pestaña en la query (`?sort=price`) en vez de en el estado de un
componente hace que el botón atrás vuelva a él, y que la página se pueda abrir en ese estado
desde un enlace o una notificación.

## Teclas y botones

Alt+Izquierda y Alt+Derecha (Cmd+[ y Cmd+] en macOS), los botones atrás y adelante del ratón y
el botón atrás de Android se mueven por el historial. `RouterApp` lo hace por ti; un router
dentro de tu propia app necesita `def on_key(self, combo): return self.router.handle_key(combo) or None`.

`on_navigate(location)` en un `RouterApp` corre tras cada navegación (para registrarla, por
ejemplo).
