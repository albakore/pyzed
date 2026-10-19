"""The database: SQLAlchemy 2.0 models on SQLite, plus the queries the window runs."""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

from sqlalchemy import String, create_engine, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DATABASE = Path(__file__).with_name("contacts.db")
engine = create_engine(f"sqlite:///{DATABASE}")


class Base(DeclarativeBase):
    pass


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True)
    company: Mapped[str] = mapped_column(String(80), default="")
    city: Mapped[str] = mapped_column(String(60), default="")
    created: Mapped[datetime] = mapped_column(default=datetime.now)


# Sorting by a column title of the table is an ORDER BY on this column.
COLUMNS = {"Name": Contact.name, "Email": Contact.email, "Company": Contact.company, "City": Contact.city}


def setup(rows: int = 20_000) -> None:
    """Creates the table and fills it with made-up contacts the first time."""
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        if session.scalar(select(func.count()).select_from(Contact)):
            return
        rng = random.Random(7)
        first = ["Ada", "Alan", "Grace", "Linus", "Guido", "Margaret", "Ken", "Barbara", "Dennis", "Radia",
                 "Tim", "Frances", "Bjarne", "Anita", "John", "Hedy", "Yukihiro", "Sophie", "Brendan", "Katherine"]
        last = ["Lovelace", "Turing", "Hopper", "Torvalds", "van Rossum", "Hamilton", "Thompson", "Liskov",
                "Ritchie", "Perlman", "Berners-Lee", "Allen", "Stroustrup", "Borg", "McCarthy", "Lamarr",
                "Matsumoto", "Wilson", "Eich", "Johnson"]
        companies = ["Acme", "Globex", "Initech", "Umbrella", "Hooli", "Stark", "Wayne", "Tyrell", "Cyberdyne", "Aperture"]
        cities = ["Buenos Aires", "Madrid", "Mexico City", "Bogotá", "Lima", "Santiago", "Montevideo", "Barcelona",
                  "Berlin", "Tokyo", "Toronto", "Lisbon"]
        weights = [12, 10, 9, 7, 6, 5, 4, 4, 3, 3, 2, 2]
        session.add_all(
            Contact(name=f"{rng.choice(first)} {rng.choice(last)}", email=f"user{i}@example.com",
                    company=rng.choice(companies), city=rng.choices(cities, weights)[0])
            for i in range(rows)
        )
        session.commit()


def search(text: str, sort: str, descending: bool) -> list[Contact]:
    """Contacts whose name, email or company contains ``text``, sorted in SQL."""
    column = COLUMNS[sort]
    query = select(Contact).order_by(column.desc() if descending else column, Contact.id)
    if text:
        pattern = f"%{text}%"
        query = query.where(or_(Contact.name.ilike(pattern), Contact.email.ilike(pattern),
                                Contact.company.ilike(pattern)))
    with Session(engine) as session:
        return list(session.scalars(query))  # plain objects keep their loaded values after the session closes


def stats() -> dict:
    """Totals and the five cities with more contacts, for the header."""
    with Session(engine) as session:
        total = session.scalar(select(func.count()).select_from(Contact))
        companies = session.scalar(select(func.count(func.distinct(Contact.company))))
        cities = session.execute(select(Contact.city, func.count()).group_by(Contact.city)
                                 .order_by(func.count().desc()).limit(5)).all()
    return {"total": total, "companies": companies, "cities": [(city, count) for city, count in cities]}


def save(contact_id: int | None, values: dict) -> Contact | dict:
    """Inserts or updates a contact. Returns it, or ``{field: message}`` when it can't be saved."""
    errors = {}
    if not values["name"].strip():
        errors["name"] = "A contact needs a name"
    if "@" not in values["email"]:
        errors["email"] = "Not an email address"
    if errors:
        return errors
    with Session(engine, expire_on_commit=False) as session:
        contact = session.get(Contact, contact_id) if contact_id else Contact()
        for key, value in values.items():
            setattr(contact, key, value.strip())
        session.add(contact)
        try:
            session.commit()
        except IntegrityError:
            return {"email": "Another contact already uses this email"}
        return contact


def delete(contact_id: int) -> None:
    with Session(engine) as session:
        contact = session.get(Contact, contact_id)
        if contact is not None:
            session.delete(contact)
            session.commit()
