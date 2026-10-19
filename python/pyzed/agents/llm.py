"""Streaming chat with tools, for every provider.

A conversation is kept in one neutral shape, close to Anthropic's: a list of ``{"role", "content"}``
messages whose content is a list of blocks (``text``, ``tool_use``, ``tool_result``, plus whatever the
provider returned, such as Claude's ``thinking`` blocks). Assistant messages remember the provider
that wrote them, so Claude gets its own blocks back unchanged and OpenAI-compatible servers get the
same conversation converted to their format.

``stream_turn`` sends one request and calls ``on_event(kind, text)`` with ``"text"`` and ``"thinking"``
deltas as they arrive; it returns the finished ``Turn``.
"""

from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from . import providers as _providers

OnEvent = Callable[[str, str], None]
#: Output budget of one turn (streamed, so long answers do not time out).
MAX_TOKENS = 64000


class AgentError(RuntimeError):
    """A request failed (bad key, no network, rate limit, refused by the server...)."""


@dataclass
class Turn:
    """One answer of the model."""

    #: Blocks in the neutral shape (Claude's are kept exactly as the API returned them).
    content: List[Dict[str, Any]] = field(default_factory=list)
    #: ``"end_turn"``, ``"tool_use"``, ``"max_tokens"``, ``"refusal"`` or ``"cancelled"``.
    stop_reason: str = "end_turn"
    usage: Dict[str, int] = field(default_factory=dict)
    #: The model that actually answered (it can differ after a refusal fallback).
    model: str = ""

    @property
    def text(self) -> str:
        return "".join(b.get("text", "") for b in self.content if b.get("type") == "text")

    @property
    def tool_uses(self) -> List[Dict[str, Any]]:
        return [b for b in self.content if b.get("type") == "tool_use"]


@dataclass(frozen=True)
class ToolSpec:
    """What the model is told about a tool."""

    name: str
    description: str
    schema: Dict[str, Any]


# -- Anthropic ----------------------------------------------------------------------------------

_OLD_CLAUDE = re.compile(r"claude-(3|instant|2)|claude-(opus|sonnet|haiku)-4-[0-5]\b|claude-(opus|sonnet|haiku)-4$")
#: Models that take the server-side refusal fallback on the Claude API.
_FALLBACK_MODELS = ("claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5")


def _adaptive(model: str) -> bool:
    """Whether ``model`` takes adaptive thinking and effort (every current Claude model)."""
    return not _OLD_CLAUDE.search(model)


def _anthropic_client(provider_id: str, settings: _providers.AgentSettings, key: Optional[str]) -> Any:
    try:
        import anthropic
    except ImportError as err:
        raise AgentError('Claude needs the anthropic package: pip install "pyzed-ui[agents]"') from err
    kwargs: Dict[str, Any] = {"max_retries": 2}
    if key:
        kwargs["api_key"] = key
    own = settings.providers.get(provider_id)
    if own and own.base_url:
        kwargs["base_url"] = own.base_url
    try:
        return anthropic.Anthropic(**kwargs)  # no key: the SDK reads an `ant auth login` profile
    except anthropic.AnthropicError as err:
        raise AgentError("Anthropic is not set up: add an API key or sign in with the browser") from err


