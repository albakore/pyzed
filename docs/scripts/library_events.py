"""The events of the component library: what each handler receives and how to handle the events.

Read by gen_library.py, which adds an "Events" section to every page of the library and writes
``library/events.mdx`` (the events of every component, counted). The events themselves come from the
signatures: every ``on_*`` parameter of an entry's public names is an event, described by its parameter
description in ``api_docs_<lang>.py``.

``HANDLERS``   What the handler of an event receives, written as the call Pyzed makes: ``"()"`` (nothing),
               ``"(text)"``, ``"(x, y)"``... Keys are ``"ui.table.on_sort"`` (one event of one name),
               ``"ui.tree.*"`` (every event of a name) or ``"on_input"`` (the default for a parameter).
               ``pz.Component`` classes default to ``"(event)"``.
``SHAPES``     ``T(en, es)`` meaning of each handler shape, for the table of ``library/events.mdx``.
``EXAMPLES``   Per slug, the same events handled three ways (shown as tabs):

               ``imperative``   an ``App`` whose methods change ``self``;
               ``declarative``  handlers that produce messages, and one ``update()`` that decides;
               ``functional``   a frozen ``State`` and a pure ``view(state, set_state)``.

               The snippets are complete: ``tests/test_library_events.py`` runs every ``imperative`` and
               ``declarative`` snippet (``pz``, ``ui`` and ``draw`` are imported, the last class is the app
               and its ``view()`` is rendered) and calls ``view(State(), set_state)`` of every
               ``functional`` one. A snippet may use ``main_view()`` for a stand-in of the rest of the app.
"""

from __future__ import annotations


def T(en, es):
    """A text in English (the site's main language) and Spanish."""
    return {"en": en, "es": es}


HANDLERS = {
    # Defaults by parameter name.
    "on_press": "()", "on_submit": "()", "on_close": "()", "on_dismiss": "()", "on_cancel": "()",
    "on_confirm": "()", "on_clear": "()", "on_save": "()", "on_discard": "()", "on_release": "()",
    "on_open": "()", "on_menu": "()", "on_more": "()", "on_new": "()", "on_minimize": "()",
    "on_maximize": "()", "on_logs": "()", "on_go_to": "()", "on_copy": "()", "on_right_press": "()",
    "on_double_press": "()", "on_double_click": "()", "on_enter": "()", "on_exit": "()",
    "on_middle_press": "()", "on_middle_release": "()", "on_remove": "()", "on_details": "()",
    "on_write": "()", "on_drag": "()",
    "on_input": "(text)", "on_query": "(text)",
    "on_toggle": "(checked)",
    "on_change": "(value)",
    "on_select": "(item)",
    "on_scroll": "(info)",
    "on_move": "(x, y)",
    "on_resize": "(size)",
    "on_cursor": "(line, column)",
    "on_zoom": "(step)",
    "on_action": "(name)",
    "on_link": "(url)",
    "on_pick": "(name)",
    "on_open_url": "(url)",
    "on_error": "(info)",
    # One name, one event.
    "ui.editor.on_change": "(text)", "pz.code_editor.on_change": "(text)",
    "ui.table.on_sort": "(title)", "ui.table.on_row_press": "(row)", "ui.table.on_row_double_press": "(row)",
    "ui.table.on_row_context": "(row)",
    "ui.tree.*": "(id)",
    "ui.accordion.on_toggle": "(key)",
    "ui.disclosure.on_toggle": "()",
    "ui.console.on_toggle_level": "(level)", "ui.console.on_context": "(line)", "ui.console.on_open": "(line)",
    "ui.console.on_source": "(source)",
    "ui.breadcrumbs.on_press": "(index)",
    "ui.tab_bar.on_select": "(tab_id)", "ui.tab_bar.on_close": "(tab_id)", "ui.tab_bar.on_drag": "(tab_id)",
    "ui.tab_bar.on_drop": "(tab_id, event)", "ui.tab_bar.on_drag_over": "(index)",
    "ui.tab_bar.on_context": "(tab_id)", "ui.tab.on_select": "()",
    "ui.workspace.on_resize": "(side, size)",
    "ui.split.on_resize": "(ratio)", "pz.split.on_resize": "(ratio)",
    "ui.error_boundary.on_details": "(info)",
    "ui.radio_group.on_select": "(value)", "pz.radio.on_select": "()",
    "ui.toggle_group.on_select": "(value)",
    "pz.canvas.on_press": "(x, y)", "pz.canvas.on_release": "(x, y)", "pz.canvas.on_right_press": "(x, y)",
    "pz.canvas.on_scroll": "(dx, dy)", "pz.mouse_area.on_scroll": "(dx, dy)",
}

#: Descriptions of events whose name is documented from its docstring (no parameter table).
TEXTS = {
    "ui.reference_browser.on_open_url": T("Called with the URL of a link that leaves the reference (open it in "
                                          "the browser).",
                                          "Se llama con la URL de un enlace que sale de la referencia (ábrela en "
                                          "el navegador)."),
}

SHAPES = {
    "()": T("Nothing: the event is the news (a press, a close, Enter).",
            "Nada: el evento ya es la noticia (una pulsación, un cierre, Enter)."),
    "(text)": T("The new text, on every keystroke.", "El texto nuevo, en cada pulsación de tecla."),
    "(checked)": T("The new state, `True` or `False`.", "El estado nuevo, `True` o `False`."),
    "(value)": T("The new value: a number, a color, an option…", "El valor nuevo: un número, un color, una opción…"),
    "(item)": T("The option that was chosen.", "La opción elegida."),
    "(event)": T("A `pz.Event`: its `value` holds the data, `source` the component.",
                 "Un `pz.Event`: su `value` trae el dato y `source` el componente."),
    "(id)": T("The id of the row or tab (for a tree, its path).", "El id de la fila o pestaña (en un árbol, su ruta)."),
    "(tab_id)": T("The id of the tab.", "El id de la pestaña."),
    "(row)": T("The row (the dict or object you passed in `rows`).", "La fila (el dict u objeto que pasaste en `rows`)."),
    "(x, y)": T("The pointer position, relative to the widget.", "La posición del puntero, relativa al widget."),
    "(dx, dy)": T("How far the wheel turned, in lines.", "Cuánto giró la rueda, en líneas."),
    "(size)": T("The new size in pixels, when a drag ends.", "El tamaño nuevo en píxeles, al terminar de arrastrar."),
    "(ratio)": T("The share of the first pane, from 0 to 1.", "La parte del primer panel, de 0 a 1."),
    "(info)": T("A dict (scroll offset and sizes) or a `ui.ErrorInfo`.",
                "Un dict (desplazamiento y tamaños) o un `ui.ErrorInfo`."),
    "(url)": T("The URL of the link.", "La URL del enlace."),
    "(name)": T("A name: of the icon, or of the editor action.", "Un nombre: del icono o de la acción del editor."),
    "(line)": T("The log line (a `ui.LogEntry`).", "La línea del registro (un `ui.LogEntry`)."),
}

#: The groups of ``pyzed.events.CATALOG``.
GROUPS = {
    "Mouse": T("Mouse", "Ratón"), "Drag": T("Drag", "Arrastre"), "Focus": T("Focus", "Foco"),
    "Keyboard": T("Keyboard", "Teclado"), "Layout": T("Layout", "Tamaño"),
}

#: The Spanish descriptions of ``pyzed.events.CATALOG`` (the English ones are its docs).
COMMON_TEXT = {
    "click": "Se hizo clic en el widget (se pulsó y soltó el botón izquierdo).",
    "double_click": "Dos clics seguidos.",
    "right_click": "Se pulsó el botón derecho (úsalo para menús contextuales).",
    "middle_click": "Se pulsó el botón central (la rueda).",
    "mouse_down": "Se pulsó cualquier botón sobre el widget (`event.button`).",
    "mouse_up": "Se soltó cualquier botón sobre el widget (`event.button`).",
    "mouse_enter": "El puntero entró en el widget.",
    "mouse_leave": "El puntero salió del widget.",
    "mouse_move": "El puntero se movió sobre el widget (`event.x`, `event.y`).",
    "scroll": "La rueda giró sobre el widget (`event.dx`, `event.dy` en líneas).",
    "drag_start": "Se pulsó el botón izquierdo y el puntero se movió unos píxeles.",
    "drag": "El puntero se movió mientras se arrastra (`event.dx`, `event.dy` desde el anterior).",
    "drag_end": "Se soltó el botón después de arrastrar.",
    "focus": "Se hizo clic en el widget y ahora recibe las teclas.",
    "blur": "Un clic en otro sitio le quitó el foco.",
    "key_down": "Se pulsó una tecla con el foco (`event.key`, por ejemplo `\"ctrl-s\"`).",
    "key_up": "Se soltó una tecla con el foco (`event.key`).",
    "resize": "El widget cambió de tamaño, también la primera vez (`event.width`, `event.height`).",
}

#: ``(field, T(en, es))`` of ``pz.Event``.
EVENT_FIELDS = [
    ("`type`", T("The event name (`\"click\"`, or a component's own event).",
                 "El nombre del evento (`\"click\"`, o un evento propio de un componente).")),
    ("`x`, `y`", T("Pointer position relative to the widget (`position` gives both).",
                   "Posición del puntero relativa al widget (`position` da las dos).")),
    ("`window_x`, `window_y`", T("Pointer position in the window.", "Posición del puntero en la ventana.")),
    ("`screen_x`, `screen_y`", T("On the screen (`None` where the system does not say, such as Wayland).",
                                 "En la pantalla (`None` donde el sistema no lo dice, como Wayland).")),
    ("`dx`, `dy`", T("Scroll amount, or drag movement since the previous `drag`.",
                     "Cantidad de desplazamiento, o movimiento del arrastre desde el `drag` anterior.")),
    ("`width`, `height`", T("The widget's size (`size` gives both).", "El tamaño del widget (`size` da los dos).")),
    ("`button`", T("`\"left\"`, `\"right\"`, `\"middle\"`…", "`\"left\"`, `\"right\"`, `\"middle\"`…")),
    ("`key`", T("The key combo, such as `\"ctrl-s\"`.", "La combinación de teclas, como `\"ctrl-s\"`.")),
    ("`shift`, `ctrl`, `alt`, `logo`", T("Modifiers held.", "Modificadores pulsados.")),
    ("`value`, `source`", T("For a component's own events: the data and the component.",
                            "En los eventos propios de un componente: el dato y el componente.")),
]


# --------------------------------------------------------------------------------- examples

EXAMPLES: dict = {}


def ex(slug, imperative, declarative, functional):
    EXAMPLES[slug] = {"imperative": imperative, "declarative": declarative, "functional": functional}


# ---------------------------------------------------------------------------------- actions

ex("button", '''class Editor(pz.App):
    def __init__(self):
        self.saved = 0

    def save(self):                      # on_press: called with nothing
        self.saved += 1

    def view(self):
        return pz.row([
            ui.button("Save", self.save, icon="save", variant="solid", keys="ctrl-s"),
            ui.button("Reset", lambda: setattr(self, "saved", 0), variant="ghost"),
            ui.label(f"Saved {self.saved} times"),
        ], spacing=8, align="center")''', '''class Editor(pz.App):
    saved = 0

    def update(self, message):           # every button sends a message here
        match message:
            case "save":
                self.saved += 1
            case "reset":
                self.saved = 0

    def view(self):
        return pz.row([
            ui.button("Save", "save", icon="save", variant="solid", keys="ctrl-s"),
            ui.button("Reset", "reset", variant="ghost"),
            ui.label(f"Saved {self.saved} times"),
        ], spacing=8, align="center")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    saved: int = 0


def view(state, set_state):              # a pure function: state in, widgets out
    return pz.row([
        ui.button("Save", lambda: set_state(saved=state.saved + 1), icon="save", variant="solid"),
        ui.button("Reset", lambda: set_state(saved=0), variant="ghost"),
        ui.label(f"Saved {state.saved} times"),
    ], spacing=8, align="center")''')

