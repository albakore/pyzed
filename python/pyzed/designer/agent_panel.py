"""The Agent panel of Pyzed Design, like Zed's: threads with an AI agent that reads and edits the open
form, its code and the project, plus inline assist in the code editor and the AI agents settings.

``AgentController`` keeps the state and runs the agent in a worker thread. The worker never touches
the designer: text, reasoning and tool calls come back through a queue that ``poll`` drains on the
UI thread (a subscription runs it while the agent works), and tools that change the document are
run there too, so every change is an ordinary undo step.
"""

from __future__ import annotations

import fnmatch
import queue
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

from .. import _core, _platform, ui
from .. import agents as _agents
from ..agents import acp as _acp
from ..agents import mcp_client as _mcp
from ..agents import providers as _providers
from ..icons import icon as _icon
from ..theme import Theme, alpha
from . import agent_tools, file_scan
from . import logs as _logs
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

INPUT_ID = "agent-input"
INLINE_ID = "agent-inline-input"
SCROLL_ID = "agent-thread"
SETTINGS_SCROLL = "agent-settings"

#: Prompts offered in an empty thread (English; shown translated).
SUGGESTIONS = (
    ("app-window", "Create a notes app with a list of notes, an editor and a search box"),
    ("layout-template", "Create a login form with email, password and a Sign in button"),
    ("component", "Create a reusable user card component with an avatar, a name and a role"),
    ("wand-sparkles", "Align the controls of this form and give them consistent margins"),
    ("code", "Write the handlers of this form and validate the inputs"),
)

INLINE_SYSTEM = """\
You rewrite Python code for a Pyzed Design form. You get the current code and an instruction. \
Answer with the complete new code in one ```python fenced block and nothing else: no explanations. \
Keep the function names and signatures unless asked otherwise; handlers are def <control>_<event>(form, event)."""

_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


def _brief(value: Any, limit: int = 160) -> str:
    """``value`` on one short line, for the Logs panel."""
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _log_args(args: Dict[str, Any]) -> str:
    return _brief(", ".join(f"{k}={v!r}" for k, v in args.items()))


@dataclass
class _Box:
    """A value handed from the UI thread to a waiting worker."""

    done: threading.Event = field(default_factory=threading.Event)
    value: Any = None
    error: Optional[BaseException] = None


@dataclass
class Confirmation:
    tool: _agents.Tool
    args: Dict[str, Any]
    box: _Box


@dataclass
class InlineAssist:
    """Inline assist in the code editor: the prompt, the streamed answer and the code it replaced."""

    prompt: str = ""
    running: bool = False
    answer: str = ""
    before: Optional[str] = None
    error: str = ""


@dataclass
class KeyCapture:
    """Signing in by copying a key: the provider's key page is open and the clipboard is watched."""

    provider: str
    deadline: float
    next_check: float = 0.0
    #: A copied key is being checked with the provider.
    checking: bool = False
    #: Keys already tried (so a refused key is not checked again and again).
    tried: set = field(default_factory=set)


@dataclass
class Mention:
    """Something added to the message with @: a file, the form, its code, the selection or a control."""

    kind: str  # "file" | "form" | "code" | "selection" | "control"
    key: str
    label: str
    icon: str


@dataclass
class Attachment:
    """An image added to the next message (from a file, the clipboard or a screenshot of the form)."""

    name: str
    data: bytes

    @property
    def block(self) -> Dict[str, Any]:
        return _agents.image_block(self.data)


@dataclass
class DeviceLogin:
    """GitHub sign-in in progress: the code the user types on GitHub."""

    provider: str
    user_code: str = ""
    uri: str = ""
    cancelled: bool = False


@dataclass
class AgentAuth:
    """An external agent that wants a sign-in before it answers (Zed's "Authentication required"): its ways
    to sign in, and the message to send again once signed in."""

    agent: str  # the agent's name in the settings
    label: str
    methods: List[Dict[str, Any]]
    prompt: Any = None
    waiting: str = ""  # the method being signed in with
    error: str = ""
    until: float = 0.0  # while a sign-in in a terminal is watched
    next_check: float = 0.0
    checking: bool = False


#: Image files that can be attached (the file dialog's filter and the @ popup).
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")

#: How long the clipboard is watched for a copied key.
CAPTURE_SECONDS = 300.0
#: How long the panel waits for the Claude Code sign-in in the terminal.
CLAUDE_LOGIN_SECONDS = 900.0
#: How long (and how often) the panel checks an external agent's sign-in in a terminal.
AGENT_LOGIN_SECONDS = 900.0
AGENT_LOGIN_EVERY = 3.0
NODE_URL = "https://nodejs.org/en/download"
#: Model answers per message: enough to build, run and fix a whole app on its own.
MAX_TURNS = 150

#: Slash commands: (name, icon, description, prompt to send or None for an action).
SLASH_COMMANDS = (
    ("new", "plus", "Start a new thread", None),
    ("history", "history", "Show the past threads", None),
    ("settings", "settings-2", "AI agents settings", None),
    ("app", "app-window", "Create an application", None),
    ("form", "layout-template", "Generate a new form", None),
    ("component", "component", "Generate a reusable component", None),
    ("explain", "book-open", "Explain this form and its code", "Explain what this form does and how its handlers work."),
    ("fix", "wrench", "Check this form's code and fix the issues",
     "Check the code of this form with validate_code and fix every issue it finds."),
    ("tidy", "wand-sparkles", "Align the controls and even out the margins",
     "Align the controls of this form and give them consistent margins."),
    ("look", "camera", "Look at the form and improve its design",
     "Take a screenshot of this form with screenshot_form, look at it and improve its layout and design."),
)

#: Permission modes as shown in the composer: mode -> (label, icon, description).
MODE_TEXT = {
    "ask": ("Ask before writing", "shield-check", "Edits the form freely; asks before creating or writing files."),
    "bypass": ("Bypass permissions", "shield-off", "Never asks: writes files and creates documents on its own."),
    "read": ("Read only", "eye", "Reads only: answers questions and suggests code without changing anything."),
    "chat": ("Chat only", "message-circle", "No tools: a plain conversation with the model."),
}
EFFORT_TEXT = {"low": "Low", "medium": "Medium", "high": "High", "xhigh": "Extra high", "max": "Max"}

_TRIGGER = re.compile(r"(?:^|\s)@([^\s@]*)$")
_FILE_SUFFIXES = (".py", ".pzform", ".pzcomp", ".md", ".toml", ".json", ".txt", ".css", ".yaml", ".yml",
                  *IMAGE_SUFFIXES)


def model_label(model: str) -> str:
    """A short name for the model picker: ``"anthropic:claude-opus-5-5"`` -> ``"Opus 5.5"``."""
    name = model.partition(":")[2] or model
    match = re.fullmatch(r"claude-(opus|sonnet|haiku|fable)-(\d+)(?:-(\d+))?", name)
    if match:
        family, major, minor = match.groups()
        return f"{family.capitalize()} {major}{'.' + minor if minor else ''}"
    name = name.rpartition("/")[2]
    return name if len(name) <= 18 else name[:17] + "…"


def extract_code(answer: str) -> Optional[str]:
    """The code of the first fenced block of ``answer`` (or the whole answer when it has no fence)."""
    match = _FENCE.search(answer)
    if match:
        return match.group(1).rstrip() + "\n"
    stripped = answer.strip()
    return stripped + "\n" if stripped and "```" not in stripped else None


