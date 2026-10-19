"""The same database code with SQLAlchemy's asyncio extension and the aiosqlite driver.

https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
The functions are coroutines: Pyzed runs them on its asyncio loop, where the engine lives.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from models import Address, Base, User, sample_users

engine = create_async_engine("sqlite+aiosqlite:///quickstart.db")
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def setup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        if (await session.scalars(select(User))).first() is None:
            session.add_all(sample_users())
            await session.commit()


async def users() -> list[User]:
    # Lazy loading needs an await, so load relationships eagerly with selectinload.
    stmt = select(User).options(selectinload(User.addresses)).order_by(User.name)
    async with async_session() as session:
        return list(await session.scalars(stmt))


async def add_user(name: str, fullname: str) -> None:
    async with async_session() as session:
        session.add(User(name=name, fullname=fullname or None))
        await session.commit()


async def add_address(user_id: int, email_address: str) -> None:
    async with async_session() as session:
        session.add(Address(user_id=user_id, email_address=email_address))
        await session.commit()


async def rename_address(address_id: int, email_address: str) -> None:
    async with async_session() as session:
        address = await session.get(Address, address_id)
        address.email_address = email_address
        await session.commit()


async def delete_user(user_id: int) -> None:
    async with async_session() as session:
        user = await session.get(User, user_id, options=[selectinload(User.addresses)])
        await session.delete(user)
        await session.commit()
