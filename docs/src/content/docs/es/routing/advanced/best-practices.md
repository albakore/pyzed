---
title: Buenas prácticas
description: "Cómo organizar una app de Pyzed con rutas: dónde va cada parte del código, leer y cambiar datos, estado global, middleware, probar las páginas y mantener rápida la ventana."
sidebar:
  order: 4
---

## Dónde va cada cosa

```text
shop/
├── main.py            solo arranca el router
├── api.py             cada llamada al servidor o a la base de datos
├── state.py           los stores: sesión, carrito, preferencias
├── app/
│   ├── layout.py      el marco: barra lateral, cabecera
│   ├── middleware.py  comprobar la sesión y redirigir
│   ├── _components/   piezas de interfaz que comparten las rutas
│   └── products/
│       ├── page.py    lo que muestra /products, y su load
│       └── loading.py
└── tests/
```

| Código | Va en |
| --- | --- |
| leer de un servidor o una base de datos | `load`, llamando a `api.py` |
| un cambio (guardar, pedir, iniciar sesión) | una `@pz.action`, llamando a `api.py` |
| valores que comparten muchas páginas | un `pz.Store` en `state.py` |
| un filtro, una pestaña, un número de página | la query (`?sort=price`) |
| lo que escribe o abre un componente | `pz.state` |
| comprobaciones antes de una página | `middleware.py` |
| avisar al usuario de que algo pasó | `pz.notify` o un toast |

## Datos

- **Lee en `load`, cambia en acciones.** La página solo decide qué mostrar con `data`.
- **Una petición por necesidad.** Junta lo que necesita una página en un `load` con
  `asyncio.gather`, en vez de lanzar peticiones desde los componentes.
- **Deja trabajar a la caché.** No copies `data` en un store; tras una acción la página se
  refresca sola, e `invalidate` marca otras páginas.
- **Falla a la vista.** Lanza desde `load` (`response.raise_for_status()`): `error.py` lo muestra
  con «Reintentar». Usa `pz.not_found()` para lo que no existe.

## Estado

- **Un store por tema** (`Session`, `Cart`, `Preferences`), una instancia de cada uno, en un módulo.
- **Reemplaza los valores** (`cart.items = [...]`) en vez de cambiarlos en su sitio, o llama a
  `changed()` después.
- **`persist` solo para lo que el usuario espera encontrar la próxima vez** (preferencias, un
  borrador), nunca tokens ni contraseñas: se guardan como JSON sin cifrar.

## Velocidad

- Nada que espere en una página, un layout o `render()`. Los `await` van en `load` o en una acción.
- Pon una pieza pesada (una tabla grande, un gráfico) en un componente, para que solo se vuelva a
  dibujar cuando cambien sus entradas.
- Añade `loading.py` donde una página tarda, cerca de la página, para que los layouts se queden quietos.
- Los enlaces precargan al pasar el ratón; para un siguiente paso evidente, usa `router.prefetch(href)`.

## Tests

Un router funciona sin ventana, así que un test puede navegar y comprobar qué muestra cada página:

```python
import pyzed as pz

import api


def test_product_page(monkeypatch):
    monkeypatch.setattr(api, "DELAY", 0)
    router = pz.Router("app", initial="/products/3")
    router.view()
    router.wait()                          # los load
    assert router.title == "4K monitor · Shop"


def test_account_needs_a_session():
    router = pz.Router("app", initial="/account")
    router.view()
    router.wait()
    assert router.pathname == "/login"


def test_add_to_cart():
    add_to_cart.run(api.PRODUCTS[0])       # espera a la acción
    assert cart.count == 1
```

`pyzed route list` muestra cada dirección y sus archivos, una forma rápida de comprobar que las
carpetas dicen lo que querías.
