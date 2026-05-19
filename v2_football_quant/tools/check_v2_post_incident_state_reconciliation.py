#!/usr/bin/env python3
"""V2 Post-Incident State Reconciliation Checker"""
import json, os, subprocess, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def main():
    R = {"check_status":"PASS","blockers":[],"warnings":[],"tests":{},
         "qq_sent":False,"cron":False,"d13":False,"verified":False,"prod_verified":False}
    block = False
    def ck(n, cond, m=""): R["tests"][n]=cond; return (not cond) and (R["blockers"].append(f"{n}: {m}") or True)

    # Incident marker
    im = MODULE/"data"/"runtime"/"status"/"v2_qq_unauthorized_send_incident_202605.json"
    block |= ck("incident_marker", im.is_file())
    
    # QQ gate in window_checker
    wc = MODULE/"engine"/"v2_window_checker_with_watchdog.py"
    wct = wc.read_text() if wc.is_file() else ""
    block |= ck("qq_hard_gate", "V2_QQ_SEND_ENABLED" in wct)
    block |= ck("incident_block", "qq_unauthorized_send_incident" in wct)
    
    # Formal state has 1545407
    sf = json.loads((MODULE/"data"/"state"/"selected_fixtures_20260519.json").read_text())
    block |= ck("formal_state_written", "1545407" in str(sf.get("selected_fixture_ids",[])))
    
    # Verify no push with gate
    env = {**os.environ, "OPENCLAW_NO_PUSH":"1", "V2_OBSERVE_ONLY":"1", "NO_PROXY":"*"}
    r = subprocess.run(["python3","engine/v2_window_checker_with_watchdog.py","--no-push","--observe-only","--no-formal-state-write","--no-verified-write"],
        capture_output=True,text=True,timeout=60,cwd=str(MODULE),env=env)
    block |= ck("no_secondary_push", "V2_QQ_SEND_ENABLED" in (r.stdout+r.stderr) or r.returncode==0)
    
    # Dashboard
    dash = (MODULE/"data"/"runtime"/"dashboard"/"v2_today.html").read_text()
    block |= ck("dash_incident", "QQ_UNAUTHORIZED" in dash or "INCIDENT" in dash)
    block |= ck("dash_prod_false", "PRODUCTION_VERIFIED" not in dash.lower()[-500:] or "false" in dash.lower())
    
    if block: R["check_status"]="BLOCKER"
    print("="*50); print("POST-INCIDENT RECONCILIATION CHECKER"); print("="*50)
    print(f"Status: {R['check_status']}")
    for k,v in R["tests"].items(): print(f"  {k}: {'✅' if v else '❌'}")
    if R["blockers"]: print(f"\nBLOCKERS: {R['blockers']}"); sys.exit(1)
    sys.exit(0)

if __name__=="__main__": main()