class AgentController:
    """State and behavior of the Agent panel, inline assist and the agent settings."""

    def __init__(self, designer: "Designer", *, store: Optional[_agents.ThreadStore] = None,
                 stream: Callable[..., Any] = _agents.stream_turn) -> None:
        self.d = designer
        self.settings = _providers.load()
        self.store = store or _agents.ThreadStore()
        self.thread = self._fresh_thread(self.settings.model)
        self.input = ""
        self.running = False
        self.error = ""
        self.view = "thread"  # "history" or "settings" (the agent settings, inside the panel like Zed's)
        self.live_text = ""
        self.live_thinking = ""
        #: the tool the model is writing a call to (its input streams before it runs), and when the run started
        self.live_tool = ""
        self.started = 0.0
        #: tool call id -> "running" | "done" | "error" | "waiting"
        self.tool_status: Dict[str, str] = {}
        self.open_blocks: set = set()  # thinking / tool cards the user expanded
        self.pending: Optional[Confirmation] = None
        self.always_allow: set = set()  # tools allowed for the rest of the session
        #: (document, form copy, code) before the agent's first change, for "Reject"
        self.snapshot: List[Tuple[Any, Any, str]] = []
        self.changed = False
        self.inline: Optional[InlineAssist] = None
        # settings dialog
        self.provider_open: Optional[str] = None
        self.advanced_open = False  # the Advanced part of the settings
        self.key_buffer: Dict[str, str] = {}
        self.url_buffer: Dict[str, str] = {}
        self.busy_provider: Optional[str] = None
        self.capture: Optional[KeyCapture] = None
        # the designer comes back to the front once a sign-in in the browser is done
        self.raise_window = False
        # signing in to Claude Code with a Claude subscription: when to stop checking, and the next check
        self.claude_login: Optional[float] = None
        self._claude_check = 0.0
        # an external agent that wants a sign-in first, with its ways to sign in
        self.agent_auth: Optional[AgentAuth] = None
        # the plan an external agent is following (the built-in agent's is read from its update_plan calls)
        self.live_plan: List[Dict[str, str]] = []
        # the designer's tools served over MCP to external agents (started with the first one)
        self._editor_server: Optional[Any] = None
        # composer
        self.menu: Optional[str] = None  # "mode" | "model" | "effort" while its menu is open
        self.mentions: List[Mention] = []
        self.picked = 0  # highlighted row of the @ / slash popup
        self.attachments: List[Attachment] = []
        self.popup_closed: Optional[str] = None  # the input when Escape closed the popup
        self.device: Optional[DeviceLogin] = None
        # MCP servers and external agents
        self.mcp = _mcp.Servers(self.settings.mcp_servers)
        self.mcp_status: Dict[str, str] = {}  # server -> "N tools" or why it failed
        self.mcp_ok: set = set()  # servers that started and listed their tools
        self.server_draft: Optional[Dict[str, Any]] = None  # the MCP server or agent being added or edited
        self._acp: Dict[str, Any] = {}  # thread id -> ACPAgent
        self.google_projects: List[str] = []
        # the settings view: agents from the ACP registry, and the agent skills
        self.registry: List[Any] = []
        self.registry_open = False
        self.registry_busy = ""
        self.registry_error = ""
        self._skills: Optional[List[Any]] = None
        self.skill_url = ""
        self.skill_busy = ""
        self._jobs = 0  # background jobs whose answer is still to come
        #: the agents of this computer Pyzed's MCP server was just added to (they need a restart to use it)
        self.mcp_added: List[str] = []
        self.mcp_clients_busy = ""
        self._clients: Optional[Tuple[float, List[Tuple[Any, str]]]] = None
        import atexit

        atexit.register(self.shutdown)
        self._files: Optional[Tuple[List[Path], List[str]]] = None
        self._queue: "queue.Queue[Tuple[Any, ...]]" = queue.Queue()
        self._agent: Optional[_agents.Agent] = None
        self._stream = stream
        self._tools: Optional[Dict[str, _agents.Tool]] = None

    def on_start(self) -> None:
        """When the designer starts: adds Pyzed's MCP server to the AI agents found on this computer that do not
        have it yet (once each), then asks to restart them."""
        if not self.settings.install_pyzed_mcp:
            return
        from ..agents import mcp_install

        skip = list(self.settings.pyzed_mcp_done)
        self._job(lambda: mcp_install.install_missing(skip), self._mcp_installed)

    def _mcp_installed(self, value: Any, error: Optional[BaseException]) -> None:
        if error is not None or not value:
            return
        added, failed = value
        for client_id, why in failed.items():
            _logs.log("agent").warning("Could not add Pyzed's MCP server to %s: %s", client_id, why)
        if not added:
            return
        _logs.event("agent", "Added Pyzed's MCP server to %s", ", ".join(c.name for c in added))
        self.settings.pyzed_mcp_done += [c.id for c in added if c.id not in self.settings.pyzed_mcp_done]
        self.save_settings()
        self.mcp_added = [c.name for c in added]
        self.d.notify(tr("Pyzed's MCP server was added to {names}", names=", ".join(self.mcp_added)),
                      tr("Restart them so they can use it"), kind="success", seconds=8)

    def mcp_clients(self) -> List[Tuple[Any, str]]:
        """The AI agents of this computer, with whether Pyzed's MCP server is in their settings (looked up again
        every few seconds, not on every frame)."""
        from ..agents import mcp_install

        now = time.monotonic()
        if self._clients is None or now - self._clients[0] > 5.0:
            self._clients = (now, [(client, mcp_install.status(client)) for client in mcp_install.detected()])
        return self._clients[1]

    def toggle_mcp_client(self, client_id: str) -> None:
        """Adds Pyzed's MCP server to an agent of this computer, or takes it out (and leaves it out)."""
        from ..agents import mcp_install

        client = next((c for c in mcp_install.detected() if c.id == client_id), None)
        if client is None:
            return
        adding = mcp_install.status(client) != "installed"
        self.mcp_clients_busy = client_id
        if client_id not in self.settings.pyzed_mcp_done:  # decided by hand: not touched on start again
            self.settings.pyzed_mcp_done.append(client_id)
            self.save_settings()

        def then(_value: Any, error: Optional[BaseException]) -> None:
            self.mcp_clients_busy = ""
            self._clients = None
            if error is not None:
                _logs.log("agent").warning("Could not change Pyzed's MCP server in %s: %s", client.name, error)
                self.d.notify(tr("Could not change {name}", name=client.name), str(error), kind="error", seconds=6)
                return
            _logs.event("agent", "%s Pyzed's MCP server %s %s", "Added" if adding else "Took out",
                        "to" if adding else "of", client.name)
            if adding:
                self.mcp_added = [client.name]
                self.d.notify(tr("Pyzed's MCP server was added to {names}", names=client.name),
                              tr("Restart them so they can use it"), kind="success", seconds=6)

        self._job(lambda: (mcp_install.install if adding else mcp_install.remove)(client), then)

    def restart_agents(self) -> None:
        """Restarts the external agents running in Pyzed (they start again with the current MCP servers), and
        hides the prompt to restart the agents Pyzed's MCP server was added to."""
        self.mcp_added = []
        if self.running:
            return
        _logs.event("agent", "Restarted the external agents")
        self.close_external_agents()
        self.prepare_agent()

    def dismiss_mcp_added(self) -> None:
        self.mcp_added = []

    def shutdown(self) -> None:
        """Stops the MCP servers and external agents this designer started."""
        self.mcp.close()
        self.close_external_agents()
        if self._editor_server is not None:
            self._editor_server.close()
            self._editor_server = None

    # -- setup ------------------------------------------------------------------------------------
    @property
    def ready(self) -> bool:
        """Whether the selected model's provider is set up (or the external agent exists)."""
        provider_id, name = _providers.split_model(self.thread.model or self.settings.model)
        if provider_id == "acp":
            return self.settings.acp_agent(name) is not None
        return _providers.is_ready(provider_id, settings=self.settings)

    @property
    def active(self) -> bool:
        """Whether something is in flight (the poll subscription runs while it is)."""
        return self.running or bool(self.inline and self.inline.running) or self.busy_provider is not None \
            or self.capture is not None or self.raise_window or self.claude_login is not None \
            or self._jobs > 0 or not self._queue.empty() or bool(self.agent_auth and self.agent_auth.until)

    @property
    def expanded(self) -> bool:
        """Whether the panel fills the window (the expand button in its header)."""
        return self.d.layout.zoomed == "agent"

    def project_root(self) -> Path:
        """The folder the file tools may use: the uv project, else the open file's folder, else the cwd."""
        project = getattr(self.d.projects, "project", None)
        if project is not None:
            return Path(project.root)
        if self.d.doc.path is not None:
            return self.d.doc.path.resolve().parent
        return Path.cwd()

    def tool_index(self) -> Dict[str, _agents.Tool]:
        """The agent's tools by name (for their titles in the thread), built once."""
        if self._tools is None:
            self._tools = {x.name: x for x in agent_tools.designer_tools(self.d)}
        return self._tools

    def models(self) -> List[str]:
        """``provider:model`` names of the providers that are set up (for the default model setting)."""
        out: List[str] = []
        for pid in _providers.PROVIDERS:
            if pid == "acp" or not _providers.is_ready(pid, settings=self.settings):
                continue
            out += [f"{pid}:{m}" for m in self.settings.models_of(pid)]
        out += [f"acp:{a.name}" for a in self.settings.acp_agents if a.enabled]
        current = self.thread.model or self.settings.model
        if current not in out:
            out.insert(0, current)
        return out

    def save_settings(self) -> None:
        _providers.save(self.settings)

    # -- the worker's side -------------------------------------------------------------------------
    def _execute(self, fn: Callable[[], Any]) -> Any:
        box = _Box()
        self._queue.put(("call", fn, box))
        box.done.wait()
        if box.error is not None:
            raise box.error
        return box.value

    def on_ui(self, fn: Callable[[], Any]) -> Any:
        """Runs ``fn`` on the UI thread from the agent's worker and returns its result; unlike the tools'
        executor it does not count as a change to review."""
        if threading.current_thread() is threading.main_thread():
            return fn()
        box = _Box()
        self._queue.put(("read", fn, box))
        box.done.wait()
        if box.error is not None:
            raise box.error
        return box.value

    def _confirm(self, tool: _agents.Tool, args: Dict[str, Any]) -> bool:
        if tool.name in self.always_allow or tool.name in self.settings.allowed_tools:
            return True
        box = _Box()
        self._queue.put(("confirm", tool, args, box))
        box.done.wait()
        return bool(box.value)

    # -- the UI thread's side ------------------------------------------------------------------------
    def poll(self) -> Any:
        """Applies what the worker sent: streamed text, tool calls to run, confirmations, the end. While
        signing in by copying a key, it also reads the clipboard about once a second."""
        self._drain()
        if self.raise_window:
            self.raise_window = False
            return _core.Command.focus_window()
        if self.claude_login is not None:
            self._check_claude_login()
        if self.agent_auth is not None and self.agent_auth.until:
            self._check_agent_login()
        capture = self.capture
        if capture is None or capture.checking:
            return None
        now = time.monotonic()
        if now > capture.deadline:
            self.capture = None
            self.d.notify(tr("No key was copied; sign in again when you are ready"), kind="info", seconds=5)
            return None
        if now < capture.next_check:
            return None
        capture.next_check = now + 1.0
        return _core.Command.paste(self.on_clipboard)

    def _drain(self) -> None:
        for _ in range(500):
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                return
            kind = item[0]
            if kind == "event":
                self._on_event(item[1])
            elif kind == "call":
                _, fn, box = item
                self._remember_documents()
                try:
                    box.value = fn()
                    self.changed = True
                except BaseException as err:  # noqa: BLE001 - handed back to the worker
                    box.error = err
                box.done.set()
            elif kind == "read":
                _, fn, box = item
                try:
                    box.value = fn()
                except BaseException as err:  # noqa: BLE001 - handed back to the worker
                    box.error = err
                box.done.set()
            elif kind == "confirm":
                _, tool_, args, box = item
                self.pending = Confirmation(tool_, args, box)
                _logs.event("agent", "Waiting for your OK to run %s", getattr(tool_, "title", "") or tool_.name)
                self._notify_desktop(tr("The agent needs your OK"), getattr(tool_, "title", "") or tool_.name)
            elif kind == "inline":
                self._on_inline(*item[1:])
            elif kind == "provider":
                _, message, ok = item
                self.busy_provider = None
                self.d.notify(message, kind="success" if ok else "error", seconds=4 if ok else 6)
            elif kind == "models":
                _, pid, names = item
                self.busy_provider = None
                self.settings.provider(pid).models = names
                self.save_settings()
                self.d.notify(tr("{count} models found", count=len(names)), kind="success")
                current, _ = _providers.split_model(self.thread.model or self.settings.model)
                if names and not _providers.is_ready(current) and _providers.is_ready(pid):
                    self.set_model(f"{pid}:{self.settings.models_of(pid)[0]}")
            elif kind == "key":
                self._on_key_checked(*item[1:])
            elif kind == "attach":
                _, name, data = item
                self.busy_provider = None if self.busy_provider == "screenshot" else self.busy_provider
                self.attachments.append(Attachment(name, data))
            elif kind == "mcp":
                _, server, why = item
                self.mcp_status[server] = why
                self.mcp_ok.discard(server)
                _logs.log("agent").warning("The MCP server %s did not start: %s", server, why)
                self.d.notify(tr("The MCP server {name} did not start", name=server), why, kind="warning",
                              seconds=6)
            elif kind == "mcp_ready":
                if self.mcp.clients:
                    _logs.log("agent").debug("MCP servers ready: %s", ", ".join(self.mcp.clients))
                for server in list(self.mcp.clients):
                    self.mcp_status[server] = tr("{count} tools", count=len(self.mcp._tools.get(server, [])))
                    self.mcp_ok.add(server)
            elif kind == "mcp_test":
                _, server, message, ok = item
                self.busy_provider = None
                self.mcp_status[server] = message
                (self.mcp_ok.add if ok else self.mcp_ok.discard)(server)
            elif kind == "device":
                _, pid, user_code, uri = item
                if self.device is not None and self.device.provider == pid:
                    self.device.user_code, self.device.uri = user_code, uri
            elif kind == "device_done":
                self.device = None
            elif kind == "job":
                _, then, value, error = item
                self._jobs -= 1
                then(value, error)
            elif kind == "projects":
                _, pid, names = item
                own = self.settings.provider(pid)
                self.google_projects = names
                if names and not own.project:
                    own.project = names[0]
                    self.save_settings()

    def _remember_documents(self) -> None:
        doc = self.d.doc
        if not any(entry[0] is doc for entry in self.snapshot):
            self.snapshot.append((doc, doc.form.copy(), doc.code))

    def _on_event(self, event: _agents.Event) -> None:
        if event.kind == "text":
            self.live_text += event.text
        elif event.kind == "thinking":
            self.live_thinking += event.text
        elif event.kind == "tool_input":
            self.live_tool = event.tool
        elif event.kind == "turn":
            if event.usage:
                _logs.log("agent").debug("Model answer finished (%s)", _log_args(event.usage))
            self.live_text = ""
            self.live_thinking = ""
            self.live_tool = ""
            used = sum(event.usage.get(k, 0) for k in ("input", "cache_read", "cache_write", "output"))
            if used:
                self.thread.context = used
        elif event.kind == "tool_call":
            _logs.event("agent", "Tool %s%s", event.tool, f" ({_log_args(event.args)})" if event.args else "")
            self.tool_status[event.call_id] = "running"
            self.live_tool = ""
        elif event.kind == "tool_result":
            if event.error:
                _logs.log("agent").warning("Tool %s failed: %s", event.tool, _brief(event.result),
                                           extra={"detail": event.result})
            else:
                _logs.log("agent").debug("Tool %s finished: %s", event.tool, _brief(event.result))
            self.tool_status[event.call_id] = "error" if event.error else "done"
            if event.tool == "write_file" and not event.error and event.args.get("path"):
                self._on_file(str(event.args["path"]), True)
        elif event.kind == "file":
            _logs.event("agent", "%s %s", "Wrote" if event.args.get("written") else "Looked at", event.text)
            self._on_file(event.text, bool(event.args.get("written")))
        elif event.kind == "plan":
            self.live_plan = list(event.args.get("steps") or [])
            steps = (str(s.get("content", s)) if isinstance(s, dict) else str(s) for s in self.live_plan)
            _logs.log("agent").debug("Plan: %s", _brief("; ".join(steps)))
        elif event.kind == "auth":
            config = getattr(self._agent, "config", None)
            name = getattr(config, "name", "")
            _logs.log("agent").warning("%s needs you to sign in", getattr(config, "label", name))
            self.agent_auth = AgentAuth(name, getattr(config, "label", name), list(event.args.get("methods") or []),
                                        event.args.get("prompt"))
        elif event.kind == "error":
            _logs.log("agent").error("The agent stopped: %s", event.text)
            self.error = event.text
        elif event.kind == "done":
            _logs.event("agent", "Finished in %.1f s", time.monotonic() - self.started)
            if self.error:
                self._notify_desktop(tr("The agent stopped"), self.error)
            elif self.agent_auth is not None:
                self._notify_desktop(tr("Sign in to {name}", name=self.agent_auth.label),
                                     tr("The agent is waiting for you to sign in"))
            else:
                self._notify_desktop(tr("The agent finished"), self.thread.display_title)
            self.running = False
            self.live_text = self.live_thinking = self.live_tool = ""
            self.live_plan = []
            self._agent = None
            self._keep()
            projects = getattr(self.d, "projects", None)
            if projects is not None:  # it may have run uv in a terminal: the Dependencies tab reads it again
                projects.poll(force=True)

    # -- the active project ---------------------------------------------------------------------------
    def project_key(self) -> str:
        """The folder of the active project (``""`` without one): threads are kept per project, like Zed's."""
        project = getattr(getattr(self.d, "projects", None), "project", None)
        return str(Path(project.root).resolve()) if project is not None else ""

    def _fresh_thread(self, model: str) -> _agents.Thread:
        return _agents.Thread(model=model, project=self.project_key())

    def project_changed(self, project: Any) -> None:
        """Another project became the active one: the agents follow it. External agents start again in its
        folder, its skills and rules are looked up again, and the panel shows a new thread of that project
        (the current one stays in the history of its own)."""
        self._skills = None
        self._files = None
        if self.running:  # a run in progress finishes on the project it started on
            return
        self.close_external_agents()
        self.mcp.close()
        self.agent_auth = None
        key = self.project_key()
        if not self.thread.messages:
            self.thread.project = key
            return
        if self.thread.project == key:
            return
        self._keep()
        self.thread = self._fresh_thread(self.thread.model or self.settings.model)
        self.view = "thread" if self.view == "history" else self.view
        self.error = ""
        self.snapshot = []
        self.changed = False

    def threads(self) -> List[_agents.Thread]:
        """The saved threads of the active project (and the ones that belong to none), newest first."""
        key = self.project_key()
        return [th for th in self.store.list() if not th.project or th.project == key]

    def project_rules(self) -> Any:
        """The active project's rules file (``AGENTS.md``, ``CLAUDE.md``, ``.rules``...), or ``None``."""
        from ..agents import rules as _rules

        return _rules.find(self.project_root())

    def open_rules(self) -> None:
        """Opens the project's rules file in the code editor, creating ``AGENTS.md`` when there is none."""
        from ..agents import rules as _rules

        found = self.project_rules()
        try:
            path = found.path if found is not None else _rules.create(self.project_root())
        except OSError as err:
            self.d.notify(tr("Could not create {name}", name="AGENTS.md"), str(err), kind="error", seconds=5)
            return
        self.d.buffers.open(path)
        files = getattr(getattr(self.d, "projects", None), "files", None)
        if files is not None and found is None:
            files.refresh()

    def _keep(self) -> None:
        """Saves the current thread, unless the settings say not to keep conversations."""
        if self.settings.keep_history:
            self.store.save(self.thread)

    # -- actions ------------------------------------------------------------------------------------
    def set_input(self, text: str) -> None:
        if self.trigger() != self._trigger_of(text):
            self.picked = 0
        self.input = text
        self.menu = None
        self.d.focus = "agent"
        # a mention whose @label was deleted from the text is dropped
        self.mentions = [m for m in self.mentions if f"@{m.label}" in text]

    def focus_box(self, *_: Any) -> None:
        """The message box got the keyboard (its cursor moved)."""
        self.d.focus = "agent"

    def _box(self, text: str) -> Any:
        """Puts ``text`` in the message box with the cursor at its end."""
        self.input = text
        lines = text.split("\n")
        return _core.Command.batch([_core.Command.set_editor_text(INPUT_ID, text),
                                    _core.Command.set_editor_cursor(INPUT_ID, len(lines), len(lines[-1]) + 1),
                                    _core.Command.focus(INPUT_ID)])

    @property
    def popup_open(self) -> bool:
        """Whether the @ / slash popup shows (Escape hides it until the text changes)."""
        return self.trigger() is not None and self.popup_closed != self.input

    def captured_keys(self) -> List[str]:
        """Keys the message box leaves to ``on_key``: Enter sends (Shift+Enter breaks the line), and the
        arrows, Tab and Escape drive the popup or a menu while one is open."""
        keys = ["enter"]
        if self.popup_open or self.menu:
            keys += ["up", "down", "tab", "escape"]
        return keys

    def on_key(self, combo: str) -> Tuple[bool, Any]:
        """A key the message box left to the designer: ``(handled, command)``."""
        if combo == "enter":
            return True, self.send()
        if combo in ("up", "down") and self.popup_open:
            self.move_pick(1 if combo == "down" else -1)
            return True, None
        if combo == "tab" and self.popup_open:
            items = self.popup_items()
            return True, items[min(self.picked, len(items) - 1)][3]() if items else None
        if combo == "escape" and (self.popup_open or self.menu):
            self.menu = None
            self.popup_closed = self.input
            return True, None
        return False, None

    def send(self, text: Optional[str] = None) -> Any:
        """Sends the input (or ``text``) to the agent in the current thread, with the @ mentions and the
        attached images. With the @ or / popup open, Enter picks its highlighted row instead."""
        if text is None and self.popup_open:
            items = self.popup_items()
            if items:
                return items[min(self.picked, len(items) - 1)][3]()
        prompt = (text if text is not None else self.input).strip()
        if (not prompt and not (text is None and self.attachments)) or self.running:
            return None
        if not self.ready:
            self.error = tr("Set up a model provider first.")
            provider_id, _ = _providers.split_model(self.thread.model or self.settings.model)
            return self.open_settings(provider_id)
        extra = self._mention_blocks() if text is None else []
        images: List[Dict[str, Any]] = []
        if text is None:
            for a in self.attachments:
                try:
                    images.append(a.block)
                except ValueError as err:
                    self.d.notify(tr("{name} was not attached: {error}", name=a.name, error=str(err)), kind="error",
                                  seconds=6)
            self.attachments = []
        self.mentions = []
        self.menu = None
        self.input = ""
        self.popup_closed = None
        note = agent_tools.context_note(self.d)
        content = [{"type": "text", "text": prompt or tr("Look at the attached images.")}, *extra, *images,
                   {"type": "text", "text": f"<context>{note}</context>"}]
        return self._launch(content)

    def _launch(self, content: List[Dict[str, Any]]) -> Any:
        """Runs the agent of the current thread on ``content`` (a user message's blocks) in a worker thread."""
        self.error = ""
        self.view = "thread"
        self.running = True
        self.snapshot = []
        self.changed = False
        self.tool_status = {}
        self.agent_auth = None
        self.live_tool = ""
        self.started = time.monotonic()
        model = self.thread.model or self.settings.model
        self.thread.model = model
        self.thread.project = self.thread.project or self.project_key()
        put = self._queue.put
        emit = lambda e: put(("event", e))  # noqa: E731
        jobs = [b for b in content if b.get("type") == "screenshot"]
        provider_id, name = _providers.split_model(model)
        asked = next((b.get("text", "") for b in content if b.get("type") == "text"), "")
        _logs.event("agent", "Asked %s: %s", model, _brief(asked))
        servers = self.mcp
        servers.cwd = str(self.project_root())
        if provider_id == "acp":
            agent: Any = self._external_agent(name)
        else:
            from ..agents import skills as _skills

            from ..agents import rules as _rules

            found = _skills.enabled(self.skills(), self.settings)
            system = "\n\n".join(part for part in (agent_tools.system_prompt(self.d), _skills.prompt(found) if found
                                                    else "", _rules.prompt(self.project_rules())) if part)
            agent = _agents.Agent(model, tools=[*agent_tools.designer_tools(self.d), *_skills.tools(found)],
                                  system=system,
                                  settings=self.settings,
                                  confirm=self._confirm, executor=self._execute, messages=self.thread.messages,
                                  max_turns=MAX_TURNS, stream=self._stream)

        def target() -> Any:
            # done here, off the UI thread: the @screenshot pictures and starting the MCP servers
            for block in jobs:
                render = block.pop("render")
                try:
                    block.update(_agents.image_block(render()))
                except Exception as err:  # noqa: BLE001 - the message goes without it
                    block.clear()
                    block.update(type="text", text=f"<context>The screenshot failed: {err}</context>")
            if provider_id != "acp" and self.settings.mcp_servers and self.settings.mode != "chat":
                for tool_ in servers.tools(lambda n, why: put(("mcp", n, why))):  # a failing server is skipped
                    agent.tools.setdefault(tool_.name, tool_)
                put(("mcp_ready",))
            return agent.run(content, on_event=emit)

        self._agent = agent
        threading.Thread(target=target, daemon=True, name="pyzed-agent").start()
        return _core.Command.batch([_core.Command.set_editor_text(INPUT_ID, ""),
                                    _core.Command.scroll_to_end(SCROLL_ID)])

    def _external_agent(self, name: str) -> Any:
        """The ACP agent of the current thread (one session per thread, started on its first message)."""
        found = self._acp.get(self.thread.id)
        config = self.settings.acp_agent(name)
        assert config is not None
        if found is not None and found.config == config:
            return found
        if found is not None:
            found.close()
        servers = _acp.mcp_entries(self.settings.mcp_servers)
        if self.settings.share_pyzed_mcp:  # the editor itself: the open form, its code, the project, Pyzed's docs
            editor = self.editor_server()
            servers[:0] = [entry for entry in (editor.acp_entry(), editor.bridge_entry()) if entry is not None]
        agent = _acp.ACPAgent(config, cwd=self.project_root(), settings=self.settings, confirm=self._confirm,
                              messages=self.thread.messages, mcp_servers=servers)
        self._acp[self.thread.id] = agent
        return agent

    def editor_server(self) -> Any:
        """The designer's tools (the same as the built-in agent's, but files and shell, which external agents
        have their own of) served over MCP on 127.0.0.1, so an external agent controls the editor."""
        if self._editor_server is None:
            from ..agents import mcp_host
            from ..agents.tools import file_tools

            own_files = {t.name for t in file_tools(self.project_root())}
            tools = [t for t in agent_tools.designer_tools(self.d) if t.name not in own_files]
            # the external agent already asked (or not) through its permission request
            runner = _agents.Agent(tools=tools, settings=self.settings, confirm=lambda tool, args: True,
                                   executor=self._execute)
            self._editor_server = mcp_host.ToolServer(runner, name="pyzed_editor",
                                                      instructions=agent_tools.external_prompt(self.d))
        return self._editor_server

    def close_external_agents(self, keep: Optional[str] = None) -> None:
        """Stops the external agents' programs (all but the one of thread ``keep``)."""
        for thread_id, agent in list(self._acp.items()):
            if thread_id != keep:
                agent.close()
                del self._acp[thread_id]

    def stop(self) -> None:
        """Stops the agent (a pending confirmation is answered "no")."""
        if self._agent is not None:
            _logs.event("agent", "Stopped by you")
            self._agent.stop()
        if self.pending is not None:
            self.answer(False)

    def answer(self, allow: bool, always: bool = False) -> None:
        """Answers the pending confirmation."""
        pending, self.pending = self.pending, None
        if pending is None:
            return
        _logs.event("agent", "%s %s%s", "Allowed" if allow else "Declined",
                    getattr(pending.tool, "title", "") or pending.tool.name, " (always)" if allow and always else "")
        if allow and always:  # remembered, like Zed's "Always allow" (Settings → Permissions lists them)
            self.always_allow.add(pending.tool.name)
            if pending.tool.name not in self.settings.allowed_tools:
                self.settings.allowed_tools.append(pending.tool.name)
                self.save_settings()
        pending.box.value = allow
        pending.box.done.set()

    def suggest(self, text: str) -> Any:
        """Fills the input with ``text`` and sends it."""
        return self.send(tr(text))

    def new_thread(self, agent: Optional[str] = None) -> Any:
        """Starts an empty thread (the current one stays in the history), with ``agent`` when given: ``""``
        for the built-in agent with the default model, ``"acp:<name>"`` for an external agent."""
        if self.running:
            return None
        self.menu = None
        if self.thread.messages:
            self._keep()
        model = self.settings.model
        if agent:
            model = agent
        elif agent == "" and model.startswith("acp:"):
            model = next((m for m in self.models() if not m.startswith("acp:")), _providers.DEFAULT_MODEL)
        self.thread = self._fresh_thread(model)
        _logs.event("agent", "New thread with %s", model)
        if agent is not None and model != self.settings.model:
            self.settings.model = model
            self.save_settings()
        self.close_external_agents()
        self.view = "thread"
        self.error = ""
        self.snapshot = []
        self.changed = False
        self.prepare_agent()
        return _core.Command.focus(INPUT_ID)

    def open_thread(self, thread_id: str) -> None:
        if self.running:
            return
        found = self.store.load(thread_id)
        if found is not None:
            self.thread = found
            self.view = "thread"
            self.error = ""

    def delete_thread(self, thread_id: str) -> None:
        self.store.delete(thread_id)
        if self.thread.id == thread_id:
            self.thread = self._fresh_thread(self.settings.model)

    def toggle_history(self) -> None:
        self.menu = None
        self.view = "thread" if self.view == "history" else "history"

    def back(self) -> None:
        """Back to the thread from the history or the settings."""
        self.menu = None
        self.view = "thread"
        self.server_draft = None

    def toggle_advanced(self) -> None:
        self.advanced_open = not self.advanced_open

    def toggle_block(self, key: str) -> None:
        self.open_blocks ^= {key}

    def set_model(self, label: str) -> None:
        """Picks the model of the current thread (and of new threads)."""
        self.thread.model = label
        self.settings.model = label
        self.menu = None
        _logs.event("agent", "Model: %s", label)
        self.save_settings()
        self.prepare_agent()

    # -- an external agent's own options ----------------------------------------------------------------
    def current_external(self) -> Any:
        """The ACP agent of the current thread when it has started (``None`` otherwise)."""
        provider_id, _ = _providers.split_model(self.thread.model or self.settings.model)
        return self._acp.get(self.thread.id) if provider_id == "acp" else None

    def agent_options(self) -> List[Dict[str, Any]]:
        """The current external agent's own options (its modes, models, effort...), as Zed shows them."""
        agent = self.current_external()
        return list(agent.options) if agent is not None else []

    def prepare_agent(self) -> None:
        """Opens the external agent's session ahead of the first message, so its options (modes, models...)
        show in the composer and a sign-in it needs is asked for right away."""
        provider_id, name = _providers.split_model(self.thread.model or self.settings.model)
        if provider_id != "acp" or self.running or self.settings.acp_agent(name) is None:
            return
        try:
            agent = self._external_agent(name)
        except Exception:  # noqa: BLE001 - the first message starts it and shows why it failed
            return
        if agent.session:
            return

        def then(_value: Any, error: Optional[BaseException]) -> None:
            if error is not None and not isinstance(error, _acp.AuthRequired):
                _logs.log("agent").warning("%s did not start: %s", agent.config.label, error)
            if isinstance(error, _acp.AuthRequired) and self.agent_auth is None and not self.running:
                self.agent_auth = AgentAuth(name, agent.config.label, list(error.methods))

        self._job(agent.start, then)

    def set_agent_option(self, option_id: str, value: str) -> None:
        """Picks ``value`` for one of the external agent's options, and remembers it for its next sessions."""
        self.menu = None
        agent = self.current_external()
        if agent is None:
            return
        agent.preferred[option_id] = value
        _logs.event("agent", "%s option %s = %s", agent.config.label, option_id, value)
        self.settings.agent_options.setdefault(agent.config.name, {})[option_id] = value
        self.save_settings()

        def then(_value: Any, error: Optional[BaseException]) -> None:
            if error is not None:
                _logs.log("agent").warning("%s did not change %s: %s", agent.config.label, option_id, error)
                self.d.notify(tr("{name} did not change the option", name=agent.config.label), str(error),
                              kind="error", seconds=6)

        self._job(lambda: agent.set_option(option_id, value), then)

    def toggle_thinking(self) -> None:
        self.settings.thinking = not self.settings.thinking
        _logs.event("agent", "Thinking %s", "on" if self.settings.thinking else "off")
        self.save_settings()

    def forget_tool(self, name: str) -> None:
        """Makes a tool ask again before it runs ("Always allow" undone)."""
        _logs.event("agent", "%s asks again before it runs", name)
        self.always_allow.discard(name)
        if name in self.settings.allowed_tools:
            self.settings.allowed_tools.remove(name)
            self.save_settings()

    def set_profile(self, label: str) -> None:
        self.settings.profile = {tr("Write"): "write", tr("Ask"): "ask", tr("Minimal"): "minimal"}.get(label, "write")
        self.save_settings()

    def keep(self) -> None:
        """Keeps the agent's changes."""
        self.snapshot = []
        self.changed = False

    def reject(self) -> None:
        """Puts every document the agent changed back as it was before this run."""
        for doc, form, code in self.snapshot:
            doc.form = form
            doc.code = code
            doc.selection = []
            doc.commit()
            doc.revision += 1
        self.snapshot = []
        self.changed = False
        if self.d.editing is not None:
            agent_tools._sync_editor(self.d)
        self.d._selection_changed()
        self.d.notify(tr("Changes rejected"), kind="info")

    def retry(self) -> Any:
        """Sends the last user message again (in place of it when it got no answer, so it is not repeated)."""
        messages = self.thread.messages
        for i in range(len(messages) - 1, -1, -1):
            m = messages[i]
            if m.get("role") == "user":
                texts = [b.get("text", "") for b in m.get("content", []) if b.get("type") == "text"]
                if texts and not texts[0].startswith("<context>"):
                    if i == len(messages) - 1 and not self.running and self.ready:
                        del messages[i]
                    return self.send(texts[0])
        return None

    def use_pyzed_agent(self) -> Any:
        """Switches the thread to Pyzed's own agent (when an external one cannot start) and sends the
        unanswered message again."""
        model = next((m for m in self.models() if not m.startswith("acp:")), _providers.DEFAULT_MODEL)
        self.set_model(model)
        self.error = ""
        return self.retry()

    def compose(self, text: str) -> Any:
        """Shows the panel with ``text`` in the input, ready to finish and send."""
        self.d.layout.show("agent")
        self.view = "thread"
        return self._box(text)

    def open_settings(self, provider: Optional[str] = None, section: Optional[str] = None) -> Any:
        """Shows the agent settings in the panel, like Zed's (with ``provider`` unfolded; ``section="agents"``
        opens the ACP registry)."""
        self.menu = None
        if provider in _providers.PROVIDERS:
            self.provider_open = provider
        if section == "agents":
            self.advanced_open = True
            self.toggle_registry(True)
        self.d.dialog = None  # e.g. the designer's Settings, where the button that opens these is
        self.d.layout.show("agent")
        self.view = "settings"
        return None

    # -- composer: menus, @ mentions and / commands ---------------------------------------------------
    def toggle_menu(self, name: str) -> None:
        self.menu = None if self.menu == name else name

    def close_menu(self) -> None:
        self.menu = None

    def set_mode(self, mode: str) -> None:
        self.settings.mode = mode
        self.menu = None
        self.save_settings()

    def set_effort(self, effort: str) -> None:
        self.settings.effort = effort
        self.menu = None
        self.save_settings()

    def toggle_fast(self) -> None:
        self.settings.fast = not self.settings.fast
        self.save_settings()

    def toggle_expand(self) -> None:
        """Lets the panel fill the window, or puts it back in its dock."""
        layout = self.d.layout
        layout.zoomed = None if layout.zoomed == "agent" else "agent"
        if layout.zoomed:
            layout.show("agent")

    @staticmethod
    def _trigger_of(text: str) -> Optional[Tuple[str, str]]:
        if text.startswith("/") and " " not in text:
            return "slash", text[1:].lower()
        match = _TRIGGER.search(text)
        if match:
            return "mention", match.group(1).lower()
        return None

    def trigger(self) -> Optional[Tuple[str, str]]:
        """``("slash", query)`` while typing a command, ``("mention", query)`` after an @, else ``None``."""
        return self._trigger_of(self.input)

    def start_mention(self) -> Any:
        """Starts an @ mention at the end of the message (the + menu's "Add context")."""
        self.picked = 0
        self.menu = None
        self.popup_closed = None
        return self._box(self.input + ("" if not self.input or self.input[-1] in " \n" else " ") + "@")

    def move_pick(self, step: int) -> None:
        items = self.popup_items()
        if items:
            self.picked = (self.picked + step) % len(items)

    def popup_items(self) -> List[Tuple[str, str, str, Callable[[], Any]]]:
        """Rows of the @ / slash popup: (icon, label, detail, action)."""
        trig = self.trigger()
        if trig is None or not self.popup_open:
            return []
        kind, query = trig
        if kind == "slash":
            return [(icon, f"/{name}", tr(text), lambda name=name, prompt=prompt: self.run_command(name, prompt))
                    for name, icon, text, prompt in SLASH_COMMANDS if name.startswith(query)]
        rows = [(m.icon, m.label, detail, lambda m=m: self.add_mention(m))
                for m, detail in self.mention_candidates() if query in m.label.lower()]
        return rows[:40]

    def run_command(self, name: str, prompt: Optional[str]) -> Any:
        clear = self._box("")
        self.picked = 0
        if prompt is not None:
            return _core.Command.batch([clear, self.send(tr(prompt)) or clear])
        if name == "new":
            return _core.Command.batch([clear, self.new_thread()])
        if name == "history":
            self.view = "history"
            return clear
        if name == "settings":
            self.open_settings()
            return clear
        if name == "app":
            return self.compose(tr("Create an application that "))
        if name == "form":
            return self.compose(tr("Create a new form for "))
        if name == "component":
            return self.compose(tr("Create a reusable component that "))
        return clear

    def project_files(self) -> List[str]:
        """Files of the project the @ popup offers (no hidden, build or secret files), read in the background."""
        from ..agents.tools import SECRET_FILES

        root = self.project_root()
        found = file_scan.files(root, _FILE_SUFFIXES, 300)
        if self._files is not None and self._files[0] is found:  # the same list as last time
            return self._files[1]
        out = [p.relative_to(root).as_posix() for p in found
               if not any(fnmatch.fnmatch(p.name, pattern) for pattern in SECRET_FILES)]
        self._files = (found, out)
        return out

    def mention_candidates(self) -> List[Tuple[Mention, str]]:
        """Everything that can be added with @, with a short detail for each."""
        doc = self.d.doc
        out: List[Tuple[Mention, str]] = []
        if doc.selection:
            out.append((Mention("selection", "", "selection", "square-dashed-mouse-pointer"),
                        tr("{count} selected controls", count=len(doc.selection))))
        out.append((Mention("form", "", doc.display_name, "layout-template"), tr("The open form")))
        out.append((Mention("code", "", "code", "file-code"), tr("Its handlers module")))
        for control in doc.form.controls[:200]:
            out.append((Mention("control", control.name, control.name, "box"), control.type))
        out.append((Mention("screenshot", "", "screenshot", "camera"), tr("A picture of the open form")))
        for rel in self.project_files():
            if rel.lower().endswith(IMAGE_SUFFIXES):
                out.append((Mention("image", rel, rel, "image"), tr("Image")))
            else:
                out.append((Mention("file", rel, rel, "file"), tr("File")))
        return out

    def add_mention(self, mention: Mention) -> Any:
        """Replaces the @query being typed with ``@label`` and attaches what it names to the message."""
        text = _TRIGGER.sub(lambda m: m.group(0)[: m.group(0).index("@")] + f"@{mention.label} ", self.input)
        if not any((m.kind, m.key, m.label) == (mention.kind, mention.key, mention.label) for m in self.mentions):
            self.mentions.append(mention)
        self.picked = 0
        return self._box(text)

    def remove_mention(self, index: int) -> Any:
        if 0 <= index < len(self.mentions):
            m = self.mentions.pop(index)
            return self._box(self.input.replace(f"@{m.label} ", "").replace(f"@{m.label}", ""))
        return None

    def _mention_blocks(self) -> List[Dict[str, Any]]:
        """The text of every @ mention, as hidden context blocks of the message."""
        import json

        doc = self.d.doc
        blocks = []
        for m in self.mentions:
            if m.kind in ("image", "screenshot"):
                try:
                    blocks.append({"type": "text", "text": f"<context>@{m.label} ({m.kind}) is attached below."
                                                           "</context>"})
                    if m.kind == "image":
                        blocks.append(_agents.image_block(self.project_root() / m.key))
                    else:  # rendered off the UI thread, just before the message goes
                        blocks.append({"type": "screenshot", "render": agent_tools.screenshot_job(self.d)})
                except Exception as err:  # noqa: BLE001 - told to the user, the message still goes
                    self.d.notify(tr("{name} was not attached: {error}", name=m.label, error=str(err)),
                                  kind="error", seconds=6)
                continue
            if m.kind == "file":
                try:
                    path = self.project_root() / m.key
                    body = path.read_bytes()[:40_000].decode("utf-8", "replace")
                except OSError:
                    continue
            elif m.kind == "form":
                body = json.dumps({"form": doc.form.name, "controls": [agent_tools._control_info(c)
                                                                        for c in doc.form.controls]},
                                  ensure_ascii=False)[:40_000]
            elif m.kind == "code":
                body = doc.code[:40_000]
            elif m.kind == "selection":
                chosen = [c for c in doc.form.controls if c.name in doc.selection]
                body = json.dumps([agent_tools._control_info(c) for c in chosen], ensure_ascii=False)[:40_000]
            else:
                found = next((c for c in doc.form.controls if c.name == m.key), None)
                if found is None:
                    continue
                body = json.dumps(agent_tools._control_info(found), ensure_ascii=False)
            blocks.append({"type": "text", "text": f"<context>@{m.label} ({m.kind}):\n{body}</context>"})
        return blocks

    # -- images ----------------------------------------------------------------------------------------
    def toggle_add_menu(self) -> None:
        self.toggle_menu("add")

    def pick_images(self) -> Any:
        """Opens the system's file dialog to attach images."""
        self.menu = None
        return _core.Command.pick_files(self.on_picked, title=tr("Attach images"),
                                        filters=[(tr("Images"), [x.lstrip(".") for x in IMAGE_SUFFIXES])],
                                        directory=str(self.project_root()))

    def on_picked(self, paths: List[str]) -> None:
        for path in paths:
            self.attach_file(path)

    def attach_file(self, path: str) -> bool:
        """Attaches the image at ``path`` to the next message; ``False`` (and a notice) when it is not one."""
        try:
            data = Path(path).read_bytes()
            _agents.Image(data).block()  # checks the format and the size
        except (OSError, ValueError) as err:
            self.d.notify(tr("{name} was not attached: {error}", name=Path(path).name, error=str(err)), kind="error",
                          seconds=6)
            return False
        self.attachments.append(Attachment(Path(path).name, data))
        return True

    def paste_image(self) -> Any:
        """Attaches the image on the clipboard (a screenshot, a copied picture)."""
        self.menu = None
        return _core.Command.paste_image(self.on_clipboard_image)

    def on_clipboard_image(self, png: Optional[bytes]) -> None:
        if not png:
            self.d.notify(tr("The clipboard has no image"), kind="warning", seconds=4)
            return
        self.attachments.append(Attachment(tr("Pasted image"), bytes(png)))

    def attach_screenshot(self) -> None:
        """Attaches a picture of the open form (rendered off-screen, in the background)."""
        self.menu = None
        try:
            render = agent_tools.screenshot_job(self.d)
        except ValueError as err:
            self.d.notify(str(err), kind="warning", seconds=5)
            return
        self.busy_provider = "screenshot"
        put, name = self._queue.put, f"{self.d.doc.display_name}.png"

        def work() -> None:
            try:
                put(("attach", name, render()))
            except Exception as err:  # noqa: BLE001
                put(("provider", tr("The screenshot failed: {error}", error=str(err)), False))

        threading.Thread(target=work, daemon=True, name="pyzed-agent-screenshot").start()

    def remove_attachment(self, index: int) -> None:
        if 0 <= index < len(self.attachments):
            del self.attachments[index]

    # -- creating documents (used by the new_document tool, on the UI thread) ------------------------
    def create_document(self, kind: str, name: str, folder: str = "", title: str = "") -> Dict[str, Any]:
        from . import new as _new
        from . import scene as _scene
        from . import scene_code as _scene_code
        from .model import SUFFIX

        base = self.d.doc.path.resolve().parent if self.d.doc.path else self.project_root()
        where = (base / folder).resolve() if folder else base
        if kind == "component":
            path = where / f"{_scene_code.member_identifier(name)}{_scene.SUFFIX}"
        elif kind == "form":
            from .model import identifier

            path = where / f"{identifier(name) or 'form1'}{SUFFIX}"
        else:
            raise ValueError('kind must be "form" or "component"')
        root = self.project_root().resolve()
        if path != root and root not in path.parents:
            raise PermissionError(f"{path} is outside the project folder")
        if path.exists():
            raise FileExistsError(f"{path.name} already exists; open it or pick another name")
        path.parent.mkdir(parents=True, exist_ok=True)
        if kind == "component":
            doc = _scene.new_component(name, path)
            doc.form.grid = self.d.prefs.grid
            doc.save()
        else:
            _new.new_form(path, title=title or None, template="blank")
        self.d.open_path(path)
        return {"created": str(path), "kind": kind, "now_open": self.d.doc.display_name}

    # -- inline assist ------------------------------------------------------------------------------
    def open_inline(self) -> Any:
        """Opens the inline assist bar over the code editor."""
        if self.d.editing is None:
            return None
        if self.inline is None or not self.inline.running:
            self.inline = InlineAssist()
        return _core.Command.focus(INLINE_ID)

    def close_inline(self) -> None:
        if self.inline is not None and self.inline.running:
            return
        self.inline = None

    def set_inline(self, text: str) -> None:
        if self.inline is not None:
            self.inline.prompt = text

    def submit_inline(self) -> None:
        """Asks the model to rewrite the code in the editor following the prompt."""
        a = self.inline
        if a is None or a.running or not a.prompt.strip() or self.d.editing is None:
            return
        if not self.ready:
            a.error = tr("Set up a model provider first.")
            return
        handler, code = self.d.editing
        a.running, a.answer, a.error = True, "", ""
        a.before = code
        what = "the whole handlers module" if handler == "*" else f"the handler {handler}()"
        form = self.d.doc.form
        controls = ", ".join(f"{c.name} ({c.type})" for c in form.controls[:60])
        prompt = (f"Instruction: {a.prompt.strip()}\n\nThis is {what} of the form {form.name}; its controls are: "
                  f"{controls or 'none'}.\n\n```python\n{code}```")
        model = self.thread.model or self.settings.model
        settings = _providers.AgentSettings.from_dict({**self.settings.to_dict(), "profile": "minimal"})
        put = self._queue.put
        stream = self._stream

        def work() -> None:
            try:
                turn = stream(model, INLINE_SYSTEM, [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                              (), settings=settings, cancel=threading.Event(),
                              on_event=lambda k, t: put(("inline", "delta", t)) if k == "text" else None)
                put(("inline", "done", turn.text))
            except Exception as err:  # noqa: BLE001
                put(("inline", "error", str(err)))

        threading.Thread(target=work, daemon=True, name="pyzed-inline-assist").start()

    def _on_inline(self, kind: str, text: str) -> None:
        a = self.inline
        if a is None:
            return
        if kind == "delta":
            a.answer += text
            return
        a.running = False
        if kind == "error":
            a.error = text
            return
        code = extract_code(text)
        if code is None:
            a.error = tr("The answer had no code.")
            return
        self.d.set_code_buffer(code)
        self.d.code_revision += 1

    def undo_inline(self) -> None:
        """Puts back the code inline assist replaced."""
        if self.inline is not None and self.inline.before is not None:
            self.d.set_code_buffer(self.inline.before)
            self.d.code_revision += 1
        self.inline = None

    # -- provider settings --------------------------------------------------------------------------
    def toggle_provider(self, pid: str) -> None:
        self.provider_open = None if self.provider_open == pid else pid

    def set_key_buffer(self, pid: str, text: str) -> None:
        self.key_buffer[pid] = text

    def save_key(self, pid: str) -> None:
        key = self.key_buffer.pop(pid, "").strip()
        if not key:
            return
        secure = _agents.set_key(pid, key)
        if secure:
            self.d.notify(tr("Key saved in the system keychain"), kind="success")
        else:
            self.d.notify(tr("No system keychain: the key is kept until you close the designer"), kind="warning",
                          seconds=6)
        if self.capture is not None and self.capture.provider == pid:
            self.capture = None
        self.refresh_models(pid)

    def remove_key(self, pid: str) -> None:
        _agents.delete_key(pid)
        if pid == "anthropic" and _agents.login.ant_signed_in():
            self._background(pid, lambda: _agents.login.ant_logout(), tr("Signed out"))
        else:
            self.d.notify(tr("Key removed"), kind="info")

    def set_url(self, pid: str, text: str) -> None:
        self.settings.provider(pid).base_url = text.strip()
        self.save_settings()

    def _background(self, pid: str, work: Callable[[], Any], success: str) -> None:
        self.busy_provider = pid
        put = self._queue.put

        def run() -> None:
            try:
                work()
                put(("provider", success, True))
            except Exception as err:  # noqa: BLE001
                put(("provider", str(err), False))

        threading.Thread(target=run, daemon=True, name="pyzed-agent-settings").start()

    def sign_in(self, pid: str) -> None:
        """Signs in to ``pid`` with the browser, with no other program needed. OpenRouter uses OAuth; the
        others open a page Pyzed serves on this computer, which links to the provider's key page and takes
        the key (a copied key is picked up too). The designer comes back to the front once it is in."""
        provider = _providers.PROVIDERS[pid]
        self.provider_open = pid
        if provider.login == "device" and self.settings.client_id(pid):
            return self._device_sign_in(pid)
        if provider.login == "google":
            return self._google_sign_in(pid)
        if provider.login == "oauth":

            def work() -> None:
                key = _agents.login.login(pid)
                if key:
                    _agents.set_key(pid, key)
                    self._queue.put(("models", pid, _agents.list_models(pid, self.settings, key=key)))

            self._background(pid, work, tr("Signed in to {provider}", provider=provider.name))
            return
        capture = self.capture = KeyCapture(pid, deadline=time.monotonic() + CAPTURE_SECONDS)
        self._portal(pid, capture)

    def _portal(self, pid: str, capture: KeyCapture) -> None:
        """Serves the sign-in page (``login.key_portal``) until a key arrives there, the clipboard brings one
        or the sign-in is cancelled; falls back to opening the provider's key page."""
        settings, put = self.settings, self._queue.put
        found: Dict[str, List[str]] = {}

        def check(key: str) -> Optional[str]:
            try:
                found[key] = _agents.list_models(pid, settings, key=key)
            except Exception as err:  # noqa: BLE001 - shown on the page
                return str(err) or type(err).__name__
            return None

        def run() -> None:
            try:
                key = _agents.login.key_portal(pid, check, timeout=CAPTURE_SECONDS,
                                               cancelled=lambda: self.capture is not capture)
            except _agents.login.LoginError:  # the wait ran out (the capture expires too)
                return
            except Exception:  # noqa: BLE001 - no local page; open the key page, the clipboard still works
                try:
                    _agents.login.key_page(pid)
                except Exception as err:  # noqa: BLE001
                    put(("provider", str(err), False))
                return
            if key:
                put(("key", pid, key, found.get(key, []), ""))

        threading.Thread(target=run, daemon=True, name="pyzed-agent-portal").start()

    def _device_sign_in(self, pid: str) -> None:
        """GitHub's device flow: a code to type on github.com, while Pyzed waits for the token."""
        login = self.device = DeviceLogin(pid)
        client_id, settings, put = self.settings.client_id(pid), self.settings, self._queue.put

        def work() -> None:
            try:
                code = _agents.login.github_device_code(client_id)
                put(("device", pid, code.user_code, code.verification_uri))
                _agents.login.open_browser(code.verification_uri)
                token = _agents.login.github_device_token(client_id, code, cancelled=lambda: login.cancelled)
                _providers.save_token(pid, token)
                put(("models", pid, _agents.list_models(pid, settings)))
            finally:
                put(("device_done",))

        self._background(pid, work, tr("Signed in to {provider}", provider=_providers.PROVIDERS[pid].name))

    def cancel_device(self) -> None:
        if self.device is not None:
            self.device.cancelled = True
        self.device = None

    def copy_device_code(self) -> Any:
        return _core.Command.copy(self.device.user_code) if self.device and self.device.user_code else None

    def _google_sign_in(self, pid: str) -> None:
        """Google sign-in in the browser (PKCE); then the account's Google Cloud projects are listed."""
        client_id, secret = _agents.login.google_client(self.settings)
        put = self._queue.put

        def work() -> None:
            token = _agents.login.google_login(client_id, secret)
            _providers.save_token(pid, token)
            put(("projects", pid, _agents.login.google_projects(token["access_token"])))

        self._background(pid, work, tr("Signed in to {provider}", provider=_providers.PROVIDERS[pid].name))

    def load_google_projects(self, pid: str = "vertex") -> None:
        put, settings = self._queue.put, self.settings

        def work() -> None:
            token = _providers.api_key(pid, settings=settings)
            if not token:
                raise RuntimeError(tr("Sign in with Google first"))
            put(("projects", pid, _agents.login.google_projects(token)))

        self._background(pid, work, tr("Projects loaded"))

    def set_provider_field(self, pid: str, key: str, value: str) -> None:
        """Changes a provider's OAuth client ID, Google Cloud project or location."""
        setattr(self.settings.provider(pid), key, value.strip())
        self.save_settings()

    def set_google_secret(self, value: str) -> None:
        """Keeps the Google OAuth client's secret in the keychain."""
        if value.strip():
            _agents.secrets.store().set("agents.vertex.client_secret", value.strip())
        else:
            _agents.secrets.store().delete("agents.vertex.client_secret")

    # -- workload identity federation (Claude) ---------------------------------------------------------
    def set_federation(self, key: str, value: str) -> None:
        setattr(self.settings.federation, key, value.strip() if key != "token_command" else value)
        self.save_settings()

    def test_provider(self, pid: str) -> None:
        """Checks the provider's credentials by asking for its models."""
        self.refresh_models(pid)

    # -- MCP servers and external agents ---------------------------------------------------------------
    def new_server(self, kind: str, preset: str = "") -> None:
        """Opens the form to add an MCP server (``kind="mcp"``) or an external agent (``"acp"``)."""
        if kind == "acp" and preset in _acp.PRESETS:
            title, command, args = _acp.PRESETS[preset]
            self.server_draft = {"kind": "acp", "name": preset, "command": " ".join([command, *args]), "url": "",
                                 "secrets": "", "title": title, "editing": None}
        else:
            self.server_draft = {"kind": kind, "name": "", "command": "", "url": "", "secrets": "", "title": "",
                                 "editing": None}

    def edit_server(self, kind: str, name: str) -> None:
        config = self.settings.mcp_server(name) if kind == "mcp" else self.settings.acp_agent(name)
        if config is None:
            return
        hidden = _mcp.get_secrets(name if kind == "mcp" else f"acp.{name}")
        self.server_draft = {"kind": kind, "name": config.name, "url": getattr(config, "url", ""),
                             "command": _agents.providers.join_command([config.command, *config.args]) if config.command else "",
                             "secrets": "; ".join(f"{k}={v}" for k, v in hidden.items()),
                             "title": getattr(config, "title", ""), "editing": name}

    def set_draft(self, key: str, value: str) -> None:
        if self.server_draft is not None:
            self.server_draft[key] = value

    def cancel_draft(self) -> None:
        self.server_draft = None

    def save_draft(self) -> None:
        """Saves the MCP server or external agent being edited; its secrets go to the keychain."""
        draft = self.server_draft
        if draft is None:
            return
        name = re.sub(r"[^A-Za-z0-9_-]+", "-", draft["name"].strip()).strip("-")
        try:
            parts = _agents.providers.split_command(draft["command"].strip()) if draft["command"].strip() else []
        except ValueError as err:
            self.d.notify(tr("The command is not valid: {error}", error=str(err)), kind="error", seconds=5)
            return
        url = draft["url"].strip()
        if not name or not (parts or (draft["kind"] == "mcp" and url)):
            self.d.notify(tr("Give it a name and a command") if draft["kind"] == "acp" else
                          tr("Give it a name and a command or a URL"), kind="warning", seconds=5)
            return
        hidden: Dict[str, str] = {}
        for line in re.split(r"[;\n]", draft["secrets"]):
            key, sep, value = line.partition("=") if "=" in line else line.partition(":")
            if sep and key.strip():
                hidden[key.strip()] = value.strip()
        kind, old = draft["kind"], draft["editing"]
        items = self.settings.mcp_servers if kind == "mcp" else self.settings.acp_agents
        others = [c for c in items if c.name not in (old, name)]
        if kind == "mcp":
            config: Any = _providers.MCPServerConfig(name, parts[0] if parts else "", parts[1:], "" if parts else url,
                                                     sorted(hidden))
        else:
            config = _providers.ACPAgentConfig(name, parts[0], parts[1:], sorted(hidden), title=draft["title"].strip())
        items[:] = [*others, config]
        if old and old != name:
            _mcp.set_secrets(old if kind == "mcp" else f"acp.{old}", {})
        _mcp.set_secrets(name if kind == "mcp" else f"acp.{name}", hidden)
        self.server_draft = None
        self.save_settings()
        self.mcp.update(self.settings.mcp_servers)
        self.mcp_status.pop(name, None)
        if kind == "mcp":
            self.test_server(name)

    def remove_server(self, kind: str, name: str) -> None:
        items = self.settings.mcp_servers if kind == "mcp" else self.settings.acp_agents
        items[:] = [c for c in items if c.name != name]
        _mcp.set_secrets(name if kind == "mcp" else f"acp.{name}", {})
        self.save_settings()
        self.mcp.update(self.settings.mcp_servers)
        if kind == "acp" and self.thread.model == f"acp:{name}":
            self.set_model(_providers.DEFAULT_MODEL)

    def toggle_server(self, kind: str, name: str) -> None:
        config = self.settings.mcp_server(name) if kind == "mcp" else self.settings.acp_agent(name)
        if config is not None:
            config.enabled = not config.enabled
            self.save_settings()
            self.mcp.update(self.settings.mcp_servers)

    def test_server(self, name: str) -> None:
        """Starts the MCP server ``name`` and lists its tools (in the background)."""
        self.busy_provider = f"mcp:{name}"
        servers, put = self.mcp, self._queue.put
        servers.cwd = str(self.project_root())

        def work() -> None:
            try:
                specs = servers.tool_specs(name)
                put(("mcp_test", name, tr("{count} tools", count=len(specs)), True))
            except Exception as err:  # noqa: BLE001
                put(("mcp_test", name, str(err), False))

        threading.Thread(target=work, daemon=True, name="pyzed-agent-mcp").start()

    def connect(self, pid: str) -> None:
        """Connects ``pid`` from the panel: signs in with the browser, or (local servers) asks for models."""
        provider = _providers.PROVIDERS[pid]
        self.menu = None
        self.open_settings(pid)
        if pid == "acp":
            return
        if provider.login:
            self.sign_in(pid)
        elif not provider.needs_key and provider.base_url:
            self.refresh_models(pid)

    def cancel_capture(self) -> None:
        self.capture = None

    def paste_key(self, pid: str) -> Any:
        """Reads a key from the clipboard right now (the Paste button)."""
        if self.capture is None or self.capture.provider != pid:
            self.capture = KeyCapture(pid, deadline=time.monotonic() + CAPTURE_SECONDS)
        self.capture.tried.clear()
        return _core.Command.paste(lambda text: self.on_clipboard(text, explicit=True))

    def on_clipboard(self, text: str, explicit: bool = False) -> None:
        """Checks what was copied: a key of the provider being signed in to is verified and saved."""
        capture = self.capture
        if capture is None or capture.checking:
            return
        key = (text or "").strip()
        if not _providers.looks_like_key(capture.provider, key):
            if explicit:
                self.d.notify(tr("The clipboard has no {provider} key",
                                 provider=_providers.PROVIDERS[capture.provider].name), kind="warning", seconds=5)
            return
        if key in capture.tried:
            return
        capture.tried.add(key)
        capture.checking = True
        self.busy_provider = capture.provider
        pid, settings, put = capture.provider, self.settings, self._queue.put

        def check() -> None:
            try:
                put(("key", pid, key, _agents.list_models(pid, settings, key=key), ""))
            except Exception as err:  # noqa: BLE001 - shown to the user
                put(("key", pid, key, None, str(err)))

        threading.Thread(target=check, daemon=True, name="pyzed-agent-key").start()

    def _on_key_checked(self, pid: str, key: str, models: Optional[List[str]], error: str) -> None:
        self.busy_provider = None
        capture = self.capture
        if capture is not None and capture.provider == pid:
            capture.checking = False
        if models is None:
            self.d.notify(tr("{provider} refused that key: {error}", provider=_providers.PROVIDERS[pid].name,
                             error=error), kind="error", seconds=7)
            return
        self.capture = None
        self.raise_window = True
        secure = _agents.set_key(pid, key)
        if models:
            self.settings.provider(pid).models = models
            self.save_settings()
        self.d.notify(tr("Signed in to {provider}", provider=_providers.PROVIDERS[pid].name) + ". "
                      + (tr("Key saved in the system keychain") if secure else
                         tr("No system keychain: the key is kept until you close the designer")),
                      kind="success" if secure else "warning", seconds=5)
        # the thread's model now works if it belongs to this provider; else offer the provider's first model
        current, _ = _providers.split_model(self.thread.model or self.settings.model)
        if not _providers.is_ready(current):
            first = self.settings.models_of(pid)
            if first:
                self.set_model(f"{pid}:{first[0]}")

    def refresh_models(self, pid: str) -> None:
        self.busy_provider = pid
        put = self._queue.put
        settings = self.settings

        def run() -> None:
            try:
                put(("models", pid, _agents.list_models(pid, settings)))
            except Exception as err:  # noqa: BLE001
                put(("provider", str(err), False))

        threading.Thread(target=run, daemon=True, name="pyzed-agent-models").start()

    # -- Claude subscription (through Claude Code) ------------------------------------------------------
    def use_claude_subscription(self) -> None:
        """Uses the user's Claude subscription (Pro or Max) through Claude Code, Anthropic's own agent: adds it
        as an external agent, picks it, and opens Claude Code in a terminal to sign in when it is not yet."""
        if _platform.which("npx") is None:
            self.d.notify(tr("Claude Code needs Node.js 22 or later"), tr("Install it, then try again."),
                          kind="warning", seconds=8)
            _agents.login.open_browser(NODE_URL)
            return
        if self.settings.acp_agent("claude-code") is None:
            self.settings.acp_agents.append(_acp.preset("claude-code"))
        self.settings.share_pyzed_mcp = True
        self.set_model("acp:claude-code")
        if _acp.claude_signed_in():
            self.d.notify(tr("Claude Code is ready"), tr("It uses your Claude subscription"), kind="success",
                          seconds=5)
            return
        self.open_claude_login()

    def open_claude_login(self) -> None:
        """Opens Claude Code in a terminal so the user signs in to their Claude account; the panel waits for it."""
        from .file_ops import run_in_terminal

        try:
            run_in_terminal(_acp.claude_login_command(), self.project_root())
        except OSError as err:
            self.d.notify(tr("No terminal was found"), tr("Run {command} in a terminal to sign in", command=" ".join(
                _acp.claude_login_command())) + f" ({err})", kind="warning", seconds=10)
        self.claude_login = time.monotonic() + CLAUDE_LOGIN_SECONDS
        self._claude_check = 0.0

    def cancel_claude_login(self) -> None:
        self.claude_login = None

    def _check_claude_login(self) -> None:
        now = time.monotonic()
        if self.claude_login is None or now < self._claude_check:
            return
        self._claude_check = now + 2.0
        if _acp.claude_signed_in():
            self.claude_login = None
            self.raise_window = True
            self.close_external_agents()  # a session opened before the sign-in starts again
            self.d.notify(tr("Signed in to Claude"), tr("Claude Code uses your Claude subscription"), kind="success",
                          seconds=6)
        elif now > self.claude_login:
            self.claude_login = None

    @property
    def needs_node(self) -> bool:
        """Whether the last answer failed because the external agent needs Node.js, which is not installed."""
        return "needs Node.js" in self.error

    @property
    def needs_claude_login(self) -> bool:
        """Whether the last answer failed because Claude Code is not signed in."""
        provider, name = _providers.split_model(self.thread.model or self.settings.model)
        error = self.error.lower()
        return provider == "acp" and name == "claude-code" and ("auth" in error or "/login" in error)

    def _notify_desktop(self, title: str, body: str) -> None:
        """A desktop notification while the designer's window is in the background (like Zed's)."""
        if not self.settings.notify_when_done or getattr(self.d, "window_focused", True):
            return
        from .. import _platform

        _platform.notify(title, body[:200])

    @property
    def context_window(self) -> int:
        """The context window of the thread's model (0 when unknown, or for an external agent)."""
        return _providers.context_window(self.thread.model or self.settings.model)

    # -- following the agent, like Zed's "Follow" -------------------------------------------------------
    def toggle_follow(self) -> None:
        """Turns following the agent on or off: the files it writes (and where an external agent edits) open
        as it works, so what it builds shows up live."""
        self.settings.follow_agent = not self.settings.follow_agent
        self.save_settings()

    def _on_file(self, raw: str, written: bool) -> None:
        """The agent wrote ``raw`` (or edits there): shows the new text where the file is open, and with
        Follow on, opens it (forms and components in their tab, other text files in the code editor)."""
        root = self.project_root().resolve()
        path = Path(raw) if Path(raw).is_absolute() else root / raw
        try:
            path = path.resolve()
            path.relative_to(root)
        except (OSError, ValueError):
            return
        if written:
            self._reload(path)
        if not self.settings.follow_agent or not path.is_file():
            return
        from .workspace import DESIGN_SUFFIXES

        focus = self.d.focus  # the input keeps the keyboard
        if path.suffix in DESIGN_SUFFIXES:
            self.d.open_path(path)
        else:
            self.d.buffers.open(path)
        self.d.focus = focus

    def _reload(self, path: Path) -> None:
        """Rereads ``path`` where it is open without unsaved changes (written by the agent)."""
        from . import files as _files
        from . import scene as _scene

        index = self.d.buffers.index_of(path)
        if index is not None:
            buffer = self.d.buffers.items[index]
            text = _files.read_text(path)
            if text is not None and not buffer.dirty and text != buffer.text:
                buffer.text = buffer.saved = text
                buffer.revision += 1
        found = self.d.panes.find_path(path)
        if found is not None:
            pane, i = found
            if not pane.docs[i].dirty:
                try:
                    pane.docs[i] = _scene.open_document(path)
                except (OSError, ValueError):
                    return
                self.d.code_revision += 1

    # -- signing in to an external agent, like Zed ------------------------------------------------------
    def pick_auth(self, method_id: str) -> None:
        """Signs in to the external agent that asked for it, with one of its ways to sign in: the agent opens
        the browser itself (and the panel waits for it), the agent's login runs in a terminal (and the panel
        checks every few seconds), or a key goes in the agent's secrets."""
        auth = self.agent_auth
        agent = self._acp.get(self.thread.id)
        method = next((m for m in (auth.methods if auth else []) if str(m.get("id")) == method_id), None)
        if auth is None or agent is None or method is None:
            return
        auth.error = ""
        kind = _acp.auth_kind(method)
        if kind == "env_var":
            var = str(method.get("varName") or method.get("var_name") or method.get("name") or "")
            if method.get("link"):
                _agents.login.open_browser(str(method["link"]))
            auth.error = tr("Add {name} to the agent's secrets in the settings, then send the message again.",
                            name=var)
            self.open_settings(section="agents")
            return
        auth.waiting = method_id
        if kind == "terminal":
            from .file_ops import run_in_terminal

            command, env = _acp.terminal_login(agent.config, method)
            if agent.config.name == "claude-code" and not (method.get("_meta") or {}).get("terminal-auth"):
                command, env = _acp.claude_login_command(), {}
            try:
                run_in_terminal(command, self.project_root(), **({"env": env} if env else {}))
            except OSError as err:
                auth.waiting = ""
                auth.error = tr("Run {command} in a terminal to sign in", command=" ".join(command)) + f" ({err})"
                return
            auth.until = time.monotonic() + AGENT_LOGIN_SECONDS
            auth.next_check = time.monotonic() + AGENT_LOGIN_EVERY
            return
        self._job(lambda: agent.authenticate(method_id), self._signed_in_to_agent)

    def _check_agent_login(self) -> None:
        """While the agent's login runs in a terminal: tries to open its session every few seconds."""
        auth, now = self.agent_auth, time.monotonic()
        if auth is None or auth.checking or now < auth.next_check:
            return
        if now > auth.until:
            auth.until, auth.waiting = 0.0, ""
            return
        agent = self._acp.get(self.thread.id)
        if agent is None:
            self.agent_auth = None
            return
        auth.next_check = now + AGENT_LOGIN_EVERY
        if agent.config.name == "claude-code" and not _acp.claude_signed_in():  # cheap: no need to start it
            return
        auth.checking = True

        def then(ok: Any, error: Optional[BaseException]) -> None:
            auth.checking = False
            if ok and self.agent_auth is auth:
                self._signed_in_to_agent(None, None)

        self._job(agent.signed_in, then)

    def _signed_in_to_agent(self, _value: Any, error: Optional[BaseException]) -> None:
        auth = self.agent_auth
        if auth is None or not auth.waiting:  # cancelled meanwhile
            return
        if error is not None:
            auth.waiting, auth.until = "", 0.0
            auth.error = str(error)
            return
        self.agent_auth = None
        self.raise_window = True
        self.d.notify(tr("Signed in to {name}", name=auth.label), kind="success", seconds=4)
        if auth.prompt and not self.running:
            self._launch(auth.prompt)

    def cancel_auth(self) -> None:
        """Stops waiting for an external agent's sign-in (its program stops; the next message starts it again)."""
        auth, self.agent_auth = self.agent_auth, None
        if auth is not None and auth.waiting:
            agent = self._acp.get(self.thread.id)
            if agent is not None:
                agent.close()

    def open_key_page(self, pid: str) -> None:
        url = _providers.PROVIDERS[pid].key_url
        if url:
            _agents.login.open_browser(url)

    # -- the panel's menus and options --------------------------------------------------------------
    def toggle_option(self, key: str) -> None:
        """Flips a yes/no setting from the panel's ⋯ menu."""
        setattr(self.settings, key, not getattr(self.settings, key))
        self.save_settings()

    def thread_markdown(self) -> str:
        """The thread as Markdown (what "Copy thread as Markdown" copies)."""
        out = [f"# {self.thread.display_title}", ""]
        for m in self.thread.messages:
            for b in m.get("content", []):
                kind = b.get("type")
                if kind == "text" and not b.get("text", "").startswith("<context>"):
                    out += [f"## {'User' if m.get('role') == 'user' else 'Agent'}", "", b["text"].strip(), ""]
                elif kind == "tool_use":
                    preview = _args_preview(b.get("input") or {})
                    out += [f"- `{b.get('name', '')}`" + (f" {preview}" if preview else ""), ""]
        return "\n".join(out).rstrip() + "\n"

    def copy_text(self, text: str) -> Any:
        """Copies ``text`` (an answer) to the clipboard and says so."""
        self.d.notify(tr("Copied to the clipboard"), kind="success", seconds=2, log=False)
        return _core.Command.copy(text)

    def copy_markdown(self) -> Any:
        self.menu = None
        self.d.notify(tr("Thread copied as Markdown"), kind="success", seconds=3)
        return _core.Command.copy(self.thread_markdown())

    # -- the agent's changes, file by file -------------------------------------------------------------
    def file_changes(self) -> List[Dict[str, Any]]:
        """The documents the agent changed in its last run, with the lines added and removed in their code."""
        import difflib

        out = []
        for doc, _form, code in self.snapshot:
            added = removed = 0
            for line in difflib.unified_diff(code.splitlines(), doc.code.splitlines(), lineterm="", n=0):
                if line.startswith("+") and not line.startswith("+++"):
                    added += 1
                elif line.startswith("-") and not line.startswith("---"):
                    removed += 1
            out.append({"path": doc.display_name, "added": added, "removed": removed})
        return out

    def _entry(self, name: str) -> Optional[Tuple[Any, Any, str]]:
        return next((e for e in self.snapshot if e[0].display_name == name), None)

    def keep_file(self, name: str) -> None:
        """Keeps the agent's changes to one document."""
        self.snapshot = [e for e in self.snapshot if e[0].display_name != name]
        self.changed = bool(self.snapshot)

    def reject_file(self, name: str) -> None:
        """Puts one document back as it was before the agent's run."""
        entry = self._entry(name)
        if entry is None:
            return
        rest = [e for e in self.snapshot if e is not entry]
        self.snapshot = [entry]
        self.reject()
        self.snapshot = rest
        self.changed = bool(rest)

    def open_file(self, name: str) -> None:
        """Brings the tab of a document the agent changed to the front."""
        entry = self._entry(name)
        if entry is not None and entry[0] in self.d.docs:
            self.d.active_doc = self.d.docs.index(entry[0])

    # -- background jobs --------------------------------------------------------------------------------
    def _job(self, work: Callable[[], Any], then: Callable[[Any, Optional[BaseException]], Any]) -> None:
        """Runs ``work`` off the UI thread; ``then(value, error)`` runs on it when done."""
        self._jobs += 1
        put = self._queue.put

        def run() -> None:
            try:
                put(("job", then, work(), None))
            except Exception as err:  # noqa: BLE001 - handed to ``then``
                put(("job", then, None, err))

        threading.Thread(target=run, daemon=True, name="pyzed-agent-job").start()

    # -- external agents from the ACP registry ---------------------------------------------------------
    def toggle_registry(self, show: Optional[bool] = None) -> None:
        """Shows (or hides) the agents of the ACP registry, loading it the first time."""
        self.registry_open = (not self.registry_open) if show is None else show
        if self.registry_open and not self.registry and self.registry_busy != "*":
            self.load_registry()

    def load_registry(self, refresh: bool = False) -> None:
        from ..agents import registry

        self.registry_busy = "*"
        self.registry_error = ""

        def then(agents: Any, error: Optional[BaseException]) -> None:
            self.registry_busy = ""
            if error is not None:
                self.registry_error = str(error)
            else:
                self.registry = list(agents)

        self._job(lambda: registry.fetch(refresh=refresh), then)

    def registry_items(self) -> List[Dict[str, Any]]:
        """The registry's agents for ``ui.Catalog``: installed ones and their updates marked."""
        from ..agents import registry

        installed = {a.registry_id: a for a in self.settings.acp_agents if a.registry_id}
        items = []
        for agent in self.registry:
            mine = installed.get(agent.id)
            newer = registry.update_available(mine, [agent]) if mine is not None else None
            items.append({"id": agent.id, "name": agent.name, "version": agent.version,
                          "description": agent.description, "installed": mine is not None,
                          "update": newer.version if newer is not None else ""})
        return items

    def agent_update(self, config: _providers.ACPAgentConfig) -> str:
        """The newer version of an installed registry agent ("" when there is none or the registry is not loaded)."""
        from ..agents import registry

        if not config.registry_id or not self.registry:
            return ""
        newer = registry.update_available(config, self.registry)
        return newer.version if newer is not None else ""

    def install_agent(self, agent_id: str) -> None:
        """Installs (or updates) an agent of the ACP registry and adds it to the new-thread menu."""
        from ..agents import registry

        agent = registry.find(self.registry, agent_id)
        if agent is None or self.registry_busy:
            return
        self.registry_busy = agent_id

        def then(config: Any, error: Optional[BaseException]) -> None:
            self.registry_busy = ""
            if error is not None:
                self.d.notify(tr("{name} was not installed", name=agent.name), str(error), kind="error", seconds=8)
                return
            old = next((a for a in self.settings.acp_agents if a.registry_id == agent.id), None)
            if old is not None:
                config.name, config.enabled = old.name, old.enabled
            elif self.settings.acp_agent(config.name) is not None:
                config.name = agent.id
            self.settings.acp_agents[:] = [a for a in self.settings.acp_agents
                                           if a.name != config.name and a.registry_id != agent.id] + [config]
            self.save_settings()
            self.close_external_agents()
            self.d.notify(tr("{name} {version} is ready", name=agent.name, version=agent.version),
                          tr("Start a thread with it from the + menu"), kind="success", seconds=5)

        self._job(lambda: registry.install(agent), then)

    def update_agent(self, name: str) -> None:
        config = self.settings.acp_agent(name)
        if config is not None and config.registry_id:
            self.install_agent(config.registry_id)

    def uninstall_agent(self, name: str) -> None:
        """Removes an external agent (and the files it was installed with from the registry)."""
        from ..agents import registry

        config = self.settings.acp_agent(name)
        if config is None:
            return
        if config.registry_id:
            try:
                registry.uninstall(config)
            except OSError as err:
                self.d.notify(tr("Some files were not removed"), str(err), kind="warning", seconds=6)
        self.remove_server("acp", name)

    # -- agent skills ------------------------------------------------------------------------------------
    def skills(self) -> List[Any]:
        """The skills found for the open project (looked up once; ``refresh_skills`` looks again)."""
        if self._skills is None:
            from ..agents import skills

            try:
                self._skills = skills.discover(self.project_root())
            except OSError:
                self._skills = []
        return self._skills

    def refresh_skills(self) -> None:
        self._skills = None

    def toggle_skill(self, name: str, on: bool) -> None:
        off = [n for n in self.settings.disabled_skills if n != name]
        self.settings.disabled_skills = off if on else [*off, name]
        self.save_settings()

    def set_skill_url(self, text: str) -> None:
        self.skill_url = text

    def _skill_job(self, label: str, work: Callable[[], Any], done: str) -> None:
        self.skill_busy = label

        def then(_value: Any, error: Optional[BaseException]) -> None:
            self.skill_busy = ""
            self.refresh_skills()
            if error is not None:
                self.d.notify(tr("The skill could not be installed"), str(error), kind="error", seconds=8)
            else:
                self.d.notify(done, kind="success", seconds=4)

        self._job(work, then)

    def install_skill_url(self) -> None:
        """Installs the skills of a Git repository (its https URL)."""
        from ..agents import skills

        url = self.skill_url.strip()
        if not url or self.skill_busy:
            return
        self.skill_url = ""
        self._skill_job("*", lambda: skills.install_git(url), tr("Skills installed"))

    def pick_skill_folder(self) -> Any:
        return _core.Command.pick_files(self.install_skill_folder, title=tr("Choose a skill folder"), folder=True,
                                         multiple=False)

    def install_skill_folder(self, paths: Any) -> None:
        from ..agents import skills

        chosen = paths[0] if isinstance(paths, (list, tuple)) and paths else paths
        if not chosen or self.skill_busy:
            return
        self._skill_job("*", lambda: skills.install_folder(Path(chosen)), tr("Skill installed"))

    def _skill(self, name: str) -> Optional[Any]:
        return next((s for s in self.skills() if s.name == name), None)

    def update_skill(self, name: str) -> None:
        from ..agents import skills

        found = self._skill(name)
        if found is not None and not self.skill_busy:
            self._skill_job(name, lambda: skills.update(found), tr("{name} is up to date", name=name))

    def remove_skill(self, name: str) -> None:
        from ..agents import skills

        found = self._skill(name)
        if found is None:
            return
        try:
            skills.remove(found)
        except (OSError, skills.SkillError) as err:
            self.d.notify(tr("The skill was not removed"), str(err), kind="error", seconds=6)
        self.refresh_skills()

    def open_skill_folder(self, name: str) -> None:
        found = self._skill(name)
        if found is not None:
            from .workspace import reveal

            reveal(found.path)

    def set_setting(self, key: str, value: Any) -> None:
        setattr(self.settings, key, value)
        self.save_settings()


# -- views -------------------------------------------------------------------------------------------

#: An MCP tool as external agents name it: ``mcp__<server>__<tool>``.
_MCP_NAME = re.compile(r"^mcp__[\w.-]+?__(\w+)$")


def _tool_title(tool_name: str, tools: Dict[str, _agents.Tool]) -> str:
    """What a tool call does, in words: the tool's title (also for Pyzed's tools an external agent calls)."""
    found = _MCP_NAME.match(tool_name)
    tool_ = tools.get(found.group(1) if found else tool_name)
    if tool_ is not None and tool_.title:
        return tr(tool_.title)
    return found.group(1).replace("_", " ").capitalize() if found else tool_name


#: The arguments that best say what a call works on, in order.
_PREVIEW_KEYS = ("name", "path", "file_path", "notebook_path", "type", "handler", "event", "control", "command",
                 "query", "pattern", "url", "slug", "topic", "kind", "description", "title")


def _args_preview(args: Dict[str, Any]) -> str:
    for key in _PREVIEW_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            first = value.strip().splitlines()[0]
            return first if len(first) <= 80 else first[:79] + "…"
    names = args.get("names") or args.get("controls")
    if isinstance(names, list) and names:
        items = [n if isinstance(n, str) else str((n or {}).get("name") or (n or {}).get("type") or "")
                 for n in names[:6]]
        return ", ".join(i for i in items if i) + (f" +{len(names) - 6}" if len(names) > 6 else "")
    return ""


def _call_detail(c: "AgentController", block: Dict[str, Any]) -> str:
    """What a call works on: the files an external agent named (relative to the project), else its arguments."""
    locations = block.get("locations") or []
    if locations:
        root = c.project_root()
        try:
            first = str(Path(locations[0]).resolve().relative_to(root.resolve()))
        except (ValueError, OSError):
            first = str(locations[0])
        return first + (f" +{len(locations) - 1}" if len(locations) > 1 else "")
    return _args_preview(block.get("input") or {})


#: How a tool's name starts -> the kind of action it is (its icon on the card).
_KIND_PREFIXES = (("update_plan", "think"), (("get_", "list_", "read_", "describe", "inspect"), "read"),
                  (("search", "find", "grep"), "search"), (("run_", "execute", "shell", "terminal"), "execute"),
                  (("fetch", "web"), "fetch"), (("delete", "remove"), "delete"))


def _kind_of(name: str, tool_: Optional[_agents.Tool]) -> str:
    """The ACP kind of a built-in tool call (``"read"``, ``"edit"``, ``"execute"``...)."""
    for prefixes, kind in _KIND_PREFIXES:
        if name.startswith(prefixes):
            return kind
    if tool_ is not None and (tool_.writes or tool_.ui):
        return "edit"
    return "other"


def _tool_card(c: AgentController, block: Dict[str, Any], result: Optional[Dict[str, Any]],
               tools: Dict[str, _agents.Tool], t: Theme) -> Any:
    """One tool call of the thread as ``ui.ToolCall``: it asks right on the card while it waits for an OK."""
    call_id = block.get("id", "")
    status = c.tool_status.get(call_id) or ("error" if result and result.get("is_error") else
                                            "done" if result else "running" if c.running else "error")
    if c.pending is not None and c.running and status == "running" and c.pending.tool.name == block.get("name"):
        status = "waiting"
    output: Any = None
    images: List[bytes] = []
    if result is not None:
        content = result.get("content")
        if isinstance(content, list):
            images = [data for data in (_image_bytes(b) for b in content if b.get("type") == "image") if data]
            content = "".join(b.get("text", "") for b in content if b.get("type") == "text")
        output = content
    kind = block.get("kind") or _kind_of(block.get("name", ""), tools.get(block.get("name", "")))
    return ui.ToolCall(title=_tool_title(block.get("name", ""), tools), detail=_call_detail(c, block),
                       kind=kind, status={"error": "failed"}.get(status, status), input=block.get("input") or None,
                       output=output, images=images, diffs=block.get("diffs") or [],
                       progress=str(block.get("progress") or "") if result is None else "", theme=t,
                       key=f"tool:{call_id}",
                       on_allow=lambda _e: c.answer(True), on_allow_always=lambda _e: c.answer(True, True),
                       on_deny=lambda _e: c.answer(False))


def _thinking_card(c: AgentController, key: str, text: str, t: Theme, live: bool = False) -> Any:
    opened = key in c.open_blocks
    head = _core.row([_icon("brain", size=12, color=t.text_muted),
                      ui.label(tr("Thinking…") if live else tr("Thought"), size="sm", color="text_muted", theme=t),
                      _icon("chevron-down" if opened else "chevron-right", size=12, color=t.text_placeholder)],
                     spacing=6, align="center")
    body = ui.label(text.strip(), size="sm", color="text_muted", selectable=SELECTION, theme=t) \
        if opened and text.strip() else None
    return _core.column([_core.button(head, lambda: c.toggle_block(key), padding=(3, 6), bg=None,
                                      hover_bg=t.element_hover, radius=t.radius),
                         _core.container(body, padding=(0, 0, 0, 24)) if body else None], spacing=2, width="fill")


#: Decoded images of the thread, by their base64 text (decoded once, not on every frame).
_IMAGES: Dict[int, bytes] = {}


def _image_bytes(block: Dict[str, Any]) -> Optional[bytes]:
    import base64

    data = (block.get("source") or {}).get("data") or ""
    key = hash(data)
    if key not in _IMAGES:
        if len(_IMAGES) > 64:
            _IMAGES.clear()
        try:
            _IMAGES[key] = base64.b64decode(data)
        except ValueError:
            return None
    return _IMAGES[key]


#: The selection group of the thread's text: one drag can select across its messages.
SELECTION = "agent-thread"


def _user_bubble(text: str, t: Theme, images: Sequence[Dict[str, Any]] = ()) -> Any:
    pictures = [_core.image(data, height=72, content_fit="contain", radius=4)
                for data in (_image_bytes(b) for b in images) if data]
    return _core.container(_core.column([
        ui.label(text, size="sm", selectable=SELECTION, theme=t) if text else None,
        _core.row(pictures, spacing=6, wrap=True) if pictures else None,
    ], spacing=6), padding=(8, 10), width="fill", bg=t.element, border_color=t.border_variant, border_width=1,
        radius=t.radius + 2)


def _messages(c: AgentController, t: Theme) -> List[Any]:
    """The thread drawn from its messages, then what is streaming now: an external agent's text and tool calls
    as they happen, the call the model is writing, or what it is doing."""
    tools = c.tool_index()
    messages = list(c.thread.messages)
    live = c._agent.live() if c.running and hasattr(c._agent, "live") else None
    if live is not None and (live[0] or live[1]):
        messages.append({"role": "assistant", "content": live[0]})
        messages.append({"role": "user", "content": live[1]})
    results: Dict[str, Dict[str, Any]] = {}
    for m in messages:
        if m.get("role") == "user":
            for b in m.get("content", []):
                if b.get("type") == "tool_result":
                    results[b.get("tool_use_id", "")] = b
    rows: List[Any] = []
    answer: List[str] = []  # the text of the agent's answer since the last user message

    def end_answer() -> None:
        if answer:
            rows.append(_answer_actions(c, "\n\n".join(answer), t))
            answer.clear()

    for i, m in enumerate(messages):
        blocks = m.get("content", [])
        if m.get("role") == "user":
            texts = [b.get("text", "") for b in blocks if b.get("type") == "text"
                     and not b.get("text", "").startswith("<context>")]
            images = [b for b in blocks if b.get("type") == "image"]
            if texts or images:
                end_answer()
                rows.append(_user_bubble("\n".join(texts), t, images))
            continue
        for j, b in enumerate(blocks):
            kind = b.get("type")
            if kind == "text" and b.get("text", "").strip():
                answer.append(b["text"].strip())
                rows.append(ui.markdown(b["text"], size=13, selectable=SELECTION, theme=t))
            elif kind == "thinking" and c.settings.show_thinking and b.get("thinking", "").strip():
                rows.append(_thinking_card(c, f"think:{i}:{j}", b["thinking"], t))
            elif kind == "tool_use":
                rows.append(_tool_card(c, b, results.get(b.get("id", "")), tools, t))
    if not c.running:
        end_answer()
    if c.running:
        if c.live_thinking and c.settings.show_thinking:
            rows.append(_thinking_card(c, "think:live", c.live_thinking, t, live=True))
        if c.live_text and live is None:  # an external agent's text is already in its live blocks
            rows.append(ui.markdown(c.live_text, size=13, selectable=SELECTION, theme=t))
        if c.live_tool:
            rows.append(ui.ToolCall(title=_tool_title(c.live_tool, tools), detail=tr("preparing…"), status="running",
                                    kind=_kind_of(c.live_tool, tools.get(c.live_tool)), theme=t, key="tool:live"))
        elif not c.live_text or live is not None:
            rows.append(_working(c, t))
    return rows


def _answer_actions(c: AgentController, text: str, t: Theme) -> Any:
    """Under each answer of the agent: a button that copies it (its text can also be selected)."""
    return _core.row([ui.icon_button("copy", lambda: c.copy_text(text), size="sm", tooltip=tr("Copy the answer"),
                                     theme=t)], width="fill")


def _working(c: AgentController, t: Theme) -> Any:
    """What the agent is doing while nothing streams: waiting for an answer, a tool running, or thinking."""
    waiting = c.pending is not None
    running = [i for i, status in c.tool_status.items() if status == "running"]
    text = tr("Waiting for your answer") if waiting else tr("Running a tool…") if running else \
        tr("Thinking…") if c.live_thinking else tr("Working…")
    seconds = int(time.monotonic() - c.started) if c.started else 0
    return _core.row([ui.spinner(size=12, theme=t), ui.label(text, size="sm", color="text_muted", theme=t),
                      ui.label(f"{seconds // 60}:{seconds % 60:02d}" if seconds >= 60 else f"{seconds}s", size="xs",
                               color="text_placeholder", theme=t) if seconds >= 3 else None],
                     spacing=6, align="center")


SUBSCRIPTION_TEXT = "Claude Pro or Max through Claude Code, Anthropic's own agent; it controls the editor"

#: Providers offered first in an empty panel that is not set up yet.
QUICK_PROVIDERS = ("anthropic", "openai", "google", "openrouter", "ollama")


def _empty(c: AgentController, t: Theme) -> Any:
    if not c.ready:
        quick = [_core.button(_core.row([
            _icon(_providers.PROVIDERS[pid].icon, size=14, color=t.text_accent),
            _core.column([ui.label(tr("Connect {provider}", provider=_providers.PROVIDERS[pid].name), size="sm",
                                   theme=t),
                          ui.label(tr(_providers.PROVIDERS[pid].description), size="xs", color="text_muted",
                                   theme=t)], width="fill"),
            _icon("chevron-right", size=12, color=t.text_placeholder)], spacing=8, align="center"),
            lambda pid=pid: c.connect(pid), padding=(6, 8), width="fill", bg=None, hover_bg=t.element_hover,
            radius=t.radius) for pid in QUICK_PROVIDERS]
        quick.insert(0, _core.button(_core.row([
            _icon("sparkles", size=14, color=t.text_accent),
            _core.column([ui.label(tr("Use my Claude subscription"), size="sm", theme=t),
                          ui.label(tr(SUBSCRIPTION_TEXT), size="xs", color="text_muted", theme=t)], width="fill"),
            _icon("chevron-right", size=12, color=t.text_placeholder)], spacing=8, align="center"),
            c.use_claude_subscription, padding=(6, 8), width="fill", bg=None, hover_bg=t.element_hover,
            radius=t.radius))
        return _core.column([
            _core.column([_icon("key-round", size=22, color=t.text_accent),
                          ui.label(tr("Connect a model"), weight="semibold", theme=t),
                          ui.label(tr("Sign in with the browser or paste a key. Keys are kept in the system "
                                      "keychain."), size="sm", color="text_muted", theme=t)],
                         spacing=6, align="center", width="fill", padding=(20, 12, 10, 12)),
            _core.column(quick, spacing=2, width="fill"),
            _core.container(ui.button(tr("All providers…"), c.open_settings, icon="settings-2", variant="ghost",
                                      size="sm", theme=t), width="fill", align_x="center"),
        ], spacing=8, width="fill")
    items = [_core.button(_core.row([_icon(icon, size=14, color=t.text_muted),
                                     _core.container(ui.label(tr(text), size="sm", theme=t), width="fill")],
                                    spacing=8, align="center"),
                          lambda text=text: c.suggest(text), padding=(6, 8), width="fill", bg=None,
                          hover_bg=t.element_hover, radius=t.radius)
             for icon, text in SUGGESTIONS]
    return _core.column([
        _core.column([_icon("sparkles", size=22, color=t.text_accent),
                      ui.label(tr("What should we build?"), weight="semibold", theme=t),
                      ui.label(tr("The agent sees the open form and its code, edits them like you would, and "
                                  "can create new forms and components."), size="sm", color="text_muted",
                               theme=t)],
                     spacing=6, align="center", width="fill", padding=(20, 12, 10, 12)),
        _core.column(items, spacing=2, width="fill"),
    ], spacing=8, width="fill")


def _confirmation(c: AgentController, t: Theme) -> Any:
    p = c.pending
    assert p is not None
    preview = _args_preview(p.args) or ", ".join(p.args)
    detail = f"{_tool_title(p.tool.name, {p.tool.name: p.tool})}: {preview}" if preview else \
        _tool_title(p.tool.name, {p.tool.name: p.tool})
    return ui.callout(tr("Allow the agent to continue?"), detail, tint="warning", icon="shield-question", actions=[
                          ui.button(tr("Allow"), lambda: c.answer(True), variant="solid", size="sm", theme=t),
                          ui.button(tr("Always allow"), lambda: c.answer(True, True), variant="ghost", size="sm",
                                    theme=t),
                          ui.button(tr("Deny"), lambda: c.answer(False), variant="ghost", size="sm", theme=t),
                      ], theme=t)


def _plan_card(c: AgentController, t: Theme) -> Optional[Any]:
    """The agent's plan (its last ``update_plan``) above the message box, while it runs or has steps left."""
    steps = c.live_plan if c.running and c.live_plan else agent_tools.plan_of(c.thread.messages)
    done = sum(1 for s in steps if s["status"] == "done")
    if not steps or (done == len(steps) and not c.running):
        return None
    return ui.Plan(steps=steps, running=c.running, theme=t, key="agent-plan")


def _review_bar(c: AgentController, t: Theme) -> Any:
    """The documents the agent changed, to keep or reject (all, or one by one) like Zed's edits bar."""
    return ui.EditsBar(files=c.file_changes(), theme=t, key="agent-edits", on_keep=lambda _e: c.keep(),
                       on_reject=lambda _e: c.reject(), on_keep_file=lambda e: c.keep_file(e.value),
                       on_reject_file=lambda e: c.reject_file(e.value), on_open=lambda e: c.open_file(e.value))


def _history(c: AgentController, t: Theme) -> Any:
    threads = [{"id": th.id, "title": th.display_title, "updated": th.updated, "detail": _thread_agent(c, th.model)}
               for th in c.threads()]
    return ui.ThreadHistory(threads=threads, selected=c.thread.id, theme=t, key="agent-history",
                            on_open=lambda e: c.open_thread(e.value), on_delete=lambda e: c.delete_thread(e.value))


def _thread_agent(c: AgentController, model: str) -> str:
    """Who answers a thread: the external agent's name, or the model's."""
    provider, name = _providers.split_model(model or c.settings.model)
    if provider == "acp":
        agent = c.settings.acp_agent(name)
        return agent.label if agent else name
    return model_label(model) if model else ""


def _chip(label: str, on_press: Any, t: Theme, *, icon: Optional[str] = None, selected: bool = False,
          menu: bool = True, tooltip: Optional[str] = None, disabled: bool = False) -> Any:
    """A small text button of the composer's bottom row (a menu opener when ``menu``)."""
    color = t.text_placeholder if disabled else t.text if selected else t.text_muted
    parts = [_icon(icon, size=12, color=t.text_accent if selected else color) if icon else None,
             ui.label(label, size="xs", color=color, theme=t),
             _icon("chevron-down", size=10, color=t.text_placeholder) if menu else None]
    button = _core.button(_core.row(parts, spacing=3, align="center"), None if disabled else on_press,
                          padding=(3, 5), bg=alpha(t.accent, 0.12) if selected else None, hover_bg=t.element_hover,
                          radius=t.radius)
    return ui.tooltip(button, tooltip, theme=t) if tooltip else button


def _menu_card(content: Any, t: Theme, height: Optional[float] = None) -> Any:
    body = _core.scrollable(content, height=height, scrollbar_width=4) if height else content
    return _core.container(body, padding=4, width="fill", bg=t.elevated_surface if hasattr(t, "elevated_surface")
                           else t.panel, border_color=t.border, border_width=1, radius=t.radius + 2)


def _menu_row(icon: Optional[str], label: str, detail: str, on_press: Any, t: Theme, *, checked: bool = False,
              highlighted: bool = False, disabled: bool = False) -> Any:
    lead = _icon("check" if checked else icon, size=13,
                 color=t.text_accent if checked else t.text_placeholder if disabled else t.text_muted) \
        if checked or icon else _core.space(width=13)
    row = _core.row([
        lead,
        _core.column([ui.label(label, size="sm", color="text_placeholder" if disabled else "text", theme=t),
                      ui.label(detail, size="xs", color="text_muted", theme=t) if detail else None], width="fill"),
    ], spacing=8, align="center")
    return _core.button(row, None if disabled else on_press, padding=(4, 8), width="fill",
                        bg=t.element_hover if highlighted else None, hover_bg=t.element_hover, radius=t.radius)


def _menu_header(text: str, t: Theme) -> Any:
    return _core.container(ui.label(text, size="xs", weight="medium", color="text_placeholder", theme=t),
                           padding=(6, 8, 2, 8))


def _model_menu(c: AgentController, t: Theme) -> Any:
    """Every provider with its models, then the external agents; one not set up offers to connect it."""
    current = c.thread.model or c.settings.model
    rows: List[Any] = []
    for pid, p in _providers.PROVIDERS.items():
        if pid == "acp":
            continue
        rows.append(_menu_header(p.name, t))
        if not _providers.is_ready(pid, settings=c.settings):
            rows.append(_menu_row("log-in", tr("Connect {provider}…", provider=p.name), tr(p.description),
                                  lambda pid=pid: c.connect(pid), t))
            continue
        names = c.settings.models_of(pid)
        if not names:
            rows.append(_menu_row("refresh-cw", tr("Refresh models"), "", lambda pid=pid: c.refresh_models(pid), t))
        for name in names:
            full = f"{pid}:{name}"
            rows.append(_menu_row(None, model_label(full), name if model_label(full) != name else "",
                                  lambda full=full: c.set_model(full), t, checked=full == current))
    rows.append(_menu_header(tr("External agents"), t))
    if c.settings.acp_agent("claude-code") is None:
        rows.append(_menu_row("sparkles", tr("Use my Claude subscription…"), tr(SUBSCRIPTION_TEXT),
                              c.use_claude_subscription, t))
    for a in c.settings.acp_agents:
        if a.enabled:
            full = f"acp:{a.name}"
            rows.append(_menu_row("terminal", a.label, " ".join([a.command, *a.args])[:60],
                                  lambda full=full: c.set_model(full), t, checked=full == current))
    rows.append(_menu_row("plus", tr("Add an external agent…"), tr("Claude Code, Gemini CLI, Codex or any ACP agent"),
                          lambda: c.connect("acp"), t))
    return _menu_card(_core.column(rows, spacing=0, width="fill"), t, height=320)


def _add_menu(c: AgentController, t: Theme) -> Any:
    """The + button's menu: context with @, images from a file or the clipboard, a picture of the form."""
    rows = [
        _menu_row("at-sign", tr("Add context"), tr("Files, the form, its code, controls (@)"), c.start_mention, t),
        _menu_row("image-plus", tr("Attach images…"), tr("PNG, JPEG, GIF or WebP files"), c.pick_images, t),
        _menu_row("clipboard-paste", tr("Paste image"), tr("A screenshot or picture you copied"), c.paste_image, t),
        _menu_row("camera", tr("Screenshot of the form"), tr("Let the agent see the open form"), c.attach_screenshot,
                  t),
    ]
    return _menu_card(_core.column(rows, spacing=0, width="fill"), t)


def _mode_menu(c: AgentController, t: Theme) -> Any:
    rows = [_menu_row(icon, tr(label), tr(text), lambda m=mode: c.set_mode(m), t, checked=c.settings.mode == mode)
            for mode, (label, icon, text) in MODE_TEXT.items()]
    return _menu_card(_core.column(rows, spacing=0, width="fill"), t)


#: An external agent's option category -> its chip's icon in the composer.
OPTION_ICONS = {"mode": "shield-check", "model": "", "thought_level": "brain"}


def _option_menu(c: AgentController, t: Theme, option_id: str) -> Any:
    """The choices of one of the external agent's options (its modes, models...), like Zed's selectors."""
    option = next((o for o in c.agent_options() if o["id"] == option_id), None)
    if option is None:
        return None
    rows = [_menu_header(option["name"], t)]
    rows += [_menu_row(None, choice["name"], choice["description"],
                       lambda v=choice["value"]: c.set_agent_option(option_id, v), t,
                       checked=choice["value"] == option["current"]) for choice in option["choices"]]
    return _menu_card(_core.column(rows, spacing=0, width="fill"), t, height=320 if len(rows) > 8 else None)


def _option_chip(c: AgentController, option: Dict[str, Any], t: Theme) -> Any:
    choice = next((ch for ch in option["choices"] if ch["value"] == option["current"]), None)
    key = f"option:{option['id']}"
    return _chip(choice["name"] if choice else option["current"], lambda: c.toggle_menu(key), t,
                 icon=OPTION_ICONS.get(option["category"], "sliders-horizontal") or None, selected=c.menu == key,
                 tooltip=(choice or {}).get("description") or option["name"])


def _effort_menu(c: AgentController, t: Theme) -> Any:
    rows = [_menu_header(tr("How much the model thinks before answering (Claude)"), t)]
    rows += [_menu_row(None, tr(EFFORT_TEXT[e]), "", lambda e=e: c.set_effort(e), t, checked=c.settings.effort == e)
             for e in _providers.EFFORTS]
    return _menu_card(_core.column(rows, spacing=0, width="fill"), t)


def _popup(c: AgentController, t: Theme) -> Optional[Any]:
    """The @ mention / slash command list above the message box."""
    trig = c.trigger()
    if trig is None or not c.popup_open:
        return None
    items = c.popup_items()
    title = tr("Commands") if trig[0] == "slash" else tr("Add context")
    if not items:
        body: List[Any] = [_menu_header(title, t), _core.container(
            ui.label(tr("No matches"), size="sm", color="text_muted", theme=t), padding=(4, 8))]
    else:
        picked = min(c.picked, len(items) - 1)
        body = [_menu_header(title + "  ·  " + tr("↑↓ to move, Enter to pick, Esc to close"), t)]
        body += [_menu_row(icon, label, detail, action, t, highlighted=i == picked)
                 for i, (icon, label, detail, action) in enumerate(items)]
    return _menu_card(_core.column(body, spacing=0, width="fill"), t, height=min(260, 34 + 40 * max(1, len(items))))


def _mentions_row(c: AgentController, t: Theme) -> Optional[Any]:
    """The @ mentions and attached images of the next message, as removable chips."""
    if not c.mentions and not c.attachments:
        return None

    def chip(lead: Any, label: str, remove: Callable[[], Any]) -> Any:
        return _core.container(_core.row([
            lead, ui.label(label if len(label) <= 28 else label[:27] + "…", size="xs", theme=t),
            _core.button(_icon("x", size=10, color=t.text_placeholder), remove, padding=1, bg=None,
                         hover_bg=t.element_hover, radius=t.radius)], spacing=3, align="center"),
            padding=(1, 4), bg=t.element, border_color=t.border_variant, border_width=1, radius=t.radius)

    chips = [chip(_icon(m.icon, size=11, color=t.text_muted), m.label, lambda i=i: c.remove_mention(i))
             for i, m in enumerate(c.mentions)]
    chips += [chip(_core.image(a.data, width=28, height=28, content_fit="cover", radius=3), a.name,
                   lambda i=i: c.remove_attachment(i)) for i, a in enumerate(c.attachments)]
    if c.busy_provider == "screenshot":
        chips.append(_core.row([ui.spinner(size=11, theme=t),
                                ui.label(tr("Taking a screenshot…"), size="xs", color="text_muted", theme=t)],
                               spacing=4, align="center"))
    return _core.row(chips, spacing=4, wrap=True)


#: Lines the message box grows to before it scrolls.
BOX_LINES = 10


def _box_height(text: str, chars: int = 52, line: float = 20.0) -> float:
    """The message box's height for ``text``: one line per wrapped line, up to ``BOX_LINES``."""
    lines = sum(max(1, -(-len(part) // chars)) for part in text.split("\n")) if text else 1
    return min(max(lines, 1), BOX_LINES) * line + 10


def _composer(c: AgentController, t: Theme) -> Any:
    """The message box, like Zed's: the text (Enter sends, Shift+Enter breaks the line), then the + menu,
    the permission mode, model, effort and fast mode."""
    s = c.settings
    send = ui.icon_button("square", c.stop, size="sm", tooltip=tr("Stop"), theme=t) if c.running else \
        ui.icon_button("arrow-up", c.send, size="sm", variant="solid", tooltip=tr("Send (Enter)"),
                       disabled=not (c.input.strip() or c.attachments), theme=t)
    box = ui.editor(INPUT_ID, c.input, on_change=c.set_input, on_cursor=c.focus_box, wrap=True, gutter=False,
                    active_line=False, folding=False, auto_close=False, match_brackets=False,
                    selection_highlight=False, font="sans", font_size=13, line_height=20,
                    height=_box_height(c.input), capture_keys=c.captured_keys(),
                    placeholder=tr("Message the agent (@ context, / commands, Shift+Enter for a new line)"), theme=t)
    field_ = _core.row([_core.container(box, width="fill"), send], spacing=4, align="end")
    model = c.thread.model or s.model
    provider_id, name = _providers.split_model(model)
    claude = _providers.PROVIDERS[provider_id].protocol == "anthropic"
    external = provider_id == "acp"
    mode_label, mode_icon, mode_text = MODE_TEXT[s.mode]
    agent = s.acp_agent(name) if external else None
    # an external agent's own options, like Zed shows Claude Code's: its mode on the left, the rest by the agent
    options = c.agent_options() if external else []
    own_mode = next((o for o in options if o["category"] == "mode"), None)
    others = [o for o in options if o is not own_mode]
    controls = _core.row([
        ui.icon_button("plus", c.toggle_add_menu, size="sm", selected=c.menu == "add",
                       tooltip=tr("Add context or images"), theme=t),
        _option_chip(c, own_mode, t) if own_mode else
        _chip(tr(mode_label), lambda: c.toggle_menu("mode"), t, icon=mode_icon, selected=c.menu == "mode",
              tooltip=tr(mode_text)),
        _core.space(width="fill"),
        ui.context_meter(c.thread.context, c.context_window, theme=t)
        if c.thread.context and c.context_window and not external else None,
        _chip(agent.label if agent else model_label(model), lambda: c.toggle_menu("model"), t,
              icon="terminal" if external else None, selected=c.menu == "model", tooltip=tr("Model")),
        *[_option_chip(c, o, t) for o in others],
        None if external else _chip(tr(EFFORT_TEXT[s.effort]), lambda: c.toggle_menu("effort"), t,
                                    selected=c.menu == "effort", tooltip=tr("Effort"), disabled=not claude),
        None if external or not claude else _chip(tr("Thinking"), c.toggle_thinking, t, icon="brain",
                                                  selected=s.thinking, menu=False,
                                                  tooltip=tr("Let Claude think before answering; off answers sooner")),
        None if external else _chip(tr("Fast"), c.toggle_fast, t, icon="zap",
                                    selected=s.fast and name in _providers.FAST_MODELS, menu=False,
                                    disabled=name not in _providers.FAST_MODELS,
                                    tooltip=tr("Fast mode: faster answers at a higher price (Claude Opus)")),
    ], spacing=2, align="center", wrap=True)
    return _core.container(_core.column([_mentions_row(c, t), field_, controls], spacing=6), padding=(6, 6, 4, 4),
                           width="fill", bg=t.editor, border_color=t.border, border_width=1, radius=t.radius + 2)


def _device_callout(c: AgentController, t: Theme) -> Optional[Any]:
    """While signing in to GitHub: the code to type on github.com."""
    login = c.device
    if login is None:
        return None
    name = _providers.PROVIDERS[login.provider].name
    if not login.user_code:
        body: List[Any] = [_core.row([ui.spinner(size=14, theme=t), ui.label(
            tr("Signing in to {provider}", provider=name), size="sm", weight="medium", theme=t)], spacing=8,
            align="center")]
    else:
        body = [
            _core.row([_icon("github", size=14, color=t.text_accent),
                       ui.label(tr("Signing in to {provider}", provider=name), size="sm", weight="medium", theme=t)],
                      spacing=8, align="center"),
            ui.label(tr("Type this code on the GitHub page that opened ({url}):", url=login.uri), size="xs",
                     color="text_muted", theme=t),
            _core.row([ui.label(login.user_code, size="lg", weight="semibold", mono=True, theme=t),
                       ui.icon_button("copy", c.copy_device_code, size="sm", tooltip=tr("Copy"), theme=t),
                       _core.space(width="fill"), ui.spinner(size=12, theme=t)], spacing=6, align="center"),
        ]
    body.append(_core.row([
        ui.button(tr("Open the page again"), lambda: _agents.login.open_browser(login.uri or "https://github.com/login/device"),
                  variant="ghost", size="sm", theme=t),
        ui.button(tr("Cancel"), c.cancel_device, variant="ghost", size="sm", theme=t)], spacing=4, wrap=True))
    return _core.container(_core.column(body, spacing=6, width="fill"), padding=(8, 10), width="fill",
                           bg=alpha(t.accent, 0.08), border_color=t.border_variant, border_width=1,
                           radius=t.radius + 2)


def _claude_login_callout(c: AgentController, t: Theme) -> Any:
    """While Claude Code is open in a terminal for the sign-in."""
    return _core.container(_core.column([
        _core.row([ui.spinner(size=14, theme=t), ui.label(tr("Sign in to Claude in the terminal"), size="sm",
                                                         weight="medium", theme=t)], spacing=8, align="center"),
        ui.label(tr("Claude Code opened in a terminal. Choose to sign in with your Claude account (Pro or Max) and "
                    "finish in the browser: Pyzed notices it and comes back."), size="xs", color="text_muted", theme=t),
        _core.row([
            ui.button(tr("Open the terminal again"), c.open_claude_login, icon="terminal", variant="ghost", size="sm",
                      theme=t),
            ui.button(tr("Cancel"), c.cancel_claude_login, variant="ghost", size="sm", theme=t),
        ], spacing=4, align="center", wrap=True),
    ], spacing=6, width="fill"), padding=(8, 10), width="fill", bg=alpha(t.accent, 0.08), border_color=t.border_variant,
        border_width=1, radius=t.radius + 2)


def _capture_callout(c: AgentController, t: Theme) -> Optional[Any]:
    """While signing in by copying a key: what to do, and Paste / Cancel."""
    cap = c.capture
    if cap is None:
        return None
    name = _providers.PROVIDERS[cap.provider].name
    detail = tr("Checking the key…") if cap.checking else tr(
        "Follow the page that opened in the browser: create a key and paste it there, or just copy it. Pyzed checks "
        "it, saves it in the system keychain and comes back to the front.")
    lead = ui.spinner(size=14, theme=t) if cap.checking else _icon("key-round", size=14, color=t.text_accent)
    return _core.container(_core.column([
        _core.row([lead, ui.label(tr("Signing in to {provider}", provider=name), size="sm", weight="medium",
                                  theme=t)], spacing=8, align="center"),
        ui.label(detail, size="xs", color="text_muted", theme=t),
        _core.row([
            ui.button(tr("Paste key"), lambda: c.paste_key(cap.provider), icon="clipboard-paste", variant="tinted",
                      size="sm", theme=t),
            ui.button(tr("Open the key page"), lambda: c.open_key_page(cap.provider), variant="ghost", size="sm",
                      theme=t),
            ui.button(tr("Cancel"), c.cancel_capture, variant="ghost", size="sm", theme=t),
        ], spacing=4, align="center", wrap=True),
    ], spacing=6, width="fill"), padding=(8, 10), width="fill", bg=alpha(t.accent, 0.08), border_color=t.border_variant,
        border_width=1, radius=t.radius + 2)


def _new_menu(c: AgentController, t: Theme) -> Any:
    """The + menu: a new thread with the built-in agent or an external one, like Zed's."""
    items: List[Any] = [tr("New thread"),
                        ui.MenuItem(tr("Pyzed Agent"), lambda: c.new_thread(""), icon="sparkles")]
    for agent in c.settings.acp_agents:
        if agent.enabled:
            items.append(ui.MenuItem(agent.label, lambda name=agent.name: c.new_thread(f"acp:{name}"),
                                     icon="terminal"))
    items += [ui.SEPARATOR, ui.MenuItem(tr("Add more agents…"), lambda: c.open_settings(section="agents"),
                                        icon="plus")]
    return ui.menu(items, width=230, theme=t)


def _options_menu(c: AgentController, t: Theme) -> Any:
    """The ⋯ menu of the panel: settings and the panel's options."""
    s = c.settings
    return ui.menu([
        ui.MenuItem(tr("Agent settings"), lambda: c.open_settings(), icon="settings-2"),
        ui.MenuItem(tr("Rules…"), lambda: c.open_settings(), icon="scroll-text"),
        ui.SEPARATOR,
        ui.MenuItem(tr("Show thinking"), lambda: c.toggle_option("show_thinking"), checked=s.show_thinking),
        ui.SEPARATOR,
        ui.MenuItem(tr("Copy thread as Markdown"), c.copy_markdown, icon="copy", disabled=not c.thread.messages),
        ui.MenuItem(tr("Back to the dock") if c.expanded else tr("Expand the panel"), c.toggle_expand,
                    icon="minimize-2" if c.expanded else "maximize-2"),
    ], width=240, theme=t)


def _header(c: AgentController, t: Theme) -> Any:
    """The panel's toolbar, like Zed's: back (from the history or the settings), the title, then the +
    menu, the history and the ⋯ menu."""
    if c.view == "history":
        title = tr("History")
    elif c.view == "settings":
        title = tr("Agent settings")
    else:
        title = c.thread.display_title if c.thread.messages else tr("New thread")
    title = title if len(title) <= 28 else title[:27].rstrip() + "…"
    lead = ui.icon_button("arrow-left", c.back, size="sm", tooltip=tr("Back to the thread"), theme=t) \
        if c.view != "thread" else _icon("terminal" if (c.thread.model or "").startswith("acp:") else "sparkles",
                                         size=14, color=t.text_accent)
    return _core.container(_core.row([
        lead,
        _core.container(ui.label(title, size="sm", weight="medium", wrap=False, theme=t), width="fill"),
        ui.icon_button("crosshair", c.toggle_follow, size="sm", selected=c.settings.follow_agent,
                       tooltip=tr("Follow the agent: open what it writes as it works"), theme=t)
        if c.view == "thread" else None,
        ui.icon_button("plus", lambda: c.toggle_menu("new"), size="sm", selected=c.menu == "new",
                       tooltip=tr("New thread"), theme=t),
        ui.icon_button("history", c.toggle_history, size="sm", selected=c.view == "history",
                       tooltip=tr("History"), theme=t),
        ui.icon_button("ellipsis", lambda: c.toggle_menu("options"), size="sm", selected=c.menu == "options",
                       tooltip=tr("Options"), theme=t),
    ], spacing=4, align="center"), padding=(4, 6, 4, 10), height=36, width="fill", bg=t.panel,
        border_color=t.border_variant, border_width=0)



def view(d: "Designer", t: Theme) -> Any:
    """The Agent panel: the toolbar, then the thread, the history or the agent settings."""
    c = d.agent
    header = _header(c, t)
    if c.view == "history":
        body = _core.column([header, _history(c, t)], width="fill", height="fill")
    elif c.view == "settings":
        body = _core.column([header, settings_view(d, t)], width="fill", height="fill")
    else:
        body = _thread_view(c, d, t, header)
    menus = {"new": _new_menu, "options": _options_menu}
    if c.menu in menus:
        body = ui.popover(body, menus[c.menu](c, t), x=8, y=34, align_x="end", on_dismiss=c.close_menu)
    if c.expanded:  # a readable column in the middle of the window, like Zed's zoomed panel
        body = _core.container(_core.container(body, max_width=860, width="fill", height="fill"), width="fill",
                               height="fill", align_x="center")
    return body


def _thread_view(c: AgentController, d: "Designer", t: Theme, header: Any) -> Any:
    rows = _messages(c, t) if c.thread.messages else [_empty(c, t)]
    if c.error and not c.running:
        actions = [
            ui.button(tr("Retry"), c.retry, icon="refresh-cw", variant="ghost", size="sm", theme=t),
            ui.button(tr("Settings"), lambda: c.open_settings(), variant="ghost", size="sm", theme=t),
        ]
        if c.needs_node:
            actions = [
                ui.button(tr("Install Node.js"), lambda: _agents.login.open_browser(NODE_URL), icon="download",
                          variant="tinted", size="sm", theme=t),
                ui.button(tr("Use Pyzed Agent"), c.use_pyzed_agent, variant="ghost", size="sm", theme=t),
                *actions]
        if c.needs_claude_login:
            actions.insert(0, ui.button(tr("Sign in to Claude"), c.open_claude_login, icon="log-in",
                                        variant="tinted", size="sm", theme=t))
        rows.append(ui.callout(tr("The agent stopped"), c.error, tint="error", icon="triangle-alert", actions=actions,
                               theme=t))
    thread = _core.scrollable(_core.column(rows, spacing=10, width="fill", padding=(10, 12)), height="fill",
                              id=SCROLL_ID, anchor_bottom=True, scrollbar_width=4)
    bottom: List[Any] = []
    if c.capture is not None:
        bottom.append(_capture_callout(c, t))
    if c.claude_login is not None:
        bottom.append(_claude_login_callout(c, t))
    if c.agent_auth is not None:
        bottom.append(_auth_card(c, t))
    if c.mcp_added:
        bottom.append(ui.callout(tr("Restart your agents to use Pyzed's MCP"), tr(
            "Pyzed's MCP server was added to {names}. Close and open them again (agents running in Pyzed restart "
            "with the button).", names=", ".join(c.mcp_added)), tint="info", icon="plug", actions=[
            ui.button(tr("Restart agents"), c.restart_agents, icon="refresh-cw", variant="tinted", size="sm",
                      theme=t),
            ui.button(tr("Later"), c.dismiss_mcp_added, variant="ghost", size="sm", theme=t)], theme=t))
    if c.device is not None:
        bottom.append(_device_callout(c, t))
    bottom.append(_plan_card(c, t))
    if c.pending is not None and not _pending_on_card(c):
        bottom.append(_confirmation(c, t))
    if c.snapshot and c.changed and not c.running:
        bottom.append(_review_bar(c, t))
    menus = {"mode": _mode_menu, "model": _model_menu, "effort": _effort_menu, "add": _add_menu}
    if c.menu in menus:
        bottom.append(menus[c.menu](c, t))
    elif c.menu and c.menu.startswith("option:"):
        bottom.append(_option_menu(c, t, c.menu[len("option:"):]))
    else:
        bottom.append(_popup(c, t))
    bottom.append(_composer(c, t))
    return _core.column([header, thread, _core.column(bottom, spacing=6, padding=(6, 8, 8, 8), width="fill")],
                        width="fill", height="fill")


def _auth_card(c: AgentController, t: Theme) -> Any:
    """Zed's "Authentication required": one button per way the external agent can sign in."""
    auth = c.agent_auth
    assert auth is not None
    icons = {"agent": "globe", "terminal": "terminal", "env_var": "key-round"}
    methods = [{"id": str(m.get("id", "")), "name": str(m.get("name") or m.get("id") or ""),
                "description": str(m.get("description") or ""), "icon": icons[_acp.auth_kind(m)]}
               for m in auth.methods]
    method = next((m for m in auth.methods if str(m.get("id")) == auth.waiting), None)
    terminal = method is not None and _acp.auth_kind(method) == "terminal"
    return ui.AuthPrompt(title=tr("Sign in to {name}", name=auth.label),
                         detail=tr("{name} needs you to sign in before it answers. Your message is sent once you are "
                                   "signed in.", name=auth.label), methods=methods, waiting=auth.waiting,
                         waiting_text=tr("Finish signing in in the terminal") if terminal
                         else tr("Finish signing in in the browser"), error=auth.error, theme=t, key="agent-auth",
                         on_pick=lambda e: c.pick_auth(e.value), on_cancel=lambda _e: c.cancel_auth())


def _pending_on_card(c: AgentController) -> bool:
    """Whether the pending question shows on its tool card (the card of a call that is still running)."""
    p = c.pending
    if p is None or not c.running:
        return False
    for m in c.thread.messages[-1:]:
        if m.get("role") == "assistant":
            return any(b.get("type") == "tool_use" and b.get("name") == p.tool.name
                       and c.tool_status.get(b.get("id", "")) == "running" for b in m.get("content", []))
    return False


def inline_bar(d: "Designer", t: Theme) -> Optional[Any]:
    """The inline assist bar over the code editor (Ctrl+Alt+I), like Zed's inline assistant."""
    a = d.agent.inline
    if a is None:
        return None
    c = d.agent
    if a.before is not None and not a.running and not a.error:
        row = _core.row([_icon("sparkles", size=14, color=t.text_accent),
                         ui.label(tr("Agent edit applied"), size="sm", theme=t), _core.space(width="fill"),
                         ui.button(tr("Undo"), c.undo_inline, icon="undo-2", variant="ghost", size="sm", theme=t),
                         ui.button(tr("Keep"), c.close_inline, icon="check", variant="tinted", size="sm", theme=t)],
                        spacing=6, align="center")
    else:
        lead = ui.spinner(size=14, theme=t) if a.running else _icon("sparkles", size=14, color=t.text_accent)
        row = _core.row([
            lead,
            ui.input(a.prompt, c.set_inline, placeholder=tr("Describe the change (Enter to run)…"),
                     on_submit=c.submit_inline, id=INLINE_ID, size="sm", borderless=True, theme=t),
            ui.label(a.error, size="xs", color="error", theme=t) if a.error else None,
            ui.icon_button("x", c.close_inline, size="sm", tooltip=tr("Close"), theme=t),
        ], spacing=6, align="center")
    return _core.container(row, padding=(4, 10), width="fill", bg=t.panel, border_color=t.border_variant,
                           border_width=1)


# -- settings dialog -----------------------------------------------------------------------------------

_SOURCE_TEXT = {
    "keychain": "Key saved in the system keychain",
    "session": "Key kept for this session only",
    "env": "Key from the environment",
    "ant": "Signed in with the Anthropic CLI profile",
    "oauth": "Signed in",
    "federation": "Workload identity federation",
    "gcloud": "Google Cloud credentials of this computer",
    "none needed": "No key needed",
}

#: The sign-in button of each kind of login.
_SIGN_IN_TEXT = {"device": "Sign in with GitHub", "google": "Sign in with Google"}


def _provider_row(c: AgentController, pid: str, t: Theme) -> Any:
    p = _providers.PROVIDERS[pid]
    source = _providers.credential_source(pid, settings=c.settings)
    opened = c.provider_open == pid
    status = ui.badge(tr(_SOURCE_TEXT[source]) if source else tr("Not set up"),
                      tint="success" if source and source != "none needed" else "accent" if source else "warning",
                      theme=t)
    head = _core.button(_core.row([
        _icon(p.icon, size=16, color=t.text_accent if source else t.text_muted),
        _core.column([ui.label(p.name, weight="medium", size="sm", theme=t),
                      ui.label(tr(p.description), size="xs", color="text_muted", theme=t)], width="fill"),
        status,
        _icon("chevron-down" if opened else "chevron-right", size=14, color=t.text_muted),
    ], spacing=10, align="center"), lambda: c.toggle_provider(pid), padding=(8, 10), width="fill", bg=None,
        hover_bg=t.element_hover, radius=t.radius)
    if not opened:
        return head
    busy = c.busy_provider == pid
    rows: List[Any] = []
    if (p.needs_key or p.key_env) and p.login != "google":
        rows.append(ui.field(tr("API key") if p.login != "device" else tr("Personal access token"), _core.row([
            ui.input(c.key_buffer.get(pid, ""), lambda v: c.set_key_buffer(pid, v),
                     placeholder=_agents.secrets.mask(_providers.api_key(pid)) or tr("Paste a key"), secure=True,
                     on_submit=lambda: c.save_key(pid), mono=True, size="sm", width=220, theme=t),
            ui.button(tr("Save"), lambda: c.save_key(pid), variant="tinted", size="sm",
                      disabled=not c.key_buffer.get(pid), theme=t),
        ], spacing=4, align="center"), description=tr("Or set {env}", env=p.key_env) if p.key_env else None, theme=t))
    actions: List[Any] = []
    capturing = c.capture is not None and c.capture.provider == pid
    if p.login and not capturing and not (c.device and c.device.provider == pid):
        label = _SIGN_IN_TEXT.get(p.login, "Sign in with the browser")
        if p.login == "device" and not c.settings.client_id(pid):
            label = "Sign in with a token"
        actions.append(ui.button(tr(label), lambda: c.sign_in(pid), icon="log-in",
                                 variant="solid" if not source or source == "none needed" else "ghost", size="sm",
                                 disabled=busy, theme=t))
    if p.key_url and not capturing:
        actions.append(ui.button(tr("Get a key"), lambda: c.open_key_page(pid), icon="external-link", variant="ghost",
                                 size="sm", theme=t))
    if source in ("keychain", "session", "ant", "oauth"):
        actions.append(ui.button(tr("Sign out") if source in ("ant", "oauth") else tr("Remove key"),
                                 lambda: c.remove_key(pid), icon="trash-2", variant="ghost", size="sm", theme=t))
    actions.append(ui.button(tr("Refresh models"), lambda: c.refresh_models(pid), icon="refresh-cw", variant="ghost",
                             size="sm", disabled=busy or not source, theme=t))
    if busy:
        actions.append(ui.spinner(size=14, theme=t))
    rows.append(_core.row(actions, spacing=4, align="center", wrap=True))
    if capturing:
        rows.append(_capture_callout(c, t))
    if c.device is not None and c.device.provider == pid:
        rows.append(_device_callout(c, t))
    rows += _provider_extra(c, pid, t)
    if p.custom_url:
        rows.append(ui.field(tr("Server URL"), ui.input(c.settings.base_url(pid), lambda v: c.set_url(pid, v),
                                                        placeholder="http://localhost:11434/v1", mono=True, size="sm",
                                                        width=260, theme=t), theme=t))
    models = c.settings.models_of(pid)
    if models:
        rows.append(ui.label(tr("{count} models: {names}", count=len(models), names=", ".join(models[:6])
                                + ("…" if len(models) > 6 else "")), size="xs", color="text_muted", theme=t))
    return _core.column([head, _core.container(_core.column(rows, spacing=8), padding=(0, 10, 10, 36), width="fill")],
                        width="fill")


def _text(value: str, on_change: Callable[[str], Any], placeholder: str, t: Theme, *, width: float = 260,
          mono: bool = True, secure: bool = False) -> Any:
    return ui.input(value, on_change, placeholder=placeholder, mono=mono, size="sm", width=width, secure=secure,
                    theme=t)


def _provider_extra(c: AgentController, pid: str, t: Theme) -> List[Any]:
    """The settings only some providers have: OAuth clients, the Google Cloud project, Claude's workload
    identity federation."""
    own = c.settings.provider(pid)
    if pid == "github":
        return [ui.field(tr("GitHub App client ID"), _text(own.client_id, lambda v: c.set_provider_field(
            pid, "client_id", v), c.settings.client_id(pid) or "Iv23…", t), description=tr(
            "For signing in with GitHub (device flow, Models permission). Without one, use a fine-grained token with "
            "the Models permission."), theme=t)]
    if pid == "vertex":
        projects = c.google_projects
        project = own.project or _providers.google_project()
        picker = ui.select(projects, project, lambda v: c.set_provider_field(pid, "project", v), width=220, size="sm",
                           theme=t) if projects else _text(own.project, lambda v: c.set_provider_field(
                               pid, "project", v), project or "my-project", t, width=220)
        return [
            ui.field(tr("Google Cloud project"), _core.row([
                picker, ui.icon_button("refresh-cw", lambda: c.load_google_projects(pid), size="sm",
                                       tooltip=tr("List my projects"), theme=t)], spacing=4, align="center"),
                     description=tr("Vertex AI must be enabled in it"), theme=t),
            ui.field(tr("Location"), _text(own.location, lambda v: c.set_provider_field(pid, "location", v), "global",
                                           t, width=160), theme=t),
            ui.field(tr("OAuth client"), _core.column([
                _text(own.client_id, lambda v: c.set_provider_field(pid, "client_id", v),
                      c.settings.client_id(pid) or tr("Client ID (Desktop app)"), t),
                _text("", c.set_google_secret, tr("Client secret (kept in the keychain)"), t, secure=True),
            ], spacing=4), description=tr("Only needed to sign in with Google; gcloud's credentials work without it"),
                theme=t),
        ]
    if pid != "anthropic":
        return []
    f = c.settings.federation
    sources = {"file": tr("File"), "command": tr("Command"), "env": tr("Variable")}
    source = ui.segmented(list(sources.values()), sources.get(f.token_source, sources["file"]),
                          lambda v: c.set_federation("token_source", next(k for k, x in sources.items() if x == v)),
                          theme=t)
    where = {"file": _text(f.token_file, lambda v: c.set_federation("token_file", v),
                           tr("Path of the JWT (or ANTHROPIC_IDENTITY_TOKEN_FILE)"), t),
             "command": _text(f.token_command, lambda v: c.set_federation("token_command", v),
                              "gcloud auth print-identity-token", t),
             "env": _text(f.token_env, lambda v: c.set_federation("token_env", v), "ANTHROPIC_IDENTITY_TOKEN", t)}
    return [
        _core.container(ui.label(tr("Workload identity federation"), size="xs", weight="medium", color="text_muted",
                                 theme=t), padding=(6, 0, 0, 0)),
        ui.label(tr("Use Claude without an API key: a token from your identity provider (GitHub Actions, Google "
                    "Cloud, Azure, Okta, Kubernetes…) is exchanged for a short-lived Claude token. Create the issuer "
                    "and the rule in the Claude Console."), size="xs", color="text_muted", theme=t),
        ui.field(tr("Federation rule"), _text(f.rule_id, lambda v: c.set_federation("rule_id", v), "fdrl_…", t),
                 theme=t),
        ui.field(tr("Organization ID"), _text(f.organization_id, lambda v: c.set_federation("organization_id", v),
                                              "00000000-0000-…", t), theme=t),
        ui.field(tr("Service account"), _text(f.service_account_id, lambda v: c.set_federation(
            "service_account_id", v), tr("svac_… (optional)"), t), theme=t),
        ui.field(tr("Workspace"), _text(f.workspace_id, lambda v: c.set_federation("workspace_id", v),
                                        tr("wrkspc_… (optional)"), t), theme=t),
        ui.field(tr("Identity token"), _core.column([source, where.get(f.token_source, where["file"])], spacing=4),
                 theme=t),
        _core.row([ui.button(tr("Test the connection"), lambda: c.test_provider(pid), icon="plug-zap",
                             variant="ghost", size="sm", disabled=not f.enabled or c.busy_provider == pid, theme=t)]),
    ]


def _draft_form(c: AgentController, t: Theme) -> Any:
    """The form that adds or edits an MCP server or an external agent."""
    draft = c.server_draft
    assert draft is not None
    mcp = draft["kind"] == "mcp"
    rows = [
        ui.field(tr("Name"), _text(draft["name"], lambda v: c.set_draft("name", v), "github", t, width=200), theme=t),
        ui.field(tr("Command"), _text(draft["command"], lambda v: c.set_draft("command", v),
                                      "npx -y @modelcontextprotocol/server-github" if mcp else
                                      "npx -y @agentclientprotocol/claude-agent-acp@latest", t, width=340),
                 description=tr("The program and its arguments, as you would type them in a terminal"), theme=t),
    ]
    if mcp:
        rows.append(ui.field(tr("Or the URL"), _text(draft["url"], lambda v: c.set_draft("url", v),
                                                     "https://example.com/mcp", t, width=340),
                             description=tr("A remote server (Streamable HTTP)"), theme=t))
    rows.append(ui.field(tr("Secrets"), _text(draft["secrets"], lambda v: c.set_draft("secrets", v),
                                              "GITHUB_TOKEN=…; OTHER=…" if mcp else "ANTHROPIC_API_KEY=…", t,
                                              width=340, secure=True),
                         description=tr("NAME=value pairs separated by ; (environment variables, or headers for a "
                                        "URL), kept in the system keychain"), theme=t))
    rows.append(_core.row([_core.space(width="fill"),
                           ui.button(tr("Cancel"), c.cancel_draft, variant="ghost", size="sm", theme=t),
                           ui.button(tr("Save"), c.save_draft, variant="solid", size="sm", theme=t)], spacing=4))
    return _core.container(_core.column(rows, spacing=8), padding=(8, 10), width="fill", bg=t.editor,
                           border_color=t.border_variant, border_width=1, radius=t.radius)



def _section(title: str, description: str, rows: Sequence[Any], t: Theme, *, actions: Sequence[Any] = ()) -> Any:
    """A part of the agent settings, like Zed's: a title with its buttons, a line about it, then its rows."""
    return _core.column([
        ui.label(title, size="sm", weight="semibold", theme=t),
        ui.label(description, size="xs", color="text_muted", theme=t) if description else None,
        _core.row(list(actions), spacing=4, wrap=True) if actions else None,
        _core.column([r for r in rows if r is not None], spacing=2, width="fill"),
    ], spacing=6, width="fill")


def _mcp_rows(c: AgentController, t: Theme) -> List[Any]:
    rows: List[Any] = []
    for config in c.settings.mcp_servers:
        why = c.mcp_status.get(config.name, "")
        busy = c.busy_provider == f"mcp:{config.name}"
        if not config.enabled:
            status = "off"
        elif busy:
            status = "starting"
        elif not why:
            status = ""
        else:
            status = "running" if config.name in c.mcp_ok else "error"
        detail = config.url or " ".join([config.command, *config.args])
        rows.append(ui.ServiceRow(
            name=config.name, detail=detail, icon_name="globe" if config.url else "plug", status=status,
            status_text=why, enabled=config.enabled, busy=busy, theme=t, key=f"mcp:{config.name}",
            on_toggle=lambda _e, n=config.name: c.toggle_server("mcp", n),
            actions=[ui.MenuItem(tr("Restart"), lambda n=config.name: c.test_server(n), icon="rotate-cw"),
                     ui.MenuItem(tr("Edit"), lambda n=config.name: c.edit_server("mcp", n), icon="pencil"),
                     ui.MenuItem(tr("Remove"), lambda n=config.name: c.remove_server("mcp", n), icon="trash-2",
                                 danger=True)]))
    draft = c.server_draft
    if draft is not None and draft["kind"] == "mcp":
        rows.append(_draft_form(c, t))
    return rows


def _agent_rows(c: AgentController, t: Theme) -> List[Any]:
    rows: List[Any] = []
    for config in c.settings.acp_agents:
        update = c.agent_update(config)
        busy = bool(config.registry_id) and c.registry_busy == config.registry_id
        if update:
            status, text = "update", tr("Version {version} is available", version=update)
        elif config.registry_id or _acp.installed(config):
            status, text = "installed", ""
        else:
            status, text = "missing", tr("{command} is not installed", command=config.command)
        actions = [ui.MenuItem(tr("Edit"), lambda n=config.name: c.edit_server("acp", n), icon="pencil"),
                   ui.MenuItem(tr("Uninstall") if config.registry_id else tr("Remove"),
                               lambda n=config.name: c.uninstall_agent(n), icon="trash-2", danger=True)]
        rows.append(ui.ServiceRow(
            name=config.label, version=config.version, detail=" ".join([config.command, *config.args]),
            icon_name="terminal", status=status, status_text=text, enabled=config.enabled, busy=busy,
            primary=tr("Update") if update else "", theme=t, key=f"acp:{config.name}",
            on_toggle=lambda _e, n=config.name: c.toggle_server("acp", n),
            on_primary=lambda _e, n=config.name: c.update_agent(n), actions=actions))
    draft = c.server_draft
    if draft is not None and draft["kind"] == "acp":
        rows.append(_draft_form(c, t))
    if c.registry_open:
        if c.registry_error:
            rows.append(ui.callout(tr("The ACP registry could not be loaded"), c.registry_error, tint="warning",
                                   icon="wifi-off", actions=[ui.button(tr("Try again"), lambda: c.load_registry(True),
                                                                       variant="ghost", size="sm", theme=t)],
                                   theme=t))
        elif c.registry_busy == "*" and not c.registry:
            rows.append(_core.row([ui.spinner(size=12, theme=t), ui.label(tr("Loading the ACP registry…"), size="sm",
                                                                         color="text_muted", theme=t)], spacing=6))
        else:
            items = c.registry_items()
            rows.append(_core.container(ui.Catalog(items=items, busy=c.registry_busy, height=min(48 * len(items) + 8, 300),
                                                   theme=t,
                                                   key="acp-registry", on_install=lambda e: c.install_agent(e.value)),
                                        padding=(6, 8), bg=t.editor, border_color=t.border_variant, border_width=1,
                                        radius=t.radius, width="fill"))
    rows.append(ui.field(tr("Let external agents control the editor"), ui.switch(
        c.settings.share_pyzed_mcp, lambda v: c.set_setting("share_pyzed_mcp", v), theme=t), description=tr(
        "Gives them the built-in agent's tools over MCP: the open form and its code, the project, running the "
        "app, and Pyzed's components and docs"), theme=t))
    return rows


def _skill_rows(c: AgentController, t: Theme) -> List[Any]:
    off = set(c.settings.disabled_skills)
    sources = {"project": tr("Project"), "claude": "~/.claude", "user": "~/.agents", "pyzed": "Pyzed"}
    rows: List[Any] = []
    for skill in c.skills():
        actions = [ui.MenuItem(tr("Show in folder"), lambda n=skill.name: c.open_skill_folder(n), icon="folder-open")]
        if skill.origin():
            actions.insert(0, ui.MenuItem(tr("Update"), lambda n=skill.name: c.update_skill(n), icon="refresh-cw"))
        if skill.source == "pyzed":
            actions.append(ui.MenuItem(tr("Remove"), lambda n=skill.name: c.remove_skill(n), icon="trash-2",
                                       danger=True))
        rows.append(ui.ServiceRow(
            name=skill.name, version=sources.get(skill.source, skill.source), summary=skill.description[:160],
            icon_name="book-open", enabled=skill.name not in off, busy=c.skill_busy == skill.name, theme=t,
            key=f"skill:{skill.name}", actions=actions,
            on_toggle=lambda e, n=skill.name: c.toggle_skill(n, bool(e.value))))
    rows.append(_core.row([
        _core.container(_text(c.skill_url, c.set_skill_url, tr("https://github.com/… (a repository of skills)"), t,
                              width=10_000), width="fill"),
        ui.spinner(size=12, theme=t) if c.skill_busy == "*" else None,
        ui.button(tr("Install"), c.install_skill_url, variant="ghost", size="sm",
                  disabled=not c.skill_url.strip() or bool(c.skill_busy), theme=t),
        ui.button(tr("From a folder…"), c.pick_skill_folder, icon="folder", variant="ghost", size="sm",
                  disabled=bool(c.skill_busy), theme=t),
    ], spacing=4, align="center"))
    return rows


def settings_view(d: "Designer", t: Theme) -> Any:
    """The agent settings inside the panel, like Zed's: model providers, external agents (with the ACP
    registry), MCP servers, skills, rules and the agent's options."""
    c = d.agent
    s = c.settings
    store = _agents.secrets.store()
    storage = ui.callout(tr("Keys are stored in {where}", where=store.backend_name), tr(
        "Never in Pyzed's settings files. Threads are saved on this computer only."), tint="success",
        icon="lock", theme=t) if store.secure else ui.callout(
        tr("No system keychain found"), tr("Keys you paste are kept only until you close the designer. Install the "
                                           "keyring package or set the key in an environment variable."),
        tint="warning", icon="lock-open", theme=t)
    providers = _section(tr("LLM providers"), tr("Sign in with the browser or paste a key."),
                         [_provider_row(c, pid, t) for pid in _providers.PROVIDERS if pid != "acp"], t)
    adding = c.server_draft is not None
    agents = _section(tr("External agents"), tr(
        "Agents that run as their own program and speak the Agent Client Protocol, like in Zed: install them from "
        "the ACP registry and start a thread with them from the + menu."), _agent_rows(c, t), t, actions=[
        ui.button(tr("Install from registry"), lambda: c.toggle_registry(), icon="package-search", variant="ghost",
                  size="sm", selected=c.registry_open, theme=t),
        ui.button(tr("Add custom agent"), lambda: c.new_server("acp"), icon="plus", variant="ghost", size="sm",
                  disabled=adding, theme=t)])
    mcp = _section(tr("MCP servers"), tr(
        "Their tools are added to the agent's. Tools that are not read-only ask first, like file writes."),
        _mcp_rows(c, t), t, actions=[ui.button(tr("Add server"), lambda: c.new_server("mcp"), icon="plus",
                                               variant="ghost", size="sm", disabled=adding, theme=t)])
    skills = _section(tr("Skills"), tr(
        "Folders with a SKILL.md: instructions and files the agent reads when a task needs them. Claude Code "
        "reads its own."), _skill_rows(c, t), t, actions=[
        ui.icon_button("refresh-cw", c.refresh_skills, size="sm", tooltip=tr("Look for skills again"), theme=t)])
    found = c.project_rules()
    rules = _section(tr("Rules"), tr("Instructions added to every thread, like Zed's rules."), [
        ui.input(s.rules, lambda v: c.set_setting("rules", v), placeholder=tr(
            "e.g. Answer in Spanish. Use snake_case names."), size="sm", theme=t),
        ui.ServiceRow(name=tr("Project rules"), icon_name="scroll-text", detail=found.name if found else "",
                      summary=tr("Read by the agent in every thread of this project") if found
                      else tr("A file at the project's root with rules for every agent"),
                      primary=tr("Open") if found else tr("Create AGENTS.md"), theme=t, key="project-rules",
                      on_primary=lambda _e: c.open_rules())], t)
    clients = _section(tr("Pyzed's MCP in your agents"), tr(
        "The AI agents of this computer (Claude Code, Cursor, Gemini CLI, Codex...) get Pyzed's MCP server, so they "
        "know its components, docs and checks. Restart an agent after adding it."), [
        ui.field(tr("Add it to new agents on start"), ui.switch(s.install_pyzed_mcp, lambda v: c.set_setting(
            "install_pyzed_mcp", v), theme=t), theme=t),
        *[ui.ServiceRow(name=client.name, detail=str(client.path), icon_name="plug",
                        status={"installed": "running", "missing": "off", "unreadable": "error"}[state],
                        status_text=tr({"installed": "Pyzed's MCP is added", "missing": "Not added",
                                        "unreadable": "Its settings file could not be read; add it by hand"}[state]),
                        busy=c.mcp_clients_busy == client.id,
                        primary="" if state == "unreadable" else tr("Remove") if state == "installed" else tr("Add"),
                        theme=t, key=f"mcp-client:{client.id}",
                        on_primary=lambda _e, cid=client.id: c.toggle_mcp_client(cid))
          for client, state in c.mcp_clients()],
    ], t)
    tools = c.tool_index()
    permissions = _section(tr("Permissions"), tr(
        "What the agent may do without asking. Pick the mode in the message box; tools you always allowed are "
        "listed here."), [
        _core.column([_menu_row(icon, tr(label), tr(text), lambda m=mode: c.set_mode(m), t,
                                checked=s.mode == mode) for mode, (label, icon, text) in MODE_TEXT.items()],
                     spacing=0, width="fill"),
        *[ui.ServiceRow(name=_tool_title(name, tools), detail=name, icon_name="shield-check",
                        summary=tr("Runs without asking"), primary=tr("Ask again"), theme=t, key=f"allowed:{name}",
                        on_primary=lambda _e, name=name: c.forget_tool(name)) for name in s.allowed_tools],
    ], t)
    efforts = list(_providers.EFFORTS)
    provider_id, model_name = _providers.split_model(s.model)
    claude = provider_id != "acp" and "claude" in model_name.lower()
    general = ui.settings_group(tr("Agent"), [row for row in [
        ui.field(tr("Default model"), ui.select(c.models(), s.model, c.set_model, width=200, size="sm", theme=t),
                 description=tr("An external agent's own options (mode, model, effort) are in the message box")
                 if provider_id == "acp" else None, theme=t),
        # Claude's own options, only when Pyzed Agent answers with Claude
        ui.field(tr("Effort"), ui.select(efforts, s.effort, lambda v: c.set_setting("effort", v), width=120, size="sm",
                                         theme=t),
                 description=tr("How much the model thinks before answering (Claude)"), theme=t) if claude else None,
        ui.field(tr("Thinking"), ui.switch(s.thinking, lambda v: c.set_setting("thinking", v), theme=t),
                 description=tr("Let Claude think before answering; off answers sooner"), theme=t) if claude else None,
        ui.field(tr("Fast mode"), ui.switch(s.fast, lambda v: c.set_setting("fast", v), theme=t),
                 description=tr("Fast mode: faster answers at a higher price (Claude Opus)"), theme=t) if claude else None,
        ui.field(tr("Ask before writing files"), ui.switch(s.confirm_writes, lambda v: c.set_setting("confirm_writes", v),
                                                           theme=t),
                 description=tr("Creating forms and saving files waits for your OK"), theme=t),
    ] if row is not None], theme=t)
    more = ui.settings_group(tr("More options"), [
        ui.field(tr("Show thinking"), ui.switch(s.show_thinking, lambda v: c.set_setting("show_thinking", v), theme=t),
                 theme=t),
        ui.field(tr("Follow the agent"), ui.switch(s.follow_agent, lambda v: c.set_setting("follow_agent", v),
                                                   theme=t),
                 description=tr("Open the files it writes as it works"), theme=t),
        ui.field(tr("Notify when the agent finishes"), ui.switch(s.notify_when_done, lambda v: c.set_setting(
            "notify_when_done", v), theme=t),
                 description=tr("A desktop notification while the window is in the background"), theme=t),
        ui.field(tr("Keep conversations"), ui.switch(s.keep_history, lambda v: c.set_setting("keep_history", v),
                                                     theme=t),
                 description=tr("Save threads on this computer, readable only by you"), theme=t),
    ], theme=t)
    rule = _core.rule(thickness=1, color=t.border_variant)
    # the everyday settings first; agents, servers, skills and the rest fold away under "Advanced"
    advanced_open = c.advanced_open or c.registry_open or adding
    advanced = ui.disclosure(tr("Advanced"), _core.column(
        [agents, rule, mcp, rule, skills, rule, rules, rule, clients, rule, more], spacing=14, width="fill"),
        open=advanced_open, on_toggle=c.toggle_advanced, theme=t)
    return _core.scrollable(_core.column([general, storage, providers, rule, permissions, rule, advanced], spacing=14,
                                         padding=(10, 12, 16, 12), width="fill"),
                            height="fill", scrollbar_width=4, id=SETTINGS_SCROLL)