ex("icon-button", '''class Toolbar(pz.App):
    def __init__(self):
        self.bold = False

    def toggle_bold(self):
        self.bold = not self.bold

    def view(self):
        return pz.row([
            ui.icon_button("bold", self.toggle_bold, selected=self.bold, tooltip="Bold", keys="ctrl-b"),
            ui.icon_button("trash-2", self.clear, tooltip="Clear", disabled=not self.bold),
        ], spacing=4)

    def clear(self):
        self.bold = False''', '''from dataclasses import dataclass


@dataclass
class ToggleBold:
    pass


class Toolbar(pz.App):
    bold = False

    def update(self, message):
        if isinstance(message, ToggleBold):
            self.bold = not self.bold

    def view(self):
        return ui.icon_button("bold", ToggleBold(), selected=self.bold, tooltip="Bold")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    bold: bool = False


def view(state, set_state):
    return ui.icon_button("bold", lambda: set_state(bold=not state.bold),
                          selected=state.bold, tooltip="Bold")''')

ex("split-button", '''class Runner(pz.App):
    def __init__(self):
        self.menu_open = False
        self.last = "nothing yet"

    def run(self, how="run"):
        self.last, self.menu_open = how, False

    def view(self):
        button = ui.split_button("Run", self.run,                     # on_press: the main action
                                 lambda: setattr(self, "menu_open", True),   # on_menu: the arrow
                                 icon="play")
        menu = ui.menu([ui.MenuItem("Debug", lambda: self.run("debug"), icon="bug")])
        return pz.column([
            ui.popover(button, menu if self.menu_open else None, y=32,
                       on_dismiss=lambda: setattr(self, "menu_open", False)),
            ui.label(f"Last: {self.last}"),
        ], spacing=8)''', '''from dataclasses import dataclass


@dataclass
class Run:
    how: str = "run"


class Runner(pz.App):
    menu_open = False
    last = "nothing yet"

    def update(self, message):
        match message:
            case Run(how):
                self.last, self.menu_open = how, False
            case "menu":
                self.menu_open = True
            case "dismiss":
                self.menu_open = False

    def view(self):
        menu = ui.menu([ui.MenuItem("Debug", Run("debug"), icon="bug")])
        return ui.popover(ui.split_button("Run", Run(), "menu", icon="play"),
                          menu if self.menu_open else None, y=32, on_dismiss="dismiss")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    menu_open: bool = False
    last: str = "nothing yet"


def view(state, set_state):
    run = lambda how: set_state(last=how, menu_open=False)
    menu = ui.menu([ui.MenuItem("Debug", lambda: run("debug"), icon="bug")])
    return ui.popover(
        ui.split_button("Run", lambda: run("run"), lambda: set_state(menu_open=True), icon="play"),
        menu if state.menu_open else None, y=32, on_dismiss=lambda: set_state(menu_open=False))''')

ex("toggle-group", '''class Toolbar(pz.App):
    def __init__(self):
        self.align = "left"

    def set_align(self, value):          # on_select gets the value of the pressed option
        self.align = value

    def view(self):
        return ui.toggle_group([("left", "align-left"), ("center", "align-center"), ("right", "align-right")],
                               self.align, self.set_align)''', '''from dataclasses import dataclass


@dataclass
class Align:
    value: str


class Toolbar(pz.App):
    align = "left"

    def update(self, message):
        match message:
            case Align(value):
                self.align = value

    def view(self):
        return ui.toggle_group([("left", "align-left"), ("center", "align-center")],
                               self.align, Align)   # the class builds the message from the value''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    align: str = "left"


def view(state, set_state):
    return ui.toggle_group([("left", "align-left"), ("center", "align-center"), ("right", "align-right")],
                           state.align, lambda value: set_state(align=value))''')

ex("chip", '''class Filters(pz.App):
    def __init__(self):
        self.tags = ["python", "rust", "iced"]
        self.active = "python"

    def view(self):
        return pz.row([
            ui.chip(t, selected=t == self.active,
                    on_press=lambda t=t: setattr(self, "active", t),     # pick it
                    on_remove=lambda t=t: self.tags.remove(t))           # its ✕
            for t in self.tags
        ], spacing=6, wrap=True)''', '''from dataclasses import dataclass


@dataclass
class Pick:
    tag: str


@dataclass
class Remove:
    tag: str


class Filters(pz.App):
    tags = ["python", "rust", "iced"]
    active = "python"

    def update(self, message):
        match message:
            case Pick(tag):
                self.active = tag
            case Remove(tag):
                self.tags = [t for t in self.tags if t != tag]

    def view(self):
        return pz.row([ui.chip(t, selected=t == self.active, on_press=Pick(t), on_remove=Remove(t))
                       for t in self.tags], spacing=6, wrap=True)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    tags: tuple = ("python", "rust", "iced")
    active: str = "python"


def view(state, set_state):
    return pz.row([
        ui.chip(t, selected=t == state.active,
                on_press=lambda t=t: set_state(active=t),
                on_remove=lambda t=t: set_state(tags=tuple(x for x in state.tags if x != t)))
        for t in state.tags
    ], spacing=6, wrap=True)''')

ex("badge", '''class Inbox(pz.App):
    def __init__(self):
        self.unread = 3

    def view(self):
        return ui.badge(f"{self.unread} new", tint="accent",
                        on_press=lambda: setattr(self, "unread", 0))   # on_press makes it clickable''', '''class Inbox(pz.App):
    unread = 3

    def update(self, message):
        if message == "read all":
            self.unread = 0

    def view(self):
        return ui.badge(f"{self.unread} new", on_press="read all")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    unread: int = 3


def view(state, set_state):
    return ui.badge(f"{state.unread} new", on_press=lambda: set_state(unread=0))''')

ex("card", '''class Plans(pz.App):
    def __init__(self):
        self.plan = "Pro"

    def view(self):
        return pz.row([
            ui.card(ui.muted(f"Plan {name}"), title=name, width=160, selected=name == self.plan,
                    on_press=lambda name=name: setattr(self, "plan", name))   # the whole card
            for name in ("Free", "Pro", "Team")
        ], spacing=8)''', '''from dataclasses import dataclass


@dataclass
class Choose:
    plan: str


class Plans(pz.App):
    plan = "Pro"

    def update(self, message):
        match message:
            case Choose(plan):
                self.plan = plan

    def view(self):
        return pz.row([ui.card(ui.muted(name), title=name, width=160, selected=name == self.plan,
                               on_press=Choose(name)) for name in ("Free", "Pro", "Team")], spacing=8)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    plan: str = "Pro"


def plan_card(name, selected, choose):        # a small function component
    return ui.card(ui.muted(name), title=name, width=160, selected=selected, on_press=choose)


def view(state, set_state):
    return pz.row([plan_card(n, n == state.plan, lambda n=n: set_state(plan=n))
                   for n in ("Free", "Pro", "Team")], spacing=8)''')

# ------------------------------------------------------------------------------------ forms

ex("input", '''class SignUp(pz.App):
    def __init__(self):
        self.email = ""
        self.sent = False

    def set_email(self, text):           # on_input: the new text on every keystroke
        self.email, self.sent = text, False

    def send(self):                      # on_submit: Enter
        self.sent = "@" in self.email

    def view(self):
        return pz.column([
            ui.input(self.email, self.set_email, placeholder="Email", icon="mail", id="email",
                     on_submit=self.send, on_clear=lambda: self.set_email(""),
                     invalid=bool(self.email) and "@" not in self.email),
            ui.label("Thanks!" if self.sent else "Press Enter to send"),
        ], spacing=8, width=320)

    def on_start(self):
        return pz.Command.focus("email")''', '''from dataclasses import dataclass


@dataclass
class Typed:
    text: str


class SignUp(pz.App):
    email = ""
    sent = False

    def update(self, message):
        match message:
            case Typed(text):
                self.email, self.sent = text, False
            case "send":
                self.sent = "@" in self.email
            case "clear":
                self.email = ""

    def view(self):
        return ui.input(self.email, Typed, placeholder="Email", icon="mail",
                        on_submit="send", on_clear="clear")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    email: str = ""
    sent: bool = False


def view(state, set_state):
    valid = "@" in state.email
    return pz.column([
        ui.input(state.email, lambda text: set_state(email=text, sent=False), placeholder="Email",
                 on_submit=lambda: set_state(sent=valid), invalid=bool(state.email) and not valid),
        ui.label("Thanks!" if state.sent else "Press Enter to send"),
    ], spacing=8, width=320)''')

ex("search-input", '''class Finder(pz.App):
    def __init__(self):
        self.query = ""
        self.files = ["main.py", "app.py", "theme.py"]

    def search(self, text):              # on_input: every keystroke
        self.query = text

    def view(self):
        matches = ui.fuzzy_filter(self.query, self.files)
        return pz.column([ui.search_input(self.query, self.search),
                          *[ui.list_item(name, icon="file") for name, _ in matches]], spacing=6)''', '''from dataclasses import dataclass


@dataclass
class Search:
    query: str


class Finder(pz.App):
    query = ""
    files = ["main.py", "app.py", "theme.py"]

    def update(self, message):
        match message:
            case Search(query):
                self.query = query

    def view(self):
        matches = ui.fuzzy_filter(self.query, self.files)
        return pz.column([ui.search_input(self.query, Search),
                          *[ui.list_item(name, icon="file") for name, _ in matches]], spacing=6)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    query: str = ""
    files: tuple = ("main.py", "app.py", "theme.py")


def view(state, set_state):
    matches = ui.fuzzy_filter(state.query, list(state.files))
    return pz.column([ui.search_input(state.query, lambda q: set_state(query=q)),
                      *[ui.list_item(name, icon="file") for name, _ in matches]], spacing=6)''')

ex("checkbox", '''class Settings(pz.App):
    def __init__(self):
        self.options = {"Format on save": True, "Show hidden files": False}

    def toggle(self, name, checked):     # on_toggle gets True or False
        self.options[name] = checked

    def view(self):
        return pz.column([
            ui.checkbox(on, lambda checked, name=name: self.toggle(name, checked), label=name)
            for name, on in self.options.items()
        ], spacing=10)''', '''from dataclasses import dataclass


@dataclass
class Toggle:
    name: str
    checked: bool


class Settings(pz.App):
    options = {"Format on save": True, "Show hidden files": False}

    def update(self, message):
        match message:
            case Toggle(name, checked):
                self.options = {**self.options, name: checked}

    def view(self):
        return pz.column([ui.checkbox(on, lambda c, n=name: Toggle(n, c), label=name)
                          for name, on in self.options.items()], spacing=10)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    format_on_save: bool = True
    hidden_files: bool = False


def view(state, set_state):
    return pz.column([
        ui.checkbox(state.format_on_save, lambda c: set_state(format_on_save=c), label="Format on save"),
        ui.checkbox(state.hidden_files, lambda c: set_state(hidden_files=c), label="Show hidden files"),
    ], spacing=10)''')

