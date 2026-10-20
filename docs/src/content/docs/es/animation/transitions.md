---
title: Transiciones y estados
description: "Anima cambios en Pyzed como en CSS: widget.transition() va hacia los valores nuevos, los estados de estilo hover y pressed se animan, pz.presence cambia de página con animaciones de entrada y salida, pz.stagger escalona listas y las ventanas se abren con transiciones."
sidebar:
  order: 4
---

Una animación se reproduce sola. Una **transición** se reproduce cuando algo cambia: se abre un
panel, se selecciona una fila, cambia la página. Tú solo pones el valor nuevo y Pyzed anima el camino.

## transition()

`widget.transition(**props)` fija valores de propiedades y **anima cada cambio** hacia ellos, como un
`transition` de CSS. Cambia los valores en `view()` y el widget se mueve hacia ellos:

![Una barra lateral se estrecha hasta dejar solo los iconos y se vuelve a ensanchar al pulsar el botón Menu, las tarjetas de al lado se recolocan y el color de la fila seleccionada pasa a otra fila](/pyzed/media/animation/transition.webp)

```python
def view(self):
    lateral = pz.column(elementos).transition(width=220 if self.abierto else 64, duration=220,
                                              easing="ease_out_cubic")
    etiqueta.transition(opacity=1 if self.abierto else 0)
    fila.transition(background="accent" if seleccionada else "panel", duration=260)
```

- `duration` (200 ms por defecto), `delay` y `easing` (`"ease_out"` por defecto) se aplican a todas
  las propiedades.
- Una propiedad puede tener su propio tiempo: `transition(scale={"value": 1.1, "duration": 90, "easing": "spring"})`.
- La primera vez que aparece el widget muestra los valores al momento; solo se animan los cambios
  posteriores.

:::tip[¿transition() o animate()?]
Usa `transition()` para un valor que sigue el estado de tu app (abierto o cerrado, seleccionado o no).
Usa `animate()` para un movimiento que se reproduce solo (una entrada, un efecto de hover, un bucle).
:::

## Estados de estilo, como en CSS

Un [estilo](/pyzed/es/theming/styles/) puede decir cómo se ve un widget mientras el puntero está
encima (`hover`), mientras está pulsado (`pressed`) y mientras tiene el foco del teclado (`focus`).
Añade `transition` y el cambio se anima, como `:hover` con `transition` en CSS:

![Tres widgets que reaccionan al puntero: un botón cambia de color y sube, un botón con borde se vuelve rojo y una tarjeta crece un poco con un borde de color](/pyzed/media/animation/states.webp)

```python
ui.button("Guardar", self.guardar).style(
    background="accent", radius=6,
    hover={"background": "#4f8cff", "translate": (0, -1)},
    pressed={"scale": 0.97},
    transition=120,                      # milisegundos, "0.2s", True o {"duration", "easing", "delay"}
)
```

Un estado puede cambiar `background`, `color`, `border_color`, `border_width`, `radius`, `opacity`,
`translate`, `scale`, `rotate` y `blur`. Ninguna mueve a los widgets de alrededor, así que el hover
nunca descoloca el layout. Mira [Estilos](/pyzed/es/theming/styles/#estados-y-transiciones) para las
hojas de estilo y los estilos con nombre.

## Presence y stagger

`pz.presence(contenido, key)` anima el contenido **al entrar y al salir** cuando cambia `key`. El
contenido viejo se queda en pantalla mientras sale, así que las páginas, las pestañas y los pasos de
un asistente pueden cruzarse:

![Tres pestañas: al pulsar una, la página vieja sale por la izquierda mientras la nueva entra por la derecha y sus filas aparecen escalonadas](/pyzed/media/animation/presence.webp)

```python
pz.presence(self.vista_pagina(), key=self.pagina, enter="fade_in_right", exit="fade_out_left")
```

`enter` y `exit` aceptan presets u objetos `pz.Animation`. Dale un `id` cuando una misma línea de
código crea varias presencias (por defecto usa el archivo y la línea desde donde se llama).

`pz.stagger(elementos, animacion, step=40)` le da a cada elemento la misma animación, cada uno
`step` milisegundos después del anterior, para que una lista entre en cascada:

```python
pz.column(pz.stagger([fila(e) for e in self.elementos], "fade_in_up", step=30))
```

## Transiciones de ventana

Una ventana se anima al abrirse y al cerrarse. Pon `transition` (un nombre de
`pz.animation.WINDOW_TRANSITIONS`, un preset o una `pz.Animation`) y, si quieres, `exit_transition`:

![Tres ventanas que se abren con zoom, pop y slide up, y luego se cierran](/pyzed/media/animation/windows.webp)

```python
class Ajustes(pz.Window):
    transition = "zoom"            # fade, zoom, pop, slide_up, slide_down, slide_left, slide_right
    exit_transition = "fade_out"
```

La ventana sigue abierta hasta que termina su animación de salida. La ventana principal de la app
acepta los mismos atributos. Mira [Ventanas](/pyzed/es/guides/windows/).
