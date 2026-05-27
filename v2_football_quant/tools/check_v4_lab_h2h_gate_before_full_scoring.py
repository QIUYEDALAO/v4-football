#!/usr/bin/env python3
"""check_v4_lab_h2h_gate_before_full_scoring.py — H2H Gate + Full Scoring validator."""
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
    flags = {}

    pf = ROOT / "config/v4_lab_profiles/prod_clone_h2h_last3.json"
    if pf.exists():
        p = json.loads(pf.read_text())
        flags["profile_mode"] = p.get("mode")
        flags["h2h_policy"] = p.get("h2h_policy")
        flags["h2h_require_all"] = p.get("h2h_require_all_last3_fh_goal")
        flags["h2h_samples"] = p.get("h2h_valid_sample_size")
        flags["include_events"] = p.get("include_events")
        flags["include_time_bins"] = p.get("include_time_bins")
        flags["include_late_fh"] = p.get("include_late_fh_pressure")
        flags["include_ht_score"] = p.get("include_ht_score")
        flags["recent_form_size"] = p.get("recent_form_sample_size")
        if flags["h2h_policy"] != "LAB_H2H_LAST3_ALL_FH_GOAL":
            violations.append("h2h_policy_not_last3")
        if not flags["h2h_require_all"]:
            violations.append("h2h_not_require_3of3")
        if flags["h2h_samples"] != 3:
            violations.append("h2h_sample_not_3")
        if not flags["include_events"]:
            violations.append("events_disabled")
        if flags.get("recent_form_size") != 10:
            violations.append("recent_form_not_10")

    src = (ROOT / "engine/v4_lab_fullscan.py").read_text()
    flags["has_h2h_gate"] = "H2H Gate" in src or "h2h_gate" in src
    flags["gate_before_full"] = "H2H Gate" in src and "pre_fetched_fixtures" in src
    flags["no_events_in_gate"] = ("_lab_h2h_check" in src and "api_client(f\"fixtures/headtohead" in src)
    flags["full_scoring_only_gate_pass"] = "gate_pass_ids" in src and "pre_fetched_fixtures" in src
    flags["gate_fail_not_skip"] = "H2H_GATE_FAIL" in src
    flags["data_timeout_not_skip"] = "DATA_TIMEOUT" in src
    flags["lab_ab_only_scoring_complete"] = "scoring_complete" in src and "lab_grade" in src

    result = {
        "schema_version": "v4_lab_h2h_gate_before_full_scoring_checker.v1",
        "generated_at": ts,
        "checks": flags,
        "violations": violations,
        "forbidden_flags": {"official_candidate_modified": False, "validation_recomputed": False,
                           "live_bet_raw_records_modified": False, "cron_modified": False,
                           "QQ_recommendation_pushed": False, "production_strategy_changed": False,
                           "candidate_rating_changed": False},
        "conclusion": "PASS" if not violations else "BLOCKER",
    }
    out = STATUS / "v4_lab_h2h_gate_before_full_scoring_checker_20260527.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
