---
title: "Juegos (pyzed.game)"
description: "Referencia de la API de pyzed.game: teclas mantenidas, movimiento, colisiones, sprites de píxeles, partículas y temblor de pantalla para juegos en un pz.canvas."
sidebar:
  order: 11
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs_es.py. -->

`pyzed.game` reúne pequeñas ayudas para juegos en tiempo real: teclas mantenidas, movimiento,
colisiones, sprites de píxeles, partículas y temblor de pantalla. Son Python puro sobre
[`pyzed.draw`](/pyzed/es/reference/draw/), así que también funcionan en capturas y tests. Mira
[Crear videojuegos](/pyzed/es/games/) para ver ejemplos completos.

```python
from pyzed import draw, game

def tick(self, dt):                      # pz.frames(self.tick) en subscriptions()
    self.x += game.axis(("left", "a"), ("right", "d")) * 300 * dt
    self.chispas.update(dt)

def view(self):
    return pz.canvas([draw.background("#0b0e14"), *game.glow(self.x, 200, 18, "#74ade8"),
                      *self.chispas.shapes()], width=400, height=300)
```

## Teclado

### `pressed`

```python
pressed()
```

Las teclas pulsadas ahora mismo, como un `frozenset` de nombres sin modificadores (`"left"`, `"space"`, `"a"`…). También está disponible como `pz.pressed()`.

### `is_pressed`

```python
is_pressed(*keys, held=None)
```

Si alguna de las teclas de `keys` está pulsada (`held` sustituye a `pressed()`, para tests). También está disponible como `pz.is_pressed()`.

### `axis`

```python
axis(negative, positive, *, held=None)
```

`-1`, `0` o `1` a partir de dos grupos de teclas: `axis(("left", "a"), ("right", "d"))`.

### `vector`

```python
vector(
    left=('left', 'a'),
    right=('right', 'd'),
    up=('up', 'w'),
    down=('down', 's'),
    *,
    held=None,
)
```

Una dirección `(x, y)` de longitud 0 o 1 a partir de cuatro grupos de teclas (flechas y WASD por defecto); las diagonales se normalizan.

## Cálculo

### `clamp`

```python
clamp(value, low, high)
```

`value` limitado a `[low, high]`.

### `lerp`

```python
lerp(a, b, t)
```

El valor que está a una fracción `t` del camino de `a` a `b` (`t` de 0 a 1).

## Colisiones

### `Rect`

```python
@dataclass
class Rect(x, y, w, h)
```

Una caja alineada con los ejes (`x`, `y` es la esquina superior izquierda) con `left`, `right`, `top`, `bottom`, `center`, `overlaps(other)`, `contains(x, y)`, `moved(dx, dy)` y `shape(**paint)` (un `draw.rect`).

### `circle_rect`

```python
circle_rect(cx, cy, r, rect)
```

Dónde choca un círculo con un `Rect`: la dirección hacia la que empujarlo `(nx, ny)`, o `None`. Una pelota rebota con `if nx: vx = abs(vx) * nx` y `if ny: vy = abs(vy) * ny`.

## Dibujo

### `rgba`

```python
rgba(color, alpha=1.0)
```

`color` (`"#rrggbb[aa]"` o una tupla) como una tupla `(r, g, b, a)` con `alpha` aplicado.

### `glow`

```python
glow(x, y, radius, color, *, layers=4, strength=0.5, core=True)
```

Una luz suave: círculos translúcidos que crecen alrededor de `(x, y)` (bloom en un lienzo). `strength` es la opacidad del halo interior; `core=False` omite el círculo sólido.

### `sprite`

```python
sprite(rows, palette, x=0.0, y=0.0, *, scale=1.0, flip=False)
```

Pixel art a partir de texto: cada carácter de `rows` es un píxel con el color de `palette` (los caracteres que no están son transparentes). Una forma por color, así que un sprite sigue siendo barato sea cual sea su tamaño.

## Efectos

### `Particles`

```python
class Particles
```

Chispas, humo, explosiones: puntos de vida corta que se mueven, caen y se desvanecen. Llama a `burst(x, y, …)` cuando pase algo, a `update(dt)` en cada fotograma y dibuja `shapes()`; `gravity`, `drag` y `limit` los ajustan.

### `Shake`

```python
class Shake
```

Temblor de pantalla: `kick(8)` al recibir un golpe, `update(dt)` en cada fotograma, y empieza las formas del lienzo con `*shake.shapes()` (un translate) para que todo se mueva a la vez.
