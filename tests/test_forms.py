"""pz.validation_errors and ui.field(error=): validation messages next to form fields."""

import pytest

import pyzed as pz
from pyzed import ui
from ui_tree import install


def test_fastapi_422_detail_drops_the_request_part():
    response = {"detail": [
        {"loc": ["body", "title"], "msg": "String should have at least 1 character", "type": "string_too_short"},
        {"loc": ["body", "address", "city"], "msg": "Field required", "type": "missing"},
        {"loc": ["body"], "msg": "Invalid JSON", "type": "json_invalid"},
        {"loc": ["body", "title"], "msg": "second message is ignored", "type": "x"},
    ]}
    assert pz.validation_errors(response) == {
        "title": "String should have at least 1 character",
        "address.city": "Field required",
        "": "Invalid JSON",
    }
    assert pz.validation_errors(response["detail"]) == pz.validation_errors(response)
    assert pz.validation_errors({"detail": "Note not found"}) == {"": "Note not found"}


def test_pydantic_errors_strip_the_value_error_prefix():
    pydantic = pytest.importorskip("pydantic")

    class Item(pydantic.BaseModel):
        name: str = pydantic.Field(min_length=2)
        quantity: int

        @pydantic.field_validator("quantity")
        @classmethod
        def positive(cls, value):
            if value < 0:
                raise ValueError("must be zero or more")
            return value

    with pytest.raises(pydantic.ValidationError) as caught:
        Item(name="x", quantity=-1)
    errors = pz.validation_errors(caught.value)
    assert set(errors) == {"name", "quantity"}
    assert errors["quantity"] == "must be zero or more"


def test_django_style_errors():
    class DjangoError(Exception):
        def __init__(self, fields=None, messages=None):
            if fields is not None:
                self.message_dict = fields
            self.messages = messages or []

    assert pz.validation_errors(DjangoError({"isbn": ["Too short.", "Digits only."], "__all__": ["Duplicate."]})) == {
        "isbn": "Too short.", "": "Duplicate."}
    assert pz.validation_errors(DjangoError(messages=["Nope."])) == {"": "Nope."}


def test_other_values():
    assert pz.validation_errors(None) == {}
    assert pz.validation_errors("Server unreachable") == {"": "Server unreachable"}
    assert pz.validation_errors({"title": ["Required"], "body": []}) == {"title": "Required"}


def test_field_shows_the_error_under_its_title(monkeypatch):
    install(monkeypatch)
    t = pz.themes.get("One Dark")
    assert ui.field("Title", None, theme=t).texts() == ["Title"]
    failing = ui.field("Title", None, description="Shown in the list", error="Field required", theme=t)
    assert failing.texts() == ["Title", "Shown in the list", "Field required"]
    error = failing.find("text", lambda n: n.args[0] == "Field required")
    assert error.props["color"] == t.error


def test_select_hands_back_the_option_objects(monkeypatch):
    install(monkeypatch)

    class Author:
        def __init__(self, pk, name):
            self.pk, self.name = pk, name

        def __str__(self):
            return self.name

    authors = [Author(1, "Borges"), Author(2, "Le Guin")]
    picked = []
    widget = ui.select(authors, authors[0], picked.append, theme=pz.themes.get("One Dark"))
    options, selected, on_select = widget.args
    assert options == ["Borges", "Le Guin"] and selected == "Borges"
    on_select("Le Guin")
    assert picked == [authors[1]]

    plain = ui.select(["a", "b"], "a", picked.append)
    assert plain.args[2] == picked.append  # strings need no translation
