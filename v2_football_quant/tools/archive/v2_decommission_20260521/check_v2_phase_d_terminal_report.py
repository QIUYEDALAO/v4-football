#!/usr/bin/env python3
"""Phase D.8.40 — Phase D terminal report (report-only)."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_phase_d_terminal_report.v1"


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
        "terminal_report_status": status,
        "current_level": "CODE_READY",
        "phase_d_engineering_complete": True,
        "phase_d_business_pass": False,
        "production_resume_ready": False,
        "pipeline_ready": False,
        "production_verified": False,
        "phase_e_recommended": False,
        "production_resume_allowed_now": False,
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
        "cron_enable_allowed": False,
        "qq_push_allowed": False,
        "verified_write_allowed": False,
        "state_write_allowed": False,
    }


def _stash_snapshot() -> dict[str, Any]:
    r = subprocess.run(["git", "stash", "list"], capture_output=True, text=True)
    lines = [x.strip() for x in r.stdout.splitlines() if x.strip()]
    has_netutils = any("net_utils" in x for x in lines)
    has_excel = any("excel" in x.lower() or "日报表" in x for x in lines)
    return {
        "stash_list": lines,
        "net_utils_stash_retained": has_netutils,
        "excel_stash_present": has_excel,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    p_d839 = STATUS_DIR / f"v2_phase_d_terminal_readiness_gate_{date_key}_{window}.json"
    p_d838 = STATUS_DIR / f"v2_production_path_proof_pack_{date_key}_{window}.json"
    p_d820 = STATUS_DIR / f"v2_controlled_resume_risk_acceptance_gate_{date_key}_{window}.json"
    p_d7 = STATUS_DIR / "v2_settlement_preflight_wrapper_block_test_20260517.json"

    d839 = _load(p_d839)
    d838 = _load(p_d838)
    d820 = _load(p_d820)
    d7 = _load(p_d7)

    warnings: list[str] = []
    blockers: list[str] = []

    sources = {"d839": d839, "d838": d838, "d820": d820, "d7": d7}
    for name, src in sources.items():
        if not src:
            blockers.append(f"{name}_marker_missing")

    stash_info = _stash_snapshot()

    if blockers:
        out = _base(date_key, window, "BLOCKER")
        out.update(
            {
                "source_markers": {
                    "d839": str(p_d839),
                    "d838": str(p_d838),
                    "d820": str(p_d820),
                    "d7": str(p_d7),
                },
                "terminal_summary": {
                    "settlement_preflight_fail_closed_completed": False,
                    "guarded_observe_chain_completed": False,
                    "proof_planning_chain_completed": False,
                    "fund_report_cleared": True,
                    "net_utils_stash_retained": bool(stash_info.get("net_utils_stash_retained", False)),
                    "production_resume_executed": False,
                    "phase_e_entered": False,
                    "unproven_items": [
                        "real_state_present_case",
                        "active_window_mutation_path",
                        "production_cron_path",
                        "production_qq_path",
                        "production_verified_path",
                        "formal_state_write_path",
                    ],
                },
                "d841_draft": {
                    "allowed_to_generate": True,
                    "allowed_to_execute": False,
                    "scope": "next_phase_decision_gate_only",
                },
                "warnings": warnings,
                "blockers": blockers,
                "generated_at": datetime.now(CN).isoformat(),
            }
        )
        out_path = STATUS_DIR / f"v2_phase_d_terminal_report_{date_key}_{window}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    for src_name, src in sources.items():
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

    if str(d839.get("terminal_readiness_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D839_STATUS_INVALID")
    if str(d838.get("proof_pack_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D838_STATUS_INVALID")
    if str(d7.get("status", "")) != "PASS":
        blockers.append("D7_WRAPPER_STATUS_NOT_PASS")

    warnings.extend([
        "UNPROVEN:real_state_present_case",
        "UNPROVEN:active_window_mutation_path",
        "UNPROVEN:production_cron_path",
        "UNPROVEN:production_qq_path",
        "UNPROVEN:production_verified_path",
        "UNPROVEN:formal_state_write_path",
    ])

    if blockers:
        status = "BLOCKER" if any(x.startswith("PIPELINE_READY_LEAK") or x.startswith("PRODUCTION_VERIFIED_LEAK") for x in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "source_markers": {
                "d839": str(p_d839),
                "d838": str(p_d838),
                "d820": str(p_d820),
                "d7": str(p_d7),
            },
            "terminal_summary": {
                "settlement_preflight_fail_closed_completed": True,
                "guarded_observe_chain_completed": True,
                "proof_planning_chain_completed": True,
                "fund_report_cleared": True,
                "net_utils_stash_retained": bool(stash_info.get("net_utils_stash_retained", False)),
                "production_resume_executed": False,
                "phase_e_entered": False,
                "unproven_items": [
                    "real_state_present_case",
                    "active_window_mutation_path",
                    "production_cron_path",
                    "production_qq_path",
                    "production_verified_path",
                    "formal_state_write_path",
                ],
            },
            "d841_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "next_phase_decision_gate_only",
            },
            "stash_snapshot": stash_info,
            "warnings": warnings,
            "blockers": blockers,
            "generated_at": datetime.now(CN).isoformat(),
        }
    )

    out_path = STATUS_DIR / f"v2_phase_d_terminal_report_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
