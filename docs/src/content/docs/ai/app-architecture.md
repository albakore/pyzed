---
title: "Architecture rules for agents"
description: "How to structure large Pyzed apps: project layout, layers and ports, state and messages, components, effects and services, errors, settings, testing and anti-patterns."
sidebar:
  order: 3.4
---

<!-- Generated from python/pyzed/mcp/architecture.md by docs/scripts/gen_ai_guides.py: edit the guide, not this page. -->

:::tip
AI agents get this page from the MCP server with `get_guide("app-architecture")`. It is just as useful for people.
:::

How to structure Pyzed code so an app can grow from one screen to a product with many screens, people and
years of changes: the project layout, the layers and the direction of their imports, state and messages,
views and components, effects and services, errors, settings, tests and tooling. It complements
`get_guide("best-practices")` (the rules for each piece of code) and `get_guide("design")` (how it looks).

## 1. Pick the size of the structure

| The app | Structure |
| --- | --- |
| A tool, a demo, one screen | `pyzed new my_tool --script`: one `main.py` with a `pz.App`. Split `view()` into methods. |
| A real app (several screens, data, tests) | `pyzed new my_app`: a uv project, logic in `src/<package>`, UI in `ui/`, tests in `tests/`. |
| A product (many features, a team) | The same uv project, with one package per feature (below) and a CI that runs `pyzed check` and the tests. |

Start with the smallest structure that fits and move up when a file passes ~400 lines or a second
person works on it. Moving up is cheap when the layers below are respected from the start.

## 2. The layers and the dependency rule

```
ui/            views, components, forms, styles        →  imports app and domain, and pyzed
src/<pkg>/app  use cases and stores (state + actions)   →  imports domain and the ports
src/<pkg>/domain  models and rules, pure Python         →  imports nothing of the app, never pyzed
src/<pkg>/adapters  database, HTTP, files, OS           →  implement the ports, imported only at start-up
```

- **Dependencies point inwards.** The domain knows nothing about Pyzed, databases or HTTP; the UI knows the
  application layer but never talks to a database or an API directly. A `grep pyzed src/<pkg>/domain` must be empty.
- **Ports and adapters**: the application layer declares what it needs as a `typing.Protocol`
  (`class InvoiceRepository(Protocol): def list(self) -> list[Invoice]: ...`) and the adapters implement it
  (`SqlInvoiceRepository`, `HttpInvoiceRepository`, `MemoryInvoiceRepository` for tests and previews).
