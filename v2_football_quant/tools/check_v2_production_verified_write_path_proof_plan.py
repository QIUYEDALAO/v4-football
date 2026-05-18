#!/usr/bin/env python3
"""Phase D.8.36 — production verified write path proof plan (plan-only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_production_verified_write_path_proof_plan.v1"


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
        "production_verified_write_path_proof_plan_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "proof_target": "production_verified_path",
        "proof_current_status": "UNPROVEN",
        "execution_performed": False,
        "production_resume_executed": False,
        "supervisor_executed": False,
        "live_worker_executed": False,
        "formal_state_written": False,
        "qq_sent": False,
        "cron_modified": False,
        "api_called": False,
        "key_read": False,
        "production_resume_allowed_now": False,
        "cron_enable_allowed": False,
        "qq_push_allowed": False,
        "verified_write_allowed": False,
        "state_write_allowed": False,
        "verified_written": False,
        "paper_trading_verify_date_called": False,
        "settlement_rerun": False,
        "historical_verified_modified": False,
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

    p_d835 = STATUS_DIR / f"v2_production_qq_path_proof_plan_{date_key}_{window}.json"
    p_d834 = STATUS_DIR / f"v2_production_cron_path_proof_plan_{date_key}_{window}.json"
    p_d831 = STATUS_DIR / f"v2_controlled_execution_decision_packet_{date_key}_{window}.json"
    p_d830 = STATUS_DIR / f"v2_final_command_authorization_gate_{date_key}_{window}.json"

    d835 = _load(p_d835)
    d834 = _load(p_d834)
    d831 = _load(p_d831)
    d830 = _load(p_d830)

    warnings: list[str] = []
    blockers: list[str] = []

    sources = {"d835": d835, "d834": d834, "d831": d831, "d830": d830}
    for name, src in sources.items():
        if not src:
            blockers.append(f"{name}_marker_missing")

    if blockers:
        out = _base(date_key, window, "BLOCKER")
        out.update(
            {
                "source_markers": {
                    "d835": str(p_d835),
                    "d834": str(p_d834),
                    "d831": str(p_d831),
                    "d830": str(p_d830),
                },
                "d838_draft": {
                    "allowed_to_generate": True,
                    "allowed_to_execute": False,
                    "scope": "production_path_proof_pack_review_only",
                },
                "proof_plan": {
                    "must_keep_verified_write_disabled": True,
                    "must_not_call_verify_date": True,
                    "must_not_rerun_settlement": True,
                    "must_not_modify_historical_verified": True,
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
        out_path = STATUS_DIR / f"v2_production_verified_write_path_proof_plan_{date_key}_{window}.json"
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

    if str(d835.get("production_qq_path_proof_plan_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D835_STATUS_INVALID")
    if str(d834.get("production_cron_path_proof_plan_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D834_STATUS_INVALID")
    if str(d831.get("controlled_execution_decision_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D831_STATUS_INVALID")
    if str(d830.get("final_command_authorization_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D830_STATUS_INVALID")

    d838 = d835.get("d838_draft", {}) if isinstance(d835.get("d838_draft"), dict) else {}
    if _bool(d838.get("allowed_to_execute"), True):
        blockers.append("D838_ALLOWED_TO_EXECUTE_TRUE")

    warnings.append("PRODUCTION_VERIFIED_PATH_UNPROVEN")

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
                "d835": str(p_d835),
                "d834": str(p_d834),
                "d831": str(p_d831),
                "d830": str(p_d830),
            },
            "d830_status": d830.get("final_command_authorization_status"),
            "d831_status": d831.get("controlled_execution_decision_status"),
            "d834_status": d834.get("production_cron_path_proof_plan_status"),
            "d835_status": d835.get("production_qq_path_proof_plan_status"),
            "proof_plan": {
                "must_keep_verified_write_disabled": True,
                "must_not_call_verify_date": True,
                "must_not_rerun_settlement": True,
                "must_not_modify_historical_verified": True,
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

    out_path = STATUS_DIR / f"v2_production_verified_write_path_proof_plan_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
