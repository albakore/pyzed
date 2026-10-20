---
title: Guía de prompts
description: "Cómo pedir a agentes de IA que construyan apps de escritorio con Pyzed, con un ejemplo completo: un agente crea un temporizador Pomodoro usando las herramientas MCP de Pyzed, con sus salidas reales."
sidebar:
  order: 4
---

Los agentes escriben mucho mejor código Pyzed cuando el prompt les da tres cosas: **para qué es la pantalla**,
**qué debe hacer** y **cómo comprobar el resultado**. Esta página tiene patrones de prompts que funcionan y una
sesión completa, con las salidas reales de las [herramientas MCP](/pyzed/es/ai/mcp/), de un agente construyendo una
app pequeña.

## Anatomía de un buen prompt

> Construye un **temporizador Pomodoro** como app Pyzed. *(qué)*
> Tiene modos Foco (25 min) y Descanso (5 min), una cuenta atrás grande, una barra de progreso, Empezar/Pausa y
> Reiniciar, y cuenta las sesiones terminadas. *(comportamiento)*
> Usa componentes de `pyzed.ui` y tokens del tema, y no pongas efectos secundarios en `view()`. *(restricciones)*
> Usa las herramientas MCP de pyzed: consulta firmas con `describe_component`, ejecuta `validate_code` y mira un
> `screenshot` antes de responder. *(cómo comprobar)*

| Incluye | Por qué |
| --- | --- |
| El propósito y quién lo usa | *"Una pantalla de ajustes para una app de notas"* da mejores decisiones que *"un formulario"*. |
| El comportamiento como lista | Cada punto se convierte en estado y un método; no se olvida nada. |
| Restricciones | Tema, tamaño de ventana, componentes a usar o evitar, versión de Python. |
| Un punto de partida | *"Parte del bloque de ajustes"* o *"sigue examples/todo.py"*. |
| La comprobación | La validación y una captura cierran el ciclo. Sin ellas el agente se queda en "debería funcionar". |

## Prompts que funcionan

**App nueva**
> Crea una app Pyzed para explorar una carpeta de notas Markdown: una lista con búsqueda a la izquierda, la nota
> renderizada a la derecha y Ctrl+N para una nota nueva. Lee primero las buenas prácticas con get_guide. Valídala
> y haz una captura.

**Desde un bloque**
> Parte del bloque de dashboard (`read_example("blocks/dashboard")`). Cambia los datos de ejemplo por cifras leídas
> de `ventas.csv` con el módulo csv, cargadas en una corrutina para que la ventana nunca se bloquee.

**Componente**
> Haz un `pz.Component` reutilizable llamado TagInput: un campo de texto que convierte palabras separadas por comas
> en chips que se pueden quitar. Props: `tags: list[str]`; evento `change` con la lista nueva. Muéstralo en una
> captura con `preview()`.

**Formulario del diseñador**
> Crea un formulario del diseñador "factura" con cliente, fecha, una tabla de líneas y un total; el total se
> actualiza cuando cambia una línea. Usa new_form y validate_form.

**Corregir**
> Esta lista no se desplaza y la ventana se congela mientras carga. Lee guides/layout y guides/async con read_docs,
> explica la causa y corrígela.

**Estilo**
> Haz que esta pantalla parezca el lanzador de un videojuego: tema oscuro con acento morado, un panel de vidrio
> sobre un degradado y un botón Jugar que brille. Mira los efectos en animation/effects.

## Qué evitar

- **"Usa código estilo tkinter"** o pegar código de otro toolkit: Pyzed no tiene `pack()`, `grid()` ni objetos de
  widget que mutar. Describe el comportamiento y deja que el agente lo escriba al estilo Pyzed.
- **Pedirlo todo a la vez** en una app grande. Construye la pantalla, compruébala y luego añade funciones: cada paso
  se valida y se mira.
- **Saltarse la comprobación.** Un agente que nunca ejecuta `validate_code` a veces inventa un parámetro; una
  llamada lo detecta.

## Un ejemplo completo

Lo que sigue es una sesión real con el servidor MCP de Pyzed (`python -m pyzed.mcp`), manejada por un cliente MCP.
Las salidas son exactamente lo que devolvieron las herramientas, acortadas donde se indica.

**El prompt:** *Construye un temporizador Pomodoro con modos Foco y Descanso, una barra de progreso,
Empezar/Pausa y Reiniciar. Usa las herramientas MCP de pyzed para comprobar lo que uses, valida el código y mira una
captura.*

### 1. Consultar los componentes

El agente necesita una barra de progreso, así que la busca:

```text
list_components(query="progress")
```

```json
[
  {"name": "pz.progress_bar", "kind": "widget", "category": "Controls", "summary": "A progress bar."},
  {"name": "ui.progress", "kind": "ui", "category": "Inputs",
   "summary": "A thin rounded progress bar filled to ``value`` out of ``max``, in the ``tint`` color."},
  {"name": "designer:progress", "kind": "designer", "category": "Display", "summary": "Shows how far a task has got."}
]
```

Prefiere el componente `ui` y pide su firma exacta:

```text
describe_component(name="ui.progress")
```

