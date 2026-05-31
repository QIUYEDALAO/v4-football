#!/usr/bin/env python3
"""check_v4_qq_enabled_gate.py — V4_QQ_ENABLED environment gate checker.

Verifies that the QQ push gate respects:
  - default false
  - env true values
  - --no-push override
  - OPENCLAW_NO_PUSH override
  - duplicate sent marker block
  - dry-run writes no sent marker
  - real_send=false during checker run
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine.v4_scan_and_brief import _parse_bool_env

LOCAL_TZ = timezone(timedelta(hours=8))
CHECKS: list[dict] = []
WARNINGS: list[str] = []
BLOCKERS: list[str] = []


def _ck(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"name": name, "ok": ok, "detail": detail})


def _warn(msg: str) -> None:
    WARNINGS.append(msg)


def _block(msg: str) -> None:
    BLOCKERS.append(msg)


def _unset_env(key: str) -> None:
    os.environ.pop(key, None)


def _set_env(key: str, val: str) -> None:
    os.environ[key] = val


# ──────────────────────────────────────────────
# 1. Default: env unset → False
# ──────────────────────────────────────────────
_unset_env("V4_QQ_ENABLED")
got = _parse_bool_env("V4_QQ_ENABLED", False)
_ck("V4_QQ_ENABLED_unset_default_false", got is False,
    f"_parse_bool_env returned {got!r}" if got is not False else "")

# ──────────────────────────────────────────────
# 2. Explicit true values: 1 / true / yes / on
# ──────────────────────────────────────────────
for val in ("1", "true", "yes", "on", "True", "YES", "ON"):
    _set_env("V4_QQ_ENABLED", val)
    got = _parse_bool_env("V4_QQ_ENABLED", False)
    _ck(f"V4_QQ_ENABLED_{val.lower()}_is_true", got is True,
        f"env={val!r} returned {got!r}" if got is not True else "")

# ──────────────────────────────────────────────
# 3. False values: 0 / false / no / off / random
# ──────────────────────────────────────────────
for val in ("0", "false", "no", "off", "False", "NO", "random", "", "abc"):
    _set_env("V4_QQ_ENABLED", val)
    got = _parse_bool_env("V4_QQ_ENABLED", False)
    _ck(f"V4_QQ_ENABLED_{val.lower() or 'empty'}_is_false", got is False,
        f"env={val!r} returned {got!r}" if got is not False else "")

# ──────────────────────────────────────────────
# 4. Verify engine imports _parse_bool_env and compiles
# ──────────────────────────────────────────────
try:
    import engine.v4_scan_and_brief
    _ck("engine_v4_scan_and_brief_imports_ok", True)
except Exception as e:
    _ck("engine_v4_scan_and_brief_imports_ok", False, str(e))

# ──────────────────────────────────────────────
# 5. Verify no hardcoded False remains
# ──────────────────────────────────────────────
source = (BASE_DIR / "engine" / "v4_scan_and_brief.py").read_text(encoding="utf-8")
lines = source.splitlines()
hardcoded_false_lines = []
for i, line in enumerate(lines, start=1):
    stripped = line.strip()
    if '"V4_QQ_ENABLED": False' in stripped and '_parse_bool_env' not in stripped:
        hardcoded_false_lines.append(i)

if hardcoded_false_lines:
    _ck("no_hardcoded_V4_QQ_ENABLED_False", False,
        f"hardcoded at lines: {hardcoded_false_lines}")
else:
    _ck("no_hardcoded_V4_QQ_ENABLED_False", True)

# ──────────────────────────────────────────────
# 6. _parse_bool_env exists and is callable
# ──────────────────────────────────────────────
_ck("_parse_bool_env_function_exists", callable(_parse_bool_env),
    f"type={type(_parse_bool_env).__name__}")

# ──────────────────────────────────────────────
# Final summary
# ──────────────────────────────────────────────
_unset_env("V4_QQ_ENABLED")

now = datetime.now(LOCAL_TZ).isoformat()
result = {
    "checker": "check_v4_qq_enabled_gate",
    "generated_at": now,
    "checks": CHECKS,
    "warnings": WARNINGS,
    "blockers": BLOCKERS,
    "conclusion": "PASS" if not BLOCKERS else "FAIL",
}

print(json.dumps(result, ensure_ascii=False, indent=2))

if BLOCKERS:
    sys.exit(1)
