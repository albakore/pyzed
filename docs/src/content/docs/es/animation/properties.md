---
title: Propiedades animables
description: "Todas las propiedades que puede cambiar una animación de Pyzed: opacidad, posición, escala, rotación, desenfoque, colores, radio, borde, brillo, tamaño, padding y tamaño de letra, con sus unidades y cómo se animan los valores."
sidebar:
  order: 2
---

Una animación cambia una o varias **propiedades** de un widget. Los mismos nombres sirven en todas
partes: en `animate()`, `transition()`, los keyframes de `pz.Animation` y las pistas de una línea de
tiempo.

![Doce tarjetas, cada una moviendo una propiedad de ida y vuelta: opacity, x, y, scale, rotate, blur, background, border color, radius, glow, width y font size](/pyzed/media/animation/properties.webp)

| Propiedad | Valores | Notas |
| --- | --- | --- |
| `opacity` | De `0` (invisible) a `1`. | Desvanece el widget y todo lo que contiene. |
| `x`, `y` | Píxeles, o `"50%"` del tamaño del propio widget. | Lo mueve sin mover a sus vecinos. |
| `scale` | Un número: `1` es su tamaño, `0.5` la mitad, `1.2` una quinta parte más grande. | Alrededor de su centro. |
| `rotate` | Grados en sentido horario, o `"0.25turn"`, `"1.5rad"`, `"90deg"`. | Alrededor de su centro. |
| `blur` | Píxeles. | Desenfoca el widget y todo lo que contiene. |
| `background`, `border_color`, `color`, `glow_color` | `"#rrggbb"`, `"#rrggbbaa"` o un token del tema (`"accent"`, `"elevated"`...). | Los colores se mezclan con suavidad. `color` cambia el texto de dentro. |
| `radius`, `border_width`, `glow` | Píxeles. | `glow` es el tamaño del halo alrededor de la caja. |
| `width`, `height` | Píxeles. | **Cambian el layout**: los widgets de alrededor se mueven. |
| `padding` | Píxeles. | Dentro de un contenedor o botón (los cuatro lados lo siguen); en otros widgets añade espacio alrededor. Cambia el layout. |
| `font_size` | Píxeles. | Todos los textos de dentro. Cambia el layout. |

`pz.animation.PROPERTIES` las enumera en código.

:::tip[Prefiere x, y, scale y opacity en vistas grandes]
`width`, `height`, `padding` y `font_size` vuelven a calcular el layout de la vista en cada fotograma
mientras se mueven. Va bien para una barra lateral o un título, pero en una página grande `x`, `y`,
`scale` y `opacity` cuestan menos y se ven igual.
:::

## Valores de propiedades como animación

Sin preset, los valores que pasas **son** la animación. Lo que significan depende del disparador:

| Disparador | El widget... |
| --- | --- |
| `mount` | **parte** de esos valores y termina en su aspecto propio: `animate(opacity=0, y=12)` aparece desde abajo. |
| `hover`, `press`, `focus`, `active` | **va hacia** esos valores mientras se cumple la condición, y vuelve después. |
| `click` | va hacia esos valores y vuelve, en cada clic. |

```python
pz.text("Hola").animate(opacity=0, y=12, duration=250)          # aparece desde abajo
tarjeta.animate(on="hover", scale=1.03, background="elevated")   # crece y se aclara en hover
boton.animate(on="press", scale=0.96, duration=90)               # se hunde al pulsar
icono.animate(on="click", rotate=360, duration=500)              # una vuelta completa en cada clic
```

La duración por defecto es de 300 ms para `mount` y `click`, y de 150 ms para `hover`, `press` y `focus`.

## Valores que vienen del widget

Una propiedad que no das al principio o al final de una animación va **desde o hacia el valor propio
del widget**. Así, una animación puede cambiar el fondo de cualquier botón sin saber su color:

```python
destello = pz.Animation({"50%": {"background": "#fbbf24"}}, duration=400)   # a amarillo y vuelta
```

Por eso una animación de `mount` puede terminar en "el aspecto propio del widget": el último
fotograma deja fuera la propiedad.

## Más ejemplos

```python
icono.animate("spin")                                             # un indicador de carga
tarjeta.animate(on="hover", rotate=-3, scale=1.02)                # se inclina en hover
lateral.transition(width=240 if self.abierto else 56, duration=200)  # el contenido de al lado se recoloca
titulo.transition(font_size=28 if self.grande else 16)
estado.animate(on="active", active=self.en_linea, background="#14532d", border_color="#22c55e")
```
