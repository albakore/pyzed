"""A thread as the entries Zed's Agent panel draws, whoever wrote it.

Pyzed's own agent and external agents (ACP) keep a thread the same way: messages with content
blocks (text, thinking, tool calls and their results). ``thread_entries`` reads them as a list of
entries, one per thing to draw, like Zed's thread view:

* ``UserMessage``: what was asked (its text and images; the hidden ``<context>`` is left out).
* ``AssistantMessage``: what the agent wrote, as chunks of text and reasoning, in order.
* ``ToolCall``: one action of the agent with its status, input, output, edits and where it works.

    from pyzed import agents

    for entry in agents.thread_entries(thread.messages, running=agent.running):
        if isinstance(entry, agents.entries.ToolCall):
            print(entry.status, entry.name)

The plan an agent keeps (``update_plan``, or an ACP agent's plan) is not an entry: a panel shows its
last version above the message box, like Zed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

__all__ = ["AssistantMessage", "Entry", "ToolCall", "UserMessage", "is_hidden", "thread_entries", "turn_end"]


def is_hidden(block: Mapping[str, Any]) -> bool:
    """Whether a text block is context the panel adds for the model (``<context>…</context>``), not shown."""
    return block.get("type") == "text" and str(block.get("text", "")).startswith("<context>")


@dataclass
class UserMessage:
    """A message of the user: ``index`` is its place in the thread's messages (to edit or resend it)."""

    index: int
    text: str
    images: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AssistantMessage:
    """What the agent wrote between two tool calls: ``chunks`` are ``("message" | "thought", text)``.
    ``stats`` (``{"seconds", "tokens"}``) is set on the last one of a finished turn."""

    index: int
    chunks: List[tuple] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """The text of its message chunks (what Copy copies)."""
        return "\n\n".join(text.strip() for kind, text in self.chunks if kind == "message" and text.strip())


@dataclass
class ToolCall:
    """One action of the agent.

    ``status`` is ``"pending"`` (being written), ``"running"``, ``"waiting"`` (for the user's OK),
    ``"done"``, ``"failed"``, ``"rejected"`` or ``"canceled"`` (the turn stopped before it ended). ``kind``
    is ACP's (``"read"``, ``"edit"``, ``"execute"``, ``"search"``…) when the agent tells it."""

    id: str
    name: str
    index: int = 0
    kind: str = ""
    status: str = "done"
    input: Dict[str, Any] = field(default_factory=dict)
    output: str = ""
    images: List[Dict[str, Any]] = field(default_factory=list)
    diffs: List[Dict[str, Any]] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    progress: str = ""


Entry = Union[UserMessage, AssistantMessage, ToolCall]


def _result_parts(content: Any) -> "tuple[str, List[Dict[str, Any]]]":
    if isinstance(content, list):
        text = "".join(str(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") == "text")
        images = [b for b in content if isinstance(b, dict) and b.get("type") == "image"]
        return text, images
    return str(content or ""), []


def thread_entries(messages: Sequence[Mapping[str, Any]], *, statuses: Optional[Mapping[str, str]] = None,
                   running: bool = False, waiting: Iterable[str] = ()) -> List[Entry]:
    """The entries of a thread, in order.

    ``statuses`` (tool call id -> ``"running" | "done" | "error"``) is what a running agent reported so far;
    ``running`` says the last turn is still going, so its calls without a result are running rather than
    canceled; ``waiting`` are the ids of calls that wait for the user's OK."""
    statuses = statuses or {}
    waiting = set(waiting)
    results: Dict[str, Mapping[str, Any]] = {}
    for m in messages:
        if m.get("role") == "user":
            for b in m.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    results[str(b.get("tool_use_id", ""))] = b
    out: List[Entry] = []
    for i, m in enumerate(messages):
        blocks = [b for b in m.get("content") or [] if isinstance(b, dict)]
        if m.get("role") == "user":
            texts = [str(b.get("text", "")) for b in blocks if b.get("type") == "text" and not is_hidden(b)]
            images = [b for b in blocks if b.get("type") == "image"]
            if any(t.strip() for t in texts) or images:
                out.append(UserMessage(i, "\n".join(t for t in texts if t.strip()), images))
            continue
        for b in blocks:
            kind = b.get("type")
            if kind in ("text", "thinking"):
                text = str(b.get("text") if kind == "text" else b.get("thinking") or "")
                if not text.strip():
                    continue
                chunk = ("message" if kind == "text" else "thought", text)
                last = out[-1] if out else None
                if isinstance(last, AssistantMessage) and last.index == i:
                    last.chunks.append(chunk)
                else:
                    out.append(AssistantMessage(i, [chunk]))
            elif kind == "tool_use":
                call_id = str(b.get("id", ""))
                result = results.get(call_id)
                reported = statuses.get(call_id, "")
                if call_id in waiting:
                    status = "waiting"
                elif result is not None:
                    output, _ = _result_parts(result.get("content"))
                    status = "failed" if result.get("is_error") else "done"
                    if status == "failed" and output.startswith(("The user did not allow", "Cancelled by the user")):
                        status = "rejected"
                elif reported in ("done", "error"):
                    status = "failed" if reported == "error" else "done"
                elif running:
                    status = "running"
                else:
                    status = "canceled"
                output, images = _result_parts(result.get("content")) if result is not None else ("", [])
                out.append(ToolCall(call_id, str(b.get("name", "")), i, kind=str(b.get("kind") or ""), status=status,
                                    input=dict(b.get("input") or {}), output=output, images=images,
                                    diffs=list(b.get("diffs") or []), locations=list(b.get("locations") or []),
                                    progress=str(b.get("progress") or "") if result is None else ""))
        stats = m.get("stats")
        if isinstance(stats, dict):
            for entry in reversed(out):
                if isinstance(entry, AssistantMessage):
                    entry.stats = dict(stats)
                    break
    return out


def turn_end(entries: Sequence[Entry], index: int, *, running: bool = False) -> bool:
    """Whether ``entries[index]`` ends a turn: the next entry is the user's (or there is none and the
    agent is not running)."""
    following = entries[index + 1] if index + 1 < len(entries) else None
    if following is None:
        return not running
    return isinstance(following, UserMessage)
