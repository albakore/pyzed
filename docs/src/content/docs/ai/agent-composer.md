---
title: The agent in Pyzed Design
description: "The AI agent built into Pyzed Design at a glance: a Zed-like composer that builds forms, components and whole apps, sees images, uses MCP servers and external agents, and signs in to many model providers."
sidebar:
  order: 2
  label: Agent in Pyzed Design
---

Pyzed Design, the visual designer, has an AI agent in its right dock. You describe a screen in words and the agent
places the controls, wires the events, writes the Python handlers, creates new forms, components or a whole project,
looks at the result and checks its own code. Every change it makes to the open form is an ordinary undo step, and
**Reject** puts back everything a run touched.

![The agent added a switch and wired its event](../../../../screenshots/designer-agent.png)

This page is a summary. The complete manual, with every button, command and setting, is
[Pyzed Design → AI agents](/pyzed/editor/ai-agents/).

## At a glance

| Feature | What it does | Details |
| --- | --- | --- |
| **Composer** | A Zed-style message box: <kbd>@</kbd> attaches the selection, the form, its code, a control or a file; <kbd>/</kbd> runs commands such as `/app`, `/fix`, `/tidy` and `/look`. | [The panel](/pyzed/editor/ai-agents/#the-panel) |
| **Permission modes** | **Ask before writing** (the default), **Bypass permissions**, **Read only** and **Chat only**. Edits to the open form never ask, since they can be undone. | [Permission modes](/pyzed/editor/ai-agents/#the-panel) |
| **Many providers** | Anthropic, OpenAI, Gemini, Vertex AI, GitHub Copilot, OpenRouter, xAI, Mistral, DeepSeek, Groq, Ollama, LM Studio and any OpenAI-compatible server, with effort and fast mode on Claude. | [Providers](/pyzed/editor/ai-agents/#providers) |
| **Sign in** | Sign in with the browser (the copied key is picked up), OpenRouter OAuth, **Sign in with GitHub** (device flow) and **Sign in with Google** for Vertex AI. | [Signing in](/pyzed/editor/ai-agents/#signing-in) |
| **Claude without a key** | Workload identity federation exchanges your identity provider's token for a short-lived Claude token. | [Claude without an API key](/pyzed/editor/ai-agents/#claude-without-an-api-key) |
| **Images** | Attach or paste pictures, or a screenshot of the form; the agent also looks at the form itself with `screenshot_form`. | [Images](/pyzed/editor/ai-agents/#images) |
| **Whole apps** | `/app` creates a project, adds packages, writes forms and components, looks at them and runs the checks. | [Building an application](/pyzed/editor/ai-agents/#building-an-application) |
| **MCP servers** | Add the tools of any Model Context Protocol server (local command or URL); their secrets go to the keychain. | [MCP servers](/pyzed/editor/ai-agents/#mcp-servers) |
| **External agents** | Run Claude Code, Gemini CLI, Codex or any Agent Client Protocol agent inside the panel, sharing Pyzed's MCP server. | [External agents](/pyzed/editor/ai-agents/#external-agents) |
| **Inline assist** | <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>I</kbd> in the code editor rewrites a handler or the file in place. | [Inline assist](/pyzed/editor/ai-agents/#inline-assist) |
| **Credentials** | Keys and tokens live in the system keychain, never in settings or the project. | [API keys and credentials](/pyzed/ai/api-keys/) |

![Adding context with @](../../../../screenshots/designer-agent-mention.png)

## A first session

1. Open the panel: the **Agent** tab in the right dock, or <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>A</kbd>.
2. Connect a model: click a provider and sign in, or pick a local model. See
   [API keys and credentials](/pyzed/ai/api-keys/) for keys, environment variables and good practices.
3. Ask for a screen: *"A customer form: name, email, a country drop-down and Save / Cancel; Save validates the email
   and shows a toast"*. Then refine it: select controls and ask, attach a mock-up, or run `/look` and `/fix`.
4. Review the run with **Keep** or **Reject**, and press <kbd>F5</kbd> to run the form.

Tips for good prompts are in [Getting good results](/pyzed/editor/ai-agents/#getting-good-results) and the
[prompting guide](/pyzed/ai/prompting/).

## The same agent in your own app

The panel runs on `pyzed.agents`, which any Pyzed app can use: the same providers, keychain storage, images, MCP
servers, external agents, tools written as Python functions and streamed events. See
[Building AI apps](/pyzed/ai/ai-apps/) and [AI agents in your app](/pyzed/guides/agents/).
