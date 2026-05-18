#!/usr/bin/env python3
"""Phase D.8.34 — production cron path proof plan (plan-only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_production_cron_path_proof_plan.v1"


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
        "production_cron_path_proof_plan_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "proof_target": "production_cron_path",
        "proof_current_status": "UNPROVEN",
        "execution_performed": False,
        "production_resume_executed": False,
        "supervisor_executed": False,
        "live_worker_executed": False,
        "formal_state_written": False,
        "verified_written": False,
        "qq_sent": False,
        "api_called": False,
        "key_read": False,
        "production_resume_allowed_now": False,
        "cron_enable_allowed": False,
        "qq_push_allowed": False,
        "verified_write_allowed": False,
        "state_write_allowed": False,
        "cron_modified": False,
        "cron_installed": False,
        "cron_started": False,
        "cron_write_allowed": False,
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

    p_d833 = STATUS_DIR / f"v2_active_window_mutation_proof_plan_{date_key}_{window}.json"
    p_d832 = STATUS_DIR / f"v2_real_state_present_proof_plan_{date_key}_{window}.json"
    p_d831 = STATUS_DIR / f"v2_controlled_execution_decision_packet_{date_key}_{window}.json"
    p_d830 = STATUS_DIR / f"v2_final_command_authorization_gate_{date_key}_{window}.json"

    d833 = _load(p_d833)
    d832 = _load(p_d832)
    d831 = _load(p_d831)
    d830 = _load(p_d830)

    warnings: list[str] = []
    blockers: list[str] = []

    sources = {"d833": d833, "d832": d832, "d831": d831, "d830": d830}
    for name, src in sources.items():
        if not src:
            blockers.append(f"{name}_marker_missing")

    if blockers:
        out = _base(date_key, window, "BLOCKER")
        out.update(
            {
                "source_markers": {
                    "d833": str(p_d833),
                    "d832": str(p_d832),
                    "d831": str(p_d831),
                    "d830": str(p_d830),
                },
                "d838_draft": {
                    "allowed_to_generate": True,
                    "allowed_to_execute": False,
                    "scope": "production_path_proof_pack_review_only",
                },
                "proof_plan": {
                    "must_keep_cron_disabled": True,
                    "must_not_write_crontab": True,
                    "must_not_modify_cron_files": True,
                    "must_not_start_scheduled_jobs": True,
                },
                "production_gates": {
                    "production_resume_allowed_now": False,
                    "cron_enable_allowed": False,
                    "qq_push_allowed": False,
                    "verified_write_allowed": False,
                    "state_write_allowed": False,
                },
                "warnings": warnings,
                "blockers": blockers,
                "generated_at": datetime.now(CN).isoformat(),
            }
        )
        out_path = STATUS_DIR / f"v2_production_cron_path_proof_plan_{date_key}_{window}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    for src_name, src in sources.items():
        if _bool(src.get("pipeline_ready"), False):
            blockers.append(f"PIPELINE_READY_LEAK:{src_name}")
        if _bool(src.get("production_verified"), False):
            blockers.append(f"PRODUCTION_VERIFIED_LEAK:{src_name}")

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
            if _bool(src.get(field), False):
                blockers.append(f"FORBIDDEN_TRUE:{field}:{src_name}")

        for g in (
            "production_resume_allowed_now",
            "cron_enable_allowed",
            "qq_push_allowed",
            "verified_write_allowed",
            "state_write_allowed",
        ):
            if _gate(src, g):
                blockers.append(f"GATE_LEAK:{g}:{src_name}")

    if str(d833.get("active_window_mutation_proof_plan_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D833_STATUS_INVALID")
    if str(d832.get("real_state_present_proof_plan_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D832_STATUS_INVALID")
    if str(d831.get("controlled_execution_decision_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D831_STATUS_INVALID")
    if str(d830.get("final_command_authorization_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D830_STATUS_INVALID")

    # ensure no execution permission from previous draft
    d834 = d833.get("d834_draft", {}) if isinstance(d833.get("d834_draft"), dict) else {}
    if _bool(d834.get("allowed_to_execute"), True):
        blockers.append("D834_ALLOWED_TO_EXECUTE_TRUE")

    warnings.append("PRODUCTION_CRON_PATH_UNPROVEN")

    if blockers:
        status = "BLOCKER" if any(x.startswith("PIPELINE_READY_LEAK") or x.startswith("PRODUCTION_VERIFIED_LEAK") for x in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "source_markers": {
                "d833": str(p_d833),
                "d832": str(p_d832),
                "d831": str(p_d831),
                "d830": str(p_d830),
            },
            "d830_status": d830.get("final_command_authorization_status"),
            "d831_status": d831.get("controlled_execution_decision_status"),
            "d832_status": d832.get("real_state_present_proof_plan_status"),
            "d833_status": d833.get("active_window_mutation_proof_plan_status"),
            "proof_plan": {
                "must_keep_cron_disabled": True,
                "must_not_write_crontab": True,
                "must_not_modify_cron_files": True,
                "must_not_start_scheduled_jobs": True,
                "must_not_resume_production_now": True,
            },
            "d838_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "production_path_proof_pack_review_only",
            },
            "production_gates": {
                "production_resume_allowed_now": False,
                "cron_enable_allowed": False,
                "qq_push_allowed": False,
                "verified_write_allowed": False,
                "state_write_allowed": False,
            },
            "warnings": warnings,
            "blockers": blockers,
            "generated_at": datetime.now(CN).isoformat(),
        }
    )

    out_path = STATUS_DIR / f"v2_production_cron_path_proof_plan_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
