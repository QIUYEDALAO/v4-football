#!/usr/bin/env python3
"""Phase D.8.14.1 — Guarded Live Observe Execution Checker."""
import argparse, json, re, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
def _l(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); p.add_argument("--window",default="midday"); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); w=a.window
    pp=SD/f"v2_guarded_live_observe_execution_{dk}_{w}.json"; o=SD/f"v2_guarded_live_observe_execution_check_{dk}_{w}.json"
    e=[]; ws=[]
    if not pp.exists():
        r={"status":"BLOCKER","errors":["marker_missing"],"date":dk}; o.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2)); raise SystemExit(2)
    m=_l(pp)
    for fld,expected in [("current_level","CODE_READY"),("pipeline_ready",False),("production_verified",False),
                          ("default_path_used",False),("guarded_path_used",True),("required_flags_present",True),
                          ("openclaw_no_push",True),("supervisor_executed",False),("observe_only",True),
                          ("no_formal_state_write",True),("no_push",True),("no_verified_write",True),("no_supervisor",True)]:
        if m.get(fld) != expected: e.append(f"field_{fld}:{m.get(fld)}")
    for fld in ["formal_state_written","qq_sent","verified_written","cron_modified","api_called","key_read"]:
        if m.get(fld): e.append(f"SAFETY_VIOLATION:{fld}")
    unchanged = m.get("formal_state_unchanged")
    state_exists = m.get("formal_state_exists")
    if not unchanged and state_exists: e.append("STATE_CHANGED")
    if not state_exists and "NO_CURRENT_STATE" not in str(m.get("warnings",[])): ws.append("STATE_MISSING_NO_WARN")
    r=subprocess.run(["git","status","--short"],capture_output=True,text=True); st=r.stdout.strip()
    runtime_staged = False
    for line in st.split("\n"):
        if "data/runtime/" in line and not line.startswith("??"):
            runtime_staged = True
            e.append("runtime_staged")
    if "data/state/" in st: e.append("state_staged")
    if "data/paper_trading/" in st: e.append("paper_trading_staged")
    sec=re.findall(r"sk-[A-Za-z0-9]{20,}",json.dumps(m,ensure_ascii=False))
    if sec: e.append("secret")
    status="FAIL" if e else ("WARN" if ws else "PASS")
    r={"status":status,"default_path_used":m.get("default_path_used"),"guarded_path_used":m.get("guarded_path_used"),
       "supervisor_executed":m.get("supervisor_executed"),"formal_state_written":m.get("formal_state_written"),
       "formal_state_unchanged":unchanged,"qq_sent":m.get("qq_sent"),"production_verified":m.get("production_verified",True),
       "secret_safe":len(sec)==0,"execution_status":m.get("execution_status"),
       "runtime_staged":runtime_staged,
       "warnings":ws,"errors":e,"date":dk,"generated_at":datetime.now(CN).isoformat()}
    o.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2))
    if status=="FAIL": raise SystemExit(1)
if __name__=="__main__": main()
