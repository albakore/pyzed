"""What each component's animated preview does (read by library_shots.py).

``SCRIPTS[slug]`` holds the ``steps`` of the preview clip, an optional ``fps`` (lower for clips that
scroll, whose every frame differs) (see anim_webp.py: ``hover``, ``press``,
``drag``, ``type_text``, ``scroll``...) and, for a few components that stand still in their page
snippet (a progress bar, a terminal's output), a ``code`` to record instead: the same widgets,
moved by ``clip_time()`` (seconds since the clip started). A slug that is not here plays the
default script (hover and press the middle); a clip in which nothing changes becomes a theme cycle.

Targets are texts shown in the view, ``"input:n"`` fields, or points in the preview's canvas
(720x360 logical pixels unless the entry sets ``size``). ``library_shots.py --probe <slug>`` prints
what there is to aim at. ``VARIANTS[stem]`` and ``EXAMPLES[stem]`` override the default script of
one variant or example.
"""

from __future__ import annotations

from anim_webp import drag, hover, key, leave, move, press, scroll, type_text, wait


def tour(*targets, hold: float = 450, after: float = 400):
    """Hovers each target in turn, then leaves."""
    steps = [wait(300)]
    for t in targets:
        steps.append(hover(t, ms=300, hold=hold))
    return steps + [leave(), wait(after)]


def clicks(*targets, after: float = 450):
    """Clicks each target in turn, then leaves."""
    steps = [wait(300)]
    for t in targets:
        steps.append(press(t, after=after))
    return steps + [leave(), wait(400)]


