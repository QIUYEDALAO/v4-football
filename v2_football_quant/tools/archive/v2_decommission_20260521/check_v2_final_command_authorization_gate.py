#!/usr/bin/env python3
"""Phase D.8.30 — final command authorization gate (review-only, no execution)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_final_command_authorization_gate.v1"


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
        "final_command_authorization_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "gate_scope": "final_command_authorization_only",
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
        "command_authorization_grants_execution": False,
        "command_template_review_only": True,
        "command_must_not_execute": True,
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

    p_d829 = STATUS_DIR / f"v2_phase_d_final_decision_packet_{date_key}_{window}.json"
    p_d828 = STATUS_DIR / f"v2_production_resume_readiness_matrix_{date_key}_{window}.json"
    p_d827 = STATUS_DIR / f"v2_controlled_execution_simulation_plan_{date_key}_{window}.json"
    p_d826 = STATUS_DIR / f"v2_final_boss_approval_gate_{date_key}_{window}.json"

    d829 = _load(p_d829)
    d828 = _load(p_d828)
    d827 = _load(p_d827)
    d826 = _load(p_d826)

    warnings: list[str] = []
    blockers: list[str] = []

    sources = {"d829": d829, "d828": d828, "d827": d827, "d826": d826}
    for name, src in sources.items():
        if not src:
            blockers.append(f"{name}_marker_missing")

    command_template = [
        "REVIEW_ONLY_TEMPLATE_DO_NOT_EXECUTE",
        "OPENCLAW_NO_PUSH=1",
        "python3",
        "tools/v2_single_window_controlled_execution.py",
        "--date",
        date_key,
        "--window",
        window,
        "--single-window-only",
        "--no-supervisor",
        "--no-push",
        "--no-cron",
        "--no-verified-write",
        "--no-formal-state-write",
        "--watchdog-only-failure",
        "--manifest-required",
    ]

    if blockers:
        out = _base(date_key, window, "BLOCKER")
        out.update(
            {
                "source_markers": {
                    "d829": str(p_d829),
                    "d828": str(p_d828),
                    "d827": str(p_d827),
                    "d826": str(p_d826),
                },
                "d831_draft": {
                    "allowed_to_generate": True,
                    "allowed_to_execute": False,
                    "scope": "controlled_execution_decision_packet_only",
                },
                "command_template": command_template,
                "warnings": warnings,
                "blockers": blockers,
                "generated_at": datetime.now(CN).isoformat(),
            }
        )
        out_path = STATUS_DIR / f"v2_final_command_authorization_gate_{date_key}_{window}.json"
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

    if str(d829.get("final_decision_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D829_STATUS_INVALID")
    if str(d828.get("readiness_matrix_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D828_STATUS_INVALID")
    if str(d827.get("simulation_plan_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D827_STATUS_INVALID")
    if str(d826.get("final_boss_gate_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D826_STATUS_INVALID")

    d830 = d829.get("d830_draft", {}) if isinstance(d829.get("d830_draft"), dict) else {}
    if not _bool(d830.get("allowed_to_generate"), False):
        blockers.append("D830_ALLOWED_TO_GENERATE_FALSE")
    if _bool(d830.get("allowed_to_execute"), True):
        blockers.append("D830_ALLOWED_TO_EXECUTE_TRUE")

    for w in d829.get("warnings", []) if isinstance(d829.get("warnings"), list) else []:
        warnings.append(str(w))

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
                "d829": str(p_d829),
                "d828": str(p_d828),
                "d827": str(p_d827),
                "d826": str(p_d826),
            },
            "d826_status": d826.get("final_boss_gate_status"),
            "d827_status": d827.get("simulation_plan_status"),
            "d828_status": d828.get("readiness_matrix_status"),
            "d829_status": d829.get("final_decision_status"),
            "d831_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "controlled_execution_decision_packet_only",
            },
            "command_template": command_template,
            "warnings": warnings,
            "blockers": blockers,
            "generated_at": datetime.now(CN).isoformat(),
        }
    )

    out_path = STATUS_DIR / f"v2_final_command_authorization_gate_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
