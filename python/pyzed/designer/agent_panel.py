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
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from .. import _core, ui
from .. import agents as _agents
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

#: Prompts offered in an empty thread (English; shown translated).
SUGGESTIONS = (
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


#: How long the clipboard is watched for a copied key.
CAPTURE_SECONDS = 300.0

#: Slash commands: (name, icon, description, prompt to send or None for an action).
SLASH_COMMANDS = (
    ("new", "plus", "Start a new thread", None),
    ("history", "history", "Show the past threads", None),
    ("settings", "settings-2", "AI agents settings", None),
    ("form", "layout-template", "Generate a new form", None),
    ("component", "component", "Generate a reusable component", None),
    ("explain", "book-open", "Explain this form and its code", "Explain what this form does and how its handlers work."),
    ("fix", "wrench", "Check this form's code and fix the issues",
     "Check the code of this form with validate_code and fix every issue it finds."),
    ("tidy", "wand-sparkles", "Align the controls and even out the margins",
     "Align the controls of this form and give them consistent margins."),
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
_FILE_SUFFIXES = (".py", ".pzform", ".pzcomp", ".md", ".toml", ".json", ".txt", ".css", ".yaml", ".yml")


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
        # composer
        self.menu: Optional[str] = None  # "mode" | "model" | "effort" while its menu is open
        self.mentions: List[Mention] = []
        self.picked = 0  # highlighted row of the @ / slash popup
        self._files: Optional[Tuple[float, List[str]]] = None
        self._queue: "queue.Queue[Tuple[Any, ...]]" = queue.Queue()
        self._agent: Optional[_agents.Agent] = None
        self._stream = stream
        self._tools: Optional[Dict[str, _agents.Tool]] = None

    # -- setup ------------------------------------------------------------------------------------
    @property
    def ready(self) -> bool:
        """Whether the selected model's provider is set up."""
        provider_id, _ = _providers.split_model(self.thread.model or self.settings.model)
        return _providers.is_ready(provider_id)

    @property
    def active(self) -> bool:
        """Whether something is in flight (the poll subscription runs while it is)."""
        return self.running or bool(self.inline and self.inline.running) or self.busy_provider is not None \
            or self.capture is not None or not self._queue.empty()

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
            if not _providers.is_ready(pid):
                continue
            out += [f"{pid}:{m}" for m in self.settings.models_of(pid)]
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
        elif event.kind == "error":
            self.error = event.text
        elif event.kind == "done":
            self.running = False
            self.live_text = self.live_thinking = ""
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
        # a mention whose @label was deleted from the text is dropped
        self.mentions = [m for m in self.mentions if f"@{m.label}" in text]

    def send(self, text: Optional[str] = None) -> Any:
        """Sends the input (or ``text``) to the agent in the current thread. With the @ or / popup open,
        Enter picks its highlighted row instead."""
        if text is None and self.trigger() is not None:
            items = self.popup_items()
            if items:
                return items[min(self.picked, len(items) - 1)][3]()
        prompt = (text if text is not None else self.input).strip()
        if not prompt or self.running:
            return None
        if not self.ready:
            self.error = tr("Set up a model provider first.")
            provider_id, _ = _providers.split_model(self.thread.model or self.settings.model)
            return self.open_settings(provider_id)
        extra = self._mention_blocks() if text is None else []
        self.mentions = []
        self.menu = None
        self.input = ""
        self.error = ""
        self.view = "thread"
        self.running = True
        self.snapshot = []
        self.changed = False
        self.tool_status = {}
        model = self.thread.model or self.settings.model
        self.thread.model = model
        note = agent_tools.context_note(self.d)
        content = [{"type": "text", "text": prompt}, *extra,
                   {"type": "text", "text": f"<context>{note}</context>"}]
        tools = agent_tools.designer_tools(self.d)
        agent = _agents.Agent(model, tools=tools, system=agent_tools.SYSTEM, settings=self.settings,
                              confirm=self._confirm, executor=self._execute, messages=self.thread.messages,
                              stream=self._stream)
        self._agent = agent
        put = self._queue.put
        threading.Thread(target=agent.run, args=(content,), kwargs={"on_event": lambda e: put(("event", e))},
                         daemon=True, name="pyzed-agent").start()
        return _core.Command.scroll_to_end(SCROLL_ID)

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
        self.input = text
        return _core.Command.focus(INPUT_ID)

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
        """The + button: starts an @ mention at the end of the message."""
        self.input = self.input + ("" if not self.input or self.input.endswith(" ") else " ") + "@"
        self.picked = 0
        self.menu = None
        return _core.Command.focus(INPUT_ID)

    def move_pick(self, step: int) -> None:
        items = self.popup_items()
        if items:
            self.picked = (self.picked + step) % len(items)

    def popup_items(self) -> List[Tuple[str, str, str, Callable[[], Any]]]:
        """Rows of the @ / slash popup: (icon, label, detail, action)."""
        trig = self.trigger()
        if trig is None:
            return []
        kind, query = trig
        if kind == "slash":
            return [(icon, f"/{name}", tr(text), lambda name=name, prompt=prompt: self.run_command(name, prompt))
                    for name, icon, text, prompt in SLASH_COMMANDS if name.startswith(query)]
        rows = [(m.icon, m.label, detail, lambda m=m: self.add_mention(m))
                for m, detail in self.mention_candidates() if query in m.label.lower()]
        return rows[:40]

    def run_command(self, name: str, prompt: Optional[str]) -> Any:
        self.input = ""
        self.picked = 0
        if prompt is not None:
            return self.send(tr(prompt))
        if name == "new":
            return self.new_thread()
        if name == "history":
            self.view = "history"
            return None
        if name == "settings":
            return self.open_settings()
        if name == "form":
            return self.compose(tr("Create a new form for "))
        if name == "component":
            return self.compose(tr("Create a reusable component that "))
        return None

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
        for rel in self.project_files():
            out.append((Mention("file", rel, rel, "file"), tr("File")))
        return out

    def add_mention(self, mention: Mention) -> Any:
        """Replaces the @query being typed with ``@label`` and attaches what it names to the message."""
        self.input = _TRIGGER.sub(lambda m: m.group(0)[: m.group(0).index("@")] + f"@{mention.label} ", self.input)
        if not any((m.kind, m.key, m.label) == (mention.kind, mention.key, mention.label) for m in self.mentions):
            self.mentions.append(mention)
        self.picked = 0
        return _core.Command.focus(INPUT_ID)

    def remove_mention(self, index: int) -> None:
        if 0 <= index < len(self.mentions):
            m = self.mentions.pop(index)
            self.input = self.input.replace(f"@{m.label} ", "").replace(f"@{m.label}", "")

    def _mention_blocks(self) -> List[Dict[str, Any]]:
        """The text of every @ mention, as hidden context blocks of the message."""
        import json

        doc = self.d.doc
        blocks = []
        for m in self.mentions:
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
        others open their key page and the key is picked up as soon as it is copied."""
        provider = _providers.PROVIDERS[pid]
        self.provider_open = pid
        if provider.login == "oauth":

            def work() -> None:
                key = _agents.login.login(pid)
                if key:
                    _agents.set_key(pid, key)
                    self._queue.put(("models", pid, _agents.list_models(pid, self.settings, key=key)))

            self._background(pid, work, tr("Signed in to {provider}", provider=provider.name))
            return
        try:
            _agents.login.key_page(pid)
        except Exception as err:  # noqa: BLE001 - no browser
            self.d.notify(str(err), kind="error", seconds=6)
        self.capture = KeyCapture(pid, deadline=time.monotonic() + CAPTURE_SECONDS)

    def connect(self, pid: str) -> None:
        """Connects ``pid`` from the panel: signs in with the browser, or (local servers) asks for models."""
        provider = _providers.PROVIDERS[pid]
        self.menu = None
        self.open_settings(pid)
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
        if result is not None:
            content = result.get("content")
            text += "\n\n→ " + (content if isinstance(content, str) else json.dumps(content, ensure_ascii=False))
        body = _core.container(ui.label(text[:4000], size="xs", mono=True, color="text_muted", theme=t),
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


def _user_bubble(text: str, t: Theme) -> Any:
    return _core.container(ui.label(text, size="sm", theme=t), padding=(8, 10), width="fill", bg=t.element,
                           border_color=t.border_variant, border_width=1, radius=t.radius + 2)


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
            if texts:
                rows.append(_user_bubble("\n".join(texts), t))
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
    """Every provider with its models; one that is not set up offers to connect it."""
    current = c.thread.model or c.settings.model
    rows: List[Any] = []
    for pid, p in _providers.PROVIDERS.items():
        rows.append(_menu_header(p.name, t))
        if not _providers.is_ready(pid):
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
    return _menu_card(_core.column(rows, spacing=0, width="fill"), t, height=320)


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
    if trig is None:
        return None
    items = c.popup_items()
    title = tr("Commands") if trig[0] == "slash" else tr("Add context")
    if not items:
        body: List[Any] = [_menu_header(title, t), _core.container(
            ui.label(tr("No matches"), size="sm", color="text_muted", theme=t), padding=(4, 8))]
    else:
        picked = min(c.picked, len(items) - 1)
        body = [_menu_header(title + "  ·  " + tr("Enter to pick"), t)]
        body += [_menu_row(icon, label, detail, action, t, highlighted=i == picked)
                 for i, (icon, label, detail, action) in enumerate(items)]
    return _menu_card(_core.column(body, spacing=0, width="fill"), t, height=min(260, 34 + 40 * max(1, len(items))))


def _mentions_row(c: AgentController, t: Theme) -> Optional[Any]:
    if not c.mentions:
        return None
    chips = [_core.container(_core.row([
        _icon(m.icon, size=11, color=t.text_muted), ui.label(m.label, size="xs", theme=t),
        _core.button(_icon("x", size=10, color=t.text_placeholder), lambda i=i: c.remove_mention(i), padding=1,
                     bg=None, hover_bg=t.element_hover, radius=t.radius)], spacing=3, align="center"),
        padding=(1, 4), bg=t.element, border_color=t.border_variant, border_width=1, radius=t.radius)
        for i, m in enumerate(c.mentions)]
    return _core.row(chips, spacing=4, wrap=True)


def _composer(c: AgentController, t: Theme) -> Any:
    """The message box, like Zed's: the text, then the permission mode, model, effort and fast mode."""
    s = c.settings
    send = ui.icon_button("square", c.stop, size="sm", tooltip=tr("Stop"), theme=t) if c.running else \
        ui.icon_button("arrow-up", c.send, size="sm", variant="solid", tooltip=tr("Send (Enter)"),
                       disabled=not c.input.strip(), theme=t)
    field_ = _core.row([
        ui.input(c.input, c.set_input, placeholder=tr("Message the agent (@ context, / commands)"),
                 on_submit=c.send, id=INPUT_ID, borderless=True, theme=t),
        send,
    ], spacing=4, align="center")
    model = c.thread.model or s.model
    provider_id, name = _providers.split_model(model)
    claude = _providers.PROVIDERS[provider_id].protocol == "anthropic"
    mode_label, mode_icon, mode_text = MODE_TEXT[s.mode]
    controls = _core.row([
        ui.icon_button("plus", c.start_mention, size="sm", tooltip=tr("Add context (@)"), theme=t),
        _chip(tr(mode_label), lambda: c.toggle_menu("mode"), t, icon=mode_icon, selected=c.menu == "mode",
              tooltip=tr(mode_text)),
        _core.space(width="fill"),
        _chip(model_label(model), lambda: c.toggle_menu("model"), t, selected=c.menu == "model",
              tooltip=tr("Model")),
        _chip(tr(EFFORT_TEXT[s.effort]), lambda: c.toggle_menu("effort"), t, selected=c.menu == "effort",
              tooltip=tr("Effort"), disabled=not claude),
        _chip(tr("Fast"), c.toggle_fast, t, icon="zap", selected=s.fast and name in _providers.FAST_MODELS,
              menu=False, disabled=name not in _providers.FAST_MODELS,
              tooltip=tr("Fast mode: faster answers at a higher price (Claude Opus)")),
    ], spacing=2, align="center")
    return _core.container(_core.column([_mentions_row(c, t), field_, controls], spacing=6), padding=(6, 6, 4, 8),
                           width="fill", bg=t.editor, border_color=t.border, border_width=1, radius=t.radius + 2)


def _capture_callout(c: AgentController, t: Theme) -> Optional[Any]:
    """While signing in by copying a key: what to do, and Paste / Cancel."""
    cap = c.capture
    if cap is None:
        return None
    name = _providers.PROVIDERS[cap.provider].name
    detail = tr("Checking the key…") if cap.checking else tr(
        "Create a key on the page that opened and copy it: Pyzed picks it up, checks it and saves it in the system "
        "keychain.")
    lead = ui.spinner(size=14, theme=t) if cap.checking else _icon("key-round", size=14, color=t.text_accent)
    return _core.container(_core.column([
        _core.row([lead, ui.label(tr("Signing in to {provider}", provider=name), size="sm", weight="medium",
                                  theme=t)], spacing=8, align="center"),
        ui.label(detail, size="xs", color="text_muted", theme=t),
        _core.row([
            ui.button(tr("Paste key"), lambda: c.paste_key(cap.provider), icon="clipboard-paste", variant="tinted",
                      size="sm", theme=t),
            ui.button(tr("Open the page again"), lambda: c.open_key_page(cap.provider), variant="ghost", size="sm",
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
        rows.append(ui.callout(tr("The agent stopped"), c.error, tint="error", icon="triangle-alert", actions=[
            ui.button(tr("Retry"), c.retry, icon="refresh-cw", variant="ghost", size="sm", theme=t),
            ui.button(tr("Settings"), lambda: c.open_settings(), variant="ghost", size="sm", theme=t),
        ], theme=t))
    thread = _core.scrollable(_core.column(rows, spacing=10, width="fill", padding=(10, 12)), height="fill",
                              id=SCROLL_ID, anchor_bottom=True, scrollbar_width=4)
    bottom: List[Any] = []
    if c.capture is not None and d.dialog != "agent_settings":
        bottom.append(_capture_callout(c, t))
    if c.pending is not None:
        bottom.append(_confirmation(c, t))
    if c.snapshot and c.changed and not c.running:
        bottom.append(_review_bar(c, t))
    menus = {"mode": _mode_menu, "model": _model_menu, "effort": _effort_menu}
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
    "none needed": "No key needed",
}


def _provider_row(c: AgentController, pid: str, t: Theme) -> Any:
    p = _providers.PROVIDERS[pid]
    source = _providers.credential_source(pid)
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
    if p.needs_key or p.key_env:
        rows.append(ui.field(tr("API key"), _core.row([
            ui.input(c.key_buffer.get(pid, ""), lambda v: c.set_key_buffer(pid, v),
                     placeholder=_agents.secrets.mask(_providers.api_key(pid)) or tr("Paste a key"), secure=True,
                     on_submit=lambda: c.save_key(pid), mono=True, size="sm", width=220, theme=t),
            ui.button(tr("Save"), lambda: c.save_key(pid), variant="tinted", size="sm",
                      disabled=not c.key_buffer.get(pid), theme=t),
        ], spacing=4, align="center"), description=tr("Or set {env}", env=p.key_env) if p.key_env else None, theme=t))
    actions: List[Any] = []
    capturing = c.capture is not None and c.capture.provider == pid
    if p.login and not capturing:
        actions.append(ui.button(tr("Sign in with the browser"), lambda: c.sign_in(pid), icon="log-in",
                                 variant="solid" if not source or source == "none needed" else "ghost", size="sm",
                                 disabled=busy, theme=t))
    if p.key_url and not capturing:
        actions.append(ui.button(tr("Get a key"), lambda: c.open_key_page(pid), icon="external-link", variant="ghost",
                                 size="sm", theme=t))
    if source in ("keychain", "session", "ant"):
        actions.append(ui.button(tr("Sign out") if source == "ant" else tr("Remove key"), lambda: c.remove_key(pid),
                                 icon="trash-2", variant="ghost", size="sm", theme=t))
    actions.append(ui.button(tr("Refresh models"), lambda: c.refresh_models(pid), icon="refresh-cw", variant="ghost",
                             size="sm", disabled=busy or not source, theme=t))
    if busy:
        actions.append(ui.spinner(size=14, theme=t))
    rows.append(_core.row(actions, spacing=4, align="center", wrap=True))
    if capturing:
        rows.append(_capture_callout(c, t))
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
    providers = ui.settings_group(tr("Providers"), [_provider_row(c, pid, t) for pid in _providers.PROVIDERS], theme=t)
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
    body = _core.scrollable(_core.column([storage, providers, agent], spacing=14, padding=(0, 6, 0, 0)), height=560,
                            scrollbar_width=4)
    return ui.modal(body, title=tr("AI agents"), on_close=d.close_dialog, width=620, theme=t,
                    footer=[_core.space(width="fill"), ui.button(tr("Done"), d.close_dialog, variant="solid", theme=t)])
