#!/usr/bin/env python3
"""Phase D.7 — Preflight Self-Test (synthetic cases, no real data)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.v2_settlement_preflight_guard import evaluate_settlement_allowed

PASS, FAIL = 0, 0

def test(label, ds, wc, mc, st_override, expect_block, expect_reasons):
    global PASS, FAIL
    decision = evaluate_settlement_allowed("20260517", ds, wc, mc, st_override)
    allowed = decision["settlement_allowed"]
    blockers = decision["reason_codes"]
    ok = (allowed != expect_block) and all(r in blockers for r in expect_reasons)
    mark = "PASS" if ok else "FAIL"
    if ok: PASS += 1
    else: FAIL += 1
    print(f"[{mark}] {label}: allowed={allowed} blockers={blockers}")

# Case 1: zero official + missed candidates target
ds1 = {"marker_found": True, "official_bet_locked": 0, "missed_candidates": 2}
wc1 = {"marker_found": True, "new_locks_count": 0, "bet_locked_count": 0, "lock_owner_evidence_quality": "not_applicable"}
mc1 = {"audit_found": True, "count": 2, "candidate_keys": ["1506982|Jeju|Anyang", "1506983|Jeonbuk|Gimcheon"]}
st1 = {"settlement_targets": 2, "target_keys": ["1506982|Jeju|Anyang", "1506983|Jeonbuk|Gimcheon"],
       "missed_in_targets": 2, "lock_owner_present": False, "all_window_checker": False}
test("Case1: zero official + missed in targets", ds1, wc1, mc1, st1, True,
     ["OFFICIAL_BET_LOCKED_ZERO", "WINDOW_CHECKER_NEW_LOCKS_ZERO", "MISSED_CANDIDATES_PRESENT"])

# Case 2: official_bet_locked=2 + lock_owner=window_checker + no missed
ds2 = {"marker_found": True, "official_bet_locked": 2, "missed_candidates": 0}
wc2 = {"marker_found": True, "new_locks_count": 2, "bet_locked_count": 2, "lock_owner_evidence_quality": "strong"}
mc2 = {"audit_found": True, "count": 0, "candidate_keys": []}
st2 = {"settlement_targets": 2, "target_keys": ["100|TeamA|B"], "missed_in_targets": 0,
       "lock_owner_present": True, "all_window_checker": True}
test("Case2: valid official locks", ds2, wc2, mc2, st2, False, [])

# Case 3: has official but lock_owner missing
ds3 = {"marker_found": True, "official_bet_locked": 1, "missed_candidates": 0}
wc3 = {"marker_found": True, "new_locks_count": 1, "bet_locked_count": 1, "lock_owner_evidence_quality": "partial"}
mc3 = {"audit_found": True, "count": 0, "candidate_keys": []}
st3 = {"settlement_targets": 1, "target_keys": ["200|C|D"], "missed_in_targets": 0,
       "lock_owner_present": False, "all_window_checker": False}
test("Case3: missing lock_owner", ds3, wc3, mc3, st3, True, ["LOCK_OWNER_MISSING"])

# Case 4: target in missed_candidates
ds4 = {"marker_found": True, "official_bet_locked": 1, "missed_candidates": 1}
wc4 = {"marker_found": True, "new_locks_count": 1, "bet_locked_count": 1, "lock_owner_evidence_quality": "strong"}
mc4 = {"audit_found": True, "count": 1, "candidate_keys": ["9999|Bad|Guy"]}
st4 = {"settlement_targets": 1, "target_keys": ["9999|Bad|Guy"], "missed_in_targets": 1,
       "lock_owner_present": True, "all_window_checker": True}
test("Case4: target in missed", ds4, wc4, mc4, st4, True, ["MISSED_CANDIDATES_PRESENT"])

# Case 5: count mismatch — 2 official/2 window locks but only 1 target
st5 = {"settlement_targets": 1, "target_keys": ["100|A|B"], "missed_in_targets": 0,
       "lock_owner_present": True, "all_window_checker": True}
test("Case5: targets < official/window locks", ds2, wc2, mc2, st5, True, ["SETTLEMENT_TARGETS_OFFICIAL_LOCKS_MISMATCH", "SETTLEMENT_TARGETS_WINDOW_LOCKS_MISMATCH"])

# Case 6: count mismatch — 1 official/2 window locks but 2 targets
st6 = {"settlement_targets": 2, "target_keys": ["100|A|B", "200|C|D"], "missed_in_targets": 0,
       "lock_owner_present": True, "all_window_checker": True}
test("Case6: targets > official locks", ds3, wc2, mc3, st6, True, ["SETTLEMENT_TARGETS_OFFICIAL_LOCKS_MISMATCH"])

print(f"\nResults: {PASS} PASS / {FAIL} FAIL")
if FAIL > 0: raise SystemExit(1)
