#!/usr/bin/env python3
"""Phase D.8.26 — final BOSS approval gate (pre-execution, no permission grant)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_final_boss_approval_gate.v1"


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
        "final_boss_gate_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "boss_approval_required": True,
        "approval_grants_execution": False,
        "accepted_risks_do_not_grant_execution": True,
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
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    p_d825 = STATUS_DIR / f"v2_final_controlled_execution_approval_packet_{date_key}_{window}.json"
    p_d824 = STATUS_DIR / f"v2_controlled_worker_dryrun_wrapper_{date_key}_{window}.json"
    p_d823 = STATUS_DIR / f"v2_single_window_noop_harness_{date_key}_{window}.json"
    p_d822 = STATUS_DIR / f"v2_controlled_command_review_dryrun_gate_{date_key}_{window}.json"

    d825 = _load(p_d825)
    d824 = _load(p_d824)
    d823 = _load(p_d823)
    d822 = _load(p_d822)

    warnings: list[str] = []
    blockers: list[str] = []

    sources = {"d825": d825, "d824": d824, "d823": d823, "d822": d822}
    for name, src in sources.items():
        if not src:
            blockers.append(f"{name}_marker_missing")

    if blockers:
        status = "BLOCKER"
        out = _base(date_key, window, status)
        out.update(
            {
                "source_markers": {k: str(v) for k, v in {
                    "d825": p_d825,
                    "d824": p_d824,
                    "d823": p_d823,
                    "d822": p_d822,
                }.items()},
                "d827_draft": {
                    "allowed_to_generate": True,
                    "allowed_to_execute": False,
                    "scope": "controlled_execution_simulation_plan_only",
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
        out_path = STATUS_DIR / f"v2_final_boss_approval_gate_{date_key}_{window}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    for name, src in sources.items():
        if _bool(src.get("pipeline_ready"), False):
            blockers.append(f"PIPELINE_READY_LEAK:{name}")
        if _bool(src.get("production_verified"), False):
            blockers.append(f"PRODUCTION_VERIFIED_LEAK:{name}")

    # all execution-like and side-effect fields must remain false
    forbidden_fields = (
        "execution_performed",
        "production_resume_executed",
        "formal_daily_pool_executed",
        "supervisor_executed",
        "live_worker_executed",
        "formal_state_written",
        "verified_written",
        "qq_sent",
        "cron_modified",
        "api_called",
        "key_read",
    )
    for name, src in sources.items():
        for field in forbidden_fields:
            if _bool(src.get(field), False):
                blockers.append(f"FORBIDDEN_TRUE:{field}:{name}")

    for name, src in sources.items():
        pg = src.get("production_gates", {}) if isinstance(src.get("production_gates"), dict) else {}
        gate_map = {
            "production_resume_allowed_now": _bool(pg.get("production_resume_allowed_now"), _bool(src.get("production_resume_allowed_now"), False)),
            "cron_enable_allowed": _bool(pg.get("cron_enable_allowed"), _bool(src.get("cron_enable_allowed"), False)),
            "qq_push_allowed": _bool(pg.get("qq_push_allowed"), _bool(src.get("qq_push_allowed"), False)),
            "verified_write_allowed": _bool(pg.get("verified_write_allowed"), _bool(src.get("verified_write_allowed"), False)),
            "state_write_allowed": _bool(pg.get("state_write_allowed"), _bool(src.get("state_write_allowed"), False)),
        }
        for g, val in gate_map.items():
            if val:
                blockers.append(f"GATE_LEAK:{g}:{name}")

    # status expectations
    if str(d825.get("final_packet_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D825_STATUS_INVALID")
    if str(d824.get("wrapper_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN", "PASS"}:
        blockers.append("D824_STATUS_INVALID")
    if str(d823.get("harness_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN", "PASS"}:
        blockers.append("D823_STATUS_INVALID")
    if str(d822.get("command_review_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D822_STATUS_INVALID")

    accepted_flag = _bool(d825.get("accepted_risks_do_not_grant_execution"), False)
    if not accepted_flag:
        blockers.append("ACCEPTED_RISKS_FLAG_FALSE")

    d826 = d825.get("d826_draft", {}) if isinstance(d825.get("d826_draft"), dict) else {}
    if _bool(d826.get("allowed_to_execute"), False):
        blockers.append("D826_ALLOWED_TO_EXECUTE_LEAK")

    # preserve unresolved warnings
    unproven = d825.get("unproven_items", []) if isinstance(d825.get("unproven_items"), list) else []
    for item in unproven:
        warnings.append(f"UNPROVEN:{item}")

    if blockers:
        status = "BLOCKER" if any(b.startswith("PIPELINE_READY_LEAK") or b.startswith("PRODUCTION_VERIFIED_LEAK") for b in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "source_markers": {
                "d825": str(p_d825),
                "d824": str(p_d824),
                "d823": str(p_d823),
                "d822": str(p_d822),
            },
            "d822_status": d822.get("command_review_status"),
            "d823_status": d823.get("harness_status"),
            "d824_status": d824.get("wrapper_status"),
            "d825_status": d825.get("final_packet_status"),
            "d827_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "controlled_execution_simulation_plan_only",
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

    out_path = STATUS_DIR / f"v2_final_boss_approval_gate_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
