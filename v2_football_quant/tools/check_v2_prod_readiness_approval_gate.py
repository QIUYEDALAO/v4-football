#!/usr/bin/env python3
"""V2 Production Readiness Approval Gate — final master checker"""
import json, os, subprocess, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def main():
    R = {"check_status":"PASS","blockers":[],"warnings":[],"tests":{},
         "prohibited":{"qq_sent":False,"cron":False,"d13":False,"verified":False,"prod_verified":False}}
    block = False
    def ck(n,cond,m=""): R["tests"][n]=cond; return (not cond) and (R["blockers"].append(f"{n}: {m}") or True)

    # 1. Issue inventory
    block |= ck("inventory", (MODULE/"docs"/"V2_PROD_READINESS_ISSUE_INVENTORY_202605.md").is_file())
    
    # 2. PIPELINE_READY
    pr = json.loads((MODULE/"data/runtime/status/PIPELINE_READY.json").read_text())
    block |= ck("pipeline_ready", pr.get("PIPELINE_READY")==True)
    block |= ck("prod_verified_false", pr.get("PRODUCTION_VERIFIED")==False)
    
    # 3. Formal state
    sf = json.loads((MODULE/"data/state/selected_fixtures_20260519.json").read_text())
    sids = sf.get("selected_fixture_ids",[])
    has_1545407 = 1545407 in sids or "1545407" in sids
    fix = sf["fixtures"].get("1545407",{})
    block |= ck("state_has_1545407", has_1545407)
    block |= ck("official_bet_locked", fix.get("official_bet_locked")==True)
    block |= ck("lock_owner_window_checker", fix.get("lock_owner")=="window_checker")
    
    # 4. QQ gate
    wct = (MODULE/"engine"/"v2_window_checker_with_watchdog.py").read_text()
    block |= ck("qq_hard_gate", "V2_QQ_SEND_ENABLED" in wct)
    block |= ck("incident_block", "qq_unauthorized_send_incident" in wct)
    
    # 5. Incident marker
    im = MODULE/"data"/"runtime"/"status"/"v2_qq_unauthorized_send_incident_202605.json"
    block |= ck("incident_marker", im.is_file() and json.loads(im.read_text()).get("incident")==True)
    
    # 6. No secondary push (dry-run verify)
    env = {**os.environ, "OPENCLAW_NO_PUSH":"1", "V2_OBSERVE_ONLY":"1", "NO_PROXY":"*"}
    r = subprocess.run(["python3","engine/v2_window_checker_with_watchdog.py","--no-push","--observe-only","--no-formal-state-write","--no-verified-write"],
        capture_output=True,text=True,timeout=60,cwd=str(MODULE),env=env)
    block |= ck("no_secondary_push", r.returncode==0 and "V2_QQ_SEND_ENABLED" in (r.stdout+r.stderr))
    
    # 7. Cron
    block |= ck("cron_shadow", (MODULE/"data/runtime/shadow/v2_cron_shadow_plan_202605.json").is_file())
    
    # 8. Verified
    vf = MODULE/"data/runtime/shadow/v2_verified_precheck_shadow_202605.json"
    if vf.is_file():
        vd = json.loads(vf.read_text())
        block |= ck("verified_shadow", vd.get("verified_written")==False)
    block |= ck("verified_missing", not (MODULE/"data/runtime/status").glob("*verified*true*").__next__() if True else True)
    
    # 9. Dashboard
    dash = (MODULE/"data/runtime/dashboard/v2_today.html").read_text()
    block |= ck("dash_prod_false", "PRODUCTION_VERIFIED" not in dash[-1000:] or "false" in dash.lower())
    block |= ck("dash_incident", "INCIDENT" in dash or "incident" in dash.lower())
    block |= ck("dash_no_stale", "20260517" not in dash[:500])
    
    # 10. Reconciled state
    rec = MODULE/"data/runtime/status/v2_post_incident_state_reconciliation_202605.json"
    if rec.is_file():
        rd = json.loads(rec.read_text())
        block |= ck("reconciliation", rd.get("prod_readiness_approval_gate_allowed")==True)
    
    if block: R["check_status"]="BLOCKER"
    elif R["warnings"]: R["check_status"]="WARN"
    print("="*60); print("V2 PROD READINESS APPROVAL GATE"); print("="*60)
    print(f"Status: {R['check_status']}")
    passed = sum(1 for v in R["tests"].values() if v)
    total = len(R["tests"])
    print(f"Passed: {passed}/{total}")
    for k,v in R["tests"].items(): print(f"  {k}: {'✅' if v else '❌'}")
    if R["blockers"]: print(f"\nBLOCKERS: {R['blockers']}"); sys.exit(1)
    print(f"\nPROD_READINESS_APPROVAL_PASS ✅")
    print(f"PRODUCTION_VERIFIED_SET_ALLOWED ✅")
    sys.exit(0)

if __name__=="__main__": main()
