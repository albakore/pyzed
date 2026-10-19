"""Data binding and validation for designed forms.

A control's ``bind`` names a field of the form's data (``form.data``): ``"name"``, or a
path such as ``"customer.address.city"`` or ``"items.0.title"``. Input controls bind in both
directions: they show the field and write back what the user types or picks. Display
controls (labels, badges, progress bars, tables...) only show it, and their ``bind`` may also
be a Python expression over the data's fields (``f"{first} {last}"``, ``len(items)``).

A control's ``rules`` say what its value must be. ``check`` returns the message of the first
rule it breaks::

    check("", {"required": True}, "input")             # "This field is required"
    check("ab", {"min_length": 3}, "input")            # "At least 3 characters"

Texts that start with ``@`` are translation keys: ``"@login.title"`` shows
``pz.t("login.title")`` (``translate``), and ``"@@"`` writes a literal ``@``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, Union

from .. import i18n

#: The property each control type binds, and whether the user changes it (two-way).
BIND_PROPS: Dict[str, Tuple[str, bool]] = {
    "input": ("text", True), "text_area": ("text", True), "search": ("text", True),
    "checkbox": ("checked", True), "switch": ("checked", True),
    "radio": ("selected", True), "select": ("selected", True), "segmented": ("selected", True),
    "tabs": ("selected", True), "list_box": ("selected", True),
    "slider": ("value", True), "number": ("value", True),
    "label": ("text", False), "heading": ("text", False), "badge": ("text", False), "link": ("text", False),
    "chip": ("text", False), "markdown": ("text", False), "callout": ("text", False), "kbd": ("keys", False),
    "avatar": ("initials", False), "stat": ("value", False), "progress": ("value", False),
    "image": ("source", False), "chart": ("values", False), "table": ("data", False),
}

#: Validation rules, in the order they are checked, with the kinds of control they apply to.
RULES: Tuple[str, ...] = ("required", "min_length", "max_length", "pattern", "min", "max", "message")
TEXT_TYPES = frozenset({"input", "text_area", "search"})
NUMBER_TYPES = frozenset({"slider", "number"})

_PATH = re.compile(r"^[A-Za-z_]\w*(\.(\w+))*$")
_MISSING = object()


def bound_prop(type_: str) -> Optional[str]:
    """The property a control of ``type_`` binds (``None`` if it cannot be bound)."""
    entry = BIND_PROPS.get(type_)
    return entry[0] if entry else None


def two_way(type_: str) -> bool:
    """Whether a control of ``type_`` writes the user's changes back to the data."""
    entry = BIND_PROPS.get(type_)
    return bool(entry and entry[1])


def rules_for(type_: str) -> Tuple[str, ...]:
    """The validation rules that make sense for ``type_`` (none for display controls)."""
    if not two_way(type_):
        return ()
    if type_ in TEXT_TYPES:
        return ("required", "min_length", "max_length", "pattern", "message")
    if type_ in NUMBER_TYPES:
        return ("min", "max", "message")
    return ("required", "message")


def is_path(text: str) -> bool:
    """Whether ``text`` is a field path (``"name"``, ``"customer.city"``, ``"items.0"``) rather than an
    expression."""
    return bool(_PATH.match(text.strip()))


def _step(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, _MISSING)
    if isinstance(value, Sequence) and not isinstance(value, str) and key.isdigit():
        index = int(key)
        return value[index] if index < len(value) else _MISSING
    return getattr(value, key, _MISSING)


def read(data: Any, path: str, default: Any = None) -> Any:
    """The field at ``path`` in ``data`` (dicts, lists and objects), or ``default`` when it is missing."""
    value = data
    for key in path.strip().split("."):
        value = _step(value, key)
        if value is _MISSING:
            return default
    return value


def has(data: Any, path: str) -> bool:
    """Whether ``data`` has a field at ``path``."""
    return read(data, path, _MISSING) is not _MISSING


def write(data: Any, path: str, value: Any) -> None:
    """Sets the field at ``path`` in ``data``, creating missing dicts on the way."""
    *parents, last = path.strip().split(".")
    target = data
    for key in parents:
        child = _step(target, key)
        if child is _MISSING or child is None:
            child = {}
            _assign(target, key, child)
        target = child
    _assign(target, last, value)


def _assign(target: Any, key: str, value: Any) -> None:
    if isinstance(target, dict):
        target[key] = value
    elif isinstance(target, list) and key.isdigit():
        index = int(key)
        target.extend([None] * (index + 1 - len(target)))
        target[index] = value
    else:
        setattr(target, key, value)