ex("switch", '''class Settings(pz.App):
    def __init__(self):
        self.autosave = True

    def set_autosave(self, on):          # on_toggle: the new state
        self.autosave = on

    def view(self):
        return pz.column([
            ui.switch(self.autosave, self.set_autosave, label="Autosave"),
            ui.label("Saving as you type" if self.autosave else "Save with Ctrl+S"),
        ], spacing=8)''', '''from dataclasses import dataclass


@dataclass
class SetAutosave:
    on: bool


class Settings(pz.App):
    autosave = True

    def update(self, message):
        match message:
            case SetAutosave(on):
                self.autosave = on

    def view(self):
        return ui.switch(self.autosave, SetAutosave, label="Autosave")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    autosave: bool = True


def view(state, set_state):
    return ui.switch(state.autosave, lambda on: set_state(autosave=on), label="Autosave")''')

ex("slider", '''class Player(pz.App):
    def __init__(self):
        self.volume = 70
        self.saved = 70

    def view(self):
        return pz.row([
            ui.slider(self.volume, lambda v: setattr(self, "volume", v),   # on_change: while dragging
                      min=0, max=100, step=1,
                      on_release=lambda: setattr(self, "saved", self.volume)),  # on_release: once
            ui.label(f"{self.volume:.0f}% (saved {self.saved:.0f}%)"),
        ], spacing=12, align="center", width=420)''', '''from dataclasses import dataclass


@dataclass
class Volume:
    value: float


class Player(pz.App):
    volume = 70
    saved = 70

    def update(self, message):
        match message:
            case Volume(value):
                self.volume = value
            case "save":
                self.saved = self.volume

    def view(self):
        return ui.slider(self.volume, Volume, min=0, max=100, step=1, on_release="save")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    volume: float = 70


def view(state, set_state):
    return pz.row([
        ui.slider(state.volume, lambda v: set_state(volume=v), min=0, max=100, step=1),
        ui.label(f"{state.volume:.0f}%"),
    ], spacing=12, align="center", width=420)''')

ex("number-field", '''class Settings(pz.App):
    def __init__(self):
        self.font_size = 14
        self.applied = 14

    def view(self):
        return pz.row([
            ui.number_field(self.font_size, lambda v: setattr(self, "font_size", v),   # on_change
                            min=8, max=32, suffix="px",
                            on_submit=lambda: setattr(self, "applied", self.font_size)),  # Enter
            pz.text("Preview", size=self.applied),
        ], spacing=12, align="center")''', '''from dataclasses import dataclass


@dataclass
class FontSize:
    value: float


class Settings(pz.App):
    font_size = 14

    def update(self, message):
        match message:
            case FontSize(value):
                self.font_size = value

    def view(self):
        return ui.number_field(self.font_size, FontSize, min=8, max=32, suffix="px")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    font_size: float = 14


def view(state, set_state):
    return pz.row([ui.number_field(state.font_size, lambda v: set_state(font_size=v), min=8, max=32),
                   pz.text("Preview", size=state.font_size)], spacing=12, align="center")''')

ex("select", '''class Settings(pz.App):
    def __init__(self):
        self.language = "Python"
        self.open = False

    def view(self):
        return pz.column([
            ui.select(["Python", "Rust", "TypeScript"], self.language,
                      lambda value: setattr(self, "language", value),       # on_select: the option
                      on_open=lambda: setattr(self, "open", True),
                      on_close=lambda: setattr(self, "open", False), width=180),
            ui.muted("Choosing…" if self.open else f"Language: {self.language}"),
        ], spacing=8)''', '''from dataclasses import dataclass


@dataclass
class Language:
    name: str


class Settings(pz.App):
    language = "Python"

    def update(self, message):
        match message:
            case Language(name):
                self.language = name

    def view(self):
        return ui.select(["Python", "Rust", "TypeScript"], self.language, Language, width=180)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    language: str = "Python"


def view(state, set_state):
    return ui.select(["Python", "Rust", "TypeScript"], state.language,
                     lambda value: set_state(language=value), width=180)''')

ex("radio-group", '''class Settings(pz.App):
    def __init__(self):
        self.indent = "spaces"

    def set_indent(self, value):         # on_select gets the value, not the label
        self.indent = value

    def view(self):
        return ui.radio_group([("spaces", "Spaces"), ("tabs", "Tabs")], self.indent, self.set_indent)''', '''from dataclasses import dataclass


@dataclass
class Indent:
    value: str


class Settings(pz.App):
    indent = "spaces"

    def update(self, message):
        match message:
            case Indent(value):
                self.indent = value

    def view(self):
        return ui.radio_group([("spaces", "Spaces"), ("tabs", "Tabs")], self.indent, Indent)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    indent: str = "spaces"


def view(state, set_state):
    return ui.radio_group([("spaces", "Spaces"), ("tabs", "Tabs")], state.indent,
                          lambda value: set_state(indent=value), horizontal=True)''')

ex("segmented", '''class Calendar(pz.App):
    def __init__(self):
        self.mode = "Week"

    def view(self):
        return pz.column([
            ui.segmented(["Day", "Week", "Month"], self.mode, lambda m: setattr(self, "mode", m)),
            ui.label(f"Showing a {self.mode.lower()}"),
        ], spacing=8, align="center")''', '''from dataclasses import dataclass


@dataclass
class Mode:
    name: str


class Calendar(pz.App):
    mode = "Week"

    def update(self, message):
        match message:
            case Mode(name):
                self.mode = name

    def view(self):
        return ui.segmented(["Day", "Week", "Month"], self.mode, Mode)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    mode: str = "Week"


def view(state, set_state):
    return ui.segmented(["Day", "Week", "Month"], state.mode, lambda m: set_state(mode=m))''')

ex("color-picker", '''class Styles(pz.App):
    def __init__(self):
        self.fill = "#3b82f6"

    def picked(self, event):             # a pz.Component: the color is event.value
        self.fill = event.value

    def view(self):
        return pz.row([
            ui.ColorPicker(value=self.fill, on_change=self.picked),
            pz.container(width=80, height=80, bg=self.fill, radius=8),
            ui.color_swatch("#ef4444", on_press=lambda: setattr(self, "fill", "#ef4444")),
        ], spacing=16)''', '''from dataclasses import dataclass


@dataclass
class Fill:
    color: str


class Styles(pz.App):
    fill = "#3b82f6"

    def update(self, message):
        match message:
            case Fill(color):
                self.fill = color

    def view(self):
        return pz.row([ui.ColorPicker(value=self.fill, on_change=lambda e: Fill(e.value)),
                       ui.color_swatch("#ef4444", on_press=Fill("#ef4444"))], spacing=16)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    fill: str = "#3b82f6"


def view(state, set_state):
    return pz.row([ui.ColorPicker(value=state.fill, on_change=lambda e: set_state(fill=e.value)),
                   pz.container(width=80, height=80, bg=state.fill, radius=8)], spacing=16)''')

ex("icon-picker", '''class Shortcut(pz.App):
    def __init__(self):
        self.icon = "rocket"
        self.picking = False

    def pick(self, name):                # on_pick: the icon's name ("" when cleared)
        self.icon, self.picking = name or "circle-dashed", False

    def view(self):
        page = ui.button("Change icon", lambda: setattr(self, "picking", True), icon=self.icon)
        dialog = ui.icon_picker_dialog(self.icon, self.pick, on_close=lambda: setattr(self, "picking", False))
        return ui.dialog_layer(page, dialog if self.picking else None,
                               on_dismiss=lambda: setattr(self, "picking", False))''', '''from dataclasses import dataclass


@dataclass
class Icon:
    name: str


class Shortcut(pz.App):
    icon = "rocket"

    def update(self, message):
        match message:
            case Icon(name):
                self.icon = name or "circle-dashed"

    def view(self):
        # IconPicker is a pz.Component: its handler gets a pz.Event
        return ui.IconPicker(value=self.icon, height=200, on_change=lambda e: Icon(e.value))''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    icon: str = "rocket"


def view(state, set_state):
    return pz.column([
        ui.icon_grid(["rocket", "star", "heart", "bell"], lambda name: set_state(icon=name),
                     selected=state.icon, columns=4, height=60),
        ui.button("Launch", None, icon=state.icon),
    ], spacing=8)''')

# --------------------------------------------------------------------------------- feedback

ex("callout", '''class Updates(pz.App):
    def __init__(self):
        self.visible = True

    def view(self):
        if not self.visible:
            return ui.muted("No news.")
        return ui.callout("A new version is out", "Pyzed adds the component designer.", tint="info",
                          on_dismiss=lambda: setattr(self, "visible", False))   # adds the ✕''', '''class Updates(pz.App):
    visible = True

    def update(self, message):
        if message == "dismiss":
            self.visible = False

    def view(self):
        return ui.callout("A new version is out", tint="info", on_dismiss="dismiss") if self.visible \\
            else ui.muted("No news.")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    visible: bool = True


def view(state, set_state):
    if not state.visible:
        return ui.muted("No news.")
    return ui.callout("A new version is out", tint="info", on_dismiss=lambda: set_state(visible=False))''')

ex("toast", '''class Notes(pz.App):
    def __init__(self):
        self.messages = ["Saved"]
        self.opened = 0

    def view(self):
        items = [ui.toast(m, kind="success",
                          on_dismiss=lambda m=m: self.messages.remove(m),           # its ✕
                          on_press=lambda: setattr(self, "opened", self.opened + 1))  # the card
                 for m in self.messages]
        return ui.toasts(main_view(), items)''', '''from dataclasses import dataclass


@dataclass
class Dismiss:
    text: str


class Notes(pz.App):
    messages = ["Saved"]

    def update(self, message):
        match message:
            case Dismiss(text):
                self.messages = [m for m in self.messages if m != text]

    def view(self):
        return ui.toasts(main_view(), [ui.toast(m, kind="success", on_dismiss=Dismiss(m))
                                       for m in self.messages])''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    messages: tuple = ("Saved",)


def view(state, set_state):
    close = lambda m: set_state(messages=tuple(x for x in state.messages if x != m))
    return ui.toasts(main_view(), [ui.toast(m, kind="success", on_dismiss=lambda m=m: close(m))
                                   for m in state.messages])''')

ex("error-boundary", '''class Report(pz.App):
    def __init__(self):
        self.values = []
        self.error = None                # the ui.ErrorInfo shown in the dialog

    def totals(self):
        return ui.label(f"Average: {sum(self.values) / len(self.values)}")   # raises on []

    def view(self):
        page = ui.error_boundary(self.totals, title="Totals",
                                 on_error=lambda info: print(info.message),         # every failure
                                 on_details=lambda info: setattr(self, "error", info))  # Details
        dialog = ui.error_dialog(self.error, lambda: setattr(self, "error", None)) if self.error else None
        return ui.dialog_layer(page, dialog)''', '''from dataclasses import dataclass


@dataclass
class ShowError:
    info: object


class Report(pz.App):
    error = None

    def totals(self):
        return ui.label(f"Average: {sum([]) / len([])}")

    def update(self, message):
        match message:
            case ShowError(info):
                self.error = info
            case "close":
                self.error = None

    def view(self):
        page = ui.error_boundary(self.totals, title="Totals", on_details=ShowError)
        return ui.dialog_layer(page, ui.error_dialog(self.error, "close") if self.error else None)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    values: tuple = ()
    failures: int = 0


def totals(values):
    return ui.label(f"Average: {sum(values) / len(values)}")


def view(state, set_state):
    return pz.column([
        ui.error_boundary(lambda: totals(state.values), title="Totals",
                          on_error=lambda info: set_state(failures=state.failures + 1)),
        ui.button("Add 10", lambda: set_state(values=state.values + (10,))),
    ], spacing=8, width=380)''')

