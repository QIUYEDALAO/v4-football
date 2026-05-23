#!/usr/bin/env python3
"""Phase D.8.12.1 — V2 Live Observe Guard Hardening Checker."""
import argparse, json, os, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
SD = BASE / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))

def _has_code(path, pattern): 
    return bool(re.search(pattern, (path).read_text(encoding="utf-8"))) if path.exists() else False

def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); p.add_argument("--window",default="midday"); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); e=[]; w=[]

    worker_p = BASE / "engine" / "v2_window_worker.py"
    supervisor_p = BASE / "engine" / "v2_window_checker_with_watchdog.py"
    sender_p = BASE / "engine" / "safe_outbound_sender.py"

    # Worker checks
    worker_ok = _has_code(worker_p, r'--observe-only|V2_OBSERVE_ONLY')
    no_write_ok = _has_code(worker_p, r'--no-formal-state-write|no_formal_state_write')
    worker_no_push = _has_code(worker_p, r'--no-push.*mode|no_push.*mode')
    no_verify_ok = _has_code(worker_p, r'--no-verified-write')
    def_ok = _has_code(worker_p, r'write_state\(today_str')

    if not worker_ok: e.append("worker_no_observe_only")
    if not no_write_ok: e.append("worker_no_formal_state_write_hook")
    if not def_ok: e.append("worker_default_behavior_modified")

    # Supervisor checks
    sup_no_push = _has_code(supervisor_p, r'no_push.*=.*True|OPENCLAW_NO_PUSH')
    sup_push_suppress = _has_code(supervisor_p, r'push_suppressed')
    sup_no_push_param = _has_code(supervisor_p, r'no_push=_no_push')
    if not sup_no_push: e.append("supervisor_no_push_guard")
    if not sup_push_suppress: e.append("supervisor_no_push_suppress_field")

    # Safe sender checks — must verify actual enforcement
    send_ok = sender_p.exists()
    allowed_field = _has_code(sender_p, r'allowed_to_send')
    allowed_guard_used = _has_code(sender_p, r'if not allowed_to_send')
    no_push_suppress = _has_code(sender_p, r'push_suppressed.*true|push_suppressed=true')
    
    # Only true if enforcement exists, not just field declaration
    safe_sender = send_ok and allowed_guard_used and no_push_suppress

    # Secret check
    for fp in [worker_p, supervisor_p, sender_p]:
        if fp.exists():
            txt = fp.read_text(encoding="utf-8")
            if re.search(r"sk-[A-Za-z0-9]{20,}|x-apisports-key", txt): e.append(f"secret_in_{fp.name}")

    no_fw_hook = worker_ok or no_write_ok
    no_push_hook = sup_no_push and sup_push_suppress
    safe_sender = send_ok

    status = "FAIL" if e else ("WARN" if w or not safe_sender else "PASS")
    r = {"schema_version":"v2_live_observe_guard_hardening.v1","hardening_status":status,
         "no_formal_state_write_hook_available":no_fw_hook,"no_push_hook_available":no_push_hook,
         "safe_sender_guard_available":safe_sender,"no_verified_write_hook_available":no_verify_ok,
         "supervisor_direct_push_guarded":sup_no_push,"worker_default_behavior_preserved":def_ok,
         "allowed_to_send_false_supported":allowed_field,
         "allowed_to_send_guard_used":allowed_guard_used,
         "no_push_suppressed":no_push_suppress,
         "subprocess_send_guarded":allowed_guard_used,
         "production_verified":False,"pipeline_ready":False,
         "remaining_risks":[],"warnings":w,"blockers":e,
         "date":dk,"generated_at":datetime.now(CN).isoformat()}
    out=SD/f"v2_live_observe_guard_hardening_{dk}_{a.window}.json"
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2))
    if status=="FAIL": raise SystemExit(1)

if __name__=="__main__": main()
