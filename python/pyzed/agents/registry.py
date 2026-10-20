"""External agents from the ACP Registry, installed and updated the way Zed does it.

The registry (https://agentclientprotocol.com) lists agents that speak the Agent Client Protocol and
how to get each one: an ``npx`` package, a ``uvx`` package or a binary archive per platform. Pyzed
downloads the index, keeps a copy in the config folder (so the list shows up offline), installs an
agent and turns it into an ``ACPAgentConfig`` the Agent panel can run:

    from pyzed.agents import providers, registry

    agents = registry.fetch()                         # cached for an hour
    claude = registry.find(agents, "claude-acp")
    config = registry.install(claude, on_progress=print)
    settings = providers.load()
    settings.acp_agents.append(config)
    providers.save(settings)

    newer = registry.update_available(config, registry.fetch(refresh=True))
    if newer:
        registry.install(newer)

Binary agents are unpacked into ``agent-servers/<id>/<version>/`` in the Pyzed config folder; older versions
are removed once a new one is in place. ``npx`` and ``uvx`` agents are run by those tools, which keep
their own caches.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import platform
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .providers import ACPAgentConfig

REGISTRY_URL = "https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json"
#: Install methods, in the order they are preferred.
METHODS = ("binary", "npx", "uvx")
#: Platform targets the registry names binaries for.
TARGETS = ("darwin-aarch64", "darwin-x86_64", "linux-aarch64", "linux-x86_64", "windows-aarch64", "windows-x86_64")
#: How long ``npm cache add`` may take to download an ``npx`` agent, in seconds.
NPM_TIMEOUT = 300.0

ProgressCallback = Callable[[str], None]

#: Ids and versions become folder names, so they must be plain names.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_CHUNK = 64 * 1024


class RegistryError(RuntimeError):
    """The registry could not be read, or an agent could not be installed."""


# -- the index -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class RegistryAgent:
    """An agent listed in the ACP Registry."""

    id: str
    name: str
    version: str
    description: str = ""
    #: URL of the agent's SVG icon ("" when it has none).
    icon: str = ""
    repository: str = ""
    website: str = ""
    #: Install methods: ``"npx"``, ``"uvx"`` and ``"binary"`` (platform target -> archive), as in the registry.
    distribution: Dict[str, Any] = field(default_factory=dict, hash=False)

    @classmethod
    def from_dict(cls, data: Any) -> Optional["RegistryAgent"]:
        """The agent of a registry entry; ``None`` when the entry is broken (no usable id, an unsafe version,
        or no install method Pyzed understands)."""
        if not isinstance(data, dict):
            return None
        agent_id = _text(data.get("id"))
        version = _text(data.get("version"))
        if not _SAFE_NAME.match(agent_id) or (version and not _SAFE_NAME.match(version)):
            return None
        distribution = _distribution(data.get("distribution"))
        if not distribution:
            return None
        return cls(id=agent_id, name=_text(data.get("name")) or agent_id, version=version,
                   description=_text(data.get("description")), icon=_text(data.get("icon")),
                   repository=_text(data.get("repository")), website=_text(data.get("website")),
                   distribution=distribution)

    @property
    def method(self) -> Optional[str]:
        """How the agent is installed on this computer: ``"binary"`` when there is one for this platform,
        else ``"npx"``, else ``"uvx"``; ``None`` when none of them fits."""
        target = platform_target()
        if target and target in self.distribution.get("binary", {}):
            return "binary"
        return next((m for m in ("npx", "uvx") if m in self.distribution), None)

    @property
    def env(self) -> Dict[str, str]:
        """Environment variables the registry asks to set when the agent runs (for ``method``)."""
        entry = _entry(self)
        return dict(entry.get("env") or {}) if entry else {}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _strings(value: Any) -> List[str]:
    return [str(v) for v in value if isinstance(v, (str, int, float))] if isinstance(value, list) else []


def _env(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items() if isinstance(k, str) and isinstance(v, (str, int, float))}


def _distribution(raw: Any) -> Dict[str, Any]:
    """The install methods of an entry, keeping only well-formed ones."""
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    for kind in ("npx", "uvx"):
        entry = raw.get(kind)
        if isinstance(entry, dict) and _text(entry.get("package")):
            out[kind] = {"package": _text(entry["package"]), "args": _strings(entry.get("args")),
                         "env": _env(entry.get("env"))}
    binaries = raw.get("binary")
    if isinstance(binaries, dict):
        targets: Dict[str, Any] = {}
        for target, entry in binaries.items():
            if not (isinstance(target, str) and isinstance(entry, dict)):
                continue
            archive, cmd = _text(entry.get("archive")), _text(entry.get("cmd"))
            if archive.startswith(("https://", "http://")) and cmd and _relative_cmd(cmd) is not None:
                targets[target] = {"archive": archive, "cmd": cmd, "args": _strings(entry.get("args")),
                                   "env": _env(entry.get("env")), "sha256": _text(entry.get("sha256")).lower()}
        if targets:
            out["binary"] = targets
    return out


def _entry(agent: RegistryAgent) -> Optional[Dict[str, Any]]:
    """The distribution entry of the agent's preferred ``method``."""
    method = agent.method
    if method == "binary":
        return agent.distribution["binary"][platform_target()]
    return agent.distribution.get(method) if method else None


