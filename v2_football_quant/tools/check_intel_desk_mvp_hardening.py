#!/usr/bin/env python3
"""Intel Desk MVP Hardening Checker"""
import json, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def main():
    R = {"check_status":"PASS","blockers":[],"tests":{}}
    block = False
    def ck(n,cond,m=""): R["tests"][n]=cond; return (not cond) and (R["blockers"].append(f"{n}: {m}") or True)

    ih = MODULE/"data/runtime/dashboard/intel_desk.html"
    block |= ck("intel_html", ih.is_file())
    if ih.is_file():
        html = ih.read_text()
        block |= ck("v2_prod_visible", "PRODUCTION" in html or "production" in html.lower())
        block |= ck("v4_counts_visible", "A/B/C/SKIP" in html or "0 / 0 / 3" in html)
        block |= ck("no_long_table", "<table>" not in html[:500])
        block |= ck("anomaly_card", "BLOCKER" in html or "NO ACTIVE" in html)
        block |= ck("next_action", "下一动作" in html or "action" in html.lower())
        block |= ck("mobile_size", "max-width" in html)

    # V4 consistency
    v4 = json.loads((MODULE/"data/daily_reports/v4_review_structured_20260519.json").read_text())
    block |= ck("v4_A0_B0_C3_SKIP2", v4['A']==0 and v4['B']==0 and v4['C']==3 and v4['SKIP']==2)
    push = json.loads((MODULE/"data/runtime/status/v4_review_push_20260519.json").read_text())
    block |= ck("actual_send_false", push['actual_send']==False)
    block |= ck("qq_sent_false", push['qq_sent']==False)

    if block: R["check_status"]="BLOCKER"
    print("="*50); print("INTEL DESK MVP HARDENING CHECKER"); print("="*50)
    print(f"Status: {R['check_status']} | Passed: {sum(1 for v in R['tests'].values() if v)}/{len(R['tests'])}")
    for k,v in R["tests"].items(): print(f"  {k}: {'✅' if v else '❌'}")
    if R["blockers"]: print(f"\nBLOCKERS: {R['blockers']}"); sys.exit(1)
    sys.exit(0)

if __name__=="__main__": main()
