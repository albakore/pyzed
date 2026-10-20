"""Agent Skills: folders of instructions an agent reads when a task calls for them.

A skill is a folder holding a ``SKILL.md`` file. The file starts with YAML frontmatter giving at least a
``name`` and a ``description``, followed by Markdown instructions; the folder may also hold scripts,
references and other files the instructions point to. It is the open format Claude Code and other agents
use. Pyzed's built-in agent finds skills in the project, in the user's folders and in Pyzed's own config
folder; external agents such as Claude Code read their own.

    from pyzed import agents
    from pyzed.agents import skills

    found = skills.enabled(skills.discover(project_root), settings)
    agent = agents.Agent(system="..." + skills.prompt(found), tools=skills.tools(found))

``install_folder`` and ``install_git`` copy skills into Pyzed's config folder, ``update`` fetches an
installed skill again from where it came from, and ``remove`` deletes one.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .agent import Tool, tool

if TYPE_CHECKING:
    from .providers import AgentSettings

#: The file that makes a folder a skill.
SKILL_FILE = "SKILL.md"
#: Where an installed skill came from (url, subdir, commit), written next to its SKILL.md.
ORIGIN_FILE = ".pyzed-source.json"
#: Files ``Skill.files`` lists at most.
FILES_LIMIT = 200
#: Bytes of a file ``read_skill_file`` returns at most.
READ_LIMIT = 100_000
#: Seconds a git command may take.
GIT_TIMEOUT = 120
#: Folders never copied nor listed.
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
#: Valid skill names: they become folder names, so no separators and no "..".
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:(?:\s+(.*)|)$")
_BLOCK = re.compile(r"^([>|])([+-]?)\d?$")


class SkillError(RuntimeError):
    """A skill could not be loaded, installed, updated or removed."""


@dataclass
class Skill:
    """A skill found on disk; ``body`` (the instructions) is read the first time it is used."""

    name: str
    description: str
    #: The skill's folder.
    path: Path
    #: Where it was found: ``"project"``, ``"user"``, ``"claude"`` or ``"pyzed"``.
    source: str
    _body: Optional[str] = field(default=None, repr=False, compare=False)

    @property
    def skill_file(self) -> Path:
        return self.path / SKILL_FILE

    @property
    def body(self) -> str:
        """The Markdown instructions after the frontmatter."""
        if self._body is None:
            try:
                self._body = parse(self.skill_file.read_text(encoding="utf-8", errors="replace"))[1]
            except OSError:
                self._body = ""
        return self._body

    def files(self, limit: int = FILES_LIMIT) -> List[str]:
        """The skill's other files, as paths relative to its folder, without hidden ones."""
        out: List[str] = []
        for path in sorted(self.path.rglob("*")):
            rel = path.relative_to(self.path)
            if any(part.startswith(".") or part in SKIP_DIRS for part in rel.parts):
                continue
            if not path.is_file() or rel.as_posix() == SKILL_FILE:
                continue
            out.append(rel.as_posix())
            if len(out) >= limit:
                break
        return out

    def origin(self) -> Optional[Dict[str, str]]:
        """Where it was installed from (``url``, ``subdir``, ``commit``), or ``None``."""
        try:
            data = json.loads((self.path / ORIGIN_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) and data.get("url") else None


# Frontmatter -------------------------------------------------------------------------------------------


def _unquote(value: str) -> str:
    """A scalar without its quotes, or without a trailing ``# comment`` when it has none."""
    if len(value) >= 2 and value[0] == value[-1] == '"':
        inner = value[1:-1]
        return re.sub(r'\\(["\\nt])', lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), inner)
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def _block(lines: Sequence[str], style: str, chomp: str) -> str:
    """The text of a ``>`` (folded) or ``|`` (literal) block from its indented lines."""
    indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
    cut = min(indents) if indents else 0
    rows = [line[cut:] if line.strip() else "" for line in lines]
    if style == "|":
        text = "\n".join(rows)
    else:
        paragraphs: List[str] = []
        current: List[str] = []
        for row in rows:
            if row:
                current.append(row.strip())
            else:
                paragraphs.append(" ".join(current))
                current = []
        paragraphs.append(" ".join(current))
        text = "\n".join(paragraphs)
    text = text.rstrip("\n")
    return text + "\n" if text and chomp != "-" else text  # YAML's "clip" and "keep" end with one newline


def _frontmatter(lines: Sequence[str]) -> Dict[str, str]:
    """``key: value`` pairs of frontmatter lines; nested mappings and lists are skipped."""
    meta: Dict[str, str] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        match = _KEY.match(line)
        if not match or line[:1].isspace():
            continue
        key, value = match.group(1), (match.group(2) or "").strip()
        nested: List[str] = []
        while index < len(lines) and (not lines[index].strip() or lines[index][:1].isspace()):
            nested.append(lines[index])
            index += 1
        block = _BLOCK.match(value)
        if block:
            meta[key] = _block(nested, block.group(1), block.group(2))
        elif value and value[0] in "\"'" and not (len(value) > 1 and value[-1] == value[0]):
            meta[key] = _unquote(" ".join([value, *(n.strip() for n in nested if n.strip())]))  # a long quoted line
        elif value:
            more = [n.strip() for n in nested if n.strip()]
            meta[key] = " ".join([_unquote(value), *more]) if more else _unquote(value)
        elif nested and not any(_KEY.match(n.strip()) or n.strip().startswith("- ") for n in nested if n.strip()):
            meta[key] = " ".join(n.strip() for n in nested if n.strip())
        elif not nested:
            meta[key] = ""
    return meta