def platform_target() -> Optional[str]:
    """This computer as a registry platform target, e.g. ``"linux-x86_64"``; ``None`` when it has none."""
    if sys.platform.startswith("linux"):
        system = "linux"
    elif sys.platform == "darwin":
        system = "darwin"
    elif sys.platform in ("win32", "cygwin"):
        system = "windows"
    else:
        return None
    machine = platform.machine().lower()
    arch = {"x86_64": "x86_64", "amd64": "x86_64", "x64": "x86_64",
            "aarch64": "aarch64", "arm64": "aarch64", "armv8": "aarch64"}.get(machine)
    return f"{system}-{arch}" if arch else None


def parse(data: Any) -> List[RegistryAgent]:
    """The agents of a registry index (broken entries and repeated ids are skipped). Raises ``ValueError``
    when ``data`` is not an index."""
    if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
        raise ValueError("not an ACP registry index")  # noqa: TRY004 - read as a broken download
    out: List[RegistryAgent] = []
    seen = set()
    for raw in data["agents"]:
        agent = RegistryAgent.from_dict(raw)
        if agent is not None and agent.id not in seen:
            seen.add(agent.id)
            out.append(agent)
    return out


def _config_dir() -> Path:
    from ..designer.settings import config_dir

    return config_dir()


def cache_path() -> Path:
    """Where the last downloaded index is kept: ``acp-registry.json`` in the Pyzed config folder."""
    return _config_dir() / "acp-registry.json"


def _read_cache(path: Path) -> Optional[List[RegistryAgent]]:
    try:
        return parse(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def _write_atomic(path: Path, data: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temp.write_bytes(data)
        os.replace(temp, path)
    except OSError:
        pass  # a read-only config folder only costs the offline copy


def _open(url: str, timeout: float) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "pyzed", "Accept": "*/*"})
    return urllib.request.urlopen(request, timeout=timeout)


def fetch(*, url: str = REGISTRY_URL, cache: Optional[Path] = None, max_age: float = 3600.0,
          timeout: float = 10.0, refresh: bool = False) -> List[RegistryAgent]:
    """The agents of the registry. The copy in ``cache`` is used while it is younger than ``max_age``
    seconds (unless ``refresh``); otherwise the index is downloaded and saved there. When the download
    fails, the saved copy is used however old it is. Raises ``RegistryError`` when there is neither."""
    cache = cache or cache_path()
    if not refresh:
        try:
            fresh = max_age > 0 and time.time() - cache.stat().st_mtime < max_age
        except OSError:
            fresh = False
        cached = _read_cache(cache) if fresh else None
        if cached is not None:
            return cached
    try:
        with _open(url, timeout) as response:
            body = response.read()
        agents = parse(json.loads(body.decode("utf-8")))
    except (OSError, ValueError, http.client.HTTPException) as err:
        stale = _read_cache(cache)
        if stale is not None:
            return stale
        raise RegistryError(f"Could not read the ACP registry: {err}") from err
    _write_atomic(cache, body)
    return agents


