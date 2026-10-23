"""Dates and times: a calendar, date, date range and time pickers, and date formats.

``Calendar`` is a month you click days on: one day, a range (``mode="range"``) or several
(``mode="multiple"``). ``DatePicker``, ``DateRangePicker`` and ``TimePicker`` are fields that
open a calendar (or a list of hours) in a popup that is never cut off by the panel they sit
in. The fields can also be typed in, and keep the keyboard: once clicked, ↑/↓ change the
day (or the minutes) without opening anything, Alt+↓ opens the popup and Escape closes it::

    class Booking(pz.App):
        def __init__(self):
            self.day = datetime.date.today()
            self.stay = (None, None)

        def view(self):
            return pz.column([
                ui.DatePicker(self.day, format="DD/MM/YYYY", on_change=lambda e: setattr(self, "day", e.value)),
                ui.DateRangePicker(self.stay, on_change=lambda e: setattr(self, "stay", e.value)),
            ], spacing=8)

Values are ``datetime.date`` (a range is a ``(start, end)`` tuple, ``datetime.time`` for times);
ISO text such as ``"2026-10-22"`` is accepted too. ``format`` is a pattern of tokens
(``YYYY`` year, ``MM`` month, ``MMM``/``MMMM`` its name, ``DD`` day, ``ddd``/``dddd`` the weekday,
``HH``/``hh`` hours, ``mm`` minutes, ``ss`` seconds, ``A`` AM/PM, ``[text]`` literal) or a
``strftime`` pattern with ``%``. Month and day names follow the language of ``pyzed.i18n``.
"""

from __future__ import annotations

import calendar as _calendar
import inspect
import datetime as _dt
import re
from typing import Any, Callable, Iterable, List, Optional, Sequence, Tuple

from .. import _core
from .. import i18n as _i18n
from ..component import Component
from ..i18n import t as _t
from ..icons import icon as _icon
from ..theme import Theme, alpha as _alpha, current as _current_theme
from .base import icon_button

__all__ = [
    "FORMATS", "TIME_FORMATS", "WEEK_STARTS", "Calendar", "DatePicker", "DateRangePicker", "TimePicker",
    "format_date", "format_time", "parse_date", "parse_time", "range_presets", "to_date", "to_time",
]

#: Date formats offered by the designer; any other pattern works too (see ``format_date``).
FORMATS = ("YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY", "DD.MM.YYYY", "D MMM YYYY", "MMM D, YYYY",
           "ddd, D MMM YYYY", "dddd, D MMMM YYYY")
#: Time formats offered by the designer.
TIME_FORMATS = ("HH:mm", "HH:mm:ss", "h:mm A", "h:mm:ss A")
#: The days a week can start on.
WEEK_STARTS = ("monday", "sunday", "saturday")
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

_i18n.add("en", {"pyzed": {"date": {
    "months": "January February March April May June July August September October November December",
    "months_short": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec",
    "days": "Monday Tuesday Wednesday Thursday Friday Saturday Sunday",
    "days_short": "Mon Tue Wed Thu Fri Sat Sun", "days_min": "Mo Tu We Th Fr Sa Su",
    "today": "Today", "clear": "Clear", "now": "Now", "week": "Wk", "pick": "Pick a date",
    "pick_range": "Pick dates", "pick_time": "Pick a time", "previous": "Previous", "next": "Next",
    "open": "Open the calendar", "hours": "Hours", "minutes": "Minutes", "seconds": "Seconds",
    "presets": {"today": "Today", "yesterday": "Yesterday", "last_7": "Last 7 days", "last_30": "Last 30 days",
                "this_week": "This week", "this_month": "This month", "last_month": "Last month",
                "this_year": "This year"},
}}})
_i18n.add("es", {"pyzed": {"date": {
    "months": "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre",
    "months_short": "ene feb mar abr may jun jul ago sept oct nov dic",
    "days": "lunes martes miércoles jueves viernes sábado domingo",
    "days_short": "lun mar mié jue vie sáb dom", "days_min": "lu ma mi ju vi sá do",
    "today": "Hoy", "clear": "Borrar", "now": "Ahora", "week": "Sem", "pick": "Elige una fecha",
    "pick_range": "Elige las fechas", "pick_time": "Elige una hora", "previous": "Anterior", "next": "Siguiente",
    "open": "Abrir el calendario", "hours": "Horas", "minutes": "Minutos", "seconds": "Segundos",
    "presets": {"today": "Hoy", "yesterday": "Ayer", "last_7": "Últimos 7 días", "last_30": "Últimos 30 días",
                "this_week": "Esta semana", "this_month": "Este mes", "last_month": "El mes pasado",
                "this_year": "Este año"},
}}})


def _names(key: str, language: Optional[str] = None) -> List[str]:
    return _t(f"pyzed.date.{key}", language=language).split()


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


# -- values ---------------------------------------------------------------------------------------------------


def to_date(value: Any) -> Optional[_dt.date]:
    """``value`` as a ``datetime.date``: a date, a datetime, ISO text (``"2026-10-22"``) or ``None``.

    Text that is not a date gives ``None``.
    """
    if value is None or value == "":
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def to_time(value: Any) -> Optional[_dt.time]:
    """``value`` as a ``datetime.time``: a time, a datetime, text such as ``"14:30"`` or ``None``."""
    if value is None or value == "":
        return None
    if isinstance(value, _dt.datetime):
        return value.time().replace(microsecond=0)
    if isinstance(value, _dt.time):
        return value
    return parse_time(str(value))


def _pair(value: Any) -> Tuple[Optional[_dt.date], Optional[_dt.date]]:
    if isinstance(value, str):
        parts = re.split(r"\s*(?:/|–|—|\.\.| to )\s*(?=\d{4}-)", value.strip())
        value = parts if len(parts) == 2 else (value, None)
    if not value:
        return None, None
    items = list(value)[:2] + [None, None]
    return to_date(items[0]), to_date(items[1])