- **One composition root**: `main.py` (or the app's `__init__`) builds the adapters and the stores and hands
  them to the UI. Nothing else creates a database session or an HTTP client.
- This is what lets the same code run behind a window, a CLI, a FastAPI server or a test
  (`get_guide("architectures")` shows the four ways to live with a backend).

A product-sized layout:

```
my_app/
├── pyproject.toml            # uv project + [tool.pyzed] (ui, main, script, rendering)
├── main.py                   # composition root: builds adapters and stores, then pz.run(App)
├── src/my_app/
│   ├── domain/               # dataclasses, enums, rules, errors — no I/O
│   ├── app/                  # stores and use cases per feature: invoices.py, customers.py
│   ├── ports.py              # Protocols the app layer needs
│   └── adapters/             # sqlite.py, api_client.py, files.py
├── ui/
│   ├── app.py                # the pz.App: window, routing between screens, global shortcuts
│   ├── styles.py             # pz.stylesheet of the whole app (classes, @media)
│   ├── components/           # pz.Component classes shared by features (Toolbar, MoneyLabel...)
│   ├── invoices/             # one folder per feature: view functions, its components, its forms
│   └── *.pzform / *.pzcomp   # designer documents, if the app uses them
├── locales/                  # pz.t() catalogues (en.json, es.json)
└── tests/                    # domain, stores, then views (screenshots)
```

## 3. State and messages

- **One owner per piece of state.** Domain data lives in a store of the application layer
  (`InvoiceStore`: the list, the selection, the filter, and methods that change them). Pure UI state
  (a popover is open, the hovered row, a draft text) lives on the component or the app that shows it.
- **Derive, don't duplicate**: `visible = store.filtered()` computed when needed, never a second list kept in sync
  by hand. Cache an expensive derivation with `functools.lru_cache` on immutable inputs or `@pz.memo` for a
  subtree.
- **Change state through methods** with intention-revealing names (`store.archive(invoice_id)`), not by
  assigning fields from the UI. The method enforces the rules; the UI only asks.
- **Messages for anything non-trivial**: small apps pass callables (`ui.button("Save", self.save)`); bigger apps
  send typed messages, frozen dataclasses handled in one `update` with `match`. They are explicit, loggable,
  easy to test and to replay.

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

- Keep `update` a dispatcher: each branch calls one store method or returns one effect. Split it per feature
  (`self.invoices.update(msg)`) when it grows past a screen.
- State is changed **on the UI thread** only: background work returns its result as a message (section 5).

## 4. Views and components

- `view()` is a pure function of the state: no I/O, no state changes, no sleeps (`validate_code` warns).
- **Compose small functions**: `view()` calls `self.toolbar()`, `self.sidebar()`, `self.content()`; reusable
  pieces are module-level functions that take data and callbacks and return widgets, like `pz.ui` does.
- **`pz.Component` when a piece has its own state or events, or is reused**: typed props (data in), events
  (`self.emit("change", value)`, data out), `pz.state()` for private state, `key=` in lists. Props down, events
  up: a component never reaches into the app or a store.
- **Cross-cutting values through context**: the current user, the services, the locale or a feature flag go
  into `with pz.provide(services=self.services): ...` once and are read with `pz.use_context("services")`
  where needed, instead of passing them through every level.
- **One stylesheet for the app** (`ui/styles.py`, imported once): classes named after what things are
  (`.invoice-row`, `.page`, `.toolbar`), theme tokens only, `@media` rules for narrow windows. Components ship
  their own look in their class `stylesheet` (`&`). No inline hex colors, no repeated keyword styles.
- **Designer forms**: layout in the `.pzform`, handlers thin. A handler reads the controls, calls the
  application layer and writes the result back; it holds no business rules.
- **Screens and routing**: the app keeps `self.screen` (an Enum or a small dataclass with parameters) and
  `view()` picks the screen; each screen is a function or a component of its feature folder. Lazy-load heavy
  features by importing their module inside the branch that shows them.
- **Isolate failures**: wrap independent regions (a plugin panel, a chart from external data) in
  `ui.error_boundary(lambda: ...)` so one broken part never takes the window down.

## 5. Effects, async and services

- **Never block the UI thread.** Anything that can take more than ~50 ms (disk, network, databases,
  parsing, image processing) runs elsewhere:

| Work | Use |
| --- | --- |
| An async library (httpx, aiosqlite, websockets) | Return a coroutine from a callback or `update`; its result goes to `update`. |
| A blocking call (SQLAlchemy session, requests, a CPU task) | `pz.Command.perform(function, then)`: runs in a worker thread, `then(result)` on the UI thread. |
| Long work with progress and cancel | `pz.Worker(work, on_progress=..., on_done=..., on_failed=...)`; `work` checks `worker.cancelled`. |
| A stream of values (logs, sockets, a download) | An (async) generator returned from a callback, or `pz.listen` in `subscriptions()`. |
| Periodic work | `pz.every(seconds, message)` in `subscriptions()`, or `pz.Timer`. |
| External processes, files that change, the clipboard, notifications, the tray | `pz.Process`, `pz.FileWatcher`, `pz.Clipboard`, `pz.Notification`, `pz.TrayIcon` (services: events arrive on the UI thread). |

- Background code **returns results**; it doesn't touch `self` or widgets. Results come back as messages and the
  UI thread applies them, so state changes stay in one place and in order.
- **Track every request's state** in the store (`idle | loading | ready | error`, plus the error) so the view
  can show the loading, empty and error states of `get_guide("design")`.
- **Cancel and ignore stale results**: give each request an id or a generation counter and drop results that
  arrive after a newer request (typing in a search box), or after the screen closed.
- **Lifecycle**: create services in `__init__`, start them in `on_start` (which may return a command or a
  coroutine), stop them and flush settings in `on_close`. Subscriptions are recalculated from state, so a timer
  exists only while `subscriptions()` returns it.
- Effects that touch the window (focus, scroll, open a window, copy) are `pz.Command`s returned from callbacks,
  `update` or `on_start`, never called from `view()`.

## 6. Errors, logging and settings

- **Expected errors are values**: the adapter raises a domain error (`InvoiceNotFound`, `OfflineError`), the
  store catches it and records it, and the view shows a message that says how to recover. Unexpected errors are
  logged with the traceback and shown with `ui.error_card` (copyable details).
- **Log with `logging`** (`logging.getLogger(__name__)`), never with `print`; configure it once in the
  composition root. Pyzed writes native crashes to `crash.log` in its config folder.
- **Settings**: user preferences in `pz.Settings("my_app", defaults={...})` (a JSON file per user); project-wide
  options in `pyproject.toml`; secrets in the system keychain (`keyring`) or environment variables — never in code,
  settings files or the repository.
- **Text**: every string the user sees goes through `pz.t("invoices.empty.title")` from the first screen, with
  `locales/en.json` and `locales/es.json` (`get_guide("i18n")`). Adding a language later is then a file, not a
  rewrite.

## 7. Performance at scale

- Long lists and tables: `ui.virtual_list` / `pz.virtual_column` (only visible rows are built), never thousands
  of widgets in a `pz.scrollable`.
- `@pz.memo` for expensive subtrees whose inputs rarely change; immutable data (tuples, frozen dataclasses)
  makes memoization and comparison cheap.
- Paginate or stream big queries; debounce search inputs (a generation counter + a short `asyncio.sleep` in
  the coroutine).
- Measure before optimizing (`get_guide("performance")`); the Rust renderer is fast, Python work in `view()`
  is usually what costs.

## 8. Testing

Test the layers from the inside out; most tests never open a window:

1. **Domain**: plain pytest on functions and dataclasses.
2. **Stores and use cases**: build them with in-memory adapters, call methods (or send messages to `update`)
   and assert on the state.
3. **The app**: create it with fake adapters, call its callbacks and `update`, assert on the store.
4. **Views**: smoke-test every screen and state with `app.screenshot(path)` (off-screen, no GPU), and keep
   reference images for the important ones.

```python
def test_archiving_removes_it_from_the_open_list():
    store = InvoiceStore(MemoryInvoiceRepository([Invoice("1", "Acme", 10)]))
    store.archive("1")
    assert store.open() == []
```

Run `pyzed check` (ruff + ty) and `pytest` in CI on Linux, Windows and macOS; `pyzed build --workflow` writes a
workflow that also packages the app.

## 9. Code quality

- Type-annotate public functions, props and stores; `ty` (in `pyzed check`) catches wrong props and messages.
- Small modules with one reason to change; names from the domain ("invoice", "customer"), the same words the UI
  shows.
- Docstrings on components, their props and events: the designer and the MCP tools show them.
- No global mutable singletons: pass dependencies in (constructor or `pz.provide`).
- Dependencies through uv only (`pyzed add httpx`, `uv.lock` committed); pin the Python version of the project.
- Version and changelog from the start; package with `pyzed build`.

## 10. Anti-patterns

| Don't | Do |
| --- | --- |
| Queries, file reads or HTTP calls in `view()` or `render()` | Load in `on_start`/callbacks with a coroutine or `Command.perform`, keep the result in a store |
| Business rules inside designer handlers or lambdas | One store method per action; the handler calls it |
| Mutating `self` from a thread or a coroutine | Return a message; apply it in `update` |
| The same list kept in two places | One owner, derived views |
| Hex colors and pixel sizes repeated across views | Theme tokens and stylesheet classes in `ui/styles.py` |
| A 2 000-line `app.py` | Feature folders with views, components and stores |
| `print` debugging left in the app | `logging` configured once |
| Secrets in code or `settings.json` | Keychain or environment variables |
| Catching every exception silently | Domain errors shown with recovery; unexpected ones logged and shown with details |

## 11. A layered app in one file

The whole structure in miniature: domain, a port and an in-memory adapter, a store, typed messages, a
composition root, views split by region and a component. In a project each section is its own module.

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
