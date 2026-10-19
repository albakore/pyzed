"""The built-in reference (pyzed.reference), its browser and the designer's help."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import pyzed as pz
from pyzed import i18n, reference, ui
from pyzed.designer import help as designer_help, new
from pyzed.designer.app import Designer

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def english():
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def test_every_library_entry_and_control_has_a_page():
    entries = reference.entries()
    ids = [e.id for e in entries]
    assert len(ids) == len(set(ids)) > 300
    assert {"control:button", "script:form", "script:event", "pyzed.text", "pyzed.ui.button", "page:widgets"} <= set(ids)
    for entry in entries:
        page = reference.page(entry.id)
        assert page.entry == entry and page.body.strip(), entry.id
    sections = [s for s, _ in reference.sections()]
    assert sections[:2] == ["Form controls", "Form code"] and "Core widgets" in sections
    groups = [g for s, gs in reference.sections() if s == "Form controls" for g, _ in gs]
    assert len(groups) == len(set(groups))  # one heading per toolbox category


def test_pages_use_the_live_signature_and_the_shipped_descriptions():
    page = reference.page("pyzed.ui.button")
    assert page.title == "ui.button" and page.url.endswith("/reference/ui/#button")
    assert "button(\n    content=None" in page.body and "| `on_press` |" in page.body
    assert "The Zed button." in page.body
    theme = reference.page("pyzed.Theme")
    assert "Methods and properties" in theme.body and "ref:pyzed.Theme.derive" in theme.body
    # site links become internal ones when the target has a page here
    assert "](ref:pyzed.canvas)" in reference.page("page:draw").body
    i18n.set_language("es")
    assert "Un texto." in reference.page("pyzed.text").body
    assert reference.page("pyzed.text").url.startswith(reference.SITE + "es/")


def test_search_and_lookup():
    titles = [e.title for e in reference.search("button")]
    assert titles[:3] == ["Button", "pz.button", "ui.button"]
    assert "ui.tab_bar" in [e.title for e in reference.search("tab bar")]
    assert reference.search("") == []
    assert reference.lookup("ui.button") == "pyzed.ui.button"
    assert reference.lookup("pz.text") == "pyzed.text"
    assert reference.lookup("Theme.derive") == "pyzed.Theme.derive"
    assert reference.lookup("text") == "pyzed.text"
    assert reference.lookup("nothing_like_this") is None


def test_user_components_get_a_page():
    class StarRating(pz.Component):
        """Stars to rate something."""

        value: int = 3
        count: int = 5

        def render(self):
            return pz.text("★" * self.value)

    page = reference.page("component:StarRating")
    assert page.entry.section == "Your components"
    assert "Stars to rate something." in page.body and "| `count` |" in page.body
    assert reference.lookup("StarRating") == "component:StarRating"
    assert "control:star_rating" not in [e.id for e in reference.entries()]


def test_control_pages_and_code_lookup():
    body = reference.page("control:slider").body
    assert "| `value` | float |" in body and "`slider1_change(form, event)`" in body
    assert "    form.slider1.value = 10" in body and "ref:pyzed.ui.slider" in body
    assert designer_help.prop_doc("table", "selected").startswith("Index of the selected row")
    assert designer_help.word_at("    form.label1.text = 1", 18) == "form.label1.text"
    assert designer_help.word_at("x = ui.button('a')", 9) == "ui.button"
    assert designer_help.lookup_code("event.value") == "script:event"
    assert designer_help.lookup_code("form.close") == "script:form"
    assert designer_help.lookup_code("ui.button") == "pyzed.ui.button"
    i18n.set_language("es")
    body = reference.page("control:slider").body
    assert "## Propiedades" in body and "Se ejecuta cuando cambia el valor de slider1" in body


def test_tables_as_lists():
    md = "Intro\n\n| A | B |\n| --- | --- |\n| `x` | one \\| two |\n| `y` | — |\n\n```\n| not | a table |\n```"
    assert reference.tables_as_lists(md) == "Intro\n\n- `x`: one | two\n- `y`\n\n```\n| not | a table |\n```"


def test_browser_history_and_links():
    browser = reference.Browser()
    assert browser.page() is None and browser.revision == 0
    assert browser.open("pyzed.ui.button") and not browser.open("nope")
    assert "Components (pyzed.ui)" in browser.expanded
    browser.follow("ref:pyzed.text")
    assert browser.current == "pyzed.text" and browser.past == ["pyzed.ui.button"]
    browser.back()
    assert browser.current == "pyzed.ui.button" and browser.future == ["pyzed.text"]
    browser.forward()
    assert browser.current == "pyzed.text" and browser.revision == 4
    assert browser.follow("/pyzed/guides/layout/") == reference.SITE + "guides/layout/"
    assert browser.follow("https://example.com") == "https://example.com"
    browser.set_query("slider")
    assert browser.results()[0].id == "control:slider"
    browser.toggle("Themes")
    assert "Themes" in browser.expanded
    browser.toggle("Themes")
    assert "Themes" not in browser.expanded
    for query in ("", "slider", "zzzz"):
        browser.set_query(query)
        assert repr(ui.reference_browser(browser, on_open_url=lambda url: None)).startswith("<Widget row")
    assert repr(ui.reference_browser(reference.Browser())).startswith("<Widget row")


def test_designer_reference_tab(tmp_path):
    from pyzed.designer import commands

    app = Designer(new.new_form(tmp_path / "shell", template="sidebar"), language_servers=False)
    app.window_size = (1440, 900)
    app.doc.selection = ["nav1"]
    app.reference_here()  # Shift+F1 with a button selected
    assert app.help_shown and app.help.current == "control:button"
    assert app.view() is not None
    assert designer_help.lookup_code("form.nav1.text", app.doc.form) == "control:button"
    app._select_tab("0")
    assert app.help_open and not app.help_shown
    app._select_tab("__reference__")
    assert app.help_shown
    app._close_tab("__reference__")
    assert not app.help_open and not app.help_shown
    assert commands.BY_ID["reference"].keys == "shift-f1" and commands.BY_ID["reference"].global_keys
    app.open_context_menu("nav1")
    assert "Help" in [i.label for i in app._context_items() if i != ui.SEPARATOR]


def test_shipped_descriptions_match_the_docs_sources():
    scripts = ROOT / "docs" / "scripts"
    if not (scripts / "gen_api.py").is_file():
        pytest.skip("not a source checkout")
    code = ("import sys; sys.path.insert(0, %r); import gen_api; "
            "sys.stdout.buffer.write(gen_api.export(sys.argv[1]).encode('utf-8'))") % str(scripts)
    for lang in reference.languages():
        # bytes, not text: the console encoding on Windows can't hold every character of the descriptions
        out = subprocess.run([sys.executable, "-c", code, lang], capture_output=True, check=True).stdout
        fresh = out.decode("utf-8")
        shipped = (Path(reference.__file__).parent / "_reference" / f"{lang}.json").read_text(encoding="utf-8")
        assert json.loads(fresh) == json.loads(shipped), f"run docs/scripts/gen_api.py ({lang})"