def _anthropic_messages(messages: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for m in messages:
        content = m["content"]
        if m["role"] == "assistant" and m.get("provider") != "anthropic":
            content = [b for b in content if b.get("type") in ("text", "tool_use")]
        out.append({"role": m["role"], "content": content})
    return out


def _anthropic_error(err: Exception) -> AgentError:
    import anthropic

    if isinstance(err, anthropic.AuthenticationError):
        return AgentError("Anthropic did not accept the credentials: check the API key or sign in again")
    if isinstance(err, anthropic.PermissionDeniedError):
        return AgentError("This key is not allowed to use that model")
    if isinstance(err, anthropic.NotFoundError):
        return AgentError("Anthropic does not know that model")
    if isinstance(err, anthropic.RateLimitError):
        return AgentError("Rate limited by Anthropic; try again in a moment")
    if isinstance(err, anthropic.APIStatusError):
        return AgentError(f"Anthropic error {err.status_code}: {getattr(err, 'message', err)}")
    if isinstance(err, anthropic.APIConnectionError):
        return AgentError("Could not reach Anthropic; check the network")
    return AgentError(str(err))


def _stream_anthropic(provider_id: str, model: str, system: str, messages: Sequence[Dict[str, Any]],
                      tools: Sequence[ToolSpec], settings: _providers.AgentSettings, key: Optional[str],
                      on_event: OnEvent, cancel: threading.Event) -> Turn:
    import anthropic

    client = _anthropic_client(provider_id, settings, key)
    params: Dict[str, Any] = {
        "model": model, "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        "messages": _anthropic_messages(messages),
    }
    if tools:
        # Inputs (whole files, forms) stream as they are written; the agent validates them before running.
        params["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.schema,
                            "eager_input_streaming": True} for t in tools]
    if _adaptive(model):
        params["thinking"] = {"type": "adaptive", "display": "summarized"}
        params["output_config"] = {"effort": settings.effort}
    betas: List[str] = []
    own = settings.providers.get(provider_id)
    if model in _FALLBACK_MODELS and not (own and own.base_url):
        # When the model declines, the API answers with the right fallback model in the same call.
        betas.append("server-side-fallback-2026-07-01")
        params["fallbacks"] = "default"
    if settings.fast and model in _providers.FAST_MODELS and not (own and own.base_url):
        # Fast mode: faster output at a higher price, on the Claude API only.
        betas.append("fast-mode-2026-02-01")
        params["speed"] = "fast"
    stream_fn = client.beta.messages.stream if betas else client.messages.stream
    if betas:
        params["betas"] = betas
    cancelled = False
    try:
        with stream_fn(**params) as stream:
            for event in stream:
                if cancel.is_set():
                    cancelled = True
                    break
                if event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        on_event("text", delta.text)
                    elif delta.type == "thinking_delta" and delta.thinking:
                        on_event("thinking", delta.thinking)
            if cancelled:
                snapshot = stream.current_message_snapshot
                content = [b for b in snapshot.to_dict().get("content", []) if b.get("type") == "text"]
                return Turn(content, "cancelled", model=model)
            final = stream.get_final_message()
    except ValueError as err:  # a tool input that is not JSON at all (eager input streaming)
        raise AgentError(f"The model sent a tool call that could not be read ({err}); try again") from err
    except anthropic.AnthropicError as err:
        raise _anthropic_error(err) from err
    data = final.to_dict()
    usage = data.get("usage") or {}
    return Turn(list(data.get("content") or []), str(data.get("stop_reason") or "end_turn"),
                {"input": int(usage.get("input_tokens") or 0), "output": int(usage.get("output_tokens") or 0),
                 "cache_read": int(usage.get("cache_read_input_tokens") or 0)},
                model=str(data.get("model") or model))


# -- OpenAI-compatible --------------------------------------------------------------------------

def _openai_messages(system: str, messages: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = [{"role": "system", "content": system}] if system else []
    for m in messages:
        blocks = m["content"]
        if m["role"] == "user":
            results = [b for b in blocks if b.get("type") == "tool_result"]
            for b in results:
                out.append({"role": "tool", "tool_call_id": b["tool_use_id"], "content": _result_text(b)})
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            if text or not results:
                out.append({"role": "user", "content": text})
        else:
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            calls = [{"id": b["id"], "type": "function",
                      "function": {"name": b["name"], "arguments": json.dumps(b.get("input") or {})}}
                     for b in blocks if b.get("type") == "tool_use"]
            msg: Dict[str, Any] = {"role": "assistant", "content": text or None}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
    return out


def _result_text(block: Dict[str, Any]) -> str:
    content = block.get("content")
    if isinstance(content, list):
        return "".join(c.get("text", "") for c in content if isinstance(c, dict))
    return str(content or "")


def _headers(provider_id: str, key: Optional[str]) -> Dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if provider_id == "openrouter":
        headers["HTTP-Referer"] = "https://albakore.github.io/pyzed/"
        headers["X-Title"] = "Pyzed"
    return headers


def _http_error(provider_id: str, err: urllib.error.HTTPError) -> AgentError:
    name = _providers.PROVIDERS[provider_id].name
    try:
        body = json.loads(err.read().decode() or "{}")
        detail = body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else body.get("error")
    except (ValueError, OSError, AttributeError):
        detail = None
    if err.code in (401, 403):
        return AgentError(f"{name} did not accept the key{f': {detail}' if detail else ''}")
    if err.code == 429:
        return AgentError(f"Rate limited by {name}; try again in a moment")
    return AgentError(f"{name} error {err.code}{f': {detail}' if detail else ''}")


def parse_sse(lines, on_event: OnEvent, cancel: threading.Event) -> Turn:
    """Builds a ``Turn`` from the lines of an OpenAI-compatible event stream."""
    text: List[str] = []
    calls: Dict[int, Dict[str, Any]] = {}
    finish = ""
    usage: Dict[str, int] = {}
    model = ""
    for raw in lines:
        if cancel.is_set():
            finish = "cancelled"
            break
        line = raw.decode("utf-8", "replace").strip() if isinstance(raw, bytes) else raw.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
        except ValueError:
            continue
        if chunk.get("error"):
            message = chunk["error"].get("message") if isinstance(chunk["error"], dict) else chunk["error"]
            raise AgentError(str(message))
        model = chunk.get("model") or model
        if chunk.get("usage"):
            u = chunk["usage"]
            usage = {"input": int(u.get("prompt_tokens") or 0), "output": int(u.get("completion_tokens") or 0)}
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            thinking = delta.get("reasoning_content") or delta.get("reasoning")
            if isinstance(thinking, str) and thinking:
                on_event("thinking", thinking)
            if delta.get("content"):
                text.append(delta["content"])
                on_event("text", delta["content"])
            for call in delta.get("tool_calls") or []:
                slot = calls.setdefault(int(call.get("index", len(calls))), {"id": "", "name": "", "arguments": ""})
                slot["id"] = call.get("id") or slot["id"]
                fn = call.get("function") or {}
                slot["name"] += fn.get("name") or ""
                slot["arguments"] += fn.get("arguments") or ""
            finish = choice.get("finish_reason") or finish
    content: List[Dict[str, Any]] = [{"type": "text", "text": "".join(text)}] if text else []
    for index in sorted(calls):
        call = calls[index]
        try:
            args = json.loads(call["arguments"] or "{}")
        except ValueError:
            args = {"INVALID_JSON": call["arguments"]}
        content.append({"type": "tool_use", "id": call["id"] or f"call_{index}", "name": call["name"],
                        "input": args if isinstance(args, dict) else {"value": args}})
    stop = {"tool_calls": "tool_use", "length": "max_tokens", "content_filter": "refusal",
            "cancelled": "cancelled"}.get(finish, "tool_use" if calls else "end_turn")
    if stop == "cancelled":
        content = [b for b in content if b["type"] == "text"]
    return Turn(content, stop, usage, model)


def _stream_openai(provider_id: str, model: str, system: str, messages: Sequence[Dict[str, Any]],
                   tools: Sequence[ToolSpec], settings: _providers.AgentSettings, key: Optional[str],
                   on_event: OnEvent, cancel: threading.Event) -> Turn:
    base = settings.base_url(provider_id)
    if not base:
        raise AgentError("Set the server's base URL in Settings → AI agents")
    body: Dict[str, Any] = {"model": model, "stream": True, "messages": _openai_messages(system, messages),
                            "stream_options": {"include_usage": True}}
    if tools:
        body["tools"] = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                                           "parameters": t.schema}} for t in tools]
    request = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(body).encode(),
                                     headers=_headers(provider_id, key), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return parse_sse(response, on_event, cancel)
    except urllib.error.HTTPError as err:
        raise _http_error(provider_id, err) from err
    except OSError as err:
        raise AgentError(f"Could not reach {base}: {getattr(err, 'reason', err)}") from err


