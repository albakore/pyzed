"""Spreadsheets: ``ui.Spreadsheet``, a grid like Google Sheets or Excel over a ``pz.Workbook``.

The workbook (``pz.Workbook``) holds the data, the formulas and the formats, and does the
work in Rust: recalculation, sorting, filters, undo, CSV and Excel files. ``pz.sheet(book)``
is the bare grid (also Rust: it draws only the visible cells). ``ui.Spreadsheet`` adds what
an office suite has around it: the toolbar, the right-click menus, the dropdowns of
validated cells, the filter menus, find and replace, the side panels for conditional
formatting and data validation, the sheet tabs and the sum of the selection.
"""

from __future__ import annotations

import os
import types
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .. import _core
from ..component import Component
from ..icons import icon as _icon
from ..theme import Theme, alpha
from .base import _theme, button, divider, icon_button, label, tooltip_text
from .controls import select
from .inputs import checkbox, input as text_input
from .lists import SEPARATOR, MenuItem, menu

__all__ = ["Spreadsheet", "sheet_colors", "NUMBER_FORMATS", "PALETTE"]

#: The number formats of the toolbar's "123" menu: ``(label, format code, example)``.
NUMBER_FORMATS: Sequence[Tuple[str, Optional[str], str]] = (
    ("Automatic", None, "1000.12"),
    ("Plain text", "@", "1000.12"),
    ("Number", "#,##0.00", "1,000.12"),
    ("Percent", "0.00%", "10.12%"),
    ("Scientific", "0.00E+00", "1.01E+03"),
    ("Financial", "#,##0.00;(#,##0.00)", "(1,000.12)"),
    ("Currency", "$#,##0.00", "$1,000.12"),
    ("Currency rounded", "$#,##0", "$1,000"),
    ("Date", "yyyy-mm-dd", "2026-09-26"),
    ("Time", "h:mm:ss AM/PM", "3:59:00 PM"),
    ("Date time", "yyyy-mm-dd h:mm", "2026-09-26 15:59"),
    ("Duration", "[h]:mm:ss", "24:01:00"),
)

#: The colors of the text and fill color menus (rows of the Sheets palette).
PALETTE: Sequence[Sequence[str]] = (
    ("#000000", "#434343", "#666666", "#999999", "#b7b7b7", "#cccccc", "#d9d9d9", "#efefef", "#f3f3f3", "#ffffff"),
    ("#980000", "#ff0000", "#ff9900", "#ffff00", "#00ff00", "#00ffff", "#4a86e8", "#0000ff", "#9900ff", "#ff00ff"),
    ("#e6b8af", "#f4cccc", "#fce5cd", "#fff2cc", "#d9ead3", "#d0e0e3", "#c9daf8", "#cfe2f3", "#d9d2e9", "#ead1dc"),
    ("#dd7e6b", "#ea9999", "#f9cb9c", "#ffe599", "#b6d7a8", "#a2c4c9", "#a4c2f4", "#9fc5e8", "#b4a7d6", "#d5a6bd"),
    ("#a61c00", "#cc0000", "#e69138", "#f1c232", "#6aa84f", "#45818e", "#3c78d8", "#3d85c6", "#674ea7", "#a64d79"),
    ("#5b0f00", "#660000", "#783f04", "#7f6000", "#274e13", "#0c343d", "#1c4587", "#073763", "#20124d", "#4c1130"),
)

_SIZES = (6, 7, 8, 9, 10, 11, 12, 14, 18, 24, 36)

#: Conditions of the conditional formatting panel: ``(label, rule, values it needs)``.
_RULES: Sequence[Tuple[str, str, int]] = (
    ("Greater than", ">", 1),
    ("Greater than or equal to", ">=", 1),
    ("Less than", "<", 1),
    ("Less than or equal to", "<=", 1),
    ("Is equal to", "=", 1),
    ("Is not equal to", "<>", 1),
    ("Is between", "between", 2),
    ("Is not between", "not_between", 2),
    ("Text contains", "contains", 1),
    ("Text does not contain", "not_contains", 1),
    ("Text starts with", "starts_with", 1),
    ("Text ends with", "ends_with", 1),
    ("Is empty", "empty", 0),
    ("Is not empty", "not_empty", 0),
    ("Duplicate values", "duplicate", 0),
    ("Unique values", "unique", 0),
    ("Custom formula is", "formula", 1),
    ("Color scale", "scale", 0),
    ("Data bar", "bar", 0),
)

#: Criteria of the data validation panel.
_CHECKS: Sequence[Tuple[str, str]] = (
    ("Dropdown (from a list)", "list"),
    ("Dropdown (from a range)", "range"),
    ("Number between", "number"),
    ("Whole number between", "integer"),
    ("Date between", "date"),
    ("Text length between", "length"),
    ("Checkbox", "checkbox"),
    ("Custom formula is", "formula"),
)

TOOLBAR_H = 40
TABS_H = 36
FIND_H = 44


def sheet_colors(theme: Optional[Theme] = None) -> Dict[str, Any]:
    """The colors of ``pz.sheet`` taken from a theme (what ``ui.Spreadsheet`` passes)."""
    t = _theme(theme)
    dark = t.appearance == "dark"
    refs = list(t.players[:8]) if t.players else []
    return {
        "background": t.editor,
        "grid": alpha(t.border_variant, 0.9 if dark else 1.0),
        "header": t.surface,
        "header_text": t.text_muted,
        "header_active": alpha(t.accent, 0.22),
        "header_active_text": t.text,
        "text": t.editor_text or t.text,
        "muted": t.text_muted,
        "accent": t.accent,
        "selection": alpha(t.accent, 0.14),
        "frozen": t.border,
        "editor": t.editor,
        "border": t.border,
        "error": t.error,
        "note": t.warning,
        "popup": t.elevated,
        "popup_text": t.text,
        "popup_selected": t.element_selected,
        **({"refs": refs} if refs else {}),
    }


def _ns(d: Any) -> Any:
    return types.SimpleNamespace(**d) if isinstance(d, dict) else d


def _cols(rng: str) -> Tuple[str, str]:
    """The first and last column letters of a range (``"B2:D9"`` → ``("B", "D")``)."""
    a, _, b = rng.partition(":")
    letters = lambda s: "".join(ch for ch in s if ch.isalpha()) or "A"  # noqa: E731
    return letters(a), letters(b or a)


def _rows(rng: str) -> Tuple[int, int]:
    a, _, b = rng.partition(":")
    digits = lambda s, d: int("".join(ch for ch in s if ch.isdigit()) or d)  # noqa: E731
    return digits(a, 1), digits(b or a, 1048576)


def _col_index(letters: str) -> int:
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


