---
title: Animaciones y efectos
description: "Da a los controles rotación, desenfoque, glow, bloom, glass y opacidad en Pyzed Design, y anímalos al aparecer, en hover, al pulsar o con foco."
sidebar:
  order: 5.5
---

Cada control visual tiene dos secciones en el panel **Propiedades**, debajo de **Estilo**: **Efectos** y
**Animación**. Lo que fijes ahí se guarda en el `.pzform` y se reproduce cuando el formulario se ejecuta. Es
el mismo sistema que [`widget.animate()` y los efectos de estilo](/pyzed/es/guides/animation/) de la biblioteca.

![Las secciones Efectos y Animación de un botón](../../../../../screenshots/editor-motion.png)

## Efectos

| Campo | Qué hace |
| --- | --- |
| **Opacidad** | Cuánto se ve el control y todo lo que tiene dentro (1 es opaco). |
| **Rotación** | Grados, en sentido horario, alrededor del centro. |
| **Desenfoque** | Desenfoca el control y todo lo que contiene, en píxeles. |
| **Desenfoque del fondo** | Desenfoca lo que hay detrás de la caja, en píxeles. |
| **Resplandor** | Un halo suave alrededor de la caja. Elige un color (o un token del tema como `accent`); **Tamaño del resplandor** fija cuánto se extiende. |
| **Bloom** | Luz que desborda de las partes brillantes del control. **Intensidad** va de 0 a 1. |
| **Cristal** | Un panel translúcido que desenfoca lo que tiene detrás, con un borde claro. **Matiz** lo colorea e **Intensidad del tinte** fija cuánto se nota el tinte. |

Los subcampos solo aparecen mientras el efecto está activo. Borra el color (o apaga **Cristal**) para
quitarlo. Los efectos son propiedades de estilo (`opacity`, `rotate`, `blur`, `backdrop_blur`, `glow`, `bloom`, `glass`), así que en el código
aparecen en `control.style` y **Restablecer el estilo** también los quita. El cristal luce mejor sobre un fondo
colorido, como un panel con degradado.

## Animación

Cada fila es una animación: un icono de lo que la reproduce, un resumen (**Aparecer subiendo · 280 ms**,
con **+retardo** y **×repeticiones** si las tiene) y el disparador debajo. El botón **▶** la previsualiza y la
papelera la quita. Haz clic en una fila para abrir su editor:

| Campo | Significado |
| --- | --- |
| **Cuándo** | Qué la reproduce: **Al aparecer**, **Con el ratón encima**, **Mientras se pulsa**, **Mientras tiene el foco** o **Al hacer clic**. Encima, pulsar y foco avanzan mientras se cumple la condición y vuelven atrás cuando termina. |
| **Animación** | El preset. Primero salen los que encajan con el disparador (entradas para *al aparecer*, interacciones para encima y pulsar, de atención para el clic); el tooltip describe el elegido. |
| **Duración**, **Retardo** | Milisegundos. Vacío mantiene el timing propio del preset. |
| **Curva** | Cómo cambia la velocidad por el camino (suave, lineal, frenar cúbica, muelle...). |
| **Repetir** | 1, 2, 3, 5 o infinito. |

**Añadir animación** añade una fila (un *aparecer subiendo* al aparecer) y la abre. Elegir otro preset
restablece el timing de la fila al del nuevo preset. Todos los cambios se pueden deshacer.

### Vista previa

El lienzo se queda quieto mientras editas, para que los controles no se muevan bajo el ratón.
**Vista previa** (al final de la sección, o **▶** en una fila) reproduce una vez en el lienzo las animaciones
del control, como si acabara de aparecer; **Detener** termina la previsualización. Ejecuta el formulario
(**F5**) para ver cada animación con su disparador real.

## En código

Las animaciones se guardan como datos simples en el control:

```json
"animations": [
  {"preset": "fade_in_up"},
  {"preset": "lift", "on": "hover", "duration": 180}
]
```

`Document.set_animations(name, animations)` las cambia desde un script y `Control.animations` las lee. Para
animar un control desde sus handlers, usa la biblioteca: `pz.Animation`, `define_animation` y la
[lista de presets](/pyzed/es/guides/animation/#presets).

## Animaciones con línea de tiempo

Para animaciones que mueven varios controles a la vez (una entrada, una transición entre estados), abre
el panel **Animation** desde **View → Animation** (`Ctrl+Shift+M`). Edita **clips**: líneas de tiempo
guardadas en el `.pzform` que se reproducen igual que con [`pz.AnimationPlayer`](/pyzed/es/guides/timeline/)
en código.

![El panel Animation: un clip intro con pistas para la tarjeta, el título y el texto de una etiqueta, y una llamada a intro_done](../../../../../screenshots/editor-animation.png)

| Acción | Resultado |
| --- | --- |
| **Añadir pista para …** | Añade una pista para una propiedad del control seleccionado (opacidad, posición, escala, colores, tamaño…) o cualquiera de sus propiedades, como el texto de una etiqueta. |
| **Doble clic** en una pista | Añade una key en ese tiempo con el valor actual del control. |
| **Arrastrar** una key | La mueve en el tiempo. Selecciona una key para editar su valor y su curva debajo de las pistas. |
| **Clic** o **arrastrar** en la regla | Mueve el cabezal; el lienzo muestra el formulario en ese tiempo. |
| Pista **Llamadas** (clic derecho en una llamada para quitarla) | Llama a un método del archivo de código del formulario en un tiempo. |
| **Duración**, **bucle**, **autoplay** | Indican cuánto dura el clip, si se repite y si se reproduce al abrir el formulario. |

Los controles dentro de un contenedor animado siguen su opacidad, posición y desenfoque. Todos los
cambios se pueden deshacer. En un formulario en ejecución, `self.animations` es el reproductor:
`self.animations.play("intro")`.
