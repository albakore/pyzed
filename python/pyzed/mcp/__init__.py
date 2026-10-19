"""An MCP server that teaches AI agents Pyzed: how it works, its components and best practices.

    pip install "pyzed-ui[mcp]"
    pyzed mcp                      # or: python -m pyzed.mcp

It speaks MCP over stdio. Tools list and describe every widget and component, search icons and
themes, read the documentation and the examples, generate apps, components and designer forms,
check code and forms, and render code to a screenshot. ``knowledge``, ``scaffold`` and
``validate`` are plain Python and work without the MCP SDK.
"""

from __future__ import annotations

from . import knowledge, scaffold, validate

__all__ = ["create", "knowledge", "main", "scaffold", "validate"]


def create():
    """Builds the MCP server (needs the ``mcp`` package)."""
    from .server import create as _create

    return _create()


def main(transport: str = "stdio") -> int:
    """Runs the MCP server until the client disconnects. Returns the exit code."""
    try:
        from .server import main as _main
    except ImportError as err:
        import sys

        print(f"error: the MCP server needs the MCP SDK ({err}); install it with: pip install \"pyzed-ui[mcp]\"",
              file=sys.stderr)
        return 1
    _main(transport)
    return 0
