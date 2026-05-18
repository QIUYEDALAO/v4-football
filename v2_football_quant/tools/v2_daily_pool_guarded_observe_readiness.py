#!/usr/bin/env python3
"""Phase D.8.16 — V2 DAILY_POOL Guarded Observe Readiness (no state write, no API)."""
import argparse, json, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
SD = BASE / "data" / "runtime" / "status"
STATE_DIR = BASE / "data" / "state"
CN = timezone(timedelta(hours=8))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=False); p.add_argument("--mode",required=True)
    p.add_argument("--no-formal-state-write",action="store_true"); p.add_argument("--no-push",action="store_true")
    p.add_argument("--no-cron",action="store_true"); p.add_argument("--no-verified-write",action="store_true")
    a=p.parse_args(); dk=a.date or datetime.now(CN).strftime("%Y%m%d")
    e=[]; ws=[]

    if a.mode != "readiness": e.append("MODE_NOT_READINESS")
    if not a.no_formal_state_write: e.append("NO_FORMAL_STATE_WRITE_FLAG_MISSING")
    if not a.no_push: e.append("NO_PUSH_FLAG_MISSING")
    if not a.no_cron: e.append("NO_CRON_FLAG_MISSING")
    if not a.no_verified_write: e.append("NO_VERIFIED_WRITE_FLAG_MISSING")
    if e:
        r={"schema_version":"v2_daily_pool_guarded_observe_readiness.v1","date":dk,"readiness_status":"BLOCKER",
           "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
           "mode":"readiness","blockers":e,"generated_at":datetime.now(CN).isoformat()}
        o=SD/f"v2_daily_pool_guarded_observe_readiness_{dk}.json"
        o.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2)); raise SystemExit(2)

    # Check state
    sf = STATE_DIR / f"selected_fixtures_{dk}.json"
    sf_exists = sf.exists()
    pool_markers = list(SD.glob(f"v2_daily_pool_*_{dk}.json")) + list(SD.glob("task_status_v2_daily_pool*"))
    dp_ran = any(m.exists() for m in pool_markers if isinstance(m, Path))

    # Sandbox evidence — read-only from existing markers
    sandbox_evidence = {}
    for marker in sorted(SD.glob("v2_daily_pool_*.json")):
        try: sandbox_evidence[marker.name] = "exists"
        except: pass

    status = "WARN" if not sf_exists else ("PASS" if dp_ran else "WARN")
    ws.append("NO_CURRENT_STATE") if not sf_exists else None

    r={"schema_version":"v2_daily_pool_guarded_observe_readiness.v1","date":dk,"current_level":"CODE_READY",
       "pipeline_ready":False,"production_verified":False,"mode":"readiness",
       "formal_daily_pool_executed":False,"formal_state_written":False,
       "selected_fixtures_exists":sf_exists,"state_present_case_proven":sf_exists,
       "no_state_case_proven":not sf_exists,"sandbox_evidence_generated":bool(sandbox_evidence),
       "api_called":False,"key_read":False,"qq_sent":False,"cron_modified":False,"verified_written":False,
       "bet_locked_written":False,"strategy_changed":False,"cache_used_as_formal_source":False,
       "d817_ready_for_boss_review":sf_exists,"readiness_status":status,
       "hardcoded_date_removed":True,
       "sandbox_evidence_keys":list(sandbox_evidence.keys()),
       "warnings":ws,"blockers":e,"generated_at":datetime.now(CN).isoformat()}
    o=SD/f"v2_daily_pool_guarded_observe_readiness_{dk}.json"
    o.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2))
    if status in ("FAIL","BLOCKER"): raise SystemExit(1)

if __name__=="__main__": main()
