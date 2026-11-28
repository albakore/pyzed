---
title: "Rutas (pyzed.routing)"
description: "Referencia de la API de pyzed.routing: rutas en carpetas al estilo de Next.js para apps de escritorio en Python, con RouterApp, Router, enlaces, hooks de navegación, not_found y redirect."
sidebar:
  order: 10.8
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs_es.py. -->

Páginas como carpetas de `app/`, como el App Router de Next.js: `page.py`, `layout.py`,
`template.py`, `loading.py`, `error.py`, `not_found.py`, `[id]`, `[...slug]`, `[[...slug]]` y
`(grupo)`. Mira la [guía de rutas](/pyzed/es/guides/routing/).

```python
pz.run(pz.RouterApp("app", title="Tienda"))
```

## El router

### `RouterApp`

```python
class RouterApp
```

Una app cuya ventana muestra sus rutas: `routes` es la carpeta `app/` (junto al archivo que define la clase) o un dict de rutas en código. El título de la ventana sigue el de la página (`title`, `title(data)` o `metadata`, con el `title_template` del layout más cercano) y usa el `title` de la app cuando la página no tiene. Alt+Izquierda/Derecha, los botones laterales del ratón y el botón atrás de Android se mueven por el historial; `on_navigate(location)` se llama después de cada navegación.

```python
class Tienda(pz.RouterApp):
routes = "app"
title = "Tienda"
```

### `Router`

```python
class Router
```

Las rutas de una carpeta `app/` (una ruta relativa se busca junto al archivo que crea el router) o de un dict como `{"/": inicio, "/users/[id]": usuario}`. `view()` dibuja la ubicación actual con sus layouts, templates, carga, errores y no encontrado. Navega con `push`, `replace`, `back`, `forward`, `go`, `refresh` y `prefetch`; lee `location`, `pathname`, `params`, `query`, `url`, `history`, `title` y `pending`. `initial` es la primera ubicación y `stale_time` los segundos que los datos de una página siguen frescos.

```python
self.router = pz.Router("app")
# en view(): return self.router.view()
```

## Enlaces y hooks

### `link`

```python
link(href, content=None, *, replace=False, prefetch=True, router=None, size=None)
```

Un enlace a `href` (`<Link>` en Next.js): un texto en el color de acento, o cualquier widget, que navega al pulsarlo. `href` es una ruta (`"/products/3"`), relativa a la página actual (`"../"`, `"reviews"`), una query (`"?page=2"`) o `("/users/[id]", {"id": 7})`. `replace` reemplaza la entrada del historial; `prefetch` empieza el `load` de la página cuando el ratón pasa por encima.

```python
pz.link("/products/3", "Ver el monitor")
```

### `nav_link`

```python
nav_link(href, label, *, icon=None, exact=None, router=None, description=None)
```

Una fila de barra lateral o menú (`ui.list_item`) que va a `href` y se ve seleccionada mientras esa página, o una que cuelga de ella, está abierta (`exact=True`: solo esa página; la raíz `/` es exacta).

```python
pz.nav_link("/settings", "Ajustes", icon="settings")
```

### `use_router`

```python
use_router()
```

El router que dibuja esta vista (`useRouter()`). Fuera de una vista (un callback, un manejador de formulario) es el último router que dibujó.

```python
pz.use_router().push("/cart")
```

### `use_pathname`

```python
use_pathname()
```

La ruta actual, como `/products/3` (`usePathname()`).

### `use_params`

```python
use_params()
```

Los parámetros de la página actual: `{"id": "3"}` en `/products/[id]` (`useParams()`).

### `use_search_params`

```python
use_search_params()
```

La query actual como dict, con `get_all(clave)` para claves repetidas (`useSearchParams()`).

## Dentro de las páginas

### `not_found`

```python
not_found()
```

Deja de dibujar la página (o su `load`) y muestra el `not_found` más cercano, como `notFound()` de Next.js.

### `redirect`

```python
redirect(href, *, push=False)
```

Va a `href` en lugar de la página que se está dibujando (desde una página, un layout o un `load`). Reemplaza la entrada actual del historial; `push=True` añade una.

```python
pz.redirect("/login")
```

### `Location`

```python
@dataclass
class Location(pathname='/', search='', hash='')
```

Dónde está el router: `pathname` (`/products/3`), la query `search` sin `?` y el `hash` sin `#`. Las mismas partes que una URL del navegador, así que una ruta se corresponde tal cual con una dirección web. `query` la da como dict y `href` como texto.

### `SearchParams`

```python
class SearchParams
```

La query de la URL (`?tab=reviews&tag=a&tag=b`) como dict de los primeros valores. `get_all("tag")` da todos los valores de una clave repetida y `str()` la query codificada.
