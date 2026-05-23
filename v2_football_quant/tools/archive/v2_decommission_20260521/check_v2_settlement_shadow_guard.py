#!/usr/bin/env python3
"""Phase D.5 — V2 Settlement Shadow Guard Checker."""
import argparse, json, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
ENG = Path(__file__).resolve().parent.parent / "engine"
CN = timezone(timedelta(hours=8))
def _l(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date", required=False); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d")
    pp=SD/f"v2_settlement_shadow_guard_{dk}.json"; o=SD/f"v2_settlement_shadow_guard_check_{dk}.json"
    e=[]; w=[]
    sp = ENG / "v2_settlement_shadow_guard.py"
    if sp.exists():
        src=sp.read_text(encoding="utf-8")
        for pat,label in [(r'\bor\s+True\b',"tautology"),(r'\bby_design\b',"by_design"),(r'\bassumed_safe\b',"assumed_safe"),(r'\bhardcoded\b',"hardcoded")]:
            if re.search(pat,src): e.append(f"src_{label}")
    if not pp.exists():
        r={"status":"BLOCKER","exists":False,"errors":["marker_missing"],"date":dk}
        o.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2)); raise SystemExit(2)
    m=_l(pp); rp=m.get("report",{})
    for fld in ["production_dependency","production_verified","formal_v2_uses_cache","shadow_affects_formal"]:
        if m.get(fld,True): e.append(f"b_{fld}")
    for fld in ["no_api","no_key_read","no_push","no_cron","no_task_trigger","no_settlement_rerun","no_verified_write","no_bet_locked_write","no_settlement_write"]:
        if not m.get(fld): e.append(f"g_{fld}")
    g=rp.get("guards",{})
    for fld in ["no_settlement_rerun","no_verified_write","no_bet_locked_written","no_qq_push","no_settlement_write","missed_not_settled","formal_link_untouched"]:
        if not g.get(fld,True): e.append(f"gv_{fld}")
    st=rp.get("settlement",{}); cmp=rp.get("compare",{})
    lo_eq=st.get("lock_owner_evidence_quality","missing")
    targets=st.get("settlement_targets",0)
    if lo_eq == "not_applicable":
        if targets != 0: e.append("NA_BUT_HAS_TARGETS")
        if cmp.get("settlement_gap_is_warning"): w.append("NA_GAP_WARNING_UNEXPECTED")
    elif lo_eq == "partial":
        w.append("SETTLE_LO_PARTIAL")
        if cmp.get("only_window_checker_locks") is True: w.append("ONLY_WC_BUT_EV_PARTIAL")
    elif lo_eq == "missing":
        w.append("SETTLE_LO_MISSING")
    # Settlement guard checks
    # Conflict checks
    t_match_ob = cmp.get("settlement_targets_match_official_locks")
    if t_match_ob is False: e.append("SETTLE_TARGETS_OFFICIAL_LOCKS_CONFLICT")
    t_match_wl = cmp.get("settlement_targets_match_window_locks")
    if t_match_wl is False: e.append("SETTLE_TARGETS_WINDOW_LOCKS_CONFLICT")
    if cmp.get("missed_candidates_absent_from_settlement") is False: e.append("MISSED_IN_SETTLEMENT")
    if cmp.get("official_lock_only") is False: e.append("OFFICIAL_LOCK_ONLY_FALSE")
    if cmp.get("only_window_checker_locks") is False: e.append("NON_WC_IN_SETTLEMENT")
    if cmp.get("settlement_gap_preserved") is False: e.append("SETTLE_GAP_NOT_PRESERVED")
    sec=re.findall(r"sk-[A-Za-z0-9]{20,}|x-apisports-key",json.dumps(m,ensure_ascii=False))
    if sec: e.append("secret")
    sts="FAIL" if e else ("WARN" if w else "PASS")
    r={"status":sts,"exists":True,"production_dependency":m.get("production_dependency",True),
       "production_verified":m.get("production_verified",True),"formal_v2_uses_cache":m.get("formal_v2_uses_cache",True),
       "shadow_affects_formal":m.get("shadow_affects_formal",True),"no_api":m.get("no_api",False),
       "no_push":m.get("no_push",False),"no_cron":m.get("no_cron",False),"no_task_trigger":m.get("no_task_trigger",False),
       "no_settlement_rerun":m.get("no_settlement_rerun",False),"no_verified_write":m.get("no_verified_write",False),
       "no_bet_locked_write":m.get("no_bet_locked_write",False),"no_settlement_write":m.get("no_settlement_write",False),
       "missed_not_settled":g.get("missed_not_settled",False),"formal_link_untouched":g.get("formal_link_untouched",False),
       "settlement_evidence_quality":lo_eq,"settlement_gap_preserved":cmp.get("settlement_gap_preserved"),
       "settlement_gap_is_warning":cmp.get("settlement_gap_is_warning"),"zero_lock_zero_settlement":cmp.get("zero_lock_zero_settlement_consistent"),
       "only_window_checker_locks":cmp.get("only_window_checker_locks"),
       "secret_safe":len(sec)==0,"src_clean":len([x for x in e if x.startswith("src_")])==0,
       "warnings":w,"errors":e,"date":dk,"generated_at":datetime.now(CN).isoformat()}
    o.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2))
    if sts=="FAIL": raise SystemExit(1)
if __name__=="__main__": main()
