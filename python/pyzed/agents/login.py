"""Signing in with the browser instead of typing a key. Nothing here needs another program.

* OpenRouter (``login="oauth"``): OAuth with PKCE. Pyzed opens the browser on OpenRouter's consent page,
  receives the code on a one-shot server bound to ``127.0.0.1``, exchanges it for a key and saves the key
  in the system keychain.
* GitHub Copilot (``login="device"``): GitHub's device flow (``github_device_code`` then
  ``github_device_token``): Pyzed shows a short code, the user types it on github.com and Pyzed receives
  a token for GitHub Models. It needs a GitHub App (``providers.GITHUB_CLIENT_ID``); a fine-grained
  personal access token with the "Models" permission works too.
* Google Vertex AI (``login="google"``): Google sign-in with PKCE on the same loopback server
  (``google_login``); the refresh token stays in the keychain and access tokens are renewed when they
  expire. The Google Cloud credentials of this computer (``gcloud auth application-default login``, a
  service account file in ``GOOGLE_APPLICATION_CREDENTIALS``) are used as they are when present.
* Anthropic, OpenAI, Gemini, xAI, Mistral, DeepSeek, Groq (``login="browser"``): these providers do not
  let other apps sign in with OAuth, so Pyzed opens their key page (``key_page``) and the designer picks
  the key up as soon as it is copied (``providers.looks_like_key``), checks it and saves it in the keychain.
* An Anthropic CLI profile (``ant auth login``), when one exists, is still used by the ``anthropic`` SDK;
  it is optional.

``openrouter_login``, ``github_device_token`` and ``google_login`` block, so the designer runs them in a
worker thread.
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

OPENROUTER_AUTH = "https://openrouter.ai/auth"
OPENROUTER_EXCHANGE = "https://openrouter.ai/api/v1/auth/keys"
GITHUB_DEVICE = "https://github.com/login/device/code"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)
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
                  timeout: float = TIMEOUT, host: str = "localhost") -> str:
    """Starts a one-shot server on ``127.0.0.1``, opens ``build_url(callback)`` and returns the ``code``
    the browser brings back."""
    path = f"/callback/{_random.token_urlsafe(16)}"
    handler = type("Callback", (_Callback,), {"codes": [], "errors": [], "path_secret": path})
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    server.timeout = 0.5
    callback = f"http://{host}:{server.server_address[1]}{path}"
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


def _post_form(url: str, payload: dict) -> dict:
    """POSTs a form (what OAuth token endpoints take) and returns the JSON answer, errors included."""
    request = urllib.request.Request(url, data=urllib.parse.urlencode(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/x-www-form-urlencoded",
                                              "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as err:
        try:
            body = json.loads(err.read().decode() or "{}")
        except (ValueError, OSError):
            body = {}
        if isinstance(body, dict) and body.get("error"):
            return body
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


# -- GitHub device flow (GitHub Copilot / GitHub Models) ---------------------------------------------

@dataclass(frozen=True)
class DeviceCode:
    """What the user types on GitHub (``user_code`` at ``verification_uri``) while Pyzed waits."""

    device_code: str
    user_code: str
    verification_uri: str
    interval: float = 5.0
    expires_in: float = 900.0


def github_device_code(client_id: str, *, post: Callable[[str, dict], dict] = _post_form) -> DeviceCode:
    """Starts GitHub's device flow for the GitHub App ``client_id``."""
    if not client_id:
        raise LoginError("GitHub sign-in needs a GitHub App: set its client ID in Settings → AI agents → GitHub "
                         "Copilot, or sign in with a personal access token")
    data = post(GITHUB_DEVICE, {"client_id": client_id})
    if data.get("error") or not data.get("device_code"):
        raise LoginError(f"GitHub did not start the sign-in ({data.get('error_description') or data.get('error')})")
    return DeviceCode(str(data["device_code"]), str(data["user_code"]), str(data["verification_uri"]),
                      float(data.get("interval") or 5), float(data.get("expires_in") or 900))


