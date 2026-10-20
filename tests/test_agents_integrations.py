"""AI agents: images, MCP servers, external agents (ACP), GitHub and Google sign-in, workload identity
federation, and how the Agent panel uses them (multi-line box, attachments, settings, building apps)."""

import base64
import http.server
import json
import os
import sys
import textwrap
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from pyzed import agents
from pyzed.agents import acp, llm, login, mcp_client, providers, secrets

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


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
def keychain(monkeypatch, tmp_path):
    for name in ("ANTHROPIC_API_KEY", "GITHUB_TOKEN", "ANTHROPIC_FEDERATION_RULE_ID", "ANTHROPIC_ORGANIZATION_ID",
                 "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT", "PYZED_GITHUB_CLIENT_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", "/nonexistent-ant-config")
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(tmp_path / "no-gcloud"))
    monkeypatch.setattr(providers, "_last", None)
    fake = FakeKeyring()
    secrets.use(secrets.SecretStore(fake))
    yield fake
    secrets.use(secrets.SecretStore(None))


def scripted(*turns):
    calls = []

    def stream(model, system, messages, tools, *, settings, on_event, cancel):
        calls.append({"model": model, "messages": json.loads(json.dumps(messages)), "tools": [t.name for t in tools]})
        blocks = turns[min(len(calls) - 1, len(turns) - 1)]
        for b in blocks:
            if b["type"] == "text":
                on_event("text", b["text"])
        return llm.Turn(blocks, "tool_use" if any(b["type"] == "tool_use" for b in blocks) else "end_turn")

    stream.calls = calls
    return stream


# -- images ------------------------------------------------------------------------------------------------

def test_images_in_messages_and_tool_results():
    image = agents.Image(PNG)
    assert image.type == "image/png" and agents.Image(b"\xff\xd8\xff\xe0rest").type == "image/jpeg"
    with pytest.raises(ValueError):
        agents.Image(b"not an image").type
    block = agents.image_block(PNG)
    assert block["type"] == "image" and base64.b64decode(block["source"]["data"]) == PNG

    @agents.tool
    def look() -> list:
        """Takes a picture."""
        return ["The picture.", agents.Image(PNG)]

    stream = scripted([{"type": "tool_use", "id": "1", "name": "look", "input": {}}], [{"type": "text", "text": "Ok"}])
    agent = agents.Agent("x", tools=[look], stream=stream, settings=providers.AgentSettings())
    agent.run([{"type": "text", "text": "Look"}, block])
    result = stream.calls[1]["messages"][2]["content"][0]
    assert result["type"] == "tool_result" and result["content"][0] == {"type": "text", "text": "The picture."}
    assert result["content"][1]["type"] == "image"
    # OpenAI-compatible servers get the images as image_url parts (tool messages carry text only)
    converted = llm._openai_messages("sys", stream.calls[1]["messages"])
    assert converted[1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert converted[3] == {"role": "tool", "tool_call_id": "1", "content": "The picture."}
    assert converted[4]["role"] == "user" and converted[4]["content"][1]["type"] == "image_url"
    assert llm._anthropic_messages(stream.calls[1]["messages"])[0]["content"][1]["type"] == "image"


def test_validation_accepts_union_types_and_open_schemas():
    tool = agents.Tool("t", "", {"type": "object", "properties": {"a": {"type": ["string", "null"]},
                                                                 "n": {"type": "integer"}}, "required": []}, print)
    assert tool.validate({"a": "x"}) is None and tool.validate({"a": None}) is None
    assert "must be of type" in tool.validate({"a": 3}) and "must be of type" in tool.validate({"n": True})
    assert "unknown argument" in tool.validate({"b": 1})
    open_ = agents.Tool("t", "", {"type": "object", "properties": {}, "additionalProperties": True}, print)
    assert open_.validate({"anything": 1}) is None


# -- MCP servers ---------------------------------------------------------------------------------------------

MCP_SERVER = textwrap.dedent('''
    import json, os, sys
    for line in sys.stdin:
        msg = json.loads(line)
        if "id" not in msg:
            continue
        method, ident = msg["method"], msg["id"]
        if method == "initialize":
            result = {"protocolVersion": msg["params"]["protocolVersion"], "capabilities": {"tools": {}},
                      "serverInfo": {"name": "fake", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": [
                {"name": "echo", "description": "Echoes.", "annotations": {"readOnlyHint": True},
                 "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
                {"name": "secret", "description": "Tells the token.", "inputSchema": {"type": "object"}},
                {"name": "fail", "description": "Fails.", "inputSchema": {"type": "object"}}]}
        elif method == "tools/call":
            name, args = msg["params"]["name"], msg["params"]["arguments"]
            if name == "echo":
                result = {"content": [{"type": "text", "text": args["text"].upper()}]}
            elif name == "secret":
                result = {"content": [{"type": "text", "text": os.environ.get("TOKEN", "")}]}
            else:
                result = {"content": [{"type": "text", "text": "it broke"}], "isError": True}
        else:
            print(json.dumps({"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": "no"}}), flush=True)
            continue
        print(json.dumps({"jsonrpc": "2.0", "id": ident, "result": result}), flush=True)
''')


def test_mcp_server_tools_over_stdio(tmp_path, keychain):
    script = tmp_path / "server.py"
    script.write_text(MCP_SERVER)
    config = providers.MCPServerConfig("fake", sys.executable, [str(script)], secret_names=["TOKEN"])
    assert mcp_client.set_secrets("fake", {"TOKEN": "s3cret"}) is True
    assert "s3cret" in keychain.data[("pyzed", "agents.mcp.fake")]
    servers = mcp_client.Servers([config], cwd=str(tmp_path))
    try:
        tools = {t.name: t for t in servers.tools()}
        assert set(tools) == {"mcp_fake_echo", "mcp_fake_secret", "mcp_fake_fail"}
        assert not tools["mcp_fake_echo"].writes and tools["mcp_fake_secret"].writes
        assert tools["mcp_fake_echo"].func(text="hi") == "HI"
        assert tools["mcp_fake_secret"].func() == "s3cret"  # the secret reached the server's environment
        with pytest.raises(RuntimeError, match="it broke"):
            tools["mcp_fake_fail"].func()
        # in an agent: read-only tools run, the others ask first
        stream = scripted([{"type": "tool_use", "id": "1", "name": "mcp_fake_echo", "input": {"text": "x"}},
                           {"type": "tool_use", "id": "2", "name": "mcp_fake_secret", "input": {}}],
                          [{"type": "text", "text": "done"}])
        agent = agents.Agent("x", tools=list(tools.values()), stream=stream, settings=providers.AgentSettings())
        agent.run("go")
        results = stream.calls[1]["messages"][2]["content"]
        assert results[0]["content"] == "X" and results[1]["is_error"]
    finally:
        servers.close()
    # settings keep the server, never its secrets
    s = providers.AgentSettings(mcp_servers=[config])
    data = json.dumps(s.to_dict())
    assert "s3cret" not in data and providers.AgentSettings.from_dict(json.loads(data)).mcp_servers == [config]


def test_a_server_that_does_not_start_is_reported(tmp_path):
    servers = mcp_client.Servers([providers.MCPServerConfig("ghost", str(tmp_path / "missing-program"))])
    failed = []
    assert servers.tools(lambda name, why: failed.append(name)) == [] and failed == ["ghost"]
    assert "ghost" in servers.errors


def test_mcp_server_over_http():
    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            msg = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append((msg.get("method"), self.headers.get("Authorization"), self.headers.get("Mcp-Session-Id")))
            if "id" not in msg:
                self.send_response(202)
                self.end_headers()
                return
            result = {"tools": [{"name": "ping", "inputSchema": {"type": "object"}}]} \
                if msg["method"] == "tools/list" else {"protocolVersion": "2025-06-18", "capabilities": {}}
            if msg["method"] == "tools/call":
                result = {"content": [{"type": "text", "text": "pong"}]}
            body = json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result})
            self.send_response(200)
            self.send_header("Mcp-Session-Id", "abc")
            if msg["method"] == "tools/call":  # answered as an event stream
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.write(f"event: message\ndata: {body}\n\n".encode())
            else:
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body.encode())

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        mcp_client.set_secrets("remote", {"Authorization": "Bearer t0k"})
        servers = mcp_client.Servers([providers.MCPServerConfig(
            "remote", url=f"http://127.0.0.1:{server.server_address[1]}/mcp")])
        tool, = servers.tools()
        assert tool.func() == "pong"
    finally:
        server.shutdown()
    assert seen[0] == ("initialize", "Bearer t0k", None) and seen[-1][2] == "abc"


