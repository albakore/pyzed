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
import shutil
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

from .. import _core, ui
from .. import agents as _agents
from ..agents import acp as _acp
from ..agents import mcp_client as _mcp
from ..agents import providers as _providers
from ..icons import icon as _icon
from ..theme import Theme, alpha
from . import agent_tools
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


#: Image files that can be attached (the file dialog's filter and the @ popup).
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")

#: How long the clipboard is watched for a copied key.
CAPTURE_SECONDS = 300.0
#: How long the panel waits for the Claude Code sign-in in the terminal.
CLAUDE_LOGIN_SECONDS = 900.0
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
        self.thread = _agents.Thread(model=self.settings.model)
        self.input = ""
        self.running = False
        self.error = ""
        self.view = "thread"  # or "history"
        self.live_text = ""
        self.live_thinking = ""
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
        self.key_buffer: Dict[str, str] = {}
        self.url_buffer: Dict[str, str] = {}
        self.busy_provider: Optional[str] = None
        self.capture: Optional[KeyCapture] = None
        # the designer comes back to the front once a sign-in in the browser is done
        self.raise_window = False
        # signing in to Claude Code with a Claude subscription: when to stop checking, and the next check
        self.claude_login: Optional[float] = None
        self._claude_check = 0.0
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
        self.server_draft: Optional[Dict[str, Any]] = None  # the MCP server or agent being added or edited
        self._acp: Dict[str, Any] = {}  # thread id -> ACPAgent
        self.google_projects: List[str] = []
        import atexit

        atexit.register(self.shutdown)
        self._files: Optional[Tuple[float, List[str]]] = None
        self._queue: "queue.Queue[Tuple[Any, ...]]" = queue.Queue()
        self._agent: Optional[_agents.Agent] = None
        self._stream = stream
        self._tools: Optional[Dict[str, _agents.Tool]] = None

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
            or not self._queue.empty()

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
        if tool.name in self.always_allow:
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
                self.d.notify(tr("The MCP server {name} did not start", name=server), why, kind="warning",
                              seconds=6)
            elif kind == "mcp_ready":
                for server in list(self.mcp.clients):
                    self.mcp_status[server] = tr("{count} tools", count=len(self.mcp._tools.get(server, [])))
            elif kind == "mcp_test":
                _, server, message = item
                self.busy_provider = None
                self.mcp_status[server] = message
            elif kind == "device":
                _, pid, user_code, uri = item
                if self.device is not None and self.device.provider == pid:
                    self.device.user_code, self.device.uri = user_code, uri
            elif kind == "device_done":
                self.device = None
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
        elif event.kind == "turn":
            self.live_text = ""
            self.live_thinking = ""
        elif event.kind == "tool_call":
            self.tool_status[event.call_id] = "running"
        elif event.kind == "tool_result":
            self.tool_status[event.call_id] = "error" if event.error else "done"
        elif event.kind == "plan":
            self.live_plan = list(event.args.get("steps") or [])
        elif event.kind == "error":
            self.error = event.text
        elif event.kind == "done":
            self.running = False
            self.live_text = self.live_thinking = ""
            self.live_plan = []
            self._agent = None
            self._keep()

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
        self.error = ""
        self.view = "thread"
        self.running = True
        self.snapshot = []
        self.changed = False
        self.tool_status = {}
        model = self.thread.model or self.settings.model
        self.thread.model = model
        note = agent_tools.context_note(self.d)
        content = [{"type": "text", "text": prompt or tr("Look at the attached images.")}, *extra, *images,
                   {"type": "text", "text": f"<context>{note}</context>"}]
        put = self._queue.put
        emit = lambda e: put(("event", e))  # noqa: E731
        jobs = [b for b in content if b.get("type") == "screenshot"]
        provider_id, name = _providers.split_model(model)
        servers = self.mcp
        servers.cwd = str(self.project_root())
        if provider_id == "acp":
            agent: Any = self._external_agent(name)
        else:
            agent = _agents.Agent(model, tools=agent_tools.designer_tools(self.d),
                                  system=agent_tools.system_prompt(self.d), settings=self.settings,
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
            self._agent.stop()
        if self.pending is not None:
            self.answer(False)

    def answer(self, allow: bool, always: bool = False) -> None:
        """Answers the pending confirmation."""
        pending, self.pending = self.pending, None
        if pending is None:
            return
        if allow and always:
            self.always_allow.add(pending.tool.name)
        pending.box.value = allow
        pending.box.done.set()

    def suggest(self, text: str) -> Any:
        """Fills the input with ``text`` and sends it."""
        return self.send(tr(text))

    def new_thread(self) -> Any:
        """Starts an empty thread (the current one stays in the history)."""
        if self.running:
            return None
        if self.thread.messages:
            self._keep()
        self.thread = _agents.Thread(model=self.settings.model)
        self.close_external_agents()
        self.view = "thread"
        self.error = ""
        self.snapshot = []
        self.changed = False
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
            self.thread = _agents.Thread(model=self.settings.model)

    def toggle_history(self) -> None:
        self.view = "thread" if self.view == "history" else "history"

    def toggle_block(self, key: str) -> None:
        self.open_blocks ^= {key}

    def set_model(self, label: str) -> None:
        """Picks the model of the current thread (and of new threads)."""
        self.thread.model = label
        self.settings.model = label
        self.menu = None
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
        """Sends the last user message again."""
        for m in reversed(self.thread.messages):
            if m.get("role") == "user":
                texts = [b.get("text", "") for b in m.get("content", []) if b.get("type") == "text"]
                if texts and not texts[0].startswith("<context>"):
                    return self.send(texts[0])
        return None

    def compose(self, text: str) -> Any:
        """Shows the panel with ``text`` in the input, ready to finish and send."""
        self.d.layout.show("agent")
        self.view = "thread"
        return self._box(text)

    def open_settings(self, provider: Optional[str] = None) -> Any:
        """Opens Settings → AI agents (with ``provider`` unfolded)."""
        self.menu = None
        if provider in _providers.PROVIDERS:
            self.provider_open = provider
        self.d.dialog = "agent_settings"
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
        """Files of the project the @ popup offers (no hidden, build or secret files), cached briefly."""
        now = time.monotonic()
        if self._files is not None and now - self._files[0] < 10:
            return self._files[1]
        from ..agents.tools import SECRET_FILES, SKIP_DIRS

        root = self.project_root()
        out: List[str] = []
        try:
            for path in sorted(root.rglob("*")):
                rel = path.relative_to(root)
                if any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts):
                    continue
                if path.suffix in _FILE_SUFFIXES and path.is_file() and \
                        not any(fnmatch.fnmatch(path.name, p) for p in SECRET_FILES):
                    out.append(rel.as_posix())
                    if len(out) >= 300:
                        break
        except OSError:
            pass
        self._files = (now, out)
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
                webbrowser.open(code.verification_uri)
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
                put(("mcp_test", name, tr("{count} tools", count=len(specs))))
            except Exception as err:  # noqa: BLE001
                put(("mcp_test", name, str(err)))

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
        if shutil.which("npx") is None:
            self.d.notify(tr("Claude Code needs Node.js 18 or later"), tr("Install it, then try again."),
                          kind="warning", seconds=8)
            webbrowser.open(NODE_URL)
            return
        if self.settings.acp_agent("claude-code") is None:
            self.settings.acp_agents.append(_acp.preset("claude-code"))
        self.settings.share_pyzed_mcp = True
        self.set_model("acp:claude-code")
        self.d.dialog = None if self.d.dialog == "agent_settings" else self.d.dialog
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
    def needs_claude_login(self) -> bool:
        """Whether the last answer failed because Claude Code is not signed in."""
        provider, name = _providers.split_model(self.thread.model or self.settings.model)
        error = self.error.lower()
        return provider == "acp" and name == "claude-code" and ("auth" in error or "/login" in error)

    def open_key_page(self, pid: str) -> None:
        url = _providers.PROVIDERS[pid].key_url
        if url:
            webbrowser.open(url)

    def set_setting(self, key: str, value: Any) -> None:
        setattr(self.settings, key, value)
        self.save_settings()


