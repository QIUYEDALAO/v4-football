#!/usr/bin/env python3
"""Phase D.8.17.1 — State-Present Guarded Observe Checker."""
import argparse, json, re, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
def _l(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); p.add_argument("--window",default="midday"); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); w=a.window; e=[]; ws=[]
    m=_l(SD/f"v2_state_present_guarded_observe_{dk}_{w}.json")
    if not m:
        r={"status":"BLOCKER","errors":["d817_marker_missing"]}; print(json.dumps(r)); raise SystemExit(2)
    for fld,exp in [("current_level","CODE_READY"),("pipeline_ready",False),("production_verified",False),
                     ("default_path_used",False),("guarded_path_used",True),("supervisor_executed",False),
                     ("observe_only",True),("no_formal_state_write",True),("no_push",True),("no_verified_write",True),
                     ("no_supervisor",True),("openclaw_no_push",True)]:
        if m.get(fld)!=exp: e.append(f"field_{fld}:{m.get(fld)}")
    for fld in ["formal_state_written","qq_sent","verified_written","cron_modified","api_called","key_read","bet_locked_written","strategy_changed"]:
        if m.get(fld): e.append(f"SAFETY:{fld}")
    if not m.get("formal_state_unchanged"): e.append("STATE_CHANGED")
    if m.get("real_state_present_case_proven"): e.append("REAL_STATE_PRESENT_INCORRECTLY_TRUE")
    r=subprocess.run(["git","status","--short"],capture_output=True,text=True); st=r.stdout
    for label,pat in [("runtime","data/runtime/"),("state","data/state/"),("paper","data/paper_trading/"),
                       ("excel","投注资金"),("net","net_utils")]:
        if any(pat in l and not l.startswith("??") for l in st.split("\n")): e.append(f"{label}_staged")
    sec=re.findall(r"sk-[A-Za-z0-9]{20,}",json.dumps(m,ensure_ascii=False))
    if sec: e.append("secret")
    status="FAIL" if e else ("WARN" if m.get("execution_status")=="WARN" else "PASS")
    out={"status":status,"execution_status":m.get("execution_status"),"synthetic_state_file_read_proven":m.get("synthetic_state_file_read_proven",False),
         "synthetic_state_present_no_write_proven":m.get("synthetic_state_present_no_write_proven",False),
         "real_state_present_case_proven":m.get("real_state_present_case_proven",True),
         "formal_state_written":m.get("formal_state_written"),"formal_state_unchanged":m.get("formal_state_unchanged"),
         "production_verified":m.get("production_verified",True),"secret_safe":len(sec)==0,
         "warnings":ws,"errors":e,"date":dk,"generated_at":datetime.now(CN).isoformat()}
    o=SD/f"v2_state_present_guarded_observe_check_{dk}_{w}.json"
    o.write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps(out,ensure_ascii=False,indent=2))
    if status=="FAIL": raise SystemExit(1)
if __name__=="__main__": main()

# D.8.17.1 closure stamp
