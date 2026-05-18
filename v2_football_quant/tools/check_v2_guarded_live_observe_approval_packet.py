#!/usr/bin/env python3
"""Phase D.8.13 — V2 Guarded Live Observe Approval Packet (BOSS review only, no execution)."""
import argparse, json, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
SD = BASE / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))

def _load(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); p.add_argument("--window",default="midday"); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); w=a.window
    e=[]; ws=[]

    contract = _load(SD / f"v2_guarded_live_observe_contract_{dk}_{w}.json")
    gate = _load(SD / f"v2_live_worker_observe_approval_gate_{dk}_{w}.json")
    hard = _load(SD / f"v2_live_observe_guard_hardening_{dk}_{w}.json")
    sandbox = _load(SD / f"v2_window_worker_sandbox_observe_{dk}_{w}.json")
    safety = _load(SD / f"v2_live_worker_safety_wrapper_{dk}_{w}.json")

    # Core invariants — must all be false
    execution_fields = {}
    for fld in ["live_worker_execution_allowed","supervisor_execution_allowed","formal_state_write_allowed",
                 "qq_push_allowed","verified_write_allowed","cron_enable_allowed"]:
        val = contract.get(fld, gate.get(fld, True))
        execution_fields[fld] = val
        if val: e.append(f"EXECUTION_LEAKED:{fld}")

    guarded_ready = contract.get("guarded_live_path_ready", False)
    default_blocked = contract.get("default_live_path_ready", True) is False
    if not guarded_ready: ws.append("GUARDED_NOT_READY")
    if not default_blocked: e.append("DEFAULT_PATH_UNBLOCKED")

    # Hardware guard checks
    guards_ok = all([
        hard.get("no_formal_state_write_hook_available"),
        hard.get("no_push_hook_available"),
        hard.get("safe_sender_guard_available"),
        hard.get("allowed_to_send_guard_used"),
        hard.get("no_push_suppressed"),
    ])
    if not guards_ok: e.append("GUARD_HOOK_MISSING")

    # Sandbox and safety
    sandbox_ok = sandbox.get("observe_status","") in ("PASS","WARN")
    safety_ok = str(safety.get("wrapper_status","")).upper() in ("READY_FOR_BOSS_REVIEW","WARN")
    if not sandbox_ok: ws.append("SANDBOX_NOT_PASSED")
    if not safety_ok: ws.append("SAFETY_NOT_READY")

    # Production boundary
    for src,label in [(contract,"contract"),(gate,"gate"),(hard,"hardening")]:
        if src.get("production_verified"): e.append(f"PV_LEAK:{label}")
        if src.get("pipeline_ready"): e.append(f"PR_LEAK:{label}")

    # Staged check
    import subprocess
    r = subprocess.run(["git","status","--short"],capture_output=True,text=True,cwd=str(BASE.parent.parent))
    staged = r.stdout.strip()
    if "data/runtime/" in staged: e.append("runtime_staged")
    if "data/state/" in staged: e.append("state_staged")
    if "data/paper_trading/" in staged: e.append("paper_trading_staged")

    status = "BLOCKER" if e else ("WARN" if ws else "READY_FOR_BOSS_REVIEW")

    rpt = {"schema_version":"v2_guarded_live_observe_approval_packet.v1","date":dk,"window":w,
           "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
           "approval_packet_status":status,
           "default_live_path_ready":default_blocked is False,  # must be false
           "guarded_live_path_ready":guarded_ready,
           "guarded_live_observe_approved":False,
           "live_worker_execution_allowed":False,"supervisor_execution_allowed":False,
           "formal_state_write_allowed":False,"qq_push_allowed":False,"verified_write_allowed":False,"cron_enable_allowed":False,
           "boss_approval_required":True,
           "required_flags":{"observe_only":True,"no_formal_state_write":True,"no_push":True,"no_verified_write":True,"no_supervisor":True},
           "required_env":{"OPENCLAW_NO_PUSH":"1"},
           "required_guards":{"safe_sender_allowed_to_send_enforced":hard.get("allowed_to_send_guard_used",False),
                              "worker_no_write_hook":hard.get("no_formal_state_write_hook_available",False),
                              "supervisor_push_suppressed":hard.get("no_push_suppressed",False),
                              "watchdog_only_failure":True},
           "d814_draft":{"allowed_to_generate":True,"allowed_to_execute":False,
                         "scope":"guarded single-window live observe execution only after explicit BOSS approval for D.8.14"},
           "rollback_gate":{"no_ai_kill_retry":True,"report_watchdog_only":True,"preserve_logs":True,"stop_on_any_push_state_verified_cron":True},
           "warnings":ws,"blockers":e,"generated_at":datetime.now(CN).isoformat()}
    out=SD/f"v2_guarded_live_observe_approval_packet_{dk}_{w}.json"
    out.write_text(json.dumps(rpt,ensure_ascii=False,indent=2)); print(json.dumps(rpt,ensure_ascii=False,indent=2))
    if status in ("FAIL","BLOCKER"): raise SystemExit(1)

if __name__=="__main__": main()
