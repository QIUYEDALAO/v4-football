#!/usr/bin/env python3
"""Phase D.8.27 — controlled execution simulation plan (simulation-only, no execution)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_controlled_execution_simulation_plan.v1"

SIMULATION_STEPS = [
    "preflight_check",
    "manifest_check",
    "no_push_env_check",
    "no_supervisor_check",
    "no_cron_check",
    "no_verified_write_check",
    "no_formal_state_write_check",
    "watchdog_only_failure_rule",
    "stop_on_marker_mismatch_rule",
    "rollback_gate",
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
        "simulation_plan_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "simulation_only": True,
        "command_executed": False,
        "worker_executed": False,
        "supervisor_executed": False,
        "execution_performed": False,
        "production_resume_executed": False,
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

    p_d826 = STATUS_DIR / f"v2_final_boss_approval_gate_{date_key}_{window}.json"
    d826 = _load(p_d826)

    blockers: list[str] = []
    warnings: list[str] = []

    if not d826:
        blockers.append("D826_MARKER_MISSING")
    else:
        if str(d826.get("final_boss_gate_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
            blockers.append("D826_STATUS_INVALID")

        if _bool(d826.get("pipeline_ready"), False):
            blockers.append("PIPELINE_READY_LEAK")
        if _bool(d826.get("production_verified"), False):
            blockers.append("PRODUCTION_VERIFIED_LEAK")

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
            if _bool(d826.get(field), False):
                blockers.append(f"FORBIDDEN_TRUE:{field}")

        pg = d826.get("production_gates", {}) if isinstance(d826.get("production_gates"), dict) else {}
        for field in (
            "production_resume_allowed_now",
            "cron_enable_allowed",
            "qq_push_allowed",
            "verified_write_allowed",
            "state_write_allowed",
        ):
            if _bool(pg.get(field), False):
                blockers.append(f"GATE_LEAK:{field}")

        d827 = d826.get("d827_draft", {}) if isinstance(d826.get("d827_draft"), dict) else {}
        if not _bool(d827.get("allowed_to_generate"), False):
            blockers.append("D827_ALLOWED_TO_GENERATE_FALSE")
        if _bool(d827.get("allowed_to_execute"), True):
            blockers.append("D827_ALLOWED_TO_EXECUTE_TRUE")

        if not _bool(d826.get("accepted_risks_do_not_grant_execution"), False):
            blockers.append("ACCEPTED_RISKS_FLAG_FALSE")

        # carry unresolved risks as WARN only
        for item in d826.get("warnings", []) if isinstance(d826.get("warnings"), list) else []:
            warnings.append(str(item))

    if blockers:
        status = "BLOCKER" if any(b in {"PIPELINE_READY_LEAK", "PRODUCTION_VERIFIED_LEAK"} for b in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "source_marker": str(p_d826),
            "simulation_steps": SIMULATION_STEPS,
            "d828_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "production_resume_readiness_matrix_only",
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

    out_path = STATUS_DIR / f"v2_controlled_execution_simulation_plan_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
