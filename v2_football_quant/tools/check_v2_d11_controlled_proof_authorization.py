#!/usr/bin/env python3
"""V2 D11.1: Controlled Proof Authorization Checker (Matrix Parser)"""
import json, subprocess, sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]; DOCS_DIR = MODULE_ROOT / "docs"

REQUIRED_DOCS = [
    "V2_D11_CONTROLLED_PROOF_EXECUTION_AUTHORIZATION_PACKET.md",
    "V2_D11_SIX_PROOF_EXECUTION_AUTHORIZATION_MATRIX.md",
    "V2_D11_CONTROLLED_PROOF_COMMAND_REVIEW.md",
    "V2_D11_WATCHDOG_ROLLBACK_STOP_GATE.md",
    "V2_D11_CONTROLLED_PROOF_AUTHORIZATION_CLOSURE.md",
]

SIX_PROOF_TARGETS = [
    "real_state_present_case", "active_window_mutation_path",
    "production_cron_path", "production_qq_path",
    "production_verified_path", "formal_state_write_path",
]

DANGER_FALSE = ["d11_allowed_to_execute","d12_allowed_to_execute",
    "production_proof_execution_authorized","production_proof_executed",
    "daily_pool_executed","supervisor_executed","live_worker_executed",
    "cron_enable_allowed","qq_push_allowed","api_called","key_read",
    "state_write_allowed","verified_write_allowed","PRODUCTION_VERIFIED",
    "phase_e_allowed","v4_controlled_observe_execution_allowed"]

REQUIRED_TRUE = ["d11_allowed_to_generate","d12_allowed_to_generate",
    "v4_frozen_at_j3","watchdog_only_failure_required",
    "no_ai_kill_retry_required","rollback_required"]

STASH_ALLOWED = ["phase-d101","phase-v4a1","phase-d87"]
FORBIDDEN = ["data/runtime","data/state","data/paper_trading",".xlsx",".xls",
    "engine/net_utils.py","nowscore_h2h.js","secret",".env","token","key",
    "verified","route_marker","sent_marker","lock"]

def _run(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or str(MODULE_ROOT), timeout=60)
    return r.returncode, r.stdout.strip(), r.stderr.strip()
def _scan(paths): return [p for p in paths for pat in FORBIDDEN if pat in p]

def _parse_matrix():
    mx = {"headers":{}, "targets":{}, "missing_headers":[], "header_complete":False, "malformed":[]}
    m = DOCS_DIR/"V2_D11_SIX_PROOF_EXECUTION_AUTHORIZATION_MATRIX.md"
    if not m.is_file(): mx["malformed"].append("not_found"); return mx
    txt=m.read_text(); hf=False; ci={}
    for line in txt.split("\n"):
        line=line.strip()
        if not line.startswith("|"): continue
        cols=[c.strip() for c in line.split("|")[1:-1]]
        if not cols: continue
        if not hf and any("proof_id" in c for c in cols):
            hf=True
            for i,c in enumerate(cols): ci[c.lower().replace(" ","_")]=i
            mx["headers"]=dict(sorted(ci.items()))
            mx["header_complete"]=len(ci)>=12
            mx["missing_headers"]=[]
            continue
        if not hf or not ci: continue
        if cols[0]=="---" or all(c.startswith("-") for c in cols if c): continue
        pi=ci.get("proof_id")
        if pi is None or pi>=len(cols): continue
        pid=cols[pi]
        if not pid or pid.isdigit() or pid=="proof_id": continue
        if len(cols) < 10: mx["malformed"].append(f"{pid}: {len(cols)} cols"); continue
        def _f(h,d=""): i=ci.get(h); return cols[i] if i is not None and i<len(cols) else d
        mx["targets"][pid]={
            "current_status":_f("status"),
            "exec_authorization_status":_f("exec_auth"),
            "execution_allowed_now":_f("exec_now"),
            "command_draft_exists":_f("command_exists"),
            "runner_exists":_f("runner"),
            "required_preconditions":_f("preconditions"),
            "stop_conditions":_f("stop_gate"),
            "rollback_required":_f("rollback"),
            "watchdog_required":_f("watchdog"),
            "no_ai_kill_required":_f("no_ai_kill"),
            "evidence_required":_f("evidence_req"),
            "allowed_to_mark_proven":_f("mark_proven"),
        }
    return mx

