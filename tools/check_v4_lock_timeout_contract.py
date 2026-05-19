#!/usr/bin/env python3
"""
V4-D: Lock / Timeout Contract Checker

Verifies that V4 lock and timeout contracts are properly defined
and current production guards are in place.
"""

import json
import os
import sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V4_REPO = os.path.join(WORKSPACE, "v2_football_quant")

SCAN_BRIEF = os.path.join(V4_REPO, "engine", "v4_scan_and_brief.py")
REVIEW_WD = os.path.join(V4_REPO, "engine", "v4_review_with_watchdog.py")
LOCK_DIR = os.path.join(V4_REPO, "data", "runtime", "locks")


def check_lock_usage():
    """Verify that key V4 engine files use locks."""
    if not os.path.isfile(SCAN_BRIEF):
        return {"valid": False, "error": "v4_scan_and_brief.py not found"}
    
    with open(SCAN_BRIEF, "r") as fh:
        scan_content = fh.read()
    
    checks = {}
    checks["scan_has_lock"] = "GLOBAL_LOCK" in scan_content and "LOCK_DIR" in scan_content
    checks["scan_has_timeout"] = "HARD_TIMEOUT" in scan_content or "SOFT_TIMEOUT" in scan_content
    checks["scan_has_stale_check"] = "stale" in scan_content.lower()
    checks["scan_has_concurrent_blocker"] = "exists()" in scan_content and "LOCK" in scan_content
    
    if not os.path.isfile(REVIEW_WD):
        return {"valid": False, "error": "v4_review_with_watchdog.py not found"}
    
    with open(REVIEW_WD, "r") as fh:
        review_content = fh.read()
    
    checks["review_has_lock"] = "acquire_lock" in review_content
    checks["review_has_timeout"] = "timeout=" in review_content
    checks["review_has_concurrent_check"] = "已有实例运行" in review_content
    
    missing = [k for k, v in checks.items() if not v]
    if missing:
        return {"valid": False, "error": f"Missing lock/timeout features: {missing}"}
    return {"valid": True, "error": None}


def main():
    results = {
        "check_status": "PASS",
        "lock_required": True,
        "timeout_required": True,
        "concurrent_run_blocker_required": True,
        "stale_lock_auto_kill_allowed": False,
        "ai_retry_allowed": False,
        "timeout_escalation_allowed": False,
        "preserve_logs": True,
        "report_watchdog_only": True,
        "state_write_allowed": False,
        "qq_push_allowed": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "blockers": [],
        "warnings": [],
    }
    
    # 1. Check lock usage in engine code
    lock_check = check_lock_usage()
    if not lock_check["valid"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append(lock_check["error"])
    else:
        print("[CHECK] Lock/timeout usage: VALID")
    
    # 2. Check blocker conditions
    if not results["lock_required"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("lock_required is false")
    if not results["timeout_required"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("timeout_required is false")
    if not results["concurrent_run_blocker_required"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("concurrent_run_blocker_required is false")
    if results["stale_lock_auto_kill_allowed"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("stale_lock_auto_kill_allowed is true")
    if results["ai_retry_allowed"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("ai_retry_allowed is true")
    if results["timeout_escalation_allowed"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("timeout_escalation_allowed is true")
    if results["production_verified"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("production_verified is true")
    if results["phase_e_allowed"]:
        results["check_status"] = "BLOCKER"
        results["blockers"].append("phase_e_allowed is true")
    
    # Print
    print("=" * 60)
    print("V4 LOCK/TIMEOUT CONTRACT CHECKER")
    print("=" * 60)
    print(f"Status: {results['check_status']}")
    print(f"Lock required: {results['lock_required']}")
    print(f"Timeout required: {results['timeout_required']}")
    print(f"Concurrent blocker: {results['concurrent_run_blocker_required']}")
    print(f"Stale lock auto-kill: {results['stale_lock_auto_kill_allowed']}")
    print(f"AI retry: {results['ai_retry_allowed']}")
    print(f"Timeout escalation: {results['timeout_escalation_allowed']}")
    print(f"Preserve logs: {results['preserve_logs']}")
    print(f"Report watchdog only: {results['report_watchdog_only']}")
    print(f"State write: {results['state_write_allowed']}")
    print(f"QQ push: {results['qq_push_allowed']}")
    print(f"Production verified: {results['production_verified']}")
    print(f"Phase E: {results['phase_e_allowed']}")
    
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
    marker_dir = os.path.join(WORKSPACE, "data", "runtime", "status")
    os.makedirs(marker_dir, exist_ok=True)
    marker_path = os.path.join(marker_dir, "v4_lock_timeout_contract_check.json")
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    
    return 0 if results["check_status"] != "BLOCKER" else 1


if __name__ == "__main__":
    sys.exit(main())
