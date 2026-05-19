#!/usr/bin/env python3
"""
V4-I.1.1: Controlled Observe Runner Checker

Hardening goals:
- Validate runner source constraints.
- Execute review-only runner preview (no observe execution).
- Parse JSON output and validate safety/phase fields.
- Enforce --date/--window required behavior.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
RUNNER = MODULE_ROOT / "engine" / "v4_observe_runner.py"

REQUIRED_BOOLEAN_FLAGS = [
    "observe_only", "dry_run", "single_window_only",
    "no_push", "no_state_write", "no_verified_write",
    "no_cron", "no_api", "no_key_read", "no_supervisor",
    "watchdog_only_failure", "no_ai_kill_retry",
    "preserve_logs", "manifest_required", "review_only",
]
REQUIRED_VALUE_FLAGS = ["date", "window"]

FORBIDDEN_PATTERNS = [
    "requests.", "api_get(", "safe_outbound_sender", "openclaw_message_send",
    "send_message(", "net_utils.get(", "acquire_lock(", ".kill(", ".retry(",
]


def _base_preview_cmd(date_value: str, window_value: str) -> list[str]:
    return [
        sys.executable,
        str(RUNNER),
        "--observe-only",
        "--dry-run",
        "--single-window-only",
        "--no-push",
        "--no-state-write",
        "--no-verified-write",
        "--no-cron",
        "--no-api",
        "--no-key-read",
        "--no-supervisor",
        "--watchdog-only-failure",
        "--no-ai-kill-retry",
        "--preserve-logs",
        "--manifest-required",
        "--review-only",
        "--date",
        date_value,
        "--window",
        window_value,
    ]


def _extract_json(text: str) -> dict:
    payload = text.strip()
    if not payload:
        raise ValueError("empty stdout")
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        start = payload.find("{")
        end = payload.rfind("}")
        if start >= 0 and end > start:
            return json.loads(payload[start : end + 1])
        raise


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    results = {
        "check_status": "PASS",
        "runner_exists": RUNNER.is_file(),
        "runner_defined": True,
        "all_required_flags_supported": True,
        "date_required_enforced": True,
        "window_required_enforced": True,
        "preview_execution_success": False,
        "preview_json_parse_success": False,
        "command_type": "REVIEW_ONLY_DRAFT",
        "command_must_not_execute": True,
        "runner_execution_authorization_required": True,
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
        "legacy_v4_12_field_found": False,
        "v4_i2_allowed_to_generate": True,
        "v4_i2_allowed_to_execute": False,
        "v4_j_allowed_to_generate": True,
        "v4_j_allowed_to_execute": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "blockers": [],
        "warnings": [],
    }

    if not results["runner_exists"]:
        results["blockers"].append("Runner not found: engine/v4_observe_runner.py")
        return _print_and_exit(results)

    content = RUNNER.read_text(encoding="utf-8")

    if 'parser.add_argument("--date", required=True' not in content:
        results["date_required_enforced"] = False
        results["blockers"].append("Runner --date is not required=True")
    if 'parser.add_argument("--window", required=True' not in content:
        results["window_required_enforced"] = False
        results["blockers"].append("Runner --window is not required=True")

    missing_flags = []
    for flag in REQUIRED_BOOLEAN_FLAGS + REQUIRED_VALUE_FLAGS:
        cli_flag = f"--{flag.replace('_', '-')}"
        if cli_flag not in content:
            missing_flags.append(cli_flag)
    if missing_flags:
        results["all_required_flags_supported"] = False
        results["blockers"].append(f"Missing required CLI flags in runner source: {missing_flags}")

    for pat in FORBIDDEN_PATTERNS:
        if pat in content:
            if pat in ("requests.", "api_get("):
                results["forbidden_api_call_found"] = True
            elif pat in ("safe_outbound_sender", "openclaw_message_send", "send_message("):
                results["forbidden_qq_send_found"] = True
            elif pat in ("acquire_lock(",):
                results["lock_created"] = True
            elif pat in (".kill(", ".retry("):
                results["kill_retry_found"] = True
            results["blockers"].append(f"Forbidden pattern '{pat}' found in runner source")

    preview_cmd = _base_preview_cmd(args.date, args.window)
    preview = _run(preview_cmd)
    if preview.returncode != 0:
        results["blockers"].append(
            f"Runner preview command failed (returncode={preview.returncode}): {preview.stderr.strip()}"
        )
    else:
        results["preview_execution_success"] = True
        try:
            preview_json = _extract_json(preview.stdout)
            results["preview_json_parse_success"] = True
        except Exception as exc:
            preview_json = {}
            results["blockers"].append(f"Runner preview stdout is not valid JSON: {exc}")

        if preview_json:
            results["runner_defined"] = bool(preview_json.get("runner_defined", False))
            results["command_type"] = preview_json.get("command_type", "")
            results["command_must_not_execute"] = bool(preview_json.get("command_must_not_execute", False))
            results["runner_execution_authorization_required"] = bool(
                preview_json.get("runner_execution_authorization_required", False)
            )
            results["observe_execution_allowed"] = bool(preview_json.get("observe_execution_allowed", True))
            results["review_only"] = bool(preview_json.get("review_only", False))
            results["dry_run"] = bool(preview_json.get("dry_run", False))
            results["no_push"] = bool(preview_json.get("no_push", False))
            results["no_state_write"] = bool(preview_json.get("no_state_write", False))
            results["no_verified_write"] = bool(preview_json.get("no_verified_write", False))
            results["no_cron"] = bool(preview_json.get("no_cron", False))
            results["no_api"] = bool(preview_json.get("no_api", False))
            results["no_key_read"] = bool(preview_json.get("no_key_read", False))
            results["no_supervisor"] = bool(preview_json.get("no_supervisor", False))
            results["route_marker_written"] = bool(preview_json.get("route_marker_written", True))
            results["sent_marker_written"] = bool(preview_json.get("sent_marker_written", True))
            results["production_verified"] = bool(preview_json.get("production_verified", True))
            results["phase_e_allowed"] = bool(preview_json.get("phase_e_allowed", True))

            if preview_json.get("date") != args.date:
                results["warnings"].append("Preview JSON date does not echo checker --date input")
            if preview_json.get("window") != args.window:
                results["warnings"].append("Preview JSON window does not echo checker --window input")

            if not bool(preview_json.get("required_flags_present", False)):
                results["blockers"].append("Runner preview reports required_flags_present=false")
            if preview_json.get("missing_required_flags"):
                results["blockers"].append(
                    f"Runner preview reports missing_required_flags={preview_json.get('missing_required_flags')}"
                )

            if "v4_12_allowed_to_generate" in preview_json or "v4_12_allowed_to_execute" in preview_json:
                results["legacy_v4_12_field_found"] = True
                results["blockers"].append("Legacy fields v4_12_allowed_* still present in runner output")

            if "v4_i2_allowed_to_generate" not in preview_json or "v4_i2_allowed_to_execute" not in preview_json:
                results["blockers"].append("Runner output missing v4_i2_allowed_* fields")
            else:
                results["v4_i2_allowed_to_generate"] = bool(preview_json.get("v4_i2_allowed_to_generate", False))
                results["v4_i2_allowed_to_execute"] = bool(preview_json.get("v4_i2_allowed_to_execute", True))

            if "v4_j_allowed_to_generate" not in preview_json or "v4_j_allowed_to_execute" not in preview_json:
                results["blockers"].append("Runner output missing v4_j_allowed_* fields")
            else:
                results["v4_j_allowed_to_generate"] = bool(preview_json.get("v4_j_allowed_to_generate", False))
                results["v4_j_allowed_to_execute"] = bool(preview_json.get("v4_j_allowed_to_execute", True))

    missing_date_cmd = [arg for arg in preview_cmd if arg != "--date" and arg != args.date]
    missing_date = _run(missing_date_cmd)
    if missing_date.returncode == 0:
        results["date_required_enforced"] = False
        results["blockers"].append("Runner accepts command without --date; required enforcement failed")

    missing_window_cmd = [arg for arg in preview_cmd if arg != "--window" and arg != args.window]
    missing_window = _run(missing_window_cmd)
    if missing_window.returncode == 0:
        results["window_required_enforced"] = False
        results["blockers"].append("Runner accepts command without --window; required enforcement failed")

    if results["observe_execution_allowed"]:
        results["blockers"].append("observe_execution_allowed is true")
    if not results["command_must_not_execute"]:
        results["blockers"].append("command_must_not_execute is false")
    if not results["runner_execution_authorization_required"]:
        results["blockers"].append("runner_execution_authorization_required is false")
    if results["v4_i2_allowed_to_execute"]:
        results["blockers"].append("v4_i2_allowed_to_execute is true")
    if results["v4_j_allowed_to_execute"]:
        results["blockers"].append("v4_j_allowed_to_execute is true")

    for guard_flag in [
        "review_only", "dry_run", "no_push", "no_state_write", "no_verified_write",
        "no_cron", "no_api", "no_key_read", "no_supervisor",
    ]:
        if not bool(results.get(guard_flag, False)):
            results["blockers"].append(f"{guard_flag} is false")

    if results["route_marker_written"]:
        results["blockers"].append("route_marker_written is true")
    if results["sent_marker_written"]:
        results["blockers"].append("sent_marker_written is true")
    if results["production_verified"]:
        results["blockers"].append("production_verified is true")
    if results["phase_e_allowed"]:
        results["blockers"].append("phase_e_allowed is true")

    _print_and_exit(results)


def _print_and_exit(results: dict) -> None:
    if results["blockers"]:
        results["check_status"] = "BLOCKER"
    elif results["warnings"]:
        results["check_status"] = "WARN"
    else:
        results["check_status"] = "PASS"

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
        for item in results["blockers"]:
            print(f"  ! {item}")
    elif results["warnings"]:
        print(f"\nWARNINGS ({len(results['warnings'])}):")
        for item in results["warnings"]:
            print(f"  ? {item}")

    marker_dir = MODULE_ROOT / "data" / "runtime" / "status"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / "v4_controlled_observe_runner_check.json"
    with open(marker_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")

    if results["check_status"] == "BLOCKER":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
