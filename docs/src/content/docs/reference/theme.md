---
title: "Temas"
description: "Theme, los temas incluidos y las utilidades de color."
sidebar:
  order: 5
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs.py. -->

Ver la guía de [temas](/pyzed/guides/theming/) para la lista de tokens y cómo crear los tuyos.

## Theme

### `Theme`

Un tema: un dataclass inmutable con los tokens de color de Zed (superficies, bordes, elementos, texto, estado, editor, sintaxis, colores de colaboradores y ANSI) y métricas (`radius`, `radius_sm`, `ui_font_size`, `buffer_font_size`). La propiedad `is_dark` indica si es oscuro.

### `derive`

```python
derive(self, **changes)
```

Devuelve una copia con algunos tokens cambiados. Los diccionarios `syntax` y `ansi` se combinan en lugar de reemplazarse.

| Parámetro | Descripción |
| --- | --- |
| `changes` | Tokens a cambiar. |

```python
oceano = pz.themes.ONE_DARK.derive(name="Océano", accent="#4fb3ff", syntax={"keyword": "#ff79c6"})
```

### `color`

```python
color(self, name)
```

Resuelve un token (`"accent"`, `"text_muted"`…) a su color. Los colores hex y `"transparent"` pasan tal cual.

| Parámetro | Descripción |
| --- | --- |
| `name` | Token o color. |

### `tokens`

```python
tokens(self)
```

Todos los tokens como diccionario.

### `syntax_scopes`

```python
syntax_scopes(self)
```

Traduce los tokens de sintaxis de Zed a scopes de TextMate para el resaltador.

### `palette`

```python
palette(self)
```

La paleta base que se pasa a Iced para sus estilos internos. De uso interno.

## Temas incluidos

### `themes`

Espacio de nombres con los temas incluidos: `themes.ONE_DARK`, `themes.ONE_LIGHT` y `themes.GRUVBOX_DARK`.

### `all`

```python
all()
```

Lista con todos los temas incluidos.

## Utilidades (pyzed.theme)

### `current`

```python
current()
```

El tema que usan los componentes cuando no se pasa `theme=`.

### `use`

```python
use(theme)
```

Cambia el tema actual. `App` lo hace antes de cada `view()`, así que normalmente no lo necesitas.

| Parámetro | Descripción |
| --- | --- |
| `theme` | El tema. |

### `alpha`

```python
alpha(color, value)
```

Devuelve `color` con su opacidad multiplicada por `value`.

| Parámetro | Descripción |
| --- | --- |
| `color` | Color hex. |
| `value` | Factor de 0 a 1. |

```python
pz.theme.alpha("#74ade8", 0.2)  # "#74ade833"
```

### `mix`

```python
mix(a, b, amount=0.5)
```

Mezcla dos colores: `amount=0` es `a` y `amount=1` es `b`.

| Parámetro | Descripción |
| --- | --- |
| `a` | Primer color. |
| `b` | Segundo color. |
| `amount` | Proporción de `b`. |
