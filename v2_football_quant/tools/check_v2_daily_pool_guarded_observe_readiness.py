#!/usr/bin/env python3
"""Phase D.8.16.2 — DAILY_POOL Guarded Observe Readiness Checker (hardened)."""
import argparse, json, re, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
FORBIDDEN = ["data/runtime/","data/state/","data/paper_trading/","投注资金日报表","engine/net_utils.py","dashboard",".env"]
def _l(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); e=[]; ws=[]
    m=_l(SD/f"v2_daily_pool_guarded_observe_readiness_{dk}.json")
    if not m:
        r={"status":"BLOCKER","errors":["readiness_marker_missing"]}; print(json.dumps(r)); raise SystemExit(2)
    for fld,exp in [("current_level","CODE_READY"),("pipeline_ready",False),("production_verified",False),
                     ("formal_daily_pool_executed",False),("formal_state_written",False)]:
        if m.get(fld)!=exp: e.append(f"field_{fld}:{m.get(fld)}")
    for fld in ["api_called","key_read","qq_sent","cron_modified","verified_written","bet_locked_written",
                 "strategy_changed","cache_used_as_formal_source"]:
        if m.get(fld): e.append(f"SAFETY:{fld}")
    if not m.get("hardcoded_date_removed"): e.append("HARDCODED_DATE_NOT_REMOVED")
    # Forbidden file guard
    rr=subprocess.run(["git","status","--short"],capture_output=True,text=True,cwd=str(SD.parent.parent))
    lines=rr.stdout.split("\n")
    runtime_staged = any("data/runtime/" in l and not l.startswith("??") for l in lines)
    state_staged = any("data/state/" in l and not l.startswith("??") for l in lines)
    paper_staged = any("data/paper_trading/" in l for l in lines)
    excel_staged = any("投注资金" in l for l in lines)
    net_staged = any("net_utils" in l for l in lines)
    if runtime_staged: e.append("runtime_staged")
    if state_staged: e.append("state_staged")
    if paper_staged: e.append("paper_trading_staged")
    if excel_staged: e.append("excel_staged")
    if net_staged: e.append("net_utils_staged")
    sec=re.findall(r"sk-[A-Za-z0-9]{20,}|x-apisports-key",json.dumps(m,ensure_ascii=False))
    if sec: e.append("secret")
    status="FAIL" if e else ("WARN" if m.get("readiness_status")=="WARN" else "PASS")
    out={"status":status,"readiness_status":m.get("readiness_status"),"selected_fixtures_exists":m.get("selected_fixtures_exists"),
         "state_present_case_proven":m.get("state_present_case_proven"),"formal_state_written":m.get("formal_state_written"),
         "production_verified":m.get("production_verified",True),"hardcoded_date_removed":m.get("hardcoded_date_removed",False),
         "runtime_staged":runtime_staged,"state_staged":state_staged,"paper_trading_staged":paper_staged,
         "excel_staged":excel_staged,"net_utils_staged":net_staged,"secret_safe":len(sec)==0,
         "warnings":ws,"errors":e,"date":dk,"generated_at":datetime.now(CN).isoformat()}
    o=SD/f"v2_daily_pool_guarded_observe_readiness_check_{dk}.json"
    o.write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps(out,ensure_ascii=False,indent=2))
    if status=="FAIL": raise SystemExit(1)
if __name__=="__main__": main()

# D.8.16.3 closure: v2_football_quant/tools/check_v2_daily_pool_guarded_observe_readiness.py
