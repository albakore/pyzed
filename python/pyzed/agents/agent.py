"""The agent loop: a model, tools it may call, and a conversation that remembers.

    from pyzed import agents

    @agents.tool
    def weather(city: str) -> str:
        "The weather in a city."
        return "Sunny"

    agent = agents.Agent("anthropic:claude-opus-5-5", tools=[weather])
    print(agent.run("Do I need an umbrella in Madrid?"))

``run`` blocks until the model is done (call it from a worker thread in a GUI) and reports what
happens through ``on_event(Event)``: text and reasoning as they stream, every tool call and its
result, and the end of each turn. Tools marked ``writes=True`` ask ``confirm(tool, args)`` first when
the settings say so (``confirm_writes``, on by default); with no ``confirm`` they are refused, so pass
one, or turn ``confirm_writes`` off to let them run unasked. ``stop()`` cancels from any thread.
"""

from __future__ import annotations

import base64
import inspect
import json
import threading
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union, get_type_hints

from . import llm
from . import providers as _providers

_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}
#: Characters of a tool result sent back to the model (the rest is cut, with a note).
RESULT_LIMIT = 40_000
#: Largest image sent to a model, in bytes (Claude takes up to 5 MB per image).
IMAGE_LIMIT = 5 * 1024 * 1024
_MAGIC = ((b"\x89PNG", "image/png"), (b"\xff\xd8\xff", "image/jpeg"), (b"GIF8", "image/gif"))


@dataclass(frozen=True)
class Image:
    """An image for the model: attach it to a message (``image_block``) or return it from a tool."""

    data: bytes
    media_type: str = ""

    @classmethod
    def open(cls, path: Union[str, Path]) -> "Image":
        """Reads a PNG, JPEG, GIF or WebP file."""
        return cls(Path(path).read_bytes())

    @property
    def type(self) -> str:
        """The media type, from ``media_type`` or the file's first bytes."""
        if self.media_type:
            return self.media_type
        for magic, kind in _MAGIC:
            if self.data.startswith(magic):
                return kind
        if self.data[:4] == b"RIFF" and self.data[8:12] == b"WEBP":
            return "image/webp"
        raise ValueError("not a PNG, JPEG, GIF or WebP image")

    def block(self) -> Dict[str, Any]:
        """The image as a content block of a message (Anthropic's shape, converted for other providers)."""
        if len(self.data) > IMAGE_LIMIT:
            raise ValueError(f"the image is {len(self.data) // 1024} KB; the limit is {IMAGE_LIMIT // 1048576} MB")
        return {"type": "image", "source": {"type": "base64", "media_type": self.type,
                                            "data": base64.b64encode(self.data).decode("ascii")}}


def image_block(image: Union[Image, bytes, str, Path], media_type: str = "") -> Dict[str, Any]:
    """A message content block for ``image`` (an ``Image``, its bytes or a file path)."""
    if isinstance(image, (str, Path)):
        image = Image.open(image)
    elif isinstance(image, (bytes, bytearray)):
        image = Image(bytes(image), media_type)
    return image.block()


@dataclass
class Tool:
    """A function the model can call."""

    name: str
    description: str
    schema: Dict[str, Any]
    func: Callable[..., Any]
    #: Changes something outside the conversation (files, the open form): asks first when configured.
    writes: bool = False
    #: Runs through the agent's ``executor`` (the designer uses it to run on the UI thread).
    ui: bool = False
    #: The short text shown in the UI while it runs ("Reading the form"...).
    title: str = ""

    @property
    def spec(self) -> llm.ToolSpec:
        return llm.ToolSpec(self.name, self.description, self.schema)

    def validate(self, args: Any) -> Optional[str]:
        """Why ``args`` do not fit the schema, or ``None`` when they do."""
        if not isinstance(args, dict):
            return "the input must be a JSON object"
        if "INVALID_JSON" in args:
            return "the input was not valid JSON"
        props = self.schema.get("properties", {})
        for name in self.schema.get("required", ()):
            if name not in args:
                return f"missing required argument {name!r}"
        checks = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list,
                  "object": dict, "null": type(None)}
        extra = self.schema.get("additionalProperties", False) is not False
        for name, value in args.items():
            if name not in props:
                if extra:
                    continue
                return f"unknown argument {name!r}"
            expected = props[name].get("type") if isinstance(props[name], dict) else None
            kinds = [expected] if isinstance(expected, str) else list(expected or [])
            if not kinds or value is None:
                continue
            known = [k for k in kinds if k in checks]
            if len(known) < len(kinds):
                continue  # a type we do not check
            if not any(isinstance(value, checks[k]) and not (k in ("integer", "number") and isinstance(value, bool))
                       for k in known):
                return f"{name!r} must be of type {' or '.join(kinds)}"
        return None


