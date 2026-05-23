#!/usr/bin/env python3
"""Check V3/V4-only Intel Ops Console daily refresh pipeline.

Read-only validation plus dry-run preview. It does not run capture, enable cron,
push messages, publish cloud, or modify strategy outputs.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS_DIR = ROOT / "data/runtime/status"
DOC_OLD = ROOT / "docs/V3V4_INTEL_OPS_CONSOLE_DAILY_AUTO_REFRESH_RUNBOOK_20260521.md"
DOC_NEW = ROOT / "docs/V3V4_INTEL_OPS_CONSOLE_DAILY_REFRESH_UI_RUNBOOK_20260523.md"
STATUS = STATUS_DIR / "v3v4_intel_ops_console_daily_auto_refresh_design_20260521.json"
RUNNER = ROOT / "tools/run_v3v4_intel_ops_console_daily_refresh.py"
TZ = timezone(timedelta(hours=8))
DATE = "20260523"


def load(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []
    design = load(STATUS)
    if not (DOC_OLD.exists() or DOC_NEW.exists()):
        blockers.append("runbook_missing")
    if not design:
        blockers.append("design_status_missing")
    if not RUNNER.exists():
        blockers.append("daily_refresh_runner_missing")
    for key in ["v2_validation_read", "v2_historical_pool_read", "v2_marker_read", "v2_dashboard_generated", "capture_ran", "qq_push", "cloud_publish", "cron_enabled"]:
        if design and design.get(key) is not False:
            blockers.append(f"{key}_not_false")
    sources = "\n".join(map(str, design.get("active_sources", []))).lower()
    if design and ("v3" not in sources or "v4" not in sources):
        blockers.append("active_sources_missing_v3_or_v4")
    dry = {}
    dry_rc = None
    if RUNNER.exists():
        r = subprocess.run([sys.executable, str(RUNNER), "--date", DATE, "--mode", "dry-run", "--source-window", "auto", "--no-capture", "--no-push", "--no-cloud", "--strict"], cwd=str(ROOT), text=True, capture_output=True, timeout=20)
        dry_rc = r.returncode
        try:
            dry = json.loads(r.stdout)
        except Exception:
            blockers.append("dry_run_output_not_json")
        if dry_rc != 0:
            blockers.append(f"dry_run_returncode:{dry_rc}")
    if dry:
        if dry.get("daily_refresh_v2_dependency") is not False:
            blockers.append("dry_run_daily_refresh_v2_dependency_not_false")
        for key in ["capture_ran", "QQ_push", "cloud_publish", "cron_enabled", "strategy_changed", "v4_candidate_numbers_changed"]:
            if dry.get(key) is not False:
                blockers.append(f"dry_run_{key}_not_false")
        if dry.get("has_lock_contract") is not True:
            blockers.append("dry_run_lock_contract_missing")
        if dry.get("has_last_good_contract") is not True:
            blockers.append("dry_run_last_good_contract_missing")
        if not dry.get("source_hash"):
            blockers.append("dry_run_source_hash_missing")
        if dry.get("source_date_mismatch") and dry.get("display_label", "").startswith("今日"):
            blockers.append("dry_run_old_source_labeled_today")
        if not dry.get("validation_source_files"):
            blockers.append("dry_run_validation_sources_missing")

        if dry.get("C_active") is not False:
            blockers.append("dry_run_C_active_not_false")
        if dry.get("last_7d_active") is not False:
            blockers.append("dry_run_last_7d_active_not_false")
        if dry.get("brief_used_for_hit_rate") is not False:
            blockers.append("dry_run_brief_used_for_hit_rate")
        if dry.get("c_excluded_from_ab") is not True:
            blockers.append("dry_run_c_excluded_from_ab_not_true")
    status = "BLOCKER" if blockers else ("WARN_ONLY" if warnings else "PASS")
    result = {
        "checker": "tools/check_v3v4_intel_ops_console_daily_refresh_pipeline.py",
        "phase": "V3V4-DASHBOARD-VALIDATION-TWO-COLUMN-SCRIPT-HIGHLIGHT-20260523",
        "generated_at": datetime.now(TZ).isoformat(),
        "conclusion": status,
        "daily_refresh_v2_dependency": False if dry else None,
        "daily_refresh_v3v4_only": bool(dry and dry.get("active_scope") == "V3_V4_ONLY"),
        "dry_run_returncode": dry_rc,
        "mode_supported": ["dry-run", "apply"] if RUNNER.exists() else [],
        "has_lock": bool(dry.get("has_lock_contract")),
        "has_last_good": bool(dry.get("has_last_good_contract")),
        "source_hash": dry.get("source_hash"),
        "source_date": dry.get("source_date"),
        "is_today_source": dry.get("is_today_source"),
        "source_date_mismatch": dry.get("source_date_mismatch"),
        "display_label": dry.get("display_label"),
        "validation_source_files": dry.get("validation_source_files", []),
        "C_active": dry.get("C_active") if dry else None,
        "last_7d_active": dry.get("last_7d_active") if dry else None,
        "brief_used_for_hit_rate": dry.get("brief_used_for_hit_rate") if dry else None,
        "c_excluded_from_ab": dry.get("c_excluded_from_ab") if dry else None,
        "cron_enabled": False,
        "capture_ran": False,
        "qq_push": False,
        "cloud_publish": False,
        "blockers": blockers,
        "warnings": warnings,
    }
    out = STATUS_DIR / f"check_v3v4_intel_ops_console_daily_refresh_pipeline_result_{DATE}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
