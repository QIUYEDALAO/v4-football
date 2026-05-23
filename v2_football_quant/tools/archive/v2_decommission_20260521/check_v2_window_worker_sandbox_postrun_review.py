#!/usr/bin/env python3
"""Phase D.8.10 post-sandbox review checker."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_window_worker_sandbox_postrun_review.v1"


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

    observe_path = STATUS_DIR / f"v2_window_worker_sandbox_observe_{date_key}_{window}.json"
    out_path = STATUS_DIR / f"v2_window_worker_sandbox_postrun_review_{date_key}_{window}.json"

    warnings: list[str] = []
    blockers: list[str] = []
    errors: list[str] = []

    if not observe_path.exists():
        blockers.append("sandbox_observe_marker_missing")
        result = {
            "schema_version": SCHEMA_VERSION,
            "date": date_key,
            "window": window,
            "review_status": "BLOCKER",
            "current_level": "CODE_READY",
            "pipeline_ready": False,
            "production_verified": False,
            "observe_scope": "missing",
            "live_window_worker_executed": False,
            "production_resume_executed": False,
            "formal_state_unchanged": False,
            "sandbox_result_summary": {},
            "next_gate_requires_boss": True,
            "next_gate": "D.8.11_OR_D.8.12",
            "warnings": warnings,
            "errors": errors,
            "blockers": blockers,
            "generated_at": datetime.now(CN).isoformat(),
        }
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    observe = _load_json(observe_path, {})
    if not isinstance(observe, dict):
        blockers.append("sandbox_observe_marker_invalid_json")
        observe = {}

    if observe.get("observe_scope") != "sandbox_worker_logic_only":
        errors.append("observe_scope_invalid")
    if observe.get("live_window_worker_executed") is not False:
        errors.append("live_window_worker_executed_not_false")
    if observe.get("production_resume_executed") is not False:
        errors.append("production_resume_executed_not_false")
    if observe.get("formal_state_unchanged") is not True:
        errors.append("formal_state_unchanged_not_true")
    if observe.get("qq_sent") is not False:
        errors.append("qq_sent_not_false")
    if observe.get("verified_written") is not False:
        errors.append("verified_written_not_false")
    if observe.get("cron_modified") is not False:
        errors.append("cron_modified_not_false")
    if observe.get("api_called") is not False:
        errors.append("api_called_not_false")
    if observe.get("production_verified") is not False:
        blockers.append("production_verified_true")

    shadow_guard = _load_json(STATUS_DIR / f"v2_settlement_shadow_guard_{date_key}.json", {})
    historical_fail_preserved = bool(isinstance(shadow_guard, dict) and str(shadow_guard.get("status", "")).upper() == "FAIL")
    if not historical_fail_preserved:
        warnings.append("historical_fail_not_preserved_or_missing")

    observe_status = str(observe.get("observe_status", "")).upper()
    if observe_status == "BLOCKER":
        blockers.append("observe_status_blocker")
    elif observe_status == "FAIL":
        errors.append("observe_status_fail")

    if blockers:
        review_status = "BLOCKER"
    elif errors:
        review_status = "FAIL"
    elif warnings or observe_status == "WARN":
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
        "observe_scope": observe.get("observe_scope", "missing"),
        "live_window_worker_executed": observe.get("live_window_worker_executed", False),
        "production_resume_executed": observe.get("production_resume_executed", False),
        "formal_state_unchanged": observe.get("formal_state_unchanged", False),
        "sandbox_result_summary": {
            "observe_status": observe_status,
            "window_status": (observe.get("worker_output") or {}).get("WINDOW_STATUS") if isinstance(observe.get("worker_output"), dict) else None,
            "reason": (observe.get("worker_output") or {}).get("REASON") if isinstance(observe.get("worker_output"), dict) else None,
            "sandbox_new_locks_count": (observe.get("sandbox_diff") or {}).get("sandbox_new_locks_count") if isinstance(observe.get("sandbox_diff"), dict) else None,
            "sandbox_official_bet_locked_count": (observe.get("sandbox_diff") or {}).get("sandbox_official_bet_locked_count") if isinstance(observe.get("sandbox_diff"), dict) else None,
        },
        "next_gate_requires_boss": True,
        "next_gate": "D.8.11_OR_D.8.12",
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
