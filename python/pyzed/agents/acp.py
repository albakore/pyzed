"""External agents through the Agent Client Protocol (ACP), like Zed's: Claude Code, Gemini CLI, Codex or
any agent that speaks ACP runs as a program, and Pyzed is its client: it shows what the agent writes and
does, answers its permission requests and reads and writes files for it, never outside the project.

    from pyzed.agents import acp, providers

    config = providers.ACPAgentConfig("gemini", "gemini", ["--experimental-acp"])
    agent = acp.ACPAgent(config, cwd="my-project")
    print(agent.run("Explain this project"))
    agent.close()

``ACPAgent`` has the same shape as ``pyzed.agents.Agent`` (``run``, ``stop``, ``messages`` and the same
events), so the designer's Agent panel shows both alike. Pyzed's own MCP server (components, docs,
generators, checks) and the MCP servers of the settings are handed to the agent, so it knows Pyzed.
"""

from __future__ import annotations

import fnmatch
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from . import mcp_client
from . import providers as _providers
from . import secrets as _secrets
from .agent import Event, Tool
from .tools import SECRET_FILES

PROTOCOL_VERSION = 1

#: Ready-made external agents: name -> (title, command, args). They need the program installed
#: (``npx`` comes with Node.js); the adapter packages are the ones Zed uses.
PRESETS: Dict[str, "tuple[str, str, List[str]]"] = {
    "claude-code": ("Claude Code", "npx", ["-y", "@zed-industries/claude-code-acp"]),
    "gemini": ("Gemini CLI", "gemini", ["--experimental-acp"]),
    "codex": ("Codex", "npx", ["-y", "@zed-industries/codex-acp"]),
}

#: What each permission mode lets an external agent do without asking (ACP tool kinds).
_READ_KINDS = ("read", "search", "think", "fetch")


def preset(name: str) -> _providers.ACPAgentConfig:
    """The settings entry of a ready-made agent (``"claude-code"``, ``"gemini"`` or ``"codex"``)."""
    title, command, args = PRESETS[name]
    return _providers.ACPAgentConfig(name, command, list(args), title=title)


