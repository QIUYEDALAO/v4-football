#!/usr/bin/env python3
"""Phase D.8.29 — Phase D final decision packet (decision-only, no execution)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_phase_d_final_decision_packet.v1"


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
        "final_decision_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "phase_d_engineering_complete": True,
        "production_resume_ready": False,
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
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    p_d828 = STATUS_DIR / f"v2_production_resume_readiness_matrix_{date_key}_{window}.json"
    p_d827 = STATUS_DIR / f"v2_controlled_execution_simulation_plan_{date_key}_{window}.json"
    p_d826 = STATUS_DIR / f"v2_final_boss_approval_gate_{date_key}_{window}.json"
    p_d825 = STATUS_DIR / f"v2_final_controlled_execution_approval_packet_{date_key}_{window}.json"

    d828 = _load(p_d828)
    d827 = _load(p_d827)
    d826 = _load(p_d826)
    d825 = _load(p_d825)

    warnings: list[str] = []
    blockers: list[str] = []

    for name, src in (("d828", d828), ("d827", d827), ("d826", d826), ("d825", d825)):
        if not src:
            blockers.append(f"{name}_marker_missing")

    if blockers:
        out = _base(date_key, window, "BLOCKER")
        out.update(
            {
                "source_markers": {
                    "d828": str(p_d828),
                    "d827": str(p_d827),
                    "d826": str(p_d826),
                    "d825": str(p_d825),
                },
                "recommended_next": "D8_30_OR_PAUSE",
                "phase_e_recommended": False,
                "d830_draft": {
                    "allowed_to_generate": True,
                    "allowed_to_execute": False,
                    "scope": "final_command_authorization_gate_only",
                },
                "decision_options": [
                    "pause",
                    "D8_30_final_command_authorization_gate",
                    "defer_phase_e",
                ],
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
        out_path = STATUS_DIR / f"v2_phase_d_final_decision_packet_{date_key}_{window}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    for src_name, src in (("d828", d828), ("d827", d827), ("d826", d826), ("d825", d825)):
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

        pg = src.get("production_gates", {}) if isinstance(src.get("production_gates"), dict) else {}
        for g in (
            "production_resume_allowed_now",
            "cron_enable_allowed",
            "qq_push_allowed",
            "verified_write_allowed",
            "state_write_allowed",
        ):
            if _bool(pg.get(g), False):
                blockers.append(f"GATE_LEAK:{g}:{src_name}")

    if str(d828.get("readiness_matrix_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D828_STATUS_INVALID")
    if str(d827.get("simulation_plan_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D827_STATUS_INVALID")
    if str(d826.get("final_boss_gate_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D826_STATUS_INVALID")
    if str(d825.get("final_packet_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D825_STATUS_INVALID")

    d829 = d828.get("d829_draft", {}) if isinstance(d828.get("d829_draft"), dict) else {}
    if _bool(d829.get("allowed_to_execute"), False):
        blockers.append("D829_ALLOWED_TO_EXECUTE_LEAK")

    # warnings: carry matrix remaining unproven items
    matrix = d828.get("readiness_matrix", []) if isinstance(d828.get("readiness_matrix"), list) else []
    for row in matrix:
        if isinstance(row, dict):
            name = row.get("name")
            st = str(row.get("current_status", ""))
            if name and st in {"UNPROVEN", "NOT_PROVEN", "UNKNOWN_OR_NOT_RECORDED"}:
                warnings.append(f"UNPROVEN:{name}")

    if blockers:
        status = "BLOCKER" if any(b.startswith("PIPELINE_READY_LEAK") or b.startswith("PRODUCTION_VERIFIED_LEAK") for b in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "source_markers": {
                "d828": str(p_d828),
                "d827": str(p_d827),
                "d826": str(p_d826),
                "d825": str(p_d825),
            },
            "d828_status": d828.get("readiness_matrix_status"),
            "d827_status": d827.get("simulation_plan_status"),
            "d826_status": d826.get("final_boss_gate_status"),
            "d825_status": d825.get("final_packet_status"),
            "recommended_next": "D8_30_OR_PAUSE",
            "phase_e_recommended": False,
            "d830_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "final_command_authorization_gate_only",
            },
            "decision_options": [
                "pause",
                "D8_30_final_command_authorization_gate",
                "defer_phase_e",
            ],
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

    out_path = STATUS_DIR / f"v2_phase_d_final_decision_packet_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
