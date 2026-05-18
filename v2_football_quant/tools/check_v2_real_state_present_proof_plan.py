#!/usr/bin/env python3
"""Phase D.8.32 — real state-present proof plan (plan-only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_real_state_present_proof_plan.v1"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    return default


def _base(date_key: str, window: str, status: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "window": window,
        "real_state_present_proof_plan_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "proof_target": "real_state_present_case",
        "proof_current_status": "UNPROVEN",
        "synthetic_proof_accepted_as_real": False,
        "formal_daily_pool_executed": False,
        "selected_fixtures_written": False,
        "execution_performed": False,
        "production_resume_executed": False,
        "supervisor_executed": False,
        "live_worker_executed": False,
        "formal_state_written": False,
        "verified_written": False,
        "qq_sent": False,
        "cron_modified": False,
        "api_called": False,
        "key_read": False,
        "production_resume_allowed_now": False,
        "cron_enable_allowed": False,
        "qq_push_allowed": False,
        "verified_write_allowed": False,
        "state_write_allowed": False,
    }


def _gate(src: dict[str, Any], field: str) -> bool:
    pg = src.get("production_gates", {}) if isinstance(src.get("production_gates"), dict) else {}
    return _bool(pg.get(field), _bool(src.get(field), False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    p_d831 = STATUS_DIR / f"v2_controlled_execution_decision_packet_{date_key}_{window}.json"
    d831 = _load(p_d831)

    warnings: list[str] = []
    blockers: list[str] = []

    if not d831:
        blockers.append("D831_MARKER_MISSING")

    if blockers:
        out = _base(date_key, window, "BLOCKER")
        out.update(
            {
                "source_marker": str(p_d831),
                "proof_plan": {
                    "requires_real_daily_pool_output": True,
                    "requires_real_selected_fixtures_file": True,
                    "synthetic_only_not_acceptable_for_real_proof": True,
                    "must_not_execute_daily_pool_now": True,
                    "must_not_write_state_now": True,
                },
                "d834_draft": {
                    "allowed_to_generate": True,
                    "allowed_to_execute": False,
                    "scope": "real_state_present_proof_review_only",
                },
                "warnings": warnings,
                "blockers": blockers,
                "generated_at": datetime.now(CN).isoformat(),
            }
        )
        out_path = STATUS_DIR / f"v2_real_state_present_proof_plan_{date_key}_{window}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    if str(d831.get("controlled_execution_decision_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D831_STATUS_INVALID")

    if _bool(d831.get("pipeline_ready"), False):
        blockers.append("PIPELINE_READY_LEAK")
    if _bool(d831.get("production_verified"), False):
        blockers.append("PRODUCTION_VERIFIED_LEAK")

    for field in (
        "execution_performed",
        "production_resume_executed",
        "supervisor_executed",
        "live_worker_executed",
        "formal_state_written",
        "verified_written",
        "qq_sent",
        "cron_modified",
        "api_called",
        "key_read",
    ):
        if _bool(d831.get(field), False):
            blockers.append(f"FORBIDDEN_TRUE:{field}")

    for g in (
        "production_resume_allowed_now",
        "cron_enable_allowed",
        "qq_push_allowed",
        "verified_write_allowed",
        "state_write_allowed",
    ):
        if _gate(d831, g):
            blockers.append(f"GATE_LEAK:{g}")

    if _bool(d831.get("production_execution_authorized"), True):
        blockers.append("PRODUCTION_EXECUTION_AUTHORIZED_TRUE")

    d832 = d831.get("d832_draft", {}) if isinstance(d831.get("d832_draft"), dict) else {}
    if not _bool(d832.get("allowed_to_generate"), False):
        blockers.append("D832_ALLOWED_TO_GENERATE_FALSE")
    if _bool(d832.get("allowed_to_execute"), True):
        blockers.append("D832_ALLOWED_TO_EXECUTE_TRUE")

    # Keep proof status UNPROVEN in this phase
    warnings.append("REAL_STATE_PRESENT_CASE_UNPROVEN")

    if blockers:
        status = "BLOCKER" if any(x in {"PIPELINE_READY_LEAK", "PRODUCTION_VERIFIED_LEAK"} for x in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "source_marker": str(p_d831),
            "d831_status": d831.get("controlled_execution_decision_status"),
            "proof_plan": {
                "requires_real_daily_pool_output": True,
                "requires_real_selected_fixtures_file": True,
                "synthetic_only_not_acceptable_for_real_proof": True,
                "must_not_execute_daily_pool_now": True,
                "must_not_write_state_now": True,
                "must_not_resume_production_now": True,
            },
            "d834_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "real_state_present_proof_review_only",
            },
            "warnings": warnings,
            "blockers": blockers,
            "generated_at": datetime.now(CN).isoformat(),
        }
    )

    out_path = STATUS_DIR / f"v2_real_state_present_proof_plan_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
