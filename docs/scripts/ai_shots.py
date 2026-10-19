"""Renders the screenshots of the AI agents pages (docs/src/assets/ai) from examples/ai_chat.py.

    python docs/scripts/ai_shots.py

The chat is driven with its demo stream (no network): the prompt is sent, the async generator runs to the
middle of the answer (``ai-chat-streaming.png``) and then to the end (``ai-chat.png``).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "src" / "assets" / "ai"
sys.path.insert(0, str(ROOT / "examples"))

import ai_chat  # noqa: E402


def drive(app, prompt, *, stop_after=None):
    """Sends ``prompt`` and feeds what the reply yields to ``update``, like Pyzed's loop does."""
    effects = app.send(prompt)
    reply = next(e for e in effects if hasattr(e, "__aiter__"))

    async def run():
        count = 0
        async for message in reply:
            app.update(message)
            count += 1
            if stop_after is not None and count >= stop_after:
                return

    asyncio.run(run())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    app = ai_chat.AIChat(stream=lambda m: ai_chat.demo_stream(m, delay=0))
    app.screenshot(OUT / "ai-chat-empty.png", size=(980, 720), scale=2)
    drive(app, ai_chat.SUGGESTIONS[0][1])
    app.screenshot(OUT / "ai-chat.png", size=(980, 720), scale=2)
    app = ai_chat.AIChat(stream=lambda m: ai_chat.demo_stream(m, delay=0))
    drive(app, ai_chat.SUGGESTIONS[0][1], stop_after=45)
    app.screenshot(OUT / "ai-chat-streaming.png", size=(980, 720), scale=2)
    for name in ("ai-chat-empty", "ai-chat", "ai-chat-streaming"):
        print("wrote", (OUT / f"{name}.png").relative_to(ROOT))


if __name__ == "__main__":
    main()