def find(agents: Sequence[RegistryAgent], agent_id: str) -> Optional[RegistryAgent]:
    """The agent of ``agents`` with the id ``agent_id``."""
    return next((a for a in agents if a.id == agent_id), None)


# -- running and installing ----------------------------------------------------------------------


def agents_dir() -> Path:
    """Where binary agents are unpacked: ``agent-servers`` in the Pyzed config folder (``agents`` holds
    the saved threads)."""
    return _config_dir() / "agent-servers"


def _relative_cmd(cmd: str) -> Optional[PurePosixPath]:
    """A binary's ``cmd`` as a path inside its folder (``None`` when it would point outside)."""
    path = PurePosixPath(cmd.replace("\\", "/"))
    if path.is_absolute() or re.match(r"^[A-Za-z]:", cmd) or ".." in path.parts:
        return None
    parts = [p for p in path.parts if p not in ("", ".")]
    return PurePosixPath(*parts) if parts else None


def version_dir(agent: RegistryAgent, root: Optional[Path] = None) -> Path:
    """The folder a binary agent of this version is unpacked into."""
    return (root or agents_dir()) / agent.id / (agent.version or "current")


def _binary_path(agent: RegistryAgent, entry: Dict[str, Any], root: Optional[Path]) -> Path:
    relative = _relative_cmd(entry["cmd"])
    if relative is None:
        raise RegistryError(f"{agent.name}: its command {entry['cmd']!r} points outside its folder")
    return version_dir(agent, root).joinpath(*relative.parts)


def _uvx() -> str:
    from ..project import find_uv

    uv = find_uv()
    if uv:
        uvx = Path(uv).with_name("uvx" + (".exe" if os.name == "nt" else ""))
        if uvx.is_file():
            return str(uvx)
    return "uvx"


def config_for(agent: RegistryAgent, *, root: Optional[Path] = None) -> ACPAgentConfig:
    """The settings entry that runs ``agent`` with its preferred ``method``; ``root`` is where binary
    agents are unpacked (``agents_dir()`` by default). Raises ``RegistryError`` when no method fits."""
    method, entry = agent.method, _entry(agent)
    if method is None or entry is None:
        raise RegistryError(f"{agent.name} cannot be installed on this computer")
    if method == "npx":
        command, args = "npx", ["-y", entry["package"], *entry["args"]]
    elif method == "uvx":
        command, args = _uvx(), [entry["package"], *entry["args"]]
    else:
        command, args = str(_binary_path(agent, entry, root)), list(entry["args"])
    return ACPAgentConfig(agent.id, command, args, title=agent.name, registry_id=agent.id, version=agent.version,
                          env=dict(agent.env))


def install(agent: RegistryAgent, *, on_progress: Optional[ProgressCallback] = None,
            timeout: float = 60.0) -> ACPAgentConfig:
    """Installs ``agent`` and returns the settings entry that runs it. ``npx`` packages are put in npm's
    cache beforehand when ``npm`` is found (a failure there is not fatal: ``npx`` downloads it later);
    ``uvx`` packages are downloaded when they first run; binaries are downloaded, checked against their
    SHA-256 and unpacked. Raises ``RegistryError`` when a binary cannot be installed."""
    report = on_progress or (lambda _message: None)
    config = config_for(agent)
    if agent.method == "npx":
        _prefetch_npm(agent, _entry(agent) or {}, report)
    elif agent.method == "binary":
        _install_binary(agent, _entry(agent) or {}, report, timeout)
    report(f"{agent.name} {agent.version} is installed" if agent.version else f"{agent.name} is installed")
    return config


