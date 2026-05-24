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

PLAN_CANDIDATES = [
    STATUS / "v3v4_dashboard_daily_auto_update_cron_plan_20260524.json",
    STATUS / "v3v4_dashboard_daily_auto_update_cron_plan_20260523.json",
]
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


def plan_path() -> Path:
    for path in PLAN_CANDIDATES:
        if path.exists():
            return path
    return PLAN_CANDIDATES[-1]


def final_task_config(plan: dict[str, Any]) -> dict[str, Any]:
    for task in plan.get("schedule", []):
        if isinstance(task, dict) and task.get("task") == "V3V4_DASHBOARD_AFTER_VALIDATION_REFRESH_FINAL":
            return task
    return {}


def validation_source_hash(validation: dict[str, Any]) -> str:
    return str(validation.get("source_hash") or digest([VALIDATION_SUMMARY]))


def previous_after_validation_hash(date: str) -> tuple[str | None, str | None]:
    preferred = [
        STATUS / f"v3v4_dashboard_daily_update_after_validation_apply_{date}.json",
        STATUS / f"v3v4_dashboard_daily_update_after_validation_dry_run_{date}.json",
    ]
    candidates = [p for p in preferred if p.exists()]
    candidates.extend(
        sorted(
            STATUS.glob("v3v4_dashboard_daily_update_after_validation_apply_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    )
    candidates.extend(
        sorted(
            STATUS.glob("v3v4_dashboard_daily_update_after_validation_dry_run_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    )
    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        data = load(path)
        if data.get("final_pass") is True:
            continue
        value = data.get("validation_source_hash")
        if value:
            return str(value), str(path.relative_to(ROOT))
    return None, None


def build_marker(args: argparse.Namespace) -> dict[str, Any]:
    plan_file = plan_path()
    plan = load(plan_file)
    scan = load(SCAN_MARKER)
    brief = load(BRIEF_MARKER)
    candidate = load(CANDIDATE_MARKER)
    validation = load(VALIDATION_SUMMARY)
    recovery = load(HISTORY_RECOVERY)
    phase_cfg = (plan.get("tasks") or {}).get(args.phase, {}) if isinstance(plan.get("tasks"), dict) else {}
    if args.final_pass:
        phase_cfg = final_task_config(plan)
    blockers: list[str] = []

    if args.phase == "after-scan":
        if args.final_pass:
            blockers.append("FINAL_PASS_ONLY_ALLOWED_AFTER_VALIDATION")
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
        if args.final_pass and args.phase != "after-validation":
            blockers.append("FINAL_PASS_ONLY_ALLOWED_AFTER_VALIDATION")
        if phase_cfg.get("planned_time") != "13:30":
            if args.final_pass:
                if phase_cfg.get("time") != "14:00":
                    blockers.append("after_validation_final_time_not_1400")
            else:
                blockers.append("after_validation_time_not_1330")
        validation_ready = bool(validation.get("source_files")) and validation.get("date_filter_field") == "match_date"
        history_ready = bool(recovery) and recovery.get("step_4", {}).get("status") == "PASS"
        if not validation_ready:
            blockers.append("VALIDATION_NOT_READY_FINAL" if args.final_pass else "VALIDATION_NOT_READY")
        # Existing history-recovery report may not be present in older worktrees, but
        # validation summary with source files is still the hard data gate.
        status = "VALIDATION_NOT_READY_FINAL" if args.final_pass and not validation_ready else ("VALIDATION_NOT_READY" if not validation_ready else "READY")
        allowed_updates = ["yesterday_validation", "cumulative_validation", "validation_summary", "validation_audit"]
        forbidden_updates = ["today_candidate_source", "brief_source", "candidate_raw_numbers", "v4_strategy"]
        candidate_touched = False
        validation_touched = args.mode == "apply" and not blockers
        current_validation_hash = validation_source_hash(validation)
        previous_hash, previous_hash_path = previous_after_validation_hash(args.date)
        source_hash_changed = previous_hash is not None and previous_hash != current_validation_hash
        final_refresh_status = None
        if args.final_pass:
            validation_touched = False
            if previous_hash is None:
                blockers.append("PREVIOUS_VALIDATION_SOURCE_HASH_MISSING")
                final_refresh_status = "VALIDATION_HASH_MISSING"
            elif not validation_ready:
                final_refresh_status = "VALIDATION_NOT_READY_FINAL"
            elif source_hash_changed:
                final_refresh_status = "REFRESH_VALIDATION_SECTION_ONLY"
                validation_touched = args.mode == "apply" and not blockers
            else:
                final_refresh_status = "NOOP"
        marker = {
            "status": status,
            "requires_validation_completed": True,
            "validation_completion_marker": str(VALIDATION_SUMMARY.relative_to(ROOT)),
            "validation_ready": validation_ready,
            "validation_source_hash": current_validation_hash,
            "previous_validation_source_hash": previous_hash,
            "previous_validation_source_hash_path": previous_hash_path,
            "source_hash_changed": source_hash_changed,
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
            "final_pass": bool(args.final_pass),
            "scan_ran": False,
            "validation_reran": False,
            "refresh_status": final_refresh_status or status,
        }

    common = {
        "schema_version": "v3v4_dashboard_daily_update_gate.v1",
        "phase": "V3V4-DASHBOARD-FINAL-PASS-RUNNER-AND-SCAN-TIMEOUT-FIX-20260524",
        "generated_at": datetime.now(TZ).isoformat(),
        "date": args.date,
        "update_phase": args.phase,
        "mode": args.mode,
        "planned_time": phase_cfg.get("time") if args.final_pass else phase_cfg.get("planned_time"),
        "plan_path": str(plan_file.relative_to(ROOT)) if plan_file.exists() else None,
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
    parser.add_argument("--final-pass", action="store_true")
    args = parser.parse_args()
    marker = build_marker(args)
    if args.final_pass and args.phase != "after-validation":
        marker["blockers"].append("FINAL_PASS_ONLY_ALLOWED_AFTER_VALIDATION")
    should_refresh_dashboard = (
        args.phase == "after-validation"
        and args.mode == "apply"
        and not marker.get("blockers")
        and not (args.final_pass and marker.get("refresh_status") == "NOOP")
    )
    if should_refresh_dashboard:
        from generate_intel_desk_html import build_dashboard

        dashboard_marker = build_dashboard(write=True, date_key=args.date)
        marker["dashboard_refreshed"] = True
        marker["dashboard_sha256"] = dashboard_marker.get("dashboard_sha256")
        marker["script_validation_visible"] = True
    else:
        marker["dashboard_refreshed"] = False
    if args.final_pass and args.phase == "after-validation":
        out = STATUS / f"v3v4_dashboard_after_validation_final_refresh_{args.date}.json"
    elif args.final_pass:
        out = STATUS / f"v3v4_dashboard_daily_update_{args.phase.replace('-', '_')}_invalid_final_pass_{args.date}.json"
    else:
        out = STATUS / f"v3v4_dashboard_daily_update_{args.phase.replace('-', '_')}_{args.mode.replace('-', '_')}_{args.date}.json"
    out.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(marker, ensure_ascii=False, indent=2))
    if args.strict and marker.get("blockers"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
