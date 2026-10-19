"""The model providers agents can use, and the user's settings for them.

Two wire protocols cover every provider: Anthropic's Messages API (through the official ``anthropic``
SDK) and the OpenAI-compatible Chat Completions API, which OpenAI, Google Gemini, OpenRouter, Ollama,
LM Studio and most self-hosted servers speak. A model is named ``"<provider>:<model>"``, for example
``"anthropic:claude-opus-5-5"`` or ``"ollama:qwen3:8b"``.

The settings (default model, base URLs, extra models, effort, permissions) are saved in
``agents.json`` in the Pyzed config folder. Secrets are not: they live in the system keychain (see
``pyzed.agents.secrets``).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import secrets as _secrets


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    #: ``"anthropic"`` or ``"openai"`` (OpenAI-compatible Chat Completions).
    protocol: str
    base_url: str = ""
    #: Environment variable read for the key when none is saved.
    key_env: str = ""
    #: Page where the user creates a key (opened by "Get a key").
    key_url: str = ""
    #: How "Sign in with the browser" works: ``"ant"`` (Anthropic CLI profile), ``"openrouter"`` (OAuth
    #: PKCE) or ``""`` (keys only).
    login: str = ""
    needs_key: bool = True
    #: Models offered before the provider's model list has been fetched.
    models: Tuple[str, ...] = ()
    #: The base URL can be changed in the settings.
    custom_url: bool = False
    icon: str = "sparkles"
    description: str = ""


PROVIDERS: Dict[str, Provider] = {p.id: p for p in (
    Provider("anthropic", "Anthropic", "anthropic", "https://api.anthropic.com", "ANTHROPIC_API_KEY",
             "https://console.anthropic.com/settings/keys", login="ant",
             models=("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"),
             icon="sparkles", description="Claude models, with an API key or the Anthropic CLI sign-in"),
    Provider("openai", "OpenAI", "openai", "https://api.openai.com/v1", "OPENAI_API_KEY",
             "https://platform.openai.com/api-keys", icon="bot", description="GPT models with an API key"),
    Provider("google", "Google Gemini", "openai", "https://generativelanguage.googleapis.com/v1beta/openai",
             "GEMINI_API_KEY", "https://aistudio.google.com/apikey", icon="gem",
             description="Gemini models with a Google AI Studio key"),
    Provider("openrouter", "OpenRouter", "openai", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY",
             "https://openrouter.ai/settings/keys", login="openrouter", icon="route",
             description="Hundreds of models behind one account; sign in with the browser"),
    Provider("ollama", "Ollama", "openai", "http://localhost:11434/v1", needs_key=False, custom_url=True,
             icon="cpu", description="Models running on this computer, no key needed"),
    Provider("lmstudio", "LM Studio", "openai", "http://localhost:1234/v1", needs_key=False, custom_url=True,
             icon="monitor", description="Models served by LM Studio on this computer"),
    Provider("custom", "OpenAI-compatible", "openai", "", "PYZED_AGENT_API_KEY", needs_key=False, custom_url=True,
             icon="server", description="Any server that speaks the OpenAI Chat Completions API"),
)}

DEFAULT_MODEL = "anthropic:claude-opus-5-5"
EFFORTS = ("low", "medium", "high", "xhigh", "max")


def split_model(model: str) -> Tuple[str, str]:
    """``"ollama:qwen3:8b"`` -> ``("ollama", "qwen3:8b")``; a bare name is taken as an Anthropic model."""
    provider, sep, name = model.partition(":")
    if not sep or provider not in PROVIDERS:
        return "anthropic", model
    return provider, name


@dataclass
class ProviderSettings:
    #: Overrides the provider's base URL ("" keeps the default).
    base_url: str = ""
    #: Models fetched from the provider or added by hand, offered in the model picker.
    models: List[str] = field(default_factory=list)


@dataclass
class AgentSettings:
    #: The model new threads use, as ``"provider:model"``.
    model: str = DEFAULT_MODEL
    #: How hard the model thinks (Claude's effort; mapped to reasoning effort elsewhere).
    effort: str = "high"
    #: ``"write"`` (may change forms and files), ``"ask"`` (reads only) or ``"minimal"`` (no tools).
    profile: str = "write"
    #: Ask before a tool writes files on disk or runs code.
    confirm_writes: bool = True
    #: Show the model's reasoning summaries in the thread.
    show_thinking: bool = True
    #: Extra instructions added to every thread (like Zed's rules).
    rules: str = ""
    providers: Dict[str, ProviderSettings] = field(default_factory=dict)

    def provider(self, provider_id: str) -> ProviderSettings:
        """The settings of ``provider_id`` (created empty when missing)."""
        return self.providers.setdefault(provider_id, ProviderSettings())

    def base_url(self, provider_id: str) -> str:
        """The base URL used for ``provider_id``."""
        own = self.providers.get(provider_id)
        return (own.base_url if own and own.base_url else PROVIDERS[provider_id].base_url).rstrip("/")

    def models_of(self, provider_id: str) -> List[str]:
        """The models offered for ``provider_id``: its known ones, then the fetched or added ones."""
        own = self.providers.get(provider_id)
        seen: List[str] = []
        for name in (*PROVIDERS[provider_id].models, *(own.models if own else ())):
            if name and name not in seen:
                seen.append(name)
        return seen

    def to_dict(self) -> Dict[str, Any]:
        """The settings as a JSON-ready dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentSettings":
        """Builds settings from saved ``data``, keeping defaults for missing or invalid values."""
        out = cls()
        for f in fields(cls):
            if f.name not in data or f.name == "providers":
                continue
            default = getattr(out, f.name)
            try:
                setattr(out, f.name, type(default)(data[f.name]))
            except (TypeError, ValueError):
                continue
        raw = data.get("providers")
        if isinstance(raw, dict):
            for pid, value in raw.items():
                if pid in PROVIDERS and isinstance(value, dict):
                    models = value.get("models")
                    out.providers[pid] = ProviderSettings(
                        base_url=str(value.get("base_url") or ""),
                        models=[str(m) for m in models][:500] if isinstance(models, list) else [])
        if out.effort not in EFFORTS:
            out.effort = "high"
        if out.profile not in ("write", "ask", "minimal"):
            out.profile = "write"
        return out