# -- external agents (ACP) ----------------------------------------------------------------------------------

ACP_AGENT = textwrap.dedent('''
    import json, sys, threading
    pending = {}
    next_id = [100]

    def send(msg):
        print(json.dumps(msg), flush=True)

    def request(method, params):
        next_id[0] += 1
        ident = next_id[0]
        event = threading.Event()
        pending[ident] = [event, None]
        send({"jsonrpc": "2.0", "id": ident, "method": method, "params": params})
        event.wait(10)
        return pending.pop(ident)[1]

    def update(session, body):
        send({"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": session, "update": body}})

    def prompt(ident, params):
        s = params["sessionId"]
        text = params["prompt"][0]["text"]
        update(s, {"sessionUpdate": "agent_thought_chunk", "content": {"type": "text", "text": "Thinking"}})
        update(s, {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "Reading. "}})
        update(s, {"sessionUpdate": "tool_call", "toolCallId": "c1", "title": "Read notes.txt", "kind": "read",
                   "status": "pending", "rawInput": {"path": "notes.txt"}})
        read = request("fs/read_text_file", {"sessionId": s, "path": "notes.txt"})
        update(s, {"sessionUpdate": "tool_call_update", "toolCallId": "c1", "status": "completed",
                   "content": [{"type": "content", "content": {"type": "text", "text": read["result"]["content"]}}]})
        secret = request("fs/read_text_file", {"sessionId": s, "path": ".env"})
        update(s, {"sessionUpdate": "tool_call", "toolCallId": "c2", "title": "Write out.txt", "kind": "edit",
                   "status": "pending"})
        answer = request("session/request_permission", {"sessionId": s, "toolCall": {"toolCallId": "c2"}, "options": [
            {"optionId": "yes", "name": "Allow", "kind": "allow_once"},
            {"optionId": "no", "name": "Reject", "kind": "reject_once"}]})
        chosen = answer["result"]["outcome"].get("optionId")
        if chosen == "yes":
            request("fs/write_text_file", {"sessionId": s, "path": "out.txt", "content": text})
        update(s, {"sessionUpdate": "tool_call_update", "toolCallId": "c2",
                   "status": "completed" if chosen == "yes" else "failed"})
        update(s, {"sessionUpdate": "agent_message_chunk", "content": {"type": "text",
                   "text": "Done: " + chosen + (" (no secrets)" if "error" in secret else "")}})
        send({"jsonrpc": "2.0", "id": ident, "result": {"stopReason": "end_turn"}})

    for line in sys.stdin:
        msg = json.loads(line)
        if "method" not in msg:
            pending[msg["id"]][1] = msg
            pending[msg["id"]][0].set()
            continue
        method, ident, params = msg["method"], msg.get("id"), msg.get("params") or {}
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": ident, "result": {"protocolVersion": 1, "agentCapabilities": {
                "promptCapabilities": {"image": True}}, "authMethods": []}})
        elif method == "session/new":
            servers = [s["name"] for s in params["mcpServers"]]
            send({"jsonrpc": "2.0", "id": ident, "result": {"sessionId": "s-" + ",".join(servers)}})
        elif method == "session/prompt":
            threading.Thread(target=prompt, args=(ident, params)).start()
''')


def test_external_agent_through_acp(tmp_path):
    script = tmp_path / "agent.py"
    script.write_text(ACP_AGENT)
    (tmp_path / "notes.txt").write_text("buy milk")
    (tmp_path / ".env").write_text("SECRET=1")
    config = providers.ACPAgentConfig("fake", sys.executable, [str(script)], title="Fake agent")
    asked = []
    settings = providers.AgentSettings()
    agent = acp.ACPAgent(config, cwd=tmp_path, settings=settings, mcp_servers=[{"name": "pyzed", "command": "x",
                                                                                 "args": [], "env": []}],
                         confirm=lambda tool, args: asked.append(tool.title) or True)
    events = []
    try:
        answer = agent.run("hello", on_event=events.append)
        assert agent.session == "s-pyzed"  # Pyzed's MCP server was handed to the agent
        assert answer.startswith("Reading. ") or "Done: yes" in answer
        assert (tmp_path / "out.txt").read_text() == "hello" and asked == ["Write out.txt"]
        kinds = [e.kind for e in events]
        assert kinds[0] == "thinking" and "tool_call" in kinds and "tool_result" in kinds and kinds[-1] == "done"
        written = [e for e in events if e.kind == "file"]  # the panel follows it and shows it live
        assert written and written[0].args["written"] and written[0].text == str(tmp_path / "out.txt")
        texts = [b["text"] for m in agent.messages if m["role"] == "assistant" for b in m["content"]
                 if b["type"] == "text"]
        assert texts[0] == "Reading. " and texts[-1] == "Done: yes (no secrets)"
        results = [b for m in agent.messages if m["role"] == "user" for b in m["content"] if b["type"] == "tool_result"]
        assert results[0]["content"] == "buy milk"
        # read-only mode: the agent's edits are refused without asking
        settings.mode = "read"
        (tmp_path / "out.txt").unlink()
        agent.run("again", on_event=events.append)
        assert not (tmp_path / "out.txt").exists() and asked == ["Write out.txt"]
        assert agent.messages[-1]["role"] == "assistant" or agent.messages[-2]["role"] == "assistant"
    finally:
        agent.close()
    # other models get the external agent's conversation as text only
    for m in llm._anthropic_messages(agent.messages):
        assert all(b["type"] == "text" for b in m["content"])


def test_acp_presets_and_a_missing_program(tmp_path):
    claude = acp.preset("claude-code")
    assert claude.label == "Claude Code" and claude.command == "npx"
    missing = providers.ACPAgentConfig("ghost", str(tmp_path / "nope"))
    assert not acp.installed(missing)
    events = []
    acp.ACPAgent(missing, cwd=tmp_path, mcp_servers=[]).run("hi", on_event=events.append)
    assert events[-2].kind == "error" and "Could not start" in events[-2].text


