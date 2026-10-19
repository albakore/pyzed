"""Renders the screenshots of the integration demos (docs/src/assets/integrations).

    uv run --with "fastapi[standard]" --with httpx --with "sqlalchemy[asyncio]" --with sqlmodel \\
        --with django --with aiosqlite --with "pydantic[email]" python docs/scripts/integration_shots.py [names...]

Each demo is imported from examples/integrations/<name>, driven to an interesting state with its
own methods and drawn off-screen with ``App.screenshot``. The httpx ones need internet access.
Databases are created in a temporary folder, so the demos' own files are left alone.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
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
    for name in ("main", "db", "models", "api", "pypi", "heroes_window", "sync_backend", "polls_window", "desktop"):  # demos reuse these module names
        sys.modules.pop(name, None)
    return [importlib.import_module(m) for m in modules]


def fastapi():
    import httpx as _httpx

    (api, window) = load("fastapi_heroes", "main", "heroes_window")
    api.create_db_and_tables()
    transport = _httpx.ASGITransport(app=api.app)
    app = window.HeroesWindow(lambda: _httpx.AsyncClient(transport=transport, base_url="http://heroes"),
                              mode="in process")
    for name, secret, age in [("Deadpond", "Dive Wilson", ""), ("Spider-Boy", "Pedro Parqueador", ""),
                              ("Rusty-Man", "Tommy Sharp", "48"), ("Black Lion", "Trevor Challa", "35")]:
        app.draft.update(name=name, secret_name=secret, age=age)
        app.update(run(app.update(run(app.save()))))  # "saved" returns the reload coroutine
        app.pick(None)
    app.pick(next(h for h in app.heroes if h["name"] == "Rusty-Man"))
    app.draft["age"] = "forty"
    app.update(run(app.save()))
    return app


def django():
    (desktop,) = load("django_polls", "desktop")
    from django.core.management import call_command

    call_command("migrate", verbosity=0)
    for text, choices in [("What's your favorite Python GUI library?", ["Pyzed", "Tkinter", "Qt", "Kivy"]),
                          ("Which backend do you use?", ["FastAPI", "Django", "Flask"])]:
        desktop.create.__wrapped__({"question_text": text, "choices": choices})
    questions = desktop.load()
    first = questions[-1]
    for choice, votes in zip(first["choices"], [9, 3, 5, 2]):
        for _ in range(votes):
            desktop.vote.__wrapped__(first["id"], choice["id"])
    app = desktop.PollsWindow(desktop.load, desktop.vote, desktop.create, mode="Django ORM, same process")
    app.loaded(desktop.load())
    app.selected_id = first["id"]
    return app


def sqlalchemy_quickstart():
    main, backend = load("sqlalchemy_quickstart", "main", "sync_backend")
    backend.setup()
    app = main.Quickstart()
    app.loaded(backend.users())
    app.selected_id = next(u.id for u in app.users if u.name == "sandy")
    app.new_email = "sandy@treedome.example"
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


def sqlmodel_heroes():
    main, db = load("sqlmodel_heroes", "main", "db")
    db.setup()
    app = main.Heroes()
    app.teams, app.heroes = db.teams(), db.heroes("all", None)
    app.open(next(h for h in app.heroes if h.name == "Spider-Boy"))
    app.draft.update(secret_name="", age="fifteen")
    app.save()
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


def httpx():
    (main,) = load("httpx_pypi", "main")
    app = main.Explorer(main.DEFAULT)

    async def stream():
        async for item in app.on_start():
            app.update(item)

    run(stream())
    app.selected = "fastapi"
    return app


def httpx_download():
    (main,) = load("httpx_download", "main")
    app = main.Downloads()
    app.url = main.EXAMPLE.replace("numpy-2.1.0", "numpy-2.1.1")

    async def until(item, fraction):
        async for _ in main.download(item):
            if item.total and item.done >= fraction * item.total:
                item.cancel = True

    done, running = main.Download(main.EXAMPLE), main.Download(main.EXAMPLE)
    done.name, running.name = "numpy-2.1.0.tar.gz", "numpy-2.1.0 (copy).tar.gz"
    run(until(done, 2))
    run(until(running, 0.42))
    running.state, running.speed = "downloading", 4.2 * 1024 * 1024
    failed = main.Download("https://files.pythonhosted.org/packages/missing.whl")
    run(until(failed, 2))
    app.items = [running, failed, done]
    return app


def pydantic():
    (main,) = load("pydantic_signup", "main")
    app = main.SignUpForm()
    app.draft.update(username="sandy", email="sandy@example.com", birthday="1992-07-14", password="acorns-123",
                     password_repeat="acorns-123", plan="pro", newsletter=True)
    app.submit()
    app.draft.update(username="Pa", email="patrick@", birthday="2019-01-01", password="star",
                     password_repeat="star")
    app.submit()
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


SHOTS = {"fastapi": fastapi, "django": django, "sqlalchemy-quickstart": sqlalchemy_quickstart,
         "sqlalchemy": sqlalchemy, "sqlmodel-heroes": sqlmodel_heroes, "sqlmodel": sqlmodel, "httpx": httpx,
         "httpx-download": httpx_download, "pydantic": pydantic, "aiosqlite": aiosqlite}


def main(names):
    names = names or list(SHOTS)
    if len(names) > 1:  # one process per demo: SQLModel's tables are global, and so is Django's setup
        for name in names:
            subprocess.run([sys.executable, __file__, name], check=True)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    app = SHOTS[names[0]]()
    app.screenshot(OUT / f"{names[0]}.png", size=app.size, scale=2, wait=0.3)
    print(f"wrote docs/src/assets/integrations/{names[0]}.png")


if __name__ == "__main__":
    main(sys.argv[1:])
