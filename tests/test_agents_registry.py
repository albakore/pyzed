"""The ACP Registry: reading the index, caching it, and installing, updating and removing agents."""

import hashlib
import http.server
import io
import json
import os
import socket
import stat
import sys
import tarfile
import threading
import time
import zipfile
from pathlib import Path

import pytest
from pyzed.agents import providers, registry

TARGET = "linux-x86_64"


def _index(*agents):
    return {"version": "1.0.0", "agents": list(agents), "extensions": []}


CLAUDE = {"id": "claude-acp", "name": "Claude Agent", "version": "0.93.0", "description": "Claude Code over ACP",
          "icon": "https://cdn.agentclientprotocol.com/registry/v1/latest/claude-acp.svg",
          "repository": "https://github.com/agentclientprotocol/claude-agent-acp",
          "distribution": {"npx": {"package": "@agentclientprotocol/claude-agent-acp@0.93.0"}}}
GEMINI = {"id": "gemini", "name": "Gemini CLI", "version": "0.64.0",
          "distribution": {"npx": {"package": "@google/gemini-cli@0.64.0", "args": ["--acp"]}}}
CODEX = {"id": "codex-acp", "name": "Codex", "version": "2.2.2",
         "distribution": {"npx": {"package": "@agentclientprotocol/codex-acp@2.2.2"}}}


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True


@pytest.fixture
def served(monkeypatch):
    """A local web server: ``served.files[path] = bytes`` publishes a file; ``served.hits`` counts requests."""
    for name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    files, hits = {}, []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            body = files.get(self.path)
            if body is None:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    server = _Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    server.files, server.hits = files, hits
    server.url = f"http://127.0.0.1:{server.server_address[1]}"
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def config(tmp_path, monkeypatch):
    folder = tmp_path / "config"
    monkeypatch.setenv("PYZED_CONFIG_DIR", str(folder))
    monkeypatch.setattr(registry, "platform_target", lambda: TARGET)
    return folder


def _closed_port_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}/registry.json"


def _zip(files, modes=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in files.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = ((modes or {}).get(name, 0o644)) << 16
            zf.writestr(info, data)
    return buffer.getvalue()


def _tar(files, mode="w:gz"):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode=mode) as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            tf.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _binary_agent(url, *, version="1.0.0", sha256=None, cmd="./bin/agent", args=("--acp",)):
    entry = {"archive": url, "cmd": cmd, "args": list(args), "env": {"AGENT_MODE": "acp"}}
    if sha256 is not None:
        entry["sha256"] = sha256
    return registry.RegistryAgent.from_dict({
        "id": "native", "name": "Native Agent", "version": version,
        "distribution": {"binary": {TARGET: entry}, "npx": {"package": "native@1"}}})


# -- parsing ---------------------------------------------------------------------------------------

def test_entries_are_parsed_and_broken_ones_skipped():
    agents = registry.parse(_index(
        CLAUDE, GEMINI, CODEX,
        {"id": "no-way", "name": "Nothing to install", "version": "1.0.0"},
        {"id": "../evil", "version": "1.0.0", "distribution": {"npx": {"package": "x"}}},
        {"id": "bad-version", "version": "../1", "distribution": {"npx": {"package": "x"}}},
        {"name": "No id", "distribution": {"npx": {"package": "x"}}},
        {"id": "escape", "version": "1.0.0",
         "distribution": {"binary": {TARGET: {"archive": "https://x/a.zip", "cmd": "../../bin/sh"}}}},
        "not a dict",
        dict(CLAUDE, name="A repeated id"),
    ))
    assert [a.id for a in agents] == ["claude-acp", "gemini", "codex-acp"]
    claude = agents[0]
    assert claude.name == "Claude Agent" and claude.version == "0.93.0" and claude.description
    assert claude.icon.endswith(".svg") and claude.repository and claude.website == ""
    assert claude.method == "npx"
    assert registry.find(agents, "gemini").distribution["npx"]["args"] == ["--acp"]
    assert registry.find(agents, "missing") is None
    assert registry.RegistryAgent.from_dict(None) is None
    with pytest.raises(ValueError):
        registry.parse({"agents": "nope"})


def test_tolerates_missing_fields_and_hashes():
    agent = registry.RegistryAgent.from_dict({"id": "tiny", "distribution": {"uvx": {"package": "tiny-acp"}}})
    assert agent.name == "tiny" and agent.version == "" and agent.method == "uvx"
    assert agent.distribution["uvx"] == {"package": "tiny-acp", "args": [], "env": {}}
    assert len({agent, agent}) == 1


