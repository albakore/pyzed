"""Desktop client for the Django site over HTTP: the site runs on its own, the window uses its JSON API.

    uv run manage.py runserver        # terminal 1: the site (http://127.0.0.1:8000/polls/)
    uv run client.py                  # terminal 2: the window
    uv run client.py https://polls.example.com

Use this when the site is deployed on a server and the desktop app is one more client. The
window needs no Django and no database, only httpx.
"""

import sys

import httpx

import pyzed as pz

from polls_window import PollsWindow

SITE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


async def load():
    try:
        async with httpx.AsyncClient(base_url=SITE, timeout=5) as client:
            response = await client.get("/polls/api/questions/")
            response.raise_for_status()
    except httpx.HTTPError as error:
        return f"Can't reach {SITE}: {error or type(error).__name__}"
    return response.json()["questions"]


async def vote(question_id, choice_id):
    try:
        async with httpx.AsyncClient(base_url=SITE, timeout=5) as client:
            response = await client.post(f"/polls/api/questions/{question_id}/vote/", json={"choice": choice_id})
            response.raise_for_status()
    except httpx.HTTPError as error:
        return f"The vote failed: {error or type(error).__name__}"
    return response.json()


if __name__ == "__main__":
    pz.run(PollsWindow(load, vote, mode=f"HTTP client of {SITE}"))
