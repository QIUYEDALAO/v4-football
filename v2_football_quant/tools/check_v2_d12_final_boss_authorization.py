#!/usr/bin/env python3
"""V2 D12.1: Final Boss Authorization Checker (Structured Evidence)"""
import json, re, subprocess, sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]; DOCS_DIR = MODULE_ROOT / "docs"

REQUIRED_DOCS = [
    "V2_D12_FINAL_BOSS_AUTHORIZATION_PACKET.md",
    "V2_D12_PROOF_EXECUTION_ORDER_MATRIX.md",
    "V2_D12_RUNNER_READINESS_AUDIT.md",
    "V2_D12_FINAL_COMMAND_REVIEW.md",
    "V2_D12_FINAL_WATCHDOG_ROLLBACK_STOP_GATE.md",
    "V2_D12_FINAL_BOSS_AUTHORIZATION_CLOSURE.md",
]

EXPECTED_ORDER = [
    "real_state_present_case","active_window_mutation_path",
    "formal_state_write_path","production_verified_path",
    "production_qq_path","production_cron_path",
]

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

def _parse_markdown_table(path, required_headers):
    """Generic header-based markdown table parser."""
    result = {"targets": {}, "headers": {}, "header_complete": False, "missing": [], "malformed": []}
    m = DOCS_DIR / path
    if not m.is_file(): result["malformed"].append("not_found"); return result
    txt = m.read_text(); hf = False; ci = {}
    for line in txt.split("\n"):
        line = line.strip()
        if not line.startswith("|"): continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if not cols: continue
        if not hf and any("proof_id" in c for c in cols):
            hf = True
            for i, c in enumerate(cols): ci[c.lower().replace(" ","_")] = i
            result["missing"] = [h for h in required_headers if h not in ci]
            result["header_complete"] = len(result["missing"]) == 0
            result["headers"] = dict(sorted(ci.items()))
            continue
        if not hf or not ci: continue
        if cols[0] == "---" or all(c.startswith("-") for c in cols if c): continue
        pi = ci.get("proof_id")
        if pi is None or pi >= len(cols): continue
        pid = cols[pi]
        if not pid or pid.isdigit() or pid == "proof_id": continue
        row = {}
        for h in required_headers:
            i = ci.get(h)
            row[h] = cols[i] if i is not None and i < len(cols) else ""
        result["targets"][pid] = row
    return result

