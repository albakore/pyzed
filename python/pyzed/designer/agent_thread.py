"""How the Agent panel looks, drawn like Zed's: the toolbar, the thread, the activity bar and the message
editor.

The thread is read as entries (``agents.thread_entries``), the same for Pyzed's own agent and for
external agents, and each entry is drawn like Zed's thread view: the user's messages as cards that can
be edited and sent again, the agent's text, its reasoning folded under "Thinking", its tool calls as a
line (or a card for edits and commands) and, at the end of each turn, how long it took and how many
tokens it wrote. Above the message editor the activity bar gathers what needs attention: a call that
waits for an OK, the plan, the files the agent changed and the messages waiting their turn.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Callable, List, Optional

from .. import _core, ui
from ..agents import entries as _entries
from ..agents import providers as _providers
from ..icons import icon as _icon
from ..theme import Theme, alpha
from ..ui.agent import indented
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .agent_panel import AgentController

#: The thread's text size and the side margin of the agent's text and tool calls (Zed's px_5).
TEXT_SIZE = 13
SIDE = 20
#: Tool calls not drawn in the thread: the plan shows in the activity bar, like Zed's.
HIDDEN_TOOLS = ("update_plan",)
#: A turn shows its time once it took this long (Zed's stopwatch threshold).
STOPWATCH_SECONDS = 30


def duration(seconds: float) -> str:
    """``42`` -> ``"42s"``, ``95`` -> ``"1m 35s"``, ``3700`` -> ``"1h 1m"``."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    return f"{seconds // 3600}h {seconds % 3600 // 60}m"


# -- the toolbar -----------------------------------------------------------------------------------------

def toolbar(c: "AgentController", t: Theme) -> Any:
    """Zed's toolbar: the agent's icon and the thread's title (click to rename it), then New thread, full
    screen and the ⋯ menu. From the history or the settings, a back arrow and their name."""
    if c.view != "thread":
        lead = ui.icon_button("arrow-left", c.back, size="sm", tooltip=tr("Back to the thread"), theme=t)
        title: Any = ui.label(tr("History") if c.view == "history" else tr("Agent settings"), size="sm",
                              wrap=False, theme=t)
    else:
        lead = ui.tooltip(_core.container(_icon(c.agent_icon(), size=14, color=t.text_muted), padding=(0, 2)),
                          c.agent_label(), theme=t)
        if c.title_editing:
            title = _core.text_input(c.title_buffer, on_input=c.set_title_buffer, on_submit=c.save_title,
                                     id=TITLE_ID, size=13, padding=(2, 4), bg=t.editor, border_color=t.border_focused,
                                     focus_border_color=t.border_focused, radius=t.radius, color=t.text)
        elif c.thread.messages:
            title = _core.button(ui.label(c.thread.display_title, size="sm", color="text_muted", wrap=False, theme=t),
                                 c.start_rename, padding=(2, 4), width="fill", bg=None, hover_bg=t.element_hover,
                                 radius=t.radius)
            title = ui.tooltip(title, tr("Edit the thread's title"), theme=t)
        else:
            title = ui.label(tr("New {agent} Thread", agent=c.agent_label()), size="sm", color="text_muted",
                             wrap=False, theme=t)
    return _core.container(_core.row([
        lead,
        _core.container(title, width="fill", clip=True),
        ui.icon_button("plus", lambda: c.toggle_menu("new"), size="sm", selected=c.menu == "new",
                       tooltip=tr("New thread…"), theme=t),
        ui.icon_button("minimize-2" if c.expanded else "maximize-2", c.toggle_expand, size="sm",
                       selected=c.expanded, tooltip=tr("Disable full screen") if c.expanded else
                       tr("Enable full screen"), theme=t),
        ui.icon_button("ellipsis", lambda: c.toggle_menu("options"), size="sm", selected=c.menu == "options",
                       tooltip=tr("Agent menu"), theme=t),
    ], spacing=2, align="center"), padding=(0, 4, 0, 8), height=34, width="fill", bg=t.tab_bar, align_y="center")


TITLE_ID = "agent-title"


def new_menu(c: "AgentController", t: Theme) -> Any:
    """The + menu, like Zed's: Pyzed's own agent, the external agents, and Add more agents."""
    current = c.thread.model or c.settings.model
    items: List[Any] = [ui.MenuItem(tr("Pyzed Agent"), lambda: c.new_thread(""), icon="sparkles",
                                    checked=not current.startswith("acp:"))]
    agents = [a for a in c.settings.acp_agents if a.enabled]
    if agents:
        items += [ui.SEPARATOR, tr("External Agents")]
        for agent in sorted(agents, key=lambda a: a.label.lower()):
            items.append(ui.MenuItem(agent.label, lambda name=agent.name: c.new_thread(f"acp:{name}"),
                                     icon="terminal", checked=current == f"acp:{agent.name}"))
    items += [ui.SEPARATOR, ui.MenuItem(tr("Add more agents"), lambda: c.open_settings(section="agents"),
                                        icon="plus")]
    return ui.menu(items, width=240, theme=t)


def options_menu(c: "AgentController", t: Theme) -> Any:
    """The ⋯ menu, like Zed's: the current thread, MCP servers, context (skills and rules), the settings,
    the history and, for an external agent, signing in again and reloading it."""
    items: List[Any] = []
    if c.thread.messages:
        items += [tr("Current Thread"),
                  ui.MenuItem(tr("Rename Thread"), c.start_rename, icon="pencil"),
                  ui.MenuItem(tr("Copy Thread as Markdown"), c.copy_markdown, icon="copy"),
                  ui.MenuItem(tr("Open Thread as Markdown"), c.open_markdown, icon="file-text"),
                  ui.SEPARATOR]
    items += [tr("MCP Servers"),
              ui.MenuItem(tr("Add Server…"), lambda: c.open_settings(section="mcp"), icon="plug"),
              ui.SEPARATOR, tr("Context"),
              ui.MenuItem(tr("Skills"), lambda: c.open_settings(section="skills"), icon="book-open"),
              ui.MenuItem(tr("Open Project Rules") if c.project_rules() is not None else tr("Create Project Rules"),
                          c.open_rules, icon="scroll-text", description="AGENTS.md"),
              ui.SEPARATOR,
              ui.MenuItem(tr("Settings"), lambda: c.open_settings(), icon="settings-2"),
              ui.MenuItem(tr("Thread History"), c.toggle_history, icon="history"),
              ui.MenuItem(tr("Show Thinking"), lambda: c.toggle_option("show_thinking"),
                          checked=c.settings.show_thinking)]
    if c.is_external:
        items += [ui.SEPARATOR, ui.MenuItem(tr("Reauthenticate"), c.reauthenticate, icon="log-in"),
                  ui.MenuItem(tr("Reload Agent"), c.reload_agent, icon="refresh-cw", disabled=c.running)]
    return ui.menu(items, width=250, theme=t)


# -- the thread ------------------------------------------------------------------------------------------

def _user_message(c: "AgentController", entry: _entries.UserMessage, t: Theme) -> Any:
    """A message of the user as Zed draws it: a card in the editor's color that can be clicked to edit it
    (Enter sends it again from that point), with Restore checkpoint above it when the agent changed
    something after it."""
    from .agent_panel import SELECTION, _image_bytes

    editing = c.editing == entry.index
    editable = c.can_edit
    pictures = [_core.image(data, height=72, content_fit="contain", radius=4)
                for data in (_image_bytes(b) for b in entry.images) if data]
    if editing:
        body: Any = ui.editor(EDIT_ID, c.edit_text, on_change=c.set_edit_text, wrap=True, gutter=False,
                              active_line=False, folding=False, auto_close=False, match_brackets=False,
                              selection_highlight=False, font="sans", font_size=TEXT_SIZE, line_height=20,
                              height=box_height(c.edit_text), capture_keys=["enter", "escape"], theme=t)
        card = _core.container(_core.column([body, _core.row(pictures, spacing=6, wrap=True) if pictures else None],
                                            spacing=6), padding=(10, 8), width="fill", bg=t.editor,
                               border_color=t.border_focused, border_width=1, radius=t.radius + 2)
        actions = _core.container(_core.row([
            ui.icon_button("x", c.cancel_edit, size="xs", color="error", tooltip=tr("Cancel editing"), theme=t),
            ui.icon_button("corner-down-left", c.submit_edit, size="xs",
                           tooltip=tr("Editing will restart the thread from this point."), theme=t),
        ], spacing=0), bg=t.editor, border_color=t.border, border_width=1, radius=t.radius)
        card = _core.stack([_core.container(card, padding=(10, 0, 0, 0), width="fill"),
                            _core.container(actions, width="fill", align_x="end", padding=(0, 12, 0, 0))],
                           width="fill")
    else:
        body = _core.column([
            ui.label(entry.text, size=TEXT_SIZE, selectable=SELECTION, theme=t) if entry.text else None,
            _core.row(pictures, spacing=6, wrap=True) if pictures else None,
        ], spacing=6, width="fill")
        card = _core.button(body, (lambda: c.start_edit(entry.index)) if editable and not c.running else None,
                            padding=(10, 8), width="fill", bg=t.editor, hover_bg=t.editor,
                            border_color=t.border, hover_border_color=alpha(t.border_focused, 0.8),
                            border_width=1, radius=t.radius + 2, shadow=(t.shadow, (0, 1), 3),
                            disabled_color=t.text)
        if not editable:
            card = ui.tooltip(card, tr("Editing previous messages is not available for {agent} yet.",
                                       agent=c.agent_label()), theme=t)
    rows: List[Any] = []
    if c.has_checkpoint(entry.index) and not c.running:
        rows.append(_core.row([
            _core.rule(thickness=1, color=t.border),
            ui.tooltip(ui.button(tr("Restore Checkpoint"), lambda: c.restore_checkpoint(entry.index), icon="undo-2",
                                 icon_color="text_muted", variant="ghost", size="xs", color=t.text_muted, theme=t),
                       tr("Restores the documents to what they were at this point of the conversation."), theme=t),
            _core.rule(thickness=1, color=t.border),
        ], spacing=8, align="center", padding=(0, 12)))
    rows.append(card)
    return _core.column(rows, spacing=6, width="fill", padding=(8, 8, 12, 8))


EDIT_ID = "agent-edit-message"


def thinking(c: "AgentController", key: str, text: str, t: Theme, live: bool = False) -> Any:
    """Zed's thinking block: "Thinking" with its icon, unfolding (while it streams, open) to the reasoning
    hanging from a thin line."""
    from .agent_panel import SELECTION

    opened = key in c.open_blocks or (live and key not in c.closed_blocks)
    head = _core.button(_core.row([
        _icon("brain", size=13, color=t.text_muted),
        ui.label(tr("Thinking"), size="sm", color="text_muted", theme=t),
        _core.space(width="fill"),
        _icon("chevron-up" if opened else "chevron-down", size=12, color=t.text_placeholder),
    ], spacing=6, align="center"), lambda: c.toggle_block(key, live), padding=(3, 4), width="fill", bg=None,
        hover_bg=t.element_hover, radius=t.radius)
    if not opened or not text.strip():
        return head
    body = ui.label(text.strip(), size=12, color="text_muted", selectable=SELECTION, theme=t)
    if not live and key not in c.open_blocks:
        body = _core.container(body, max_height=256, clip=True)
    return _core.column([head, indented(body, theme=t)], spacing=4, width="fill")


def _assistant(c: "AgentController", entry: _entries.AssistantMessage, t: Theme) -> Any:
    from .agent_panel import SELECTION

    rows: List[Any] = []
    for n, (kind, text) in enumerate(entry.chunks):
        if kind == "message":
            rows.append(ui.markdown(text, size=TEXT_SIZE, selectable=SELECTION, theme=t))
        elif c.settings.show_thinking:
            rows.append(thinking(c, f"think:{entry.index}:{n}", text, t))
    return _core.column(rows, spacing=12, width="fill", padding=(6, SIDE))


def _tool_call(c: "AgentController", entry: _entries.ToolCall, t: Theme) -> Any:
    from .agent_panel import _call_detail, _image_bytes, _kind_of, _tool_title

    tools = c.tool_index()
    block = {"input": entry.input, "locations": entry.locations}
    return _core.container(ui.ToolCall(
        title=_tool_title(entry.name, tools), detail=_call_detail(c, block),
        kind=entry.kind or _kind_of(entry.name, tools.get(entry.name)), status=entry.status,
        input=entry.input or None, output=entry.output or None,
        images=[data for data in (_image_bytes(b) for b in entry.images) if data], diffs=entry.diffs,
        progress=entry.progress, theme=t, key=f"tool:{entry.id}",
        on_allow=lambda _e: c.answer(True), on_allow_always=lambda _e: c.answer(True, True),
        on_deny=lambda _e: c.answer(False)), padding=(2, SIDE), width="fill")


def turn_controls(c: "AgentController", entry: Optional[_entries.AssistantMessage], last: bool, t: Theme) -> Any:
    """Under the end of a turn, like Zed: how long it took and the tokens the agent wrote, then copy the
    answer and go to the top of the thread."""
    stats = entry.stats if entry is not None else {}
    seconds, tokens = float(stats.get("seconds") or 0), int(stats.get("tokens") or 0)
    left: List[Any] = []
    if seconds >= STOPWATCH_SECONDS or (last and seconds >= 1):
        left.append(ui.label(duration(seconds), size="xs", color="text_muted", theme=t))
        if tokens:
            left += [ui.label("•", size="xs", color="text_disabled", theme=t),
                     ui.label(tr("{tokens} tokens", tokens=ui.format_tokens(tokens)), size="xs", color="text_muted",
                              theme=t)]
    text = entry.text if entry is not None else ""
    return _core.row([
        *left,
        _core.space(width="fill"),
        ui.icon_button("copy", lambda: c.copy_text(text), size="xs", tooltip=tr("Copy This Agent Response"),
                       disabled=not text, theme=t),
        ui.icon_button("arrow-up", c.scroll_to_top, size="xs", tooltip=tr("Scroll to Top"), theme=t)
        if last else None,
    ], spacing=4, align="center", padding=(0, SIDE - 4, 6, SIDE))


def generating(c: "AgentController", t: Theme) -> Any:
    """What shows under the thread while the agent works, like Zed: a spinner (or "Awaiting Confirmation"),
    and once it takes a while, the time and the tokens written so far."""
    elapsed = time.monotonic() - c.started if c.started else 0.0
    parts: List[Any] = [ui.spinner(size=12, theme=t)]
    if c.pending is not None:
        parts.append(ui.label(tr("Awaiting Confirmation"), size="sm", color="text_muted", theme=t))
    if elapsed >= STOPWATCH_SECONDS:
        parts.append(ui.label(duration(elapsed), size="sm", color="text_muted", theme=t))
        if c.turn_tokens:
            parts.append(_core.row([_icon("arrow-up" if c.pending is not None else "arrow-down", size=11,
                                          color=t.text_muted),
                                    ui.label(tr("{tokens} tokens", tokens=ui.format_tokens(c.turn_tokens)),
                                             size="sm", color="text_muted", theme=t)], spacing=2, align="center"))
    return _core.row(parts, spacing=8, align="center", padding=(8, 22))


def thread_rows(c: "AgentController", t: Theme) -> List[Any]:
    """The thread's entries drawn one by one, then what is streaming now and the spinner."""
    messages = list(c.thread.messages)
    live = c.live_blocks()
    if live is not None and (live[0] or live[1]):
        messages.append({"role": "assistant", "content": live[0]})
        messages.append({"role": "user", "content": live[1]})
    waiting = c.waiting_calls()
    entries = [e for e in _entries.thread_entries(messages, statuses=c.tool_status, running=c.running,
                                                  waiting=waiting)
               if not (isinstance(e, _entries.ToolCall) and e.name in HIDDEN_TOOLS)]
    rows: List[Any] = []
    last_answer: Optional[_entries.AssistantMessage] = None
    for i, entry in enumerate(entries):
        if isinstance(entry, _entries.UserMessage):
            rows.append(_user_message(c, entry, t))
            last_answer = None
            continue
        if isinstance(entry, _entries.AssistantMessage):
            rows.append(_assistant(c, entry, t))
            last_answer = entry
        else:
            rows.append(_tool_call(c, entry, t))
        if _entries.turn_end(entries, i, running=c.running):
            rows.append(turn_controls(c, last_answer, i + 1 == len(entries), t))
    if c.editing is not None:  # what follows the message being edited is dimmed, like Zed's backdrop
        cut = next((n for n, e in enumerate(entries) if isinstance(e, _entries.UserMessage)
                    and e.index == c.editing), None)
        if cut is not None:
            index = _row_of(entries, cut)
            rows = rows[:index + 1] + [_dimmed(r, t) for r in rows[index + 1:]]
    if c.running:
        if c.live_thinking and c.settings.show_thinking and live is None:
            rows.append(_core.container(thinking(c, "think:live", c.live_thinking, t, live=True), padding=(6, SIDE),
                                        width="fill"))
        if c.live_text and live is None:  # an external agent's text is already in its live blocks
            from .agent_panel import SELECTION

            rows.append(_core.container(ui.markdown(c.live_text, size=TEXT_SIZE, selectable=SELECTION, theme=t),
                                        padding=(6, SIDE), width="fill"))
        if c.live_tool:
            from .agent_panel import _kind_of, _tool_title

            tools = c.tool_index()
            rows.append(_core.container(ui.ToolCall(title=_tool_title(c.live_tool, tools), status="pending",
                                                    kind=_kind_of(c.live_tool, tools.get(c.live_tool)), theme=t,
                                                    key="tool:live"), padding=(2, SIDE), width="fill"))
        rows.append(generating(c, t))
    return rows


def _row_of(entries: List[Any], index: int) -> int:
    """The row of ``entries[index]`` among the drawn rows (turn controls add rows of their own)."""
    rows = 0
    for i in range(index):
        rows += 1
        if not isinstance(entries[i], _entries.UserMessage) and _entries.turn_end(entries, i):
            rows += 1
    return rows


def _dimmed(row: Any, t: Theme) -> Any:
    shade = _core.container(None, width="fill", height="fill", bg=alpha(t.panel, 0.75))
    return _core.stack([row, _core.opaque(shade)], width="fill")


# -- the activity bar ------------------------------------------------------------------------------------

def _summary(c: "AgentController", flag: str, opened: bool, content: List[Any], t: Theme,
             end: Optional[List[Any]] = None) -> Any:
    """A row of the activity bar: a disclosure that unfolds it, what it is about, and its buttons."""
    head = _core.button(_core.row([
        _icon("chevron-down" if opened else "chevron-right", size=12, color=t.text_muted),
        *content,
    ], spacing=6, align="center"), lambda: c.toggle_flag(flag), padding=(2, 4), width="fill", bg=None,
        hover_bg=t.element_hover, radius=t.radius)
    return _core.row([_core.container(head, width="fill"), *(end or [])], spacing=2, align="center", padding=4)


def _plan(c: "AgentController", t: Theme) -> Optional[Any]:
    from . import agent_tools

    steps = c.live_plan if c.running and c.live_plan else agent_tools.plan_of(c.thread.messages)
    if not steps:
        return None
    done = sum(1 for s in steps if s["status"] == "done")
    if done == len(steps) and not c.running:
        return None
    current = next((s for s in steps if s["status"] == "in_progress"), None)
    left = len(steps) - done
    if current is not None and not c.plan_expanded:
        content = [ui.label(tr("Current:"), size="sm", color="text_muted", theme=t),
                   _core.container(ui.label(current["step"], size="sm", color="text_muted", wrap=False, theme=t),
                                   width="fill", clip=True),
                   ui.label(tr("{count} left", count=left), size="sm", color="text_muted", theme=t)]
    else:
        content = [ui.label(tr("Plan"), size="sm", color="text_muted", theme=t), _core.space(width="fill"),
                   ui.label(tr("{done}/{total} completed", done=done, total=len(steps)) if done else
                            tr("{count} steps", count=len(steps)), size="sm", color="text_muted", theme=t)]
    rows: List[Any] = [_summary(c, "plan_expanded", c.plan_expanded, content, t)]
    if c.plan_expanded:
        items = []
        for n, s in enumerate(steps):
            status = s["status"]
            lead = ui.spinner(size=12, theme=t) if status == "in_progress" and c.running else _icon(
                "circle-check" if status == "done" else "circle-dot" if status == "in_progress" else "circle",
                size=13, color=t.success if status == "done" else t.text_accent if status == "in_progress"
                else t.text_placeholder)
            items.append(_core.container(_core.row([lead, ui.label(s["step"], size="xs", wrap=False, theme=t,
                                                                   color="text_muted")], spacing=8, align="center"),
                                         padding=(5, 10), width="fill", bg=t.editor))
            if n + 1 < len(steps):
                items.append(_core.rule(thickness=1, color=t.border_variant))
        rows += [_core.rule(thickness=1, color=t.border_variant),
                 _core.scrollable(_core.column(items, spacing=0, width="fill"), height=min(160, 27 * len(steps)),
                                  scrollbar_width=3)]
    return _core.column(rows, spacing=0, width="fill")


def _edits(c: "AgentController", t: Theme) -> Optional[Any]:
    if not (c.snapshot and c.changed) or c.running:
        return None
    files = c.file_changes()
    added, removed = sum(f["added"] for f in files), sum(f["removed"] for f in files)
    dot = ui.label("•", size="xs", color="text_disabled", theme=t)
    content = [ui.label(tr("Edits"), size="sm", color="text_muted", theme=t), dot,
               ui.label(tr("{count} files", count=len(files)) if len(files) != 1 else tr("1 file"), size="sm",
                        color="text_muted", theme=t)]
    if added or removed:
        content += [dot, ui.label(f"+{added}", size="sm", color="success", mono=True, theme=t),
                    ui.label(f"-{removed}", size="sm", color="error", mono=True, theme=t)]
    end = [ui.icon_button("list-todo", c.review_changes, size="sm", tooltip=tr("Review Changes"), theme=t),
           _core.container(_core.rule(vertical=True, thickness=1, color=t.border_variant), height=14),
           ui.button(tr("Reject All"), c.reject, variant="ghost", size="sm", theme=t),
           ui.button(tr("Keep All"), c.keep, variant="ghost", size="sm", theme=t)]
    rows: List[Any] = [_summary(c, "edits_expanded", c.edits_expanded, content, t, end)]
    if c.edits_expanded:
        items = []
        for n, f in enumerate(files):
            path = f["path"]
            name, _, folder = path.replace("\\", "/").rpartition("/")[::-1]
            items.append(_core.container(_core.row([
                _core.button(_core.row([
                    _icon("file", size=12, color=t.text_muted),
                    ui.label(name or path, size="xs", wrap=False, theme=t),
                    ui.label(folder, size="xs", color="text_placeholder", wrap=False, theme=t) if folder else None,
                    ui.diff_stat(f["added"], f["removed"], blocks=3, theme=t) if f["added"] or f["removed"] else None,
                ], spacing=6, align="center"), lambda p=path: c.open_file(p), padding=(2, 4), bg=None,
                    hover_bg=t.element_hover, radius=t.radius),
                _core.space(width="fill"),
                ui.button(tr("Reject"), lambda p=path: c.reject_file(p), icon="undo-2", variant="ghost", size="xs",
                          theme=t),
                ui.button(tr("Keep"), lambda p=path: c.keep_file(p), icon="check", variant="ghost", size="xs",
                          theme=t),
            ], spacing=2, align="center"), padding=(2, 6), width="fill", bg=t.editor))
            if n + 1 < len(files):
                items.append(_core.rule(thickness=1, color=t.border_variant))
        rows += [_core.rule(thickness=1, color=t.border_variant), _core.column(items, spacing=0, width="fill")]
    return _core.column(rows, spacing=0, width="fill")


def _queue(c: "AgentController", t: Theme) -> Optional[Any]:
    if not c.queued:
        return None
    count = len(c.queued)
    content = [ui.label(tr("{count} Queued Messages", count=count) if count != 1 else tr("1 Queued Message"),
                        size="sm", color="text_muted", theme=t)]
    end = [ui.button(tr("Send Now"), c.send_queued_now, variant="ghost", size="sm", theme=t,
                     tooltip=tr("Stop the agent and send the next message now")),
           ui.button(tr("Clear All"), c.clear_queue, variant="ghost", size="sm", theme=t)]
    rows: List[Any] = [_summary(c, "queue_expanded", c.queue_expanded, content, t, end)]
    if c.queue_expanded:
        items = []
        for n, q in enumerate(c.queued):
            items.append(_core.container(_core.row([
                _icon("circle-dashed" if n else "corner-down-right", size=12, color=t.text_muted),
                _core.container(ui.label(q.text.splitlines()[0] if q.text else tr("Images"), size="xs",
                                         wrap=False, theme=t), width="fill", clip=True),
                ui.icon_button("pencil", lambda n=n: c.edit_queued(n), size="xs", tooltip=tr("Edit"), theme=t),
                ui.icon_button("trash-2", lambda n=n: c.remove_queued(n), size="xs", tooltip=tr("Remove"), theme=t),
            ], spacing=6, align="center"), padding=(2, 8), width="fill", bg=t.editor))
        rows += [_core.rule(thickness=1, color=t.border_variant), _core.column(items, spacing=0, width="fill")]
    return _core.column(rows, spacing=0, width="fill")


def _awaiting(c: "AgentController", t: Theme) -> Optional[Any]:
    """A call waiting for an OK that is not on screen as a card (an external agent's question, or one asked
    before its call shows): asked here, like Zed's floating "Awaiting Confirmation"."""
    from .agent_panel import _args_preview, _pending_on_card, _tool_title

    p = c.pending
    if p is None or _pending_on_card(c):
        return None
    preview = _args_preview(p.args)
    head = _core.row([ui.spinner(size=12, theme=t), ui.label(tr("Awaiting Confirmation"), size="sm",
                                                             color="text_muted", theme=t)],
                     spacing=8, align="center", padding=(6, 8))
    card = ui.ToolCall(title=_tool_title(p.tool.name, {p.tool.name: p.tool}), detail=preview, status="waiting",
                       kind="edit" if getattr(p.tool, "writes", False) else "", theme=t, key="agent-awaiting",
                       on_allow=lambda _e: c.answer(True), on_allow_always=lambda _e: c.answer(True, True),
                       on_deny=lambda _e: c.answer(False))
    return _core.column([head, _core.rule(thickness=1, color=t.border_variant),
                         _core.container(card, padding=6, width="fill")], spacing=0, width="fill")


def activity_bar(c: "AgentController", t: Theme) -> Optional[Any]:
    """Zed's activity bar, attached to the top of the message editor: the call waiting for an OK, the plan,
    the edits to keep or reject and the queued messages, one under the other."""
    parts = [p for p in (_awaiting(c, t), _plan(c, t), _edits(c, t), _queue(c, t)) if p is not None]
    if not parts:
        return None
    rows: List[Any] = []
    for n, part in enumerate(parts):
        if n:
            rows.append(_core.rule(thickness=1, color=t.border))
        rows.append(part)
    card = _core.container(_core.column(rows, spacing=0, width="fill"), width="fill", bg=t.surface,
                           border_color=t.border, border_width=1, radius=(t.radius + 2, t.radius + 2, 0, 0),
                           clip=True, shadow=(t.shadow, (1, -1), 2))
    return _core.container(card, padding=(0, 8), width="fill")


# -- the message editor ----------------------------------------------------------------------------------

#: Lines the message editor grows to before it scrolls.
BOX_LINES = 10


def box_height(text: str, chars: int = 52, line: float = 20.0, lines_max: int = BOX_LINES) -> float:
    """The message editor's height for ``text``: one line per wrapped line, up to ``lines_max``."""
    lines = sum(max(1, -(-len(part) // chars)) for part in text.split("\n")) if text else 1
    return min(max(lines, 1), lines_max) * line + 10


def _toggle(icon: str, on: bool, on_press: Callable[[], Any], tip: str, t: Theme, *, off_icon: str = "",
            disabled: bool = False) -> Any:
    """An icon toggle of the editor's bottom row (accent while on, like Zed's)."""
    return ui.icon_button(icon if on or not off_icon else off_icon, None if disabled else on_press, size="sm",
                          color="accent" if on else None, tooltip=tip, theme=t)


def selector(label: str, on_press: Any, t: Theme, *, icon: Optional[str] = None, opened: bool = False,
             tooltip: Optional[str] = None, disabled: bool = False) -> Any:
    """A picker of the editor's bottom row (profile, mode, model, effort): its value and a chevron."""
    color = t.text_disabled if disabled else t.text_muted
    parts = [_icon(icon, size=13, color=color) if icon else None,
             ui.label(label, size="sm", color="text_disabled" if disabled else "text_muted", wrap=False, theme=t),
             _icon("chevron-up" if opened else "chevron-down", size=11, color=t.text_placeholder)]
    widget = _core.button(_core.row(parts, spacing=4, align="center"), None if disabled else on_press,
                          padding=(3, 6), bg=t.element_selected if opened else None, hover_bg=t.element_hover,
                          radius=t.radius)
    return ui.tooltip(widget, tooltip, theme=t) if tooltip else widget


def message_editor(c: "AgentController", t: Theme, *, fill: bool = False) -> Any:
    """Zed's message editor: the text across the panel (Enter sends, Shift+Enter breaks the line), the
    expand button, then the bottom row: add context, follow the agent, fast mode and thinking on the left;
    tokens used, profile, model and Send (Stop while it works) on the right. An external agent shows its
    own options (its modes, models…) in place of the profile and the model."""
    from .agent_panel import INPUT_ID, MODE_TEXT, _mentions_row, model_label

    s = c.settings
    lines = 26 if c.editor_expanded else BOX_LINES
    box = ui.editor(INPUT_ID, c.input, on_change=c.set_input, on_cursor=c.focus_box, wrap=True, gutter=False,
                    active_line=False, folding=False, auto_close=False, match_brackets=False,
                    selection_highlight=False, font="sans", font_size=TEXT_SIZE, line_height=20,
                    height="fill" if fill else box_height(c.input, lines_max=lines), capture_keys=c.captured_keys(),
                    placeholder=c.placeholder(), theme=t)
    has_messages = bool(c.thread.messages)
    expand = ui.icon_button("minimize-2" if c.editor_expanded else "maximize-2", c.toggle_editor_expanded,
                            size="xs", tooltip=tr("Minimize Message Editor") if c.editor_expanded else
                            tr("Expand Message Editor"), theme=t) if has_messages else None
    text = _core.row([_core.container(box, width="fill", height="fill" if fill else None), expand], spacing=2,
                     height="fill" if fill else None)
    model = c.thread.model or s.model
    provider_id, name = _providers.split_model(model)
    external = provider_id == "acp"
    agent = s.acp_agent(name) if external else None
    claude = _providers.PROVIDERS[provider_id].protocol == "anthropic"
    left: List[Any] = [
        ui.icon_button("plus", c.toggle_add_menu, size="sm", selected=c.menu == "add", tooltip=tr("Add Context"),
                       theme=t),
        _toggle("crosshair", s.follow_agent, c.toggle_follow,
                tr("Stop Following the Agent") if s.follow_agent else tr("Follow the Agent"), t),
    ]
    right: List[Any] = []
    if not external:
        fast_ok = name in _providers.FAST_MODELS
        if fast_ok:
            left.append(_toggle("fast-forward", s.fast, c.toggle_fast,
                                tr("Disable Fast Mode") if s.fast else tr("Enable Fast Mode"), t))
        if claude:
            left.append(_toggle("brain", s.thinking, c.toggle_thinking,
                                tr("Disable Thinking Mode") if s.thinking else tr("Enable Thinking Mode"), t))
            if s.thinking:
                from .agent_panel import EFFORT_TEXT

                left.append(selector(tr(EFFORT_TEXT[s.effort]), lambda: c.toggle_menu("effort"), t,
                                     opened=c.menu == "effort", tooltip=tr("Change Thinking Effort")))
        if c.thread.context and c.context_window:
            right.append(ui.context_meter(c.thread.context, c.context_window, theme=t))
        profile = PROFILE_TEXT[s.profile]
        right.append(selector(tr(profile[0]), lambda: c.toggle_menu("mode"), t, icon=profile[1],
                              opened=c.menu == "mode", tooltip=tr(MODE_TEXT[s.mode][2])))
        right.append(selector(model_label(model), lambda: c.toggle_menu("model"), t, opened=c.menu == "model",
                              tooltip=tr("Change Model")))
    else:
        from .agent_panel import _option_chip

        options = c.agent_options()
        if options:
            right += [_option_chip(c, o, t) for o in options]
        else:
            right.append(selector(agent.label if agent else name, lambda: c.toggle_menu("model"), t,
                                  icon="terminal", opened=c.menu == "model", tooltip=tr("Change Agent")))
    if c.running and not c.input.strip():
        send = ui.icon_button("square", c.stop, size="sm", tint="error", tooltip=tr("Stop Generation"),
                              theme=t)
    elif c.running:
        send = ui.icon_button("list-plus", c.send, size="sm", variant="solid",
                              tooltip=tr("Queue and Send (Enter)"), theme=t)
    else:
        send = ui.icon_button("arrow-up", c.send, size="sm", variant="solid", tooltip=tr("Send Message"),
                              keys="enter", disabled=not (c.input.strip() or c.attachments), theme=t)
    bottom = _core.row([_core.row(left, spacing=2, align="center", wrap=True), _core.space(width="fill"),
                        _core.row([*right, send], spacing=2, align="center", wrap=True)],
                       spacing=4, align="center")
    column = _core.column([_mentions_row(c, t), text, bottom], spacing=8, width="fill",
                          height="fill" if fill else None)
    return _core.container(column, padding=(8, 8, 8, 10), width="fill", height="fill" if fill else None,
                           bg=t.editor)


#: Zed's profiles: profile -> (label, icon).
PROFILE_TEXT = {"write": ("Write", "pencil"), "ask": ("Ask", "message-circle-question"),
                "minimal": ("Minimal", "circle-dashed")}


def profile_menu(c: "AgentController", t: Theme) -> Any:
    """The profile picker, like Zed's: Write, Ask or Minimal, then whether writing asks first."""
    descriptions = {"write": "Edits forms, code and files", "ask": "Reads only, changes nothing",
                    "minimal": "No tools, just chat"}
    items: List[Any] = [tr("Profiles")]
    for key, (label, icon) in PROFILE_TEXT.items():
        items.append(ui.MenuItem(tr(label), lambda key=key: c.set_profile_key(key), icon=icon,
                                 checked=c.settings.profile == key, description=tr(descriptions[key])))
    items += [ui.SEPARATOR,
              ui.MenuItem(tr("Ask before writing files"), c.toggle_confirm_writes,
                          checked=c.settings.confirm_writes, disabled=c.settings.profile != "write"),
              ui.MenuItem(tr("Configure profiles…"), lambda: c.open_settings(section="permissions"),
                          icon="settings-2")]
    return ui.menu(items, width=280, theme=t)


# -- the panel ------------------------------------------------------------------------------------------

def thread_view(c: "AgentController", t: Theme) -> Any:
    """The thread with its activity bar and message editor; an empty thread is all message editor, like
    Zed's (with the providers to connect first when none is set up)."""
    from .agent_panel import SCROLL_ID, _auth_card, _capture_callout, _claude_login_callout, _device_callout, \
        _empty, _popup

    above: List[Any] = []  # sign-ins and notices, over the activity bar
    if c.capture is not None:
        above.append(_capture_callout(c, t))
    if c.claude_login is not None:
        above.append(_claude_login_callout(c, t))
    if c.agent_auth is not None:
        above.append(_auth_card(c, t))
    if c.mcp_added:
        above.append(ui.callout(tr("Restart your agents to use Pyzed's MCP"), tr(
            "Pyzed's MCP server was added to {names}. Close and open them again (agents running in Pyzed restart "
            "with the button).", names=", ".join(c.mcp_added)), tint="info", icon="plug", actions=[
            ui.button(tr("Restart agents"), c.restart_agents, icon="refresh-cw", variant="tinted", size="sm",
                      theme=t),
            ui.button(tr("Later"), c.dismiss_mcp_added, variant="ghost", size="sm", theme=t)], theme=t))
    if c.device is not None:
        above.append(_device_callout(c, t))
    error = _error(c, t)
    empty = not c.thread.messages and not c.running
    if empty and c.ready and not above and error is None:
        editor = message_editor(c, t, fill=True)
        return _with_menu(c, t, editor, popup=_popup(c, t), bottom_gap=40)  # above the bottom row
    rows = thread_rows(c, t) if c.thread.messages or c.running else [_empty(c, t)]
    if error is not None:
        rows.append(_core.container(error, padding=(4, 12), width="fill"))
    thread = _core.scrollable(_core.column(rows, spacing=0, width="fill", padding=(4, 0, 12, 0)), height="fill",
                              id=SCROLL_ID, anchor_bottom=True, scrollbar_width=4)
    popup = _popup(c, t)
    thread = _with_menu(c, t, thread, popup=popup)
    bottom = [_core.container(_core.column(above, spacing=6, width="fill"), padding=(6, 8), width="fill")
              if above else None, activity_bar(c, t),
              _core.rule(thickness=1, color=t.border) if activity_bar(c, t) is None else None,
              message_editor(c, t)]
    return _core.column([thread, *bottom], width="fill", height="fill")


def _with_menu(c: "AgentController", t: Theme, base: Any, *, popup: Any = None, bottom_gap: float = 0) -> Any:
    """``base`` with the open picker of the message editor floating over its bottom, like Zed's popovers
    (the @ / slash list too); ``bottom_gap`` keeps that much of the bottom uncovered."""
    from .agent_panel import _add_menu, _effort_menu, _model_menu, _option_menu

    menus = {"mode": profile_menu, "model": _model_menu, "effort": _effort_menu, "add": _add_menu}
    content = None
    align = "end"
    if c.menu in menus:
        content = menus[c.menu](c, t)
        align = "start" if c.menu in ("add", "effort") else "end"
    elif c.menu and c.menu.startswith("option:"):
        content = _option_menu(c, t, c.menu[len("option:"):])
    elif popup is not None:
        content, align = popup, "start"
    if content is None:
        return base
    width = 320 if c.menu != "add" else 300
    placed = _core.container(_core.opaque(_core.container(content, max_width=width)), width="fill", height="fill",
                             align_x=align, align_y="end", padding=(8, 8, 6 + bottom_gap, 8))
    shade = _core.mouse_area(_core.container(None, width="fill", height="fill"), on_press=c.close_menu)
    return _core.stack([base, shade, placed], width="fill", height="fill")


def _error(c: "AgentController", t: Theme) -> Optional[Any]:
    from .agent_panel import NODE_URL
    from .. import agents as _agents

    if not c.error or c.running:
        return None
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
    return ui.callout(tr("The agent stopped"), c.error, tint="error", icon="triangle-alert", actions=actions, theme=t)


def panel(c: "AgentController", t: Theme) -> Any:
    """The Agent panel: the toolbar, then the thread, the history or the agent settings."""
    from .agent_panel import _history, settings_view

    bar = _core.column([toolbar(c, t), _core.rule(thickness=1, color=t.border)], spacing=0, width="fill")
    if c.view == "history":
        body = _core.column([bar, _history(c, t)], width="fill", height="fill")
    elif c.view == "settings":
        body = _core.column([bar, settings_view(c.d, t)], width="fill", height="fill")
    else:
        body = _core.column([bar, thread_view(c, t)], width="fill", height="fill")
    menus = {"new": new_menu, "options": options_menu}
    if c.menu in menus:
        body = ui.popover(body, menus[c.menu](c, t), x=6, y=34, align_x="end", on_dismiss=c.close_menu)
    body = _core.container(body, width="fill", height="fill", bg=t.panel)
    if c.expanded:  # a readable column in the middle of the window, like Zed's zoomed panel
        body = _core.container(_core.container(body, max_width=860, width="fill", height="fill"), width="fill",
                               height="fill", align_x="center", bg=t.panel)
    return body
