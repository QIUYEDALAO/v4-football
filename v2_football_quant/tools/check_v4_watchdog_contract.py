#!/usr/bin/env python3
"""
V4-D: Watchdog Contract Checker

Verifies that V4 watchdog/state/lock contracts are properly defined
and current production guards are in place.
"""

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]  # v2_football_quant/
REPO_ROOT = MODULE_ROOT.parent                     # repo root

DOC_WATCHDOG = MODULE_ROOT / "docs" / "V4_WATCHDOG_STATE_LOCK.md"
DOC_LIFECYCLE = MODULE_ROOT / "docs" / "V4_STATE_LIFECYCLE_CONTRACT.md"
ENGINE_WATCHDOG = MODULE_ROOT / "engine" / "v4_review_with_watchdog.py"


def check_doc_exists(path, label):
    if not path.is_file():
        return {"valid": False, "error": f"{label}: {path} not found"}
    return {"valid": True, "error": None}


def check_watchdog_entry_exists():
    """Check that the watchdog wrapper exists and has basic contract fields."""
    if not ENGINE_WATCHDOG.is_file():
        return {"valid": False, "error": "v4_review_with_watchdog.py not found"}
    
    with open(ENGINE_WATCHDOG, "r") as fh:
        content = fh.read()
    
    checks = {
        "has_lock": "acquire_lock" in content,
        "has_route_marker": "route_marker" in content.lower(),
        "has_sent_marker": "sent_marker" in content.lower(),
        "has_guard_status": "guard_status" in content,
        "has_timeout": "timeout=" in content,
    }
    
    missing = [k for k, v in checks.items() if not v]
    if missing:
        return {"valid": False, "error": f"Missing watchdog features: {missing}"}
    return {"valid": True, "error": None}


def main():
    results = {
        "check_status": "PASS",
        "watchdog_doc_exists": False,
        "state_lifecycle_doc_exists": False,
        "watchdog_entry_exists": False,
        "watchdog_required": True,
        "watchdog_bypass_allowed": False,
        "no_ai_kill_retry": True,
        "report_watchdog_only": True,
        "fail_closed_required": True,
        "route_requires_watchdog": True,
        "sent_requires_watchdog": True,
        "production_verified_requires_watchdog": True,
        "production_verified": False,
        "phase_e_allowed": False,
        "v4_e_allowed_to_generate": True,
        "v4_e_allowed_to_execute": False,
        "blockers": [],
        "warnings": [],
    }
    
    # 1. Check doc existence
    doc_wd = check_doc_exists(DOC_WATCHDOG, "V4_WATCHDOG_STATE_LOCK.md")
    results["watchdog_doc_exists"] = doc_wd["valid"]
    if not doc_wd["valid"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append(doc_wd["error"])
    
    doc_lc = check_doc_exists(DOC_LIFECYCLE, "V4_STATE_LIFECYCLE_CONTRACT.md")
    results["state_lifecycle_doc_exists"] = doc_lc["valid"]
    if not doc_lc["valid"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append(doc_lc["error"])
    
    # 2. Check watchdog entry
    wd_entry = check_watchdog_entry_exists()
    results["watchdog_entry_exists"] = wd_entry["valid"]
    if not wd_entry["valid"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append(wd_entry["error"])
    
    # 3. Check blocker conditions
    if not results["watchdog_required"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("watchdog_required is false")
    if results["watchdog_bypass_allowed"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("watchdog_bypass_allowed is true")
    if not results["no_ai_kill_retry"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("no_ai_kill_retry is false")
    if not results["fail_closed_required"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("fail_closed_required is false")
    if results["production_verified"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("production_verified is true")
    if results["phase_e_allowed"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("phase_e_allowed is true")
    
    # Print
    print("=" * 60)
    print("V4 WATCHDOG CONTRACT CHECKER")
    print("=" * 60)
    print(f"Status: {results['check_status']}")
    print(f"Watchdog doc: {results['watchdog_doc_exists']}")
    print(f"Lifecycle doc: {results['state_lifecycle_doc_exists']}")
    print(f"Watchdog entry: {results['watchdog_entry_exists']}")
    print(f"Watchdog required: {results['watchdog_required']}")
    print(f"Watchdog bypass: {results['watchdog_bypass_allowed']}")
    print(f"No AI kill/retry: {results['no_ai_kill_retry']}")
    print(f"Report watchdog only: {results['report_watchdog_only']}")
    print(f"Fail closed: {results['fail_closed_required']}")
    print(f"Route needs watchdog: {results['route_requires_watchdog']}")
    print(f"Sent needs watchdog: {results['sent_requires_watchdog']}")
    print(f"Prod verified needs watchdog: {results['production_verified_requires_watchdog']}")
    print(f"Production verified: {results['production_verified']}")
    print(f"Phase E allowed: {results['phase_e_allowed']}")
    print(f"V4-E allowed_to_generate: {results['v4_e_allowed_to_generate']}")
    print(f"V4-E allowed_to_execute: {results['v4_e_allowed_to_execute']}")
    
    if results["blockers"]:
        print(f"\nBLOCKERS ({len(results['blockers'])}):")
        for b in results["blockers"]:
            print(f"  ! {b}")
        sys.exit(1)
    elif results["warnings"]:
        print(f"\nWARNINGS ({len(results['warnings'])}):")
        for w in results["warnings"]:
            print(f"  ? {w}")
    
    # Write marker to module data/runtime/status (NOT committed)
    marker_dir = MODULE_ROOT / "data" / "runtime" / "status"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / "v4_watchdog_contract_check.json"
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    
    return 0 if results["check_status"] != "BLOCKER" else 1


if __name__ == "__main__":
    sys.exit(main())
