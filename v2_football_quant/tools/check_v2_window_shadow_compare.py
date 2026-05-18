#!/usr/bin/env python3
"""Phase D.4 — V2 Window Shadow Compare Checker."""
import argparse, json, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
def _l(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date", required=False); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d")
    pp=SD/f"v2_window_shadow_compare_{dk}.json"; o=SD/f"v2_window_shadow_compare_check_{dk}.json"
    e=[]; w=[]
    if not pp.exists():
        r={"status":"BLOCKER","exists":False,"errors":["marker_missing"],"date":dk}
        o.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2)); raise SystemExit(2)
    m=_l(pp); rp=m.get("report",{})
    for f in ["production_dependency","production_verified","formal_v2_uses_cache","shadow_affects_formal"]:
        if m.get(f,True): e.append(f"b_{f}")
    for f in ["no_api","no_key_read","no_push","no_cron","no_task_trigger","no_window_checker_rerun","no_bet_locked_write","no_settlement_write"]:
        if not m.get(f): e.append(f"g_{f}")
    g=rp.get("guards",{})
    for f in ["no_window_checker_rerun","no_bet_locked_written","no_qq_push","no_settlement_write","missed_not_promoted","formal_link_untouched"]:
        if not g.get(f,True): e.append(f"gv_{f}")
    wc=rp.get("window_checker",{}); st=rp.get("settlement_guard",{}); cp=rp.get("compare",{})
    if wc.get("lock_owner_evidence_quality","missing")!="strong": w.append("WC_LO_EV_PARTIAL")
    if st.get("evidence_quality","missing")!="strong": w.append("ST_EV_PARTIAL")
    if not cp.get("new_locks_vs_daily_status_consistent",True): w.append("NL_DS_INCONSISTENT")
    sec=re.findall(r"sk-[A-Za-z0-9]{20,}|x-apisports-key",json.dumps(m,ensure_ascii=False))
    if sec: e.append("secret")
    sts="FAIL" if e else ("WARN" if w else "PASS")
    r={"status":sts,"exists":True,"production_dependency":m.get("production_dependency",True),
       "production_verified":m.get("production_verified",True),"formal_v2_uses_cache":m.get("formal_v2_uses_cache",True),
       "shadow_affects_formal":m.get("shadow_affects_formal",True),"no_api":m.get("no_api",False),
       "no_push":m.get("no_push",False),"no_cron":m.get("no_cron",False),"no_task_trigger":m.get("no_task_trigger",False),
       "no_window_checker_rerun":m.get("no_window_checker_rerun",False),"no_bet_locked_write":m.get("no_bet_locked_write",False),
       "no_settlement_write":m.get("no_settlement_write",False),"missed_not_promoted":g.get("missed_not_promoted",False),
       "formal_link_untouched":g.get("formal_link_untouched",False),"lock_owner_evidence_quality":wc.get("lock_owner_evidence_quality","missing"),
       "settlement_evidence_quality":st.get("evidence_quality","missing"),"secret_safe":len(sec)==0,
       "warnings":w,"errors":e,"date":dk,"generated_at":datetime.now(CN).isoformat()}
    o.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2))
    if sts=="FAIL": raise SystemExit(1)
if __name__=="__main__": main()
