---
title: Animaciones con línea de tiempo
description: "Anima muchos widgets y el estado de tu app en una línea de tiempo con clips, pistas, keys y llamadas a métodos, como el AnimationPlayer de Godot: interpolación, curva por key, bucles y pistas de atributos."
sidebar:
  order: 7
---

`animate()` le da a un widget su propio movimiento. Cuando **varios widgets** tienen que moverse a la
vez (una pantalla de título, una escena, un HUD que reacciona a un golpe, un recorrido guiado), ponlos
en una **línea de tiempo**. Un **clip** guarda esa línea de tiempo y un **reproductor de animaciones**
la reproduce, con reproducir, pausar, buscar, velocidad y colas. El AnimationPlayer de Godot funciona
igual.

![Una pantalla de nivel completado: la tarjeta sube, el título salta, tres estrellas entran girando una tras otra, la puntuación sube y el botón Siguiente nivel aparece y después sigue respirando](/pyzed/media/animation/timeline-intro.webp)

```python
import pyzed as pz

INTRO = pz.Clip("intro", length=2.2, tracks=[
    pz.Track("card:opacity", {0: 0, 0.35: 1}),
    pz.Track("card:y", [(0, 40, "ease_out_back"), (0.5, 0)]),
    pz.Track("title:scale", [(0.3, 0.6, "ease_out_back"), (0.7, 1)]),
    pz.Track(":puntos", [(0.7, 0, "ease_out_cubic"), (1.9, 12_480)]),
], calls=[pz.Call(1.6, "campana")])


class Juego(pz.App):
    def __init__(self):
        self.puntos = 0
        self.player = pz.AnimationPlayer(INTRO, autoplay="intro")

    def campana(self):
        ...

    def view(self):
        return pz.column([
            pz.text("NIVEL COMPLETADO").animate(self.player["title"]),
            pz.text(f"{self.puntos:,.0f}"),
        ]).animate(self.player["card"])
```

