#!/usr/bin/env python3
"""Phase D.8.15 — V2 Guarded Live Observe Pause Decision."""
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
    rv=_l(SD/f"v2_guarded_live_observe_review_{dk}_{w}.json")
    e=[]; ws=[]
    for fld in ["default_path_used","formal_state_written","qq_sent","verified_written","cron_modified","api_called","key_read"]:
        if m.get(fld): e.append(f"SAFETY:{fld}")
    if m.get("supervisor_executed"): e.append("SUPERVISOR")
    if m.get("production_verified"): e.append("PV_LEAK")
    no_state = not m.get("formal_state_exists")
    no_state_proven = rv.get("no_state_case_proven",False)
    status="FAIL" if e else ("WARN" if no_state else "READY_FOR_BOSS_REVIEW")
    out={"schema_version":"v2_guarded_live_observe_pause_decision.v1","decision_status":status,
         "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
         "d814_status":m.get("execution_status"),"no_current_state_for_live_observe":no_state,
         "production_resume_allowed_now":False,"cron_enable_allowed":False,
         "qq_push_allowed":False,"verified_write_allowed":False,"state_write_allowed":False,
         "boss_approval_required":True,
         "recommended_action":"pause_or_prepare_D8_16",
         "recommended_reason":"state_present_case_not_proven" if no_state else "guarded_observe_completed_await_boss",
         "d816_draft":{"allowed_to_generate":True,"allowed_to_execute":False,
                        "scope":"DAILY_POOL guarded observe or state-present guarded observe only after BOSS approval"},
         "warnings":ws,"blockers":e,"generated_at":datetime.now(CN).isoformat()}
    o=SD/f"v2_guarded_live_observe_pause_decision_{dk}_{w}.json"
    o.write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
