---
title: AI agents in your app
description: pyzed.agents - talk to Claude, OpenAI, Gemini, OpenRouter, Ollama and OpenAI-compatible servers, give the model tools, stream its answer into your UI and keep keys in the system keychain.
sidebar:
  order: 17
---

`pyzed.agents` is the engine behind the designer's [Agent panel](/pyzed/editor/ai-agents/), and it works in any
Pyzed app: one API for several model providers, tools written as plain Python functions, streaming events for the
UI, saved threads, and keys kept in the operating system's keychain.

```bash
pip install "pyzed-ui[agents]"     # anthropic (Claude) and keyring
```

## A first agent

```python
from pyzed import agents

agents.set_key("anthropic", "sk-ant-…")          # once: saved in the system keychain


@agents.tool
def stock(product: str) -> int:
    """How many units of a product are in stock.

    product: the product's name.
    """
    return {"chair": 4, "desk": 0}.get(product, 0)


agent = agents.Agent("anthropic:claude-opus-5-5", tools=[stock], system="You help the shop's staff.")
print(agent.run("Can I sell two desks today?"))
```

`run` calls the model, runs the tools it asks for, sends their results back and repeats until the model answers.
It returns the last answer and never raises: failures (a bad key, no network) come back as an `"error"` event and
as the returned text. `agent.messages` keeps the conversation, so the next `run` continues it.

## Models and providers

A model is named `"<provider>:<model>"`:

| Provider | Example | Credentials |
| --- | --- | --- |
| `anthropic` | `anthropic:claude-opus-5-5` | `set_key`, `ANTHROPIC_API_KEY` (an `ant auth login` profile also works) |
| `openai` | `openai:<model>` | `set_key` or `OPENAI_API_KEY` |
| `google` | `google:<gemini model>` | `set_key` or `GEMINI_API_KEY` |
| `openrouter` | `openrouter:anthropic/claude-opus-5-5` | `set_key`, `OPENROUTER_API_KEY` or `agents.login.openrouter_login()` |
| `xai`, `mistral`, `deepseek`, `groq` | `groq:<model>` | `set_key` or `XAI_API_KEY`, `MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `GROQ_API_KEY` |
| `ollama`, `lmstudio` | `ollama:qwen3:8b` | none (local) |
| `custom` | `custom:<model>` | the server URL in the settings, and a key if needed |

`agents.list_models("openai")` asks a provider for its models. Claude goes through the official `anthropic` SDK
with adaptive thinking, the `effort` setting, prompt caching and the server-side refusal fallback; every other
provider through the OpenAI-compatible Chat Completions API.

## Settings

```python
settings = agents.AgentSettings(model="ollama:qwen3:8b", effort="medium", profile="ask",
                                rules="Answer in Spanish.")
settings.provider("ollama").base_url = "http://gpu-box:11434/v1"
agent = agents.Agent(tools=[stock], settings=settings)
```

| Field | Meaning |
| --- | --- |
| `model` | Default model. |
| `effort` | `low`, `medium`, `high`, `xhigh` or `max` (Claude). |
| `fast` | Fast mode on the models in `providers.FAST_MODELS` (Claude Opus 5.5 and Opus 5, Claude API only): faster output at a higher price. |
| `profile` | `"write"` (every tool), `"ask"` (only tools without `writes=True`) or `"minimal"` (no tools). |
| `mode` | The Agent panel's permission mode, a shortcut over `profile` and `confirm_writes`: `"ask"`, `"bypass"`, `"read"` or `"chat"`. |
| `confirm_writes` | Call `confirm(tool, args)` before a tool marked `writes=True` (on by default). Without a `confirm` callback those tools are refused; turn it off to let them run unasked. |
| `rules` | Text added to the system prompt. |
| `keep_history` | Whether Pyzed Design saves threads on this computer (on by default). |
| `providers[id].base_url` / `.models` | Server URL and the models offered for a provider. |

`agents.providers.load()` and `save()` read and write `agents.json` in Pyzed's settings folder (the designer's
settings); keys are never part of it.

## Tools

`@agents.tool` builds the JSON schema from the signature: `str`, `int`, `float`, `bool`, `list`, `dict` and
`Optional[...]`; arguments with a default are optional. The first paragraph of the docstring describes the tool
and `name: text` lines describe the arguments. Return a string or anything JSON can encode.

```python
@agents.tool(writes=True, title="Placing an order")
def order(product: str, units: int) -> dict:
    """Orders units of a product from the supplier."""
    ...
