---
title: Visión general
description: "Resumen de pyzed.ui, los componentes listos para usar para GUIs de escritorio en Python: workspaces, pestañas, árboles, editores, paletas y menús."
sidebar:
  order: 0
---

:::tip[Biblioteca de componentes]
Cada componente tiene ahora su propia página, con vista previa, ejemplos y su API completa, en la
[biblioteca de componentes](/pyzed/es/library/). Esta página se mantiene como resumen.
:::

`pyzed.ui` es una colección de componentes listos para usar que reproducen el aspecto del editor
[Zed](https://zed.dev). Son **funciones** que devuelven widgets, así que se combinan libremente
con los [widgets base](/pyzed/es/reference/widgets/) y entre sí.

![Galería de componentes (One Dark)](../../../../../screenshots/components-dark.png)

```python
import pyzed as pz
from pyzed import ui

ui.button("Guardar", self.guardar, icon="save", variant="solid", keys="ctrl-s")
```

## Reglas comunes

- **Colores del tema.** Cada componente lee el tema actual (`App.theme`, o el de la ventana en
  [multi-ventana](/pyzed/es/guides/windows/)). Cambiar el tema restiliza toda la interfaz. Todos aceptan `theme=` para usar otro.
- **Tokens o hex.** Los parámetros de color (`color`, `icon_color`, `tint`…) aceptan un token del
  tema como `"accent"`, `"text_muted"` o `"error"`, o un color `"#rrggbb"`.
- **Mensajes o callables.** `on_press`, `on_select`, `on_toggle`… aceptan un mensaje para `update`
  o un callable. Los que producen un valor (texto, `bool`, id) llaman al callable con ese valor.
- **Iconos.** El parámetro `icon=` acepta cualquier nombre de [Lucide](https://lucide.dev).
- **Atajos.** `keys="ctrl-shift-p"` muestra el atajo (con símbolos en macOS).

## Grupos

| Grupo | Componentes |
| --- | --- |
| [Básicos](/pyzed/es/components/basics/) | `button`, `icon_button`, `label`, `muted`, `heading`, `badge`, `indicator`, `kbd`, `avatar`, `tooltip`, `divider`, `card` |
| [Formularios](/pyzed/es/components/forms/) | `input`, `search_input`, `switch`, `checkbox`, `slider`, `progress`, `segmented`, `field` |
| [Listas y árbol](/pyzed/es/components/lists/) | `list_item`, `list_header`, `tree` + `TreeNode`, `menu` + `MenuItem` |
| [Navegación](/pyzed/es/components/navigation/) | `tab_bar` + `Tab`, `breadcrumbs`, `toolbar` |
| [Workspace](/pyzed/es/components/workspace/) | `workspace`, `title_bar`, `title_button`, `status_bar`, `status_item`, `panel`, `panel_header` |
| [Overlays](/pyzed/es/components/overlays/) | `layer`, `modal`, `command_palette`, `picker`, `fuzzy_filter`, `toast`, `toasts` |
| [Código](/pyzed/es/components/code/) | `editor`, `terminal`, `ansi` |
| [Más controles](/pyzed/es/components/controls/) | `select`, `radio_group`, `number_field`, `split_button`, `toggle_group`, `chip`, `disclosure` |
| [Datos y feedback](/pyzed/es/components/data/) | `table` + `Column`, `callout`, `empty_state`, `settings_group`, `stat`, `sparkline`, `bar_chart`, `donut`, `spinner`, `count_badge`, `facepile`, `diff_stat`, `keybinding_hint` |
| [Contenido y paneles](/pyzed/es/components/content/) | `markdown`, `split`, `popover`; widgets base `pz.image`, `pz.image_viewer`, `pz.rich_text`, `pz.qr_code`, `pz.grid` |
| [Diálogos y herramientas](/pyzed/es/components/dialogs/) | `dialog_layer`, `alert`, `confirm`, `prompt`, `choice`, `unsaved_changes`, `accordion`, `Log` + `console`, `shortcuts`, `about`, `ColorPicker`, `color_swatch` |

Para ver todos funcionando, ejecuta la galería:

```bash
python examples/gallery.py
```

:::tip[Ilustraciones]
Las imágenes de esta sección se generan con `python docs/scripts/component_shots.py`, que dibuja
cada ejemplo fuera de pantalla con `App.screenshot`.
:::
