#!/usr/bin/env python3
"""
V4-I.1: Controlled Observe Runner

Minimum no-exec harness. No API, no key, no QQ, no state, no verified.
All required flags are validated. Runner only produces preview output.

Guard markers:
  NO_API = true
  NO_KEY = true
  NO_QQ = true
  NO_STATE = true
  NO_VERIFIED = true
  NO_EXEC = true
"""

import argparse
import json
import sys

ALLOWED_WINDOWS = ["early", "midday", "evening", "night"]

REQUIRED_BOOLEAN_FLAGS = [
    "observe_only", "dry_run", "single_window_only",
    "no_push", "no_state_write", "no_verified_write",
    "no_cron", "no_api", "no_key_read", "no_supervisor",
    "watchdog_only_failure", "no_ai_kill_retry",
    "preserve_logs", "manifest_required", "review_only",
]
REQUIRED_VALUE_FLAGS = ["date", "window"]


def check_required_flags(args) -> list[str]:
    missing = []
    for flag in REQUIRED_BOOLEAN_FLAGS:
        if not getattr(args, flag, False):
            missing.append(f"--{flag.replace('_', '-')}")
    for flag in REQUIRED_VALUE_FLAGS:
        value = getattr(args, flag, "")
        if not str(value).strip():
            missing.append(f"--{flag.replace('_', '-')}")
    return missing


def main():
    parser = argparse.ArgumentParser(description="V4 Controlled Observe Runner (no-exec)")
    parser.add_argument("--observe-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--single-window-only", action="store_true")
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--no-state-write", action="store_true")
    parser.add_argument("--no-verified-write", action="store_true")
    parser.add_argument("--no-cron", action="store_true")
    parser.add_argument("--no-api", action="store_true")
    parser.add_argument("--no-key-read", action="store_true")
    parser.add_argument("--no-supervisor", action="store_true")
    parser.add_argument("--watchdog-only-failure", action="store_true")
    parser.add_argument("--no-ai-kill-retry", action="store_true")
    parser.add_argument("--preserve-logs", action="store_true")
    parser.add_argument("--manifest-required", action="store_true")
    parser.add_argument("--review-only", action="store_true")
    parser.add_argument("--date", required=True, help="YYYYMMDD or YYYY-MM-DD")
    parser.add_argument(
        "--window",
        required=True,
        choices=ALLOWED_WINDOWS,
        help="observe window",
    )

    args = parser.parse_args()
    missing = check_required_flags(args)

    result = {
        "runner_status": "REVIEW_ONLY_READY" if not missing else "BLOCKER",
        "command_type": "REVIEW_ONLY_DRAFT",
        "runner": "engine/v4_observe_runner.py (no-exec harness)",
        "version": "0.1.0",
        "runner_defined": True,
        "runner_exists": True,
        "runner_execution_authorization_required": True,
        "date": args.date,
        "window": args.window,
        "allowed_windows": ALLOWED_WINDOWS,
        "observe_execution_allowed": False,
        "command_must_not_execute": True,
        "observe_only": args.observe_only,
        "dry_run": args.dry_run,
        "single_window_only": args.single_window_only,
        "required_flags_present": not bool(missing),
        "missing_required_flags": missing,
        "no_push": args.no_push,
        "no_state_write": args.no_state_write,
        "no_verified_write": args.no_verified_write,
        "no_cron": args.no_cron,
        "no_api": args.no_api,
        "no_key_read": args.no_key_read,
        "no_supervisor": args.no_supervisor,
        "watchdog_only_failure": args.watchdog_only_failure,
        "no_ai_kill_retry": args.no_ai_kill_retry,
        "preserve_logs": args.preserve_logs,
        "manifest_required": args.manifest_required,
        "review_only": args.review_only,
        "route_marker_written": False,
        "sent_marker_written": False,
        "qq_sent": False,
        "state_written": False,
        "verified_written": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "v4_i2_allowed_to_generate": True,
        "v4_i2_allowed_to_execute": False,
        "v4_j_allowed_to_generate": True,
        "v4_j_allowed_to_execute": False,
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if missing:
        print(f"\n[BLOCKER] Missing required flags: {missing}", file=sys.stderr)
        sys.exit(2)

    print("\n[INFO] No observe executed. Review-only harness.", file=sys.stderr)


if __name__ == "__main__":
    main()
