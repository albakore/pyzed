"""Agent Skills: ``pyzed.agents.skills``."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pyzed.agents import skills
from pyzed.agents.providers import AgentSettings
from pyzed.designer import settings as designer_settings


def write_skill(folder: Path, name: str, description: str = "Does things.", body: str = "Do it well.\n",
                files=None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n{body}",
                                     encoding="utf-8")
    for rel, text in (files or {}).items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(text, encoding="utf-8")
    return folder


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A fake home, Pyzed config folder and project."""
    home, config, project = tmp_path / "home", tmp_path / "config", tmp_path / "project"
    for folder in (home, config, project):
        folder.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(designer_settings, "config_dir", lambda: config)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return type("Env", (), {"home": home, "config": config, "project": project, "tmp": tmp_path})


# Frontmatter -------------------------------------------------------------------------------------------


def test_parse_simple_and_quoted_values():
    meta, body = skills.parse('---\nname: pdf\ndescription: "Reads: PDFs"\nlicense: \'it\'\'s MIT\'\n'
                              "version: 1.2 # a comment\n---\n\n# Title\nText\n")
    assert meta == {"name": "pdf", "description": "Reads: PDFs", "license": "it's MIT", "version": "1.2"}
    assert body == "# Title\nText"


def test_parse_folded_and_literal_descriptions():
    text = ("---\nname: x\ndescription: >\n  First line\n  goes on.\n\n  Second paragraph.\n"
            "notes: |-\n  one\n  two\nwrapped: a plain value\n  that wraps\n---\nbody")
    meta, body = skills.parse(text)
    assert meta["description"] == "First line goes on.\nSecond paragraph.\n"
    assert meta["notes"] == "one\ntwo"
    assert meta["wrapped"] == "a plain value that wraps"
    assert body == "body"


def test_parse_skips_nested_mappings_and_handles_missing_frontmatter():
    meta, _ = skills.parse("---\nname: x\nmetadata:\n  author: me\n  tags:\n    - a\ndescription: d\n---\n")
    assert meta == {"name": "x", "description": "d"}
    assert skills.parse("# Just markdown\n") == ({}, "# Just markdown\n")
    assert skills.parse("---\nname: x\nno end") == ({}, "---\nname: x\nno end")


def test_load_needs_a_name_and_a_description(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "SKILL.md").write_text("---\nname: a\n---\nbody")
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "SKILL.md").write_text("---\ndescription: no name\n---\nbody")
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / "SKILL.md").write_text("---\nname: ../evil\ndescription: bad name\n---\n")
    assert skills.load(tmp_path / "a", "user") is None
    assert skills.load(tmp_path / "b", "user") is None
    assert skills.load(tmp_path / "c", "user") is None
    assert skills.load(tmp_path / "missing", "user") is None
    write_skill(tmp_path / "d", "d", description=">\n  Folded\n  text")
    skill = skills.load(tmp_path / "d", "user")
    assert skill.description == "Folded text"
    assert skill._body is None  # read lazily
    assert skill.body == "Do it well."
    assert skill.skill_file == tmp_path / "d" / "SKILL.md"


def test_files_skip_hidden_and_skill_md(tmp_path):
    folder = write_skill(tmp_path / "s", "s", files={"scripts/run.py": "print()", "ref.md": "r", ".secret": "x",
                                                     ".git/config": "x", "a/.hidden/b.txt": "x"})
    skill = skills.load(folder, "user")
    assert skill.files() == ["ref.md", "scripts/run.py"]
    assert skill.files(limit=1) == ["ref.md"]


# Discovery ---------------------------------------------------------------------------------------------


def test_locations_order(env):
    found = skills.locations(env.project)
    assert found == [
        ("project", env.project / ".claude" / "skills"), ("project", env.project / ".agents" / "skills"),
        ("claude", env.home / ".claude" / "skills"), ("user", env.home / ".agents" / "skills"),
        ("pyzed", env.config / "skills"),
    ]
    assert [source for source, _ in skills.locations()] == ["claude", "user", "pyzed"]


