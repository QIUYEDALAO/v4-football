#!/usr/bin/env python3
"""Compatibility wrapper for the strict V3/V4 Intel Ops Console UI checker."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRICT = ROOT / "tools/check_v3v4_intel_ops_console_ui.py"


def main() -> int:
    result = subprocess.run([sys.executable, str(STRICT)], cwd=str(ROOT), text=True)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
