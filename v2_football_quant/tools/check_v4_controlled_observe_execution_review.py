#!/usr/bin/env python3
"""
V4-I.2: Controlled Observe Execution Review Checker

Generates review evidence by executing four-window runner previews (no-exec only)
and validating that all safety gates remain closed.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = MODULE_ROOT / "docs"
RUNNER = MODULE_ROOT / "engine" / "v4_observe_runner.py"

EXECUTION_REVIEW_DOC = DOCS_DIR / "V4_CONTROLLED_OBSERVE_EXECUTION_REVIEW.md"
FOUR_WINDOW_MATRIX_DOC = DOCS_DIR / "V4_CONTROLLED_OBSERVE_FOUR_WINDOW_PREVIEW_MATRIX.md"

WINDOWS = ["early", "midday", "evening", "night"]


def _base_cmd(window: str) -> list[str]:
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
        "20260519",
        "--window",
        window,
    ]


def _run_window(window: str) -> tuple[int, dict, str]:
    env = os.environ.copy()
    env["OPENCLAW_NO_PUSH"] = "1"
    proc = subprocess.run(_base_cmd(window), capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        return proc.returncode, {}, proc.stderr.strip()
    try:
        payload = json.loads(proc.stdout)
    except Exception as exc:
        return 99, {}, f"JSON parse error: {exc}"
    return 0, payload, ""


def main() -> int:
    results = {
        "check_status": "PASS",
        "execution_review_exists": EXECUTION_REVIEW_DOC.is_file(),
        "four_window_matrix_exists": FOUR_WINDOW_MATRIX_DOC.is_file(),
        "windows_tested": 0,
        "windows_passed": 0,
        "all_windows_review_only_ready": True,
        "all_windows_no_exec": True,
        "all_windows_no_push": True,
        "all_windows_no_state": True,
        "all_windows_no_verified": True,
        "all_windows_no_api": True,
        "all_windows_no_key_read": True,
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
        "window_results": {},
        "blockers": [],
        "warnings": [],
    }

    if not results["execution_review_exists"]:
        results["blockers"].append("Missing docs/V4_CONTROLLED_OBSERVE_EXECUTION_REVIEW.md")
    if not results["four_window_matrix_exists"]:
        results["blockers"].append("Missing docs/V4_CONTROLLED_OBSERVE_FOUR_WINDOW_PREVIEW_MATRIX.md")

    if not RUNNER.is_file():
        results["blockers"].append("Missing engine/v4_observe_runner.py")
        return _finish(results)

    for w in WINDOWS:
        results["windows_tested"] += 1
        rc, payload, err = _run_window(w)
        if rc != 0:
            results["blockers"].append(f"Window {w} preview failed: rc={rc}, err={err}")
            results["window_results"][w] = {"status": "BLOCKER", "returncode": rc, "error": err}
            continue

        row = {
            "runner_status": payload.get("runner_status"),
            "command_must_not_execute": payload.get("command_must_not_execute"),
            "observe_execution_allowed": payload.get("observe_execution_allowed"),
            "no_push": payload.get("no_push"),
            "no_state_write": payload.get("no_state_write"),
            "no_verified_write": payload.get("no_verified_write"),
            "no_cron": payload.get("no_cron"),
            "no_api": payload.get("no_api"),
            "no_key_read": payload.get("no_key_read"),
            "route_marker_written": payload.get("route_marker_written"),
            "sent_marker_written": payload.get("sent_marker_written"),
            "qq_sent": payload.get("qq_sent"),
            "state_written": payload.get("state_written"),
            "verified_written": payload.get("verified_written"),
            "production_verified": payload.get("production_verified"),
            "phase_e_allowed": payload.get("phase_e_allowed"),
            "v4_i2_allowed_to_generate": payload.get("v4_i2_allowed_to_generate"),
            "v4_i2_allowed_to_execute": payload.get("v4_i2_allowed_to_execute"),
            "v4_j_allowed_to_generate": payload.get("v4_j_allowed_to_generate"),
            "v4_j_allowed_to_execute": payload.get("v4_j_allowed_to_execute"),
        }
        results["window_results"][w] = row

        ok = True
        if row["runner_status"] != "REVIEW_ONLY_READY":
            ok = False
            results["all_windows_review_only_ready"] = False
            results["blockers"].append(f"Window {w}: runner_status != REVIEW_ONLY_READY")
        if row["command_must_not_execute"] is not True:
            ok = False
            results["all_windows_no_exec"] = False
            results["blockers"].append(f"Window {w}: command_must_not_execute != true")
        if row["observe_execution_allowed"] is not False:
            ok = False
            results["all_windows_no_exec"] = False
            results["blockers"].append(f"Window {w}: observe_execution_allowed != false")
        if row["no_push"] is not True:
            ok = False
            results["all_windows_no_push"] = False
            results["blockers"].append(f"Window {w}: no_push != true")
        if row["no_state_write"] is not True or row["state_written"] is not False:
            ok = False
            results["all_windows_no_state"] = False
            results["blockers"].append(f"Window {w}: state guard/write mismatch")
        if row["no_verified_write"] is not True or row["verified_written"] is not False:
            ok = False
            results["all_windows_no_verified"] = False
            results["blockers"].append(f"Window {w}: verified guard/write mismatch")
        if row["no_api"] is not True:
            ok = False
            results["all_windows_no_api"] = False
            results["blockers"].append(f"Window {w}: no_api != true")
        if row["no_key_read"] is not True:
            ok = False
            results["all_windows_no_key_read"] = False
            results["blockers"].append(f"Window {w}: no_key_read != true")

        if row["route_marker_written"] is not False:
            ok = False
            results["route_marker_written"] = True
            results["blockers"].append(f"Window {w}: route_marker_written != false")
        if row["sent_marker_written"] is not False:
            ok = False
            results["sent_marker_written"] = True
            results["blockers"].append(f"Window {w}: sent_marker_written != false")
        if row["qq_sent"] is not False:
            ok = False
            results["qq_sent"] = True
            results["blockers"].append(f"Window {w}: qq_sent != false")

        if row["production_verified"] is not False:
            ok = False
            results["production_verified"] = True
            results["blockers"].append(f"Window {w}: production_verified != false")
        if row["phase_e_allowed"] is not False:
            ok = False
            results["phase_e_allowed"] = True
            results["blockers"].append(f"Window {w}: phase_e_allowed != false")

        if row["v4_i2_allowed_to_generate"] is not True:
            ok = False
            results["blockers"].append(f"Window {w}: v4_i2_allowed_to_generate != true")
        if row["v4_i2_allowed_to_execute"] is not False:
            ok = False
            results["v4_i2_allowed_to_execute"] = True
            results["blockers"].append(f"Window {w}: v4_i2_allowed_to_execute != false")
        if row["v4_j_allowed_to_generate"] is not True:
            ok = False
            results["blockers"].append(f"Window {w}: v4_j_allowed_to_generate != true")
        if row["v4_j_allowed_to_execute"] is not False:
            ok = False
            results["v4_j_allowed_to_execute"] = True
            results["blockers"].append(f"Window {w}: v4_j_allowed_to_execute != false")

        if ok:
            results["windows_passed"] += 1

    # Recompute aggregate booleans using tested windows
    if results["windows_passed"] != len(WINDOWS):
        results["all_windows_review_only_ready"] = False if results["windows_passed"] < len(WINDOWS) else results["all_windows_review_only_ready"]

    return _finish(results)


def _finish(results: dict) -> int:
    if results["blockers"]:
        results["check_status"] = "BLOCKER"
    elif results["warnings"]:
        results["check_status"] = "WARN"
    else:
        results["check_status"] = "PASS"

    print("=" * 68)
    print("V4 CONTROLLED OBSERVE EXECUTION REVIEW CHECKER")
    print("=" * 68)
    print(f"Status: {results['check_status']}")
    for k, v in results.items():
        if k in ("blockers", "warnings", "window_results"):
            continue
        print(f"  {k}: {v}")

    print("\nWindow Results:")
    for w in WINDOWS:
        print(f"  {w}: {results.get('window_results', {}).get(w, {})}")

    if results["blockers"]:
        print(f"\nBLOCKERS ({len(results['blockers'])}):")
        for b in results["blockers"]:
            print(f"  ! {b}")
    elif results["warnings"]:
        print(f"\nWARNINGS ({len(results['warnings'])}):")
        for w in results["warnings"]:
            print(f"  ? {w}")

    marker_dir = MODULE_ROOT / "data" / "runtime" / "status"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / "v4_controlled_observe_execution_review_check.json"
    with open(marker_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    print(f"\nMarker: {marker_path} (NOT committed)")

    return 1 if results["check_status"] == "BLOCKER" else 0


if __name__ == "__main__":
    raise SystemExit(main())
