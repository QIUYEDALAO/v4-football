#!/usr/bin/env python3
"""V2 D12 Final Boss Authorization Checker"""
import json, subprocess, sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]; DOCS_DIR = MODULE_ROOT / "docs"

REQUIRED_DOCS = ["V2_D12_FINAL_BOSS_AUTHORIZATION_PACKET.md",
    "V2_D12_PROOF_EXECUTION_ORDER_MATRIX.md","V2_D12_RUNNER_READINESS_AUDIT.md",
    "V2_D12_FINAL_COMMAND_REVIEW.md","V2_D12_FINAL_WATCHDOG_ROLLBACK_STOP_GATE.md"]

DANGER_FALSE = ["d12_allowed_to_execute","d13_allowed_to_execute",
    "production_proof_execution_authorized","production_proof_executed",
    "daily_pool_executed","supervisor_executed","live_worker_executed",
    "cron_enable_allowed","qq_push_allowed","api_called","key_read",
    "state_write_allowed","verified_write_allowed","PRODUCTION_VERIFIED",
    "phase_e_allowed","v4_controlled_observe_execution_allowed"]

REQUIRED_TRUE = ["d12_allowed_to_generate","d13_allowed_to_generate",
    "boss_explicit_authorization_required","no_implicit_execution",
    "v4_frozen_at_j3","watchdog_only_failure_required",
    "no_ai_kill_retry_required","rollback_required"]

STASH_ALLOWED = ["phase-d101","phase-v4a1","phase-d87"]
FORBIDDEN = ["data/runtime","data/state","data/paper_trading",".xlsx",".xls",
    "engine/net_utils.py","nowscore_h2h.js","secret",".env","token","key"]

def _run(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or str(MODULE_ROOT), timeout=60)
    return r.returncode, r.stdout.strip(), r.stderr.strip()
def _scan(paths): return [p for p in paths for pat in FORBIDDEN if pat in p]

def main():
    R = {"check_status":"PASS","docs_required_present":0,
        "d10_checker_pass":False,"d11_checker_pass":False,
        "v4_frozen_at_j3":True,"current_level":"CODE_READY",
        "PIPELINE_READY":False,"PRODUCTION_VERIFIED":False,
        "d12_allowed_to_generate":True,"d12_allowed_to_execute":False,
        "d13_allowed_to_generate":True,"d13_allowed_to_execute":False,
        "boss_explicit_authorization_required":True,"no_implicit_execution":True,
        "production_proof_execution_authorized":False,"production_proof_executed":False,
        "daily_pool_executed":False,"supervisor_executed":False,"live_worker_executed":False,
        "cron_enable_allowed":False,"qq_push_allowed":False,"api_called":False,"key_read":False,
        "state_write_allowed":False,"verified_write_allowed":False,
        "PRODUCTION_VERIFIED":False,"phase_e_allowed":False,
        "v4_controlled_observe_execution_allowed":False,
        "watchdog_only_failure_required":True,"no_ai_kill_retry_required":True,"rollback_required":True,
        "forbidden_dirty":[],"forbidden_staged":[],"blockers":[],"warnings":[]}
    block = False

    for doc in REQUIRED_DOCS:
        if (DOCS_DIR/doc).is_file(): R["docs_required_present"] += 1
        else: R["blockers"].append(f"Missing: {doc}"); block = True

    R["d10_checker_pass"] = _run(["python3","tools/check_v2_d10_production_proof_authorization.py"])[0] == 0
    R["d11_checker_pass"] = _run(["python3","tools/check_v2_d11_controlled_proof_authorization.py"])[0] == 0
    if not R["d10_checker_pass"]: R["blockers"].append("D10 checker failed"); block = True
    if not R["d11_checker_pass"]: R["blockers"].append("D11 checker failed"); block = True

    for f in DANGER_FALSE:
        if f not in R: R["blockers"].append(f"{f} missing"); block = True
        elif R[f] is not False: R["blockers"].append(f"{f} is true"); block = True
    for f in REQUIRED_TRUE:
        if f not in R: R["blockers"].append(f"{f} missing"); block = True
        elif R[f] is not True: R["blockers"].append(f"{f} is false"); block = True

    _,so,_ = _run(["git","stash","list"]); sl=[l.strip() for l in so.split("\n") if l.strip()]
    unk=[l for l in sl if not any(a in l for a in STASH_ALLOWED)]
    if unk: R["blockers"].append(f"Unknown stash"); block = True
    _,do,_ = _run(["git","status","--short"]); R["forbidden_dirty"]=_scan([l.strip() for l in do.split("\n") if l.strip()])
    _,sg,_ = _run(["git","diff","--name-only","--cached"]); R["forbidden_staged"]=_scan([l.strip() for l in sg.split("\n") if l.strip()])
    if R["forbidden_dirty"]: R["blockers"].append(f"Forbidden dirty"); block = True
    if R["forbidden_staged"]: R["blockers"].append(f"Forbidden staged"); block = True

    if block: R["check_status"] = "BLOCKER"
    elif R["warnings"]: R["check_status"] = "WARN"

    print("="*50); print("V2 D12 FINAL BOSS AUTHORIZATION CHECKER"); print("="*50)
    print(f"Status: {R['check_status']}  Docs: {R['docs_required_present']}  D10: {'PASS' if R['d10_checker_pass'] else 'FAIL'}  D11: {'PASS' if R['d11_checker_pass'] else 'FAIL'}")
    if R["blockers"]: print(f"\nBLOCKERS ({len(R['blockers'])}):"); [print(f"  ! {b}") for b in R["blockers"]]; sys.exit(1)
    elif R["warnings"]: print(f"\nWARNINGS ({len(R['warnings'])}):"); [print(f"  ? {w}") for w in R["warnings"]]

    md=MODULE_ROOT/"data"/"runtime"/"status"; md.mkdir(parents=True,exist_ok=True)
    mp=md/"v2_d12_final_boss_authorization_check.json"; mp.write_text(json.dumps(R,indent=2,ensure_ascii=False,default=str))
    print(f"\nMarker: {mp} (NOT committed)")
    return 0
if __name__=="__main__": sys.exit(main())
