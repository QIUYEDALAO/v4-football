#!/usr/bin/env python3
"""Phase D.4 — V2 Window Shadow Compare Dry-Run."""
import argparse, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.v2_window_shadow_compare import build_v2_window_shadow_compare
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date", required=False); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); r=build_v2_window_shadow_compare(dk); s=r["summary"]
    m={"schema_version":"v2_window_shadow_compare_dryrun.v1","date":dk,"status":s["overall_status"],
       "generated_at":datetime.now(CN).isoformat(),"production_dependency":False,"production_verified":False,
       "formal_v2_uses_cache":False,"shadow_affects_formal":False,"no_api":True,"no_key_read":True,
       "no_push":True,"no_cron":True,"no_task_trigger":True,"no_window_checker_rerun":True,
       "no_bet_locked_write":True,"no_settlement_write":True,"overall_status":s,"report":r}
    o=SD/f"v2_window_shadow_compare_{dk}.json"; o.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"ok":s["overall_status"]!="FAIL","status":s["overall_status"],"marker":str(o),
                       "pass":s["pass_count"],"warn":s["warn_count"],"fail":s["fail_count"]},ensure_ascii=False,indent=2))
    if s["overall_status"]=="FAIL": raise SystemExit(1)
if __name__=="__main__": main()
