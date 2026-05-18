#!/usr/bin/env python3
"""Phase D.8.20 — V2 Controlled Resume Risk Acceptance Gate (review only, no execution)."""
import argparse, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
def _l(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); p.add_argument("--window",default="midday"); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); w=a.window; e=[]; ws=[]
    eg=_l(SD/f"v2_controlled_resume_execution_gate_{dk}_{w}.json")
    ap=_l(SD/f"v2_controlled_resume_approval_packet_{dk}_{w}.json")
    m17=_l(SD/f"v2_state_present_guarded_observe_{dk}_{w}.json")
    if not eg: e.append("d819_marker_missing")
    if not ap: e.append("d818_marker_missing")
    if not m17: e.append("d817_marker_missing")
    if e:
        out={"schema_version":"v2_controlled_resume_risk_acceptance_gate.v1","risk_acceptance_status":"BLOCKER",
             "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
             "gate_scope":"controlled_resume_risk_acceptance_only","execution_performed":False,"production_resume_executed":False,
             "production_resume_allowed_now":False,"cron_enable_allowed":False,"qq_push_allowed":False,
             "verified_write_allowed":False,"state_write_allowed":False,
             "accepted_risks_do_not_grant_execution":True,"boss_acceptance_required":True,
             "d821_draft":{"allowed_to_generate":False,"allowed_to_execute":False},
             "blockers":e,"generated_at":datetime.now(CN).isoformat()}
        print(json.dumps(out,ensure_ascii=False,indent=2)); raise SystemExit(2)
    if eg.get("production_verified") or ap.get("production_verified") or m17.get("production_verified"): e.append("PV_LEAK")
    syn_read=eg.get("synthetic_state_file_read_proven",False)
    syn_nw=eg.get("synthetic_state_present_no_write_proven",False)
    syn_aw=eg.get("synthetic_active_window_mutation_proven",False)
    real_sp=eg.get("real_state_present_case_proven",True)
    no_state=eg.get("no_state_case_proven",False)
    accepted_risks=["synthetic_only_state_present_proof","real_state_present_case_gap","active_window_mutation_gap","production_cron_path_gap","production_qq_path_gap","production_verified_path_gap"]
    remaining=["production_execution_without_boss_d821_forbidden","cron_enable_forbidden","qq_push_forbidden","verified_write_forbidden","formal_state_write_forbidden","production_verified_forbidden"]
    status="FAIL" if e else "READY_FOR_BOSS_REVIEW"
    out={"schema_version":"v2_controlled_resume_risk_acceptance_gate.v1","risk_acceptance_status":status,
         "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
         "gate_scope":"controlled_resume_risk_acceptance_only","execution_performed":False,"production_resume_executed":False,
         "formal_daily_pool_executed":False,"supervisor_executed":False,"live_worker_executed":False,
         "cron_modified":False,"qq_sent":False,"verified_written":False,"formal_state_written":False,
         "no_state_case_proven":no_state,"synthetic_state_file_read_proven":syn_read,
         "synthetic_state_present_no_write_proven":syn_nw,"synthetic_active_window_mutation_proven":syn_aw,
         "real_state_present_case_proven":real_sp,
         "risk_acceptance":{"boss_acceptance_required":True,"accepted_risks_do_not_grant_execution":True,
                            "accepted_risks":accepted_risks,"remaining_blockers":remaining},
         "production_resume_allowed_now":False,"cron_enable_allowed":False,"qq_push_allowed":False,
         "verified_write_allowed":False,"state_write_allowed":False,
         "d821_draft":{"allowed_to_generate":True,"allowed_to_execute":False,
                        "scope":"single-window controlled execution draft only after BOSS explicit approval",
                        "required_guards":["no_supervisor","no_push","no_verified_write","no_cron_enable","preflight_required","rollback_required","watchdog_only_failure","manifest_gate_required","stop_on_any_marker_mismatch","no_ai_kill_retry"]},
         "rollback_gate":{"no_ai_kill_retry":True,"report_watchdog_only":True,"preserve_logs":True,"stop_on_any_push_state_verified_cron":True,"stop_on_any_marker_mismatch":True},
         "warnings":ws,"blockers":e,"generated_at":datetime.now(CN).isoformat()}
    o=SD/f"v2_controlled_resume_risk_acceptance_gate_{dk}_{w}.json"
    o.write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
