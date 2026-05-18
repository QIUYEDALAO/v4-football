#!/usr/bin/env python3
"""Phase D.8.18 — V2 Controlled Resume Approval Packet (BOSS review only, no execution)."""
import argparse, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
def _l(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); p.add_argument("--window",default="midday"); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); w=a.window; e=[]; ws=[]
    m14=_l(SD/f"v2_guarded_live_observe_execution_{dk}_{w}.json")
    m17=_l(SD/f"v2_state_present_guarded_observe_{dk}_{w}.json")
    m816=_l(SD/f"v2_daily_pool_guarded_observe_readiness_{dk}.json")
    if not m14: e.append("d814_marker_missing")
    if not m17: e.append("d817_marker_missing")
    if not m816: e.append("d816_marker_missing")
    if e:
        out={"approval_packet_status":"BLOCKER","blockers":e}; print(json.dumps(out)); raise SystemExit(2)
    no_state = m14.get("warnings") and "NO_CURRENT_STATE" in str(m14.get("warnings",[]))
    syn_read = m17.get("synthetic_state_file_read_proven",False)
    syn_nw = m17.get("synthetic_state_present_no_write_proven",False)
    syn_aw = m17.get("synthetic_active_window_mutation_proven",False)
    real_sp = m17.get("real_state_present_case_proven",True)
    for src,label in [(m14,"d814"),(m17,"d817"),(m816,"d816")]:
        if src.get("production_verified"): e.append(f"PV_LEAK:{label}")
        if src.get("production_resume_allowed_now") if "resume" in str(src.keys()) else False: e.append(f"RESUME_LEAK:{label}")
    proven=["no_state_guarded_skip_safe","synthetic_state_file_read_safe","synthetic_state_present_no_write_safe"]
    not_proven=["real_state_present_case","active_window_mutation_path","production_cron_path","production_qq_path","production_verified_path"]
    blocked=["default_live_path","supervisor_direct_path","formal_state_write","qq_push","verified_write","cron_enable"]
    status="FAIL" if e else ("WARN" if not syn_aw or real_sp else "READY_FOR_BOSS_REVIEW" if syn_nw else "WARN")
    out={"schema_version":"v2_controlled_resume_approval_packet.v1","approval_packet_status":status,
         "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
         "approval_scope":"controlled_resume_approval_packet_only","execution_performed":False,
         "production_resume_executed":False,"formal_daily_pool_executed":False,
         "supervisor_executed":False,"live_worker_executed":False,
         "cron_modified":False,"qq_sent":False,"verified_written":False,"formal_state_written":False,
         "no_state_case_proven":no_state,"synthetic_state_file_read_proven":syn_read,
         "synthetic_state_present_no_write_proven":syn_nw,"synthetic_active_window_mutation_proven":syn_aw,
         "real_state_present_case_proven":real_sp,
         "risk_classification":{"proven":proven,"not_proven":not_proven,"blocked":blocked},
         "production_resume_allowed_now":False,"cron_enable_allowed":False,"qq_push_allowed":False,
         "verified_write_allowed":False,"state_write_allowed":False,
         "d819_draft":{"allowed_to_generate":True,"allowed_to_execute":False,
                        "scope":"controlled execution draft only after BOSS approval",
                        "required_guards":["no_supervisor","no_push","no_verified_write","no_formal_state_write","preflight_required","rollback_required","watchdog_only_failure"]},
         "rollback_gate":{"no_ai_kill_retry":True,"report_watchdog_only":True,"preserve_logs":True,"stop_on_any_push_state_verified_cron":True},
         "warnings":ws,"blockers":e,"generated_at":datetime.now(CN).isoformat()}
    o=SD/f"v2_controlled_resume_approval_packet_{dk}_{w}.json"
    o.write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
