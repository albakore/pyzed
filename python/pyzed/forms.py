"""Helpers for forms backed by validation libraries (Pydantic, SQLModel, Django, FastAPI)."""

from __future__ import annotations

from typing import Any, Dict, Iterable

# Locations FastAPI puts in front of the field name in a 422 response.
_REQUEST_PARTS = {"body", "query", "path", "header", "cookie", "form"}


def validation_errors(error: Any) -> Dict[str, str]:
    """Maps a validation error to ``{field: message}``, ready for ``ui.field(..., error=)``.

    ``error`` can be a Pydantic (or SQLModel) ``ValidationError``, a Django
    ``ValidationError``, the JSON of a FastAPI 422 response (``{"detail": [...]}``) or its
    ``detail`` list. Nested fields are joined with dots (``"address.city"``) and errors that
    belong to no field use the key ``""``. Only the first message of each field is kept.
    """
    if hasattr(error, "message_dict"):  # Django, raised with a dict of fields
        return _first({("" if k == "__all__" else k): v for k, v in error.message_dict.items()})
    if hasattr(error, "errors") and callable(error.errors):  # Pydantic
        return _from_items(error.errors())
    if hasattr(error, "messages"):  # Django, raised with a message or a list
        return {"": error.messages[0]} if error.messages else {}
    if isinstance(error, dict):
        detail = error.get("detail", error)
        if isinstance(detail, str):
            return {"": detail}
        if isinstance(detail, dict):
            return _first(detail)
        error = detail
    if isinstance(error, (list, tuple)):
        return _from_items(error)
    return {"": str(error)} if error else {}


def _from_items(items: Iterable[Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for item in items:
        loc = [str(part) for part in item.get("loc", ())]
        if len(loc) > 1 and loc[0] in _REQUEST_PARTS:
            loc = loc[1:]
        elif loc and loc[0] in _REQUEST_PARTS:
            loc = []
        message = str(item.get("msg", ""))
        if message.startswith("Value error, "):
            message = message[len("Value error, "):]
        out.setdefault(".".join(loc), message)
    return out


def _first(fields: Dict[str, Any]) -> Dict[str, str]:
    out = {}
    for name, messages in fields.items():
        if isinstance(messages, (list, tuple)):
            if not messages:
                continue
            messages = messages[0]
        out[name] = str(messages)
    return out
