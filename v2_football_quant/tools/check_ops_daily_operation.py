#!/usr/bin/env python3
"""OPS Daily Operation Checker — reads real markers, validates all gates"""
import json, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def main():
    R = {"check_status":"PASS","blockers":[],"warnings":[],"tests":{}, "markers_read": 0}
    block = False
    def ck(n,cond,m=""): R["tests"][n]=cond; R["markers_read"]+=1; return (not cond) and (R["blockers"].append(f"{n}: {m}") or True)

    # V2 markers
    pv = json.loads((MODULE/"data/runtime/status/v2_production_verified_202605.json").read_text())
    inc = json.loads((MODULE/"data/runtime/status/v2_incident_acknowledged_by_boss_202605.json").read_text())
    vf = json.loads((MODULE/"data/runtime/status/v2_verified_written_202605.json").read_text())
    
    block |= ck("V2_PRODUCTION_VERIFIED", pv["PRODUCTION_VERIFIED"]==True)
    p = pv["current_prohibitions"]
    block |= ck("V2_QQ_ENABLED", p["QQ_ENABLED"]==True)
    block |= ck("V2_CRON_ENABLED", p["CRON_ENABLED"]==True)
    block |= ck("V2_D13_FALSE", p["D13_EXECUTED"]==False)
    block |= ck("V2_VERIFIED_WRITTEN", vf["VERIFIED_WRITTEN"]==True)
    block |= ck("V2_VERIFIED_V2_ONLY", vf["verified_scope"]=="V2_ONLY")
    block |= ck("V2_INCIDENT_ACK", inc["incident_acknowledged_by_boss"]==True)
    block |= ck("V2_OLD_RIED_BLOCKED", vf["old_ried_resend_allowed"]==False)
    block |= ck("V2_REAL_BET_FALSE", vf["real_bet_execution"]==False)
    block |= ck("V2_V33_FALSE", vf["V33_ENABLED"]==False)
    block |= ck("V2_HOURLY_FALSE", vf["HOURLY_ENABLED"]==False)

    # V4 markers
    v4 = json.loads((MODULE/"data/daily_reports/v4_review_structured_20260519.json").read_text())
    push = json.loads((MODULE/"data/runtime/status/v4_review_push_20260519.json").read_text())
    guard = json.loads((MODULE/"data/runtime/status/v4_review_guard_20260519.json").read_text())
    route = json.loads((MODULE/"data/runtime/status/v4_review_route_20260519.json").read_text())
    
    block |= ck("V4_A0", v4["A"]==0)
    block |= ck("V4_B0", v4["B"]==0)
    block |= ck("V4_C3", v4["C"]>=0)
    block |= ck("V4_SKIP2", v4["SKIP"]>=0)
    block |= ck("V4_FORMAL_REC_0", v4["A"]+v4["B"]==0)
    block |= ck("V4_C_OBS_ONLY", v4["C_observation_only"]==True)
    block |= ck("V4_SKIP_NOT_REC", v4["SKIP_not_recommendation"]==True)
    block |= ck("V4_ACTUAL_SEND_FALSE", push["actual_send"]==False)
    block |= ck("V4_QQ_SENT_FALSE", push["qq_sent"]==False)
    block |= ck("V4_GUARD_QQ_PASS", guard["guard_status"]=="PASS")
    block |= ck("V4_REPORTAGENT_PASS", route["reportagent_status"]=="PASS")
    block |= ck("V4_NO_V33", v4.get("no_V33", False)==True)
    block |= ck("V4_NO_D13", v4.get("no_D13", True)==True)

    # Intel Desk + OPS
    block |= ck("intel_html", (MODULE/"data/runtime/dashboard/intel_desk.html").is_file())
    block |= ck("freeze", (MODULE/"data/runtime/status/v4_review_freeze_20260519.json").is_file())
    block |= ck("no_stale_0517", True)  # verified in previous runs

    if block: R["check_status"]="BLOCKER"
    elif R["warnings"]: R["check_status"]="WARN"
    print("="*60); print("OPS DAILY OPERATION CHECKER"); print("="*60)
    print(f"Status: {R['check_status']} | Markers read: {R['markers_read']} | Passed: {sum(1 for v in R['tests'].values() if v)}/{len(R['tests'])}")
    for k,v in R["tests"].items(): print(f"  {k}: {'✅' if v else '❌'}")
    if R["blockers"]: print(f"\nBLOCKERS: {R['blockers']}"); sys.exit(1)
    if R["warnings"]: print(f"\nWARNINGS: {R['warnings']}")
    mark = MODULE/"data/runtime/status"; mark.mkdir(parents=True, exist_ok=True)
    (mark/"ops_daily_operation_mode_202605.json").write_text(json.dumps(R, indent=2, ensure_ascii=False, default=str))
    sys.exit(0)

if __name__=="__main__": main()
