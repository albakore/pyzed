"""Queries the window runs (in worker threads): select(), where(), relationships, add, delete."""

from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from models import Hero, HeroCreate, Team, create_db_and_tables, create_heroes, engine


def setup() -> None:
    create_db_and_tables()
    create_heroes()


def teams() -> list[Team]:
    with Session(engine) as session:
        # Load each team's heroes now: relationships can't be read after the session closes.
        return list(session.exec(select(Team).options(selectinload(Team.heroes)).order_by(Team.name)))


def heroes(team_id: int | None | str, min_age: int | None) -> list[Hero]:
    """team_id is a team id, None for heroes without a team, or "all"."""
    statement = select(Hero).options(selectinload(Hero.team)).order_by(Hero.name)
    if team_id != "all":
        statement = statement.where(Hero.team_id == team_id)
    if min_age is not None:
        statement = statement.where(col(Hero.age) >= min_age)  # the tutorial's "where" chapter
    with Session(engine) as session:
        return list(session.exec(statement))


def save(hero_id: int | None, data: HeroCreate) -> None:
    with Session(engine) as session:
        hero = session.get(Hero, hero_id) if hero_id else Hero.model_validate(data)
        hero.sqlmodel_update(data.model_dump())
        session.add(hero)
        session.commit()


def delete(hero_id: int) -> None:
    with Session(engine) as session:
        session.delete(session.get(Hero, hero_id))
        session.commit()
