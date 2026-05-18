#!/usr/bin/env python3
"""Phase D.7 — Preflight Checker."""
import argparse, json, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
def _l(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d")
    pp=SD/f"v2_settlement_preflight_{dk}.json"; o=SD/f"v2_settlement_preflight_check_{dk}.json"
    e=[]; w=[]
    if not pp.exists():
        r={"status":"BLOCKER","errors":["marker_missing"],"date":dk}; o.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2)); raise SystemExit(2)
    m=_l(pp); d=m.get("decision",{}); rc=d.get("reason_codes",[]); c=m.get("required_conditions",{})
    if m.get("settlement_allowed"): e.append("SHOULD_BE_BLOCKED")
    if not m.get("fail_closed"): e.append("NOT_FAIL_CLOSED")
    if not c.get("official_bet_locked_positive"): w.append("OB_ZERO")
    if not c.get("window_checker_new_locks_positive"): w.append("WC_NL_ZERO")
    if "MISSED_CANDIDATES_PRESENT" not in rc: e.append("MISSED_NOT_IN_BLOCKERS")
    if "OFFICIAL_BET_LOCKED_ZERO" not in rc: e.append("OB_ZERO_NOT_IN_BLOCKERS")
    if "WINDOW_CHECKER_NEW_LOCKS_ZERO" not in rc: e.append("WC_ZERO_NOT_IN_BLOCKERS")
    sec=re.findall(r"sk-[A-Za-z0-9]{20,}|x-apisports-key",json.dumps(m,ensure_ascii=False))
    if sec: e.append("secret")
    sts="FAIL" if e else ("WARN" if w else "PASS")
    r={"status":sts,"settlement_allowed":m.get("settlement_allowed"),"fail_closed":m.get("fail_closed"),
       "reason_codes":rc,"production_verified":m.get("production_verified",False),
       "no_verified_write":m.get("boundaries",{}).get("no_verified_write",False),
       "no_push":m.get("boundaries",{}).get("no_push",False),
       "secret_safe":len(sec)==0,"warnings":w,"errors":e,"date":dk,"generated_at":datetime.now(CN).isoformat()}
    o.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2))
    if sts=="FAIL": raise SystemExit(1)
if __name__=="__main__": main()
