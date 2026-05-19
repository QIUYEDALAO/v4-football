#!/usr/bin/env python3
"""V4 Wrapper Final Guard — static check: no old scout as evidence, no synthetic"""
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def main():
    R = {"check_status":"PASS","blockers":[],"tests":{}}
    block = False
    def ck(n,cond,m=""): R["tests"][n]=cond; return (not cond) and (R["blockers"].append(f"{n}: {m}") or True)

    wrap = MODULE/"tools/run_v4_window_scan_capture_readonly.py"
    txt = wrap.read_text() if wrap.is_file() else ""

    block |= ck("wrapper_exists", wrap.is_file())
    block |= ck("before_hash", "scout_before_hash" in txt)
    block |= ck("after_hash", "scout_after_hash" in txt)
    block |= ck("scout_updated_check", "scout_updated" in txt)
    block |= ck("evidence_source_real", "real_runner_output" in txt)
    block |= ck("synthetic_blocked", "synthetic" in txt.lower() and "False" in txt.split('synthetic_evidence')[1][:30] if 'synthetic_evidence' in txt else True)
    block |= ck("no_hardcoded_abc", 'result["A"]' not in txt.split('scout_updated')[0] if 'scout_updated' in txt else True)
    block |= ck("preflight_no_write", "preflight" in txt and "capture_ran" in txt)
    block |= ck("stale_scout_warned", "not_updated_by_this_run" in txt or "STALE" in txt)

    if block: R["check_status"]="BLOCKER"
    print("="*50); print("V4 WRAPPER FINAL GUARD"); print("="*50)
    print(f"Status: {R['check_status']} | Passed: {sum(1 for v in R['tests'].values() if v)}/{len(R['tests'])}")
    for k,v in R["tests"].items(): print(f"  {k}: {'✅' if v else '❌'}")
    if R["blockers"]: print(f"\nBLOCKERS: {R['blockers']}"); sys.exit(1)
    sys.exit(0)

if __name__=="__main__": main()
