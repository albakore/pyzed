"""Dates and times: formats, the calendar, the date, range and time pickers, and their designer controls."""

import datetime as dt

import pytest

import pyzed as pz
from pyzed import i18n, ui
from pyzed.designer import components
from pyzed.designer.model import Form
from pyzed.designer.runtime import FormApp
from pyzed.ui import dates

D = dt.date


@pytest.fixture
def spanish():
    i18n.set_language("es")
    yield
    i18n.set_language("en")


def test_formats_write_dates_with_tokens():
    day = D(2026, 10, 5)
    assert ui.format_date(day) == "2026-10-05"
    assert ui.format_date(day, "DD/MM/YYYY") == "05/10/2026"
    assert ui.format_date("2026-10-05", "MMM D, YYYY") == "Oct 5, 2026"
    assert ui.format_date(day, "dddd, D MMMM YYYY") == "Monday, 5 October 2026"
    assert ui.format_date(day, "[week of] D/M/YY") == "week of 5/10/26"
    assert ui.format_date(day, "%d.%m.%Y") == "05.10.2026"  # strftime
    assert ui.format_date(None) == "" and ui.format_date("not a date") == ""
    assert ui.format_time(dt.time(14, 5)) == "14:05"
    assert ui.format_time("14:05", "h:mm A") == "2:05 PM" and ui.format_time("00:30", "hh:mm a") == "12:30 am"


def test_month_and_day_names_follow_the_language(spanish):
    assert ui.format_date(D(2026, 10, 5), "dddd, D [de] MMMM [de] YYYY") == "lunes, 5 de octubre de 2026"
    assert ui.parse_date("lunes, 5 de octubre de 2026", "dddd, D [de] MMMM [de] YYYY") == D(2026, 10, 5)
    assert ui.parse_date("5 sept 2026", "D MMM YYYY") == D(2026, 9, 5)


def test_parsing_reads_the_format_and_falls_back_to_iso():
    assert ui.parse_date("05/10/2026", "DD/MM/YYYY") == D(2026, 10, 5)
    assert ui.parse_date("10/05/2026", "MM/DD/YYYY") == D(2026, 10, 5)
    assert ui.parse_date("Oct 5, 2026", "MMM D, YYYY") == D(2026, 10, 5)
    assert ui.parse_date("  5.10.2026 ", "DD.MM.YYYY") == D(2026, 10, 5)
    assert ui.parse_date("2026-10-05", "DD/MM/YYYY") == D(2026, 10, 5)  # ISO always works
    assert ui.parse_date("31/02/2026", "DD/MM/YYYY") is None and ui.parse_date("soon", "DD/MM/YYYY") is None
    assert ui.parse_time("2:30 PM", "h:mm A") == dt.time(14, 30)
    assert ui.parse_time("14:30:05", "HH:mm:ss") == dt.time(14, 30, 5)
    assert ui.parse_time("9") == dt.time(9, 0) and ui.parse_time("25:00") is None


def test_range_presets():
    presets = dict(dates.range_presets(D(2026, 10, 22)))
    assert presets["Today"] == (D(2026, 10, 22), D(2026, 10, 22))
    assert presets["Last 7 days"] == (D(2026, 10, 16), D(2026, 10, 22))
    assert presets["This week"] == (D(2026, 10, 19), D(2026, 10, 25))  # Monday to Sunday
    assert presets["Last month"] == (D(2026, 9, 1), D(2026, 9, 30))
    sunday = dict(dates.range_presets(D(2026, 10, 22), first_weekday="sunday"))
    assert sunday["This week"] == (D(2026, 10, 18), D(2026, 10, 24))


def test_calendar_picks_a_day_a_range_or_several():
    seen = []
    cal = ui.Calendar.create(D(2026, 10, 5), on_change=lambda e: seen.append(e.value))
    assert cal.month() == (2026, 10)
    cal.pick(D(2026, 10, 9))
    assert seen == [D(2026, 10, 9)] and cal.value == D(2026, 10, 9)

    seen.clear()
    cal = ui.Calendar.create(mode="range", on_change=lambda e: seen.append(e.value))
    cal.pick(D(2026, 10, 14))
    assert seen == [] and cal.anchor == D(2026, 10, 14)  # waiting for the end
    cal.set_hover(D(2026, 10, 2))
    assert cal.hover == D(2026, 10, 2)
    cal.pick(D(2026, 10, 2))
    assert seen == [(D(2026, 10, 2), D(2026, 10, 14))] and cal.anchor is None

    seen.clear()
    cal = ui.Calendar.create(["2026-10-01"], mode="multiple", on_change=lambda e: seen.append(e.value))
    cal.pick(D(2026, 10, 3))
    cal.pick(D(2026, 10, 1))
    assert seen[-1] == [D(2026, 10, 3)]


