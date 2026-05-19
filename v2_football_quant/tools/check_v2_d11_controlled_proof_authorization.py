#!/usr/bin/env python3
"""V2 D11.2: Controlled Proof Authorization Checker (Strict Header + Full Flag Blocker)"""
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

REQUIRED_MATRIX_HEADERS = [
    "proof_id", "current_status", "execution_authorization_status",
    "execution_allowed_now", "command_draft_exists", "runner_exists",
    "required_preconditions", "stop_conditions",
    "rollback_required", "watchdog_only_failure_required",
    "no_ai_kill_retry_required", "evidence_required_after_execution",
    "allowed_to_mark_proven_now",
]

HEADER_ALIASES = {
    "status": "current_status", "exec_auth": "execution_authorization_status",
    "exec_now": "execution_allowed_now", "command_exists": "command_draft_exists",
    "preconditions": "required_preconditions", "stop_gate": "stop_conditions",
    "rollback": "rollback_required", "watchdog": "watchdog_only_failure_required",
    "no_ai_kill": "no_ai_kill_retry_required", "evidence_req": "evidence_required_after_execution",
    "mark_proven": "allowed_to_mark_proven_now", "runner": "runner_exists",
}

DANGER_FALSE = ["d11_allowed_to_execute","d12_allowed_to_execute",
    "production_proof_execution_authorized","production_proof_executed",
    "daily_pool_executed","supervisor_executed","live_worker_executed",
    "cron_enable_allowed","qq_push_allowed","api_called","key_read",
    "state_write_allowed","verified_write_allowed","PRODUCTION_VERIFIED",
    "phase_e_allowed","v4_controlled_observe_execution_allowed"]

REQUIRED_TRUE = ["d11_allowed_to_generate","d12_allowed_to_generate",
    "v4_frozen_at_j3"]

MATRIX_REQUIRED_TRUE_FLAGS = [
    "all_six_targets_present",
    "all_six_targets_unproven",
    "all_six_execution_authorization_review_only",
    "all_six_execution_allowed_now_false",
    "all_six_command_draft_exists",
    "all_six_runner_status_recorded",
    "all_six_rollback_required",
    "all_six_watchdog_required",
    "all_six_no_ai_kill_retry_required",
    "all_six_allowed_to_mark_proven_now_false",
    "all_six_preconditions_present",
    "all_six_stop_conditions_present",
    "all_six_evidence_present",
]

STASH_ALLOWED = ["phase-d101","phase-v4a1","phase-d87"]
FORBIDDEN = ["data/runtime","data/state","data/paper_trading",".xlsx",".xls",
    "engine/net_utils.py","nowscore_h2h.js","secret",".env","token","key",
    "verified","route_marker","sent_marker","lock"]

def _run(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or str(MODULE_ROOT), timeout=60)
    return r.returncode, r.stdout.strip(), r.stderr.strip()
def _scan(paths): return [p for p in paths for pat in FORBIDDEN if pat in p]

def _resolve_header_name(h):
    """Resolve header alias to canonical name."""
    k = h.lower().replace(" ", "_")
    return HEADER_ALIASES.get(k, k)