# -- GitHub and Google sign-in ------------------------------------------------------------------------------

def test_github_device_flow(keychain):
    with pytest.raises(login.LoginError, match="GitHub App"):
        login.github_device_code("")
    answers = iter([{"error": "authorization_pending"}, {"error": "slow_down", "interval": 0},
                    {"access_token": "ghu_abc", "refresh_token": "ghr_x", "expires_in": 28800}])
    posted = []

    def post(url, data):
        posted.append((url, data))
        if url == login.GITHUB_DEVICE:
            return {"device_code": "dc", "user_code": "ABCD-1234", "verification_uri": "https://github.com/login/device",
                    "interval": 0, "expires_in": 60}
        return next(answers)

    code = login.github_device_code("Iv23client", post=post)
    assert code.user_code == "ABCD-1234"
    token = login.github_device_token("Iv23client", code, post=post, sleep=lambda s: None)
    assert token["access_token"] == "ghu_abc" and token["refresh_token"] == "ghr_x" and token["expires_at"] > time.time()
    assert posted[1][1]["grant_type"] == "urn:ietf:params:oauth:grant-type:device_code"
    providers.save_token("github", token)
    assert providers.credential_source("github") == "oauth" and providers.api_key("github") == "ghu_abc"
    with pytest.raises(login.LoginError, match="declined"):
        login.github_device_token("Iv23client", code, post=lambda u, d: {"error": "access_denied"},
                                  sleep=lambda s: None)


def test_expired_tokens_are_refreshed(keychain, monkeypatch):
    providers.save_token("vertex", {"access_token": "old", "refresh_token": "r1", "expires_at": time.time() - 10})
    calls = []

    def refresh(pid, token, settings, **kw):
        calls.append((pid, token["refresh_token"]))
        return {"access_token": "new", "refresh_token": "r1", "expires_at": time.time() + 3600}

    monkeypatch.setattr(login, "refresh", refresh)
    assert providers.api_key("vertex") == "new" and calls == [("vertex", "r1")]
    assert json.loads(keychain.data[("pyzed", "agents.vertex")])["access_token"] == "new"
    assert providers.api_key("vertex") == "new" and len(calls) == 1  # still valid: no second refresh


def test_google_sign_in_and_vertex(monkeypatch, tmp_path):
    def browser(url):
        query = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
        callback = urllib.request.unquote(query["redirect_uri"])
        assert callback.startswith("http://127.0.0.1:") and query["access_type"] == "offline"
        threading.Thread(target=lambda: urllib.request.urlopen(callback + "?code=g0"), daemon=True).start()

    posted = {}
    token = login.google_login("cid.apps.googleusercontent.com", "sec", open_url=browser, timeout=10,
                               post=lambda u, d: posted.update(d) or {"access_token": "ya29", "expires_in": 3599,
                                                                      "refresh_token": "1//r"})
    assert token["refresh_token"] == "1//r" and posted["code"] == "g0" and posted["code_verifier"]
    assert posted["client_secret"] == "sec" and posted["grant_type"] == "authorization_code"
    s = providers.AgentSettings()
    assert s.base_url("vertex") == ""  # no project yet
    s.provider("vertex").project = "my-proj"
    assert s.base_url("vertex") == \
        "https://aiplatform.googleapis.com/v1/projects/my-proj/locations/global/endpoints/openapi"
    s.provider("vertex").location = "us-central1"
    assert s.base_url("vertex").startswith("https://us-central1-aiplatform.googleapis.com/")
    # the Google Cloud credentials of this computer (gcloud auth application-default login)
    folder = tmp_path / "no-gcloud"
    folder.mkdir()
    (folder / "application_default_credentials.json").write_text(json.dumps({
        "type": "authorized_user", "client_id": "c", "client_secret": "s", "refresh_token": "r",
        "quota_project_id": "adc-proj"}))
    assert providers.credential_source("vertex") == "gcloud" and providers.google_project() == "adc-proj"
    monkeypatch.setitem(sys.modules, "google", None)  # no google-auth: refreshed by hand
    login._default_token.clear()
    token = login.google_default_token(post=lambda u, d: {"access_token": "ya29.adc", "expires_in": 3600})
    assert token == "ya29.adc"


# -- workload identity federation ---------------------------------------------------------------------------

def test_claude_with_workload_identity_federation(tmp_path):
    anthropic = pytest.importorskip("anthropic")
    try:
        from anthropic.lib.credentials import WorkloadIdentityCredentials  # noqa: F401
    except ImportError:
        pytest.skip("this anthropic version has no workload identity federation")
    jwt = tmp_path / "token.jwt"
    jwt.write_text("eyJ.fake.jwt")
    s = providers.AgentSettings()
    assert providers.credential_source("anthropic", settings=s) == ""
    s.federation = providers.FederationSettings(rule_id="fdrl_1", organization_id="00000000-0000-0000-0000-000000000000",
                                                token_file=str(jwt))
    assert s.federation.enabled and providers.credential_source("anthropic", settings=s) == "federation"
    assert llm._credential("anthropic", s) is None  # no key is sent
    client = llm._anthropic_client("anthropic", s, None)
    assert isinstance(client, anthropic.Anthropic) and client is llm._anthropic_client("anthropic", s, None)
    back = providers.AgentSettings.from_dict(json.loads(json.dumps(s.to_dict())))
    assert back.federation == s.federation
    # a token printed by a command
    s.federation.token_source, s.federation.token_command = "command", f'"{sys.executable}" -c "print(123)"'
    assert llm._identity_token(s.federation)() == "123"


# -- the Agent panel ------------------------------------------------------------------------------------------

def _until(check, d, limit=3000):
    for _ in range(limit):
        d.agent.poll()
        if check():
            return
        threading.Event().wait(0.005)
    raise AssertionError("timed out")


def test_message_box_keys_attachments_and_images(tmp_path):
    from pyzed import _core
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    stream = scripted([{"type": "text", "text": "Nice picture."}])
    d = Designer()
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path), stream=stream)
    c.thread.model = c.settings.model = "ollama:llama3"
    d.layout.show("agent")
    c.set_input("first line\nsecond line")
    assert d.focus == "agent" and c.captured_keys() == ["enter"]
    d.view()
    c.set_input("@co")
    assert {"up", "down", "escape"} <= set(c.captured_keys())
    first = c.popup_items()[0][1]
    d.on_key("down")
    assert c.picked == 1
    d.on_key("escape")
    assert not c.popup_open and not c.popup_items()
    c.set_input("@cod")
    assert c.popup_open  # typing again shows it
    c.set_input("Look at this")
    assert first
    (tmp_path / "shot.png").write_bytes(PNG)
    (tmp_path / "bad.png").write_bytes(b"nope")
    c.on_picked([str(tmp_path / "shot.png"), str(tmp_path / "bad.png")])
    assert [a.name for a in c.attachments] == ["shot.png"]
    c.on_clipboard_image(PNG)
    c.on_clipboard_image(None)
    assert len(c.attachments) == 2
    assert isinstance(c.pick_images(), _core.Command) and isinstance(c.paste_image(), _core.Command)
    c.toggle_add_menu()
    d.view()
    c.close_menu()
    d.view()  # thumbnails in the composer
    result = d.on_key("enter")  # Enter sends
    assert isinstance(result, _core.Command) and c.running and not c.attachments
    _until(lambda: not c.running, d)
    sent = stream.calls[0]["messages"][0]["content"]
    assert sent[0]["text"] == "Look at this" and [b["type"] for b in sent].count("image") == 2
    d.view()  # the thread shows the pictures