# -- views -------------------------------------------------------------------------------------------

def _tool_title(tool_name: str, tools: Dict[str, _agents.Tool]) -> str:
    tool_ = tools.get(tool_name)
    return tr(tool_.title) if tool_ is not None and tool_.title else tool_name


def _args_preview(args: Dict[str, Any]) -> str:
    for key in ("name", "path", "type", "handler", "event", "query", "slug", "kind", "pattern"):
        if isinstance(args.get(key), str) and args[key]:
            return args[key]
    return ""


def _tool_card(c: AgentController, block: Dict[str, Any], result: Optional[Dict[str, Any]],
               tools: Dict[str, _agents.Tool], t: Theme) -> Any:
    call_id = block.get("id", "")
    status = c.tool_status.get(call_id) or ("error" if result and result.get("is_error") else
                                            "done" if result else "running" if c.running else "error")
    if c.pending is not None and c.running and status == "running" and c.pending.tool.name == block.get("name"):
        status = "waiting"
    icon = {"running": None, "waiting": "hand", "done": "check", "error": "circle-x"}[status]
    color = {"waiting": t.warning, "done": t.text_muted, "error": t.error}.get(status, t.text_muted)
    lead = ui.spinner(size=12, theme=t) if status == "running" else _icon(icon or "check", size=12, color=color)
    title = _tool_title(block.get("name", ""), tools)
    preview = _args_preview(block.get("input") or {})
    head = _core.row([lead, ui.label(title, size="sm", color="text_muted", theme=t),
                      ui.label(preview, size="sm", mono=True, color="text_placeholder", theme=t) if preview else None],
                     spacing=6, align="center")
    key = f"tool:{call_id}"
    body = None
    if key in c.open_blocks:
        import json

        text = json.dumps(block.get("input") or {}, indent=1, ensure_ascii=False)
        pictures: List[Any] = []
        if result is not None:
            content = result.get("content")
            if isinstance(content, list):
                pictures = [_core.image(data, height=160, content_fit="contain", radius=4)
                            for data in (_image_bytes(b) for b in content if b.get("type") == "image") if data]
                content = "".join(b.get("text", "") for b in content if b.get("type") == "text")
            text += "\n\n→ " + (content if isinstance(content, str) else json.dumps(content, ensure_ascii=False))
        body = _core.container(_core.column([
            ui.label(text[:4000], size="xs", mono=True, color="text_muted", theme=t), *pictures], spacing=6),
            padding=(6, 8), width="fill", bg=t.editor, radius=t.radius)
    return _core.column([
        _core.button(head, lambda: c.toggle_block(key), padding=(3, 6), width="fill", bg=None, hover_bg=t.element_hover,
                     radius=t.radius),
        body,
    ], spacing=2, width="fill")


