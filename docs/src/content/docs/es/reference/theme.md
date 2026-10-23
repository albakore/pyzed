---
title: "Temas"
description: "Referencia de la API de Theme en Pyzed: los temas incluidos, los tokens de color, cómo derivar temas propios y utilidades de color."
sidebar:
  order: 5
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs_es.py. -->

Ver la guía de [temas](/pyzed/es/theming/themes/) para la lista de tokens y cómo crear los tuyos.

## Theme

### `Theme`

Un tema: un dataclass inmutable con los tokens de color (superficies, bordes, elementos, texto, estado, editor, sintaxis, colores de colaboradores y ANSI) y métricas (`radius`, `radius_sm`, `ui_font_size`, `buffer_font_size`). La propiedad `is_dark` indica si es oscuro.

**Métodos y propiedades**

#### `Theme.is_dark`

```python
Theme.is_dark  # property
```

Si el aspecto del tema es oscuro.

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

Traduce los tokens de sintaxis del tema a scopes de TextMate para el resaltador.

### `palette`

```python
palette(self)
```

La paleta base que se pasa a Iced para sus estilos internos. De uso interno.

### `with_accent`

```python
with_accent(self, accent)
```

Una copia con otro color de acento y todo lo que depende de él (foco, selección, enlaces, botones principales, texto sobre acento).

| Parámetro | Descripción |
| --- | --- |
| `accent` | El color. |

### `generate`

```python
generate(
    name,
    *,
    background,
    text,
    accent,
    appearance=None,
    error=None,
    warning=None,
    success=None,
    syntax=None,
    radius=6.0,
)
```

Crea un tema completo a partir de unos pocos colores. Superficies, bordes, estados de hover y textos atenuados se mezclan a partir de `background` y `text`; la apariencia se deduce del brillo del fondo si no se indica.

| Parámetro | Descripción |
| --- | --- |
| `name` | Nombre. |
| `background` | Color del editor/fondo. |
| `text` | Color del texto. |
| `accent` | Color de acento. |
| `appearance` | `"dark"` o `"light"`. |
| `error` | Color de error. |
| `warning` | Color de aviso. |
| `success` | Color de éxito. |
| `syntax` | Colores de sintaxis extra. |
| `radius` | Radio de las esquinas. |

```python
pz.Theme.generate("Propio", background="#1b1d23", text="#e6e6e6", accent="#ff8a65")
```

### `from_zed`

```python
from_zed(source, name=None)
```

Lee un tema de un archivo de familia de temas de Zed (`.json`) o un dict. Una familia suele tener varios (Ayu Dark/Light/Mirage); `name` elige uno (por defecto, el primero).

| Parámetro | Descripción |
| --- | --- |
| `source` | Ruta, texto JSON o dict. |
| `name` | Nombre del tema dentro de la familia. |

### `to_dict`

```python
to_dict(self)
```

Un dict apto para JSON; `Theme.from_dict` lo vuelve a leer.

### `from_dict`

```python
from_dict(data, *, base=None)
```

Crea un tema a partir de `to_dict`. Los tokens que falten salen de `base` (One Dark u One Light según `appearance`).

| Parámetro | Descripción |
| --- | --- |
| `data` | Los tokens. |
| `base` | Tema base. |

### `save`

```python
save(self, path)
```

Guarda el tema como JSON (formato propio de Pyzed).

| Parámetro | Descripción |
| --- | --- |
| `path` | Ruta del archivo. |

### `load`

```python
load(path)
```

Lee un tema escrito con `save` (para temas de Zed usa `from_zed`).

| Parámetro | Descripción |
| --- | --- |
| `path` | Ruta del archivo. |

## Temas incluidos

### `themes`

Espacio de nombres con los temas incluidos (los de Pyzed y las familias One, Ayu y Gruvbox) y el registro de temas. Los incluidos también están como atributos: `themes.PYZED_DARK` (el predeterminado), `themes.PYZED_LIGHT`, `themes.ONE_DARK`, `themes.ONE_LIGHT`, `themes.AYU_DARK`, `themes.AYU_LIGHT`, `themes.AYU_MIRAGE`, `themes.GRUVBOX_DARK`, `themes.GRUVBOX_LIGHT`…

