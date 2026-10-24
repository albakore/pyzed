---
title: "Reglas de arquitectura para agentes"
description: "Cómo estructurar apps grandes con Pyzed: estructura del proyecto, capas y puertos, estado y mensajes, componentes, efectos y servicios, errores, ajustes, tests y antipatrones."
sidebar:
  order: 3.4
---

<!-- Generated from python/pyzed/mcp/architecture.es.md by docs/scripts/gen_ai_guides.py: edit the guide, not this page. -->

:::tip
Los agentes de IA reciben esta página del servidor MCP con `get_guide("app-architecture")`. Sirve igual para personas.
:::

Cómo estructurar el código de Pyzed para que una app pueda crecer de una pantalla a un producto con muchas
pantallas, personas y años de cambios: la estructura del proyecto, las capas y la dirección de sus imports, el
estado y los mensajes, vistas y componentes, efectos y servicios, errores, ajustes, tests y herramientas.
Complementa a `get_guide("best-practices")` (las reglas de cada trozo de código) y a `get_guide("design")` (cómo
se ve).

## 1. Elige el tamaño de la estructura

| La app | Estructura |
| --- | --- |
| Una herramienta, una demo, una pantalla | `pyzed new mi_herramienta --script`: un `main.py` con un `pz.App`. Divide `view()` en métodos. |
| Una app real (varias pantallas, datos, tests) | `pyzed new mi_app`: un proyecto uv, la lógica en `src/<paquete>`, la interfaz en `ui/`, los tests en `tests/`. |
| Un producto (muchas funciones, un equipo) | El mismo proyecto uv, con un paquete por funcionalidad (abajo) y una CI que corre `pyzed check` y los tests. |

Empieza con la estructura más pequeña que sirva y sube cuando un archivo pase de ~400 líneas o trabaje en él una
segunda persona. Subir es barato si se respetan las capas desde el principio.

## 2. Las capas y la regla de dependencias

```
ui/            vistas, componentes, formularios, estilos  →  importa app y domain, y pyzed
src/<pkg>/app  casos de uso y stores (estado + acciones)   →  importa domain y los puertos
src/<pkg>/domain  modelos y reglas, Python puro           →  no importa nada de la app, nunca pyzed
src/<pkg>/adapters  base de datos, HTTP, archivos, SO      →  implementan los puertos, solo se importan al arrancar
```

- **Las dependencias apuntan hacia dentro.** El dominio no sabe nada de Pyzed, bases de datos ni HTTP; la
  interfaz conoce la capa de aplicación pero nunca habla directamente con una base de datos o una API.
  `grep pyzed src/<pkg>/domain` debe salir vacío.
- **Puertos y adaptadores**: la capa de aplicación declara lo que necesita como un `typing.Protocol`
  (`class InvoiceRepository(Protocol): def list(self) -> list[Invoice]: ...`) y los adaptadores lo implementan
  (`SqlInvoiceRepository`, `HttpInvoiceRepository`, `MemoryInvoiceRepository` para tests y vistas previas).
- **Una sola raíz de composición**: `main.py` (o el `__init__` de la app) construye los adaptadores y los stores y
  se los pasa a la interfaz. Nadie más crea una sesión de base de datos o un cliente HTTP.
- Eso permite que el mismo código corra detrás de una ventana, una CLI, un servidor FastAPI o un test
  (`get_guide("architectures")` muestra las cuatro formas de convivir con un backend).

Estructura de un producto:

