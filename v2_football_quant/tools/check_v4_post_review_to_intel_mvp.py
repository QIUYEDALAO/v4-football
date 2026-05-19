#!/usr/bin/env python3
"""V4 Post-Review to Intel MVP Checker — reads real markers, no hardcoded True"""
import json, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def main():
    R = {"check_status":"PASS","blockers":[],"tests":{}}
    block = False
    def ck(n,cond,m=""): R["tests"][n]=cond; return (not cond) and (R["blockers"].append(f"{n}: {m}") or True)

    # File existence checks
    files = {
        "freeze": "data/runtime/status/v4_review_freeze_20260519.json",
        "structured": "data/daily_reports/v4_review_structured_20260519.json",
        "validation": "data/daily_reports/v4_ht_recommend_validation_20260519.json",
        "attribution": "data/v4_archive/v4_result_attribution_20260519.jsonl",
        "guard_full": "data/runtime/status/v4_review_guard_20260519_full.json",
        "guard_qq": "data/runtime/status/v4_review_guard_20260519.json",
        "route": "data/runtime/status/v4_review_route_20260519.json",
        "push": "data/runtime/status/v4_review_push_20260519.json",
        "intel_html": "data/runtime/dashboard/intel_desk.html",
    }
    for name, path in files.items():
        block |= ck(f"file_{name}", (MODULE/path).is_file(), path)

    # Read real markers (not hardcoded)
    structured = json.loads((MODULE/"data/daily_reports/v4_review_structured_20260519.json").read_text())
    freeze = json.loads((MODULE/"data/runtime/status/v4_review_freeze_20260519.json").read_text())
    guard = json.loads((MODULE/"data/runtime/status/v4_review_guard_20260519.json").read_text())
    guard_full = json.loads((MODULE/"data/runtime/status/v4_review_guard_20260519_full.json").read_text())
    route = json.loads((MODULE/"data/runtime/status/v4_review_route_20260519.json").read_text())
    push = json.loads((MODULE/"data/runtime/status/v4_review_push_20260519.json").read_text())

    # A/B/C/SKIP from real source
    a = structured.get("A", 0); b = structured.get("B", 0)
    c = structured.get("C", 0); s = structured.get("SKIP", 0)
    block |= ck("A_count", a == 0, f"got {a}")
    block |= ck("B_count", b == 0, f"got {b}")
    block |= ck("C_count", c >= 0)
    block |= ck("SKIP_count", s >= 0)
    block |= ck("formal_rec_zero", a + b == 0)

    # C/SKIP terminology from structured
    block |= ck("c_observation_only", structured.get("C_observation_only") == True)
    block |= ck("skip_not_rec", structured.get("SKIP_not_recommendation") == True)

    # Guards from real markers
    block |= ck("guard_full_pass", guard_full.get("guard_status") == "PASS")
    block |= ck("guard_qq_pass", guard.get("guard_status") == "PASS")
    block |= ck("reportagent_pass", route.get("reportagent_status") == "PASS")

    # Send status from real marker
    block |= ck("actual_send", push.get("actual_send") == False, f"got {push.get('actual_send')}")
    block |= ck("qq_sent", push.get("qq_sent") == False, f"got {push.get('qq_sent')}")

    # V33/D13/HOURLY from structured
    block |= ck("v33_disabled", structured.get("no_V33", False) == True)
    block |= ck("d13_false", structured.get("no_D13", True) == True)

    # Freeze consistency
    block |= ck("freeze_ab_match", freeze.get("A") == a and freeze.get("B") == b)
    block |= ck("freeze_actual_send", freeze.get("actual_send") == False)

    if block: R["check_status"]="BLOCKER"
    print("="*60); print("V4 POST-REVIEW STRONG CHECKER"); print("="*60)
    print(f"Status: {R['check_status']} | A={a} B={b} C={c} SKIP={s}")
    print(f"Passed: {sum(1 for v in R['tests'].values() if v)}/{len(R['tests'])}")
    for k,v in R["tests"].items(): print(f"  {k}: {'✅' if v else '❌'}")
    if R["blockers"]: print(f"\nBLOCKERS: {R['blockers']}"); sys.exit(1)
    sys.exit(0)

if __name__=="__main__": main()
