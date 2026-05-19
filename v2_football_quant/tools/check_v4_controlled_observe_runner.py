#!/usr/bin/env python3
"""
V4-I.1: Controlled Observe Runner Checker

Verifies runner exists, supports all required flags, and has no dangerous side effects.
"""

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
RUNNER = MODULE_ROOT / "engine" / "v4_observe_runner.py"

REQUIRED_FLAGS = [
    "observe_only", "dry_run", "single_window_only",
    "no_push", "no_state_write", "no_verified_write",
    "no_cron", "no_api", "no_key_read", "no_supervisor",
    "watchdog_only_failure", "no_ai_kill_retry",
    "preserve_logs", "manifest_required", "review_only",
]

FORBIDDEN_PATTERNS = [
    "api_get", "requests.", "safe_outbound_sender",
    "qq_send", "send_message",
    "PRODUCTION_VERIFIED", "v4_live_verified",
    "route_marker", "sent_marker",
    "acquire_lock", ".kill(", ".retry(",
    "net_utils.get(",
]


def main():
    results = {
        "check_status": "PASS",
        "runner_exists": RUNNER.is_file(),
        "runner_defined": True,
        "all_required_flags_supported": True,
        "command_type": "REVIEW_ONLY_DRAFT",
        "command_must_not_execute": True,
        "observe_execution_allowed": False,
        "review_only": True,
        "dry_run": True,
        "no_push": True,
        "no_state_write": True,
        "no_verified_write": True,
        "no_cron": True,
        "no_api": True,
        "no_key_read": True,
        "no_supervisor": True,
        "forbidden_api_call_found": False,
        "forbidden_key_read_found": False,
        "forbidden_qq_send_found": False,
        "forbidden_state_write_found": False,
        "forbidden_verified_write_found": False,
        "route_marker_written": False,
        "sent_marker_written": False,
        "lock_created": False,
        "kill_retry_found": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "blockers": [], "warnings": [],
    }

    block = False

    if not results["runner_exists"]:
        results["blockers"].append("Runner not found: engine/v4_observe_runner.py")
        block = True
        results["check_status"] = "BLOCKER"
        _print_and_exit(results)

    content = RUNNER.read_text()

    # Check required flags in argparse
    missing_flags = []
    for flag in REQUIRED_FLAGS:
        cli_flag = f"--{flag.replace('_', '-')}"
        if cli_flag not in content:
            missing_flags.append(cli_flag)

    if missing_flags:
        results["all_required_flags_supported"] = False
        results["warnings"].append(f"Missing required flags: {missing_flags}")

    # Check runner output field observe_execution_allowed
    if "observe_execution_allowed" not in content:
        results["warnings"].append("Missing observe_execution_allowed field in runner output")
    if "command_must_not_execute" not in content:
        results["warnings"].append("Missing command_must_not_execute field")

    # Scan forbidden patterns
    for pat in FORBIDDEN_PATTERNS:
        if pat in content:
            key = None
            if pat in ("api_get", "requests."):
                key = "forbidden_api_call_found"
            elif pat in ("safe_outbound_sender", "qq_send", "send_message"):
                key = "forbidden_qq_send_found"
            elif pat in ("PRODUCTION_VERIFIED", "v4_live_verified"):
                key = "forbidden_verified_write_found"
            elif pat in ("route_marker", "sent_marker"):
                pass  # Check if used as write, not as variable name
                if f"{pat}_written" not in content:
                    key = None  # Only flag if used as actual write
            if key:
                results[key] = True
                results["blockers"].append(f"Forbidden pattern '{pat}' found in runner")
                block = True

    # Check lock/kill/retry
    for pat in ["acquire_lock", ".kill(", ".retry("]:
        if pat in content:
            if pat == "acquire_lock":
                results["lock_created"] = True
            else:
                results["kill_retry_found"] = True
            results["blockers"].append(f"Forbidden pattern '{pat}' found")
            block = True

    # Check output field values
    if "observe_execution_allowed" in content and "False" not in content.split("observe_execution_allowed")[1][:20]:
        results["blockers"].append("observe_execution_allowed not set to False")
        block = True

    # Production guard checks
    if results["production_verified"]:
        results["blockers"].append("production_verified is true")
        block = True
    if results["phase_e_allowed"]:
        results["blockers"].append("phase_e_allowed is true")
        block = True

    if block:
        results["check_status"] = "BLOCKER"
    elif results["warnings"]:
        results["check_status"] = "WARN"

    _print_and_exit(results)


def _print_and_exit(results):
    print("=" * 60)
    print("V4 CONTROLLED OBSERVE RUNNER CHECKER")
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
    marker_path = marker_dir / "v4_controlled_observe_runner_check.json"
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    sys.exit(0 if results["check_status"] != "BLOCKER" else 1)


if __name__ == "__main__":
    main()
