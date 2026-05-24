#!/usr/bin/env python3
"""Check 14:00 final validation rerun + dashboard refresh gate."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
RUNNER = ROOT / "tools/run_v3v4_validation_final_and_dashboard_refresh.py"
TZ = timezone(timedelta(hours=8))
DATE = datetime.now(TZ).strftime("%Y%m%d")


def load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=DATE)
    args = parser.parse_args()
    blockers: list[str] = []
    warnings: list[str] = []
    plan_candidates = sorted(STATUS.glob("v3v4_dashboard_daily_auto_update_cron_plan_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    plan_path = plan_candidates[0] if plan_candidates else STATUS / f"v3v4_dashboard_daily_auto_update_cron_plan_{args.date}.json"
    plan = load(plan_path)
    runner_text = RUNNER.read_text(encoding="utf-8") if RUNNER.exists() else ""

    if not RUNNER.exists():
        blockers.append("final_validation_runner_missing")
    if "final_validation_ran" not in runner_text:
        blockers.append("runner_missing_final_validation_marker")

    final_cfg = (plan.get("tasks") or {}).get("final-validation-dashboard-refresh", {}) if isinstance(plan.get("tasks"), dict) else {}
    final_cmd = str(final_cfg.get("command", ""))
    if "run_v3v4_validation_final_and_dashboard_refresh.py" not in final_cmd:
        blockers.append("cron_plan_final_command_not_validation_runner")
    if final_cfg.get("final_validation_ran") is not True:
        blockers.append("cron_plan_final_validation_ran_not_true")
    if final_cfg.get("dashboard_refresh_after_validation") is not True:
        blockers.append("cron_plan_dashboard_refresh_after_validation_not_true")
    if final_cfg.get("noop_when_source_hash_unchanged") is not True:
        blockers.append("cron_plan_final_noop_guard_missing")
    if plan.get("cron_enabled") is not False:
        blockers.append("cron_enabled_not_false")

    proc = subprocess.run([
        sys.executable, str(RUNNER), "--date", args.date, "--mode", "dry-run",
        "--no-capture", "--no-push", "--no-cloud", "--strict",
    ], cwd=str(ROOT), text=True, capture_output=True, timeout=180)
    if proc.returncode != 0:
        warnings.append(f"final_validation_runner_rc_{proc.returncode}")

    marker = load(STATUS / f"v3v4_validation_final_and_dashboard_refresh_{args.date}.json")
    if marker.get("final_validation_ran") is not True:
        blockers.append("final_validation_ran_not_true")
    if marker.get("scan_ran") is not False:
        blockers.append("final_scan_ran")
    if marker.get("candidate_touched") is not False:
        blockers.append("final_candidate_touched")
    if marker.get("match_date_used") is not True:
        blockers.append("final_match_date_not_used")
    if marker.get("scan_date_used_for_validation") is not False:
        blockers.append("final_scan_date_used_for_validation")
    if marker.get("brief_used_for_hit_rate") is not False:
        blockers.append("final_brief_used_for_hit_rate")
    if marker.get("brief_used_for_script_validation") is not False:
        blockers.append("final_brief_used_for_script_validation")
    if marker.get("yesterday_validation_target_date") != "20260523":
        blockers.append("final_target_date_not_20260523")
    if marker.get("script_unknown_excluded_from_denominator") is not True:
        blockers.append("script_unknown_denominator_guard_missing")
    val_path = STATUS / f"v3v4_validation_summary_{args.date}.json"
    if val_path.exists():
        val = load(val_path)
        y = ((val.get("dashboard_active") or {}).get("yesterday") or {})
        a = ((y.get("A") or {}).get("display_rate") or "N/A")
        b = ((y.get("B") or {}).get("display_rate") or "N/A")
        ab = (((y.get("A_plus_B") or y.get("AB") or {})).get("display_rate") or "N/A")
        if a == "N/A" and b == "N/A" and ab == "N/A":
            reason = ((val.get("yesterday") or {}).get("reason")) or ((y.get("A_plus_B") or {}).get("reason"))
            if not reason:
                blockers.append("final_all_na_without_reason")
    if marker.get("refresh_status") not in {"NOOP_AFTER_VALIDATION_RERUN", "UPDATED_AFTER_FINAL_VALIDATION", "VALIDATION_NOT_READY_FINAL", "VALIDATION_HASH_MISSING"}:
        blockers.append(f"final_refresh_status_invalid:{marker.get('refresh_status')}")
    if marker.get("dashboard_validation_refreshed") not in {True, False}:
        blockers.append("dashboard_validation_refreshed_missing")
    for key in ("capture_ran", "QQ_push", "cloud_publish", "cron_enabled", "v2_restored", "v33_active", "c_active_in_dashboard", "c_validation_visible", "c_script_validation_visible", "last_7d_visible"):
        if marker.get(key) is not False:
            blockers.append(f"{key}_not_false")

    result = {
        "checker": "tools/check_v3v4_dashboard_after_validation_final_refresh.py",
        "phase": "V3V4-DASHBOARD-DYNAMIC-DATE-MARKER-AND-MATCHDATE-TZ-HOTFIX",
        "date": args.date,
        "final_validation_guard": not blockers,
        "scan_boundary_guard": marker.get("scan_ran") is False,
        "candidate_boundary_guard": marker.get("candidate_touched") is False,
        "final_validation_ran": marker.get("final_validation_ran"),
        "dashboard_validation_refreshed": marker.get("dashboard_validation_refreshed"),
        "refresh_status": marker.get("refresh_status"),
        "source_hash_guard": marker.get("previous_validation_source_hash") is not None,
        "noop_on_same_hash": marker.get("refresh_status") == "NOOP_AFTER_VALIDATION_RERUN",
        "last_good_preserved": marker.get("last_good_preserved"),
        "scan_ran": marker.get("scan_ran"),
        "candidate_touched": marker.get("candidate_touched"),
        "match_date_used": marker.get("match_date_used"),
        "yesterday_validation_target_date": marker.get("yesterday_validation_target_date"),
        "cron_enabled": plan.get("cron_enabled"),
        "blockers": blockers,
        "warnings": warnings,
        "conclusion": "PASS" if not blockers else "BLOCKER",
    }
    out = STATUS / f"check_v3v4_dashboard_after_validation_final_refresh_result_{args.date}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
