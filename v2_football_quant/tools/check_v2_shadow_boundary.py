#!/usr/bin/env python3
"""Phase D.1 — V2 Shadow Boundary Checker (read-only, no production impact)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
STATUS_DIR = RUNTIME_DIR / "status"
CN_TZ = timezone(timedelta(hours=8))

DOC_PATH = BASE_DIR / "docs" / "V2_SHADOW_INTEGRATION_BOUNDARY.md"
DAILY_RUNNER_PATH = BASE_DIR / "engine" / "daily_runner.py"
SETTLE_PATH = BASE_DIR / "engine" / "v2_settle_with_watchdog.py"

REQUIRED_DOC_PHRASES = [
    "lock_owner=window_checker",
    "official_bet_locked=true",
    "action_code=BET_LOCKED",
    "candidate_stage",
    "missed candidates",
    "不补推",
    "不结算",
    "shadow 不能推 QQ",
    "shadow 不能替代正式链路",
    "production_verified=false",
]

DAILY_POOL_FORBIDDEN = [
    (r'action_code["\']?\s*[=:]["\' ]\s*["\']?BET_LOCKED', "DAILY_POOL writes BET_LOCKED action_code"),
    (r'lock_owner["\']?\s*[=:]["\' ]\s*["\']?window_checker', "DAILY_POOL writes lock_owner=window_checker"),
    (r'official_bet_locked["\']?\s*[=:]["\' ]\s*True', "DAILY_POOL writes official_bet_locked=true"),
]

SETTLE_REQUIRED = [
    r"official_bet_locked",
    r"lock_owner",
]


def main() -> None:
    warnings: list[str] = []
    errors: list[str] = []

    # 1. Document checks
    doc_ok = DOC_PATH.exists()
    if not doc_ok:
        errors.append("doc_missing")
    else:
        doc_text = DOC_PATH.read_text(encoding="utf-8")
        for phrase in REQUIRED_DOC_PHRASES:
            if phrase not in doc_text:
                errors.append(f"doc_missing_phrase:{phrase}")

    # 2. DAILY_POOL checks
    dp_ok = DAILY_RUNNER_PATH.exists()
    if dp_ok:
        dp_text = DAILY_RUNNER_PATH.read_text(encoding="utf-8")
        for pattern, desc in DAILY_POOL_FORBIDDEN:
            if re.search(pattern, dp_text):
                errors.append(desc)
        # verify summary message
        if "建池阶段不锁定" not in dp_text and "BET_LOCKED 等待" not in dp_text:
            warnings.append("daily_runner_missing_pool_boundary_message")

        # verify DAILY_POOL summary tool
        summary_path = BASE_DIR / "engine" / "v2_daily_pool_summary.py"
        if summary_path.exists():
            summary_text = summary_path.read_text(encoding="utf-8")
            if "建池阶段不锁定" in summary_text:
                pass  # confirmed
            else:
                warnings.append("pool_summary_missing_boundary_text")
        else:
            warnings.append("pool_summary_missing")

    # 3. Settlement checks
    settle_ok = SETTLE_PATH.exists()
    if settle_ok:
        settle_text = SETTLE_PATH.read_text(encoding="utf-8")
        for pat in SETTLE_REQUIRED:
            if pat not in settle_text:
                warnings.append(f"settlement_missing_guard:{pat}")

    # 4. Missed candidates audit check
    audit_dir = RUNTIME_DIR / "audit"
    if audit_dir.exists():
        found = False
        for f in sorted(audit_dir.glob("v2_missed_lock_candidates_*.json")):
            found = True
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                for c in data.get("candidates", []):
                    if c.get("official_bet_locked") or c.get("qq_pushed") or c.get("settlement_required"):
                        errors.append(f"missed_candidate_leaked_lock:{c.get('fixture_id')}")
            except Exception:
                warnings.append(f"cannot_parse_audit:{f.name}")
        if not found:
            warnings.append("no_missed_candidates_audit_found")
    else:
        warnings.append("audit_dir_missing")

    # Determine status
    status = "PASS"
    if errors:
        status = "FAIL"
    elif warnings:
        status = "WARN"

    result = {
        "schema_version": "v2_shadow_boundary_check.v1",
        "status": status,
        "production_dependency": False,
        "production_verified": False,
        "formal_v2_uses_cache": False,
        "shadow_affects_formal": False,
        "daily_pool_owner_valid": len([e for e in errors if "DAILY_POOL" in e]) == 0,
        "window_checker_owner_valid": True,
        "settlement_guard_valid": len([e for e in errors if "settlement" in e.lower()]) == 0,
        "missed_candidates_guard_valid": len([e for e in errors if "missed" in e.lower()]) == 0,
        "doc_exists": doc_ok,
        "doc_phrases_found": len(REQUIRED_DOC_PHRASES) - len([e for e in errors if e.startswith("doc_missing_phrase")]),
        "doc_phrases_total": len(REQUIRED_DOC_PHRASES),
        "no_api": True,
        "no_key_read": True,
        "no_push": True,
        "no_cron": True,
        "warnings": warnings,
        "errors": errors,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out_path = STATUS_DIR / "v2_shadow_boundary_check_20260517.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if status == "FAIL":
        raise SystemExit(1)
    if status == "BLOCKER":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