```
mi_app/
├── pyproject.toml            # proyecto uv + [tool.pyzed] (ui, main, script, rendering)
├── main.py                   # raíz de composición: crea adaptadores y stores, luego pz.run(App)
├── src/mi_app/
│   ├── domain/               # dataclasses, enums, reglas, errores — sin E/S
│   ├── app/                  # stores y casos de uso por funcionalidad: invoices.py, customers.py
│   ├── ports.py              # Protocols que necesita la capa de aplicación
│   └── adapters/             # sqlite.py, api_client.py, files.py
├── ui/
│   ├── app.py                # el pz.App: ventana, navegación entre pantallas, atajos globales
│   ├── styles.py             # el pz.stylesheet de toda la app (clases, @media)
│   ├── components/           # clases pz.Component compartidas (Toolbar, MoneyLabel...)
│   ├── invoices/             # una carpeta por funcionalidad: funciones de vista, sus componentes, sus formularios
│   └── *.pzform / *.pzcomp   # documentos del diseñador, si la app los usa
├── locales/                  # catálogos de pz.t() (en.json, es.json)
└── tests/                    # dominio, stores, luego vistas (capturas)
```

## 3. Estado y mensajes

- **Un dueño por cada trozo de estado.** Los datos del dominio viven en un store de la capa de aplicación
  (`InvoiceStore`: la lista, la selección, el filtro, y métodos que los cambian). El estado puramente visual (un
  popover abierto, la fila bajo el puntero, un texto a medio escribir) vive en el componente o la app que lo
  muestra.
- **Deriva, no dupliques**: `visible = store.filtered()` calculado cuando hace falta, nunca una segunda lista que
  se sincroniza a mano. Cachea una derivación cara con `functools.lru_cache` sobre entradas inmutables o con
  `@pz.memo` para un subárbol.
- **Cambia el estado con métodos** de nombre claro (`store.archive(invoice_id)`), no asignando campos desde la
  interfaz. El método aplica las reglas; la interfaz solo pide.
- **Mensajes para todo lo que no sea trivial**: las apps pequeñas pasan callables (`ui.button("Save", self.save)`);
  las grandes envían mensajes tipados, dataclasses congeladas que maneja un único `update` con `match`. Son
  explícitos, se pueden registrar, probar y reproducir.

```python
@dataclass(frozen=True)
class Archive:
    invoice_id: str

def update(self, message):
    match message:
        case Archive(invoice_id):
            self.store.archive(invoice_id)
        case Saved():
            self.toasts.append(...)
```

- Mantén `update` como un despachador: cada rama llama a un método del store o devuelve un efecto. Divídelo por
  funcionalidad (`self.invoices.update(msg)`) cuando ocupe más de una pantalla.
- El estado cambia **solo en el hilo de la interfaz**: el trabajo en segundo plano devuelve su resultado como
  mensaje (sección 5).

## 4. Vistas y componentes

- `view()` es una función pura del estado: sin E/S, sin cambios de estado, sin esperas (`validate_code` avisa).
- **Compón funciones pequeñas**: `view()` llama a `self.toolbar()`, `self.sidebar()`, `self.content()`; las piezas
  reutilizables son funciones de módulo que reciben datos y callbacks y devuelven widgets, como hace `pz.ui`.
- **`pz.Component` cuando una pieza tiene estado o eventos propios, o se reutiliza**: props tipadas (los datos
  entran), eventos (`self.emit("change", value)`, los datos salen), `pz.state()` para el estado privado, `key=` en
  listas. Props hacia abajo, eventos hacia arriba: un componente nunca toca la app ni un store.
- **Valores transversales por contexto**: el usuario actual, los servicios, el idioma o un flag van en
  `with pz.provide(services=self.services): ...` una vez y se leen con `pz.use_context("services")` donde hagan
  falta, en lugar de pasarlos por cada nivel.
- **Una hoja de estilos para la app** (`ui/styles.py`, importada una vez): clases con el nombre de lo que son
  (`.invoice-row`, `.page`, `.toolbar`), solo tokens del tema, reglas `@media` para ventanas estrechas. Los
  componentes llevan su propio aspecto en su `stylesheet` de clase (`&`). Nada de hex en línea ni estilos repetidos.
- **Formularios del diseñador**: la maquetación en el `.pzform`, los handlers finos. Un handler lee los controles,
  llama a la capa de aplicación y escribe el resultado; no contiene reglas de negocio.
