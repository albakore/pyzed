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
2. The first time, the panel asks you to **connect a model** and lists the main providers. Click one to
   [sign in with the browser](#signing-in), or **All providers…** for the rest.
3. Type what you want and press <kbd>Enter</kbd>, or click one of the suggestions.

Claude needs the optional dependencies (`anthropic` and `keyring`); the compiled Pyzed Design already has them:

```bash
pip install "pyzed-ui[agents]"     # or: uv add "pyzed-ui[agents]"
```

![An empty thread with suggestions](../../../../screenshots/designer-agent-empty.png)

### Signing in

Signing in happens inside Pyzed Design; no other program is needed.

- **Anthropic, OpenAI, Gemini, xAI, Mistral, DeepSeek, Groq**: these providers don't let other apps sign in
  with OAuth, so Pyzed opens the provider's API keys page in your browser. Create a key there and click its
  **Copy** button. Pyzed notices the copied key, checks it with the provider, saves it in the system keychain and
  loads the provider's models. While it waits, a **Signing in** card offers **Paste key** (read the clipboard
  now), **Open the page again** and **Cancel**. The clipboard is read only while that card is showing (at most
  five minutes), and only a text that looks like that provider's key is used.
- **OpenRouter**: real OAuth with PKCE. You approve Pyzed on OpenRouter's page and the key it issues comes back to
  Pyzed directly; nothing to copy.
- **Ollama, LM Studio**: nothing to sign in to. Clicking them asks the local server for its models.

You can always paste a key by hand in the [settings](#settings) or set the provider's environment variable.

![Signing in to Anthropic: the key page is open and Pyzed waits for the copied key](../../../../screenshots/designer-agent-connect.png)

## The panel

| Part | What it does |
| --- | --- |
| **Header** | The thread's title, **New thread** (<kbd>+</kbd>), **History**, **Expand the panel** (it fills the window; click again to put it back in its dock) and the agent's **settings**. |
| **Thread** | Your messages, the agent's answers (Markdown), its reasoning (**Thought**, folded) and one line per tool it used: a spinner while it runs, a check when it worked, a red cross when it failed. Click a line to see the tool's input and result. |
| **Agent changes** | After a run that changed something: **Reject** puts every form and code file it touched back as they were before the run; **Keep** hides the bar. Undo (<kbd>Ctrl</kbd>+<kbd>Z</kbd>) still steps back one change at a time. |
| **Message box** | <kbd>Enter</kbd> sends. Type <kbd>@</kbd> to [add context](#adding-context-with-) and <kbd>/</kbd> for [commands](#commands-with-). While the agent works the send button becomes **Stop**. |
| **+** | Starts an @ mention, like typing <kbd>@</kbd>. |
| **Permission mode** | What the agent may do without asking (see below). |
| **Model** | Every provider with its models. A provider that is not set up shows **Connect…**, which signs in right there. |
| **Effort** | How much the model thinks before answering: **Low**, **Medium**, **High**, **Extra high**, **Max**. Claude models only. |
| **Fast** | Fast mode: faster answers at a higher price, on Claude Opus 5.5 and Opus 5 through the Claude API. |

| Permission mode | What the agent may do |
| --- | --- |
| **Ask before writing** | Edits the open form and its code freely (every change can be undone); asks before creating documents or writing files. The default. |
| **Bypass permissions** | Never asks. |
| **Read only** | Reads only: answers questions and suggests code without changing anything. |
| **Chat only** | No tools: a plain conversation with the model. |

![Every provider in the model picker](../../../../screenshots/designer-agent-models.png)

Each message carries a short note of where you are (the open document, the selected controls, the handler in the
code editor), so "align these" or "validate this field" refer to what you are looking at.

### Adding context with @

Type <kbd>@</kbd> (or click **+**) and pick what to attach: the **selection**, the open **form**, its **code**,
one of its **controls**, or a **file** of the project. Keep typing to filter the list; <kbd>Enter</kbd> picks the
highlighted row. What you pick shows as a chip above the message and its content goes with the message, so the
agent doesn't have to look for it. Files that may hold secrets (`.env`, keys…) are never offered.

![Adding context with @](../../../../screenshots/designer-agent-mention.png)

### Commands with /

Type <kbd>/</kbd> at the start of the message:

| Command | Does |
| --- | --- |
| `/new` | Starts a new thread. |
| `/history` | Shows the past threads. |
| `/settings` | Opens the AI agents settings. |
| `/form`, `/component` | Starts a request to generate a form or a component. |
| `/explain` | Explains the open form and its handlers. |
| `/fix` | Checks the form's code with `validate_code` and fixes what it finds. |
| `/tidy` | Aligns the controls and evens out the margins. |

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

Tools that **create or write files** ask first in the **Ask before writing** mode: a card shows **Allow**,
**Always allow** (for the rest of the session) and **Deny**. **Bypass permissions** skips it. Changes to the open
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
| **Anthropic** | **Sign in with the browser**, API key or `ANTHROPIC_API_KEY` | Claude models stream their reasoning summaries, use adaptive thinking and take effort and fast mode. An existing Anthropic CLI profile (`ant auth login`) is also used, but the CLI is not needed. |
| **OpenAI** | **Sign in with the browser**, API key or `OPENAI_API_KEY` | |
| **Google Gemini** | **Sign in with the browser**, AI Studio key or `GEMINI_API_KEY` | Through Gemini's OpenAI-compatible endpoint. |
| **OpenRouter** | **Sign in with the browser** (OAuth), API key or `OPENROUTER_API_KEY` | OAuth with PKCE: the key OpenRouter issues for Pyzed goes to the keychain. |
| **xAI**, **Mistral**, **DeepSeek**, **Groq** | **Sign in with the browser**, API key or `XAI_API_KEY`, `MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `GROQ_API_KEY` | Their models are listed after signing in. |
| **Ollama**, **LM Studio** | Nothing: they run on your computer | Change the **Server URL** if they run elsewhere. |
| **OpenAI-compatible** | Server URL, and a key if the server needs one | vLLM, llama.cpp, a company gateway… |

Click a provider to open it: **Sign in with the browser** (see [Signing in](#signing-in)), paste a key and
**Save**, **Get a key** (opens the provider's key page), **Remove key**, and **Refresh models**, which asks the
provider for its list of models so they show up in the model picker.

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
| **Fast mode** | Faster answers at a higher price (Claude Opus 5.5 and Opus 5). Also in the message box. |
| **Ask before writing files** | Creating forms and components and saving files wait for your OK. On by default; the same as the **Ask before writing** / **Bypass permissions** modes. |
| **Show thinking** | Shows the model's reasoning summaries in the thread. |
| **Rules** | Instructions added to every thread, like Zed's rules: "Answer in Spanish", "Name buttons with a `_button` suffix"… |

## History

**History** in the header lists your threads, newest first. Click one to continue it (the agent remembers the
whole conversation), or delete it. The last 200 threads are kept.

## Using agents in your own app

The agent is not tied to the designer: `pyzed.agents` gives any app the same providers, keychain storage and
agent loop. See [AI agents in your app](/pyzed/guides/agents/).