### `all`

```python
all()
```

Lista con todos los temas incluidos.

### `names`

```python
names()
```

Nombres de todos los temas registrados.

### `get`

```python
get(name)
```

Busca un tema por nombre (sin distinguir mayúsculas). Lanza `KeyError` si no existe.

| Parámetro | Descripción |
| --- | --- |
| `name` | Nombre. |

### `register`

```python
register(theme)
```

Añade (o reemplaza) un tema para poder usarlo por su nombre.

| Parámetro | Descripción |
| --- | --- |
| `theme` | El tema. |

### `load_zed`

```python
load_zed(source)
```

Carga y registra todos los temas de un archivo de familia de Zed.

| Parámetro | Descripción |
| --- | --- |
| `source` | Ruta, texto JSON o dict. |

### `auto`

```python
auto(light='Pyzed Light', dark='Pyzed Dark')
```

Un tema que sigue el modo claro/oscuro del sistema.

| Parámetro | Descripción |
| --- | --- |
| `light` | Tema (o nombre) para modo claro. |
| `dark` | Tema (o nombre) para modo oscuro. |

### `AutoTheme`

Lo que devuelve `themes.auto`: un par `(light, dark)`. `pick(dark)` devuelve el que toca.

**Métodos y propiedades**

#### `AutoTheme.pick`

```python
AutoTheme.pick(dark)
```

Devuelve el tema oscuro si `dark` es verdadero; si no, el claro.

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

### `resolve`

```python
resolve(value, *, dark=True)
```

Convierte un valor de `App.theme` (tema, nombre, `AutoTheme` o `None`) en un `Theme`.

| Parámetro | Descripción |
| --- | --- |
| `value` | El valor. |
| `dark` | Si el sistema está en modo oscuro. |

### `lighten`

```python
lighten(color, amount=0.1)
```

Aclara un color.

| Parámetro | Descripción |
| --- | --- |
| `color` | Color hex. |
| `amount` | Cantidad de 0 a 1. |

### `darken`

```python
darken(color, amount=0.1)
```

Oscurece un color.

| Parámetro | Descripción |
| --- | --- |
| `color` | Color hex. |
| `amount` | Cantidad de 0 a 1. |

### `luminance`

```python
luminance(color)
```

Luminancia relativa (WCAG) de un color, de 0 a 1.

| Parámetro | Descripción |
| --- | --- |
| `color` | Color hex. |

### `contrast`

```python
contrast(a, b)
```

Relación de contraste WCAG entre dos colores (1 a 21).

| Parámetro | Descripción |
| --- | --- |
| `a` | Primer color. |
| `b` | Segundo color. |

### `readable_on`

```python
readable_on(background, light='#fafafa', dark='#1c2025')
```

Devuelve `light` u `dark`, el que más contraste tenga sobre `background`.

| Parámetro | Descripción |
| --- | --- |
| `background` | Color de fondo. |
| `light` | Texto claro. |
| `dark` | Texto oscuro. |

## Logo (pyzed.brand)

### `mark`

```python
mark(size=20, *, color=None, theme=None)
```

La marca de Pyzed (la pitón que dibuja la «p») como widget SVG teñido con un color del tema.

| Parámetro | Descripción |
| --- | --- |
| `size` | Alto en píxeles. |
| `color` | Token de color o hex (`text_accent` por defecto). |
| `theme` | Tema. |

```python
ui.title_bar([pz.brand.mark(16), ui.label("Mi app")], [])
```

### `wordmark`

```python
wordmark(height=28, *, theme=None)
```

El logotipo «pyzed», con la pitón como su «p»; la versión oscura en temas oscuros.

| Parámetro | Descripción |
| --- | --- |
| `height` | Alto en píxeles. |
| `theme` | Tema. |
