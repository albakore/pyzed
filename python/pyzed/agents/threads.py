"""Saved conversations ("threads"), kept as JSON on this computer.

Each thread is one file in ``agents/threads`` inside the Pyzed config folder. Threads hold the
messages and the model only; keys never go there.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

#: Threads kept; older ones are deleted when a new one is saved.
KEEP = 200


@dataclass
class Thread:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    model: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    @property
    def display_title(self) -> str:
        """The title, or the start of the first message."""
        if self.title:
            return self.title
        for m in self.messages:
            if m.get("role") == "user":
                text = "".join(b.get("text", "") for b in m.get("content", []) if b.get("type") == "text").strip()
                if text:
                    first = text.splitlines()[0]
                    return first if len(first) <= 60 else first[:57] + "…"
        return "New thread"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Thread":
        messages = data.get("messages")
        return cls(id=str(data.get("id") or uuid.uuid4().hex[:12]), title=str(data.get("title") or ""),
                   model=str(data.get("model") or ""), messages=messages if isinstance(messages, list) else [],
                   created=float(data.get("created") or time.time()), updated=float(data.get("updated") or time.time()))


class ThreadStore:
    """Reads and writes threads in a folder (``agents/threads`` in the config folder by default)."""

    def __init__(self, folder: Optional[Path] = None) -> None:
        if folder is None:
            from ..designer.settings import config_dir

            folder = config_dir() / "agents" / "threads"
        self.folder = Path(folder)

    def _path(self, thread_id: str) -> Path:
        return self.folder / f"{''.join(c for c in thread_id if c.isalnum())}.json"

    def save(self, thread: Thread) -> Optional[Path]:
        """Writes ``thread``; ``None`` when the folder is not writable."""
        thread.updated = time.time()
        path = self._path(thread.id)
        try:
            self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
            text = json.dumps(thread.to_dict(), ensure_ascii=False)
            # Threads can hold project code and files the agent read: only the user may read them.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                file.write(text)
            os.chmod(path, 0o600)
        except (OSError, TypeError, ValueError):
            return None
        self._prune()
        return path

    def load(self, thread_id: str) -> Optional[Thread]:
        try:
            data = json.loads(self._path(thread_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return Thread.from_dict(data) if isinstance(data, dict) else None

    def delete(self, thread_id: str) -> None:
        try:
            self._path(thread_id).unlink()
        except OSError:
            pass

    def list(self) -> List[Thread]:
        """Every saved thread, most recently updated first."""
        out = []
        try:
            paths = list(self.folder.glob("*.json"))
        except OSError:
            return []
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict):
                out.append(Thread.from_dict(data))
        return sorted(out, key=lambda t: t.updated, reverse=True)

    def _prune(self) -> None:
        threads = self.list()
        for old in threads[KEEP:]:
            self.delete(old.id)
