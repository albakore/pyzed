"""Records the animations of the Routing section (docs/public/media/routing/*.webp).

    uv run python docs/scripts/routing_media.py [names...]

Each clip is the store of ``examples/routing`` driven like a user would: real clicks on its links and
buttons, while its pretend backend (``api.py``) takes a moment to answer, so the loading files,
the middleware, the actions and the global state show up as they do in the app. The pictures of a
single moment are ``routing_shots.py``; the native notification is ``routing_notification.py``.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "docs" / "public" / "media" / "routing"
sys.path.insert(0, str(ROOT / "examples" / "routing"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import api  # noqa: E402
from anim_webp import call, hover, key, press, record_webp, wait  # noqa: E402
from main import Store  # noqa: E402

SIZE = (1040, 620)
TOGGLE = (1014, 20)  # the sidebar button, top right


def settle(seconds: float = 0.5):
    """Lets the pretend backend answer (real time passes; the clip's clock doesn't)."""
    def run(app):
        time.sleep(seconds)
        app.router.wait()
        time.sleep(0.05)

    run.__name__ = "settle"
    return call(run)


def fresh(url: str = "/", **changes):
    """A new store at ``url``, with the global state reset."""
    from state import cart, session

    cart.reset()
    session.reset()
    for name, value in changes.items():
        setattr(session if name == "user" else cart, name, value)
    app = Store()
    app.router.replace(url)
    if url != "/":
        app.router.prefetch(url)
        app.router.wait()
    return app


def navigation():
    return fresh("/"), [
        wait(700), hover("Products", 450, 250), press(after=0), wait(500), settle(), wait(900),
        hover("4K monitor", 500, 250), press(after=0), wait(500), settle(), wait(1000),
        key("Left", "alt"), wait(900), hover("Docs", 500, 250), press(after=0), wait(900),
        hover("Settings", 450, 250), press(after=0), wait(1200),
    ]


def middleware():
    return fresh("/"), [
        wait(700), hover("Account", 500, 300), press(after=0), wait(1200),
        hover("Sign in#1", 500, 300), press(after=0), wait(500), settle(0.6), wait(1600),
    ]


def actions():
    return fresh("/products/2"), [
        wait(700), hover("Add to cart", 500, 300), press(after=0), wait(450), settle(0.5), wait(900),
        press(after=0), wait(450), settle(0.5), wait(900), hover("Account", 500, 300), wait(900),
    ]


def loading():
    return fresh("/products"), [
        wait(500), hover("Headphones", 450, 250), press(after=0), wait(700), settle(), wait(1300),
    ]


def errors():
    api.FLAKY.add("6")
    return fresh("/products"), [
        wait(500), hover("Desk lamp", 450, 250), press(after=0), wait(500), settle(), wait(1400),
        hover("Try again", 450, 300), press(after=0), wait(500), settle(), wait(1400),
    ]


def layouts():
    return fresh("/settings/profile"), [
        wait(600), hover("Clicked 0 times", 450, 200), press(after=200), press(after=200), wait(500),
        hover(TOGGLE, 600, 300), press(after=300), wait(500),
        hover("Notifications", 600, 300), press(after=0), wait(1200),
        hover("Profile", 500, 300), press(after=0), wait(1200),
        hover(TOGGLE, 600, 300), press(after=300), wait(800),
    ]


CLIPS = {"navigation": navigation, "middleware": middleware, "actions": actions, "loading": loading,
         "errors": errors, "layouts": layouts}


def main(names) -> None:
    MEDIA.mkdir(parents=True, exist_ok=True)
    api.DELAY = 0.3
    for name in names or CLIPS:
        app, steps = CLIPS[name]()
        out = MEDIA / f"{name}.webp"
        result = record_webp(app, steps, out=out, size=SIZE, scale=1, fps=15, quality=82)
        print(f"{out.relative_to(ROOT)}: {result['bytes'] // 1024} KB, {result['unique']} frames")


if __name__ == "__main__":
    main(sys.argv[1:])