- **Pantallas y navegación**: la app guarda `self.screen` (un Enum o una dataclass pequeña con parámetros) y
  `view()` elige la pantalla; cada pantalla es una función o un componente de su carpeta. Carga tarde las
  funcionalidades pesadas importando su módulo dentro de la rama que las muestra.
- **Aísla los fallos**: envuelve las regiones independientes (un panel de plugin, un gráfico con datos externos) en
  `ui.error_boundary(lambda: ...)` para que una parte rota nunca tumbe la ventana.

## 5. Efectos, async y servicios

- **Nunca bloquees el hilo de la interfaz.** Todo lo que pueda tardar más de ~50 ms (disco, red, bases de datos,
  parseo, imágenes) corre en otro sitio:

| Trabajo | Usa |
| --- | --- |
| Una librería async (httpx, aiosqlite, websockets) | Devuelve una corrutina desde un callback o `update`; su resultado va a `update`. |
| Una llamada bloqueante (sesión de SQLAlchemy, requests, una tarea de CPU) | `pz.Command.perform(function, then)`: corre en un hilo, `then(result)` en el hilo de la interfaz. |
| Trabajo largo con progreso y cancelación | `pz.Worker(work, on_progress=..., on_done=..., on_failed=...)`; `work` mira `worker.cancelled`. |
| Un flujo de valores (logs, sockets, una descarga) | Un generador (async) devuelto desde un callback, o `pz.listen` en `subscriptions()`. |
| Trabajo periódico | `pz.every(seconds, message)` en `subscriptions()`, o `pz.Timer`. |
| Procesos externos, archivos que cambian, portapapeles, notificaciones, bandeja | `pz.Process`, `pz.FileWatcher`, `pz.Clipboard`, `pz.Notification`, `pz.TrayIcon` (servicios: los eventos llegan al hilo de la interfaz). |

- El código en segundo plano **devuelve resultados**; no toca `self` ni widgets. Los resultados vuelven como
  mensajes y el hilo de la interfaz los aplica, así los cambios de estado están en un solo sitio y en orden.
- **Guarda el estado de cada petición** en el store (`idle | loading | ready | error`, más el error) para que la
  vista muestre los estados de carga, vacío y error de `get_guide("design")`.
- **Cancela e ignora resultados viejos**: da a cada petición un id o un contador de generación y descarta los
  resultados que lleguen después de una petición más nueva (escribir en un buscador) o con la pantalla cerrada.
- **Ciclo de vida**: crea los servicios en `__init__`, arráncalos en `on_start` (que puede devolver un comando o una
  corrutina), páralos y guarda los ajustes en `on_close`. Las suscripciones se recalculan desde el estado, así que
  un temporizador existe solo mientras `subscriptions()` lo devuelve.
- Los efectos sobre la ventana (foco, scroll, abrir una ventana, copiar) son `pz.Command` devueltos desde
  callbacks, `update` u `on_start`, nunca llamados desde `view()`.

## 6. Errores, logs y ajustes

- **Los errores esperados son valores**: el adaptador lanza un error de dominio (`InvoiceNotFound`,
  `OfflineError`), el store lo captura y lo guarda, y la vista muestra un mensaje que dice cómo recuperarse. Los
  errores inesperados se registran con su traceback y se muestran con `ui.error_card` (detalles copiables).
- **Registra con `logging`** (`logging.getLogger(__name__)`), nunca con `print`; configúralo una vez en la raíz de
  composición. Pyzed escribe los fallos nativos en `crash.log`, en su carpeta de configuración.
- **Ajustes**: las preferencias del usuario en `pz.Settings("mi_app", defaults={...})` (un JSON por usuario); las
  opciones del proyecto en `pyproject.toml`; los secretos en el llavero del sistema (`keyring`) o en variables de
  entorno — nunca en el código, en archivos de ajustes ni en el repositorio.
- **Textos**: cada texto que ve el usuario pasa por `pz.t("invoices.empty.title")` desde la primera pantalla, con
  `locales/en.json` y `locales/es.json` (`get_guide("i18n")`). Añadir un idioma después es un archivo, no reescribir.

