---
title: Diálogos y herramientas
description: Diálogos listos para usar, acordeones, una consola de logs, una lista de atajos, una ventana Acerca de y el selector de color.
sidebar:
  order: 11
---

:::tip[Biblioteca de componentes]
Cada componente tiene ahora su propia página, con vista previa, ejemplos y su API completa, en la
[biblioteca de componentes](/pyzed/es/library/). Esta página se mantiene como resumen.
:::

## Diálogos

![Un diálogo de confirmación y uno de texto](../../../../assets/components/dialogs.png)

Guarda en tu estado qué diálogo está abierto y envuelve la vista con `ui.dialog_layer`, que
oscurece la ventana, centra el diálogo y llama a `on_dismiss` al pulsar el fondo. Con
`dialog=None` devuelve la vista sin cambios, así que puede envolverla siempre.

```python
class Archivos(pz.App):
    def __init__(self):
        self.preguntando = False
        self.renombrando = None

    def view(self):
        dialogo = None
        if self.preguntando:
            dialogo = ui.confirm("¿Eliminar main.py? No se puede deshacer.", self.eliminar, self.cerrar_dialogo,
                                 title="Eliminar archivo", danger=True)
        elif self.renombrando is not None:
            dialogo = ui.prompt("Renombrar", self.renombrando, self.set_nombre, self.renombrar, self.cerrar_dialogo)
        return ui.dialog_layer(self.vista_principal(), dialogo, on_dismiss=self.cerrar_dialogo)
```

| Diálogo | Qué hace |
| --- | --- |
| `ui.alert(message, on_close, kind=)` | Un mensaje con un botón; `kind` (`"info"`, `"success"`, `"warning"`, `"error"`) añade un icono. |
| `ui.confirm(message, on_confirm, on_cancel, danger=)` | Una pregunta de sí o no; `danger=True` pinta de rojo el botón de confirmar. |
| `ui.prompt(title, value, on_input, on_submit, on_cancel)` | Pide una línea de texto; Enter o el botón la envían. |
| `ui.choice(message, [(label, on_press), ...], on_cancel)` | Tus propios botones; el último es el principal. |
| `ui.unsaved_changes(name, on_save, on_discard, on_cancel)` | "¿Guardar los cambios antes de cerrar?" |

Los textos de los botones se traducen con [`pyzed.i18n`](/pyzed/es/guides/i18n/). Para cualquier
otra cosa, `ui.modal(content, title=, footer=[...])` es la misma superficie con tu contenido.

## Acordeón

![Un acordeón con dos secciones abiertas](../../../../assets/components/accordion.png)

```python
ui.accordion(
    [("editor", "Editor", ajustes_editor), ("files", "Archivos", ajustes_archivos), ("git", "Git", ajustes_git)],
    open=self.secciones_abiertas,                  # un set de ids, un dict {id: bool} o True
    on_toggle=lambda clave: self.secciones_abiertas.symmetric_difference_update({clave}),
    icons={"editor": "file-code", "files": "folder", "git": "git-branch"},
)
```

Las secciones también pueden ser `ui.AccordionSection(key, title, content, icon=, end=)`, donde
`end` añade widgets a la derecha de la cabecera. Para un único bloque plegable usa
[`ui.disclosure`](/pyzed/es/components/controls/).

## Consola de logs

![Una consola de logs con cinco niveles](../../../../assets/components/console.png)

`ui.Log` reúne las entradas (seguro entre hilos, con límite y agrupando líneas repetidas) y
`ui.console` las muestra como la consola de las herramientas de desarrollo de un navegador: un
filtro, un interruptor por nivel con su recuento, copiar y limpiar.

```python
self.log = ui.Log(on_write=lambda: pz.post("log"))   # redibuja cuando llega una línea
self.log.write("warning", "no se encontró settings.json, se usan los valores por defecto")
self.log.capture()                                    # recoge también print() y stderr

ui.console(self.log.entries, query=self.filtro, on_query=self.set_filtro,
           hidden=self.ocultos, on_toggle_level=self.alternar_nivel,
           on_clear=self.log.clear, on_copy=lambda: pz.Command.copy(self.log.text()))
```

Los niveles son `info`, `event`, `stdout`, `stderr`, `warning` y `error` (`ui.LOG_LEVELS`).

## Atajos y Acerca de

| Atajos de teclado | Acerca de |
| --- | --- |
| ![Una lista de atajos con búsqueda](../../../../assets/components/shortcuts.png) | ![Una ventana Acerca de](../../../../assets/components/about.png) |

```python
ui.shortcuts([("Archivo", [("Guardar", "ctrl-s"), ("Abrir archivo", "ctrl-p")]),
              ("Ver", [("Paleta de comandos", "ctrl-shift-p")])],
             query=self.filtro, on_query=self.set_filtro)

ui.about("Notas", "1.2.0", "Una pequeña app de notas hecha con Pyzed.", icon="notebook-pen",
         details=[("Python", "3.12")], links=[("Web", lambda: webbrowser.open(URL))])
```

Los dos encajan bien dentro de un `ui.modal`.

## Selector de color

![El selector de color y muestras de color](../../../../assets/components/color-picker.png)

```python
ui.ColorPicker(value=self.relleno, on_change=lambda e: setattr(self, "relleno", e.value))
ui.color_swatch(self.relleno, size=24, on_press=self.abrir_selector)
```

`ui.ColorPicker` es un componente: elige un color con transparencia, un degradado lineal o un
relleno con máscara de opacidad, y `on_change` recibe un texto `"#rrggbb[aa]"`, un `pz.Gradient`
o un `pz.Paint`, todos válidos como `background`. `ui.color_swatch` muestra cualquiera de ellos
sobre un tablero de cuadros. Ver [Estilos](/pyzed/es/guides/styles/#selector-de-color).

Referencia completa: [Diálogos](/pyzed/es/reference/ui/#diálogos), [Consola y ayuda](/pyzed/es/reference/ui/#consola-y-ayuda)
y [Selector de color](/pyzed/es/reference/ui/#selector-de-color).
