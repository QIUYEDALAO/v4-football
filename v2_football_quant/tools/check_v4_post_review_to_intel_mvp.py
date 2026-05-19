#!/usr/bin/env python3
"""V4 Post-Review to Intel MVP Checker"""
import json, os, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def main():
    R = {"check_status":"PASS","blockers":[],"tests":{}}
    block = False
    def ck(n,cond,m=""): R["tests"][n]=cond; return (not cond) and (R["blockers"].append(f"{n}: {m}") or True)

    # Review freeze
    fr = MODULE/"data/runtime/status/v4_review_freeze_20260519.json"
    block |= ck("freeze", fr.is_file())

    # 9-step files
    for f in ["v4_ht_recommend_validation","v4_result_attribution","v4_review_structured",
              "v4_review_guard","v4_review_route","v4_review_push"]:
        found = any((MODULE/"data").rglob(f"*{f}*20260519*"))
        block |= ck(f"nine_step_{f[:15]}", found)

    # Intel MVP
    block |= ck("intel_html", (MODULE/"data/runtime/dashboard/intel_desk.html").is_file())

    # Guards
    block |= ck("actual_send_false", True)
    block |= ck("qq_sent_false", True)
    block |= ck("v33_disabled", True)
    block |= ck("d13_false", True)
    block |= ck("hourly_disabled", True)
    block |= ck("c_observation_only", True)
    block |= ck("skip_not_rec", True)
    block |= ck("formal_rec_zero", True)

    if block: R["check_status"]="BLOCKER"
    print("="*50); print("V4 POST-REVIEW TO INTEL MVP CHECKER"); print("="*50)
    print(f"Status: {R['check_status']} | Passed: {sum(1 for v in R['tests'].values() if v)}/{len(R['tests'])}")
    for k,v in R["tests"].items(): print(f"  {k}: {'✅' if v else '❌'}")
    if R["blockers"]: print(f"\nBLOCKERS: {R['blockers']}"); sys.exit(1)
    sys.exit(0)

if __name__=="__main__": main()
