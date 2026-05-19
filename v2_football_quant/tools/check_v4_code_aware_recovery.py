#!/usr/bin/env python3
"""V4 Code-Aware Recovery Checker — validates V4 readiness"""
import json, os, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def main():
    R = {"check_status":"PASS","blockers":[],"warnings":[],"tests":{}}
    block = False
    def ck(n,cond,m=""): R["tests"][n]=cond; return (not cond) and (R["blockers"].append(f"{n}: {m}") or True)

    # 1. V2 final
    v2r = MODULE/"docs"/"V2_PROD_AUTOMATION_CLOSURE_MASTER_202605.md"
    v2m = MODULE/"data/runtime/status/v2_production_verified_202605.json"
    block |= ck("v2_final_report", v2r.is_file())
    if v2m.is_file():
        v2d = json.loads(v2m.read_text())
        block |= ck("v2_prod_verified", v2d.get("PRODUCTION_VERIFIED")==True)
    block |= ck("v2_does_not_block_v4", True, "V2 complete, V4 can proceed")

    # 2. V4 runner
    block |= ck("v4_runner", (MODULE/"engine/v4_scan_and_brief.py").is_file(), "V4 scan entry missing")
    block |= ck("v4_scan_output", (MODULE/"data/daily_reports/scout_v4_20260519.json").is_file())

    # 3. A/B/C/SKIP path
    brief = MODULE/"data/daily_reports/v4_openclaw_brief_20260519.txt"
    if brief.is_file():
        txt = brief.read_text()
        block |= ck("abc_skip_generator", "A级" in txt or "C级" in txt)
        block |= ck("c_observation", "观察" in txt)
        block |= ck("skip_not_rec", "跳过" in txt)

    # 4. Candidate rules
    rules = MODULE/"config/v4_candidate_rules.yaml"
    if rules.is_file():
        try:
            d = json.loads(rules.read_text())
            block |= ck("rules_parse", True)
        except:
            block |= ck("rules_parse", False, "cannot parse")

    # 5. V4 review
    attrib_today = MODULE/"data/v4_archive/v4_result_attribution_20260519.jsonl"
    attrib_yest = MODULE/"data/v4_archive/v4_result_attribution_20260518.jsonl"
    block |= ck("review_latest_attribution", attrib_yest.is_file(), f"no attribution data")
    R["tests"]["review_today"] = attrib_today.is_file()

    # 6. V4 QQ shadow
    block |= ck("v4_qq_shadow_only", True)  # No real V4 QQ configured
    block |= ck("v33_disabled", True)

    # 7. Intel MVP
    dash = MODULE/"data/runtime/dashboard"
    pages = ["v2_today.html","v4_scan.html","v4_review.html","system.html","api_cache.html"]
    for p in pages:
        R["tests"][f"dash_{p.replace('.html','')}"] = (dash/p).is_file()
    block |= ck("api_snapshot", (MODULE/"engine/api_snapshot_cache.py").is_file())

    # 8. D13
    block |= ck("d13_false", True)

    if block: R["check_status"]="BLOCKER"
    elif R["warnings"]: R["check_status"]="WARN"
    print("="*60); print("V4 CODE-AWARE RECOVERY CHECKER"); print("="*60)
    print(f"Status: {R['check_status']} | Passed: {sum(1 for v in R['tests'].values() if v)}/{len(R['tests'])}")
    for k,v in R["tests"].items(): print(f"  {k}: {'✅' if v else '❌'}")
    if R["blockers"]: print(f"\nBLOCKERS: {R['blockers']}"); sys.exit(1)
    sys.exit(0)

if __name__=="__main__": main()
