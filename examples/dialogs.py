"""Dialogs and languages: ready-made dialogs and switching the app's language while it runs.

    python examples/dialogs.py

- Pick a language in the toolbar; every text (and the dialogs' buttons) follows it.
- Each button opens one of the dialogs in ``pyzed.ui``.
"""

import pyzed as pz
from pyzed import i18n, ui

i18n.add("en", {
    "title": "Dialogs",
    "language": "Language",
    "files": {"zero": "No files", "one": "{count} file", "other": "{count} files"},
    "actions": {"alert": "Show an alert", "confirm": "Delete files", "prompt": "Rename", "choice": "Export",
                "unsaved": "Close document"},
    "delete_question": "Delete {files}? This cannot be undone.",
    "saved": "Your changes were saved.",
    "rename": "Rename file",
    "new_name": "New name",
    "export": "Export the report as…",
    "last": "Last action: {action}",
})
i18n.add("es", {
    "title": "Diálogos",
    "language": "Idioma",
    "files": {"zero": "Ningún archivo", "one": "{count} archivo", "other": "{count} archivos"},
    "actions": {"alert": "Mostrar un aviso", "confirm": "Eliminar archivos", "prompt": "Renombrar", "choice": "Exportar",
                "unsaved": "Cerrar documento"},
    "delete_question": "¿Eliminar {files}? No se puede deshacer.",
    "saved": "Tus cambios se guardaron.",
    "rename": "Renombrar archivo",
    "new_name": "Nombre nuevo",
    "export": "Exportar el informe como…",
    "last": "Última acción: {action}",
})

LANGUAGES = {"en": "English", "es": "Español"}


class DialogsDemo(pz.App):
    size = (720, 460)

    def __init__(self):
        self.dialog = None
        self.files = 3
        self.name = "report.md"
        self.last = "-"

    def title(self):
        return pz.t("title")

    def open(self, kind):
        self.dialog = kind

    def done(self, action):
        self.last = action
        self.dialog = None

    def delete(self):
        self.files = 0
        self.done("delete")

    def dialog_view(self):
        close = lambda: self.done("cancel")  # noqa: E731
        if self.dialog == "alert":
            return ui.alert(pz.t("saved"), close, kind="success")
        if self.dialog == "confirm":
            return ui.confirm(pz.t("delete_question", files=pz.t("files", count=self.files)), self.delete, close,
                              danger=True)
        if self.dialog == "prompt":
            return ui.prompt(pz.t("rename"), self.name, lambda v: setattr(self, "name", v),
                             lambda: self.done(f"rename → {self.name}"), close, message=pz.t("new_name"))
        if self.dialog == "choice":
            return ui.choice(pz.t("export"), [(f, lambda f=f: self.done(f"export {f}")) for f in ("CSV", "PDF")], close)
        if self.dialog == "unsaved":
            return ui.unsaved_changes(self.name, lambda: self.done("save"), lambda: self.done("discard"), close)
        return None

    def view(self):
        toolbar = pz.row([
            ui.heading(pz.t("title")),
            pz.space(width="fill"),
            ui.label(pz.t("language"), color="text_muted"),
            ui.segmented([LANGUAGES[k] for k in LANGUAGES], LANGUAGES[i18n.language()[:2]],
                         lambda name: i18n.set_language(next(k for k, v in LANGUAGES.items() if v == name))),
        ], align="center", spacing=10)
        buttons = pz.grid(
            [ui.button(pz.t(f"actions.{kind}"), lambda kind=kind: self.open(kind), full_width=True)
             for kind in ("alert", "confirm", "prompt", "choice", "unsaved")],
            columns=["1fr", "1fr"], spacing=8,
        )
        body = pz.column([
            toolbar,
            ui.label(f"{self.name} · {pz.t('files', count=self.files)}", color="text_muted"),
            buttons,
            ui.label(pz.t("last", action=self.last), mono=True, size="sm"),
        ], spacing=16, padding=24)
        return ui.dialog_layer(body, self.dialog_view(), on_dismiss=lambda: self.done("cancel"))


if __name__ == "__main__":
    pz.run(DialogsDemo)
