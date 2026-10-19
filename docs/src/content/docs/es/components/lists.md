---
title: Listas, árbol y menús
description: "Filas de lista, el árbol de archivos del proyecto y menús contextuales: componentes de listas estilo Zed para apps de escritorio en Python."
sidebar:
  order: 3
---

:::tip[Biblioteca de componentes]
Cada componente tiene ahora su propia página, con vista previa, ejemplos y su API completa, en la
[biblioteca de componentes](/pyzed/es/library/). Esta página se mantiene como resumen.
:::

## Elementos de lista

![Elementos de lista](../../../../assets/components/list.png)

```python
pz.column([
    ui.list_header("RECIENTES", end=ui.icon_button("plus", self.nuevo, size="xs")),
    ui.list_item("main.py", self.abrir, icon="file-code", icon_color="#3572a5", selected=True, inset=True),
    ui.list_item("README.md", self.abrir, icon="file-text", inset=True, end=ui.badge("M", tint="warning")),
    ui.list_item("Cargo.toml", self.abrir, icon="file-cog", inset=True, end=ui.kbd("ctrl-1", size="xs")),
    ui.list_item("antiguo.txt", self.abrir, icon="file", inset=True, disabled=True),
], width=300)
```

`list_item` tiene huecos `start` y `end` para cualquier widget, `indent` para anidar,
`focused` para el borde de foco y `on_right_press` para abrir un menú contextual.

Para pasar el elemento al callback, usa un argumento por defecto en la lambda:

```python
[ui.list_item(f, lambda f=f: self.abrir(f), selected=f == self.actual) for f in self.archivos]
```

## Árbol de archivos

El panel de proyecto de Zed: carpetas plegables, iconos por tipo de archivo y colores de git.

![Árbol de archivos](../../../../assets/components/tree.png)

```python
class Explorador(pz.App):
    def __init__(self):
        self.nodes = ui.TreeNode.from_paths(
            ["src/main.rs", "src/app.rs", "src/ui/button.rs", "src/ui/mod.rs",
             "tests/app.rs", "Cargo.toml", "README.md"],
            status={"src/app.rs": "modified", "src/ui/button.rs": "created", "README.md": "modified"},
        )
        self.expanded = {"src", "src/ui"}
        self.selected = "src/app.rs"

    def toggle(self, folder):
        self.expanded ^= {folder}

    def select(self, path):
        self.selected = path

    def view(self):
        return ui.tree(self.nodes, expanded=self.expanded, selected=self.selected,
                       on_toggle=self.toggle, on_select=self.select)
```

- `TreeNode.from_paths(rutas, status=...)` crea el árbol, pone las carpetas primero y propaga el
  estado de git a las carpetas que contienen cambios.
- El id de cada nodo es su ruta (`"src/ui/button.rs"`).
- `status`: `"modified"`, `"created"`, `"deleted"`, `"conflict"` o `"ignored"`.
- Puedes crear los nodos a mano: `TreeNode("src", children=[TreeNode("main.rs", id="src/main.rs")])`.

Para leer una carpeta real:

```python
from pathlib import Path

root = Path(".")
paths = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]
nodes = ui.TreeNode.from_paths(paths)
```

## Menú contextual

![Menú contextual](../../../../assets/components/menu.png)

```python
ui.menu([
    ui.MenuItem("Nuevo archivo", self.nuevo, icon="file-plus", keys="ctrl-n"),
    ui.MenuItem("Nueva carpeta", self.nueva_carpeta, icon="folder-plus"),
    ui.SEPARATOR,
    "EDITAR",                                   # un texto suelto es un encabezado
    ui.MenuItem("Copiar ruta", self.copiar, keys="ctrl-alt-c"),
    ui.MenuItem("Ajuste de línea", self.toggle_wrap, checked=self.wrap),
    ui.SEPARATOR,
    ui.MenuItem("Eliminar", self.eliminar, icon="trash-2", danger=True),
])
```

Para mostrarlo flotando, úsalo como overlay de [`ui.layer`](/pyzed/es/components/overlays/#capas):

```python
layout = ui.layer(layout, self.menu_abierto and ui.menu(...) or None,
                  on_dismiss=self.cerrar_menu, align_x="start", offset=120)
```

Referencia completa: [Listas, árbol y menús](/pyzed/es/reference/ui/#listas-árbol-y-menús).
