#!/usr/bin/env python3
"""Phase D.9.2 — production proof evidence schema (definition-only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_d9_proof_evidence_schema.v1"

MARKER_FILES = {
    "d91": "v2_d9_proof_execution_scope_matrix_{date}_{window}.json",
    "d841": "v2_next_phase_decision_gate_{date}_{window}.json",
    "d840": "v2_phase_d_terminal_report_{date}_{window}.json",
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
        "d9_evidence_schema_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "schema_complete": False,
        "schema_execution_performed": False,
        "proof_result_default": "UNPROVEN",
        "proof_current_status_default": "UNPROVEN",
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

    for k, src in markers.items():
        if not src:
            blockers.append(f"{k}_marker_missing")

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

        if str(markers["d91"].get("d9_scope_matrix_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
            blockers.append("D91_STATUS_INVALID")

        if not _bool(markers["d91"].get("all_six_targets_present"), False):
            blockers.append("D91_TARGETS_MISSING")
        if not _bool(markers["d91"].get("all_six_status_unproven"), False):
            blockers.append("D91_UNPROVEN_FLAG_INVALID")
        if _bool(markers["d91"].get("any_execution_allowed"), True):
            blockers.append("D91_ANY_EXECUTION_ALLOWED_TRUE")

        warnings.extend([
            "EVIDENCE_SCHEMA_DEFAULT_UNPROVEN_ONLY",
            "EXECUTION_NOT_AUTHORIZED_IN_D9_2",
        ])

    evidence_schema = {
        "proof_id": "string",
        "proof_target": "string",
        "run_date": "YYYYMMDD",
        "window": "string",
        "pre_state_hash": "string",
        "post_state_hash": "string",
        "pre_state_mtime": "int_or_float",
        "post_state_mtime": "int_or_float",
        "pre_state_size": "int",
        "post_state_size": "int",
        "command_template": ["REVIEW_ONLY_DO_NOT_EXECUTE", "..."] ,
        "command_executed": False,
        "supervisor_executed": False,
        "live_worker_executed": False,
        "cron_modified": False,
        "qq_sent": False,
        "verified_written": False,
        "formal_state_written": False,
        "api_called": False,
        "key_read": False,
        "watchdog_status": "string",
        "marker_status": "string",
        "rollback_status": "string",
        "evidence_status": "string",
        "proof_result": "UNPROVEN|PASS|FAIL|BLOCKER",
        "proof_current_status": "UNPROVEN",
    }

    if blockers:
        status = "BLOCKER" if any(x.startswith("PIPELINE_READY_LEAK") or x.startswith("PRODUCTION_VERIFIED_LEAK") for x in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "schema_complete": True,
            "schema_execution_performed": False,
            "proof_result_default": "UNPROVEN",
            "proof_current_status_default": "UNPROVEN",
            "evidence_schema": evidence_schema,
            "source_markers": {k: str(v) for k, v in marker_paths.items()},
            "d9_3_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "controlled_proof_runbook_draft_only",
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

    out_path = STATUS_DIR / f"v2_d9_proof_evidence_schema_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