def test_settings_add_mcp_servers_and_external_agents(tmp_path, monkeypatch, keychain):
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    script = tmp_path / "server.py"
    script.write_text(MCP_SERVER)
    monkeypatch.setattr(providers, "config_path", lambda: tmp_path / "agents.json")
    d = Designer()
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"))
    c.open_settings()
    d.view()
    c.new_server("mcp")
    c.set_draft("name", "fake server")
    c.set_draft("command", f'"{sys.executable}" "{script}"')
    c.set_draft("secrets", "TOKEN=abc; OTHER=2")
    d.view()
    c.save_draft()
    server = c.settings.mcp_server("fake-server")
    assert server is not None and server.command == sys.executable and server.secret_names == ["OTHER", "TOKEN"]
    assert "abc" not in (tmp_path / "agents.json").read_text()
    assert json.loads(keychain.data[("pyzed", "agents.mcp.fake-server")]) == {"TOKEN": "abc", "OTHER": "2"}
    _until(lambda: c.busy_provider is None, d)
    assert c.mcp_status["fake-server"] == "3 tools"
    c.edit_server("mcp", "fake-server")
    assert "TOKEN=abc" in c.server_draft["secrets"]
    c.cancel_draft()
    c.new_server("acp", "gemini")
    assert c.server_draft["command"] == "gemini --experimental-acp"
    c.save_draft()
    assert c.settings.acp_agent("gemini").args == ["--experimental-acp"] and "acp:gemini" in c.models()
    d.view()
    c.toggle_menu("model")
    d.view()  # the model menu lists the external agent
    c.set_model("acp:gemini")
    assert c.ready
    d.view()
    c.toggle_server("mcp", "fake-server")
    assert not c.settings.mcp_server("fake-server").enabled
    c.remove_server("acp", "gemini")
    assert c.settings.acp_agent("gemini") is None and c.thread.model == providers.DEFAULT_MODEL
    c.remove_server("mcp", "fake-server")
    assert ("pyzed", "agents.mcp.fake-server") not in keychain.data
    for pid in ("github", "vertex", "anthropic"):
        c.toggle_provider(pid)
        d.view()
    c.set_federation("rule_id", "fdrl_9")
    c.set_federation("organization_id", "org")
    assert providers.load(tmp_path / "agents.json").federation.rule_id == "fdrl_9"
    c.shutdown()


def test_the_agent_uses_mcp_tools_and_knows_the_project(tmp_path):
    from pyzed.designer import agent_tools
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    script = tmp_path / "server.py"
    script.write_text(MCP_SERVER)
    stream = scripted([{"type": "tool_use", "id": "1", "name": "mcp_fake_echo", "input": {"text": "hey"}},
                       {"type": "tool_use", "id": "2", "name": "get_project", "input": {}}],
                      [{"type": "text", "text": "Done."}])
    d = Designer()
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path), stream=stream)
    c.thread.model = c.settings.model = "ollama:llama3"
    c.settings.mcp_servers = [providers.MCPServerConfig("fake", sys.executable, [str(script)])]
    c.mcp.update(c.settings.mcp_servers)
    try:
        c.send("Use the server")
        _until(lambda: not c.running, d)
    finally:
        c.shutdown()
    call = stream.calls[0]
    assert "mcp_fake_echo" in call["tools"] and {"create_project", "screenshot_form", "list_examples",
                                                 "screenshot"} <= set(call["tools"])
    results = stream.calls[1]["messages"][2]["content"]
    assert results[0]["content"] == "HEY" and json.loads(results[1]["content"])["project"] is None
    prompt = agent_tools.system_prompt(d)
    assert "create_project" in prompt and "Pyzed Design" in prompt
    assert "No project is open" in agent_tools.context_note(d)


def test_slash_app_and_screenshot_mention(tmp_path, monkeypatch):
    from pyzed.designer import agent_tools
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    stream = scripted([{"type": "text", "text": "Seen."}])
    d = Designer()
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path), stream=stream)
    c.thread.model = c.settings.model = "ollama:llama3"
    c.set_input("/app")
    assert [i[1] for i in c.popup_items()] == ["/app"]
    c.send()
    assert c.input == "Create an application that "
    monkeypatch.setattr(agent_tools, "screenshot_job", lambda d: lambda: PNG)
    c.set_input("@screen")
    c.send()  # picks @screenshot
    assert c.mentions[0].kind == "screenshot"
    c.set_input(c.input + "how does it look?")
    c.send()
    _until(lambda: not c.running, d)
    sent = stream.calls[0]["messages"][0]["content"]
    assert any(b["type"] == "image" for b in sent)


def test_commands_are_split_like_the_platform_shell(monkeypatch):
    assert providers.split_command('npx -y "my server"') == ["npx", "-y", "my server"]
    monkeypatch.setattr(providers.os, "name", "nt")
    parts = providers.split_command(r'"C:\Program Files\Py\python.exe" -c "print(1)" C:\data')
    monkeypatch.undo()
    assert parts == [r"C:\Program Files\Py\python.exe", "-c", "print(1)", r"C:\data"]


def test_release_builds_bundle_the_oauth_apps(tmp_path, monkeypatch):
    import importlib.util
    import subprocess

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("build_designer", root / "scripts" / "build_designer.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    for name in ("PYZED_GITHUB_CLIENT_ID", "PYZED_GOOGLE_CLIENT_ID", "PYZED_GOOGLE_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    assert build.oauth_apps(tmp_path) is None
    monkeypatch.setenv("PYZED_GITHUB_CLIENT_ID", "Iv23-test")
    module = build.oauth_apps(tmp_path)
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(module.parent), os.environ.get("PYTHONPATH", "")])}
    env.pop("PYZED_GITHUB_CLIENT_ID")
    out = subprocess.run([sys.executable, "-c", "from pyzed.agents import providers as p; "
                          "print(p.GITHUB_CLIENT_ID, p.AgentSettings().client_id('github'), repr(p.GOOGLE_CLIENT_ID))"],
                         capture_output=True, text=True, env=env, check=True).stdout.split()
    assert out == ["Iv23-test", "Iv23-test", "''"]