def test_preferred_method(config, monkeypatch):
    agent = _binary_agent("https://example.com/agent.tar.gz")
    assert agent.method == "binary" and agent.env == {"AGENT_MODE": "acp"}
    monkeypatch.setattr(registry, "platform_target", lambda: "windows-aarch64")
    assert agent.method == "npx"
    monkeypatch.setattr(registry, "platform_target", lambda: None)
    assert agent.method == "npx"


@pytest.mark.parametrize("plat,machine,expected", [
    ("linux", "x86_64", "linux-x86_64"), ("linux", "aarch64", "linux-aarch64"),
    ("darwin", "arm64", "darwin-aarch64"), ("darwin", "x86_64", "darwin-x86_64"),
    ("win32", "AMD64", "windows-x86_64"), ("win32", "ARM64", "windows-aarch64"),
    ("linux", "riscv64", None), ("sunos5", "x86_64", None),
])
def test_platform_target(monkeypatch, plat, machine, expected):
    monkeypatch.setattr(registry.sys, "platform", plat)
    monkeypatch.setattr(registry.platform, "machine", lambda: machine)
    assert registry.platform_target() == expected


# -- the cache -------------------------------------------------------------------------------------

def test_fetch_downloads_and_caches(config, served):
    served.files["/registry.json"] = json.dumps(_index(CLAUDE, GEMINI)).encode()
    url = served.url + "/registry.json"
    assert [a.id for a in registry.fetch(url=url)] == ["claude-acp", "gemini"]
    assert (config / "acp-registry.json").is_file()
    served.files["/registry.json"] = json.dumps(_index(CODEX)).encode()
    assert [a.id for a in registry.fetch(url=url)] == ["claude-acp", "gemini"]  # fresh cache, no request
    assert len(served.hits) == 1
    assert [a.id for a in registry.fetch(url=url, refresh=True)] == ["codex-acp"]
    assert len(served.hits) == 2


def test_stale_cache_is_refreshed(config, served, tmp_path):
    cache = tmp_path / "custom.json"
    cache.write_text(json.dumps(_index(CLAUDE)))
    old = time.time() - 7200
    os.utime(cache, (old, old))
    served.files["/registry.json"] = json.dumps(_index(GEMINI)).encode()
    assert [a.id for a in registry.fetch(url=served.url + "/registry.json", cache=cache)] == ["gemini"]
    assert len(served.hits) == 1 and "gemini" in cache.read_text()
    assert [a.id for a in registry.fetch(url=served.url + "/registry.json", cache=cache, max_age=0)] == ["gemini"]
    assert len(served.hits) == 2


def test_offline_falls_back_to_the_stale_cache(config, served):
    cache = config / "acp-registry.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps(_index(CLAUDE)))
    old = time.time() - 30 * 86400
    os.utime(cache, (old, old))
    assert [a.id for a in registry.fetch(url=_closed_port_url(), timeout=2)] == ["claude-acp"]
    # A server error or a broken index also keeps the saved copy.
    assert [a.id for a in registry.fetch(url=served.url + "/missing.json", refresh=True)] == ["claude-acp"]
    served.files["/broken.json"] = b"{not json"
    assert [a.id for a in registry.fetch(url=served.url + "/broken.json", refresh=True)] == ["claude-acp"]
    assert "claude-acp" in cache.read_text()


def test_offline_without_a_cache_raises(config):
    with pytest.raises(registry.RegistryError):
        registry.fetch(url=_closed_port_url(), timeout=2)


# -- commands --------------------------------------------------------------------------------------

def test_config_for_npx(config):
    gemini = registry.RegistryAgent.from_dict(GEMINI)
    c = registry.config_for(gemini)
    assert isinstance(c, providers.ACPAgentConfig)
    assert (c.name, c.command, c.args) == ("gemini", "npx", ["-y", "@google/gemini-cli@0.64.0", "--acp"])
    assert (c.title, c.registry_id, c.version) == ("Gemini CLI", "gemini", "0.64.0")
    claude = registry.config_for(registry.RegistryAgent.from_dict(CLAUDE))
    assert claude.args == ["-y", "@agentclientprotocol/claude-agent-acp@0.93.0"]


def test_config_for_uvx(config, monkeypatch, tmp_path):
    agent = registry.RegistryAgent.from_dict({"id": "py-agent", "name": "Py Agent", "version": "0.1.0",
                                              "distribution": {"uvx": {"package": "py-agent==0.1.0",
                                                                       "args": ["acp"]}}})
    from pyzed import project

    monkeypatch.setattr(project, "find_uv", lambda: None)
    assert registry.config_for(agent).command == "uvx"
    exe = ".exe" if os.name == "nt" else ""
    (tmp_path / f"uv{exe}").write_text("")
    (tmp_path / f"uvx{exe}").write_text("")
    monkeypatch.setattr(project, "find_uv", lambda: str(tmp_path / f"uv{exe}"))
    c = registry.config_for(agent)
    assert c.command == str(tmp_path / f"uvx{exe}") and c.args == ["py-agent==0.1.0", "acp"]


