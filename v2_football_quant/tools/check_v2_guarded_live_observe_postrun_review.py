#!/usr/bin/env python3
"""Phase D.8.14.1 — Guarded Live Observe Postrun Review."""
import argparse, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
def _l(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); p.add_argument("--window",default="midday"); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); w=a.window
    m=_l(SD/f"v2_guarded_live_observe_execution_{dk}_{w}.json")
    if not m:
        r={"status":"BLOCKER","errors":["marker_missing"]}; print(json.dumps(r,ensure_ascii=False,indent=2)); raise SystemExit(2)
    e=[]; ws=m.get("warnings",[])
    for fld in ["default_path_used","formal_state_written","qq_sent","verified_written","cron_modified","api_called","key_read"]:
        if m.get(fld): e.append(f"SAFETY:{fld}")
    if m.get("supervisor_executed"): e.append("SUPERVISOR_EXECUTED")
    if m.get("production_verified"): e.append("PV_LEAK")
    status="FAIL" if e else ("WARN" if ws or m.get("execution_status")=="WARN" else "PASS")
    r={"schema_version":"v2_guarded_live_observe_postrun_review.v1","review_status":status,
       "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
       "execution_scope":"guarded_single_window_observe","production_resume_executed":False,
       "default_path_used":m.get("default_path_used"),"guarded_path_used":m.get("guarded_path_used"),
       "supervisor_executed":m.get("supervisor_executed"),"formal_state_written":m.get("formal_state_written"),
       "qq_sent":m.get("qq_sent"),"verified_written":m.get("verified_written"),
       "cron_modified":m.get("cron_modified"),"api_called":m.get("api_called"),"key_read":m.get("key_read"),
       "formal_state_unchanged":m.get("formal_state_unchanged"),"window_status":m.get("window_status"),
       "new_locks_count":m.get("new_locks_count"),"warn_reason":ws,
       "next_gate_requires_boss":True,"next_gate":"D.8.15_GUARDED_OBSERVE_REVIEW_OR_PAUSE",
       "warnings":ws,"blockers":e,"generated_at":datetime.now(CN).isoformat()}
    out=SD/f"v2_guarded_live_observe_postrun_review_{dk}_{w}.json"
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2))
    if status=="FAIL": raise SystemExit(1)
if __name__=="__main__": main()
