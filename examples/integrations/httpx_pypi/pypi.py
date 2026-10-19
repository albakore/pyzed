"""PyPI's JSON API, described with Pydantic models and fetched with httpx."""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime
from typing import AsyncIterator

import httpx
from pydantic import BaseModel, ValidationError


class Info(BaseModel):
    name: str
    version: str
    summary: str | None = None
    license: str | None = None
    license_expression: str | None = None  # newer packages declare an SPDX expression instead
    requires_python: str | None = None
    project_urls: dict[str, str] | None = None


class File(BaseModel):
    upload_time_iso_8601: datetime
    yanked: bool = False


class Package(BaseModel):
    """Only the fields the app shows; Pydantic ignores the rest of the response."""

    info: Info
    releases: dict[str, list[File]]

    def history(self) -> list[tuple[str, datetime]]:
        """(version, first upload) for every release with files, newest first."""
        dated = [(version, min(f.upload_time_iso_8601 for f in files)) for version, files in self.releases.items() if files]
        return sorted(dated, key=lambda item: item[1], reverse=True)

    def per_year(self, years: int = 8) -> list[tuple[int, int]]:
        counts = Counter(date.year for _, date in self.history())
        last = datetime.now().year
        return [(year, counts.get(year, 0)) for year in range(last - years + 1, last + 1)]


async def fetch(client: httpx.AsyncClient, name: str) -> Package | str:
    """The package, or a short message saying why it couldn't be loaded."""
    try:
        response = await client.get(f"https://pypi.org/pypi/{name}/json")
    except httpx.HTTPError as error:
        return f"Network error: {error or type(error).__name__}"
    if response.status_code == 404:
        return "Not on PyPI"
    if response.is_error:
        return f"PyPI answered {response.status_code}"
    try:
        return Package.model_validate_json(response.content)
    except ValidationError as error:
        return f"Unexpected response: {error.error_count()} problems"


async def fetch_all(names: list[str]) -> AsyncIterator[tuple[str, Package | str]]:
    """Requests every package at once and yields each one as soon as it arrives."""
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        async def one(name):
            return name, await fetch(client, name)

        for done in asyncio.as_completed([one(n) for n in names]):
            yield await done
