---
title: AI agents
description: The Agent panel of Pyzed Design - an AI agent that builds forms and components, writes their code and edits the open form, with inline assist in the code editor, several model providers and keys kept in the system keychain.
sidebar:
  order: 10.5
---

The **Agent** panel (right dock, next to Properties and Events) is an AI agent in the style of Zed's. Describe
what you want and it reads the open form, adds and arranges controls, wires events, writes the handlers, creates
new forms and components, and checks its own code. Every change it makes is an ordinary undo step, and you can
reject the whole run at once.

![The agent added a switch and wired its event](../../../../screenshots/designer-agent.png)

## Getting started

1. Open the panel: the **Agent** tab in the right dock, **View → Agent panel**, or <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>A</kbd>.
2. The first time, the panel asks you to **connect a model**. **Set up AI agents…** opens the
   [settings](#settings): paste an API key or click **Sign in with the browser**.
3. Type what you want and press <kbd>Enter</kbd>, or click one of the suggestions.

Claude needs the optional dependencies (`anthropic` and `keyring`); the compiled Pyzed Design already has them:

```bash
pip install "pyzed-ui[agents]"     # or: uv add "pyzed-ui[agents]"
```

![An empty thread with suggestions](../../../../screenshots/designer-agent-empty.png)

## The panel

| Part | What it does |
| --- | --- |
| **Header** | The thread's title, **New thread** (<kbd>+</kbd>), **History** and the agent's **settings**. |
| **Thread** | Your messages, the agent's answers (Markdown), its reasoning (**Thought**, folded) and one line per tool it used: a spinner while it runs, a check when it worked, a red cross when it failed. Click a line to see the tool's input and result. |
| **Agent changes** | After a run that changed something: **Reject** puts every form and code file it touched back as they were before the run; **Keep** hides the bar. Undo (<kbd>Ctrl</kbd>+<kbd>Z</kbd>) still steps back one change at a time. |
| **Message box** | <kbd>Enter</kbd> sends. While the agent works the send button becomes **Stop**. |
| **Model** | The model of this thread (and of new ones). Only providers that are set up are listed. |
| **Profile** | **Write**: may change the open form, its code and files in the project. **Ask**: reads only, answers and suggests code. **Minimal**: no tools, a plain chat. |

Each message carries a short note of where you are (the open document, the selected controls, the handler in the
code editor), so "align these" or "validate this field" refer to what you are looking at.

### What the agent can do

| Tool | Does |
| --- | --- |
| `get_document` | Reads the open form or component: settings, every control with its rect, props, events and style, the selection and the code. |
| `add_control`, `update_control`, `remove_controls` | Place, change, move into a container, rename and delete controls. Types and props are checked against the toolbox. |
| `set_form`, `select_controls` | Change the form's title, size, theme or style; select controls so you see them. |
| `wire_event`, `set_handler`, `set_code` | Connect events and write one handler or the whole module (it must parse). |
| `new_document`, `save_document` | Create a new form or component next to the open one and open it in a tab; save. |
| `list_components`, `describe_component`, `search_icons`, `list_themes`, `read_docs`… | The same knowledge as the [MCP server](/pyzed/guides/mcp/): components, icons, themes and this documentation. |
| `validate_code`, `validate_form` | Check code and forms before handing them back. |
| `list_files`, `read_file`, `search_text`, `write_file` | Work with files of the project, never outside its folder. |

Tools that **create or write files** ask first: a card shows **Allow**, **Always allow** (for the rest of the
session) and **Deny**. Turn **Ask before writing files** off in the settings to skip it. Changes to the open
document never ask, since they can be undone.

## Generating forms and components

**View → Generate a form with AI…** and **Generate a component with AI…** (also in the command palette) open the
panel with the start of the request written for you: finish the sentence and press <kbd>Enter</kbd>. For example:

> Create a new form for a customer: name, email, a country drop-down and Save / Cancel buttons; Save validates
> the email and shows a toast.

The agent creates `customer.pzform` and `customer.py`, opens them, places and aligns the controls, wires the
buttons and writes the handlers. With a component it creates the `.pzcomp` and its class, which then shows up
in the toolbox like any [component](/pyzed/editor/component-designer/).

## Inline assist

In the code editor, <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>I</kbd> (or the ✦ button in its header) opens a bar over
the code. Describe the change and press <kbd>Enter</kbd>: the model rewrites the handler (or the whole file, in
whole-file mode) and the editor shows the result. **Undo** puts the previous code back, **Keep** closes the bar.
Nothing is applied to the form until you click **Apply**, as with your own edits.

![Inline assist over a handler](../../../../screenshots/designer-agent-inline.png)

## Settings

**Settings → AI agents → AI agents settings…**, the gear in the panel header, or **AI agents settings…** in the
command palette.

![Providers, keys and the agent's options](../../../../screenshots/designer-agent-settings.png)

### Providers

| Provider | How to connect | Notes |
| --- | --- | --- |
| **Anthropic** | API key, `ANTHROPIC_API_KEY`, or **Sign in with the browser** | Sign-in runs the official Anthropic CLI (`ant auth login`); the CLI keeps the short-lived token in its own folder and Pyzed never sees it. Claude models stream their reasoning summaries and use adaptive thinking. |
| **OpenAI** | API key or `OPENAI_API_KEY` | |
| **Google Gemini** | AI Studio key or `GEMINI_API_KEY` | Through Gemini's OpenAI-compatible endpoint. |
| **OpenRouter** | **Sign in with the browser**, API key or `OPENROUTER_API_KEY` | Sign-in uses OAuth with PKCE: OpenRouter's page opens, and the key it issues for Pyzed goes to the keychain. |
| **Ollama**, **LM Studio** | Nothing: they run on your computer | Change the **Server URL** if they run elsewhere. |
| **OpenAI-compatible** | Server URL, and a key if the server needs one | vLLM, llama.cpp, Groq, Mistral, DeepSeek, a company gateway… |

Click a provider to open it: paste a key and **Save**, **Sign in with the browser**, **Get a key** (opens the
provider's key page), **Remove key** / **Sign out**, and **Refresh models**, which asks the provider for its list
of models so they show up in the model picker.

### Where keys are stored

Keys and tokens go to the **operating system's keychain**: Keychain on macOS, Credential Manager on Windows,
Secret Service (GNOME Keyring, KWallet) on Linux, under the service `pyzed`. They are never written to Pyzed's
settings files, to threads, or to the project. If no keychain is available, a key you paste is kept in memory until
the designer closes, and the settings say so; use an environment variable instead in that case.

The rest stays on your computer too: the settings in `agents.json` and the threads in `agents/threads/`, both in
[Pyzed's settings folder](/pyzed/editor/settings/#where-they-are-saved). Nothing is sent anywhere except the
requests to the provider you picked.

### Agent options

| Setting | What it does |
| --- | --- |
| **Default model** | The model new threads start with. |
| **Effort** | How much the model thinks before answering (`low` … `max`). Claude only; `high` by default. |
| **Ask before writing files** | Creating forms and components and saving files wait for your OK. On by default. |
| **Show thinking** | Shows the model's reasoning summaries in the thread. |
| **Rules** | Instructions added to every thread, like Zed's rules: "Answer in Spanish", "Name buttons with a `_button` suffix"… |

## History

**History** in the header lists your threads, newest first. Click one to continue it (the agent remembers the
whole conversation), or delete it. The last 200 threads are kept.

## Using agents in your own app

The agent is not tied to the designer: `pyzed.agents` gives any app the same providers, keychain storage and
agent loop. See [AI agents in your app](/pyzed/guides/agents/).
