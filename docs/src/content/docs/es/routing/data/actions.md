---
title: "Cambiar datos: acciones"
description: "pz.action para guardar, pedir e iniciar sesión: pending, result y error para el botón, datos frescos después, invalidar otras páginas y código al terminar."
sidebar:
  order: 2
---

`load` **lee** datos. Para **cambiarlos** (guardar un formulario, hacer un pedido, iniciar
sesión) usa una acción: una función decorada con `@pz.action`, llamada desde cualquier botón. Es
la versión de Pyzed de las server actions de Next.js con `useActionState`.

```python
# app/(shop)/products/[id]/page.py
import pyzed as pz
from pyzed import ui

import api
from state import cart


@pz.action
async def add_to_cart(product):
    await api.place_order([product.id])      # fuera del hilo de la interfaz
    cart.add(product.id)                     # el estado global: el contador de la cabecera se actualiza


def page(data):
    return ui.button("Añadiendo…" if add_to_cart.pending else "Añadir al carrito",
                     lambda: add_to_cart(data), loading=add_to_cart.pending)
```

![Añadir al carrito: el botón muestra que está ocupado, el contador del carrito sube y una notificación lo confirma](/pyzed/media/routing/actions.webp)

## Qué pasa al llamarla

1. `pending` pasa a `True`, así que el botón puede decir «Añadiendo…» o mostrar un spinner.
2. La función corre **fuera del hilo de la interfaz**: `async def` en el bucle de Pyzed, un `def`
   normal en un hilo de trabajo. La ventana sigue respondiendo.
3. Al terminar, `result` tiene lo que devolvió, o `error` la excepción que lanzó.
4. El `load` de la página actual corre otra vez (`refresh=True`), dejando los datos viejos en
   pantalla mientras tanto, para que lo que muestra la página coincida con el servidor.

Una acción es un [`pz.Store`](/pyzed/es/routing/data/state/): los componentes que leen
`pending`, `result` o `error` se vuelven a dibujar solos cuando cambian.

| Atributo o llamada | Qué es |
| --- | --- |
| `pending` | `True` mientras corre |
| `result` | lo que devolvió la última llamada |
| `error` | la excepción de la última llamada, o `None` |
| `calls` | cuántas veces se llamó |
| `action(...)` | la empieza y devuelve un `Future` |
| `action.run(...)` | la empieza y espera (tests y scripts) |
| `action.reset()` | borra `result` y `error` |

## Opciones

```python
@pz.action(refresh=False,                   # no recargar la página actual después
           invalidate=["/products", "/products/[id]"],   # marcar como viejos los datos de otras páginas
           on_done=lambda result: pz.use_router().push("/orders"),
           on_error=lambda error: pz.notify("No se pudo guardar", str(error)))
async def save(form):
    ...
```

`on_done(result)` y `on_error(error)` corren **en el hilo de la interfaz**, así que pueden
navegar, cambiar el estado de un componente o mostrar una notificación. Sin `on_error`, el error
se imprime en la terminal y se guarda en `error` para que la página lo muestre.

`invalidate` acepta direcciones (`"/products/3"`) o patrones (`"/products/[id]"`, todos los
productos): como `revalidatePath` de Next.js, sus datos se cargan otra vez la próxima vez que se
vean.

## Mostrar errores

```python
def page(data):
    return pz.column([
        ui.button("Guardar", lambda: save(data), loading=save.pending),
        ui.label(str(save.error), color="danger") if save.error else None,
    ])
```

## Un formulario para iniciar sesión

La página de login del ejemplo guarda el nombre en el estado del componente, inicia sesión con
una acción y va adonde el [middleware](/pyzed/es/routing/advanced/middleware/) paró al usuario:

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
            ui.button("Entrar", lambda: sign_in(self.name, self.query.get("next")),
                      loading=sign_in.pending),
        ])
```

## Conviene saber

- Una acción definida al principio de un archivo es **una para toda la app**: dos páginas de
  producto comparten su `pending`. Para una por elemento, guarda el estado en el componente del
  elemento (`pz.state`) o crea la acción en el `setup` de un componente.
- Deja la red y la base de datos en `api.py` y llámalas desde las acciones; la página solo decide
  qué mostrar.
- En los tests, `add_to_cart.run(product)` espera el resultado y lanza su error.
