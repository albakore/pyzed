"""AI agents: providers, secrets, the agent loop, streaming parsers, browser sign-in and the Agent panel."""

import http.server
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

from pyzed import agents
from pyzed.agents import llm, login, providers, secrets


class FakeKeyring:
    name = "Fake keychain"

    def __init__(self):
        self.data = {}

    def get_password(self, service, key):
        return self.data.get((service, key))

    def set_password(self, service, key, value):
        self.data[(service, key)] = value

    def delete_password(self, service, key):
        self.data.pop((service, key), None)


@pytest.fixture(autouse=True)
def keychain(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", "/nonexistent-ant-config")
    fake = FakeKeyring()
    secrets.use(secrets.SecretStore(fake))
    yield fake
    secrets.use(secrets.SecretStore(None))


# -- secrets and settings ---------------------------------------------------------------------------

def test_keys_go_to_the_keychain_never_to_settings(keychain, tmp_path):
    assert agents.set_key("openai", "  sk-test-123456789  ") is True
    assert keychain.data[("pyzed", "agents.openai")] == "sk-test-123456789"
    assert agents.get_key("openai") == "sk-test-123456789"
    assert providers.credential_source("openai") == "keychain"
    path = providers.save(providers.AgentSettings(), tmp_path / "agents.json")
    assert "sk-test" not in path.read_text()
    agents.delete_key("openai")
    assert agents.get_key("openai") is None and providers.credential_source("openai") == ""


def test_without_a_keychain_secrets_last_for_the_session(monkeypatch):
    store = secrets.SecretStore(None)
    secrets.use(store)
    assert not store.secure and "memory" in store.backend_name
    assert agents.set_key("anthropic", "sk-ant-abc") is False
    assert agents.get_key("anthropic") == "sk-ant-abc"
    assert providers.credential_source("anthropic") == "session"


def test_environment_keys_and_local_providers(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    assert providers.credential_source("openai") == "env"
    assert providers.credential_source("ollama") == "none needed"
    assert providers.is_ready("ollama") and not providers.is_ready("google")
    assert secrets.mask("sk-ant-0123456789abcd") == "sk-ant…abcd" and secrets.mask("short") == "•••••"


def test_model_names_and_settings_roundtrip(tmp_path):
    assert providers.split_model("ollama:qwen3:8b") == ("ollama", "qwen3:8b")
    assert providers.split_model("openrouter:anthropic/claude-opus-5-5") == ("openrouter", "anthropic/claude-opus-5-5")
    assert providers.split_model("claude-opus-5-5") == ("anthropic", "claude-opus-5-5")
    s = providers.AgentSettings(model="ollama:llama3", effort="max", profile="ask", rules="Be brief")
    s.provider("ollama").base_url = "http://box:11434/v1/"
    s.provider("ollama").models = ["llama3", "qwen3:8b"]
    providers.save(s, tmp_path / "a.json")
    back = providers.load(tmp_path / "a.json")
    assert back == s
    assert back.base_url("ollama") == "http://box:11434/v1"
    assert back.models_of("anthropic")[0] == "claude-opus-5-5"
    bad = providers.AgentSettings.from_dict({"effort": "huge", "profile": "?", "providers": {"nope": {}}})
    assert bad.effort == "high" and bad.profile == "write" and not bad.providers


# -- tools and the agent loop -------------------------------------------------------------------------

def test_tool_schema_from_signature_and_validation():
    @agents.tool(writes=True)
    def resize(name: str, width: float, keep: bool = True, tags: list = None):
        """Resizes a control.

        name: the control.
        width: in pixels.
        """

    assert resize.writes and resize.description == "Resizes a control."
    assert resize.schema["required"] == ["name", "width"]
    assert resize.schema["properties"]["width"] == {"type": "number", "description": "in pixels."}
    assert resize.schema["properties"]["tags"]["type"] == "array"
    assert resize.validate({"name": "a", "width": 3}) is None
    assert "missing" in resize.validate({"name": "a"})
    assert "type number" in resize.validate({"name": "a", "width": "wide"})
    assert "unknown" in resize.validate({"name": "a", "width": 1, "height": 2})
    assert "JSON" in resize.validate({"INVALID_JSON": "{"})


def scripted(*turns):
    """A fake ``stream_turn`` answering with ``turns`` in order (each a list of blocks or a Turn)."""
    calls = []

    def stream(model, system, messages, tools, *, settings, on_event, cancel, **kw):
        calls.append({"model": model, "messages": [dict(m) for m in messages], "tools": [t.name for t in tools]})
        turn = turns[len(calls) - 1]
        if not isinstance(turn, llm.Turn):
            uses = any(b["type"] == "tool_use" for b in turn)
            turn = llm.Turn(turn, "tool_use" if uses else "end_turn", {"input": 10, "output": 5})
        for b in turn.content:
            if b["type"] == "text":
                on_event("text", b["text"])
        return turn

    stream.calls = calls
    return stream


def test_agent_runs_tools_until_the_model_answers():
    seen = []

    @agents.tool
    def add(a: int, b: int) -> int:
        """Adds two numbers."""
        return a + b

    stream = scripted(
        [{"type": "text", "text": "Let me add."}, {"type": "tool_use", "id": "t1", "name": "add", "input": {"a": 2, "b": 3}}],
        [{"type": "text", "text": "It is 5."}],
    )
    agent = agents.Agent("anthropic:claude-opus-5-5", tools=[add], stream=stream,
                         settings=providers.AgentSettings())
    assert agent.run("2+3?", on_event=seen.append) == "It is 5."
    kinds = [e.kind for e in seen]
    assert kinds.count("turn") == 2 and kinds[-1] == "done" and "tool_result" in kinds
    result = agent.messages[2]["content"][0]
    assert result == {"type": "tool_result", "tool_use_id": "t1", "content": "5", "is_error": False}
    assert agent.messages[1]["provider"] == "anthropic"
    assert agent.usage == {"input": 20, "output": 10}
    assert stream.calls[0]["tools"] == ["add"]


def test_profiles_confirmations_and_bad_inputs():
    @agents.tool(writes=True)
    def write(path: str) -> str:
        """Writes."""
        raise AssertionError("must not run")

    @agents.tool
    def read(path: str) -> str:
        """Reads."""
        return "data"

    stream = scripted(
        [{"type": "tool_use", "id": "1", "name": "write", "input": {"path": "x"}},
         {"type": "tool_use", "id": "2", "name": "read", "input": {"nope": 1}}],
        [{"type": "text", "text": "ok"}],
    )
    asked = []
    agent = agents.Agent("x", tools=[write, read], stream=stream, settings=providers.AgentSettings(),
                         confirm=lambda tool, args: asked.append(tool.name) or False)
    agent.run("go")
    results = agent.messages[2]["content"]
    assert asked == ["write"] and results[0]["is_error"] and "did not allow" in results[0]["content"]
    assert results[1]["is_error"] and "INVALID_INPUT" in results[1]["content"]
    unasked = agents.Agent("x", tools=[write], settings=providers.AgentSettings(),
                           stream=scripted([{"type": "tool_use", "id": "3", "name": "write", "input": {"path": "x"}}],
                                           [{"type": "text", "text": "ok"}]))
    unasked.run("go")
    assert unasked.messages[2]["content"][0]["is_error"] and "confirmation" in unasked.messages[2]["content"][0]["content"]
    ask = agents.Agent("x", tools=[write, read], settings=providers.AgentSettings(profile="ask"))
    assert [t.name for t in ask.active_tools()] == ["read"]
    assert agents.Agent("x", tools=[read], settings=providers.AgentSettings(profile="minimal")).active_tools() == []


def test_refusals_cut_outputs_and_errors_never_raise():
    @agents.tool
    def noop() -> str:
        """Nothing."""
        return ""

    refused = llm.Turn([{"type": "text", "text": "No."}, {"type": "tool_use", "id": "1", "name": "noop", "input": {}}],
                       "refusal")
    events = []
    agent = agents.Agent("x", tools=[noop], stream=scripted(refused), settings=providers.AgentSettings())
    agent.run("hi", on_event=events.append)
    assert all(b["type"] != "tool_use" for b in agent.messages[-1]["content"])
    assert any(e.kind == "error" and "declined" in e.text for e in events)

    cut = llm.Turn([{"type": "tool_use", "id": "9", "name": "noop", "input": {}}], "max_tokens")
    agent = agents.Agent("x", tools=[noop], stream=scripted(cut, [{"type": "text", "text": "done"}]),
                         settings=providers.AgentSettings())
    agent.run("hi")
    assert agent.messages[2]["content"][0]["is_error"] and "cut off" in agent.messages[2]["content"][0]["content"]

    def broken(*a, **k):
        raise llm.AgentError("bad key")

    events = []
    agent = agents.Agent("x", stream=broken, settings=providers.AgentSettings())
    assert agent.run("hi", on_event=events.append) == "bad key"
    assert [e.kind for e in events] == ["error", "done"] and not agent.running


def test_pyzed_and_file_tools(tmp_path):
    tools = {t.name: t for t in agents.pyzed_tools() + agents.file_tools(tmp_path)}
    assert any(c["name"] == "designer:button" for c in tools["list_components"].func(kind="designer"))
    assert tools["validate_code"].func(code="import pyzed as pz\npz.colum()\n")["issues"]
    tools["write_file"].func(path="ui/a.py", content="x = 1\n")
    assert tools["read_file"].func(path="ui/a.py") == "x = 1\n"
    assert tools["list_files"].func(pattern="*.py")["files"] == ["ui/a.py"]
    assert tools["search_text"].func(text="x =")["matches"] == ["ui/a.py:1: x = 1"]
    with pytest.raises(PermissionError):
        tools["read_file"].func(path="../outside.txt")
    assert tools["write_file"].writes and not tools["read_file"].writes

    # Keys and credentials stay out of the agent's reach, even when it names them.
    (tmp_path / ".env").write_text("TOKEN=secret\n")
    (tmp_path / "ui" / "server.key").write_text("x = 1\n")
    assert ".env" not in tools["list_files"].func(pattern="*")["files"]
    assert tools["search_text"].func(text="x =", pattern="*")["matches"] == ["ui/a.py:1: x = 1"]
    for name in (".env", "ui/server.key"):
        with pytest.raises(PermissionError, match="secrets"):
            tools["read_file"].func(path=name)
    with pytest.raises(PermissionError, match="secrets"):
        tools["write_file"].func(path=".env.local", content="")


def test_threads_are_saved_locally(tmp_path):
    store = agents.ThreadStore(tmp_path)
    thread = agents.Thread(model="ollama:llama3", messages=[{"role": "user", "content": [{"type": "text", "text": "Hola\nmundo"}]}])
    path = store.save(thread)
    assert [t.id for t in store.list()] == [thread.id]
    if os.name != "nt":  # only the user can read saved threads
        assert path.stat().st_mode & 0o777 == 0o600
    assert store.load(thread.id).display_title == "Hola"
    store.delete(thread.id)
    assert store.list() == [] and agents.Thread().display_title == "New thread"


# -- OpenAI-compatible streaming ------------------------------------------------------------------------

def test_openai_stream_with_tool_calls_and_reasoning():
    lines = [
        'data: {"model":"m","choices":[{"delta":{"reasoning_content":"hmm"}}]}',
        'data: {"choices":[{"delta":{"content":"Hi "}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1","function":{"name":"add","arguments":"{\\"a\\":"}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"1}"}}]},"finish_reason":"tool_calls"}]}',
        'data: {"choices":[],"usage":{"prompt_tokens":7,"completion_tokens":3}}',
        "data: [DONE]",
    ]
    events = []
    turn = llm.parse_sse([line.encode() for line in lines], lambda k, t: events.append((k, t)), threading.Event())
    assert events == [("thinking", "hmm"), ("text", "Hi ")]
    assert turn.stop_reason == "tool_use" and turn.usage == {"input": 7, "output": 3}
    assert turn.content[1] == {"type": "tool_use", "id": "c1", "name": "add", "input": {"a": 1}}


def test_conversation_converts_to_openai_messages():
    history = [
        {"role": "user", "content": [{"type": "text", "text": "q"}]},
        {"role": "assistant", "provider": "anthropic", "content": [
            {"type": "thinking", "thinking": "…", "signature": "s"}, {"type": "text", "text": "a"},
            {"type": "tool_use", "id": "t", "name": "f", "input": {"x": 1}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "r"}]},
    ]
    out = llm._openai_messages("sys", history)
    assert out[0] == {"role": "system", "content": "sys"}
    assert out[2]["tool_calls"][0]["function"] == {"name": "f", "arguments": '{"x": 1}'}
    assert out[3] == {"role": "tool", "tool_call_id": "t", "content": "r"}
    # Claude gets its own blocks back unchanged, and other providers' blocks without extras
    assert llm._anthropic_messages(history)[1]["content"][0]["type"] == "thinking"
    foreign = [{"role": "assistant", "provider": "openai", "content": [{"type": "x"}, {"type": "text", "text": "a"}]}]
    assert llm._anthropic_messages(foreign)[0]["content"] == [{"type": "text", "text": "a"}]


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True


def _serve(handler):
    server = _Server(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def test_openai_compatible_server_end_to_end():
    bodies = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            bodies.append((self.headers.get("Authorization"), json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(b'data: {"choices":[{"delta":{"content":"pong"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')

        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"data":[{"id":"b"},{"id":"a"}]}')

        def log_message(self, *a):
            pass

    server, url = _serve(Handler)
    try:
        s = providers.AgentSettings()
        s.provider("custom").base_url = url
        agents.set_key("custom", "tok")
        turn = agents.stream_turn("custom:tiny", "be nice", [{"role": "user", "content": [{"type": "text", "text": "ping"}]}],
                                  settings=s)
        assert turn.text == "pong" and turn.stop_reason == "end_turn"
        assert bodies[0][0] == "Bearer tok" and bodies[0][1]["messages"][0]["role"] == "system"
        assert agents.list_models("custom", s) == ["a", "b"]
    finally:
        server.shutdown()


@pytest.mark.skipif(sys.version_info < (3, 10), reason="the anthropic SDK needs Python 3.10+")
def test_claude_through_the_sdk(monkeypatch):
    pytest.importorskip("anthropic")
    seen = []
    events = [
        ("message_start", {"type": "message_start", "message": {"id": "m", "type": "message", "role": "assistant",
                                                               "model": "claude-opus-5-5", "content": [],
                                                               "stop_reason": None, "usage": {"input_tokens": 9,
                                                                                              "output_tokens": 1}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hola"}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("content_block_start", {"type": "content_block_start", "index": 1, "content_block": {
            "type": "tool_use", "id": "tu1", "name": "get_document", "input": {}}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 1, "delta": {
            "type": "input_json_delta", "partial_json": "{}"}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 1}),
        ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 4}}),
        ("message_stop", {"type": "message_stop"}),
    ]

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append((self.path, {k.lower(): v for k, v in self.headers.items()}, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for name, data in events:
                self.wfile.write(f"event: {name}\ndata: {json.dumps(data)}\n\n".encode())

        def log_message(self, *a):
            pass

    server, url = _serve(Handler)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", url)
    try:
        agents.set_key("anthropic", "sk-ant-test")
        deltas = []
        tools = [llm.ToolSpec("get_document", "Reads.", {"type": "object", "properties": {}, "required": []})]
        turn = agents.stream_turn("anthropic:claude-opus-5-5", "sys", [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
                                  tools, settings=providers.AgentSettings(effort="xhigh", fast=True),
                                  on_event=lambda k, t: deltas.append((k, t)))
    finally:
        server.shutdown()
    path, headers, body = seen[0]
    assert path.startswith("/v1/messages") and headers["x-api-key"] == "sk-ant-test"
    assert "server-side-fallback-2026-07-01" in headers.get("anthropic-beta", "") and body["fallbacks"] == "default"
    assert body["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert body["output_config"] == {"effort": "xhigh"} and body["tools"][0]["eager_input_streaming"] is True
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert body["speed"] == "fast" and "fast-mode-2026-02-01" in headers.get("anthropic-beta", "")
    assert deltas == [("text", "Hola")]
    assert turn.stop_reason == "tool_use" and turn.tool_uses[0]["name"] == "get_document"
    assert turn.usage["output"] == 4


# -- browser sign-in ---------------------------------------------------------------------------------------

def test_pkce_and_the_openrouter_browser_flow():
    import base64
    import hashlib

    verifier, challenge = login.pkce_pair()
    assert base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode() == challenge

    def browser(url):  # the provider redirects back to the local callback with a code
        query = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
        callback = urllib.request.unquote(query["callback_url"])
        assert callback.startswith("http://localhost:") and query["code_challenge_method"] == "S256"
        local = callback.replace("localhost", "127.0.0.1")

        def visit():
            # A request to another path (a forged callback, the favicon) neither signs in nor cancels.
            for wrong in (local.rsplit("/", 1)[0] + "/guess?code=evil", local.split("/callback")[0] + "/favicon.ico"):
                with pytest.raises(urllib.error.HTTPError):
                    urllib.request.urlopen(wrong)
            urllib.request.urlopen(local + "?code=abc")

        threading.Thread(target=visit, daemon=True).start()

    posted = {}
    key = login.openrouter_login(open_url=browser, post=lambda url, data: posted.update(data) or {"key": "sk-or-1"},
                                 timeout=10)
    assert key == "sk-or-1" and posted["code"] == "abc" and posted["code_verifier"]


def test_ant_cli_sign_in(monkeypatch, tmp_path):
    monkeypatch.setattr(login, "ant_path", lambda: None)
    with pytest.raises(login.LoginError):
        login.ant_login()
    monkeypatch.setattr(login, "ant_path", lambda: "/usr/bin/ant")
    calls = []

    class Done:
        returncode, stdout, stderr = 0, "", ""

    login.ant_login(run=lambda args, **kw: calls.append(args) or Done())
    assert calls == [["/usr/bin/ant", "auth", "login"]]
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", str(tmp_path))
    assert not login.ant_signed_in()
    (tmp_path / "credentials").mkdir()
    (tmp_path / "credentials" / "default.json").write_text("{}")
    assert login.ant_signed_in() and providers.credential_source("anthropic") == "ant"


# -- the Agent panel ---------------------------------------------------------------------------------------

def _drain(d, limit=2000):
    for _ in range(limit):
        d.agent.poll()
        if not d.agent.active:
            return
        threading.Event().wait(0.005)
    raise AssertionError("the agent did not finish")


def test_agent_panel_builds_a_form_and_can_reject_it(tmp_path):
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    stream = scripted(
        [{"type": "tool_use", "id": "1", "name": "get_document", "input": {}},
         {"type": "tool_use", "id": "2", "name": "add_control", "input": {
             "type": "button", "name": "send", "x": 16, "y": 60, "props": {"text": "Send"}}}],
        [{"type": "tool_use", "id": "3", "name": "wire_event", "input": {"control": "send", "event": "click"}}],
        [{"type": "tool_use", "id": "4", "name": "set_handler", "input": {
            "handler": "send_click", "code": "def send_click(form, event):\n    form.send.text = 'Sent'\n"}}],
        [{"type": "text", "text": "Added a **Send** button."}],
    )
    d = Designer()
    d.agent = AgentController(d, store=agents.ThreadStore(tmp_path), stream=stream)
    d.agent.settings.model = "ollama:llama3"  # no key needed
    d.agent.thread.model = "ollama:llama3"
    d.layout.show("agent")
    d.agent.send("Add a send button")
    assert d.agent.running
    d.view()  # draws while it works
    _drain(d)
    send = d.doc.form.get("send")
    assert send is not None and send.props["text"] == "Send" and send.events == {"click": "send_click"}
    assert "form.send.text = 'Sent'" in d.doc.code
    assert "<context>" in stream.calls[0]["messages"][0]["content"][1]["text"]
    assert d.agent.changed and d.agent.store.list()[0].id == d.agent.thread.id
    d.view()
    d.agent.reject()
    assert d.doc.form.get("send") is None and "send_click" not in d.doc.code


def test_agent_panel_asks_before_creating_files(tmp_path, monkeypatch):
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    monkeypatch.chdir(tmp_path)
    stream = scripted(
        [{"type": "tool_use", "id": "1", "name": "new_document", "input": {"kind": "component", "name": "user card"}}],
        [{"type": "text", "text": "Done"}],
    )
    d = Designer()
    d.agent = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"), stream=stream)
    d.agent.thread.model = "ollama:llama3"
    d.agent.send("Make a user card")
    for _ in range(400):
        d.agent.poll()
        if d.agent.pending is not None:
            break
        threading.Event().wait(0.005)
    assert d.agent.pending is not None and d.agent.pending.tool.name == "new_document"
    d.view()
    d.agent.answer(True)
    _drain(d)
    assert (tmp_path / "user_card.pzcomp").exists() and d.doc.display_name == "user_card.pzcomp"


def test_inline_assist_rewrites_the_open_code(tmp_path):
    from pyzed.designer.agent_panel import AgentController, extract_code
    from pyzed.designer.app import Designer

    assert extract_code("Sure:\n```python\nx = 1\n```\n") == "x = 1\n"
    assert extract_code("y = 2") == "y = 2\n" and extract_code("``` broken") is None
    d = Designer()
    d.doc.add("button", 10, 10)
    d.open_default_event("button1")
    before = d.editing[1]
    new = "def button1_click(form, event):\n    print('hi')\n"
    d.agent = AgentController(d, store=agents.ThreadStore(tmp_path),
                              stream=scripted([{"type": "text", "text": f"```python\n{new}```"}]))
    d.agent.thread.model = "ollama:llama3"
    d.agent.open_inline()
    d.agent.set_inline("print hi")
    d.agent.submit_inline()
    d.view()
    _drain(d)
    assert d.editing[1] == new
    d.view()
    d.agent.undo_inline()
    assert d.editing[1] == before and d.agent.inline is None


def test_agent_texts_are_translated():
    import ast
    from pathlib import Path

    from pyzed.designer import agent_panel, agent_tools, commands, locale

    keys = set(locale._ES)
    for module in (agent_panel, agent_tools):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "tr" and node.args \
                    and isinstance(node.args[0], ast.Constant):
                assert node.args[0].value in keys, node.args[0].value
            if isinstance(node, ast.keyword) and node.arg == "title" and isinstance(node.value, ast.Constant) \
                    and module is agent_tools:
                assert node.value.value in keys, node.value.value
    for action in commands.ACTIONS:
        if action.id.startswith(("agent", "generate", "inline")):
            assert action.text in keys
    for text in (*agents.PROFILES.values(), *(p.description for p in agents.PROVIDERS.values())):
        assert text in keys


# -- signing in without other programs, every provider, Zed-like composer ---------------------------------

def test_copied_keys_are_recognised_per_provider():
    assert providers.looks_like_key("anthropic", "sk-ant-api03-" + "a" * 40)
    assert not providers.looks_like_key("openai", "sk-ant-api03-" + "a" * 40)
    assert providers.looks_like_key("openai", "sk-proj-" + "b" * 40)
    assert providers.looks_like_key("google", "AIza" + "c" * 35)
    assert providers.looks_like_key("openrouter", "sk-or-v1-" + "d" * 40)
    assert not providers.looks_like_key("anthropic", "just some copied text, not a key at all")
    assert not providers.looks_like_key("anthropic", "sk-ant-short")
    assert {"anthropic", "openai", "google", "openrouter", "xai", "mistral", "deepseek", "groq", "ollama"} \
        <= set(providers.PROVIDERS)
    assert all(p.login in ("browser", "oauth", "device", "google") for p in providers.PROVIDERS.values() if p.needs_key)
    with pytest.raises(login.LoginError):
        login.login("anthropic")  # Anthropic signs in by copying a key, never through a CLI
    opened = []
    assert login.key_page("anthropic", open_url=opened.append) == opened[0] and "anthropic" in opened[0]


def test_permission_modes_map_to_the_settings():
    s = providers.AgentSettings()
    assert s.mode == "ask"
    for mode in providers.MODES:
        s.mode = mode
        assert s.mode == mode
        assert providers.AgentSettings.from_dict(s.to_dict()).mode == mode


def _until(check, d, limit=2000, commands=None):
    for _ in range(limit):
        command = d.agent.poll()
        if commands is not None and command is not None:
            commands.append(repr(command))
        if check():
            return
        threading.Event().wait(0.005)
    raise AssertionError("timed out")


def test_signing_in_by_copying_a_key(tmp_path, monkeypatch, keychain):
    from pyzed.designer import agent_panel
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    opened = []

    def fake_portal(pid, check, cancelled=lambda: False, **kw):  # the page waits until the clipboard wins
        opened.append(pid)
        while not cancelled():
            time.sleep(0.01)

    monkeypatch.setattr(login, "key_portal", fake_portal)
    checked = []

    def fake_models(pid, settings=None, key=None):
        checked.append(key)
        if key.endswith("bad"):
            raise agents.AgentError("401")
        return ["claude-opus-5-5", "claude-sonnet-5-5"]

    monkeypatch.setattr(agent_panel._agents, "list_models", fake_models)
    monkeypatch.setattr(providers, "config_path", lambda: tmp_path / "agents.json")
    d = Designer()
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"))
    assert not c.ready
    d.view()  # the empty panel offers every main provider
    c.connect("anthropic")
    _until(lambda: opened, d)
    assert opened == ["anthropic"] and c.capture is not None and c.active and c.view == "settings"
    d.view()
    c.capture.next_check = 0
    assert c.poll() is not None  # reads the clipboard about once a second
    c.on_clipboard("hello")  # not a key: ignored
    assert not checked
    c.on_clipboard("sk-ant-api03-" + "x" * 40 + "bad")
    _until(lambda: c.busy_provider is None, d)
    assert c.capture is not None and not providers.is_ready("anthropic")  # refused: still waiting
    key = "sk-ant-api03-" + "y" * 40
    c.on_clipboard(key)
    commands = []
    _until(lambda: c.capture is None, d, commands=commands)
    assert providers.api_key("anthropic") == key and c.ready and len(checked) == 2
    assert key in keychain.data.values() and key not in (tmp_path / "agents.json").read_text()
    assert c.settings.models_of("anthropic")[:2] == ["claude-opus-5-5", "claude-sonnet-5-5"]
    assert "window operation" in commands[-1] and not c.raise_window  # the designer comes back to the front


def test_signing_in_on_the_local_page_brings_the_designer_back(tmp_path, monkeypatch, keychain):
    from pyzed.designer import agent_panel
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    key = "sk-ant-api03-" + "z" * 40

    def fake_portal(pid, check, **kw):
        assert check("sk-ant-api03-" + "x" * 40 + "bad") == "401"
        assert check(key) is None
        return key

    def fake_models(pid, settings=None, key=None):
        if key.endswith("bad"):
            raise agents.AgentError("401")
        return ["claude-opus-5-5"]

    monkeypatch.setattr(login, "key_portal", fake_portal)
    monkeypatch.setattr(agent_panel._agents, "list_models", fake_models)
    monkeypatch.setattr(providers, "config_path", lambda: tmp_path / "agents.json")
    d = Designer()
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"))
    c.sign_in("anthropic")
    commands = []
    _until(lambda: c.capture is None, d, commands=commands)
    assert providers.api_key("anthropic") == key and c.settings.models_of("anthropic")[0] == "claude-opus-5-5"
    assert commands == ["Command.<window operation>(...)"] and not c.active  # back to the front, once


def _portal_request(url, method="GET", data=None, headers=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # straight to 127.0.0.1
    try:
        with opener.open(req, timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, ""
    except OSError as err:  # a reset connection fails this request, not the whole sign-in
        return None, str(err)


def test_the_local_sign_in_page_takes_a_key_only_from_itself():
    import urllib.parse

    key = "sk-ant-api03-" + "k" * 40
    seen, visits = {}, []

    def browser(url):
        def visit():
            parts = urllib.parse.urlsplit(url)
            origin = f"{parts.scheme}://{parts.netloc}"
            post = lambda k, **h: _portal_request(url, "POST", urllib.parse.urlencode({"key": k}).encode(), h)
            seen["get"] = _portal_request(url)
            seen["other path"] = _portal_request(origin + "/connect/guess")
            seen["no origin"] = post(key)
            seen["other site"] = post(key, Origin="https://evil.example")
            seen["rebinding"] = post(key, Origin=origin, Host="evil.example")
            seen["not a key"] = post("hello", Origin=origin)
            seen["refused"] = post(key + "bad", Origin=origin)
            seen["ok"] = post(key, Origin=origin)

        visits.append(threading.Thread(target=visit, daemon=True))
        visits[0].start()

    check = lambda k: "401 invalid key" if k.endswith("bad") else None
    assert login.key_portal("anthropic", check, open_url=browser, timeout=20) == key
    visits[0].join(5)
    status, page = seen["get"]
    assert status == 200 and "console.anthropic.com" in page and 'type="password"' in page
    assert seen["other path"][0] == seen["no origin"][0] == seen["other site"][0] == seen["rebinding"][0] == 404
    assert "does not look like" in seen["not a key"][1] and "401 invalid key" in seen["refused"][1]
    assert seen["ok"][0] == 200 and "is connected" in seen["ok"][1] and key not in seen["ok"][1]
    with pytest.raises(login.LoginError):
        login.key_portal("anthropic", check, open_url=lambda url: None, timeout=0.2)
    assert login.key_portal("anthropic", check, open_url=lambda url: None, cancelled=lambda: True) is None


def test_composer_mentions_commands_menus_and_expand(tmp_path):
    from pyzed.designer.agent_panel import AgentController, model_label
    from pyzed.designer.app import Designer

    stream = scripted([{"type": "text", "text": "Looked at it."}])
    d = Designer()
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path), stream=stream)
    c.thread.model = c.settings.model = "ollama:llama3"
    assert model_label("anthropic:claude-opus-5-5") == "Opus 5.5" and model_label("ollama:qwen3:8b") == "qwen3:8b"
    c.set_input("/ex")
    assert c.trigger() == ("slash", "ex") and [i[1] for i in c.popup_items()] == ["/explain"]
    c.set_input("Look at @co")
    assert c.trigger() == ("mention", "co")
    labels = [i[1] for i in c.popup_items()]
    assert "code" in labels
    d.view()
    c.send()  # Enter with the popup open picks its first row
    assert c.input.endswith("@code ") and c.mentions[0].kind == "code" and c.trigger() is None
    c.set_input(c.input + "and explain it")
    for name in ("mode", "model", "effort"):
        c.toggle_menu(name)
        d.view()
    c.set_mode("read")
    assert c.settings.profile == "ask" and c.menu is None
    c.toggle_fast()
    assert c.settings.fast
    c.toggle_expand()
    assert c.expanded
    d.view()
    c.toggle_expand()
    assert not c.expanded
    c.send()
    _drain(d)
    sent = stream.calls[0]["messages"][0]["content"]
    assert any(b["text"].startswith("<context>@code (code):") for b in sent)
    assert not c.mentions
    c.set_input("/new")
    c.send()
    assert not c.thread.messages
