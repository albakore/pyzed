import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_core_stub_is_up_to_date():
    spec = importlib.util.spec_from_file_location("gen_stubs", ROOT / "scripts" / "gen_stubs.py")
    gen_stubs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen_stubs)
    assert gen_stubs.main(["--check"]) == 0, "run python scripts/gen_stubs.py"
    assert (ROOT / "python" / "pyzed" / "py.typed").is_file()
