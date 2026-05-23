#!/usr/bin/env python3
"""Phase D.8.22 — Controlled command review / dry-run gate (review-only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_controlled_command_review_dryrun_gate.v1"

REQUIRED_FLAGS = [
    "OPENCLAW_NO_PUSH=1",
    "--single-window-only",
    "--no-supervisor",
    "--no-push",
    "--no-cron",
    "--no-verified-write",
    "--no-formal-state-write",
    "--watchdog-only-failure",
    "--manifest-required",
]


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
        "command_review_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "gate_scope": "controlled_command_review_dryrun_only",
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    p_d821 = STATUS_DIR / f"v2_single_window_execution_draft_gate_{date_key}_{window}.json"
    d821 = _load(p_d821)

    blockers: list[str] = []
    warnings: list[str] = []

    if not d821:
        blockers.append("D821_MARKER_MISSING")
        out = _base(date_key, window, "BLOCKER")
        out.update(
            {
                "review_target": str(p_d821),
                "review_only": True,
                "command_type": "review_only",
                "command_must_not_execute": True,
                "proposed_command": [],
                "required_flags": REQUIRED_FLAGS,
                "required_flag_presence": {k: False for k in REQUIRED_FLAGS},
                "missing_required_flags": REQUIRED_FLAGS,
                "d823_draft": {
                    "allowed_to_generate": True,
                    "allowed_to_execute": False,
                    "scope": "no_op_shell_safe_dryrun_harness_only",
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
        out_path = STATUS_DIR / f"v2_controlled_command_review_dryrun_gate_{date_key}_{window}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    status_821 = str(d821.get("execution_draft_status", ""))
    if status_821 not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append(f"D821_STATUS_INVALID:{status_821 or 'MISSING'}")

    # hard leak checks from upstream marker
    for field, code, severity in (
        ("pipeline_ready", "PIPELINE_READY_LEAK", "BLOCKER"),
        ("production_verified", "PRODUCTION_VERIFIED_LEAK", "BLOCKER"),
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
        if _bool(d821.get(field), False):
            blockers.append(code if severity == "FAIL" else f"{code}:BLOCKER")

    production_gates = d821.get("production_gates", {}) if isinstance(d821.get("production_gates"), dict) else {}
    gate_values = {
        "production_resume_allowed_now": _bool(production_gates.get("production_resume_allowed_now"), _bool(d821.get("production_resume_allowed_now"), False)),
        "cron_enable_allowed": _bool(production_gates.get("cron_enable_allowed"), _bool(d821.get("cron_enable_allowed"), False)),
        "qq_push_allowed": _bool(production_gates.get("qq_push_allowed"), _bool(d821.get("qq_push_allowed"), False)),
        "verified_write_allowed": _bool(production_gates.get("verified_write_allowed"), _bool(d821.get("verified_write_allowed"), False)),
        "state_write_allowed": _bool(production_gates.get("state_write_allowed"), _bool(d821.get("state_write_allowed"), False)),
    }
    for k, v in gate_values.items():
        if v:
            blockers.append(f"{k.upper()}_LEAK")

    draft_policy = d821.get("draft_policy", {}) if isinstance(d821.get("draft_policy"), dict) else {}
    if not _bool(draft_policy.get("accepted_risks_do_not_grant_execution"), False):
        blockers.append("ACCEPTED_RISKS_FLAG_FALSE")
    if _bool(draft_policy.get("draft_execution_allowed"), False):
        blockers.append("D821_DRAFT_EXECUTION_ALLOWED_LEAK")

    draft_command = d821.get("draft_command", {}) if isinstance(d821.get("draft_command"), dict) else {}
    command_type = str(draft_command.get("command_type", ""))
    must_not_execute = _bool(draft_command.get("command_must_not_execute"), False)
    proposed = draft_command.get("proposed_command", [])
    if not isinstance(proposed, list):
        proposed = []

    if command_type != "review_only":
        blockers.append("COMMAND_TYPE_NOT_REVIEW_ONLY")
    if not must_not_execute:
        blockers.append("COMMAND_MUST_NOT_EXECUTE_FALSE")

    proposed_str = " ".join(str(x) for x in proposed)
    flag_presence = {flag: (flag in proposed_str) for flag in REQUIRED_FLAGS}
    missing_flags = [flag for flag, present in flag_presence.items() if not present]
    if missing_flags:
        blockers.extend([f"MISSING_REQUIRED_FLAG:{flag}" for flag in missing_flags])

    if not _bool(d821.get("single_window_scope", {}).get("single_window_only"), False):
        blockers.append("SINGLE_WINDOW_SCOPE_MISSING")

    # warnings carry unresolved proof gaps from d821
    evidence = d821.get("evidence", {}) if isinstance(d821.get("evidence"), dict) else {}
    if not _bool(evidence.get("real_state_present_case_proven"), False):
        warnings.append("REAL_STATE_PRESENT_CASE_NOT_PROVEN")
    if not _bool(evidence.get("synthetic_active_window_mutation_proven"), False):
        warnings.append("SYNTHETIC_ACTIVE_WINDOW_MUTATION_NOT_PROVEN")

    has_blocker = any(x.endswith(":BLOCKER") or x.startswith("PIPELINE_READY_LEAK") or x.startswith("PRODUCTION_VERIFIED_LEAK") for x in blockers)
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
            "review_target": str(p_d821),
            "review_only": True,
            "command_type": "review_only",
            "command_must_not_execute": True,
            "proposed_command": proposed,
            "required_flags": REQUIRED_FLAGS,
            "required_flag_presence": flag_presence,
            "missing_required_flags": missing_flags,
            "d823_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "no_op_shell_safe_dryrun_harness_only",
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

    out_path = STATUS_DIR / f"v2_controlled_command_review_dryrun_gate_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
