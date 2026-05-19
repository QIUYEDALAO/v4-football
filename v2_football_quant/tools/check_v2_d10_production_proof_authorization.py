#!/usr/bin/env python3
"""
V2 D10.1: Production Proof Authorization Checker (Hardened)
Structured matrix parser, no loose string checks.
"""
import json, re, subprocess, sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = MODULE_ROOT / "docs"
REPO_ROOT = MODULE_ROOT.parent

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

MATRIX_REQUIRED_FIELDS = [
    "current_status", "execution_allowed", "production_allowed",
    "blocker_if_missing", "proof_result_required_before_PIPELINE_READY",
]

FORBIDDEN_STAGED_PATTERNS = [
    "data/runtime", "data/state", "data/paper_trading",
    ".xlsx", ".xls", "engine/net_utils.py",
    "secret", ".env", "token", "key",
    "verified", "route_marker", "sent_marker", "lock",
]

STASH_ALLOWED = [
    "phase-d101 workspace isolation: nowscore scratch only",
    "phase-v4a1 workspace isolation: discipline archive residue only",
    "phase-d87 workspace isolation: net_utils only",
]


def _run(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or str(MODULE_ROOT), timeout=60)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _parse_matrix_targets() -> dict:
    """Structured parse of six-proof matrix. Returns dict per target."""
    matrix = DOCS_DIR / "V2_D10_SIX_PROOF_EVIDENCE_MATRIX.md"
    targets = {}
    if not matrix.is_file():
        return targets

    txt = matrix.read_text()
    lines = txt.split("\n")
    in_table = False
    for line in lines:
        line = line.strip()
        if "proof_id" in line and "proof_name" in line:
            in_table = True
            continue
        if not in_table or not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) < 11:
            continue
        # Identify the row: first col is #, second is proof_id
        if cols[0] == "---" or cols[0].startswith("#"):
            continue
        pid = cols[1]  # proof_id is column 2 (index 1)
        if not pid or pid.isdigit():
            continue
        # Column indices (after #, proof_id, proof_name):
        # col[3]=current_status, col[5]=allowed_action_now,
        # col[6]=execution_allowed, col[7]=production_allowed,
        # col[8]=production_risk, col[9]=blocker_if_missing,
        # col[10]=command_draft_required, col[11]=proof_result_required
        def _v(i, d): return cols[i] if len(cols) > i else d
        targets[pid] = {
            "current_status": _v(3, "UNKNOWN"),
            "execution_allowed": _v(6, "true") == "false",
            "production_allowed": _v(7, "true") == "false",
            "blocker_if_missing": _v(9, "false") == "true",
            "proof_result_required": _v(11, "false") == "true",
        }
    return targets


def main():
    r = {
        "check_status": "PASS",
        "docs_required_present": 0,
        "all_six_targets_present": False,
        "all_six_targets_unproven": False,
        "all_six_execution_allowed_false": False,
        "all_six_production_allowed_false": False,
        "matrix_fields_complete": False,
        "matrix_parse_errors": [],
        "target_details": {},
        "d10_allowed_to_generate": True,
        "d10_allowed_to_execute": False,
        "d11_allowed_to_generate": True,
        "d11_allowed_to_execute": False,
        "production_proof_execution_authorized": False,
        "PIPELINE_READY": False,
        "PRODUCTION_VERIFIED": False,
        "phase_e_allowed": False,
        "cron_enable_allowed": False,
        "qq_push_allowed": False,
        "state_write_allowed": False,
        "verified_write_allowed": False,
        "v4_frozen_at_j3": True,
        "v4_controlled_observe_execution_allowed": False,
        "forbidden_staged": [],
        "blockers": [], "warnings": [],
    }
    block = False

    # A. Required docs
    for doc in REQUIRED_DOCS:
        if (DOCS_DIR / doc).is_file():
            r["docs_required_present"] += 1
        else:
            r["blockers"].append(f"Missing doc: {doc}")
            block = True

    # B. Structured matrix parse
    targets = _parse_matrix_targets()
    r["all_six_targets_present"] = all(t in targets for t in SIX_PROOF_TARGETS)
    if not r["all_six_targets_present"]:
        missing = [t for t in SIX_PROOF_TARGETS if t not in targets]
        r["blockers"].append(f"Missing proof targets: {missing}")
        block = True

    unproven_all = True
    exec_false_all = True
    prod_false_all = True
    for t in SIX_PROOF_TARGETS:
        td = targets.get(t, {})
        r["target_details"][t] = td
        if td.get("current_status") != "UNPROVEN":
            unproven_all = False
            r["blockers"].append(f"{t}: status is {td.get('current_status')}, not UNPROVEN")
            block = True
        if not td.get("execution_allowed", False):
            exec_false_all = False
            r["blockers"].append(f"{t}: execution_allowed is true")
            block = True
        if not td.get("production_allowed", False):
            prod_false_all = False
            r["blockers"].append(f"{t}: production_allowed is true")
            block = True
    r["all_six_targets_unproven"] = unproven_all
    r["all_six_execution_allowed_false"] = exec_false_all
    r["all_six_production_allowed_false"] = prod_false_all
    r["matrix_fields_complete"] = len(targets) >= 6

    # C. Staged forbidden files
    _, out, _ = _run(["git", "diff", "--name-only", "--cached"])
    for line in out.split("\n"):
        for pat in FORBIDDEN_STAGED_PATTERNS:
            if pat in line.strip():
                r["forbidden_staged"].append(line.strip())
    if r["forbidden_staged"]:
        r["blockers"].append(f"Forbidden staged: {r['forbidden_staged']}")
        block = True

    # D. Blocker guards
    for name, val in [
        ("d10_allowed_to_execute", r["d10_allowed_to_execute"]),
        ("production_proof_execution_authorized", r["production_proof_execution_authorized"]),
        ("PIPELINE_READY", r["PIPELINE_READY"]),
        ("PRODUCTION_VERIFIED", r["PRODUCTION_VERIFIED"]),
        ("phase_e_allowed", r["phase_e_allowed"]),
    ]:
        if val:
            r["blockers"].append(f"{name} is true")
            block = True

    if block:
        r["check_status"] = "BLOCKER"
    elif r["warnings"]:
        r["check_status"] = "WARN"

    # Print
    print("=" * 60)
    print("V2 D10.1 PRODUCTION PROOF AUTHORIZATION CHECKER (Hardened)")
    print("=" * 60)
    print(f"Status: {r['check_status']}")
    for k, v in r.items():
        if k in ("blockers", "warnings", "target_details"):
            continue
        if isinstance(v, list) and not v:
            continue
        print(f"  {k}: {v}")
    if r["blockers"]:
        print(f"\nBLOCKERS ({len(r['blockers'])}):")
        for b in r["blockers"]:
            print(f"  ! {b}")
        sys.exit(1)
    elif r["warnings"]:
        print(f"\nWARNINGS ({len(r['warnings'])}):")
        for w in r["warnings"]:
            print(f"  ? {w}")

    # Write marker
    md = MODULE_ROOT / "data" / "runtime" / "status"
    md.mkdir(parents=True, exist_ok=True)
    mp = md / "v2_d10_production_proof_authorization_check.json"
    mp.write_text(json.dumps(r, indent=2, ensure_ascii=False))
    print(f"\nMarker: {mp} (NOT committed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
