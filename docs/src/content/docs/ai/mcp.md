---
title: MCP server
description: "Connect Cursor, VS Code, Zed, Claude Desktop or any MCP client to Pyzed: components, docs, code generators, validation and off-screen screenshots for AI agents."
sidebar:
  order: 1
---

`pyzed mcp` is a [Model Context Protocol](https://modelcontextprotocol.io) server that ships with Pyzed. It gives
an AI agent the same knowledge a Pyzed expert has, taken from the **installed version** of the package: every
component's signature and docs, the icons, the themes, this documentation, the examples and blocks, generators for
apps, components and forms, two validators, an off-screen renderer and project tools to build a whole app in a
folder.

This page is the short version. The [full MCP reference](/pyzed/guides/mcp/) lists every tool, resource and prompt.

## Connect your agent

Most MCP clients (Claude Desktop, Cursor, Windsurf and others) read a JSON file with this shape, such as
`.cursor/mcp.json` in your project:

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

VS Code reads `.vscode/mcp.json`:

```json
{
  "servers": {
    "pyzed": { "type": "stdio", "command": "uvx", "args": ["--from", "pyzed-ui[mcp]", "pyzed", "mcp"] }
  }
}
```

Zed and other editors take the same command and arguments in their own settings (Zed calls them *context
servers*).

:::tip[Use your project's environment]
Inside a project made with `pyzed new`, point the agent at the project's own environment, so the server sees the
same Pyzed version and **your own components**: `"command": "uv", "args": ["run", "pyzed", "mcp"]`. If Pyzed is
already installed, `"command": "pyzed", "args": ["mcp"]` works too.
:::

`uvx` runs the server without installing anything first; it needs [uv](https://docs.astral.sh/uv/). Without uv,
run `pip install "pyzed-ui[mcp]"` (Python 3.10 or newer) and use `pyzed mcp` as the command.

## What the agent can do

| Group | Tools | Use them to |
| --- | --- | --- |
| Learn | `get_guide`, `list_guides`, `list_docs`, `read_docs` | Read how Pyzed works, its rules, the cookbook of runnable recipes, topics such as games or shaders, and any page of these docs (English or Spanish). |
| Look up | `list_components`, `describe_component`, `search_reference`, `read_reference`, `search_icons`, `list_themes`, `editor_keymap` | Get exact signatures, parameters, icon names, color tokens and key bindings instead of guessing. |
| Reuse | `list_examples`, `read_example` | Read the examples, the [Blocks](/pyzed/blocks/) (`read_example("blocks/settings")`), games, showcase and backend integrations. |
| Generate | `new_app`, `new_component`, `new_form` | Start from correct skeletons: an app, a `pz.Component`, a visual-designer form. |
| Check | `validate_code`, `validate_form` | Catch unknown names, wrong keyword arguments, side effects in `view()` and broken forms before running. |
| See | `screenshot` | Render the app or a component off-screen and get a PNG back. |
| Plan | `plan_app` | Find the blocks, examples, components and guides an app needs, and the steps to build it. |
| Build | `project_info`, `create_project`, `list_files`, `read_file`, `write_files`, `add_dependency`, `check_project`, `run_tests`, `screenshot_project` | Create a project, write it, add libraries, check, test and look at it, in the folder the server runs in and the project's own environment. |
| Watch | `start_live_preview`, `live_preview_status`, `stop_live_preview` | Open the app in a window with hot reload, so you see it change as the agent writes each file. |

The prompts `create_app`, `create_component`, `create_form` and `build_project` (a whole app, end to end) start a task with the right steps, and resources
such as `pyzed://best-practices` and `pyzed://docs/{slug}` can be attached by clients that support them.

## Prompts that use the server well

- *"Use the pyzed MCP tools. Read the best practices first, then build..."*: agents follow instructions about
  their tools more reliably when you name them.
- *"Validate with validate_code and look at a screenshot before you answer."*: makes the agent close the loop.
- *"Start from the dashboard block."*: a tested screen is a better base than a blank file.
- *"Check describe_component for ui.table before using it."*: for components with many parameters.

More in the [prompting guide](/pyzed/ai/prompting/), including a full session with real tool outputs.

## Security

- Over **stdio** (the default) the server only talks to the agent that started it.
- `screenshot` **runs the code it is given** in a separate process with a 60 second limit and without opening a
  window. Treat it like running code yourself: agents normally ask before calling tools, keep that on for
  untrusted prompts.
- The project tools read and write files only inside the folder the server was started in (or `--root PATH`),
  never files that may hold secrets (`.env`, keys...), and run uv, ruff, ty and pytest there.
- `pyzed mcp --transport streamable-http` serves it on `127.0.0.1` without authentication; there `screenshot` and
  the project tools are off unless you add `--allow-code`.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| The agent lists no `pyzed` tools | Run the command from the config by hand (`uvx --from "pyzed-ui[mcp]" pyzed mcp`); it should wait silently for input. Check the client's MCP logs. |
| `ModuleNotFoundError: mcp` | Install the extra: `pip install "pyzed-ui[mcp]"`. Python 3.10+ is required. |
| The agent doesn't know your components | Run the server from your project's environment (`uv run pyzed mcp`), so it imports them. |
| Docs can't be read offline | Pages are read from a source checkout or downloaded from GitHub; offline, point the agent at a checkout or at the [Markdown pages](/pyzed/ai/llms-txt/). |
| Screenshots time out | The code must define a `pz.App` or a top-level `preview()`; long work in `__init__` hits the 60 second limit. |

## Without MCP

Every part of the server is plain Python, usable from scripts, tests or your own agent:

```python
from pyzed.mcp import knowledge, scaffold, validate

print(knowledge.describe_component("ui.progress")["signature"])
print(validate.check_code(open("main.py").read())["issues"])
print(scaffold.app("Notes", layout="workspace"))
```

Agents that can't use MCP at all can read the docs as text: see [llms.txt and editor rules](/pyzed/ai/llms-txt/).
