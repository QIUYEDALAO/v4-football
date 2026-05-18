#!/usr/bin/env python3
"""Phase D.8.9 post-run review checker for controlled single-window observe scope."""

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
SCHEMA_VERSION = "v2_controlled_resume_postrun_review.v1"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _staged_files() -> list[str]:
    p = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=BASE_DIR, text=True, capture_output=True)
    return [x.strip() for x in (p.stdout or "").splitlines() if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = str(args.date).replace("-", "")
    window = args.window

    run_path = STATUS_DIR / f"v2_controlled_single_window_resume_{date_key}_{window}.json"
    out_path = STATUS_DIR / f"v2_controlled_resume_postrun_review_{date_key}_{window}.json"

    warnings: list[str] = []
    errors: list[str] = []
    blockers: list[str] = []

    if not run_path.exists():
        blockers.append("d88_run_marker_missing")
        result = {
            "schema_version": SCHEMA_VERSION,
            "date": date_key,
            "window": window,
            "review_status": "BLOCKER",
            "current_level": "CODE_READY",
            "pipeline_ready": False,
            "production_verified": False,
            "execution_scope": "missing",
            "controlled_preflight_observe_performed": False,
            "live_window_worker_executed": False,
            "production_resume_executed": False,
            "qq_sent": False,
            "verified_written": False,
            "cron_modified": False,
            "api_called": False,
            "historical_fail_preserved": False,
            "next_gate_requires_boss": True,
            "warnings": warnings,
            "errors": errors,
            "blockers": blockers,
            "generated_at": datetime.now(CN).isoformat(),
        }
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    run = _load_json(run_path, {})
    if not isinstance(run, dict):
        blockers.append("d88_run_marker_invalid_json")
        run = {}

    settlement_shadow = _load_json(STATUS_DIR / f"v2_settlement_shadow_guard_{date_key}.json", {})
    historical_fail_preserved = bool(
        isinstance(settlement_shadow, dict)
        and str(settlement_shadow.get("status", "")).upper() == "FAIL"
    )
    if not historical_fail_preserved:
        warnings.append("historical_fail_not_explicitly_preserved")

    approval = _load_json(STATUS_DIR / f"v2_limited_resume_approval_packet_{date_key}.json", {})
    if not approval:
        warnings.append("approval_packet_missing_for_cross_check")
    elif bool(approval.get("production_verified", False)):
        blockers.append("approval_packet_production_verified_true")

    def expect_true(name: str) -> None:
        if run.get(name) is not True:
            errors.append(f"{name}_not_true")

    def expect_false(name: str) -> None:
        if run.get(name) is not False:
            errors.append(f"{name}_not_false")

    if run.get("execution_scope") != "preflight_observe_only":
        errors.append("execution_scope_not_preflight_observe_only")

    expect_true("controlled_preflight_observe_performed")
    expect_false("live_window_worker_executed")
    expect_false("production_resume_executed")
    expect_false("production_task_triggered")
    expect_false("qq_sent")
    expect_false("verified_written")
    expect_false("cron_modified")
    expect_false("api_called")
    expect_false("production_verified")
    expect_false("pipeline_ready")

    if run.get("production_verified") is True:
        blockers.append("production_verified_true")
    if run.get("production_resume_executed") is True:
        errors.append("production_resume_executed_true")
    if run.get("qq_sent") is True:
        errors.append("qq_sent_true")
    if run.get("verified_written") is True:
        errors.append("verified_written_true")
    if run.get("cron_modified") is True:
        errors.append("cron_modified_true")
    if run.get("api_called") is True:
        errors.append("api_called_true")

    staged = _staged_files()
    if any(f.startswith("data/runtime/") for f in staged):
        blockers.append("runtime_artifacts_staged")
    if any(f.startswith("data/paper_trading/") for f in staged):
        blockers.append("paper_trading_artifacts_staged")

    if blockers:
        review_status = "BLOCKER"
    elif errors:
        review_status = "FAIL"
    elif warnings or str(run.get("execution_status", "")).upper() == "WARN":
        review_status = "WARN"
    else:
        review_status = "PASS"

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "window": window,
        "review_status": review_status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "execution_scope": run.get("execution_scope", "missing"),
        "controlled_preflight_observe_performed": run.get("controlled_preflight_observe_performed", False),
        "live_window_worker_executed": run.get("live_window_worker_executed", False),
        "production_resume_executed": run.get("production_resume_executed", False),
        "qq_sent": run.get("qq_sent", False),
        "verified_written": run.get("verified_written", False),
        "cron_modified": run.get("cron_modified", False),
        "api_called": run.get("api_called", False),
        "historical_fail_preserved": historical_fail_preserved,
        "next_gate_requires_boss": True,
        "warnings": warnings,
        "errors": errors,
        "blockers": blockers,
        "generated_at": datetime.now(CN).isoformat(),
    }

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if review_status == "BLOCKER":
        raise SystemExit(2)
    if review_status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
