#!/usr/bin/env python3
"""Phase D.4.1 — V2 Window Shadow Compare Checker (semantic-hardened)."""
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
    pp=SD/f"v2_window_shadow_compare_{dk}.json"; o=SD/f"v2_window_shadow_compare_check_{dk}.json"
    e=[]; w=[]
    # Static source check
    sp = ENG / "v2_window_shadow_compare.py"
    if sp.exists():
        src=sp.read_text(encoding="utf-8")
        for pat,label in [(r'\bor\s+True\b',"tautology"),(r'\bby_design\b',"by_design"),(r'\bassumed_safe\b',"assumed_safe"),(r'\bhardcoded\b',"hardcoded"),(r'!=\s*"strong"',"neq_strong_simplified")]:
            if re.search(pat,src): e.append(f"src_{label}")
    if not pp.exists():
        r={"status":"BLOCKER","exists":False,"errors":["marker_missing"],"date":dk}
        o.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2)); raise SystemExit(2)
    m=_l(pp); rp=m.get("report",{})
    for fld in ["production_dependency","production_verified","formal_v2_uses_cache","shadow_affects_formal"]:
        if m.get(fld,True): e.append(f"b_{fld}")
    for fld in ["no_api","no_key_read","no_push","no_cron","no_task_trigger","no_window_checker_rerun","no_bet_locked_write","no_settlement_write"]:
        if not m.get(fld): e.append(f"g_{fld}")
    g=rp.get("guards",{})
    for fld in ["no_window_checker_rerun","no_bet_locked_written","no_qq_push","no_settlement_write","missed_not_promoted","formal_link_untouched"]:
        if not g.get(fld,True): e.append(f"gv_{fld}")
    wc=rp.get("window_checker",{}); st=rp.get("settlement_guard",{}); cp=rp.get("compare",{})
    cmp_eq=cp.get("lock_owner_evidence_quality","missing")
    gap_preserved=cp.get("lock_owner_gap_preserved")
    gap_warning=cp.get("lock_owner_gap_is_warning")
    gap_reason=cp.get("lock_owner_gap_reason","")
    wc_nl=wc.get("new_locks_count",0)
    # Field presence
    for fld in ["lock_owner_gap_preserved","lock_owner_gap_is_warning","lock_owner_evidence_quality","lock_owner_gap_reason"]:
        if cp.get(fld) is None: e.append(f"missing_field_{fld}")
    # Semantic consistency
    if cmp_eq == "not_applicable":
        if wc_nl != 0: e.append("NOT_APPLICABLE_BUT_HAS_LOCKS")
        if not gap_preserved: e.append("NA_BUT_GAP_NOT_PRESERVED")
        if gap_warning: e.append("NA_BUT_GAP_IS_WARNING")
    elif cmp_eq == "strong":
        if gap_warning: e.append("STRONG_BUT_GAP_IS_WARNING")
    elif cmp_eq in ("partial","missing"):
        w.append(f"LO_EVIDENCE_{cmp_eq.upper()}")
    # Settlement
    st_eq=st.get("evidence_quality","missing")
    if st_eq != "strong": w.append(f"ST_EV_{st_eq.upper()}")
    if st.get("only_window_checker_locks") is False: e.append("ST_NOT_ONLY_WC")
    # Gap warning consistency
    if gap_warning and gap_reason and "missing" not in gap_reason and cmp_eq not in ("partial","missing"):
        w.append("GAP_WARNING_WITHOUT_OBVIOUS_REASON")
    # Secret
    sec=re.findall(r"sk-[A-Za-z0-9]{20,}|x-apisports-key",json.dumps(m,ensure_ascii=False))
    if sec: e.append("secret")
    sts="FAIL" if e else ("WARN" if w else "PASS")
    r={"status":sts,"exists":True,"production_dependency":m.get("production_dependency",True),
       "production_verified":m.get("production_verified",True),"formal_v2_uses_cache":m.get("formal_v2_uses_cache",True),
       "shadow_affects_formal":m.get("shadow_affects_formal",True),"no_api":m.get("no_api",False),
       "no_push":m.get("no_push",False),"no_cron":m.get("no_cron",False),"no_task_trigger":m.get("no_task_trigger",False),
       "no_window_checker_rerun":m.get("no_window_checker_rerun",False),"no_bet_locked_write":m.get("no_bet_locked_write",False),
       "no_settlement_write":m.get("no_settlement_write",False),"missed_not_promoted":g.get("missed_not_promoted",False),
       "formal_link_untouched":g.get("formal_link_untouched",False),
       "lock_owner_gap_preserved":gap_preserved,"lock_owner_gap_is_warning":gap_warning,
       "lock_owner_evidence_quality":cmp_eq,"lock_owner_gap_reason":gap_reason,
       "settlement_evidence_quality":st_eq,"secret_safe":len(sec)==0,"src_clean":len([x for x in e if x.startswith("src_")])==0,
       "warnings":w,"errors":e,"date":dk,"generated_at":datetime.now(CN).isoformat()}
    o.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2))
    if sts=="FAIL": raise SystemExit(1)
if __name__=="__main__": main()
