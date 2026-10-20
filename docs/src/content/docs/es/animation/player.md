---
title: El reproductor de animaciones
description: "pz.AnimationPlayer reproduce clips de línea de tiempo de Pyzed: reproducir, pausar, reanudar, detener, buscar, reproducir al revés, velocidad, colas y eventos, y guarda clips reutilizables en bibliotecas .pzanim."
sidebar:
  order: 8
---

`pz.AnimationPlayer` reproduce los [clips](/pyzed/es/animation/timeline/) que le das, uno cada vez, y
le da a cada widget su parte con `player["objetivo"]`.

```python
self.player = pz.AnimationPlayer(INTRO, REPOSO, "ui.pzanim", autoplay="intro",
                                 on_started=..., on_finished=...)
```

- **Fuentes:** clips, listas de clips, [bibliotecas](#bibliotecas-y-archivos-pzanim) o rutas de
  archivos `.pzanim`.
- **Dónde guardarlo:** en un atributo de la app (o de una ventana). Ahí encuentra a su **dueño**, el
  objeto cuyos atributos y métodos usan las pistas y las llamadas, y se mantiene en marcha.
- **Objetivos:** `widget.animate(self.player["card"])` le da a un widget el objetivo `card`. Todos los
  widgets que usan el mismo objetivo lo siguen.

## Controles

![La pantalla de nivel completado controlada por el reproductor: play, pause, seek a 0.5 s, reproducir al revés y después a doble velocidad, con la llamada arriba y los controles siguiéndola](/pyzed/media/animation/timeline-player.webp)

| Llamada | Qué hace |
| --- | --- |
| `play(nombre, speed=1, backwards=False, restart=False)` | Reproduce un clip o sigue con el actual. Un clip que ya se está reproduciendo sigue, salvo con `restart`; uno terminado vuelve a empezar. |
| `play_backwards(nombre)` | Lo reproduce al revés desde el final. |
| `pause()`, `resume()`, `toggle()` | Detiene el tiempo y lo vuelve a poner en marcha. |
| `stop(reset=False)` | Vuelve al primer fotograma y vacía la cola. Con `reset=True` los widgets recuperan sus valores propios. |
| `seek(segundos)` | Salta a un momento. Las llamadas de en medio no se ejecutan. |
| `advance(segundos)` | Avanza el tiempo a mano y ejecuta las llamadas del camino (útil en tests). |
| `queue(nombre)`, `clear_queue()` | Reproduce un clip cuando termina el actual. |
| `speed` | La velocidad de todos los clips (`2` es el doble de rápido). `play(speed=...)` la multiplica. |

```python
def repetir(self):
    self.player.play("intro", restart=True)
    self.player.queue("reposo")            # en bucle después de la intro

def poner_velocidad(self, etiqueta):
    self.player.speed = float(etiqueta.rstrip("×"))
```

## Estado y eventos

| Lee | Da |
| --- | --- |
| `current` | El nombre del clip que se reproduce o está en pausa (`None` si está detenido). |
| `position`, `length` | Dónde está el cabezal y cuánto dura el clip, en segundos. |
| `playing`, `paused`, `finished` | Qué está haciendo el reproductor. |
| `queued` | Los clips que esperan su turno. |
| `names`, `has(nombre)`, `clip(nombre)` | Los clips que conoce. |
| `value(ruta)` | El valor que el clip actual le da a una ruta en este momento: `player.value(":puntos")`. |

`on_started(nombre)` y `on_finished(nombre)` se llaman cuando un clip empieza y cuando termina (los
clips en bucle nunca terminan). Un slider unido a `position` y `seek` hace de barra de búsqueda:

```python
ui.slider(p.position, p.seek, min=0, max=p.length, step=0.01)
```

:::tip[Solo despierta a tu app cuando hace falta]
Las pistas de widget se reproducen de forma nativa y nunca necesitan tu código. Un clip con pistas de
atributo las actualiza hasta `fps` veces por segundo (60 por defecto, `pz.AnimationPlayer(..., fps=30)`
para menos). Sin ellas, el reproductor solo despierta para la siguiente llamada o el final del clip.
:::

## Bibliotecas y archivos .pzanim

Los clips son valores inmutables, así que puedes compartirlos entre reproductores y apps. Una
`AnimationLibrary` los agrupa y los guarda en un archivo `.pzanim` (JSON) que puedes tener en tu
proyecto y cargar en cualquier app:

```python
biblioteca = pz.AnimationLibrary([INTRO, REPOSO], name="ui")
biblioteca.save("ui.pzanim")

player = pz.AnimationPlayer("ui.pzanim")      # clips llamados "ui/intro", "ui/reposo"
player.play("ui/intro")
biblioteca = pz.load_animations("ui.pzanim")
```

Una biblioteca también tiene `add`, `remove`, `rename` y `names`. Los formularios hechos en Pyzed
Design guardan sus clips dentro del `.pzform`; mira el
[panel Animation](/pyzed/es/editor/animations-and-effects/#animaciones-con-línea-de-tiempo).

## Reutilizar clips

![El mismo clip de rebote en tres widgets: en su propio objetivo, movido a otro widget y convertido en una pz.Animation](/pyzed/media/animation/timeline-reuse.webp)

Los métodos de un clip devuelven un clip **nuevo**, así que el original no cambia:

- `clip.retarget({"card": "panel"})` mueve las pistas del clip a otros objetivos.
- `clip.animation("card")` convierte las pistas de un objetivo en una `pz.Animation`. Reprodúcela con
  `animate()` sin reproductor, o dale un nombre con `pz.define_animation`.
- `clip.with_key(ruta, tiempo, valor)`, `without_key`, `with_track` y `without_track` lo editan.
- `clip.to_dict()` y `pz.Clip.from_dict()` lo convierten en datos aptos para JSON y al revés.
