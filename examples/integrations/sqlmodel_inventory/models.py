"""SQLModel models: one class is both the Pydantic schema and the database table."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

CATEGORIES = ["Keyboards", "Mice", "Monitors", "Audio", "Cables"]

engine = create_engine(f"sqlite:///{Path(__file__).with_name('inventory.db')}")


class ProductBase(SQLModel):
    """The fields and their rules, shared by the form and the table."""

    name: str = Field(min_length=2, max_length=60)
    sku: str
    category: str = "Keyboards"
    price: float = Field(gt=0)
    stock: int = Field(ge=0)

    @field_validator("sku")
    @classmethod
    def sku_format(cls, sku: str) -> str:
        sku = sku.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}-\d{4}", sku):
            raise ValueError("Expected something like KEY-0001")
        return sku


class Product(ProductBase, table=True):
    # Table models skip validation on purpose (SQLAlchemy builds them); validate with ProductIn first.
    id: int | None = Field(default=None, primary_key=True)
    sku: str = Field(unique=True, index=True)


class ProductIn(ProductBase):
    """Validates what the form typed: "12.5" becomes 12.5, "abc" becomes an error on that field."""


def setup() -> None:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        if session.exec(select(Product)).first():
            return
        session.add_all([
            Product(name="Mechanical keyboard", sku="KEY-0001", category="Keyboards", price=129.0, stock=14),
            Product(name="Low-profile keyboard", sku="KEY-0002", category="Keyboards", price=89.5, stock=3),
            Product(name="Wireless mouse", sku="MOU-0001", category="Mice", price=49.9, stock=40),
            Product(name="Vertical mouse", sku="MOU-0002", category="Mice", price=59.0, stock=0),
            Product(name='27" 4K monitor', sku="MON-0001", category="Monitors", price=399.0, stock=6),
            Product(name='34" ultrawide', sku="MON-0002", category="Monitors", price=649.0, stock=2),
            Product(name="Studio headphones", sku="AUD-0001", category="Audio", price=149.0, stock=11),
            Product(name="USB microphone", sku="AUD-0002", category="Audio", price=99.0, stock=7),
            Product(name="USB-C cable 2 m", sku="CAB-0001", category="Cables", price=12.0, stock=120),
            Product(name="HDMI 2.1 cable", sku="CAB-0002", category="Cables", price=18.0, stock=4),
        ])
        session.commit()


def products() -> list[Product]:
    with Session(engine) as session:
        return list(session.exec(select(Product).order_by(Product.category, Product.name)))


def save(product_id: int | None, data: ProductIn) -> Product | dict:
    """Stores validated data; returns ``{field: message}`` when the SKU is taken."""
    with Session(engine, expire_on_commit=False) as session:
        clash = session.exec(select(Product).where(Product.sku == data.sku, Product.id != product_id)).first()
        if clash:
            return {"sku": f"Already used by “{clash.name}”"}
        product = session.get(Product, product_id) if product_id else Product.model_validate(data)
        product.sqlmodel_update(data.model_dump())
        session.add(product)
        session.commit()
        return product


def restock(product_id: int, amount: int) -> None:
    with Session(engine) as session:
        product = session.get(Product, product_id)
        product.stock = max(0, product.stock + amount)
        session.add(product)
        session.commit()
