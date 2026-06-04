#!/usr/bin/env python3
"""
V3 WC 2026 104 Cards Checker

Validates:
1. Total = 104 cards
2. Group stage = 72 (matches 1-72)
3. Knockout stage = 32 (matches 73-104)
4. match_id 1-104 all unique
5. No betting/prediction fields
6. Group stage correctly assigned to Groups A-L (6 each)
7. Knockout stage correctly classified (16+8+4+2+1+1)
8. All required fields present

Usage:
    python3 tools/check_v3_wc2026_104_cards.py

Returns:
    Exit code 0 = PASS
    Exit code 1 = FAIL (with details)
"""

import json
import os
import sys
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS_PATH = os.path.join(BASE, "data", "runtime", "wc2026", "fixtures", "v3_wc2026_104_cards.json")


def check():
    print("=" * 60)
    print("V3 WC2026 104 CARDS CHECKER")
    print("=" * 60)

    if not os.path.exists(CARDS_PATH):
        print(f"\n❌ FAIL: Cards file not found: {CARDS_PATH}")
        return False

    with open(CARDS_PATH) as f:
        data = json.load(f)

    matches = data.get("matches", [])
    total = len(matches)
    print(f"\nTotal cards found: {total}")

    # ── Check 1: Total = 104 ──
    if total != 104:
        print(f"  ❌ FAIL: Expected 104 cards, got {total}")
        return False
    print(f"  ✅ PASS: Total = 104")

    # ── Check 2: Match IDs 1-104 unique ──
    ids = [m["match_id"] for m in matches]
    id_set = set(ids)
    if len(ids) != len(id_set):
        from collections import Counter
        dupes = [mid for mid, cnt in Counter(ids).items() if cnt > 1]
        print(f"  ❌ FAIL: Duplicate match IDs: {dupes}")
        return False
    print(f"  ✅ PASS: All match IDs unique")

    expected_ids = set(range(1, 105))
    missing = expected_ids - id_set
    extra = id_set - expected_ids
    if missing:
        print(f"  ❌ FAIL: Missing match IDs: {sorted(missing)}")
        return False
    if extra:
        print(f"  ❌ FAIL: Extra match IDs: {sorted(extra)}")
        return False
    print(f"  ✅ PASS: Match IDs 1-104 complete")

    # ── Check 3: Group stage = 72 (ids 1-72) ──
    group_cards = [m for m in matches if 1 <= m["match_id"] <= 72]
    if len(group_cards) != 72:
        print(f"  ❌ FAIL: Group stage cards: {len(group_cards)} != 72")
        return False
    print(f"  ✅ PASS: Group stage = 72 (match_id 1-72)")

    # ── Check 4: Knockout stage = 32 (ids 73-104) ──
    ko_cards = [m for m in matches if 73 <= m["match_id"] <= 104]
    if len(ko_cards) != 32:
        print(f"  ❌ FAIL: Knockout stage cards: {len(ko_cards)} != 32")
        return False
    print(f"  ✅ PASS: Knockout stage = 32 (match_id 73-104)")

    # ── Check 5: No betting/prediction fields ──
    betting_fields = ["prediction", "rating", "score", "bet", "line",
                       "predicted_score", "confidence", "expected_goals"]
    for m in matches:
        for f in betting_fields:
            if f in m and m[f] is not None:
                print(f"  ❌ FAIL: Match #{m['match_id']} has betting field '{f}': {m[f]}")
                return False
    print(f"  ✅ PASS: No betting/prediction fields")

    # ── Check 6: Status = scheduled, result = null ──
    for m in matches:
        if m.get("status") != "scheduled":
            print(f"  ❌ FAIL: Match #{m['match_id']} status is '{m.get('status')}', expected 'scheduled'")
            return False
        if m.get("result") is not None:
            print(f"  ❌ FAIL: Match #{m['match_id']} has result: {m['result']}")
            return False
    print(f"  ✅ PASS: All cards: status=scheduled, result=null")

    # ── Check 7: Group stage assignment (Groups A-L, 6 each) ──
    expected_groups = {f"Group {c}" for c in "ABCDEFGHIJKL"}
    found_groups = {}
    for m in group_cards:
        g = m.get("stage")
        if not g or not g.startswith("Group "):
            print(f"  ❌ FAIL: Match #{m['match_id']} has non-group stage: {g}")
            return False
        found_groups[g] = found_groups.get(g, 0) + 1

    if set(found_groups.keys()) != expected_groups:
        extra_g = set(found_groups.keys()) - expected_groups
        missing_g = expected_groups - set(found_groups.keys())
        if extra_g:
            print(f"  ❌ FAIL: Extra groups: {sorted(extra_g)}")
        if missing_g:
            print(f"  ❌ FAIL: Missing groups: {sorted(missing_g)}")
        if extra_g or missing_g:
            return False

    for g, count in sorted(found_groups.items()):
        if count != 6:
            print(f"  ❌ FAIL: {g} has {count} matches, expected 6")
            return False
    print(f"  ✅ PASS: Groups A-L, each 6 matches ({len(found_groups)} groups)")

    # ── Check 8: Knockout stage breakdown ──
    expected_ko = {
        "round_of_32": 16,
        "round_of_16": 8,
        "quarter_final": 4,
        "semi_final": 2,
        "third_place": 1,
        "final": 1,
    }
    ko_stage_counts = {}
    for m in ko_cards:
        stage = m.get("stage")
        ko_stage_counts[stage] = ko_stage_counts.get(stage, 0) + 1

    for stage, expected_count in expected_ko.items():
        actual = ko_stage_counts.get(stage, 0)
        if actual != expected_count:
            print(f"  ❌ FAIL: {stage}: got {actual}, expected {expected_count}")
            return False
    print(f"  ✅ PASS: Knockout stage breakdown: 16+8+4+2+1+1 = 32")

    # ── Check 9: Group field correctness ──
    for m in group_cards:
        expected_group = m["stage"]
        actual_group = m.get("group")
        if actual_group != expected_group:
            print(f"  ❌ FAIL: Match #{m['match_id']}: group field '{actual_group}' != stage '{expected_group}'")
            return False
    print(f"  ✅ PASS: Group field matches stage for all group cards")

    # ── Check 10: KO group field = null ──
    for m in ko_cards:
        if m.get("group") is not None:
            print(f"  ❌ FAIL: KO Match #{m['match_id']} has group='{m['group']}', expected null")
            return False
    print(f"  ✅ PASS: All KO cards have group=null")

    # ── Check 11: All required fields present and non-null ──
    required_fields = ["match_id", "stage", "group", "match_number",
                       "home_team", "away_team", "venue", "date",
                       "kickoff", "status", "result"]
    for m in matches:
        for f in required_fields:
            if f not in m:
                print(f"  ❌ FAIL: Match #{m['match_id']} missing field '{f}'")
                return False
            if m[f] is None and f != "result" and f != "group":
                print(f"  ❌ FAIL: Match #{m['match_id']} field '{f}' is null")
                return False
    print(f"  ✅ PASS: All required fields present")

    # ── Check 12: No PARSE_REQUIRED values ──
    for m in matches:
        for f in ["venue", "date", "kickoff", "home_team", "away_team"]:
            val = str(m.get(f, ""))
            if "PARSE_REQUIRED" in val:
                print(f"  ❌ FAIL: Match #{m['match_id']} field '{f}' is PARSE_REQUIRED: {val}")
                return False
    print(f"  ✅ PASS: No PARSE_REQUIRED values")

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print(f"RESULT: ✅ ALL CHECKS PASSED")
    print(f"{'=' * 60}")
    print(f"\nCards: {total}/104")
    print(f"  Group stage: {len(group_cards)}")
    print(f"  KO stage: {len(ko_cards)}")
    print(f"  Venues: {len(set(m['venue'] for m in matches))} unique")
    print(f"  Group assignments: {len(found_groups)} groups, 6 matches each")

    # Show venue coverage
    venues = set(m["venue"] for m in matches)
    print(f"\n  Venues ({len(venues)}):")
    for v in sorted(venues):
        matches_at_venue = [m for m in matches if m["venue"] == v]
        print(f"    {v}: {len(matches_at_venue)} matches")

    return True


if __name__ == "__main__":
    result = check()
    sys.exit(0 if result else 1)
