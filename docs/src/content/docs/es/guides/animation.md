---
title: Animación y efectos
description: "Anima cualquier widget de Pyzed como en la web (presets, keyframes, transiciones, presence) y añade rotación, desenfoque, glow, bloom, glass y opacidad."
sidebar:
  order: 3.5
---

Todo widget puede animarse. Las animaciones se reproducen de forma nativa a la frecuencia de la
pantalla: Python las describe una vez en `view()` y la parte de Rust las reproduce, así que una
animación en marcha nunca llama a tu código.

![Presets, efectos, la transición de un panel y transiciones entre páginas](../../../../assets/tutorials/animations.png)

```python
pz.text("Guardado").animate("fade_in_up")                       # al aparecer
tarjeta.animate("lift", on="hover")                             # avanza en hover y vuelve al salir
icono.animate("pulse", repeat="infinite")                       # en bucle
campo.animate("shake", key=self.errores)                        # se repite cuando cambia key
boton.animate(on="press", scale=0.96, duration=90)              # valores a medida
panel.transition(opacity=1 if self.abierto else 0, x=0 if self.abierto else -24)   # como CSS
```

Ejecuta [`examples/animations.py`](https://github.com/albakore/pyzed/blob/main/examples/animations.py) para probarlas todas.

## animate()

`widget.animate(*animaciones, **opciones)` acepta nombres de presets, objetos `pz.Animation` (o
listas de ellos) y estas opciones, que sobrescriben el timing propio de cada animación:

| Opción | Valores |
| --- | --- |
| `on` | Qué la reproduce. `"mount"` (por defecto) la reproduce cuando aparece el widget. `"hover"`, `"press"`, `"focus"` y `"active"` avanzan mientras se cumple la condición y vuelven atrás cuando termina. `"click"` la reproduce desde el principio en cada clic. |
| `duration`, `delay` | Milisegundos, o `"0.3s"` / `"300ms"`. |
| `easing` | Un nombre de `pz.animation.EASINGS` (`"ease"`, `"ease_out_cubic"`, `"ease_out_back"`, `"spring"`...), una Bézier cúbica `(x1, y1, x2, y2)` o `"steps(4)"`. |
| `repeat` | Un número de veces o `"infinite"`. |
| `direction` | `"normal"`, `"reverse"`, `"alternate"` o `"alternate_reverse"`. |
| `fill` | `"both"` (por defecto), `"forwards"`, `"backwards"` o `"none"`, como en CSS. |
| `key` | Cualquier valor: cuando cambia, la animación vuelve a empezar (la sacudida de un error, el destello de "copiado"). |
| `active` | `True` la reproduce (hacia delante) y `False` la devuelve: `animate("glow_pulse", active=self.grabando)`. |
| `on_start`, `on_end` | Un callable o mensaje que se envía al empezar y al terminar. |

Llamar a `animate()` varias veces añade animaciones; cada una conserva su disparador:

```python
ui.button("Comprar", self.comprar).animate("fade_in_up").animate("lift", on="hover").animate("shrink", on="press")
```

### Valores de propiedades

Sin preset, los valores de las propiedades *son* la animación. En `mount` el widget parte de
ellos y termina en su aspecto propio; con los demás disparadores va hacia ellos:

```python
pz.text("Hola").animate(opacity=0, y=12, duration=250)          # aparece desde abajo
tarjeta.animate(on="hover", scale=1.03, background="elevated")  # crece y se aclara en hover
```

Las propiedades animables son:

| Propiedad | Valores |
| --- | --- |
| `opacity`, `scale` | Números (`scale` alrededor del centro). |
| `x`, `y` | Píxeles o `"50%"` del tamaño del propio widget. |
| `rotate` | Grados en sentido horario alrededor del centro, o `"0.25turn"`, `"1.5rad"`, `"90deg"`. |
| `blur` | Un desenfoque gaussiano del widget, en píxeles. |
| `background`, `border_color`, `color`, `glow_color` | Hex o tokens del tema. |
| `radius`, `border_width`, `glow` | Píxeles. |
| `width`, `height`, `padding`, `font_size` | Píxeles. Cambian el layout, así que los widgets de alrededor se mueven con él. |

```python
icono.animate("spin")                                           # un indicador de carga
tarjeta.animate(on="hover", rotate=-3, scale=1.02)              # se inclina en hover
lateral.transition(width=240 if self.abierto else 56, duration=200)   # el contenido de al lado se recoloca
titulo.transition(font_size=28 if self.grande else 16)
```

`padding` anima el padding interior de un contenedor o botón (los cuatro lados siguen el mismo
valor); en cualquier otro widget añade espacio alrededor. `font_size` cambia todos los textos de dentro.

## Keyframes

`pz.Animation` es una regla CSS `@keyframes` con su timing. Los frames son una lista (repartidos
por igual) o un dict de offsets (`0` a `1`, `"50%"`, `"from"`, `"to"`); un frame puede fijar su
propio `easing`:

```python
meneo = pz.Animation([{"x": 0}, {"x": -6}, {"x": 6}, {"x": 0}], duration=300)
latido = pz.Animation({0: {"scale": 1}, "30%": {"scale": 1.15, "easing": "ease_out"}, 1: {"scale": 1}},
                      duration=900, repeat="infinite")
corazon.animate(latido)

pz.define_animation("meneo", meneo)        # ahora animate("meneo") funciona en cualquier sitio
```

Una propiedad que falte al principio o al final sale del valor propio del widget o vuelve a él.
`Animation.to_dict()` y `Animation.from_dict()` guardan y cargan animaciones como JSON.

## Transiciones

`widget.transition(**props)` fija valores de propiedades y anima cada cambio, como una
`transition` de CSS. Cambia los valores en `view()` y el widget se mueve hacia ellos:

```python
pz.container(menu).transition(x=0 if self.abierto else -240, opacity=1 if self.abierto else 0, duration=220)
fila.transition(background="accent" if seleccionada else "panel", easing="ease_out")
```

`duration` y `easing` se aplican a todas las propiedades; da a una propiedad un dict para
temporizarla por separado: `transition(scale={"value": 1.1, "duration": 90, "easing": "spring"})`.

## Presence y stagger

`pz.presence(content, key)` anima la entrada y salida del contenido cuando cambia `key`, y
mantiene en pantalla el contenido anterior mientras sale (transiciones entre páginas, pestañas, asistentes):

```python
pz.presence(self.vista_pagina(), key=self.pagina, enter="slide_in_right", exit="fade_out")
```

Dale un `id` cuando una misma línea de código cree varias presences (por defecto usa el archivo y la línea desde donde se llama).

`pz.stagger(items, animacion, step=40)` da a cada elemento la misma animación, cada uno
empezando `step` milisegundos después del anterior, para que una lista entre en cascada:

```python
pz.column(pz.stagger([fila(item) for item in self.items], "fade_in_up", step=30))
```

## Transiciones de ventana

Una ventana se anima al abrirse y al cerrarse con `transition` (un nombre de
`pz.animation.WINDOW_TRANSITIONS`, un preset o una `pz.Animation`) y, opcionalmente, `exit_transition`:

```python
class Ajustes(pz.Window):
    transition = "zoom"            # fade, zoom, pop, slide_up, slide_down, slide_left, slide_right
    exit_transition = "fade_out"
```

La ventana sigue abierta hasta que termina su animación de salida. Ver [Ventanas](/pyzed/es/guides/windows/).

## Efectos

Los efectos son propiedades de [estilo](/pyzed/es/guides/styles/), así que funcionan con
`style()`, `pz.Style` y los estilos con nombre:

| Propiedad | Qué hace |
| --- | --- |
| `opacity` | De 0 a 1. Desvanece el widget y todo lo que tiene dentro. |
| `rotate` | Grados en sentido horario (o `"0.25turn"`, `"1rad"`): dibuja el widget girado sobre su centro. |
| `blur` | Píxeles: desenfoca el widget y todo lo que tiene dentro. |
| `backdrop_blur` | Píxeles: desenfoca lo que hay detrás de la caja, dentro de sus esquinas redondeadas. |
| `glow` | Un halo suave alrededor de la caja: un color, un tamaño (color de acento) o `(color, tamaño)`. |
| `bloom` | Luz que desborda de las partes brillantes del widget: un color o `(color, intensidad)` con intensidad de 0 a 1. |
| `glass` | Un panel translúcido que desenfoca lo que tiene detrás, con un borde claro: `True`, un color de tinte o `{"tint": ..., "strength": 0.08, "blur": 20}`. |
| `translate` | `(x, y)` en píxeles o `"50%"`: dibuja el widget desplazado sin cambiar el layout. |
| `scale` | Dibuja el widget más grande o más pequeño alrededor de su centro. |

```python
pz.container(tarjeta).style(glass=True, radius=12, padding=16)
ui.button("Ir", self.ir).style(glow=("#22d3ee", 18))
insignia.style(bloom=("accent", 0.8), opacity=0.9)
pegatina.style(rotate=-8)
```

![Rotación, glass, bloom y desenfoque sobre un degradado](../../../../assets/tutorials/effects.png)

La rotación, el desenfoque, el desenfoque del fondo y el bloom los dibuja el renderer: el widget se
dibuja en su propia capa, que luego se gira, se desenfoca o se ilumina antes de llegar a la ventana.
En una caja (un widget con fondo o glass) bloom
añade además un halo suave y un borde iluminado; en un texto o icono sin caja solo brilla, y glass un degradado tintado, un borde y una
sombra; los que fijes tú mismo tienen prioridad. Glass luce mejor sobre un fondo colorido (un
degradado o una imagen). Las animaciones también pueden cambiar `glow` y `glow_color`: los presets
`glow`, `bloom`, `glow_pulse` y `glow_flash` los usan.

## Presets

`pz.animation.presets(categoria)` los lista; cada uno tiene una `description`.

| Categoría | Presets |
| --- | --- |
| Entrada | `fade_in`, `fade_in_up`, `fade_in_down`, `fade_in_left`, `fade_in_right`, `slide_in_up`, `slide_in_down`, `slide_in_left`, `slide_in_right`, `zoom_in`, `pop_in`, `bounce_in`, `drop_in`, `blur_in`, `rotate_in` |
| Salida | `fade_out`, `fade_out_up`, `fade_out_down`, `fade_out_left`, `fade_out_right`, `slide_out_up`, `slide_out_down`, `slide_out_left`, `slide_out_right`, `zoom_out`, `pop_out`, `blur_out`, `rotate_out` |
| Atención | `pulse`, `heartbeat`, `shake`, `wobble`, `bounce`, `flash`, `rubber_band`, `tada`, `swing`, `glow_flash` |
| Interacción (hover, press, focus) | `lift`, `grow`, `shrink`, `dim`, `glow`, `bloom`, `nudge_right`, `tilt` |
| Bucle | `float`, `breathe`, `blink`, `glow_pulse`, `throb`, `drift`, `spin` |

`pz.animation.ease(easing, t)` evalúa cualquier easing, útil para animar tus propios dibujos
en un [canvas](/pyzed/es/guides/canvas/) con las mismas curvas.

## Movimiento reducido y tests

`pz.set_reduced_motion(True)` apaga el movimiento: cada animación muestra al instante su estado
de reposo. Por defecto Pyzed sigue el ajuste "reducir movimiento" del sistema, leído al
arrancar la app; `set_reduced_motion(False)` o `True` lo reemplaza (ofrécelo como ajuste de tu
app), `None` vuelve a seguir al sistema y la variable de entorno `PYZED_REDUCED_MOTION` (`1` o
`0`) se impone a ambos. Ver [Accesibilidad](/pyzed/es/guides/accessibility/#reducir-movimiento).

Las capturas (`App.screenshot`, `pz.screenshot`) también muestran siempre el estado de reposo:
donde termina una animación de entrada, para que los tests y las imágenes de la documentación
sean estables. Para probar el comportamiento, revisa el árbol de widgets: `repr(widget)` termina
en `.animate(2 animation(s), 1 transition(s))`.

## Límites

- Las transformaciones son traslación, escala uniforme y rotación; no hay sesgado.
- Un widget girado o desenfocado recibe la entrada donde está su caja en el layout, no donde se dibuja.
- Un widget con rotación, desenfoque, desenfoque del fondo o bloom se dibuja encima de sus hermanos,
  así que su bloom puede iluminar los widgets de al lado.
- `backdrop_blur` desenfoca lo que la ventana dibujó antes del widget dentro de la misma capa padre
  (los scrollables y otros widgets que recortan empiezan una capa nueva).
- `width`, `height`, `padding` y `font_size` recalculan el layout en cada frame mientras se mueven,
  así que para vistas grandes es mejor `x`, `y` y `scale`.
- Las animaciones vuelven a empezar cuando un widget sale del árbol y vuelve. Usa una `key`
  estable, o `presence`, para controlar cuándo se repiten.
