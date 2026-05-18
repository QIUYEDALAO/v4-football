#!/usr/bin/env python3
"""Phase D.8.19 — V2 Controlled Resume Execution Gate (BLOCKED for execution)."""
import argparse, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
def _l(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); p.add_argument("--window",default="midday"); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); w=a.window; e=[]; ws=[]
    ap=_l(SD/f"v2_controlled_resume_approval_packet_{dk}_{w}.json")
    m17=_l(SD/f"v2_state_present_guarded_observe_{dk}_{w}.json")
    if not ap: e.append("d818_marker_missing")
    if not m17: e.append("d817_marker_missing")
    if e:
        out={"schema_version":"v2_controlled_resume_execution_gate.v1","execution_gate_status":"BLOCKER",
              "ready_for_boss_review":False,"current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
              "gate_scope":"controlled_resume_execution_gate_only","execution_performed":False,
              "production_resume_executed":False,"production_resume_allowed_now":False,
              "cron_enable_allowed":False,"qq_push_allowed":False,"verified_write_allowed":False,"state_write_allowed":False,
              "d820_draft":{"allowed_to_generate":True,"allowed_to_execute":False},
              "blockers":e,"generated_at":datetime.now(CN).isoformat()}
        print(json.dumps(out,ensure_ascii=False,indent=2)); raise SystemExit(2)
    if ap.get("production_verified") or m17.get("production_verified"): e.append("PV_LEAK")
    # Explicit resume check — no ambiguous inline ternary
    ap_resume = bool(ap.get("production_resume_allowed_now", False))
    m17_resume = bool(m17.get("production_resume_allowed_now", False))
    if ap_resume or m17_resume: e.append("RESUME_LEAK")
    # Explicit gate checks
    for fld,label in [("cron_enable_allowed","CRON"),("qq_push_allowed","QQ"),("verified_write_allowed","VERIFIED"),("state_write_allowed","STATE")]:
        if ap.get(fld) or m17.get(fld): e.append(f"GATE_LEAK:{label}")
    no_state=ap.get("no_state_case_proven",False)
    syn_read=ap.get("synthetic_state_file_read_proven",False)
    syn_nw=ap.get("synthetic_state_present_no_write_proven",False)
    syn_aw=ap.get("synthetic_active_window_mutation_proven",False)
    real_sp=ap.get("real_state_present_case_proven",True)
    blockers=["real_state_present_case_not_proven","active_window_mutation_path_not_proven","production_cron_path_not_proven","production_qq_path_not_proven","production_verified_path_not_proven"]
    status="FAIL" if e else "BLOCKED_FOR_EXECUTION"
    out={"schema_version":"v2_controlled_resume_execution_gate.v1","execution_gate_status":status,"ready_for_boss_review":True,
         "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
         "gate_scope":"controlled_resume_execution_gate_only","execution_performed":False,
         "production_resume_executed":False,"formal_daily_pool_executed":False,
         "supervisor_executed":False,"live_worker_executed":False,
         "cron_modified":False,"qq_sent":False,"verified_written":False,"formal_state_written":False,
         "no_state_case_proven":no_state,"synthetic_state_file_read_proven":syn_read,
         "synthetic_state_present_no_write_proven":syn_nw,"synthetic_active_window_mutation_proven":syn_aw,
         "real_state_present_case_proven":real_sp,
         "production_resume_allowed_now":False,"cron_enable_allowed":False,"qq_push_allowed":False,
         "verified_write_allowed":False,"state_write_allowed":False,
         "d820_draft":{"allowed_to_generate":True,"allowed_to_execute":False,
                        "scope":"controlled execution only after BOSS explicit approval",
                        "required_conditions":["approval_packet_warn_accepted_by_boss","no_supervisor","no_push","no_verified_write","no_cron_enable","preflight_required","rollback_required","watchdog_only_failure","manifest_gate_required"]},
         "rollback_gate":{"no_ai_kill_retry":True,"report_watchdog_only":True,"preserve_logs":True,"stop_on_any_push_state_verified_cron":True},
         "blockers":blockers,"warnings":ws,"generated_at":datetime.now(CN).isoformat()}
    o=SD/f"v2_controlled_resume_execution_gate_{dk}_{w}.json"
    o.write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