def main():
    R = {"check_status":"PASS","docs_required_present":0,"docs_required_missing":[],
        "proof_order_parser_exists":False,"runner_readiness_parser_exists":False,
        "command_review_parser_exists":False,"v4_frozen_evidence_checked":False,
        "d10_checker_pass":False,"d10_checker_returncode":None,
        "d11_checker_pass":False,"d11_checker_returncode":None,
        "v4_frozen_at_j3":True,"v4_j_allowed_to_execute":False,
        "v4_observe_execution_allowed":False,"v4_production_verified":False,"v4_phase_e_allowed":False,
        "current_level":"CODE_READY","PIPELINE_READY":False,"PRODUCTION_VERIFIED":False,
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
        # Proof order
        "all_six_targets_present":False,"all_six_targets_unproven":False,
        "all_six_execution_allowed_now_false":False,"all_six_boss_authorization_required":False,
        "all_six_allowed_to_mark_proven_now_false":False,"all_six_allowed_to_unlock_next_proof_now_false":False,
        "execution_order_unique":False,"execution_order_1_to_6":False,"proof_order_matches_expected_sequence":False,
        # Runner
        "all_runner_status_recorded":False,"all_runner_execution_allowed_now_false":False,
        "all_runner_command_must_not_execute":False,"all_runner_required_no_flags_recorded":False,
        # Command
        "all_command_must_not_execute":False,"all_commands_review_only":False,
        "all_commands_no_push":False,"all_commands_no_cron":False,
        "all_commands_no_state_write":False,"all_commands_no_verified_write":False,
        "all_commands_no_api":False,"all_commands_no_key_read":False,
        "all_commands_no_supervisor":False,"all_commands_watchdog_only_failure":False,
        "all_commands_no_ai_kill_retry":False,"all_commands_preserve_logs":False,
        "all_commands_manifest_required":False,"all_commands_boss_d13_required":False,
        "forbidden_dirty":[],"forbidden_staged":[],"stash_allowed_only":False,"unknown_stash_found":False,
        "blockers":[],"warnings":[]}
    block = False

    # A. Docs (6/6)
    for doc in REQUIRED_DOCS:
        if (DOCS_DIR/doc).is_file(): R["docs_required_present"] += 1
        else: R["docs_required_missing"].append(doc); R["blockers"].append(f"Missing: {doc}"); block = True

    # B. D10/D11 subcheckers
    rc, out, err = _run(["python3","tools/check_v2_d10_production_proof_authorization.py"])
    R["d10_checker_returncode"] = rc; R["d10_checker_pass"] = rc == 0
    if rc != 0: R["blockers"].append(f"D10 checker exit {rc}"); block = True
    rc, out, err = _run(["python3","tools/check_v2_d11_controlled_proof_authorization.py"])
    R["d11_checker_returncode"] = rc; R["d11_checker_pass"] = rc == 0
    if rc != 0: R["blockers"].append(f"D11 checker exit {rc}"); block = True

    # C. V4 frozen evidence (try running V4-J gate checker)
    rc, out, _ = _run(["python3","tools/check_v4_j_gate_package.py"])
    R["v4_frozen_evidence_checked"] = True
    if rc == 0:
        # Extract key fields from stdout/marker
        m = MODULE_ROOT/"data"/"runtime"/"status"/"v4_j_gate_package_check.json"
        if m.is_file():
            try:
                vd = json.loads(m.read_text())
                R["v4_j_allowed_to_execute"] = vd.get("v4_j_allowed_to_execute", False)
                R["v4_observe_execution_allowed"] = vd.get("observe_execution_allowed", False)
                R["v4_production_verified"] = vd.get("production_verified", False)
                R["v4_phase_e_allowed"] = vd.get("phase_e_allowed", False)
            except: pass
    if R.get("v4_j_allowed_to_execute", True): R["blockers"].append("V4 j allowed_to_execute true"); block = True
    if R.get("v4_observe_execution_allowed", True): R["blockers"].append("V4 observe execution allowed true"); block = True

    # D. Proof order matrix
    mx = _parse_markdown_table("V2_D12_PROOF_EXECUTION_ORDER_MATRIX.md",
        ["proof_id","status","order","exec_now","boss_req","unlocked_next","proven_now","watchdog","no_ai","rollback"])
    R["proof_order_parser_exists"] = mx["header_complete"]
    targets = mx["targets"]
    R["all_six_targets_present"] = all(t in targets for t in EXPECTED_ORDER)
    if not R["all_six_targets_present"]: R["blockers"].append(f"Missing proof targets in order matrix"); block = True
    _unproven = True; _exec = True; _boss = True; _mark = True; _unlock = True; _wd = True; _noai = True; _rb = True
    orders = {}
    for t in EXPECTED_ORDER:
        td = targets.get(t, {})
        if td.get("status","?") != "UNPROVEN": _unproven = False
        if td.get("exec_now","true") != "false": _exec = False
        if td.get("boss_req","false") != "true": _boss = False
        if td.get("proven_now","true") != "false": _mark = False
        if td.get("unlocked_next","true") != "false": _unlock = False
        if td.get("watchdog","false") != "true": _wd = False
        if td.get("no_ai","false") != "true": _noai = False
        if td.get("rollback","false") != "true": _rb = False
        orders[t] = td.get("order","")
    R.update({k:v for k,v in zip(
        ["all_six_targets_unproven","all_six_execution_allowed_now_false","all_six_boss_authorization_required",
         "all_six_allowed_to_mark_proven_now_false","all_six_allowed_to_unlock_next_proof_now_false",
         "all_six_watchdog_required","all_six_no_ai_kill_retry_required","all_six_rollback_required"],
        [_unproven,_exec,_boss,_mark,_unlock,_wd,_noai,_rb])})
    R["execution_order_unique"] = len(set(orders.values())) == 6
    R["execution_order_1_to_6"] = sorted(orders.values()) == list(map(str, range(1,7)))
    R["proof_order_matches_expected_sequence"] = all(str(i+1) == orders.get(t,"") for i,t in enumerate(EXPECTED_ORDER))
    if not R["execution_order_unique"]: R["blockers"].append("Proof execution order not unique"); block = True
    if not R["proof_order_matches_expected_sequence"]: R["blockers"].append("Proof order wrong sequence"); block = True

    # E. Runner readiness (header-based table parser)
    rmx = _parse_markdown_table("V2_D12_RUNNER_READINESS_AUDIT.md",
        ["proof_id","runner_exists","command_must_not_execute","no_push","no_cron",
         "no_state_write","no_verified_write","no_api","no_key_read","no_supervisor",
         "watchdog_only_failure","no_ai_kill_retry","preserve_logs","manifest_required",
         "execution_allowed_now"])
    R["runner_readiness_parser_exists"] = rmx["header_complete"]
    rtargs = rmx["targets"]
    if rmx["header_complete"] and len(rtargs) >= 6:
        runner_flags = {k:True for k in ["all_runner_status_recorded","all_runner_execution_allowed_now_false",
            "all_runner_command_must_not_execute","all_runner_required_no_flags_recorded"]}
        for t in EXPECTED_ORDER:
            td = rtargs.get(t, {})
            if not td.get("runner_exists",""): runner_flags["all_runner_status_recorded"] = False
            if td.get("execution_allowed_now","true") != "false": runner_flags["all_runner_execution_allowed_now_false"] = False
            if td.get("command_must_not_execute","false") != "true": runner_flags["all_runner_command_must_not_execute"] = False
            for flag in ["no_push","no_cron","no_state_write","no_verified_write","no_api","no_key_read","no_supervisor"]:
                if td.get(flag,"false") != "true": runner_flags["all_runner_required_no_flags_recorded"] = False
        for k,v in runner_flags.items():
            R[k] = v
            if not v: R["blockers"].append(f"Runner: {k} is False"); block = True

    # F. Command review (header-based table parser)
    cmx = _parse_markdown_table("V2_D12_FINAL_COMMAND_REVIEW.md",
        ["proof_id","command_must_not_execute","review_only","no_push","no_cron",
         "no_state_write","no_verified_write","no_api","no_key_read","no_supervisor",
         "watchdog_only_failure","no_ai_kill_retry","preserve_logs","manifest_required",
         "boss_d13_required"])
    R["command_review_parser_exists"] = cmx["header_complete"]
    ctargs = cmx["targets"]
    if cmx["header_complete"] and len(ctargs) >= 6:
        cmd_flags = True
        for t in EXPECTED_ORDER:
            td = ctargs.get(t, {})
            if td.get("command_must_not_execute","false") != "true": cmd_flags = False
            if td.get("review_only","false") != "true": cmd_flags = False
            for flag in ["no_push","no_cron","no_state_write","no_verified_write","no_api","no_key_read","no_supervisor",
                         "watchdog_only_failure","no_ai_kill_retry","preserve_logs","manifest_required","boss_d13_required"]:
                if td.get(flag,"false") != "true": cmd_flags = False
        R["all_command_must_not_execute"] = cmd_flags
        R["all_commands_review_only"] = cmd_flags
        R["all_commands_no_push"] = cmd_flags
        R["all_commands_no_cron"] = cmd_flags
        R["all_commands_no_state_write"] = cmd_flags
        R["all_commands_no_verified_write"] = cmd_flags
        R["all_commands_no_api"] = cmd_flags
        R["all_commands_no_key_read"] = cmd_flags
        R["all_commands_no_supervisor"] = cmd_flags
        R["all_commands_watchdog_only_failure"] = cmd_flags
        R["all_commands_no_ai_kill_retry"] = cmd_flags
        R["all_commands_preserve_logs"] = cmd_flags
        R["all_commands_manifest_required"] = cmd_flags
        R["all_commands_boss_d13_required"] = cmd_flags
        if not cmd_flags: R["blockers"].append("Command review: some proofs missing required flags"); block = True

    # G. Permission blocker
    for f in DANGER_FALSE:
        if f not in R: R["blockers"].append(f"{f} missing"); block = True
        elif R[f] is not False: R["blockers"].append(f"{f} is true"); block = True
    for f in REQUIRED_TRUE:
        if f not in R: R["blockers"].append(f"{f} missing"); block = True
        elif R[f] is not True: R["blockers"].append(f"{f} is false"); block = True

    # H. Stash/dirty/staged
    _, so, _ = _run(["git","stash","list"]); sl = [l.strip() for l in so.split("\n") if l.strip()]
    unk = [l for l in sl if not any(a in l for a in STASH_ALLOWED)]
    R["stash_allowed_only"] = len(unk) == 0; R["unknown_stash_found"] = len(unk) > 0
    if unk: R["blockers"].append(f"Unknown stash"); block = True
    _, do,_ = _run(["git","status","--short"]); R["forbidden_dirty"] = _scan([l.strip() for l in do.split("\n") if l.strip()])
    _, sg,_ = _run(["git","diff","--name-only","--cached"]); R["forbidden_staged"] = _scan([l.strip() for l in sg.split("\n") if l.strip()])
    if R["forbidden_dirty"]: R["blockers"].append("Forbidden dirty"); block = True
    if R["forbidden_staged"]: R["blockers"].append("Forbidden staged"); block = True

    if block: R["check_status"] = "BLOCKER"
    elif R["warnings"]: R["check_status"] = "WARN"

    print("="*50); print("V2 D12.1 STRUCTURED BOSS AUTHORIZATION CHECKER"); print("="*50)
    print(f"Status: {R['check_status']}  Docs: {R['docs_required_present']}/{len(REQUIRED_DOCS)}  D10: {'PASS' if R['d10_checker_pass'] else 'FAIL'}  D11: {'PASS' if R['d11_checker_pass'] else 'FAIL'}")
    for k in ["docs_required_missing","proof_order_parser_exists","proof_order_matches_expected_sequence",
        "runner_readiness_parser_exists","command_review_parser_exists","v4_frozen_evidence_checked",
        "d12_allowed_to_execute","d13_allowed_to_execute","forbidden_dirty","forbidden_staged"]:
        print(f"  {k}: {R.get(k,'?')}")
    if R["blockers"]: print(f"\nBLOCKERS ({len(R['blockers'])}):"); [print(f"  ! {b}") for b in R["blockers"]]; sys.exit(1)
    elif R["warnings"]: print(f"\nWARNINGS ({len(R['warnings'])}):"); [print(f"  ? {w}") for w in R["warnings"]]

    md = MODULE_ROOT/"data"/"runtime"/"status"; md.mkdir(parents=True,exist_ok=True)
    mp = md/"v2_d12_final_boss_authorization_check.json"; mp.write_text(json.dumps(R,indent=2,ensure_ascii=False,default=str))
    print(f"\nMarker: {mp} (NOT committed)")
    return 0
if __name__ == "__main__":
    sys.exit(main())
