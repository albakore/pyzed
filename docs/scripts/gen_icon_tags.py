"""Writes python/pyzed/_lucide_tags.py: the search tags of every bundled Lucide icon.

    npm pack lucide-static && tar xzf lucide-static-*.tgz
    python docs/scripts/gen_icon_tags.py package/tags.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from pyzed._lucide import CODEPOINTS  # noqa: E402


def main() -> int:
    tags = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    lines = ['"""Search tags of the bundled Lucide icons (generated from lucide-static by',
             'docs/scripts/gen_icon_tags.py). ISC License."""', "", "TAGS: dict[str, str] = {"]
    for name in sorted(CODEPOINTS):
        words = [w for w in dict.fromkeys(t.strip().lower() for t in tags.get(name, ())) if w]
        if words:
            lines.append(f"    {json.dumps(name)}: {json.dumps(', '.join(words), ensure_ascii=False)},")
    lines.append("}")
    (ROOT / "python" / "pyzed" / "_lucide_tags.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
