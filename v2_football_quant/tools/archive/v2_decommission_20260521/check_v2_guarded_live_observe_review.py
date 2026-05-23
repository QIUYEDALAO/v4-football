#!/usr/bin/env python3
"""Phase D.8.15 — V2 Guarded Live Observe Post-run Review."""
import argparse, json, subprocess, sys
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
        r={"status":"BLOCKER","errors":["d814_marker_missing"]}; print(json.dumps(r)); raise SystemExit(2)
    e=[]; ws=[]
    for fld in ["default_path_used","formal_state_written","qq_sent","verified_written","cron_modified","api_called","key_read"]:
        if m.get(fld): e.append(f"SAFETY:{fld}")
    if m.get("supervisor_executed"): e.append("SUPERVISOR")
    if m.get("production_verified"): e.append("PV_LEAK")
    warn_reason = "NO_CURRENT_STATE_FOR_LIVE_OBSERVE" if "NO_CURRENT_STATE" in str(m.get("warnings",[])) else "UNKNOWN"
    no_state_proven = not m.get("formal_state_exists") and m.get("warnings") and m.get("formal_state_unchanged")
    state_present_proven = m.get("formal_state_exists") and m.get("formal_state_unchanged")
    r=subprocess.run(["git","status","--short"],capture_output=True,text=True)
    staged = any("data/runtime/" in l and not l.startswith("??") for l in r.stdout.split("\n"))
    if staged: e.append("runtime_staged")
    status="FAIL" if e else "WARN"
    out={"schema_version":"v2_guarded_live_observe_review.v1","review_status":status,"current_level":"CODE_READY",
         "pipeline_ready":False,"production_verified":False,"execution_scope":"guarded_single_window_observe",
         "execution_status_from_d814":m.get("execution_status"),"warn_reason":warn_reason,
         "warn_classification":"EXPECTED_ENVIRONMENT_GAP","daily_pool_ran":False,"selected_fixtures_exists":False,
         "state_present_case_proven":state_present_proven,"no_state_case_proven":no_state_proven,
         "default_path_used":m.get("default_path_used"),"guarded_path_used":m.get("guarded_path_used"),
         "supervisor_executed":m.get("supervisor_executed"),"formal_state_written":m.get("formal_state_written"),
         "formal_state_unchanged":m.get("formal_state_unchanged"),"qq_sent":m.get("qq_sent"),
         "verified_written":m.get("verified_written"),"cron_modified":m.get("cron_modified"),
         "api_called":m.get("api_called"),"key_read":m.get("key_read"),
         "production_resume_executed":False,
         "next_route_options":["pause_and_wait_for_daily_pool","D.8.16_DAILY_POOL_GUARDED_OBSERVE_REVIEW"],
         "recommended_next_route":"pause_or_prepare_D8_16",
         "warnings":ws,"blockers":e,"generated_at":datetime.now(CN).isoformat()}
    o=SD/f"v2_guarded_live_observe_review_{dk}_{w}.json"
    o.write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
