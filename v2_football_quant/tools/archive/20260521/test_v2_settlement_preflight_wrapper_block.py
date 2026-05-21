#!/usr/bin/env python3
"""Phase D.7.3 — Strict wrapper-level preflight block test.

Goals:
1) Wrapper exit_code MUST be 2 when preflight blocks.
2) verified file hash/mtime/size/existence MUST stay unchanged.
3) 7 primary blocker reason codes MUST be present.
4) watchdog status MUST be BLOCKED_PREFLIGHT.
5) verify_date MUST NOT be called.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE / "data" / "runtime" / "status"
TASK_STATUS = STATUS_DIR / "task_status_v2_daily_settle.json"
CN_TZ = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_settlement_preflight_wrapper_block_test.v1"

REQUIRED_CODES = [
    "OFFICIAL_BET_LOCKED_ZERO",
    "WINDOW_CHECKER_NEW_LOCKS_ZERO",
    "LOCK_OWNER_MISSING",
    "MISSED_CANDIDATES_PRESENT",
    "SETTLEMENT_WITHOUT_OFFICIAL_LOCKS",
    "SETTLEMENT_WITHOUT_WINDOW_LOCKS",
    "HISTORICAL_SETTLEMENT_CONTAMINATION",
]

ALLOWED_EXTRA_CODES = {
    "SETTLEMENT_TARGETS_OFFICIAL_LOCKS_MISMATCH",
    "SETTLEMENT_TARGETS_WINDOW_LOCKS_MISMATCH",
}


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _fingerprint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "mtime": None,
            "size": None,
            "sha256": None,
        }
    data = path.read_bytes()
    return {
        "exists": True,
        "mtime": path.stat().st_mtime,
        "size": path.stat().st_size,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _iso_now() -> str:
    return datetime.now(CN_TZ).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    args = parser.parse_args()
    date_key = str(args.date).replace("-", "")

    verified_path = BASE / "data" / "paper_trading" / f"verified_{date_key}.json"
    preflight_path = STATUS_DIR / f"v2_settlement_preflight_{date_key}.json"
    out_marker = STATUS_DIR / f"v2_settlement_preflight_wrapper_block_test_{date_key}.json"

    before = _fingerprint(verified_path)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(BASE)
    cmd = [
        sys.executable,
        str(BASE / "engine" / "v2_settle_with_watchdog.py"),
        "--date",
        date_key,
        "--mode",
        "main",
    ]
    result = subprocess.run(
        cmd,
        cwd=str(BASE),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    merged = stdout + "\n" + stderr
    exit_code = int(result.returncode)

    preflight = _load_json(preflight_path, {})
    decision = preflight.get("decision", {}) if isinstance(preflight, dict) else {}
    summary = preflight.get("summary", {}) if isinstance(preflight, dict) else {}
    reason_codes = decision.get("reason_codes") or summary.get("blockers") or []
    reason_codes = [str(x) for x in reason_codes]

    after = _fingerprint(verified_path)

    watchdog = _load_json(TASK_STATUS, {})
    watchdog_status = str(watchdog.get("status", "")) if isinstance(watchdog, dict) else ""
    watchdog_error = str(watchdog.get("error", "")) if isinstance(watchdog, dict) else ""

    required_missing = [code for code in REQUIRED_CODES if code not in reason_codes]
    required_reason_codes_present = len(required_missing) == 0

    # strict exit code check
    exit_code_ok = exit_code == 2

    # verified file immutability checks
    verified_hash_unchanged = before["sha256"] == after["sha256"]
    verified_mtime_unchanged = before["mtime"] == after["mtime"]
    verified_size_unchanged = before["size"] == after["size"]
    verified_exists_stable = before["exists"] == after["exists"]
    file_created = (not before["exists"]) and after["exists"]

    # verify_date not called heuristics
    verify_date_called = any(
        token in merged.lower()
        for token in [
            "verify_date",
            "[preflight allow]",
            "settlement proceeding",
        ]
    )

    settlement_allowed = bool(preflight.get("settlement_allowed")) if isinstance(preflight, dict) else True
    fail_closed = bool(preflight.get("fail_closed")) if isinstance(preflight, dict) else False

    watchdog_blocked_preflight = (
        watchdog_status == "BLOCKED_PREFLIGHT"
        or "BLOCKED_PREFLIGHT" in merged
        or "BLOCKED_PREFLIGHT" in watchdog_error
    )

    name_error = any(tok in merged for tok in ["NameError", "KeyError", "Undefined"])

    errors: list[str] = []
    if not exit_code_ok:
        errors.append(f"exit_code_not_2:{exit_code}")
    if settlement_allowed:
        errors.append("settlement_allowed_true")
    if not fail_closed:
        errors.append("fail_closed_false")
    if not required_reason_codes_present:
        errors.append("required_reason_codes_missing:" + ",".join(required_missing))
    if not verified_exists_stable:
        errors.append("verified_existence_changed")
    if file_created:
        errors.append("verified_file_created")
    if not verified_hash_unchanged:
        errors.append("verified_hash_changed")
    if not verified_mtime_unchanged:
        errors.append("verified_mtime_changed")
    if not verified_size_unchanged:
        errors.append("verified_size_changed")
    if verify_date_called:
        errors.append("verify_date_called_detected")
    if not watchdog_blocked_preflight:
        errors.append("watchdog_status_not_blocked_preflight")
    if name_error:
        errors.append("name_error_in_wrapper_output")

    status = "PASS" if not errors else "FAIL"
    marker = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "date": date_key,
        "exit_code": exit_code,
        "settlement_allowed": settlement_allowed,
        "required_reason_codes_present": required_reason_codes_present,
        "required_reason_codes_missing": required_missing,
        "reason_codes": reason_codes,
        "reason_codes_allowed_extra_present": [
            code for code in reason_codes if code in ALLOWED_EXTRA_CODES
        ],
        "verified_hash_unchanged": verified_hash_unchanged,
        "verified_mtime_unchanged": verified_mtime_unchanged,
        "verified_size_unchanged": verified_size_unchanged,
        "verified_exists_stable": verified_exists_stable,
        "verify_date_called": verify_date_called,
        "watchdog_blocked_preflight": watchdog_blocked_preflight,
        "watchdog_status": watchdog_status,
        "name_error": name_error,
        "production_verified": False,
        "fail_closed": fail_closed,
        "errors": errors,
        "generated_at": _iso_now(),
    }
    out_marker.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(marker, ensure_ascii=False, indent=2))

    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
