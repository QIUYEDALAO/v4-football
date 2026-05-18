#!/usr/bin/env python3
"""Phase D.8.24 — controlled worker dry-run wrapper (dry-run-only, no execution)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_controlled_worker_dryrun_wrapper.v1"

REQUIRED_GUARDS = [
    "dry_run_only",
    "openclaw_no_push",
    "no_supervisor",
    "no_push",
    "no_cron",
    "no_verified_write",
    "no_formal_state_write",
]


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
        "wrapper_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "wrapper_mode": "dry_run_only",
        "execution_performed": False,
        "production_resume_executed": False,
        "formal_daily_pool_executed": False,
        "supervisor_executed": False,
        "live_worker_executed": False,
        "cron_modified": False,
        "qq_sent": False,
        "verified_written": False,
        "formal_state_written": False,
        "api_called": False,
        "key_read": False,
        "dry_run_only": True,
        "sandbox_or_synthetic_path_only": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    parser.add_argument("--dry-run-only", action="store_true")
    parser.add_argument("--openclaw-no-push", action="store_true")
    parser.add_argument("--no-supervisor", action="store_true")
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--no-cron", action="store_true")
    parser.add_argument("--no-verified-write", action="store_true")
    parser.add_argument("--no-formal-state-write", action="store_true")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    p_d823 = STATUS_DIR / f"v2_single_window_noop_harness_{date_key}_{window}.json"
    d823 = _load(p_d823)

    guard_presence = {
        "dry_run_only": bool(args.dry_run_only),
        "openclaw_no_push": bool(args.openclaw_no_push),
        "no_supervisor": bool(args.no_supervisor),
        "no_push": bool(args.no_push),
        "no_cron": bool(args.no_cron),
        "no_verified_write": bool(args.no_verified_write),
        "no_formal_state_write": bool(args.no_formal_state_write),
    }

    warnings: list[str] = []
    blockers: list[str] = []

    if not d823:
        blockers.append("D823_MARKER_MISSING")
    else:
        if str(d823.get("harness_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN", "PASS"}:
            blockers.append("D823_STATUS_INVALID")
        for field, code in (
            ("pipeline_ready", "PIPELINE_READY_LEAK"),
            ("production_verified", "PRODUCTION_VERIFIED_LEAK"),
            ("execution_performed", "EXECUTION_PERFORMED_LEAK"),
            ("production_resume_executed", "PRODUCTION_RESUME_EXECUTED_LEAK"),
            ("supervisor_executed", "SUPERVISOR_EXECUTED_LEAK"),
            ("live_worker_executed", "LIVE_WORKER_EXECUTED_LEAK"),
            ("cron_modified", "CRON_MODIFIED_LEAK"),
            ("qq_sent", "QQ_SENT_LEAK"),
            ("verified_written", "VERIFIED_WRITTEN_LEAK"),
            ("formal_state_written", "FORMAL_STATE_WRITTEN_LEAK"),
            ("api_called", "API_CALLED_LEAK"),
            ("key_read", "KEY_READ_LEAK"),
        ):
            if _bool(d823.get(field), False):
                blockers.append(code)

        pg = d823.get("production_gates", {}) if isinstance(d823.get("production_gates"), dict) else {}
        for field in (
            "production_resume_allowed_now",
            "cron_enable_allowed",
            "qq_push_allowed",
            "verified_write_allowed",
            "state_write_allowed",
        ):
            if _bool(pg.get(field), False):
                blockers.append(f"PRODUCTION_GATE_LEAK:{field}")

    for g in REQUIRED_GUARDS:
        if not guard_presence[g]:
            blockers.append(f"MISSING_GUARD:{g}")

    missing_guards = [g for g in REQUIRED_GUARDS if not guard_presence[g]]

    proposed_command = []
    if isinstance(d823.get("proposed_command"), list):
        proposed_command = [str(x) for x in d823.get("proposed_command", [])]

    if not proposed_command:
        warnings.append("PROPOSED_COMMAND_EMPTY_IN_D823")

    if blockers:
        status = "BLOCKER" if any(b.startswith("PIPELINE_READY") or b.startswith("PRODUCTION_VERIFIED") for b in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "source_marker": str(p_d823),
            "guard_presence": guard_presence,
            "missing_required_guards": missing_guards,
            "proposed_command": proposed_command,
            "execution_path": "observe_only_sandbox_or_synthetic",
            "d825_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "final_controlled_execution_approval_packet_only",
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

    out_path = STATUS_DIR / f"v2_controlled_worker_dryrun_wrapper_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