```json
{
  "name": "ui.progress",
  "signature": "ui.progress(value: 'float', *, max: 'float' = 1.0, tint: 'str' = 'accent', height: 'float' = 4, width: 'Any' = 'fill', theme: 'Optional[Theme]' = None) -> '_core.Widget'",
  "parameters": [
    {"name": "value", "required": true, "description": "Current value."},
    {"name": "max", "default": "1.0", "description": "Maximum value."},
    {"name": "height", "default": "4", "description": "Thickness."},
    "…"
  ],
  "docs": "https://albakore.github.io/pyzed/reference/ui/"
}
```

Y el nombre de un icono, porque los iconos son nombres de Lucide:

```text
search_icons(query="timer", limit=8)
```

```json
{"total": 3, "icons": ["timer", "timer-off", "timer-reset"]}
```

### 2. Un primer borrador y lo que dice el validador

El primer borrador tiene tres errores típicos del código generado: un atributo de clase mutable, un cambio de
estado dentro de `view()` y un argumento mal escrito.

```python
import pyzed as pz
from pyzed import ui


class Pomodoro(pz.App):
    title = "Pomodoro"
    size = (420, 360)
    tasks = []

    def __init__(self):
        self.left = 25 * 60
        self.running = False

    def subscriptions(self):
        return [pz.every(1, self.tick)] if self.running else []

    def tick(self):
        self.left -= 1

    def view(self):
        self.running = self.left > 0
        return pz.column([
            ui.heading(f"{self.left // 60:02d}:{self.left % 60:02d}"),
            ui.progress(1 - self.left / 1500, heigth=8),
            ui.button("Start", lambda: setattr(self, "running", True), icon="play"),
        ], spacing=16, padding=24)


pz.run(Pomodoro)
```

```text
validate_code(code=…)
```

```json
{
  "ok": false,
  "issues": [
    {"line": 8, "column": 5, "severity": "warning",
     "message": "mutable class attribute tasks on an App is shared state; initialize it in __init__"},
    {"line": 21, "column": 9, "severity": "warning",
     "message": "view() changes self.running; view() runs after every message and must not change state"},
    {"line": 24, "column": 47, "severity": "error",
     "message": "ui.progress() has no parameter 'heigth'; it takes: height, max, theme, tint, value, width"}
  ]
}
```

### 3. La app corregida

El agente corrige los tres problemas, añade los modos y el contador de sesiones, y vuelve a validar:

```json
{"ok": true, "issues": []}
```

```python title="examples/pomodoro.py"
"""A Pomodoro timer: the app built step by step in the AI prompting guide."""

import pyzed as pz
from pyzed import ui

WORK, BREAK = 25 * 60, 5 * 60


class Pomodoro(pz.App):
    title = "Pomodoro"
    size = (420, 380)

    def __init__(self):
        self.mode = "Focus"
        self.left = WORK
        self.running = False
        self.done = 0

    def subscriptions(self):
        return [pz.every(1, self.tick, key="timer")] if self.running else []

    def tick(self):
        self.left -= 1
        if self.left <= 0:
            if self.mode == "Focus":
                self.done += 1
            self.mode = "Break" if self.mode == "Focus" else "Focus"
            self.left = BREAK if self.mode == "Break" else WORK

    def switch(self, mode):
        self.mode, self.running = mode, False
        self.left = WORK if mode == "Focus" else BREAK

    def toggle(self):
        self.running = not self.running

    def reset(self):
        self.running, self.left = False, WORK if self.mode == "Focus" else BREAK

    def view(self):
        total = WORK if self.mode == "Focus" else BREAK
        return pz.center(pz.column([
            ui.segmented(["Focus", "Break"], self.mode, self.switch),
            pz.text(f"{self.left // 60:02d}:{self.left % 60:02d}", size=64, weight="bold"),
            ui.progress(1 - self.left / total, height=8, width=280),
            pz.row([
                ui.button("Pause" if self.running else "Start", self.toggle,
                          icon="pause" if self.running else "play", variant="solid", size="lg"),
                ui.icon_button("rotate-ccw", self.reset, tooltip="Reset"),
            ], spacing=8, align="center"),
            ui.muted(f"{self.done} sessions today", size="sm"),
        ], spacing=18, align="center")).style(background="editor")


if __name__ == "__main__":
    pz.run(Pomodoro)
```

### 4. Mirar el resultado

```text
screenshot(code=…, width=420, height=380, scale=2)
```

La herramienta renderizó la app sin pantalla y devolvió este PNG, que el agente revisa antes de responder:

![El temporizador Pomodoro renderizado por la herramienta screenshot](../../../../assets/ai/pomodoro.png)

Todo el ciclo (consultar, escribir, validar, mirar) llevó cinco llamadas a herramientas. La app está en el
repositorio como [`examples/pomodoro.py`](https://github.com/albakore/pyzed/blob/main/examples/pomodoro.py) y se
ejecuta con `python examples/pomodoro.py`.

## Reproducir la sesión

La sesión se puede ejecutar con el SDK de MCP para Python, útil para probar tus propios prompts o herramientas:

```python
import asyncio, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server = StdioServerParameters(command=sys.executable, args=["-m", "pyzed.mcp"])
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("describe_component", {"name": "ui.progress"})
        print(result.content[0].text)


asyncio.run(main())
```