```

| Option | Meaning |
| --- | --- |
| `writes=True` | It changes something: skipped in the `"ask"` profile, and confirmed first when `confirm_writes` is on. |
| `ui=True` | Runs through the agent's `executor` (see below). |
| `title` | Short text for your UI while it runs. |

The model's arguments are checked against the schema before the function runs; a wrong or missing argument, or
an exception, goes back to the model as an error so it can fix its call.

Ready-made tools: `agents.pyzed_tools()` (Pyzed's components, icons, themes, docs, generators and checks, the
same as the [MCP server](/pyzed/guides/mcp/)) and `agents.file_tools(folder)` (list, read, search and write files,
never outside `folder`). The file tools never open keys or credentials (`.env`, `*.pem`, `*.key`, SSH keys...;
`agents.tools.SECRET_FILES`), so a prompt injection in a project file cannot send them to the provider; pass
`hidden=` to change the list.

## Streaming into the UI

`run` blocks, so in an app call it from a worker thread and hand the events to the UI. Pyzed's views run on the UI
thread, so put events on a queue and drain it from a `pz.every` subscription:

```python
import queue, threading
import pyzed as pz
from pyzed import agents, ui


class Chat(pz.App):
    def __init__(self):
        self.agent = agents.Agent("anthropic:claude-opus-5-5")
        self.events = queue.Queue()
        self.answer, self.prompt, self.busy = "", "", False

    def send(self):
        self.busy, self.answer = True, ""
        threading.Thread(target=self.agent.run, args=(self.prompt,),
                         kwargs={"on_event": self.events.put}, daemon=True).start()

    def poll(self):
        while not self.events.empty():
            event = self.events.get()
            if event.kind == "text":
                self.answer += event.text
            elif event.kind == "done":
                self.busy = False

    def subscriptions(self):
        return [pz.every(1 / 30, self.poll, key="chat")] if self.busy else []

    def view(self):
        return pz.column([
            ui.markdown(self.answer),
            ui.input(self.prompt, lambda v: setattr(self, "prompt", v), on_submit=self.send),
        ], spacing=8, padding=16)
```

Events: `text` and `thinking` (a new piece of the answer or of the reasoning summary), `tool_call` and
`tool_result` (`tool`, `args`, `call_id`, `result`, `error`), `turn` (one model answer finished, with `usage`),
`error` and `done`. `agent.stop()` cancels from any thread.

Tools that must touch your app's state should run on the UI thread too: pass `executor=` (a function that runs a
callable there and returns its result) and mark them `ui=True`. The designer does exactly that, which is why the
agent's edits are ordinary undo steps.

## Keys and sign-in

```python
agents.set_key("openai", "sk-…")      # True: in the keychain; False: no keychain, kept for this session only
agents.get_key("openai")              # the saved key, or the environment variable
agents.delete_key("openai")
agents.secrets.store().backend_name   # "Keyring" backend in use, or "memory (this session only)"

key = agents.login.openrouter_login() # OpenRouter: browser + PKCE, returns a key
agents.set_key("openrouter", key)

agents.login.key_page("anthropic")    # the others: opens the provider's API keys page...
agents.providers.looks_like_key("anthropic", copied_text)  # ...and tells whether a copied text is its key
```

Only OpenRouter offers OAuth to other apps. For the rest, Pyzed Design opens the key page and watches the
clipboard for a few minutes; when a text that `looks_like_key` is copied, it checks it with `list_models(key=...)`
and saves it with `set_key`. Your app can do the same.

Keys live in the system keychain (`keyring`, service `pyzed`); `PYZED_KEYRING=0` disables it, and
`agents.secrets.use(SecretStore(my_backend))` plugs in your own vault (any object with keyring's
`get_password` / `set_password` / `delete_password`).

## Threads

```python
store = agents.ThreadStore()                      # agents/threads in Pyzed's settings folder
thread = agents.Thread(model="ollama:qwen3:8b")
agent = agents.Agent(thread.model, messages=thread.messages)
agent.run("Hello")
store.save(thread)                                # JSON only you can read; no keys
store.list()                                      # newest first
```

## Testing

Pass `stream=` to `Agent` to replace the model with a script, so tests run offline and always the same way:

```python
from pyzed.agents import llm

def fake(model, system, messages, tools, *, settings, on_event, cancel):
    if len(messages) == 1:
        return llm.Turn([{"type": "tool_use", "id": "1", "name": "stock", "input": {"product": "desk"}}], "tool_use")
    return llm.Turn([{"type": "text", "text": "No desks left."}])

agent = agents.Agent("x", tools=[stock], stream=fake, settings=agents.AgentSettings())
assert agent.run("Desks?") == "No desks left."
```