# ------------------------------------------------------------------------------------- data

ex("table", '''class Files(pz.App):
    def __init__(self):
        self.rows = [{"name": "app.py", "lines": 512}, {"name": "theme.py", "lines": 730}]
        self.sort_by, self.descending = "Lines", True
        self.selected, self.opened = None, None

    def sort(self, title):               # on_sort: the clicked column title
        self.descending = not self.descending if self.sort_by == title else False
        self.sort_by = title

    def view(self):
        key = "name" if self.sort_by == "File" else "lines"
        rows = sorted(self.rows, key=lambda r: r[key], reverse=self.descending)
        return ui.table(
            [ui.Column("File", "name"), ui.Column("Lines", "lines", width=80, align="end")], rows,
            sort_by=self.sort_by, descending=self.descending, on_sort=self.sort, selected=self.selected,
            on_row_press=lambda row: setattr(self, "selected", row),         # click
            on_row_double_press=lambda row: setattr(self, "opened", row),    # double click
            on_row_context=lambda row: print("menu for", row["name"]),       # right click
        )''', '''from dataclasses import dataclass


@dataclass
class Sort:
    title: str


@dataclass
class Select:
    row: dict


class Files(pz.App):
    rows = [{"name": "app.py", "lines": 512}, {"name": "theme.py", "lines": 730}]
    sort_by, descending, selected = "Lines", True, None

    def update(self, message):
        match message:
            case Sort(title):
                self.descending = not self.descending if title == self.sort_by else False
                self.sort_by = title
            case Select(row):
                self.selected = row

    def view(self):
        return ui.table([ui.Column("File", "name"), ui.Column("Lines", "lines", width=80)], self.rows,
                        sort_by=self.sort_by, descending=self.descending, selected=self.selected,
                        on_sort=Sort, on_row_press=Select)''', '''from dataclasses import dataclass

ROWS = ({"name": "app.py", "lines": 512}, {"name": "theme.py", "lines": 730})


@dataclass(frozen=True)
class State:
    sort_by: str = "Lines"
    descending: bool = True
    selected: str = ""


def view(state, set_state):
    key = "name" if state.sort_by == "File" else "lines"
    rows = sorted(ROWS, key=lambda r: r[key], reverse=state.descending)
    return ui.table(
        [ui.Column("File", "name"), ui.Column("Lines", "lines", width=80)], rows,
        sort_by=state.sort_by, descending=state.descending,
        selected=next((r for r in rows if r["name"] == state.selected), None),
        on_sort=lambda t: set_state(sort_by=t, descending=not state.descending if t == state.sort_by else False),
        on_row_press=lambda row: set_state(selected=row["name"]))''')

ex("virtual-list", '''class Logs(pz.App):
    def __init__(self):
        self.lines = [f"[{i:06}] request handled" for i in range(100_000)]
        self.top = 0

    def scrolled(self, info):            # on_scroll: offsets and sizes of the viewport
        self.top = int(info["y"] // 20)

    def view(self):
        return pz.column([
            ui.label(f"Line {self.top + 1} of {len(self.lines)}"),
            ui.virtual_list(self.lines, lambda line: pz.text(line, font="mono", size=12),
                            item_height=20, height=200, on_scroll=self.scrolled),
        ], spacing=6)''', '''from dataclasses import dataclass


@dataclass
class Scrolled:
    info: dict


class Logs(pz.App):
    lines = [f"[{i:06}] request handled" for i in range(100_000)]
    top = 0

    def update(self, message):
        match message:
            case Scrolled(info):
                self.top = int(info["y"] // 20)

    def view(self):
        return ui.virtual_list(self.lines, lambda line: pz.text(line, size=12), item_height=20,
                               height=200, on_scroll=Scrolled)''', '''from dataclasses import dataclass

LINES = [f"[{i:06}] request handled" for i in range(100_000)]


@dataclass(frozen=True)
class State:
    top: int = 0


def view(state, set_state):
    return pz.column([
        ui.label(f"Line {state.top + 1}"),
        ui.virtual_list(LINES, lambda line: pz.text(line, size=12), item_height=20, height=200,
                        on_scroll=lambda info: set_state(top=int(info["y"] // 20))),
    ], spacing=6)''')

ex("stat", '''class Dashboard(pz.App):
    def __init__(self):
        self.detail = None

    def view(self):
        return pz.column([
            pz.row([ui.stat("Users", "1,284", delta=12.5, width=200,
                            on_press=lambda: setattr(self, "detail", "Users")),   # the whole card
                    ui.stat("Errors", "37", delta=-8.0, width=200,
                            on_press=lambda: setattr(self, "detail", "Errors"))], spacing=12),
            ui.muted(f"Details of {self.detail}" if self.detail else "Click a number"),
        ], spacing=8)''', '''from dataclasses import dataclass


@dataclass
class Open:
    metric: str


class Dashboard(pz.App):
    detail = None

    def update(self, message):
        match message:
            case Open(metric):
                self.detail = metric

    def view(self):
        return pz.row([ui.stat(m, v, width=200, on_press=Open(m))
                       for m, v in (("Users", "1,284"), ("Errors", "37"))], spacing=12)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    detail: str = ""


def view(state, set_state):
    return pz.row([ui.stat(m, v, width=200, on_press=lambda m=m: set_state(detail=m))
                   for m, v in (("Users", "1,284"), ("Errors", "37"))], spacing=12)''')

# ------------------------------------------------------------------------------------ lists

ex("list-item", '''class Recent(pz.App):
    def __init__(self):
        self.files = ["main.py", "app.py", "README.md"]
        self.current = "main.py"
        self.opened = None

    def view(self):
        return pz.column([
            ui.list_item(f, lambda f=f: setattr(self, "current", f), icon="file",   # on_press
                         selected=f == self.current, inset=True,
                         on_double_press=lambda f=f: setattr(self, "opened", f),
                         on_right_press=lambda f=f: print("menu for", f))
            for f in self.files
        ], width=280)''', '''from dataclasses import dataclass


@dataclass
class Select:
    path: str


@dataclass
class Open:
    path: str


class Recent(pz.App):
    files = ["main.py", "app.py", "README.md"]
    current, opened = "main.py", None

    def update(self, message):
        match message:
            case Select(path):
                self.current = path
            case Open(path):
                self.opened = path

    def view(self):
        return pz.column([ui.list_item(f, Select(f), icon="file", selected=f == self.current,
                                       on_double_press=Open(f)) for f in self.files], width=280)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    files: tuple = ("main.py", "app.py", "README.md")
    current: str = "main.py"


def file_row(name, selected, select):
    return ui.list_item(name, select, icon="file", selected=selected, inset=True)


def view(state, set_state):
    return pz.column([file_row(f, f == state.current, lambda f=f: set_state(current=f))
                      for f in state.files], width=280)''')

ex("tree", '''class Explorer(pz.App):
    def __init__(self):
        self.nodes = ui.TreeNode.from_paths(["src/main.rs", "src/app.rs", "Cargo.toml"])
        self.expanded = {"src"}
        self.selected = None

    def toggle(self, folder):            # on_toggle: the folder's id (its path)
        self.expanded ^= {folder}

    def view(self):
        return ui.tree(self.nodes, expanded=self.expanded, selected=self.selected,
                       on_toggle=self.toggle,
                       on_select=lambda path: setattr(self, "selected", path),   # click on a file
                       on_open=lambda path: print("open", path),                 # double click
                       on_context=lambda path: print("menu for", path))          # right click''', '''from dataclasses import dataclass


@dataclass
class Toggle:
    folder: str


@dataclass
class Select:
    path: str


class Explorer(pz.App):
    nodes = ui.TreeNode.from_paths(["src/main.rs", "src/app.rs", "Cargo.toml"])
    expanded = frozenset({"src"})
    selected = None

    def update(self, message):
        match message:
            case Toggle(folder):
                self.expanded = self.expanded ^ {folder}
            case Select(path):
                self.selected = path

    def view(self):
        return ui.tree(self.nodes, expanded=self.expanded, selected=self.selected,
                       on_toggle=Toggle, on_select=Select)''', '''from dataclasses import dataclass

NODES = ui.TreeNode.from_paths(["src/main.rs", "src/app.rs", "Cargo.toml"])


@dataclass(frozen=True)
class State:
    expanded: frozenset = frozenset({"src"})
    selected: str = ""


def view(state, set_state):
    return ui.tree(NODES, expanded=state.expanded, selected=state.selected,
                   on_toggle=lambda folder: set_state(expanded=state.expanded ^ {folder}),
                   on_select=lambda path: set_state(selected=path))''')

ex("menu", '''class Files(pz.App):
    def __init__(self):
        self.wrap = True
        self.log = []

    def view(self):
        return ui.menu([
            ui.MenuItem("New file", lambda: self.log.append("new"), icon="file-plus", keys="ctrl-n"),
            ui.MenuItem("Soft wrap", lambda: setattr(self, "wrap", not self.wrap), checked=self.wrap),
            ui.SEPARATOR,
            ui.MenuItem("Delete", lambda: self.log.append("delete"), icon="trash-2", danger=True),
        ])''', '''class Files(pz.App):
    wrap = True

    def update(self, message):           # each item's on_press is a message
        match message:
            case "new":
                print("new file")
            case "wrap":
                self.wrap = not self.wrap

    def view(self):
        return ui.menu([ui.MenuItem("New file", "new", icon="file-plus", keys="ctrl-n"),
                        ui.MenuItem("Soft wrap", "wrap", checked=self.wrap)])''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    wrap: bool = True


def view(state, set_state):
    return ui.menu([
        ui.MenuItem("Soft wrap", lambda: set_state(wrap=not state.wrap), checked=state.wrap),
        ui.MenuItem("Delete", None, icon="trash-2", danger=True, disabled=True),
    ])''')

ex("accordion", '''class Settings(pz.App):
    def __init__(self):
        self.open = {"editor"}

    def toggle(self, key):               # on_toggle: the key of the clicked header
        self.open ^= {key}

    def view(self):
        return ui.accordion([("editor", "Editor", ui.muted("Font, tabs, wrapping")),
                             ("files", "Files", ui.muted("Autosave, encoding"))],
                            open=self.open, on_toggle=self.toggle)''', '''from dataclasses import dataclass


@dataclass
class Toggle:
    key: str


class Settings(pz.App):
    open = frozenset({"editor"})

    def update(self, message):
        match message:
            case Toggle(key):
                self.open = self.open ^ {key}

    def view(self):
        return ui.accordion([("editor", "Editor", ui.muted("…")), ("files", "Files", ui.muted("…"))],
                            open=self.open, on_toggle=Toggle)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    open: frozenset = frozenset({"editor"})


def view(state, set_state):
    return ui.accordion([("editor", "Editor", ui.muted("…")), ("files", "Files", ui.muted("…"))],
                        open=state.open, on_toggle=lambda key: set_state(open=state.open ^ {key}))''')