def github_device_token(client_id: str, code: DeviceCode, *, post: Callable[[str, dict], dict] = _post_form,
                        sleep: Callable[[float], None] = time.sleep,
                        cancelled: Callable[[], bool] = lambda: False) -> Dict[str, Any]:
    """Waits until the user enters ``code`` on GitHub and returns the token (``access_token``, and
    ``refresh_token`` / ``expires_at`` when the app's tokens expire)."""
    interval = code.interval
    deadline = time.monotonic() + code.expires_in
    while time.monotonic() < deadline:
        if cancelled():
            raise LoginError("Sign-in cancelled")
        sleep(interval)
        data = post(GITHUB_TOKEN, {"client_id": client_id, "device_code": code.device_code,
                                   "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        error = data.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval = float(data.get("interval") or interval + 5)
            continue
        if error:
            raise LoginError({"expired_token": "The code expired; sign in again",
                              "access_denied": "Sign-in was declined on GitHub"}.get(
                                  error, data.get("error_description") or error))
        return _token(data)
    raise LoginError("The code expired; sign in again")


def _token(data: Dict[str, Any], old: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """A token answer as what the keychain keeps (absolute expiry; the refresh token is kept when the
    provider does not send a new one)."""
    token = {"access_token": str(data["access_token"])}
    refresh_token = data.get("refresh_token") or (old or {}).get("refresh_token")
    if refresh_token:
        token["refresh_token"] = str(refresh_token)
    if data.get("expires_in"):
        token["expires_at"] = time.time() + float(data["expires_in"])
    return token


# -- Google sign-in (Vertex AI) ----------------------------------------------------------------------

def google_client(settings: Any) -> "tuple[str, str]":
    """The Google OAuth client (ID and the desktop app's secret, which Google does not treat as one)."""
    from . import providers, secrets

    client_id = settings.client_id("vertex")
    secret = secrets.store().get("agents.vertex.client_secret") or os.environ.get("PYZED_GOOGLE_CLIENT_SECRET") \
        or (providers.GOOGLE_CLIENT_SECRET if client_id == providers.GOOGLE_CLIENT_ID else "")
    return client_id, secret


def google_login(client_id: str, client_secret: str, *, open_url: Callable[[str], None] = webbrowser.open,
                 post: Callable[[str, dict], dict] = _post_form, timeout: float = TIMEOUT,
                 scopes=GOOGLE_SCOPES) -> Dict[str, Any]:
    """Signs in with a Google account in the browser and returns its token (with a refresh token)."""
    if not client_id:
        raise LoginError("Google sign-in needs an OAuth client: set it in Settings → AI agents → Google Vertex AI, "
                         "or sign in with `gcloud auth application-default login`")
    verifier, challenge = pkce_pair()
    callbacks: List[str] = []

    def url(callback: str) -> str:
        callbacks.append(callback)
        return GOOGLE_AUTH + "?" + urllib.parse.urlencode({
            "client_id": client_id, "redirect_uri": callback, "response_type": "code", "scope": " ".join(scopes),
            "code_challenge": challenge, "code_challenge_method": "S256", "access_type": "offline",
            "prompt": "consent"})

    code = wait_for_code(open_url, url, timeout=timeout, host="127.0.0.1")
    data = post(GOOGLE_TOKEN, {"code": code, "client_id": client_id, "client_secret": client_secret,
                               "redirect_uri": callbacks[-1], "grant_type": "authorization_code",
                               "code_verifier": verifier})
    if data.get("error") or not data.get("access_token"):
        raise LoginError(f"Google refused the sign-in ({data.get('error_description') or data.get('error')})")
    return _token(data)


def refresh(provider_id: str, token: Dict[str, Any], settings: Any, *,
            post: Callable[[str, dict], dict] = _post_form) -> Dict[str, Any]:
    """Renews an expired OAuth token with its refresh token."""
    if provider_id == "vertex":
        client_id, secret = google_client(settings)
        data = post(GOOGLE_TOKEN, {"client_id": client_id, "client_secret": secret, "grant_type": "refresh_token",
                                   "refresh_token": token["refresh_token"]})
    elif provider_id == "github":
        data = post(GITHUB_TOKEN, {"client_id": settings.client_id("github"), "grant_type": "refresh_token",
                                   "refresh_token": token["refresh_token"]})
    else:
        raise LoginError("This provider does not renew its tokens")
    if data.get("error") or not data.get("access_token"):
        raise LoginError("The sign-in expired; sign in again")
    return _token(data, token)


def _gcloud_dir() -> Path:
    if os.environ.get("CLOUDSDK_CONFIG"):
        return Path(os.environ["CLOUDSDK_CONFIG"])
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "gcloud"
    return Path.home() / ".config" / "gcloud"


def google_default_credentials() -> Optional[Dict[str, Any]]:
    """This computer's Google Cloud credentials (application default credentials), or ``None``."""
    for path in (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
                 _gcloud_dir() / "application_default_credentials.json"):
        if not path:
            continue
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("type") in ("authorized_user", "service_account",
                                                           "external_account", "impersonated_service_account"):
            return data
    return None


_default_token: Dict[str, Any] = {}


def google_default_token(*, post: Callable[[str, dict], dict] = _post_form) -> Optional[str]:
    """An access token from this computer's Google Cloud credentials (renewed when it expires)."""
    if _default_token.get("access_token") and time.time() < _default_token.get("expires_at", 0) - 60:
        return _default_token["access_token"]
    found = google_default_credentials()
    if found is None:
        return None
    try:  # google-auth handles every kind of credentials (service accounts, workload identity...)
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(scopes=list(GOOGLE_SCOPES))
        credentials.refresh(google.auth.transport.requests.Request())
        _default_token.update(access_token=credentials.token, expires_at=time.time() + 3000)
        return credentials.token
    except ImportError:
        pass
    except Exception as err:  # noqa: BLE001
        raise LoginError(f"Google Cloud credentials did not work: {err}") from err
    if found.get("type") != "authorized_user":
        raise LoginError("These Google Cloud credentials need the google-auth package: pip install google-auth")
    data = post(GOOGLE_TOKEN, {"client_id": found.get("client_id", ""), "client_secret": found.get("client_secret", ""),
                               "refresh_token": found.get("refresh_token", ""), "grant_type": "refresh_token"})
    if data.get("error") or not data.get("access_token"):
        raise LoginError("Google Cloud credentials expired: run gcloud auth application-default login again")
    _default_token.update(_token(data))
    return _default_token["access_token"]


def google_projects(token: str) -> List[str]:
    """The Google Cloud projects the signed-in account can use (for the Vertex AI project setting)."""
    request = urllib.request.Request("https://cloudresourcemanager.googleapis.com/v1/projects?filter="
                                     + urllib.parse.quote("lifecycleState:ACTIVE"),
                                     headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode() or "{}")
    except (OSError, ValueError):
        return []
    return sorted(str(p.get("projectId")) for p in data.get("projects") or [] if p.get("projectId"))


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
    raise LoginError(f"{PROVIDERS[provider_id].name} signs in by copying a key from its page (key_page), with "
                     "github_device_code (GitHub) or with google_login (Google)")
