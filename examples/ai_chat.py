"""A streaming AI chat: any OpenAI-compatible server through httpx, with a built-in demo stream.

    python examples/ai_chat.py                                    # demo: canned answers, no network
    CHAT_BASE_URL=http://localhost:11434/v1 CHAT_MODEL=llama3.2 python examples/ai_chat.py     # Ollama
    CHAT_BASE_URL=https://api.openai.com/v1 CHAT_API_KEY=sk-... CHAT_MODEL=<model> python examples/ai_chat.py

The answer streams token by token: ``send`` returns an async generator, Pyzed runs it on its asyncio
loop and every value it yields goes to ``update``, so the window keeps responding while the model writes.
"""

import asyncio
import json
import os
import time

import pyzed as pz
from pyzed import ui

BASE_URL = os.environ.get("CHAT_BASE_URL", "")  # empty: demo mode
API_KEY = os.environ.get("CHAT_API_KEY", "")
MODEL = os.environ.get("CHAT_MODEL", "demo" if not BASE_URL else "llama3.2")
SYSTEM = "You are a concise assistant inside a desktop app. Answer in Markdown."

SUGGESTIONS = [
    ("code", "Write a Python function that removes duplicates but keeps the order"),
    ("lightbulb", "Explain async/await like I'm new to Python"),
    ("table", "Compare SQLite, PostgreSQL and DuckDB in a table"),
]

DEMO_ANSWER = """Sure! A `dict` keeps insertion order, so it does the work for you:

```python
def unique(items):
    \"\"\"Removes duplicates and keeps the first occurrence of each item.\"\"\"
    return list(dict.fromkeys(items))


unique([3, 1, 3, 2, 1])   # [3, 1, 2]
```

- **O(n)**: one pass, no nested loops.
- Works with any *hashable* item (numbers, strings, tuples).
- For unhashable items such as lists, keep a `seen` list instead.
"""


# -- the model ---------------------------------------------------------------------------------
async def openai_stream(messages, *, model=MODEL, base_url=BASE_URL, api_key=API_KEY):
    """Yields the answer's text pieces from an OpenAI-compatible ``/chat/completions`` endpoint."""
    import httpx  # only needed when talking to a real server

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    body = {"model": model, "messages": messages, "stream": True}
    async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as client:
        async with client.stream("POST", f"{base_url.rstrip('/')}/chat/completions", json=body,
                                 headers=headers) as response:
            if response.status_code >= 400:
                detail = (await response.aread()).decode(errors="replace")[:300]
                raise RuntimeError(f"HTTP {response.status_code}: {detail}")
            async for line in response.aiter_lines():  # server-sent events: "data: {...}"
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
                if delta:
                    yield delta


async def demo_stream(messages, *, delay=0.015):
    """A stand-in for the model: streams a canned answer a few characters at a time."""
    text = DEMO_ANSWER
    for i in range(0, len(text), 4):
        await asyncio.sleep(delay)
        yield text[i:i + 4]


def model_stream(messages):
    return demo_stream(messages) if not BASE_URL else openai_stream(messages)