ex("disclosure", '''class Form(pz.App):
    def __init__(self):
        self.advanced = False

    def view(self):
        return ui.disclosure("Advanced options", ui.muted("Proxy, timeouts…"), open=self.advanced,
                             on_toggle=lambda: setattr(self, "advanced", not self.advanced))  # no argument''', '''class Form(pz.App):
    advanced = False

    def update(self, message):
        if message == "toggle advanced":
            self.advanced = not self.advanced

    def view(self):
        return ui.disclosure("Advanced options", ui.muted("…"), open=self.advanced,
                             on_toggle="toggle advanced")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    advanced: bool = False


def view(state, set_state):
    return ui.disclosure("Advanced options", ui.muted("…"), open=state.advanced,
                         on_toggle=lambda: set_state(advanced=not state.advanced))''')

# ------------------------------------------------------------------------------- navigation

ex("tab-bar", '''class Editor(pz.App):
    def __init__(self):
        self.open, self.active = ["main.py", "app.py"], "main.py"
        self.untitled = 0

    def close(self, path):               # on_close: the id of the tab
        i = self.open.index(path)
        self.open.remove(path)
        if self.active == path:
            self.active = self.open[min(i, len(self.open) - 1)] if self.open else None

    def new(self):                       # on_new: double click after the tabs
        self.untitled += 1
        self.open.append(f"untitled-{self.untitled}")
        self.active = self.open[-1]

    def view(self):
        return ui.tab_bar([ui.Tab.for_file(p) for p in self.open], self.active,
                          on_select=lambda p: setattr(self, "active", p), on_close=self.close,
                          on_new=self.new, on_context=lambda p: print("menu for", p))''', '''from dataclasses import dataclass


@dataclass
class Activate:
    path: str


@dataclass
class Close:
    path: str


class Editor(pz.App):
    open, active = ["main.py", "app.py"], "main.py"

    def update(self, message):
        match message:
            case Activate(path):
                self.active = path
            case Close(path):
                self.open = [p for p in self.open if p != path]
                self.active = self.open[0] if self.open else None

    def view(self):
        return ui.tab_bar([ui.Tab.for_file(p) for p in self.open], self.active,
                          on_select=Activate, on_close=Close)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    open: tuple = ("main.py", "app.py")
    active: str = "main.py"


def view(state, set_state):
    def close(path):
        rest = tuple(p for p in state.open if p != path)
        set_state(open=rest, active=state.active if state.active != path else (rest[0] if rest else ""))
    return ui.tab_bar([ui.Tab.for_file(p) for p in state.open], state.active,
                      on_select=lambda p: set_state(active=p), on_close=close)''')

ex("breadcrumbs", '''class Browser(pz.App):
    def __init__(self):
        self.path = ["home", "ada", "projects", "pyzed"]

    def go(self, index):                 # on_press: the index of the clicked part
        self.path = self.path[:index + 1]

    def view(self):
        return ui.breadcrumbs(self.path, on_press=self.go, max_items=3,
                              on_more=lambda: self.go(0))   # the … of the hidden parts''', '''from dataclasses import dataclass


@dataclass
class GoTo:
    index: int


class Browser(pz.App):
    path = ["home", "ada", "projects", "pyzed"]

    def update(self, message):
        match message:
            case GoTo(index):
                self.path = self.path[:index + 1]

    def view(self):
        return ui.breadcrumbs(self.path, on_press=GoTo)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    path: tuple = ("home", "ada", "projects", "pyzed")


def view(state, set_state):
    return ui.breadcrumbs(list(state.path), on_press=lambda i: set_state(path=state.path[:i + 1]))''')

# --------------------------------------------------------------------------------- overlays

ex("layer", '''class App(pz.App):
    def __init__(self):
        self.finder_open = True

    def view(self):
        finder = ui.card(ui.muted("Search files…"), width=320)
        return ui.layer(main_view(), finder if self.finder_open else None,
                        on_dismiss=lambda: setattr(self, "finder_open", False))   # click outside''', '''class App(pz.App):
    finder_open = True

    def update(self, message):
        match message:
            case "open finder":
                self.finder_open = True
            case "close finder":
                self.finder_open = False

    def view(self):
        overlay = ui.card(ui.muted("Search files…"), width=320) if self.finder_open else None
        return ui.layer(main_view(), overlay, on_dismiss="close finder")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    finder_open: bool = True


def view(state, set_state):
    overlay = ui.card(ui.muted("Search files…"), width=320) if state.finder_open else None
    return ui.layer(main_view(), overlay, on_dismiss=lambda: set_state(finder_open=False))''')

ex("modal", '''class Notes(pz.App):
    def __init__(self):
        self.asking = True

    def save(self):
        self.asking = False

    def view(self):
        dialog = ui.modal(ui.muted("Save your changes before closing?"), title="Save changes?",
                          on_close=lambda: setattr(self, "asking", False),   # ✕ and Escape
                          footer=[ui.button("Save", self.save, variant="solid")], width=420)
        return ui.dialog_layer(main_view(), dialog if self.asking else None)''', '''class Notes(pz.App):
    asking = True

    def update(self, message):
        if message in ("save", "close"):
            self.asking = False

    def view(self):
        dialog = ui.modal(ui.muted("Save your changes?"), title="Save changes?", on_close="close",
                          footer=[ui.button("Save", "save", variant="solid")])
        return ui.dialog_layer(main_view(), dialog if self.asking else None)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    asking: bool = True


def view(state, set_state):
    close = lambda: set_state(asking=False)
    dialog = ui.modal(ui.muted("Save your changes?"), title="Save changes?", on_close=close,
                      footer=[ui.button("Save", close, variant="solid")])
    return ui.dialog_layer(main_view(), dialog if state.asking else None)''')

ex("popover", '''class Canvas(pz.App):
    def __init__(self):
        self.pointer, self.menu_at = (0, 0), None

    def view(self):
        base = pz.mouse_area(main_view(), on_move=lambda x, y: setattr(self, "pointer", (x, y)),
                             on_right_press=lambda: setattr(self, "menu_at", self.pointer))
        menu = ui.menu([ui.MenuItem("Copy", lambda: setattr(self, "menu_at", None))])
        x, y = self.menu_at or (0, 0)
        return ui.popover(base, menu if self.menu_at else None, x=x, y=y,
                          on_dismiss=lambda: setattr(self, "menu_at", None))   # click outside''', '''from dataclasses import dataclass


@dataclass
class MenuAt:
    x: float
    y: float


class Canvas(pz.App):
    menu_at = None

    def update(self, message):
        match message:
            case MenuAt(x, y):
                self.menu_at = (x, y)
            case "close":
                self.menu_at = None

    def view(self):
        base = pz.canvas([], width=400, height=200, on_right_press=MenuAt)
        x, y = self.menu_at or (0, 0)
        return ui.popover(base, ui.menu([ui.MenuItem("Copy", "close")]) if self.menu_at else None,
                          x=x, y=y, on_dismiss="close")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    menu_at: tuple = ()


def view(state, set_state):
    base = pz.canvas([], width=400, height=200, on_right_press=lambda x, y: set_state(menu_at=(x, y)))
    menu = ui.menu([ui.MenuItem("Copy", lambda: set_state(menu_at=()))]) if state.menu_at else None
    x, y = state.menu_at or (0, 0)
    return ui.popover(base, menu, x=x, y=y, on_dismiss=lambda: set_state(menu_at=()))''')

ex("command-palette", '''class App(pz.App):
    def __init__(self):
        self.open, self.query, self.wrap = True, "", False

    def toggle_wrap(self):
        self.wrap, self.open = not self.wrap, False

    def commands(self):                  # each item's on_press runs the command
        return [ui.PaletteItem("editor: toggle soft wrap", self.toggle_wrap, keys="alt-z")]

    def run_first(self):                 # on_submit: Enter runs the first match
        matches = ui.fuzzy_filter(self.query, self.commands(), key=lambda c: c.label)
        return matches[0][0].on_press() if matches else None

    def view(self):
        palette = ui.command_palette(self.query, lambda q: setattr(self, "query", q),   # on_query
                                     self.commands(), on_submit=self.run_first)
        return ui.layer(main_view(), palette if self.open else None,
                        on_dismiss=lambda: setattr(self, "open", False))''', '''from dataclasses import dataclass


@dataclass
class Query:
    text: str


class App(pz.App):
    open, query, wrap = True, "", False

    def update(self, message):
        match message:
            case Query(text):
                self.query = text
            case "toggle wrap" | "submit":
                self.wrap, self.open = not self.wrap, False

    def view(self):
        palette = ui.command_palette(self.query, Query,
                                     [ui.PaletteItem("editor: toggle soft wrap", "toggle wrap")],
                                     on_submit="submit")
        return ui.layer(main_view(), palette if self.open else None)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    query: str = ""
    wrap: bool = False


def view(state, set_state):
    items = [ui.PaletteItem("editor: toggle soft wrap", lambda: set_state(wrap=not state.wrap))]
    return ui.command_palette(state.query, lambda q: set_state(query=q), items,
                              on_submit=lambda: set_state(wrap=not state.wrap))''')

ex("picker", '''class Finder(pz.App):
    def __init__(self):
        self.query, self.opened = "", None
        self.files = ["src/app.rs", "src/render.rs", "README.md"]

    def matches(self):
        return ui.fuzzy_filter(self.query, self.files)

    def open_first(self):                # on_submit: Enter
        found = self.matches()
        self.opened = found[0][0] if found else None

    def view(self):
        items = [(ui.PaletteItem(f, lambda f=f: setattr(self, "opened", f), icon="file"), positions)
                 for f, positions in self.matches()]
        return ui.picker(self.query, lambda q: setattr(self, "query", q), items,   # on_query
                         on_submit=self.open_first, placeholder="Search files…")''', '''from dataclasses import dataclass


@dataclass
class Query:
    text: str


@dataclass
class Open:
    path: str


class Finder(pz.App):
    query, opened = "", None
    files = ["src/app.rs", "src/render.rs", "README.md"]

    def update(self, message):
        match message:
            case Query(text):
                self.query = text
            case Open(path):
                self.opened = path

    def view(self):
        items = [(ui.PaletteItem(f, Open(f), icon="file"), p) for f, p in ui.fuzzy_filter(self.query, self.files)]
        return ui.picker(self.query, Query, items, placeholder="Search files…")''', '''from dataclasses import dataclass

FILES = ["src/app.rs", "src/render.rs", "README.md"]


@dataclass(frozen=True)
class State:
    query: str = ""
    opened: str = ""


def view(state, set_state):
    items = [(ui.PaletteItem(f, lambda f=f: set_state(opened=f), icon="file"), p)
             for f, p in ui.fuzzy_filter(state.query, FILES)]
    return ui.picker(state.query, lambda q: set_state(query=q), items, placeholder="Search files…")''')

# ---------------------------------------------------------------------------------- dialogs

ex("dialog-layer", '''class Files(pz.App):
    def __init__(self):
        self.asking = True

    def close(self):
        self.asking = False

    def view(self):
        dialog = ui.confirm("Delete main.py?", self.close, self.close, danger=True) if self.asking else None
        return ui.dialog_layer(main_view(), dialog, on_dismiss=self.close)   # click on the backdrop''', '''class Files(pz.App):
    asking = True

    def update(self, message):
        if message in ("delete", "cancel"):
            self.asking = False

    def view(self):
        dialog = ui.confirm("Delete main.py?", "delete", "cancel", danger=True) if self.asking else None
        return ui.dialog_layer(main_view(), dialog, on_dismiss="cancel")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    asking: bool = True


def view(state, set_state):
    close = lambda: set_state(asking=False)
    dialog = ui.confirm("Delete main.py?", close, close, danger=True) if state.asking else None
    return ui.dialog_layer(main_view(), dialog, on_dismiss=close)''')

