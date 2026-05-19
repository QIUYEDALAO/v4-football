#!/usr/bin/env python3
"""
V2 D10.2: Production Proof Authorization Checker (Matrix Parser Final)
Header-based parser. Stash enforced. Dirty/staged scanned.
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

MATRIX_HEADER_FIELDS = [
    "#", "proof_id", "proof_name", "current_status",
    "required_evidence", "allowed_action_now", "execution_allowed",
    "production_allowed", "production_risk", "blocker_if_missing",
    "command_draft_required", "proof_result_required_before_PIPELINE_READY",
]

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


def _run(cmd, cwd=None, timeout=60):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or str(MODULE_ROOT), timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _parse_matrix() -> dict:
    """Header-based matrix parser. Returns {'targets': {}, 'fields_present': [], 'errors': []}."""
    result = {"targets": {}, "fields_present": [], "errors": [], "malformed": []}
    matrix = DOCS_DIR / "V2_D10_SIX_PROOF_EVIDENCE_MATRIX.md"
    if not matrix.is_file():
        result["errors"].append("Matrix file not found")
        return result

    txt = matrix.read_text()
    lines = txt.split("\n")
    col_index = {}
    in_header = False
    header_found = False
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if not cols:
            continue

        # Detect header row: contains "proof_id" and "proof_name"
        if not header_found and any("proof_id" in c for c in cols):
            header_found = True
            for i, c in enumerate(cols):
                # Normalize header names (strip extra whitespace)
                h = c.strip().lower().replace(" ", "_")
                col_index[h] = i
            # Verify required headers
            for needed in ["proof_id", "current_status", "execution_allowed", "production_allowed", "proof_result_required_before_pipeline_ready"]:
                if needed not in col_index:
                    result["errors"].append(f"Missing header field: {needed}")
            result["fields_present"] = sorted(col_index.keys())
            continue

        if not header_found or not col_index:
            continue

        # Skip separator |---| lines
        if cols[0] == "---" or all(c.startswith("-") for c in cols if c):
            continue

        # Extract proof_id via header index
        pid_idx = col_index.get("proof_id")
        if pid_idx is None or pid_idx >= len(cols):
            continue
        pid = cols[pid_idx]
        if not pid or pid.isdigit() or pid == "proof_id":
            continue

        # Extract fields via header index
        def _f(name, default=""):
            idx = col_index.get(name)
            if idx is not None and idx < len(cols):
                return cols[idx]
            return default

        cs = _f("current_status", "UNKNOWN")
        ea = _f("execution_allowed", "true")
        pa = _f("production_allowed", "true")
        pr = _f("proof_result_required_before_pipeline_ready", "false")

        result["targets"][pid] = {
            "current_status": cs,
            "execution_allowed": ea.lower() == "false",
            "production_allowed": pa.lower() == "false",
            "proof_result_required": pr.lower() == "true",
        }

    return result


def _scan_forbidden(name: str, paths: list[str]) -> list[str]:
    """Scan paths for forbidden patterns."""
    hits = []
    for p in paths:
        for pat in FORBIDDEN_PATTERNS:
            if pat in p:
                hits.append(f"{name}: {p}")
    return hits


def main():
    r = {
        "check_status": "PASS",
        "docs_required_present": 0,
        "matrix_header_fields_present": [],
        "matrix_business_fields_complete": False,
        "malformed_rows": [],
        "proof_targets_count": 0,
        "parsed_proof_ids": [],
        "missing_proof_ids": [],
        "all_six_targets_present": False,
        "all_six_targets_unproven": False,
        "all_six_execution_allowed_false": False,
        "all_six_production_allowed_false": False,
        "all_six_proof_result_required": False,
        "d10_allowed_to_generate": True,
        "d10_allowed_to_execute": False,
        "d11_allowed_to_generate": True,
        "d11_allowed_to_execute": False,
        "production_proof_execution_authorized": False,
        "PIPELINE_READY": False,
        "PRODUCTION_VERIFIED": False,
        "phase_e_allowed": False,
        "v4_frozen_at_j3": True,
        "v4_controlled_observe_execution_allowed": False,
        "stash_checked": False,
        "stash_allowed_only": False,
        "unknown_stash_found": False,
        "forbidden_dirty_files": [],
        "forbidden_staged_files": [],
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

    # B. Header-based matrix parse
    matrix = _parse_matrix()
    r["matrix_header_fields_present"] = matrix["fields_present"]
    r["matrix_business_fields_complete"] = len(matrix["fields_present"]) >= 11
    r["malformed_rows"] = matrix["malformed"]
    r["proof_targets_count"] = len(matrix["targets"])
    r["parsed_proof_ids"] = sorted(matrix["targets"].keys())

    targets = matrix["targets"]
    present = all(t in targets for t in SIX_PROOF_TARGETS)
    r["missing_proof_ids"] = [t for t in SIX_PROOF_TARGETS if t not in targets]
    r["all_six_targets_present"] = present
    if not present:
        r["blockers"].append(f"Missing proof targets: {r['missing_proof_ids']}")
        block = True

    unproven = True
    exec_ok = True
    prod_ok = True
    proof_req_ok = True
    for t in SIX_PROOF_TARGETS:
        td = targets.get(t, {})
        if td.get("current_status", "?") != "UNPROVEN":
            unproven = False
            r["blockers"].append(f"{t}: status={td.get('current_status')}, not UNPROVEN")
            block = True
        if not td.get("execution_allowed", False):
            exec_ok = False
            r["blockers"].append(f"{t}: execution_allowed is true")
            block = True
        if not td.get("production_allowed", False):
            prod_ok = False
            r["blockers"].append(f"{t}: production_allowed is true")
            block = True
        if not td.get("proof_result_required", False):
            proof_req_ok = False
            r["blockers"].append(f"{t}: proof_result_required_before_pipeline_ready is false")
            block = True
    r["all_six_targets_unproven"] = unproven
    r["all_six_execution_allowed_false"] = exec_ok
    r["all_six_production_allowed_false"] = prod_ok
    r["all_six_proof_result_required"] = proof_req_ok

    # C. Stash check
    r["stash_checked"] = True
    _, stash_out, _ = _run(["git", "stash", "list"])
    stash_lines = [l.strip() for l in stash_out.split("\n") if l.strip()]
    unknown = []
    for line in stash_lines:
        if not any(a in line for a in STASH_ALLOWED_MSGS):
            unknown.append(line)
    r["stash_allowed_only"] = len(unknown) == 0
    r["unknown_stash_found"] = len(unknown) > 0
    if unknown:
        r["blockers"].append(f"Unknown stashes: {unknown}")
        block = True

    # D. Forbidden dirty/staged scan
    _, dirty_out, _ = _run(["git", "status", "--short"])
    r["forbidden_dirty_files"] = _scan_forbidden("dirty", [l.strip() for l in dirty_out.split("\n") if l.strip()])

    _, staged_out, _ = _run(["git", "diff", "--name-only", "--cached"])
    r["forbidden_staged_files"] = _scan_forbidden("staged", [l.strip() for l in staged_out.split("\n") if l.strip()])

    if r["forbidden_dirty_files"]:
        r["blockers"].append(f"Forbidden dirty: {r['forbidden_dirty_files']}")
        block = True
    if r["forbidden_staged_files"]:
        r["blockers"].append(f"Forbidden staged: {r['forbidden_staged_files']}")
        block = True

    # E. Permission guards
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
    print("V2 D10.2 MATRIX PARSER FINAL CHECKER")
    print("=" * 60)
    print(f"Status: {r['check_status']}")
    for k, v in r.items():
        if k in ("blockers", "warnings", "matrix_header_fields_present"):
            continue
        if isinstance(v, list) and not v:
            continue
        print(f"  {k}: {v}")
    print(f"  matrix_header_fields_present: {r['matrix_header_fields_present']}")
    if r["blockers"]:
        print(f"\nBLOCKERS ({len(r['blockers'])}):")
        for b in r["blockers"]:
            print(f"  ! {b}")
        sys.exit(1)
    elif r["warnings"]:
        print(f"\nWARNINGS ({len(r['warnings'])}):")
        for w in r["warnings"]:
            print(f"  ? {w}")

    md = MODULE_ROOT / "data" / "runtime" / "status"
    md.mkdir(parents=True, exist_ok=True)
    mp = md / "v2_d10_production_proof_authorization_check.json"
    mp.write_text(json.dumps(r, indent=2, ensure_ascii=False))
    print(f"\nMarker: {mp} (NOT committed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
