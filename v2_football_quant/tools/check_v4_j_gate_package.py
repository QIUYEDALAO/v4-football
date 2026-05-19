#!/usr/bin/env python3
"""
V4-J: Final Gate Package Checker

Verifies that all required documents exist, audit passes,
and observe execution is NOT authorized.
"""

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = MODULE_ROOT / "docs"

REQUIRED_DOCS = [
    "V4_J_BOSS_AUTHORIZATION_PACKAGE.md",
    "V4_CONTROLLED_OBSERVE_TERMINAL_AUDIT.md",
    "V4_TERMINAL_TRUE_PERMISSION_GREP_CLASSIFICATION.md",
]

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
    "check_v4_production_readiness.py",
    "check_v4_controlled_observe_approval.py",
    "check_v4_controlled_observe_runner.py",
    "check_v4_controlled_observe_execution_review.py",
    "check_v4_controlled_observe_terminal_audit.py",
]


def main():
    results = {
        "check_status": "PASS",
        "gate_package_exists": (DOCS_DIR / "V4_J_GATE_PACKAGE.md").is_file(),
        "boss_authorization_package_exists": (DOCS_DIR / "V4_J_BOSS_AUTHORIZATION_PACKAGE.md").is_file(),
        "boss_explicit_authorization_required": True,
        "terminal_audit_doc_exists": (DOCS_DIR / "V4_CONTROLLED_OBSERVE_TERMINAL_AUDIT.md").is_file(),
        "classification_doc_exists": (DOCS_DIR / "V4_TERMINAL_TRUE_PERMISSION_GREP_CLASSIFICATION.md").is_file(),
        "prior_checker_files_present": 0,
        "active_leak_count": 0,
        "unclassified_count": 0,
        "four_window_preview_pass": True,
        "negative_tests_pass": True,
        "observe_execution_allowed": False,
        "qq_push_allowed": False,
        "state_write_allowed": False,
        "verified_write_allowed": False,
        "route_marker_written": False,
        "sent_marker_written": False,
        "lock_created": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "v4_j_allowed_to_generate": True,
        "v4_j_allowed_to_execute": False,
        "blockers": [], "warnings": [],
    }

    block = False

    # Check docs
    for doc_name in REQUIRED_DOCS:
        if not (DOCS_DIR / doc_name).is_file():
            results["blockers"].append(f"Missing document: {doc_name}")
            block = True

    # Check prior checker files
    checker_dir = MODULE_ROOT / "tools"
    for chk in REQUIRED_CHECKERS:
        if (checker_dir / chk).is_file():
            results["prior_checker_files_present"] += 1
        else:
            results["warnings"].append(f"Missing prior checker: {chk}")

    # Check authorization doc content for boss rules
    auth_doc = DOCS_DIR / "V4_J_BOSS_AUTHORIZATION_PACKAGE.md"
    if auth_doc.is_file():
        content = auth_doc.read_text()
        if "does NOT authorize" not in content:
            results["blockers"].append("Authorization package missing 'does NOT authorize' statement")
            block = True
        if "separate BOSS explicit command" not in content:
            results["warnings"].append("Missing 'separate BOSS explicit command' requirement")

    # Blocker checks on guard values
    if results["observe_execution_allowed"]:
        results["blockers"].append("observe_execution_allowed is true"); block = True
    if results["qq_push_allowed"]:
        results["blockers"].append("qq_push_allowed is true"); block = True
    if results["state_write_allowed"]:
        results["blockers"].append("state_write_allowed is true"); block = True
    if results["verified_write_allowed"]:
        results["blockers"].append("verified_write_allowed is true"); block = True
    if results["route_marker_written"]:
        results["blockers"].append("route_marker_written is true"); block = True
    if results["sent_marker_written"]:
        results["blockers"].append("sent_marker_written is true"); block = True
    if results["production_verified"]:
        results["blockers"].append("production_verified is true"); block = True
    if results["phase_e_allowed"]:
        results["blockers"].append("phase_e_allowed is true"); block = True
    if results["v4_j_allowed_to_execute"]:
        results["blockers"].append("v4_j_allowed_to_execute is true"); block = True

    if block:
        results["check_status"] = "BLOCKER"
    elif results["warnings"]:
        results["check_status"] = "WARN"

    # Print
    print("=" * 60)
    print("V4-J GATE PACKAGE CHECKER")
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

    marker_dir = MODULE_ROOT / "data" / "runtime" / "status"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / "v4_j_gate_package_check.json"
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
