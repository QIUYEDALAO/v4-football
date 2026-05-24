#!/usr/bin/env python3
"""14:00 final validation rerun + dashboard validation refresh runner.

This is not a scan runner. It performs a second postmatch validation dry-run/apply
through existing match_date validation rebuilders, then refreshes only the
validation/dashboard layer when the validation source hash changed. It never
runs capture, QQ push, cloud publish, cron creation, candidate mutation, or V4
strategy logic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))
RESULT_REBUILD = ROOT / "tools/rebuild_v3v4_validation_summary_from_match_date_history.py"
SCRIPT_REBUILD = ROOT / "tools/rebuild_v4_script_validation_from_match_date.py"
DASHBOARD_RUNNER = ROOT / "tools/run_v3v4_dashboard_daily_update.py"
LAST_GOOD = STATUS / "v3v4_intel_ops_console_daily_refresh_last_good.json"


def now() -> str:
    return datetime.now(TZ).isoformat()


def load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def sha(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validation_hash(date: str) -> str | None:
    summary = STATUS / f"v3v4_validation_summary_{date}.json"
    data = load(summary)
    if data.get("source_hash"):
        return str(data.get("source_hash"))
    return sha(summary)


def previous_validation_hash(date: str) -> tuple[str | None, str | None]:
    preferred = [
        STATUS / f"v3v4_dashboard_daily_update_after_validation_apply_{date}.json",
        STATUS / f"v3v4_dashboard_daily_update_after_validation_dry_run_{date}.json",
    ]
    candidates = [p for p in preferred if p.exists()]
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


def run_step(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, timeout=120)
    parsed: dict[str, Any] = {}
    try:
        raw = json.loads(proc.stdout)
        if isinstance(raw, dict):
            parsed = raw
    except Exception:
        parsed = {}
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
        "parsed": parsed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], required=True)
    parser.add_argument("--no-capture", action="store_true", required=True)
    parser.add_argument("--no-push", action="store_true", required=True)
    parser.add_argument("--no-cloud", action="store_true", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    blockers: list[str] = []
    warnings: list[str] = []
    prev_hash, prev_hash_path = previous_validation_hash(args.date)

    result_validation = run_step([sys.executable, str(RESULT_REBUILD), "--date", args.date, "--mode", args.mode, "--no-api", "--strict"])
    script_validation = run_step([sys.executable, str(SCRIPT_REBUILD), "--date", args.date, "--mode", args.mode, "--no-api", "--strict"])
    if result_validation["returncode"] != 0:
        blockers.append(f"result_validation_rerun_rc_{result_validation['returncode']}")
    if script_validation["returncode"] != 0:
        blockers.append(f"script_validation_rerun_rc_{script_validation['returncode']}")

    parsed_summary = result_validation.get("parsed", {}).get("summary", {})
    current_hash = str(parsed_summary.get("source_hash")) if parsed_summary.get("source_hash") else validation_hash(args.date)
    source_hash_changed = prev_hash is not None and current_hash is not None and prev_hash != current_hash
    validation_ready = current_hash is not None and not blockers

    dashboard_validation_refreshed = False
    dashboard_result: dict[str, Any] | None = None
    if not validation_ready:
        refresh_status = "VALIDATION_NOT_READY_FINAL"
    elif prev_hash is None:
        warnings.append("previous_validation_source_hash_missing; preserving last_good")
        refresh_status = "VALIDATION_HASH_MISSING"
    elif source_hash_changed:
        refresh_status = "UPDATED_AFTER_FINAL_VALIDATION"
        if args.mode == "apply":
            dashboard_result = run_step([
                sys.executable, str(DASHBOARD_RUNNER), "--date", args.date, "--phase", "after-validation",
                "--mode", "apply", "--no-api", "--no-capture", "--no-push", "--no-cloud", "--strict",
            ])
            if dashboard_result["returncode"] != 0:
                blockers.append(f"dashboard_validation_refresh_rc_{dashboard_result['returncode']}")
            else:
                dashboard_validation_refreshed = True
    else:
        refresh_status = "NOOP_AFTER_VALIDATION_RERUN"

    disk_summary = load(STATUS / f"v3v4_validation_summary_{args.date}.json")
    summary = parsed_summary if isinstance(parsed_summary, dict) and parsed_summary else disk_summary
    marker = {
        "schema_version": "v3v4_validation_final_and_dashboard_refresh.v2",
        "phase": "VALIDATION_FINAL_AND_DASHBOARD_REFRESH",
        "generated_at": now(),
        "date": args.date,
        "dashboard_date": args.date,
        "yesterday_validation_target_date": (datetime.strptime(args.date, "%Y%m%d").date() - timedelta(days=1)).strftime("%Y%m%d"),
        "mode": args.mode,
        "final_validation_ran": True,
        "final_validation_mode": "local_match_date_no_api_dry_run" if args.mode == "dry-run" else "local_match_date_no_api_apply",
        "api_called": False,
        "api_route_audit_only": True,
        "scan_ran": False,
        "candidate_touched": False,
        "marker_resolution": {
            "validation_summary": f"data/runtime/status/v3v4_validation_summary_{args.date}.json",
            "script_validation_summary": f"data/runtime/status/v4_script_validation_summary_{args.date}.json",
            "previous_after_validation_candidates": [
                f"data/runtime/status/v3v4_dashboard_daily_update_after_validation_apply_{args.date}.json",
                f"data/runtime/status/v3v4_dashboard_daily_update_after_validation_dry_run_{args.date}.json",
            ],
        },
        "validation_source_hash": current_hash,
        "previous_validation_source_hash": prev_hash,
        "previous_validation_source_hash_path": prev_hash_path,
        "source_hash_changed": source_hash_changed,
        "dashboard_validation_refreshed": dashboard_validation_refreshed,
        "refresh_status": refresh_status,
        "validation_ready": validation_ready,
        "last_good_preserved": refresh_status in {"NOOP_AFTER_VALIDATION_RERUN", "VALIDATION_NOT_READY_FINAL", "VALIDATION_HASH_MISSING"},
        "date_filter_field": summary.get("date_filter_field"),
        "match_date_used": summary.get("date_filter_field") == "match_date",
        "scan_date_used_for_validation": False,
        "brief_used_for_hit_rate": bool(summary.get("brief_used_for_hit_rate")),
        "brief_used_for_script_validation": bool((summary.get("script_validation") or {}).get("brief_used_for_script_validation")),
        "script_unknown_excluded_from_denominator": bool((summary.get("script_validation") or {}).get("unknown_excluded_from_denominator", True)),
        "capture_ran": False,
        "QQ_push": False,
        "push_enabled": False,
        "cloud_publish": False,
        "cron_enabled": False,
        "autosync_cron_created": False,
        "full_scan_ran": False,
        "v2_restored": False,
        "v33_active": False,
        "c_active_in_dashboard": False,
        "c_validation_visible": False,
        "c_script_validation_visible": False,
        "last_7d_visible": False,
        "strategy_changed": False,
        "v4_candidate_numbers_changed": False,
        "result_validation_changed": False,
        "script_validation_changed": False,
        "attribution_numbers_changed": False,
        "secrets_printed": False,
        "last_good_path": str(LAST_GOOD.relative_to(ROOT)),
        "result_validation_step": result_validation,
        "script_validation_step": script_validation,
        "dashboard_refresh_step": dashboard_result,
        "blockers": blockers,
        "warnings": warnings,
        "check_status": "BLOCKER" if blockers else ("WARN_ONLY" if warnings or args.mode == "dry-run" else "PASS"),
    }
    out = STATUS / f"v3v4_validation_final_and_dashboard_refresh_{args.date}.json"
    out.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(marker, ensure_ascii=False, indent=2))
    if args.strict and blockers:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
