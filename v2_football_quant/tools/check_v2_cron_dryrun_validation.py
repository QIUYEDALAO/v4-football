#!/usr/bin/env python3
"""Phase D.8.2 — Controlled Cron Dry-run Validation (read-only)."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_cron_dryrun_validation.v1"
CN = timezone(timedelta(hours=8))


CRON_ENTRY_FILES = [
    BASE_DIR / "engine" / "daily_runner.py",
    BASE_DIR / "engine" / "task_watchdog.py",
    BASE_DIR / "engine" / "v2_window_checker_with_watchdog.py",
    BASE_DIR / "engine" / "v2_settle_with_watchdog.py",
    BASE_DIR / "engine" / "v2_daily_pool_summary.py",
]


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=BASE_DIR, text=True).strip()


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _scan_next_run_at() -> tuple[bool, list[str], list[str]]:
    files: list[str] = []
    active_files: list[str] = []
    for p in sorted(STATUS_DIR.glob("*.json")):
        d = _load_json(p, None)
        if not isinstance(d, dict):
            continue
        if "nextRunAt" in d:
            files.append(str(p))
            v = d.get("nextRunAt")
            if v not in (None, "", "null", "None"):
                active_files.append(str(p))
    return bool(active_files), files, active_files


def _scan_task_running() -> tuple[bool, list[str]]:
    running: list[str] = []
    # D.8.2 only evaluates V2 resume risk; do not fail on unrelated modules (e.g. V4).
    for p in sorted(STATUS_DIR.glob("task_status_v2*.json")):
        d = _load_json(p, {})
        status = str(d.get("status", "")).upper()
        if status in {"RUNNING", "STARTED", "IN_PROGRESS"}:
            running.append(str(p))
    return bool(running), running


def _scan_staged_flags() -> dict[str, bool]:
    staged = _run(["git", "diff", "--cached", "--name-only"])
    files = [x.strip() for x in staged.splitlines() if x.strip()]
    return {
        "runtime_staged": any(f.startswith("data/runtime/") for f in files),
        "paper_staged": any(f.startswith("data/paper_trading/") for f in files),
        "dashboard_html_staged": any(f.startswith("data/runtime/dashboard/") and f.endswith(".html") for f in files),
        "cron_files_staged": any(f in {
            "engine/daily_runner.py",
            "engine/task_watchdog.py",
            "engine/v2_window_checker_with_watchdog.py",
            "engine/v2_settle_with_watchdog.py",
            "engine/v2_daily_pool_summary.py",
        } for f in files),
    }


def _contains(text: str, needle: str) -> bool:
    return needle in text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    args = parser.parse_args()
    date_key = str(args.date).replace("-", "")

    findings: dict[str, Any] = {}
    risks: list[str] = []
    blockers: list[str] = []

    missing_entry_files = [str(p) for p in CRON_ENTRY_FILES if not p.exists()]
    if missing_entry_files:
        blockers.append("cron_entry_files_missing")

    next_run_active, next_run_files, next_run_active_files = _scan_next_run_at()
    task_running, task_running_files = _scan_task_running()
    staged = _scan_staged_flags()

    settle_wrapper = (BASE_DIR / "engine" / "v2_settle_with_watchdog.py").read_text(encoding="utf-8", errors="replace") if (BASE_DIR / "engine" / "v2_settle_with_watchdog.py").exists() else ""
    pool_script = (BASE_DIR / "engine" / "v2_daily_pool_summary.py").read_text(encoding="utf-8", errors="replace") if (BASE_DIR / "engine" / "v2_daily_pool_summary.py").exists() else ""

    preflight_hook_present = _contains(settle_wrapper, "build_v2_settlement_preflight")
    verify_date_call_present = _contains(settle_wrapper, "verify_date(")

    qq_push_path_present = _contains(pool_script, "--push") and _contains(pool_script, "push_to_qqbot")

    production_verified_true = False
    for p in STATUS_DIR.glob("*.json"):
        d = _load_json(p, None)
        if isinstance(d, dict) and d.get("production_verified") is True:
            production_verified_true = True
            break

    cron_modified = bool(staged["cron_files_staged"])
    cron_started = bool(next_run_active)
    task_triggered = bool(task_running)

    if cron_modified:
        risks.append("cron_files_staged_detected")
    if cron_started:
        risks.append("nextRunAt_active_detected")
    if task_triggered:
        risks.append("task_running_detected")
    if qq_push_path_present:
        risks.append("manual_qq_push_path_exists_must_keep_disabled")
    if not preflight_hook_present or not verify_date_call_present:
        risks.append("settlement_entry_preflight_or_verify_path_unreadable")

    if production_verified_true:
        blockers.append("production_verified_true_detected")
    if staged["runtime_staged"]:
        blockers.append("runtime_artifacts_staged")
    if staged["paper_staged"]:
        blockers.append("paper_trading_staged")
    if staged["dashboard_html_staged"]:
        blockers.append("dashboard_html_staged")

    if blockers:
        status = "BLOCKER"
    elif cron_started or task_triggered:
        status = "FAIL"
    elif risks:
        status = "WARN"
    else:
        status = "PASS"

    findings.update(
        {
            "cron_entry_files": [str(p) for p in CRON_ENTRY_FILES],
            "missing_entry_files": missing_entry_files,
            "task_watchdog_entry": str(BASE_DIR / "engine" / "task_watchdog.py"),
            "daily_runner_entry": str(BASE_DIR / "engine" / "daily_runner.py"),
            "v2_daily_entry": str(BASE_DIR / "engine" / "v2_daily_pool_summary.py"),
            "v2_window_entry": str(BASE_DIR / "engine" / "v2_window_checker_with_watchdog.py"),
            "v2_settle_entry": str(BASE_DIR / "engine" / "v2_settle_with_watchdog.py"),
            "nextRunAt_files": next_run_files,
            "nextRunAt_active_files": next_run_active_files,
            "task_running_files": task_running_files,
            "qq_push_path_present": qq_push_path_present,
            "preflight_hook_present": preflight_hook_present,
            "verify_date_call_present": verify_date_call_present,
        }
    )

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "cron_dryrun_status": status,
        "cron_enable_allowed": False,
        "cron_modified": cron_modified,
        "cron_started": cron_started,
        "task_triggered": task_triggered,
        "no_api": True,
        "no_push": True,
        "no_verified_write": True,
        "no_production_verified": True,
        "findings": findings,
        "risks": risks,
        "blockers": blockers,
        "generated_at": datetime.now(CN).isoformat(),
    }

    out = STATUS_DIR / f"v2_cron_dryrun_validation_{date_key}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if status == "BLOCKER":
        raise SystemExit(2)
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
