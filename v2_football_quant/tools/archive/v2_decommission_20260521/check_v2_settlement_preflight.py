#!/usr/bin/env python3
"""Phase D.7.3 — V2 settlement preflight checker (strict closure)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_settlement_preflight_check.v1"

REQUIRED_REASON_CODES = [
    "OFFICIAL_BET_LOCKED_ZERO",
    "WINDOW_CHECKER_NEW_LOCKS_ZERO",
    "LOCK_OWNER_MISSING",
    "MISSED_CANDIDATES_PRESENT",
    "SETTLEMENT_WITHOUT_OFFICIAL_LOCKS",
    "SETTLEMENT_WITHOUT_WINDOW_LOCKS",
    "HISTORICAL_SETTLEMENT_CONTAMINATION",
]


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _status_level(errors: list[str], warnings: list[str]) -> str:
    if errors:
        return "FAIL"
    if warnings:
        return "WARN"
    return "PASS"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False, help="YYYYMMDD")
    args = parser.parse_args()
    date_key = (args.date or datetime.now(CN_TZ).strftime("%Y%m%d")).replace("-", "")

    preflight_path = STATUS_DIR / f"v2_settlement_preflight_{date_key}.json"
    wrapper_path = STATUS_DIR / f"v2_settlement_preflight_wrapper_block_test_{date_key}.json"
    out_path = STATUS_DIR / f"v2_settlement_preflight_check_{date_key}.json"

    errors: list[str] = []
    warnings: list[str] = []

    if not preflight_path.exists():
        result = {
            "status": "BLOCKER",
            "schema_version": SCHEMA_VERSION,
            "date": date_key,
            "errors": ["marker_missing"],
            "warnings": [],
            "generated_at": datetime.now(CN_TZ).isoformat(),
        }
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    preflight = _load_json(preflight_path, {})
    decision = preflight.get("decision", {}) if isinstance(preflight, dict) else {}
    reason_codes = decision.get("reason_codes") or preflight.get("summary", {}).get("blockers") or []
    reason_codes = [str(x) for x in reason_codes]

    settlement_allowed = bool(preflight.get("settlement_allowed", True))
    fail_closed = bool(preflight.get("fail_closed", False))
    production_verified = bool(preflight.get("production_verified", False))
    boundaries = preflight.get("boundaries", {}) if isinstance(preflight.get("boundaries", {}), dict) else {}

    if settlement_allowed:
        errors.append("SHOULD_BE_BLOCKED")
    if not fail_closed:
        errors.append("NOT_FAIL_CLOSED")
    if production_verified:
        errors.append("PRODUCTION_VERIFIED_TRUE")

    reason_codes_missing = [code for code in REQUIRED_REASON_CODES if code not in reason_codes]
    if reason_codes_missing:
        errors.append("REASON_CODES_MISSING:" + ",".join(reason_codes_missing))

    # secret scan in marker content
    marker_text = json.dumps(preflight, ensure_ascii=False)
    sec_hits = re.findall(r"sk-[A-Za-z0-9]{20,}|x-apisports-key|APIFOOTBALL_KEY|OPENCLAW_APIFOOTBALL_KEY", marker_text)
    secret_safe = len(sec_hits) == 0
    if not secret_safe:
        errors.append("SECRET_LEAK_DETECTED")

    wrapper = _load_json(wrapper_path, {})
    wrapper_found = wrapper_path.exists()
    wrapper_status = str(wrapper.get("status", "MISSING")).upper() if wrapper_found else "MISSING"
    wrapper_exit_code = wrapper.get("exit_code") if wrapper_found else None
    wrapper_verified_hash_unchanged = bool(wrapper.get("verified_hash_unchanged", False)) if wrapper_found else False
    wrapper_verified_mtime_unchanged = bool(wrapper.get("verified_mtime_unchanged", False)) if wrapper_found else False
    wrapper_verified_size_unchanged = bool(wrapper.get("verified_size_unchanged", False)) if wrapper_found else False
    wrapper_watchdog_blocked = bool(wrapper.get("watchdog_blocked_preflight", False)) if wrapper_found else False
    wrapper_verify_date_called = bool(wrapper.get("verify_date_called", True)) if wrapper_found else True
    wrapper_name_error = bool(wrapper.get("name_error", True)) if wrapper_found else True
    wrapper_required_reasons = bool(wrapper.get("required_reason_codes_present", False)) if wrapper_found else False

    if not wrapper_found:
        warnings.append("WRAPPER_MARKER_MISSING")
    else:
        if wrapper_status != "PASS":
            errors.append(f"WRAPPER_STATUS_NOT_PASS:{wrapper_status}")
        if wrapper_exit_code != 2:
            errors.append(f"WRAPPER_EXIT_CODE_NOT_2:{wrapper_exit_code}")
        if bool(wrapper.get("settlement_allowed", True)):
            errors.append("WRAPPER_SETTLEMENT_ALLOWED_TRUE")
        if not wrapper_required_reasons:
            errors.append("WRAPPER_REQUIRED_REASON_CODES_MISSING")
        if not wrapper_verified_hash_unchanged:
            errors.append("WRAPPER_VERIFIED_HASH_CHANGED")
        if not wrapper_verified_mtime_unchanged:
            errors.append("WRAPPER_VERIFIED_MTIME_CHANGED")
        if not wrapper_verified_size_unchanged:
            errors.append("WRAPPER_VERIFIED_SIZE_CHANGED")
        if wrapper_verify_date_called:
            errors.append("WRAPPER_VERIFY_DATE_CALLED")
        if not wrapper_watchdog_blocked:
            errors.append("WRAPPER_WATCHDOG_NOT_BLOCKED_PREFLIGHT")
        if wrapper_name_error:
            errors.append("WRAPPER_NAME_ERROR")

    status = _status_level(errors, warnings)

    result = {
        "status": status,
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "settlement_allowed": settlement_allowed,
        "fail_closed": fail_closed,
        "reason_codes": reason_codes,
        "reason_codes_missing": reason_codes_missing,
        "wrapper_block_test_status": wrapper_status,
        "exit_code": wrapper_exit_code,
        "verified_hash_unchanged": wrapper_verified_hash_unchanged,
        "verified_mtime_unchanged": wrapper_verified_mtime_unchanged,
        "verified_size_unchanged": wrapper_verified_size_unchanged,
        "watchdog_blocked_preflight": wrapper_watchdog_blocked,
        "verify_date_called": wrapper_verify_date_called,
        "name_error": wrapper_name_error,
        "production_verified": False,
        "no_verified_write": bool(boundaries.get("no_verified_write", False)),
        "no_push": bool(boundaries.get("no_push", False)),
        "no_api": bool(boundaries.get("no_api", False)),
        "no_cron": bool(boundaries.get("no_cron", False)),
        "secret_safe": secret_safe,
        "warnings": warnings,
        "errors": errors,
        "preflight_marker_path": str(preflight_path),
        "wrapper_marker_path": str(wrapper_path),
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
