#!/usr/bin/env python3
"""Phase D.8.8 checker for controlled single-window resume marker."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_controlled_single_window_resume_check.v1"

SECRET_PAT = re.compile(r"APIFOOTBALL_KEY|OPENCLAW_APIFOOTBALL_KEY|x-apisports-key|sk-[A-Za-z0-9]{20,}")


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=BASE_DIR, text=True).strip()


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _staged_flags() -> dict[str, bool]:
    staged = _run(["git", "diff", "--cached", "--name-only"])
    files = [x.strip() for x in staged.splitlines() if x.strip()]
    return {
        "runtime_staged": any(f.startswith("data/runtime/") for f in files),
        "paper_staged": any(f.startswith("data/paper_trading/") for f in files),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = str(args.date).replace("-", "")
    window = args.window

    marker_path = STATUS_DIR / f"v2_controlled_single_window_resume_{date_key}_{window}.json"
    out_path = STATUS_DIR / f"v2_controlled_single_window_resume_check_{date_key}_{window}.json"

    warnings: list[str] = []
    errors: list[str] = []

    if not marker_path.exists():
        result = {
            "schema_version": SCHEMA_VERSION,
            "date": date_key,
            "window": window,
            "status": "BLOCKER",
            "errors": ["marker_missing"],
            "warnings": [],
            "generated_at": datetime.now(CN).isoformat(),
        }
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    marker = _load_json(marker_path, {})

    def expect_true(field: str) -> None:
        if marker.get(field) is not True:
            errors.append(f"{field}_not_true")

    def expect_false(field: str) -> None:
        if marker.get(field) is not False:
            errors.append(f"{field}_not_false")

    if str(marker.get("window")) != window:
        errors.append("window_mismatch")

    expect_true("no_push")
    expect_true("no_settlement_write")
    expect_true("require_preflight")
    expect_false("production_verified")
    expect_false("pipeline_ready")
    expect_false("qq_sent")
    expect_false("verified_written")
    expect_false("cron_modified")
    expect_false("full_cron_enabled")
    expect_false("api_called")
    expect_false("key_read")

    exec_performed = bool(marker.get("execution_performed", False))
    exec_status = str(marker.get("execution_status", "")).upper()
    watchdog_status = str(marker.get("watchdog_status") or "")

    if exec_performed and not watchdog_status:
        errors.append("watchdog_status_missing_when_execution_performed")

    if exec_status == "WARN" and not exec_performed:
        warn_msgs = [str(x) for x in marker.get("warnings", [])] if isinstance(marker.get("warnings", []), list) else []
        if not any("plan_only" in w.lower() or "no_safe_execution" in w.lower() for w in warn_msgs):
            errors.append("warn_plan_only_without_reason")

    marker_text = marker_path.read_text(encoding="utf-8", errors="replace")
    if SECRET_PAT.search(marker_text):
        errors.append("secret_pattern_detected")

    staged = _staged_flags()
    if staged["runtime_staged"]:
        errors.append("runtime_artifacts_staged")
    if staged["paper_staged"]:
        errors.append("paper_trading_staged")

    if exec_status in {"BLOCKER", "FAIL"}:
        status = "FAIL"
    elif errors:
        status = "FAIL"
    elif exec_status == "WARN":
        status = "WARN"
    else:
        status = "PASS"

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "window": window,
        "status": status,
        "execution_status": exec_status,
        "execution_performed": exec_performed,
        "no_push": marker.get("no_push"),
        "no_settlement_write": marker.get("no_settlement_write"),
        "require_preflight": marker.get("require_preflight"),
        "production_verified": marker.get("production_verified"),
        "pipeline_ready": marker.get("pipeline_ready"),
        "qq_sent": marker.get("qq_sent"),
        "verified_written": marker.get("verified_written"),
        "cron_modified": marker.get("cron_modified"),
        "full_cron_enabled": marker.get("full_cron_enabled"),
        "api_called": marker.get("api_called"),
        "key_read": marker.get("key_read"),
        "watchdog_status": marker.get("watchdog_status"),
        "preflight_status": marker.get("preflight_status"),
        "reason_codes": marker.get("reason_codes", []),
        "warnings": warnings,
        "errors": errors,
        "generated_at": datetime.now(CN).isoformat(),
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
