---
title: llms.txt y reglas para editores
description: "Da la documentación de Pyzed a cualquier LLM o IDE con IA: llms.txt, llms-full.txt, páginas en Markdown, y plantillas listas de AGENTS.md, reglas de Cursor e instrucciones de Copilot para proyectos Pyzed."
sidebar:
  order: 3
---

No todos los agentes hablan MCP, y a veces solo quieres pegar la documentación en un chat. Este sitio se publica
también como texto plano para modelos de lenguaje, siguiendo la convención [llms.txt](https://llmstxt.org), y esta
página tiene archivos de instrucciones listos que enseñan a cualquier editor con IA a escribir Pyzed.

## La documentación como texto

| URL | Qué contiene | Para |
| --- | --- | --- |
| [`/pyzed/es/llms.txt`](/pyzed/es/llms.txt) | Un índice: cada página con su título, enlace y resumen de una línea. | Que un agente elija qué leer. |
| [`/pyzed/es/llms-full.txt`](/pyzed/es/llms-full.txt) | Toda la documentación en español en un archivo. | Indexarla en un IDE con IA o en modelos de contexto largo. |
| `/pyzed/es/<página>.md` | Cualquier página en Markdown: [`/pyzed/es/guides/layout.md`](/pyzed/es/guides/layout.md). | Enlazar una página desde un prompt o una regla. |
| [`/pyzed/llms.txt`](/pyzed/llms.txt), [`/pyzed/llms-small.txt`](/pyzed/llms-small.txt), [`/pyzed/llms-full.txt`](/pyzed/llms-full.txt) | Lo mismo en inglés; `llms-small.txt` tiene lo esencial (primeros pasos, tutoriales, guías, IA y preguntas frecuentes). | Modelos que trabajan mejor en inglés o con poco contexto. |
| `/pyzed/llms/<sección>.txt` | Una sección en inglés, como [`guides`](/pyzed/llms/guides.txt), [`library`](/pyzed/llms/library.txt) o [`blocks`](/pyzed/llms/blocks.txt). | Solo lo que necesita una tarea. |

La dirección completa empieza por `https://albakore.github.io`, por ejemplo
`https://albakore.github.io/pyzed/es/llms-full.txt`. Todos se generan a partir de las mismas páginas que estás
leyendo, así que siempre coinciden con la versión actual.

## En tu editor con IA

- **Cursor**: *Settings → Indexing & Docs → Add doc* con `https://albakore.github.io/pyzed/llms-full.txt`, y
  menciónalo como `@Pyzed` en el chat. Añade la [regla de Cursor](#reglas-de-cursor) de abajo para todas las
  peticiones.
- **VS Code con Copilot**: añade el [archivo de instrucciones](#github-copilot) de abajo; en el chat, usa `#fetch`
  con una página como `https://albakore.github.io/pyzed/es/guides/async.md` cuando necesites sus detalles.
- **Zed**: `/fetch https://albakore.github.io/pyzed/llms-small.txt` en el panel del agente, y añade el
  [`AGENTS.md`](#agentsmd-para-un-proyecto-pyzed) al proyecto.
- **Un chat en el navegador**: adjunta o pega `llms-small.txt`, o dale el enlace al modelo si puede navegar.
- **Cualquier agente con MCP**: mejor el [servidor MCP](/pyzed/es/ai/mcp/). Lee las mismas páginas cuando las
  necesita y además valida código y hace capturas.

El paquete también incluye **stubs de tipos** (`pyzed/_core.pyi` y tipos en línea), así los editores y agentes que
leen tipos ven los parámetros de cada widget incluso sin la documentación.

## AGENTS.md para un proyecto Pyzed

Muchos agentes leen un `AGENTS.md` en la raíz del proyecto. Copia este; encaja con los proyectos de `pyzed new`.
Está en inglés porque los modelos siguen las instrucciones igual de bien y así sirve a todo el equipo, pero puedes
traducirlo.

```markdown
# AGENTS.md

This is a desktop app written with Pyzed (Python UI on Iced/Rust, styled like the Zed editor).
Docs: https://albakore.github.io/pyzed/llms-small.txt (all of it: /pyzed/llms-full.txt).
If the `pyzed` MCP server is available, use its tools instead of guessing APIs.

## Commands
- Run with hot reload: `uv run pyzed dev main.py`
- Check (ruff + types): `uv run pyzed check`
- Tests: `uv run pytest -q`
- Package: `uv run pyzed build`

## How Pyzed apps work
- An app is a `pz.App` subclass. State lives on `self` (set in `__init__`), `view()` returns widgets,
  events call methods or send messages to `update(message)`.
- `view()` runs after every event: no I/O, no sleeps, no state changes inside it.
- Slow work: return a coroutine (`async def`) or an async generator from a callback or `update`;
  each result or yielded value goes back to `update`. Timers and streams go in `subscriptions()`
  (`pz.every`, `pz.listen`).
- Effects (focus, scroll, clipboard, windows) are `pz.Command`s returned from callbacks.

## Rules
- Prefer `pyzed.ui` components (`ui.button`, `ui.input`, `ui.table`, `ui.card`...) over raw `pz.*` widgets.
- Look up signatures (MCP `describe_component`, or the docs) before using a component. Never invent parameters.
- Colors: use theme tokens (`"accent"`, `"panel"`, `"text_muted"`, `"border"`) so light and dark both work.
  `pz.container(bg=...)` takes real colors; use `.style(background="panel")` for tokens.
- Icons are Lucide names (`pyzed icons` lists them).
- Lambdas in loops capture the variable: `lambda item=item: self.open(item)`.
- Don't name app attributes after window options (`title`, `size`, `position`, `theme`, `style`...)
  unless you mean them.
- Reusable pieces with their own state: `pz.Component` with typed props, `pz.state()` and `events`.
- Call `pz.run(App)` once, under `if __name__ == "__main__":`.

## Before you finish
- Run `pyzed check` (or the MCP `validate_code` tool) and fix every issue.
- Smoke-test the UI off-screen: `App().screenshot("shot.png")` (or the MCP `screenshot` tool) and look at it.
```

## Reglas de Cursor

Guárdalo como `.cursor/rules/pyzed.mdc`. Se aplica a cada archivo Python y apunta Cursor a la documentación y al
`AGENTS.md` de arriba:

```markdown
---
description: Writing desktop UIs with Pyzed
globs: ["**/*.py", "**/*.pzform"]
alwaysApply: false
---

- This project uses Pyzed for its UI. Follow AGENTS.md at the repository root.
- Before using a Pyzed component, check its signature with the `pyzed` MCP tools
  (`describe_component`) or in https://albakore.github.io/pyzed/llms/library.txt.
- Build screens from `pyzed.ui` components; start from a block when one fits:
  https://albakore.github.io/pyzed/llms/blocks.txt
- After editing, run `validate_code` (MCP) or `uv run pyzed check`, and fix what it reports.
```

## GitHub Copilot

Guárdalo como `.github/copilot-instructions.md` (para todo el repositorio), o como
`.github/instructions/pyzed.instructions.md` con una cabecera `applyTo` para acotarlo:

```markdown
---
applyTo: "**/*.py"
---

This repository's UI is written with Pyzed (https://albakore.github.io/pyzed/).
Read https://albakore.github.io/pyzed/llms-small.txt for how Pyzed apps work, and follow AGENTS.md.

- `pz.App` subclasses hold state on `self`; `view()` only builds widgets from that state.
- Use `pyzed.ui` components and theme tokens ("accent", "panel", "text_muted").
- Long work goes in coroutines or async generators returned from callbacks; never block `view()`.
- Verify component parameters in https://albakore.github.io/pyzed/llms/library.txt instead of guessing.
```

## Un prompt de sistema para tu propio agente

¿Construyes un agente que escribe Pyzed (con `pyzed.agents` o cualquier SDK)? Dale la guía y las herramientas:

```python
from pyzed import agents
from pyzed.mcp import knowledge

system = knowledge.guide("overview") + "\n\n" + knowledge.guide("best-practices")
agent = agents.Agent(tools=agents.pyzed_tools(), system=system)
```

`agents.pyzed_tools()` le da al modelo las mismas consultas, generadores y comprobaciones que el servidor MCP.
