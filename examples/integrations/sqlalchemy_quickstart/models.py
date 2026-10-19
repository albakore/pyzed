"""The models of SQLAlchemy's ORM Quick Start: https://docs.sqlalchemy.org/en/20/orm/quickstart.html"""

from typing import List, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30))
    fullname: Mapped[Optional[str]]

    addresses: Mapped[List["Address"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, name={self.name!r}, fullname={self.fullname!r})"


class Address(Base):
    __tablename__ = "address"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_address: Mapped[str]
    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"))

    user: Mapped["User"] = relationship(back_populates="addresses")

    def __repr__(self) -> str:
        return f"Address(id={self.id!r}, email_address={self.email_address!r})"


def sample_users() -> list[User]:
    """The users the Quick Start creates."""
    return [
        User(name="spongebob", fullname="Spongebob Squarepants",
             addresses=[Address(email_address="spongebob@sqlalchemy.org")]),
        User(name="sandy", fullname="Sandy Cheeks",
             addresses=[Address(email_address="sandy@sqlalchemy.org"), Address(email_address="sandy@squirrelpower.org")]),
        User(name="patrick", fullname="Patrick Star"),
    ]
