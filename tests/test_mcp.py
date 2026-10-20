"""The MCP server for AI agents: knowledge, generators, checks, previews and the server itself."""

import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from pyzed.mcp import knowledge, preview, projects, scaffold, validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def checkout(monkeypatch):
    """Reads pages and examples from this repository instead of GitHub."""
    monkeypatch.setattr(knowledge, "source_root", lambda: ROOT)


def test_guides_are_bundled():
    assert "Elm architecture" in knowledge.guide("overview")
    assert "view()" in knowledge.guide("best-practices")
    with pytest.raises(KeyError):
        knowledge.guide("nope")


def test_list_components_covers_every_layer():
    names = {e["name"] for e in knowledge.list_components()}
    assert {"pz.column", "pz.text", "ui.button", "ui.tab_bar", "designer:button"} <= names
    assert all(e["kind"] == "ui" for e in knowledge.list_components("ui"))
    assert all(e["summary"] for e in knowledge.list_components("widget"))
    layout = knowledge.list_components("widget", category="layout")
    assert "pz.row" in {e["name"] for e in layout} and "pz.text" not in {e["name"] for e in layout}
    assert {e["name"] for e in knowledge.list_components(query="palette")} >= {"ui.command_palette"}
    with pytest.raises(ValueError):
        knowledge.list_components("nope")


def test_describe_component():
    button = knowledge.describe_component("ui.button")
    assert button["signature"].startswith("ui.button(")
    assert "variant" in {p["name"] for p in button["parameters"]}
    assert "pz.button" in button["see_also"]

    column = knowledge.describe_component("pz.column")  # implemented in Rust: documented from the docs
    assert column["description"]
    spacing = next(p for p in column["parameters"] if p["name"] == "spacing")
    assert "pixels" in spacing["description"]

    designer = knowledge.describe_component("designer:button")
    assert "click" in designer["events"] and designer["props"][0]["name"] == "text"
    assert knowledge.describe_component("button")["name"] == "ui.button"  # bare names prefer pz.ui
    with pytest.raises(KeyError, match="did you mean"):
        knowledge.describe_component("butto")


def test_describe_a_user_component():
    import pyzed as pz

    class McpRating(pz.Component):
        """Stars."""

        value: int = 0
        hover: int = pz.state(0)
        events = {"change": "A star was picked."}

        def render(self):
            return pz.text("★" * self.value)

    info = knowledge.describe_component("McpRating")
    assert info["kind"] == "component" and info["doc"] == "Stars."
    assert info["props"] == [{"name": "value", "type": "int", "default": "0"}]
    assert info["state"][0]["name"] == "hover" and "change" in info["events"]


def test_icons_and_themes():
    found = knowledge.search_icons("arrow left", limit=3)
    assert len(found["icons"]) == 3 and found["total"] >= 3
    assert all("arrow" in n and "left" in n for n in found["icons"])
    themes = knowledge.list_themes()
    assert {"name": "One Dark", "dark": True} in themes["themes"]
    assert {"accent", "panel", "border"} <= set(themes["tokens"])


def test_docs_index_points_at_real_files():
    data = json.loads((ROOT / "python" / "pyzed" / "mcp" / "docs_index.json").read_text(encoding="utf-8"))
    for entry in data["docs"] + data["examples"]:
        assert (ROOT / entry["path"]).is_file(), f"{entry['path']} is gone: run docs/scripts/gen_mcp_index.py"
    assert data["api"]["entries"]["pyzed.column"]["desc"]


def test_read_docs_and_examples(checkout):
    assert {"guides/layout", "index"} <= {p["slug"] for p in knowledge.list_docs()}
    assert "title: Layout" in knowledge.read_docs("guides/layout")
    assert "title: Layout y estilo" in knowledge.read_docs("/pyzed/es/guides/layout/", lang="es")
    with pytest.raises(KeyError):
        knowledge.read_docs("guides/nope")
    assert "counter" in {e["name"] for e in knowledge.list_examples()}
    assert "pz.App" in knowledge.read_example("counter.py")


