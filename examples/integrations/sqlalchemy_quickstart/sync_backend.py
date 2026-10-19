"""The database code, as the Quick Start writes it: an Engine, a Session per unit of work, select().

Each function opens its own Session, so Pyzed can run it in a worker thread (Command.perform).
"""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from models import Address, Base, User, sample_users

engine = create_engine("sqlite:///quickstart.db")


def setup() -> None:
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        if session.scalars(select(User)).first() is None:
            session.add_all(sample_users())
            session.commit()


def users() -> list[User]:
    # selectinload fetches the addresses now, so the window can read them after the session closes.
    stmt = select(User).options(selectinload(User.addresses)).order_by(User.name)
    with Session(engine) as session:
        return list(session.scalars(stmt))


def add_user(name: str, fullname: str) -> None:
    with Session(engine) as session:
        session.add(User(name=name, fullname=fullname or None))
        session.commit()


def add_address(user_id: int, email_address: str) -> None:
    with Session(engine) as session:
        user = session.get(User, user_id)
        user.addresses.append(Address(email_address=email_address))
        session.commit()


def rename_address(address_id: int, email_address: str) -> None:
    with Session(engine) as session:
        session.get(Address, address_id).email_address = email_address
        session.commit()


def delete_user(user_id: int) -> None:
    with Session(engine) as session:
        session.delete(session.get(User, user_id))  # cascade="all, delete-orphan" removes the addresses
        session.commit()