def config_path() -> Path:
    """``agents.json`` in the Pyzed config folder."""
    from ..designer.settings import config_dir

    return config_dir() / "agents.json"


def load(path: Optional[Path] = None) -> AgentSettings:
    """The saved agent settings (defaults when there are none)."""
    try:
        data = json.loads((path or config_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AgentSettings()
    return AgentSettings.from_dict(data) if isinstance(data, dict) else AgentSettings()


def save(settings: AgentSettings, path: Optional[Path] = None) -> Optional[Path]:
    """Writes the settings; ``None`` when the folder is not writable. Never contains secrets."""
    path = path or config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings.to_dict(), indent=2) + "\n", encoding="utf-8")
    except OSError:
        return None
    return path


# -- credentials -------------------------------------------------------------------------------

def key_name(provider_id: str) -> str:
    """The keychain entry of a provider's key."""
    return f"agents.{provider_id}"


def api_key(provider_id: str, store: Optional[_secrets.SecretStore] = None) -> Optional[str]:
    """The key of ``provider_id``: the saved one, or its environment variable."""
    store = store or _secrets.store()
    saved = store.get(key_name(provider_id))
    if saved:
        return saved
    env = PROVIDERS[provider_id].key_env
    return os.environ.get(env) or None if env else None


def credential_source(provider_id: str, store: Optional[_secrets.SecretStore] = None) -> str:
    """Where the provider's credentials come from: ``"keychain"``, ``"session"`` (memory only), ``"env"``,
    ``"ant"`` (Anthropic CLI profile), ``"none needed"`` or ``""`` (not set up)."""
    store = store or _secrets.store()
    if store.get(key_name(provider_id)):
        return "keychain" if store.secure else "session"
    provider = PROVIDERS[provider_id]
    if provider.key_env and os.environ.get(provider.key_env):
        return "env"
    if provider.login == "ant":
        from .login import ant_signed_in

        if ant_signed_in():
            return "ant"
    if not provider.needs_key:
        return "none needed"
    return ""


def is_ready(provider_id: str, store: Optional[_secrets.SecretStore] = None) -> bool:
    """Whether ``provider_id`` can be used now."""
    return bool(credential_source(provider_id, store))