def test_the_agent_plans_builds_and_runs_an_app_on_its_own(tmp_path):
    from pyzed.designer import agent_panel, agent_tools
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    plan = [{"step": "Build the form", "status": "done"}, {"step": "Run the app", "status": "in_progress"}]
    stream = scripted(
        [{"type": "tool_use", "id": "1", "name": "update_plan", "input": {"steps": plan}},
         {"type": "tool_use", "id": "2", "name": "add_control",
          "input": {"type": "button", "name": "send_button", "props": {"text": "Send"}}},
         {"type": "tool_use", "id": "3", "name": "set_code",
          "input": {"code": 'print("hello from the app")\n'}},
         {"type": "tool_use", "id": "4", "name": "save_document", "input": {}},
         {"type": "tool_use", "id": "5", "name": "run_app", "input": {}}],
        [{"type": "tool_use", "id": "6", "name": "update_plan",
          "input": {"steps": [dict(s, status="done") for s in plan]}}],
        [{"type": "text", "text": "The app runs."}])
    d = Designer(tmp_path / "main.pzform", language_servers=False)
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"), stream=stream)
    c.thread.model = c.settings.model = "ollama:llama3"
    c.settings.mode = "bypass"
    c.send("Build me an app")
    _until(lambda: agent_tools.plan_of(c.thread.messages) == plan, d)
    assert agent_panel._plan_card(c, d.theme) is not None  # shown while the agent works
    _until(lambda: not c.running, d, limit=20000)
    assert agent_tools.plan_of(c.thread.messages)[1]["status"] == "done"
    assert agent_panel._plan_card(c, d.theme) is None  # all done: folded away
    results = stream.calls[1]["messages"][2]["content"]
    run = results[4]
    assert not run.get("is_error"), run
    texts = [b["text"] for b in run["content"] if b["type"] == "text"]
    assert "main.pzform started" in texts[0] and "hello from the app" in texts[0]
    assert any(b["type"] == "image" for b in run["content"])
    prompt = agent_tools.system_prompt(d)
    assert "run_app" in prompt and "update_plan" in prompt


def test_run_app_reports_errors_and_plans_are_checked(tmp_path):
    from pyzed.designer import agent_tools
    from pyzed.designer.model import Form

    form = tmp_path / "broken.pzform"
    form.write_text(Form(name="broken").to_json())
    form.with_suffix(".py").write_text("raise RuntimeError('the backend is down')\n")
    result = agent_tools.run_form_check(form)
    assert isinstance(result, dict) and not result["ok"] and "the backend is down" in result["output"]
    with pytest.raises(ValueError):
        agent_tools._plan_steps([{"step": "x", "status": "maybe"}])
    with pytest.raises(ValueError):
        agent_tools._plan_steps([])
    assert agent_tools.plan_of([]) == []


EDITOR_AGENT = textwrap.dedent('''
    import json, sys, threading, urllib.request
    servers = {}

    def send(msg):
        print(json.dumps(msg), flush=True)

    def update(session, body):
        send({"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": session, "update": body}})

    def mcp(method, params, ident=1):
        server = servers["pyzed_editor"]
        headers = {h["name"]: h["value"] for h in server["headers"]}
        headers.update({"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
        body = json.dumps({"jsonrpc": "2.0", "id": ident, "method": method, "params": params}).encode()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(urllib.request.Request(server["url"], data=body, headers=headers), timeout=30) as r:
            return json.loads(r.read())

    def prompt(ident, params):
        s = params["sessionId"]
        update(s, {"sessionUpdate": "plan", "entries": [
            {"content": "Add the button", "status": "in_progress", "priority": "high"},
            {"content": "Check the form", "status": "pending", "priority": "medium"}]})
        info = mcp("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                  "clientInfo": {"name": "fake", "version": "1"}})
        names = [t["name"] for t in mcp("tools/list", {})["result"]["tools"]]
        update(s, {"sessionUpdate": "tool_call", "toolCallId": "c1", "title": "add_control", "kind": "other",
                   "status": "pending"})
        added = mcp("tools/call", {"name": "add_control", "arguments": {"type": "button", "name": "ok_button",
                                                                         "props": {"text": "OK"}}})
        update(s, {"sessionUpdate": "tool_call_update", "toolCallId": "c1", "status": "completed"})
        doc = mcp("tools/call", {"name": "get_document", "arguments": {}})["result"]["content"][0]["text"]
        update(s, {"sessionUpdate": "plan", "entries": [
            {"content": "Add the button", "status": "completed", "priority": "high"},
            {"content": "Check the form", "status": "completed", "priority": "medium"}]})
        report = {"instructions": "Pyzed Design" in info["result"].get("instructions", ""),
                  "tools": names, "added": not added["result"]["isError"], "seen": "ok_button" in doc}
        update(s, {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": json.dumps(report)}})
        send({"jsonrpc": "2.0", "id": ident, "result": {"stopReason": "end_turn"}})

    for line in sys.stdin:
        msg = json.loads(line)
        method, ident, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": ident, "result": {"protocolVersion": 1, "agentCapabilities": {
                "mcpCapabilities": {"http": True}}, "authMethods": []}})
        elif method == "session/new":
            servers.update({s["name"]: s for s in params["mcpServers"]})
            send({"jsonrpc": "2.0", "id": ident, "result": {"sessionId": "s1"}})
        elif method == "session/prompt":
            threading.Thread(target=prompt, args=(ident, params)).start()
''')


def test_an_external_agent_controls_the_editor_over_mcp(tmp_path):
    from pyzed.designer import agent_tools
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    script = tmp_path / "agent.py"
    script.write_text(EDITOR_AGENT)
    d = Designer(tmp_path / "main.pzform", language_servers=False)
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"))
    c.settings.acp_agents.append(providers.ACPAgentConfig("fake", sys.executable, [str(script)], title="Fake"))
    c.thread.model = c.settings.model = "acp:fake"
    c.settings.mode = "bypass"
    plans = []
    try:
        c.send("Add an OK button")
        for _ in range(4000):
            c.poll()
            if c.live_plan and c.live_plan not in plans:
                plans.append(list(c.live_plan))
            if not c.running:
                break
            time.sleep(0.005)
        else:
            raise AssertionError("timed out")
    finally:
        c.shutdown()
    assert not c.error, c.error
    assert any(ctl.name == "ok_button" for ctl in d.doc.form.controls)  # changed live, in the open form
    text = [b["text"] for m in c.thread.messages if m["role"] == "assistant" for b in m["content"]
            if b["type"] == "text"][-1]
    report = json.loads(text)
    assert report["added"] and report["seen"] and report["instructions"]
    assert {"add_control", "run_app", "update_plan", "list_components"} <= set(report["tools"])
    assert "write_file" not in report["tools"]  # files and shell are the agent's own
    assert plans and plans[0][0] == {"step": "Add the button", "status": "in_progress"}
    assert [s["status"] for s in agent_tools.plan_of(c.thread.messages)] == ["done", "done"]
    assert c.changed  # the agent's changes can be kept or rejected like the built-in agent's