# -- entry points -------------------------------------------------------------------------------

def stream_turn(model: str, system: str, messages: Sequence[Dict[str, Any]], tools: Sequence[ToolSpec] = (), *,
                settings: Optional[_providers.AgentSettings] = None, on_event: Optional[OnEvent] = None,
                cancel: Optional[threading.Event] = None, key: Optional[str] = None) -> Turn:
    """Sends the conversation to ``model`` (``"provider:model"``) and streams the answer."""
    settings = settings or _providers.load()
    provider_id, name = _providers.split_model(model)
    provider = _providers.PROVIDERS[provider_id]
    key = key if key is not None else _providers.api_key(provider_id)
    if provider.needs_key and not key and not (provider_id == "anthropic" and _providers.credential_source(provider_id)):
        raise AgentError(f"{provider.name} is not set up: add a key in Settings → AI agents")
    fn = _stream_anthropic if provider.protocol == "anthropic" else _stream_openai
    turn = fn(provider_id, name, system, messages, tools, settings, key, on_event or (lambda k, t: None),
              cancel or threading.Event())
    return turn


def list_models(provider_id: str, settings: Optional[_providers.AgentSettings] = None,
                key: Optional[str] = None) -> List[str]:
    """Asks the provider which models it offers (sorted names, without the provider prefix)."""
    settings = settings or _providers.load()
    provider = _providers.PROVIDERS[provider_id]
    key = key if key is not None else _providers.api_key(provider_id)
    if provider.protocol == "anthropic":
        import anthropic

        client = _anthropic_client(provider_id, settings, key)
        try:
            return sorted(m.id for m in client.models.list(limit=100))
        except anthropic.AnthropicError as err:
            raise _anthropic_error(err) from err
    base = settings.base_url(provider_id)
    if not base:
        raise AgentError("Set the server's base URL first")
    request = urllib.request.Request(f"{base}/models", headers=_headers(provider_id, key))
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as err:
        raise _http_error(provider_id, err) from err
    except (OSError, ValueError) as err:
        raise AgentError(f"Could not reach {base}: {getattr(err, 'reason', err)}") from err
    items = data.get("data") or data.get("models") or []
    names = [str(m.get("id") or m.get("name") or "") for m in items if isinstance(m, dict)]
    return sorted(n.removeprefix("models/") for n in names if n)
