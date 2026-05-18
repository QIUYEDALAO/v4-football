#!/usr/bin/env python3
"""Phase D.8.20.1 — V2 Controlled Resume Risk Acceptance Gate (fail-closed hardening)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_controlled_resume_risk_acceptance_gate.v1"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _base_payload(date_key: str, window: str, status: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "window": window,
        "risk_acceptance_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "gate_scope": "controlled_resume_risk_acceptance_only",
        "execution_performed": False,
        "production_resume_executed": False,
        "production_resume_allowed_now": False,
        "cron_enable_allowed": False,
        "qq_push_allowed": False,
        "verified_write_allowed": False,
        "state_write_allowed": False,
        "accepted_risks_do_not_grant_execution": True,
        "boss_acceptance_required": True,
        "d821_draft": {
            "allowed_to_generate": True,
            "allowed_to_execute": False,
            "scope": "single-window controlled execution draft only after BOSS explicit approval",
            "required_guards": [
                "no_supervisor",
                "no_push",
                "no_verified_write",
                "no_cron_enable",
                "preflight_required",
                "rollback_required",
                "watchdog_only_failure",
                "manifest_gate_required",
                "stop_on_any_marker_mismatch",
                "no_ai_kill_retry",
            ],
        },
    }


def _bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    return default


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    blockers: list[str] = []
    warnings: list[str] = []
    source_warnings: list[str] = []

    p_d819 = SD / f"v2_controlled_resume_execution_gate_{date_key}_{window}.json"
    p_d818 = SD / f"v2_controlled_resume_approval_packet_{date_key}_{window}.json"
    p_d817 = SD / f"v2_state_present_guarded_observe_{date_key}_{window}.json"

    d819 = _load(p_d819)
    d818 = _load(p_d818)
    d817 = _load(p_d817)

    missing = []
    if not d819:
        missing.append("d819_marker_missing")
    if not d818:
        missing.append("d818_marker_missing")
    if not d817:
        missing.append("d817_marker_missing")

    if missing:
        out = _base_payload(date_key, window, "BLOCKER")
        out.update(
            {
                "read_sources": {
                    "d819_execution_gate": str(p_d819),
                    "d818_approval_packet": str(p_d818),
                    "d817_state_present_guarded_observe": str(p_d817),
                },
                "real_state_present_case_proven": False,
                "synthetic_active_window_mutation_proven": False,
                "secret_safe": True,
                "warnings": [],
                "blockers": missing,
                "generated_at": datetime.now(CN).isoformat(),
            }
        )
        out_path = SD / f"v2_controlled_resume_risk_acceptance_gate_{date_key}_{window}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    sources = {
        "d819": d819,
        "d818": d818,
        "d817": d817,
    }

    # ---- Fail-closed upstream leak validation (explicit input checks) ----
    for name, src in sources.items():
        if _bool(src.get("pipeline_ready"), False):
            blockers.append(f"PIPELINE_READY_LEAK:{name}")
        if _bool(src.get("production_verified"), False):
            blockers.append(f"PRODUCTION_VERIFIED_LEAK:{name}")

    for name, src in sources.items():
        if _bool(src.get("production_resume_allowed_now"), False):
            blockers.append(f"PRODUCTION_RESUME_ALLOWED_LEAK:{name}")
        if _bool(src.get("cron_enable_allowed"), False):
            blockers.append(f"CRON_ENABLE_ALLOWED_LEAK:{name}")
        if _bool(src.get("qq_push_allowed"), False):
            blockers.append(f"QQ_PUSH_ALLOWED_LEAK:{name}")
        if _bool(src.get("verified_write_allowed"), False):
            blockers.append(f"VERIFIED_WRITE_ALLOWED_LEAK:{name}")
        if _bool(src.get("state_write_allowed"), False):
            blockers.append(f"STATE_WRITE_ALLOWED_LEAK:{name}")

    for name, src in sources.items():
        if _bool(src.get("execution_performed"), False):
            blockers.append(f"EXECUTION_PERFORMED_LEAK:{name}")
        if _bool(src.get("production_resume_executed"), False):
            blockers.append(f"PRODUCTION_RESUME_EXECUTED_LEAK:{name}")

    for name, src in sources.items():
        if _bool(src.get("cron_modified"), False):
            blockers.append(f"CRON_MODIFIED_LEAK:{name}")
        if _bool(src.get("qq_sent"), False):
            blockers.append(f"QQ_SENT_LEAK:{name}")
        if _bool(src.get("verified_written"), False):
            blockers.append(f"VERIFIED_WRITTEN_LEAK:{name}")
        if _bool(src.get("formal_state_written"), False):
            blockers.append(f"FORMAL_STATE_WRITTEN_LEAK:{name}")

    # Execution signal fields must be read and surfaced.
    # d817 may legitimately include historical synthetic worker execution evidence, so keep as warning.
    for name, src in sources.items():
        if _bool(src.get("supervisor_executed"), False):
            source_warnings.append(f"SUPERVISOR_EXECUTED_SIGNAL:{name}")
        if _bool(src.get("live_worker_executed"), False):
            source_warnings.append(f"LIVE_WORKER_EXECUTED_SIGNAL:{name}")

    real_state_present_case_proven = _bool(d819.get("real_state_present_case_proven"), False)
    synthetic_active_window_mutation_proven = _bool(d819.get("synthetic_active_window_mutation_proven"), False)

    # Current round requires both proofs to remain false unless explicit round permission exists.
    if real_state_present_case_proven:
        blockers.append("REAL_STATE_PROOF_UNEXPECTED")
    if synthetic_active_window_mutation_proven:
        blockers.append("ACTIVE_WINDOW_PROOF_UNEXPECTED")

    if source_warnings:
        warnings.extend(source_warnings)

    # hard status routing
    has_pipeline_or_pv_leak = any(
        x.startswith("PIPELINE_READY_LEAK") or x.startswith("PRODUCTION_VERIFIED_LEAK")
        for x in blockers
    )

    if has_pipeline_or_pv_leak:
        status = "BLOCKER"
    elif blockers:
        status = "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base_payload(date_key, window, status)
    out.update(
        {
            "formal_daily_pool_executed": False,
            "supervisor_executed": False,
            "live_worker_executed": False,
            "cron_modified": False,
            "qq_sent": False,
            "verified_written": False,
            "formal_state_written": False,
            "no_state_case_proven": _bool(d819.get("no_state_case_proven"), False),
            "synthetic_state_file_read_proven": _bool(d819.get("synthetic_state_file_read_proven"), False),
            "synthetic_state_present_no_write_proven": _bool(d819.get("synthetic_state_present_no_write_proven"), False),
            "synthetic_active_window_mutation_proven": synthetic_active_window_mutation_proven,
            "real_state_present_case_proven": real_state_present_case_proven,
            "risk_acceptance": {
                "boss_acceptance_required": True,
                "accepted_risks_do_not_grant_execution": True,
                "accepted_risks": [
                    "synthetic_only_state_present_proof",
                    "real_state_present_case_gap",
                    "active_window_mutation_gap",
                    "production_cron_path_gap",
                    "production_qq_path_gap",
                    "production_verified_path_gap",
                ],
                "remaining_blockers": [
                    "production_execution_without_boss_d821_forbidden",
                    "cron_enable_forbidden",
                    "qq_push_forbidden",
                    "verified_write_forbidden",
                    "formal_state_write_forbidden",
                    "production_verified_forbidden",
                ],
            },
            "rollback_gate": {
                "no_ai_kill_retry": True,
                "report_watchdog_only": True,
                "preserve_logs": True,
                "stop_on_any_push_state_verified_cron": True,
                "stop_on_any_marker_mismatch": True,
            },
            "source_fields_checked": {
                "d819": {
                    "pipeline_ready": _bool(d819.get("pipeline_ready"), False),
                    "production_verified": _bool(d819.get("production_verified"), False),
                    "execution_performed": _bool(d819.get("execution_performed"), False),
                    "production_resume_executed": _bool(d819.get("production_resume_executed"), False),
                    "production_resume_allowed_now": _bool(d819.get("production_resume_allowed_now"), False),
                    "cron_enable_allowed": _bool(d819.get("cron_enable_allowed"), False),
                    "qq_push_allowed": _bool(d819.get("qq_push_allowed"), False),
                    "verified_write_allowed": _bool(d819.get("verified_write_allowed"), False),
                    "state_write_allowed": _bool(d819.get("state_write_allowed"), False),
                    "cron_modified": _bool(d819.get("cron_modified"), False),
                    "qq_sent": _bool(d819.get("qq_sent"), False),
                    "verified_written": _bool(d819.get("verified_written"), False),
                    "formal_state_written": _bool(d819.get("formal_state_written"), False),
                    "supervisor_executed": _bool(d819.get("supervisor_executed"), False),
                    "live_worker_executed": _bool(d819.get("live_worker_executed"), False),
                },
                "d818": {
                    "pipeline_ready": _bool(d818.get("pipeline_ready"), False),
                    "production_verified": _bool(d818.get("production_verified"), False),
                    "execution_performed": _bool(d818.get("execution_performed"), False),
                    "production_resume_executed": _bool(d818.get("production_resume_executed"), False),
                    "production_resume_allowed_now": _bool(d818.get("production_resume_allowed_now"), False),
                    "cron_enable_allowed": _bool(d818.get("cron_enable_allowed"), False),
                    "qq_push_allowed": _bool(d818.get("qq_push_allowed"), False),
                    "verified_write_allowed": _bool(d818.get("verified_write_allowed"), False),
                    "state_write_allowed": _bool(d818.get("state_write_allowed"), False),
                    "cron_modified": _bool(d818.get("cron_modified"), False),
                    "qq_sent": _bool(d818.get("qq_sent"), False),
                    "verified_written": _bool(d818.get("verified_written"), False),
                    "formal_state_written": _bool(d818.get("formal_state_written"), False),
                    "supervisor_executed": _bool(d818.get("supervisor_executed"), False),
                    "live_worker_executed": _bool(d818.get("live_worker_executed"), False),
                },
                "d817": {
                    "pipeline_ready": _bool(d817.get("pipeline_ready"), False),
                    "production_verified": _bool(d817.get("production_verified"), False),
                    "execution_performed": _bool(d817.get("execution_performed"), False),
                    "production_resume_executed": _bool(d817.get("production_resume_executed"), False),
                    "production_resume_allowed_now": _bool(d817.get("production_resume_allowed_now"), False),
                    "cron_enable_allowed": _bool(d817.get("cron_enable_allowed"), False),
                    "qq_push_allowed": _bool(d817.get("qq_push_allowed"), False),
                    "verified_write_allowed": _bool(d817.get("verified_write_allowed"), False),
                    "state_write_allowed": _bool(d817.get("state_write_allowed"), False),
                    "cron_modified": _bool(d817.get("cron_modified"), False),
                    "qq_sent": _bool(d817.get("qq_sent"), False),
                    "verified_written": _bool(d817.get("verified_written"), False),
                    "formal_state_written": _bool(d817.get("formal_state_written"), False),
                    "supervisor_executed": _bool(d817.get("supervisor_executed"), False),
                    "live_worker_executed": _bool(d817.get("live_worker_executed"), False),
                },
            },
            "secret_safe": True,
            "warnings": warnings,
            "blockers": blockers,
            "generated_at": datetime.now(CN).isoformat(),
        }
    )

    out_path = SD / f"v2_controlled_resume_risk_acceptance_gate_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status == "BLOCKER":
        raise SystemExit(2)
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
