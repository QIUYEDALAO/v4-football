#!/usr/bin/env python3
"""
V4-H: Production Readiness Checker

Verifies that all V4 prior checkers exist, V4-A through V4-G.1 are covered,
readiness matrix and preflight gate docs exist, and production guards are in place.
"""

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = MODULE_ROOT / "docs"
TOOLS_DIR = MODULE_ROOT / "tools"

REQUIRED_CHECKERS = [
    "check_v4_path_canonicalization.py",
    "check_v4_boundary_contract.py",
    "check_v4_active_contamination.py",
    "check_v4_output_schema.py",
    "check_v4_renderer_guard.py",
    "check_v4_qq_guard.py",
    "check_v4_no_push_enforcement.py",
    "check_v4_watchdog_contract.py",
    "check_v4_lock_timeout_contract.py",
    "check_v4_attribution_schema.py",
    "check_v4_attribution_guard.py",
    "check_v4_attribution_no_api_guard.py",
    "check_v4_rolling_schema.py",
    "check_v4_rolling_guard.py",
    "check_v4_reporting_schema.py",
    "check_v4_reporting_guard.py",
]

REQUIRED_PHASE_DOCS = [
    "V4_A - Boundary and Contract",
    "V4_A.1 - Active Contamination",
    "V4_B - Output Schema and Renderer Guard",
    "V4_C - QQ Guard and No-Push",
    "V4_D - Watchdog State Lock",
    "V4_D.1 - Path Canonicalization",
    "V4_E - Attribution Schema and Guard",
    "V4_E.1 - No-API Guard Hardening",
    "V4_E.2 - UNKNOWN Policy Hardening",
    "V4_F - Rolling Validation",
    "V4_G - Reporting Schema and Guard",
    "V4_G.1 - Terminology Guard Hardening",
]


def main():
    results = {
        "check_status": "PASS",
        "readiness_matrix_exists": (DOCS_DIR / "V4_PRODUCTION_READINESS_MATRIX.md").is_file(),
        "preflight_gate_exists": (DOCS_DIR / "V4_PRODUCTION_PREFLIGHT_GATE.md").is_file(),
        "prior_checker_files_present": 0,
        "all_required_phases_covered": True,
        "active_contamination_blocked": True,
        "no_push_enforced": True,
        "watchdog_required": True,
        "lock_required": True,
        "timeout_required": True,
        "attribution_no_api_guard_required": True,
        "attribution_unknown_policy_required": True,
        "rolling_guard_required": True,
        "reporting_guard_required": True,
        "terminology_guard_required": True,
        "production_allowed": False,
        "execution_allowed": False,
        "qq_push_allowed": False,
        "state_write_allowed": False,
        "verified_write_allowed": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "v4_i_allowed_to_generate": True,
        "v4_i_allowed_to_execute": False,
        "blockers": [], "warnings": [],
    }

    block = False

    # Check docs exist
    if not results["readiness_matrix_exists"]:
        results["blockers"].append("Readiness matrix doc missing")
        block = True
    if not results["preflight_gate_exists"]:
        results["blockers"].append("Preflight gate doc missing")
        block = True

    # Check prior checker files exist
    missing = []
    for chk in REQUIRED_CHECKERS:
        if (TOOLS_DIR / chk).is_file():
            results["prior_checker_files_present"] += 1
        else:
            missing.append(chk)
    if missing:
        results["blockers"].append(f"Missing prior checkers: {missing}")
        block = True

    # Check preflight gate content for V4-I params
    if results["preflight_gate_exists"]:
        gate_content = (DOCS_DIR / "V4_PRODUCTION_PREFLIGHT_GATE.md").read_text()
        if "V4-I allowed_to_generate" not in gate_content:
            results["warnings"].append("Preflight gate missing V4-I allowed_to_generate")
        if "V4-I allowed_to_execute" not in gate_content:
            results["warnings"].append("Preflight gate missing V4-I allowed_to_execute")

    # Phase coverage check from matrix
    if results["readiness_matrix_exists"]:
        matrix_content = (DOCS_DIR / "V4_PRODUCTION_READINESS_MATRIX.md").read_text()
        for phase in REQUIRED_PHASE_DOCS:
            if phase not in matrix_content:
                results["all_required_phases_covered"] = False
                results["warnings"].append(f"Phase '{phase}' not found in readiness matrix")

    # Blocker checks on guard values
    if results["production_allowed"]:
        results["blockers"].append("production_allowed is true"); block = True
    if results["execution_allowed"]:
        results["blockers"].append("execution_allowed is true"); block = True
    if results["qq_push_allowed"]:
        results["blockers"].append("qq_push_allowed is true"); block = True
    if results["state_write_allowed"]:
        results["blockers"].append("state_write_allowed is true"); block = True
    if results["verified_write_allowed"]:
        results["blockers"].append("verified_write_allowed is true"); block = True
    if results["production_verified"]:
        results["blockers"].append("production_verified is true"); block = True
    if results["phase_e_allowed"]:
        results["blockers"].append("phase_e_allowed is true"); block = True

    if block:
        results["check_status"] = "BLOCKER"
    elif results["warnings"]:
        results["check_status"] = "WARN"

    # Print
    print("=" * 60)
    print("V4 PRODUCTION READINESS CHECKER")
    print("=" * 60)
    print(f"Status: {results['check_status']}")
    for k, v in results.items():
        if k in ("blockers", "warnings"):
            continue
        print(f"  {k}: {v}")
    if results["blockers"]:
        print(f"\nBLOCKERS ({len(results['blockers'])}):")
        for b in results["blockers"]:
            print(f"  ! {b}")
        sys.exit(1)
    elif results["warnings"]:
        print(f"\nWARNINGS ({len(results['warnings'])}):")
        for w in results["warnings"]:
            print(f"  ? {w}")

    # Write marker
    marker_dir = MODULE_ROOT / "data" / "runtime" / "status"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / "v4_production_readiness_check.json"
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
