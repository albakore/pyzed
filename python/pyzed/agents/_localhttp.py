"""The small HTTP servers Pyzed runs on ``127.0.0.1`` (the editor's MCP server for external agents, the
sign-in callbacks), quiet about clients that drop their connection.

Agents and browsers close idle keep-alive connections whenever they like; on Windows that arrives as a
reset (``ConnectionResetError: [WinError 10054]``) while the server waits for the next request.
``http.server`` prints a traceback for it, though nothing went wrong, so these servers skip it; any other
error goes to the ``pyzed.agents.http`` log with its traceback instead of the console.
"""

from __future__ import annotations

import http.server
import logging
import sys
from typing import Any

#: A client that went away: not an error of the server.
DROPPED = (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError)

_log = logging.getLogger("pyzed.agents.http")


class _Quiet:
    def handle_error(self, request: Any, client_address: Any) -> None:
        error = sys.exc_info()[1]
        if isinstance(error, DROPPED):
            return
        _log.warning("Error answering a request from %s", client_address[0], exc_info=True)


class HTTPServer(_Quiet, http.server.HTTPServer):
    """``http.server.HTTPServer`` that does not print dropped connections."""


class ThreadingHTTPServer(_Quiet, http.server.ThreadingHTTPServer):
    """``http.server.ThreadingHTTPServer`` that does not print dropped connections."""
