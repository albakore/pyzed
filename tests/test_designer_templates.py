"""Form templates and the designer's translations are data files, not Python code."""

import json

from pyzed import i18n
from pyzed.designer import locale, new


def test_builtin_templates_are_folders():
    names = [t.name for t in new.templates()]
    assert names[:5] == ["blank", "dialog", "login", "sidebar", "settings"]
    for name in names[:5]:
        folder = new.TEMPLATES_DIR / name
        assert (folder / "template.json").is_file() and (folder / "form.pzform").is_file()
    assert not list(new.TEMPLATES_DIR.rglob("*.py"))  # handlers are .py.tmpl data files


def test_dialog_template_titles_wires_and_resizes():
    doc = new.create("Confirm", title="Delete file?", template="dialog")
    form = doc.form
    assert form.name == "Confirm" and form.title == "Delete file?" and (form.width, form.height) == (420, 220)
    assert form["heading"].props["text"] == "Delete file?"
    assert form["ok"].events["click"] == "ok_click" and "return form.close()" in doc.code
    wide = new.create("Confirm", template="dialog", width=620, height=300).form
    # the buttons stay at the bottom and the text stretches, as their anchors say
    assert wide["buttons"].y == form["buttons"].y + 80 and wide["message"].width == form["message"].width + 200


def test_load_your_own_template_folder(tmp_path):
    folder = tmp_path / "toolbar"
    folder.mkdir()
    (folder / "template.json").write_text(json.dumps({"label": "Toolbar", "icon": "panel-top",
                                                      "description": "A row of buttons on top."}))
    base = new.create("Base", template="blank").form
    data = base.to_dict()
    data["controls"] = [{"name": "save", "type": "button", "x": 8, "y": 8, "width": 80, "height": 30,
                         "props": {"text": "Save {title}"}, "events": {"click": "save_click"}}]
    (folder / "form.pzform").write_text(json.dumps(data))
    (folder / "handlers.py.tmpl").write_text('def save_click(form, event):\n    print("saved")\n')
    [template] = new.load_templates(tmp_path)
    try:
        assert template.name == "toolbar" and template in new.templates()
        doc = new.create("Editor", title="notes", template="toolbar")
        assert doc.form["save"].props["text"] == "Save notes" and 'print("saved")' in doc.code
    finally:
        new._TEMPLATES.pop("toolbar")


def test_translations_are_json():
    data = json.loads((locale.LOCALES_DIR / "es.json").read_text(encoding="utf-8"))
    assert data["designer"]["Save"] == "Guardar" and locale._ES == data["designer"]
    i18n.set_language("es")
    try:
        assert locale.tr("Save as…") == "Guardar como…" and locale.tr("Not translated") == "Not translated"
    finally:
        i18n.set_language("en")


def test_every_designer_text_has_a_spanish_translation():
    """Each literal ``tr("...")`` in the designer's modules is in ``locales/es.json``."""
    import ast
    from pathlib import Path

    missing = {}
    for path in sorted(Path(locale.__file__).parent.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == "tr" \
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) \
                    and node.args[0].value not in locale._ES:
                missing.setdefault(path.name, []).append(node.args[0].value)
    assert missing == {}