def _parse_matrix():
    mx = {"targets": {}, "missing_headers": [], "header_complete": False, "malformed": []}
    m = DOCS_DIR / "V2_D11_SIX_PROOF_EXECUTION_AUTHORIZATION_MATRIX.md"
    if not m.is_file(): mx["malformed"].append("not_found"); return mx
    txt = m.read_text(); hf = False; ci = {}  # ci: canonical_name → column_index
    for line in txt.split("\n"):
        line = line.strip()
        if not line.startswith("|"): continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if not cols: continue
        if not hf and any("proof_id" in c for c in cols):
            hf = True
            for i, c in enumerate(cols):
                canonical = _resolve_header_name(c)
                if "proof_id" in canonical or canonical in REQUIRED_MATRIX_HEADERS + ["#"]:
                    ci[canonical] = i
            # Verify all required headers present
            mx["missing_headers"] = [h for h in REQUIRED_MATRIX_HEADERS if h not in ci]
            mx["header_complete"] = len(mx["missing_headers"]) == 0
            continue
        if not hf or not ci: continue
        if cols[0] == "---" or all(c.startswith("-") for c in cols if c): continue

        pi = ci.get("proof_id")
        if pi is None or pi >= len(cols): mx["malformed"].append(f"no_proof_id_col"); continue
        pid = cols[pi]
        if not pid or pid.isdigit() or pid == "proof_id": continue

        # Check all required columns present
        max_needed = max(ci.values()) if ci else 11
        if len(cols) <= max_needed:
            mx["malformed"].append(f"{pid}: {len(cols)} cols (need >{max_needed})"); continue

        def _f(h, d=""):
            idx = ci.get(h)
            return cols[idx] if idx is not None and idx < len(cols) else d

        mx["targets"][pid] = {
            "current_status": _f("current_status"),
            "exec_auth_status": _f("execution_authorization_status"),
            "execution_allowed_now": _f("execution_allowed_now"),
            "command_draft_exists": _f("command_draft_exists"),
            "runner_exists": _f("runner_exists"),
            "required_preconditions": _f("required_preconditions"),
            "stop_conditions": _f("stop_conditions"),
            "rollback_required": _f("rollback_required"),
            "watchdog_required": _f("watchdog_only_failure_required"),
            "no_ai_kill_required": _f("no_ai_kill_retry_required"),
            "evidence_required": _f("evidence_required_after_execution"),
            "allowed_to_mark_proven": _f("allowed_to_mark_proven_now"),
        }
    return mx