## 7. Rendimiento a escala

- Listas y tablas largas: `ui.virtual_list` / `pz.virtual_column` (solo se construyen las filas visibles), nunca
  miles de widgets en un `pz.scrollable`.
- `@pz.memo` para subárboles caros cuyas entradas cambian poco; los datos inmutables (tuplas, dataclasses
  congeladas) abaratan memoizar y comparar.
- Pagina o transmite las consultas grandes; aplica debounce a los buscadores (un contador de generación + un
  `asyncio.sleep` corto en la corrutina).
- Mide antes de optimizar (`get_guide("performance")`); el renderizador en Rust es rápido, lo que suele costar es
  el trabajo de Python en `view()`.

## 8. Tests

Prueba las capas de dentro hacia fuera; la mayoría de los tests nunca abren una ventana:

1. **Dominio**: pytest sobre funciones y dataclasses.
2. **Stores y casos de uso**: créalos con adaptadores en memoria, llama a sus métodos (o envía mensajes a
   `update`) y comprueba el estado.
3. **La app**: créala con adaptadores falsos, llama a sus callbacks y a `update`, comprueba el store.
4. **Vistas**: prueba cada pantalla y estado con `app.screenshot(path)` (fuera de pantalla, sin GPU) y guarda
   imágenes de referencia de las importantes.

```python
def test_archiving_removes_it_from_the_open_list():
    store = InvoiceStore(MemoryInvoiceRepository([Invoice("1", "Acme", 10)]))
    store.archive("1")
    assert store.open() == []
```

Corre `pyzed check` (ruff + ty) y `pytest` en la CI en Linux, Windows y macOS; `pyzed build --workflow` escribe un
workflow que además empaqueta la app.

## 9. Calidad del código

- Anota los tipos de las funciones públicas, props y stores; `ty` (en `pyzed check`) detecta props y mensajes
  equivocados.
- Módulos pequeños con un solo motivo para cambiar; nombres del dominio ("factura", "cliente"), las mismas palabras
  que muestra la interfaz.
- Docstrings en componentes, sus props y eventos: el diseñador y las herramientas del MCP los muestran.
- Nada de singletons globales mutables: pasa las dependencias (en el constructor o con `pz.provide`).
- Dependencias solo con uv (`pyzed add httpx`, `uv.lock` en el repositorio); fija la versión de Python del
  proyecto.
- Versión y changelog desde el principio; empaqueta con `pyzed build`.

## 10. Antipatrones

| No | Sí |
| --- | --- |
| Consultas, lecturas de archivos o HTTP en `view()` o `render()` | Carga en `on_start`/callbacks con una corrutina o `Command.perform` y guarda el resultado en un store |
| Reglas de negocio dentro de handlers del diseñador o lambdas | Un método del store por acción; el handler lo llama |
| Cambiar `self` desde un hilo o una corrutina | Devuelve un mensaje y aplícalo en `update` |
| La misma lista guardada en dos sitios | Un dueño, vistas derivadas |
| Colores hex y tamaños en píxeles repetidos por las vistas | Tokens del tema y clases en `ui/styles.py` |
| Un `app.py` de 2 000 líneas | Carpetas por funcionalidad con vistas, componentes y stores |
| `print` de depuración en la app | `logging` configurado una vez |
| Secretos en el código o en `settings.json` | Llavero o variables de entorno |
| Capturar todas las excepciones en silencio | Errores de dominio mostrados con cómo recuperarse; los inesperados, registrados y mostrados con detalles |

## 11. Una app por capas en un archivo

Toda la estructura en miniatura: dominio, un puerto y un adaptador en memoria, un store, mensajes tipados, una raíz
de composición, vistas divididas por región y un componente. En un proyecto cada sección es su propio módulo.