class Spreadsheet(Component):
    """A spreadsheet like Google Sheets or Excel: a grid of cells with formulas, formats,
    sorting and filters, a toolbar, right-click menus, find and replace, data validation,
    conditional formatting and sheet tabs.

    ``book`` is the ``pz.Workbook`` it shows and edits (one is made when it is ``None``, and a
    path such as ``"sales.xlsx"`` opens that file; read it back with ``component.book``). Everything the user does goes to the workbook, so
    the app reads the data from it (``book["B2"]``, ``book.records()``...) and changes it from
    code the same way; the grid shows the changes at once.

    ``toolbar``, ``formula_bar``, ``tabs`` (the sheet tabs and the selection's sum),
    ``headers`` (column letters and row numbers) turn the parts on and off; ``readonly``
    allows selecting and copying only.

    Events:
        ``on_change(event)``: cells changed: ``event.value.action`` (``"edit"``, ``"paste"``,
        ``"fill"``, ``"clear"``, ``"undo"``, ``"redo"``, ``"format"``, ``"sort"``,
        ``"structure"``...), ``event.value.range`` and ``event.value.sheet``.
        ``on_select(event)``: the selection changed (``event.value.range``).
    """

    book: Any = None
    toolbar: bool = True
    formula_bar: bool = True
    tabs: bool = True
    headers: bool = True
    readonly: bool = False
    text_size: float = 13
    width: Any = "fill"
    height: Any = "fill"
    events = {
        "change": "Cells changed (``event.value.action``, ``event.value.range``, ``event.value.sheet``).",
        "select": "The selection changed (``event.value.range``).",
    }
    icon = "sheet"
    label = "Spreadsheet"
    category = "Display"
    size = (760, 420)
    cache = False

    def setup(self) -> None:
        if isinstance(self.book, (str, os.PathLike)):
            # A path (the designer's Properties panel gives text): open it, or start empty.
            path = os.fspath(self.book)
            try:
                self.book = _core.Workbook.open(path) if path.strip() else _core.Workbook()
            except (OSError, ValueError):
                self.book = _core.Workbook()
        elif self.book is None:
            self.book = _core.Workbook()
        self.open: Optional[str] = None  # the toolbar menu that is open
        self.menu: Optional[Dict[str, Any]] = None  # a context, dropdown or filter menu
        self.find: Optional[Dict[str, Any]] = None
        self.renaming: Optional[Tuple[int, str]] = None
        self.panel: Optional[str] = None  # "conditional" | "validation" | "note"
        self.form: Dict[str, Any] = {}
        self.message: Optional[str] = None
        self.view: Tuple[float, float] = (760.0, 420.0)  # the grid's size, to keep menus inside it

    # -- helpers -------------------------------------------------------------
    @property
    def wb(self) -> Any:
        return self.book

    def _offset(self) -> float:
        return (TOOLBAR_H if self.toolbar else 0) + (FIND_H if self.find else 0)

    def changed(self, action: str, rng: Optional[str] = None) -> Any:
        """Tells the parent that cells changed (and gives the grid the keyboard back)."""
        self.wb.focused = True
        return self.emit("change", types.SimpleNamespace(action=action, range=rng or self.wb.selection,
                                                         sheet=self.wb.sheet))

    def each(self, fn) -> Any:
        """Runs ``fn(range)`` on every selected range as one undo step."""
        ranges = list(self.wb.selections)
        self.wb.batch(lambda: [fn(r) for r in ranges])

    def fmt(self, **kwargs) -> Any:
        self.each(lambda r: self.wb.format(r, **kwargs))
        self.open = None
        return self.changed("format")

    def style(self) -> Dict[str, Any]:
        return self.wb.style(self.wb.active_cell)

    def toggle(self, key: str) -> Any:
        return self.fmt(**{key: not self.style().get(key, False)})

    # -- grid events -----------------------------------------------------------
    def on_grid_change(self, e: Dict[str, Any]) -> Any:
        return self.emit("change", _ns(e))

    def on_grid_select(self, e: Dict[str, Any]) -> Any:
        self.open = None
        return self.emit("select", types.SimpleNamespace(range=self.wb.selection, sheet=self.wb.sheet))

    def _seen(self, e: Dict[str, Any]) -> None:
        self.view = (e.get("view_width", self.view[0]), e.get("view_height", self.view[1]))

    def on_grid_context(self, e: Dict[str, Any]) -> None:
        self._seen(e)
        self.open = None
        self.menu = {"kind": "context", "target": e["kind"], "cell": e["cell"], "x": e["x"], "y": e["y"] + self._offset()}

    def on_grid_dropdown(self, e: Dict[str, Any]) -> None:
        self._seen(e)
        self.menu = {"kind": "dropdown", "cell": e["cell"], "options": e["options"], "x": e["x"],
                     "y": e["y"] + self._offset(), "width": max(160.0, e["width"])}

    def on_grid_filter(self, e: Dict[str, Any]) -> None:
        self._seen(e)
        col = e["column"]
        values = self.wb.filter_values(col)
        self.menu = {"kind": "filter", "column": col, "x": e["x"], "y": e["y"] + self._offset(), "query": "",
                     "shown": {v for v, shown in values if shown}, "values": [v for v, _ in values],
                     "condition": ""}

    def on_grid_find(self, e: Dict[str, Any]) -> Any:
        return self.open_find(e["mode"])

    def on_grid_invalid(self, e: Dict[str, Any]) -> None:
        self.message = e.get("message") or f"{e['value']!r} is not allowed in {e['cell']}."

    def close_menu(self) -> None:
        self.menu = None
        self.open = None
        self.wb.focused = True

    # -- find and replace ------------------------------------------------------
    def open_find(self, mode: str = "find") -> Any:
        self.find = {"mode": mode, "query": (self.find or {}).get("query", ""), "with": (self.find or {}).get("with", ""),
                     "case": False, "whole": False, "formulas": False, "all": False, "matches": [], "index": -1}
        self.wb.focused = False
        return _core.Command.select_all("pyzed-sheet-find")

    def search(self) -> None:
        f = self.find
        if not f:
            return
        f["matches"] = self.wb.find(f["query"], match_case=f["case"], whole_cell=f["whole"], formulas=f["formulas"],
                                    all_sheets=f["all"]) if f["query"] else []
        f["index"] = -1

    def find_step(self, step: int) -> None:
        f = self.find
        if not f:
            return
        if not f["matches"]:
            self.search()
        if not f["matches"]:
            return
        f["index"] = (f["index"] + step) % len(f["matches"])
        self.wb.select(f["matches"][f["index"]])

    def replace_one(self) -> Any:
        f = self.find
        if not f or not f["matches"]:
            self.find_step(1)
            return None
        cell = f["matches"][max(0, f["index"])]
        self.wb.replace(f["query"], f["with"], match_case=f["case"], whole_cell=f["whole"], cell=cell)
        self.search()
        self.find_step(1)
        return self.changed("replace", cell.split("!")[-1])

    def replace_all(self) -> Any:
        f = self.find
        if not f or not f["query"]:
            return None
        n = self.wb.replace(f["query"], f["with"], match_case=f["case"], whole_cell=f["whole"], all_sheets=f["all"])
        self.message = f"Replaced {n} occurrence{'s' if n != 1 else ''}."
        self.search()
        return self.changed("replace")

    # -- structure (context menu) ----------------------------------------------
    def structure(self, what: str) -> Any:
        wb = self.wb
        rng = wb.selection
        r0, r1 = _rows(rng)
        c0, c1 = _cols(rng)
        n_rows = min(r1, 1048576) - r0 + 1
        n_cols = _col_index(c1) - _col_index(c0) + 1
        if what == "row_above":
            wb.insert_rows(r0, n_rows)
        elif what == "row_below":
            wb.insert_rows(r1 + 1, n_rows)
        elif what == "col_left":
            wb.insert_cols(c0, n_cols)
        elif what == "col_right":
            wb.insert_cols(_core.Workbook.column_name(_col_index(c1) + 1), n_cols)
        elif what == "delete_rows":
            wb.delete_rows(r0, n_rows)
        elif what == "delete_cols":
            wb.delete_cols(c0, n_cols)
        elif what == "hide_rows":
            wb.hide_rows(list(range(r0, r1 + 1)))
        elif what == "hide_cols":
            wb.hide_cols([_core.Workbook.column_name(i) for i in range(_col_index(c0), _col_index(c1) + 1)])
        elif what == "show_rows":
            wb.show_rows(list(range(max(1, r0 - 1), r1 + 2)))
        elif what == "show_cols":
            wb.show_cols([_core.Workbook.column_name(i) for i in range(max(1, _col_index(c0) - 1), _col_index(c1) + 2)])
        elif what == "autofit":
            wb.autofit([_core.Workbook.column_name(i) for i in range(_col_index(c0), _col_index(c1) + 1)])
        self.menu = None
        return self.changed("structure")

    def sort(self, descending: bool) -> Any:
        rng = self.wb.selection
        c0, _ = _cols(rng)
        r0, r1 = _rows(rng)
        if r0 == r1:
            # One cell: the whole data region around it, like Sheets' "Sort range".
            region = self._region(self.wb.active_cell)
            if region:
                rng = region
                c0 = _cols(self.wb.active_cell)[0]
        header = bool(self.wb.filter_range and rng == self.wb.filter_range) or self._has_header(rng)
        self.wb.sort(rng, c0, descending=descending, header=header)
        self.menu = None
        self.open = None
        return self.changed("sort", rng)

    def _region(self, cell: str) -> Optional[str]:
        """The block of data around ``cell``, up to the first empty row and column on each side
        (Ctrl+A in Excel): totals under a blank row stay out of a sort."""
        used = self.wb.used_range
        if not used:
            return None
        name = _core.Workbook.column_name
        (u0, u1), (v0, v1) = _cols(used), _rows(used)
        c_lo, c_hi = _col_index(u0), _col_index(u1)
        grid = self.wb.values(used)  # grid[row - v0][col - c_lo]
        col, row = _col_index(_cols(cell)[0]), _rows(cell)[0]
        if not (c_lo <= col <= c_hi and v0 <= row <= v1):
            return None

        def row_empty(r: int, a: int, b: int) -> bool:
            return all(grid[r - v0][c - c_lo] in (None, "") for c in range(a, b + 1))

        def col_empty(c: int, a: int, b: int) -> bool:
            return all(grid[r - v0][c - c_lo] in (None, "") for r in range(a, b + 1))

        top = bottom = row
        left = right = col
        grown = True
        while grown:
            grown = False
            if top > v0 and not row_empty(top - 1, left, right):
                top, grown = top - 1, True
            if bottom < v1 and not row_empty(bottom + 1, left, right):
                bottom, grown = bottom + 1, True
            if left > c_lo and not col_empty(left - 1, top, bottom):
                left, grown = left - 1, True
            if right < c_hi and not col_empty(right + 1, top, bottom):
                right, grown = right + 1, True
        return f"{name(left)}{top}:{name(right)}{bottom}"

    def _has_header(self, rng: str) -> bool:
        """Whether a range's first row looks like a header: bold over plain cells, or text over numbers."""
        rows = self.wb.values(rng)
        if len(rows) < 2:
            return False
        c0, r0 = _col_index(_cols(rng)[0]), _rows(rng)[0]
        name = _core.Workbook.column_name
        top = [f"{name(c0 + i)}{r0}" for i, v in enumerate(rows[0]) if v is not None]
        if top and all(self.wb.style(a).get("bold") for a in top) and \
                not self.wb.style(f"{top[0][:len(top[0]) - len(str(r0))]}{r0 + 1}").get("bold"):
            return True
        return all(v is None or isinstance(v, str) for v in rows[0]) and any(
            isinstance(a, str) and isinstance(b, (int, float)) and not isinstance(b, bool)
            for a, b in zip(rows[0], rows[1]))

    def clip(self, what: str) -> Any:
        self.menu = None
        if what in ("copy", "cut"):
            return _core.Command.copy(self.wb.copy(cut=what == "cut"))
        values_only = what == "paste_values"

        def pasted(text: Any) -> Any:
            if text:
                self.wb.paste(str(text), values_only=values_only)
                return self.changed("paste")
            return None

        return _core.Command.paste(pasted)

    def clear(self, what: str) -> Any:
        self.each(lambda r: self.wb.clear(r, what))
        self.menu = None
        self.open = None
        return self.changed("clear")

    # -- sheet tabs ------------------------------------------------------------
    def go(self, index: int) -> Any:
        self.wb.active = index
        self.renaming = None
        self.wb.focused = True
        return self.emit("select", types.SimpleNamespace(range=self.wb.selection, sheet=self.wb.sheet))

    def add_sheet(self) -> Any:
        self.wb.add_sheet()
        return self.changed("sheets")

    def rename_done(self) -> Any:
        if self.renaming is None:
            return None
        index, name = self.renaming
        self.renaming = None
        name = name.strip()
        if name and name != self.wb.sheets[index]:
            try:
                self.wb.rename_sheet(index, name)
            except ValueError as err:
                self.message = str(err)
                return None
            return self.changed("sheets")
        return None

    def sheet_action(self, index: int, what: str) -> Any:
        wb = self.wb
        self.menu = None
        if what == "rename":
            self.renaming = (index, wb.sheets[index])
            wb.focused = False
            return _core.Command.select_all("pyzed-sheet-rename")
        if what == "duplicate":
            wb.duplicate_sheet(index)
        elif what == "delete" and len(wb.sheets) > 1:
            wb.remove_sheet(index)
        elif what == "left" and index > 0:
            wb.move_sheet(index, index - 1)
        elif what == "right" and index < len(wb.sheets) - 1:
            wb.move_sheet(index, index + 1)
        elif what.startswith("color:"):
            wb.tab_color(index, what[6:] or None)
        return self.changed("sheets")

    # -- panels ------------------------------------------------------------------
    def open_panel(self, name: str) -> None:
        self.open = None
        self.menu = None
        self.panel = name
        if name == "conditional":
            self.form = {"range": self.wb.selection, "rule": 0, "value": "", "value2": "", "fill": "#b7e1cd",
                         "color": "", "bold": False, "low": "#ffffff", "high": "#57bb8a"}
        elif name == "validation":
            options = self.wb.options(self.wb.active_cell) or []
            self.form = {"range": self.wb.selection, "check": 0, "items": ", ".join(options), "source": "",
                         "min": "", "max": "", "formula": "", "strict": True, "message": ""}
        elif name == "note":
            self.form = {"cell": self.wb.active_cell, "text": self.wb.note(self.wb.active_cell) or ""}

    def add_rule(self) -> Any:
        f = self.form
        _label, rule, needs = _RULES[f["rule"]]
        rng = f["range"] or self.wb.selection

        def num(v: str) -> Any:
            try:
                return float(v)
            except ValueError:
                return v

        kwargs: Dict[str, Any] = {}
        if rule == "scale":
            kwargs["colors"] = [f["low"], f["high"]]
        elif rule == "bar":
            kwargs["color"] = f["fill"] or "#57bb8a"
        else:
            if f["fill"]:
                kwargs["fill"] = f["fill"]
            if f["color"]:
                kwargs["color"] = f["color"]
            if f["bold"]:
                kwargs["bold"] = True
        value = num(f["value"]) if needs >= 1 else None
        value2 = num(f["value2"]) if needs >= 2 else None
        try:
            self.wb.conditional_format(rng, rule, value, value2, **kwargs)
        except ValueError as err:
            self.message = str(err)
            return None
        return self.changed("format", rng)

    def save_validation(self) -> Any:
        f = self.form
        check = _CHECKS[f["check"]][1]
        rng = f["range"] or self.wb.selection

        def bounds() -> Tuple[Optional[float], Optional[float]]:
            def n(v: str) -> Optional[float]:
                try:
                    return float(v) if v.strip() else None
                except ValueError:
                    return None
            return n(f["min"]), n(f["max"])

        kwargs: Dict[str, Any] = {"strict": f["strict"], "message": f["message"] or None}
        if check == "list":
            kwargs["options"] = [o.strip() for o in f["items"].split(",") if o.strip()]
        elif check == "range":
            kwargs["source"] = f["source"]
        elif check in ("number", "integer"):
            kwargs["number"] = bounds()
            kwargs["integer"] = check == "integer"
        elif check == "date":
            kwargs["date"] = (f["min"] or None, f["max"] or None)
        elif check == "length":
            lo, hi = bounds()
            kwargs["length"] = (None if lo is None else int(lo), None if hi is None else int(hi))
        elif check == "checkbox":
            kwargs = {"checkbox": True}
        elif check == "formula":
            kwargs["formula"] = f["formula"]
        try:
            self.wb.validate(rng, **kwargs)
        except (ValueError, TypeError) as err:
            self.message = str(err)
            return None
        self.panel = None
        return self.changed("validation", rng)

    def save_note(self) -> Any:
        self.wb.note(self.form["cell"], self.form["text"])
        self.panel = None
        return self.changed("note", self.form["cell"])

    # -- rendering ---------------------------------------------------------------
    def render(self) -> Any:
        t = _theme(None)
        wb = self.wb
        grid = _core.sheet(
            wb,
            colors=sheet_colors(t),
            text_size=self.text_size,
            formula_bar=self.formula_bar,
            headers=self.headers,
            readonly=self.readonly,
            on_change=self.on_grid_change,
            on_select=self.on_grid_select,
            on_context=self.on_grid_context,
            on_dropdown=self.on_grid_dropdown,
            on_filter=self.on_grid_filter,
            on_find=self.on_grid_find,
            on_invalid=self.on_grid_invalid,
        )
        middle: List[Any] = [grid]
        if self.panel:
            middle.append(self.render_panel(t))
        parts: List[Any] = []
        if self.toolbar:
            parts.append(self.render_toolbar(t))
        if self.find:
            parts.append(self.render_find(t))
        parts.append(_core.row(middle, width="fill", height="fill"))
        if self.tabs:
            parts.append(self.render_tabs(t))
        body = _core.column(parts, width=self.width, height=self.height)
        overlay = self.render_menu(t)
        if overlay is not None:
            x, y = self._place()
            body = _core.stack([
                body,
                _core.mouse_area(_core.container(None, width="fill", height="fill"), on_press=self.close_menu,
                                 on_right_press=self.close_menu),
                _core.pin(_core.opaque(overlay), x=x, y=y),
            ], width=self.width, height=self.height)
        if self.message:
            toast = _core.container(
                _core.row([label(self.message, theme=t),
                           icon_button("x", lambda: setattr(self, "message", None), size="sm", theme=t)],
                          spacing=8, align="center"),
                padding=(6, 8, 6, 12), bg=t.elevated, border_color=t.border, border_width=1, radius=t.radius)
            body = _core.stack([body, _core.container(toast, width="fill", height="fill", align_x="center",
                                                      align_y="end", padding=(0, 0, 48, 0))],
                               width=self.width, height=self.height)
        return body

    # Toolbar ------------------------------------------------------------------------
    def _tool(self, t: Theme, name: str, on_press: Any, tip: str, keys: Optional[str] = None,
              selected: bool = False) -> Any:
        return icon_button(name, None if self.readonly else on_press, tooltip=tip, keys=keys, selected=selected,
                           size="sm", theme=t)

    def _dropdown(self, t: Theme, key: str, base: Any, content: Any) -> Any:
        return _core.popup(base, content if self.open == key else None, on_dismiss=lambda: setattr(self, "open", None),
                           side="bottom", align="start", gap=4)

    def _opener(self, key: str):
        return lambda: setattr(self, "open", None if self.open == key else key)

    def _palette(self, t: Theme, on_pick, reset: str) -> Any:
        rows = [
            _core.row([
                _core.button(None, (lambda c=c: on_pick(c)), width=18, height=18, padding=0, bg=c, radius=9,
                             border_color=t.border_variant, border_width=1, hover_border_color=t.text)
                for c in line
            ], spacing=4)
            for line in PALETTE
        ]
        return _core.container(
            _core.column([button(reset, lambda: on_pick(None), icon="eraser", variant="ghost", size="sm", theme=t),
                          *rows], spacing=4),
            padding=8, bg=t.elevated, border_color=t.border, border_width=1, radius=t.radius,
        )

    def render_toolbar(self, t: Theme) -> Any:
        wb = self.wb
        st = self.style()
        sep = divider(vertical=True, theme=t)
        fmt_menu = menu([
            MenuItem(name, (lambda code=code: self.fmt(number_format=code or "General")), description=example,
                     checked=(st.get("number_format") or None) == code)
            for name, code, example in NUMBER_FORMATS
        ], width=230, theme=t)
        size = int(st.get("size") or 10)
        borders = menu([
            MenuItem("All borders", lambda: self.fmt(borders="all"), icon="grid-2x2"),
            MenuItem("Inner borders", lambda: self.fmt(borders="inner"), icon="grid-2x2"),
            MenuItem("Outer borders", lambda: self.fmt(borders="outer"), icon="square"),
            SEPARATOR,
            MenuItem("Top border", lambda: self.fmt(borders="top"), icon="panel-top"),
            MenuItem("Bottom border", lambda: self.fmt(borders="bottom"), icon="panel-bottom"),
            MenuItem("Left border", lambda: self.fmt(borders="left"), icon="panel-left"),
            MenuItem("Right border", lambda: self.fmt(borders="right"), icon="panel-right"),
            SEPARATOR,
            MenuItem("Clear borders", lambda: self.fmt(borders="none"), icon="eraser"),
        ], width=200, theme=t)
        align = st.get("align")
        valign = st.get("valign")
        align_menu = menu([
            MenuItem("Left", lambda: self.fmt(align="left"), icon="align-left", checked=align == "left"),
            MenuItem("Center", lambda: self.fmt(align="center"), icon="align-center", checked=align == "center"),
            MenuItem("Right", lambda: self.fmt(align="right"), icon="align-right", checked=align == "right"),
            SEPARATOR,
            MenuItem("Top", lambda: self.fmt(valign="top"), icon="align-vertical-justify-start", checked=valign == "top"),
            MenuItem("Middle", lambda: self.fmt(valign="middle"), icon="align-vertical-justify-center",
                     checked=valign == "middle"),
            MenuItem("Bottom", lambda: self.fmt(valign="bottom"), icon="align-vertical-justify-end",
                     checked=valign in (None, "bottom")),
        ], width=180, theme=t)
        fr, fc = wb.frozen
        active = wb.active_cell
        arow = _rows(active)[0]
        acol = _cols(active)[0]
        acol_n = _col_index(acol)

        def freeze(rows: Optional[int] = None, cols: Optional[int] = None) -> Any:
            r, c = wb.frozen
            wb.freeze(r if rows is None else rows, c if cols is None else cols)
            self.open = None
            return self.changed("freeze")

        freeze_menu = menu([
            MenuItem("No rows", lambda: freeze(rows=0), checked=fr == 0),
            MenuItem("1 row", lambda: freeze(rows=1), checked=fr == 1),
            MenuItem("2 rows", lambda: freeze(rows=2), checked=fr == 2),
            MenuItem(f"Up to row {arow}", lambda: freeze(rows=arow), checked=fr == arow and arow > 2),
            SEPARATOR,
            MenuItem("No columns", lambda: freeze(cols=0), checked=fc == 0),
            MenuItem("1 column", lambda: freeze(cols=1), checked=fc == 1),
            MenuItem("2 columns", lambda: freeze(cols=2), checked=fc == 2),
            MenuItem(f"Up to column {acol}", lambda: freeze(cols=acol_n), checked=fc == acol_n and acol_n > 2),
        ], width=190, theme=t)

        def insert_function(name: str) -> Any:
            self.open = None
            rng = wb.selection
            cell = wb.active_cell
            if rng != cell:
                # A range selected: the function of it goes under it (like Excel's AutoSum).
                r1 = _rows(rng)[1]
                c0 = _cols(rng)[0]
                target = f"{c0}{min(r1 + 1, 1048576)}"
                wb[target] = f"={name}({rng})"
                wb.select(target)
                return self.changed("edit", target)
            wb[cell] = f"={name}()"
            return self.changed("edit", cell)

        functions = menu([MenuItem(n, (lambda n=n: insert_function(n))) for n in ("SUM", "AVERAGE", "COUNT", "MAX", "MIN")]
                         + [SEPARATOR, MenuItem("All functions…", self._show_functions)], width=190, theme=t)
        merged = any(m.split(":")[0] == active for m in wb.merges())

        def merge() -> Any:
            if merged:
                wb.unmerge(active)
            elif wb.selection != active:
                wb.merge(wb.selection)
            return self.changed("merge")

        def decimals(delta: int) -> Any:
            self.each(lambda r: wb.change_decimals(r, delta))
            return self.changed("format")

        color_btn = _core.button(
            _core.column([_icon("baseline", size=15, color=t.icon),
                          _core.container(None, width=14, height=3, bg=st.get("color") or t.text, radius=1)],
                         spacing=0, align="center"),
            None if self.readonly else self._opener("color"), padding=4, bg="transparent", hover_bg=t.ghost_hover,
            radius=t.radius_sm)
        fill_btn = _core.button(
            _core.column([_icon("paint-bucket", size=15, color=t.icon),
                          _core.container(None, width=14, height=3, bg=st.get("fill") or "transparent", radius=1,
                                          border_color=t.border_variant, border_width=0 if st.get("fill") else 1)],
                         spacing=0, align="center"),
            None if self.readonly else self._opener("fill"), padding=4, bg="transparent", hover_bg=t.ghost_hover,
            radius=t.radius_sm)
        items = [
            self._tool(t, "undo-2", self._undo if wb.can_undo else None, "Undo", "ctrl-z"),
            self._tool(t, "redo-2", self._redo if wb.can_redo else None, "Redo", "ctrl-y"),
            sep,
            self._tool(t, "dollar-sign", lambda: self.fmt(number_format="$#,##0.00"), "Format as currency"),
            self._tool(t, "percent", lambda: self.fmt(number_format="0.00%"), "Format as percent"),
            self._tool(t, "decimals-arrow-left", lambda: decimals(-1), "Decrease decimal places"),
            self._tool(t, "decimals-arrow-right", lambda: decimals(1), "Increase decimal places"),
            self._dropdown(t, "format", tooltip_text(button("123", None if self.readonly else self._opener("format"),
                                                            variant="ghost", size="sm", theme=t),
                                                     "More formats", theme=t), fmt_menu),
            sep,
            select([str(s) for s in _SIZES], str(size), None if self.readonly else (lambda v: self.fmt(size=float(v))),
                   width=64, size="sm", theme=t),
            sep,
            self._tool(t, "bold", lambda: self.toggle("bold"), "Bold", "ctrl-b", st.get("bold", False)),
            self._tool(t, "italic", lambda: self.toggle("italic"), "Italic", "ctrl-i", st.get("italic", False)),
            self._tool(t, "strikethrough", lambda: self.toggle("strike"), "Strikethrough", "ctrl-5",
                       st.get("strike", False)),
            self._tool(t, "underline", lambda: self.toggle("underline"), "Underline", "ctrl-u",
                       st.get("underline", False)),
            self._dropdown(t, "color", tooltip_text(color_btn, "Text color", theme=t),
                           self._palette(t, lambda c: self.fmt(color=c), "Reset")),
            self._dropdown(t, "fill", tooltip_text(fill_btn, "Fill color", theme=t),
                           self._palette(t, lambda c: self.fmt(fill=c), "No fill")),
            sep,
            self._dropdown(t, "borders", self._tool(t, "grid-2x2", self._opener("borders"), "Borders"), borders),
            self._tool(t, "table-cells-merge", merge, "Merge cells", selected=merged),
            self._dropdown(t, "align", self._tool(t, {"center": "align-center", "right": "align-right"}.get(align, "align-left"),
                                                  self._opener("align"), "Alignment"), align_menu),
            self._tool(t, "wrap-text", lambda: self.toggle("wrap"), "Wrap text", selected=st.get("wrap", False)),
            sep,
            self._tool(t, "arrow-down-a-z", lambda: self.sort(False), "Sort A → Z"),
            self._tool(t, "arrow-down-z-a", lambda: self.sort(True), "Sort Z → A"),
            self._tool(t, "funnel", self._toggle_filter, "Filter", "ctrl-shift-l", wb.filter_range is not None),
            self._dropdown(t, "freeze", self._tool(t, "snowflake", self._opener("freeze"), "Freeze",
                                                   selected=fr > 0 or fc > 0), freeze_menu),
            sep,
            self._dropdown(t, "functions", self._tool(t, "sigma", self._opener("functions"), "Functions"), functions),
            self._tool(t, "paintbrush", lambda: self.open_panel("conditional"), "Conditional formatting",
                       selected=self.panel == "conditional"),
            self._tool(t, "list-checks", lambda: self.open_panel("validation"), "Data validation",
                       selected=self.panel == "validation"),
            self._tool(t, "sticky-note", lambda: self.open_panel("note"), "Note", selected=self.panel == "note"),
        ]
        row = _core.row([*items, _core.space(width="fill"),
                         icon_button("search", lambda: self.open_find("find"), tooltip="Find and replace",
                                     keys="ctrl-f", size="sm", theme=t)],
                        spacing=2, align="center")
        return _core.container(row, height=TOOLBAR_H, width="fill", padding=(0, 8), align_y="center", bg=t.surface,
                               clip=True)

    def _undo(self) -> Any:
        self.wb.undo()
        return self.changed("undo")

    def _redo(self) -> Any:
        self.wb.redo()
        return self.changed("redo")

    def _toggle_filter(self) -> Any:
        wb = self.wb
        if wb.filter_range:
            wb.filter(None)
        else:
            rng = wb.selection
            wb.filter(None if rng == wb.active_cell else rng)
        return self.changed("filter")

    def _show_functions(self) -> None:
        self.open = None
        names = ", ".join(f[0] for f in _core.Workbook.functions())
        self.message = f"{len(_core.Workbook.functions())} functions: {names[:300]}…"

    # Find bar -----------------------------------------------------------------------
    def render_find(self, t: Theme) -> Any:
        f = self.find
        assert f is not None

        def set_query(v: str) -> None:
            f["query"] = v
            self.search()

        def set_with(v: str) -> None:
            f["with"] = v

        def flag(key: str):
            def run(v: bool) -> None:
                f[key] = v
                self.search()
            return run

        n = len(f["matches"])
        count = f"{f['index'] + 1} of {n}" if n and f["index"] >= 0 else (f"{n} found" if f["query"] else "")
        parts: List[Any] = [
            text_input(f["query"], set_query, placeholder="Find", icon="search", on_submit=lambda: self.find_step(1),
                       width=200, size="sm", id="pyzed-sheet-find", theme=t),
            label(count, size="sm", color="text_muted", theme=t),
            icon_button("chevron-up", lambda: self.find_step(-1), tooltip="Previous", size="sm", theme=t),
            icon_button("chevron-down", lambda: self.find_step(1), tooltip="Next", size="sm", theme=t),
        ]
        if f["mode"] == "replace" and not self.readonly:
            parts += [
                text_input(f["with"], set_with, placeholder="Replace with", icon="replace", width=180, size="sm",
                           on_submit=self.replace_one, theme=t),
                button("Replace", self.replace_one, size="sm", theme=t),
                button("Replace all", self.replace_all, size="sm", theme=t),
            ]
        else:
            parts.append(icon_button("replace", lambda: f.update(mode="replace"), tooltip="Replace", size="sm",
                                     theme=t))
        parts += [
            checkbox(f["case"], flag("case"), label="Match case", size="sm", theme=t),
            checkbox(f["whole"], flag("whole"), label="Entire cell", size="sm", theme=t),
            checkbox(f["formulas"], flag("formulas"), label="In formulas", size="sm", theme=t),
            checkbox(f["all"], flag("all"), label="All sheets", size="sm", theme=t),
            _core.space(width="fill"),
            icon_button("x", self._close_find, tooltip="Close", size="sm", theme=t),
        ]
        return _core.container(_core.row(parts, spacing=6, align="center"), height=FIND_H, width="fill",
                               padding=(0, 8), align_y="center", bg=t.surface, clip=True)

    def _close_find(self) -> None:
        self.find = None
        self.wb.focused = True

    # Sheet tabs -----------------------------------------------------------------------
    def render_tabs(self, t: Theme) -> Any:
        wb = self.wb
        tabs: List[Any] = []
        for i, name in enumerate(wb.sheets):
            active = i == wb.active
            if self.renaming and self.renaming[0] == i:
                tabs.append(text_input(self.renaming[1], lambda v, i=i: setattr(self, "renaming", (i, v)),
                                       on_submit=self.rename_done, width=120, size="sm", id="pyzed-sheet-rename",
                                       theme=t))
                continue
            color = wb.tab_color(i)
            content = _core.column([
                _core.text(name, size=12.5, color=t.text if active else t.text_muted,
                           weight="semibold" if active else None, wrap=False),
                _core.container(None, width="fill", height=3, bg=color or ("transparent"), radius=1),
            ], spacing=1, align="center")
            # A plain container rather than a button: a button captures the clicks, and the
            # mouse area would never see the double click that renames the sheet.
            tab = _core.container(content, padding=(5, 12, 2, 12),
                                  bg=t.editor if active else "transparent", radius=t.radius_sm,
                                  border_color=t.border_variant if active else "transparent",
                                  border_width=1 if active else 0)
            tab = _core.mouse_area(tab, on_press=(lambda i=i: None if i == self.wb.active else self.go(i)),
                                   on_double_click=(lambda i=i: self.sheet_action(i, "rename")),
                                   on_right_press=(lambda i=i: self._tab_menu(i)), cursor="pointer")
            tabs.append(tab)
        status = self.render_status(t)
        bar = _core.row([
            icon_button("plus", None if self.readonly else self.add_sheet, tooltip="Add sheet", size="sm", theme=t),
            _core.scrollable(_core.row(tabs, spacing=2, align="center"), direction="horizontal", width="fill",
                             scrollbar_width=0, scroller_width=0),
            status,
        ], spacing=6, align="center")
        return _core.container(bar, height=TABS_H, width="fill", padding=(0, 8), align_y="center", bg=t.surface)

    def _tab_menu(self, index: int) -> None:
        if self.readonly:
            return
        x = 40 + 90 * index
        self.menu = {"kind": "tab", "index": index, "x": x, "y": 1e6}  # placed above the tabs

    def render_status(self, t: Theme) -> Any:
        rng = self.wb.selection
        if rng == self.wb.active_cell:
            return _core.space(width=0)
        s = self.wb.stats(rng)
        if not s["count"]:
            return _core.space(width=0)
        parts = []
        if s["numbers"]:
            parts.append(f"Sum: {s['sum']:,.10g}")
            parts.append(f"Average: {s['average']:,.6g}")
        parts.append(f"Count: {s['count']}")
        return label("   ".join(parts), size="sm", color="text_muted", theme=t)

    # Menus ----------------------------------------------------------------------------
    def _place(self) -> Tuple[float, float]:
        """Where the open menu goes: at the pointer, moved up or left to stay inside the grid."""
        m = self.menu
        w, h = m.get("w", 240.0), m.get("h", 300.0)
        bottom = self._offset() + self.view[1]
        right = self.view[0]
        x = max(4.0, min(m["x"], right - w - 4))
        y = m["y"]
        if y + h > bottom - 4:
            y = max(4.0, bottom - h - 4)
        return x, y

    @staticmethod
    def _menu_size(items: List[Any], width: float, max_height: float = 1e9) -> Tuple[float, float]:
        h = 10.0
        for it in items:
            h += 9 if it == SEPARATOR else 24 if isinstance(it, str) else 40 if getattr(it, "description", None) else 26
        return width, min(h, max_height + 10)

    def render_menu(self, t: Theme) -> Any:
        m = self.menu
        if not m:
            return None
        if m["kind"] == "dropdown":
            current = self.wb.text(m["cell"])

            def pick(option: str) -> Any:
                self.wb[m["cell"]] = option
                self.close_menu()
                return self.changed("edit", m["cell"])

            items = [MenuItem(o, (lambda o=o: pick(o)), checked=o == current) for o in m["options"]] or ["No options"]
            m["w"], m["h"] = self._menu_size(items, m["width"], 320)
            return menu(items, width=m["width"], max_height=320, theme=t)
        if m["kind"] == "filter":
            m["w"], m["h"] = 280.0, 420.0
            return self.render_filter(t, m)
        if m["kind"] == "tab":
            i = m["index"]
            colors = [MenuItem(name, (lambda c=c: self.sheet_action(i, f"color:{c}")), icon="circle" if c else "circle-off")
                      for name, c in (("Red", "#ea4335"), ("Orange", "#fa7b17"), ("Yellow", "#fbbc04"),
                                      ("Green", "#34a853"), ("Blue", "#4285f4"), ("Purple", "#a142f4"),
                                      ("No color", ""))]
            items = [
                MenuItem("Rename", lambda: self.sheet_action(i, "rename"), icon="text-cursor-input"),
                MenuItem("Duplicate", lambda: self.sheet_action(i, "duplicate"), icon="copy"),
                MenuItem("Delete", lambda: self.sheet_action(i, "delete"), icon="trash-2", danger=True,
                         disabled=len(self.wb.sheets) < 2),
                SEPARATOR,
                MenuItem("Move left", lambda: self.sheet_action(i, "left"), icon="arrow-left", disabled=i == 0),
                MenuItem("Move right", lambda: self.sheet_action(i, "right"), icon="arrow-right",
                         disabled=i >= len(self.wb.sheets) - 1),
                SEPARATOR,
                "Color",
                *colors,
            ]
            m["w"], m["h"] = self._menu_size(items, 200)
            m["h"] += TABS_H
            return menu(items, width=200, theme=t)
        target = m["target"]
        ro = self.readonly
        items: List[Any] = [
            MenuItem("Cut", lambda: self.clip("cut"), icon="scissors", keys="ctrl-x", disabled=ro),
            MenuItem("Copy", lambda: self.clip("copy"), icon="copy", keys="ctrl-c"),
            MenuItem("Paste", lambda: self.clip("paste"), icon="clipboard-paste", keys="ctrl-v", disabled=ro),
            MenuItem("Paste values only", lambda: self.clip("paste_values"), icon="clipboard-type", keys="ctrl-shift-v",
                     disabled=ro),
            SEPARATOR,
        ]
        if not ro:
            if target in ("cell", "row"):
                items += [MenuItem("Insert row above", lambda: self.structure("row_above"), icon="between-horizontal-start"),
                          MenuItem("Insert row below", lambda: self.structure("row_below"), icon="between-horizontal-end")]
            if target in ("cell", "column"):
                items += [MenuItem("Insert column left", lambda: self.structure("col_left"), icon="between-vertical-start"),
                          MenuItem("Insert column right", lambda: self.structure("col_right"), icon="between-vertical-end")]
            items.append(SEPARATOR)
            if target in ("cell", "row"):
                items.append(MenuItem("Delete row", lambda: self.structure("delete_rows"), icon="trash-2"))
            if target in ("cell", "column"):
                items.append(MenuItem("Delete column", lambda: self.structure("delete_cols"), icon="trash-2"))
            if target == "row":
                items += [MenuItem("Hide row", lambda: self.structure("hide_rows"), icon="eye-off"),
                          MenuItem("Unhide rows", lambda: self.structure("show_rows"), icon="eye")]
            if target == "column":
                items += [MenuItem("Hide column", lambda: self.structure("hide_cols"), icon="eye-off"),
                          MenuItem("Unhide columns", lambda: self.structure("show_cols"), icon="eye"),
                          MenuItem("Fit to data", lambda: self.structure("autofit"), icon="move-horizontal")]
            items += [
                SEPARATOR,
                MenuItem("Clear contents", lambda: self.clear("contents"), icon="eraser", keys="delete"),
                MenuItem("Clear formatting", lambda: self.clear("formats"), icon="remove-formatting", keys="ctrl-\\"),
                SEPARATOR,
                MenuItem("Sort A → Z", lambda: self.sort(False), icon="arrow-down-a-z"),
                MenuItem("Sort Z → A", lambda: self.sort(True), icon="arrow-down-z-a"),
                SEPARATOR,
                MenuItem("Insert note", lambda: self.open_panel("note"), icon="sticky-note"),
                MenuItem("Conditional formatting", lambda: self.open_panel("conditional"), icon="paintbrush"),
                MenuItem("Data validation", lambda: self.open_panel("validation"), icon="list-checks"),
            ]
        m["w"], m["h"] = self._menu_size(items, 260, 460)
        return menu(items, width=260, max_height=460, theme=t)

    def render_filter(self, t: Theme, m: Dict[str, Any]) -> Any:
        col = m["column"]
        query = m["query"].lower()
        values = [v for v in m["values"] if query in v.lower()]

        def toggle(v: str, on: bool) -> None:
            (m["shown"].add if on else m["shown"].discard)(v)

        def apply() -> Any:
            hide = [v for v in m["values"] if v not in m["shown"]]
            self.wb.filter_column(col, hide=hide, condition=m["condition"] or None)
            self.close_menu()
            return self.changed("filter")

        def sort(desc: bool) -> Any:
            rng = self.wb.filter_range
            if rng:
                self.wb.sort(rng, col, descending=desc, header=True)
            self.close_menu()
            return self.changed("sort", rng)

        rows = [checkbox(v in m["shown"], (lambda on, v=v: toggle(v, on)), label=v or "(Blanks)", size="sm", theme=t)
                for v in values[:500]]
        content = _core.column([
            button("Sort A → Z", lambda: sort(False), icon="arrow-down-a-z", variant="ghost", size="sm", theme=t),
            button("Sort Z → A", lambda: sort(True), icon="arrow-down-z-a", variant="ghost", size="sm", theme=t),
            divider(theme=t),
            label("Filter by condition", size="sm", color="text_muted", theme=t),
            text_input(m["condition"], lambda v: m.update(condition=v), placeholder='e.g. >100, <>Done, *north*',
                       size="sm", theme=t),
            label("Filter by values", size="sm", color="text_muted", theme=t),
            _core.row([
                button("Select all", lambda: m.update(shown=set(m["values"])), variant="ghost", size="sm", theme=t),
                button("Clear", lambda: m.update(shown=set()), variant="ghost", size="sm", theme=t),
            ], spacing=4),
            text_input(m["query"], lambda v: m.update(query=v), placeholder="Search", icon="search", size="sm", theme=t),
            _core.scrollable(_core.column(rows, spacing=4, width="fill"), height=180, width="fill"),
            _core.row([_core.space(width="fill"),
                       button("Cancel", self.close_menu, size="sm", theme=t),
                       button("OK", apply, variant="solid", size="sm", theme=t)], spacing=6),
        ], spacing=6, width=260)
        return _core.container(content, padding=10, bg=t.elevated, border_color=t.border, border_width=1,
                               radius=t.radius)

    # Side panels ------------------------------------------------------------------------
    def render_panel(self, t: Theme) -> Any:
        f = self.form

        def field(key: str, placeholder: str = "", width: Any = "fill") -> Any:
            return text_input(str(f.get(key, "")), lambda v, k=key: f.update({k: v}), placeholder=placeholder,
                              width=width, size="sm", theme=t)

        def colors(key: str, title: str) -> Any:
            swatches = ["", "#b7e1cd", "#fce8b2", "#f4c7c3", "#c9daf8", "#d9d2e9", "#57bb8a", "#e67c73", "#000000",
                        "#ffffff"]
            return _core.column([
                label(title, size="sm", color="text_muted", theme=t),
                _core.row([
                    _core.button(_icon("x", size=10, color=t.icon_muted) if not c else None,
                                 (lambda c=c: f.update({key: c})), width=20, height=20, padding=0,
                                 bg=c or "transparent", radius=10,
                                 border_color=t.accent if f.get(key) == c else t.border_variant,
                                 border_width=2 if f.get(key) == c else 1)
                    for c in swatches
                ], spacing=4),
            ], spacing=4)

        head = lambda title: _core.row([label(title, weight="semibold", theme=t), _core.space(width="fill"),  # noqa: E731
                                        icon_button("x", self._close_panel, size="sm", theme=t)], align="center")
        if self.panel == "note":
            body = [
                head(f"Note in {f['cell']}"),
                _core.text_editor(f["text"], on_change=lambda v: f.update(text=v), height=140) if hasattr(_core, "text_editor")
                else field("text", "Note"),
                _core.row([_core.space(width="fill"),
                           button("Delete", lambda: (f.update(text=""), self.save_note())[1], size="sm", theme=t),
                           button("Save", self.save_note, variant="solid", size="sm", theme=t)], spacing=6),
            ]
        elif self.panel == "conditional":
            labels = [r[0] for r in _RULES]
            _name, rule, needs = _RULES[f["rule"]]
            body = [
                head("Conditional formatting"),
                label("Apply to range", size="sm", color="text_muted", theme=t),
                field("range", "A1:B10"),
                label("Format cells if…", size="sm", color="text_muted", theme=t),
                select(labels, labels[f["rule"]], lambda v: f.update(rule=labels.index(v)), width="fill", size="sm",
                       theme=t),
            ]
            if needs >= 1:
                body.append(field("value", "Formula, e.g. =A1>B1" if rule == "formula" else "Value"))
            if needs >= 2:
                body.append(field("value2", "and"))
            if rule == "scale":
                body += [colors("low", "Lowest value"), colors("high", "Highest value")]
            elif rule == "bar":
                body.append(colors("fill", "Bar color"))
            else:
                body += [colors("fill", "Fill color"), colors("color", "Text color"),
                         checkbox(f["bold"], lambda v: f.update(bold=v), label="Bold", size="sm", theme=t)]
            body.append(_core.row([_core.space(width="fill"),
                                   button("Add rule", self.add_rule, variant="solid", size="sm", theme=t)]))
            rules = self.wb.conditional_formats()
            if rules:
                body.append(divider(theme=t))
                body.append(label("Rules on this sheet", size="sm", color="text_muted", theme=t))
                names = {rule: name for name, rule, _n in _RULES}
                names.update(color_scale="Color scale", data_bar="Data bar")
                for rng, desc in rules:
                    desc = f"Custom formula {desc}" if desc.startswith("=") else names.get(desc, desc)
                    body.append(_core.row([
                        _core.column([label(desc, size="sm", theme=t), label(rng, size="xs", color="text_muted", theme=t)],
                                     spacing=0, width="fill"),
                        icon_button("trash-2", (lambda rng=rng: self._remove_rule(rng)), size="sm", theme=t),
                    ], align="center"))
        else:
            labels = [c[0] for c in _CHECKS]
            check = _CHECKS[f["check"]][1]
            body = [
                head("Data validation"),
                label("Apply to range", size="sm", color="text_muted", theme=t),
                field("range", "A1:A100"),
                label("Criteria", size="sm", color="text_muted", theme=t),
                select(labels, labels[f["check"]], lambda v: f.update(check=labels.index(v)), width="fill", size="sm",
                       theme=t),
            ]
            if check == "list":
                body.append(field("items", "Options, separated by commas"))
            elif check == "range":
                body.append(field("source", "Sheet2!A1:A20"))
            elif check in ("number", "integer", "date", "length"):
                hint = "yyyy-mm-dd" if check == "date" else "Min"
                body.append(_core.row([field("min", hint), field("max", "Max")], spacing=6))
            elif check == "formula":
                body.append(field("formula", "=A1>0"))
            if check != "checkbox":
                body += [
                    checkbox(f["strict"], lambda v: f.update(strict=v), label="Reject invalid input", size="sm", theme=t),
                    field("message", "Help text shown for invalid data"),
                ]
            body.append(_core.row([
                button("Remove", self._remove_validation, size="sm", theme=t),
                _core.space(width="fill"),
                button("Done", self.save_validation, variant="solid", size="sm", theme=t),
            ], spacing=6))
        return _core.container(_core.scrollable(_core.column(body, spacing=8, width="fill"), height="fill"),
                               width=300, height="fill", padding=12, bg=t.panel, border_color=t.border,
                               border_width=1)

    def _close_panel(self) -> None:
        self.panel = None
        self.wb.focused = True

    def _remove_rule(self, rng: str) -> Any:
        self.wb.clear_conditional_formats(rng)
        return self.changed("format", rng)

    def _remove_validation(self) -> Any:
        self.wb.clear_validation(self.form["range"] or self.wb.selection)
        self.panel = None
        return self.changed("validation")


def _signature() -> None:
    """``help(ui.Spreadsheet)`` and the reference show its props and events."""
    from .dates import _signature as sign

    sign(Spreadsheet)


_signature()