def main():
    R = {"check_status":"PASS","docs_required_present":0,
        "d10_checker_pass":False,"v4_frozen_at_j3":True,
        "current_level":"CODE_READY","PIPELINE_READY":False,
        "d11_allowed_to_generate":True,"d11_allowed_to_execute":False,
        "d12_allowed_to_generate":True,"d12_allowed_to_execute":False,
        "production_proof_execution_authorized":False,"production_proof_executed":False,
        "daily_pool_executed":False,"supervisor_executed":False,"live_worker_executed":False,
        "cron_enable_allowed":False,"qq_push_allowed":False,"api_called":False,"key_read":False,
        "state_write_allowed":False,"verified_write_allowed":False,
        "PRODUCTION_VERIFIED":False,"phase_e_allowed":False,
        "v4_controlled_observe_execution_allowed":False,
        "watchdog_only_failure_required":True,"no_ai_kill_retry_required":True,"rollback_required":True,
        # Matrix parse fields
        "d11_matrix_header_fields_complete":False,"d11_missing_headers":[],"d11_proof_targets_count":0,
        "d11_parsed_proof_ids":[],"d11_missing_proof_ids":[],"d11_malformed_rows":[],
        "all_six_targets_present":False,"all_six_targets_unproven":False,
        "all_six_execution_authorization_review_only":False,"all_six_execution_allowed_now_false":False,
        "all_six_command_draft_exists":False,"all_six_rollback_required":False,
        "all_six_watchdog_required":False,"all_six_no_ai_kill_retry_required":False,
        "all_six_allowed_to_mark_proven_now_false":False,"all_six_preconditions_present":False,
        "all_six_stop_conditions_present":False,"all_six_evidence_present":False,
        "forbidden_dirty":[],"forbidden_staged":[],"blockers":[],"warnings":[]}
    block = False

    # A. Docs
    for doc in REQUIRED_DOCS:
        if (DOCS_DIR/doc).is_file(): R["docs_required_present"] += 1
        else: R["blockers"].append(f"Missing: {doc}"); block = True

    # B. D10 checker
    rc,_,_ = _run(["python3","tools/check_v2_d10_production_proof_authorization.py"])
    R["d10_checker_pass"] = rc == 0
    if not R["d10_checker_pass"]: R["blockers"].append("D10 checker failed"); block = True

    # C. Matrix parser (structured)
    mx = _parse_matrix()
    R["d11_matrix_header_fields_complete"] = mx["header_complete"]
    R["d11_missing_headers"] = mx["missing_headers"]
    R["d11_malformed_rows"] = mx["malformed"]
    R["d11_proof_targets_count"] = len(mx["targets"])
    R["d11_parsed_proof_ids"] = sorted(mx["targets"].keys())
    R["d11_missing_proof_ids"] = [t for t in SIX_PROOF_TARGETS if t not in mx["targets"]]
    R["all_six_targets_present"] = len(R["d11_missing_proof_ids"]) == 0
    if not R["all_six_targets_present"]:
        R["blockers"].append(f"Missing targets: {R['d11_missing_proof_ids']}"); block = True

    flags = {"unproven":True,"exec_auth_ro":True,"exec_now":True,"cmd_exist":True,
        "rollback":True,"watchdog":True,"no_ai":True,"mark_proven":True,
        "precond":True,"stop":True,"ev":True}
    flag_map = {"unproven":"all_six_targets_unproven","exec_auth_ro":"all_six_execution_authorization_review_only",
        "exec_now":"all_six_execution_allowed_now_false","cmd_exist":"all_six_command_draft_exists",
        "rollback":"all_six_rollback_required","watchdog":"all_six_watchdog_required",
        "no_ai":"all_six_no_ai_kill_retry_required","mark_proven":"all_six_allowed_to_mark_proven_now_false",
        "precond":"all_six_preconditions_present","stop":"all_six_stop_conditions_present",
        "ev":"all_six_evidence_present"}
    for t in SIX_PROOF_TARGETS:
        td = mx["targets"].get(t, {})
        if td.get("current_status","?") != "UNPROVEN": flags["unproven"]=False
        if td.get("exec_authorization_status","?") != "REVIEW_ONLY": flags["exec_auth_ro"]=False
        if td.get("execution_allowed_now","true") != "false": flags["exec_now"]=False
        if td.get("command_draft_exists","false") != "true": flags["cmd_exist"]=False
        if td.get("rollback_required","false") != "true": flags["rollback"]=False
        if td.get("watchdog_required","false") != "true": flags["watchdog"]=False
        if td.get("no_ai_kill_required","false") != "true": flags["no_ai"]=False
        if td.get("allowed_to_mark_proven","true") != "false": flags["mark_proven"]=False
        if not td.get("required_preconditions",""): flags["precond"]=False
        if not td.get("stop_conditions",""): flags["stop"]=False
        if not td.get("evidence_required",""): flags["ev"]=False
    for k in flags:
        R[flag_map[k]] = flags[k]
    if not flags["unproven"]: R["blockers"].append("Some targets not UNPROVEN"); block = True
    if not flags["exec_now"]: R["blockers"].append("Some targets execution_allowed_now true"); block = True
    if not flags["mark_proven"]: R["blockers"].append("Some targets allowed_to_mark_proven_now true"); block = True

    # D. Permission blocker
    for f in DANGER_FALSE:
        if f not in R: R["blockers"].append(f"{f} missing"); block = True
        elif R[f] is not False: R["blockers"].append(f"{f} is true"); block = True
    for f in REQUIRED_TRUE:
        if f not in R: R["blockers"].append(f"{f} missing"); block = True
        elif R[f] is not True: R["blockers"].append(f"{f} is false"); block = True

    # E. Stash/dirty/staged
    _,so,_ = _run(["git","stash","list"]); sl=[l.strip() for l in so.split("\n") if l.strip()]
    unk=[l for l in sl if not any(a in l for a in STASH_ALLOWED)]
    if unk: R["blockers"].append(f"Unknown stashes: {unk}"); block = True
    _,do,_ = _run(["git","status","--short"]); R["forbidden_dirty"]=_scan([l.strip() for l in do.split("\n") if l.strip()])
    _,sgo,_ = _run(["git","diff","--name-only","--cached"]); R["forbidden_staged"]=_scan([l.strip() for l in sgo.split("\n") if l.strip()])
    if R["forbidden_dirty"]: R["blockers"].append(f"Forbidden dirty"); block = True
    if R["forbidden_staged"]: R["blockers"].append(f"Forbidden staged"); block = True

    if block: R["check_status"] = "BLOCKER"
    elif R["warnings"]: R["check_status"] = "WARN"

    print("="*50); print("V2 D11.1 CONTROLLED PROOF AUTHORIZATION CHECKER"); print("="*50)
    print(f"Status: {R['check_status']}  Docs: {R['docs_required_present']}  D10: {'PASS' if R['d10_checker_pass'] else 'FAIL'}")
    for k in ["d11_proof_targets_count","all_six_targets_present","all_six_targets_unproven",
        "all_six_execution_allowed_now_false","all_six_allowed_to_mark_proven_now_false",
        "d11_allowed_to_execute","d12_allowed_to_execute","production_proof_executed",
        "forbidden_dirty","forbidden_staged"]: print(f"  {k}: {R[k]}")
    if R["blockers"]: print(f"\nBLOCKERS ({len(R['blockers'])}):"); [print(f"  ! {b}") for b in R["blockers"]]; sys.exit(1)
    elif R["warnings"]: print(f"\nWARNINGS ({len(R['warnings'])}):"); [print(f"  ? {w}") for w in R["warnings"]]

    md = MODULE_ROOT/"data"/"runtime"/"status"; md.mkdir(parents=True,exist_ok=True)
    mp = md/"v2_d11_controlled_proof_authorization_check.json"
    mp.write_text(json.dumps(R,indent=2,ensure_ascii=False,default=str))
    print(f"\nMarker: {mp} (NOT committed)")
    return 0
if __name__=="__main__": sys.exit(main())