def test_config_for_binary(config, tmp_path):
    agent = _binary_agent("https://example.com/agent.zip")
    c = registry.config_for(agent)
    assert c.command == str(config / "agent-servers" / "native" / "1.0.0" / "bin" / "agent")
    assert c.args == ["--acp"] and c.registry_id == "native" and c.version == "1.0.0"
    assert registry.config_for(agent, root=tmp_path).command == str(tmp_path / "native" / "1.0.0" / "bin" / "agent")


def test_config_for_without_a_method(config, monkeypatch):
    agent = registry.RegistryAgent.from_dict({"id": "mac-only", "version": "1.0.0", "distribution": {
        "binary": {"darwin-aarch64": {"archive": "https://x/a.zip", "cmd": "./a"}}}})
    assert agent.method is None
    with pytest.raises(registry.RegistryError):
        registry.config_for(agent)


# -- installing ------------------------------------------------------------------------------------

def _publish(served, name, data):
    served.files["/" + name] = data
    return f"{served.url}/{name}", hashlib.sha256(data).hexdigest()


@pytest.mark.skipif(sys.platform == "win32", reason="executable bits")
def test_install_binary_zip_with_checksum(config, served):
    url, digest = _publish(served, "agent.zip", _zip({"bin/agent": b"#!/bin/sh\necho hi\n", "README": b"hi"}))
    old = config / "agent-servers" / "native" / "0.9.0"
    old.mkdir(parents=True)
    (old / "stale").write_text("x")
    messages = []
    c = registry.install(_binary_agent(url, sha256=digest.upper()), on_progress=messages.append)
    path = config / "agent-servers" / "native" / "1.0.0" / "bin" / "agent"
    assert c.command == str(path) and path.read_bytes().startswith(b"#!/bin/sh")
    assert path.stat().st_mode & stat.S_IXUSR
    assert sorted(p.name for p in (config / "agent-servers" / "native").iterdir()) == ["1.0.0"]  # older version removed
    assert any("Downloading" in m for m in messages) and messages[-1] == "Native Agent 1.0.0 is installed"
    from pyzed.agents import acp

    assert acp.installed(c)


def test_install_binary_tarball_and_raw(config, served):
    url, _ = _publish(served, "agent.tar.gz", _tar({"bin/agent": b"tar binary"}))
    c = registry.install(_binary_agent(url))
    assert Path(c.command).read_bytes() == b"tar binary"
    url, digest = _publish(served, "agent-linux", b"raw binary")
    c = registry.install(_binary_agent(url, version="1.1.0", sha256=digest, cmd="./agent"))
    assert Path(c.command).read_bytes() == b"raw binary"
    assert sorted(p.name for p in (config / "agent-servers" / "native").iterdir()) == ["1.1.0"]


def test_install_binary_wrong_checksum_keeps_nothing(config, served):
    url, _ = _publish(served, "agent.zip", _zip({"bin/agent": b"changed"}))
    with pytest.raises(registry.RegistryError, match="SHA-256"):
        registry.install(_binary_agent(url, sha256="0" * 64))
    assert not (config / "agent-servers" / "native" / "1.0.0").exists()
    assert list((config / "agent-servers" / "native").iterdir()) == []


def test_install_binary_missing_cmd(config, served):
    url, _ = _publish(served, "agent.zip", _zip({"other": b"x"}))
    with pytest.raises(registry.RegistryError, match="not in the download"):
        registry.install(_binary_agent(url))


@pytest.mark.parametrize("name", ["../../escaped", "/tmp/absolute-escaped", "bin/../../escaped", "C:/escaped"])
def test_zip_slip_is_rejected(config, served, tmp_path, name):
    url, _ = _publish(served, "evil.zip", _zip({"bin/agent": b"ok", name: b"evil"}))
    with pytest.raises(registry.RegistryError, match="unsafe"):
        registry.install(_binary_agent(url))
    assert not (config / "agent-servers" / "native" / "1.0.0").exists()
    assert not (config / "agent-servers" / "escaped").exists() and not (config / "escaped").exists()


@pytest.mark.parametrize("name", ["../escaped", "/abs/escaped"])
def test_tar_traversal_is_rejected(config, served, name):
    url, _ = _publish(served, "evil.tgz", _tar({"bin/agent": b"ok", name: b"evil"}))
    with pytest.raises(registry.RegistryError, match="unsafe"):
        registry.install(_binary_agent(url))
    assert not (config / "agent-servers" / "native" / "1.0.0").exists()