def _doc_parts(func: Callable[..., Any]) -> "tuple[str, Dict[str, str]]":
    doc = inspect.getdoc(func) or ""
    summary, _, rest = doc.partition("\n\n")
    params: Dict[str, str] = {}
    current = None
    for line in rest.splitlines():
        stripped = line.strip()
        if ":" in stripped and not line.startswith("        ") and stripped.split(":")[0].isidentifier():
            current, text = (s.strip() for s in stripped.split(":", 1))
            params[current] = text
        elif current and stripped:
            params[current] += " " + stripped
    return summary.replace("\n", " ").strip(), params


def _json_type(annotation: Any) -> Dict[str, Any]:
    origin = getattr(annotation, "__origin__", None)
    if origin is Union:
        args = [a for a in annotation.__args__ if a is not type(None)]
        return _json_type(args[0]) if len(args) == 1 else {}
    if origin in (list, List, Sequence):
        return {"type": "array"}
    if origin in (dict, Dict):
        return {"type": "object"}
    return {"type": _JSON_TYPES[annotation]} if annotation in _JSON_TYPES else {}


def tool(func: Optional[Callable[..., Any]] = None, *, name: Optional[str] = None, writes: bool = False,
         ui: bool = False, title: str = "") -> Any:
    """Turns a function into a ``Tool``; the JSON schema comes from its signature and docstring.

    The docstring's first paragraph describes the tool; ``name: text`` lines after it describe the
    arguments. Arguments with a default are optional.
    """

    def make(fn: Callable[..., Any]) -> Tool:
        summary, docs = _doc_parts(fn)
        try:
            hints = get_type_hints(fn)
        except Exception:  # noqa: BLE001 - unresolved annotations: no types
            hints = {}
        props: Dict[str, Any] = {}
        required: List[str] = []
        for param in inspect.signature(fn).parameters.values():
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue
            schema = dict(_json_type(hints.get(param.name, str)))
            if param.name in docs:
                schema["description"] = docs[param.name]
            props[param.name] = schema
            if param.default is inspect.Parameter.empty:
                required.append(param.name)
        schema = {"type": "object", "properties": props, "required": required}
        return Tool(name or fn.__name__, summary or fn.__name__, schema, fn, writes=writes, ui=ui, title=title)

    return make(func) if func is not None else make


@dataclass
class Event:
    """Something that happened while the agent ran.

    ``kind`` is ``"text"`` / ``"thinking"`` (``text`` holds the new piece), ``"tool_call"`` (``tool``,
    ``args``, ``call_id``), ``"tool_result"`` (adds ``result`` and ``error``), ``"turn"`` (a model answer
    finished; ``usage``), ``"error"`` (``text``) or ``"done"``.
    """

    kind: str
    text: str = ""
    tool: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    call_id: str = ""
    result: str = ""
    error: bool = False
    usage: Dict[str, int] = field(default_factory=dict)


PROFILES = {
    "write": "May read and change the open form, its code and files in the project.",
    "ask": "Reads only: answers questions and suggests code without changing anything.",
    "minimal": "No tools: a plain conversation with the model.",
}


