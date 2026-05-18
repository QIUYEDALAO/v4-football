#!/usr/bin/env python3
"""Phase D.8.12.3 — V2 Guarded Live Observe Contract (default path vs guarded path split)."""
import argparse, json, os, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
SD = BASE / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))

def _load(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def _safety_ok(p):
    if not p.exists(): return False
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return str(d.get("wrapper_status","")).upper() in ("READY_FOR_BOSS_REVIEW","WARN")
    except: return False

def _sandbox_ok(p):
    if not p.exists(): return False
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d.get("status", d.get("observe_status","")) in ("PASS","WARN")
    except: return False

def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); p.add_argument("--window",default="midday"); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); w=a.window
    e=[]; warn=[]

    hard = _load(SD / f"v2_live_observe_guard_hardening_{dk}_{w}.json")
    no_write = hard.get("no_formal_state_write_hook_available", False)
    no_push = hard.get("no_push_hook_available", False)
    safe_sender = hard.get("safe_sender_guard_available", False)
    no_verify = hard.get("no_verified_write_hook_available", False)
    send_guard_used = hard.get("allowed_to_send_guard_used", False)
    push_suppress = hard.get("no_push_suppressed", False)

    safety_wrapper = SD / f"v2_live_worker_safety_wrapper_{dk}_{w}.json"
    sandbox = SD / f"v2_window_worker_sandbox_observe_{dk}_{w}.json"

    d810_ok = _sandbox_ok(sandbox)
    d811_ok = _safety_ok(safety_wrapper)

    # Default path: production code with write/push → blocked
    default_path_ready = False  # always blocked, by design

    # Guarded path: requires all guard hooks
    guarded_ready = bool(no_write and no_push and safe_sender and no_verify and send_guard_used and push_suppress and d810_ok and d811_ok)

    if not no_write: e.append("NO_WRITE_HOOK_MISSING")
    if not no_push: e.append("NO_PUSH_HOOK_MISSING")
    if not safe_sender: e.append("SAFE_SENDER_GUARD_MISSING")
    if not send_guard_used: e.append("ALLOWED_TO_SEND_NOT_ENFORCED")
    if not push_suppress: e.append("PUSH_SUPPRESSED_NOT_AVAILABLE")

    required_flags = {"observe_only": True, "no_formal_state_write": True, "no_push": True, "no_verified_write": True, "no_supervisor": True}
    required_env = {"OPENCLAW_NO_PUSH": "1"}
    required_guards = {"safe_sender_allowed_to_send_enforced": send_guard_used, "worker_no_write_hook": no_write, "supervisor_push_suppressed": push_suppress, "watchdog_only_failure": True}

    status = "NOT_READY" if e else ("WARN" if warn or not guarded_ready else "READY_FOR_BOSS_REVIEW")
    r = {"schema_version":"v2_guarded_live_observe_contract.v1","date":dk,"window":w,"current_level":"CODE_READY",
         "pipeline_ready":False,"production_verified":False,"contract_status":status,
         "default_live_path_ready":default_path_ready,"guarded_live_path_ready":guarded_ready,
         "live_worker_execution_allowed":False,"supervisor_execution_allowed":False,
         "formal_state_write_allowed":False,"qq_push_allowed":False,"verified_write_allowed":False,"cron_enable_allowed":False,
         "required_flags":required_flags,"required_env":required_env,"required_guards":required_guards,
         "d813_draft":{"allowed_to_generate":True,"allowed_to_execute":False,"scope":"guarded single-window live observe only after explicit BOSS approval"},
         "warnings":warn,"blockers":e,"generated_at":datetime.now(CN).isoformat()}
    out=SD/f"v2_guarded_live_observe_contract_{dk}_{w}.json"
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2))
    if status=="FAIL": raise SystemExit(1)

if __name__=="__main__": main()
