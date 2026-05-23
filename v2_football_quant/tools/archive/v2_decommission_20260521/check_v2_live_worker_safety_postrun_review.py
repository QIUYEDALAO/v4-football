#!/usr/bin/env python3
"""Phase D.8.11 post-wrapper review checker."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_live_worker_safety_postrun_review.v1"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = str(args.date).replace("-", "")
    window = args.window

    wrapper_path = STATUS_DIR / f"v2_live_worker_safety_wrapper_{date_key}_{window}.json"
    out_path = STATUS_DIR / f"v2_live_worker_safety_postrun_review_{date_key}_{window}.json"

    warnings: list[str] = []
    errors: list[str] = []
    blockers: list[str] = []

    if not wrapper_path.exists():
        blockers.append("wrapper_marker_missing")
        result = {
            "schema_version": SCHEMA_VERSION,
            "date": date_key,
            "window": window,
            "review_status": "BLOCKER",
            "current_level": "CODE_READY",
            "pipeline_ready": False,
            "production_verified": False,
            "wrapper_mode": "missing",
            "live_worker_executed": False,
            "supervisor_executed": False,
            "production_resume_executed": False,
            "formal_state_written": False,
            "next_gate_requires_boss": True,
            "next_gate": "D.8.12_LIVE_WORKER_OBSERVE_APPROVAL",
            "warnings": warnings,
            "errors": errors,
            "blockers": blockers,
            "generated_at": datetime.now(CN).isoformat(),
        }
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    marker = _load_json(wrapper_path, {})

    if marker.get("wrapper_mode") != "plan_only":
        errors.append("wrapper_mode_not_plan_only")
    if marker.get("live_worker_executed") is not False:
        errors.append("live_worker_executed_not_false")
    if marker.get("supervisor_executed") is not False:
        errors.append("supervisor_executed_not_false")
    if marker.get("production_resume_executed") is not False:
        errors.append("production_resume_executed_not_false")
    if marker.get("formal_state_written") is not False:
        errors.append("formal_state_written_not_false")
    if marker.get("qq_sent") is not False:
        errors.append("qq_sent_not_false")
    if marker.get("verified_written") is not False:
        errors.append("verified_written_not_false")
    if marker.get("cron_modified") is not False:
        errors.append("cron_modified_not_false")
    if marker.get("api_called") is not False:
        errors.append("api_called_not_false")

    if marker.get("production_verified") is not False:
        blockers.append("production_verified_true")

    plan = marker.get("future_live_observe_plan") if isinstance(marker.get("future_live_observe_plan"), dict) else {}
    if plan.get("next_gate") != "D.8.12_LIVE_WORKER_OBSERVE_APPROVAL":
        errors.append("next_gate_invalid")
    if plan.get("boss_approval_required") is not True:
        errors.append("next_gate_boss_approval_required_not_true")

    wrapper_status = str(marker.get("wrapper_status", "")).upper()

    if blockers:
        review_status = "BLOCKER"
    elif errors:
        review_status = "FAIL"
    elif warnings or wrapper_status == "WARN":
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
        "wrapper_mode": marker.get("wrapper_mode", "missing"),
        "live_worker_executed": marker.get("live_worker_executed", False),
        "supervisor_executed": marker.get("supervisor_executed", False),
        "production_resume_executed": marker.get("production_resume_executed", False),
        "formal_state_written": marker.get("formal_state_written", False),
        "next_gate_requires_boss": True,
        "next_gate": "D.8.12_LIVE_WORKER_OBSERVE_APPROVAL",
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
