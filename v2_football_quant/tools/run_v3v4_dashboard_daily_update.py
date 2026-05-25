#!/usr/bin/env python3
"""V3/V4 dashboard daily update gate with dynamic date marker resolution.

This runner models the after-scan and after-validation dashboard refresh gates.
It never runs V4 scan, capture, QQ push, cloud publish, cron creation, or V4
strategy logic. All formal markers are resolved from --date; stale fixed-date
markers are never used as fallback.
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
REPORTS = ROOT / "data/daily_reports"
TZ = timezone(timedelta(hours=8))
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


def plan_path() -> Path | None:
    candidates = sorted(STATUS.glob("v3v4_dashboard_daily_auto_update_cron_plan_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def marker_paths(date: str) -> dict[str, Path]:
    return {
        "scout": REPORTS / f"scout_v4_{date}.json",
        "scan_perf": REPORTS / f"scan_perf_v4_{date}.json",
        "brief": REPORTS / f"v4_openclaw_brief_{date}.txt",
        "brief_resolution": STATUS / f"v3v4_dashboard_brief_resolution_{date}.json",
        "candidate_view": STATUS / f"v3v4_dashboard_candidate_view_{date}.json",
        "validation_summary": STATUS / f"v3v4_validation_summary_{date}.json",
        "script_validation_summary": STATUS / f"v4_script_validation_summary_{date}.json",
        "history_recovery": STATUS / f"v4_match_date_validation_history_recovery_{date}.json",
    }


def load_allowlist(date: str | None = None) -> dict[str, Any]:
    if date is None:
        from datetime import datetime, timezone, timedelta
        date = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d")
    path = STATUS / f"v3v4_dashboard_active_source_allowlist_{date}.json"
    return load(path) if path.exists() else {}


def is_allowlisted(path: Path, key: str) -> bool:
    cfg = load_allowlist().get("active_allowlist", {})
    if not isinstance(cfg, dict):
        return True
    allowed = cfg.get(key)
    if not isinstance(allowed, list):
        return True
    rel = str(path.relative_to(ROOT))
    return rel in allowed


def _yesterday_target(date: str) -> str:
    return (datetime.strptime(date, "%Y%m%d").date() - timedelta(days=1)).strftime("%Y%m%d")

def ensure_validation_summary(date: str, paths: dict[str, Path]) -> bool:
    if paths["validation_summary"].exists():
        return True
    try:
        from v3v4_dashboard_validation_resolver import resolve as resolve_validation
        resolved = resolve_validation(date, write=True)
        return bool(resolved)
    except Exception:
        return False


def ensure_scan_markers(date: str, paths: dict[str, Path]) -> dict[str, Any]:
    rebuilt = False
    rebuild_status = "not_required"
    if (not paths["brief_resolution"].exists() or not paths["candidate_view"].exists()) and paths["brief"].exists():
        try:
            from v3v4_dashboard_brief_resolver import resolve as resolve_brief
            resolve_brief(date, write=True)
            rebuilt = True
            rebuild_status = "rebuilt_from_formal_brief"
        except Exception as exc:  # keep gate explicit; do not fallback to stale dates
            rebuild_status = f"rebuild_failed:{exc}"
    return {"attempted": rebuilt, "status": rebuild_status}

def enrich_team_cn(date: str) -> dict[str, Any]:
    result = {"candidate_enriched": False, "outside57_enriched": False, "errors": []}
    try:
        from v3v4_dashboard_brief_resolver import resolve as resolve_brief
        if (REPORTS / f"v4_openclaw_brief_{date}.txt").exists():
            resolve_brief(date, write=True)
            result["candidate_enriched"] = True
    except Exception as exc:
        result["errors"].append(f"candidate_enrich_failed:{exc}")
    try:
        import subprocess
        cmd = [sys.executable, str(ROOT / "tools/enrich_outside_57_pool_team_cn.py"), "--date", date, "--mode", "apply"]
        proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        if proc.returncode == 0:
            result["outside57_enriched"] = True
        else:
            result["errors"].append(f"outside57_enrich_rc_{proc.returncode}")
    except Exception as exc:
        result["errors"].append(f"outside57_enrich_failed:{exc}")
    return result


def final_task_config(plan: dict[str, Any]) -> dict[str, Any]:
    for task in plan.get("schedule", []):
        if not isinstance(task, dict):
            continue
        if task.get("task") in {"V4_VALIDATION_DRY_RUN_FINAL_AND_DASHBOARD_REFRESH", "V3V4_DASHBOARD_AFTER_VALIDATION_REFRESH_FINAL"}:
            return task
    return {}


def validation_source_hash(validation: dict[str, Any], paths: dict[str, Path]) -> str:
    return str(validation.get("source_hash") or digest([paths["validation_summary"], paths["script_validation_summary"]]))


def previous_after_validation_hash(date: str) -> tuple[str | None, str | None]:
    preferred = [
        STATUS / f"v3v4_dashboard_daily_update_after_validation_apply_{date}.json",
        STATUS / f"v3v4_dashboard_daily_update_after_validation_dry_run_{date}.json",
    ]
    candidates = [p for p in preferred if p.exists()]
    # Audit fallback only: same-date markers are preferred; cross-date is never used for gating.
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
    paths = marker_paths(args.date)
    yesterday_target = _yesterday_target(args.date)
    team_cn_enrich = enrich_team_cn(args.date)
    marker_resolution = ensure_scan_markers(args.date, paths)
    plan_file = plan_path()
    plan = load(plan_file) if plan_file else {}
    scan_perf = load(paths["scan_perf"])
    brief = load(paths["brief_resolution"])
    candidate = load(paths["candidate_view"])
    validation = load(paths["validation_summary"])
    recovery = load(paths["history_recovery"])
    phase_cfg = (plan.get("tasks") or {}).get(args.phase, {}) if isinstance(plan.get("tasks"), dict) else {}
    if args.final_pass:
        phase_cfg = final_task_config(plan)
    blockers: list[str] = []
    warnings: list[str] = []
    if paths["candidate_view"].exists() and not is_allowlisted(paths["candidate_view"], "candidate_view"):
        blockers.append("CANDIDATE_SOURCE_NOT_ALLOWLISTED")
    if paths["validation_summary"].exists() and not is_allowlisted(paths["validation_summary"], "validation_summary"):
        blockers.append("VALIDATION_SOURCE_NOT_ALLOWLISTED")
    if paths["script_validation_summary"].exists() and not is_allowlisted(paths["script_validation_summary"], "script_validation_summary"):
        blockers.append("SCRIPT_VALIDATION_SOURCE_NOT_ALLOWLISTED")

    if args.phase == "after-scan":
        if args.final_pass:
            blockers.append("FINAL_PASS_ONLY_ALLOWED_AFTER_VALIDATION")
        planned_time = phase_cfg.get("planned_time") or phase_cfg.get("time")
        if planned_time and planned_time != "13:00":
            blockers.append("after_scan_time_not_1300")
        scan_completed = bool(paths["scout"].exists() and scan_perf) and str(scan_perf.get("scout_file_date") or scan_perf.get("scan_date") or "").replace("-", "") == args.date
        brief_ready = bool(brief.get("brief_exists")) and brief.get("date") == args.date and brief.get("source_date") == args.date
        candidate_ready = bool(candidate) and candidate.get("scan_date") == args.date
        source_window = candidate.get("source_window") or brief.get("window") or scan_perf.get("run_tag")
        source_window_ok = source_window in {"daily_1200", "auto", "V4_MIDDAY", "midday"}
        if not scan_completed:
            blockers.append("SCAN_NOT_READY")
        if not brief_ready:
            blockers.append("BRIEF_NOT_READY")
        if not candidate_ready:
            blockers.append("CANDIDATE_NOT_READY")
        if not source_window_ok:
            blockers.append("SOURCE_WINDOW_NOT_DAILY_1200_COMPATIBLE")
        status = "SCAN_NOT_READY" if any(b in blockers for b in ["SCAN_NOT_READY", "BRIEF_NOT_READY", "CANDIDATE_NOT_READY"]) else "READY"
        validation_touched = False
        validation_summary_exists = ensure_validation_summary(args.date, paths)
        validation_preserved = bool(validation_summary_exists)
        candidate_touched = args.mode == "apply" and not blockers
        marker = {
            "status": status,
            "requires_scan_completed": True,
            "scan_completed": scan_completed,
            "scan_completion_marker": str(paths["scan_perf"].relative_to(ROOT)) if paths["scan_perf"].exists() else None,
            "scout_marker": str(paths["scout"].relative_to(ROOT)) if paths["scout"].exists() else None,
            "brief_ready": brief_ready,
            "candidate_ready": candidate_ready,
            "source_window": source_window,
            "source_window_policy": "daily_1200_required; V4_MIDDAY accepted as scan_perf run_tag alias for daily_1200",
            "allowed_updates": ["candidate_list", "A_B_SKIP", "v4_status", "data_status_card", "today_brief_display"],
            "forbidden_updates": ["yesterday_validation", "cumulative_validation", "validation_summary", "attribution", "review"],
            "dashboard_date": args.date,
            "yesterday_validation_target_date": yesterday_target,
            "validation_preserved": validation_preserved,
            "validation_touched": validation_touched,
            "candidate_touched": candidate_touched,
            "result_validation_changed": False,
            "script_validation_changed": False,
            "last_good_preserved_on_not_ready": True,
        }
    else:
        if args.final_pass and args.phase != "after-validation":
            blockers.append("FINAL_PASS_ONLY_ALLOWED_AFTER_VALIDATION")
        planned_time = phase_cfg.get("planned_time") or phase_cfg.get("time")
        if args.final_pass:
            if planned_time and planned_time != "14:00":
                blockers.append("after_validation_final_time_not_1400")
        elif planned_time and planned_time != "13:30":
            blockers.append("after_validation_time_not_1330")
        validation_ready = bool(validation.get("source_files")) and validation.get("date_filter_field") == "match_date"
        history_ready = bool(recovery) and recovery.get("step_4", {}).get("status") == "PASS"
        if not validation_ready:
            blockers.append("VALIDATION_NOT_READY_FINAL" if args.final_pass else "VALIDATION_NOT_READY")
        status = "VALIDATION_NOT_READY_FINAL" if args.final_pass and not validation_ready else ("VALIDATION_NOT_READY" if not validation_ready else "READY")
        candidate_touched = False
        validation_touched = args.mode == "apply" and not blockers
        current_validation_hash = validation_source_hash(validation, paths)
        previous_hash, previous_hash_path = previous_after_validation_hash(args.date)
        source_hash_changed = previous_hash is not None and previous_hash != current_validation_hash
        final_refresh_status = None
        if args.final_pass:
            validation_touched = False
            if previous_hash is None:
                warnings.append("previous_validation_source_hash_missing; preserving last_good")
                final_refresh_status = "VALIDATION_HASH_MISSING"
            elif not validation_ready:
                final_refresh_status = "VALIDATION_NOT_READY_FINAL"
            elif source_hash_changed:
                final_refresh_status = "UPDATED_AFTER_FINAL_VALIDATION"
                validation_touched = args.mode == "apply" and not blockers
            else:
                final_refresh_status = "NOOP_AFTER_VALIDATION_RERUN"
        marker = {
            "status": status,
            "requires_validation_completed": True,
            "validation_completion_marker": str(paths["validation_summary"].relative_to(ROOT)) if paths["validation_summary"].exists() else None,
            "script_validation_marker": str(paths["script_validation_summary"].relative_to(ROOT)) if paths["script_validation_summary"].exists() else None,
            "validation_ready": validation_ready,
            "dashboard_date": args.date,
            "yesterday_validation_target_date": yesterday_target,
            "validation_source_hash": current_validation_hash,
            "previous_validation_source_hash": previous_hash,
            "previous_validation_source_hash_path": previous_hash_path,
            "source_hash_changed": source_hash_changed,
            "history_recovery_ready": history_ready,
            "api_enabled": bool(validation.get("api_enabled")),
            "api_disabled_reason": validation.get("api_disabled_reason"),
            "brief_used_for_hit_rate": validation.get("brief_used_for_hit_rate"),
            "date_filter_field": validation.get("date_filter_field"),
            "allowed_updates": ["yesterday_validation", "cumulative_validation", "validation_summary", "validation_audit"],
            "forbidden_updates": ["today_candidate_source", "brief_source", "candidate_raw_numbers", "v4_strategy"],
            "validation_touched": validation_touched,
            "candidate_touched": candidate_touched,
            "last_good_preserved_on_not_ready": True,
            "final_pass": bool(args.final_pass),
            "scan_ran": False,
            "validation_reran": False,
            "refresh_status": final_refresh_status or status,
        }

    common = {
        "schema_version": "v3v4_dashboard_daily_update_gate.v2",
        "phase": "V3V4-DASHBOARD-DYNAMIC-DATE-MARKER-AND-MATCHDATE-TZ-HOTFIX",
        "generated_at": datetime.now(TZ).isoformat(),
        "date": args.date,
        "update_phase": args.phase,
        "mode": args.mode,
        "planned_time": phase_cfg.get("time") if args.final_pass else phase_cfg.get("planned_time"),
        "plan_path": str(plan_file.relative_to(ROOT)) if plan_file and plan_file.exists() else None,
        "marker_resolution": {k: (str(v.relative_to(ROOT)) if isinstance(v, Path) else v) for k, v in paths.items()} | marker_resolution,
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
        "team_cn_enrich": team_cn_enrich,
        "source_hash": digest([paths["scan_perf"], paths["brief_resolution"], paths["candidate_view"], paths["validation_summary"], paths["script_validation_summary"]]),
        "last_good_path": str(LAST_GOOD.relative_to(ROOT)),
        "blockers": blockers,
        "warnings": warnings,
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
        args.mode == "apply"
        and not marker.get("blockers")
        and (
            args.phase == "after-scan"
            or (args.phase == "after-validation" and not (args.final_pass and marker.get("refresh_status") == "NOOP_AFTER_VALIDATION_RERUN"))
        )
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
