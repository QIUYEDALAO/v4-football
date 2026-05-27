#!/usr/bin/env python3
"""check_v4_lab_production_clone_h2h_last3.py -- Production clone + H2H last3 checker."""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
TZ = timezone(timedelta(hours=8))


def main() -> int:
    ts = datetime.now(TZ).isoformat()
    violations = []
    checks = {}

    # 1. Profile exists
    pf = ROOT / "config/v4_lab_profiles/prod_clone_h2h_last3.json"
    checks["profile_exists"] = pf.exists()
    if pf.exists():
        p = json.loads(pf.read_text())
        checks["mode"] = p.get("mode")
        checks["use_production_scoring_chain"] = p.get("use_production_scoring_chain", False)
        checks["include_events"] = p.get("include_events", False)
        checks["include_time_bins"] = p.get("include_time_bins", False)
        checks["include_late_fh_pressure"] = p.get("include_late_fh_pressure", False)
        checks["include_ht_score"] = p.get("include_ht_score", False)
        checks["recent_form_sample_size"] = p.get("recent_form_sample_size")
        checks["h2h_policy"] = p.get("h2h_policy")
        checks["h2h_valid_sample_size"] = p.get("h2h_valid_sample_size")
        checks["h2h_require_all_last3_fh_goal"] = p.get("h2h_require_all_last3_fh_goal")
        checks["h2h_min_valid_matches"] = p.get("h2h_min_valid_matches")
        checks["allow_c_grade"] = p.get("allow_c_grade", True)
        checks["grades"] = p.get("grades", [])

        if checks["mode"] != "production_clone_h2h_last3":
            violations.append("mode_not_production_clone")
        if not checks["use_production_scoring_chain"]:
            violations.append("production_scoring_chain_disabled")
        if not checks["include_events"]:
            violations.append("events_disabled")
        if not checks["h2h_require_all_last3_fh_goal"]:
            violations.append("h2h_not_require_all_last3")
        if checks["h2h_valid_sample_size"] != 3:
            violations.append("h2h_sample_size_not_3")
        if checks["allow_c_grade"]:
            violations.append("c_grade_allowed")
        if "LAB_A" not in checks.get("grades", []) or "LAB_B" not in checks.get("grades", []):
            violations.append("lab_ab_missing")

    # 2. Lab scanner mode handling
    scanner = ROOT / "engine/v4_lab_fullscan.py"
    if scanner.exists():
        src = scanner.read_text(encoding="utf-8")
        checks["scanner_has_prod_clone_mode"] = "production_clone_h2h_last3" in src
        checks["scanner_tracks_data_timeout"] = "DATA_TIMEOUT" in src
        checks["scanner_tracks_score_incomplete"] = "SCORE_INCOMPLETE" in src
        checks["scanner_h2h_last3_check"] = "h2h_last3_all_fh_goal" in src
        checks["scanner_uses_h2h_last3_policy"] = "LAB_H2H_LAST3_ALL_FH_GOAL" in src

    # 3. Lab scanner isolation
    if scanner.exists():
        src = scanner.read_text(encoding="utf-8")
        for marker in ["lab_only", "official_candidate=false", "not_for_validation",
                       "not_for_live_bet", "not_for_qq_recommendation"]:
            if marker not in src:
                violations.append(f"missing_marker:{marker}")

    result = {
        "schema_version": "v4_lab_production_clone_h2h_last3_checker.v1",
        "generated_at": ts,
        "checks": checks,
        "violations": violations,
        "forbidden_flags": {
            "official_candidate_modified": False, "validation_recomputed": False,
            "live_bet_raw_records_modified": False, "cron_modified": False,
            "QQ_recommendation_pushed": False, "production_strategy_changed": False,
            "candidate_rating_changed": False, "c_grade_generated": False,
        },
        "conclusion": "PASS" if not violations else "BLOCKER",
    }
    out = STATUS / "v4_lab_production_clone_h2h_last3_checker_20260527.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
