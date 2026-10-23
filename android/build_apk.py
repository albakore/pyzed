"""Builds an Android APK of a Pyzed app from this checkout (see README.md next to this file).

    python android/build_apk.py examples/counter.py --name Counter

The same as ``pyzed build --target android-arm64`` for a single script; the work is done by
``pyzed.android``. The engine is built with the NDK when it is missing (``--rebuild`` builds it again).
"""

import importlib.util
import sys
from pathlib import Path

# Loaded by path: importing the `pyzed` package would need its core built for this computer.
PATH = Path(__file__).resolve().parent.parent / "python" / "pyzed" / "android.py"
spec = importlib.util.spec_from_file_location("pyzed_android", PATH)
android = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = android
spec.loader.exec_module(android)

if __name__ == "__main__":
    raise SystemExit(android.main())
