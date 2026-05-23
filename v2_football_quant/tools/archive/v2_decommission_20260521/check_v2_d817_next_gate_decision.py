#!/usr/bin/env python3
"""Phase D.8.17.1 — D.8.17 Next Gate Decision."""
import argparse, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
def _l(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); p.add_argument("--window",default="midday"); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); w=a.window; e=[]; ws=[]
    m=_l(SD/f"v2_state_present_guarded_observe_{dk}_{w}.json")
    if not m: e.append("d817_marker_missing")
    if e:
        out={"schema_version":"v2_d817_next_gate_decision.v1","decision_status":"BLOCKER",
             "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
             "production_resume_allowed_now":False,"cron_enable_allowed":False,
             "qq_push_allowed":False,"verified_write_allowed":False,"state_write_allowed":False,
             "boss_approval_required":True,"recommended_next":"cannot_determine",
             "d818_draft":{"allowed_to_generate":False,"allowed_to_execute":False},
             "blockers":e,"generated_at":datetime.now(CN).isoformat()}
        o=SD/f"v2_d817_next_gate_decision_{dk}_{w}.json"
        o.write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps(out)); raise SystemExit(2)
    for fld in ["formal_state_written","qq_sent","verified_written","cron_modified","api_called","key_read","bet_locked_written"]:
        if m.get(fld): e.append(f"SAFETY:{fld}")
    no_write_proven = m.get("synthetic_state_present_no_write_proven",False)
    status="FAIL" if e else ("WARN" if not no_write_proven else "READY_FOR_BOSS_REVIEW")
    out={"schema_version":"v2_d817_next_gate_decision.v1","decision_status":status,
         "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
         "no_state_case_proven":True,"synthetic_state_file_read_proven":m.get("synthetic_state_file_read_proven",False),
         "synthetic_state_present_no_write_proven":no_write_proven,
         "real_state_present_case_proven":False,
         "production_resume_allowed_now":False,"cron_enable_allowed":False,
         "qq_push_allowed":False,"verified_write_allowed":False,"state_write_allowed":False,
         "boss_approval_required":True,
         "recommended_next":"D.8.18_controlled_resume_approval_packet" if no_write_proven else "pause_until_real_daily_pool_runs",
         "d818_draft":{"allowed_to_generate":True,"allowed_to_execute":False,
                        "scope":"controlled resume approval packet only, not execution"},
         "warnings":ws,"blockers":e,"generated_at":datetime.now(CN).isoformat()}
    o=SD/f"v2_d817_next_gate_decision_{dk}_{w}.json"
    o.write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__": main()

# D.8.17.1 closure stamp
