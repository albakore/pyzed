---
title: Contenido y paneles
description: "Markdown, texto enriquecido, imágenes, códigos QR, paneles redimensionables, rejillas y popovers: componentes de contenido para GUIs en Python."
sidebar:
  order: 10
---

:::tip[Biblioteca de componentes]
Cada componente tiene ahora su propia página, con vista previa, ejemplos y su API completa, en la
[biblioteca de componentes](/pyzed/es/library/). Esta página se mantiene como resumen.
:::

## Markdown, texto enriquecido y QR

![Markdown, rich_text y QR](../../../../assets/components/content.png)

```python
pz.markdown("## Markdown\n\nTexto con **negrita**, `código` y [enlaces](https://iced.rs).",
            on_link=webbrowser.open)   # import webbrowser

pz.rich_text([
    pz.span("rich_text "),
    pz.span("mezcla ", color="#e5c07b"),
    pz.span("estilos", weight="bold", underline=True),
    pz.span(" en una línea", italic=True),
])

pz.qr_code("https://albakore.github.io/pyzed/", cell_size=4)
```

- `pz.markdown(source)` renderiza Markdown con los colores del tema. `ui.markdown` es la misma
  idea con el tamaño y los colores de los componentes. `on_link(url)` recibe los enlaces pulsados.
- `pz.rich_text(spans)` combina fragmentos `pz.span(texto, color=, size=, font=, weight=, italic=,
  bg=, underline=, strikethrough=, link=)` en un solo bloque de texto.
- `pz.qr_code(data)` dibuja un código QR; `color` y `bg` cambian sus colores.

Ejemplo completo: [`markdown_viewer.py`](https://github.com/albakore/pyzed/blob/main/examples/markdown_viewer.py).

## Imágenes

![Imágenes](../../../../assets/components/media.png)

```python
pz.image("captura.png", width=240, height=140, content_fit="contain")
pz.image("captura.png", width=160, height=140, opacity=0.5)
pz.image("pixel-art.png", width=120, height=140, filter="nearest")
pz.image_viewer("mapa.png", width="fill", height="fill")   # zoom con la rueda, arrastrar para mover
```

`source` puede ser una ruta, `bytes` con el archivo (PNG, JPEG, GIF, WebP, BMP…) o píxeles RGBA
con `size=(ancho, alto)`. Opciones: `content_fit` (`"contain"`, `"cover"`, `"fill"`, `"none"`,
`"scale_down"`), `filter` (`"linear"` o `"nearest"`), `opacity`, `radius`, `rotation` y `scale`.
Para iconos vectoriales usa `pz.svg`.

Ejemplo completo: [`image_viewer.py`](https://github.com/albakore/pyzed/blob/main/examples/image_viewer.py).

## Paneles redimensionables

![Paneles divididos](../../../../assets/components/split.png)

```python
ui.split(
    barra_lateral,
    ui.split(editor, terminal, vertical=True, ratio=self.alto, on_resize=self.set_alto),
    ratio=self.ancho, on_resize=self.set_ancho,
)
```

`ui.split(first, second)` separa dos widgets con un divisor arrastrable. La proporción es tuya:
guárdala en `on_resize(ratio)`. `vertical=True` los apila. `pz.split` es la versión base, con
`color`, `hover_color`, `thickness` y `handle` configurables.

## Rejillas

```python
pz.grid([tarjeta(p) for p in proyectos], columns=3, spacing=12)
pz.grid(miniaturas, max_width=180, spacing=8, aspect_ratio=1)   # columnas según el ancho
```

`columns` fija el número de columnas; `max_width` las calcula según el espacio disponible.

## Popover

![Popover con un menú contextual](../../../../assets/components/popover.png)

```python
def view(self):
    base = pz.mouse_area(contenido, on_move=self.recordar_puntero, on_right_press=self.abrir_menu)
    menu = ui.menu([ui.MenuItem("Copiar", self.copiar), ui.MenuItem("Pegar", self.pegar)]) if self.menu else None
    return ui.popover(base, menu, x=self.x, y=self.y, on_dismiss=self.cerrar_menu)
```

`ui.popover(base, content, x=, y=)` muestra `content` encima de `base` en esa posición; un clic
fuera llama a `on_dismiss`. Con `content=None` solo se ve `base`.

Ejemplo completo: [`context_menu.py`](https://github.com/albakore/pyzed/blob/main/examples/context_menu.py).
Referencia: [Widgets base](/pyzed/es/reference/widgets/) y [Overlays](/pyzed/es/reference/ui/#overlays).
