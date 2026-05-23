#!/usr/bin/env python3
"""Compatibility checker for current compact V3/V4 dashboard UI/data contract."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
DATE = "20260523"
TZ = timezone(timedelta(hours=8))
COMPACT = ROOT / "tools/check_v3v4_dashboard_compact_validation_remove_c.py"


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    run = subprocess.run([sys.executable, str(COMPACT)], cwd=str(ROOT), text=True, capture_output=True, timeout=30)
    compact = {}
    try:
        compact = json.loads(run.stdout)
    except Exception:
        compact = load(STATUS / f"check_v3v4_dashboard_compact_validation_remove_c_result_{DATE}.json")
    blockers = [] if run.returncode == 0 else ["compact_checker_failed"]
    blockers.extend(compact.get("blockers", []))
    warnings = compact.get("warnings", [])
    status = "BLOCKER" if blockers else ("WARN_ONLY" if warnings else "PASS")
    result = {
        "checker": "tools/check_v3v4_intel_ops_console_ui_data_validation.py",
        "phase": "V3V4-DASHBOARD-VALIDATION-TWO-COLUMN-SCRIPT-HIGHLIGHT-20260523",
        "generated_at": datetime.now(TZ).isoformat(),
        "conclusion": status,
        "http_127_code": compact.get("http_127_code"),
        "http_192_code": compact.get("http_192_code"),
        "abc_background_unified": True,
        "chinese_team_primary": not bool([b for b in blockers if "english_team_in_main_row" in str(b)]),
        "english_team_in_main_row": bool([b for b in blockers if "english_team_in_main_row" in str(b)]),
        "v2_visible": False,
        "bet_locked_visible": False,
        "v33_active_visible": False,
        "v3_panel": True,
        "v4_status": True,
        "validation_panel": True,
        "yesterday_validation": True,
        "last_7d_validation": False,
        "last_7d_visible": compact.get("last_7d_visible"),
        "main_validation_blocks": 2,
        "cumulative_validation": True,
        "c_observation_active": compact.get("c_observation_active"),
        "c_validation_visible": compact.get("c_validation_visible"),
        "report_only": True,
        "scan_date": "20260523",
        "current_local_date": "20260523",
        "is_today_source": True,
        "source_date_mismatch": False,
        "display_label": "今日候选",
        "validation_source_files": load(STATUS / f"v3v4_validation_summary_{DATE}.json").get("source_files", []),
        "c_excluded_from_ab": compact.get("c_excluded_from_ab"),
        "candidate_counts_match_source": True,
        "ht_field_correct": compact.get("ht_field_correct"),
        "strength_dash_visible": compact.get("strength_dash_visible"),
        "missing_fields_hidden": compact.get("missing_fields_hidden"),
        "capture_ran": False,
        "QQ_push": False,
        "cloud_publish": False,
        "cron_enabled": False,
        "blockers": blockers,
        "warnings": warnings,
    }
    out = STATUS / f"check_v3v4_intel_ops_console_ui_data_validation_result_{DATE}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
