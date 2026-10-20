---
title: Keyframes y curvas
description: "Escribe tus propias animaciones de Pyzed con keyframes de pz.Animation (como @keyframes en CSS), dale a cada paso su curva, nómbralas y guárdalas, y elige curvas: ease, cubic, back, bounce, spring, Bézier y steps."
sidebar:
  order: 3
---

Cuando ningún preset hace lo que quieres, describe la animación tú mismo con `pz.Animation`. Funciona
como una regla `@keyframes` de CSS con su tiempo.

## Keyframes

Un **keyframe** dice cómo se ve el widget en un momento de la animación. Pyzed rellena los momentos
entre keyframes.

![Un corazón que late y una tarjeta que se sacude, cada uno con una barra de sus keyframes y un cabezal que los recorre](/pyzed/media/animation/keyframes.webp)

```python
latido = pz.Animation({0: {"scale": 1}, "30%": {"scale": 1.25, "easing": "ease_out"}, "45%": {"scale": 1},
                       "60%": {"scale": 1.15}, 1: {"scale": 1}}, duration=1000, repeat="infinite")
corazon.animate(latido)

sacudida = pz.Animation([{"x": 0}, {"x": -10}, {"x": 10}, {"x": -6}, {"x": 0}], duration=1000)
tarjeta.animate(sacudida, key=self.errores)
```

Los fotogramas se escriben de dos formas:

- **Una lista:** los fotogramas se reparten por igual, del principio al final.
- **Un dict:** la clave dice dónde va el fotograma, de `0` (principio) a `1` (final). También puede
  ser `"50%"`, `"from"` o `"to"`.

Cada fotograma es un dict de [propiedades](/pyzed/es/animation/properties/). Un fotograma también
puede fijar su propio `"easing"`: la curva **desde ese fotograma hasta el siguiente**.

`pz.Animation` acepta el mismo tiempo que `animate()`: `duration`, `delay`, `easing`, `repeat`,
`direction`, `fill` y `on`. Las opciones que le das a `animate()` lo sustituyen.

:::note[Los valores que faltan vienen del widget]
Una propiedad que falta al principio o al final va desde o hacia el valor propio del widget, así que
`{"50%": {"background": "#fbbf24"}}` hace destellar en amarillo a cualquier widget y vuelve.
:::

## Nombrar y guardar animaciones

`pz.define_animation(nombre, animacion)` le da un nombre a una animación, para que `animate(nombre)`
funcione en toda tu app, como un preset:

```python
pz.define_animation("sacudida", sacudida)
ui.button("Reintentar", self.reintentar).animate("sacudida", key=self.fallos)
```

`Animation.to_dict()` y `Animation.from_dict()` convierten una animación en datos aptos para JSON y
al revés, para guardarla en un archivo o en un ajuste. Para guardar **muchas** animaciones que mueven
varios widgets a la vez, usa un [clip de línea de tiempo y un archivo `.pzanim`](/pyzed/es/animation/player/#bibliotecas-y-archivos-pzanim).

## Curvas

La **curva** (easing) es la forma del movimiento: si empieza despacio, termina suave, se pasa o
rebota. El mismo movimiento con cada curva:

![Nueve bolas que recorren la misma distancia, cada una con una curva distinta dibujada al lado: linear, ease, ease in, ease out cubic, ease in out, ease out back, ease out bounce, spring y steps](/pyzed/media/animation/easing.webp)

| Curva | Se siente | Va bien para |
| --- | --- | --- |
| `"linear"` | Una velocidad constante. | Indicadores de carga, progreso, ciclos de color. |
| `"ease"` | Un inicio y un final suaves (la de CSS por defecto). | Casi todo. |
| `"ease_in"` | Empieza despacio y termina rápido. | Cosas que salen de la pantalla. |
| `"ease_out"`, `"ease_out_cubic"` | Empieza rápido y termina suave. | Cosas que llegan: menús, avisos, páginas. |
| `"ease_in_out"` | Lento, rápido, lento. | Moverse entre dos sitios de la pantalla. |
| `"ease_out_back"` | Se pasa un poco del final y se asienta. | Botones, entradas con gracia. |
| `"ease_out_bounce"` | Rebota al final. | Caídas, juegos. |
| `"spring"` | Se pasa y oscila como un muelle. | Interruptores, tarjetas que encajan en su sitio. |
| `"steps(5)"` | Salta en 5 pasos, sin movimiento entre ellos. | Fotogramas de sprites, relojes, texto que se escribe. |

`pz.animation.EASINGS` enumera todos los nombres: `linear`, `ease`, `ease_in`, `ease_out`,
`ease_in_out`, las familias `sine`, `quad`, `cubic`, `quart`, `expo`, `circ` y `back` (cada una con
`ease_in_*`, `ease_out_*` y `ease_in_out_*`), `ease_in_elastic`, `ease_out_elastic`,
`ease_in_bounce`, `ease_out_bounce` y `spring`.

También puedes dar:

- **Una Bézier cúbica** `(x1, y1, x2, y2)`, como `cubic-bezier()` en CSS: `easing=(0.2, 0.8, 0.2, 1)`.
- **Pasos** `"steps(n)"`: `n` saltos en lugar de un movimiento suave.

`pz.animation.ease(curva, t)` evalúa cualquier curva en `t` (de 0 a 1). Úsala para animar tus propios
dibujos en un [canvas](/pyzed/es/guides/canvas/) con las mismas curvas:

```python
from pyzed import animation

y = 300 - animation.ease("ease_out_bounce", self.t) * 240   # una bola que cae en un canvas
```