def test_discover_priority_and_override(env):
    write_skill(env.project / ".claude" / "skills" / "shared", "shared", "From the project.")
    write_skill(env.project / ".agents" / "skills" / "agents-only", "agents-only", "Project agents folder.")
    write_skill(env.home / ".claude" / "skills" / "shared", "shared", "From the user.")
    write_skill(env.home / ".claude" / "skills" / "mine", "mine", "Only the user's.")
    write_skill(env.config / "skills" / "Alpha", "Alpha", "Installed in Pyzed.")
    write_skill(env.config / "skills" / "mine", "mine", "Shadowed.")
    (env.config / "skills" / "broken").mkdir()
    found = skills.discover(env.project)
    assert [s.name for s in found] == ["agents-only", "Alpha", "mine", "shared"]
    by_name = {s.name: s for s in found}
    assert (by_name["shared"].source, by_name["shared"].description) == ("project", "From the project.")
    assert (by_name["mine"].source, by_name["mine"].description) == ("claude", "Only the user's.")
    assert by_name["Alpha"].source == "pyzed"
    assert {s.name for s in skills.discover()} == {"Alpha", "mine", "shared"}


def test_enabled_filters_disabled_skills(env):
    write_skill(env.config / "skills" / "a", "a")
    write_skill(env.config / "skills" / "b", "b")
    found = skills.discover()
    assert [s.name for s in skills.enabled(found, AgentSettings(disabled_skills=["a"]))] == ["b"]
    assert [s.name for s in skills.enabled(found, AgentSettings())] == ["a", "b"]
    assert [s.name for s in skills.enabled(found)] == ["a", "b"]


# Installing --------------------------------------------------------------------------------------------


def test_install_folder(env):
    src = write_skill(env.tmp / "src" / "whatever", "my-skill", files={"scripts/x.sh": "echo", ".git/HEAD": "x"})
    skill = skills.install_folder(src)
    assert skill.source == "pyzed"
    assert skill.path == env.config / "skills" / "my-skill"
    assert (skill.path / "scripts" / "x.sh").read_text() == "echo"
    assert not (skill.path / ".git").exists()
    write_skill(src, "my-skill", body="Version two.\n")
    (src / "scripts" / "x.sh").unlink()
    again = skills.install_folder(src)
    assert again.body == "Version two."
    assert not (again.path / "scripts" / "x.sh").exists()
    assert [p.name for p in (env.config / "skills").iterdir()] == ["my-skill"]  # no staging left behind
    (env.tmp / "empty").mkdir()
    with pytest.raises(skills.SkillError):
        skills.install_folder(env.tmp / "empty")


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(env):
    """A bare repository with two skills, and the working copy that pushes to it."""
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    bare, work = env.tmp / "skills.git", env.tmp / "work"
    git("init", "--bare", "--quiet", str(bare), cwd=env.tmp)
    git("init", "--quiet", str(work), cwd=env.tmp)
    git("config", "user.email", "test@example.com", cwd=work)
    git("config", "user.name", "Test", cwd=work)
    write_skill(work / "skills" / "one", "one", "First.", files={"ref.md": "reference"})
    write_skill(work / "skills" / "two", "two", "Second.")
    (work / "README.md").write_text("not a skill")
    git("add", "-A", cwd=work)
    git("commit", "--quiet", "-m", "first", cwd=work)
    git("push", "--quiet", str(bare), "HEAD:refs/heads/main", cwd=work)
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=bare)
    return type("Repo", (), {"bare": bare, "work": work})


def test_install_git_installs_every_skill_and_records_the_origin(env, repo):
    installed = skills.install_git(str(repo.bare))
    assert [s.name for s in installed] == ["one", "two"]
    assert (env.config / "skills" / "one" / "ref.md").read_text() == "reference"
    origin = json.loads((env.config / "skills" / "one" / ".pyzed-source.json").read_text())
    assert origin["url"] == str(repo.bare) and origin["subdir"] == "skills/one" and len(origin["commit"]) == 40
    assert installed[0].files() == ["ref.md"]  # the origin file is hidden


