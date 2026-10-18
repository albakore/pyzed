---
title: Más controles
description: Desplegables, radios, campos numéricos, botones divididos, chips y secciones plegables.
sidebar:
  order: 8
---

![Más controles](../../../../assets/components/controls.png)

```python
class Ajustes(pz.App):
    def __init__(self):
        self.lenguaje = "Rust"
        self.fuente = 14
        self.indentacion = "a"
        self.alineado = "c"
        self.avanzado = True

    def view(self):
        return pz.column([
            pz.row([
                ui.select(["Python", "Rust", "TypeScript"], self.lenguaje,
                          lambda v: setattr(self, "lenguaje", v), width=160),
                ui.number_field(self.fuente, lambda v: setattr(self, "fuente", v), min=8, max=32, suffix="px"),
                ui.split_button("Ejecutar", self.ejecutar, self.abrir_menu, icon="play"),
            ], spacing=10, align="center"),
            ui.radio_group([("a", "Espacios"), ("b", "Tabs")], self.indentacion,
                           lambda v: setattr(self, "indentacion", v), horizontal=True),
            ui.toggle_group([("l", "align-left"), ("c", "align-center"), ("r", "align-right")],
                            self.alineado, lambda v: setattr(self, "alineado", v)),
            pz.row([ui.chip("python", icon="tag", selected=True),
                    ui.chip("rust", on_remove=self.quitar_etiqueta),
                    ui.chip("iced", on_press=self.filtrar)], spacing=6),
            ui.disclosure("Opciones avanzadas", ui.muted("Contenido plegable."), open=self.avanzado,
                          on_toggle=lambda: setattr(self, "avanzado", not self.avanzado)),
        ], spacing=14)
```

| Componente | Para qué |
| --- | --- |
| `ui.select(options, selected, on_select)` | Desplegable con el estilo de Zed (`DropdownMenu`). Llama a `on_select` con la opción elegida. |
| `ui.radio_group(options, selected, on_select)` | Opciones excluyentes. `options` son textos o pares `(valor, etiqueta)`. `horizontal=True` las pone en fila. |
| `ui.number_field(value, on_change)` | Número con botones `−`/`+`, límites `min`/`max`, `step` y `suffix`. |
| `ui.split_button(content, on_press, on_menu)` | Acción principal y un chevron para más opciones (normalmente abre un [`ui.popover`](/pyzed/es/components/content/#popover)). |
| `ui.toggle_group(options, selected, on_select)` | Grupo segmentado solo con iconos: `options` son pares `(valor, icono)`. |
| `ui.chip(content)` | Etiqueta compacta. `on_press` la hace pulsable y `on_remove` añade una ✕. |
| `ui.disclosure(title, content, open=)` | Sección plegable. El estado abierto/cerrado es tuyo: cámbialo en `on_toggle`. |

Para los controles básicos (`input`, `switch`, `slider`…) mira [Formularios](/pyzed/es/components/forms/).
Referencia completa: [Controles](/pyzed/es/reference/ui/#controles).
