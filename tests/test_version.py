import re
from pathlib import Path

import pyzed


def test_version_matches_cargo():
    cargo = (Path(__file__).resolve().parent.parent / "Cargo.toml").read_text(encoding="utf-8")
    expected = re.search(r'^version = "([^"]+)"', cargo, re.MULTILINE).group(1)
    assert pyzed.__version__ == expected