def test_new_component_is_valid_and_works():
    out = scaffold.component("star rating", description="Stars.", events={"change": "Picked."},
                             props=[{"name": "value", "type": "int", "default": 3},
                                    {"name": "caption", "default": "Hi"}],
                             state=[{"name": "hover", "default": 0}])
    assert out["class_name"] == "StarRating" and "on_change=" in out["usage"]
    assert validate.check_code(out["code"])["ok"]
    namespace: dict = {}
    exec(compile(out["code"], "star_rating.py", "exec"), namespace)
    cls = namespace["StarRating"]
    assert set(cls.__props__) == {"value", "caption"} and "hover" in cls.__state__ and "change" in cls.__events__
    for bad in ("class", "label", "render"):
        with pytest.raises(ValueError):
            scaffold.component("x", props=[{"name": bad}])
    with pytest.raises(ValueError):
        scaffold.component("x", events={"mount": "built in"})
    assert "def emit_render(self" in scaffold.component("x", events={"render": "clash"})["code"]


@pytest.mark.parametrize("layout", ["simple", "workspace"])
def test_new_app_is_valid(layout):
    code = scaffold.app("Demo", layout=layout)
    compile(code, "main.py", "exec")
    assert validate.check_code(code)["ok"]


def test_new_form_round_trips():
    out = scaffold.form("login", title="Sign in", form_events=["load"], controls=[
        {"type": "input", "name": "email", "props": {"placeholder": "Email"}, "events": ["submit"]},
        {"type": "button", "name": "send", "props": {"text": "Send"}, "events": {"click": "send_clicked"}},
        {"type": "label", "name": "title"},  # reserved: renamed
    ])
    form, handlers = out["files"]["login.pzform"], out["files"]["login.py"]
    assert "title1" in form and any("renamed" in w for w in out["warnings"])
    assert "def send_clicked(form, event):" in handlers and "def form_load(form, event):" in handlers
    assert validate.check_form(form, handlers) == {"ok": True, "issues": [], "controls": 3}
    data = json.loads(form)
    assert data["controls"][1]["y"] > data["controls"][0]["y"]  # stacked
    with pytest.raises(KeyError):
        scaffold.form("bad", controls=[{"type": "nope"}])


def test_check_form_reports_problems():
    form = json.dumps({"format": "pyzed.form/1", "form": {"name": "f", "events": {"blink": "f_blink"}}, "controls": [
        {"name": "a", "type": "button", "props": {"nope": 1}, "events": {"hover": "a_hover", "click": "a_click"}},
        {"name": "a", "type": "nope"},
        {"name": "b", "type": "label", "parent": "a"},
    ]})
    result = validate.check_form(form, "def other(form, event):\n    pass\n")
    messages = "\n".join(i["message"] for i in result["issues"])
    assert not result["ok"]
    for text in ("two controls", "unknown component type", "no prop 'nope'", "no event 'hover'",
                 "the form has no event 'blink'", "does not define", "not a container"):
        assert text in messages
    assert not validate.check_form("{ not json")["ok"]


def test_check_code_finds_mistakes():
    source = '''
import pyzed as pz
from pyzed import ui, nothing


class Bad(pz.App):
    items = []

    def view(self):
        self.count = 1
        return pz.column([ui.button(f, lambda: self.open(f)) for f in self.items], spacingg=3)


class Broken(pz.Component):
    pass


class NoView(pz.App):
    pass


pz.nope()
pz.run(Bad)
pz.run(Bad)
'''
    issues = validate.check_code(source, lint=False)["issues"]
    messages = "\n".join(i["message"] for i in issues)
    for text in ("no 'nothing'", "mutable class attribute", "changes self.count", "loop variable 'f'",
                 "no parameter 'spacingg'", "without a render()", "without a view()", "pz.nope does not exist",
                 "more than once"):
        assert text in messages
    assert not validate.check_code("def f(:\n")["ok"]


def test_check_code_accepts_the_examples():
    for name in ("todo.py", "components.py", "mini_editor.py"):
        path = ROOT / "examples" / name
        result = validate.check_code(path.read_text(encoding="utf-8"), lint=False)
        assert result["ok"] and not result["issues"], (path, result["issues"])


def test_preview_renders_apps_and_components():
    png = preview.render("import pyzed as pz\nclass A(pz.App):\n    def view(self):\n        return pz.text('hi')\n"
                         "pz.run(A)\n", size=(160, 90))
    assert png.startswith(b"\x89PNG")
    png = preview.render("import pyzed as pz\ndef preview():\n    return pz.text('hi')\n", size=(120, 60))
    assert png.startswith(b"\x89PNG")
    with pytest.raises(RuntimeError, match="no pz.App"):
        preview.render("x = 1")


def _content(result):
    content = result.content if hasattr(result, "content") else result
    if isinstance(content, tuple):  # mcp 1.x returns (content, structured)
        content = content[0]
    return content