def _prefetch_npm(agent: RegistryAgent, entry: Dict[str, Any], report: ProgressCallback) -> None:
    npm = shutil.which("npm")
    if not npm:
        return
    from ..project import execute

    report(f"Downloading {entry['package']}…")
    result = execute([npm, "cache", "add", entry["package"]], timeout=NPM_TIMEOUT)
    if not result.ok:
        report(f"npm could not download {entry['package']}; npx will try when {agent.name} starts")


def _install_binary(agent: RegistryAgent, entry: Dict[str, Any], report: ProgressCallback, timeout: float) -> None:
    home = agents_dir() / agent.id
    target = version_dir(agent)
    command = _binary_path(agent, entry, None)
    home.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=home))
    download = staging.with_name(staging.name + ".download")
    try:
        digest = _download(entry["archive"], download, report, agent.name, timeout)
        expected = entry.get("sha256", "").removeprefix("sha256:")
        if expected and digest != expected:
            raise RegistryError(f"{agent.name}: the download is damaged or was changed (SHA-256 does not match)")
        report(f"Unpacking {agent.name}…")
        relative = command.relative_to(target)
        _unpack(download, entry["archive"], staging, relative)
        unpacked = staging / relative
        if not unpacked.is_file():
            raise RegistryError(f"{agent.name}: {entry['cmd']} is not in the download")
        _make_executable(unpacked)
        if target.exists():
            shutil.rmtree(target)
        os.replace(staging, target)
    finally:
        download.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)
    _remove_other_versions(home, keep=target.name)