```python
from dataclasses import dataclass, field, replace
from typing import List, Protocol

import pyzed as pz
from pyzed import ui


# -- domain (src/tasks/domain.py): pure Python, no pyzed --------------------------------------------------
@dataclass(frozen=True)
class Task:
    id: int
    title: str
    done: bool = False


# -- port and adapter (src/tasks/ports.py, adapters/memory.py) ---------------------------------------------
class TaskRepository(Protocol):
    def load(self) -> List[Task]: ...
    def save(self, tasks: List[Task]) -> None: ...


@dataclass
class MemoryTasks:
    tasks: List[Task] = field(default_factory=list)

    def load(self) -> List[Task]:
        return list(self.tasks)

    def save(self, tasks: List[Task]) -> None:
        self.tasks = list(tasks)


# -- application (src/tasks/app.py): state and actions, testable without a window -------------------------
class TaskStore:
    def __init__(self, repo: TaskRepository):
        self.repo = repo
        self.tasks = repo.load()
        self.filter = "open"            # "open" | "done" | "all"

    def visible(self) -> List[Task]:
        if self.filter == "all":
            return self.tasks
        return [t for t in self.tasks if t.done == (self.filter == "done")]

    def add(self, title: str) -> None:
        if title.strip():
            self.tasks.append(Task(max((t.id for t in self.tasks), default=0) + 1, title.strip()))
            self.repo.save(self.tasks)

    def toggle(self, task_id: int) -> None:
        self.tasks = [replace(t, done=not t.done) if t.id == task_id else t for t in self.tasks]
        self.repo.save(self.tasks)


# -- messages (ui/messages.py) -----------------------------------------------------------------------------
@dataclass(frozen=True)
class Toggle:
    task_id: int


@dataclass(frozen=True)
class Filter:
    value: str


# -- a reusable component (ui/components/task_row.py) -----------------------------------------------------
class TaskRow(pz.Component):
    """One task with its checkbox."""

    designer = False
    title: str = ""
    done: bool = False
    events = {"toggle": "The checkbox was clicked."}

    def render(self):
        return pz.box(
            ui.checkbox(self.done, lambda _: self.emit("toggle")),
            ui.label(self.title, color="text_muted" if self.done else "text"),
            display="flex", gap=8, align="center", padding=(6, 8), height="shrink",
        )


# -- the app (ui/app.py): wiring, routing and views split by region ---------------------------------------
class Tasks(pz.App):
    title = "Tasks"
    size = (480, 320)

    def __init__(self, store: "TaskStore | None" = None):
        self.store = store or TaskStore(MemoryTasks([Task(1, "Write the domain"), Task(2, "Test the store")]))
        self.draft = ""

    def update(self, message):
        match message:
            case Toggle(task_id):
                self.store.toggle(task_id)
            case Filter(value):
                self.store.filter = value

    def add(self):
        self.store.add(self.draft)
        self.draft = ""

    def header(self):
        return pz.box(
            ui.input(self.draft, lambda v: setattr(self, "draft", v), placeholder="Add a task", on_submit=self.add),
            ui.button("Add task", self.add, variant="solid"),
            display="flex", gap=8, height="shrink",
        )

    def tabs(self):
        return ui.segmented([("open", "Open"), ("done", "Done"), ("all", "All")], self.store.filter, lambda v: Filter(v))

    def items(self):
        tasks = self.store.visible()
        if not tasks:
            return ui.empty_state("Nothing here", "Tasks you add show up in this list.", icon="list-checks", size="sm")
        return pz.box(*[TaskRow(title=t.title, done=t.done, key=t.id, on_toggle=lambda _e, i=t.id: Toggle(i))
                        for t in tasks])

    def view(self):
        return pz.box(self.header(), self.tabs(), self.items(), gap=12, padding=20, height="fill")


# -- composition root (main.py) ----------------------------------------------------------------------------
if __name__ == "__main__":
    pz.run(Tasks)
```

Docs: `guides/architecture`, `guides/projects`, `guides/components`, `guides/async`, `guides/services`,
`guides/testing`, `integrations/architectures`.
