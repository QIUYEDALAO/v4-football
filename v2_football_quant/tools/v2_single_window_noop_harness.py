#!/usr/bin/env python3
"""Phase D.8.23 — no-op / shell-safe dry-run harness (print only, never execute)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_single_window_noop_harness.v1"

DEFAULT_REQUIRED_FLAGS = [
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


def _bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    return default


def _base(date_key: str, window: str, status: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "window": window,
        "harness_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "harness_mode": "no_op_print_only",
        "execution_performed": False,
        "production_resume_executed": False,
        "command_executed": False,
        "formal_daily_pool_executed": False,
        "supervisor_executed": False,
        "live_worker_executed": False,
        "cron_modified": False,
        "qq_sent": False,
        "verified_written": False,
        "formal_state_written": False,
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

    p_d822 = STATUS_DIR / f"v2_controlled_command_review_dryrun_gate_{date_key}_{window}.json"
    d822 = _load(p_d822)

    warnings: list[str] = []
    blockers: list[str] = []

    if not d822:
        blockers.append("D822_MARKER_MISSING")
        out = _base(date_key, window, "BLOCKER")
        out.update(
            {
                "source_marker": str(p_d822),
                "command_printed": False,
                "command_type": "review_only",
                "proposed_command": [],
                "required_flags": DEFAULT_REQUIRED_FLAGS,
                "required_flags_present": False,
                "missing_required_flags": DEFAULT_REQUIRED_FLAGS,
                "d824_draft": {
                    "allowed_to_generate": True,
                    "allowed_to_execute": False,
                    "scope": "controlled_worker_dryrun_wrapper_only",
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
        out_path = STATUS_DIR / f"v2_single_window_noop_harness_{date_key}_{window}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    if str(d822.get("command_review_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D822_STATUS_INVALID")

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
    ):
        if _bool(d822.get(field), False):
            blockers.append(code)

    pg = d822.get("production_gates", {}) if isinstance(d822.get("production_gates"), dict) else {}
    gate_values = {
        "production_resume_allowed_now": _bool(pg.get("production_resume_allowed_now"), False),
        "cron_enable_allowed": _bool(pg.get("cron_enable_allowed"), False),
        "qq_push_allowed": _bool(pg.get("qq_push_allowed"), False),
        "verified_write_allowed": _bool(pg.get("verified_write_allowed"), False),
        "state_write_allowed": _bool(pg.get("state_write_allowed"), False),
    }
    for k, v in gate_values.items():
        if v:
            blockers.append(f"{k.upper()}_LEAK")

    required_flags = d822.get("required_flags", DEFAULT_REQUIRED_FLAGS)
    if not isinstance(required_flags, list) or not required_flags:
        required_flags = DEFAULT_REQUIRED_FLAGS
    required_flags = [str(x) for x in required_flags]

    cmd = d822.get("proposed_command", [])
    if not isinstance(cmd, list):
        cmd = []
    cmd = [str(x) for x in cmd]

    cmd_str = " ".join(cmd)
    missing_flags = [flag for flag in required_flags if flag not in cmd_str]
    required_flags_present = len(missing_flags) == 0

    if not required_flags_present:
        blockers.extend([f"MISSING_REQUIRED_FLAG:{f}" for f in missing_flags])

    command_type = str(d822.get("command_type", "review_only"))
    if command_type != "review_only":
        blockers.append("COMMAND_TYPE_NOT_REVIEW_ONLY")

    command_printed = len(cmd) > 0
    if not command_printed:
        blockers.append("PROPOSED_COMMAND_EMPTY")

    # No-op behavior: only print the command string for review, never execute.
    printed_command = " ".join(cmd)
    if printed_command:
        print(printed_command)

    if blockers:
        status = "BLOCKER" if any(x.startswith("PIPELINE_READY") or x.startswith("PRODUCTION_VERIFIED") for x in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "source_marker": str(p_d822),
            "command_printed": command_printed,
            "printed_command": printed_command,
            "command_type": "review_only",
            "proposed_command": cmd,
            "required_flags": required_flags,
            "required_flags_present": required_flags_present,
            "missing_required_flags": missing_flags,
            "d824_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "controlled_worker_dryrun_wrapper_only",
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

    out_path = STATUS_DIR / f"v2_single_window_noop_harness_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
