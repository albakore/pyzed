"""Translations, ready-made dialogs and opening forms from code."""

import pytest

import pyzed as pz
from pyzed import designer, i18n, ui
from pyzed.designer.runtime import FormApp


@pytest.fixture(autouse=True)
def english():
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def test_translations_fall_back_and_format():
    i18n.add("en", {"greeting": "Hello, {name}!", "menu": {"open": "Open"}})
    i18n.add("es", {"greeting": "¡Hola, {name}!"})
    assert pz.t("greeting", name="Kev") == "Hello, Kev!"
    i18n.set_language("es-AR")
    assert i18n.language() == "es_ar"
    assert pz.t("greeting", name="Kev") == "¡Hola, Kev!"  # es_ar -> es
    assert pz.t("menu.open") == "Open"  # missing in Spanish -> English
    assert pz.t("missing.key") == "missing.key"
    assert pz.t("missing.key", default="?") == "?"
    assert pz.t("greeting", language="en", name="Ana") == "Hello, Ana!"
    assert i18n.has("menu.open") and not i18n.has("nope")


def test_plurals_and_listeners():
    i18n.add("en", {"files": {"zero": "No files", "one": "{count} file", "other": "{count} files"}})
    assert [pz.t("files", count=n) for n in (0, 1, 3)] == ["No files", "1 file", "3 files"]
    seen = []
    remove = i18n.on_change(seen.append)
    i18n.set_language("es")
    i18n.set_language("es")  # no change, no call
    remove()
    i18n.set_language("en")
    assert seen == ["es"]


def test_catalog_files(tmp_path):
    (tmp_path / "fr.json").write_text('{"hello": "Bonjour"}', encoding="utf-8")
    (tmp_path / "it.toml").write_text('hello = "Ciao"\n[menu]\nopen = "Apri"\n', encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    assert i18n.load(tmp_path) == ["fr", "it"]
    assert pz.t("hello", language="fr") == "Bonjour"
    assert pz.t("menu.open", language="it") == "Apri"
    assert {"en", "es", "fr", "it"} <= set(i18n.languages())


def test_system_language(monkeypatch):
    monkeypatch.setenv("LC_ALL", "es_AR.UTF-8")
    assert i18n.system_language() == "es_ar"


def test_dialogs_follow_the_language():
    assert pz.t("pyzed.cancel") == "Cancel"
    i18n.set_language("es")
    assert pz.t("pyzed.cancel") == "Cancelar"
    assert pz.t("pyzed.unsaved.message", name="a.py") == "¿Guardar los cambios de a.py antes de cerrar?"
    assert ui.dialog_layer("base") == "base"
    for dialog in (
        ui.alert("Saved", lambda: None, kind="success"),
        ui.confirm("Delete?", lambda: None, lambda: None, danger=True),
        ui.prompt("Rename", "a", lambda v: None, lambda: None, lambda: None, message="New name"),
        ui.choice("Pick one", [("A", lambda: None), ("B", lambda: None)], lambda: None),
        ui.unsaved_changes("a.py", lambda: None, lambda: None, lambda: None),
    ):
        assert repr(dialog) == "<Widget container>.on(key_down)"  # Escape closes it
        assert repr(ui.dialog_layer("base", dialog, on_dismiss=lambda: None)) == "<Widget stack>"


def test_dialogs_render(tmp_path):
    class Demo(pz.App):
        def view(self):
            return ui.dialog_layer(pz.text("app"), ui.confirm("Delete 3 files?", None, None, danger=True))

    pz.screenshot(Demo, tmp_path / "dialog.png", size=(500, 300), scale=1)
    assert (tmp_path / "dialog.png").stat().st_size > 0


def test_new_form_and_open_from_a_handler(tmp_path):
    path = designer.new_form(tmp_path / "order-details", title="Order")
    assert path.name == "order-details.pzform" and path.with_suffix(".py").exists()
    form = designer.load(path)
    assert (form.name, form.title) == ("OrderDetails", "Order")
    with pytest.raises(FileExistsError):
        designer.new_form(path)

    window = designer.form_window("order-details", folder=tmp_path, data={"id": 7})
    assert window.form.data == {"id": 7} and window.title == "Order"

    main = designer.Form(name="Main")
    app = FormApp(main, {}, tmp_path / "main.pzform")
    assert app.form.data is None
    assert repr(app.form.open("order-details", data=1)) == "Command.open_window(...)"
    assert repr(app.form.open(designer.Form(title="Built in code"))) == "Command.open_window(...)"
    with pytest.raises(FileNotFoundError):
        app.form.open("nowhere")


def test_project_new_form(tmp_path):
    from pyzed import project

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "shop"\n\n[tool.pyzed]\nui = "ui"\n', encoding="utf-8")
    created = project.find(tmp_path)
    path = created.new_form("settings", title="Settings")
    assert path == created.ui_dir / "settings.pzform" and path in created.forms()


def test_designer_menus_code_panel_and_color_picker_are_translated(tmp_path):
    import re
    from pathlib import Path

    from pyzed.designer import code_panel, locale, new, settings_ui
    from pyzed.designer.app import Designer

    # Every text the code panel and the settings show has a Spanish translation.
    source = Path(code_panel.__file__).read_text(encoding="utf-8")
    texts = set(re.findall(r'tr\("([^"]+)"', source))
    assert len(texts) > 15
    texts |= {text for s in settings_ui.SETTINGS for text in (s.title, s.description) if text}
    texts |= {label for s in settings_ui.SETTINGS if not callable(s.options) for _, label in s.options}
    texts |= {text for group, pages in settings_ui.PAGES for text in (group, *(title for _, title, _ in pages))}
    assert len(texts) > 100
    assert sorted(text for text in texts if text not in locale._ES and text not in ("ty", "ruff")) == []

    app = Designer(new.new_form(tmp_path / "shell", template="sidebar"), language_servers=False)
    app.window_size = (1440, 900)
    i18n.set_language("es")
    app.open_context_menu("nav1")
    labels = [item.label for item in app._context_items() if item != ui.SEPARATOR]
    assert labels[0] == "Ver código" and "Bloquear" in labels and "Eliminar" in labels
    assert pz.t("pyzed.color.gradient") == "Degradado"
    assert ui.ColorPicker(pz.Gradient(["#000", "#fff"])) is not None
    assert app.window_title().endswith("— Pyzed Design")
    assert app.status_bar(app.theme_obj) is not None
    from pyzed.designer import components
    assert all(components.get(type_).description in locale._ES for type_ in ("label", "button", "table", "timer"))


def test_every_designer_text_has_a_spanish_translation():
    import ast
    from pathlib import Path

    from pyzed.designer import locale

    folder = Path(locale.__file__).parent
    texts = set()
    for path in folder.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "tr" and node.args
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                texts.add((path.name, node.args[0].value))
    assert len(texts) > 1000
    assert sorted(f"{name}: {text}" for name, text in texts if text not in locale._ES) == []
