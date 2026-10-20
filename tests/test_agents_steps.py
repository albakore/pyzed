"""The Agent panel shows every step as it happens, works fast with what it already knows, offers each agent's own
options like Zed (modes, models, thinking, permissions) and adds Pyzed's MCP server to the agents of this computer."""

import json
import sys
import textwrap
import threading
import time

import pytest

from pyzed import agents, ui
from pyzed.agents import acp, llm, mcp_install, providers, secrets


@pytest.fixture(autouse=True)
def keychain(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(providers, "_last", None)
    secrets.use(secrets.SecretStore(None))
    yield


# -- an external agent's steps and options -------------------------------------------------------------------

AGENT = textwrap.dedent('''
    import json, os, sys, threading, time
    go = sys.argv[1]
    current = {"mode": "default", "model": "sonnet"}

    def send(msg):
        print(json.dumps(msg), flush=True)

    def update(session, body):
        send({"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": session, "update": body}})

    def prompt(ident, params):
        s = params["sessionId"]
        update(s, {"sessionUpdate": "tool_call", "toolCallId": "c1", "title": "mcp__pyzed_editor__add_control",
                   "kind": "edit", "status": "pending", "rawInput": {}})
        update(s, {"sessionUpdate": "tool_call_update", "toolCallId": "c1", "status": "in_progress",
                   "rawInput": {"type": "input", "name": "email"}, "locations": [{"path": "ui/main.pzform"}],
                   "content": [{"type": "diff", "path": "ui/main.pzform", "oldText": "a\\n", "newText": "a\\nb\\n"}]})
        while not os.path.exists(go):
            time.sleep(0.01)
        update(s, {"sessionUpdate": "tool_call_update", "toolCallId": "c1", "status": "completed"})
        update(s, {"sessionUpdate": "agent_message_chunk", "content": {"type": "text",
                   "text": "Done in " + current["mode"] + " with " + current["model"]}})
        send({"jsonrpc": "2.0", "id": ident, "result": {"stopReason": "end_turn"}})

    for line in sys.stdin:
        msg = json.loads(line)
        if "method" not in msg:
            continue
        method, ident, params = msg["method"], msg.get("id"), msg.get("params") or {}
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": ident, "result": {"protocolVersion": 1, "agentCapabilities": {},
                                                           "authMethods": []}})
        elif method == "session/new":
            send({"jsonrpc": "2.0", "id": ident, "result": {"sessionId": "s1", "modes": {
                "currentModeId": "default", "availableModes": [
                    {"id": "default", "name": "Default", "description": "Asks before edits"},
                    {"id": "plan", "name": "Plan mode"}]},
                "models": {"currentModelId": "sonnet", "availableModels": [
                    {"modelId": "sonnet", "name": "Sonnet"}, {"modelId": "opus", "name": "Opus"}]}}})
        elif method == "session/set_mode":
            current["mode"] = params["modeId"]
            update(params["sessionId"], {"sessionUpdate": "current_mode_update", "currentModeId": params["modeId"]})
            send({"jsonrpc": "2.0", "id": ident, "result": {}})
        elif method == "session/set_model":
            current["model"] = params["modelId"]
            send({"jsonrpc": "2.0", "id": ident, "result": {}})
        elif method == "session/prompt":
            threading.Thread(target=prompt, args=(ident, params)).start()
''')


def _agent(tmp_path, **settings):
    script = tmp_path / "agent.py"
    script.write_text(AGENT)
    config = providers.ACPAgentConfig("fake", sys.executable, [str(script), str(tmp_path / "go")], title="Fake")
    return acp.ACPAgent(config, cwd=tmp_path, settings=providers.AgentSettings(**settings), mcp_servers=[])


def test_external_agent_steps_show_while_they_run_and_its_options_like_zed(tmp_path):
    agent = _agent(tmp_path, agent_options={"fake": {"model": "opus"}})
    try:
        agent.start()  # the session opens before the first message, with the model picked last time
        assert [(o["id"], o["current"], [c["value"] for c in o["choices"]]) for o in agent.options] == [
            ("mode", "default", ["default", "plan"]), ("model", "opus", ["sonnet", "opus"])]
        agent.set_option("mode", "plan")
        assert agent.options[0]["current"] == "plan"
        answer: list = []
        worker = threading.Thread(target=lambda: answer.append(agent.run("go")))
        worker.start()
        for _ in range(500):  # the call is visible before it ends, with what came in later updates
            blocks, results = agent.live()
            if blocks and blocks[0].get("diffs"):
                break
            time.sleep(0.01)
        call = blocks[0]
        assert call["name"] == "mcp__pyzed_editor__add_control" and call["input"] == {"type": "input", "name": "email"}
        assert call["locations"] == ["ui/main.pzform"] and call["diffs"][0]["new"] == "a\nb\n" and not results
        (tmp_path / "go").write_text("")
        worker.join(10)
        assert answer == ["Done in plan with opus"]
        assert agent.live() == ([], [])
    finally:
        agent.close()


def test_session_config_options_are_read_with_groups():
    options = acp.session_options({"configOptions": [
        {"id": "model", "name": "Model", "category": "model", "type": "select", "currentValue": "opus",
         "options": [{"group": "Claude", "name": "Claude", "options": [{"value": "opus", "name": "Opus"},
                                                                       {"value": "haiku", "name": "Haiku"}]}]},
        {"id": "effort", "name": "Effort", "category": "thought_level", "type": "select", "currentValue": "high",
         "options": [{"value": "low", "name": "Low"}, {"value": "high", "name": "High"}]},
        {"id": "on", "type": "boolean"}], "modes": {"availableModes": [{"id": "x"}]}})
    assert [(o["id"], o["via"], o["current"], len(o["choices"])) for o in options] == [
        ("model", "config", "opus", 2), ("effort", "config", "high", 2)]  # config options replace modes


def test_tool_calls_render_with_diffs_and_progress():
    card = ui.ToolCall(title="Edit", detail="a.py", kind="edit", status="running", progress="line 1\nline 2",
                       diffs=[{"path": "a.py", "old": "x = 1\n", "new": "x = 2\n"}])
    assert card is not None
    assert ui.diff_view({"path": "a.py", "old": "a\n" * 300, "new": "b\n" * 300}, max_lines=10) is not None


# -- the panel ------------------------------------------------------------------------------------------------

def _designer(tmp_path, monkeypatch, stream):
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    d = Designer(tmp_path / "main.pzform", language_servers=False)
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"), stream=stream)
    monkeypatch.setattr(c, "save_settings", lambda: None)
    monkeypatch.setattr(providers, "is_ready", lambda *a, **k: True)
    return d, c


def _run(c, text):
    c.send(text)
    for _ in range(3000):
        c.poll()
        if not c.running:
            return
        time.sleep(0.005)
    raise AssertionError("timed out")


def test_the_built_in_agent_knows_the_editor_and_builds_in_one_call(tmp_path, monkeypatch):
    from pyzed.designer import agent_panel, agent_tools

    seen = []

    def stream(model, system, messages, tools, *, settings, on_event, cancel, **kw):
        seen.append((system, json.loads(json.dumps(messages)), settings.thinking))
        if len(seen) == 1:
            on_event("tool", "add_controls")  # the panel shows the call while the model writes it
            return llm.Turn([{"type": "tool_use", "id": "t1", "name": "add_controls", "input": {"controls": [
                {"type": "column", "name": "box", "x": 16, "y": 16, "width": 300, "height": 200},
                {"type": "input", "name": "email", "parent": "box", "props": {"placeholder": "Email"}},
                {"type": "button", "name": "send_button", "parent": "box", "props": {"text": "Send"}}]}}],
                "tool_use")
        return llm.Turn([{"type": "text", "text": "Built."}], "end_turn")

    d, c = _designer(tmp_path, monkeypatch, stream)
    c.thread.model = c.settings.model = "anthropic:claude-opus-5-5"
    c.toggle_thinking()
    events = []
    real = c._on_event
    monkeypatch.setattr(c, "_on_event", lambda e: (events.append((e.kind, e.tool)), real(e)))
    _run(c, "make a sign-in form")
    system, messages, thinking = seen[0]
    assert "- button (" in system and "best practices" in system.lower() and "add_controls" in system
    assert "Its controls:" in messages[0]["content"][-1]["text"]  # the open document came with the message
    assert thinking is False
    assert ("tool_input", "add_controls") in events
    names = [x.name for x in d.doc.form.controls]
    assert names[-3:] == ["box", "email", "send_button"] and d.doc.form["email"].parent == "box"
    d.doc.undo()
    assert "email" not in [x.name for x in d.doc.form.controls]  # one undo step for the whole batch
    add_controls = c.tool_index()["add_controls"].func
    with pytest.raises(ValueError, match=r"controls\[1\] \(b\).*nothing was added"):
        add_controls([{"type": "label", "name": "a"}, {"type": "nope", "name": "b"}])
    assert "a" not in [x.name for x in d.doc.form.controls]
    assert agent_panel._tool_title("mcp__pyzed_editor__add_control", c.tool_index()) == "Adding a control"
    assert agent_panel._args_preview({"controls": [{"name": "a"}, {"type": "b"}]}) == "a, b"
    assert len(agent_tools.knowledge()) < 40_000


def test_the_agent_steps_go_to_the_logs_panel(tmp_path, monkeypatch):
    calls = []

    def stream(model, system, messages, tools, *, settings, on_event, cancel, **kw):
        calls.append(1)
        if len(calls) == 1:
            return llm.Turn([{"type": "tool_use", "id": "t1", "name": "select", "input": {"name": "nope"}}],
                            "tool_use", usage={"input": 10, "output": 5})
        return llm.Turn([{"type": "text", "text": "Done."}], "end_turn")

    d, c = _designer(tmp_path, monkeypatch, stream)
    c.thread.model = c.settings.model = "anthropic:claude-opus-5-5"
    _run(c, "select the button")
    c.toggle_thinking()
    entries = [(e.level, e.source, e.text) for e in d.logs.log.entries if e.source == "agent"]
    texts = [text for _, _, text in entries]
    assert ("event", "agent", "Asked anthropic:claude-opus-5-5: select the button") in entries
    assert ("event", "agent", "Tool select (name='nope')") in entries
    assert any(level == "warning" and text.startswith("Tool select failed") for level, _, text in entries)
    assert any(text.startswith("Finished in ") for text in texts) and "Thinking off" in texts
    d.logs.uninstall()


def test_always_allow_is_remembered_and_agent_options_show_in_the_composer(tmp_path, monkeypatch):
    from pyzed.designer import agent_panel

    d, c = _designer(tmp_path, monkeypatch, lambda *a, **k: llm.Turn([], "end_turn"))
    tool_ = agents.Tool("write_file", "", {"type": "object", "properties": {}}, lambda: None, writes=True)
    box = agent_panel._Box()
    c.pending = agent_panel.Confirmation(tool_, {}, box)
    c.answer(True, always=True)
    assert c.settings.allowed_tools == ["write_file"] and c._confirm(tool_, {})
    c.forget_tool("write_file")
    assert c.settings.allowed_tools == [] and "write_file" not in c.always_allow

    agent = _agent(tmp_path)
    c.settings.acp_agents = [agent.config]
    c.thread.model = "acp:fake"
    c._acp[c.thread.id] = agent
    try:
        agent.start()
        t = d.theme
        assert agent_panel._composer(c, t) is not None
        c.toggle_menu("option:mode")
        assert agent_panel._thread_view(c, d, t, None) is not None
        c.set_agent_option("mode", "plan")
        for _ in range(500):
            c.poll()
            if agent.options[0]["current"] == "plan":
                break
            time.sleep(0.01)
        assert agent.options[0]["current"] == "plan" and c.settings.agent_options == {"fake": {"mode": "plan"}}
        assert agent_panel.settings_view(d, t) is not None
    finally:
        agent.close()


# -- Pyzed's MCP server in the agents of this computer ------------------------------------------------------

def test_pyzed_mcp_is_added_to_the_agents_found(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("APPDATA", str(home / "AppData"))
    monkeypatch.setattr(mcp_install.shutil, "which", lambda name: None)
    monkeypatch.setattr(mcp_install, "server_command", lambda: ["/bin/uvx", "--from", "pyzed-ui[mcp]", "pyzed", "mcp"])
    found = {c.id: c for c in mcp_install.clients(home)}
    for cid in ("cursor", "codex", "vscode", "zed", "claude-code"):
        found[cid].marker.mkdir(parents=True)
    found["cursor"].path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    found["codex"].path.write_text('model = "o3"\n\n[mcp_servers.pyzed]\ncommand = "old"\n\n[mcp_servers.pyzed.env]\n'
                                   'A = "1"\n')
    found["zed"].path.write_text('{\n  // my settings\n  "theme": "One Dark"\n}\n')
    assert {c.id for c in mcp_install.detected(home)} == {"cursor", "codex", "vscode", "zed", "claude-code"}
    assert mcp_install.status(found["codex"]) == "installed" and mcp_install.status(found["zed"]) == "unreadable"

    added, failed = mcp_install.install_missing(["vscode"], home)
    assert sorted(c.id for c in added) == ["claude-code", "cursor"] and failed == {}
    cursor = json.loads(found["cursor"].path.read_text())
    assert cursor["mcpServers"]["other"] == {"command": "x"}  # the rest is kept
    assert cursor["mcpServers"]["pyzed"] == {"command": "/bin/uvx", "args": ["--from", "pyzed-ui[mcp]", "pyzed", "mcp"]}
    assert found["cursor"].path.with_name("mcp.json.pyzed-backup").exists()
    assert "pyzed" in json.loads(found["claude-code"].path.read_text())["mcpServers"]  # no claude CLI: its file

    mcp_install.install(found["vscode"])
    assert json.loads(found["vscode"].path.read_text())["servers"]["pyzed"]["type"] == "stdio"
    mcp_install.install(found["codex"])
    codex = found["codex"].path.read_text()
    assert codex.count("[mcp_servers.pyzed") == 1 and 'command = "/bin/uvx"' in codex and 'model = "o3"' in codex
    mcp_install.remove(found["codex"])
    mcp_install.remove(found["cursor"])
    assert mcp_install.status(found["codex"]) == "missing" and 'model = "o3"' in found["codex"].path.read_text()
    assert json.loads(found["cursor"].path.read_text())["mcpServers"] == {"other": {"command": "x"}}
    with pytest.raises(ValueError):
        mcp_install.install(found["zed"])  # comments: left alone


def test_the_designer_adds_pyzed_mcp_on_start_and_asks_to_restart(tmp_path, monkeypatch):
    from pyzed.designer import agent_panel

    d, c = _designer(tmp_path, monkeypatch, lambda *a, **k: llm.Turn([], "end_turn"))
    cursor = mcp_install.Client("cursor", "Cursor", "json", tmp_path / "mcp.json", tmp_path)
    monkeypatch.setattr(mcp_install, "detected", lambda home=None: [cursor])
    monkeypatch.setattr(mcp_install, "server_command", lambda: ["uvx", "pyzed"])
    c.on_start()
    for _ in range(500):
        c.poll()
        if c.mcp_added:
            break
        time.sleep(0.01)
    assert c.mcp_added == ["Cursor"] and c.settings.pyzed_mcp_done == ["cursor"]
    assert agent_panel._thread_view(c, d, d.theme, None) is not None
    c.restart_agents()
    assert c.mcp_added == []
    cursor.path.write_text("{}")  # taken out by hand: not added again on the next start
    c.on_start()
    for _ in range(50):
        c.poll()
        time.sleep(0.01)
    assert mcp_install.status(cursor) == "missing"