ex("alert", '''class Export(pz.App):
    def __init__(self):
        self.done = True

    def view(self):
        alert = ui.alert("128 files were written.", lambda: setattr(self, "done", False),   # on_close
                         title="Export", kind="success")
        return ui.dialog_layer(main_view(), alert if self.done else None)''', '''class Export(pz.App):
    done = True

    def update(self, message):
        if message == "ok":
            self.done = False

    def view(self):
        return ui.dialog_layer(main_view(), ui.alert("128 files were written.", "ok", title="Export")
                               if self.done else None)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    done: bool = True


def view(state, set_state):
    alert = ui.alert("128 files were written.", lambda: set_state(done=False), title="Export")
    return ui.dialog_layer(main_view(), alert if state.done else None)''')

ex("confirm", '''class Files(pz.App):
    def __init__(self):
        self.files = ["notes.py", "todo.txt"]
        self.deleting = "notes.py"       # the file waiting for an answer

    def delete(self):                    # on_confirm
        self.files.remove(self.deleting)
        self.deleting = None

    def view(self):
        dialog = None
        if self.deleting:
            dialog = ui.confirm(f"Delete {self.deleting}?", self.delete,
                                lambda: setattr(self, "deleting", None),   # on_cancel
                                title="Delete file", danger=True, confirm_label="Delete")
        return ui.dialog_layer(main_view(), dialog)''', '''from dataclasses import dataclass


@dataclass
class Delete:
    name: str


class Files(pz.App):
    files = ["notes.py", "todo.txt"]
    deleting = "notes.py"

    def update(self, message):
        match message:
            case Delete(name):
                self.files = [f for f in self.files if f != name]
                self.deleting = None
            case "cancel":
                self.deleting = None

    def view(self):
        dialog = ui.confirm(f"Delete {self.deleting}?", Delete(self.deleting), "cancel", danger=True) \\
            if self.deleting else None
        return ui.dialog_layer(main_view(), dialog)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    files: tuple = ("notes.py", "todo.txt")
    deleting: str = "notes.py"


def view(state, set_state):
    if not state.deleting:
        return main_view()
    keep = tuple(f for f in state.files if f != state.deleting)
    return ui.dialog_layer(main_view(), ui.confirm(
        f"Delete {state.deleting}?", lambda: set_state(files=keep, deleting=""),
        lambda: set_state(deleting=""), danger=True))''')

ex("prompt", '''class Files(pz.App):
    def __init__(self):
        self.name = "notes.py"
        self.new_name = "notes.py"       # None while the dialog is closed

    def rename(self):                    # on_submit: Enter or the button
        self.name, self.new_name = self.new_name, None

    def view(self):
        dialog = None
        if self.new_name is not None:
            dialog = ui.prompt("Rename", self.new_name,
                               lambda text: setattr(self, "new_name", text),     # on_input
                               self.rename,
                               lambda: setattr(self, "new_name", None),          # on_cancel
                               message="New name for the file:")
        return ui.dialog_layer(main_view(), dialog)''', '''from dataclasses import dataclass


@dataclass
class Typed:
    text: str


class Files(pz.App):
    name, new_name = "notes.py", "notes.py"

    def update(self, message):
        match message:
            case Typed(text):
                self.new_name = text
            case "rename":
                self.name, self.new_name = self.new_name, None
            case "cancel":
                self.new_name = None

    def view(self):
        dialog = ui.prompt("Rename", self.new_name, Typed, "rename", "cancel") \\
            if self.new_name is not None else None
        return ui.dialog_layer(main_view(), dialog)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    name: str = "notes.py"
    draft: str = "notes.py"
    renaming: bool = True


def view(state, set_state):
    if not state.renaming:
        return ui.label(state.name)
    return ui.dialog_layer(main_view(), ui.prompt(
        "Rename", state.draft, lambda text: set_state(draft=text),
        lambda: set_state(name=state.draft, renaming=False), lambda: set_state(renaming=False)))''')

ex("choice", '''class Copy(pz.App):
    def __init__(self):
        self.asking, self.answer = True, None

    def answer_with(self, what):
        self.asking, self.answer = False, what

    def view(self):
        dialog = ui.choice("notes.py already exists in this folder.",
                           [("Keep both", lambda: self.answer_with("both")),   # one handler per option
                            ("Replace", lambda: self.answer_with("replace"))],
                           lambda: setattr(self, "asking", False),             # on_cancel: the ✕
                           title="File exists")
        return ui.dialog_layer(main_view(), dialog if self.asking else None)''', '''from dataclasses import dataclass


@dataclass
class Answer:
    what: str


class Copy(pz.App):
    asking = True

    def update(self, message):
        match message:
            case Answer(what):
                self.asking = False
                print("chose", what)
            case "cancel":
                self.asking = False

    def view(self):
        dialog = ui.choice("notes.py already exists.", [("Keep both", Answer("both")),
                                                        ("Replace", Answer("replace"))], "cancel")
        return ui.dialog_layer(main_view(), dialog if self.asking else None)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    answer: str = ""


def view(state, set_state):
    if state.answer:
        return ui.label(f"You chose: {state.answer}")
    return ui.dialog_layer(main_view(), ui.choice(
        "notes.py already exists.",
        [(label, lambda a=answer: set_state(answer=a)) for label, answer in (("Keep both", "both"),
                                                                            ("Replace", "replace"))],
        lambda: set_state(answer="cancel")))''')

ex("unsaved-changes", '''class Notes(pz.App):
    def __init__(self):
        self.closing = True

    def save(self):
        self.closing = False             # write the file, then close

    def view(self):
        dialog = ui.unsaved_changes("notes.py", self.save,
                                    lambda: setattr(self, "closing", False),   # on_discard
                                    lambda: setattr(self, "closing", False))   # on_cancel
        return ui.dialog_layer(main_view(), dialog if self.closing else None)''', '''class Notes(pz.App):
    closing = True

    def update(self, message):
        match message:
            case "save" | "discard":
                self.closing = False
            case "cancel":
                self.closing = False

    def view(self):
        dialog = ui.unsaved_changes("notes.py", "save", "discard", "cancel")
        return ui.dialog_layer(main_view(), dialog if self.closing else None)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    closing: bool = True
    saved: bool = False


def view(state, set_state):
    dialog = ui.unsaved_changes("notes.py", lambda: set_state(saved=True, closing=False),
                                lambda: set_state(closing=False), lambda: set_state(closing=False))
    return ui.dialog_layer(main_view(), dialog if state.closing else None)''')

ex("error-dialog", '''class Notes(pz.App):
    def __init__(self):
        try:
            open("/no/such/file")
        except OSError as err:
            self.error = ui.ErrorInfo.from_exception(err, where="Open")

    def close(self):                     # on_close: the button and Escape
        self.error = None

    def view(self):
        dialog = ui.error_dialog(self.error, self.close,
                                 on_go_to=lambda: print("go to", self.error.origin),  # adds Go to
                                 on_logs=lambda: print("show logs")) if self.error else None
        return ui.dialog_layer(main_view(), dialog, on_dismiss=self.close)''', '''class Notes(pz.App):
    error = ui.ErrorInfo("FileNotFoundError", "No such file: notes.txt")

    def update(self, message):
        match message:
            case "close":
                self.error = None
            case "logs":
                print("show logs")

    def view(self):
        dialog = ui.error_dialog(self.error, "close", on_logs="logs") if self.error else None
        return ui.dialog_layer(main_view(), dialog, on_dismiss="close")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    error: object = ui.ErrorInfo("FileNotFoundError", "No such file: notes.txt")


def view(state, set_state):
    close = lambda: set_state(error=None)
    dialog = ui.error_dialog(state.error, close) if state.error else None
    return ui.dialog_layer(main_view(), dialog, on_dismiss=close)''')

# -------------------------------------------------------------------------------- workspace

ex("workspace", '''class Ide(pz.App):
    def __init__(self):
        self.left_width, self.bottom_height = 220, 160

    def resized(self, side, size):       # on_resize: which dock and its new size
        if side == "left":
            self.left_width = size
        elif side == "bottom":
            self.bottom_height = size

    def view(self):
        return ui.workspace(main_view(), left=ui.panel_header("Project"), bottom=ui.panel_header("Terminal"),
                            left_width=self.left_width, bottom_height=self.bottom_height,
                            on_resize=self.resized)''', '''from dataclasses import dataclass


@dataclass
class Resized:
    side: str
    size: float


class Ide(pz.App):
    sizes = {"left": 220, "bottom": 160}

    def update(self, message):
        match message:
            case Resized(side, size):
                self.sizes = {**self.sizes, side: size}

    def view(self):
        return ui.workspace(main_view(), left=ui.panel_header("Project"), bottom=ui.panel_header("Terminal"),
                            left_width=self.sizes["left"], bottom_height=self.sizes["bottom"],
                            on_resize=Resized)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    left: float = 220
    bottom: float = 160


def view(state, set_state):
    return ui.workspace(main_view(), left=ui.panel_header("Project"), bottom=ui.panel_header("Terminal"),
                        left_width=state.left, bottom_height=state.bottom,
                        on_resize=lambda side, size: set_state(**{side: size}))''')

ex("title-bar", '''class Ide(pz.App):
    def __init__(self):
        self.picking = None

    def view(self):
        return ui.title_bar([
            ui.title_button("pyzed", lambda: setattr(self, "picking", "project"), chevron=True),
            ui.title_button("main", lambda: setattr(self, "picking", "branch"), icon="git-branch", muted=True),
        ], center=ui.muted(f"Pick a {self.picking}" if self.picking else "notes.py"))''', '''from dataclasses import dataclass


@dataclass
class Pick:
    what: str


class Ide(pz.App):
    picking = None

    def update(self, message):
        match message:
            case Pick(what):
                self.picking = what

    def view(self):
        return ui.title_bar([ui.title_button("pyzed", Pick("project"), chevron=True),
                             ui.title_button("main", Pick("branch"), icon="git-branch", muted=True)])''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    project: str = "pyzed"
    projects: tuple = ("pyzed", "notes")


def view(state, set_state):
    nxt = state.projects[(state.projects.index(state.project) + 1) % len(state.projects)]
    return ui.title_bar([ui.title_button(state.project, lambda: set_state(project=nxt), chevron=True)])''')

ex("window-frame", '''class Notes(pz.App):
    frame = "custom"                     # Pyzed draws the title bar

    def view(self):
        bar = ui.window_title_bar(
            "notes.py",
            on_drag=lambda: self.drag(),                 # the empty part of the bar
            on_minimize=lambda: self.minimize(),
            on_maximize=lambda: self.toggle_maximize(),  # also a double click on the bar
            on_close=lambda: self.close(),
            on_menu=lambda: print("window menu"),        # right click on the bar
            maximized=self.window_maximized,
        )
        return pz.column([bar, main_view()])''', '''class Notes(pz.App):
    frame = "custom"

    def update(self, message):           # the commands are returned from update
        match message:
            case "drag":
                return self.drag()
            case "minimize":
                return self.minimize()
            case "maximize":
                return self.toggle_maximize()
            case "close":
                return self.close()

    def view(self):
        return pz.column([ui.window_title_bar("notes.py", on_drag="drag", on_minimize="minimize",
                                              on_maximize="maximize", on_close="close"), main_view()])''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    title: str = "notes.py"


def view(state, set_state):
    # A handler can return a command: Pyzed runs it.
    return pz.column([ui.window_title_bar(state.title, on_drag=lambda: pz.Command.drag_window(),
                                          on_close=lambda: pz.Command.exit()), main_view()])''')

