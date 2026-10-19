---
title: API keys and credentials
description: "How Pyzed Design and pyzed.agents find model provider credentials: the system keychain, environment variables, browser sign-in, Google Cloud credentials and workload identity federation, and how to keep keys safe."
sidebar:
  order: 2.5
---

The agent in [Pyzed Design](/pyzed/editor/ai-agents/) and the [`pyzed.agents`](/pyzed/guides/agents/) library
need a credential for the model provider you pick: an API key, a sign-in token or, for Claude, workload identity
federation. This page explains where Pyzed looks for them, how to give it one without writing it in a file, and how
to keep it safe. Local models (Ollama, LM Studio) need nothing.

## Where Pyzed looks

For each request, Pyzed takes the first credential it finds, in this order:

1. **The system keychain.** A key you pasted or a sign-in token, saved under the service `pyzed` in the operating
   system's credential store: Keychain on macOS, Credential Manager on Windows, Secret Service (GNOME Keyring,
   KWallet) on Linux. Sign-in tokens (OpenRouter, GitHub, Google) are kept there too and refreshed when they are
   about to expire.
2. **Workload identity federation** (Anthropic only), when it is turned on in the settings and no key is saved.
   See [Claude without an API key](#claude-without-an-api-key).
3. **The provider's environment variable**, such as `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` (table below). It is
   read, never copied anywhere.
4. **What the computer already has.** Google Vertex AI uses the Google Cloud credentials from
   `gcloud auth application-default login`. Anthropic also uses an Anthropic CLI profile (`ant auth login`) and the
   `ANTHROPIC_FEDERATION_RULE_ID` / `ANTHROPIC_ORGANIZATION_ID` variables.

A saved key always wins: if you set an environment variable and it seems to be ignored, open the provider in the
settings and click **Remove key**. Each provider in the settings has a badge that says where its credential comes
from, and **Test the connection** checks that it works:

| Badge | Meaning |
| --- | --- |
| **Key saved in the system keychain** | A key you pasted, stored in the keychain. |
| **Key kept for this session only** | No keychain was found: the key lives in memory until the designer closes. |
| **Signed in** | A sign-in token (OAuth or GitHub device flow) in the keychain. |
| **Key from the environment** | The provider's environment variable. |
| **Workload identity federation** | Claude through federation, no key. |
| **Signed in with the Anthropic CLI profile** | An `ant auth login` profile on this computer. |
| **Google Cloud credentials of this computer** | Vertex AI through `gcloud`'s application default credentials. |
| **No key needed** | Ollama, LM Studio, or an OpenAI-compatible server without a key. |

## Environment variables per provider

| Provider | Model prefix | Environment variable | Other ways in |
| --- | --- | --- | --- |
| Anthropic | `anthropic:` | `ANTHROPIC_API_KEY` | Sign in with the browser, federation, `ant auth login` |
| OpenAI | `openai:` | `OPENAI_API_KEY` | Sign in with the browser |
| Google Gemini (AI Studio) | `google:` | `GEMINI_API_KEY` | Sign in with the browser |
| Google Vertex AI | `vertex:` | none | Sign in with Google, `gcloud auth application-default login` or a service account file in `GOOGLE_APPLICATION_CREDENTIALS`; the project comes from the settings or `GOOGLE_CLOUD_PROJECT` |
| GitHub Copilot (GitHub Models) | `github:` | `GITHUB_TOKEN` | Sign in with GitHub (device flow), a fine-grained token with the **Models** permission |
| OpenRouter | `openrouter:` | `OPENROUTER_API_KEY` | Sign in with the browser (OAuth with PKCE) |
| xAI | `xai:` | `XAI_API_KEY` | Sign in with the browser |
| Mistral | `mistral:` | `MISTRAL_API_KEY` | Sign in with the browser |
| DeepSeek | `deepseek:` | `DEEPSEEK_API_KEY` | Sign in with the browser |
| Groq | `groq:` | `GROQ_API_KEY` | Sign in with the browser |
| Ollama, LM Studio | `ollama:`, `lmstudio:` | none | Nothing: they run on your computer |
| OpenAI-compatible | `custom:` | `PYZED_AGENT_API_KEY` | A key in the settings, only if the server needs one |

Other variables Pyzed reads: `ANTHROPIC_FEDERATION_RULE_ID`, `ANTHROPIC_ORGANIZATION_ID`,
`ANTHROPIC_IDENTITY_TOKEN_FILE` and `ANTHROPIC_IDENTITY_TOKEN` (federation), `PYZED_GITHUB_CLIENT_ID`,
`PYZED_GOOGLE_CLIENT_ID` and `PYZED_GOOGLE_CLIENT_SECRET` (your own OAuth apps for signing in),
`GOOGLE_APPLICATION_CREDENTIALS` (a Google Cloud service account file for Vertex AI) and `PYZED_KEYRING=0`
(don't use the keychain).

## The recommended way: the keychain

Keep keys out of files and shells altogether and let Pyzed Design put them in the keychain:

1. Open **Settings → AI agents → AI agents settings…** (also the gear in the Agent panel, or `/settings`).
2. Under **Providers**, click the provider to open it.
3. Either click **Sign in with the browser** (Pyzed opens the provider's key page and picks up the key when you click
   its **Copy** button; see [Signing in](/pyzed/editor/ai-agents/#signing-in)), or paste the key in **API key**
   and click **Save**.
4. A notice says **Key saved in the system keychain**, and the provider's badge says the same.

The key never goes to `agents.json`, to the threads or to your project, and the field only shows a masked preview
(`sk-ant…a1b2`) afterwards. **Remove key** deletes it from the keychain.

From code, the same store is one call away:

```python
from pyzed import agents

agents.set_key("anthropic", "sk-ant-…")   # True: in the keychain; False: kept for this session only
agents.get_key("anthropic")               # the saved key, or the environment variable
agents.delete_key("anthropic")
```

Run that once from a Python prompt, not from a file you keep, so the key is never written to disk.

### "Key kept for this session only"

If the settings show **No system keychain found** and the badge says **Key kept for this session only**, Pyzed
could not reach a keychain, so a key you paste lasts until the designer closes. It is never written in plain text
as a fallback. To fix it:

- **Running Pyzed from pip or uv:** install the extra that brings `keyring`:

  ```bash
  pip install "pyzed-ui[agents]"     # or: uv add "pyzed-ui[agents]"
  ```

- **Linux:** `keyring` needs a Secret Service running, which GNOME and KDE desktops start for you. On a minimal
  window manager or a headless machine, install and unlock `gnome-keyring` (or KWallet), or use an environment
  variable instead.
- **The compiled Pyzed Design** ([download](/pyzed/download/)) already bundles `keyring`; if it still says so,
  the keychain itself is locked or missing.

Pyzed ignores keyring's "fail" and plain-text backends on purpose, so a key is never saved unencrypted.

## Using environment variables

An environment variable is handy on a CI runner, in a container or when you already keep keys in a password
manager that exports them. Pyzed only reads it.

From a terminal, set it and start the designer from the same terminal:

```bash
export ANTHROPIC_API_KEY="sk-ant-…"   # macOS and Linux (bash, zsh)
pyzed design
```

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-…"   # Windows PowerShell, this window only
pyzed design
```

Apps started from the Finder, the Start menu or a desktop launcher don't read your shell's `~/.zshrc` or
`~/.bashrc`, so a variable set there is not seen by the compiled Pyzed Design. Set it where GUI apps get their
environment, then quit and reopen Pyzed Design:

- **macOS:** `launchctl setenv ANTHROPIC_API_KEY "sk-ant-…"`. It lasts until you restart the Mac; to keep it, run it
  from a login item or a LaunchAgent.
- **Windows:** **Start → Edit environment variables for your account → New…** (user variables), or
  `setx ANTHROPIC_API_KEY "sk-ant-…"` in a terminal. Programs started after that see it.
- **Linux (systemd desktops):** add `ANTHROPIC_API_KEY=sk-ant-…` to a file such as
  `~/.config/environment.d/pyzed.conf`, then log out and in again.

Keep in mind that an environment variable is plain text: every program started from that environment inherits it,
including the apps you run with <kbd>F5</kbd>. A key in the keychain is only handed to Pyzed. Prefer the keychain on
your own computer, and environment variables where there is no keychain.

Pyzed Design does not load `.env` files. In your own app you can load one with a library such as `python-dotenv`;
keep it out of git (add it to `.gitignore`).

## Claude without an API key

Workload identity federation exchanges a short-lived token from your identity provider (GitHub Actions, Google
Cloud, Azure, Okta, Kubernetes…) for a short-lived Claude token, so no Anthropic key is stored at all. Set it up in
the Claude Console, then fill in **Anthropic → Workload identity federation** in the settings, or set
`ANTHROPIC_FEDERATION_RULE_ID`, `ANTHROPIC_ORGANIZATION_ID` and `ANTHROPIC_IDENTITY_TOKEN_FILE`. The identity token
can come from a file, a command that prints a fresh one (`gcloud auth print-identity-token`) or a variable. The
fields are explained in [Claude without an API key](/pyzed/editor/ai-agents/#claude-without-an-api-key), and the
code version in [AI agents in your app](/pyzed/guides/agents/#claude-without-an-api-key).

Federation is used only when no key is saved: remove a saved Anthropic key to switch to it.

## Sign-in tokens

- **OpenRouter** signs in with OAuth and PKCE; the key it issues for Pyzed goes to the keychain.
- **GitHub Copilot** signs in with GitHub's device flow (you type a short code on `github.com/login/device`). It
  needs a GitHub App client ID in the provider's settings or `PYZED_GITHUB_CLIENT_ID`; without one, paste a
  fine-grained personal access token with the **Models** permission.
- **Google Vertex AI** signs in with Google (OAuth with PKCE) or uses `gcloud` credentials. Signing in with your own
  OAuth client needs its client secret, which goes to the keychain as well.

The tokens are saved in the keychain as the provider's entry, refreshed shortly before they expire, and
**Sign out** deletes them.

## MCP servers and external agents

[MCP servers](/pyzed/editor/ai-agents/#mcp-servers) and [external agents](/pyzed/editor/ai-agents/#external-agents)
often need their own token (`GITHUB_TOKEN` for the GitHub MCP server, a key for an external agent). Put them in the
**Secrets** field as `NAME=value` pairs separated by `;`. They are saved in the keychain, never in `agents.json`,
and passed to the server as environment variables (or as HTTP headers for a remote server) when it starts. In code:

```python
from pyzed.agents import mcp_client

mcp_client.set_secrets("github", {"GITHUB_TOKEN": "github_pat_…"})   # in the keychain
```

## What the agent cannot read

The agent's file tools refuse to list, read, search or write files that usually hold credentials, so a prompt
injection hidden in a web page or a file can't make it send them to the model:

`.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, `id_ecdsa*`, `id_ed25519*`, `.netrc`, `.pypirc`,
`.npmrc` and `.git-credentials`.

They are not offered in the <kbd>@</kbd> menu either, and external agents get the same rule when they ask Pyzed for
files. The list is `pyzed.agents.tools.SECRET_FILES`; pass your own to `file_tools(folder, hidden=...)` in your app.
Keys are also never written to threads or settings, and the field only shows a masked preview.

## Good practices

- **Use a dedicated key** for Pyzed, with a **spending limit** or budget in the provider's console, so a leak or a
  runaway loop has a ceiling.
- **Never put a key in code**, in a `.pzform`, in `agents.json` or anywhere in the repository. If one is
  committed, deleting the commit is not enough: revoke it.
- **Rotate a key you think leaked**: revoke it in the provider's console, create a new one and paste it again
  (**Remove key**, then **Save**).
- **Prefer short-lived credentials** where you can: sign-in tokens, Google Cloud credentials or Claude federation
  instead of a long-lived API key, especially on shared machines and CI.
- **Shipping an app that uses `pyzed.agents`?** Don't bundle your key in it: anything inside an app can be
  extracted. Let each user sign in or paste their own key (it goes to their keychain), or put a server you control
  between the app and the provider.
- **Use local models** (Ollama, LM Studio) when the data must not leave the computer.