def _thinking_card(c: AgentController, key: str, text: str, t: Theme, live: bool = False) -> Any:
    opened = key in c.open_blocks
    head = _core.row([_icon("brain", size=12, color=t.text_muted),
                      ui.label(tr("Thinking…") if live else tr("Thought"), size="sm", color="text_muted", theme=t),
                      _icon("chevron-down" if opened else "chevron-right", size=12, color=t.text_placeholder)],
                     spacing=6, align="center")
    body = ui.label(text.strip(), size="sm", color="text_muted", theme=t) if opened and text.strip() else None
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


def _user_bubble(text: str, t: Theme, images: Sequence[Dict[str, Any]] = ()) -> Any:
    pictures = [_core.image(data, height=72, content_fit="contain", radius=4)
                for data in (_image_bytes(b) for b in images) if data]
    return _core.container(_core.column([
        ui.label(text, size="sm", theme=t) if text else None,
        _core.row(pictures, spacing=6, wrap=True) if pictures else None,
    ], spacing=6), padding=(8, 10), width="fill", bg=t.element, border_color=t.border_variant, border_width=1,
        radius=t.radius + 2)


def _messages(c: AgentController, t: Theme) -> List[Any]:
    """The thread drawn from its messages, then what is streaming now."""
    tools = c.tool_index()
    messages = list(c.thread.messages)
    results: Dict[str, Dict[str, Any]] = {}
    for m in messages:
        if m.get("role") == "user":
            for b in m.get("content", []):
                if b.get("type") == "tool_result":
                    results[b.get("tool_use_id", "")] = b
    rows: List[Any] = []
    for i, m in enumerate(messages):
        blocks = m.get("content", [])
        if m.get("role") == "user":
            texts = [b.get("text", "") for b in blocks if b.get("type") == "text"
                     and not b.get("text", "").startswith("<context>")]
            images = [b for b in blocks if b.get("type") == "image"]
            if texts or images:
                rows.append(_user_bubble("\n".join(texts), t, images))
            continue
        for j, b in enumerate(blocks):
            kind = b.get("type")
            if kind == "text" and b.get("text", "").strip():
                rows.append(ui.markdown(b["text"], size=13, theme=t))
            elif kind == "thinking" and c.settings.show_thinking and b.get("thinking", "").strip():
                rows.append(_thinking_card(c, f"think:{i}:{j}", b["thinking"], t))
            elif kind == "tool_use":
                rows.append(_tool_card(c, b, results.get(b.get("id", "")), tools, t))
    if c.running:
        if c.live_thinking and c.settings.show_thinking:
            rows.append(_thinking_card(c, "think:live", c.live_thinking, t, live=True))
        if c.live_text:
            rows.append(ui.markdown(c.live_text, size=13, theme=t))
        if not c.live_text:
            rows.append(_core.row([ui.spinner(size=12, theme=t),
                                   ui.label(tr("Working…"), size="sm", color="text_muted", theme=t)],
                                  spacing=6, align="center"))
    return rows


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
    """The agent's plan (its last ``update_plan``) as a checklist above the message box, while it is running
    or has steps left. Clicking the header folds it."""
    steps = c.live_plan if c.running and c.live_plan else agent_tools.plan_of(c.thread.messages)
    done = sum(1 for s in steps if s["status"] == "done")
    if not steps or (done == len(steps) and not c.running):
        return None
    folded = "plan" in c.open_blocks
    head = _core.row([
        _icon("list-checks", size=13, color=t.text_accent),
        ui.label(tr("Plan"), size="sm", weight="medium", theme=t),
        ui.label(f"{done}/{len(steps)}", size="xs", color="text_muted", theme=t),
        _core.space(width="fill"),
        _icon("chevron-right" if folded else "chevron-down", size=12, color=t.text_placeholder),
    ], spacing=6, align="center")
    rows: List[Any] = [_core.button(head, lambda: c.toggle_block("plan"), padding=(2, 4), bg=None,
                                    hover_bg=t.element_hover, radius=t.radius, width="fill")]
    if not folded:
        for step in steps:
            status = step["status"]
            if status == "in_progress":
                lead = ui.spinner(size=12, theme=t) if c.running else _icon("circle-dot", size=12, color=t.accent)
            else:
                lead = _icon("circle-check" if status == "done" else "circle", size=12,
                             color=t.success if status == "done" else t.text_placeholder)
            rows.append(_core.row([lead, ui.label(step["step"], size="sm", theme=t,
                                                  color="text_muted" if status == "done" else "text")],
                                  spacing=8, align="center", padding=(0, 4)))
    return _core.container(_core.column(rows, spacing=4, width="fill"), padding=(6, 8), width="fill",
                           bg=t.surface,
                           border_color=t.border_variant, border_width=1, radius=t.radius + 2)


