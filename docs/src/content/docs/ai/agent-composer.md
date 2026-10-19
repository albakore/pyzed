---
title: Agent composer in Pyzed Design
description: "The AI agent built into Pyzed Design: a Zed-like composer with permission modes, model picker, effort, @ context and / commands that builds forms and components and writes their Python code."
sidebar:
  order: 2
---

Pyzed Design, the visual designer, has an AI agent in its right dock. You describe a screen in words and the agent
places the controls, wires the events, writes the Python handlers, creates new forms and components, and checks
its own code. Every change it makes to the open form is an ordinary undo step, and **Reject** puts back everything
a run touched.

![The agent added a switch and wired its event](../../../../screenshots/designer-agent.png)

The full manual of the panel is in [Pyzed Design → AI agents](/pyzed/editor/ai-agents/). This page is a tour of
the composer and of how to get good results from it.

## The composer

The message box at the bottom of the panel is modelled on Zed's agent composer:

| Part | What it does |
| --- | --- |
| **Message** | <kbd>Enter</kbd> sends. While the agent works, the send button becomes **Stop**. |
| **@ context** | Type <kbd>@</kbd> (or click **+**) to attach the **selection**, the open **form**, its **code**, one **control** or a **file** of the project. What you pick goes with the message, so the agent doesn't have to search for it. Files that may hold secrets (`.env`, keys) are never offered. |
| **/ commands** | `/new`, `/history`, `/settings`, `/form`, `/component`, `/explain`, `/fix` and `/tidy`. `/fix` runs `validate_code` on the form's code and fixes what it finds; `/tidy` aligns the controls and evens out the margins. |
| **Permission mode** | **Ask before writing** (the default: edits the form freely, asks before creating or writing files), **Bypass permissions**, **Read only** or **Chat only**. |
| **Model** | Every provider and its models. A provider that is not set up shows **Connect…**, which signs in right there. |
| **Effort** and **Fast** | How much the model thinks before answering, and fast mode, on the models that support them. |
| **Expand** | The panel fills the window for long conversations; click again to dock it. |

![Adding context with @](../../../../screenshots/designer-agent-mention.png)

## Connecting a model

The first time, the panel lists the main providers. Click one to sign in: Pyzed opens the provider's API keys page,
notices the key when you copy it, checks it and saves it in the **system keychain** (never in a settings file or in
the project). OpenRouter signs in with OAuth. Local models through **Ollama** or **LM Studio** need nothing, and any
**OpenAI-compatible** server (vLLM, llama.cpp, a company gateway) works with its URL.

![Every provider in the model picker](../../../../screenshots/designer-agent-models.png)

## What the agent can touch

The agent works through tools, the same way an MCP client uses the [MCP server](/pyzed/ai/mcp/):

- **The open document**: read it, add, change, move and remove controls, set the form's title, size, theme and style,
  select controls so you can see them.
- **Code**: wire events, write one handler or the whole module (it must parse), validate it.
- **New documents**: create forms and components next to the open one and open them in tabs.
- **Knowledge**: components, icons, themes and these docs.
- **Project files**: list, read, search and write files, never outside the project folder and never secret files.

Each message carries a short note of where you are (the open document, the selected controls, the handler in the
code editor), so *"align these"* or *"validate this field"* mean what you are looking at.

## Inline assist

In the code editor, <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>I</kbd> (or the ✦ button) opens a bar over the code.
Describe the change and the model rewrites the handler or the file; **Undo** and **Keep** decide, and nothing is
applied to the form until you click **Apply**.

![Inline assist over a handler](../../../../screenshots/designer-agent-inline.png)

## Getting good results

- **Start from the screen, not the widgets.** *"A customer form: name, email, a country drop-down and Save / Cancel;
  Save validates the email and shows a toast"* gives the agent the goal and the rules at once.
- **Select, then ask.** Select a group of controls and say *"put these in a row with 8 px spacing"*.
- **Use @ for precision.** `@email_input` plus *"only accept company addresses"* leaves no doubt about which control.
- **Let it check itself.** Finish requests with *"then run /fix"*, or ask it to validate before it answers.
- **Keep rules in the settings.** *Rules* in the AI agents settings are added to every thread: *"Answer in
  Spanish"*, *"Name buttons with a `_button` suffix"*, *"Use the Gruvbox Dark theme"*.
- **Review, then keep.** After a run, the **Agent changes** bar offers **Keep** or **Reject** for the whole run.

## The same agent in your own app

The panel runs on `pyzed.agents`, which any Pyzed app can use: the same providers, keychain storage, tools written
as Python functions and streamed events. See [Building AI apps](/pyzed/ai/ai-apps/) and
[AI agents in your app](/pyzed/guides/agents/).