# -- formats ------------------------------------------------------------------------------------------------------

_TOKENS = re.compile(r"\[[^\]]*\]|YYYY|YY|MMMM|MMM|MM|M|DD|D|dddd|ddd|HH|H|hh|h|mm|m|ss|s|A|a")


def format_date(value: Any, fmt: str = "YYYY-MM-DD", *, language: Optional[str] = None) -> str:
    """``value`` (a date, datetime or ISO text) written with ``fmt``; ``""`` for no date.

    Tokens: ``YYYY`` 2026, ``YY`` 26, ``MMMM`` October, ``MMM`` Oct, ``MM`` 10, ``M`` 10, ``DD`` 05,
    ``D`` 5, ``dddd`` Monday, ``ddd`` Mon, ``HH``/``H`` hours (24h), ``hh``/``h`` hours (12h),
    ``mm``/``m`` minutes, ``ss``/``s`` seconds, ``A``/``a`` AM/PM, ``[text]`` text kept as is.
    A ``fmt`` with ``%`` is a ``strftime`` pattern instead.
    """
    if isinstance(value, _dt.time):
        moment = _dt.datetime.combine(_dt.date(2000, 1, 1), value)
    elif isinstance(value, _dt.datetime):
        moment = value
    else:
        day = to_date(value)
        if day is None:
            return ""
        moment = _dt.datetime.combine(day, _dt.time())
    if "%" in fmt:
        return moment.strftime(fmt)

    def token(m: "re.Match[str]") -> str:
        tok = m.group(0)
        if tok.startswith("["):
            return tok[1:-1]
        hour12 = moment.hour % 12 or 12
        return {
            "YYYY": f"{moment.year:04d}", "YY": f"{moment.year % 100:02d}",
            "MMMM": _names("months", language)[moment.month - 1],
            "MMM": _names("months_short", language)[moment.month - 1],
            "MM": f"{moment.month:02d}", "M": str(moment.month), "DD": f"{moment.day:02d}", "D": str(moment.day),
            "dddd": _names("days", language)[moment.weekday()],
            "ddd": _names("days_short", language)[moment.weekday()],
            "HH": f"{moment.hour:02d}", "H": str(moment.hour), "hh": f"{hour12:02d}", "h": str(hour12),
            "mm": f"{moment.minute:02d}", "m": str(moment.minute), "ss": f"{moment.second:02d}",
            "s": str(moment.second), "A": "PM" if moment.hour >= 12 else "AM",
            "a": "pm" if moment.hour >= 12 else "am",
        }[tok]

    return _TOKENS.sub(token, fmt)


def format_time(value: Any, fmt: str = "HH:mm") -> str:
    """``value`` (a time, or text such as ``"14:30"``) written with ``fmt`` (see ``format_date``)."""
    moment = to_time(value)
    return "" if moment is None else format_date(moment, fmt)


def _month_number(word: str, language: Optional[str]) -> Optional[int]:
    word = word.lower().rstrip(".")
    for lang in dict.fromkeys((language, "en")):
        for key in ("months", "months_short"):
            names = [n.lower().rstrip(".") for n in _names(key, lang)]
            if word in names:
                return names.index(word) + 1
        for i, name in enumerate(_names("months", lang)):  # "sep" for "septiembre"
            if len(word) >= 3 and name.lower().startswith(word):
                return i + 1
    return None


def _literal(text: str) -> str:
    """A regex for the text between tokens, lenient about spaces."""
    return r"\s*" + r"\s*".join(re.escape(part) for part in text.split()) + r"\s*"


def _pattern(fmt: str) -> "re.Pattern[str]":
    out, last = [], 0
    for m in _TOKENS.finditer(fmt):
        out.append(_literal(fmt[last:m.start()]))
        tok = m.group(0)
        if tok.startswith("["):
            out.append(re.escape(tok[1:-1]))
        elif tok in ("MMMM", "MMM", "dddd", "ddd"):
            out.append(rf"(?P<{tok}>[^\W\d_]+\.?)")
        elif tok in ("A", "a"):
            out.append(r"(?P<A>[aApP]\.?\s*[mM]\.?)")
        elif tok == "YYYY":
            out.append(r"(?P<YYYY>\d{4})")
        else:
            out.append(rf"(?P<{tok}>\d{{1,2}})")
        last = m.end()
    out.append(_literal(fmt[last:]))
    return re.compile("^" + "".join(out) + "$", re.IGNORECASE)


def _parse(text: str, fmt: str, language: Optional[str]) -> Optional[_dt.datetime]:
    text = (text or "").strip()
    if not text:
        return None
    if "%" in fmt:
        try:
            return _dt.datetime.strptime(text, fmt)
        except ValueError:
            return None
    m = _pattern(fmt).match(text)
    if m is None:
        return None
    g = {k: v for k, v in m.groupdict().items() if v is not None}
    try:
        year = int(g["YYYY"]) if "YYYY" in g else (2000 + int(g["YY"]) if "YY" in g else 2000)
        month = int(g.get("MM") or g.get("M") or 0) or _month_number(g.get("MMMM") or g.get("MMM") or "", language) \
            or 1
        day = int(g.get("DD") or g.get("D") or 1)
        hour = int(g.get("HH") or g.get("H") or g.get("hh") or g.get("h") or 0)
        if "A" in g and ("hh" in g or "h" in g):
            hour = hour % 12 + (12 if g["A"].lower().startswith("p") else 0)
        return _dt.datetime(year, month, day, hour, int(g.get("mm") or g.get("m") or 0),
                            int(g.get("ss") or g.get("s") or 0))
    except (ValueError, TypeError):
        return None


def parse_date(text: str, fmt: str = "YYYY-MM-DD", *, language: Optional[str] = None) -> Optional[_dt.date]:
    """The date ``text`` holds when written with ``fmt`` (or as ISO ``YYYY-MM-DD``); ``None`` if it is not one."""
    moment = _parse(text, fmt, language)
    if moment is not None:
        return moment.date()
    return to_date(text)


