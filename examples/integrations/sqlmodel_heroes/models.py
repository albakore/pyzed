"""The tables of SQLModel's tutorial ("Relationship Attributes"): https://sqlmodel.tiangolo.com/tutorial/"""

from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select


class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    headquarters: str

    heroes: list["Hero"] = Relationship(back_populates="team")


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    secret_name: str
    age: int | None = Field(default=None, index=True)

    team_id: int | None = Field(default=None, foreign_key="team.id")
    team: Team | None = Relationship(back_populates="heroes")


class HeroCreate(SQLModel):
    """A data model (no table=True) that validates what the form typed, as in the "Multiple Models" chapter."""

    name: str = Field(min_length=1)
    secret_name: str = Field(min_length=1)
    age: int | None = Field(default=None, ge=0)
    team_id: int | None = None


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def create_heroes():
    """The tutorial's heroes and teams, added the first time."""
    with Session(engine) as session:
        if session.exec(select(Hero)).first():
            return
        team_preventers = Team(name="Preventers", headquarters="Sharp Tower")
        team_z_force = Team(name="Z-Force", headquarters="Sister Margaret's Bar")
        session.add_all([
            Hero(name="Deadpond", secret_name="Dive Wilson", team=team_z_force),
            Hero(name="Rusty-Man", secret_name="Tommy Sharp", age=48, team=team_preventers),
            Hero(name="Spider-Boy", secret_name="Pedro Parqueador", team=team_preventers),
            Team(name="Wakaland", headquarters="Wakaland Capital City", heroes=[
                Hero(name="Black Lion", secret_name="Trevor Challa", age=35),
                Hero(name="Princess Sure-E", secret_name="Sure-E"),
            ]),
            Hero(name="Tarantula", secret_name="Natalia Roman-on", age=32, team=team_preventers),
            Hero(name="Dr. Weird", secret_name="Steve Weird", age=36, team=team_preventers),
            Hero(name="Captain North America", secret_name="Esteban Rogelios", age=93, team=team_preventers),
        ])
        session.commit()