SCRIPTS: dict[str, dict] = {
    # -- actions --
    "button": {"steps": tour("Cancel") + [hover("Save"), press(hold=220, after=500), leave()]},
    "icon-button": {"steps": [wait(300), hover((309, 180), hold=900), hover((343, 180), hold=900),
                              hover((377, 180)), press((411, 180)), leave()]},
    "split-button": {"steps": [wait(300), hover("Run"), press("Run"), hover((338, 180)), hover("Deploy"),
                               press(hold=220), leave()]},
    "toggle-group": {"steps": clicks((295, 180), (351, 180), (397, 180), (323, 180))},
    "chip": {"steps": tour("python", "rust") + [hover((396, 180)), press(), leave()]},
    "mouse-area": {"steps": [wait(300), hover("Open project…", hold=600), press(hold=220), leave()]},
    # -- display --
    "tooltip": {"steps": [wait(300), hover((342, 100), hold=1200), hover((378, 100), hold=1200), leave()]},
    "card": {"steps": tour((523, 145), "Cancel") + [hover("OK"), press(), leave()]},
    "avatar": {"steps": tour("AL", "KV", "MZ", "JD")},
    # -- forms --
    "input": {"steps": [wait(300), press("input:0"), type_text("Pyzed app"), press("input:1"),
                        key("End"), type_text(".dev"), leave(), wait(600)]},
    "search-input": {"steps": [wait(300), press("input:0"), type_text("toolbar"), wait(400),
                               press("input:1"), key("End"), type_text("s"), leave(), wait(500)]},
    "checkbox": {"steps": clicks("Show hidden files", "Format on save", "Use tabs")},
    "switch": {"steps": clicks((325, 195), (325, 165), (325, 195))},
    "slider": {"steps": [wait(300), drag((308, 162), (470, 162)), drag((429, 196), (250, 196)), leave()]},
    "number-field": {"steps": [wait(300), press((264, 180)), press((264, 180)), press((396, 180)),
                               press((436, 180)), leave(), wait(400)]},
    "select": {"steps": [wait(300), press((263, 180), after=600), hover((230, 152), hold=400),
                         press(after=400), press((455, 180), after=600), hover((420, 152), hold=300),
                         press(after=400), leave()]},
    "radio-group": {"steps": clicks((232, 193), (392, 180), (462, 180), (232, 167))},
    "segmented": {"steps": clicks("Terminal", "Both", "Month", "Day")},
    "field": {"steps": clicks((562, 143), (572, 183), (566, 220), (566, 220))},
    "color-picker": {"steps": [wait(300), drag((402, 100), (300, 160)), drag((363, 275), (250, 275)),
                               drag((412, 311), (300, 311)), leave()]},
    "icon-picker": {"steps": [wait(300), press("input:0"), type_text("star"), wait(500),
                              hover((228, 89), hold=300), press(), leave()]},
    # -- feedback --
    "progress": {
        "code": '''t = clip_time()
fill = lambda start: start + (1 - start) * min(1, (t % 4) / 3.2)
pz.column([
    ui.progress(fill(0.25)),
    ui.progress(fill(0.6), tint="success", height=6),
    ui.progress(37 * fill(0.4), max=40, tint="warning", height=8),
], spacing=18, width=360)''',
        "steps": [wait(4000)],
    },
    "spinner": {"steps": [wait(2500)]},
    "callout": {"steps": tour("What's new") + [hover((598, 147)), press(), leave()]},
    "toast": {
        "code": '''pz.column(pz.stagger([
    ui.toast("Saved", "main.py was saved.", kind="success", on_dismiss=on_dismiss),
    ui.toast("Update available", "Pyzed 0.4 is on PyPI.", kind="info",
             actions=[ui.button("What's new", on_open, size="sm")], on_dismiss=on_dismiss),
    ui.toast("Could not connect", kind="error", on_dismiss=on_dismiss),
], "fade_in_up", step=350), spacing=8)''',
        "steps": [wait(1600), hover("What's new"), hover((509, 74)), press(), leave()],
    },
    "empty-state": {"steps": [wait(300), hover("Clear filters", hold=600), press(), leave()]},
    "count-badge": {"steps": [wait(300), hover((409, 180), hold=700), press(), leave()]},
    "error-boundary": {"steps": tour("Copy error") + [hover("Details"), press(), leave()]},
    # -- data --
    "table": {"steps": [wait(300), hover("render.rs"), hover("app.py"), press(), hover("Lines"),
                        press(after=600), leave()]},
    "virtual-list": {"fps": 12, "steps": [wait(300), hover("src/module_000003.py"), scroll(8, ms=900), wait(300),
                               scroll(14, ms=900), wait(300), scroll(-22, ms=700), leave()]},
    "stat": {"steps": tour("Users", "Errors", "Build time")},
    "settings-group": {"steps": [wait(300), press((562, 159)), press((562, 159)), press((558, 203)),
                                 press((500, 247), after=600), hover((470, 220), hold=300), press(), leave()]},
    "list-item": {"steps": tour("main.py", "README.md", "Cargo.toml", "old.txt")},
    "list-header": {"steps": tour("main.py", "app.py") + [hover((493, 131)), press(), leave()]},
    "tree": {"steps": [wait(300), hover("button.rs"), press("mod.rs"), press("ui", after=500),
                       press("tests", after=500), press("src", after=500), press("src", after=500), leave()]},
    "menu": {"steps": tour("New file", "New folder", "Copy path", "Soft wrap", "Delete")},
    "accordion": {"steps": [wait(300), press("Editor", after=500), press("Git", after=500), press((530, 149)),
                            press("Editor", after=500), leave()]},
    "disclosure": {"steps": [wait(300), press("Advanced options", after=500),
                             press("Environment variables", after=500), press("Advanced options", after=500),
                             leave()]},
    # -- navigation --
    "tab-bar": {"steps": [wait(300), press("app.rs"), press("README.md"), hover((412, 70)),
                          press("main.rs"), leave()]},
    "breadcrumbs": {"steps": tour("src", "ui", "main.rs", "fn main", "Editor")},
    "toolbar": {"steps": tour("main.rs", (651, 60), (677, 60))},
    # -- overlays & dialogs --
    "layer": {"steps": [wait(300), press("input:0"), type_text("read"), hover("README.md"), press(), leave()]},
    "modal": {"steps": tour("Don't save", "Cancel") + [hover("Save"), press(), leave()]},
    "popover": {"steps": tour("Copy", "Paste", "Delete")},
    "command-palette": {"steps": [wait(300), press("input:0"), type_text("gle"), hover((300, 249)),
                                  hover((300, 187)), press(), leave()]},
    "picker": {"steps": [wait(300), press("input:0"), type_text(".py"), wait(300), hover("python/pyzed/"),
                         press(), leave()]},
    "dialog-layer": {"steps": tour("Cancel") + [hover("Delete"), press(), leave()]},
    "alert": {"steps": [wait(300), hover("OK", hold=600), press(), leave()]},
    "confirm": {"steps": tour("Cancel") + [hover("Delete"), press(), leave()]},
    "prompt": {"steps": [wait(300), press("input:0"), key("a", "ctrl"), type_text("todo.py"),
                         hover("OK"), press(), leave()]},
    "choice": {"steps": tour("Keep both", "Skip", "Replace")},
    "unsaved-changes": {"steps": tour("Don't save", "Cancel", "Save")},
    "error-dialog": {"steps": tour("Show in Logs", "Copy error", "Go to source") + [hover("Close"), press(),
                                                                                    leave()]},
    # -- workspace --
    "workspace": {"steps": tour("pyzed", "main", "ui.py", "README.md") + [hover((300, 140)), press(),
                                                                         type_text("# hi"), leave()]},
    "title-bar": {"steps": tour("pyzed", "main", (653, 60), "KV")},
    "window-frame": {"steps": tour("pyzed", (605, 16), (651, 16), (697, 16))},
    "status-bar": {"steps": [wait(300), hover((43, 60), hold=1100), hover("UTF-8"), hover("Python"), leave()]},
    "panel": {"steps": tour("Inbox", "Archive", (204, 16))},
    "panel-header": {"steps": tour((481, 158), (505, 158), (505, 202))},
    "split": {"steps": [wait(300), drag((289, 180), (420, 180)), drag((502, 170), (502, 100)), leave()]},
    # -- code --
    "editor": {"steps": [wait(300), press((420, 175)), key("End"), key("Enter"), type_text("    # count up"),
                         wait(400), leave()]},
    "terminal": {
        "code": '''t = clip_time()
lines = ["$ pytest -q", "\\x1b[32m........................\\x1b[0m", "\\x1b[32m24 passed\\x1b[0m in 1.21s",
         "$ maturin develop --release", "\\x1b[2m   Compiling pyzed v0.4.0\\x1b[0m",
         "\\x1b[32m✓\\x1b[0m Installed pyzed-0.4.0", "$ "]
shown = min(len(lines), 1 + int(t / 0.45))
pz.container(ui.terminal("\\n".join(lines[:shown])), width=560, height=190)''',
        "steps": [wait(4500)],
    },
    "console": {"steps": [wait(300), press("input:0"), type_text("save"), wait(600), key("a", "ctrl"),
                          key("Backspace"), hover((264, 85)), leave()]},
    "markdown": {"steps": tour((532, 173), (440, 173))},
    "shortcuts": {"steps": [wait(300), press("input:0"), type_text("pal"), wait(600), leave()]},
    "about": {"steps": tour("Website", "GitHub")},
    "reference-browser": {"fps": 12, "steps": [wait(300), hover("ui.label"), hover("ui.button"), press(),
                                    scroll(6, (115, 300)), leave()]},
    # -- agents --
    "tool-call": {"steps": [wait(300), hover("Read file"), press(after=600), hover("Search"), wait(400), leave()]},
    "edits-bar": {"steps": tour("Reject all") + [hover("Keep all"), press(), leave()]},
    "thread-history": {"steps": tour("Fix the failing tests", "Dark theme for the settings", "First steps")},
    "auth-prompt": {"steps": tour("Log in with the browser", "Use an API key")},
    "service-row": {"steps": tour("github", "filesystem", "Update")},
    "catalog": {"steps": [wait(300), hover("Goose"), scroll(3, "Goose"), hover("OpenCode"), leave()]},
    # -- layout & content --
    "scrollable": {"fps": 12, "steps": [wait(300), hover((300, 140)), scroll(10, ms=1000), wait(300), scroll(-10, ms=800),
                             leave()]},
    "resizable": {"steps": [wait(300), drag((259, 180), (420, 180)), drag((420, 180), (200, 180)), leave()]},
    "animation": {"steps": [wait(1200), hover((360, 180), hold=700), hover((360, 120), hold=700), leave(),
                            wait(400)]},
    "anchor-layout": {"steps": [wait(300), press("input:0"), type_text("Q3"), hover("Close"), press(), leave()]},
}

#: Example clips (``<slug>-<n>``) that need their own script.
EXAMPLES: dict[str, list] = {}

#: Variant clips (``<slug>-v<group>-<n>``) that need their own script.
VARIANTS: dict[str, list] = {}

__all__ = ["EXAMPLES", "SCRIPTS", "VARIANTS", "move"]
