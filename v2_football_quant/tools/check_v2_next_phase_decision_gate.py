#!/usr/bin/env python3
"""Phase D.8.41 — next phase decision gate (decision-only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_next_phase_decision_gate.v1"


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


def _gate(src: dict[str, Any], field: str) -> bool:
    pg = src.get("production_gates", {}) if isinstance(src.get("production_gates"), dict) else {}
    return _bool(pg.get(field), _bool(src.get(field), False))


def _base(date_key: str, window: str, status: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "window": window,
        "next_phase_decision_status": status,
        "current_level": "CODE_READY",
        "recommended_next": "D9_OR_PAUSE",
        "allowed_decision_options": [
            "pause",
            "D9_PRODUCTION_PROOF_EXECUTION_PLANNING",
            "DEFER_PHASE_E",
        ],
        "decision_scope": "next_phase_decision_only",
        "phase_e_allowed": False,
        "phase_e_recommended": False,
        "d9_allowed_to_generate": True,
        "d9_allowed_to_execute": False,
        "production_resume_allowed_now": False,
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
        "cron_enable_allowed": False,
        "qq_push_allowed": False,
        "verified_write_allowed": False,
        "state_write_allowed": False,
        "pipeline_ready": False,
        "production_verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    p_d840 = STATUS_DIR / f"v2_phase_d_terminal_report_{date_key}_{window}.json"
    p_d839 = STATUS_DIR / f"v2_phase_d_terminal_readiness_gate_{date_key}_{window}.json"
    p_d838 = STATUS_DIR / f"v2_production_path_proof_pack_{date_key}_{window}.json"
    p_d830 = STATUS_DIR / f"v2_final_command_authorization_gate_{date_key}_{window}.json"

    d840 = _load(p_d840)
    d839 = _load(p_d839)
    d838 = _load(p_d838)
    d830 = _load(p_d830)

    warnings: list[str] = []
    blockers: list[str] = []

    sources = {"d840": d840, "d839": d839, "d838": d838, "d830": d830}
    for name, src in sources.items():
        if not src:
            blockers.append(f"{name}_marker_missing")

    if blockers:
        out = _base(date_key, window, "BLOCKER")
        out.update(
            {
                "source_markers": {
                    "d840": str(p_d840),
                    "d839": str(p_d839),
                    "d838": str(p_d838),
                    "d830": str(p_d830),
                },
                "warnings": warnings,
                "blockers": blockers,
                "generated_at": datetime.now(CN).isoformat(),
            }
        )
        out_path = STATUS_DIR / f"v2_next_phase_decision_gate_{date_key}_{window}.json"
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

    if str(d840.get("terminal_report_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D840_STATUS_INVALID")
    if str(d839.get("terminal_readiness_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D839_STATUS_INVALID")
    if str(d838.get("proof_pack_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D838_STATUS_INVALID")
    if str(d830.get("final_command_authorization_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D830_STATUS_INVALID")

    warnings.extend(
        [
            "PHASE_E_STILL_BLOCKED",
            "PRODUCTION_RESUME_STILL_BLOCKED",
            "UNPROVEN_ITEMS_REMAIN",
        ]
    )

    if blockers:
        status = (
            "BLOCKER"
            if any(x.startswith("PIPELINE_READY_LEAK") or x.startswith("PRODUCTION_VERIFIED_LEAK") for x in blockers)
            else "FAIL"
        )
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "source_markers": {
                "d840": str(p_d840),
                "d839": str(p_d839),
                "d838": str(p_d838),
                "d830": str(p_d830),
            },
            "warnings": warnings,
            "blockers": blockers,
            "generated_at": datetime.now(CN).isoformat(),
        }
    )

    out_path = STATUS_DIR / f"v2_next_phase_decision_gate_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
