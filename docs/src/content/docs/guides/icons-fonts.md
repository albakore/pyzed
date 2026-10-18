---
title: Iconos y fuentes
description: Los iconos de Lucide, los iconos por tipo de archivo y cómo cargar fuentes propias.
sidebar:
  order: 6
---

## Iconos

Pyzed incluye la fuente de iconos de [Lucide](https://lucide.dev) (~2000 iconos, licencia ISC).

```python
pz.icon("folder", size=16, color="#74ade8")
ui.button("Abrir", self.abrir, icon="folder-open")
ui.list_item("Ajustes", self.ajustes, icon="settings")
```

Busca nombres en [lucide.dev/icons](https://lucide.dev/icons) o desde la terminal:

```bash
pyzed icons git
# git-branch, git-commit-horizontal, git-compare, git-fork, git-merge, git-pull-request, ...
```

`pyzed.icons.names()` devuelve la lista completa y `pyzed.icons.glyph("folder")` el carácter,
para mezclarlo con texto usando `font="icons"`.

### Iconos por tipo de archivo

```python
from pyzed import icons

icons.for_file("main.rs")       # ("file-code", "#dea584")
icons.for_file("Cargo.toml")    # ("file-cog", "#9c4221")
icons.language_for("main.py")   # "Python"
```

`ui.Tab.for_file` y `ui.tree` ya los usan.

## Fuentes

Fuentes incluidas:

| Nombre | Fuente |
| --- | --- |
| `"sans"` (por defecto) | IBM Plex Sans |
| `"mono"` | IBM Plex Mono |
| `"icons"` | Lucide |

Para usar otra, cárgala antes de ejecutar la app y refiérete a ella por su nombre de familia:

```python
pz.load_font("fonts/JetBrainsMono-Regular.ttf")

pz.text("fn main() {}", font="JetBrains Mono")
pz.code_editor("buf", texto, font="JetBrains Mono")
```

`load_font` también acepta los `bytes` del archivo.
