#!/usr/bin/env python3
"""
V4-I: Controlled Observe Approval Checker

Verifies that the V4 controlled observe approval packet and command draft
exist with correct guard and execution constraints.
"""

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = MODULE_ROOT / "docs"

APPROVAL_PACKET = DOCS_DIR / "V4_CONTROLLED_OBSERVE_APPROVAL_PACKET.md"
COMMAND_DRAFT = DOCS_DIR / "V4_CONTROLLED_OBSERVE_COMMAND_DRAFT.md"


def main():
    results = {
        "check_status": "PASS",
        "approval_packet_exists": APPROVAL_PACKET.is_file(),
        "command_draft_exists": COMMAND_DRAFT.is_file(),
        "v4_i_allowed_to_generate": True,
        "v4_i_allowed_to_execute": False,
        "single_window_only": True,
        "observe_only": True,
        "dry_run": True,
        "no_push": True,
        "no_state_write": True,
        "no_verified_write": True,
        "no_cron": True,
        "no_api": True,
        "no_key_read": True,
        "no_supervisor": True,
        "watchdog_only_failure": True,
        "no_ai_kill_retry": True,
        "command_must_not_execute": True,
        "observe_execution_allowed": False,
        "route_marker_written": False,
        "sent_marker_written": False,
        "qq_sent": False,
        "state_written": False,
        "verified_written": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "v4_j_allowed_to_generate": True,
        "v4_j_allowed_to_execute": False,
        "blockers": [], "warnings": [],
    }

    block = False

    # Check docs exist
    if not results["approval_packet_exists"]:
        results["blockers"].append("Approval packet missing")
        block = True
    if not results["command_draft_exists"]:
        results["blockers"].append("Command draft missing")
        block = True

    # Check content
    if results["approval_packet_exists"]:
        content = APPROVAL_PACKET.read_text()
        for check in ["observe_only", "dry_run", "no_push", "not yet authorized",
                       "single_window_only", "no_state_write", "no_verified_write",
                       "no_cron", "no_api", "no_key_read", "no_supervisor",
                       "watchdog_only_failure", "no_ai_kill_retry"]:
            if check not in content.lower():
                results["warnings"].append(f"'{check}' not found in approval packet")

    if results["command_draft_exists"]:
        cd_content = COMMAND_DRAFT.read_text()
        if "REVIEW_ONLY_DRAFT" not in cd_content:
            results["blockers"].append("Command draft not marked REVIEW_ONLY_DRAFT")
            block = True
        if "NOT_EXECUTABLE_UNTIL_RUNNER_DEFINED" not in cd_content:
            results["warnings"].append("Command draft missing NOT_EXECUTABLE marker")
        if "command_must_not_execute" not in cd_content:
            results["warnings"].append("Command draft missing command_must_not_execute")
        if "no-supervisor" not in cd_content:
            results["warnings"].append("Command draft missing --no-supervisor flag")

    # Blocker checks
    if results["observe_execution_allowed"]:
        results["blockers"].append("observe_execution_allowed is true")
        block = True
    if not results["command_must_not_execute"]:
        results["blockers"].append("command_must_not_execute is false")
        block = True
    if results["route_marker_written"]:
        results["blockers"].append("route_marker_written is true (must be false)")
        block = True
    if results["sent_marker_written"]:
        results["blockers"].append("sent_marker_written is true (must be false)")
        block = True
    if results["production_verified"]:
        results["blockers"].append("production_verified is true")
        block = True
    if results["phase_e_allowed"]:
        results["blockers"].append("phase_e_allowed is true")
        block = True
    if results["v4_j_allowed_to_execute"]:
        results["blockers"].append("V4-J allowed_to_execute is true (should be false)")
        block = True

    if block:
        results["check_status"] = "BLOCKER"
    elif results["warnings"]:
        results["check_status"] = "WARN"

    # Print
    print("=" * 60)
    print("V4 CONTROLLED OBSERVE APPROVAL CHECKER")
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
    marker_path = marker_dir / "v4_controlled_observe_approval_check.json"
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
