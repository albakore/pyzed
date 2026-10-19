---
title: MCP server for AI agents
description: "Connect AI coding agents (Cursor, VS Code, Zed and other MCP clients) to Pyzed's MCP server so they know its API, generate and check GUI code."
sidebar:
  order: 16
---

Pyzed ships an [MCP](https://modelcontextprotocol.io) server. Connect it to your AI agent (Claude Code,
Claude Desktop, Cursor, VS Code, Zed...) and the agent stops guessing: it looks up the exact signature of
every widget and component, reads this documentation, follows Pyzed's best practices, generates apps,
components and designer forms, checks the code it writes and even looks at a screenshot of the result.

## Install

The server is an optional extra of the package (it needs Python 3.10 or newer):

```bash
pip install "pyzed-ui[mcp]"     # or: uv add "pyzed-ui[mcp]"
pyzed mcp                       # runs the server over stdio (python -m pyzed.mcp works too)
```

You rarely run it by hand: the agent starts it. With [uv](https://docs.astral.sh/uv/) the agent can run it
without installing anything first, using `uvx --from "pyzed-ui[mcp]" pyzed mcp`.

`pyzed mcp --transport streamable-http` serves it over HTTP on `127.0.0.1` instead. Any program on your computer can reach it there without signing in, so the `screenshot` tool, which runs the code it is given, is left out unless you add `--allow-code`.

## Connect your agent

### Claude Code

```bash
claude mcp add pyzed -- uvx --from "pyzed-ui[mcp]" pyzed mcp
```

Inside a Pyzed project created with `pyzed new`, use the project's own environment so the server sees the
same Pyzed version and your components: `claude mcp add pyzed -- uv run pyzed mcp`.

### Claude Desktop, Cursor and other clients

Most clients read a JSON file with the same shape (`claude_desktop_config.json`, `.cursor/mcp.json`...):

```json
{
  "mcpServers": {
    "pyzed": {
      "command": "uvx",
      "args": ["--from", "pyzed-ui[mcp]", "pyzed", "mcp"]
    }
  }
}
```

### VS Code

In `.vscode/mcp.json`:

```json
{
  "servers": {
    "pyzed": { "type": "stdio", "command": "uvx", "args": ["--from", "pyzed-ui[mcp]", "pyzed", "mcp"] }
  }
}
```

If Pyzed is already installed in an environment, `"command": "pyzed", "args": ["mcp"]` works everywhere.

## What the agent gets

### Tools

| Tool | What it does |
| --- | --- |
| `get_guide` | How Pyzed works (`"overview"`) and its rules (`"best-practices"`). |
| `list_components` | Every widget (`pz.*`), Zed-style component (`pz.ui.*`), designer toolbox type and `pz.Component` class, with a one-line summary. Filter by `kind`, `query` or `category`. |
| `describe_component` | The signature, documentation and parameters of one widget or component (`"pz.column"`, `"ui.button"`), or the props and events of a designer type (`"designer:button"`). |
| `search_icons` | Lucide icon names for `icon=` and `pz.icon`. |
| `list_themes` | The built-in themes and the color tokens styles accept (`"accent"`, `"panel"`...). |
| `list_docs`, `read_docs` | The pages of this documentation, in English or Spanish. |
| `list_examples`, `read_example` | The source of the example apps (a Zed-like editor, a to-do list, dialogs...). |
| `new_app` | A runnable `pz.App` script: a simple starting point or a Zed-like workspace. |
| `new_component` | A `pz.Component` skeleton with its props, state and events. |
| `new_form` | A visual-designer form: the `.pzform` layout and its handlers module. |
| `validate_code` | Checks code without running it: names that don't exist in `pz` or `pz.ui`, keyword arguments a function doesn't take, apps without `view()`, components without `render()`, side effects in `view()`, lambdas in loops that don't capture the loop variable, and ruff's pyflakes checks when ruff is installed. |
| `validate_form` | Checks a `.pzform` (types, props, events, names, containers) and that its handlers module defines every handler. |
| `screenshot` | Renders the code off-screen (no window, no GPU) and returns a PNG, so the agent can see what it built. |

### Resources and prompts

Clients that support resources can attach `pyzed://guide`, `pyzed://best-practices`,
`pyzed://components`, `pyzed://themes`, `pyzed://docs`, `pyzed://component/{name}` and
`pyzed://docs/{slug}` (with `--` instead of `/`, such as `guides--layout`).

The prompts `create_app`, `create_component` and `create_form` start a task with the right steps:
read the guides, look up existing components, generate, validate and preview.

## Example session

> Make a Pyzed component that shows a rating with stars and lets the user change it.

A typical agent run with the server connected:

1. `get_guide("best-practices")`, then `list_components(query="rating")` to check nothing similar exists.
2. `new_component("star rating", props=[{"name": "value", "type": "int", "default": 0}], events={"change": "A star was picked."}, icon="star")`.
3. Fills in `render()` with `pz.row`, `pz.text(...).on(click=...)` and `self.emit("change", i)`, looking up
   `describe_component("pz.text")` for the parameters.
4. `validate_code(code)` and `screenshot(code + "def preview():\n    return StarRating(value=3)")` to see it.

## How it works

The server lives in the package (`pyzed.mcp`), so what it knows always matches the installed version:
signatures and docstrings come from the code itself, the descriptions from this reference and the
designer's toolbox from its registry, including your own `pz.Component` classes. Documentation pages and
examples are read from a source checkout when there is one, and otherwise downloaded from GitHub at the
installed version's tag.

`screenshot` runs the code in a separate process with a 60 second limit and replaces `pz.run`, so no
window opens. It uses the same off-screen renderer as [tests and screenshots](/pyzed/guides/testing/).

`pyzed.mcp.knowledge`, `pyzed.mcp.scaffold` and `pyzed.mcp.validate` are plain Python and work without the
MCP SDK, for example from your own scripts or tests.

## More on AI agents

The [AI agents](/pyzed/ai/) section collects everything else: [prompting guide](/pyzed/ai/prompting/) with a real
MCP session, [llms.txt and editor rules](/pyzed/ai/llms-txt/) with `AGENTS.md`, Cursor and Copilot templates, and
[Building AI apps](/pyzed/ai/ai-apps/).
