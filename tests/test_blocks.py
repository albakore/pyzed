"""The Blocks of the documentation (examples/blocks) and the streaming AI chat example (examples/ai_chat.py)."""

import asyncio
import importlib
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import pyzed as pz
from pyzed.mcp import validate

ROOT = Path(__file__).resolve().parents[1]
BLOCKS = sorted((ROOT / "examples" / "blocks").glob("*.py"))


def _app_class(module):
    apps = [v for v in vars(module).values()
            if isinstance(v, type) and issubclass(v, pz.App) and v.__module__ == module.__name__]
    assert apps, f"{module.__name__} defines no App"
    return apps[-1]


@pytest.fixture
def import_example(monkeypatch):
    loaded = []

    def load(path):
        monkeypatch.syspath_prepend(str(path.parent))
        loaded.append(path.stem)
        return importlib.import_module(path.stem)

    yield load
    for name in loaded:
        sys.modules.pop(name, None)


def test_there_are_blocks():
    assert {p.stem for p in BLOCKS} >= {"login", "dashboard", "settings", "data_table", "chat", "file_explorer",
                                        "onboarding", "music_player", "kanban"}


@pytest.mark.parametrize("path", BLOCKS, ids=lambda p: p.stem)
@pytest.mark.parametrize("theme", ["One Dark", "One Light"])
def test_blocks_render(path, theme, tmp_path, import_example):
    app = _app_class(import_example(path))()
    app.theme = theme
    app.__pyzed_view__()  # raises if the view is broken (the off-screen renderer would only print it)
    out = tmp_path / f"{path.stem}.png"
    app.screenshot(out, size=(1200, 760), scale=1)
    assert out.exists()


@pytest.mark.parametrize("path", BLOCKS + [ROOT / "examples" / "ai_chat.py"], ids=lambda p: p.stem)
def test_blocks_pass_validate_code(path):
    result = validate.check_code(path.read_text(encoding="utf-8"), lint=False)
    assert result["ok"] and not result["issues"], result["issues"]


def test_kanban_moves_cards(import_example):
    kanban = import_example(ROOT / "examples" / "blocks" / "kanban.py")
    app = kanban.Kanban()
    card = next(c for c in app.cards if c.column == "doing")
    app.move(card, 1)
    assert card.column == "done"
    app.move(card, 5)
    assert card.column == "done"


def test_data_table_filters_and_pages(import_example):
    table = import_example(ROOT / "examples" / "blocks" / "data_table.py")
    app = table.DataTable()
    assert all(r["status"] in {"Active", "Invited"} for r in app.visible())
    app.toggle_status("Suspended")
    assert len(app.visible()) == len(table.ROWS)
    app.set_query("lee")
    assert [r["name"] for r in app.visible()] == ["Jackson Lee"]


def _drive(app, prompt):
    effects = app.send(prompt)
    reply = next(e for e in effects if hasattr(e, "__aiter__"))

    async def run():
        async for message in reply:
            app.update(message)

    asyncio.run(run())


def test_ai_chat_streams_the_demo_answer(import_example):
    chat = import_example(ROOT / "examples" / "ai_chat.py")
    app = chat.AIChat(stream=lambda m: chat.demo_stream(m, delay=0))
    _drive(app, "hello")
    assert not app.busy and app.messages[-1]["content"] == chat.DEMO_ANSWER
    app.__pyzed_view__()


def test_ai_chat_ignores_a_stopped_reply(import_example):
    chat = import_example(ROOT / "examples" / "ai_chat.py")
    app = chat.AIChat(stream=lambda m: chat.demo_stream(m, delay=0))
    effects = app.send("hello")
    reply = next(e for e in effects if hasattr(e, "__aiter__"))

    async def run():
        count = 0
        async for message in reply:
            app.update(message)
            count += 1
            if count == 3:
                app.stop()

    asyncio.run(run())
    assert not app.busy and 0 < len(app.messages[-1]["content"]) < len(chat.DEMO_ANSWER)


def test_ai_chat_shows_errors(import_example):
    chat = import_example(ROOT / "examples" / "ai_chat.py")

    async def failing(messages):
        raise ConnectionError("no route to host")
        yield  # pragma: no cover

    app = chat.AIChat(stream=failing)
    _drive(app, "hello")
    assert app.error == "no route to host" and not app.busy


def test_ai_chat_talks_to_an_openai_compatible_server(import_example):
    pytest.importorskip("httpx")
    chat = import_example(ROOT / "examples" / "ai_chat.py")
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            seen["path"] = self.path
            seen["auth"] = self.headers.get("Authorization")
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for piece in ["Hel", "lo", "!"]:
                chunk = {"choices": [{"delta": {"content": piece}}]}
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/v1"

        async def collect():
            return [p async for p in chat.openai_stream([{"role": "user", "content": "hi"}], model="m",
                                                        base_url=url, api_key="k")]

        assert "".join(asyncio.run(collect())) == "Hello!"
        assert seen["path"] == "/v1/chat/completions" and seen["auth"] == "Bearer k"
        assert seen["body"]["stream"] is True and seen["body"]["model"] == "m"
    finally:
        server.shutdown()


def test_block_pages_are_up_to_date():
    """docs/scripts/gen_blocks.py copies each block's code into its page; run it after changing a block."""
    import subprocess

    result = subprocess.run([sys.executable, str(ROOT / "docs" / "scripts" / "gen_blocks.py"), "--check"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
