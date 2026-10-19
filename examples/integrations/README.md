# Integrations

Desktop apps built with Pyzed on top of backend and data libraries. Each folder is a
[uv](https://docs.astral.sh/uv/) project:

```bash
cd examples/integrations/fastapi_notes
uv run main.py
```

| Folder | Libraries | What it shows |
| --- | --- | --- |
| [`fastapi_notes`](fastapi_notes) | FastAPI, uvicorn, httpx | A client for a REST API with the server embedded in the same process; 422 errors on each field. |
| [`sqlalchemy_contacts`](sqlalchemy_contacts) | SQLAlchemy 2.0 | 20,000 rows in a virtual table, searched and sorted in SQL from a worker thread. |
| [`sqlmodel_inventory`](sqlmodel_inventory) | SQLModel, Pydantic | One model validates the form and defines the table. |
| [`django_library`](django_library) | Django | Django's async ORM and `full_clean()` in a desktop app that shares its data with the admin. |
| [`httpx_pypi`](httpx_pypi) | httpx, Pydantic | Concurrent requests streamed into the window and parsed into models. |
| [`aiosqlite_journal`](aiosqlite_journal) | aiosqlite | An async SQLite connection on Pyzed's event loop. |

Inside this repository the demos use your checkout of Pyzed (`[tool.uv.sources]` in each
`pyproject.toml`). To start your own app from one, copy the folder and delete those two lines.

Walkthroughs: https://albakore.github.io/pyzed/integrations/overview/
