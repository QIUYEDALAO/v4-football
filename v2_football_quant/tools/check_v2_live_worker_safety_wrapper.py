#!/usr/bin/env python3
"""Phase D.8.11 checker for v2 live worker safety wrapper marker."""

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
SCHEMA_VERSION = "v2_live_worker_safety_wrapper_check.v1"
SECRET_PAT = re.compile(r"APIFOOTBALL_KEY|OPENCLAW_APIFOOTBALL_KEY|x-apisports-key|sk-[A-Za-z0-9]{20,}")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=BASE_DIR, text=True).strip()


def _staged_flags() -> dict[str, bool]:
    staged = _run(["git", "diff", "--cached", "--name-only"])
    files = [x.strip() for x in staged.splitlines() if x.strip()]
    return {
        "state_staged": any(f.startswith("data/state/") for f in files),
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

    marker_path = STATUS_DIR / f"v2_live_worker_safety_wrapper_{date_key}_{window}.json"
    out_path = STATUS_DIR / f"v2_live_worker_safety_wrapper_check_{date_key}_{window}.json"

    warnings: list[str] = []
    errors: list[str] = []

    if not marker_path.exists():
        result = {
            "schema_version": SCHEMA_VERSION,
            "date": date_key,
            "window": window,
            "status": "BLOCKER",
            "warnings": [],
            "errors": ["marker_missing"],
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

    if marker.get("wrapper_mode") != "plan_only":
        errors.append("wrapper_mode_not_plan_only")
    expect_true("plan_only")
    expect_false("live_worker_executed")
    expect_false("supervisor_executed")
    expect_false("formal_state_written")
    expect_false("qq_sent")
    expect_false("verified_written")
    expect_false("cron_modified")
    expect_false("api_called")
    expect_false("key_read")
    expect_false("production_verified")
    expect_false("pipeline_ready")

    plan = marker.get("future_live_observe_plan")
    if not isinstance(plan, dict):
        errors.append("future_live_observe_plan_not_dict")
    else:
        if plan.get("boss_approval_required") is not True:
            errors.append("future_plan_boss_approval_required_not_true")
        if plan.get("next_gate") != "D.8.12_LIVE_WORKER_OBSERVE_APPROVAL":
            errors.append("future_plan_next_gate_invalid")

    wrapper_status = str(marker.get("wrapper_status", "")).upper()
    if wrapper_status in {"FAIL", "BLOCKER"}:
        errors.append("wrapper_status_not_pass_warn_ready")

    marker_text = marker_path.read_text(encoding="utf-8", errors="replace")
    if SECRET_PAT.search(marker_text):
        errors.append("secret_pattern_detected")

    staged = _staged_flags()
    if staged["state_staged"]:
        errors.append("state_artifacts_staged")
    if staged["runtime_staged"]:
        errors.append("runtime_artifacts_staged")
    if staged["paper_staged"]:
        errors.append("paper_artifacts_staged")

    if errors:
        status = "FAIL"
    elif wrapper_status == "WARN" or marker.get("warnings"):
        status = "WARN"
    else:
        status = "PASS"

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "window": window,
        "status": status,
        "wrapper_status": wrapper_status,
        "wrapper_mode": marker.get("wrapper_mode"),
        "plan_only": marker.get("plan_only"),
        "live_worker_executed": marker.get("live_worker_executed"),
        "supervisor_executed": marker.get("supervisor_executed"),
        "formal_state_written": marker.get("formal_state_written"),
        "qq_sent": marker.get("qq_sent"),
        "verified_written": marker.get("verified_written"),
        "cron_modified": marker.get("cron_modified"),
        "api_called": marker.get("api_called"),
        "key_read": marker.get("key_read"),
        "production_verified": marker.get("production_verified"),
        "pipeline_ready": marker.get("pipeline_ready"),
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