def _review_bar(c: AgentController, t: Theme) -> Any:
    names = ", ".join(doc.display_name for doc, _, _ in c.snapshot)
    return _core.container(_core.row([
        ui.tooltip(ui.label(tr("Agent changes"), size="sm", weight="medium", theme=t),
                   tr("The agent changed {files}", files=names) + ". " + tr("Each change is also an undo step."),
                   theme=t),
        _core.space(width="fill"),
        ui.button(tr("Reject"), c.reject, variant="ghost", size="sm", theme=t),
        ui.button(tr("Keep"), c.keep, variant="tinted", size="sm", theme=t),
    ], spacing=6, align="center"), padding=(4, 8), width="fill", bg=alpha(t.accent, 0.08), border_color=t.border_variant,
        border_width=1, radius=t.radius)


def _history(c: AgentController, t: Theme) -> Any:
    threads = c.store.list()
    if not threads:
        return ui.empty_state(tr("No threads yet"), tr("Your conversations with the agent show up here."),
                              icon="history", theme=t)
    rows = []
    for th in threads:
        rows.append(_core.row([
            _core.container(ui.list_item(th.display_title, lambda i=th.id: c.open_thread(i), icon="message-square",
                                         selected=th.id == c.thread.id, height=30,
                                         end=ui.label(th.model.partition(":")[2], size="xs", color="text_placeholder",
                                                      theme=t), theme=t),
                            width="fill"),
            ui.icon_button("trash-2", lambda i=th.id: c.delete_thread(i), size="sm", tooltip=tr("Delete"), theme=t),
        ], spacing=2, align="center"))
    return _core.scrollable(_core.column(rows, spacing=1, width="fill", padding=(4, 6)), height="fill",
                            scrollbar_width=4)


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
    controls = _core.row([
        ui.icon_button("plus", c.toggle_add_menu, size="sm", selected=c.menu == "add",
                       tooltip=tr("Add context or images"), theme=t),
        _chip(tr(mode_label), lambda: c.toggle_menu("mode"), t, icon=mode_icon, selected=c.menu == "mode",
              tooltip=tr(mode_text)),
        _core.space(width="fill"),
        _chip(agent.label if agent else model_label(model), lambda: c.toggle_menu("model"), t,
              icon="terminal" if external else None, selected=c.menu == "model", tooltip=tr("Model")),
        None if external else _chip(tr(EFFORT_TEXT[s.effort]), lambda: c.toggle_menu("effort"), t,
                                    selected=c.menu == "effort", tooltip=tr("Effort"), disabled=not claude),
        None if external else _chip(tr("Fast"), c.toggle_fast, t, icon="zap",
                                    selected=s.fast and name in _providers.FAST_MODELS, menu=False,
                                    disabled=name not in _providers.FAST_MODELS,
                                    tooltip=tr("Fast mode: faster answers at a higher price (Claude Opus)")),
    ], spacing=2, align="center")
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
        ui.button(tr("Open the page again"), lambda: webbrowser.open(login.uri or "https://github.com/login/device"),
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


def view(d: "Designer", t: Theme) -> Any:
    """The Agent panel: header, the thread (or the history), and the message box."""
    c = d.agent
    title = tr("History") if c.view == "history" else (c.thread.display_title if c.thread.messages else tr("New thread"))
    title = title if len(title) <= 26 else title[:25].rstrip() + "…"
    header = ui.panel_header(title, icon="sparkles", actions=[
        ui.icon_button("plus", c.new_thread, size="sm", tooltip=tr("New thread"), theme=t),
        ui.icon_button("history", c.toggle_history, size="sm", selected=c.view == "history",
                       tooltip=tr("History"), theme=t),
        ui.icon_button("minimize-2" if c.expanded else "maximize-2", c.toggle_expand, size="sm",
                       tooltip=tr("Back to the dock") if c.expanded else tr("Expand the panel"), theme=t),
        ui.icon_button("settings-2", lambda: c.open_settings(), size="sm", tooltip=tr("AI agents settings"),
                       theme=t),
    ], theme=t)
    if c.view == "history":
        return _core.column([header, _history(c, t)], width="fill", height="fill")
    rows = _messages(c, t) if c.thread.messages else [_empty(c, t)]
    if c.error and not c.running:
        actions = [
            ui.button(tr("Retry"), c.retry, icon="refresh-cw", variant="ghost", size="sm", theme=t),
            ui.button(tr("Settings"), lambda: c.open_settings(), variant="ghost", size="sm", theme=t),
        ]
        if c.needs_claude_login:
            actions.insert(0, ui.button(tr("Sign in to Claude"), c.open_claude_login, icon="log-in",
                                        variant="tinted", size="sm", theme=t))
        rows.append(ui.callout(tr("The agent stopped"), c.error, tint="error", icon="triangle-alert", actions=actions,
                               theme=t))
    thread = _core.scrollable(_core.column(rows, spacing=10, width="fill", padding=(10, 12)), height="fill",
                              id=SCROLL_ID, anchor_bottom=True, scrollbar_width=4)
    bottom: List[Any] = []
    if c.capture is not None and d.dialog != "agent_settings":
        bottom.append(_capture_callout(c, t))
    if c.claude_login is not None:
        bottom.append(_claude_login_callout(c, t))
    if c.device is not None and d.dialog != "agent_settings":
        bottom.append(_device_callout(c, t))
    bottom.append(_plan_card(c, t))
    if c.pending is not None:
        bottom.append(_confirmation(c, t))
    if c.snapshot and c.changed and not c.running:
        bottom.append(_review_bar(c, t))
    menus = {"mode": _mode_menu, "model": _model_menu, "effort": _effort_menu, "add": _add_menu}
    bottom.append(menus[c.menu](c, t) if c.menu in menus else _popup(c, t))
    bottom.append(_composer(c, t))
    body = _core.column([header, thread, _core.column(bottom, spacing=6, padding=(6, 8, 8, 8), width="fill")],
                        width="fill", height="fill")
    if c.expanded:  # a readable column in the middle of the window, like Zed's zoomed panel
        body = _core.container(_core.container(body, max_width=860, width="fill", height="fill"), width="fill",
                               height="fill", align_x="center")
    return body



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
                                      "npx -y @zed-industries/claude-code-acp", t, width=340),
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


