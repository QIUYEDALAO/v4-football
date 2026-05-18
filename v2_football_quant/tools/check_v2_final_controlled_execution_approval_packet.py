#!/usr/bin/env python3
"""Phase D.8.25 — final controlled execution approval packet (pre-execution only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_final_controlled_execution_approval_packet.v1"

UNPROVEN_ITEMS = [
    "real_state_present_case",
    "active_window_mutation_path",
    "production_cron_path",
    "production_qq_path",
    "production_verified_path",
    "formal_state_write_path",
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
        "final_packet_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "gate_scope": "final_controlled_execution_approval_packet_only",
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
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    p_d822 = STATUS_DIR / f"v2_controlled_command_review_dryrun_gate_{date_key}_{window}.json"
    p_d823 = STATUS_DIR / f"v2_single_window_noop_harness_{date_key}_{window}.json"
    p_d824 = STATUS_DIR / f"v2_controlled_worker_dryrun_wrapper_{date_key}_{window}.json"
    p_d820 = STATUS_DIR / f"v2_controlled_resume_risk_acceptance_gate_{date_key}_{window}.json"

    d822 = _load(p_d822)
    d823 = _load(p_d823)
    d824 = _load(p_d824)
    d820 = _load(p_d820)

    warnings: list[str] = []
    blockers: list[str] = []

    for name, src in (("d822", d822), ("d823", d823), ("d824", d824), ("d820", d820)):
        if not src:
            blockers.append(f"{name}_marker_missing")

    if blockers:
        out = _base(date_key, window, "BLOCKER")
        out.update(
            {
                "source_markers": {
                    "d822": str(p_d822),
                    "d823": str(p_d823),
                    "d824": str(p_d824),
                    "d820": str(p_d820),
                },
                "unproven_items": UNPROVEN_ITEMS,
                "d826_draft": {
                    "allowed_to_generate": True,
                    "allowed_to_execute": False,
                    "scope": "controlled_execution_dryrun_or_command_review_only_after_explicit_boss_instruction",
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
        out_path = STATUS_DIR / f"v2_final_controlled_execution_approval_packet_{date_key}_{window}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    sources = {"d822": d822, "d823": d823, "d824": d824, "d820": d820}

    for name, src in sources.items():
        if _bool(src.get("pipeline_ready"), False):
            blockers.append(f"PIPELINE_READY_LEAK:{name}")
        if _bool(src.get("production_verified"), False):
            blockers.append(f"PRODUCTION_VERIFIED_LEAK:{name}")

    for name, src in sources.items():
        for fld in (
            "execution_performed",
            "production_resume_executed",
            "formal_daily_pool_executed",
            "supervisor_executed",
            "live_worker_executed",
            "cron_modified",
            "qq_sent",
            "verified_written",
            "formal_state_written",
            "api_called",
            "key_read",
        ):
            if _bool(src.get(fld), False):
                blockers.append(f"FORBIDDEN_TRUE:{fld}:{name}")

    # read production gates from nested and flat variants
    for name, src in sources.items():
        pg = src.get("production_gates", {}) if isinstance(src.get("production_gates"), dict) else {}
        gate_map = {
            "production_resume_allowed_now": _bool(pg.get("production_resume_allowed_now"), _bool(src.get("production_resume_allowed_now"), False)),
            "cron_enable_allowed": _bool(pg.get("cron_enable_allowed"), _bool(src.get("cron_enable_allowed"), False)),
            "qq_push_allowed": _bool(pg.get("qq_push_allowed"), _bool(src.get("qq_push_allowed"), False)),
            "verified_write_allowed": _bool(pg.get("verified_write_allowed"), _bool(src.get("verified_write_allowed"), False)),
            "state_write_allowed": _bool(pg.get("state_write_allowed"), _bool(src.get("state_write_allowed"), False)),
        }
        for k, v in gate_map.items():
            if v:
                blockers.append(f"GATE_LEAK:{k}:{name}")

    # Upstream status sanity
    if str(d822.get("command_review_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D822_STATUS_INVALID")
    if str(d823.get("harness_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN", "PASS"}:
        blockers.append("D823_STATUS_INVALID")
    if str(d824.get("wrapper_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN", "PASS"}:
        blockers.append("D824_STATUS_INVALID")

    # D.8.26 gate is draft-only.
    d824_draft = d824.get("d825_draft", {}) if isinstance(d824.get("d825_draft"), dict) else {}
    if _bool(d824_draft.get("allowed_to_execute"), False):
        blockers.append("D825_ALLOWED_TO_EXECUTE_LEAK")

    accepted_risks = _bool(d820.get("accepted_risks_do_not_grant_execution"), False)
    if not accepted_risks:
        blockers.append("ACCEPTED_RISKS_FLAG_FALSE")

    # Explicitly preserve unresolved proofs as warnings, not execution permission.
    real_state_present = _bool(d820.get("real_state_present_case_proven"), False)
    synthetic_active_mutation = _bool(d820.get("synthetic_active_window_mutation_proven"), False)
    if not real_state_present:
        warnings.append("UNPROVEN:real_state_present_case")
    if not synthetic_active_mutation:
        warnings.append("UNPROVEN:active_window_mutation_path")
    warnings.extend(
        [
            "UNPROVEN:production_cron_path",
            "UNPROVEN:production_qq_path",
            "UNPROVEN:production_verified_path",
            "UNPROVEN:formal_state_write_path",
        ]
    )

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
                "d822": str(p_d822),
                "d823": str(p_d823),
                "d824": str(p_d824),
                "d820": str(p_d820),
            },
            "d822_status": d822.get("command_review_status"),
            "d823_status": d823.get("harness_status"),
            "d824_status": d824.get("wrapper_status"),
            "accepted_risks_do_not_grant_execution": accepted_risks,
            "unproven_items": UNPROVEN_ITEMS,
            "d826_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "controlled_execution_dryrun_or_command_review_only_after_explicit_boss_instruction",
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

    out_path = STATUS_DIR / f"v2_final_controlled_execution_approval_packet_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
