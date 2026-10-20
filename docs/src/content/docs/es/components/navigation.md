---
title: Navegación
description: "Pestañas de editor, breadcrumbs y barra de herramientas: componentes de navegación para crear GUIs tipo IDE en Python con Pyzed."
sidebar:
  order: 4
---

:::tip[Biblioteca de componentes]
Cada componente tiene ahora su propia página, con vista previa, ejemplos y su API completa, en la
[biblioteca de componentes](/pyzed/es/library/). Esta página se mantiene como resumen.
:::

![Pestañas, breadcrumbs y barra de herramientas](../../../../assets/components/tabs.png)

```python
pz.column([
    ui.tab_bar(
        [
            ui.Tab.for_file("src/main.rs"),
            ui.Tab.for_file("src/app.rs", dirty=True, status="modified"),
            ui.Tab.for_file("README.md", preview=True),
        ],
        active="src/main.rs",
        on_select=self.activar,
        on_close=self.cerrar,
        start=[ui.icon_button("arrow-left", self.atras, size="sm"),
               ui.icon_button("arrow-right", self.adelante, size="sm")],
        end=[ui.icon_button("plus", self.nuevo, size="sm"),
             ui.icon_button("columns-2", self.dividir, size="sm")],
    ),
    ui.toolbar(
        [ui.breadcrumbs([("file-code", "src"), "main.rs", "fn main"])],
        [ui.icon_button("search", self.buscar, size="sm")],
    ),
])
```

## Pestañas

- `Tab(id, label, icon=None, icon_color=None, dirty=False, preview=False, status=None)`.
- `Tab.for_file(ruta)` usa el nombre del archivo como etiqueta, la ruta como id y el icono de su tipo.
- `dirty=True` muestra un punto; al pasar el ratón se convierte en el botón de cerrar.
- `preview=True` dibuja el nombre en cursiva (pestaña de vista previa).
- `status` tiñe el nombre con el color de git.
- `on_select(id)` y `on_close(id)` reciben el id de la pestaña.

Un patrón habitual para gestionar pestañas:

```python
def abrir(self, path):
    if path not in self.abiertas:
        self.abiertas.append(path)
    self.activa = path

def cerrar(self, path):
    i = self.abiertas.index(path)
    self.abiertas.remove(path)
    if self.activa == path:
        self.activa = self.abiertas[min(i, len(self.abiertas) - 1)] if self.abiertas else None
```

## Breadcrumbs

```python
ui.breadcrumbs(["src", "ui", "button.rs"])
ui.breadcrumbs([("folder", "src"), ("file-code", "main.rs")], on_press=self.ir_a_nivel)
```

Las partes pueden ser textos o tuplas `(icono, texto)`. `on_press` recibe el índice.

## Barra de herramientas

`ui.toolbar(start, end)` es la barra bajo las pestañas de un editor de código: normalmente breadcrumbs a
la izquierda y acciones del buffer a la derecha.

Referencia completa: [Navegación](/pyzed/es/reference/ui/#navegación).