def parse_time(text: str, fmt: str = "HH:mm") -> Optional[_dt.time]:
    """The time ``text`` holds (``"14:30"``, ``"2:30 PM"``, ``"14:30:05"``), read with ``fmt`` first."""
    moment = _parse(text, fmt, None)
    if moment is not None and ("H" in fmt or "h" in fmt or "%" in fmt):
        return moment.time()
    m = re.match(r"^\s*(\d{1,2})(?::(\d{2}))?(?::(\d{2}))?\s*([aApP])?\.?\s*[mM]?\.?\s*$", text or "")
    if not m:
        return None
    hour, minute, second = int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0)
    if m.group(4):
        hour = hour % 12 + (12 if m.group(4).lower() == "p" else 0)
    try:
        return _dt.time(hour, minute, second)
    except ValueError:
        return None


def range_presets(today: Optional[_dt.date] = None, first_weekday: str = "monday"
                  ) -> List[Tuple[str, Tuple[_dt.date, _dt.date]]]:
    """Ranges a ``DateRangePicker`` offers next to its calendar, as ``(name, (start, end))``."""
    d = today or _dt.date.today()
    week_start = d - _dt.timedelta(days=(d.weekday() - _first(first_weekday)) % 7)
    month_start = d.replace(day=1)
    last_month_end = month_start - _dt.timedelta(days=1)
    return [
        (_t("pyzed.date.presets.today"), (d, d)),
        (_t("pyzed.date.presets.yesterday"), (d - _dt.timedelta(days=1),) * 2),
        (_t("pyzed.date.presets.last_7"), (d - _dt.timedelta(days=6), d)),
        (_t("pyzed.date.presets.last_30"), (d - _dt.timedelta(days=29), d)),
        (_t("pyzed.date.presets.this_week"), (week_start, week_start + _dt.timedelta(days=6))),
        (_t("pyzed.date.presets.this_month"), (month_start, _add_months(month_start, 1) - _dt.timedelta(days=1))),
        (_t("pyzed.date.presets.last_month"), (last_month_end.replace(day=1), last_month_end)),
        (_t("pyzed.date.presets.this_year"), (d.replace(month=1, day=1), d.replace(month=12, day=31))),
    ]


def _first(first_weekday: Any) -> int:
    if isinstance(first_weekday, int):
        return first_weekday % 7
    name = str(first_weekday or "monday").lower()
    return _WEEKDAYS.index(name) if name in _WEEKDAYS else 0


def _add_months(day: _dt.date, months: int) -> _dt.date:
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    return _dt.date(year, month + 1, min(day.day, _calendar.monthrange(year, month + 1)[1]))


def _disabled_check(min_: Any, max_: Any, disabled: Iterable[Any]) -> Callable[[_dt.date], bool]:
    lo, hi = to_date(min_), to_date(max_)
    days, weekdays = set(), set()
    for item in disabled or ():
        name = str(item).strip().lower()
        if name in ("weekend", "weekends"):
            weekdays |= {5, 6}
        elif name in _WEEKDAYS:
            weekdays.add(_WEEKDAYS.index(name))
        elif (d := to_date(item)) is not None:
            days.add(d)

    def off(d: _dt.date) -> bool:
        return (lo is not None and d < lo) or (hi is not None and d > hi) or d in days or d.weekday() in weekdays

    return off


def _lines(value: Any) -> List[Any]:
    if isinstance(value, str):
        return [part for part in re.split(r"[\n,;]+", value) if part.strip()]
    return list(value or ())


# -- Calendar -----------------------------------------------------------------------------------------------------

CELL = 32


