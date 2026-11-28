---
title: Middleware
description: "middleware.py en Pyzed: comprobar la sesión, redirigir, reescribir y proteger antes de mostrar una página, con matchers, comprobaciones async y valores para las páginas."
sidebar:
  order: 1
---

Un middleware es código que corre **antes de cada navegación**, antes de cualquier `load` y antes
de dibujar la página. Es el sitio para las comprobaciones que afectan a muchas páginas a la vez:
¿ha iniciado sesión el usuario?, ¿puede ver esto?, ¿esta dirección vieja debería ir a otro sitio?

```python
# app/middleware.py
from state import session

matcher = ["/account/:path*"]           # solo estas direcciones (opcional)


def middleware(request):
    if not session.signed_in:
        return request.redirect(f"/login?next={request.pathname}")
    request.locals["user"] = session.user     # las páginas lo reciben como `locals`
```

![La página de la cuenta está detrás de un middleware: va al login y después vuelve a la cuenta](/pyzed/media/routing/middleware.webp)

## Qué puede responder

| Devuelve | Qué pasa |
| --- | --- |
| nada (`None`) | corre el middleware siguiente y después se ve la página |
| `request.redirect("/login")` | va allí en su lugar, reemplazando la entrada (`push=True` deja la vieja en el historial) |
| `request.rewrite("/maintenance")` | muestra esa ruta, pero la dirección no cambia |
| `False` | se queda donde está (un formulario sin guardar, por ejemplo) |
| `pz.not_found()` | muestra el `not_found.py` más cercano |
| una excepción | la muestra el `error.py` más cercano |

`pz.redirect(...)` y `pz.rewrite(...)` también sirven, devueltos o lanzados.

## La petición

| Atributo | Qué es |
| --- | --- |
| `pathname`, `query`, `hash`, `href` | adónde va: `/account`, `{"tab": "orders"}`... |
| `location`, `previous` | esa dirección, y la actual (`None` al arrancar) |
| `action` | `"start"`, `"push"`, `"replace"`, `"back"`, `"forward"` o `"refresh"` |
| `route`, `params` | el patrón que responde (`"/products/[id]"`) y sus valores; `route` es `None` si no responde ninguna página |
| `locals` | un dict que llega como `locals` a las páginas, layouts, `load` y `provide` de esa dirección |
| `router` | el router |
| `matches("/admin/:path*")` | si la dirección coincide con un patrón |

## Dónde corre

Un `middleware.py` corre para cada dirección **por debajo de su carpeta**. Si hay varios en el
camino, primero corren los exteriores, así que `app/middleware.py` puede comprobar la sesión y
`app/admin/middleware.py` que el usuario es administrador.

`matcher` limita un archivo a algunas direcciones. Acepta la sintaxis de Next.js o la de las
carpetas:

| Patrón | Coincide con |
| --- | --- |
| `/about` | esa dirección |
| `/products/:id` o `/products/[id]` | una parte: `/products/3` |
| `/docs/:path*` o `/docs/[[...path]]` | `/docs` y todo lo de debajo |
| `/docs/:path+` o `/docs/[...path]` | todo lo de debajo de `/docs`, no `/docs` |
| `/users/*/posts` | `*` es una parte cualquiera |
| `/files/**` | cualquier cosa por debajo |
| `^/v[0-9]+/` | una expresión regular, si empieza por `^` |

Una lista coincide con cualquiera de sus patrones, y una función (`matcher = lambda request: ...`)
decide por su cuenta.

## Middleware en código

También se le puede dar middleware al router. Corre **antes** que los archivos:

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
    middleware = [log, admins_only]       # o: pz.Router("app", middleware=[...])
```

## Esperar algo

`async def middleware` corre fuera del hilo de la interfaz, en el bucle de Pyzed: la página
actual sigue en pantalla hasta que responde. Si el usuario vuelve a navegar mientras tanto, gana
la navegación más nueva.

```python
async def middleware(request):
    if not await api.token_is_valid(session.token):
        return request.redirect("/login")
```

Que sea corto: retrasa cada navegación a la que se aplica. Los datos que muestra la página van en
`load`.

## Ejemplos

```python
# Direcciones viejas
def middleware(request):
    if request.pathname.startswith("/shop/"):
        return request.redirect(request.pathname.replace("/shop/", "/products/", 1))


# Modo mantenimiento: la misma dirección, otra página
def middleware(request):
    if settings.maintenance and request.route != "/maintenance":
        return request.rewrite("/maintenance")


# No salir de un formulario con cambios sin guardar
def middleware(request):
    if draft.dirty and request.action != "refresh":
        pz.notify("Cambios sin guardar", "Guárdalos o descártalos primero")
        return False
```

## Diferencias con Next.js

- Corre en la app, no en un servidor, así que puede leer directamente el estado global (`pz.Store`).
- Hay uno por carpeta, no uno por proyecto, y se suman de fuera hacia dentro.
- `locals` sustituye a pasar valores en las cabeceras de la petición.