def _server_row(c: AgentController, kind: str, config: Any, t: Theme) -> Any:
    status = c.mcp_status.get(config.name, "") if kind == "mcp" else (
        "" if _acp.installed(config) else tr("{command} is not installed", command=config.command))
    detail = config.url if getattr(config, "url", "") else " ".join([config.command, *config.args])
    busy = c.busy_provider == f"mcp:{config.name}"
    return _core.row([
        _icon("plug" if kind == "mcp" else "terminal", size=14, color=t.text_accent if config.enabled else t.text_muted),
        _core.column([ui.label(getattr(config, "label", config.name), size="sm", weight="medium", theme=t),
                      ui.label(detail[:70], size="xs", mono=True, color="text_muted", theme=t),
                      ui.label(status, size="xs", color="text_muted", theme=t) if status else None], width="fill"),
        ui.spinner(size=12, theme=t) if busy else None,
        ui.icon_button("plug-zap", lambda: c.test_server(config.name), size="sm", tooltip=tr("Test"), theme=t)
        if kind == "mcp" else None,
        ui.switch(config.enabled, lambda _v: c.toggle_server(kind, config.name), theme=t),
        ui.icon_button("pencil", lambda: c.edit_server(kind, config.name), size="sm", tooltip=tr("Edit"), theme=t),
        ui.icon_button("trash-2", lambda: c.remove_server(kind, config.name), size="sm", tooltip=tr("Remove"),
                       theme=t),
    ], spacing=6, align="center")