ex("status-bar", '''class Ide(pz.App):
    def __init__(self):
        self.show_left = True

    def view(self):
        return ui.status_bar(
            [ui.status_item(icon="panel-left", selected=self.show_left, tooltip="Project panel",
                            on_press=lambda: setattr(self, "show_left", not self.show_left))],
            [ui.status_item("Python", icon="file-code")],
        )''', '''class Ide(pz.App):
    show_left = True

    def update(self, message):
        if message == "toggle left":
            self.show_left = not self.show_left

    def view(self):
        return ui.status_bar([ui.status_item(icon="panel-left", on_press="toggle left",
                                             selected=self.show_left)])''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    show_left: bool = True


def view(state, set_state):
    return ui.status_bar([ui.status_item(icon="panel-left", selected=state.show_left,
                                         on_press=lambda: set_state(show_left=not state.show_left))])''')

ex("panel", '''class Mail(pz.App):
    def __init__(self):
        self.width = 220

    def view(self):
        return pz.row([
            ui.panel(ui.muted("Inbox"), header=ui.panel_header("Mail"), width=self.width,
                     on_resize=lambda size: setattr(self, "width", size)),   # when the drag ends
            main_view(),
        ], height="fill")''', '''from dataclasses import dataclass


@dataclass
class Width:
    size: float


class Mail(pz.App):
    width = 220

    def update(self, message):
        match message:
            case Width(size):
                self.width = size

    def view(self):
        return pz.row([ui.panel(ui.muted("Inbox"), width=self.width, on_resize=Width), main_view()],
                      height="fill")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    width: float = 220


def view(state, set_state):
    return pz.row([ui.panel(ui.muted("Inbox"), width=state.width, on_resize=lambda s: set_state(width=s)),
                   main_view()], height="fill")''')

ex("split", '''class Panes(pz.App):
    def __init__(self):
        self.ratio = 0.3

    def view(self):
        return ui.split(ui.muted(f"Sidebar ({self.ratio:.0%})"), main_view(), ratio=self.ratio,
                        on_resize=lambda r: setattr(self, "ratio", r))   # the share of the first pane''', '''from dataclasses import dataclass


@dataclass
class Ratio:
    value: float


class Panes(pz.App):
    ratio = 0.3

    def update(self, message):
        match message:
            case Ratio(value):
                self.ratio = value

    def view(self):
        return ui.split(ui.muted("Sidebar"), main_view(), ratio=self.ratio, on_resize=Ratio)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    ratio: float = 0.3


def view(state, set_state):
    return ui.split(ui.muted("Sidebar"), main_view(), ratio=state.ratio,
                    on_resize=lambda r: set_state(ratio=r))''')

# ------------------------------------------------------------------------------------- code

ex("editor", '''class Editor(pz.App):
    def __init__(self):
        self.text = "print('hello')\\n"
        self.cursor = (1, 1)
        self.font_size = 14

    def zoom(self, step):                # on_zoom: 1, -1 or 0 (Ctrl+=, Ctrl+-, Ctrl+0)
        self.font_size = 14 if step == 0 else self.font_size + step

    def view(self):
        line, column = self.cursor
        return pz.column([
            ui.editor("main.py", self.text, path="main.py", font_size=self.font_size, height=200,
                      on_change=lambda text: setattr(self, "text", text),            # every edit
                      on_cursor=lambda ln, col: setattr(self, "cursor", (ln, col)),  # from 1
                      on_zoom=self.zoom,
                      on_action=lambda name: print("ran", name)),                    # "undo"...
            ui.status_bar([], [ui.status_item(f"Ln {line}, Col {column}")]),
        ])''', '''from dataclasses import dataclass


@dataclass
class Edited:
    text: str


@dataclass
class Moved:
    line: int
    column: int


class Editor(pz.App):
    text, cursor = "print('hello')\\n", (1, 1)

    def update(self, message):
        match message:
            case Edited(text):
                self.text = text
            case Moved(line, column):
                self.cursor = (line, column)

    def view(self):
        return ui.editor("main.py", self.text, path="main.py", height=200,
                         on_change=Edited, on_cursor=Moved)   # the classes build the messages''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    text: str = "print('hello')\\n"
    line: int = 1
    column: int = 1


def view(state, set_state):
    return pz.column([
        ui.editor("main.py", state.text, path="main.py", height=200,
                  on_change=lambda text: set_state(text=text),
                  on_cursor=lambda line, column: set_state(line=line, column=column)),
        ui.label(f"Ln {state.line}, Col {state.column}"),
    ])''')

ex("console", '''class Debug(pz.App):
    def __init__(self):
        self.log = ui.Log()
        self.log.write("info", "Started")
        self.log.write("error", "ValueError: bad input")
        self.log.on_write = lambda: pz.post("log")          # a line arrived (from any thread)
        self.query, self.hidden = "", set()

    def update(self, message):
        pass                             # "log" just redraws

    def view(self):
        return ui.console(self.log.entries, query=self.query, hidden=self.hidden,
                          on_query=lambda q: setattr(self, "query", q),               # the filter
                          on_toggle_level=lambda lvl: self.hidden.symmetric_difference_update({lvl}),
                          on_clear=self.log.clear,                                    # adds Clear
                          on_copy=lambda: pz.Command.copy(self.log.text()),           # adds Copy
                          on_open=lambda entry: print("open", entry.text))            # double click''', '''from dataclasses import dataclass


@dataclass
class Filter:
    query: str


@dataclass
class ToggleLevel:
    level: str


class Debug(pz.App):
    log = ui.Log()
    query, hidden = "", frozenset()

    def update(self, message):
        match message:
            case Filter(query):
                self.query = query
            case ToggleLevel(level):
                self.hidden = self.hidden ^ {level}
            case "clear":
                self.log.clear()

    def view(self):
        return ui.console(self.log.entries, query=self.query, hidden=self.hidden, on_query=Filter,
                          on_toggle_level=ToggleLevel, on_clear="clear")''', '''from dataclasses import dataclass

LOG = ui.Log()
LOG.write("info", "Started")


@dataclass(frozen=True)
class State:
    query: str = ""
    hidden: frozenset = frozenset()


def view(state, set_state):
    return ui.console(LOG.entries, query=state.query, hidden=state.hidden,
                      on_query=lambda q: set_state(query=q),
                      on_toggle_level=lambda lvl: set_state(hidden=state.hidden ^ {lvl}))''')

ex("markdown", '''import webbrowser


class Notes(pz.App):
    def __init__(self):
        self.last = None

    def follow(self, url):               # on_link: the URL of the clicked link
        self.last = url
        webbrowser.open(url)

    def view(self):
        return ui.markdown("Read the [docs](https://albakore.github.io/pyzed/) or the "
                           "[changelog](https://github.com/albakore/pyzed).", on_link=self.follow)''', '''from dataclasses import dataclass


@dataclass
class Link:
    url: str


class Notes(pz.App):
    def update(self, message):
        match message:
            case Link(url) if url.startswith("app:"):
                print("internal page", url[4:])   # links can drive the app, too
            case Link(url):
                print("open", url)

    def view(self):
        return ui.markdown("Go to [settings](app:settings) or the [docs](https://albakore.github.io/pyzed/).",
                           on_link=Link)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    page: str = "home"


PAGES = {"home": "Welcome. See [about](about).", "about": "Made with Pyzed. Back [home](home)."}


def view(state, set_state):
    text = PAGES.get(state.page, "Not found. Back [home](home).")
    return ui.markdown(text, on_link=lambda url: set_state(page=url))''')

ex("shortcuts", '''class Help(pz.App):
    def __init__(self):
        self.query = ""

    def view(self):
        return ui.shortcuts([("File", [("Save", "ctrl-s"), ("Open file", "ctrl-p")])],
                            query=self.query, on_query=lambda q: setattr(self, "query", q))  # adds search''', '''from dataclasses import dataclass


@dataclass
class Search:
    query: str


class Help(pz.App):
    query = ""

    def update(self, message):
        match message:
            case Search(query):
                self.query = query

    def view(self):
        return ui.shortcuts([("File", [("Save", "ctrl-s")])], query=self.query, on_query=Search)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    query: str = ""


def view(state, set_state):
    return ui.shortcuts([("File", [("Save", "ctrl-s"), ("Open file", "ctrl-p")])],
                        query=state.query, on_query=lambda q: set_state(query=q))''')

ex("reference-browser", '''import webbrowser

from pyzed import reference


class Help(pz.App):
    def __init__(self):
        self.browser = reference.Browser("pyzed.ui.button")

    def view(self):
        return ui.reference_browser(self.browser, on_open_url=webbrowser.open)   # links to the web''', '''from dataclasses import dataclass

from pyzed import reference


@dataclass
class OpenUrl:
    url: str


class Help(pz.App):
    browser = reference.Browser("pyzed.ui.button")

    def update(self, message):
        match message:
            case OpenUrl(url):
                print("open", url)

    def view(self):
        return ui.reference_browser(self.browser, on_open_url=OpenUrl)''', '''from dataclasses import dataclass

from pyzed import reference

BROWSER = reference.Browser("pyzed.ui.button")


@dataclass(frozen=True)
class State:
    last_url: str = ""


def view(state, set_state):
    return ui.reference_browser(BROWSER, on_open_url=lambda url: set_state(last_url=url))''')

# ----------------------------------------------------------------------------------- agents

ex("tool-call", '''class Chat(pz.App):
    def __init__(self):
        self.status = "waiting"

    def answer(self, status):
        self.status = status

    def view(self):                      # a pz.Component: handlers get a pz.Event
        return ui.ToolCall(title="Run", detail="pytest -q", kind="execute", status=self.status,
                           input={"command": "pytest -q"},
                           on_allow=lambda e: self.answer("done"),
                           on_allow_always=lambda e: self.answer("done"),
                           on_deny=lambda e: self.answer("rejected"))''', '''class Chat(pz.App):
    status = "waiting"

    def update(self, message):
        match message:
            case "allow":
                self.status = "done"
            case "deny":
                self.status = "rejected"

    def view(self):
        return ui.ToolCall(title="Run", detail="pytest -q", kind="execute", status=self.status,
                           on_allow="allow", on_deny="deny")   # messages work for components too''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    status: str = "waiting"


def view(state, set_state):
    return ui.ToolCall(title="Run", detail="pytest -q", kind="execute", status=state.status,
                       on_allow=lambda e: set_state(status="done"),
                       on_deny=lambda e: set_state(status="rejected"))''')

ex("edits-bar", '''class Review(pz.App):
    def __init__(self):
        self.files = [{"path": "app/storage.py", "added": 12, "removed": 3},
                      {"path": "tests/test_storage.py", "added": 8, "removed": 0}]

    def drop(self, path=None):           # None: every file
        self.files = [f for f in self.files if path is not None and f["path"] != path]

    def view(self):                      # event.value is the file's path
        return ui.EditsBar(files=self.files,
                           on_keep=lambda e: self.drop(), on_reject=lambda e: self.drop(),
                           on_keep_file=lambda e: self.drop(e.value),
                           on_reject_file=lambda e: self.drop(e.value),
                           on_open=lambda e: print("open", e.value))''', '''from dataclasses import dataclass


@dataclass
class Done:
    path: str = ""


class Review(pz.App):
    files = [{"path": "app/storage.py", "added": 12, "removed": 3}]

    def update(self, message):
        match message:
            case Done(""):
                self.files = []
            case Done(path):
                self.files = [f for f in self.files if f["path"] != path]

    def view(self):
        return ui.EditsBar(files=self.files, on_keep=Done(), on_keep_file=lambda e: Done(e.value))''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    files: tuple = ({"path": "app/storage.py", "added": 12, "removed": 3},)


def view(state, set_state):
    without = lambda path: tuple(f for f in state.files if f["path"] != path)
    return ui.EditsBar(files=list(state.files), on_keep=lambda e: set_state(files=()),
                       on_keep_file=lambda e: set_state(files=without(e.value)))''')

