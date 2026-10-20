---
title: Overlays
description: "Capas, modales, paleta de comandos, pickers con búsqueda difusa y notificaciones: componentes superpuestos para apps de escritorio con Pyzed."
sidebar:
  order: 6
---

:::tip[Biblioteca de componentes]
Cada componente tiene ahora su propia página, con vista previa, ejemplos y su API completa, en la
[biblioteca de componentes](/pyzed/es/library/). Esta página se mantiene como resumen.
:::

## Capas

`ui.layer(base, overlay, on_dismiss=...)` dibuja `overlay` encima de la interfaz. Hacer clic
fuera envía `on_dismiss`. Si `overlay` es `None`, devuelve `base` sin cambios, así que puedes
escribir:

```python
def view(self):
    layout = ui.workspace(...)
    return ui.layer(layout, self.dialogo(), on_dismiss=self.cerrar, backdrop="#00000066")

def dialogo(self):
    if not self.confirmando:
        return None
    return ui.modal(...)
```

`align_x`, `align_y` y `offset` controlan dónde aparece el overlay (por defecto, centrado arriba
como una paleta de comandos).

## Modal

![Modal](../../../../assets/components/modal.png)

```python
ui.modal(
    ui.muted("Hay cambios sin guardar en main.py. ¿Quieres guardarlos antes de cerrar?"),
    title="¿Guardar cambios?",
    on_close=self.cerrar,
    footer=[
        ui.button("No guardar", self.descartar, variant="ghost"),
        ui.button("Cancelar", self.cerrar),
        ui.button("Guardar", self.guardar, variant="solid"),
    ],
    width=420,
)
```

## Paleta de comandos

![Paleta de comandos](../../../../assets/components/palette.png)

```python
class App(pz.App):
    def __init__(self):
        self.palette_open = False
        self.query = ""
        self.selected = 0

    def commands(self):
        return [
            ui.PaletteItem("editor: toggle soft wrap", self.toggle_wrap, keys="alt-z"),
            ui.PaletteItem("theme selector: toggle", self.toggle_theme, keys="ctrl-k ctrl-t"),
            ui.PaletteItem("workspace: toggle left dock", self.toggle_left, keys="ctrl-b"),
        ]

    def on_key(self, combo):
        if combo == "ctrl-shift-p":
            self.palette_open, self.query, self.selected = True, "", 0
            return Command.focus("command-palette")
        if self.palette_open and combo == "escape":
            self.palette_open = False
        elif self.palette_open and combo in ("up", "down"):
            self.selected += 1 if combo == "down" else -1

    def run_selected(self):
        matches = ui.fuzzy_filter(self.query, self.commands(), key=lambda c: c.label)
        if matches:
            self.palette_open = False
            command = matches[self.selected % len(matches)][0]
            return command.on_press()

    def view(self):
        layout = ...
        palette = None
        if self.palette_open:
            palette = ui.command_palette(self.query, lambda q: setattr(self, "query", q), self.commands(),
                                         selected=self.selected, on_submit=self.run_selected)
        return ui.layer(layout, palette, on_dismiss=lambda: setattr(self, "palette_open", False))
```

Enter (`on_submit`) ejecuta el comando resaltado; las flechas cambian `selected`.

## Picker y búsqueda difusa

![Picker con coincidencias difusas](../../../../assets/components/picker.png)

`command_palette` está construida sobre `picker` y `fuzzy_filter`. Úsalos para tus propios
buscadores (archivos, símbolos, ramas…):

```python
matches = ui.fuzzy_filter(self.query, self.archivos)            # [(archivo, posiciones), ...]
items = [(ui.PaletteItem(Path(f).name, lambda f=f: self.abrir(f), icon="file", detail=f), pos)
         for f, pos in matches[:50]]
ui.picker(self.query, self.set_query, items, selected=self.sel, placeholder="Buscar archivos…")
```

`fuzzy_match(query, texto)` devuelve `(puntuación, posiciones)` o `None`, y `highlighted()`
dibuja un texto con las coincidencias resaltadas.

## Notificaciones

![Notificaciones](../../../../assets/components/toasts.png)

```python
ui.toast("Guardado", "main.py se guardó correctamente.", kind="success", on_dismiss=self.cerrar_aviso)
ui.toast("Actualización disponible", "Pyzed 0.2 ya está en PyPI.", kind="info",
         actions=[ui.button("Ver novedades", self.novedades, size="sm")])
```

`ui.toasts(base, items)` las apila en la esquina inferior derecha. Para que desaparezcan solas,
usa un hilo y [`pz.post`](/pyzed/es/guides/commands/#mensajes-desde-otros-hilos):

```python
def avisar(self, titulo):
    self.avisos.append(titulo)
    threading.Timer(3, pz.post, args=(("quitar_aviso", titulo),)).start()
```

Referencia completa: [Overlays](/pyzed/es/reference/ui/#overlays).
