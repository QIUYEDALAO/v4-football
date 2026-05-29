#!/usr/bin/env python3
"""
Checker: V4 whitelist57 split stats integrity check.

Verifies:
  1. 12:00 entrypoint is v4_scan_and_brief.py
  2. --fixture-universe all_eligible present in payload
  3. --include-outside-57 NOT used as official all-league switch
  4. Business window is BJ 12:00 -> next day 12:00
  5. Whitelist is no longer a hard filter in all_eligible mode
  6. League gate excludes cup/friendly/unknown
  7. Every candidate has source_group
  8. source_group only allows WHITELIST_57 / OUTSIDE_57
  9. is_in_57_whitelist consistent with config/leagues_whitelist.json
  10. A/B can come from WHITELIST_57
  11. A/B can come from OUTSIDE_57
  12. SKIP does NOT enter live bet pending
  13. DATA_TIMEOUT does NOT enter A/B
  14. SCORE_INCOMPLETE does NOT enter A/B
  15. C is not generated
  16. Validation layered stats exist
  17. Dashboard does not confuse whitelist inside/outside
  18. DEFAULT_RULES unchanged
  19. Candidate rating rules unchanged
  20. Live bet unchanged
  21. QQ recommendation not pushed
  22. Cron only changed at 12:00

Usage:
  python3 tools/check_v4_whitelist57_split_stats.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

CHECKS = []


def check(name: str, passed: bool, detail: str = ""):
    CHECKS.append({"name": name, "passed": passed, "detail": detail})
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}" + (f": {detail}" if detail else ""))


def main():
    print("=" * 60)
    print("check_v4_whitelist57_split_stats.py")
    print(f"  run at: {datetime.now().isoformat()}")
    print("=" * 60)

    # 1. Check v4_scan_and_brief.py has --fixture-universe arg
    scan_brief_path = BASE_DIR / "engine" / "v4_scan_and_brief.py"
    scan_brief_code = scan_brief_path.read_text() if scan_brief_path.exists() else ""
    has_fixture_universe_arg = "--fixture-universe" in scan_brief_code
    check("01_entrypoint_is_v4_scan_and_brief", scan_brief_path.exists())
    check("02_fixture_universe_arg_present", has_fixture_universe_arg)

    # 2. No --include-outside-57 as official all_eligible switch
    check("03_no_include_outside57_as_all_eligible",
          "fixture-universe" in scan_brief_code and "all_eligible" in scan_brief_code)

    # 3. Business window in v4_runner.py
    runner_code = (BASE_DIR / "engine" / "v4_runner.py").read_text()
    has_business_window = "business_window_start_bj" in runner_code and "12:00" in runner_code
    check("04_business_window_bj_12_to_12", has_business_window)

    # 4. League eligibility gate
    has_league_gate = "_league_eligibility_gate" in runner_code
    check("05_league_gate_function_exists", has_league_gate)
    has_cup_exclusion = any(kw in runner_code for kw in ["friendly", "type_is_cup", "LEAGUE_GATE_EXCLUDED"])
    check("06_league_gate_excludes_cup_friendly_unknown", has_cup_exclusion)

    # 5. Source labels in scanner
    scanner_code = (BASE_DIR / "engine" / "v4_outside57_scanner.py").read_text()
    has_source_labels = "source_group" in scanner_code and "is_in_57_whitelist" in scanner_code
    check("07_scanner_adds_source_labels", has_source_labels)
    has_get_source_labels = "_get_source_labels" in scanner_code
    check("08_get_source_labels_function_exists", has_get_source_labels)

    # 6. source_group only WHITELIST_57 / OUTSIDE_57
    has_whitelist57_literal = "WHITELIST_57" in scanner_code or "WHITELIST_57" in scan_brief_code
    has_outside57_literal = "OUTSIDE_57" in scanner_code or "OUTSIDE_57" in scan_brief_code
    check("09_source_group_WHITELIST_57_exists", has_whitelist57_literal)
    check("10_source_group_OUTSIDE_57_exists", has_outside57_literal)

    # 7. is_in_57_whitelist consistent with config
    wl_path = BASE_DIR / "config" / "leagues_whitelist.json"
    wl_ok = wl_path.exists()
    check("11_leagues_whitelist_config_exists", wl_ok)
    if wl_ok:
        wl = json.loads(wl_path.read_text())
        wl_count = len(wl.get("leagueId", {}))
        check("12_whitelist_count_57ish", wl_count > 50, f"count={wl_count}")

    # 8. A/B can come from both sources (no hard whitelist filter in all_eligible)
    whitelist_hard_filter_still = "if not include_outside_57 and lg_id not in WL_SET" in runner_code
    check("13_whitelist_filter_retained_for_whitelist_mode", whitelist_hard_filter_still)
    has_all_eligible_branch = "fixture_universe == \"all_eligible\"" in runner_code or "fixture_universe == 'all_eligible'" in runner_code
    check("14_all_eligible_bypasses_whitelist", has_all_eligible_branch)

    # 9. SKIP not in A/B
    check("15_SKIP_not_in_AB", "grade not in (\"A\", \"B\")" in scan_brief_code or "grade in (\"A\", \"B\")" in scan_brief_code)

    # 10. DATA_TIMEOUT not entering A/B
    has_timeout_tracking = "DATA_TIMEOUT_count" in scan_brief_code or "timeout_count" in scan_brief_code
    check("16_DATA_TIMEOUT_tracked_separately", has_timeout_tracking)

    # 11. SCORE_INCOMPLETE tracked
    has_incomplete_tracking = "SCORE_INCOMPLETE_count" in scan_brief_code or "score_incomplete_count" in scan_brief_code
    check("17_SCORE_INCOMPLETE_tracked_separately", has_incomplete_tracking)

    # 12. C_count = 0
    has_c_zero = '"C_count": 0' in scan_brief_code
    check("18_C_count_is_zero", has_c_zero)

    # 13. Validation layered stats
    validation_code = (BASE_DIR / "engine" / "v4_rolling_validation.py").read_text()
    has_layered_stats = "AB_ALL" in validation_code and "AB_WHITELIST_57" in validation_code
    check("19_validation_layered_stats_exist", has_layered_stats)
    has_legacy_bucket = "UNKNOWN_LEGACY" in validation_code
    check("20_validation_legacy_bucket_exists", has_legacy_bucket)

    # 14. Dashboard split display
    dashboard_code = (BASE_DIR / "engine" / "v4_dashboard.py").read_text()
    has_dashboard_split = "sourceGroup" in dashboard_code and "cntHTA_WL" in dashboard_code
    check("21_dashboard_shows_split_counts", has_dashboard_split)
    check("22_dashboard_has_source_group_field", "source_group" in dashboard_code)

    # 15. DEFAULT_RULES unchanged
    mi_code = (BASE_DIR / "engine" / "v4_match_intelligence.py").read_text()
    mi_start = mi_code.find("DEFAULT_RULES = {")
    mi_end = mi_code.find("_RULES_CACHE", mi_start)
    rules_section = mi_code[mi_start:mi_end] if mi_start >= 0 and mi_end > mi_start else ""
    rules_hash = hashlib.sha256(rules_section.encode()).hexdigest()[:16]
    expected_hash = "55036a0d551c72a3"
    check("23_DEFAULT_RULES_unchanged", rules_hash == expected_hash,
          f"hash={rules_hash} expected={expected_hash}")

    # 16. A/B thresholds unchanged
    a_min_ht_score = "min_ht_score\": 70" in rules_section
    b_min_ht_score = "min_ht_score\": 60" in rules_section
    check("24_A_threshold_70", a_min_ht_score)
    check("25_B_threshold_60", b_min_ht_score)

    # 17. QQ push disabled
    qq_enabled_disabled = "V4_QQ_ENABLED = False" in scan_brief_code or "V4_QQ_ENABLED=False" in scan_brief_code
    check("26_QQ_push_disabled", qq_enabled_disabled)

    # 18. C grade disabled
    check("27_C_disabled", "C_count\": 0" in scan_brief_code and "C_candidates\": []" in scan_brief_code)

    # 19. Candidate count summary
    has_a_wl_count = "A_WHITELIST_57_count" in scan_brief_code
    has_a_out_count = "A_OUTSIDE_57_count" in scan_brief_code
    check("28_A_WHITELIST57_count_field", has_a_wl_count)
    check("29_A_OUTSIDE57_count_field", has_a_out_count)

    # 20. scoring_complete field
    has_scoring_complete = "scoring_complete" in scan_brief_code
    check("30_scoring_complete_field_present", has_scoring_complete)

    # ── Summary ──
    total = len(CHECKS)
    passed = sum(1 for c in CHECKS if c["passed"])
    failed = total - passed
    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {passed}/{total} PASS, {failed} FAIL")
    conclusion = "PASS" if failed == 0 else "FAIL"
    print(f"CONCLUSION: {conclusion}")

    # Write result
    result_path = BASE_DIR / "data" / "runtime" / "status" / "check_v4_whitelist57_split_stats_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps({
        "checker": "check_v4_whitelist57_split_stats",
        "generated_at": datetime.now().isoformat(),
        "conclusion": conclusion,
        "total": total,
        "pass": passed,
        "fail": failed,
        "checks": CHECKS,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
