---
title: Visión general
description: Los componentes de pyzed.ui, inspirados en el editor Zed.
sidebar:
  order: 0
---

`pyzed.ui` es una colección de componentes listos para usar que reproducen el aspecto del editor
[Zed](https://zed.dev). Son **funciones** que devuelven widgets, así que se combinan libremente
con los [widgets base](/pyzed/reference/widgets/) y entre sí.

![Galería de componentes (One Dark)](../../../../screenshots/components-dark.png)

```python
import pyzed as pz
from pyzed import ui

ui.button("Guardar", self.guardar, icon="save", variant="solid", keys="ctrl-s")
```

## Reglas comunes

- **Colores del tema.** Cada componente lee el tema actual (`App.theme`). Cambiar el tema
  restiliza toda la interfaz. Todos aceptan `theme=` para usar otro.
- **Tokens o hex.** Los parámetros de color (`color`, `icon_color`, `tint`…) aceptan un token del
  tema como `"accent"`, `"text_muted"` o `"error"`, o un color `"#rrggbb"`.
- **Mensajes o callables.** `on_press`, `on_select`, `on_toggle`… aceptan un mensaje para `update`
  o un callable. Los que producen un valor (texto, `bool`, id) llaman al callable con ese valor.
- **Iconos.** El parámetro `icon=` acepta cualquier nombre de [Lucide](https://lucide.dev).
- **Atajos.** `keys="ctrl-shift-p"` muestra el atajo al estilo de Zed (símbolos en macOS).

## Grupos

| Grupo | Componentes |
| --- | --- |
| [Básicos](/pyzed/components/basics/) | `button`, `icon_button`, `label`, `muted`, `heading`, `badge`, `indicator`, `kbd`, `avatar`, `tooltip`, `divider`, `card` |
| [Formularios](/pyzed/components/forms/) | `input`, `search_input`, `switch`, `checkbox`, `slider`, `progress`, `segmented`, `field` |
| [Listas y árbol](/pyzed/components/lists/) | `list_item`, `list_header`, `tree` + `TreeNode`, `menu` + `MenuItem` |
| [Navegación](/pyzed/components/navigation/) | `tab_bar` + `Tab`, `breadcrumbs`, `toolbar` |
| [Workspace](/pyzed/components/workspace/) | `workspace`, `title_bar`, `title_button`, `status_bar`, `status_item`, `panel`, `panel_header` |
| [Overlays](/pyzed/components/overlays/) | `layer`, `modal`, `command_palette`, `picker`, `fuzzy_filter`, `toast`, `toasts` |
| [Código](/pyzed/components/code/) | `editor`, `terminal`, `ansi` |

Para ver todos funcionando, ejecuta la galería:

```bash
python examples/gallery.py
```

:::tip[Ilustraciones]
Las imágenes de esta sección se generan con `python docs/scripts/component_shots.py`, que dibuja
cada ejemplo fuera de pantalla con `App.screenshot`.
:::