def test_server_registers_everything(tmp_path):
    pytest.importorskip("mcp")
    from pyzed.mcp import create

    server = create(root=str(tmp_path))
    project_tools = {"project_info", "list_files", "read_file", "write_files", "create_project", "add_dependency",
                     "check_project", "run_tests", "screenshot_project", "start_live_preview",
                     "live_preview_status", "stop_live_preview"}

    async def check():
        tools = {t.name for t in await server.list_tools()}
        assert {"get_guide", "list_guides", "list_components", "describe_component", "search_reference",
                "read_reference", "editor_keymap", "new_component", "new_form", "validate_code", "validate_form",
                "screenshot", "read_docs", "list_examples", "plan_app", "list_shader_nodes", "check_shader",
                "new_shader"} | project_tools <= tools
        resources = {str(r.uri) for r in await server.list_resources()}
        assert {"pyzed://guide", "pyzed://best-practices", "pyzed://cookbook", "pyzed://components"} <= resources
        assert {p.name for p in await server.list_prompts()} == {"create_component", "create_app", "create_form",
                                                                  "build_project"}
        assert "ui.button(" in _content(await server.call_tool("describe_component", {"name": "ui.button"}))[0].text
        written = _content(await server.call_tool("write_files", {"files": {"app.py": APP}}))
        assert json.loads(written[0].text)["ok"]
        shot = _content(await server.call_tool("screenshot_project", {"target": "app.py"}))
        assert shot[0].text.startswith("Screenshot of app.py") and shot[1].type == "image"
        with pytest.raises(Exception, match="may hold secrets"):  # the agent sees why a call failed
            await server.call_tool("read_file", {"path": ".env"})

    asyncio.run(check())

    async def no_code():
        tools = {t.name for t in await create(allow_code=False).list_tools()}
        assert "screenshot" not in tools and not tools & project_tools

    asyncio.run(no_code())


APP = "import pyzed as pz\n\n\nclass A(pz.App):\n    def view(self):\n        return pz.text('hi')\n\n\npz.run(A)\n"


def test_project_tools_stay_in_their_folder(tmp_path):
    result = projects.write_files(tmp_path, {"app/main.py": APP, "bad.py": "import pyzed as pz\npz.nope()\n"})
    assert result["written"] == ["app/main.py", "bad.py"] and not result["ok"]
    assert "pz.nope" in result["checks"]["bad.py"]["issues"][0]["message"]
    for path in ("../outside.py", ".env", "keys/id_rsa"):
        with pytest.raises(PermissionError):
            projects.write_files(tmp_path, {path: "x"})
    (tmp_path / ".env").write_text("TOKEN=1")
    assert ".env" not in projects.list_files(tmp_path)["files"]
    with pytest.raises(PermissionError):
        projects.read_file(tmp_path, ".env")
    assert projects.read_file(tmp_path, "app/main.py") == APP
    assert projects.info(tmp_path)["project"] is None
    checked = projects.check_project(tmp_path, tools=False)
    assert not checked["ok"] and list(checked["pyzed"]) == ["bad.py"]
    caption, png = projects.screenshot(tmp_path, "app/main.py", size=(160, 90))
    assert caption == "Screenshot of app/main.py." and png.startswith(b"\x89PNG")


def test_project_tools_read_a_project(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "0.2.0"\n'
                                              'dependencies = ["pyzed-ui"]\n\n[tool.pyzed]\n')
    from pyzed.designer.model import Form, save

    (tmp_path / "ui").mkdir()
    save(Form(title="Main", width=200, height=120), tmp_path / "ui" / "main.pzform")
    found = projects.info(tmp_path)
    assert found["project"] == "demo" and found["version"] == "0.2.0" and found["main_form"] == "ui/main.pzform"
    assert [d["name"] for d in found["dependencies"]] == ["pyzed-ui"]
    caption, png = projects.screenshot(tmp_path)
    assert "ui/main.pzform" in caption and png.startswith(b"\x89PNG")


