# AGENTS.md

This is a desktop app written with Pyzed (a Python UI rendered by Iced in Rust, with themed components that look
like the Zed editor). Instructions for the AI coding agents working on it.

- Docs: https://albakore.github.io/pyzed/llms-small.txt (everything: /pyzed/llms-full.txt).
- If the `pyzed` MCP server is available (`pyzed mcp`), use its tools instead of guessing APIs:
  `plan_app`, `describe_component`, `validate_code`, `review_design`, `screenshot_project`.
- Design rules: https://albakore.github.io/pyzed/ai/design.md (MCP: `get_guide("design")`).
- Architecture rules: https://albakore.github.io/pyzed/ai/app-architecture.md (MCP: `get_guide("app-architecture")`).

## Commands

- Run: `uv run pyzed run` (the startup file: the main form, or `script` in `[tool.pyzed]`) or
  `uv run pyzed dev main.py` (a script, with hot reload)
- Edit forms visually: `uv run pyzed design`
- Check (ruff + ty): `uv run pyzed check`
- Tests: `uv run pytest -q`
- Add a library: `uv run pyzed add <name>`
- Look at it in both themes: `uv run pyzed record shot ui/main.pzform --theme "Pyzed Dark,Pyzed Light"`
- Package: `uv run pyzed build`

## Where things go

- {backend}: models, rules and stores in plain Python. Never import pyzed here.
- Databases, HTTP and files: adapters behind `typing.Protocol` ports, created once in the composition root.
- `ui/`: forms (`.pzform` + handlers `.py`), components (`.pzcomp` or `pz.Component`), views and the
  `pz.stylesheet`. Handlers are thin: they read controls, call the package and write the result back.
- `tests/`: the package first (no window), then screens with `app.screenshot(path)`.

## How the code works

- An app is a `pz.App`: state on `self` (set in `__init__`), `view()` returns widgets from that state, events
  call methods or send typed messages to `update(message)`.
- `view()` and `render()` run after every event: no I/O, no sleeps, no state changes.
- Slow work never blocks the UI: return a coroutine, use `pz.Command.perform(function, then)` or `pz.Worker`;
  results come back as messages and only the UI thread changes state.
- Prefer `pyzed.ui` components; look parameters up instead of inventing them. Icons are Lucide names.
- Lambdas in loops capture the variable: `lambda item=item: self.open(item)`.
- Drag and drop uses `pz.sortable` (lists, boards, grids), `pz.draggable` / `pz.droppable` and
  `pz.drag_handle`; the handler applies the drop with `pz.dnd.move(lists, event)`. Never rebuild it from mouse events.
- Settings in `pz.Settings`, secrets in the keychain or environment variables, user-facing text through `pz.t`,
  `logging` instead of `print`.

## How the UI looks

- Each screen has one job and one primary action (`variant="solid"`); the rest is `"filled"` or `"ghost"`.
- One `ui.heading` per screen, body `ui.label`, secondary text `color="text_muted"`; sizes xs/sm/md/lg/xl/2xl.
- Spacing on a 4 px grid (4, 8, 12, 16, 24, 32); inner space smaller than outer space.
- Theme tokens only (`"panel"`, `"surface"`, `"text_muted"`, `"accent"`, `"error"`), never hex colors; it must work in
  Pyzed Dark and Pyzed Light.
- Every list and request has loading, empty (`ui.empty_state`) and error (`ui.callout(tint="error")`) states.
- Every input has a visible label (`ui.field`), every icon button a tooltip, every shortcut `keys=`.
- Sentence case; buttons say what they do ("Save changes", never "OK"); errors say how to fix them.

## Files that are not yours

- Do not delete the example form (`ui/main.pzform` and `ui/main.py`) or any file you did not create without
  asking: it may be open in Pyzed Design. An app written in code sets `script = "main.py"` in `[tool.pyzed]`
  so `uv run pyzed run` and Pyzed Design start from it.

## Before you finish

1. `uv run pyzed check` and `uv run pytest -q` pass.
2. `review_design` reports nothing on the views you changed.
3. Look at every screen you changed in both themes (`screenshot_project(..., theme="Pyzed Light")`).
