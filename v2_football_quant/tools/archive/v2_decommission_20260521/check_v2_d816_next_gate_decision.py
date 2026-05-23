#!/usr/bin/env python3
"""Phase D.8.16 — Next Gate Decision."""
import argparse, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
def _l(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); e=[]; ws=[]
    rd=_l(SD/f"v2_daily_pool_guarded_observe_readiness_{dk}.json")
    pause=_l(SD/f"v2_guarded_live_observe_pause_decision_{dk}_midday.json")
    if not rd: e.append("readiness_marker_missing")
    if not pause: e.append("d815_pause_marker_missing")
    if e:
        out={"schema_version":"v2_d816_next_gate_decision.v1","decision_status":"BLOCKER",
             "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
             "blockers":e,"date":dk,"generated_at":datetime.now(CN).isoformat()}
        o=SD/f"v2_d816_next_gate_decision_{dk}.json"
        o.write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps(out)); raise SystemExit(2)
    sp_proven = rd.get("state_present_case_proven",False)
    readiness_ok = rd.get("readiness_status") in ("PASS","WARN")
    status = "BLOCKER" if not readiness_ok else ("WARN" if not sp_proven else "READY_FOR_BOSS_REVIEW")
    if not sp_proven: ws.append("STATE_PRESENT_CASE_NOT_PROVEN")
    if not rd.get("selected_fixtures_exists"): ws.append("NO_SELECTED_FIXTURES")
    out={"schema_version":"v2_d816_next_gate_decision.v1","decision_status":status,
         "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
         "d816_readiness_status":rd.get("readiness_status"),"state_present_case_proven":sp_proven,
         "production_resume_allowed_now":False,"cron_enable_allowed":False,
         "qq_push_allowed":False,"verified_write_allowed":False,"state_write_allowed":False,
         "boss_approval_required":True,
         "recommended_next":"pause_until_daily_pool_runs" if not sp_proven else "D.8.17_state_present_guarded_observe",
         "d817_draft":{"allowed_to_generate":True,"allowed_to_execute":False,
                        "scope":"state-present guarded observe only after BOSS approval and selected_fixtures exists"},
         "warnings":ws,"blockers":e,"generated_at":datetime.now(CN).isoformat()}
    o=SD/f"v2_d816_next_gate_decision_{dk}.json"
    o.write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__": main()

# D.8.16.3 closure: v2_football_quant/tools/check_v2_d816_next_gate_decision.py