def test_project_tools_know_the_entry_environment_and_shaders(tmp_path):
    from pyzed.mcp import shaders

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n\n[tool.pyzed]\nscript = "app.py"\n')
    (tmp_path / "app.py").write_text(APP)
    (tmp_path / "fx").mkdir()
    (tmp_path / "fx" / "glow.pzshad").write_text(shaders.template("glow_ring"))
    found = projects.info(tmp_path)
    assert found["entry"] == "app.py" and found["shaders"] == ["fx/glow.pzshad"]
    assert {"system", "wsl", "venv", "runs_in"} <= set(found["environment"])
    assert projects.check_project(tmp_path, tools=False)["ok"]
    assert projects.write_files(tmp_path, {"bad.pzshad": "{}"})["checks"]["bad.pzshad"]["issues"]
    caption, png = projects.screenshot(tmp_path, size=(160, 90))  # the entry by default
    assert "app.py" in caption and png.startswith(b"\x89PNG")
    caption, png = projects.screenshot(tmp_path, "fx/glow.pzshad", size=(120, 80))
    assert png.startswith(b"\x89PNG")


def test_live_preview_runs_and_reports(tmp_path):
    from pyzed.mcp import live

    (tmp_path / "app.py").write_text(APP)
    assert live.command(tmp_path, "app.py")[-3:] == ["pyzed", "dev", str((tmp_path / "app.py").resolve())]
    crash = [sys.executable, "-c", "print('starting'); raise SystemExit(4)"]
    result = live.start(tmp_path, "app.py", cmd=crash)
    assert not result["running"] and result["exit_code"] == 4 and "starting" in result["output"]
    wait = [sys.executable, "-c", "import time; print('up', flush=True); time.sleep(60)"]
    assert live.start(tmp_path, "app.py", cmd=wait)["running"]
    assert [p["target"] for p in live.status()] == ["app.py"]
    assert live.stop()["stopped"] == ["app.py"] and live.status() == []


def test_plan_app_points_at_blocks_and_topics():
    found = knowledge.plan("a kanban board that saves tasks to a SQLModel database")
    assert found["examples"][0]["name"] == "blocks/kanban"
    assert "integrations" in found["topics"] and found["steps"]


COOKBOOK = re.findall(r"```python\n(.*?)```", knowledge.guide("cookbook"), re.S)


@pytest.mark.parametrize("recipe", COOKBOOK, ids=[f"recipe{i}" for i in range(len(COOKBOOK))])
def test_cookbook_recipes_are_valid_and_render(recipe):
    result = validate.check_code(recipe, lint=False)
    assert result["ok"] and not result["issues"], result["issues"]
    assert preview.render(recipe, size=(320, 200)).startswith(b"\x89PNG")


def test_preview_reports_view_errors():
    with pytest.raises(RuntimeError, match="ZeroDivisionError"):
        preview.render("import pyzed as pz\nclass A(pz.App):\n    def view(self):\n        return 1 / 0\n")


def test_guide_topics_reference_and_keymap(checkout):
    pages = {p["slug"] for p in knowledge.list_docs()}
    assert set(knowledge.TOPICS.values()) <= pages
    assert set(knowledge.guides()) >= {"overview", "best-practices", "cookbook", "games", "shaders"}
    assert "pz.frames" in knowledge.guide("games")
    hits = knowledge.search_reference("virtual list")
    assert any("virtual" in h["id"] for h in hits)
    page = knowledge.read_reference("pz.shader")
    assert "uniforms" in page["body"]
    with pytest.raises(KeyError):
        knowledge.read_reference("pz.does_not_exist_anywhere")
    keymap = knowledge.editor_keymap()
    assert keymap["actions"] and "keymap_for" in keymap["change"]


def test_examples_cover_every_kind():
    kinds = {e["kind"] for e in knowledge.list_examples()}
    assert {"app", "blocks", "games", "showcase", "integrations", "tutorial", "designer"} <= kinds
    assert all(e["kind"] == "games" for e in knowledge.list_examples(kind="games"))


def test_check_code_counts_positional_arguments():
    issues = validate.check_code("import pyzed as pz\npz.anchor(pz.text('a'), 1, 2)\n", lint=False)["issues"]
    assert any("positional" in i["message"] for i in issues)


def test_shader_uniforms_take_theme_tokens():
    import pyzed as pz

    pz.shader("fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> "
              "{ return tint(); }", uniforms={"tint": "accent"})


def test_cli_without_the_sdk_explains_how_to_install(tmp_path):
    # A stub `mcp` package that fails to import, as when the SDK is missing.
    (tmp_path / "mcp").mkdir()
    (tmp_path / "mcp" / "__init__.py").write_text("raise ImportError('no mcp here')\n")
    result = subprocess.run([sys.executable, "-c", "import sys; from pyzed.cli import main; sys.exit(main(['mcp']))"],
                            capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(tmp_path)}, timeout=60)
    assert result.returncode == 1 and "pyzed-ui[mcp]" in result.stderr
