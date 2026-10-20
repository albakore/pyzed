"""Changing the theme: a bundled theme, an accent color, follow the system, or your own.

    python examples/tutorial/theme_switcher.py

- ``theme`` (a class attribute or ``self.theme``) takes the name of a bundled theme, a ``pz.Theme``
  or ``pz.themes.auto(light, dark)``, which follows the operating system's light/dark setting.
- ``theme.with_accent("#e5c07b")`` changes only the accent (primary buttons, focus, selection).
- ``pz.Theme.generate(...)`` builds a whole theme from three colors; ``pz.themes.register``
  adds it to ``pz.themes.names()``.

Every component reads its colors from the active theme, so the window restyles at once.
Walkthrough: https://albakore.github.io/pyzed/tutorials/basic/themes/
"""

import pyzed as pz
from pyzed import ui

# A theme of your own, made from three colors and registered by name.
SUNSET = pz.themes.register(pz.Theme.generate("Sunset", background="#2b1d2f", text="#f5e6e8", accent="#ff8a65"))

ACCENTS = {"Theme": None, "Blue": "#74ade8", "Purple": "#b477cf", "Green": "#a1c181", "Gold": "#e5c07b"}


class ThemeSwitcher(pz.App):
    title = "Themes"
    size = (760, 520)
    theme = "One Dark"  # the theme the window opens with

    def __init__(self):
        self.base = "One Dark"
        self.accent = "Theme"
        self.follow_system = False
        self.name = "Ada"

    def apply(self):
        """Builds the theme from the choices and assigns it: the next view() uses it."""
        if self.follow_system:
            self.theme = pz.themes.auto("One Light", "One Dark")
            return
        theme = pz.themes.get(self.base)
        color = ACCENTS[self.accent]
        self.theme = theme.with_accent(color) if color else theme

    def choose(self, field):
        def setter(value):
            setattr(self, field, value)
            self.apply()
        return setter

    def controls(self):
        return ui.settings_group("Appearance", [
            ui.field("Follow the system", ui.switch(self.follow_system, self.choose("follow_system")),
                     description="Light or dark, as your operating system"),
            ui.field("Theme", ui.select(pz.themes.names(), self.base, self.choose("base"), width=220)),
            ui.field("Accent", ui.segmented(list(ACCENTS), self.accent, self.choose("accent"))),
        ])

    def preview(self):
        return ui.card(pz.column([
            ui.input(self.name, lambda v: setattr(self, "name", v), placeholder="Your name", icon="user"),
            pz.row([
                ui.button("Save", lambda: None, variant="solid", icon="check"),
                ui.button("Cancel", lambda: None, variant="ghost"),
                pz.hspace(),
                ui.badge("New"), ui.badge("Done", tint="success"), ui.badge("Late", tint="error"),
            ], spacing=8, align="center"),
            ui.progress(0.65),
            ui.callout("Hello " + (self.name or "there"), "Every color here comes from the theme.", tint="info"),
        ], spacing=12), title="Preview", width="fill")

    def view(self):
        t = self.resolved_theme()  # the Theme in use right now
        return pz.container(
            pz.column([
                ui.heading("Pick a look", level=2),
                ui.muted(f"Using {t.name} ({'dark' if t.is_dark else 'light'})"),
                self.controls(),
                self.preview(),
            ], spacing=16),
            padding=24, width="fill", height="fill", bg=t.background,
        )


if __name__ == "__main__":
    pz.run(ThemeSwitcher)
