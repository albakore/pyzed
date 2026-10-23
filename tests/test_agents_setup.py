"""Setting up the agents on a desktop: programs installed with nvm or in ~/.local/bin are found when the app
is opened from the desktop's menu, an agent that needs Node.js says so, and Retry does not repeat the message."""

import os
import stat
import time

import pytest

from pyzed import _platform, agents
from pyzed.agents import acp, llm, mcp_client, providers


def test_tool_folders_put_the_newest_node_of_nvm_first(tmp_path, monkeypatch):
    monkeypatch.delenv("NVM_DIR", raising=False)
    for version in ("v18.20.1", "v20.11.0", "v9.0.0"):
        (tmp_path / ".nvm" / "versions" / "node" / version / "bin").mkdir(parents=True)
    (tmp_path / ".local" / "bin").mkdir(parents=True)
    found = _platform.tool_dirs(tmp_path)
    if os.name == "nt":
        assert str(tmp_path / ".local" / "bin") in found
        return
    nvm = [p for p in found if ".nvm" in p]
    assert nvm[0].endswith(os.path.join("v20.11.0", "bin")) and nvm[-1].endswith(os.path.join("v9.0.0", "bin"))
    assert str(tmp_path / ".local" / "bin") in found


@pytest.mark.skipif(os.name == "nt", reason="a shell script stands for the program")
def test_programs_in_the_users_shell_path_are_found_and_started(tmp_path, monkeypatch):
    folder = tmp_path / "nvm-bin"
    folder.mkdir()
    program = folder / "fake-npx"
    program.write_text("#!/bin/sh\nread line\necho '{\"jsonrpc\": \"2.0\", \"id\": 1, \"result\": {\"path\": \"'$PATH'\"}}'\n")
    program.chmod(program.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(_platform, "_user_path", None)
    monkeypatch.setattr(_platform, "_shell_path", lambda: [str(folder)])
    monkeypatch.setattr(_platform, "tool_dirs", lambda home=None: [])
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    assert _platform.which("fake-npx") == str(program)
    rpc = mcp_client.JsonRpcProcess("fake-npx")  # found, and started with the shell's PATH (for its node)
    try:
        assert str(folder) in rpc.request("ping", {}, timeout=10)["path"]
    finally:
        rpc.close()
    _platform.use_user_path()
    assert str(folder) in os.environ["PATH"]


def _no_node(monkeypatch):
    monkeypatch.setattr(acp._platform, "which", lambda name: None)

    def fail(command, *args, **kwargs):
        raise mcp_client.MCPError(f"Could not start {command}: [Errno 2] No such file or directory: '{command}'")

    monkeypatch.setattr(acp.mcp_client, "JsonRpcProcess", fail)


def test_an_agent_without_node_says_what_to_install(tmp_path, monkeypatch):
    _no_node(monkeypatch)
    agent = acp.ACPAgent(acp.preset("claude-code"), cwd=tmp_path, settings=providers.AgentSettings(), mcp_servers=[])
    events = []
    agent.run("hi", on_event=events.append)
    error = next(e.text for e in events if e.kind == "error")
    assert "Claude Code needs Node.js 22 or later" in error and "Pyzed Agent" in error


def test_retry_does_not_repeat_the_message_and_pyzed_agent_takes_over(tmp_path, monkeypatch):
    from pyzed.designer import agent_thread
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    _no_node(monkeypatch)

    def stream(model, system, messages, tools, *, settings, on_event, cancel, **kw):
        return llm.Turn([{"type": "text", "text": "Hecho."}], "end_turn")

    d = Designer(tmp_path / "main.pzform", language_servers=False)
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"), stream=stream)
    monkeypatch.setattr(c, "save_settings", lambda: None)
    monkeypatch.setattr(providers, "is_ready", lambda *a, **k: True)
    c.settings.acp_agents.append(acp.preset("claude-code"))
    c.set_model("acp:claude-code")

    def wait():
        for _ in range(2000):
            c.poll()
            if not c.running:
                return
            time.sleep(0.005)
        raise AssertionError("timed out")

    def asked():
        return [m for m in c.thread.messages if m.get("role") == "user"]

    c.send("Crea un login")
    wait()
    assert c.needs_node and len(asked()) == 1
    t = d.theme
    assert agent_thread.thread_view(c, t) is not None  # with Install Node.js and Use Pyzed Agent
    for _ in range(3):
        c.retry()
        wait()
    assert len(asked()) == 1  # the unanswered message is sent again, not added again
    c.use_pyzed_agent()
    wait()
    assert not c.thread.model.startswith("acp:") and not c.error
    assert len(asked()) == 1 and c.thread.messages[-1]["role"] == "assistant"


def test_the_agent_settings_show_the_everyday_ones_first(tmp_path, monkeypatch):
    from pyzed.designer import agent_panel
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    d = Designer(tmp_path / "main.pzform", language_servers=False)
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"))
    monkeypatch.setattr(c, "save_settings", lambda: None)
    t = d.theme
    c.settings.model = "anthropic:claude-opus-5-5"
    assert agent_panel.settings_view(d, t) is not None
    c.settings.model = "acp:claude-code"
    assert agent_panel.settings_view(d, t) is not None
    assert not c.advanced_open
    c.toggle_advanced()
    assert agent_panel.settings_view(d, t) is not None and c.advanced_open
    c.advanced_open = False
    c.open_settings(section="agents")
    assert c.advanced_open  # the registry of agents is in the Advanced part


def test_claude_code_runs_the_current_adapter_with_its_new_models_and_effort():
    claude = acp.preset("claude-code")
    assert claude.args == ["-y", "@agentclientprotocol/claude-agent-acp@latest"]
    saved = providers.AgentSettings.from_dict({"acp_agents": [
        {"name": "claude-code", "command": "npx", "args": ["-y", "@zed-industries/claude-code-acp"]},
        {"name": "codex", "command": "npx", "args": ["-y", "@zed-industries/codex-acp@0.16.0"]},
        {"name": "mine", "command": "npx", "args": ["-y", "my-agent"]}]})
    assert [a.args[-1] for a in saved.acp_agents] == [
        "@agentclientprotocol/claude-agent-acp@latest", "@agentclientprotocol/codex-acp@latest", "my-agent"]
    # what the current adapter answers to session/new (trimmed)
    options = acp.session_options({"sessionId": "s", "configOptions": [
        {"id": "model", "name": "Model", "category": "model", "type": "select", "currentValue": "default", "options": [
            {"value": "default", "name": "Default (recommended)"}, {"value": "fable", "name": "Fable 5.1"},
            {"value": "opus", "name": "Opus 5.5"}, {"value": "sonnet", "name": "Sonnet 5.5"},
            {"value": "haiku", "name": "Haiku 5.5"}]},
        {"id": "effort", "name": "Effort", "category": "thought_level", "type": "select", "currentValue": "default",
         "options": [{"value": v, "name": v.capitalize()} for v in ("default", "low", "medium", "high", "xhigh", "max")]},
    ]})
    by_id = {o["id"]: o for o in options}
    assert [c["name"] for c in by_id["model"]["choices"]][1:] == ["Fable 5.1", "Opus 5.5", "Sonnet 5.5", "Haiku 5.5"]
    assert [c["value"] for c in by_id["effort"]["choices"]][-2:] == ["xhigh", "max"]
    assert by_id["effort"]["category"] == "thought_level"
