"""The form's rules, written as Pydantic models (https://docs.pydantic.dev/latest/concepts/models/)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, SecretStr, TypeAdapter, field_validator, model_validator


class SignUp(BaseModel):
    username: str = Field(min_length=3, max_length=20, pattern=r"^[a-z0-9_]+$")
    email: EmailStr
    birthday: date
    plan: Literal["free", "pro", "team"] = "free"
    password: SecretStr  # repr() and str() show ********
    password_repeat: SecretStr
    newsletter: bool = False

    @field_validator("username", mode="before")
    @classmethod
    def lowercase(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("birthday")
    @classmethod
    def old_enough(cls, value: date) -> date:
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 13:
            raise ValueError("You must be at least 13 years old")
        return value

    @field_validator("password")
    @classmethod
    def long_enough(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 8:
            raise ValueError("Use 8 characters or more")
        return value

    @model_validator(mode="after")
    def passwords_match(self) -> SignUp:
        if self.password.get_secret_value() != self.password_repeat.get_secret_value():
            raise ValueError("The passwords don't match")
        return self


class Account(BaseModel):
    """What gets saved: the sign-up without the passwords."""

    username: str
    email: EmailStr
    birthday: date
    plan: Literal["free", "pro", "team"]
    newsletter: bool


Accounts = TypeAdapter(list[Account])  # validates and serializes a whole list at once
