"""Signing in with the browser instead of typing a key. Nothing here needs another program.

* OpenRouter (``login="oauth"``): OAuth with PKCE. Pyzed opens the browser on OpenRouter's consent page,
  receives the code on a one-shot server bound to ``127.0.0.1``, exchanges it for a key and saves the key
  in the system keychain.
* Anthropic, OpenAI, Gemini, xAI, Mistral, DeepSeek, Groq (``login="browser"``): these providers do not
  let other apps sign in with OAuth, so Pyzed opens their key page (``key_page``) and the designer picks
  the key up as soon as it is copied (``providers.looks_like_key``), checks it and saves it in the keychain.
* An Anthropic CLI profile (``ant auth login``), when one exists, is still used by the ``anthropic`` SDK;
  it is optional.

``openrouter_login`` blocks, so the designer runs it in a worker thread.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets as _random
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Callable, List, Optional

OPENROUTER_AUTH = "https://openrouter.ai/auth"
OPENROUTER_EXCHANGE = "https://openrouter.ai/api/v1/auth/keys"
#: Seconds to wait for the browser to come back.
TIMEOUT = 300.0


class LoginError(RuntimeError):
    """Signing in did not finish (cancelled, timed out, refused or the tool is missing)."""


# -- Anthropic CLI (optional) --------------------------------------------------------------------

def ant_path() -> Optional[str]:
    """The ``ant`` executable, if installed."""
    return shutil.which("ant")


def ant_config_dir() -> Path:
    """Where the Anthropic CLI keeps its profiles."""
    if os.environ.get("ANTHROPIC_CONFIG_DIR"):
        return Path(os.environ["ANTHROPIC_CONFIG_DIR"])
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "Anthropic"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "anthropic"


def ant_signed_in() -> bool:
    """Whether an Anthropic CLI profile with credentials exists on this computer."""
    folder = ant_config_dir() / "credentials"
    try:
        return any(p.suffix == ".json" for p in folder.iterdir())
    except OSError:
        return False


def ant_login(*, run: Callable[..., "subprocess.CompletedProcess"] = subprocess.run) -> None:
    """Runs ``ant auth login`` (it opens the browser) and waits for it to finish."""
    exe = ant_path()
    if exe is None:
        raise LoginError("The Anthropic CLI (ant) is not installed. Install it, or paste an API key instead.")
    result = run([exe, "auth", "login"], capture_output=True, text=True, timeout=TIMEOUT)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        raise LoginError(detail[-1] if detail else "ant auth login failed")


def ant_logout(*, run: Callable[..., "subprocess.CompletedProcess"] = subprocess.run) -> None:
    """Runs ``ant auth logout`` (clears the active profile)."""
    exe = ant_path()
    if exe is not None:
        run([exe, "auth", "logout"], capture_output=True, text=True, timeout=60)


# -- OAuth with PKCE (OpenRouter) ----------------------------------------------------------------

def pkce_pair() -> "tuple[str, str]":
    """A random code verifier and its S256 challenge."""
    verifier = base64.urlsafe_b64encode(_random.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


_PAGE = """<!doctype html><meta charset="utf-8"><title>Pyzed</title>
<body style="font-family:system-ui;background:#282c34;color:#dce0e5;display:grid;place-items:center;height:90vh">
<div style="text-align:center"><h2>{title}</h2><p>{text}</p></div></body>"""


class _Callback(http.server.BaseHTTPRequestHandler):
    codes: List[str]
    errors: List[str]
    #: The callback's path, with a random part only this sign-in knows (it plays OAuth's ``state``).
    path_secret: str

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        url = urllib.parse.urlparse(self.path)
        if url.path != self.path_secret:
            # Anything else (a favicon, another page, a forged callback) neither signs in nor cancels.
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        query = urllib.parse.parse_qs(url.query)
        if "code" in query:
            self.codes.append(query["code"][0])
            body = _PAGE.format(title="Signed in", text="You can close this tab and go back to Pyzed.")
        else:
            self.errors.append((query.get("error") or ["cancelled"])[0])
            body = _PAGE.format(title="Not signed in", text="Pyzed did not get access. You can close this tab.")
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:  # silence the default stderr logging
        pass


def wait_for_code(open_url: Callable[[str], None], build_url: Callable[[str], str], *,
                  timeout: float = TIMEOUT) -> str:
    """Starts a one-shot server on ``127.0.0.1``, opens ``build_url(callback)`` and returns the ``code``
    the browser brings back."""
    path = f"/callback/{_random.token_urlsafe(16)}"
    handler = type("Callback", (_Callback,), {"codes": [], "errors": [], "path_secret": path})
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    server.timeout = 0.5
    callback = f"http://localhost:{server.server_address[1]}{path}"
    try:
        open_url(build_url(callback))
        deadline = time.monotonic() + timeout
        while not handler.codes and not handler.errors:
            if time.monotonic() > deadline:
                raise LoginError("Timed out waiting for the browser")
            server.handle_request()
    finally:
        server.server_close()
    if handler.errors:
        raise LoginError(f"Sign-in was not completed ({handler.errors[0]})")
    return handler.codes[0]


def _post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as err:
        raise LoginError(f"The provider refused the sign-in ({err.code})") from err
    except OSError as err:
        raise LoginError(f"Could not reach the provider: {err}") from err


def openrouter_login(*, open_url: Callable[[str], None] = webbrowser.open,
                     post: Callable[[str, dict], dict] = _post_json, timeout: float = TIMEOUT) -> str:
    """Signs in to OpenRouter in the browser and returns the API key it issues for Pyzed."""
    verifier, challenge = pkce_pair()

    def url(callback: str) -> str:
        return OPENROUTER_AUTH + "?" + urllib.parse.urlencode(
            {"callback_url": callback, "code_challenge": challenge, "code_challenge_method": "S256"})

    code = wait_for_code(open_url, url, timeout=timeout)
    data = post(OPENROUTER_EXCHANGE, {"code": code, "code_verifier": verifier, "code_challenge_method": "S256"})
    key = data.get("key") if isinstance(data, dict) else None
    if not key:
        raise LoginError("OpenRouter did not return a key")
    return str(key)


def key_page(provider_id: str, *, open_url: Callable[[str], None] = webbrowser.open) -> str:
    """Opens the provider's page for creating a key (the first step of ``login="browser"``)."""
    from .providers import PROVIDERS

    url = PROVIDERS[provider_id].key_url
    if not url:
        raise LoginError(f"{PROVIDERS[provider_id].name} has no key page; paste a key instead")
    open_url(url)
    return url


def login(provider_id: str) -> Optional[str]:
    """Signs in to an OAuth provider (``login="oauth"``) with the browser and returns its key. For the
    other providers the designer opens ``key_page`` and picks the copied key up."""
    from .providers import PROVIDERS

    if PROVIDERS[provider_id].login == "oauth":
        return openrouter_login()
    raise LoginError(f"{PROVIDERS[provider_id].name} signs in by copying a key from its page; use key_page()")