def _servers_group(c: AgentController, t: Theme) -> Any:
    s = c.settings
    draft = c.server_draft
    rows: List[Any] = [_server_row(c, "mcp", m, t) for m in s.mcp_servers]
    if draft is not None and draft["kind"] == "mcp":
        rows.append(_draft_form(c, t))
    else:
        rows.append(_core.row([ui.button(tr("Add an MCP server"), lambda: c.new_server("mcp"), icon="plus",
                                         variant="ghost", size="sm", theme=t)]))
    mcp = ui.settings_group(tr("MCP servers"), [
        ui.label(tr("Their tools are added to the agent's. Tools that are not read-only ask first, like file writes."),
                 size="xs", color="text_muted", theme=t), *rows], theme=t)
    agents: List[Any] = [_server_row(c, "acp", a, t) for a in s.acp_agents]
    if draft is not None and draft["kind"] == "acp":
        agents.append(_draft_form(c, t))
    else:
        missing = [name for name in _acp.PRESETS if s.acp_agent(name) is None]
        agents.append(_core.row([
            *[ui.button(_acp.PRESETS[name][0], lambda name=name: c.new_server("acp", name), icon="plus",
                        variant="ghost", size="sm", theme=t) for name in missing],
            ui.button(tr("Other…"), lambda: c.new_server("acp"), icon="plus", variant="ghost", size="sm", theme=t),
        ], spacing=4, wrap=True))
    external = ui.settings_group(tr("External agents"), [
        ui.label(tr("Agents that run as their own program and speak the Agent Client Protocol, like in Zed. They work "
                    "in the project folder, ask before acting according to the permission mode and get Pyzed's MCP "
                    "server."), size="xs", color="text_muted", theme=t),
        *agents,
        ui.field(tr("Let external agents control the editor"), ui.switch(s.share_pyzed_mcp, lambda v: c.set_setting(
            "share_pyzed_mcp", v), theme=t), description=tr(
            "Gives them the built-in agent's tools over MCP: the open form and its code, the project, running the "
            "app, and Pyzed's components and docs"), theme=t),
    ], theme=t)
    return _core.column([mcp, external], spacing=14, width="fill")


