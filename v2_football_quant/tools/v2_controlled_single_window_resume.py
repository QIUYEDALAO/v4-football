#!/usr/bin/env python3
"""Phase D.8.8 — V2 controlled single-window resume execution (guarded observe).

This tool executes a strictly controlled single-window observe flow:
- requires --no-push --no-settlement-write --require-preflight
- never enables cron, never sends QQ, never writes verified
- runs preflight dry-run as execution evidence
- records auditable marker for D.8.8
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_controlled_single_window_resume.v1"


def _run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=BASE_DIR, text=True, capture_output=True)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _staged_flags() -> dict[str, bool]:
    p = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=BASE_DIR, text=True, capture_output=True)
    files = [x.strip() for x in (p.stdout or "").splitlines() if x.strip()]
    return {
        "runtime_staged": any(f.startswith("data/runtime/") for f in files),
        "paper_staged": any(f.startswith("data/paper_trading/") for f in files),
        "dashboard_html_staged": any(f.startswith("data/runtime/dashboard/") and f.endswith(".html") for f in files),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    parser.add_argument("--window", default="midday", choices=["midday"])
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--no-settlement-write", action="store_true")
    parser.add_argument("--require-preflight", action="store_true")
    # forbidden flags (must remain false)
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--write-verified", action="store_true")
    parser.add_argument("--production-verified", action="store_true")
    args = parser.parse_args()

    date_key = str(args.date).replace("-", "")
    window = args.window

    warnings: list[str] = []
    blockers: list[str] = []

    if not args.no_push:
        blockers.append("missing_required_flag_no_push")
    if not args.no_settlement_write:
        blockers.append("missing_required_flag_no_settlement_write")
    if not args.require_preflight:
        blockers.append("missing_required_flag_require_preflight")
    if args.push:
        blockers.append("forbidden_flag_push_true")
    if args.write_verified:
        blockers.append("forbidden_flag_write_verified_true")
    if args.production_verified:
        blockers.append("forbidden_flag_production_verified_true")

    approval = _load_json(STATUS_DIR / f"v2_limited_resume_approval_packet_{date_key}.json", {})
    if not approval:
        blockers.append("approval_packet_missing")
    if bool(approval.get("resume_execution_allowed", False)):
        blockers.append("approval_packet_resume_execution_allowed_true")
    if bool(approval.get("cron_enable_allowed", False)):
        blockers.append("approval_packet_cron_enable_allowed_true")
    if bool(approval.get("qq_push_allowed", False)):
        blockers.append("approval_packet_qq_push_allowed_true")
    if bool(approval.get("production_verified", False)):
        blockers.append("approval_packet_production_verified_true")

    # Controlled execution: preflight dry-run only (no production task trigger)
    execution_performed = False
    preflight_status = "MISSING"
    reason_codes: list[str] = []
    preflight_rc = None

    if not blockers:
        preflight_cmd = [
            "python3",
            "tools/v2_settlement_preflight_dryrun.py",
            "--date",
            date_key,
        ]
        preflight_rc, preflight_out, preflight_err = _run(preflight_cmd)
        execution_performed = True
        # dryrun returns 1 when blocked (expected for 20260517); 0 if allowed
        if preflight_rc not in (0, 1):
            blockers.append("preflight_dryrun_unexpected_exit")
            warnings.append(f"preflight_exit_code={preflight_rc}")
        preflight_marker = _load_json(STATUS_DIR / f"v2_settlement_preflight_{date_key}.json", {})
        decision = preflight_marker.get("decision", {}) if isinstance(preflight_marker, dict) else {}
        preflight_status = str(decision.get("status") or "MISSING").upper()
        reason_codes = [str(x) for x in decision.get("reason_codes", [])] if isinstance(decision.get("reason_codes", []), list) else []
        if preflight_status in {"MISSING", ""}:
            warnings.append("preflight_status_missing_in_marker")

        if preflight_out.strip() == "" and preflight_err.strip() == "":
            warnings.append("preflight_dryrun_no_output")

    wrapper = _load_json(STATUS_DIR / f"v2_settlement_preflight_wrapper_block_test_{date_key}.json", {})
    verify_date_called = bool(wrapper.get("verify_date_called", True)) if isinstance(wrapper, dict) else True
    verified_unchanged = bool(
        wrapper.get("verified_hash_unchanged", False)
        and wrapper.get("verified_mtime_unchanged", False)
        and wrapper.get("verified_size_unchanged", False)
    ) if isinstance(wrapper, dict) else False
    if verify_date_called:
        blockers.append("verify_date_called_true_detected")
    if not verified_unchanged:
        blockers.append("verified_unchanged_proof_missing")

    watchdog = _load_json(STATUS_DIR / "task_status_v2_daily_settle.json", {})
    watchdog_status = str(watchdog.get("status") or "MISSING").upper() if isinstance(watchdog, dict) else "MISSING"
    if watchdog_status == "MISSING":
        warnings.append("watchdog_status_missing")

    staged = _staged_flags()
    if staged["runtime_staged"]:
        blockers.append("runtime_artifacts_staged")
    if staged["paper_staged"]:
        blockers.append("paper_trading_staged")
    if staged["dashboard_html_staged"]:
        warnings.append("dashboard_html_staged_detected")

    qq_sent = False
    verified_written = False
    cron_modified = False
    full_cron_enabled = False
    api_called = False
    key_read = False

    if blockers:
        execution_status = "BLOCKER"
    elif warnings:
        execution_status = "WARN"
    else:
        execution_status = "PASS"

    # If we could not perform controlled observe, downgrade explicitly
    if not execution_performed and not blockers:
        execution_status = "WARN"
        warnings.append("controlled_plan_only_no_safe_execution")

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "window": window,
        "execution_status": execution_status,
        "execution_performed": execution_performed,
        "execution_mode": "controlled_single_window",
        "no_push": True,
        "no_settlement_write": True,
        "require_preflight": True,
        "production_verified": False,
        "pipeline_ready": False,
        "qq_sent": qq_sent,
        "verified_written": verified_written,
        "cron_modified": cron_modified,
        "full_cron_enabled": full_cron_enabled,
        "api_called": api_called,
        "key_read": key_read,
        "watchdog_status": watchdog_status,
        "preflight_status": preflight_status,
        "preflight_exit_code": preflight_rc,
        "reason_codes": reason_codes,
        "warnings": warnings,
        "blockers": blockers,
        "generated_at": datetime.now(CN).isoformat(),
    }

    out = STATUS_DIR / f"v2_controlled_single_window_resume_{date_key}_{window}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if execution_status == "BLOCKER":
        raise SystemExit(2)
    if execution_status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