def parse(text: str) -> Tuple[Dict[str, str], str]:
    """The frontmatter of a ``SKILL.md`` as a dict of strings, and the Markdown after it.

    Understands ``key: value``, quoted values and ``>``/``|`` multi-line values; text without frontmatter
    gives an empty dict and the whole text.
    """
    text = text.lstrip("﻿")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for end in range(1, len(lines)):
        if lines[end].strip() in ("---", "..."):
            body = "\n".join(lines[end + 1:]).lstrip("\n")
            return _frontmatter(lines[1:end]), body
    return {}, text


def load(folder: Path, source: str) -> Optional[Skill]:
    """The skill in ``folder``, or ``None`` when it has no ``SKILL.md`` with a valid name and a description."""
    folder = Path(folder)
    try:
        meta, _ = parse((folder / SKILL_FILE).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    name, description = meta.get("name", "").strip(), " ".join(meta.get("description", "").split())
    if not _NAME.match(name) or not description:
        return None
    return Skill(name, description, folder, source)


# Discovery ---------------------------------------------------------------------------------------------


def _skills_home() -> Path:
    """Pyzed's own skills folder, where installed skills go."""
    from ..designer import settings

    return settings.config_dir() / "skills"


def locations(project_root: Optional[Path] = None) -> List[Tuple[str, Path]]:
    """The folders skills are looked for in, as ``(source, folder)``, highest priority first.

    The project's ``.claude/skills`` and ``.agents/skills``, the user's ``~/.claude/skills`` (Claude Code's,
    or ``$CLAUDE_CONFIG_DIR/skills``) and ``~/.agents/skills``, then Pyzed's ``<config>/skills``.
    """
    out: List[Tuple[str, Path]] = []
    if project_root is not None:
        root = Path(project_root)
        out += [("project", root / ".claude" / "skills"), ("project", root / ".agents" / "skills")]
    home = Path.home()
    claude = Path(os.environ.get("CLAUDE_CONFIG_DIR") or home / ".claude")
    out += [("claude", claude / "skills"), ("user", home / ".agents" / "skills"), ("pyzed", _skills_home())]
    return out


def _folders(base: Path) -> Iterable[Path]:
    try:
        return sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError:
        return []


def discover(project_root: Optional[Path] = None) -> List[Skill]:
    """Every skill of ``locations(project_root)``, sorted by name; when two share a name, the one of the
    higher-priority folder wins (the project's over the user's)."""
    found: Dict[str, Skill] = {}
    for source, base in locations(project_root):
        for folder in _folders(base):
            skill = load(folder, source)
            if skill is not None and skill.name not in found:
                found[skill.name] = skill
    return sorted(found.values(), key=lambda s: s.name.lower())


def enabled(skills: Iterable[Skill], settings: Optional["AgentSettings"] = None) -> List[Skill]:
    """``skills`` without the ones ``settings.disabled_skills`` turns off."""
    off = set(settings.disabled_skills) if settings is not None else set()
    return [s for s in skills if s.name not in off]


# Installing --------------------------------------------------------------------------------------------


def _ignore(folder: str, names: List[str]) -> List[str]:
    return [n for n in names if n in SKIP_DIRS or n == ORIGIN_FILE]


def install_folder(src: Path) -> Skill:
    """Copies the skill in ``src`` to ``<config>/skills/<name>``, replacing an installed one of that name."""
    src = Path(src)
    skill = load(src, "pyzed")
    if skill is None:
        raise SkillError(f"{src} has no {SKILL_FILE} with a valid name and description")
    home = _skills_home()
    dest = home / skill.name
    if dest.exists() and dest.resolve() == src.resolve():
        return skill
    home.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{skill.name}-", dir=home))
    try:
        shutil.copytree(src, staging / "skill", ignore=_ignore)
        if dest.exists():
            shutil.rmtree(dest)
        (staging / "skill").rename(dest)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    installed = load(dest, "pyzed")
    assert installed is not None
    return installed


def _git(*args: str, cwd: Optional[Path] = None) -> str:
    """Runs git and returns its output; raises ``SkillError`` when it fails or is missing."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT,
                              check=False, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except FileNotFoundError as err:
        raise SkillError("git is not installed") from err
    except subprocess.TimeoutExpired as err:
        raise SkillError(f"git {args[0]} took more than {GIT_TIMEOUT} seconds") from err
    if done.returncode != 0:
        raise SkillError(f"git {args[0]} failed: {(done.stderr or done.stdout).strip()}")
    return done.stdout.strip()


def _check_source(url: str, subdir: str) -> None:
    if not (url.startswith("https://") or (not url.startswith("-") and Path(url).is_dir())):
        raise SkillError(f"only https:// git URLs can be installed, not {url!r}")
    parts = Path(subdir).parts
    if Path(subdir).is_absolute() or ".." in parts:
        raise SkillError(f"{subdir!r} must be a folder inside the repository")


def _skill_folders(base: Path) -> List[Path]:
    """Folders under ``base`` holding a ``SKILL.md``, outermost only, outside ``.git``."""
    found: List[Path] = []
    for file in sorted(base.rglob(SKILL_FILE)):
        rel = file.parent.relative_to(base)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if not any(f == file.parent or f in file.parent.parents for f in found):
            found.append(file.parent)
    return found


def install_git(url: str, *, subdir: str = "") -> List[Skill]:
    """Clones the git repository at ``url`` (https) and installs every skill in it, or only the ones under
    ``subdir``; each remembers where it came from so ``update`` can fetch it again."""
    _check_source(url, subdir)
    with tempfile.TemporaryDirectory(prefix="pyzed-skill-") as tmp:
        repo = Path(tmp) / "repo"
        _git("clone", "--depth", "1", "--quiet", "--", url, str(repo))
        commit = _git("rev-parse", "HEAD", cwd=repo)
        base = repo / subdir if subdir else repo
        if not base.is_dir():
            raise SkillError(f"{url} has no folder {subdir!r}")
        folders = _skill_folders(base)
        if not folders:
            raise SkillError(f"no {SKILL_FILE} found in {url}" + (f" under {subdir}" if subdir else ""))
        installed: List[Skill] = []
        for folder in folders:
            if load(folder, "pyzed") is None:
                continue
            skill = install_folder(folder)
            origin = {"url": url, "subdir": folder.relative_to(repo).as_posix(), "commit": commit}
            (skill.path / ORIGIN_FILE).write_text(json.dumps(origin, indent=1), encoding="utf-8")
            installed.append(skill)
    if not installed:
        raise SkillError(f"no valid {SKILL_FILE} found in {url}")
    return installed


def update(skill: Skill) -> Skill:
    """Installs ``skill`` again from the repository it came from, and returns the new version."""
    origin = skill.origin()
    if origin is None:
        raise SkillError(f"{skill.name} was not installed from a git repository, so it cannot be updated")
    subdir = origin.get("subdir", "")
    installed = install_git(origin["url"], subdir="" if subdir == "." else subdir)
    fresh = next((s for s in installed if s.name == skill.name), installed[0])
    if fresh.name != skill.name and skill.source == "pyzed" and skill.path.exists():
        shutil.rmtree(skill.path)  # renamed upstream: drop the old copy
    return fresh


def remove(skill: Skill) -> None:
    """Deletes an installed skill; only Pyzed's own (``source == "pyzed"``) can be removed."""
    home = _skills_home().resolve()
    if skill.source != "pyzed" or home not in skill.path.resolve().parents:
        raise SkillError(f"{skill.name} is not one of Pyzed's installed skills, so it cannot be removed here")
    shutil.rmtree(skill.path)


# For the agent -----------------------------------------------------------------------------------------


def prompt(skills: Sequence[Skill]) -> str:
    """The system-prompt section that tells the model which skills it has; empty when there are none."""
    if not skills:
        return ""
    lines = [f"- {s.name}: {s.description}" for s in skills]
    return ("## Skills\n\nSkills are instructions for particular tasks. Before you do a task a skill covers, "
            "call read_skill with its name and follow what it says; read_skill_file reads the files it "
            "mentions.\n\n" + "\n".join(lines))


def tools(skills: Sequence[Skill]) -> List[Tool]:
    """``read_skill`` and ``read_skill_file``: the read-only tools that give the model the skills' contents."""
    by_name = {s.name: s for s in skills}

    def find(name: str) -> Skill:
        if name not in by_name:
            raise ValueError(f"no skill named {name!r}; the skills are: {', '.join(sorted(by_name)) or 'none'}")
        return by_name[name]

    @tool(title="Reading a skill")
    def read_skill(name: str) -> Any:
        """The instructions of a skill, and the list of its other files.

        name: the skill's name, as the system prompt lists it.
        """
        skill = find(name)
        return {"name": skill.name, "description": skill.description, "instructions": skill.body,
                "files": skill.files()}

    @tool(title="Reading a skill's file")
    def read_skill_file(name: str, path: str) -> str:
        """The text of one of a skill's files (a script, a reference...), as read_skill lists them.

        name: the skill's name.
        path: relative to the skill's folder.
        """
        root = find(name).path.resolve()
        target = (root / path).resolve()
        if root not in target.parents:
            raise PermissionError(f"{path} is outside the skill {name!r}")
        if not target.is_file():
            raise FileNotFoundError(f"{name} has no file {path}")
        with target.open("rb") as handle:
            data = handle.read(READ_LIMIT + 1)
        text = data[:READ_LIMIT].decode("utf-8", "replace")
        return text + "\n… (the file is longer; the rest was cut)" if len(data) > READ_LIMIT else text

    return [read_skill, read_skill_file]