def test_the_editor_server_checks_its_caller_and_bridges_stdio():
    import io

    from pyzed.agents import mcp_host

    @agents.tool
    def shout(text: str) -> str:
        """Shouts."""
        return text.upper()

    @agents.tool
    def picture() -> object:
        """A picture."""
        return ["a dot", agents.Image(PNG)]

    server = mcp_host.ToolServer(agents.Agent(tools=[shout, picture]), name="test", instructions="Be nice.")
    try:
        headers = {"Authorization": f"Bearer {server.token}"}
        good = mcp_client.HttpTransport(server.url, headers)
        assert good.request("initialize", {"protocolVersion": "2025-03-26"})["instructions"] == "Be nice."
        assert {t["name"] for t in good.request("tools/list")["tools"]} == {"shout", "picture"}
        assert good.request("tools/call", {"name": "shout", "arguments": {"text": "hi"}})["content"][0]["text"] == "HI"
        shot = good.request("tools/call", {"name": "picture", "arguments": {}})["content"]
        assert shot[1]["type"] == "image" and shot[1]["mimeType"] == "image/png"
        assert good.request("tools/call", {"name": "nope", "arguments": {}})["isError"]
        with pytest.raises(mcp_client.MCPError):
            mcp_client.HttpTransport(server.url, {"Authorization": "Bearer wrong"}).request("tools/list")
        with pytest.raises(mcp_client.MCPError):
            mcp_client.HttpTransport(server.url + "x", headers).request("tools/list")
        entry = server.acp_entry()
        assert entry["type"] == "http" and entry["headers"][0]["value"] == f"Bearer {server.token}"
        assert server.bridge_entry()["args"][-1] == server.url
        agent = acp.ACPAgent(providers.ACPAgentConfig("x", "x"), cwd=".", settings=providers.AgentSettings(),
                             mcp_servers=[entry, server.bridge_entry(), {"name": "other", "command": "y"}])
        assert [s.get("type", "stdio") for s in agent._servers()] == ["stdio", "stdio"]  # no HTTP: the bridge
        agent.capabilities = {"mcpCapabilities": {"http": True}}
        assert [s.get("type", "stdio") for s in agent._servers()] == ["http", "stdio"]
        out = io.StringIO()
        mcp_host.bridge(server.url, server.token, io.StringIO(
            json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                        "params": {"name": "shout", "arguments": {"text": "yo"}}}) + "\n"
            + json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"), out)
        lines = [json.loads(x) for x in out.getvalue().splitlines()]
        assert len(lines) == 1 and lines[0]["id"] == 7 and lines[0]["result"]["content"][0]["text"] == "YO"
    finally:
        server.close()


def test_using_a_claude_subscription_through_claude_code(tmp_path, monkeypatch):
    from pyzed.designer import agent_panel, file_ops
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(acp.sys, "platform", "linux")
    monkeypatch.setattr(providers, "config_path", lambda: tmp_path / "agents.json")
    assert not acp.claude_signed_in()
    opened, terminals = [], []
    monkeypatch.setattr(login, "open_browser", opened.append)
    monkeypatch.setattr(file_ops, "run_in_terminal", lambda args, folder: terminals.append(args))
    d = Designer()
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"))
    d.view()  # the empty panel offers the subscription first

    monkeypatch.setattr(agent_panel.shutil, "which", lambda name: None)
    c.use_claude_subscription()  # no Node.js: says so and opens its download page
    assert opened == [agent_panel.NODE_URL] and c.settings.acp_agent("claude-code") is None

    monkeypatch.setattr(agent_panel.shutil, "which", lambda name: "/usr/bin/npx" if name == "npx" else None)
    c.use_claude_subscription()
    assert c.settings.acp_agent("claude-code") is not None and c.thread.model == "acp:claude-code"
    assert terminals == [["npx", "-y", "@anthropic-ai/claude-code"]] and c.claude_login is not None and c.active
    d.view()
    c.poll()
    assert c.claude_login is not None  # still waiting
    home.mkdir()
    (home / ".credentials.json").write_text("{}")
    c._claude_check = 0
    c.poll()
    assert c.claude_login is None and c.raise_window and acp.claude_signed_in()
    assert c.poll() is not None  # back to the front
    c.error = "Authentication required"
    assert c.needs_claude_login
    d.view()


def test_commands_run_in_the_systems_terminal(monkeypatch, tmp_path):
    from pyzed.designer import file_ops

    monkeypatch.delenv("TERMINAL", raising=False)
    monkeypatch.setattr(file_ops.sys, "platform", "linux")
    monkeypatch.setattr(file_ops.shutil, "which", lambda name: "/usr/bin/" + name if name == "konsole" else None)
    assert file_ops.run_in_terminal_command(["claude"], tmp_path) == ["/usr/bin/konsole", "-e", "claude"]
    monkeypatch.setattr(file_ops.sys, "platform", "darwin")
    mac = file_ops.run_in_terminal_command(["claude"], tmp_path)
    assert mac[0] == "osascript" and "claude" in mac[2]
    monkeypatch.setattr(file_ops.sys, "platform", "linux")
    monkeypatch.setattr(file_ops.shutil, "which", lambda name: None)
    with pytest.raises(OSError):
        file_ops.run_in_terminal_command(["claude"], tmp_path)


def test_panel_menus_history_and_settings_view_like_zed(tmp_path, monkeypatch):
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    monkeypatch.setattr(providers, "config_path", lambda: tmp_path / "agents.json")
    d = Designer()
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"))
    c.settings.acp_agents.append(acp.preset("gemini"))
    c.toggle_menu("new")
    d.view()  # the + menu lists the built-in agent and the external ones
    c.new_thread("acp:gemini")
    assert c.thread.model == "acp:gemini" and c.settings.model == "acp:gemini" and c.menu is None
    c.new_thread("")  # the built-in agent again, with a model of its own
    assert not c.thread.model.startswith("acp:")
    c.thread.messages = [{"role": "user", "content": [{"type": "text", "text": "Make a login form"}]},
                         {"role": "assistant", "content": [{"type": "text", "text": "Done."},
                                                           {"type": "tool_use", "id": "t1", "name": "add_control",
                                                            "input": {"name": "email"}}]}]
    assert "## User" in c.thread_markdown() and "`add_control` email" in c.thread_markdown()
    c.toggle_menu("options")
    d.view()
    c._keep()
    c.toggle_history()
    d.view()  # the history, grouped by day with a search box
    assert c.view == "history"
    c.back()
    c.open_settings(section="agents")
    assert c.view == "settings" and c.registry_open and d.dialog is None
    d.view()


def test_installing_agents_from_the_acp_registry(tmp_path, monkeypatch):
    from pyzed.agents import registry
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    monkeypatch.setattr(providers, "config_path", lambda: tmp_path / "agents.json")
    entries = [registry.RegistryAgent.from_dict({"id": "gemini", "name": "Gemini CLI", "version": v,
                                                 "distribution": {"npx": {"package": f"@google/gemini-cli@{v}",
                                                                          "args": ["--acp"]}}})
               for v in ("0.64.0", "0.65.0")]
    current = [entries[0]]
    monkeypatch.setattr(registry, "fetch", lambda refresh=False: list(current))
    monkeypatch.setattr(registry, "_prefetch_npm", lambda *a: None)
    d = Designer()
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"))
    c.open_settings(section="agents")
    _until(lambda: c.registry, d)
    assert c.registry_items()[0]["installed"] is False
    c.install_agent("gemini")
    _until(lambda: not c.registry_busy, d)
    config = c.settings.acp_agent("gemini")
    assert config.registry_id == "gemini" and config.version == "0.64.0"
    assert config.args == ["-y", "@google/gemini-cli@0.64.0", "--acp"]
    d.view()
    current[:] = [entries[1]]
    c.load_registry(refresh=True)
    _until(lambda: not c.registry_busy, d)
    assert c.agent_update(config) == "0.65.0" and c.registry_items()[0]["update"] == "0.65.0"
    d.view()  # the agent's row offers the update
    c.update_agent("gemini")
    _until(lambda: not c.registry_busy, d)
    assert c.settings.acp_agent("gemini").version == "0.65.0" and len(c.settings.acp_agents) == 1
    c.uninstall_agent("gemini")
    assert c.settings.acp_agent("gemini") is None


