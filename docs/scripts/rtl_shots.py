"""Renders the screenshots of the right-to-left guide (docs/src/assets/guides/rtl-*.png).

    uv run python docs/scripts/rtl_shots.py

The same settings screen is drawn in Arabic (right to left), in English (left to right) and a
Hebrew inbox, so the guide can show what mirrors and what doesn't. Run optimize_images.py after.
"""

from __future__ import annotations

from pathlib import Path

import pyzed as pz
from pyzed import ui

OUT = Path(__file__).resolve().parents[2] / "docs" / "src" / "assets" / "guides"

TEXTS = {
    "ar": {
        "settings": "الإعدادات", "account": "الحساب", "notifications": "الإشعارات", "appearance": "المظهر",
        "language": "اللغة والمنطقة", "profile": "الملف الشخصي", "name": "الاسم", "name_value": "نور",
        "email": "البريد الإلكتروني", "digest": "أرسل لي ملخصًا أسبوعيًا", "dark": "الوضع الداكن",
        "volume": "مستوى الصوت", "storage": "التخزين: ٧٠٪ مستخدم",
        "mixed": "إصدار Pyzed 1.15 يدعم 3 لغات، الرابط https://pyzed.dev",
        "save": "حفظ", "cancel": "إلغاء", "next": "التالي",
    },
    "en": {
        "settings": "Settings", "account": "Account", "notifications": "Notifications", "appearance": "Appearance",
        "language": "Language and region", "profile": "Profile", "name": "Name", "name_value": "Noor",
        "email": "Email", "digest": "Send me a weekly digest", "dark": "Dark mode", "volume": "Volume",
        "storage": "Storage: 70% used", "mixed": "Pyzed 1.15 supports 3 languages, see https://pyzed.dev",
        "save": "Save", "cancel": "Cancel", "next": "Next",
    },
}


def noop():
    pass


def settings(lang: str):
    t = TEXTS[lang]

    class Settings(pz.App):
        size = (860, 520)
        direction = "rtl" if lang == "ar" else "ltr"

        def view(self):
            chevron = pz.icon("chevron-right", size=14)
            sidebar = pz.column([
                ui.panel_header(t["settings"], icon="settings"),
                ui.list_item(t["account"], icon="user", end=chevron, selected=True),
                ui.list_item(t["notifications"], icon="bell", end=ui.badge("3")),
                ui.list_item(t["appearance"], icon="palette", end=chevron),
                ui.list_item(t["language"], icon="globe", end=chevron),
            ], width=220, spacing=2, padding=8)
            form = pz.column([
                ui.breadcrumbs([t["settings"], t["account"], t["profile"]]),
                ui.heading(t["profile"], level=2),
                ui.field(t["name"], ui.input(t["name_value"])),
                ui.field(t["email"], ui.input("noor@example.com", icon="mail")),
                ui.checkbox(True, label=t["digest"]),
                ui.switch(True, label=t["dark"]),
                pz.row([pz.text(t["volume"]), ui.slider(0.3, width=200)], spacing=12, align="center"),
                ui.progress(0.7, label=t["storage"], show_value=True),
                pz.text(t["mixed"]),
                pz.row([ui.button(t["save"], noop, icon="check"), ui.button(t["cancel"], noop, variant="ghost"),
                        ui.button(t["next"], noop, icon="arrow-right", icon_position="end", variant="outline")], spacing=8),
            ], spacing=12, padding=16, width="fill")
            return pz.row([sidebar, form], height="fill")

    return Settings()


class Inbox(pz.App):
    size = (560, 360)
    direction = "rtl"

    def view(self):
        def message(sender, subject, time, unread=False):
            return ui.list_item(subject, icon="mail" if unread else "mail-open", description=sender,
                                end=pz.text(time, size=12))

        return pz.column([
            pz.row([ui.heading("תיבת דואר", level=3), pz.space(width="fill"), ui.button("הודעה חדשה", noop, icon="plus")],
                   align="center"),
            ui.input("", placeholder="חיפוש בהודעות", icon="search"),
            message("דנה כהן", "הפגישה הועברה ליום שלישי", "09:41", unread=True),
            message("יוסי לוי", "הדוח החודשי מוכן (PDF, 2 MB)", "אתמול"),
            message("Pyzed", "גרסה 1.15 זמינה להורדה", "12/11"),
            pz.row([ui.button("הקודם", noop, icon="arrow-left", variant="ghost"),
                    ui.button("הבא", noop, icon="arrow-right", icon_position="end", variant="ghost")], spacing=8),
        ], spacing=10, padding=16, width="fill")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, app in [("rtl-arabic", settings("ar")), ("rtl-english", settings("en")), ("rtl-hebrew", Inbox())]:
        path = OUT / f"{name}.png"
        app.screenshot(str(path), scale=2)
        print(path.relative_to(OUT.parents[3]))


if __name__ == "__main__":
    main()
