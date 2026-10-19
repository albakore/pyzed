"""Renders the screenshots of the integration demos (docs/src/assets/integrations).

    uv run --with fastapi --with uvicorn --with httpx --with sqlalchemy --with sqlmodel \\
        --with django --with aiosqlite python docs/scripts/integration_shots.py [names...]

Each demo is imported from examples/integrations/<name>, driven to an interesting state with its
own methods and drawn off-screen with ``App.screenshot``. The httpx one needs internet access.
Databases are created in a temporary folder, so the demos' own files are left alone.
"""

from __future__ import annotations

import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMOS = ROOT / "examples" / "integrations"
OUT = ROOT / "docs" / "src" / "assets" / "integrations"

from pyzed import _async  # noqa: E402

run = _async.run


def load(demo: str, *modules: str):
    """Copies the demo to a temporary folder (its databases go there) and imports its modules."""
    folder = Path(tempfile.mkdtemp()) / demo
    shutil.copytree(DEMOS / demo, folder, ignore=shutil.ignore_patterns("*.db", "*.sqlite3", ".venv", "__pycache__"))
    os.chdir(folder)
    sys.path.insert(0, str(folder))
    for name in ("main", "db", "models", "api", "pypi"):  # demos reuse these module names
        sys.modules.pop(name, None)
    return [importlib.import_module(m) for m in modules]


def fastapi():
    (main,) = load("fastapi_notes", "main")
    app = main.NotesClient(main.serve_in_background())
    app.update(run(app.fetch("")))
    app.open_note(next(n for n in app.notes if n["title"] == "Welcome"))
    app.draft.update(title="", tags="pyzed, a-tag-that-is-far-too-long")
    app.update(run(app.send(app.selected, {"title": "", "body": app.draft["body"],
                                           "tags": ["pyzed", "a-tag-that-is-far-too-long"]})))
    return app


def sqlalchemy():
    main, db = load("sqlalchemy_contacts", "main", "db")
    db.setup()
    app = main.Contacts()
    app.loaded("", db.search("", "Name", False))
    app.stats = db.stats()
    app.open(app.rows[5])
    app.draft["email"] = app.rows[6].email
    app.saved(db.save(app.rows[5].id, dict(app.draft)))
    return app


def sqlmodel():
    main, models = load("sqlmodel_inventory", "main", "models")
    models.setup()
    app = main.Inventory()
    app.loaded(models.products())
    app.open(next(p for p in app.products if p.sku == "MON-0001"))
    app.draft.update(sku="mon1", price="abc", stock="-3")
    app.save()
    return app


def django():
    (main,) = load("django_library", "main")
    main.prepare_database()
    app = main.Library()
    app.update(run(app.reload()))
    run(app.set_available(next(b for b in app.books if b.title == "El Aleph").pk, False))
    app.update(run(app.reload()))
    app.open("new")
    app.draft.update(title="Ficciones", year="1944a", isbn=next(b for b in app.books if b.title == "Ficciones").isbn)
    app.update(run(app.save()))
    return app


def httpx():
    (main,) = load("httpx_pypi", "main")
    app = main.Explorer(main.DEFAULT)

    async def stream():
        async for item in app.on_start():
            app.update(item)

    run(stream())
    app.selected = "fastapi"
    return app


def aiosqlite():
    (main,) = load("aiosqlite_journal", "main")
    app = main.Journal()
    app.update(run(app.on_start()))
    for text, mood in [("Shipped the FastAPI demo", "great"), ("Long meeting, little code", "okay"),
                       ("The build broke twice", "rough"), ("Pair-programmed the Django tutorial", "great")]:
        app.update(run(app.add(text, mood)))
    app.mood, app.text = "okay", "Writing the docs"
    return app


SHOTS = {"fastapi": fastapi, "sqlalchemy": sqlalchemy, "sqlmodel": sqlmodel, "django": django,
         "httpx": httpx, "aiosqlite": aiosqlite}


def main(names):
    OUT.mkdir(parents=True, exist_ok=True)
    for name, make in SHOTS.items():
        if names and name not in names:
            continue
        app = make()
        app.screenshot(OUT / f"{name}.png", size=app.size, scale=2, wait=0.3)
        print(f"wrote docs/src/assets/integrations/{name}.png")


if __name__ == "__main__":
    main(sys.argv[1:])
