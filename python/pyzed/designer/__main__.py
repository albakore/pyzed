"""``python -m pyzed.designer [form.pzform]`` opens the visual designer."""

import sys

from . import design

design(sys.argv[1] if len(sys.argv) > 1 else None)
