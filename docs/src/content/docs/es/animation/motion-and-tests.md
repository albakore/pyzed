---
title: Movimiento reducido, tests y límites
description: "Respeta el ajuste de reducir movimiento del sistema en Pyzed, prueba vistas animadas y clips de línea de tiempo, haz capturas estables y conoce los límites del sistema de animación."
sidebar:
  order: 9
---

## Movimiento reducido

A algunas personas el movimiento las marea o las distrae, y activan "reducir movimiento" en su
sistema. Pyzed sigue ese ajuste, que lee al arrancar la app: entonces cada animación **muestra su
estado de reposo al momento**, sin moverse.

- `pz.set_reduced_motion(True)` quita el movimiento, `False` lo activa y `None` vuelve a seguir al
  sistema. Ofrécelo como un ajuste de tu app.
- La variable de entorno `PYZED_REDUCED_MOTION` (`1` o `0`) manda sobre ambos.

Mira [Accesibilidad](/pyzed/es/guides/accessibility/#reducir-movimiento).

:::tip
No escondas información solo en el movimiento. Si un campo se sacude con una contraseña incorrecta,
muestra también el mensaje de error.
:::

## Tests y capturas

Las capturas (`App.screenshot`, `pz.screenshot`) siempre muestran el **estado de reposo**: en lo que
termina una animación de `mount`. Así los tests y las imágenes de la documentación son estables, sea
cual sea el tiempo.

Para comprobar que un widget se anima, mira el árbol de widgets: `repr(widget)` termina en
`.animate(2 animation(s), 1 transition(s))`.

Para probar una línea de tiempo, controla el reproductor a mano. `advance` ejecuta las llamadas y
actualiza las pistas de atributo; `seek` salta sin ejecutar llamadas:

```python
def test_intro_suena():
    app = Juego()
    app.player.owner = app                  # una app en marcha lo fija; un test lo fija a mano
    app.player.pause()
    app.player.advance(1.7)                 # pasa la llamada campana() en 1.6 s
    assert app.mensaje == "¡Nuevo récord!"
    app.player.seek(0.5)
    assert app.player.value("card:y") < 40
```

Un reproductor en pausa muestra su clip en el cabezal, incluso en una captura, así que puedes sacar
una foto de cualquier momento de un clip: `app.player.pause(); app.player.seek(0.8); app.screenshot("intro.png")`.

## Límites

- Las transformaciones son traslación, escala uniforme y rotación; no hay inclinación (skew).
- Un widget girado o desenfocado recibe los clics donde está su caja en el layout, no donde se dibuja.
- Un widget con rotación, desenfoque, desenfoque de fondo o bloom se dibuja encima de sus vecinos, así
  que su bloom puede iluminar a los widgets de al lado.
- `backdrop_blur` desenfoca lo que la ventana dibujó antes del widget, dentro de la misma capa padre
  (los contenedores con scroll y otros widgets que recortan empiezan una capa nueva).
- `width`, `height`, `padding` y `font_size` vuelven a calcular el layout en cada fotograma mientras
  se mueven, así que en vistas grandes prefiere `x`, `y` y `scale`.
- Las animaciones vuelven a empezar cuando un widget sale del árbol y regresa. Dale un `key` estable,
  o usa [`presence`](/pyzed/es/animation/transitions/#presence-y-stagger), para decidir cuándo se repiten.
- Un reproductor reproduce un clip cada vez. Para dos escenas a la vez, usa dos reproductores.
