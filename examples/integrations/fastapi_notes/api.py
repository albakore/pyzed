"""The REST API: a FastAPI app with Pydantic models, kept in memory.

    uv run uvicorn api:app --reload        # serve it on its own (http://127.0.0.1:8000/docs)
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator


class NoteIn(BaseModel):
    """What the client sends. FastAPI answers 422 with the details when it doesn't validate."""

    title: str = Field(min_length=1, max_length=60)
    body: str = ""
    tags: list[str] = []

    @field_validator("tags")
    @classmethod
    def short_tags(cls, tags: list[str]) -> list[str]:
        if any(len(tag) > 16 for tag in tags):
            raise ValueError("each tag must be 16 characters or fewer")
        return tags


class Note(NoteIn):
    id: int
    updated: datetime


app = FastAPI(title="Notes API")
_notes: dict[int, Note] = {}
_lock = threading.Lock()


def _save(note_id: int, data: NoteIn) -> Note:
    note = Note(id=note_id, updated=datetime.now(timezone.utc), **data.model_dump())
    with _lock:
        _notes[note_id] = note
    return note


@app.get("/notes")
def list_notes(q: str = "") -> list[Note]:
    q = q.lower()
    with _lock:
        notes = list(_notes.values())
    found = [n for n in notes if q in n.title.lower() or q in n.body.lower() or any(q in t for t in n.tags)]
    return sorted(found, key=lambda n: n.updated, reverse=True)


@app.post("/notes", status_code=201)
def create_note(data: NoteIn) -> Note:
    with _lock:
        note_id = max(_notes, default=0) + 1
    return _save(note_id, data)


@app.put("/notes/{note_id}")
def update_note(note_id: int, data: NoteIn) -> Note:
    if note_id not in _notes:
        raise HTTPException(404, "Note not found")
    return _save(note_id, data)


@app.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int) -> None:
    with _lock:
        if _notes.pop(note_id, None) is None:
            raise HTTPException(404, "Note not found")


for title, body, tags in [
    ("Welcome", "# Welcome\n\nThese notes live in a **FastAPI** server.", ["pyzed", "fastapi"]),
    ("Shopping", "- Coffee\n- Bread", ["home"]),
    ("Ideas", "Write a desktop client for every API.", []),
]:
    create_note(NoteIn(title=title, body=body, tags=tags))
