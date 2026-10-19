"""The Pyzed window shared by desktop.py (Django ORM in this process) and client.py (HTTP to the site).

A backend is three functions returning plain dicts like ``polls.views.question_json``.
They may be regular functions (Pyzed runs them in a thread) or ``async def`` (run on
Pyzed's asyncio loop): ``Command.perform`` accepts both.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import pyzed as pz
from pyzed import Command, ui


class PollsWindow(pz.App):
    title = "Polls · Django"
    size = (960, 600)

    def __init__(self, load: Callable, vote: Callable, create: Optional[Callable] = None, mode: str = ""):
        self.backend_load, self.backend_vote, self.backend_create = load, vote, create
        self.mode = mode
        self.questions: list[dict] = []
        self.selected_id: int | None = None
        self.message = ""
        self.creating = False
        self.draft = {"question_text": "", "choices": ["", "", ""]}
        self.errors: dict[str, str] = {}

    # -- backend calls ----------------------------------------------------------------------
    def on_start(self):
        return self.reload()

    def reload(self):
        return Command.perform(self.backend_load, self.loaded)

    def loaded(self, result):
        if isinstance(result, str):  # the backend couldn't answer
            self.message = result
            return
        self.questions, self.message = result, ""
        if self.questions and self.selected_id not in {q["id"] for q in self.questions}:
            self.selected_id = self.questions[0]["id"]

    def vote(self, question_id: int, choice_id: int):
        return Command.perform(lambda: self.backend_vote(question_id, choice_id), self.voted)

    def voted(self, result):
        if isinstance(result, str):
            self.message = result
            return None
        return self.reload()

    def create(self):
        draft = {"question_text": self.draft["question_text"], "choices": [c for c in self.draft["choices"] if c.strip()]}
        return Command.perform(lambda: self.backend_create(draft), self.created)

    def created(self, result):
        if "id" not in result:  # {field: message}
            self.errors = result
            return None
        self.creating, self.selected_id = False, result["id"]
        self.draft = {"question_text": "", "choices": ["", "", ""]}
        return self.reload()

    # -- view --------------------------------------------------------------------------------
    @staticmethod
    def recent(question: dict) -> bool:  # Question.was_published_recently, on the JSON
        published = datetime.fromisoformat(question["pub_date"])
        now = datetime.now(timezone.utc)
        return now - timedelta(days=1) <= published <= now

    def sidebar(self, t):
        rows = [ui.list_item(q["question_text"], lambda q=q: setattr(self, "selected_id", q["id"]), icon="vote",
                             end=ui.badge("new", tint="success") if self.recent(q) else None,
                             selected=q["id"] == self.selected_id, inset=True, height=30)
                for q in self.questions]
        new = ui.button("New question", lambda: setattr(self, "creating", True), icon="plus", full_width=True) \
            if self.backend_create else ui.muted("Add questions in the Django admin.", size="sm")
        return pz.container(pz.column([ui.muted("QUESTIONS", size="xs", weight="semibold"), *rows, pz.vspace(), new],
                                      spacing=2), padding=8, width=300, height="fill", bg=t.panel)

    def results(self):
        question = next((q for q in self.questions if q["id"] == self.selected_id), None)
        if question is None:
            return ui.empty_state("No polls are available.", icon="vote")
        total = sum(c["votes"] for c in question["choices"]) or 1
        rows = [pz.row([
            pz.container(ui.label(c["choice_text"]), width=200),
            pz.container(ui.progress(c["votes"] / total, height=8), width="fill"),
            pz.container(ui.muted(f"{c['votes']} vote{'s' if c['votes'] != 1 else ''}", size="sm"), width=70, align_x="end"),
            ui.button("Vote", lambda c=c: self.vote(question["id"], c["id"]), size="sm"),
        ], spacing=12, align="center") for c in question["choices"]]
        return pz.column([ui.heading(question["question_text"], level=2),
                          ui.muted(f"Published {question['pub_date'][:16].replace('T', ' ')}", size="sm"),
                          *rows], spacing=14, padding=24)

    def dialog(self):
        if not self.creating:
            return None
        choices = self.draft["choices"]

        def set_choice(i):
            return lambda value: choices.__setitem__(i, value)

        form = pz.column([
            ui.field("Question", ui.input(self.draft["question_text"], lambda v: self.draft.__setitem__("question_text", v),
                                          placeholder="What's new?", width=260), error=self.errors.get("question_text")),
            *[ui.field(f"Choice {i + 1}", ui.input(text, set_choice(i), width=260)) for i, text in enumerate(choices)],
            ui.callout(self.errors[""], tint="error") if self.errors.get("") else None,
        ], spacing=12)
        close = lambda: setattr(self, "creating", False)  # noqa: E731
        return ui.modal(form, title="New question", on_close=close, width=520,
                        footer=[ui.button("Cancel", close, variant="ghost"),
                                ui.button("Publish", self.create, icon="check", variant="solid")])

    def view(self):
        t = self.resolved_theme()
        status = ui.status_bar([ui.status_item(self.message or self.mode, icon="circle-alert" if self.message else "database",
                                               icon_color="error" if self.message else "success")])
        page = pz.column([pz.row([self.sidebar(t), pz.container(self.results(), width="fill", height="fill", bg=t.editor)]),
                          status])
        return ui.layer(page, self.dialog(), on_dismiss=lambda: setattr(self, "creating", False), backdrop="#00000066")
