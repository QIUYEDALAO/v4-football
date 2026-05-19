#!/usr/bin/env python3
"""V2 Production Automation Closure — final regression checker"""
import json, os, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def main():
    R = {"check_status":"PASS","blockers":[],"warnings":[],"tests":{}}
    block = False
    def ck(n,cond,m=""): R["tests"][n]=cond; return (not cond) and (R["blockers"].append(f"{n}: {m}") or True)

    # Core state
    pv = json.loads((MODULE/"data/runtime/status/v2_production_verified_202605.json").read_text())
    block |= ck("prod_verified", pv["PRODUCTION_VERIFIED"]==True)
    block |= ck("pipeline_ready", pv["PIPELINE_READY"]==True)
    p = pv["current_prohibitions"]
    block |= ck("qq_enabled", p["QQ_ENABLED"]==True)
    block |= ck("cron_enabled", p["CRON_ENABLED"]==True)
    block |= ck("d13_false", p["D13_EXECUTED"]==False)
    block |= ck("V2_QQ_SEND_ENABLED", p["V2_QQ_SEND_ENABLED"]==1)

    # Verified
    vf = json.loads((MODULE/"data/runtime/status/v2_verified_written_202605.json").read_text())
    block |= ck("verified", vf["VERIFIED_WRITTEN"]==True)
    block |= ck("verified_scope_v2", vf["verified_scope"]=="V2_ONLY")
    block |= ck("verified_d13_false", vf["D13_EXECUTED"]==False)
    block |= ck("v33_disabled", vf["V33_ENABLED"]==False)
    block |= ck("hourly_disabled", vf["HOURLY_ENABLED"]==False)

    # Incident
    inc = json.loads((MODULE/"data/runtime/status/v2_qq_unauthorized_send_incident_202605.json").read_text())
    ack = json.loads((MODULE/"data/runtime/status/v2_incident_acknowledged_by_boss_202605.json").read_text())
    block |= ck("incident_ack", ack["incident_acknowledged_by_boss"]==True)
    block |= ck("old_ried_blocked", vf["old_ried_resend_allowed"]==False)
    block |= ck("real_bet_false", vf["real_bet_execution"]==False)

    # Dashboard
    dash = (MODULE/"data/runtime/dashboard/v2_today.html").read_text()
    block |= ck("dash_cron", "CRON_ENABLED" in dash or "cron" in dash.lower())
    block |= ck("dash_verified", "VERIFIED_WRITTEN" in dash or "verified" in dash.lower())

    # QQ gate in code
    wct = (MODULE/"engine/v2_window_checker_with_watchdog.py").read_text()
    block |= ck("qq_gate_code", "V2_QQ_SEND_ENABLED" in wct)
    block |= ck("incident_block_code", "qq_unauthorized_send_incident" in wct)

    if block: R["check_status"]="BLOCKER"
    print("="*60); print("V2 PROD AUTOMATION CLOSURE CHECKER"); print("="*60)
    print(f"Status: {R['check_status']} | Passed: {sum(1 for v in R['tests'].values() if v)}/{len(R['tests'])}")
    for k,v in R["tests"].items(): print(f"  {k}: {'✅' if v else '❌'}")
    if R["blockers"]: print(f"\nBLOCKERS: {R['blockers']}"); sys.exit(1)
    print("\n✅ V2 PROD AUTOMATION COMPLETE")
    sys.exit(0)

if __name__=="__main__": main()