class _View:
    """Attribute access over dicts, so expressions write ``customer.city`` for ``data["customer"]["city"]``."""

    __slots__ = ("_value",)

    def __init__(self, value: Any) -> None:
        self._value = value

    def __getattr__(self, key: str) -> Any:
        found = _step(self._value, key)
        if found is _MISSING:
            raise AttributeError(key)
        return _wrap(found)

    def __getitem__(self, key: Any) -> Any:
        return _wrap(self._value[key])

    def __iter__(self) -> Any:
        return (_wrap(v) for v in self._value)

    def __len__(self) -> int:
        return len(self._value)

    def __str__(self) -> str:
        return str(self._value)

    def __format__(self, spec: str) -> str:
        return format(self._value, spec)

    def __repr__(self) -> str:
        return repr(self._value)


def _wrap(value: Any) -> Any:
    return _View(value) if isinstance(value, Mapping) else value


def names(data: Any, **extra: Any) -> Dict[str, Any]:
    """The names an expression can use: the data's fields (top level), ``data`` itself and ``extra``."""
    out: Dict[str, Any] = {}
    if isinstance(data, Mapping):
        out.update({str(k): _wrap(v) for k, v in data.items() if isinstance(k, str)})
    elif data is not None:
        out.update({k: getattr(data, k) for k in dir(data) if not k.startswith("_")})
    out["data"] = _wrap(data)
    out.update(extra)
    return out


_code_cache: Dict[str, Any] = {}


def evaluate(expression: str, data: Any, **extra: Any) -> Any:
    """The value of ``bind`` for ``data``: the field when it is a path, else the Python expression evaluated
    over the data's fields. Raises on a missing field or a bad expression."""
    if is_path(expression):
        value = read(data, expression, _MISSING)
        if value is _MISSING:
            raise KeyError(expression)
        return value
    code = _code_cache.get(expression)
    if code is None:
        code = _code_cache[expression] = compile(expression, "<bind>", "eval")
    value = eval(code, {"__builtins__": __builtins__}, names(data, **extra))  # noqa: S307 - the form's own code
    return value._value if isinstance(value, _View) else value


def _empty(value: Any) -> bool:
    return value is None or value is False or (isinstance(value, (str, list, tuple, dict)) and not value)


def _number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def check(value: Any, rules: Mapping[str, Any], type_: str = "input") -> Optional[str]:
    """The message of the first rule ``value`` breaks, or ``None`` when it passes them all.

    ``required`` (a checked box for check boxes and switches), ``min_length``, ``max_length``, ``pattern``
    (a regular expression the whole text must match), ``min`` and ``max``. ``message``, when set, replaces
    the built-in message. Empty values only fail ``required``.
    """
    if not rules:
        return None
    error: Optional[str] = None
    if rules.get("required") and _empty(value):
        error = i18n.t("pyzed.validation.required")
    elif not _empty(value):
        text = "" if value is None else str(value)
        low, high = rules.get("min_length"), rules.get("max_length")
        pattern = rules.get("pattern")
        number = _number(value)
        if low not in (None, "") and len(text) < int(low):
            error = i18n.t("pyzed.validation.min_length", min=int(low))
        elif high not in (None, "") and len(text) > int(high):
            error = i18n.t("pyzed.validation.max_length", max=int(high))
        elif pattern and not _matches(pattern, text):
            error = i18n.t("pyzed.validation.pattern")
        elif rules.get("min") not in (None, "") and number is not None and number < float(rules["min"]):
            error = i18n.t("pyzed.validation.min", min=f"{float(rules['min']):g}")
        elif rules.get("max") not in (None, "") and number is not None and number > float(rules["max"]):
            error = i18n.t("pyzed.validation.max", max=f"{float(rules['max']):g}")
    if error is not None and rules.get("message"):
        return translate(str(rules["message"]))
    return error


def _matches(pattern: str, text: str) -> bool:
    try:
        return re.fullmatch(pattern, text) is not None
    except re.error:
        return True  # a broken pattern is the designer's problem, not the user's


def translate(value: Any, language: Optional[str] = None) -> Any:
    """``value`` with ``@key`` texts looked up in the current (or given) language; lists are translated item by
    item and ``@@`` stands for a literal ``@``."""
    if isinstance(value, str) and value.startswith("@"):
        if value.startswith("@@"):
            return value[1:]
        key = value[1:].strip()
        return i18n.t(key, language=language) if key else value
    if isinstance(value, list) and any(isinstance(v, str) and v.startswith("@") for v in value):
        return [translate(v, language) for v in value]
    return value


def load_texts(path: Optional[Union[str, Path]]) -> list:
    """Loads the translation catalogs of the form at ``path``: ``locales/`` next to it and in the folders
    above, up to the project root. Returns the languages found."""
    if path is None:
        return []
    found: list = []
    folder = Path(path).resolve().parent
    for candidate in (folder, *folder.parents):
        locales = candidate / "locales"
        if locales.is_dir():
            found += [lang for lang in i18n.load(locales) if lang not in found]
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            break
    return found
