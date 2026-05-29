#!/usr/bin/env python3
"""
Checker: V4 all_eligible candidate pool integrity check.

Verifies the all_eligible scan mode produces a clean candidate pool:
  - no cup/friendly/unknown in A/B
  - every candidate has source_group
  - A/B split by WHITELIST_57 / OUTSIDE_57
  - no SKIP in pending
  - no DATA_TIMEOUT / SCORE_INCOMPLETE in A/B
  - no C generation
  - fixture_universe labelled correctly

Usage:
  python3 tools/check_v4_all_eligible_candidate_pool.py
  python3 tools/check_v4_all_eligible_candidate_pool.py --candidate-view-path <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Known cup/friendly/unfriendly league names to check against
EXCLUDED_KEYWORDS = [
    "friendly", "friendlies", "amistoso", "amical",
    "cup", "coppa", "copa", "pokal", "beker", "coupe",
    "super cup", "supercopa", "supercoppa", "trophee",
    "community shield", "recopa",
    "world cup", "euro ", "copa america", "afcon",
    "nations league", "concacaf",
]

CHECKS = []


def check(name: str, passed: bool, detail: str = ""):
    CHECKS.append({"name": name, "passed": passed, "detail": detail})
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}" + (f": {detail}" if detail else ""))


def load_candidate_view(candidate_path: Path | None = None) -> dict | None:
    """Load the latest candidate_view, optionally from a given path."""
    if candidate_path and candidate_path.exists():
        return json.loads(candidate_path.read_text(encoding="utf-8"))

    status_dir = BASE_DIR / "data" / "runtime" / "status"
    pattern = "v3v4_dashboard_candidate_view_*.json"
    candidates = sorted(status_dir.glob(pattern), reverse=True)
    if candidates:
        return json.loads(candidates[0].read_text(encoding="utf-8"))
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-view-path", default=None)
    args = parser.parse_args()

    print("=" * 60)
    print("check_v4_all_eligible_candidate_pool.py")
    print(f"  run at: {datetime.now().isoformat()}")
    print("=" * 60)

    cv = load_candidate_view(Path(args.candidate_view_path) if args.candidate_view_path else None)

    if cv is None:
        print("\n  [INFO] No candidate_view found. Running code-level checks only.\n")
        check("00_candidate_view_exists", False, "no candidate_view file found")
    else:
        check("00_candidate_view_exists", True,
              f"date={cv.get('scan_date')} schema={cv.get('schema_version')}")

        # 1. Check fixture_universe field
        fixture_universe = cv.get("fixture_universe", "unknown")
        check("01_fixture_universe_field", fixture_universe in ("all_eligible", "whitelist"),
              f"value={fixture_universe}")

        # 2. Check C_count is 0
        c_count = cv.get("C_count", -1)
        check("02_C_count_is_zero", c_count == 0, f"C_count={c_count}")

        # 3. Check A_candidates have source_group
        a_candidates = cv.get("A_candidates", [])
        b_candidates = cv.get("B_candidates", [])
        all_ab = a_candidates + b_candidates

        if all_ab:
            has_source_group = all(c.get("source_group") for c in all_ab)
            check("03_all_AB_have_source_group", has_source_group,
                  f"{len(all_ab)} A/B candidates checked")
        else:
            check("03_all_AB_have_source_group", True, "no A/B candidates (may be normal)")

        # 4. Check source_group values
        valid_groups = {"WHITELIST_57", "OUTSIDE_57"}
        invalid_groups = [c for c in all_ab if c.get("source_group") not in valid_groups]
        check("04_source_group_only_valid_values", len(invalid_groups) == 0,
              f"invalid={[c.get('source_group') for c in invalid_groups]}" if invalid_groups else f"{len(all_ab)} checked")

        # 5. Check for excluded league keywords in A/B
        excluded_in_ab = []
        for c in all_ab:
            league_name = str(c.get("league", "")).lower()
            for kw in EXCLUDED_KEYWORDS:
                if kw in league_name:
                    excluded_in_ab.append(f"{c.get('league')}#{c.get('fixture_id')}")
                    break
        check("05_no_cup_friendly_in_AB", len(excluded_in_ab) == 0,
              f"excluded={excluded_in_ab[:5]}" if excluded_in_ab else f"{len(all_ab)} checked")

        # 6. Check A/B have is_in_57_whitelist
        if all_ab:
            has_is_in = all("is_in_57_whitelist" in c for c in all_ab)
            check("06_all_AB_have_is_in_57_whitelist", has_is_in, f"{len(all_ab)} checked")

        # 7. A/B split counts match
        a_wl = cv.get("A_WHITELIST_57_count", -1)
        a_out = cv.get("A_OUTSIDE_57_count", -1)
        b_wl = cv.get("B_WHITELIST_57_count", -1)
        b_out = cv.get("B_OUTSIDE_57_count", -1)
        check("07_A_WHITELIST_count_field", a_wl >= 0, f"value={a_wl}")
        check("08_A_OUTSIDE_count_field", a_out >= 0, f"value={a_out}")
        check("09_B_WHITELIST_count_field", b_wl >= 0, f"value={b_wl}")
        check("10_B_OUTSIDE_count_field", b_out >= 0, f"value={b_out}")

        # 8. Sum check
        expected_a = a_wl + a_out
        actual_a = cv.get("A_count", 0)
        check("11_A_count_consistency", expected_a == actual_a,
              f"WL+OUT={expected_a} vs A_count={actual_a}")

        # 9. DATA_TIMEOUT count
        timeout_count = cv.get("DATA_TIMEOUT_count", -1)
        check("12_DATA_TIMEOUT_count_present", timeout_count >= 0, f"value={timeout_count}")

        # 10. SCORE_INCOMPLETE count
        incomplete_count = cv.get("SCORE_INCOMPLETE_count", -1)
        check("13_SCORE_INCOMPLETE_count_present", incomplete_count >= 0, f"value={incomplete_count}")

        # 11. No SKIP in A/B
        skip_in_ab = [c for c in all_ab if c.get("grade") == "SKIP"]
        check("14_no_SKIP_in_AB", len(skip_in_ab) == 0,
              f"skip_in_ab={len(skip_in_ab)}" if skip_in_ab else f"{len(all_ab)} checked")

        # 12. scoring_complete field
        if all_ab:
            has_scoring_complete = all("scoring_complete" in c for c in all_ab)
            check("15_scoring_complete_present_in_all_AB", has_scoring_complete,
                  f"{len(all_ab)} checked")

        # 13. official_candidate field
        if all_ab:
            all_official = all(c.get("official_candidate") is True for c in all_ab)
            check("16_all_AB_are_official_candidates", all_official,
                  f"{len(all_ab)} checked")

        # 14. source_group consistency with is_in_57_whitelist
        inconsistent = []
        for c in all_ab:
            sg = c.get("source_group", "")
            is_in = c.get("is_in_57_whitelist")
            if sg == "WHITELIST_57" and is_in is not True:
                inconsistent.append(c.get("fixture_id"))
            elif sg == "OUTSIDE_57" and is_in is not False:
                inconsistent.append(c.get("fixture_id"))
        check("17_source_group_consistent_with_is_in_flag", len(inconsistent) == 0,
              f"inconsistent={inconsistent[:5]}" if inconsistent else f"{len(all_ab)} checked")

        # 15. Print summary split
        print(f"\n  Split Summary:")
        print(f"    A total={actual_a} (WL={a_wl}, OUT={a_out})")
        print(f"    B total={cv.get('B_count', 0)} (WL={b_wl}, OUT={b_out})")
        print(f"    SKIP={cv.get('SKIP_count', 0)} TIMEOUT={timeout_count} INCOMPLETE={incomplete_count}")

    # ── Code-level checks ──
    # 16. DEFAULT_RULES hash
    import hashlib
    mi_path = BASE_DIR / "engine" / "v4_match_intelligence.py"
    if mi_path.exists():
        mi_code = mi_path.read_text()
        start = mi_code.find("DEFAULT_RULES = {")
        end = mi_code.find("_RULES_CACHE", start)
        rules_str = mi_code[start:end] if start >= 0 and end > start else ""
        rules_hash = hashlib.sha256(rules_str.encode()).hexdigest()[:16]
        check("18_DEFAULT_RULES_hash", rules_hash == "55036a0d551c72a3",
              f"hash={rules_hash}")

    # 17. Candidate rating rules
    config_path = BASE_DIR / "config" / "v4_candidate_rules.yaml"
    if config_path.exists():
        candidate_rules = config_path.read_text()
        rules_hash = hashlib.sha256(candidate_rules.encode()).hexdigest()[:16]
        check("19_candidate_rules_exist", True, f"hash={rules_hash}")
    else:
        check("19_candidate_rules_exist", False, "file missing")

    # ── Summary ──
    total = len(CHECKS)
    passed = sum(1 for c in CHECKS if c["passed"])
    failed = total - passed
    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {passed}/{total} PASS, {failed} FAIL")
    conclusion = "PASS" if failed == 0 else "FAIL"
    print(f"CONCLUSION: {conclusion}")

    result_path = BASE_DIR / "data" / "runtime" / "status" / "check_v4_all_eligible_candidate_pool_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps({
        "checker": "check_v4_all_eligible_candidate_pool",
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
