"""The Agent panel's thread works like Zed's: one model of entries for every agent, reasoning kept from external
agents, messages that queue while the agent works, editing a message with its checkpoint, the turn's stats and
a title that can be renamed."""

import time

import pytest

from pyzed import agents
from pyzed.agents import acp, llm, providers, secrets
from pyzed.agents.entries import AssistantMessage, ToolCall, UserMessage, thread_entries, turn_end


@pytest.fixture(autouse=True)
def keychain(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(providers, "_last", None)
    secrets.use(secrets.SecretStore(None))
    yield


# -- entries --------------------------------------------------------------------------------------------------

def test_thread_entries_read_messages_like_zed():
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "make a form"},
                                     {"type": "text", "text": "<context>hidden</context>"}]},
        {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "Let me see"}, {"type": "text", "text": "Sure."},
            {"type": "tool_use", "id": "a", "name": "read_file", "input": {"path": "x.py"}},
            {"type": "tool_use", "id": "b", "name": "write_file", "input": {}},
            {"type": "tool_use", "id": "c", "name": "run", "input": {}, "kind": "execute"},
            {"type": "tool_use", "id": "d", "name": "run", "input": {}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "a", "content": [{"type": "text", "text": "print(1)"}]},
            {"type": "tool_result", "tool_use_id": "b", "is_error": True,
             "content": "The user did not allow write_file"},
            {"type": "tool_result", "tool_use_id": "c", "is_error": True, "content": "boom"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "Done."}], "stats": {"seconds": 4, "tokens": 90}},
    ]
    entries = thread_entries(messages)
    kinds = [type(e).__name__ for e in entries]
    assert kinds == ["UserMessage", "AssistantMessage", "ToolCall", "ToolCall", "ToolCall", "ToolCall",
                     "AssistantMessage"]
    user, answer = entries[0], entries[1]
    assert isinstance(user, UserMessage) and user.text == "make a form" and user.index == 0
    assert isinstance(answer, AssistantMessage) and answer.chunks == [("thought", "Let me see"), ("message", "Sure.")]
    assert answer.text == "Sure." and not answer.stats
    calls = [e for e in entries if isinstance(e, ToolCall)]
    assert [(c.id, c.status) for c in calls] == [("a", "done"), ("b", "rejected"), ("c", "failed"),
                                                ("d", "canceled")]
    assert calls[0].output == "print(1)" and calls[2].kind == "execute"
    assert entries[-1].stats == {"seconds": 4, "tokens": 90}
    assert turn_end(entries, len(entries) - 1) and not turn_end(entries, len(entries) - 1, running=True)
    # while the agent runs, its calls without a result run; the ones it asks about wait for the user
    running = thread_entries(messages[:2], running=True, waiting=["b"], statuses={"c": "done"})
    assert [(e.id, e.status) for e in running if isinstance(e, ToolCall)] == [
        ("a", "running"), ("b", "waiting"), ("c", "done"), ("d", "running")]


