#!/usr/bin/env python3
"""Phase D.9.3 — controlled proof runbook draft (review-only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_d9_controlled_proof_runbook_draft.v1"

TARGETS = [
    "real_state_present_case",
    "active_window_mutation_path",
    "formal_state_write_path",
    "production_verified_path",
    "production_qq_path",
    "production_cron_path",
]

MARKER_FILES = {
    "d92": "v2_d9_proof_evidence_schema_{date}_{window}.json",
    "d91": "v2_d9_proof_execution_scope_matrix_{date}_{window}.json",
    "d841": "v2_next_phase_decision_gate_{date}_{window}.json",
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
        "d9_runbook_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "runbook_scope": "review_only",
        "command_templates_count": 0,
        "all_commands_must_not_execute": False,
        "any_command_executed": False,
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


def _template_for(target: str, date_key: str, window: str) -> dict[str, Any]:
    cmd = [
        "REVIEW_ONLY_DO_NOT_EXECUTE",
        "OPENCLAW_NO_PUSH=1",
        "python3",
        "tools/v2_d9_proof_execution_template.py",
        "--date",
        date_key,
        "--window",
        window,
        "--proof-target",
        target,
        "--no-supervisor",
        "--no-push",
        "--no-cron",
        "--no-verified-write",
        "--no-formal-state-write",
        "--watchdog-only-failure",
        "--manifest-required",
    ]
    return {
        "proof_target": target,
        "command_type": "review_only",
        "command_must_not_execute": True,
        "execution_allowed_now": False,
        "requires_boss_explicit_approval": True,
        "requires_preflight": True,
        "requires_manifest": True,
        "requires_watchdog": True,
        "requires_no_push": True,
        "requires_no_cron": True,
        "requires_no_verified_write": True,
        "requires_no_formal_state_write": True,
        "requires_no_supervisor": True,
        "command_template": cmd,
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

    templates: list[dict[str, Any]] = []

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

        if str(markers["d92"].get("d9_evidence_schema_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
            blockers.append("D92_STATUS_INVALID")
        if str(markers["d91"].get("d9_scope_matrix_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
            blockers.append("D91_STATUS_INVALID")

        if _bool(markers["d91"].get("any_execution_allowed"), True):
            blockers.append("D91_ANY_EXECUTION_ALLOWED_TRUE")

        for target in TARGETS:
            templates.append(_template_for(target, date_key, window))

        warnings.append("RUNBOOK_REVIEW_ONLY_DO_NOT_EXECUTE")

    all_must_not_execute = len(templates) == 6 and all(
        _bool(t.get("command_must_not_execute"), False) and not _bool(t.get("execution_allowed_now"), True)
        for t in templates
    )

    if blockers:
        status = "BLOCKER" if any(x.startswith("PIPELINE_READY_LEAK") or x.startswith("PRODUCTION_VERIFIED_LEAK") for x in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "runbook_scope": "review_only",
            "command_templates_count": len(templates),
            "all_commands_must_not_execute": all_must_not_execute,
            "any_command_executed": False,
            "command_templates": templates,
            "source_markers": {k: str(v) for k, v in marker_paths.items()},
            "d9_4_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "proof_stop_rollback_gate_only",
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

    out_path = STATUS_DIR / f"v2_d9_controlled_proof_runbook_draft_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
