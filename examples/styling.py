"""Theming playground, after Iced's ``styling`` demo.

    python examples/styling.py

- pick any bundled theme (One, Ayu and Gruvbox families, from Zed),
- follow the OS light/dark setting with ``themes.auto``,
- or build your own from three colors with ``Theme.generate`` and tweak the accent.

Every component reads its colors from the current theme, so the whole window
restyles at once.
"""

import pyzed as pz
from pyzed import ui

ACCENTS = ["#74ade8", "#b477cf", "#a1c181", "#e5c07b", "#d07277", "#6eb4bf"]


class Styling(pz.App):
    title = "Styling"
    size = (1000, 680)

    def __init__(self):
        self.mode = "Bundled"
        self.base = "Pyzed Dark"
        self.accent = None
        self.custom_bg = 0.12
        self.custom_hue = 0
        self.progress = 0.6
        self.checked = True
        self.toggled = False
        self.text = "Hello, Pyzed"
        self.apply()

    def apply(self):
        if self.mode == "Follow OS":
            self.theme = pz.themes.auto("Pyzed Light", "Pyzed Dark")
            return
        if self.mode == "Custom":
            level = int(self.custom_bg * 255)
            background = f"#{level:02x}{level:02x}{min(255, level + 8):02x}"
            text = "#1c2025" if self.custom_bg > 0.5 else "#e6e8eb"
            theme = pz.Theme.generate("Custom", background=background, text=text,
                                      accent=ACCENTS[self.custom_hue])
        else:
            theme = pz.themes.get(self.base)
        self.theme = theme.with_accent(self.accent) if self.accent else theme

    def set(self, field):
        def setter(value):
            setattr(self, field, value)
            self.apply()
        return setter

    def controls(self):
        rows = [
            ui.field("Source", ui.segmented(["Bundled", "Follow OS", "Custom"], self.mode, self.set("mode"))),
        ]
        if self.mode == "Bundled":
            rows.append(ui.field("Theme", ui.select(pz.themes.names(), self.base, self.set("base"), width=200)))
        if self.mode == "Custom":
            rows.append(ui.field("Background", pz.container(
                ui.slider(self.custom_bg, self.set("custom_bg")), width=200)))
            rows.append(ui.field("Accent", pz.row([
                pz.button(None, lambda i=i: self.set("custom_hue")(i), width=22, height=22, bg=color, radius=11,
                          border_color="#ffffff" if i == self.custom_hue else None, border_width=2)
                for i, color in enumerate(ACCENTS)], spacing=6)))
        if self.mode != "Follow OS":
            rows.append(ui.field("Accent override", pz.row(
                [ui.chip("none", selected=self.accent is None, on_press=lambda: self.set("accent")(None))]
                + [pz.button(None, lambda c=c: self.set("accent")(c), width=22, height=22, bg=c, radius=11,
                             border_color="#ffffff" if c == self.accent else None, border_width=2) for c in ACCENTS],
                spacing=6, align="center")))
        return ui.settings_group("Theme", rows)

    def preview(self):
        return ui.card(pz.column([
            pz.row([ui.button("Primary", lambda: None, variant="solid"), ui.button("Filled", lambda: None),
                    ui.button("Outline", lambda: None, variant="outline"), ui.button("Ghost", lambda: None, variant="ghost"),
                    ui.button("Danger", lambda: None, tint="error")], spacing=8),
            ui.input(self.text, lambda v: setattr(self, "text", v), icon="search"),
            pz.row([ui.checkbox(self.checked, lambda v: setattr(self, "checked", v), label="Checkbox"),
                    ui.switch(self.toggled, lambda v: setattr(self, "toggled", v)),
                    ui.badge("Badge"), ui.badge("Success", tint="success"), ui.badge("Error", tint="error")],
                   spacing=12, align="center"),
            ui.slider(self.progress, lambda v: setattr(self, "progress", v)),
            ui.progress(self.progress),
            ui.callout("Heads up", "This callout uses the info color.", tint="info"),
            ui.editor("preview", 'def greet(name: str) -> str:\n    return f"Hello, {name}!"  # comment\n',
                      language="py", height="shrink"),
        ], spacing=12), title="Preview", width="fill")

    def view(self):
        t = self.resolved_theme()
        return pz.container(
            pz.scrollable(pz.row([pz.column([self.controls()], width=440), self.preview()], spacing=20, padding=24),
                          height="fill"),
            width="fill", height="fill", bg=t.background,
        )


if __name__ == "__main__":
    pz.run(Styling)
