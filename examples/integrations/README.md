# Integrations

Desktop apps built with Pyzed on top of backend and data libraries. Each folder is a
[uv](https://docs.astral.sh/uv/) project:

```bash
cd examples/integrations/sqlmodel_heroes
uv run main.py
```

| Folder | Libraries | What it shows | Run |
| --- | --- | --- | --- |
| [`fastapi_heroes`](fastapi_heroes) | FastAPI, SQLModel, httpx | FastAPI's SQL tutorial API and a desktop client for it, run three ways: separate server, embedded server and in-process. | `uv run fastapi dev main.py · uv run client.py` |
| [`django_polls`](django_polls) | Django, httpx | Django's polls tutorial, used from a window through the ORM in the same process or over HTTP while runserver runs. | `uv run manage.py migrate · uv run desktop.py` |
| [`sqlalchemy_quickstart`](sqlalchemy_quickstart) | SQLAlchemy 2.0, aiosqlite | The ORM Quick Start's users and addresses, with a sync Session in threads or an AsyncSession on the loop. | `uv run main.py [--async]` |
| [`sqlalchemy_contacts`](sqlalchemy_contacts) | SQLAlchemy 2.0 | 20,000 rows in a virtual table, searched and sorted in SQL from a worker thread. | `uv run main.py` |
| [`sqlmodel_heroes`](sqlmodel_heroes) | SQLModel | SQLModel's tutorial: teams, heroes, where() filters, relationships and a validated form. | `uv run main.py` |
| [`sqlmodel_inventory`](sqlmodel_inventory) | SQLModel, Pydantic | One model validates the form and defines the table. | `uv run main.py` |
| [`httpx_pypi`](httpx_pypi) | httpx, Pydantic | Concurrent requests streamed into the window and parsed into models. | `uv run main.py` |
| [`httpx_download`](httpx_download) | httpx | Streaming downloads with progress bars and cancel. | `uv run main.py` |
| [`pydantic_signup`](pydantic_signup) | Pydantic | A sign-up form validated by a model, saved and loaded as JSON. | `uv run main.py` |
| [`aiosqlite_journal`](aiosqlite_journal) | aiosqlite | An async SQLite connection on Pyzed's event loop. | `uv run main.py` |

Inside this repository the demos use your checkout of Pyzed (`[tool.uv.sources]` in each
`pyproject.toml`). To start your own app from one, copy the folder and delete those two lines.

Walkthroughs: https://albakore.github.io/pyzed/integrations/overview/