def test_install_git_subdir_and_bad_sources(env, repo):
    assert [s.name for s in skills.install_git(str(repo.bare), subdir="skills/two")] == ["two"]
    assert not (env.config / "skills" / "one").exists()
    for url in ("http://example.com/x.git", "git@github.com:a/b.git", "--upload-pack=evil", "ext::sh -c x"):
        with pytest.raises(skills.SkillError):
            skills.install_git(url)
    with pytest.raises(skills.SkillError):
        skills.install_git(str(repo.bare), subdir="../outside")
    with pytest.raises(skills.SkillError):
        skills.install_git(str(repo.bare), subdir="missing")


def test_update_after_a_new_commit(env, repo):
    one = next(s for s in skills.install_git(str(repo.bare)) if s.name == "one")
    write_skill(repo.work / "skills" / "one", "one", "First, improved.", body="New steps.\n")
    git("commit", "--quiet", "-am", "second", cwd=repo.work)
    git("push", "--quiet", str(repo.bare), "HEAD:refs/heads/main", cwd=repo.work)
    fresh = skills.update(one)
    assert fresh.description == "First, improved."
    assert fresh.body == "New steps."
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo.work, capture_output=True, text=True,
                          check=True).stdout.strip()
    assert fresh.origin()["commit"] == head
    local = skills.install_folder(write_skill(env.tmp / "local", "local"))
    with pytest.raises(skills.SkillError):
        skills.update(local)


def test_remove_only_pyzed_skills(env):
    installed = skills.install_folder(write_skill(env.tmp / "src", "gone"))
    skills.remove(installed)
    assert not installed.path.exists()
    project = skills.load(write_skill(env.project / ".claude" / "skills" / "p", "p"), "project")
    with pytest.raises(skills.SkillError):
        skills.remove(project)
    assert project.path.exists()
    sneaky = skills.Skill("p", "d", project.path, "pyzed")  # claims to be Pyzed's, lives elsewhere
    with pytest.raises(skills.SkillError):
        skills.remove(sneaky)
    assert project.path.exists()


# For the agent -----------------------------------------------------------------------------------------


def test_prompt_lists_skills():
    assert skills.prompt([]) == ""
    text = skills.prompt([skills.Skill("pdf", "Reads PDFs.", Path("."), "user")])
    assert "- pdf: Reads PDFs." in text and "read_skill" in text


def test_tools_read_skills_and_refuse_escapes(tmp_path, monkeypatch):
    folder = write_skill(tmp_path / "skills" / "s", "s", body="Steps.\n", files={"scripts/run.py": "print(1)"})
    (tmp_path / "skills" / "outside.txt").write_text("secret")
    read_skill, read_skill_file = skills.tools([skills.load(folder, "user")])
    assert (read_skill.name, read_skill_file.name) == ("read_skill", "read_skill_file")
    assert not read_skill.writes and not read_skill_file.writes
    assert read_skill_file.schema["required"] == ["name", "path"]
    result = read_skill.func(name="s")
    assert result["instructions"] == "Steps." and result["files"] == ["scripts/run.py"]
    assert read_skill_file.func(name="s", path="scripts/run.py") == "print(1)"
    for path in ("../outside.txt", "/etc/passwd", "scripts/../../outside.txt", "."):
        with pytest.raises(PermissionError):
            read_skill_file.func(name="s", path=path)
    with pytest.raises(FileNotFoundError):
        read_skill_file.func(name="s", path="nope.txt")
    with pytest.raises(ValueError):
        read_skill.func(name="other")
    monkeypatch.setattr(skills, "READ_LIMIT", 4)
    assert read_skill_file.func(name="s", path="scripts/run.py").startswith("prin\n")
