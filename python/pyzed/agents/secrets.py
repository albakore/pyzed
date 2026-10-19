"""Where API keys and sign-in tokens live: the operating system's credential store.

Secrets go to the system keychain through ``keyring`` (Keychain on macOS, Credential Manager on
Windows, Secret Service or KWallet on Linux), under the service ``pyzed``. They are never written to
Pyzed's settings files. When no keychain is available, a secret is kept in memory for the session
only and the user is told so; it is never saved in plain text.

Keys can also come from environment variables (``ANTHROPIC_API_KEY``, ``OPENAI_API_KEY``...), which
are read but never stored.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, Optional

SERVICE = "pyzed"


class SecretStore:
    """Reads and writes secrets in the system keychain, with an in-memory fallback.

    ``backend`` may be any object with keyring's ``get_password``/``set_password``/``delete_password``
    (tests pass a fake); by default the ``keyring`` package is used when it has a usable backend.
    """

    def __init__(self, backend: Any = None, *, service: str = SERVICE) -> None:
        self.service = service
        self._backend = backend if backend is not None else _system_keyring()
        self._memory: Dict[str, str] = {}
        self._lock = threading.Lock()

    @property
    def secure(self) -> bool:
        """Whether secrets are saved in a system keychain (``False``: they last until the app closes)."""
        return self._backend is not None

    @property
    def backend_name(self) -> str:
        """A readable name of where secrets are kept."""
        if self._backend is None:
            return "memory (this session only)"
        name = getattr(self._backend, "name", None) or type(self._backend).__name__
        return str(name)

    def get(self, key: str) -> Optional[str]:
        """Returns the secret saved as ``key``, or ``None``."""
        with self._lock:
            if key in self._memory:
                return self._memory[key]
        if self._backend is None:
            return None
        try:
            return self._backend.get_password(self.service, key) or None
        except Exception:  # noqa: BLE001 - a locked or broken keychain is the same as no secret
            return None

    def set(self, key: str, secret: str) -> bool:
        """Saves ``secret`` as ``key``; returns ``True`` when it went to the keychain, ``False`` when it is
        only kept in memory (no keychain, or the keychain refused it)."""
        secret = secret.strip()
        if not secret:
            self.delete(key)
            return self.secure
        if self._backend is not None:
            try:
                self._backend.set_password(self.service, key, secret)
                with self._lock:
                    self._memory.pop(key, None)
                return True
            except Exception:  # noqa: BLE001
                pass
        with self._lock:
            self._memory[key] = secret
        return False

    def delete(self, key: str) -> None:
        """Forgets the secret saved as ``key`` (in the keychain and in memory)."""
        with self._lock:
            self._memory.pop(key, None)
        if self._backend is not None:
            try:
                self._backend.delete_password(self.service, key)
            except Exception:  # noqa: BLE001 - nothing saved
                pass


def _system_keyring() -> Any:
    """The ``keyring`` module when it has a real (non-fail, non-plaintext) backend, else ``None``."""
    if os.environ.get("PYZED_KEYRING", "1") in ("0", "off", "no", "false"):
        return None
    try:
        import keyring
        from keyring.backends import fail
    except ImportError:
        return None
    try:
        backend = keyring.get_keyring()
    except Exception:  # noqa: BLE001
        return None
    if isinstance(backend, fail.Keyring) or "plaintext" in type(backend).__module__.lower():
        return None
    if getattr(backend, "priority", 1) <= 0:
        return None
    return backend


_store: Optional[SecretStore] = None


def store() -> SecretStore:
    """The process-wide secret store."""
    global _store
    if _store is None:
        _store = SecretStore()
    return _store


def use(store_: SecretStore) -> None:
    """Replaces the process-wide secret store (tests and apps with their own vault)."""
    global _store
    _store = store_


def mask(secret: Optional[str]) -> str:
    """``sk-ant-…a1b2`` style preview of a secret, never the whole of it."""
    if not secret:
        return ""
    if len(secret) <= 10:
        return "•" * len(secret)
    return f"{secret[:6]}…{secret[-4:]}"
