#!/usr/bin/env python3
"""Phase D.9.5 — D10 authorization pre-gate (approval-prep only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_d10_authorization_pre_gate.v1"

MARKER_FILES = {
    "d94": "v2_d9_proof_stop_rollback_gate_{date}_{window}.json",
    "d93": "v2_d9_controlled_proof_runbook_draft_{date}_{window}.json",
    "d92": "v2_d9_proof_evidence_schema_{date}_{window}.json",
    "d91": "v2_d9_proof_execution_scope_matrix_{date}_{window}.json",
    "d841": "v2_next_phase_decision_gate_{date}_{window}.json",
    "d838": "v2_production_path_proof_pack_{date}_{window}.json",
    "d820": "v2_controlled_resume_risk_acceptance_gate_{date}_{window}.json",
}


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
        "d10_authorization_pre_gate_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "boss_approval_required": True,
        "production_proof_execution_authorized": False,
        "d10_allowed_to_generate": True,
        "d10_allowed_to_execute": False,
        "phase_e_allowed": False,
        "all_six_targets_still_unproven": True,
        "any_proof_marked_proven": False,
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    marker_paths = {
        k: STATUS_DIR / pattern.format(date=date_key, window=window)
        for k, pattern in MARKER_FILES.items()
    }
    markers = {k: _load(p) for k, p in marker_paths.items()}

    warnings: list[str] = []
    blockers: list[str] = []

    for key, src in markers.items():
        if not src:
            blockers.append(f"{key}_marker_missing")

    if not blockers:
        for src_name, src in markers.items():
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

        if str(markers["d94"].get("d9_stop_rollback_gate_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
            blockers.append("D94_STATUS_INVALID")
        if str(markers["d93"].get("d9_runbook_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
            blockers.append("D93_STATUS_INVALID")
        if str(markers["d92"].get("d9_evidence_schema_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
            blockers.append("D92_STATUS_INVALID")
        if str(markers["d91"].get("d9_scope_matrix_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
            blockers.append("D91_STATUS_INVALID")
        if str(markers["d841"].get("next_phase_decision_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
            blockers.append("D841_STATUS_INVALID")

        if not _bool(markers["d91"].get("all_six_status_unproven"), False):
            blockers.append("D91_UNPROVEN_FLAG_INVALID")
        if _bool(markers["d838"].get("any_proof_marked_proven"), False):
            blockers.append("D838_ANY_PROOF_MARKED_PROVEN_TRUE")

        warnings.append("D10_PRE_GATE_REVIEW_ONLY")

    if blockers:
        status = "BLOCKER" if any(x.startswith("PIPELINE_READY_LEAK") or x.startswith("PRODUCTION_VERIFIED_LEAK") for x in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "source_markers": {k: str(v) for k, v in marker_paths.items()},
            "d10_scope": {
                "pre_gate_only": True,
                "execution_not_authorized": True,
                "phase_e_not_allowed": True,
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

    out_path = STATUS_DIR / f"v2_d10_authorization_pre_gate_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
