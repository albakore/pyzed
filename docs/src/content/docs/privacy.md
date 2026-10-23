---
title: Privacy policy
description: "What Pyzed and Pyzed Design send over the network, what they keep on your computer and how to turn each part off. No accounts, no ads, no tracking."
---

_Last updated: October 23, 2026._

Pyzed is an open-source project maintained by Kevin Kener ([albakore](https://github.com/albakore)). This page
covers the **pyzed-ui** library, the **Pyzed Design** app and this website. In short: there are no accounts, no
ads and no tracking. Pyzed collects nothing about you. The few connections the app makes are listed below, with
how to turn each one off.

## The pyzed-ui library

The library collects nothing and sends nothing on its own. An app built with Pyzed only connects to the internet
if its developer makes it do so (for example with [`pyzed.updater`](/pyzed/packaging/updates/) or a web request
in its own code). That is the developer's responsibility, under their own privacy policy.

## Pyzed Design

### Connections it makes

| What | Where to | When | Turn it off |
| --- | --- | --- | --- |
| **Looking for updates** and downloading them | GitHub (`api.github.com`, `github.com`) | Once a day in the background, and when you choose *Check for updates* | **Settings → General → Check for updates** |
| **What's new** notes | GitHub | After an update, or when you open them | Not needed: only release notes are read |
| **Creating projects and installing packages** | The Python Package Index (pypi.org), Python's downloads and uv's installer (astral.sh), through [uv](https://docs.astral.sh/uv/) | When you create a project, add a package or update one | Don't create or update projects (uv works offline with what it already downloaded) |
| **Example projects** missing from your copy | GitHub | When you open the gallery and the examples aren't installed | Not needed in the installed app: they come with it |
| **AI agents** (Agent panel and inline assist) | The provider **you choose and set up**: Anthropic, OpenAI, Google, GitHub, OpenRouter, Mistral, Groq, xAI, DeepSeek, or an agent program installed on your computer | Only after you add a provider and send a message | Don't add a provider, or remove it in the Agent panel's settings |
| **List of agent programs** | The Agent Client Protocol registry (`cdn.agentclientprotocol.com`) | When you browse agents to install | Don't open the list |
| **Telemetry** | Only an address **you** type in | Never by default (see below) | It is off unless you turn it on |

What these services receive is what any connection carries (your IP address and a program name such as
`pyzed-updater`) plus, for an AI provider, the messages you send and the code or files you attach to them.
Each service handles that under its own privacy policy. Pyzed never sends your code, files, keys or settings to
the project or to anyone else.

### Telemetry (off by default)

Pyzed Design does not collect usage data unless you turn it on in **Settings → Telemetry**. When it is on, it
counts the commands you use and times the start, renders and commands, and keeps those numbers in
`telemetry.json` in Pyzed's settings folder, on your computer. Nothing leaves your computer unless you also type
in an address to send it to (for example, a server of your own). No code, text, file names or paths are ever
recorded. `PYZED_TELEMETRY=0` turns it off whatever the settings say. Details:
[Settings → Telemetry](/pyzed/editor/settings/#telemetry).

### What stays on your computer

- **Settings, recent projects, layouts, logs and downloaded updates**, in Pyzed's settings folder
  (`%APPDATA%\pyzed` on Windows, `~/Library/Application Support/pyzed` on macOS, `~/.config/pyzed` on Linux).
- **API keys and sign-ins** for AI providers, in your system's keychain (Windows Credential Manager, macOS
  Keychain, Secret Service on Linux), never in plain files.
- **Your projects**, in the folders you choose.

Deleting the app and that settings folder removes everything Pyzed Design saved.

### Changes to other programs' settings

To let the AI agents installed on your computer (Claude Code, Cursor, Gemini CLI, Codex, VS Code, Zed...) use
Pyzed's help, Pyzed Design adds Pyzed's MCP server to their settings files, once for each agent. It changes only
its own `pyzed` entry, keeps a copy of each file next to it (`.pyzed-backup`) before the first change, and tells
you which agents it added it to. Turn it off in the Agent panel's settings: **Pyzed's MCP in your agents → Add it
to new agents on start**.

## This website

The docs are hosted on GitHub Pages, which, like any web server, sees your IP address (see
[GitHub's privacy statement](https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement)).
The pages load their fonts from Google Fonts. The site uses no cookies, no analytics and no ads.

## Code signing

Windows builds of Pyzed Design may be signed by [SignPath Foundation](https://signpath.org), with a free
certificate from [SignPath.io](https://signpath.io). Signing only proves that the files come from this project's
public builds. It adds no data collection.

## Changes and contact

If this policy changes, the new version will be published on this page with its date, and in the
[changelog](/pyzed/changelog/). For questions, open an issue at
[github.com/albakore/pyzed/issues](https://github.com/albakore/pyzed/issues).