def settings_dialog(d: "Designer", t: Theme) -> Any:
    """Settings → AI agents: providers and their keys or sign-in, the default model and the permissions."""
    c = d.agent
    s = c.settings
    store = _agents.secrets.store()
    storage = ui.callout(tr("Keys are stored in {where}", where=store.backend_name), tr(
        "Never in Pyzed's settings files. Threads are saved on this computer only."), tint="success",
        icon="lock", theme=t) if store.secure else ui.callout(
        tr("No system keychain found"), tr("Keys you paste are kept only until you close the designer. Install the "
                                           "keyring package or set the key in an environment variable."),
        tint="warning", icon="lock-open", theme=t)
    providers = ui.settings_group(tr("Providers"), [_provider_row(c, pid, t) for pid in _providers.PROVIDERS
                                                    if pid != "acp"], theme=t)
    efforts = list(_providers.EFFORTS)
    agent = ui.settings_group(tr("Agent"), [
        ui.field(tr("Default model"), ui.select(c.models(), s.model, c.set_model, width=240, size="sm", theme=t),
                 theme=t),
        ui.field(tr("Effort"), ui.select(efforts, s.effort, lambda v: c.set_setting("effort", v), width=120, size="sm",
                                         theme=t),
                 description=tr("How much the model thinks before answering (Claude)"), theme=t),
        ui.field(tr("Fast mode"), ui.switch(s.fast, lambda v: c.set_setting("fast", v), theme=t),
                 description=tr("Fast mode: faster answers at a higher price (Claude Opus)"), theme=t),
        ui.field(tr("Ask before writing files"), ui.switch(s.confirm_writes, lambda v: c.set_setting("confirm_writes", v),
                                                           theme=t),
                 description=tr("Creating forms and saving files waits for your OK"), theme=t),
        ui.field(tr("Show thinking"), ui.switch(s.show_thinking, lambda v: c.set_setting("show_thinking", v), theme=t),
                 theme=t),
        ui.field(tr("Keep conversations"), ui.switch(s.keep_history, lambda v: c.set_setting("keep_history", v),
                                                     theme=t),
                 description=tr("Save threads on this computer, readable only by you"), theme=t),
        ui.field(tr("Rules"), ui.input(s.rules, lambda v: c.set_setting("rules", v),
                                       placeholder=tr("e.g. Answer in Spanish. Use snake_case names."), size="sm",
                                       width=280, theme=t),
                 description=tr("Instructions added to every thread"), theme=t),
    ], theme=t)
    body = _core.scrollable(_core.column([storage, providers, _servers_group(c, t), agent], spacing=14,
                                         padding=(0, 6, 0, 0)), height=560, scrollbar_width=4, id=SETTINGS_SCROLL)
    return ui.modal(body, title=tr("AI agents"), on_close=d.close_dialog, width=620, theme=t,
                    footer=[_core.space(width="fill"), ui.button(tr("Done"), d.close_dialog, variant="solid", theme=t)])
