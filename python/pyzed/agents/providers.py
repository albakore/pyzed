"""The model providers agents can use, and the user's settings for them.

Two wire protocols cover every model provider: Anthropic's Messages API (through the official
``anthropic`` SDK) and the OpenAI-compatible Chat Completions API, which OpenAI, Google Gemini, GitHub
Copilot (GitHub Models), Vertex AI, OpenRouter, Ollama, LM Studio and most self-hosted servers speak. A
model is named ``"<provider>:<model>"``, for example ``"anthropic:claude-opus-5-5"`` or
``"ollama:qwen3:8b"``. External agents (Claude Code, Gemini CLI... through the Agent Client Protocol)
are named ``"acp:<agent>"`` and run with ``pyzed.agents.acp``.

The settings (default model, base URLs, extra models, effort, permissions, MCP servers, external
agents, workload identity federation) are saved in ``agents.json`` in the Pyzed config folder. Secrets
are not: keys, OAuth tokens and the secret environment variables of MCP servers live in the system
keychain (see ``pyzed.agents.secrets``).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import secrets as _secrets


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    #: ``"anthropic"``, ``"openai"`` (OpenAI-compatible Chat Completions) or ``"acp"`` (external agents).
    protocol: str
    base_url: str = ""
    #: Environment variable read for the key when none is saved.
    key_env: str = ""
    #: Page where the user creates a key (opened by "Get a key").
    key_url: str = ""
    #: How "Sign in with the browser" works: ``"browser"`` (Pyzed opens the provider's key page and picks
    #: up the key when it is copied), ``"oauth"`` (OAuth with PKCE, no copying), ``"device"`` (GitHub's
    #: device flow: a code to type on github.com), ``"google"`` (Google sign-in) or ``""`` (keys only).
    login: str = ""
    #: How the provider's keys start; used to recognise a copied key.
    key_prefixes: Tuple[str, ...] = ()
    needs_key: bool = True
    #: Models offered before the provider's model list has been fetched.
    models: Tuple[str, ...] = ()
    #: The base URL can be changed in the settings.
    custom_url: bool = False
    icon: str = "sparkles"
    description: str = ""


PROVIDERS: Dict[str, Provider] = {p.id: p for p in (
    Provider("anthropic", "Anthropic", "anthropic", "https://api.anthropic.com", "ANTHROPIC_API_KEY",
             "https://console.anthropic.com/settings/keys", login="browser", key_prefixes=("sk-ant-",),
             models=("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"),
             icon="sparkles", description="Claude models; sign in with the browser or paste an API key"),
    Provider("openai", "OpenAI", "openai", "https://api.openai.com/v1", "OPENAI_API_KEY",
             "https://platform.openai.com/api-keys", login="browser", key_prefixes=("sk-proj-", "sk-svcacct-", "sk-"),
             icon="bot", description="GPT models; sign in with the browser or paste an API key"),
    Provider("google", "Google Gemini", "openai", "https://generativelanguage.googleapis.com/v1beta/openai",
             "GEMINI_API_KEY", "https://aistudio.google.com/apikey", login="browser", key_prefixes=("AIza",),
             icon="gem", description="Gemini models with a Google AI Studio key"),
    Provider("vertex", "Google Vertex AI", "openai", "", login="google",
             models=("google/gemini-2.5-pro", "google/gemini-2.5-flash"), icon="cloud",
             description="Gemini with your Google account, through Google Cloud; no key"),
    Provider("github", "GitHub Copilot", "openai", "https://models.github.ai/inference", "GITHUB_TOKEN",
             "https://github.com/settings/personal-access-tokens/new", login="device",
             key_prefixes=("github_pat_", "ghp_", "gho_", "ghu_"), models=("openai/gpt-4.1",), icon="github",
             description="The models of your GitHub account and Copilot plan (GitHub Models)"),
    Provider("openrouter", "OpenRouter", "openai", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY",
             "https://openrouter.ai/settings/keys", login="oauth", key_prefixes=("sk-or-",), icon="route",
             description="Hundreds of models behind one account; sign in with the browser"),
    Provider("xai", "xAI", "openai", "https://api.x.ai/v1", "XAI_API_KEY", "https://console.x.ai",
             login="browser", key_prefixes=("xai-",), icon="zap", description="Grok models with an xAI API key"),
    Provider("mistral", "Mistral", "openai", "https://api.mistral.ai/v1", "MISTRAL_API_KEY",
             "https://console.mistral.ai/api-keys", login="browser", icon="wind",
             description="Mistral and Codestral models with an API key"),
    Provider("deepseek", "DeepSeek", "openai", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY",
             "https://platform.deepseek.com/api_keys", login="browser", key_prefixes=("sk-",), icon="search-code",
             description="DeepSeek models with an API key"),
    Provider("groq", "Groq", "openai", "https://api.groq.com/openai/v1", "GROQ_API_KEY",
             "https://console.groq.com/keys", login="browser", key_prefixes=("gsk_",), icon="gauge",
             description="Open models on Groq's fast inference"),
    Provider("ollama", "Ollama", "openai", "http://localhost:11434/v1", needs_key=False, custom_url=True,
             icon="cpu", description="Models running on this computer, no key needed"),
    Provider("lmstudio", "LM Studio", "openai", "http://localhost:1234/v1", needs_key=False, custom_url=True,
             icon="monitor", description="Models served by LM Studio on this computer"),
    Provider("custom", "OpenAI-compatible", "openai", "", "PYZED_AGENT_API_KEY", needs_key=False, custom_url=True,
             icon="server", description="Any server that speaks the OpenAI Chat Completions API"),
    Provider("acp", "External agents", "acp", needs_key=False, icon="terminal",
             description="Claude Code, Gemini CLI, Codex and other agents, through the Agent Client Protocol"),
)}

#: OAuth apps Pyzed signs in with (``PYZED_GITHUB_CLIENT_ID``... or the provider's settings override them).
#: A GitHub App with the device flow on and the "Models" account permission; a Google "Desktop app" client.
#: Empty in the repository; the release builds of Pyzed Design fill them from the workflow's secrets
#: (``scripts/build_designer.py`` bundles them as the ``pyzed_oauth_apps`` module).
GITHUB_CLIENT_ID = ""
GOOGLE_CLIENT_ID = ""
GOOGLE_CLIENT_SECRET = ""  # not confidential for desktop apps (Google's installed-app flow)
try:
    from pyzed_oauth_apps import GITHUB_CLIENT_ID, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET  # type: ignore  # noqa: F401
except ImportError:
    pass

DEFAULT_MODEL = "anthropic:claude-opus-5-5"
EFFORTS = ("low", "medium", "high", "xhigh", "max")
#: Claude models that take fast mode (faster output at a higher price; the Claude API only).
FAST_MODELS = ("claude-opus-5-5", "claude-opus-5")
#: Permission modes of the Agent panel, like Zed's: what the agent may do without asking.
MODES = ("read", "ask", "bypass", "chat")


#: Context windows (tokens) by model name prefix, longest match first; the panel's context meter uses them.
CONTEXT_WINDOWS: Dict[str, int] = {
    "claude-haiku-4": 200_000, "claude-3": 200_000, "claude-sonnet-4-5": 200_000, "claude-opus-4-5": 200_000,
    "claude-opus-4-1": 200_000, "claude-sonnet-4-2": 200_000, "claude-opus-4-2": 200_000, "claude-": 1_000_000,
    "gpt-4.1": 1_047_576, "gpt-4o": 128_000, "gpt-5": 400_000, "o3": 200_000, "o4": 200_000,
    "gemini-": 1_048_576, "google/gemini": 1_048_576, "openai/gpt-4.1": 1_047_576, "grok-4": 256_000,
    "deepseek-": 128_000, "mistral-large": 128_000,
}


def context_window(model: str) -> int:
    """The context window of ``model`` (``"provider:name"``), in tokens; 0 when it is not known."""
    _, name = split_model(model)
    name = name.lower()
    for prefix in sorted(CONTEXT_WINDOWS, key=len, reverse=True):
        if name.startswith(prefix):
            return CONTEXT_WINDOWS[prefix]
    return 0


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
    #: The OAuth client used to sign in (GitHub, Google); "" uses Pyzed's.
    client_id: str = ""
    #: Google Cloud project and location (Vertex AI).
    project: str = ""
    location: str = ""


@dataclass
class FederationSettings:
    """Workload identity federation for Claude: an identity token from your identity provider (GitHub
    Actions, Google Cloud, Azure, Okta, Kubernetes...) is exchanged for a short-lived Claude token, so no
    API key is stored anywhere. Set up the issuer and the rule in the Claude Console."""

    #: ``fdrl_...``, the federation rule that accepts your tokens.
    rule_id: str = ""
    #: The organization's UUID.
    organization_id: str = ""
    #: ``svac_...``, the rule's service account (optional when the rule names one).
    service_account_id: str = ""
    #: ``wrkspc_...`` or ``"default"`` (optional).
    workspace_id: str = ""
    #: Where the identity token comes from: ``"file"``, ``"command"`` (prints it) or ``"env"``.
    token_source: str = "file"
    #: The token file (``""`` reads ``ANTHROPIC_IDENTITY_TOKEN_FILE``).
    token_file: str = ""
    #: A command that prints a fresh token, e.g. ``gcloud auth print-identity-token``.
    token_command: str = ""
    token_env: str = "ANTHROPIC_IDENTITY_TOKEN"

    @property
    def enabled(self) -> bool:
        return bool(self.rule_id.strip() and self.organization_id.strip())

    def to_tuple(self) -> Tuple[str, ...]:
        return tuple(str(getattr(self, f.name)) for f in fields(self))


@dataclass
class MCPServerConfig:
    """An MCP server the agent can use (its tools are added to the agent's). Secret environment
    variables and headers are kept in the system keychain, not here."""

    name: str
    #: The program of a local (stdio) server, e.g. ``"npx"``; empty for a remote one.
    command: str = ""
    args: List[str] = field(default_factory=list)
    #: The URL of a remote (Streamable HTTP) server.
    url: str = ""
    #: Names of the environment variables (or HTTP headers) whose values are in the keychain.
    secret_names: List[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class ACPAgentConfig:
    """An external agent spoken to with the Agent Client Protocol (like Zed's external agents)."""

    name: str
    command: str
    args: List[str] = field(default_factory=list)
    secret_names: List[str] = field(default_factory=list)
    enabled: bool = True
    title: str = ""
    #: The agent's id in the ACP registry when it was installed from there (``agents.registry``).
    registry_id: str = ""
    #: The installed version (registry agents), compared with the registry's to offer updates.
    version: str = ""
    #: Environment variables the agent needs that are not secret (secret ones are in the keychain).
    env: Dict[str, str] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return self.title or self.name


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
    #: Fast mode on Claude models that take it (``FAST_MODELS``).
    fast: bool = False
    #: Show the model's reasoning summaries in the thread.
    show_thinking: bool = True
    #: Keep conversations on this computer (``ThreadStore``) so they show up in the history.
    keep_history: bool = True
    #: Extra instructions added to every thread (like Zed's rules).
    rules: str = ""
    providers: Dict[str, ProviderSettings] = field(default_factory=dict)
    #: Claude without an API key (see ``FederationSettings``).
    federation: FederationSettings = field(default_factory=FederationSettings)
    #: MCP servers whose tools the agent may use.
    mcp_servers: List[MCPServerConfig] = field(default_factory=list)
    #: External agents offered in the model picker.
    acp_agents: List[ACPAgentConfig] = field(default_factory=list)
    #: Give external agents Pyzed's own MCP server (components, docs, generators, checks).
    share_pyzed_mcp: bool = True
    #: Agent skills (``agents.skills``) the built-in agent must not use, by name.
    disabled_skills: List[str] = field(default_factory=list)
    #: Open the files the agent writes (and where an external agent edits) as it works, like Zed's "Follow".
    follow_agent: bool = True
    #: A desktop notification when the agent finishes or waits for an answer while the window is in the
    #: background, like Zed's.
    notify_when_done: bool = True

    def provider(self, provider_id: str) -> ProviderSettings:
        """The settings of ``provider_id`` (created empty when missing)."""
        return self.providers.setdefault(provider_id, ProviderSettings())

    def base_url(self, provider_id: str) -> str:
        """The base URL used for ``provider_id``."""
        own = self.providers.get(provider_id)
        if provider_id == "vertex" and not (own and own.base_url):
            project = (own.project if own else "") or google_project()
            location = (own.location if own else "") or "global"
            if not project:
                return ""
            host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
            return f"https://{host}/v1/projects/{project}/locations/{location}/endpoints/openapi"
        return (own.base_url if own and own.base_url else PROVIDERS[provider_id].base_url).rstrip("/")

    def client_id(self, provider_id: str) -> str:
        """The OAuth client ``provider_id`` signs in with ("" when none is set up)."""
        own = self.providers.get(provider_id)
        if own and own.client_id:
            return own.client_id
        if provider_id == "github":
            return os.environ.get("PYZED_GITHUB_CLIENT_ID") or GITHUB_CLIENT_ID
        if provider_id == "vertex":
            return os.environ.get("PYZED_GOOGLE_CLIENT_ID") or GOOGLE_CLIENT_ID
        return ""

    def acp_agent(self, name: str) -> Optional[ACPAgentConfig]:
        return next((a for a in self.acp_agents if a.name == name), None)

    def mcp_server(self, name: str) -> Optional[MCPServerConfig]:
        return next((m for m in self.mcp_servers if m.name == name), None)

    def models_of(self, provider_id: str) -> List[str]:
        """The models offered for ``provider_id``: its known ones, then the fetched or added ones."""
        own = self.providers.get(provider_id)
        seen: List[str] = []
        for name in (*PROVIDERS[provider_id].models, *(own.models if own else ())):
            if name and name not in seen:
                seen.append(name)
        return seen

    @property
    def mode(self) -> str:
        """The permission mode: ``"read"`` (reads only), ``"ask"`` (asks before writing files),
        ``"bypass"`` (never asks) or ``"chat"`` (no tools)."""
        if self.profile == "minimal":
            return "chat"
        if self.profile == "ask":
            return "read"
        return "ask" if self.confirm_writes else "bypass"

    @mode.setter
    def mode(self, value: str) -> None:
        self.profile = {"read": "ask", "chat": "minimal"}.get(value, "write")
        if value in ("ask", "bypass"):
            self.confirm_writes = value == "ask"

    def to_dict(self) -> Dict[str, Any]:
        """The settings as a JSON-ready dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentSettings":
        """Builds settings from saved ``data``, keeping defaults for missing or invalid values."""
        out = cls()
        for f in fields(cls):
            if f.name not in data or f.name in ("providers", "federation", "mcp_servers", "acp_agents"):
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
                        models=[str(m) for m in models][:500] if isinstance(models, list) else [],
                        client_id=str(value.get("client_id") or ""), project=str(value.get("project") or ""),
                        location=str(value.get("location") or ""))
        fed = data.get("federation")
        if isinstance(fed, dict):
            out.federation = FederationSettings(**{f.name: str(fed[f.name]) for f in fields(FederationSettings)
                                                   if isinstance(fed.get(f.name), str)})
        out.mcp_servers = _configs(data.get("mcp_servers"), MCPServerConfig)
        out.acp_agents = _configs(data.get("acp_agents"), ACPAgentConfig)
        if out.effort not in EFFORTS:
            out.effort = "high"
        if out.profile not in ("write", "ask", "minimal"):
            out.profile = "write"
        return out


def _configs(raw: Any, cls: Any) -> List[Any]:
    """Server or agent configs from saved JSON, skipping broken entries and repeated names."""
    out: List[Any] = []
    if not isinstance(raw, list):
        return out
    names = {f.name for f in fields(cls)}
    for item in raw:
        if not isinstance(item, dict) or not str(item.get("name") or "").strip():
            continue
        values = {k: v for k, v in item.items() if k in names}
        for key in ("args", "secret_names"):
            values[key] = [str(v) for v in values.get(key) or []] if isinstance(values.get(key), list) else []
        if "env" in values:
            values["env"] = {str(k): str(v) for k, v in values["env"].items()} if isinstance(values["env"], dict) else {}
        try:
            config = cls(**values)
        except TypeError:
            continue
        if config.name not in {c.name for c in out}:
            out.append(config)
    return out


#: The settings last loaded or saved (``credential_source`` reads the federation from them).
_last: Optional[AgentSettings] = None


def config_path() -> Path:
    """``agents.json`` in the Pyzed config folder."""
    from ..designer.settings import config_dir

    return config_dir() / "agents.json"


def load(path: Optional[Path] = None) -> AgentSettings:
    """The saved agent settings (defaults when there are none)."""
    global _last
    try:
        data = json.loads((path or config_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    _last = AgentSettings.from_dict(data) if isinstance(data, dict) else AgentSettings()
    return _last


def save(settings: AgentSettings, path: Optional[Path] = None) -> Optional[Path]:
    """Writes the settings; ``None`` when the folder is not writable. Never contains secrets."""
    global _last
    _last = settings
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


def saved_secret(provider_id: str, store: Optional[_secrets.SecretStore] = None) -> Optional[str]:
    """What the keychain holds for ``provider_id`` (a key, or an OAuth token as JSON)."""
    return (store or _secrets.store()).get(key_name(provider_id))


def save_token(provider_id: str, token: Dict[str, Any], store: Optional[_secrets.SecretStore] = None) -> bool:
    """Keeps an OAuth token (``access_token``, ``refresh_token``, ``expires_at``...) in the keychain."""
    return (store or _secrets.store()).set(key_name(provider_id), json.dumps(token))


def api_key(provider_id: str, store: Optional[_secrets.SecretStore] = None,
            settings: Optional[AgentSettings] = None) -> Optional[str]:
    """The key of ``provider_id``: the saved one (an OAuth token is refreshed when it is about to expire),
    its environment variable, or (Vertex AI) the Google Cloud credentials of this computer."""
    store = store or _secrets.store()
    saved = store.get(key_name(provider_id))
    if saved and saved.startswith("{"):
        return _access_token(provider_id, saved, store, settings or _last or AgentSettings())
    if saved:
        return saved
    env = PROVIDERS[provider_id].key_env
    if env and os.environ.get(env):
        return os.environ[env]
    if provider_id == "vertex":
        from . import login

        return login.google_default_token()
    return None


def _access_token(provider_id: str, saved: str, store: _secrets.SecretStore, settings: AgentSettings) -> Optional[str]:
    try:
        token = json.loads(saved)
    except ValueError:
        return None
    expires = float(token.get("expires_at") or 0)
    if expires and time.time() > expires - 60 and token.get("refresh_token"):
        from . import login

        token = login.refresh(provider_id, token, settings)
        store.set(key_name(provider_id), json.dumps(token))
    return token.get("access_token") or None


def split_command(text: str) -> List[str]:
    """A command line typed by the user as a program and its arguments, the way this platform's
    shell splits it (backslashes in Windows paths are kept). Raises ``ValueError`` on unbalanced quotes."""
    import shlex

    if os.name != "nt":
        return shlex.split(text)
    lexer = shlex.shlex(text, posix=True)
    lexer.whitespace_split, lexer.escape = True, ""  # Windows paths use backslashes, not escapes
    return list(lexer)


def join_command(parts: List[str]) -> str:
    """The inverse of ``split_command``."""
    import shlex
    import subprocess

    return subprocess.list2cmdline(parts) if os.name == "nt" else shlex.join(parts)


def looks_like_key(provider_id: str, text: str) -> bool:
    """Whether ``text`` (say, what was just copied) looks like a key of ``provider_id``."""
    text = text.strip()
    if not 20 <= len(text) <= 300 or any(ch.isspace() for ch in text):
        return False
    provider = PROVIDERS[provider_id]
    if not provider.key_prefixes:
        return text.isascii() and text.replace("-", "").replace("_", "").replace(".", "").isalnum()
    if provider_id != "anthropic" and text.startswith("sk-ant-"):
        return False
    if provider_id not in ("openrouter",) and text.startswith("sk-or-"):
        return False
    return text.startswith(provider.key_prefixes)


def credential_source(provider_id: str, store: Optional[_secrets.SecretStore] = None,
                      settings: Optional[AgentSettings] = None) -> str:
    """Where the provider's credentials come from: ``"keychain"``, ``"session"`` (memory only), ``"oauth"``
    (signed in, token in the keychain), ``"env"``, ``"federation"`` (Claude, workload identity federation),
    ``"ant"`` (Anthropic CLI profile), ``"gcloud"`` (Google Cloud credentials), ``"none needed"`` or ``""``."""
    store = store or _secrets.store()
    settings = settings or _last or AgentSettings()
    saved = store.get(key_name(provider_id))
    if saved:
        if saved.startswith("{"):
            return "oauth"
        return "keychain" if store.secure else "session"
    provider = PROVIDERS[provider_id]
    if provider_id == "anthropic" and (settings.federation.enabled or (
            os.environ.get("ANTHROPIC_FEDERATION_RULE_ID") and os.environ.get("ANTHROPIC_ORGANIZATION_ID"))):
        return "federation"
    if provider.key_env and os.environ.get(provider.key_env):
        return "env"
    if provider_id == "anthropic":
        from .login import ant_signed_in

        if ant_signed_in():
            return "ant"
    if provider_id == "vertex":
        from .login import google_default_credentials

        if google_default_credentials() is not None:
            return "gcloud"
    if provider_id == "acp":
        return "none needed" if settings.acp_agents else ""
    if not provider.needs_key:
        return "none needed"
    return ""


def is_ready(provider_id: str, store: Optional[_secrets.SecretStore] = None,
             settings: Optional[AgentSettings] = None) -> bool:
    """Whether ``provider_id`` can be used now."""
    return bool(credential_source(provider_id, store, settings))


def google_project() -> str:
    """The Google Cloud project of this computer's credentials or environment ("" when unknown)."""
    for env in ("GOOGLE_CLOUD_PROJECT", "CLOUDSDK_CORE_PROJECT", "GCLOUD_PROJECT"):
        if os.environ.get(env):
            return os.environ[env]
    from .login import google_default_credentials

    found = google_default_credentials()
    return str((found or {}).get("quota_project_id") or "")
