#!/usr/bin/env python3
"""Phase D.8.21 — V2 single-window controlled execution draft gate (draft-only, no execution)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_single_window_execution_draft_gate.v1"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _base(date_key: str, window: str, status: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "window": window,
        "execution_draft_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "gate_scope": "single_window_controlled_execution_draft_only",
        "execution_performed": False,
        "production_resume_executed": False,
        "formal_daily_pool_executed": False,
        "supervisor_executed": False,
        "live_worker_executed": False,
        "cron_modified": False,
        "qq_sent": False,
        "verified_written": False,
        "formal_state_written": False,
    }


def _collect_bool(sources: dict[str, dict[str, Any]], field: str) -> tuple[bool, list[str]]:
    leaking = []
    for name, src in sources.items():
        if _bool(src.get(field), False):
            leaking.append(name)
    return (len(leaking) > 0), leaking


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    p_d820 = STATUS_DIR / f"v2_controlled_resume_risk_acceptance_gate_{date_key}_{window}.json"
    p_d819 = STATUS_DIR / f"v2_controlled_resume_execution_gate_{date_key}_{window}.json"
    p_d818 = STATUS_DIR / f"v2_controlled_resume_approval_packet_{date_key}_{window}.json"
    p_d817_check = STATUS_DIR / f"v2_state_present_guarded_observe_check_{date_key}_{window}.json"
    p_d817_decision = STATUS_DIR / f"v2_d817_next_gate_decision_{date_key}_{window}.json"
    p_d816_decision = STATUS_DIR / f"v2_d816_next_gate_decision_{date_key}.json"

    d820 = _load(p_d820)
    d819 = _load(p_d819)
    d818 = _load(p_d818)
    d817_check = _load(p_d817_check)
    d817_decision = _load(p_d817_decision)
    d816_decision = _load(p_d816_decision)

    missing = []
    for name, src in (
        ("d820", d820),
        ("d819", d819),
        ("d818", d818),
        ("d817_check", d817_check),
        ("d817_decision", d817_decision),
        ("d816_decision", d816_decision),
    ):
        if not src:
            missing.append(f"{name}_marker_missing")

    warnings: list[str] = []
    blockers: list[str] = []

    if missing:
        blockers.extend(missing)
        status = "BLOCKER"
        out = _base(date_key, window, status)
        out.update(
            {
                "evidence": {
                    "no_state_case_proven": False,
                    "synthetic_state_file_read_proven": False,
                    "synthetic_state_present_no_write_proven": False,
                    "synthetic_active_window_mutation_proven": False,
                    "real_state_present_case_proven": False,
                },
                "draft_policy": {
                    "boss_approval_required": True,
                    "accepted_risks_do_not_grant_execution": True,
                    "draft_generation_allowed": True,
                    "draft_execution_allowed": False,
                    "d822_allowed_to_generate": True,
                    "d822_allowed_to_execute": False,
                },
                "single_window_scope": {
                    "window": window,
                    "single_window_only": True,
                    "full_day_resume_allowed": False,
                    "multi_window_resume_allowed": False,
                    "cron_resume_allowed": False,
                    "qq_push_allowed": False,
                    "verified_write_allowed": False,
                    "formal_state_write_allowed": False,
                    "supervisor_allowed": False,
                },
                "draft_command": {
                    "command_type": "review_only",
                    "command_must_not_execute": True,
                    "proposed_command": [
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
                    ],
                },
                "required_guards": [
                    "no_supervisor",
                    "no_push",
                    "openclaw_no_push",
                    "no_cron",
                    "no_verified_write",
                    "no_formal_state_write",
                    "preflight_required",
                    "watchdog_only_failure",
                    "rollback_required",
                    "manifest_gate_required",
                    "stop_on_any_marker_mismatch",
                    "no_ai_kill_retry",
                    "preserve_logs",
                ],
                "rollback_gate": {
                    "no_ai_kill_retry": True,
                    "report_watchdog_only": True,
                    "preserve_logs": True,
                    "stop_on_any_push_state_verified_cron": True,
                    "stop_on_any_marker_mismatch": True,
                    "disable_cron_if_modified": True,
                    "mark_draft_execution_blocked_if_any_guard_missing": True,
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
        out_path = STATUS_DIR / f"v2_single_window_execution_draft_gate_{date_key}_{window}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    sources = {
        "d820": d820,
        "d819": d819,
        "d818": d818,
        "d817_decision": d817_decision,
        "d816_decision": d816_decision,
    }

    # Strong leak checks across upstream gates.
    for field, code, severity in (
        ("pipeline_ready", "PIPELINE_READY_LEAK", "BLOCKER"),
        ("production_verified", "PRODUCTION_VERIFIED_LEAK", "BLOCKER"),
        ("production_resume_allowed_now", "PRODUCTION_RESUME_ALLOWED_LEAK", "FAIL"),
        ("cron_enable_allowed", "CRON_ENABLE_ALLOWED_LEAK", "FAIL"),
        ("qq_push_allowed", "QQ_PUSH_ALLOWED_LEAK", "FAIL"),
        ("verified_write_allowed", "VERIFIED_WRITE_ALLOWED_LEAK", "FAIL"),
        ("state_write_allowed", "STATE_WRITE_ALLOWED_LEAK", "FAIL"),
        ("execution_performed", "EXECUTION_PERFORMED_LEAK", "FAIL"),
        ("production_resume_executed", "PRODUCTION_RESUME_EXECUTED_LEAK", "FAIL"),
        ("formal_daily_pool_executed", "FORMAL_DAILY_POOL_EXECUTED_LEAK", "FAIL"),
        ("supervisor_executed", "SUPERVISOR_EXECUTED_LEAK", "FAIL"),
        ("live_worker_executed", "LIVE_WORKER_EXECUTED_LEAK", "FAIL"),
        ("cron_modified", "CRON_MODIFIED_LEAK", "FAIL"),
        ("qq_sent", "QQ_SENT_LEAK", "FAIL"),
        ("verified_written", "VERIFIED_WRITTEN_LEAK", "FAIL"),
        ("formal_state_written", "FORMAL_STATE_WRITTEN_LEAK", "FAIL"),
    ):
        leak, names = _collect_bool(sources, field)
        if leak:
            for src_name in names:
                blockers.append(f"{code}:{src_name}")
            if severity == "BLOCKER":
                blockers.append(f"{code}:BLOCKER_ROUTE")

    accepted_risks_do_not_grant_execution = _bool(d820.get("accepted_risks_do_not_grant_execution"), False)
    if not accepted_risks_do_not_grant_execution:
        blockers.append("ACCEPTED_RISKS_FLAG_FALSE")

    d821_draft = d820.get("d821_draft", {}) if isinstance(d820.get("d821_draft"), dict) else {}
    d822_allowed_to_generate = _bool(d821_draft.get("allowed_to_generate"), False)
    d822_allowed_to_execute = _bool(d821_draft.get("allowed_to_execute"), False)
    if d822_allowed_to_execute:
        blockers.append("D822_ALLOWED_TO_EXECUTE_LEAK")

    no_state_case_proven = _bool(d820.get("no_state_case_proven"), False)
    synthetic_state_file_read_proven = _bool(d820.get("synthetic_state_file_read_proven"), False)
    synthetic_state_present_no_write_proven = _bool(d820.get("synthetic_state_present_no_write_proven"), False)
    synthetic_active_window_mutation_proven = _bool(d820.get("synthetic_active_window_mutation_proven"), False)
    real_state_present_case_proven = _bool(d820.get("real_state_present_case_proven"), False)

    if not no_state_case_proven:
        blockers.append("NO_STATE_CASE_NOT_PROVEN")
    if not synthetic_state_file_read_proven:
        blockers.append("SYNTHETIC_STATE_FILE_READ_NOT_PROVEN")
    if not synthetic_state_present_no_write_proven:
        blockers.append("SYNTHETIC_STATE_PRESENT_NO_WRITE_NOT_PROVEN")
    if synthetic_active_window_mutation_proven:
        blockers.append("ACTIVE_WINDOW_MUTATION_PROOF_UNEXPECTED")
    if real_state_present_case_proven:
        blockers.append("REAL_STATE_PRESENT_PROOF_UNEXPECTED")

    if not real_state_present_case_proven:
        warnings.append("REAL_STATE_PRESENT_CASE_NOT_PROVEN")
    if not synthetic_active_window_mutation_proven:
        warnings.append("SYNTHETIC_ACTIVE_WINDOW_MUTATION_NOT_PROVEN")

    has_blocker = any(x.startswith("PIPELINE_READY_LEAK") or x.startswith("PRODUCTION_VERIFIED_LEAK") or x.endswith(":BLOCKER_ROUTE") for x in blockers)
    if has_blocker:
        status = "BLOCKER"
    elif blockers:
        status = "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "evidence": {
                "no_state_case_proven": no_state_case_proven,
                "synthetic_state_file_read_proven": synthetic_state_file_read_proven,
                "synthetic_state_present_no_write_proven": synthetic_state_present_no_write_proven,
                "synthetic_active_window_mutation_proven": synthetic_active_window_mutation_proven,
                "real_state_present_case_proven": real_state_present_case_proven,
            },
            "draft_policy": {
                "boss_approval_required": True,
                "accepted_risks_do_not_grant_execution": accepted_risks_do_not_grant_execution,
                "draft_generation_allowed": d822_allowed_to_generate,
                "draft_execution_allowed": False,
                "d822_allowed_to_generate": d822_allowed_to_generate,
                "d822_allowed_to_execute": False,
            },
            "single_window_scope": {
                "window": window,
                "single_window_only": True,
                "full_day_resume_allowed": False,
                "multi_window_resume_allowed": False,
                "cron_resume_allowed": False,
                "qq_push_allowed": False,
                "verified_write_allowed": False,
                "formal_state_write_allowed": False,
                "supervisor_allowed": False,
            },
            "draft_command": {
                "command_type": "review_only",
                "command_must_not_execute": True,
                "proposed_command": [
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
                ],
            },
            "required_guards": [
                "no_supervisor",
                "no_push",
                "openclaw_no_push",
                "no_cron",
                "no_verified_write",
                "no_formal_state_write",
                "preflight_required",
                "watchdog_only_failure",
                "rollback_required",
                "manifest_gate_required",
                "stop_on_any_marker_mismatch",
                "no_ai_kill_retry",
                "preserve_logs",
            ],
            "rollback_gate": {
                "no_ai_kill_retry": True,
                "report_watchdog_only": True,
                "preserve_logs": True,
                "stop_on_any_push_state_verified_cron": True,
                "stop_on_any_marker_mismatch": True,
                "disable_cron_if_modified": True,
                "mark_draft_execution_blocked_if_any_guard_missing": True,
            },
            "production_gates": {
                "production_resume_allowed_now": False,
                "cron_enable_allowed": False,
                "qq_push_allowed": False,
                "verified_write_allowed": False,
                "state_write_allowed": False,
            },
            "source_fields_checked": {
                name: {
                    "pipeline_ready": _bool(src.get("pipeline_ready"), False),
                    "production_verified": _bool(src.get("production_verified"), False),
                    "execution_performed": _bool(src.get("execution_performed"), False),
                    "production_resume_executed": _bool(src.get("production_resume_executed"), False),
                    "production_resume_allowed_now": _bool(src.get("production_resume_allowed_now"), False),
                    "cron_enable_allowed": _bool(src.get("cron_enable_allowed"), False),
                    "qq_push_allowed": _bool(src.get("qq_push_allowed"), False),
                    "verified_write_allowed": _bool(src.get("verified_write_allowed"), False),
                    "state_write_allowed": _bool(src.get("state_write_allowed"), False),
                    "formal_daily_pool_executed": _bool(src.get("formal_daily_pool_executed"), False),
                    "supervisor_executed": _bool(src.get("supervisor_executed"), False),
                    "live_worker_executed": _bool(src.get("live_worker_executed"), False),
                    "cron_modified": _bool(src.get("cron_modified"), False),
                    "qq_sent": _bool(src.get("qq_sent"), False),
                    "verified_written": _bool(src.get("verified_written"), False),
                    "formal_state_written": _bool(src.get("formal_state_written"), False),
                }
                for name, src in sources.items()
            },
            "warnings": warnings,
            "blockers": blockers,
            "generated_at": datetime.now(CN).isoformat(),
        }
    )

    out_path = STATUS_DIR / f"v2_single_window_execution_draft_gate_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