def _download(url: str, dest: Path, report: ProgressCallback, name: str, timeout: float) -> str:
    """Saves ``url`` to ``dest`` and returns its SHA-256 (hex)."""
    digest = hashlib.sha256()
    report(f"Downloading {name}…")
    try:
        with _open(url, timeout) as response, dest.open("wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            done, shown = 0, -1
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                percent = done * 100 // total if total else -1
                if percent >= 0 and percent // 10 != shown // 10:
                    shown = percent
                    report(f"Downloading {name}… {percent}%")
    except (OSError, ValueError, http.client.HTTPException) as err:
        raise RegistryError(f"Could not download {name}: {err}") from err
    return digest.hexdigest()


def _archive_kind(url: str) -> str:
    path = urllib.parse.urlparse(url).path.lower()
    if path.endswith(".zip"):
        return "zip"
    if path.endswith((".tar.gz", ".tgz")):
        return "r:gz"
    if path.endswith((".tar.bz2", ".tbz2")):
        return "r:bz2"
    if path.endswith((".tar.xz", ".txz")):
        return "r:xz"
    if path.endswith(".tar"):
        return "r:"
    return "raw"


def _unpack(archive: Path, url: str, dest: Path, raw_path: Path) -> None:
    """Unpacks ``archive`` into ``dest``; a raw binary is copied there as ``raw_path`` (relative)."""
    kind = _archive_kind(url)
    try:
        if kind == "zip":
            _extract_zip(archive, dest)
        elif kind == "raw":
            (dest / raw_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(archive, dest / raw_path)
        else:
            _extract_tar(archive, dest, kind)
    except (OSError, zipfile.BadZipFile, tarfile.TarError, EOFError) as err:
        raise RegistryError(f"Could not unpack {Path(urllib.parse.urlparse(url).path).name}: {err}") from err


def _inside(dest: Path, name: str) -> Path:
    """Where member ``name`` of an archive goes in ``dest``; raises ``RegistryError`` when it would land
    outside (an absolute path, a drive, or ``..``)."""
    clean = name.replace("\\", "/")
    if clean.startswith("/") or re.match(r"^[A-Za-z]:", clean) or ".." in PurePosixPath(clean).parts:
        raise RegistryError(f"The archive has an unsafe path: {name!r}")
    path = (dest / clean).resolve()
    root = dest.resolve()
    if path != root and root not in path.parents:
        raise RegistryError(f"The archive has an unsafe path: {name!r}")
    return path


def _extract_zip(archive: Path, dest: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        members = zf.infolist()
        for info in members:
            _inside(dest, info.filename)
        for info in members:
            zf.extract(info, dest)
            mode = (info.external_attr >> 16) & 0o777
            if mode & 0o111 and not info.is_dir():
                _make_executable(_inside(dest, info.filename))


def _extract_tar(archive: Path, dest: Path, mode: str) -> None:
    with tarfile.open(archive, mode) as tf:  # type: ignore[call-overload]
        members = tf.getmembers()
        for member in members:
            _inside(dest, member.name)
        if hasattr(tarfile, "data_filter"):  # Python 3.12, and 3.8.17+ / 3.9.17+ / 3.10.12+ / 3.11.4+
            try:
                tf.extractall(dest, filter="data")
            except tarfile.FilterError as err:
                raise RegistryError(f"The archive has an unsafe member: {err}") from err
            return
        for member in members:
            _check_tar_member(dest, member)
        tf.extractall(dest)  # every member was checked above


def _check_tar_member(dest: Path, member: tarfile.TarInfo) -> None:
    """Older Pythons: refuses devices and links that lead outside ``dest``."""
    if member.isfile() or member.isdir():
        return
    if member.issym() or member.islnk():
        base = PurePosixPath(member.name).parent if member.issym() else PurePosixPath()
        _inside(dest, str(base / member.linkname))
        return
    raise RegistryError(f"The archive has an unsupported member: {member.name!r}")


def _make_executable(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def _remove_other_versions(home: Path, keep: str) -> None:
    for child in home.iterdir():
        if child.name == keep:
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def uninstall(config: ACPAgentConfig) -> bool:
    """Removes the files of a registry agent (``agent-servers/<registry_id>``); ``True`` when there were
    some. An agent without a ``registry_id`` (or with an unsafe one) is refused, so the whole folder is never
    removed. ``npx`` and ``uvx`` agents have no files: their tools' caches are left alone."""
    registry_id = (config.registry_id or "").strip()
    if not registry_id or not _SAFE_NAME.match(registry_id):
        return False
    folder = agents_dir() / registry_id
    if not folder.exists():
        return False
    shutil.rmtree(folder, ignore_errors=True)
    return not folder.exists()


# -- updates -------------------------------------------------------------------------------------


def version_key(version: str) -> Tuple[Any, ...]:
    """A sort key for versions like ``"1.2.3"`` and ``"1.2.3-preview.4"``: numbers compare as numbers,
    trailing zeros do not count (``1.2 == 1.2.0``) and a pre-release comes before its release."""
    text = version.strip().lstrip("vV").split("+", 1)[0]
    release, _, pre = text.partition("-")
    numbers = [int(m.group()) if (m := re.match(r"\d+", part)) else 0 for part in release.split(".") if part]
    while numbers and numbers[-1] == 0:
        numbers.pop()
    pre_parts = tuple((0, int(p), "") if p.isdigit() else (1, 0, p.lower()) for p in re.split(r"[.-]", pre) if p)
    return (tuple(numbers), 0 if pre else 1, pre_parts)


def update_available(config: ACPAgentConfig, agents: Sequence[RegistryAgent]) -> Optional[RegistryAgent]:
    """The registry's entry for ``config`` when it has a newer version than the installed one
    (``None`` when it is up to date or did not come from the registry)."""
    if not config.registry_id:
        return None
    latest = find(agents, config.registry_id)
    if latest is None or not latest.version:
        return None
    if config.version and version_key(latest.version) <= version_key(config.version):
        return None
    return latest
