---
title: Estilos
description: "Da estilo a cualquier widget de Pyzed como en CSS: colores, bordes, radios, sombras y estados, estilos reutilizables y el estilo global de la app."
sidebar:
  order: 4
---

Todo widget tiene un método `style()` que le da estilo como en CSS: fondo, bordes, radio,
sombra, padding, margen, tamaño y tipografía.

![Botones con estilo, una tarjeta y un gradiente con máscara](../../../../assets/tutorials/styles.png)

```python
ui.button("Guardar", self.guardar).style(radius=0, border=(2, "#ef4444"))
pz.text("Título").style(size=20, weight="bold", color="accent")
pz.column([...]).style(background="panel", padding=16, radius=10, shadow=("#00000055", (0, 6), 18))
```

En un botón o un contenedor, `style()` cambia el propio widget (un botón cuadrado sigue siendo
un botón). Los demás widgets reciben una caja alrededor que lleva el estilo.

## Propiedades

| Propiedad | Valores |
| --- | --- |
| `background` | Un color, un `pz.Gradient` o un `pz.Paint`. |
| `color` | Color del texto. |
| `font` | `"sans"`, `"mono"`, `"serif"` o una familia cargada con `pz.load_font`. |
| `weight` | `"light"`, `"normal"`, `"medium"`, `"semibold"`, `"bold"`… o de 100 a 900. |
| `italic`, `size`, `line_height` | Tipografía. |
| `border_color`, `border_width` | El borde; `border=(ancho, color)` fija ambos. |
| `radius` | Un número, o `(arriba_izq, arriba_der, abajo_der, abajo_izq)`. |
| `shadow` | `(color, (x, y), desenfoque)`. |
| `padding`, `margin` | Un número, `(vertical, horizontal)` o `(arriba, derecha, abajo, izquierda)`. |
| `width`, `height` | Píxeles, `"fill"`, `"shrink"` o `"fill:N"`; `max_width`, `max_height`, `min_width` y `min_height` en píxeles. |
| `align_x`, `align_y` | Dónde se coloca el contenido dentro de la caja. |
| `clip` | Recorta el contenido a la caja. |
| `position`, `top`, `right`, `bottom`, `left`, `z_index` | `position="absolute"` coloca un hijo de una [`pz.box`](/pyzed/es/guides/layout/#cajas) por sus desplazamientos, fuera del flujo. |
| `opacity`, `translate`, `scale`, `rotate` | Desvanecen, desplazan, escalan o giran cómo se dibuja el widget, sin cambiar el layout. |
| `blur`, `backdrop_blur` | Desenfocan el widget o lo que tiene detrás. |
| `glow`, `bloom`, `glass` | Efectos visuales: un halo, luz que desborda de las partes brillantes y un panel esmerilado. Ver [Animación y efectos](/pyzed/es/guides/animation/#efectos). |

Los colores pueden ser textos hex (con alfa, `"#3b82f680"`), tuplas `(r, g, b[, a])` o tokens
del tema como `"accent"`, `"panel"` o `"text_muted"`, así que los estilos siguen al tema.

Las propiedades de texto se aplican a **todos los textos de dentro** del widget, también a las
etiquetas de los componentes de `pyzed.ui`. Gana el estilo más cercano.

## Estados y transiciones

Como `:hover`, `:active` y `:focus` en CSS, un estilo puede decir cómo se ve el widget
mientras el puntero está encima (`hover`), mientras se pulsa (`pressed`, o `active`) y
mientras tiene el foco del teclado (`focus`). `transition` anima el cambio, como
`transition` en CSS:

```python
ui.button("Guardar", self.save).style(
    background="accent", radius=6,
    hover={"background": "#4f8cff", "translate": (0, -1)},
    pressed={"scale": 0.97},
    transition=120,                      # milisegundos, "0.2s", True o {"duration", "easing", "delay"}
)
```

Un estado puede cambiar `background` (un color), `color`, `border_color`, `border_width`,
`radius`, `opacity`, `translate`, `scale`, `rotate` y `blur`. Ninguno mueve los widgets de
alrededor, así que el hover nunca descoloca el layout. Sin `transition` el estado se ve al
instante. Con ella, los cambios de `opacity`, `translate`, `scale`, `rotate` y `blur` de un
render al siguiente también se animan. Para algo más, ver [Animación](/pyzed/es/guides/animation/).

## Hojas de estilo

`pz.stylesheet` añade reglas por selector, como un archivo CSS. `widget.classes(...)` le da
clases (y un `id`) a un widget, y las reglas que coinciden le dan estilo:

```python
pz.stylesheet({
    ".card": {"background": "panel", "padding": 16, "radius": 8, "border": (1, "border")},
    ".card:hover": {"border_color": "accent"},
    ".card.selected, #featured": {"border": (2, "accent")},
    "Rating": {"padding": 4},                       # todos los componentes Rating
})

pz.column([...]).classes("card", "selected" if self.chosen else None)
Rating(value=3, class_="card", id="featured")       # los componentes aceptan class_= e id=
```

- Selectores: `.clase`, varias clases (`.card.selected`), `#id`, el nombre de la clase de un
  componente y un `:hover`, `:pressed` (o `:active`) o `:focus` opcional. Las comas juntan
  varios selectores en una regla.
- Como en CSS, ganan los selectores más específicos (un id gana a las clases, más clases
  ganan a menos y las clases ganan al nombre de un componente) y después la regla posterior.
  Un `style()` después de `classes()` va encima.
- Definir otra vez un selector reemplaza su regla, así que recargar el código no acumula
  reglas. `pz.clear_stylesheet()` las quita todas.
- Los estilos con nombre de `pz.define_style` también sirven como clases.

## Estilos responsive

Los estilos pueden seguir el tamaño de la ventana, como las media queries de CSS:

```python
pz.stylesheet({
    ".sidebar": {"width": 260},
    "@media (max_width: 700)": {".sidebar": {"width": 64}},
    "@md": {".content": {"padding": 32}},             # un breakpoint: desde 768 px de ancho
})
panel.style(padding=24, media={"max_width: 600": {"padding": 8}})
```

- Una consulta es `min_width`, `max_width`, `min_height` o `max_height` en píxeles
  (`"max_width: 600"` o `"(max_width: 600px)"`), `orientation` (`portrait` o `landscape`) o
  `theme` (`dark` o `light`). Se juntan varias con `and`.
- Los breakpoints siguen a Tailwind y se aplican desde ese ancho en adelante: `sm` (640),
  `md` (768), `lg` (1024), `xl` (1280) y `xxl` (1536).
- Los estilos se actualizan al cambiar el tamaño de la ventana.
- En una vista, `pz.viewport()` devuelve el tamaño de la ventana y `pz.media("max_width: 600")`
  dice si una consulta se cumple. `pz.current_breakpoint()` devuelve `"xs"`, `"sm"`, `"md"`, etc.
  `pz.responsive(lambda w, h: ...)` construye contenido con el espacio que recibe de verdad un widget.

## Reutilizar estilos

```python
tarjeta = pz.Style(background="elevated", border=(1, "border"), radius=10, padding=16)
pz.column([...]).style(tarjeta)
pz.column([...]).style(tarjeta | pz.Style(shadow=("#0006", (0, 4), 12)))   # gana el de la derecha

pz.define_style("pill", radius=999, padding=(4, 12), size=12, weight="semibold")
pz.text("nuevo").style("pill", background="accent")
```

`widget.style(a, b, color=...)` combina en orden, y volver a llamar a `style()` combina con lo
que el widget ya tiene. Pasar `None` en una propiedad la quita. `Style.to_dict()` y
`Style.from_dict()` convierten un estilo en datos aptos para JSON y viceversa.

Los componentes también aceptan `style=`: `Rating(value=3, style="card")`.

## Gradientes, opacidad y máscaras

```python
atardecer = pz.Gradient(["#f97316", "#db2777", "#7c3aed"], angle=120)
caja.style(background=atardecer)
caja.style(background=pz.Paint("success", opacity=0.2))                 # un token translúcido
caja.style(background=pz.Paint(atardecer, mask=pz.Mask([1, 0.15])))     # se desvanece
```

- `pz.Gradient(paradas, angle=180)`: colores repartidos por igual o pares `(posición, color)`.
  Los ángulos siguen CSS (0 arriba, 90 derecha). Hasta 8 paradas.
- `pz.Mask(paradas)`: opacidades en la dirección del relleno (sobre un color liso, en su propio
  `angle`).
- `pz.Paint(relleno, opacity=, mask=)`: un color o gradiente con opacidad general y máscara.

## Selector de color

`ui.ColorPicker` edita cualquiera de ellos: un color con alfa, un gradiente (un clic en la barra
añade una parada, las paradas se arrastran y la papelera quita la seleccionada) o una máscara.
Devuelve un texto hex, un `pz.Gradient` o un `pz.Paint`, listos para `background`:

```python
ui.ColorPicker(value=self.fill, on_change=lambda e: setattr(self, "fill", e.value))
```

![El selector de color editando un gradiente](../../../../assets/tutorials/color-picker.png)

`alpha=False`, `gradients=False` y `masks=False` ocultan esas partes; `swatches=[...]` fija los
colores rápidos. `ui.color_swatch(valor)` muestra un valor como un cuadrito. Ver
[`examples/color_picker.py`](https://github.com/albakore/pyzed/blob/main/examples/color_picker.py).

## El estilo global

`App.style` da estilo a toda la ventana, y `pz.set_style(...)` fija un estilo para todas las
ventanas (el `style` de cada ventana va encima):

```python
class MiApp(pz.App):
    style = pz.Style(font="serif", size=15, color="#e6e1cf", radius=2)
```

Sus propiedades de texto completan lo que los textos no fijan, y su `color`, `size`,
`background`, `border_color` y `radius` también se vuelven los tokens `text`, `ui_font_size`,
`background`, `border` y `radius` del tema, así que los componentes de `pyzed.ui` los siguen.
Cambia `self.style` cuando quieras para cambiar el estilo de la app. Para otros colores del
tema, deriva un tema: `self.theme = themes.get("One Dark").with_accent("#ff6b6b")` (ver
[Temas](/pyzed/es/theming/themes/)).

Ver [`examples/styles.py`](https://github.com/albakore/pyzed/blob/main/examples/styles.py).
