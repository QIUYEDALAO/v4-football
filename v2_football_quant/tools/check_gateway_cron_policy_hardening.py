#!/usr/bin/env python3
"""Gateway cron policy checker for V3/V4-only active scope.

Read-only: does not create, delete, or enable cron. Historical Gateway backups
may exist in archive; active policy must contain zero V2 cron jobs.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS_DIR = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))
DATE = "20260521"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    policy = load_json(STATUS_DIR / f"v3v4_gateway_cron_policy_{DATE}.json")
    blockers: list[str] = []
    warnings: list[str] = []
    if not policy:
        blockers.append("missing_v3v4_gateway_cron_policy")
    active_v2_cron_count = int(policy.get("active_v2_cron_count", 999) if policy else 999)
    if active_v2_cron_count != 0:
        blockers.append(f"active_v2_cron_count_not_zero:{active_v2_cron_count}")
    if policy.get("cron_enabled") is not False:
        blockers.append("cron_enabled_not_false")
    allowed = set(policy.get("allowed_cron_scopes", []))
    if not {"V3", "V4", "SYS", "cloud"}.issubset(allowed):
        warnings.append(f"allowed_cron_scopes_incomplete:{sorted(allowed)}")
    for key in ("v2_window_checker_active", "v2_daily_pool_active", "v2_settlement_active", "v2_fallback_active"):
        if policy.get(key) is not False:
            blockers.append(f"{key}_not_false")
    status = "BLOCKER" if blockers else ("WARN_ONLY" if warnings else "PASS")
    result = {
        "checker": "tools/check_gateway_cron_policy_hardening.py",
        "phase": "V2-DECOMMISSION-KEEP-V3-V4-ONLY-EXECUTION-20260521",
        "generated_at": datetime.now(TZ).isoformat(),
        "conclusion": status,
        "active_v2_cron_count": active_v2_cron_count if policy else None,
        "v2_window_checker_active": policy.get("v2_window_checker_active") if policy else None,
        "v2_daily_pool_active": policy.get("v2_daily_pool_active") if policy else None,
        "v2_settlement_active": policy.get("v2_settlement_active") if policy else None,
        "v2_fallback_active": policy.get("v2_fallback_active") if policy else None,
        "cron_enabled": policy.get("cron_enabled") if policy else None,
        "new_cron_created": False,
        "capture_ran": False,
        "qq_push": False,
        "cloud_publish": False,
        "blockers": blockers,
        "warnings": warnings,
    }
    out = STATUS_DIR / f"check_gateway_cron_policy_hardening_result_{DATE}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
