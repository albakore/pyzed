---
title: Galería de presets
description: "Todos los presets de animación de Pyzed, en movimiento: entradas, salidas, avisos, respuesta a hover y press, y bucles, con su duración y cuándo usarlos."
sidebar:
  order: 5
---

Un **preset** es una animación lista con un nombre. Pasa el nombre a `animate()`:

```python
dialogo.animate("pop_in")
tarjeta.animate("lift", on="hover")
pz.icon("loader-circle").animate("spin")
```

Las opciones cambian el tiempo de un preset sin cambiar el preset: `animate("fade_in_up", duration=600, delay=200)`.
`pz.animation.presets(categoria)` los enumera en código, cada uno con su `description`, y
`pz.define_animation` añade [los tuyos](/pyzed/es/animation/keyframes/#nombrar-y-guardar-animaciones).

## Entrada

Se reproducen una vez cuando aparece el widget (`on="mount"`). Úsalos en páginas, diálogos, avisos y elementos de lista.

![Quince tarjetas que aparecen, cada una con un preset de entrada](/pyzed/media/animation/presets-entrance.webp)

| Preset | Qué hace | Duración |
| --- | --- | --- |
| `fade_in` | Aparece desvaneciéndose. | 280 ms |
| `fade_in_up` | Aparece mientras sube. | 280 ms |
| `fade_in_down` | Aparece mientras baja. | 280 ms |
| `fade_in_left` | Aparece desde la izquierda. | 280 ms |
| `fade_in_right` | Aparece desde la derecha. | 280 ms |
| `slide_in_up` | Entra deslizándose desde abajo, una vez su altura. | 280 ms |
| `slide_in_down` | Entra deslizándose desde arriba. | 280 ms |
| `slide_in_left` | Entra deslizándose desde la izquierda. | 280 ms |
| `slide_in_right` | Entra deslizándose desde la derecha. | 280 ms |
| `zoom_in` | Crece desde un poco más pequeño. | 280 ms |
| `pop_in` | Aparece de golpe y se pasa un poco. | 320 ms |
| `bounce_in` | Entra rebotando desde pequeño. | 600 ms |
| `drop_in` | Cae a su sitio con un rebote. | 520 ms |
| `blur_in` | Se enfoca, como una lente. | 360 ms |
| `rotate_in` | Entra girando desde un cuarto de vuelta. | 420 ms |

## Salida

Lo contrario: el widget se va. Úsalos como `exit=` de [`pz.presence`](/pyzed/es/animation/transitions/#presence-y-stagger), como `exit_transition` de una ventana o antes de quitar algo.

![Trece tarjetas que se van, cada una con un preset de salida](/pyzed/media/animation/presets-exit.webp)

| Preset | Qué hace | Duración |
| --- | --- | --- |
| `fade_out` | Se desvanece. | 220 ms |
| `fade_out_up` | Se desvanece mientras sube. | 220 ms |
| `fade_out_down` | Se desvanece mientras baja. | 220 ms |
| `fade_out_left` | Se desvanece hacia la izquierda. | 220 ms |
| `fade_out_right` | Se desvanece hacia la derecha. | 220 ms |
| `slide_out_up` | Sale deslizándose hacia arriba. | 220 ms |
| `slide_out_down` | Sale deslizándose hacia abajo. | 220 ms |
| `slide_out_left` | Sale deslizándose hacia la izquierda. | 220 ms |
| `slide_out_right` | Sale deslizándose hacia la derecha. | 220 ms |
| `zoom_out` | Se encoge hasta desaparecer. | 220 ms |
| `pop_out` | Se hincha un poco y desaparece. | 260 ms |
| `blur_out` | Se desenfoca. | 260 ms |
| `rotate_out` | Se va girando un cuarto de vuelta. | 320 ms |

## Atención

Un pequeño aviso para mirar aquí. Repítelos con `key` (`animate("shake", key=self.errores)`) o con `on="click"`.

![Diez tarjetas, cada una con un preset de atención](/pyzed/media/animation/presets-attention.webp)

| Preset | Qué hace | Duración |
| --- | --- | --- |
| `pulse` | Crece y se encoge una vez. | 600 ms |
| `heartbeat` | Dos latidos rápidos. | 1000 ms |
| `shake` | Se sacude de lado a lado (un dato incorrecto). | 450 ms |
| `wobble` | Se tambalea y se asienta. | 800 ms |
| `bounce` | Salta dos veces. | 900 ms |
| `flash` | Parpadea dos veces. | 800 ms |
| `rubber_band` | Se estira y vuelve como una goma. | 800 ms |
| `tada` | Un salto de celebración con un meneo. | 900 ms |
| `swing` | Se balancea como un cartel colgado. | 900 ms |
| `glow_flash` | Un destello de brillo alrededor de la caja. | 700 ms |

## Interacción

Respuesta a hover, press y focus: avanzan mientras el puntero está sobre el widget y vuelven después. Su disparador por defecto está en la tabla.

![Ocho tarjetas que pasan a su aspecto de hover o press y vuelven](/pyzed/media/animation/presets-interaction.webp)

| Preset | Qué hace | Duración | Disparador |
| --- | --- | --- | --- |
| `lift` | Sube con un brillo suave (tarjetas y botones). | 160 ms | `hover` |
| `grow` | Crece un poco. | 160 ms | `hover` |
| `shrink` | Se hunde (para press). | 90 ms | `press` |
| `dim` | Se apaga un poco. | 160 ms | `hover` |
| `glow` | Brilla alrededor de la caja. | 200 ms | `hover` |
| `bloom` | Un brillo fuerte y amplio que sale de la caja. | 260 ms | `hover` |
| `nudge_right` | Se mueve un poco a la derecha (enlaces, flechas). | 140 ms | `hover` |
| `tilt` | Se inclina un poco (pegatinas, tarjetas). | 180 ms | `hover` |

## Bucle

Movimiento que no se detiene (`repeat="infinite"`): luces de estado, indicadores de carga, cosas que flotan.

![Siete tarjetas con presets en bucle: float, breathe, blink, glow pulse, throb, drift y spin](/pyzed/media/animation/presets-loop.webp)

| Preset | Qué hace | Duración |
| --- | --- | --- |
| `float` | Flota arriba y abajo. | 2400 ms |
| `breathe` | Se apaga y se encoge despacio, como al respirar. | 3000 ms |
| `blink` | Parpadea (luces de estado, cursores). | 1000 ms |
| `glow_pulse` | El brillo crece y se apaga (grabando, en directo). | 1600 ms |
| `throb` | Late sin parar (notificaciones). | 1200 ms |
| `drift` | Se desplaza de lado a lado. | 3000 ms |
| `spin` | Gira sin parar (indicadores de carga). | 1000 ms |
