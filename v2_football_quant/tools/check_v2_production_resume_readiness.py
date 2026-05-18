#!/usr/bin/env python3
"""Phase D.8 — V2 Production Resume Readiness Gate (read-only)."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_production_resume_readiness.v1"

REQUIRED_REASON_CODES = [
    "OFFICIAL_BET_LOCKED_ZERO",
    "WINDOW_CHECKER_NEW_LOCKS_ZERO",
    "LOCK_OWNER_MISSING",
    "MISSED_CANDIDATES_PRESENT",
    "SETTLEMENT_WITHOUT_OFFICIAL_LOCKS",
    "SETTLEMENT_WITHOUT_WINDOW_LOCKS",
    "HISTORICAL_SETTLEMENT_CONTAMINATION",
]

SECRET_PAT = re.compile(r"APIFOOTBALL_KEY|OPENCLAW_APIFOOTBALL_KEY|x-apisports-key|sk-[A-Za-z0-9]{20,}")


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=BASE_DIR, text=True).strip()


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _scan_next_run_at() -> tuple[bool, list[str]]:
    """Return (found_enabled_like, files_with_next_run_at)."""
    hits: list[str] = []
    enabled = False
    for p in STATUS_DIR.glob("*.json"):
        data = _load_json(p, None)
        if not isinstance(data, dict):
            continue
        if "nextRunAt" in data:
            hits.append(str(p))
            v = data.get("nextRunAt")
            if v not in (None, "", "null", "None"):
                enabled = True
    return enabled, hits


def _scan_secret_safe(paths: list[Path]) -> bool:
    for p in paths:
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        if SECRET_PAT.search(txt):
            return False
    return True


def _staged_flags() -> dict[str, bool]:
    staged = _run(["git", "diff", "--cached", "--name-only"])
    files = [x.strip() for x in staged.splitlines() if x.strip()]
    return {
        "runtime_artifacts_staged": any(f.startswith("data/runtime/") for f in files),
        "paper_trading_staged": any(f.startswith("data/paper_trading/") for f in files),
        "dashboard_html_staged": any(f.startswith("data/runtime/dashboard/") and f.endswith(".html") for f in files),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False, default="20260517")
    args = parser.parse_args()
    date_key = str(args.date).replace("-", "")

    preflight = _load_json(STATUS_DIR / f"v2_settlement_preflight_{date_key}.json", {})
    preflight_check = _load_json(STATUS_DIR / f"v2_settlement_preflight_check_{date_key}.json", {})
    wrapper = _load_json(STATUS_DIR / f"v2_settlement_preflight_wrapper_block_test_{date_key}.json", {})
    shadow = _load_json(STATUS_DIR / f"v2_settlement_shadow_guard_{date_key}.json", {})
    shadow_check = _load_json(STATUS_DIR / f"v2_settlement_shadow_guard_check_{date_key}.json", {})
    completion = _load_json(STATUS_DIR / f"phase_d_completion_check_{date_key}.json", {})

    warnings: list[str] = []
    risks: list[str] = []
    blockers: list[str] = []

    staged = _staged_flags()
    next_run_enabled, next_run_files = _scan_next_run_at()
    secret_safe = _scan_secret_safe(
        [
            STATUS_DIR / f"v2_settlement_preflight_{date_key}.json",
            STATUS_DIR / f"v2_settlement_preflight_check_{date_key}.json",
            STATUS_DIR / f"v2_settlement_preflight_wrapper_block_test_{date_key}.json",
            STATUS_DIR / f"v2_settlement_shadow_guard_{date_key}.json",
            STATUS_DIR / f"v2_settlement_shadow_guard_check_{date_key}.json",
            STATUS_DIR / f"phase_d_completion_check_{date_key}.json",
        ]
    )

    reason_codes = preflight.get("decision", {}).get("reason_codes", []) if isinstance(preflight, dict) else []
    reason_codes = [str(x) for x in reason_codes]

    phase_d_complete = bool(completion.get("phase_d_engineering_complete", False))
    known_historical_fail_archived = bool(completion.get("known_historical_fail", False))
    preflight_gate_installed = bool(preflight) and preflight.get("settlement_allowed") is False
    wrapper_block_test_passed = str(wrapper.get("status", "")).upper() == "PASS"
    verified_unchanged_proven = bool(
        wrapper.get("verified_hash_unchanged", False)
        and wrapper.get("verified_mtime_unchanged", False)
        and wrapper.get("verified_size_unchanged", False)
    )
    preflight_blocks_20260517 = bool(preflight.get("settlement_allowed") is False and preflight.get("fail_closed") is True)
    settlement_shadow_fail_preserved = str(shadow.get("status", "")).upper() == "FAIL" and (
        "MISSED_IN_SETTLEMENT" in (shadow.get("report", {}).get("errors", []) if isinstance(shadow.get("report", {}), dict) else [])
        or "MISSED_IN_SETTLEMENT" in (shadow_check.get("errors", []) if isinstance(shadow_check, dict) else [])
    )
    formal_v2_uses_cache = bool(completion.get("formal_v2_uses_cache", False))
    shadow_affects_formal = bool(completion.get("shadow_affects_formal", False))

    cron_enabled = next_run_enabled
    qq_push_enabled = False
    production_verified_written = bool(
        preflight.get("production_verified", False)
        or preflight_check.get("production_verified", False)
        or wrapper.get("production_verified", False)
        or shadow.get("production_verified", False)
        or shadow_check.get("production_verified", False)
        or completion.get("production_verified", False)
    )

    required_reasons_ok = all(code in reason_codes for code in REQUIRED_REASON_CODES)
    if not required_reasons_ok:
        risks.append("required_reason_codes_incomplete")

    checks = {
        "phase_d_complete": phase_d_complete,
        "known_historical_fail_archived": known_historical_fail_archived,
        "preflight_gate_installed": preflight_gate_installed,
        "wrapper_block_test_passed": wrapper_block_test_passed,
        "verified_unchanged_proven": verified_unchanged_proven,
        "preflight_blocks_20260517": preflight_blocks_20260517,
        "settlement_shadow_fail_preserved": settlement_shadow_fail_preserved,
        "formal_v2_uses_cache": formal_v2_uses_cache,
        "shadow_affects_formal": shadow_affects_formal,
        "cron_enabled": cron_enabled,
        "qq_push_enabled": qq_push_enabled,
        "production_verified_written": production_verified_written,
        "runtime_artifacts_staged": staged["runtime_artifacts_staged"],
        "paper_trading_staged": staged["paper_trading_staged"],
        "secret_safe": secret_safe,
    }

    # BLOCKER conditions
    if production_verified_written:
        blockers.append("production_verified_written_true")
    if staged["runtime_artifacts_staged"]:
        blockers.append("runtime_artifacts_staged_true")
    if staged["paper_trading_staged"]:
        blockers.append("paper_trading_staged_true")
    if not secret_safe:
        blockers.append("secret_safe_false")
    if formal_v2_uses_cache:
        blockers.append("formal_v2_uses_cache_true")
    if shadow_affects_formal:
        blockers.append("shadow_affects_formal_true")

    # NOT_READY conditions
    not_ready = False
    if not preflight_gate_installed:
        risks.append("preflight_gate_not_installed")
        not_ready = True
    if not wrapper_block_test_passed:
        risks.append("wrapper_block_test_not_passed")
        not_ready = True
    if not verified_unchanged_proven:
        risks.append("verified_unchanged_not_proven")
        not_ready = True

    # WARN-only conditions (non-blocking for review)
    if cron_enabled:
        warnings.append("nextRunAt_detected_review_required")
    if not phase_d_complete:
        warnings.append("phase_d_complete_false")
    if not known_historical_fail_archived:
        warnings.append("known_historical_fail_not_archived")
    if not settlement_shadow_fail_preserved:
        warnings.append("settlement_shadow_fail_not_preserved")

    if blockers:
        readiness_status = "BLOCKER"
    elif not_ready:
        readiness_status = "NOT_READY"
    elif warnings or risks:
        readiness_status = "WARN"
    else:
        readiness_status = "READY_FOR_BOSS_REVIEW"

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "readiness_status": readiness_status,
        "resume_allowed_now": False,
        "boss_approval_required": True,
        "checks": checks,
        "risks": risks,
        "warnings": warnings,
        "blockers": blockers,
        "next_options": [
            "D.8.1 Controlled Resume Plan",
            "Phase E V4 Scan Standardization",
            "Pause architecture and observe manually",
        ],
        "context": {
            "required_reason_codes_present": required_reasons_ok,
            "nextRunAt_files": next_run_files,
            "preflight_reason_codes": reason_codes,
            "phase_d_completion_status": completion.get("status"),
            "phase_d_business_pass": completion.get("phase_d_business_pass"),
        },
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out = STATUS_DIR / f"v2_production_resume_readiness_{date_key}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if readiness_status == "BLOCKER":
        raise SystemExit(2)
    if readiness_status == "NOT_READY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