class Calendar(Component):
    """A month to pick a day on, or a range of days, or several.

    ``mode`` is ``"single"`` (``value`` is a date), ``"range"`` (``value`` is ``(start, end)``:
    the first click starts it, the second ends it) or ``"multiple"`` (``value`` is a list of
    dates, each click adds or removes one). ``min``/``max`` and ``disabled`` (dates, weekday
    names such as ``"sunday"`` or ``"weekends"``) turn days off. ``months`` shows that many
    months side by side; the title opens a grid of months, then of years, to jump far.
    Once clicked it takes the keyboard: arrows move, Enter picks, Page Up/Down change month.

    Events:
        ``on_change(event)``: A day was picked (``event.value``: a date, a ``(start, end)``
            tuple or a list of dates, by ``mode``).
        ``on_month(event)``: Another month is shown (``event.value`` is ``(year, month)``).
    """

    value: Any = None
    mode: str = "single"
    min: Any = None  # noqa: A003
    max: Any = None  # noqa: A003
    disabled: list = ()
    first_weekday: str = "monday"
    months: int = 1
    week_numbers: bool = False
    show_outside: bool = True
    today_button: bool = False
    events = {"change": "A day was picked (``event.value``).", "month": "Another month is shown (``event.value``)."}
    icon = "calendar"
    label = "Calendar"
    category = "Date & time"
    size = (252, 300)
    designer = False

    def setup(self) -> None:
        self.shown: Optional[Tuple[int, int]] = None
        self.view = "days"  # "days", "months" or "years"
        self.anchor: Optional[_dt.date] = None  # the first click of a range
        self.hover: Optional[_dt.date] = None
        self.cursor: Optional[_dt.date] = None  # the day the arrow keys move

    # -- state ------------------------------------------------------------------------------------------------
    def selected(self) -> List[_dt.date]:
        """The picked days, in order."""
        if self.mode == "range":
            start, end = _pair(self.value)
            return [d for d in (start, end) if d is not None]
        if self.mode == "multiple":
            return sorted(d for d in map(to_date, _lines(self.value)) if d is not None)
        d = to_date(self.value)
        return [d] if d else []

    def month(self) -> Tuple[int, int]:
        """The ``(year, month)`` shown first."""
        if self.shown is None:
            picked = self.selected()
            d = self.cursor or (picked[0] if picked else _dt.date.today())
            self.shown = (d.year, d.month)
        return self.shown

    def show(self, year: int, month: int) -> Any:
        """Shows ``month`` of ``year`` (out-of-range months roll over into the next year)."""
        index = year * 12 + month - 1
        self.shown = (index // 12, index % 12 + 1)
        return self.emit("month", self.shown)

    def step(self, months: int) -> Any:
        """Shows the month ``months`` after (or before) the current one; in the year grids, years."""
        year, month = self.month()
        if self.view == "months":
            return self.show(year + months, month)
        if self.view == "years":
            return self.show(year + 12 * months, month)
        return self.show(year, month + months)

    def set_view(self, view: str) -> None:
        """Switches between the ``"days"``, ``"months"`` and ``"years"`` grids."""
        self.view = view

    def pick(self, day: _dt.date) -> Any:
        """What a click on ``day`` does in this ``mode``."""
        if _disabled_check(self.min, self.max, self.disabled)(day):
            return None
        self.cursor = day
        if (day.year, day.month) != self.month() and self.months == 1:
            self.shown = (day.year, day.month)
        if self.mode == "range":
            if self.anchor is None:
                self.anchor, self.hover = day, None
                return None
            start, end = sorted((self.anchor, day))
            self.anchor = self.hover = None
            self.value = (start, end)
            return self.emit("change", (start, end))
        if self.mode == "multiple":
            days = self.selected()
            days = [d for d in days if d != day] if day in days else sorted([*days, day])
            self.value = days
            return self.emit("change", days)
        self.value = day
        return self.emit("change", day)

    def today(self) -> Any:
        """Picks today (in a range: today to today)."""
        day = _dt.date.today()
        self.shown, self.view = (day.year, day.month), "days"
        if self.mode == "range":
            self.anchor = None
            self.value = (day, day)
            return self.emit("change", (day, day))
        return self.pick(day)

    def key(self, event: Any) -> Any:
        """Arrows move the cursor day, Enter/Space picks it, Page Up/Down change month, Home/End the week."""
        combo = (event.key or "").lower()
        name = combo.rsplit("-", 1)[-1]
        picked = self.selected()
        day = self.cursor or (picked[-1] if picked else _dt.date.today())
        moves = {"left": -1, "right": 1, "up": -7, "down": 7}
        if name in moves:
            day += _dt.timedelta(days=moves[name])
        elif name in ("pageup", "pagedown"):
            months = (1 if name == "pagedown" else -1) * (12 if "shift" in combo else 1)
            day = _add_months(day, months)
        elif name == "home":
            day -= _dt.timedelta(days=(day.weekday() - _first(self.first_weekday)) % 7)
        elif name == "end":
            day += _dt.timedelta(days=6 - (day.weekday() - _first(self.first_weekday)) % 7)
        elif name in ("enter", "space"):
            return self.pick(day)
        else:
            return None
        self.cursor = day
        if self.mode == "range" and self.anchor is not None:
            self.hover = day
        year, month = self.month()
        first = _dt.date(year, month, 1)
        if day < first or day > _add_months(first, self.months) - _dt.timedelta(days=1):
            self.shown = (day.year, day.month)
        return None

    def set_hover(self, day: Optional[_dt.date]) -> None:
        """Previews a range ending on ``day`` while it is being picked."""
        if self.anchor is not None and self.hover != day:
            self.hover = day

    # -- view -------------------------------------------------------------------------------------------------
    def _header(self, t: Theme, title: str, on_title: Any) -> Any:
        return _core.row([
            icon_button("chevron-left", lambda: self.step(-1), size="sm", tooltip=_t("pyzed.date.previous"), theme=t),
            _core.container(
                _core.button(_core.text(title, size=13, weight="semibold", color=t.text, wrap=False), on_title,
                             padding=(3, 8), bg="transparent", hover_bg=t.ghost_hover, radius=t.radius_sm),
                width="fill", align_x="center"),
            icon_button("chevron-right", lambda: self.step(1), size="sm", tooltip=_t("pyzed.date.next"), theme=t),
        ], align="center", width="fill")

    def _day(self, t: Theme, day: _dt.date, in_month: bool, off: bool, picked: List[_dt.date],
             span: Optional[Tuple[_dt.date, _dt.date]]) -> Any:
        if not in_month and not self.show_outside:
            return _core.space(width=CELL, height=CELL)
        chosen = day in picked
        inside = span is not None and span[0] < day < span[1]
        today = day == _dt.date.today()
        color = t.on_accent if chosen else (t.text_disabled if off else (t.text if in_month else t.text_muted))
        bg = t.accent if chosen else (_alpha(t.accent, 0.16) if inside else None)
        ring = t.border_focused if day == self.cursor else (t.accent if today and not chosen else None)
        cell = _core.container(
            _core.text(str(day.day), size=12.5, color=color, weight="semibold" if today else None, wrap=False),
            width=CELL, height=CELL, center=True, bg=bg, radius=t.radius_sm,
            border_color=ring, border_width=1.0 if ring else 0.0)
        if off:
            return cell
        cell = cell.on(click=lambda d=day: self.pick(d), cursor="pointer")
        if self.mode == "range" and self.anchor is not None:
            cell = cell.on(mouse_enter=lambda d=day: self.set_hover(d))
        if not chosen:
            cell = cell.style(hover={"background": t.ghost_hover})
        return cell

    def _month(self, t: Theme, year: int, month: int, header: Any) -> Any:
        first = _first(self.first_weekday)
        names = _names("days_min")
        weekdays = [_core.container(_core.text(_capital(names[(first + i) % 7]), size=11, color=t.text_muted,
                                               wrap=False), width=CELL, height=24, center=True) for i in range(7)]
        if self.week_numbers:
            weekdays.insert(0, _core.container(_core.text(_t("pyzed.date.week"), size=10, color=t.text_placeholder,
                                                          wrap=False), width=CELL - 6, height=24, center=True))
        off = _disabled_check(self.min, self.max, self.disabled)
        picked = self.selected()
        span: Optional[Tuple[_dt.date, _dt.date]] = None
        if self.mode == "range":
            if self.anchor is not None:
                end = self.hover or self.anchor
                span = tuple(sorted((self.anchor, end)))  # type: ignore[assignment]
                picked = list(span)  # type: ignore[arg-type]
            elif len(picked) == 2:
                span = (picked[0], picked[1])
        start = _dt.date(year, month, 1)
        start -= _dt.timedelta(days=(start.weekday() - first) % 7)
        rows = [_core.row(weekdays, spacing=2)]
        for week in range(6):
            days = [start + _dt.timedelta(days=week * 7 + i) for i in range(7)]
            cells = [self._day(t, d, d.month == month, off(d), picked, span) for d in days]
            if self.week_numbers:
                cells.insert(0, _core.container(_core.text(str(days[0].isocalendar()[1]), size=10,
                                                           color=t.text_placeholder, wrap=False),
                                                width=CELL - 6, height=CELL, center=True))
            rows.append(_core.row(cells, spacing=2))
        return _core.column([header, *rows], spacing=2)

    def _grid(self, t: Theme, items: Sequence[Tuple[str, Any, bool]]) -> Any:
        rows = []
        for i in range(0, len(items), 3):
            cells = []
            for text, action, active in items[i:i + 3]:
                cells.append(_core.button(
                    _core.container(_core.text(text, size=12.5, color=t.on_accent if active else t.text, wrap=False),
                                    width="fill", center=True),
                    action, width="fill", height=40, padding=0, radius=t.radius_sm,
                    bg=t.accent if active else "transparent", hover_bg=t.accent if active else t.ghost_hover))
            rows.append(_core.row(cells, spacing=4, width="fill"))
        return _core.column(rows, spacing=4, width="fill")

    def render(self) -> Any:
        t = _current_theme()
        year, month = self.month()
        names = _names("months")
        picked = self.selected()
        if self.view == "months":
            def choose_month(m: int) -> None:
                self.shown, self.view = (year, m), "days"

            body = _core.column([
                self._header(t, str(year), lambda: self.set_view("years")),
                self._grid(t, [(_capital(n).rstrip("."), lambda m=i + 1: choose_month(m),
                                (year, i + 1) == (_dt.date.today().year, _dt.date.today().month))
                               for i, n in enumerate(_names("months_short"))]),
            ], spacing=8, width=7 * CELL + 12)
        elif self.view == "years":
            base = year - year % 12

            def choose_year(y: int) -> None:
                self.shown, self.view = (y, month), "months"

            body = _core.column([
                self._header(t, f"{base} – {base + 11}", None),
                self._grid(t, [(str(y), lambda y=y: choose_year(y), any(d.year == y for d in picked))
                               for y in range(base, base + 12)]),
            ], spacing=8, width=7 * CELL + 12)
        else:
            months = []
            for i in range(max(1, int(self.months or 1))):
                index = year * 12 + month - 1 + i
                y, m = index // 12, index % 12 + 1
                title = f"{_capital(names[m - 1])} {y}"
                if self.months > 1:  # one pair of arrows for all: back on the first, forward on the last
                    header = _core.row([
                        icon_button("chevron-left", lambda: self.step(-1), size="sm", theme=t) if i == 0 else
                        _core.space(width=24),
                        _core.container(_core.text(title, size=13, weight="semibold", color=t.text, wrap=False),
                                        width="fill", align_x="center"),
                        icon_button("chevron-right", lambda: self.step(1), size="sm", theme=t)
                        if i == self.months - 1 else _core.space(width=24),
                    ], align="center", width="fill")
                else:
                    header = self._header(t, title, lambda: self.set_view("months"))
                months.append(self._month(t, y, m, header))
            body = _core.row(months, spacing=16)
        # a fixed width: the popup of a picker would let the "Today" row stretch to the whole window
        month_width = 7 * CELL + 12 + (CELL - 4 if self.week_numbers else 0)
        count = 1 if self.view != "days" else max(1, int(self.months or 1))
        width = month_width * count + 16 * (count - 1) if self.view == "days" else 7 * CELL + 12
        parts = [body]
        if self.today_button:
            parts.append(_core.row([
                _core.space(width="fill"),
                _core.button(_core.text(_t("pyzed.date.today"), size=12.5, color=t.text_accent, wrap=False),
                             self.today, padding=(3, 8), bg="transparent", hover_bg=t.ghost_hover,
                             radius=t.radius_sm),
            ], width="fill"))
        return _core.container(_core.column(parts, spacing=6, width=width), padding=8).on(key_down=self.key)


# -- fields ---------------------------------------------------------------------------------------------------


def _panel(content: Any, t: Theme) -> Any:
    return _core.container(content, padding=4, bg=t.elevated, border_color=t.border, border_width=1,
                           radius=t.radius + 2, shadow=(t.shadow, (0, 4), 12))


def _field(t: Theme, text: str, placeholder: str, on_input: Any, on_submit: Any, icon: str, on_icon: Any,
           disabled: bool, invalid: bool, open_: bool, clear: Any = None, id: Optional[str] = None) -> Any:
    """A text box with a button at the end, the look of ``ui.input``."""
    entry = _core.text_input(
        text, placeholder=placeholder, on_input=None if disabled else on_input,
        on_submit=None if disabled else on_submit, id=id, size=13.5, padding=(5, 8), width="fill",
        bg="transparent", border_width=0.0, color=t.text_disabled if disabled else t.text,
        placeholder_color=t.text_placeholder, selection_color=t.selection)
    parts = [entry]
    if clear is not None and text and not disabled:
        parts.append(_core.button(_icon("x", size=12, color=t.icon_muted), clear, padding=3, bg="transparent",
                                  hover_bg=t.ghost_hover, radius=999))
    parts.append(_core.button(_icon(icon, size=14, color=t.text_disabled if disabled else
                                    (t.text_accent if open_ else t.icon_muted)),
                              None if disabled else on_icon, padding=(4, 6), bg="transparent",
                              hover_bg=t.ghost_hover, radius=t.radius_sm - 1))
    border = t.error if invalid else (t.border_focused if open_ else t.border)
    return _core.container(_core.row(parts, align="center", spacing=2), width="fill", padding=(0, 2, 0, 0),
                           bg=t.element if disabled else t.editor, border_color=border, border_width=1,
                           radius=t.radius_sm)


class DatePicker(Component):
    """A date field with a calendar that opens below it.

    Type a date in ``format`` and press Enter, or open the calendar with its button or Alt+↓.
    Once clicked, ↑/↓ move the date a day (Page Up/Down a month) without opening anything.
    ``clearable`` adds an x that empties it; ``today_button`` a "Today" link in the calendar.

    Events:
        ``on_change(event)``: The date changed (``event.value`` is a ``datetime.date`` or ``None``).
        ``on_open(event)``: The calendar opened.
        ``on_close(event)``: The calendar closed.
    """

    value: Any = None
    format: str = "YYYY-MM-DD"  # noqa: A003
    placeholder: str = ""
    min: Any = None  # noqa: A003
    max: Any = None  # noqa: A003
    disabled_dates: list = ()
    first_weekday: str = "monday"
    week_numbers: bool = False
    clearable: bool = True
    today_button: bool = True
    disabled: bool = False
    invalid: bool = False
    events = {"change": "The date changed (``event.value``).", "open": "The calendar opened.",
              "close": "The calendar closed."}
    icon = "calendar-days"
    label = "Date picker"
    category = "Date & time"
    size = (180, 30)
    designer = False

    def setup(self) -> None:
        self.open = False
        self.text: Optional[str] = None  # what is being typed, until Enter

    def set_open(self, open_: bool) -> Any:
        """Opens or closes the calendar."""
        if open_ == self.open or (open_ and self.disabled):
            return None
        self.open = open_
        return self.emit("open" if open_ else "close")

    def toggle(self) -> Any:
        return self.set_open(not self.open)

    def choose(self, day: Optional[_dt.date]) -> Any:
        """Sets the date (``None`` empties it), closes the calendar and emits ``change``."""
        self.text = None
        closing = self.set_open(False)
        if day == to_date(self.value):
            return closing
        self.value = day
        return self.emit("change", day)

    def typed(self, text: str) -> None:
        self.text = text

    def commit(self) -> Any:
        """Reads the typed text (Enter or leaving the field); text that is not a date is dropped."""
        if self.text is None:
            return None
        text, self.text = self.text, None
        if not text.strip():
            return self.choose(None)
        day = parse_date(text, self.format)
        if day is None or _disabled_check(self.min, self.max, self.disabled_dates)(day):
            return None
        return self.choose(day)

    def nudge(self, days: int = 0, months: int = 0) -> Any:
        """Moves the date (today when there is none), skipping days that are turned off."""
        day = to_date(self.value) or _dt.date.today()
        off = _disabled_check(self.min, self.max, self.disabled_dates)
        for _ in range(366):
            day = _add_months(day, months) if months else day + _dt.timedelta(days=days)
            if not off(day):
                self.text = None
                self.value = day
                return self.emit("change", day)
            if months:
                return None
        return None

    def key(self, event: Any) -> Any:
        combo = (event.key or "").lower()
        if self.open or self.disabled:
            return None
        if combo in ("alt-down", "f4"):
            return self.set_open(True)
        if combo == "up":
            return self.nudge(days=-1)
        if combo == "down":
            return self.nudge(days=1)
        if combo == "pageup":
            return self.nudge(months=-1)
        if combo == "pagedown":
            return self.nudge(months=1)
        return None

    def render(self) -> Any:
        t = _current_theme()
        shown = self.text if self.text is not None else format_date(self.value, self.format)
        field = _field(t, shown, self.placeholder or self.format, self.typed, self.commit, "calendar",
                       self.toggle, self.disabled, self.invalid, self.open,
                       clear=(lambda: self.choose(None)) if self.clearable else None)
        field = field.on(key_down=self.key, blur=self.commit)
        calendar = None
        if self.open:
            calendar = _panel(Calendar(self.value, min=self.min, max=self.max, disabled=self.disabled_dates,
                                       first_weekday=self.first_weekday, week_numbers=self.week_numbers,
                                       today_button=self.today_button, on_change=lambda e: self.choose(e.value)), t)
        return _core.popup(field, calendar, on_dismiss=lambda: self.set_open(False))


class DateRangePicker(Component):
    """A field for a start and an end date, with two months and quick ranges ("Last 7 days"...).

    The first click on the calendar picks the start and the second the end. Typed text is two
    dates in ``format`` split by ``separator``. ``presets`` shows the quick ranges.

    Events:
        ``on_change(event)``: The range changed (``event.value`` is ``(start, end)``, dates or ``None``).
        ``on_open(event)``: The calendar opened.
        ``on_close(event)``: The calendar closed.
    """

    value: Any = None
    format: str = "YYYY-MM-DD"  # noqa: A003
    separator: str = " – "
    placeholder: str = ""
    min: Any = None  # noqa: A003
    max: Any = None  # noqa: A003
    disabled_dates: list = ()
    first_weekday: str = "monday"
    months: int = 2
    presets: bool = True
    clearable: bool = True
    disabled: bool = False
    invalid: bool = False
    events = {"change": "The range changed (``event.value`` is ``(start, end)``).", "open": "The calendar opened.",
              "close": "The calendar closed."}
    icon = "calendar-range"
    label = "Date range picker"
    category = "Date & time"
    size = (240, 30)
    designer = False

    def setup(self) -> None:
        self.open = False
        self.text: Optional[str] = None

    def set_open(self, open_: bool) -> Any:
        if open_ == self.open or (open_ and self.disabled):
            return None
        self.open = open_
        return self.emit("open" if open_ else "close")

    def toggle(self) -> Any:
        return self.set_open(not self.open)

    def choose(self, value: Any) -> Any:
        """Sets the range, closes the calendar and emits ``change``."""
        start, end = _pair(value)
        self.text = None
        closing = self.set_open(False)
        if (start, end) == _pair(self.value):
            return closing
        self.value = (start, end)
        return self.emit("change", (start, end))

    def typed(self, text: str) -> None:
        self.text = text

    def commit(self) -> Any:
        if self.text is None:
            return None
        text, self.text = self.text, None
        if not text.strip():
            return self.choose((None, None))
        parts = [p for p in re.split(r"\s*(?:" + re.escape(self.separator.strip() or "–") + r"|–|—)\s*", text)
                 if p.strip()]
        days = [parse_date(p, self.format) for p in parts[:2]]
        if len(days) != 2 or None in days:
            return None
        return self.choose(tuple(sorted(days)))  # type: ignore[type-var]

    def key(self, event: Any) -> Any:
        combo = (event.key or "").lower()
        if not self.open and not self.disabled and combo in ("alt-down", "f4"):
            return self.set_open(True)
        return None

    def text_of(self) -> str:
        start, end = _pair(self.value)
        if start is None and end is None:
            return ""
        return f"{format_date(start, self.format)}{self.separator}{format_date(end, self.format)}"

    def render(self) -> Any:
        t = _current_theme()
        shown = self.text if self.text is not None else self.text_of()
        field = _field(t, shown, self.placeholder or f"{self.format}{self.separator}{self.format}", self.typed,
                       self.commit, "calendar-range", self.toggle, self.disabled, self.invalid, self.open,
                       clear=(lambda: self.choose((None, None))) if self.clearable else None)
        field = field.on(key_down=self.key, blur=self.commit)
        content = None
        if self.open:
            calendar = Calendar(self.value, mode="range", min=self.min, max=self.max, disabled=self.disabled_dates,
                                first_weekday=self.first_weekday, months=self.months,
                                on_change=lambda e: self.choose(e.value))
            parts: List[Any] = []
            if self.presets:
                current = _pair(self.value)
                parts.append(_core.column([
                    _core.button(_core.text(name, size=12.5, color=t.text, wrap=False),
                                 lambda r=r: self.choose(r), width="fill", padding=(5, 8), radius=t.radius_sm,
                                 bg=t.element_selected if r == current else "transparent", hover_bg=t.ghost_hover)
                    for name, r in range_presets(first_weekday=self.first_weekday)
                ], spacing=1, width=132, padding=(8, 4, 8, 0)))
            parts.append(calendar)
            content = _panel(_core.row(parts, spacing=4), t)
        return _core.popup(field, content, on_dismiss=lambda: self.set_open(False))


class TimePicker(Component):
    """A time field with columns of hours and minutes that open below it.

    ``format`` is ``"HH:mm"`` (24 hours), ``"h:mm A"`` (12 hours with AM/PM) or one with
    seconds; ``minute_step`` spaces the minutes offered (5 gives 00, 05, 10...). Once clicked,
    ↑/↓ change it by ``minute_step`` without opening anything.

    Events:
        ``on_change(event)``: The time changed (``event.value`` is a ``datetime.time`` or ``None``).
        ``on_open(event)``: The list opened.
        ``on_close(event)``: The list closed.
    """

    value: Any = None
    format: str = "HH:mm"  # noqa: A003
    placeholder: str = ""
    minute_step: int = 5
    min: Any = None  # noqa: A003
    max: Any = None  # noqa: A003
    clearable: bool = True
    disabled: bool = False
    invalid: bool = False
    events = {"change": "The time changed (``event.value``).", "open": "The list opened.", "close": "The list closed."}
    icon = "clock"
    label = "Time picker"
    category = "Date & time"
    size = (140, 30)
    designer = False

    def setup(self) -> None:
        self.open = False
        self.text: Optional[str] = None
        self.ids = tuple(f"time-picker-{id(self)}-{n}" for n in range(3))

    @property
    def twelve(self) -> bool:
        return "h" in self.format.replace("hh", "h") and "H" not in self.format or "%I" in self.format

    @property
    def seconds(self) -> bool:
        return "s" in self.format.replace("%", "") and ("ss" in self.format or ":s" in self.format or "%S" in self.format)

    def set_open(self, open_: bool) -> Any:
        if open_ == self.open or (open_ and self.disabled):
            return None
        self.open = open_
        event = self.emit("open" if open_ else "close")
        if not open_:
            return event
        # Each column scrolls to the selected value, a few rows from the top.
        now = to_time(self.value) or _dt.time(0, 0)
        step = max(1, int(self.minute_step or 1))
        rows = [now.hour % 12 if self.twelve else now.hour, now.minute // step, now.second // step]
        scroll = _core.Command.batch([_core.Command.scroll_to(id_, y=max(row - 3, 0) * 27)
                                      for id_, row in zip(self.ids, rows)])
        return scroll if event is None else [event, scroll]

    def toggle(self) -> Any:
        return self.set_open(not self.open)

    def allowed(self, moment: _dt.time) -> bool:
        lo, hi = to_time(self.min), to_time(self.max)
        return (lo is None or moment >= lo) and (hi is None or moment <= hi)

    def choose(self, moment: Optional[_dt.time], close: bool = False) -> Any:
        self.text = None
        closing = self.set_open(False) if close else None
        if moment is not None and not self.allowed(moment):
            return closing
        if moment == to_time(self.value):
            return closing
        self.value = moment
        return self.emit("change", moment)

    def set_part(self, hour: Optional[int] = None, minute: Optional[int] = None, second: Optional[int] = None,
                 pm: Optional[bool] = None) -> Any:
        """Changes one part of the time (the others stay)."""
        now = to_time(self.value) or _dt.time(0, 0)
        h = now.hour if hour is None else hour
        if pm is not None:
            h = h % 12 + (12 if pm else 0)
        elif hour is not None and self.twelve:
            h = hour % 12 + (12 if now.hour >= 12 else 0)
        return self.choose(_dt.time(h, now.minute if minute is None else minute,
                                    now.second if second is None else second))

    def typed(self, text: str) -> None:
        self.text = text

    def commit(self) -> Any:
        if self.text is None:
            return None
        text, self.text = self.text, None
        if not text.strip():
            return self.choose(None)
        moment = parse_time(text, self.format)
        return self.choose(moment) if moment is not None else None

    def nudge(self, minutes: int) -> Any:
        now = to_time(self.value) or _dt.time(0, 0)
        total = (now.hour * 60 + now.minute + minutes) % (24 * 60)
        return self.choose(_dt.time(total // 60, total % 60, now.second))

    def key(self, event: Any) -> Any:
        combo = (event.key or "").lower()
        if self.open or self.disabled:
            return None
        step = max(1, int(self.minute_step or 1))
        if combo in ("alt-down", "f4"):
            return self.set_open(True)
        if combo == "up":
            return self.nudge(-step)
        if combo == "down":
            return self.nudge(step)
        if combo == "pageup":
            return self.nudge(-60)
        if combo == "pagedown":
            return self.nudge(60)
        return None

    def _column(self, t: Theme, items: Sequence[Tuple[str, Any, bool, bool]], id_: str) -> Any:
        rows = [_core.button(_core.container(_core.text(text, size=12.5, wrap=False,
                                                        color=t.on_accent if active else
                                                        (t.text_disabled if off else t.text)),
                                             width="fill", center=True),
                             None if off else action, width=44, height=26, padding=0, radius=t.radius_sm,
                             bg=t.accent if active else "transparent", hover_bg=t.accent if active else t.ghost_hover)
                for text, action, active, off in items]
        return _core.scrollable(_core.column(rows, spacing=1, padding=(0, 6, 0, 0)), height=208, width=52,
                                scrollbar_width=3, scroller_width=3, id=id_)

    def render(self) -> Any:
        t = _current_theme()
        shown = self.text if self.text is not None else format_time(self.value, self.format)
        field = _field(t, shown, self.placeholder or self.format, self.typed, self.commit, "clock", self.toggle,
                       self.disabled, self.invalid, self.open,
                       clear=(lambda: self.choose(None)) if self.clearable else None)
        field = field.on(key_down=self.key, blur=self.commit)
        content = None
        if self.open:
            now = to_time(self.value)
            step = max(1, int(self.minute_step or 1))
            if self.twelve:
                hours = [(f"{h:02d}" if "hh" in self.format else str(h), (h % 12), ) for h in (12, *range(1, 12))]
                hour_items = [(text, lambda h=h: self.set_part(hour=h), now is not None and now.hour % 12 == h, False)
                              for text, h in hours]
            else:
                hour_items = [(f"{h:02d}", lambda h=h: self.set_part(hour=h), now is not None and now.hour == h,
                               False) for h in range(24)]
            columns = [self._column(t, hour_items, self.ids[0]), self._column(t, [
                (f"{m:02d}", lambda m=m: self.set_part(minute=m), now is not None and now.minute == m, False)
                for m in range(0, 60, step)], self.ids[1])]
            if self.seconds:
                columns.append(self._column(t, [
                    (f"{s:02d}", lambda s=s: self.set_part(second=s), now is not None and now.second == s, False)
                    for s in range(0, 60, step)], self.ids[2]))
            if self.twelve:
                columns.append(_core.column([
                    _core.button(_core.container(_core.text(x, size=12.5, wrap=False, color=t.on_accent if on
                                                            else t.text), width="fill", center=True),
                                 lambda pm=pm: self.set_part(pm=pm), width=44, height=26, padding=0,
                                 radius=t.radius_sm, bg=t.accent if on else "transparent",
                                 hover_bg=t.accent if on else t.ghost_hover)
                    for x, pm, on in (("AM", False, now is not None and now.hour < 12),
                                      ("PM", True, now is not None and now.hour >= 12))], spacing=1))
            footer = _core.row([
                _core.button(_core.text(_t("pyzed.date.now"), size=12.5, color=t.text_accent, wrap=False),
                             lambda: self.choose(_dt.datetime.now().time().replace(second=0, microsecond=0)),
                             padding=(3, 8), bg="transparent", hover_bg=t.ghost_hover, radius=t.radius_sm),
                _core.space(width="fill"),
                _core.button(_core.text(_t("pyzed.ok"), size=12.5, color=t.text, wrap=False),
                             lambda: self.set_open(False), padding=(3, 10), bg=t.element, hover_bg=t.element_hover,
                             radius=t.radius_sm),
            ], width="fill", align="center")
            width = 52 * len(columns) + 4 * (len(columns) - 1) + 8
            content = _panel(_core.column([_core.container(_core.row(columns, spacing=4), width="fill", align_x="center"),
                                           footer], spacing=6, padding=4,
                                          width=max(width, 150)), t)
        return _core.popup(field, content, on_dismiss=lambda: self.set_open(False))


def _signature(cls: type, positional: int = 1) -> None:
    """Gives ``cls`` the signature of its props and events (shown by help() and the reference); the first
    ``positional`` props can be passed without their name."""
    params = [inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD if i < positional else
                                inspect.Parameter.KEYWORD_ONLY,
                                default=inspect.Parameter.empty if info.required else info.default)
              for i, (name, info) in enumerate(cls.__props__.items())]
    params += [inspect.Parameter(f"on_{name}", inspect.Parameter.KEYWORD_ONLY, default=None)
               for name in cls.__events__ if name not in ("mount", "unmount")]
    cls.__signature__ = inspect.Signature(params)  # type: ignore[attr-defined]


for _cls in (Calendar, DatePicker, DateRangePicker, TimePicker):
    _signature(_cls)
