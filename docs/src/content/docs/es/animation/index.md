---
title: Animación
description: "Cómo funciona la animación en Pyzed: anima cualquier widget como en la web (presets, keyframes, transiciones), mueve muchos widgets en una línea de tiempo como el AnimationPlayer de Godot y edita clips en Pyzed Design."
sidebar:
  order: 0
  label: Introducción
---

Cualquier widget de Pyzed puede moverse, aparecer, crecer, girar, desenfocarse, brillar o cambiar de
color. Esta sección explica cada parte del sistema de animación, con un ejemplo animado de cada una.

![Un panel que entra: el encabezado baja, las tarjetas suben una tras otra, una insignia late y un indicador de carga gira](/pyzed/media/animation/overview.webp)

```python
pz.text("Hola de nuevo").animate("fade_in_down")                 # al aparecer
pz.row(pz.stagger(tarjetas, "fade_in_up", step=80))              # una tras otra
insignia.animate("pulse", repeat="infinite")                     # sin parar
ui.button("Grabando", self.parar).animate("glow_pulse")          # un brillo en bucle
pz.icon("loader-circle").animate("spin")                         # un indicador de carga
```

## Tres formas de animar

Elige la que encaje con lo que quieres hacer. Funcionan juntas, así que una app suele usar las tres.

| Quieres... | Usa | Página |
| --- | --- | --- |
| Darle a un widget su propio movimiento: aparecer, reaccionar al puntero, llamar la atención, repetirse. | `widget.animate(...)` | [animate() y disparadores](/pyzed/es/animation/animate/) |
| Mover un widget con suavidad cada vez que cambia uno de sus valores (abrir un panel, seleccionar una fila). | `widget.transition(...)` y estados de estilo | [Transiciones y estados](/pyzed/es/animation/transitions/) |
| Reproducir una escena en la que cambian a la vez muchos widgets y valores de tu app, con reproducir, pausar y buscar. | `pz.AnimationPlayer` y `pz.Clip` | [Animaciones con línea de tiempo](/pyzed/es/animation/timeline/) |

Y en [Pyzed Design](/pyzed/es/editor/animations-and-effects/) puedes hacer lo mismo sin código: una
sección **Animación** en cada control y un panel **Animation** con una línea de tiempo para los clips.

## Cómo se reproduce

Python describe una animación una vez, en `view()`. La parte de Rust la reproduce a la frecuencia de
la pantalla, así que **una animación en marcha nunca llama a tu código** y no ralentiza tu app.
Cuando algo cambia (un clic, datos nuevos), `view()` se vuelve a ejecutar como siempre; las
animaciones que no cambiaron siguen donde estaban.

- Los **presets** son animaciones listas con un nombre (`"fade_in_up"`, `"lift"`, `"spin"`). Mira
  la [galería de presets](/pyzed/es/animation/presets/).
- Los **keyframes** describen tu propia animación paso a paso, como `@keyframes` en CSS. Mira
  [Keyframes y curvas](/pyzed/es/animation/keyframes/).
- Las **propiedades** son lo que una animación puede cambiar: posición, tamaño, rotación, colores,
  desenfoque, brillo... Mira [Propiedades animables](/pyzed/es/animation/properties/).
- Los **efectos** como glass, bloom y glow son propiedades de estilo que las animaciones también
  pueden cambiar. Mira [Efectos](/pyzed/es/animation/effects/).

:::tip[Pruébalas]
Ejecuta [`examples/animations.py`](https://github.com/albakore/pyzed/blob/main/examples/animations.py)
para las animaciones de widgets y [`examples/timeline.py`](https://github.com/albakore/pyzed/blob/main/examples/timeline.py)
para una línea de tiempo. Los dos son cortos y están comentados.
:::

## En esta sección

| Página | Qué explica |
| --- | --- |
| [animate() y disparadores](/pyzed/es/animation/animate/) | Qué reproduce una animación (aparecer, hover, press, focus, clic, un indicador) y sus opciones de tiempo. |
| [Propiedades animables](/pyzed/es/animation/properties/) | Todas las propiedades que puede cambiar una animación y cómo funcionan los valores. |
| [Keyframes y curvas](/pyzed/es/animation/keyframes/) | Tus propias animaciones con `pz.Animation` y las curvas que dan forma al movimiento. |
| [Transiciones y estados](/pyzed/es/animation/transitions/) | `transition()`, estilos de hover y pressed, cambios de página con `presence`, listas con `stagger` y transiciones de ventana. |
| [Galería de presets](/pyzed/es/animation/presets/) | Todas las animaciones con nombre, en movimiento. |
| [Efectos](/pyzed/es/animation/effects/) | Glass, glow, bloom, desenfoque, rotación y opacidad. |
| [Animaciones con línea de tiempo](/pyzed/es/animation/timeline/) | Clips, pistas, keys, bucles y llamadas a métodos en una línea de tiempo. |
| [El reproductor de animaciones](/pyzed/es/animation/player/) | Reproducir, pausar, buscar y encolar clips, y guardarlos en archivos `.pzanim`. |
| [Movimiento reducido, tests y límites](/pyzed/es/animation/motion-and-tests/) | Respetar "reducir movimiento", probar vistas animadas y lo que el sistema no puede hacer. |
