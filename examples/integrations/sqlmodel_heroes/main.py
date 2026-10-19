"""SQLModel's tutorial in a Pyzed window: teams, heroes, where() filters and a validated form.

    uv run main.py

The database (database.db) is created and filled with the tutorial's heroes on the first run.
Walkthrough: https://albakore.github.io/pyzed/integrations/sqlmodel/
"""

from __future__ import annotations

from pydantic import ValidationError

import pyzed as pz
from pyzed import Command, ui

import db
from models import Hero, HeroCreate

NO_TEAM = "No team"


class Heroes(pz.App):
    title = "Heroes · SQLModel"
    size = (1060, 620)

    def __init__(self):
        self.teams = []
        self.heroes: list[Hero] = []
        self.team_id: int | None | str = "all"  # a team id, None (heroes without a team) or "all"
        self.older = False                       # only heroes aged 35 or more
        self.editing: Hero | None | str = None   # a Hero, "new" or None
        self.draft: dict = {}
        self.errors: dict[str, str] = {}

    # -- database, in worker threads ------------------------------------------------------------
    def on_start(self):
        return Command.perform(db.setup, lambda _: self.reload())

    def reload(self):
        team_id, min_age = self.team_id, 35 if self.older else None
        return [Command.perform(db.teams, lambda teams: setattr(self, "teams", teams)),
                Command.perform(lambda: db.heroes(team_id, min_age), lambda heroes: setattr(self, "heroes", heroes))]

    def show_team(self, team_id):
        self.team_id = team_id
        return self.reload()

    def toggle_older(self, value: str):
        self.older = value != "All ages"
        return self.reload()

    # -- the form ---------------------------------------------------------------------------------
    def open(self, hero):
        self.editing, self.errors = hero, {}
        if hero == "new":
            self.draft = {"name": "", "secret_name": "", "age": "", "team": NO_TEAM}
        else:
            self.draft = {"name": hero.name, "secret_name": hero.secret_name,
                          "age": "" if hero.age is None else str(hero.age),
                          "team": hero.team.name if hero.team else NO_TEAM}

    def save(self):
        team = next((t for t in self.teams if t.name == self.draft["team"]), None)
        try:
            data = HeroCreate.model_validate({**self.draft, "age": self.draft["age"] or None,
                                              "team_id": team.id if team else None})
        except ValidationError as error:
            self.errors = pz.validation_errors(error)
            return None
        hero_id = None if self.editing == "new" else self.editing.id
        self.editing, self.errors = None, {}
        return Command.perform(lambda: db.save(hero_id, data), lambda _: self.reload())

    def delete(self):
        hero_id, self.editing = self.editing.id, None
        return Command.perform(lambda: db.delete(hero_id), lambda _: self.reload())

    def edit(self, key):
        return lambda value: self.draft.__setitem__(key, value)

    # -- view ---------------------------------------------------------------------------------------
    def sidebar(self, t):
        def item(label, team_id, count, icon):
            return ui.list_item(label, lambda: self.show_team(team_id), icon=icon,
                                end=ui.muted(str(count), size="sm"), selected=self.team_id == team_id, inset=True, height=30)

        teams = [item(team.name, team.id, len(team.heroes), "shield") for team in self.teams]
        return pz.container(pz.column([
            ui.muted("TEAMS", size="xs", weight="semibold"),
            item("All heroes", "all", sum(len(t.heroes) for t in self.teams), "users"),
            *teams,
            item(NO_TEAM, None, "", "user-x"),
        ], spacing=2), padding=8, width=230, height="fill", bg=t.panel)

    def panel(self, t):
        if self.editing is None:
            return None
        e = self.errors.get
        new = self.editing == "new"
        return pz.container(pz.column([
            ui.heading("New hero" if new else self.editing.name, level=3),
            ui.field("Name", ui.input(self.draft["name"], self.edit("name"), width=180), error=e("name")),
            ui.field("Secret name", ui.input(self.draft["secret_name"], self.edit("secret_name"), width=180),
                     error=e("secret_name")),
            ui.field("Age", ui.input(self.draft["age"], self.edit("age"), placeholder="unknown", width=180), error=e("age")),
            ui.field("Team", ui.select([NO_TEAM, *[team.name for team in self.teams]], self.draft["team"],
                                       self.edit("team"), width=180)),
            pz.row([None if new else ui.button("Delete", self.delete, icon="trash-2", variant="ghost", tint="error"),
                    pz.hspace(), ui.button("Cancel", lambda: setattr(self, "editing", None), variant="ghost"),
                    ui.button("Save", self.save, icon="check", variant="solid")], spacing=6),
        ], spacing=12), padding=16, width=380, height="fill", bg=t.panel)

    def view(self):
        t = self.resolved_theme()
        columns = [ui.Column("Name", "name", width="fill:2"), ui.Column("Secret name", "secret_name", width="fill:2"),
                   ui.Column("Age", lambda h: "—" if h.age is None else h.age, width=60, align="end"),
                   ui.Column("Team", lambda h: h.team.name if h.team else "—")]
        main = pz.column([
            pz.row([ui.segmented(["All ages", "Age ≥ 35"], "Age ≥ 35" if self.older else "All ages", self.toggle_older),
                    pz.hspace(), ui.button("New hero", lambda: self.open("new"), icon="plus", variant="solid")],
                   align="center"),
            ui.table(columns, self.heroes, on_row_press=self.open, selected=self.editing, height="fill"),
        ], spacing=12, padding=16)
        return pz.row([self.sidebar(t), pz.container(main, width="fill", height="fill", bg=t.editor), self.panel(t)])


if __name__ == "__main__":
    pz.run(Heroes)