El ejemplo completo es [`examples/timeline.py`](https://github.com/albakore/pyzed/blob/main/examples/timeline.py).
Para hacer clips sin código, usa el [panel Animation](/pyzed/es/editor/animations-and-effects/#animaciones-con-línea-de-tiempo)
de Pyzed Design.

## Las partes de una línea de tiempo

![Una tarjeta a la izquierda y su clip a la derecha: un carril por pista con sus keys, un carril de llamadas y un cabezal que va de 0 a 2 segundos mientras la tarjeta aparece, sube, el título crece y la puntuación sube](/pyzed/media/animation/timeline-tracks.webp)

| Parte | Qué es |
| --- | --- |
| **Clip** (`pz.Clip`) | Una línea de tiempo con nombre: una duración `length` en segundos, pistas, llamadas y un modo de bucle. |
| **Pista** (`pz.Track`) | Una propiedad que cambia con el tiempo, como la `y` de `card`. |
| **Key** (`pz.Key`) | Un valor en un momento de una pista. Pyzed rellena el tiempo entre keys. |
| **Llamada** (`pz.Call`) | Un método de tu app que se ejecuta cuando el cabezal pasa por su momento. |
| **Objetivo** | Un nombre, como `"card"`, al que se unen los widgets con `.animate(self.player["card"])`. |
| **Cabezal** | Dónde está el reproductor dentro del clip (`player.position`). |

Un clip sin `length` dura hasta su última key o llamada.

### Rutas de las pistas

La ruta de una pista dice qué anima:

| Ruta | Anima |
| --- | --- |
| `"card:opacity"` | Una propiedad de todos los widgets que reproducen el objetivo `card`. |
| `":puntos"` | Un atributo de la app. |
| `":hud.vida"` | Un atributo de un atributo (sigue los puntos). |

Las **pistas de widget** usan las [propiedades animables](/pyzed/es/animation/properties/) (`opacity`,
`x`, `y`, `scale`, `rotate`, `blur`, colores, `radius`, `glow`, `width`, `font_size`...). Se reproducen
de forma nativa a la frecuencia de la pantalla y tu código no se ejecuta mientras tanto.

Las **pistas de atributo** (empiezan por `:`) cambian valores de tu propia app, así que pueden
controlar **cualquier parámetro de cualquier widget**: el texto de una etiqueta, el valor de una barra
de progreso, un tamaño, un icono. Los números, los colores (`"#rrggbb"`) y las tuplas de números se
mezclan entre keys; los demás valores (textos, booleanos) cambian en cada key. Mira
[pistas de atributo y llamadas](#pistas-de-atributo-y-llamadas) más abajo.

### Escribir keys

Las keys se pueden escribir de varias formas:

```python
pz.Track("card:x", {0: -40, 0.5: 0})                       # {tiempo: valor}
pz.Track("card:x", [(0, -40, "ease_out_back"), (0.5, 0)])  # (tiempo, valor, curva hasta la siguiente key)
pz.Track("card:x", [pz.Key(0, -40), pz.Key("500ms", 0)])   # objetos Key; los tiempos también como "500ms"
```

## Entre keys

![Tres pistas con las mismas keys, cada una con su curva y una bola: linear se mueve a velocidad constante, la curva por key se pasa y luego se suaviza, discrete salta de valor en valor](/pyzed/media/animation/timeline-keys.webp)

- **Curva por key.** El `easing` de una key es la curva **hasta la siguiente key**. Sirve cualquier
  nombre de [`pz.animation.EASINGS`](/pyzed/es/animation/keyframes/#curvas), además de Bézier cúbicas
  `(x1, y1, x2, y2)` y `"steps(n)"`. El `easing` de la pista (`"linear"` por defecto) se usa en las
  keys que no fijan uno.
- **Discreta.** `interpolation="discrete"` mantiene cada valor hasta la siguiente key, sin movimiento
  entre ellas. Va bien para fotogramas de sprites, textos e interruptores.
- **Silenciar.** `enabled=False` deja la pista en el clip sin reproducirla.
- **Antes y después de las keys.** Un widget mantiene el valor de la primera key antes de ella y el de
  la última key después, como en Godot.

## Bucles

![Tres cabezales: once se detiene al final, loop vuelve a empezar, pingpong va y vuelve](/pyzed/media/animation/timeline-loops.webp)

| `loop=` | Se reproduce |
| --- | --- |
| `"none"` (por defecto) | Una vez, y se queda en el último fotograma. |
| `"loop"` | Vuelve a empezar al llegar al final, sin parar. |
| `"pingpong"` | Va hasta el final y vuelve, sin parar. |

```python
REPOSO = pz.Clip("reposo", length=1.2, loop="pingpong", tracks=[
    pz.Track("button:scale", [(0, 1, "ease_in_out_sine"), (1.2, 1.06)]),
])
```

## Pistas de atributo y llamadas

![Una tarjeta de subida cuyo texto de estado, barra de progreso y número de archivos vienen de pistas de atributo, mientras el carril de llamadas dispara halfway() y finished() cuando el cabezal pasa por ellas](/pyzed/media/animation/timeline-calls.webp)

```python
SUBIDA = pz.Clip("subida", length=2.0, tracks=[
    pz.Track(":progreso", [(0, 0, "ease_in_out"), (1.8, 1)]),
    pz.Track(":estado", {0: "Subiendo…", 0.9: "Casi listo", 1.8: "Hecho"}),   # los textos cambian en cada key
    pz.Track(":archivos", [(0, 0), (1.8, 24)]),
], calls=[pz.Call(0.9, "a_medias"), pz.Call(1.8, "terminado", "informe.pdf")])


class Subida(pz.App):
    def __init__(self):
        self.progreso, self.estado, self.archivos = 0.0, "", 0
        self.player = pz.AnimationPlayer(SUBIDA, autoplay="subida")

    def a_medias(self):
        ...

    def terminado(self, nombre):
        ...

    def view(self):
        return pz.column([pz.text(self.estado), ui.progress(self.progreso), pz.text(f"{self.archivos:.0f} / 24")])
```

`pz.Call(tiempo, metodo, *args)` llama a un método de la app cuando el clip pasa por ese momento.
`metodo` también puede ser cualquier función. Lo que devuelve se trata como lo que devuelve un callback
(un `Command`, un mensaje). Las llamadas se ejecutan al reproducir hacia delante, hacia atrás y en cada
vuelta de un bucle, pero no cuando saltas con `seek`.

:::note[El dueño]
Las pistas de atributo y las llamadas actúan sobre el **dueño** del reproductor: la app (o ventana)
que guarda el reproductor en un atributo. Pyzed lo encuentra solo; pasa `owner=` a
`pz.AnimationPlayer` para elegir otro objeto.
:::

Siguiente: [el reproductor de animaciones](/pyzed/es/animation/player/) reproduce, pausa, busca y
encola clips, y los guarda en archivos `.pzanim`.
