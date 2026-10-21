"""An AI agent that knows Pyzed: a chat whose answers call tools, shown like Zed's Agent panel.

    python examples/agent_chat.py                                         # demo: a scripted model
    AGENT_MODEL=anthropic:claude-opus-5-5 python examples/agent_chat.py   # a real model (pip install "pyzed-ui[agents]")

``pyzed.agents.Agent`` runs the conversation in a thread: the model writes, asks for a tool, the
tool runs and the model goes on with its result. Its events (text, tool calls, results, usage)
reach the window through ``pz.post`` and are drawn with the agent components of ``pyzed.ui``
(``ToolCall``, ``context_meter``). The tools are ``agents.pyzed_tools()``, the same ones the
Pyzed MCP server and the Agent panel of Pyzed Design use; they only read Pyzed's reference. In
demo mode a scripted stand-in for the model calls them for real, with no network and no key.
Set the key of a real model in Pyzed Design (Settings → AI agents) or its environment variable.
"""

import json
import os
import threading
import time

import pyzed as pz
from pyzed import agents, ui
from pyzed.agents import llm

MODEL = os.environ.get("AGENT_MODEL", "")  # empty: demo mode
SYSTEM = "You help people build desktop apps with Pyzed. Look things up with your tools, then answer in Markdown."
SUGGESTIONS = [
    ("list", "Which component shows a long list fast?"),
    ("palette", "How do I change the theme of my app?"),
    ("gamepad-2", "What do I need to make a game?"),
]

#: Words the demo model looks up (otherwise it takes the longest word of the question).
TOPICS = ("list", "table", "theme", "game", "shader", "audio", "animation", "button", "form", "chart", "window")


# -- a stand-in for the model ---------------------------------------------------------------------
def demo_stream(model, system, messages, tools=(), *, on_event=None, cancel=None, **_):
    """Answers like a model would: first a call to ``search_reference``, then an answer from its result."""
    emit = on_event or (lambda kind, text: None)

    def say(text):
        for i in range(0, len(text), 5):
            if cancel is not None and cancel.is_set():
                return llm.Turn([{"type": "text", "text": text[:i]}], "cancelled")
            time.sleep(0.012)
            emit("text", text[i:i + 5])
        return None

    last = messages[-1]["content"]
    usage = {"input": 1200 * len(messages), "output": 180}
    if last and last[0].get("type") == "tool_result":  # the tool answered: write the answer from what it found
        try:
            found = json.loads(last[0]["content"])
        except (TypeError, ValueError):
            found = []
        found = found.get("results", found) if isinstance(found, dict) else found
        lines = [f"- **`{hit.get('title', '?')}`**: {hit.get('summary', '')}".rstrip(": ")
                 for hit in found[:5] if isinstance(hit, dict)]
        text = ("Here is what Pyzed's reference has on it:\n\n" + "\n".join(lines) +
                "\n\nOpen any of them in the docs, or ask me for an example.") if lines else \
            "I found nothing about that in the reference. Try other words?"
        return say(text) or llm.Turn([{"type": "text", "text": text}], usage=usage)
    question = next(b["text"] for b in last if b.get("type") == "text")
    words = [w.strip("?.,!").lower() for w in question.split()]
    query = next((w for w in words if w in TOPICS), max(words, key=len, default="app"))
    intro = "Let me look that up in the reference."
    stopped = say(intro)
    if stopped:
        return stopped
    emit("tool", "search_reference")
    call = {"type": "tool_use", "id": f"call_{len(messages)}", "name": "search_reference",
            "input": {"query": query, "limit": 5}}
    return llm.Turn([{"type": "text", "text": intro}, call], "tool_use", usage=usage)


