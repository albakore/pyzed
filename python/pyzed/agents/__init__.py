"""AI agents for Pyzed apps and for Pyzed Design.

    pip install "pyzed-ui[agents]"     # Claude support and the system keychain

    from pyzed import agents

    agents.set_key("anthropic", "sk-ant-…")        # saved in the system keychain
    agent = agents.Agent("anthropic:claude-opus-5-5", tools=agents.pyzed_tools())
    print(agent.run("Which pz.ui component shows a list of files?"))

Providers: Anthropic (API key, workload identity federation or ``ant auth login``), OpenAI, Google Gemini,
Google Vertex AI (Google sign-in), GitHub Copilot (GitHub sign-in), OpenRouter, xAI, Mistral, DeepSeek,
Groq, Ollama, LM Studio and any OpenAI-compatible server; external agents (Claude Code, Gemini CLI...)
through the Agent Client Protocol (``agents.acp``); and the tools of MCP servers (``agents.mcp_client``).
Settings live in ``agents.json`` in the Pyzed config folder; keys and tokens live in the operating
system's keychain, never in a file.
"""

from __future__ import annotations

from typing import Optional

from . import acp, llm, login, mcp_client, providers, secrets
from .agent import PROFILES, Agent, Event, Image, Tool, image_block, tool
from .llm import AgentError, Turn, list_models, stream_turn
from .providers import DEFAULT_MODEL, PROVIDERS, AgentSettings, Provider, split_model
from .threads import Thread, ThreadStore
from .tools import file_tools, pyzed_tools

__all__ = [
    "PROFILES", "PROVIDERS", "DEFAULT_MODEL", "Agent", "AgentError", "AgentSettings", "Event", "Image", "Provider",
    "Thread", "ThreadStore", "Tool", "Turn", "acp", "delete_key", "file_tools", "get_key", "image_block",
    "list_models", "llm", "login", "mcp_client", "providers", "pyzed_tools", "secrets", "set_key", "split_model",
    "stream_turn", "tool",
]


def set_key(provider_id: str, key: str) -> bool:
    """Saves the API key of ``provider_id`` in the system keychain; ``False`` when no keychain is available
    (the key is then kept for this session only)."""
    return secrets.store().set(providers.key_name(provider_id), key)


def get_key(provider_id: str) -> Optional[str]:
    """The key of ``provider_id`` (saved, or from its environment variable)."""
    return providers.api_key(provider_id)


def delete_key(provider_id: str) -> None:
    """Forgets the saved key of ``provider_id``."""
    secrets.store().delete(providers.key_name(provider_id))