ex("thread-history", '''import time


class Chats(pz.App):
    def __init__(self):
        now = time.time()
        self.threads = [{"id": "1", "title": "Add a login form", "updated": now - 60},
                        {"id": "2", "title": "Fix the tests", "updated": now - 900}]
        self.open_id = "1"

    def view(self):                      # event.value is the thread's id
        return ui.ThreadHistory(threads=self.threads, selected=self.open_id,
                                on_open=lambda e: setattr(self, "open_id", e.value),
                                on_delete=lambda e: self.delete(e.value))

    def delete(self, ident):
        self.threads = [t for t in self.threads if t["id"] != ident]''', '''from dataclasses import dataclass


@dataclass
class OpenThread:
    ident: str


@dataclass
class DeleteThread:
    ident: str


class Chats(pz.App):
    threads = [{"id": "1", "title": "Add a login form", "updated": 0}]
    open_id = ""

    def update(self, message):
        match message:
            case OpenThread(ident):
                self.open_id = ident
            case DeleteThread(ident):
                self.threads = [t for t in self.threads if t["id"] != ident]

    def view(self):
        return ui.ThreadHistory(threads=self.threads, selected=self.open_id,
                                on_open=lambda e: OpenThread(e.value), on_delete=lambda e: DeleteThread(e.value))''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    threads: tuple = ({"id": "1", "title": "Add a login form", "updated": 0},)
    open_id: str = ""


def view(state, set_state):
    return ui.ThreadHistory(
        threads=list(state.threads), selected=state.open_id,
        on_open=lambda e: set_state(open_id=e.value),
        on_delete=lambda e: set_state(threads=tuple(t for t in state.threads if t["id"] != e.value)))''')

ex("auth-prompt", '''class Agent(pz.App):
    def __init__(self):
        self.waiting, self.code = "", ""

    def sign_in(self, method):           # on_pick: event.value is the method's id
        self.waiting, self.code = method, "ABCD-1234"

    def view(self):
        return ui.AuthPrompt(title="Sign in to use the agent", waiting=self.waiting, code=self.code,
                             methods=[{"id": "browser", "name": "Log in with the browser"}],
                             on_pick=lambda e: self.sign_in(e.value),
                             on_cancel=lambda e: setattr(self, "waiting", ""),
                             on_copy=lambda e: pz.Command.copy(e.value))   # the code''', '''from dataclasses import dataclass


@dataclass
class Picked:
    method: str


class Agent(pz.App):
    waiting = ""

    def update(self, message):
        match message:
            case Picked(method):
                self.waiting = method
            case "cancel":
                self.waiting = ""

    def view(self):
        return ui.AuthPrompt(title="Sign in", waiting=self.waiting,
                             methods=[{"id": "key", "name": "Use an API key"}],
                             on_pick=lambda e: Picked(e.value), on_cancel="cancel")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    waiting: str = ""


def view(state, set_state):
    return ui.AuthPrompt(title="Sign in", waiting=state.waiting,
                         methods=[{"id": "browser", "name": "Log in with the browser"}],
                         on_pick=lambda e: set_state(waiting=e.value),
                         on_cancel=lambda e: set_state(waiting=""))''')

ex("service-row", '''class Settings(pz.App):
    def __init__(self):
        self.on = True
        self.updates = 0

    def view(self):
        return ui.ServiceRow(name="github", status="running" if self.on else "off", enabled=self.on,
                             primary="Update",
                             on_toggle=lambda e: setattr(self, "on", e.value),     # the switch
                             on_primary=lambda e: setattr(self, "updates", self.updates + 1))''', '''from dataclasses import dataclass


@dataclass
class Enable:
    on: bool


class Settings(pz.App):
    on = True

    def update(self, message):
        match message:
            case Enable(on):
                self.on = on

    def view(self):
        return ui.ServiceRow(name="github", enabled=self.on, status="running" if self.on else "off",
                             on_toggle=lambda e: Enable(e.value))''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    on: bool = True


def view(state, set_state):
    return ui.ServiceRow(name="github", enabled=state.on, status="running" if state.on else "off",
                         on_toggle=lambda e: set_state(on=e.value))''')

ex("catalog", '''class Agents(pz.App):
    def __init__(self):
        self.items = [{"id": "goose", "name": "Goose", "version": "1.9.0"},
                      {"id": "codex", "name": "Codex CLI", "version": "0.40.0"}]
        self.installing = ""

    def install(self, ident):            # on_install: event.value is the item's id
        self.installing = ident

    def view(self):
        return ui.Catalog(items=self.items, busy=self.installing, height=200,
                          on_install=lambda e: self.install(e.value))''', '''from dataclasses import dataclass


@dataclass
class Install:
    ident: str


class Agents(pz.App):
    items = [{"id": "goose", "name": "Goose", "version": "1.9.0"}]
    installing = ""

    def update(self, message):
        match message:
            case Install(ident):
                self.installing = ident

    def view(self):
        return ui.Catalog(items=self.items, busy=self.installing, height=200,
                          on_install=lambda e: Install(e.value))''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    installed: frozenset = frozenset()


ITEMS = [{"id": "goose", "name": "Goose", "version": "1.9.0"}]


def view(state, set_state):
    items = [{**i, "installed": i["id"] in state.installed} for i in ITEMS]
    return ui.Catalog(items=items, height=200,
                      on_install=lambda e: set_state(installed=state.installed | {e.value}))''')

# ----------------------------------------------------------------------------------- layout

ex("scrollable", '''class Feed(pz.App):
    def __init__(self):
        self.items = [f"Post {i}" for i in range(1, 30)]
        self.at_end = False

    def scrolled(self, info):            # on_scroll: x, y, relative_x, relative_y, sizes
        self.at_end = info["relative_y"] > 0.95

    def view(self):
        return pz.column([
            pz.scrollable(pz.column([ui.list_item(p, icon="file") for p in self.items]),
                          height=200, on_scroll=self.scrolled),
            ui.muted("You reached the end" if self.at_end else "Scroll down"),
        ], spacing=6, width=300)''', '''from dataclasses import dataclass


@dataclass
class Scrolled:
    info: dict


class Feed(pz.App):
    items = [f"Post {i}" for i in range(1, 30)]

    def update(self, message):
        match message:
            case Scrolled(info) if info["relative_y"] > 0.95:
                self.items = self.items + [f"Post {len(self.items) + 1}"]   # load more

    def view(self):
        return pz.scrollable(pz.column([ui.list_item(p) for p in self.items]), height=200,
                             on_scroll=Scrolled)''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    progress: float = 0.0


def view(state, set_state):
    return pz.column([
        ui.progress(state.progress),
        pz.scrollable(pz.column([ui.list_item(f"Post {i}") for i in range(30)]), height=200,
                      on_scroll=lambda info: set_state(progress=info["relative_y"])),
    ], spacing=6, width=300)''')

ex("resizable", '''class Mail(pz.App):
    def __init__(self):
        self.width = 260

    def view(self):
        return pz.row([
            pz.resizable(ui.muted(f"{self.width:.0f} px"), edge="right", size=self.width, min_size=160,
                         on_resize=lambda size: setattr(self, "width", size)),   # when the drag ends
            main_view(),
        ], height="fill")''', '''from dataclasses import dataclass


@dataclass
class Width:
    size: float


class Mail(pz.App):
    width = 260

    def update(self, message):
        match message:
            case Width(size):
                self.width = size

    def view(self):
        return pz.row([pz.resizable(ui.muted("Folders"), size=self.width, on_resize=Width), main_view()],
                      height="fill")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    width: float = 260


def view(state, set_state):
    return pz.row([pz.resizable(ui.muted("Folders"), size=state.width,
                                on_resize=lambda size: set_state(width=size)), main_view()], height="fill")''')

ex("canvas", '''class Paint(pz.App):
    def __init__(self):
        self.dots, self.drawing = [], False

    def press(self, x, y):               # on_press / on_move get the position
        self.drawing = True
        self.dots.append((x, y))

    def move(self, x, y):
        if self.drawing:
            self.dots.append((x, y))

    def view(self):
        return pz.canvas([draw.circle(x, y, 3, fill="#74ade8") for x, y in self.dots],
                         width=420, height=200, cursor="crosshair",
                         on_press=self.press, on_move=self.move,
                         on_release=lambda x, y: setattr(self, "drawing", False),
                         on_right_press=lambda x, y: self.dots.clear())''', '''from dataclasses import dataclass


@dataclass
class Dot:
    x: float
    y: float


class Paint(pz.App):
    dots = []

    def update(self, message):
        match message:
            case Dot(x, y):
                self.dots = self.dots + [(x, y)]
            case "clear":
                self.dots = []

    def view(self):
        return pz.canvas([draw.circle(x, y, 3, fill="#74ade8") for x, y in self.dots],
                         width=420, height=200, on_press=Dot, on_right_press=lambda x, y: "clear")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    dots: tuple = ()
    zoom: float = 1.0


def view(state, set_state):
    shapes = [draw.circle(x, y, 3 * state.zoom, fill="#74ade8") for x, y in state.dots]
    return pz.canvas(shapes, width=420, height=200,
                     on_press=lambda x, y: set_state(dots=state.dots + ((x, y),)),
                     on_scroll=lambda dx, dy: set_state(zoom=max(0.5, state.zoom + dy * 0.1)))''')

ex("mouse-area", '''class Board(pz.App):
    def __init__(self):
        self.pointer, self.hovering, self.zoom = (0, 0), False, 1.0

    def view(self):
        return pz.mouse_area(
            ui.card(ui.label(f"{self.pointer} · zoom {self.zoom:.1f}"), width=320),
            on_enter=lambda: setattr(self, "hovering", True),
            on_exit=lambda: setattr(self, "hovering", False),
            on_move=lambda x, y: setattr(self, "pointer", (round(x), round(y))),
            on_scroll=lambda dx, dy: setattr(self, "zoom", max(0.1, self.zoom + dy * 0.1)),
            on_double_click=lambda: setattr(self, "zoom", 1.0),
            on_right_press=lambda: print("context menu"),
            cursor="crosshair",
        )''', '''from dataclasses import dataclass


@dataclass
class Moved:
    x: float
    y: float


class Board(pz.App):
    pointer = (0, 0)

    def update(self, message):
        match message:
            case Moved(x, y):
                self.pointer = (round(x), round(y))
            case "reset":
                self.pointer = (0, 0)

    def view(self):
        return pz.mouse_area(ui.card(ui.label(str(self.pointer)), width=320),
                             on_move=Moved, on_double_click="reset")''', '''from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    hovering: bool = False


def view(state, set_state):
    return pz.mouse_area(ui.card(ui.label("Hovering" if state.hovering else "Point at me"), width=320),
                         on_enter=lambda: set_state(hovering=True), on_exit=lambda: set_state(hovering=False))''')
