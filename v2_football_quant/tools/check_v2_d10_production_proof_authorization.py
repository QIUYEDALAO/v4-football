#!/usr/bin/env python3
"""V2 D10.3: Full Matrix Field Validation Checker"""
import json, subprocess, sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = MODULE_ROOT / "docs"

REQUIRED_DOCS = [
    "V2_D10_PRODUCTION_PROOF_AUTHORIZATION_PACKET.md",
    "V2_D10_SIX_PROOF_EVIDENCE_MATRIX.md",
    "V2_D10_CONTROLLED_PROOF_COMMAND_DRAFTS.md",
    "V2_D10_PRODUCTION_PROOF_AUTHORIZATION_CLOSURE.md",
]
SIX_PROOF_TARGETS = [
    "real_state_present_case", "active_window_mutation_path",
    "production_cron_path", "production_qq_path",
    "production_verified_path", "formal_state_write_path",
]
REQUIRED_HEADERS = [
    "#", "proof_id", "proof_name", "current_status",
    "required_evidence", "allowed_action_now", "execution_allowed",
    "production_allowed", "production_risk", "blocker_if_missing",
    "command_draft_required", "proof_result_required_before_pipeline_ready",
]
VALID_RISKS = {"HIGH", "CRITICAL"}
FORBIDDEN_PATTERNS = [
    "data/runtime", "data/state", "data/paper_trading",
    ".xlsx", ".xls", "engine/net_utils.py", "nowscore_h2h.js",
    "secret", ".env", "token", "key",
    "verified", "route_marker", "sent_marker", "lock",
]
STASH_ALLOWED_MSGS = [
    "phase-d101 workspace isolation: nowscore scratch only",
    "phase-v4a1 workspace isolation: discipline archive residue only",
    "phase-d87 workspace isolation: net_utils only",
]

def _run(cmd, cwd=None): 
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or str(MODULE_ROOT), timeout=60)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def _parse_matrix():
    r = {"headers": {}, "targets": {}, "missing_headers": [], "extra_headers": [], 
         "malformed": [], "header_complete": False}
    m = DOCS_DIR / "V2_D10_SIX_PROOF_EVIDENCE_MATRIX.md"
    if not m.is_file(): r["malformed"].append("not_found"); return r
    
    txt = m.read_text(); header_found = False; col_index = {}
    for line in txt.split("\n"):
        line = line.strip()
        if not line.startswith("|"): continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if not cols: continue
        if not header_found and any("proof_id" in c for c in cols):
            header_found = True
            for i, c in enumerate(cols): col_index[c.lower().replace(" ", "_")] = i
            present = {c.lower().replace(" ", "_") for c in cols}
            required = {h.lower() for h in REQUIRED_HEADERS}
            r["missing_headers"] = sorted(required - present)
            r["extra_headers"] = sorted(present - required)
            r["headers"] = {k: v for k, v in sorted(col_index.items())}
            r["header_complete"] = len(r["missing_headers"]) == 0
            continue
        if not header_found or not col_index: continue
        if cols[0] == "---" or all(c.startswith("-") for c in cols if c): continue
        
        pid_idx = col_index.get("proof_id")
        if pid_idx is None or pid_idx >= len(cols): continue
        pid = cols[pid_idx]
        if not pid or pid.isdigit() or pid == "proof_id": continue
        if len(cols) < 12: r["malformed"].append(f"{pid}: {len(cols)} cols (need 12)"); continue
        
        def _f(h, d=""):
            idx = col_index.get(h); return cols[idx] if idx is not None and idx < len(cols) else d
        r["targets"][pid] = {
            "proof_id": pid, "proof_name": _f("proof_name"),
            "current_status": _f("current_status"),
            "required_evidence": _f("required_evidence"),
            "allowed_action_now": _f("allowed_action_now"),
            "execution_allowed": _f("execution_allowed"),
            "production_allowed": _f("production_allowed"),
            "production_risk": _f("production_risk"),
            "blocker_if_missing": _f("blocker_if_missing"),
            "command_draft_required": _f("command_draft_required"),
            "proof_result_required_before_pipeline_ready": _f("proof_result_required_before_pipeline_ready"),
        }
    return r

def _scan_forbidden(paths): return [p for p in paths for pat in FORBIDDEN_PATTERNS if pat in p]