# -- the app -----------------------------------------------------------------------------------
class AIChat(pz.App):
    title = "AI chat"
    size = (980, 720)

    def __init__(self, stream=model_stream):
        self.stream = stream            # a function: messages -> async iterator of text
        self.messages = []              # [{"role": "user" | "assistant", "content": str}]
        self.draft = ""
        self.busy = False
        self.error = ""
        self.turn = 0                   # tags each reply, so pieces of a stopped one are ignored
        self.started = 0.0
        self.tokens = 0

    # -- actions --------------------------------------------------------------------------------
    def send(self, text=None):
        text = (text if text is not None else self.draft).strip()
        if not text or self.busy:
            return None
        self.messages += [{"role": "user", "content": text}, {"role": "assistant", "content": ""}]
        self.draft, self.error, self.busy = "", "", True
        self.turn += 1
        self.started, self.tokens = time.monotonic(), 0
        history = [{"role": "system", "content": SYSTEM}] + self.messages[:-1]
        return [self.reply(self.turn, history), pz.Command.scroll_to_end("thread")]

    async def reply(self, turn, history):
        """Runs on Pyzed's asyncio loop; each yield goes to update() on the UI thread."""
        try:
            async for piece in self.stream(history):
                if turn != self.turn:   # stopped or superseded
                    return
                yield ("delta", turn, piece)
        except Exception as error:      # network errors, bad keys... shown in the thread
            yield ("error", turn, str(error) or type(error).__name__)
        yield ("done", turn, None)

    def stop(self):
        self.turn += 1                  # the running reply sees a new turn and ends
        self.busy = False

    def clear(self):
        self.stop()
        self.messages, self.error = [], ""

    def update(self, message):
        kind, turn, value = message
        if turn != self.turn:
            return None
        if kind == "delta":
            self.messages[-1]["content"] += value
            self.tokens += 1
            return pz.Command.scroll_to_end("thread")
        if kind == "error":
            self.error = value
        elif kind == "done":
            self.busy = False
        return None

    # -- view -----------------------------------------------------------------------------------
    def bubble(self, index, message):
        last = index == len(self.messages) - 1
        if message["role"] == "user":
            return pz.row([pz.hspace(), pz.container(ui.label(message["content"]), padding=(10, 14),
                                                     max_width=560).style(background="element", radius=14)])
        content = message["content"]
        if last and self.busy:
            content += " ▍"
        body = [ui.markdown(content) if content.strip() else
                pz.row([ui.spinner(size=14), ui.muted("Thinking…")], spacing=8, align="center")]
        if not (last and self.busy) and content:
            body.append(pz.row([
                ui.icon_button("copy", pz.Command.copy(message["content"]), size="sm", tooltip="Copy"),
                ui.icon_button("refresh-cw", self.retry, size="sm", tooltip="Regenerate") if last else None,
                ui.icon_button("thumbs-up", None, size="sm"), ui.icon_button("thumbs-down", None, size="sm"),
            ], spacing=2))
        avatar = pz.container(pz.icon("sparkles", size=15, color="#ffffff"), width=30, height=30, center=True).style(
            background=pz.Gradient(["#8b5cf6", "#ec4899"], angle=135), radius=15)
        return pz.row([avatar, pz.column(body, spacing=6, width="fill")], spacing=12)

    def retry(self):
        if self.messages and not self.busy:
            question = self.messages[-2]["content"]
            self.messages = self.messages[:-2]
            return self.send(question)
        return None

    def empty(self):
        cards = [pz.button(pz.row([pz.icon(icon, size=16), ui.label(text, size="sm")], spacing=10, align="center"),
                           lambda text=text: self.send(text), width="fill", padding=(12, 14), radius=10,
                           bg=self.resolved_theme().surface, hover_bg=self.resolved_theme().element_hover,
                           border_color=self.resolved_theme().border_variant, border_width=1)
                 for icon, text in SUGGESTIONS]
        return pz.container(pz.column([
            pz.container(pz.icon("sparkles", size=26, color="#ffffff"), width=56, height=56, center=True).style(
                background=pz.Gradient(["#8b5cf6", "#ec4899"], angle=135), radius=16, glow=("#8b5cf6", 18)),
            ui.heading("How can I help?"),
            ui.muted(f"Model: {MODEL}" + ("  ·  demo stream, no network" if not BASE_URL else "")),
            pz.space(height=8),
            pz.column(cards, spacing=8, width=480),
        ], spacing=10, align="center"), width="fill", height="fill", center=True)

    def composer(self):
        action = (ui.icon_button("square", self.stop, variant="solid", tooltip="Stop") if self.busy else
                  ui.icon_button("arrow-up", self.send, variant="solid" if self.draft.strip() else "filled",
                                 tooltip="Send", disabled=not self.draft.strip()))
        return pz.container(pz.row([
            ui.input(self.draft, lambda v: setattr(self, "draft", v), placeholder="Ask anything…",
                     on_submit=self.send, borderless=True, id="prompt", size="lg"),
            action,
        ], spacing=8, align="center"), padding=(6, 8, 6, 12), max_width=760).style(
            background="surface", border=(1, "border"), radius=16, shadow=("#00000026", (0, 4), 16))

    def view(self):
        speed = ""
        if self.tokens and self.busy:
            speed = f"{self.tokens / max(time.monotonic() - self.started, 0.001):.0f} chunks/s"
        header = ui.toolbar(
            [pz.icon("sparkles", size=14),
             ui.label("Assistant", weight="semibold"), ui.badge(MODEL, tint="info", variant="soft")],
            [ui.muted(speed, size="sm") if speed else None,
             ui.icon_button("trash-2", self.clear, size="sm", tooltip="New chat")], height=44)
        if self.messages:
            thread = pz.column([self.bubble(i, m) for i, m in enumerate(self.messages)], spacing=22, max_width=760,
                               padding=(24, 24, 8, 24))
            if self.error:
                thread = pz.column([thread, pz.container(ui.callout("The model failed", self.error, tint="error",
                                                                    icon="circle-alert"), max_width=760,
                                                         padding=(0, 24))])
            middle = pz.scrollable(pz.container(thread, width="fill", align_x="center"), height="fill", id="thread",
                                   anchor_bottom=True)
        else:
            middle = self.empty()
        return pz.column([
            header, ui.divider(), middle,
            pz.container(self.composer(), width="fill", align_x="center", padding=(8, 24, 20, 24)),
        ], height="fill").style(background="editor")


if __name__ == "__main__":
    pz.run(AIChat)
