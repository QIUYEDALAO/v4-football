#!/usr/bin/env python3
"""Phase D.8.31 — controlled execution decision packet (decision-only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_controlled_execution_decision_packet.v1"


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
        "controlled_execution_decision_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "decision_only": True,
        "production_execution_authorized": False,
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

    p_d830 = STATUS_DIR / f"v2_final_command_authorization_gate_{date_key}_{window}.json"
    d830 = _load(p_d830)

    warnings: list[str] = []
    blockers: list[str] = []

    if not d830:
        blockers.append("D830_MARKER_MISSING")

    if blockers:
        out = _base(date_key, window, "BLOCKER")
        out.update(
            {
                "source_marker": str(p_d830),
                "recommended_next": "REAL_PROOF_PLANS_OR_PAUSE",
                "phase_e_recommended": False,
                "d832_draft": {
                    "allowed_to_generate": True,
                    "allowed_to_execute": False,
                    "scope": "real_state_present_proof_plan_only",
                },
                "d833_draft": {
                    "allowed_to_generate": True,
                    "allowed_to_execute": False,
                    "scope": "active_window_mutation_proof_plan_only",
                },
                "warnings": warnings,
                "blockers": blockers,
                "generated_at": datetime.now(CN).isoformat(),
            }
        )
        out_path = STATUS_DIR / f"v2_controlled_execution_decision_packet_{date_key}_{window}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    if str(d830.get("final_command_authorization_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D830_STATUS_INVALID")

    if _bool(d830.get("pipeline_ready"), False):
        blockers.append("PIPELINE_READY_LEAK")
    if _bool(d830.get("production_verified"), False):
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
        if _bool(d830.get(field), False):
            blockers.append(f"FORBIDDEN_TRUE:{field}")

    for g in (
        "production_resume_allowed_now",
        "cron_enable_allowed",
        "qq_push_allowed",
        "verified_write_allowed",
        "state_write_allowed",
    ):
        if _gate(d830, g):
            blockers.append(f"GATE_LEAK:{g}")

    d831 = d830.get("d831_draft", {}) if isinstance(d830.get("d831_draft"), dict) else {}
    if not _bool(d831.get("allowed_to_generate"), False):
        blockers.append("D831_ALLOWED_TO_GENERATE_FALSE")
    if _bool(d831.get("allowed_to_execute"), True):
        blockers.append("D831_ALLOWED_TO_EXECUTE_TRUE")

    if _bool(d830.get("command_authorization_grants_execution"), True):
        blockers.append("AUTHORIZATION_GRANTS_EXECUTION_TRUE")

    for w in d830.get("warnings", []) if isinstance(d830.get("warnings"), list) else []:
        warnings.append(str(w))

    if blockers:
        status = "BLOCKER" if any(x in {"PIPELINE_READY_LEAK", "PRODUCTION_VERIFIED_LEAK"} for x in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "source_marker": str(p_d830),
            "d830_status": d830.get("final_command_authorization_status"),
            "recommended_next": "REAL_PROOF_PLANS_OR_PAUSE",
            "phase_e_recommended": False,
            "d832_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "real_state_present_proof_plan_only",
            },
            "d833_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "active_window_mutation_proof_plan_only",
            },
            "decision_options": [
                "pause",
                "prepare_real_state_present_proof_plan",
                "prepare_active_window_mutation_proof_plan",
            ],
            "warnings": warnings,
            "blockers": blockers,
            "generated_at": datetime.now(CN).isoformat(),
        }
    )

    out_path = STATUS_DIR / f"v2_controlled_execution_decision_packet_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