# -- the app ------------------------------------------------------------------------------------------
class AgentChat(pz.App):
    title = "Pyzed agent"
    size = (980, 720)

    def __init__(self):
        self.agent = agents.Agent(MODEL or "anthropic:demo", tools=agents.pyzed_tools(screenshots=False),
                                  system=SYSTEM, stream=llm.stream_turn if MODEL else demo_stream)
        self.agent.settings.profile = "ask"  # read-only tools: nothing to confirm
        self.thread = []    # {"role": "user", "text"} or {"role": "agent", "parts": [...]}
        self.draft = ""
        self.busy = False
        self.used = 0

    # -- running the agent --------------------------------------------------------------------------
    def send(self, text=None):
        text = (text if text is not None else self.draft).strip()
        if not text or self.busy:
            return None
        self.thread += [{"role": "user", "text": text}, {"role": "agent", "parts": []}]
        self.draft, self.busy = "", True
        threading.Thread(target=self.agent.run, args=(text,), kwargs={"on_event": pz.post}, daemon=True).start()
        return pz.Command.scroll_to_end("thread")

    def stop(self):
        self.agent.stop()

    def update(self, event):
        parts = self.thread[-1]["parts"]
        if event.kind == "text":
            if not parts or parts[-1]["kind"] != "text":
                parts.append({"kind": "text", "text": ""})
            parts[-1]["text"] += event.text
        elif event.kind == "tool_input":
            parts.append({"kind": "tool", "name": event.tool, "status": "pending", "args": {}, "result": ""})
        elif event.kind == "tool_call":
            call = self.tool_part(parts, event.tool)
            call.update(status="running", args=event.args)
        elif event.kind == "tool_result":
            call = self.tool_part(parts, event.tool)
            call.update(status="failed" if event.error else "done", result=event.result)
        elif event.kind == "turn":
            self.used = event.usage.get("input", 0) + event.usage.get("output", 0)
        elif event.kind == "error":
            parts.append({"kind": "error", "text": event.text})
        elif event.kind == "done":
            self.busy = False
        return pz.Command.scroll_to_end("thread")

    @staticmethod
    def tool_part(parts, name):
        for part in reversed(parts):
            if part["kind"] == "tool" and part["name"] == name and part["status"] in ("pending", "running"):
                return part
        parts.append({"kind": "tool", "name": name, "status": "pending", "args": {}, "result": ""})
        return parts[-1]

    # -- view -----------------------------------------------------------------------------------------
    def part(self, part):
        if part["kind"] == "text":
            return ui.markdown(part["text"])
        if part["kind"] == "error":
            return ui.callout("The agent stopped", part["text"], tint="error", icon="circle-alert")
        tool = self.agent.tools.get(part["name"])
        return ui.ToolCall(title=getattr(tool, "title", "") or part["name"], detail=part["args"].get("query", ""),
                           kind="search", status=part["status"], input=part["args"] or None,
                           output=part["result"] or None)

    def message(self, index, message):
        if message["role"] == "user":
            return pz.row([pz.hspace(), pz.container(ui.label(message["text"]), padding=(10, 14), max_width=560)
                           .style(background="element", radius=14)])
        body = [self.part(p) for p in message["parts"]]
        if index == len(self.thread) - 1 and self.busy:
            body.append(pz.row([ui.spinner(size=14), ui.muted("Working…", size="sm")], spacing=8, align="center"))
        return pz.column(body, spacing=8, width="fill")

    def empty(self):
        t = self.resolved_theme()
        cards = [pz.button(pz.row([pz.icon(icon, size=16), ui.label(text, size="sm")], spacing=10, align="center"),
                           lambda text=text: self.send(text), width="fill", padding=(12, 14), radius=10,
                           bg=t.surface, hover_bg=t.element_hover, border_color=t.border_variant, border_width=1)
                 for icon, text in SUGGESTIONS]
        return pz.container(pz.column([
            pz.container(pz.icon("bot", size=26, color="#ffffff"), width=56, height=56, center=True).style(
                background=pz.Gradient(["#6366f1", "#06b6d4"], angle=135), radius=16, glow=("#6366f1", 18)),
            ui.heading("Ask about Pyzed"),
            ui.muted("The agent searches Pyzed's reference with its tools before it answers.", size="sm"),
            pz.space(height=8),
            pz.column(cards, spacing=8, width=480),
        ], spacing=10, align="center"), width="fill", height="fill", center=True)

    def composer(self):
        action = (ui.icon_button("square", self.stop, variant="solid", tooltip="Stop") if self.busy else
                  ui.icon_button("arrow-up", self.send, variant="solid", tooltip="Send",
                                 disabled=not self.draft.strip()))
        return pz.container(pz.row([
            ui.input(self.draft, lambda v: setattr(self, "draft", v), placeholder="Ask the agent…",
                     on_submit=self.send, borderless=True, id="prompt", size="lg"),
            action,
        ], spacing=8, align="center"), padding=(6, 8, 6, 12), max_width=760).style(
            background="surface", border=(1, "border"), radius=16)

    def view(self):
        header = ui.toolbar(
            [pz.icon("bot", size=14), ui.label("Agent", weight="semibold"),
             ui.badge(MODEL or "demo model", tint="info", variant="soft"),
             ui.badge(f"{len(self.agent.tools)} tools", variant="soft")],
            [ui.context_meter(self.used, 200_000)], height=44)
        if self.thread:
            middle = pz.scrollable(pz.container(
                pz.column([self.message(i, m) for i, m in enumerate(self.thread)], spacing=22, max_width=760,
                          padding=(24, 24, 8, 24)), width="fill", align_x="center"),
                height="fill", id="thread", anchor_bottom=True)
        else:
            middle = self.empty()
        return pz.column([
            header, ui.divider(), middle,
            pz.container(self.composer(), width="fill", align_x="center", padding=(8, 24, 20, 24)),
        ], height="fill").style(background="editor")


if __name__ == "__main__":
    pz.run(AgentChat)