def claude_signed_in() -> bool:
    """Whether Claude Code is signed in on this computer (with a Claude subscription, or a key it is given), so
    the ``claude-code`` agent can answer. Claude Code keeps its sign-in in ``~/.claude`` (or the macOS keychain)."""
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"):
        return True
    folder = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    if (folder / ".credentials.json").is_file():
        return True
    if sys.platform == "darwin":
        try:
            found = subprocess.run(["security", "find-generic-password", "-s", "Claude Code-credentials"],
                                   capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return False
        return found.returncode == 0
    return False


def claude_login_command() -> List[str]:
    """The command that opens Claude Code in a terminal, where it asks to sign in with a Claude account (Pro or
    Max) the first time; ``npx`` downloads it when it is not installed."""
    claude = shutil.which("claude")
    return [claude] if claude else ["npx", "-y", "@anthropic-ai/claude-code"]


def installed(config: _providers.ACPAgentConfig) -> bool:
    """Whether the agent's program can be found."""
    return shutil.which(config.command) is not None or Path(config.command).is_file()


def pyzed_mcp_server() -> Optional[Dict[str, Any]]:
    """Pyzed's MCP server as an ACP ``mcpServers`` entry (``None`` when the MCP SDK is not installed)."""
    try:
        import mcp  # noqa: F401
    except ImportError:
        return None
    return {"name": "pyzed", "command": sys.executable, "args": ["-m", "pyzed", "mcp"], "env": []}


def mcp_entries(configs: Sequence[_providers.MCPServerConfig],
                store: Optional[_secrets.SecretStore] = None) -> List[Dict[str, Any]]:
    """The settings' MCP servers in ACP's shape, with their secrets from the keychain."""
    out: List[Dict[str, Any]] = []
    for c in configs:
        if not c.enabled:
            continue
        values = [{"name": k, "value": v} for k, v in mcp_client.get_secrets(c.name, store).items()]
        if c.url:
            out.append({"type": "http", "name": c.name, "url": c.url, "headers": values})
        else:
            out.append({"name": c.name, "command": c.command, "args": list(c.args), "env": values})
    return out


class ACPError(RuntimeError):
    """The agent could not start or answered with an error."""


class AuthRequired(ACPError):
    """The agent wants a sign-in before it opens a session; ``methods`` are its ways to sign in (ACP
    ``authMethods``: dicts with ``id``, ``name``, ``description`` and, for some, ``type``)."""

    def __init__(self, label: str, methods: List[Dict[str, Any]]) -> None:
        super().__init__(f"{label} needs you to sign in")
        self.methods = methods


def auth_kind(method: Dict[str, Any]) -> str:
    """How a way to sign in works, as in Zed: ``"agent"`` (the agent signs in by itself, usually opening the
    browser and waiting for its page to come back), ``"terminal"`` (the agent's program runs in a terminal
    with extra arguments, for example Claude Code's login) or ``"env_var"`` (a key in a variable)."""
    kind = str(method.get("type") or "")
    if kind in ("terminal", "env_var"):
        return kind
    if isinstance((method.get("_meta") or {}).get("terminal-auth"), dict):
        return "terminal"
    return "agent"


def terminal_login(config: _providers.ACPAgentConfig, method: Dict[str, Any]) -> "tuple[List[str], Dict[str, str]]":
    """The command (and extra environment) a ``"terminal"`` way to sign in runs in a terminal: the agent's own
    program with the method's arguments, or the command the method names in ``_meta["terminal-auth"]``."""
    meta = (method.get("_meta") or {}).get("terminal-auth")
    if isinstance(meta, dict) and meta.get("command"):
        command, args, env = str(meta["command"]), list(meta.get("args") or []), meta.get("env") or {}
    else:
        command, args, env = config.command, [*config.args, *(method.get("args") or [])], method.get("env") or {}
    if isinstance(env, list):  # [{"name": ..., "value": ...}], like an MCP server's
        env = {str(e.get("name")): str(e.get("value", "")) for e in env if isinstance(e, dict)}
    return [command, *map(str, args)], {str(k): str(v) for k, v in dict(env).items()}


def _auth_error(err: Exception) -> bool:
    text = str(err).lower()
    return "auth" in text or "-32000" in text or "/login" in text or "sign in" in text


def _blocks(content: Union[str, List[Dict[str, Any]]], images: bool) -> List[Dict[str, Any]]:
    """A message in Pyzed's shape as ACP content blocks."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    out: List[Dict[str, Any]] = []
    for b in content:
        if b.get("type") == "text":
            out.append({"type": "text", "text": b.get("text", "")})
        elif b.get("type") == "image":
            source = b.get("source") or {}
            if images:
                out.append({"type": "image", "mimeType": source.get("media_type", "image/png"),
                            "data": source.get("data", "")})
            else:
                out.append({"type": "text", "text": "[An image was attached, but this agent does not take images.]"})
    return out


def _text_of(content: Any) -> str:
    """The text of an ACP content block or tool call content list."""
    if isinstance(content, dict):
        if content.get("type") == "text":
            return str(content.get("text") or "")
        if content.get("type") == "content":
            return _text_of(content.get("content"))
        if content.get("type") == "diff":
            old, new = str(content.get("oldText") or "").splitlines(), str(content.get("newText") or "").splitlines()
            return f"Edited {content.get('path', '')} (+{max(len(new) - len(old), 0)} lines)" if old else \
                f"Wrote {content.get('path', '')} ({len(new)} lines)"
        if content.get("type") == "terminal":
            return ""
        if content.get("type") in ("resource", "resource_link"):
            res = content.get("resource") or content
            return str(res.get("text") or res.get("uri") or "")
        return ""
    if isinstance(content, list):
        return "\n".join(t for t in (_text_of(c) for c in content) if t)
    return ""


def _describe(block: Dict[str, Any], update: Dict[str, Any]) -> None:
    """Keeps what a tool call update tells about the call on its block: the files it works on
    (``locations``), the edits it made (``diffs``: path, old and new text) and its terminal output."""
    paths = [str(loc["path"]) for loc in update.get("locations") or [] if isinstance(loc, dict) and loc.get("path")]
    if paths:
        block["locations"] = paths[:20]
    diffs = [{"path": str(c.get("path") or ""), "old": str(c.get("oldText") or "")[:20_000],
              "new": str(c.get("newText") or "")[:20_000]}
             for c in update.get("content") or [] if isinstance(c, dict) and c.get("type") == "diff"]
    if diffs:
        block["diffs"] = diffs[:10]
    text = _text_of([c for c in update.get("content") or [] if isinstance(c, dict) and c.get("type") != "diff"])
    if text:
        block["progress"] = text[-4000:]


def session_options(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The options an agent offers for its session, from ``session/new`` (or a ``configOptions`` update), in
    one shape: ``{"id", "name", "category", "current", "via", "choices": [{"value", "name", "description"}]}``.
    ``category`` is ACP's (``"mode"``, ``"model"``, ``"thought_level"``...); ``via`` says how it is changed:
    ``"config"`` (session config options), ``"mode"`` (session modes) or ``"model"`` (session models)."""
    out: List[Dict[str, Any]] = []
    config = result.get("configOptions")
    if isinstance(config, list) and config:
        for item in config:
            if not isinstance(item, dict) or item.get("type", "select") != "select" or not item.get("id"):
                continue
            choices: List[Dict[str, str]] = []
            for entry in item.get("options") or []:
                if not isinstance(entry, dict):
                    continue
                group = entry.get("options") if isinstance(entry.get("options"), list) else [entry]  # grouped
                choices += [{"value": str(c.get("value")), "name": str(c.get("name") or c.get("value")),
                             "description": str(c.get("description") or "")}
                            for c in group if isinstance(c, dict) and c.get("value") is not None]
            if choices:
                out.append({"id": str(item["id"]), "name": str(item.get("name") or item["id"]),
                            "category": str(item.get("category") or ""), "via": "config",
                            "current": str(item.get("currentValue") or choices[0]["value"]), "choices": choices})
        return out
    modes = result.get("modes")
    if isinstance(modes, dict) and modes.get("availableModes"):
        choices = [{"value": str(m.get("id")), "name": str(m.get("name") or m.get("id")),
                    "description": str(m.get("description") or "")}
                   for m in modes["availableModes"] if isinstance(m, dict) and m.get("id")]
        if choices:
            out.append({"id": "mode", "name": "Mode", "category": "mode", "via": "mode", "choices": choices,
                        "current": str(modes.get("currentModeId") or choices[0]["value"])})
    models = result.get("models")
    if isinstance(models, dict) and models.get("availableModels"):
        choices = [{"value": str(m.get("modelId")), "name": str(m.get("name") or m.get("modelId")),
                    "description": str(m.get("description") or "")}
                   for m in models["availableModels"] if isinstance(m, dict) and m.get("modelId")]
        if choices:
            out.append({"id": "model", "name": "Model", "category": "model", "via": "model", "choices": choices,
                        "current": str(models.get("currentModelId") or choices[0]["value"])})
    return out


class ACPAgent:
    """A conversation with an external agent (one ACP session, started on the first ``run``)."""

    def __init__(self, config: _providers.ACPAgentConfig, *, cwd: Union[str, Path],
                 settings: Optional[_providers.AgentSettings] = None,
                 confirm: Optional[Callable[[Tool, Dict[str, Any]], bool]] = None,
                 messages: Optional[List[Dict[str, Any]]] = None, mcp_servers: Optional[List[Dict[str, Any]]] = None,
                 store: Optional[_secrets.SecretStore] = None) -> None:
        self.config = config
        self.root = Path(cwd).resolve()
        self.settings = settings or _providers.load()
        self.confirm = confirm
        self.messages: List[Dict[str, Any]] = messages if messages is not None else []
        self.model = f"acp:{config.name}"
        self.usage: Dict[str, int] = {"input": 0, "output": 0}
        self.running = False
        if mcp_servers is None:
            mcp_servers = mcp_entries(self.settings.mcp_servers, store)
            own = pyzed_mcp_server() if self.settings.share_pyzed_mcp else None
            if own is not None:
                mcp_servers.insert(0, own)
        self.mcp_servers = mcp_servers
        self._store = store
        self._rpc: Optional[mcp_client.JsonRpcProcess] = None
        self.session: Optional[str] = None
        self.capabilities: Dict[str, Any] = {}
        self.auth_methods: List[Dict[str, Any]] = []
        self._emit: Callable[[Event], None] = lambda e: None
        self._lock = threading.Lock()
        self._blocks: List[Dict[str, Any]] = []
        self._results: List[Dict[str, Any]] = []
        self._calls: Dict[str, Dict[str, Any]] = {}
        #: The agent's own options for the session (its modes, models, effort...), as ``Option`` lists; empty
        #: until the session opens (``start``).
        self.options: List[Dict[str, Any]] = []
        #: Values to pick for ``options`` when a session opens, by option id (what the user picked last time).
        self.preferred: Dict[str, str] = dict(self.settings.agent_options.get(config.name) or {})
        self._start_lock = threading.Lock()

    # -- the connection ---------------------------------------------------------------------------
    def start(self) -> None:
        """Starts the program and opens a session (done by the first ``run``). Raises ``AuthRequired`` when
        the agent wants a sign-in first."""
        with self._start_lock:  # the panel may open the session ahead of the first message
            if self._rpc is not None and self._rpc.alive and self.session:
                return
            self._connect()
            try:
                self.session = self._new_session()
            except AuthRequired:
                raise
            except (ACPError, mcp_client.MCPError) as err:
                self.close()
                raise ACPError(f"{self.config.label}: {err}") from err
            self._apply_preferred()

    def _apply_preferred(self) -> None:
        """Picks the values of ``preferred`` the new session offers and does not have yet (never raises)."""
        for option in list(self.options):
            value = self.preferred.get(option["id"])
            if value and value != option["current"] and any(c["value"] == value for c in option["choices"]):
                try:
                    self.set_option(option["id"], value)
                except ACPError:
                    continue

    def _connect(self) -> None:
        """Starts the program and introduces Pyzed (``initialize``), once."""
        if self._rpc is not None and self._rpc.alive:
            return
        from .. import _platform

        hidden = mcp_client.get_secrets(f"acp.{self.config.name}", self._store)
        try:
            # under WSL its sign-in page opens in Windows' browser, like Pyzed's own
            self._rpc = mcp_client.JsonRpcProcess(self.config.command, self.config.args,
                                                  env={**_platform.browser_env(), **self.config.env, **hidden},
                                                  cwd=str(self.root), on_request=self._on_request,
                                                  on_notify=self._on_notify)
        except mcp_client.MCPError as err:
            raise ACPError(f"Could not start {self.config.label}: is {self.config.command} installed? ({err})") from err
        try:
            from .mcp_client import _version

            info = self._rpc.request("initialize", {
                "protocolVersion": PROTOCOL_VERSION,
                "clientCapabilities": {"fs": {"readTextFile": True, "writeTextFile": True}, "terminal": False},
                "clientInfo": {"name": "Pyzed", "version": _version()}}, timeout=120) or {}
            self.capabilities = info.get("agentCapabilities") or {}
            self.auth_methods = [m for m in info.get("authMethods") or [] if isinstance(m, dict)]
        except mcp_client.MCPError as err:
            self.close()
            raise ACPError(f"{self.config.label}: {err}") from err

    def _new_session(self) -> str:
        assert self._rpc is not None
        params = {"cwd": str(self.root), "mcpServers": self._servers()}
        try:
            result = self._rpc.request("session/new", params, timeout=120) or {}
        except mcp_client.MCPError as err:
            if not self.auth_methods or not _auth_error(err):
                raise
            raise AuthRequired(self.config.label, self.auth_methods) from err
        session = result.get("sessionId")
        if not session:
            raise ACPError(f"{self.config.label} did not open a session")
        self.options = session_options(result)
        if self.options:
            self._emit(Event("options"))
        return str(session)

    # -- the agent's options -----------------------------------------------------------------------
    def set_option(self, option_id: str, value: str) -> None:
        """Picks ``value`` for one of ``options`` (a mode, a model, the effort...), like Zed's selectors.
        Raises ``ACPError`` when the agent refuses it."""
        option = next((o for o in self.options if o["id"] == option_id), None)
        if option is None or self._rpc is None or not self.session:
            raise ACPError(f"{self.config.label} has no option {option_id!r}")
        try:
            if option["via"] == "config":
                result = self._rpc.request("session/set_config_option", {
                    "sessionId": self.session, "configId": option_id, "value": value}, timeout=60) or {}
                if isinstance(result.get("configOptions"), list):
                    self.options = session_options({"configOptions": result["configOptions"]})
                    return
            elif option["via"] == "mode":
                self._rpc.request("session/set_mode", {"sessionId": self.session, "modeId": value}, timeout=60)
            else:
                self._rpc.request("session/set_model", {"sessionId": self.session, "modelId": value}, timeout=60)
        except mcp_client.MCPError as err:
            raise ACPError(f"{self.config.label}: {err}") from err
        option["current"] = value

    def authenticate(self, method_id: str, *, timeout: float = 600) -> None:
        """Signs in with one of the agent's ``auth_methods`` (an ``"agent"`` one: the agent opens the browser
        itself and answers once the sign-in is done), then opens the session. Raises ``ACPError``."""
        try:
            self._connect()
            assert self._rpc is not None
            self._rpc.request("authenticate", {"methodId": method_id}, timeout=timeout)
            self.session = self._new_session()
            self._apply_preferred()
        except AuthRequired:
            raise ACPError(f"{self.config.label}: the sign-in did not finish") from None
        except mcp_client.MCPError as err:
            raise ACPError(f"{self.config.label}: {err}") from err

    def signed_in(self) -> bool:
        """Tries to open the session again (after a sign-in done elsewhere, such as in a terminal); whether it
        worked. Never raises."""
        try:
            self.close()
            self.start()
            return True
        except ACPError:
            return False

    def _servers(self) -> List[Dict[str, Any]]:
        """The MCP servers the agent can start. A server given twice by name (over HTTP and as a local bridge)
        goes over HTTP when the agent supports it, else through the bridge."""
        http = bool((self.capabilities.get("mcpCapabilities") or {}).get("http"))
        if not http:
            return [s for s in self.mcp_servers if s.get("type") != "http"]
        remote = {s.get("name") for s in self.mcp_servers if s.get("type") == "http"}
        return [s for s in self.mcp_servers if s.get("type") == "http" or s.get("name") not in remote]

    def close(self) -> None:
        """Stops the program."""
        if self._rpc is not None:
            self._rpc.close()
        self._rpc = None
        self.session = None

    def stop(self) -> None:
        """Cancels the current answer."""
        if self._rpc is not None and self.session:
            try:
                self._rpc.notify("session/cancel", {"sessionId": self.session})
            except mcp_client.MCPError:
                pass

    # -- running ----------------------------------------------------------------------------------
    def run(self, prompt: Union[str, List[Dict[str, Any]]], *, on_event: Optional[Callable[[Event], None]] = None) -> str:
        """Sends ``prompt`` and waits for the agent to finish; returns its last text. Never raises."""
        self._emit = on_event or (lambda e: None)
        content = [{"type": "text", "text": prompt}] if isinstance(prompt, str) else prompt
        self.messages.append({"role": "user", "content": content})
        self.running = True
        last = ""
        try:
            self.start()
            assert self._rpc is not None
            images = bool((self.capabilities.get("promptCapabilities") or {}).get("image"))
            result = self._rpc.request("session/prompt", {"sessionId": self.session,
                                                          "prompt": _blocks(content, images)}, timeout=6 * 3600) or {}
            stop = str(result.get("stopReason") or "end_turn")
            last = self._flush()
            self._emit(Event("turn"))
            if stop == "cancelled":
                self._emit(Event("error", "Stopped."))
            elif stop == "refusal":
                self._emit(Event("error", "The agent declined to continue with this request."))
            elif stop in ("max_tokens", "max_turn_requests"):
                self._emit(Event("error", "The agent stopped at its limit."))
        except AuthRequired as err:  # the message waits for the sign-in; the panel sends it again
            self._flush()
            if self.messages and self.messages[-1].get("content") is content:
                self.messages.pop()
            self._emit(Event("auth", str(err), args={"methods": err.methods, "prompt": content}))
            last = str(err)
        except (ACPError, mcp_client.MCPError) as err:
            self._flush()
            self._emit(Event("error", str(err)))
            last = str(err)
        except Exception as err:  # noqa: BLE001 - never kill the caller's thread
            self._flush()
            self._emit(Event("error", f"{type(err).__name__}: {err}"))
            last = str(err)
        finally:
            self.running = False
            self._emit(Event("done"))
        return last

    def live(self) -> "tuple[List[Dict[str, Any]], List[Dict[str, Any]]]":
        """What the agent wrote and did since the last flush, still running: copies of its blocks (text and
        tool calls, as in ``messages``) and of the results so far. The panel shows them as they happen."""
        with self._lock:
            return [dict(b) for b in self._blocks], [dict(r) for r in self._results]

    def _flush(self) -> str:
        """Adds what the agent wrote and did since the last flush to ``messages``; returns its text."""
        with self._lock:
            blocks, results = self._blocks, self._results
            self._blocks, self._results = [], []
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        if blocks:
            self.messages.append({"role": "assistant", "content": blocks, "provider": "acp", "model": self.model})
        if results:
            self.messages.append({"role": "user", "content": results})
        return text

    # -- what the agent sends ---------------------------------------------------------------------
    def _on_notify(self, method: str, params: Any) -> None:
        if method != "session/update" or not isinstance(params, dict):
            return
        update = params.get("update") or {}
        kind = update.get("sessionUpdate")
        if kind == "current_mode_update":
            for option in self.options:
                if option["via"] == "mode":
                    option["current"] = str(update.get("currentModeId") or option["current"])
            self._emit(Event("options"))
        elif kind == "config_option_update" and isinstance(update.get("configOptions"), list):
            self.options = session_options({"configOptions": update["configOptions"]})
            self._emit(Event("options"))
        elif kind in ("agent_message_chunk", "agent_thought_chunk"):
            text = _text_of(update.get("content"))
            if not text:
                return
            if kind == "agent_thought_chunk":
                self._emit(Event("thinking", text))
                return
            with self._lock:
                if self._results:  # text after tool calls starts the next assistant message
                    pending = True
                else:
                    pending = False
            if pending:
                self._flush()
            with self._lock:
                if self._blocks and self._blocks[-1].get("type") == "text":
                    self._blocks[-1]["text"] += text
                else:
                    self._blocks.append({"type": "text", "text": text})
            self._emit(Event("text", text))
        elif kind == "tool_call":
            call_id = str(update.get("toolCallId") or "")
            title = str(update.get("title") or update.get("kind") or "Tool")
            args = update.get("rawInput") if isinstance(update.get("rawInput"), dict) else {}
            block = {"type": "tool_use", "id": call_id, "name": title, "input": args, "kind": update.get("kind")}
            _describe(block, update)
            with self._lock:
                self._blocks.append(block)
                self._calls[call_id] = block
            self._emit(Event("tool_call", tool=title, args=args, call_id=call_id))
            self._follow(update)
            if update.get("status") in ("completed", "failed"):
                self._finish_call(call_id, update)
        elif kind == "tool_call_update":
            call_id = str(update.get("toolCallId") or "")
            with self._lock:
                block = self._calls.get(call_id)
                if block is not None and update.get("title"):
                    block["name"] = str(update["title"])
                if block is not None and update.get("kind"):
                    block["kind"] = update["kind"]
                if block is not None:  # the input, where it works and what it wrote often come later
                    if isinstance(update.get("rawInput"), dict) and update["rawInput"]:
                        block["input"] = update["rawInput"]
                    _describe(block, update)
                kind_ = (block or {}).get("kind")
            self._follow({**update, "kind": update.get("kind") or kind_})
            if update.get("status") in ("completed", "failed"):
                self._finish_call(call_id, update)
        elif kind == "plan":
            # the same shape as the built-in agent's update_plan, so the panel shows it as its Plan card
            statuses = {"completed": "done", "in_progress": "in_progress"}
            steps = [{"step": str(e.get("content") or ""), "status": statuses.get(str(e.get("status")), "pending")}
                     for e in update.get("entries") or [] if isinstance(e, dict) and e.get("content")]
            if not steps:
                return
            with self._lock:
                self._blocks = [b for b in self._blocks if b.get("type") != "plan"] + [{"type": "plan", "steps": steps}]
            self._emit(Event("plan", args={"steps": steps}))

    def _follow(self, update: Dict[str, Any]) -> None:
        """Tells where the agent edits (an ACP tool call's ``locations``) with a ``"file"`` event."""
        if update.get("kind") not in ("edit", "delete", "move"):
            return
        for loc in update.get("locations") or []:
            if isinstance(loc, dict) and loc.get("path"):
                self._emit(Event("file", str(loc["path"]), args={"line": loc.get("line"), "written": False}))
                return

    def _finish_call(self, call_id: str, update: Dict[str, Any]) -> None:
        error = update.get("status") == "failed"
        text = _text_of(update.get("content")) or str(update.get("rawOutput") or ("Failed" if error else "Done"))
        with self._lock:
            block = self._calls.pop(call_id, None)
            if block is None:
                return
            self._results.append({"type": "tool_result", "tool_use_id": call_id, "content": text[:40_000],
                                  "is_error": error})
        self._emit(Event("tool_result", tool=block["name"], args=block.get("input") or {}, call_id=call_id,
                         result=text[:4000], error=error))

    def _on_request(self, method: str, params: Any) -> Any:
        params = params if isinstance(params, dict) else {}
        if method == "session/request_permission":
            return {"outcome": self._permission(params)}
        if method == "fs/read_text_file":
            path = self._path(str(params.get("path") or ""))
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            start = max(int(params.get("line") or 1) - 1, 0)
            limit = params.get("limit")
            chosen = lines[start:start + int(limit)] if limit else lines[start:]
            return {"content": "".join(chosen)}
        if method == "fs/write_text_file":
            if self.settings.mode in ("read", "chat"):
                raise PermissionError("Pyzed is in read-only mode: files cannot be written")
            path = self._path(str(params.get("path") or ""))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(str(params.get("content") or "").encode("utf-8"))
            self._emit(Event("file", str(path), args={"written": True}))
            return None
        raise LookupError(method)

    def _path(self, raw: str) -> Path:
        """A path the agent asked for, which must be inside the project and not a secrets file."""
        path = Path(raw)
        target = (path if path.is_absolute() else self.root / path).resolve()
        if target != self.root and self.root not in target.parents:
            raise PermissionError(f"{raw} is outside the project folder")
        if any(fnmatch.fnmatch(target.name, pattern) for pattern in SECRET_FILES):
            raise PermissionError(f"{raw} may hold secrets, so the agent cannot open it")
        return target

    def _permission(self, params: Dict[str, Any]) -> Dict[str, Any]:
        options = [o for o in params.get("options") or [] if isinstance(o, dict)]
        call = params.get("toolCall") if isinstance(params.get("toolCall"), dict) else {}
        call = {**(self._calls.get(str(call.get("toolCallId") or "")) or {}), **{k: v for k, v in call.items() if v}}
        kind = str(call.get("kind") or "")

        def pick(*kinds: str) -> Dict[str, Any]:
            for wanted in kinds:
                for option in options:
                    if option.get("kind") == wanted:
                        return {"outcome": "selected", "optionId": option.get("optionId")}
            return {"outcome": "cancelled"}

        mode = self.settings.mode
        if mode == "chat" or (mode == "read" and kind not in _READ_KINDS):
            return pick("reject_once", "reject_always")
        if mode == "bypass" or (mode == "read" and kind in _READ_KINDS):
            return pick("allow_once", "allow_always")
        title = str(call.get("title") or call.get("name") or kind or "An action")
        tool = Tool(title, title, {"type": "object", "properties": {}}, lambda: None, writes=True, title=title)
        args = call.get("rawInput") if isinstance(call.get("rawInput"), dict) else {}
        allowed = bool(self.confirm(tool, args)) if self.confirm is not None else False
        return pick("allow_once", "allow_always") if allowed else pick("reject_once", "reject_always")
