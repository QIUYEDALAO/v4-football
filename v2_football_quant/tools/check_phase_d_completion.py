#!/usr/bin/env python3
"""Phase D.6 — V2 Shadow Completion Audit Checker."""
import argparse, json, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
def _l(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
REQUIRED_MARKERS = ["v2_shadow_boundary_check", "v2_shadow_baseline", "v2_shadow_compare", "v2_window_shadow_compare", "v2_settlement_shadow_guard"]
SETTLE_ERRORS = ["MISSED_IN_SETTLEMENT", "SETTLEMENT_TARGETS_OFFICIAL_LOCKS_CONFLICT", "SETTLEMENT_TARGETS_WINDOW_LOCKS_CONFLICT"]
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date", required=False); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); w=[]; e=[]
    missing=[]; found=[]
    for prefix in REQUIRED_MARKERS:
        matches = list(SD.glob(f"{prefix}*_{dk}.json")) or list(SD.glob(f"{prefix}_{dk}.json")) or list(SD.glob(f"{prefix}*_{dk}*.json"))
        if matches: found.append(prefix)
        else: missing.append(prefix)
    if missing: e.extend([f"marker_missing:{m}" for m in missing])
    # Check settlement guard
    sg = _l(SD / f"v2_settlement_shadow_guard_{dk}.json")
    sg_errors = sg.get("report",{}).get("errors",[]) if sg else []
    settle_fail = "FAIL" in str(sg.get("status",""))
    settle_errors_ok = all(x in sg_errors for x in SETTLE_ERRORS)
    if not settle_fail: e.append("settlement_not_fail")
    if not settle_errors_ok:
        for x in SETTLE_ERRORS:
            if x not in sg_errors: e.append(f"settlement_missing_error:{x}")
    # Boundary checks
    for prefix in found:
        m = _l(SD / f"{prefix}_{dk}.json")
        if not m: continue
        for fld in ["production_dependency","production_verified","formal_v2_uses_cache","shadow_affects_formal"]:
            if m.get(fld): e.append(f"{prefix}_{fld}")
    phase_d_engineering_complete = len(missing) == 0 and len(e) == 0
    phase_d_business_pass = False  # By design: settlement historical fail
    known_historical_fail = settle_fail and settle_errors_ok
    status = "BLOCKER" if missing else ("FAIL" if e else "WARN")
    r = {"schema_version":"phase_d_completion_check.v1","status":status,
         "phase_d_engineering_complete":phase_d_engineering_complete,
         "phase_d_business_pass":phase_d_business_pass,
         "known_historical_fail":known_historical_fail,
         "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
         "formal_v2_uses_cache":False,"shadow_affects_formal":False,
         "no_api":True,"no_push":True,"no_cron":True,"no_task_trigger":True,
         "no_verified_write":True,"no_settlement_rerun":True,"no_qq_push":True,
         "settlement_errors":sg_errors,"markers_found":found,"markers_missing":missing,
         "warnings":w,"errors":e,"date":dk,"generated_at":datetime.now(CN).isoformat()}
    out=SD/f"phase_d_completion_check_{dk}.json"
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2))
    if status=="FAIL": raise SystemExit(1)
if __name__=="__main__": main()
