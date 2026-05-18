#!/usr/bin/env python3
"""Phase D.2.1 — V2 Shadow Baseline Checker (evidence-hardened, read-only verification)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _secret_scan(text: str) -> list[str]:
    findings: list[str] = []
    for pat_name, pat in [("sk_key", r"sk-[A-Za-z0-9]{20,}"), ("key_like", r"(?i)x-apisports-key"), ("token_like", r"(?i)access_token")]:
        if re.search(pat, text):
            findings.append(pat_name)
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="V2 Shadow Baseline Checker (evidence-hardened)")
    parser.add_argument("--date", required=False, default=None, help="YYYYMMDD (default: today)")
    args = parser.parse_args()
    date_key = args.date or datetime.now(CN_TZ).strftime("%Y%m%d")

    baseline_path = STATUS_DIR / f"v2_shadow_baseline_{date_key}.json"
    out_path = STATUS_DIR / f"v2_shadow_baseline_check_{date_key}.json"

    errors: list[str] = []
    warnings: list[str] = []

    if not baseline_path.exists():
        result = {
            "status": "BLOCKER",
            "baseline_exists": False,
            "errors": ["baseline_marker_missing"],
            "date": date_key,
            "generated_at": datetime.now(CN_TZ).isoformat(),
        }
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    marker = _load_json(baseline_path)
    report = marker.get("report", {})

    # Top-level boundary checks
    for field, expected in [("production_dependency", False), ("production_verified", False), ("formal_v2_uses_cache", False), ("shadow_affects_formal", False)]:
        if marker.get(field, True):
            errors.append(f"boundary_{field}_not_false")

    for field in ["no_api", "no_key_read", "no_push", "no_cron", "no_task_trigger", "no_bet_locked_write", "no_settlement_write"]:
        if not marker.get(field):
            errors.append(f"guard_{field}_not_true")

    # Evidence quality checks per component
    components = ["daily_pool", "window_checker", "daily_status", "missed_candidates", "settlement"]
    for key in components:
        comp = report.get(key, {})
        eq = comp.get("evidence_quality", "missing")
        sources = comp.get("evidence_sources", [])
        assumptions = comp.get("assumptions", [])
        unknown_fields = comp.get("unknown_fields", [])

        # Must have evidence_sources
        if not sources:
            warnings.append(f"{key}_NO_EVIDENCE_SOURCES")
        # Must have evidence_quality
        if eq == "missing":
            warnings.append(f"{key}_EVIDENCE_MISSING")
        # Unknown fields must not pass silently
        if unknown_fields:
            warnings.append(f"{key}_UNKNOWN_FIELDS")

    # Settlement-specific checks
    st = report.get("settlement", {})
    st_assumptions = st.get("assumptions", [])
    st_targets = int(st.get("settlement_targets", 0) or 0)

    # Reject hardcoded assumptions
    hardcoded_assumptions = [a for a in st_assumptions if "by_design" in a.lower() or "hardcoded" in a.lower()]
    if hardcoded_assumptions:
        errors.append(f"SETTLEMENT_HARDCODED_ASSUMPTION:{';'.join(hardcoded_assumptions)}")
    if "lock_owner_field_missing_all_settled_assumed_safe" in str(st_assumptions):
        if st_targets > 0:
            warnings.append("SETTLEMENT_PARTIAL_EVIDENCE_WITH_TARGETS")

    # Check only_window_checker_locks evidence
    if st.get("evidence_quality") == "partial" and "no_targets_to_verify" not in str(st_assumptions):
        if not st.get("only_window_checker_locks"):
            errors.append("SETTLEMENT_NOT_ONLY_WINDOW_CHECKER")

    # DAILY_POOL boundary
    dp = report.get("daily_pool", {})
    if dp.get("writes_bet_locked"):
        errors.append("DAILY_POOL_BET_LOCKED_LEAK")
    if dp.get("writes_locked_stage"):
        errors.append("DAILY_POOL_LOCKED_STAGE_LEAK")

    # Missed candidates boundary
    mc = report.get("missed_candidates", {})
    if mc.get("leaked_to_bet_locked"):
        errors.append("MISSED_LEAKED_TO_BET")
    if mc.get("leaked_to_settlement"):
        errors.append("MISSED_LEAKED_TO_SETTLE")
    if mc.get("leaked_to_qq"):
        errors.append("MISSED_LEAKED_TO_QQ")

    # Secret safety
    marker_text = json.dumps(marker, ensure_ascii=False)
    sec = _secret_scan(marker_text)
    if sec:
        errors.append(f"secret_pattern_detected:{','.join(sec)}")

    status = "FAIL" if errors else ("WARN" if warnings else "PASS")

    result = {
        "status": status,
        "baseline_exists": True,
        "production_dependency": marker.get("production_dependency", True),
        "production_verified": marker.get("production_verified", True),
        "formal_v2_uses_cache": marker.get("formal_v2_uses_cache", True),
        "shadow_affects_formal": marker.get("shadow_affects_formal", True),
        "no_api": marker.get("no_api", False),
        "no_push": marker.get("no_push", False),
        "no_cron": marker.get("no_cron", False),
        "no_task_trigger": marker.get("no_task_trigger", False),
        "no_bet_locked_write": marker.get("no_bet_locked_write", False),
        "no_settlement_write": marker.get("no_settlement_write", False),
        "secret_safe": len(sec) == 0,
        "evidence_hardened": True,
        "hardcoded_assumption_rejected": len(hardcoded_assumptions) == 0,
        "warnings": warnings,
        "errors": errors,
        "date": date_key,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if status == "FAIL" or status == "BLOCKER":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