def test_tar_links_outside_are_rejected_without_the_data_filter(config, served, monkeypatch):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tf:
        info = tarfile.TarInfo("bin/agent")
        info.type, info.linkname = tarfile.SYMTYPE, "../../../../etc/passwd"
        tf.addfile(info)
    url, _ = _publish(served, "link.tar.gz", buffer.getvalue())
    monkeypatch.delattr(tarfile, "data_filter", raising=False)
    with pytest.raises(registry.RegistryError, match="unsafe"):
        registry.install(_binary_agent(url))


def test_install_npx_warms_the_npm_cache(config, monkeypatch):
    from pyzed import project

    calls = []
    monkeypatch.setattr(registry.shutil, "which", lambda name: "/usr/bin/npm" if name == "npm" else None)
    monkeypatch.setattr(project, "execute", lambda args, cwd=None, *, timeout=None: (
        calls.append((list(args), timeout)) or project.Result(list(args), 1, "offline")))
    messages = []
    c = registry.install(registry.RegistryAgent.from_dict(CODEX), on_progress=messages.append)
    assert calls == [(["/usr/bin/npm", "cache", "add", "@agentclientprotocol/codex-acp@2.2.2"], registry.NPM_TIMEOUT)]
    assert c.command == "npx" and c.version == "2.2.2"
    assert any("npx will try" in m for m in messages)  # a failed download is not fatal
    monkeypatch.setattr(registry.shutil, "which", lambda name: None)
    calls.clear()
    registry.install(registry.RegistryAgent.from_dict(CODEX))
    assert calls == []


def test_install_uvx_downloads_nothing(config, monkeypatch):
    from pyzed import project

    monkeypatch.setattr(project, "execute", lambda *a, **k: pytest.fail("nothing should run"))
    agent = registry.RegistryAgent.from_dict({"id": "py", "version": "1.0.0", "distribution": {"uvx": {"package": "py"}}})
    assert registry.install(agent).args == ["py"]


# -- updates and removal ---------------------------------------------------------------------------

@pytest.mark.parametrize("older,newer", [
    ("1.2.3", "1.2.4"), ("1.2.9", "1.10.0"), ("0.9.0", "1.0.0"), ("1.2.3-preview.1", "1.2.3"),
    ("1.2.3-preview.2", "1.2.3-preview.10"), ("1.2.2", "1.2.3-preview.1"), ("v1.0", "1.0.1"), ("", "0.0.1"),
])
def test_version_order(older, newer):
    assert registry.version_key(older) < registry.version_key(newer)


def test_equal_versions():
    assert registry.version_key("1.2") == registry.version_key("1.2.0") == registry.version_key("v1.2.0+build5")


def test_update_available():
    agents = registry.parse(_index(CLAUDE, dict(GEMINI, version="0.65.0-preview.1")))
    def cfg(registry_id, version):
        return providers.ACPAgentConfig(registry_id or "custom", "npx", registry_id=registry_id, version=version)
    assert registry.update_available(cfg("claude-acp", "0.92.5"), agents).version == "0.93.0"
    assert registry.update_available(cfg("claude-acp", "0.93.0"), agents) is None
    assert registry.update_available(cfg("claude-acp", "0.94.0"), agents) is None
    assert registry.update_available(cfg("claude-acp", "0.93.0-preview.3"), agents).version == "0.93.0"
    assert registry.update_available(cfg("gemini", "0.65.0"), agents) is None  # preview is older than the release
    assert registry.update_available(cfg("gemini", "0.64.0"), agents).version == "0.65.0-preview.1"
    assert registry.update_available(cfg("gone", "1.0.0"), agents) is None
    assert registry.update_available(cfg("", ""), agents) is None
    assert registry.update_available(cfg("claude-acp", ""), agents) is not None


def test_uninstall(config, served):
    url, _ = _publish(served, "agent.zip", _zip({"bin/agent": b"x"}))
    c = registry.install(_binary_agent(url))
    assert (config / "agent-servers" / "native").is_dir()
    assert registry.uninstall(c) is True
    assert not (config / "agent-servers" / "native").exists()
    assert registry.uninstall(c) is False
    (config / "agent-servers" / "keep").mkdir(parents=True)
    assert registry.uninstall(providers.ACPAgentConfig("x", "npx", registry_id="..")) is False
    assert registry.uninstall(providers.ACPAgentConfig("x", "npx")) is False
    assert (config / "agent-servers" / "keep").is_dir()


def test_installed_agent_round_trips_through_settings(config, tmp_path):
    c = registry.config_for(registry.RegistryAgent.from_dict(GEMINI))
    settings = providers.AgentSettings(acp_agents=[c])
    path = providers.save(settings, tmp_path / "agents.json")
    loaded = providers.load(path).acp_agent("gemini")
    assert (loaded.registry_id, loaded.version, loaded.title, loaded.args) == (
        "gemini", "0.64.0", "Gemini CLI", ["-y", "@google/gemini-cli@0.64.0", "--acp"])