def main():
    R = {"check_status": "PASS", "docs_required_present": 0,
         "matrix_header_fields_complete": False, "matrix_header_missing_fields": [],
         "matrix_business_fields_complete": False, "proof_targets_count": 0,
         "parsed_proof_ids": [], "missing_proof_ids": [], "malformed_rows": [],
         "per_target_validation": {},
         "all_six_targets_present": False, "all_six_targets_unproven": False,
         "all_six_required_evidence_present": False, "all_six_allowed_action_review_only": False,
         "all_six_execution_allowed_false": False, "all_six_production_allowed_false": False,
         "all_six_production_risk_valid": False, "all_six_blocker_if_missing_true": False,
         "all_six_command_draft_required_true": False, "all_six_proof_result_required_before_pipeline_ready": False,
         "d10_allowed_to_generate": True, "d10_allowed_to_execute": False,
         "d11_allowed_to_generate": True, "d11_allowed_to_execute": False,
         "PIPELINE_READY": False, "PRODUCTION_VERIFIED": False, "phase_e_allowed": False,
         "v4_frozen_at_j3": True, "v4_controlled_observe_execution_allowed": False,
         "stash_checked": False, "stash_allowed_only": False, "unknown_stash_found": False,
         "forbidden_dirty_files": [], "forbidden_staged_files": [],
         "blockers": [], "warnings": []}
    block = False

    # A. Docs
    for doc in REQUIRED_DOCS:
        if (DOCS_DIR / doc).is_file(): R["docs_required_present"] += 1
        else: R["blockers"].append(f"Missing: {doc}"); block = True

    # B. Matrix parse
    mx = _parse_matrix()
    R["matrix_header_fields_complete"] = mx["header_complete"]
    R["matrix_header_missing_fields"] = mx["missing_headers"]
    R["malformed_rows"] = mx["malformed"]
    if not mx["header_complete"]:
        R["blockers"].append(f"Header missing: {mx['missing_headers']}"); block = True

    R["proof_targets_count"] = len(mx["targets"])
    R["parsed_proof_ids"] = sorted(mx["targets"].keys())
    R["missing_proof_ids"] = [t for t in SIX_PROOF_TARGETS if t not in mx["targets"]]
    R["all_six_targets_present"] = len(R["missing_proof_ids"]) == 0
    if not R["all_six_targets_present"]:
        R["blockers"].append(f"Missing targets: {R['missing_proof_ids']}"); block = True

    # C. Per-target full field validation (11 business fields)
    pv = {}
    flags = {
        "unproven": True, "required_evidence": True, "allowed_action_rdo": True,
        "exec_false": True, "prod_false": True, "risk_valid": True,
        "blocker_true": True, "cmd_draft_true": True, "proof_req_true": True,
    }
    for t in SIX_PROOF_TARGETS:
        td = mx["targets"].get(t, {})
        v = {"proof_id": t}
        fields_ok = len(td) >= 11
        v["fields_present"] = len(td)
        v["fields_missing"] = []
        if not fields_ok:
            for fn in ["proof_name", "current_status", "required_evidence", "allowed_action_now",
                        "execution_allowed", "production_allowed", "production_risk",
                        "blocker_if_missing", "command_draft_required", "proof_result_required_before_pipeline_ready"]:
                if not td.get(fn): v["fields_missing"].append(fn)

        cs = td.get("current_status", ""); v["current_status"] = cs
        if cs != "UNPROVEN": v["status_error"] = f"not UNPROVEN: {cs}"; flags["unproven"] = False
        else: v["status_ok"] = True

        re = td.get("required_evidence", ""); v["required_evidence"] = re[:50]
        if not re: v["ev_error"] = "empty"; flags["required_evidence"] = False
        else: v["ev_ok"] = True

        aa = td.get("allowed_action_now", ""); v["allowed_action_now"] = aa
        if aa != "REVIEW_ONLY_DRAFT": v["action_error"] = f"not REVIEW_ONLY_DRAFT: {aa}"; flags["allowed_action_rdo"] = False
        else: v["action_ok"] = True

        ea = td.get("execution_allowed", ""); v["execution_allowed"] = ea
        if ea.lower() != "false": v["exec_error"] = f"not false: {ea}"; flags["exec_false"] = False
        else: v["exec_ok"] = True

        pa = td.get("production_allowed", ""); v["production_allowed"] = pa
        if pa.lower() != "false": v["prod_error"] = f"not false: {pa}"; flags["prod_false"] = False
        else: v["prod_ok"] = True

        pr = td.get("production_risk", ""); v["production_risk"] = pr
        if pr not in VALID_RISKS: v["risk_error"] = f"invalid: {pr}"; flags["risk_valid"] = False
        else: v["risk_ok"] = True

        bi = td.get("blocker_if_missing", ""); v["blocker_if_missing"] = bi
        if bi.lower() != "true": v["blocker_error"] = f"not true: {bi}"; flags["blocker_true"] = False
        else: v["blocker_ok"] = True

        cd = td.get("command_draft_required", ""); v["command_draft_required"] = cd
        if cd.lower() != "true": v["cmd_error"] = f"not true: {cd}"; flags["cmd_draft_true"] = False
        else: v["cmd_ok"] = True

        pq = td.get("proof_result_required_before_pipeline_ready", ""); v["proof_result_required_before_pipeline_ready"] = pq
        if pq.lower() != "true": v["proof_req_error"] = f"not true: {pq}"; flags["proof_req_true"] = False
        else: v["proof_req_ok"] = True

        pv[t] = v

    R["per_target_validation"] = pv
    R["all_six_targets_unproven"] = flags["unproven"]
    R["all_six_required_evidence_present"] = flags["required_evidence"]
    R["all_six_allowed_action_review_only"] = flags["allowed_action_rdo"]
    R["all_six_execution_allowed_false"] = flags["exec_false"]
    R["all_six_production_allowed_false"] = flags["prod_false"]
    R["all_six_production_risk_valid"] = flags["risk_valid"]
    R["all_six_blocker_if_missing_true"] = flags["blocker_true"]
    R["all_six_command_draft_required_true"] = flags["cmd_draft_true"]
    R["all_six_proof_result_required_before_pipeline_ready"] = flags["proof_req_true"]
    R["matrix_business_fields_complete"] = all(flags.values())

    # Raise blockers for each failed field
    if not flags["unproven"]: R["blockers"].append("Some targets not UNPROVEN"); block = True
    if not flags["required_evidence"]: R["blockers"].append("Some targets missing required_evidence"); block = True
    if not flags["allowed_action_rdo"]: R["blockers"].append("Some targets allowed_action_now != REVIEW_ONLY_DRAFT"); block = True
    if not flags["exec_false"]: R["blockers"].append("Some targets execution_allowed != false"); block = True
    if not flags["prod_false"]: R["blockers"].append("Some targets production_allowed != false"); block = True
    if not flags["risk_valid"]: R["blockers"].append("Some targets production_risk invalid"); block = True
    if not flags["blocker_true"]: R["blockers"].append("Some targets blocker_if_missing != true"); block = True
    if not flags["cmd_draft_true"]: R["blockers"].append("Some targets command_draft_required != true"); block = True
    if not flags["proof_req_true"]: R["blockers"].append("Some targets proof_result_required != true"); block = True

    # D. Stash / dirty / staged
    R["stash_checked"] = True
    _, so, _ = _run(["git", "stash", "list"])
    sl = [l.strip() for l in so.split("\n") if l.strip()]
    unk = [l for l in sl if not any(a in l for a in STASH_ALLOWED_MSGS)]
    R["stash_allowed_only"] = len(unk) == 0; R["unknown_stash_found"] = len(unk) > 0
    if unk: R["blockers"].append(f"Unknown stashes: {unk}"); block = True

    _, do, _ = _run(["git", "status", "--short"])
    R["forbidden_dirty_files"] = _scan_forbidden([l.strip() for l in do.split("\n") if l.strip()])
    _, sgo, _ = _run(["git", "diff", "--name-only", "--cached"])
    R["forbidden_staged_files"] = _scan_forbidden([l.strip() for l in sgo.split("\n") if l.strip()])
    if R["forbidden_dirty_files"]: R["blockers"].append(f"Forbidden dirty: {R['forbidden_dirty_files']}"); block = True
    if R["forbidden_staged_files"]: R["blockers"].append(f"Forbidden staged: {R['forbidden_staged_files']}"); block = True

    # E. Permission guards
    for n, v in [("d10_allowed_to_execute", R["d10_allowed_to_execute"]),
                 ("PIPELINE_READY", R["PIPELINE_READY"]), ("PRODUCTION_VERIFIED", R["PRODUCTION_VERIFIED"]),
                 ("phase_e_allowed", R["phase_e_allowed"])]:
        if v: R["blockers"].append(f"{n} is true"); block = True

    if block: R["check_status"] = "BLOCKER"
    elif R["warnings"]: R["check_status"] = "WARN"

    # Print summary
    print("=" * 60)
    print("V2 D10.3 FULL MATRIX FIELD VALIDATION CHECKER")
    print("=" * 60)
    print(f"Status: {R['check_status']}")
    for k in [
        "docs_required_present", "matrix_header_fields_complete",
        "matrix_business_fields_complete", "proof_targets_count", "parsed_proof_ids",
        "all_six_targets_present", "all_six_targets_unproven",
        "all_six_required_evidence_present", "all_six_allowed_action_review_only",
        "all_six_execution_allowed_false", "all_six_production_allowed_false",
        "all_six_production_risk_valid", "all_six_blocker_if_missing_true",
        "all_six_command_draft_required_true", "all_six_proof_result_required_before_pipeline_ready",
        "d10_allowed_to_execute", "d11_allowed_to_execute", "PIPELINE_READY",
        "PRODUCTION_VERIFIED", "phase_e_allowed", "v4_frozen_at_j3",
        "stash_allowed_only", "unknown_stash_found",
        "forbidden_dirty_files", "forbidden_staged_files",
    ]:
        v = R.get(k); print(f"  {k}: {v}")
    if R["blockers"]:
        print(f"\nBLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]: print(f"  ! {b}")
        sys.exit(1)
    elif R["warnings"]:
        print(f"\nWARNINGS ({len(R['warnings'])}):")
        for w in R["warnings"]: print(f"  ? {w}")

    md = MODULE_ROOT / "data" / "runtime" / "status"; md.mkdir(parents=True, exist_ok=True)
    mp = md / "v2_d10_production_proof_authorization_check.json"
    mp.write_text(json.dumps(R, indent=2, ensure_ascii=False, default=str))
    print(f"\nMarker: {mp} (NOT committed)")
    return 0

if __name__ == "__main__": sys.exit(main())
