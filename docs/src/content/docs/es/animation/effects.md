---
title: Efectos
description: "Efectos visuales en Pyzed: opacidad, rotación, desenfoque, desenfoque de fondo, glow, bloom, glass, translate y scale como propiedades de estilo, y cuáles pueden cambiar las animaciones."
sidebar:
  order: 6
---

Los efectos son propiedades de [estilo](/pyzed/es/theming/styles/), así que funcionan con `style()`,
`pz.Style` y los estilos con nombre. Varios también son [propiedades animables](/pyzed/es/animation/properties/),
así que una animación puede cambiarlos con el tiempo.

![Sobre un degradado de colores: una tarjeta que se desenfoca y se enfoca, otra que se inclina, otra que brilla, otra que se desvanece y un panel de cristal que pasa sobre círculos de colores](/pyzed/media/animation/effects.webp)

| Propiedad | Qué hace | Animable |
| --- | --- | --- |
| `opacity` | De 0 a 1. Desvanece el widget y todo lo que contiene. | Sí |
| `rotate` | Grados en sentido horario (o `"0.25turn"`, `"1rad"`): dibuja el widget girado alrededor de su centro. | Sí |
| `blur` | Píxeles: desenfoca el widget y todo lo que contiene. | Sí |
| `backdrop_blur` | Píxeles: desenfoca lo que hay detrás de la caja, dentro de sus esquinas redondeadas. | No |
| `glow` | Un halo suave alrededor de la caja: un color, un tamaño (color de acento) o `(color, tamaño)`. | Sí (`glow` y `glow_color`) |
| `bloom` | Luz que sale de las partes claras del widget: un color o `(color, intensidad)` con una intensidad de 0 a 1. | No |
| `glass` | Un panel translúcido que desenfoca lo que hay detrás, con un borde de luz: `True`, un color de tinte o `{"tint": ..., "strength": 0.08, "blur": 20}`. | No (muévelo con `x`, `y`) |
| `translate` | `(x, y)` en píxeles o `"50%"`: dibuja el widget desplazado, sin cambiar el layout. | Sí (como `x`, `y`) |
| `scale` | Dibuja el widget más grande o más pequeño alrededor de su centro. | Sí |

```python
pz.container(tarjeta).style(glass=True, radius=12, padding=16)
ui.button("Ir", self.ir).style(glow=("#22d3ee", 18))
insignia.style(bloom=("accent", 0.8), opacity=0.9)
pegatina.style(rotate=-8)
```

![Rotación, glass, bloom y desenfoque sobre un degradado](../../../../assets/tutorials/effects.png)

## Cómo se dibujan

La rotación, el desenfoque, el desenfoque de fondo y el bloom los dibuja el renderizador: el widget se
dibuja en su propia capa, que después se gira, se desenfoca o se ilumina antes de llegar a la ventana.

- En una caja (un widget con fondo o glass), el bloom también añade un halo suave y un borde
  iluminado; en un texto o icono solo, solo brilla.
- Glass añade un degradado con tinte, un borde y una sombra; los que fijes tú mandan. Se ve mejor
  sobre un fondo de colores (un degradado o una imagen).
- Los presets `glow`, `bloom`, `glow_pulse` y `glow_flash` animan `glow` y `glow_color`.

:::caution[Efectos y clics]
Un widget girado o desenfocado recibe los clics donde está su caja en el layout, no donde se dibuja.
Un widget con rotación, desenfoque, desenfoque de fondo o bloom se dibuja encima de sus vecinos, así
que su bloom puede iluminar a los widgets de al lado.
:::