def test_skills_in_the_settings_and_the_agent(tmp_path, monkeypatch):
    from pyzed.agents import skills
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    monkeypatch.setattr(providers, "config_path", lambda: tmp_path / "agents.json")
    folder = tmp_path / "skills" / "forms"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("---\nname: forms\ndescription: How to lay out forms\n---\nUse a grid.\n")
    monkeypatch.setattr(skills, "discover", lambda root=None: [skills.load(folder, "project")])
    d = Designer()
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"))
    c.open_settings()
    d.view()
    assert [s.name for s in c.skills()] == ["forms"]
    c.toggle_skill("forms", False)
    assert c.settings.disabled_skills == ["forms"]
    c.toggle_skill("forms", True)
    assert c.settings.disabled_skills == []


def test_keeping_and_rejecting_changes_file_by_file(tmp_path, monkeypatch):
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    monkeypatch.setattr(providers, "config_path", lambda: tmp_path / "agents.json")
    d = Designer()
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"))
    doc = d.doc
    before = doc.code
    c._remember_documents()
    doc.code = before + "\nvalue = 1\n"
    c.changed = True
    [change] = c.file_changes()
    assert change["added"] == 2 and change["removed"] == 0
    d.view()  # the edits bar
    c.reject_file(doc.display_name)
    assert doc.code == before and not c.changed
    c._remember_documents()
    doc.code = before + "\nkept = 1\n"
    c.changed = True
    c.keep_file(doc.display_name)
    assert doc.code.endswith("kept = 1\n") and not c.snapshot


AUTH_AGENT = textwrap.dedent('''
    import json, sys
    from pathlib import Path

    flag = Path(sys.argv[1])  # signed in (the terminal login writes it)

    def send(msg):
        sys.stdout.write(json.dumps(msg) + "\\n")
        sys.stdout.flush()

    for line in sys.stdin:
        msg = json.loads(line)
        method, ident, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": ident, "result": {"protocolVersion": 1, "agentCapabilities": {},
                  "authMethods": [
                      {"id": "oauth", "name": "Log in with Google", "description": "Opens the browser"},
                      {"id": "login", "name": "Log in in a terminal", "type": "terminal", "args": ["--login"],
                       "env": {"FAKE_LOGIN": "1"}},
                      {"id": "key", "name": "Use an API key", "type": "env_var", "varName": "FAKE_API_KEY"}]}})
        elif method == "authenticate":
            if params["methodId"] == "oauth":
                flag.write_text("yes")
            send({"jsonrpc": "2.0", "id": ident, "result": {}})
        elif method == "session/new":
            if flag.exists():
                send({"jsonrpc": "2.0", "id": ident, "result": {"sessionId": "s1"}})
            else:
                send({"jsonrpc": "2.0", "id": ident, "error": {"code": -32000, "message": "Authentication required"}})
        elif method == "session/prompt":
            send({"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": "s1", "update": {
                "sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "hi there"}}}})
            send({"jsonrpc": "2.0", "id": ident, "result": {"stopReason": "end_turn"}})
''')


def test_external_agent_sign_in_methods_like_zed(tmp_path):
    script, flag = tmp_path / "agent.py", tmp_path / "signed"
    script.write_text(AUTH_AGENT)
    config = providers.ACPAgentConfig("fake", sys.executable, [str(script), str(flag)], title="Fake")
    agent = acp.ACPAgent(config, cwd=tmp_path, mcp_servers=[])
    events = []
    try:
        agent.run("hello", on_event=events.append)
        auth = next(e for e in events if e.kind == "auth")
        assert [m["id"] for m in auth.args["methods"]] == ["oauth", "login", "key"]
        assert auth.args["prompt"][0]["text"] == "hello" and agent.messages == []  # it waits for the sign-in
        assert [acp.auth_kind(m) for m in auth.args["methods"]] == ["agent", "terminal", "env_var"]
        command, env = acp.terminal_login(config, auth.args["methods"][1])
        assert command == [sys.executable, str(script), str(flag), "--login"] and env == {"FAKE_LOGIN": "1"}
        meta = {"id": "x", "_meta": {"terminal-auth": {"command": "claude", "args": ["/login"]}}}
        assert acp.auth_kind(meta) == "terminal" and acp.terminal_login(config, meta) == (["claude", "/login"], {})
        assert not agent.signed_in()
        agent.authenticate("oauth")
        assert agent.session == "s1"
        assert agent.run("hello") == "hi there"
    finally:
        agent.close()


@pytest.mark.parametrize("method", ["login", "oauth"])
def test_the_panel_signs_in_to_an_external_agent_and_sends_again(tmp_path, monkeypatch, method):
    from pyzed.designer import agent_panel, file_ops
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    script, flag = tmp_path / "agent.py", tmp_path / "signed"
    script.write_text(AUTH_AGENT)
    d = Designer(tmp_path / "main.pzform", language_servers=False)
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"))
    c.settings.acp_agents.append(providers.ACPAgentConfig("fake", sys.executable, [str(script), str(flag)],
                                                          title="Fake"))
    c.thread.model = c.settings.model = "acp:fake"
    opened = []
    monkeypatch.setattr(file_ops, "run_in_terminal", lambda args, folder, env=None: opened.append((args, env)) or flag.write_text("y"))
    monkeypatch.setattr(agent_panel, "AGENT_LOGIN_EVERY", 0.0)

    def settle(until):
        for _ in range(4000):
            c.poll()
            if until():
                return
            time.sleep(0.005)
        raise AssertionError("timed out")

    try:
        c.send("hello")
        settle(lambda: not c.running)
        assert c.agent_auth is not None and not c.error and c.thread.messages == []
        assert agent_panel._auth_card(c, d.theme) is not None
        c.pick_auth("key")  # a key: it goes in the agent's secrets
        assert "FAKE_API_KEY" in c.agent_auth.error and c.view == "settings"
        c.view = "thread"
        c.pick_auth(method)  # the agent opens the browser, or its login runs in a terminal and the panel checks
        if method == "login":
            assert opened == [([sys.executable, str(script), str(flag), "--login"], {"FAKE_LOGIN": "1"})]
        assert c.active and c.agent_auth.waiting == method
        settle(lambda: c.agent_auth is None and not c.running and c.thread.messages)
        settle(lambda: not c.running)
        texts = [b["text"] for m in c.thread.messages for b in m["content"] if b["type"] == "text"]
        assert texts[0] == "hello" and texts[-1] == "hi there"
        assert not c.error
    finally:
        c.shutdown()


