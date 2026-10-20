"""The apps of the tutorials (examples/tutorial): they render, and the steps the pages describe work.

The plain-Python apps are also rendered by ``test_features.test_examples_render``; this file adds the
designer forms of the tutorials and checks what each tutorial says its app does.
"""

import importlib
import sys
from pathlib import Path

import pytest

import pyzed as pz
from pyzed import shading
from pyzed.designer.runtime import open_form

ROOT = Path(__file__).resolve().parents[1]
TUTORIAL = ROOT / "examples" / "tutorial"
FORMS = sorted((TUTORIAL / "designer").glob("*.pzform"))


@pytest.fixture
def tutorial(monkeypatch):
    """Imports a module of examples/tutorial by name."""
    monkeypatch.syspath_prepend(str(TUTORIAL))
    loaded = []

    def load(name):
        loaded.append(name)
        return importlib.import_module(name)

    yield load
    for name in loaded:
        sys.modules.pop(name, None)


def test_the_tutorial_forms_exist():
    assert {p.stem for p in FORMS} >= {"hello", "contact", "signup", "welcome"}
    assert (TUTORIAL / "designer" / "glow.pzshad").is_file()


@pytest.mark.parametrize("path", FORMS, ids=lambda p: p.stem)
def test_tutorial_forms_load_and_render(path, tmp_path):
    app = open_form(path)
    app.runtime.load()
    assert app.runtime.error is None
    app.screenshot(tmp_path / f"{path.stem}.png", scale=1)
    assert (tmp_path / f"{path.stem}.png").exists()


def test_hello_greets():
    rt = open_form(TUTORIAL / "designer" / "hello.pzform").runtime
    rt.ctx.on(rt.form["your_name"], "change", "text")("Ada")
    rt.dispatch(rt.form["greet"], "click")
    assert rt.error is None
    assert rt.form["headline"].props["text"] == "Hello, Ada!"


def test_contact_checks_fields_then_thanks():
    rt = open_form(TUTORIAL / "designer" / "contact.pzform").runtime
    rt.load()
    rt.dispatch(rt.form["send"], "click")
    assert "name" in rt.form["status"].props["text"]
    rt.ctx.on(rt.form["your_name"], "change", "text")("Ada Lovelace")
    rt.ctx.on(rt.form["email"], "change", "text")("ada@example.com")
    rt.ctx.on(rt.form["message"], "change", "text")("Hi!")
    assert rt.form["counter"].props["text"] == "3 / 500"
    rt.dispatch(rt.form["send"], "click")
    assert rt.error is None
    assert rt.form["status"].props["text"].startswith("Thanks, Ada!")


def test_signup_validates_its_bound_data():
    app = open_form(TUTORIAL / "designer" / "signup.pzform")
    rt = app.runtime
    rt.load()
    rt.dispatch(rt.form["create"], "click")
    assert not app.form.valid and "email" in app.form.errors
    for control, prop, value in [("your_name", "text", "Ada"), ("email", "text", "ada@example.com"),
                                 ("password", "text", "analytical"), ("terms", "checked", True)]:
        rt.ctx.on(rt.form[control], "change", prop)(value)
    rt.dispatch(rt.form["create"], "click")
    assert rt.error is None and app.form.valid
    assert app.form.data["name"] == "Ada" and app.form.data["terms"] is True
    assert rt.form["status"].props["text"] == "Welcome aboard, Ada!"


def test_welcome_changes_the_shader_variables():
    rt = open_form(TUTORIAL / "designer" / "welcome.pzform").runtime
    rt.load()
    assert rt.form["backdrop"].props["file"].endswith("glow.pzshad")
    rt.dispatch(rt.form["faster"], "click")
    rt.dispatch(rt.form["color"], "click")
    assert rt.error is None
    assert rt.form["backdrop"].props["variables"] == {"pulse": 3.5, "color": "#a78bfa"}


def test_glow_shader_compiles():
    compiled = shading.load(TUTORIAL / "designer" / "glow.pzshad").compiled()
    assert not compiled.errors


def test_aurora_graph_compiles(tutorial, tmp_path):
    module = tutorial("aurora_graph")
    compiled = module.build_aurora().compile()
    assert not compiled.errors
    saved = module.build_aurora().save(tmp_path / "aurora.pzshad")
    assert shading.load(saved).variables["speed"] == pytest.approx(0.3)


def test_layout_follow_button(tutorial):
    app = tutorial("layout_basics").Profile()
    app.toggle_follow()
    assert app.follows
    app.__pyzed_view__()


def test_theme_switcher(tutorial):
    module = tutorial("theme_switcher")
    assert "Sunset" in pz.themes.names()
    app = module.ThemeSwitcher()
    app.choose("base")("Sunset")
    assert app.resolved_theme().name == "Sunset"
    app.choose("accent")("Gold")
    assert app.resolved_theme().accent == "#e5c07b"
    app.__pyzed_view__()


def test_navigation(tutorial):
    app = tutorial("navigation").Navigation()
    app.on_key("ctrl-3")
    assert app.page == "Settings"
    for tab in ("General", "Notifications", "About"):
        app.tab = tab
        app.__pyzed_view__()
    app.go("Inbox")
    app.__pyzed_view__()


def test_lists_tables(tutorial):
    module = tutorial("lists_tables")
    app = module.Library()
    app.query = "le"
    assert {b["title"] for b in app.visible()} == {"The Left Hand of Darkness", "Solaris"}
    app.sort("Year")
    assert app.descending
    app.selected = module.BOOKS[0]
    app.mode = "List"
    app.__pyzed_view__()


def test_feedback(tutorial):
    app = tutorial("feedback").Signup()
    app.submit()
    assert app.tried and set(app.errors()) == {"name", "email", "password"} and app.notes
    app.name, app.email, app.password = "Ada", "ada@example.com", "analytical"
    app.submit()
    assert app.confirming
    app.__pyzed_view__()
    app.create()
    assert not app.confirming and app.name == "" and app.notes[-1][1] == "success"
    app.dismiss(app.notes[-1][0])
    app.__pyzed_view__()


def test_dodge_loop(tutorial):
    module = tutorial("dodge")
    app = module.Dodge(seed=1)
    for _ in range(120):
        app.tick(1 / 60)
    assert app.time == pytest.approx(2.0) and app.blocks
    app.blocks.append(module.game.Rect(app.x, module.PLAYER_Y, 20, 20))
    app.tick(1 / 60)
    assert app.over and app.subscriptions() == []
    app.on_key("enter")
    assert not app.over


def test_contacts_backend(tutorial, tmp_path):
    module = tutorial("contacts_backend")
    repo = module.ContactsRepository(tmp_path / "contacts.db", delay=0)
    assert [c["name"] for c in repo.search()] == ["Ada Lovelace", "Alan Turing"]
    repo.add("Grace Hopper", "grace@example.com")
    assert [c["name"] for c in repo.search("grace")] == ["Grace Hopper"]
    with pytest.raises(ValueError):
        repo.add("", "nobody")
    app = module.Contacts(repo)
    app.loaded(repo.search())
    app.__pyzed_view__()