def test_calendar_turns_days_off_and_moves_with_the_keyboard():
    seen = []
    cal = ui.Calendar.create(D(2026, 10, 5), min="2026-10-02", disabled=["sunday", "2026-10-20"],
                             on_change=lambda e: seen.append(e.value))
    cal.pick(D(2026, 10, 1))  # before min
    cal.pick(D(2026, 10, 11))  # a Sunday
    cal.pick(D(2026, 10, 20))
    assert seen == []
    key = lambda k: cal.key(pz.Event("key_down", key=k))  # noqa: E731
    key("right")
    key("down")
    assert cal.cursor == D(2026, 10, 13)
    key("pagedown")
    assert cal.cursor == D(2026, 11, 13) and cal.month() == (2026, 11)
    key("enter")
    assert seen == [D(2026, 11, 13)]
    cal.step(-1)
    assert cal.month() == (2026, 10)
    cal.set_view("years")
    cal.step(1)
    assert cal.month() == (2038, 10)


def test_calendar_renders_every_view():
    cal = ui.Calendar.create(("2026-10-05", "2026-10-14"), mode="range", months=2, week_numbers=True,
                             today_button=True)
    assert cal.render() is not None
    for view in ("months", "years"):
        cal.set_view(view)
        assert cal.render() is not None


def test_date_picker_types_steps_and_opens():
    seen, opened = [], []
    picker = ui.DatePicker.create("2026-10-05", format="DD/MM/YYYY", min="2026-10-01",
                                  on_change=lambda e: seen.append(e.value), on_open=lambda e: opened.append(True))
    picker.typed("09/10/2026")
    picker.commit()
    assert seen == [D(2026, 10, 9)] and picker.text is None
    picker.typed("not a date")
    picker.commit()
    assert seen == [D(2026, 10, 9)]  # ignored
    key = lambda k: picker.key(pz.Event("key_down", key=k))  # noqa: E731
    key("down")
    key("pagedown")
    assert seen[-2:] == [D(2026, 10, 10), D(2026, 11, 10)] and not picker.open
    key("alt-down")
    assert picker.open and opened == [True]
    assert picker.render() is not None
    picker.choose(D(2026, 12, 24))
    assert not picker.open and seen[-1] == D(2026, 12, 24)
    picker.typed("")
    picker.commit()
    assert seen[-1] is None


def test_date_range_picker_reads_two_dates():
    seen = []
    picker = ui.DateRangePicker.create(format="DD/MM/YYYY", on_change=lambda e: seen.append(e.value))
    picker.typed("14/10/2026 – 05/10/2026")
    picker.commit()
    assert seen == [(D(2026, 10, 5), D(2026, 10, 14))]
    assert picker.text_of() == "05/10/2026 – 14/10/2026"
    picker.set_open(True)
    assert picker.render() is not None


def test_time_picker_parts_and_steps():
    seen = []
    picker = ui.TimePicker.create("14:30", format="h:mm A", minute_step=15, on_change=lambda e: seen.append(e.value))
    assert picker.twelve and not picker.seconds
    picker.set_part(minute=45)
    picker.set_part(pm=False)
    picker.set_part(hour=3)
    assert seen == [dt.time(14, 45), dt.time(2, 45), dt.time(3, 45)]
    picker.key(pz.Event("key_down", key="down"))
    assert seen[-1] == dt.time(4, 0)
    picker.set_open(True)
    assert picker.render() is not None
    assert ui.TimePicker.create(format="HH:mm:ss").seconds


def test_popup_is_a_widget():
    assert repr(pz.popup(pz.text("a"), pz.text("b"), side="top", align="end")) == "<Widget popup>"
    assert repr(pz.popup(pz.text("a"))) == "<Widget popup>"
    with pytest.raises(ValueError):
        pz.popup(pz.text("a"), side="middle")


# -- in Pyzed Design ------------------------------------------------------------------------------------------------
def _app(type_, events=(), **props):
    form = Form(name="f")
    control = components.get(type_).create("c1", 10, 10)
    control.props.update(props)
    control.events = {e: f"c1_{e}" for e in events}
    form.controls.append(control)
    seen = []
    app = FormApp(form, {f"c1_{e}": (lambda form, event: seen.append((event.name, event.value))) for e in events})
    app.seen = seen
    return app, app.runtime.form["c1"]


def test_date_controls_are_in_their_own_toolbox_section():
    groups = components.categories()
    assert [c.type for c in groups["Date & time"]] == ["date_picker", "date_range", "time_picker", "calendar"]
    assert {"input", "checkbox", "select", "number", "slider", "color_picker"} <= {c.type for c in groups["Forms"]}
    assert [c.type for c in groups["Common"]] == ["label", "heading", "button", "link", "split_button"]
    names = list(groups)
    assert names.index("Forms") == 1 and names.index("Date & time") == 2


def test_designer_date_controls_keep_text_values(tmp_path):
    for type_ in ("date_picker", "date_range", "time_picker", "calendar"):
        app, _ = _app(type_)
        app.screenshot(tmp_path / f"{type_}.png", size=(400, 360), scale=1.0)
    from pyzed.designer.runtime import LiveContext

    app, control = _app("date_picker", ("change",))

    ctx = LiveContext(app.runtime)
    components._changed(control, ctx, "value")(pz.Event("change", value=D(2026, 10, 22)))
    assert control.props["value"] == "2026-10-22" and app.seen == [("change", "2026-10-22")]
    assert components._iso(dt.time(9, 30)) == "09:30" and components._iso(None) == ""