def main():
    R = {"check_status": "PASS", "docs_required_present": 0,
        "d10_checker_pass": False, "v4_frozen_at_j3": True,
        "d11_allowed_to_generate": True, "d11_allowed_to_execute": False,
        "d12_allowed_to_generate": True, "d12_allowed_to_execute": False,
        "production_proof_execution_authorized": False, "production_proof_executed": False,
        "daily_pool_executed": False, "supervisor_executed": False, "live_worker_executed": False,
        "cron_enable_allowed": False, "qq_push_allowed": False, "api_called": False, "key_read": False,
        "state_write_allowed": False, "verified_write_allowed": False,
        "PRODUCTION_VERIFIED": False, "phase_e_allowed": False,
        "v4_controlled_observe_execution_allowed": False,
        # Matrix header
        "required_headers": REQUIRED_MATRIX_HEADERS, "d11_missing_headers": [],
        "d11_matrix_header_fields_complete": False, "d11_malformed_rows": [],
        # Matrix flags
        "d11_proof_targets_count": 0, "d11_parsed_proof_ids": [],
        "d11_missing_proof_ids": [], "per_target_validation": {},
        "matrix_required_true_flags_count": len(MATRIX_REQUIRED_TRUE_FLAGS),
        "matrix_required_true_flags_blocker_enforced": 0,
        "matrix_required_true_flags_missing": [], "all_matrix_flags_blocker_enforced": False,
        "forbidden_dirty": [], "forbidden_staged": [],
        "matrix_required_true_flags_unique_count": 0, "matrix_required_true_flags_expected_count": 13, "matrix_required_true_flags_duplicate_items": [], "blockers": [], "warnings": []}
    block = False

    for doc in REQUIRED_DOCS:
        if (DOCS_DIR / doc).is_file(): R["docs_required_present"] += 1
        else: R["blockers"].append(f"Missing: {doc}"); block = True

    # D10 checker
    rc, _, _ = _run(["python3", "tools/check_v2_d10_production_proof_authorization.py"])
    R["d10_checker_pass"] = rc == 0
    if not R["d10_checker_pass"]: R["blockers"].append("D10 checker failed"); block = True

    # Matrix parser
    mx = _parse_matrix()
    R["d11_matrix_header_fields_complete"] = mx["header_complete"]
    R["d11_missing_headers"] = mx["missing_headers"]
    R["d11_malformed_rows"] = mx["malformed"]
    if not mx["header_complete"]:
        R["blockers"].append(f"Matrix header missing: {mx['missing_headers']}"); block = True
    if mx["malformed"]:
        R["blockers"].append(f"Malformed rows: {mx['malformed']}"); block = True

    R["d11_proof_targets_count"] = len(mx["targets"])
    R["d11_parsed_proof_ids"] = sorted(mx["targets"].keys())
    R["d11_missing_proof_ids"] = [t for t in SIX_PROOF_TARGETS if t not in mx["targets"]]
    R["all_six_targets_present"] = len(R["d11_missing_proof_ids"]) == 0
    if not R["all_six_targets_present"]:
        R["blockers"].append(f"Missing targets: {R['d11_missing_proof_ids']}"); block = True

    # Per-target full validation
    pv = {}
    flags = {f: True for f in MATRIX_REQUIRED_TRUE_FLAGS}
        ("all_six_targets_unproven", "unproven"),
        ("all_six_execution_authorization_review_only", "exec_auth_ro"),
        ("all_six_execution_allowed_now_false", "exec_now_false"),
        ("all_six_command_draft_exists", "cmd_exists"),
        ("all_six_rollback_required", "rollback"),
        ("all_six_watchdog_required", "watchdog"),
        ("all_six_no_ai_kill_retry_required", "no_ai"),
        ("all_six_allowed_to_mark_proven_now_false", "mark_proven"),
        ("all_six_preconditions_present", "precond"),
        ("all_six_stop_conditions_present", "stop"),
        ("all_six_evidence_present", "ev"),
    ]

    for t in SIX_PROOF_TARGETS:
        td = mx["targets"].get(t, {})
        v = {"proof_id": t}
        v["current_status_unproven"] = td.get("current_status", "?") == "UNPROVEN"
        v["exec_auth_review_only"] = td.get("exec_auth_status", "?") == "REVIEW_ONLY"
        v["execution_allowed_now_false"] = td.get("execution_allowed_now", "true") == "false"
        v["command_draft_exists_true"] = td.get("command_draft_exists", "false") == "true"
        v["runner_recorded"] = bool(td.get("runner_exists","")) and td.get("runner_exists","") in ["true","false","unknown","NOT_EXECUTABLE_UNTIL_RUNNER_DEFINED"]
        v["rollback_required_true"] = td.get("rollback_required", "false") == "true"
        v["watchdog_required_true"] = td.get("watchdog_required", "false") == "true"
        v["no_ai_kill_required_true"] = td.get("no_ai_kill_required", "false") == "true"
        v["mark_proven_false"] = td.get("allowed_to_mark_proven", "true") == "false"
        v["preconditions_present"] = bool(td.get("required_preconditions", ""))
        v["stop_conditions_present"] = bool(td.get("stop_conditions", ""))
        v["evidence_present"] = bool(td.get("evidence_required", ""))

        # Accumulate flags — any target failing makes the flag False
        if not v["current_status_unproven"]: flags["all_six_targets_unproven"] = False
        if not v["exec_auth_review_only"]: flags["all_six_execution_authorization_review_only"] = False
        if not v["execution_allowed_now_false"]: flags["all_six_execution_allowed_now_false"] = False
        if not v["command_draft_exists_true"]: flags["all_six_command_draft_exists"] = False
        if not v["runner_recorded"]: flags["all_six_runner_status_recorded"] = False
        if not v["rollback_required_true"]: flags["all_six_rollback_required"] = False
        if not v["watchdog_required_true"]: flags["all_six_watchdog_required"] = False
        if not v["no_ai_kill_required_true"]: flags["all_six_no_ai_kill_retry_required"] = False
        if not v["mark_proven_false"]: flags["all_six_allowed_to_mark_proven_now_false"] = False
        if not v["preconditions_present"]: flags["all_six_preconditions_present"] = False
        if not v["stop_conditions_present"]: flags["all_six_stop_conditions_present"] = False
        if not v["evidence_present"]: flags["all_six_evidence_present"] = False
        pv[t] = v

    R["per_target_validation"] = pv
    for fk, fv in flags.items():
        R[fk] = fv

    # ALL matrix flags BLOCKER-gated
    enforced = 0; missing_flags = []
    for flag in MATRIX_REQUIRED_TRUE_FLAGS:
        if flag not in R:
            missing_flags.append(flag)
        elif R[flag] is not True:
            R["blockers"].append(f"Matrix flag {flag} is not True")
            block = True
        else:
            enforced += 1
    unique = list(set(MATRIX_REQUIRED_TRUE_FLAGS))
    R["matrix_required_true_flags_unique_count"] = len(unique)
    R["matrix_required_true_flags_expected_count"] = 13
    R["matrix_required_true_flags_duplicate_items"] = [x for x in set(MATRIX_REQUIRED_TRUE_FLAGS) if MATRIX_REQUIRED_TRUE_FLAGS.count(x) > 1]
    if R["matrix_required_true_flags_duplicate_items"]:
        R["blockers"].append(f"Duplicate matrix flags: {R['matrix_required_true_flags_duplicate_items']}")
        block = True
    if len(unique) != 13:
        R["blockers"].append(f"Matrix flags unique count {len(unique)} != 13")
        block = True
    R["matrix_required_true_flags_blocker_enforced"] = enforced
    R["matrix_required_true_flags_missing"] = missing_flags
    R["all_matrix_flags_blocker_enforced"] = enforced == len(MATRIX_REQUIRED_TRUE_FLAGS)
    if missing_flags:
        R["blockers"].append(f"Matrix flags missing: {missing_flags}"); block = True

    # Permission blocker
    for f in DANGER_FALSE:
        if f not in R: R["blockers"].append(f"{f} missing"); block = True
        elif R[f] is not False: R["blockers"].append(f"{f} is true"); block = True
    for f in REQUIRED_TRUE:
        if f not in R: R["blockers"].append(f"{f} missing"); block = True
        elif R[f] is not True: R["blockers"].append(f"{f} is false"); block = True

    # Stash/dirty/staged
    _, so, _ = _run(["git", "stash", "list"])
    sl = [l.strip() for l in so.split("\n") if l.strip()]
    unk = [l for l in sl if not any(a in l for a in STASH_ALLOWED)]
    if unk: R["blockers"].append(f"Unknown stashes: {unk}"); block = True
    _, do, _ = _run(["git", "status", "--short"]); R["forbidden_dirty"] = _scan([l.strip() for l in do.split("\n") if l.strip()])
    _, sgo, _ = _run(["git", "diff", "--name-only", "--cached"]); R["forbidden_staged"] = _scan([l.strip() for l in sgo.split("\n") if l.strip()])
    if R["forbidden_dirty"]: R["blockers"].append(f"Forbidden dirty"); block = True
    if R["forbidden_staged"]: R["blockers"].append(f"Forbidden staged"); block = True

    if block: R["check_status"] = "BLOCKER"
    elif R["warnings"]: R["check_status"] = "WARN"

    print("=" * 50); print("V2 D11.2 MATRIX HEADER & FLAG BLOCKER CHECKER"); print("=" * 50)
    print(f"Status: {R['check_status']}  Docs: {R['docs_required_present']}  D10: {'PASS' if R['d10_checker_pass'] else 'FAIL'}")
    for k in ["d11_matrix_header_fields_complete", "d11_missing_headers", "d11_proof_targets_count",
        "all_six_targets_present", "all_matrix_flags_blocker_enforced",
        "matrix_required_true_flags_blocker_enforced",
        "d11_allowed_to_execute", "d12_allowed_to_execute",
        "forbidden_dirty", "forbidden_staged"]: print(f"  {k}: {R.get(k, '?')}")
    if R["blockers"]: print(f"\nBLOCKERS ({len(R['blockers'])}):"); [print(f"  ! {b}") for b in R["blockers"]]; sys.exit(1)
    elif R["warnings"]: print(f"\nWARNINGS ({len(R['warnings'])}):"); [print(f"  ? {w}") for w in R["warnings"]]

    md = MODULE_ROOT / "data" / "runtime" / "status"; md.mkdir(parents=True, exist_ok=True)
    mp = md / "v2_d11_controlled_proof_authorization_check.json"
    mp.write_text(json.dumps(R, indent=2, ensure_ascii=False, default=str))
    print(f"\nMarker: {mp} (NOT committed)")
    return 0
if __name__ == "__main__": sys.exit(main())
