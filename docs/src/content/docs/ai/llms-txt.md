---
title: llms.txt and editor rules
description: "Feed the Pyzed docs to any LLM or AI IDE: llms.txt, llms-full.txt, Markdown pages, plus copy-ready AGENTS.md, Cursor rules and Copilot instructions for Pyzed projects."
sidebar:
  order: 3
---

Not every agent speaks MCP, and sometimes you just want to paste the docs into a chat. This site publishes itself
as plain text for language models, following the [llms.txt](https://llmstxt.org) convention, and this page has
ready-made instruction files that teach any AI editor how to write Pyzed.

## The docs as text

| URL | What it has | Use it for |
| --- | --- | --- |
| [`/pyzed/llms.txt`](/pyzed/llms.txt) | An index: every page with its title, link and one-line summary. | Letting an agent pick what to read. |
| [`/pyzed/llms-small.txt`](/pyzed/llms-small.txt) | The essentials in one file: getting started, tutorials, guides, AI and FAQ. | Pasting into a chat or a model with a small context. |
| [`/pyzed/llms-full.txt`](/pyzed/llms-full.txt) | The whole documentation in one file. | Indexing in an AI IDE, long-context models. |
| `/pyzed/llms/<section>.txt` | One section, such as [`guides`](/pyzed/llms/guides.txt), [`library`](/pyzed/llms/library.txt) or [`blocks`](/pyzed/llms/blocks.txt). | Just what a task needs. |
| `/pyzed/<page>.md` | Any page as Markdown: [`/pyzed/guides/layout.md`](/pyzed/guides/layout.md). | Linking one page from a prompt or a rule. |
| [`/pyzed/es/llms.txt`](/pyzed/es/llms.txt), [`/pyzed/es/llms-full.txt`](/pyzed/es/llms-full.txt) | The same in Spanish. | Working in Spanish. |

The full address starts with `https://albakore.github.io`, for example
`https://albakore.github.io/pyzed/llms-full.txt`. All of them are generated from the same pages you are reading,
so they always match the current release.

## In your AI editor

- **Cursor**: *Settings → Indexing & Docs → Add doc* with `https://albakore.github.io/pyzed/llms-full.txt`, then
  mention it as `@Pyzed` in a chat. Add the [Cursor rule](#cursor-rules) below for every request.
- **VS Code with Copilot**: add the [instructions file](#github-copilot) below; in a chat, `#fetch` a page such as
  `https://albakore.github.io/pyzed/guides/async.md` when you need its details.
- **Zed**: `/fetch https://albakore.github.io/pyzed/llms-small.txt` in the agent panel, and add the
  [`AGENTS.md`](#agentsmd-for-a-pyzed-project) to the project.
- **A chat in the browser**: attach or paste `llms-small.txt`, or give the model the link if it can browse.
- **Any agent with MCP**: prefer the [MCP server](/pyzed/ai/mcp/). It reads the same pages on demand and also
  validates code and takes screenshots.

The package also ships **type stubs** (`pyzed/_core.pyi` and inline types), so editors and agents that read types
see every widget's parameters even without the docs.

## AGENTS.md for a Pyzed project

Many agents read an `AGENTS.md` at the root of the project. `pyzed new` writes a complete one (commands, where
each layer goes, the design rules and the checks before finishing); for other projects, copy this one.

```markdown
# AGENTS.md

This is a desktop app written with Pyzed (Python UI on Iced/Rust, with ready-made themed components).
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

## Design (https://albakore.github.io/pyzed/ai/design.md)
- Each screen: one job, one primary action (`variant="solid"`), a known pattern (start from a block).
- Hierarchy: one `ui.heading`, body `ui.label`, secondary text `color="text_muted"`; sizes xs/sm/md/lg/xl/2xl only.
- Spacing on a 4 px grid (4, 8, 12, 16, 24, 32); inner space smaller than outer space.
- Theme tokens only, never hex; status colors only for status; check Pyzed Dark and Pyzed Light.
- Design the loading, empty (`ui.empty_state`), error (`ui.callout(tint="error")`) and ideal states.
- Visible label for every input (`ui.field`), tooltips on icon buttons, sentence case, verb + object labels.

## Architecture (https://albakore.github.io/pyzed/ai/app-architecture.md)
- Models, rules and stores in `src/<package>/` without pyzed; databases and APIs in adapters behind Protocols;
  views, components and the stylesheet in `ui/`; one composition root (`main.py`).
- One owner per piece of state; change it through store methods or typed messages handled in `update`.
- Background work returns results as messages; only the UI thread changes state.
- Settings in `pz.Settings`, secrets in the keychain or the environment, strings through `pz.t`, `logging` not `print`.

## Before you finish
- Run `pyzed check` (or the MCP `validate_code` tool) and fix every issue.
- Run the MCP `review_design` tool on each view and fix what it reports.
- Smoke-test the UI off-screen: `App().screenshot("shot.png")` (or the MCP `screenshot` tool, also with
  `theme="Pyzed Light"`) and look at it.
```

## Cursor rules

Save as `.cursor/rules/pyzed.mdc`. It applies to every Python file and points Cursor at the docs and the
`AGENTS.md` above:

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

Save as `.github/copilot-instructions.md` (repository-wide), or as
`.github/instructions/pyzed.instructions.md` with an `applyTo` header to scope it:

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

## A system prompt for your own agent

Building an agent that writes Pyzed (with `pyzed.agents` or any SDK)? Give it the guide and the tools:

```python
from pyzed import agents
from pyzed.mcp import knowledge

system = knowledge.guide("overview") + "\n\n" + knowledge.guide("best-practices")
agent = agents.Agent(tools=agents.pyzed_tools(), system=system)
```

`agents.pyzed_tools()` gives the model the same lookups, generators and checks as the MCP server.
