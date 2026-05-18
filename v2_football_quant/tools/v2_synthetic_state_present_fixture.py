#!/usr/bin/env python3
"""Phase D.8.17 — Synthetic State-Present Fixture Generator (sandbox only, no formal state)."""
import argparse, json, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
SD = BASE / "data" / "runtime" / "status"
SANDBOX = BASE / "data" / "runtime" / "sandbox" / "v2_state_present_guarded_observe"
CN = timezone(timedelta(hours=8))
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); p.add_argument("--window",default="midday")
    p.add_argument("--no-formal-state-write",action="store_true"); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); w=a.window
    if not a.no_formal_state_write:
        print(json.dumps({"status":"BLOCKER","blockers":["no_formal_state_write_flag_missing"]})); raise SystemExit(2)
    # Check formal state NOT touched
    formal_state = BASE / "data" / "state" / f"selected_fixtures_{dk}.json"
    formal_exists = formal_state.exists()
    # Create sandbox fixture
    sd = SANDBOX / dk; sd.mkdir(parents=True, exist_ok=True)
    fixture = {"schema_version":"v2_synthetic_state_present_fixture.v1","date":dk,"source":"synthetic_sandbox",
               "strategy_mutation":False,"selected":["SYNTHETIC_D817_001"],
               "fixtures":{"SYNTHETIC_D817_001":{
                   "fixture_id":"SYNTHETIC_D817_001","home_team":"Synthetic_Home","away_team":"Synthetic_Away",
                   "league":"SANDBOX_LEAGUE","kickoff_time":f"{dk[:4]}-{dk[4:6]}-{dk[6:]}T15:00:00+08:00",
                   "odds_D":2.50,"odds_H":2.80,"odds_A":2.90,"last_seen_odds_D":2.50,"last_seen_odds_H":2.80,"last_seen_odds_A":2.90,
                   "candidate_stage":"SYNTHETIC_OBSERVE_ONLY","action_code":"OBSERVE_ONLY_SKIP","lock_status":"HT_SKIP",
                   "official_bet_locked":False,"qq_required":False,"settlement_required":False,
                   "lock_owner":"sandbox_observe","lock_source":"synthetic_guarded_observe",
                   "strategy_mutation":False}}}
    sf = sd / f"selected_fixtures_{dk}_synthetic.json"
    sf.write_text(json.dumps(fixture,ensure_ascii=False,indent=2),encoding="utf-8")
    marker = {"schema_version":"v2_synthetic_state_present_fixture.v1","date":dk,"window":w,
              "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
              "sandbox_fixture_generated":True,"sandbox_fixture_path":str(sf),
              "formal_state_written":False,"formal_state_path_touched":False,"formal_state_exists_before":formal_exists,
              "bet_locked_written":False,"qq_required_any":False,"settlement_required_any":False,
              "api_called":False,"key_read":False,"synthetic_only":True,
              "warnings":[],"blockers":[],"generated_at":datetime.now(CN).isoformat()}
    o=SD/f"v2_synthetic_state_present_fixture_{dk}_{w}.json"
    o.write_text(json.dumps(marker,ensure_ascii=False,indent=2)); print(json.dumps(marker,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
