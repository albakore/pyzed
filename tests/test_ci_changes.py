"""scripts/ci_changes.py: the file groups that decide which CI jobs run."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci_changes.py"
spec = importlib.util.spec_from_file_location("ci_changes", SCRIPT)
ci_changes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_changes)

GROUPS = {"rust": ["src/**", "Cargo.toml"], "code": ["!docs/**", "!**.md"]}


def test_groups_match_every_changed_file():
    docs = [f"docs/src/page{i}.mdx" for i in range(400)]
    assert ci_changes.groups(docs, GROUPS) == {"rust": False, "code": False}
    # a Rust file after the first 300 still counts (GitHub's path filters stop at 300)
    assert ci_changes.groups([*docs, "src/lib.rs"], GROUPS) == {"rust": True, "code": True}
    assert ci_changes.groups(["tests/test_x.py", "README.md"], GROUPS) == {"rust": False, "code": True}


def test_everything_runs_when_the_diff_is_unknown():
    assert ci_changes.changed_files("0" * 40, "HEAD") is None
    assert ci_changes.groups(None, GROUPS) == {"rust": True, "code": True}