def test_following_the_agent_opens_and_refreshes_what_it_writes(tmp_path, monkeypatch):
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    monkeypatch.chdir(tmp_path)
    d = Designer(tmp_path / "main.pzform", language_servers=False)
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"))
    monkeypatch.setattr(c, "project_root", lambda: tmp_path)
    monkeypatch.setattr(c, "save_settings", lambda: None)
    app = tmp_path / "app.py"
    app.write_text("print(1)\n")
    assert d.buffers.open(app)
    d.focus = "agent"
    app.write_text("print(2)\n")  # an external agent wrote it: the open file shows the new text
    c._on_event(agents.Event("file", str(app), args={"written": True}))
    buffer = d.buffers.items[d.buffers.index_of(app)]
    assert buffer.text == "print(2)\n" and buffer.revision == 1 and not buffer.dirty
    views = tmp_path / "views.py"
    views.write_text("x = 1\n")
    c._on_event(agents.Event("tool_result", tool="write_file", args={"path": "views.py"}))  # the built-in agent
    assert d.buffers.index_of(views) is not None and d.focus == "agent"  # opened, the input keeps the keyboard
    c.toggle_follow()
    assert not c.settings.follow_agent
    other = tmp_path / "other.py"
    other.write_text("y = 2\n")
    c._on_event(agents.Event("file", str(other), args={"written": True}))
    assert d.buffers.index_of(other) is None
    c.toggle_follow()
    c._on_event(agents.Event("file", str(tmp_path.parent / "outside.py"), args={"written": True}))
    assert len(d.buffers.items) == 2  # never outside the project


def test_context_meter_and_desktop_notifications(tmp_path, monkeypatch):
    from pyzed import _platform
    from pyzed.designer import agent_panel
    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    assert providers.context_window("anthropic:claude-opus-5-5") == 1_000_000
    assert providers.context_window("anthropic:claude-haiku-4-5") == 200_000
    assert providers.context_window("openai:gpt-4.1-mini") == 1_047_576
    assert providers.context_window("ollama:qwen3:8b") == 0
    thread = agents.Thread(context=48_000)
    assert agents.Thread.from_dict(thread.to_dict()).context == 48_000

    monkeypatch.setattr(_platform.sys, "platform", "darwin")
    assert _platform.desktop_notification_command('Say "hi"', "done")[-1] == \
        'display notification "done" with title "Say \\"hi\\""'
    monkeypatch.setattr(_platform.sys, "platform", "win32")
    command = _platform.desktop_notification_command("t", "b")
    assert command[0] == "powershell" and "$env:PYZED_TITLE" in command[-1]  # the texts go in variables

    d = Designer(tmp_path / "main.pzform", language_servers=False)
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"))
    shown = []
    monkeypatch.setattr(_platform, "notify", lambda title, body: shown.append((title, body)) or True)
    c._on_event(agents.Event("turn", usage={"input": 40_000, "cache_read": 7_000, "output": 1_000}))
    assert c.thread.context == 48_000 and c.context_window == providers.context_window(c.settings.model)
    assert agent_panel._composer(c, d.theme) is not None  # the meter shows next to the model
    c.running = True
    c._on_event(agents.Event("done"))
    assert shown == []  # the window has the focus: nothing to tell
    d.window_focused = False
    c.running = True
    c._on_event(agents.Event("done"))
    assert shown and shown[0][0] == "The agent finished"
    c.settings.notify_when_done = False
    c._on_event(agents.Event("done"))
    assert len(shown) == 1


def test_external_agents_open_windows_browser_under_wsl(monkeypatch):
    from pyzed import _platform

    monkeypatch.delenv("BROWSER", raising=False)
    monkeypatch.setattr(_platform, "is_wsl", lambda release=None: False)
    assert _platform.browser_env() == {}
    monkeypatch.setattr(_platform, "is_wsl", lambda release=None: True)
    monkeypatch.setattr(_platform.shutil, "which", lambda name: None)
    monkeypatch.setattr(_platform, "windows_command", lambda name: "/mnt/c/Windows/System32/rundll32.exe")
    assert _platform.browser_env() == {"BROWSER": "/mnt/c/Windows/System32/rundll32.exe url.dll,FileProtocolHandler %s"}
    monkeypatch.setenv("BROWSER", "firefox")
    assert _platform.browser_env() == {}


def test_project_rules_files_like_zed(tmp_path):
    from pyzed.agents import rules

    assert rules.find(tmp_path) is None and rules.prompt(None) == ""
    (tmp_path / "CLAUDE.md").write_text("Use tabs.")
    (tmp_path / "AGENTS.md").write_text("  \n")  # empty: skipped
    assert rules.find(tmp_path).name == "CLAUDE.md"
    (tmp_path / ".rules").write_text("Answer in Spanish.")
    found = rules.find(tmp_path)
    assert found.name == ".rules" and "<project_rules>\nAnswer in Spanish.\n</project_rules>" in rules.prompt(found)
    other = tmp_path / "other"
    path = rules.create(other)
    assert path.name == "AGENTS.md" and rules.find(other).text.startswith("# Rules for AI agents")


def test_the_agents_follow_the_active_project(tmp_path, monkeypatch):
    import types

    from pyzed.designer.agent_panel import AgentController
    from pyzed.designer.app import Designer

    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir()
    two.mkdir()
    (two / "AGENTS.md").write_text("Name buttons with a _button suffix.")
    stream = []

    def fake(model, system, messages, tools, *, settings, on_event, cancel, **kw):
        stream.append(system)
        on_event("text", "ok")
        return llm.Turn([{"type": "text", "text": "ok"}], "end_turn", {"input": 10, "output": 5})

    d = Designer(tmp_path / "main.pzform", language_servers=False)
    d.agent = c = AgentController(d, store=agents.ThreadStore(tmp_path / "threads"), stream=fake)
    monkeypatch.setattr(c, "save_settings", lambda: None)
    c.thread.model = c.settings.model = "ollama:llama3"
    monkeypatch.setattr(providers, "is_ready", lambda *a, **k: True)
    environment = lambda: types.SimpleNamespace(describe=lambda: "This computer (Linux).", is_wsl=False)  # noqa: E731
    project = lambda root: types.SimpleNamespace(root=root, environment=environment(), name=root.name)  # noqa: E731

    def run(text):
        c.send(text)
        for _ in range(2000):
            c.poll()
            if not c.running:
                return
            time.sleep(0.005)
        raise AssertionError("timed out")

    d.projects.project = project(one)
    c.project_changed(d.projects.project)
    assert c.thread.project == str(one.resolve())  # an empty thread moves to the new project
    run("hello")
    assert "<project_rules>" not in stream[-1]
    first = c.thread.id
    d.projects.project = project(two)
    c.project_changed(d.projects.project)  # another project: a new thread of its own
    assert c.thread.id != first and not c.thread.messages and c.thread.project == str(two.resolve())
    assert first not in [th.id for th in c.threads()]  # the history shows this project's threads
    run("add a button")
    assert "Name buttons with a _button suffix." in stream[-1] and c.project_rules().name == "AGENTS.md"
    d.projects.project = project(one)
    c.project_changed(d.projects.project)
    assert first in [th.id for th in c.threads()]
    c.open_rules()  # creates the project's AGENTS.md and opens it
    assert (one / "AGENTS.md").is_file() and d.buffers.index_of(one / "AGENTS.md") is not None
