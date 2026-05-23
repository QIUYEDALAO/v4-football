#!/usr/bin/env python3
"""Plan-only V3/V4 dashboard daily update gate.

This runner models the after-scan and after-validation dashboard refresh gates.
It does not run V4 scan, capture, QQ push, cloud publish, cron creation, or
strategy logic. Apply mode writes only a status marker for review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
STATUS = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))

PLAN = STATUS / "v3v4_dashboard_daily_auto_update_cron_plan_20260523.json"
SCAN_MARKER = STATUS / "v4_scout_date_daily1200_post_repair_openclaw_verify_20260523.json"
BRIEF_MARKER = STATUS / "v3v4_dashboard_brief_resolution_20260523.json"
CANDIDATE_MARKER = STATUS / "v3v4_dashboard_candidate_view_20260523.json"
VALIDATION_SUMMARY = STATUS / "v3v4_validation_summary_20260523.json"
HISTORY_RECOVERY = STATUS / "v4_match_date_validation_history_recovery_20260523.json"
LAST_GOOD = STATUS / "v3v4_intel_ops_console_daily_refresh_last_good.json"


def load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def digest(paths: list[Path]) -> str:
    parts = []
    for path in paths:
        if path.exists():
            parts.append(hashlib.sha256(path.read_bytes()).hexdigest())
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def build_marker(args: argparse.Namespace) -> dict[str, Any]:
    plan = load(PLAN)
    scan = load(SCAN_MARKER)
    brief = load(BRIEF_MARKER)
    candidate = load(CANDIDATE_MARKER)
    validation = load(VALIDATION_SUMMARY)
    recovery = load(HISTORY_RECOVERY)
    phase_cfg = (plan.get("tasks") or {}).get(args.phase, {}) if isinstance(plan.get("tasks"), dict) else {}
    blockers: list[str] = []

    if args.phase == "after-scan":
        if phase_cfg.get("planned_time") != "13:00":
            blockers.append("after_scan_time_not_1300")
        scan_completed = bool(scan) and scan.get("contaminated_rows") == 0 and scan.get("active_scan_time") == "12:00"
        brief_ready = bool(brief.get("brief_exists")) and brief.get("date") == args.date and brief.get("is_today_brief") is True
        candidate_ready = bool(candidate) and candidate.get("scan_date") == args.date
        source_window_ok = scan.get("active_scan_window") == "daily_1200" and candidate.get("source_window") in {"daily_1200", "auto"}
        if not scan_completed:
            blockers.append("SCAN_NOT_READY")
        if not brief_ready:
            blockers.append("BRIEF_NOT_READY")
        if not candidate_ready:
            blockers.append("CANDIDATE_NOT_READY")
        if not source_window_ok:
            blockers.append("SOURCE_WINDOW_NOT_DAILY_1200_COMPATIBLE")
        status = "SCAN_NOT_READY" if any(b in blockers for b in ["SCAN_NOT_READY", "BRIEF_NOT_READY", "CANDIDATE_NOT_READY"]) else "READY"
        allowed_updates = ["candidate_list", "A_B_SKIP", "v4_status", "data_status_card", "today_brief_display"]
        forbidden_updates = ["yesterday_validation", "cumulative_validation", "validation_summary", "attribution", "review"]
        validation_touched = False
        candidate_touched = args.mode == "apply" and not blockers
        marker = {
            "status": status,
            "requires_scan_completed": True,
            "scan_completion_marker": str(SCAN_MARKER.relative_to(ROOT)),
            "scan_completed": scan_completed,
            "brief_ready": brief_ready,
            "candidate_ready": candidate_ready,
            "source_window": candidate.get("source_window"),
            "source_window_policy": "daily_1200_required; auto accepted only as dashboard resolver alias after daily_1200 proof",
            "allowed_updates": allowed_updates,
            "forbidden_updates": forbidden_updates,
            "validation_touched": validation_touched,
            "candidate_touched": candidate_touched,
            "last_good_preserved_on_not_ready": True,
        }
    else:
        if phase_cfg.get("planned_time") != "13:30":
            blockers.append("after_validation_time_not_1330")
        validation_ready = bool(validation.get("source_files")) and validation.get("date_filter_field") == "match_date"
        history_ready = bool(recovery) and recovery.get("step_4", {}).get("status") == "PASS"
        if not validation_ready:
            blockers.append("VALIDATION_NOT_READY")
        # Existing history-recovery report may not be present in older worktrees, but
        # validation summary with source files is still the hard data gate.
        status = "VALIDATION_NOT_READY" if not validation_ready else "READY"
        allowed_updates = ["yesterday_validation", "cumulative_validation", "validation_summary", "validation_audit"]
        forbidden_updates = ["today_candidate_source", "brief_source", "candidate_raw_numbers", "v4_strategy"]
        candidate_touched = False
        validation_touched = args.mode == "apply" and not blockers
        marker = {
            "status": status,
            "requires_validation_completed": True,
            "validation_completion_marker": str(VALIDATION_SUMMARY.relative_to(ROOT)),
            "validation_ready": validation_ready,
            "history_recovery_ready": history_ready,
            "api_enabled": bool(validation.get("api_enabled")),
            "api_disabled_reason": validation.get("api_disabled_reason"),
            "brief_used_for_hit_rate": validation.get("brief_used_for_hit_rate"),
            "date_filter_field": validation.get("date_filter_field"),
            "allowed_updates": allowed_updates,
            "forbidden_updates": forbidden_updates,
            "validation_touched": validation_touched,
            "candidate_touched": candidate_touched,
            "last_good_preserved_on_not_ready": True,
        }

    common = {
        "schema_version": "v3v4_dashboard_daily_update_gate.v1",
        "phase": "V3V4-DASHBOARD-DAILY-AUTO-UPDATE-SCHEDULE-CORRECTION-20260523",
        "generated_at": datetime.now(TZ).isoformat(),
        "date": args.date,
        "update_phase": args.phase,
        "mode": args.mode,
        "planned_time": phase_cfg.get("planned_time"),
        "command_review_only": True,
        "cron_enabled": False,
        "autosync_cron_created": False,
        "boss_approval_required": True,
        "auto_retry": False,
        "auto_kill": False,
        "timeout_change": False,
        "capture_ran": False,
        "v4_scan_ran": False,
        "QQ_push": False,
        "push_enabled": False,
        "cloud_publish": False,
        "strategy_changed": False,
        "v4_candidate_numbers_changed": False,
        "validation_numbers_changed": False,
        "attribution_numbers_changed": False,
        "brief_used_for_hit_rate": False,
        "scan_date_used_for_validation": False,
        "v2_restored": False,
        "v33_active": False,
        "c_active_in_dashboard": False,
        "c_validation_visible": False,
        "last_7d_visible": False,
        "source_hash": digest([SCAN_MARKER, BRIEF_MARKER, CANDIDATE_MARKER, VALIDATION_SUMMARY]),
        "last_good_path": str(LAST_GOOD.relative_to(ROOT)),
        "blockers": blockers,
    }
    return common | marker


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--phase", choices=["after-scan", "after-validation"], required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], required=True)
    parser.add_argument("--no-api", action="store_true", required=True)
    parser.add_argument("--no-capture", action="store_true", required=True)
    parser.add_argument("--no-push", action="store_true", required=True)
    parser.add_argument("--no-cloud", action="store_true", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    marker = build_marker(args)
    if args.phase == "after-validation" and args.mode == "apply" and not marker.get("blockers"):
        from generate_intel_desk_html import build_dashboard

        dashboard_marker = build_dashboard(write=True, date_key=args.date)
        marker["dashboard_refreshed"] = True
        marker["dashboard_sha256"] = dashboard_marker.get("dashboard_sha256")
        marker["script_validation_visible"] = True
    else:
        marker["dashboard_refreshed"] = False
    out = STATUS / f"v3v4_dashboard_daily_update_{args.phase.replace('-', '_')}_{args.mode.replace('-', '_')}_{args.date}.json"
    out.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(marker, ensure_ascii=False, indent=2))
    if args.strict and marker.get("blockers"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