class Agent:
    """A conversation with a model that can call tools."""

    def __init__(self, model: Optional[str] = None, *, tools: Sequence[Tool] = (), system: str = "",
                 settings: Optional[_providers.AgentSettings] = None,
                 confirm: Optional[Callable[[Tool, Dict[str, Any]], bool]] = None,
                 executor: Optional[Callable[[Callable[[], Any]], Any]] = None,
                 messages: Optional[List[Dict[str, Any]]] = None, max_turns: int = 40,
                 stream: Callable[..., llm.Turn] = llm.stream_turn) -> None:
        self.settings = settings or _providers.load()
        self.model = model or self.settings.model
        self.tools: Dict[str, Tool] = {t.name: t for t in tools}
        self.system = system
        self.confirm = confirm
        self.executor = executor
        self.messages: List[Dict[str, Any]] = messages if messages is not None else []
        self.max_turns = max_turns
        self.usage: Dict[str, int] = {"input": 0, "output": 0}
        self._stream = stream
        self._cancel = threading.Event()
        self.running = False

    # -- tools ------------------------------------------------------------------------------------
    def active_tools(self) -> List[Tool]:
        """The tools the current profile allows (``"ask"`` keeps the read-only ones)."""
        profile = self.settings.profile
        if profile == "minimal":
            return []
        return [t for t in self.tools.values() if profile == "write" or not t.writes]

    def _system(self) -> str:
        rules = self.settings.rules.strip()
        return self.system + (f"\n\nThe user's rules:\n{rules}" if rules else "")

    def _call(self, block: Dict[str, Any], on_event: Callable[[Event], None]) -> Dict[str, Any]:
        name, args, call_id = block.get("name", ""), block.get("input") or {}, block.get("id", "")
        images: List[Dict[str, Any]] = []
        on_event(Event("tool_call", tool=name, args=args if isinstance(args, dict) else {}, call_id=call_id))
        tool_ = self.tools.get(name)
        allowed = {t.name for t in self.active_tools()}
        if tool_ is None or name not in allowed:
            result, error = f"No tool named {name!r} is available.", True
        elif (problem := tool_.validate(args)) is not None:
            result, error = json.dumps({"INVALID_INPUT": problem, "received": args}, default=str), True
        elif tool_.writes and self.settings.confirm_writes and self.confirm is None:
            # Nobody can be asked, so writing is refused rather than allowed silently.
            result, error = "This action needs the user's confirmation, and nobody can be asked.", True
        elif tool_.writes and self.settings.confirm_writes and not self.confirm(tool_, args):
            result, error = "The user did not allow this action.", True
        elif self._cancel.is_set():
            result, error = "Cancelled by the user.", True
        else:
            try:
                work = lambda: tool_.func(**args)  # noqa: E731
                value = self.executor(work) if tool_.ui and self.executor is not None else work()
                parts = list(value) if isinstance(value, (list, tuple)) and any(isinstance(v, Image) for v in value) \
                    else [value]
                images = [v.block() for v in parts if isinstance(v, Image)]
                rest = [v for v in parts if not isinstance(v, Image)]
                if images:
                    rest = rest[0] if len(rest) == 1 else rest or "The image is attached."
                else:
                    rest = value
                result = rest if isinstance(rest, str) else json.dumps(rest, indent=1, ensure_ascii=False,
                                                                       default=str)
                error = False
            except Exception as err:  # noqa: BLE001 - the model sees the error and can fix its call
                result, error = f"{type(err).__name__}: {err}", True
                if not isinstance(err, (ValueError, KeyError, FileNotFoundError, PermissionError, TypeError)):
                    result += "\n" + traceback.format_exc(limit=3)
        if len(result) > RESULT_LIMIT:
            result = result[:RESULT_LIMIT] + f"\n… ({len(result) - RESULT_LIMIT} more characters cut)"
        on_event(Event("tool_result", tool=name, args=args if isinstance(args, dict) else {}, call_id=call_id,
                       result=result, error=error))
        if not error and images:
            return {"type": "tool_result", "tool_use_id": call_id, "is_error": False,
                    "content": [{"type": "text", "text": result}, *images]}
        return {"type": "tool_result", "tool_use_id": call_id, "content": result, "is_error": error}

    # -- running ----------------------------------------------------------------------------------
    def stop(self) -> None:
        """Cancels the run (the current answer stops streaming and no more tools run)."""
        self._cancel.set()

    def run(self, prompt: Union[str, List[Dict[str, Any]]], *, on_event: Optional[Callable[[Event], None]] = None) -> str:
        """Sends ``prompt`` and lets the model work until it answers; returns its last text.

        Errors are reported as an ``"error"`` event and returned text; nothing raises.
        """
        emit = on_event or (lambda e: None)
        self._cancel.clear()
        self.running = True
        content = [{"type": "text", "text": prompt}] if isinstance(prompt, str) else prompt
        self.messages.append({"role": "user", "content": content})
        provider_id, _ = _providers.split_model(self.model)
        last = ""
        try:
            for _ in range(self.max_turns):
                turn = self._stream(self.model, self._system(), self.messages, [t.spec for t in self.active_tools()],
                                    settings=self.settings, cancel=self._cancel,
                                    on_event=lambda kind, text: emit(Event(kind, text)))
                for key, value in turn.usage.items():
                    self.usage[key] = self.usage.get(key, 0) + value
                blocks = turn.content
                if turn.stop_reason in ("refusal", "cancelled"):
                    blocks = [b for b in blocks if b.get("type") != "tool_use"]  # never leave a call unanswered
                self.messages.append({"role": "assistant", "content": blocks, "provider": provider_id,
                                      "model": turn.model or self.model})
                last = turn.text or last
                emit(Event("turn", usage=dict(turn.usage)))
                if turn.stop_reason == "cancelled":
                    emit(Event("error", "Stopped."))
                    break
                if turn.stop_reason == "refusal":
                    emit(Event("error", "The model declined to continue with this request."))
                    break
                if not turn.tool_uses:
                    if turn.stop_reason == "max_tokens":
                        emit(Event("error", "The answer was cut off at the output limit."))
                    break
                if turn.stop_reason == "max_tokens":  # a tool input may be cut: run nothing, let it retry
                    results = [{"type": "tool_result", "tool_use_id": b["id"], "is_error": True,
                                "content": "Your output was cut off at the token limit before this call was "
                                           "complete. Retry with smaller pieces."} for b in turn.tool_uses]
                else:
                    results = [self._call(b, emit) for b in turn.tool_uses]
                self.messages.append({"role": "user", "content": results})
                if self._cancel.is_set():
                    emit(Event("error", "Stopped."))
                    break
            else:
                emit(Event("error", f"Stopped after {self.max_turns} steps."))
        except llm.AgentError as err:
            emit(Event("error", str(err)))
            last = str(err)
        except Exception as err:  # noqa: BLE001 - never kill the caller's thread
            emit(Event("error", f"{type(err).__name__}: {err}"))
            last = str(err)
        finally:
            self.running = False
            emit(Event("done"))
        return last