def test_acp_keeps_the_reasoning_of_external_agents(tmp_path):
    agent = acp.ACPAgent(providers.ACPAgentConfig("fake", "true", []), cwd=tmp_path,
                         settings=providers.AgentSettings(), mcp_servers=[])
    seen = []
    agent._emit = seen.append

    def update(body):
        agent._on_notify("session/update", {"update": body})

    update({"sessionUpdate": "agent_thought_chunk", "content": {"type": "text", "text": "Hmm, "}})
    update({"sessionUpdate": "agent_thought_chunk", "content": {"type": "text", "text": "a form."}})
    update({"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "On it."}})
    blocks, _ = agent.live()
    assert blocks == [{"type": "thinking", "thinking": "Hmm, a form."}, {"type": "text", "text": "On it."}]
    assert [e.kind for e in seen] == ["thinking", "thinking", "text"]
    assert agent._flush() == "On it."  # the thinking is kept in the thread but is not the answer
    entries = thread_entries(agent.messages)
    assert entries[0].chunks == [("thought", "Hmm, a form."), ("message", "On it.")]
    # other models never get it back
    assert llm._anthropic_messages(agent.messages) == [{"role": "assistant",
                                                        "content": [{"type": "text", "text": "On it."}]}]


# -- the panel ------------------------------------------------------------------------------------------------

def _designer(tmp_path, monkeypatch, stream):
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    d = Designer(tmp_path / "main.pzform", language_servers=False)
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"), stream=stream)
    monkeypatch.setattr(c, "save_settings", lambda: None)
    monkeypatch.setattr(providers, "is_ready", lambda *a, **k: True)
    return d, c


def _wait(c):
    for _ in range(3000):
        c.poll()
        if not c.running:
            return
        time.sleep(0.005)
    raise AssertionError("timed out")


def _texts(c):
    return [b["text"] for m in c.thread.messages for b in m["content"]
            if b.get("type") == "text" and not b["text"].startswith("<context>")]


def test_messages_sent_while_the_agent_works_queue_and_go_next(tmp_path, monkeypatch):
    gate = []

    def stream(model, system, messages, tools, *, settings, on_event, cancel, **kw):
        while not gate and not cancel.is_set():
            time.sleep(0.005)
        last = messages[-1]["content"]
        asked = next(b["text"] for b in last if b.get("type") == "text" and not b["text"].startswith("<context>"))
        return llm.Turn([{"type": "text", "text": "re: " + asked}], "end_turn", usage={"output_tokens": 7})

    d, c = _designer(tmp_path, monkeypatch, stream)
    c.send("first")
    assert c.running
    c.send("second")
    c.send("third")
    assert [q.text for q in c.queued] == ["second", "third"] and c.running
    c.remove_queued(1)
    gate.append(1)
    _wait(c)  # the first run ends and the queued message goes on its own
    _wait(c)
    assert _texts(c) == ["first", "re: first", "second", "re: second"] and not c.queued
    stats = [m.get("stats") for m in c.thread.messages if m["role"] == "assistant"]
    assert all(s and s["seconds"] >= 0 for s in stats)


def test_editing_a_message_sends_it_again_from_its_checkpoint(tmp_path, monkeypatch):
    calls = []

    def stream(model, system, messages, tools, *, settings, on_event, cancel, **kw):
        calls.append(1)
        if len(calls) % 2:
            return llm.Turn([{"type": "tool_use", "id": f"t{len(calls)}", "name": "add_controls", "input": {
                "controls": [{"type": "button", "name": f"b{len(calls)}"}]}}], "tool_use")
        return llm.Turn([{"type": "text", "text": "Added."}], "end_turn")

    d, c = _designer(tmp_path, monkeypatch, stream)
    names = lambda: [x.name for x in d.doc.form.controls]  # noqa: E731
    before = names()
    c.send("add a button")
    _wait(c)
    assert "b1" in names() and c.has_checkpoint(0)
    c.start_edit(0)
    assert c.editing == 0 and c.edit_text == "add a button"
    c.set_edit_text("add another button")
    c.submit_edit()
    _wait(c)
    assert _texts(c) == ["add another button", "Added."]
    assert "b1" not in names() and "b3" in names()  # the documents went back before the new run
    c.restore_checkpoint(0, notify=False)
    assert names() == before and not c.has_checkpoint(0)


def test_rename_and_the_activity_bar_toggles(tmp_path, monkeypatch):
    d, c = _designer(tmp_path, monkeypatch, None)
    c.start_rename()
    assert c.title_editing
    c.set_title_buffer("  Sign-in form ")
    c.save_title()
    assert c.thread.display_title == "Sign-in form" and not c.title_editing
    assert not c.plan_expanded
    c.toggle_flag("plan_expanded")
    assert c.plan_expanded
    assert c.agent_label() == "Pyzed Agent" and not c.is_external


def test_the_thread_has_a_right_click_menu_to_copy(tmp_path, monkeypatch):
    from pyzed import _core
    from pyzed.designer import agent_thread
    from pyzed.theme import current

    d, c = _designer(tmp_path, monkeypatch, None)
    c.thread.messages = [{"role": "user", "content": [{"type": "text", "text": "hi"}]},
                         {"role": "assistant", "content": [{"type": "text", "text": "Hello there"}]}]
    d.window_pointer = (120, 80)
    c.open_thread_menu("Hello there")
    assert c.thread_menu == ("Hello there", 120, 80)
    monkeypatch.setattr(_core, "selected_text", lambda group: "there" if group == "agent-thread" else None)
    menu, x, y = agent_thread.thread_menu_at(c, current())
    assert menu is not None and x >= 4 and y >= 4
    copied = c.copy_selection()
    assert copied is not None and c.thread_menu is None
    c.open_thread_menu()
    c.select_all_text()  # nothing drawn yet: selects nothing, closes the menu
    assert c.thread_menu is None
    c.open_thread_menu()
    d.on_key("escape")
    assert c.thread_menu is None


def test_composer_chips_stay_short():
    from pyzed.designer.agent_panel import chip_text

    assert chip_text("Bypass permissions") == "Bypass permissions"
    assert chip_text("Default (recommended)") == "Default"
    assert chip_text("A very long model name without notes") == "A very long model n…"
