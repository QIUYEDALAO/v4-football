#!/usr/bin/env python3
"""Phase D.9.1 — production proof execution scope matrix (planning-only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_d9_proof_execution_scope_matrix.v1"

TARGET_ORDER = [
    "real_state_present_case",
    "active_window_mutation_path",
    "formal_state_write_path",
    "production_verified_path",
    "production_qq_path",
    "production_cron_path",
]

TARGET_SPECS = {
    "real_state_present_case": {
        "can_be_synthetic": False,
        "must_be_real": True,
        "dependency": [],
        "required_inputs": ["real_daily_pool_selected_fixtures"],
        "required_outputs": ["real_state_present_evidence"],
        "forbidden_side_effects": ["qq_push", "verified_write", "formal_state_write", "cron_change"],
        "evidence_required": ["state_file_exists", "state_hash_snapshot", "watchdog_log"],
    },
    "active_window_mutation_path": {
        "can_be_synthetic": True,
        "must_be_real": True,
        "dependency": ["real_state_present_case"],
        "required_inputs": ["active_window_fixture_set"],
        "required_outputs": ["mutation_trace", "watchdog_trace"],
        "forbidden_side_effects": ["qq_push", "verified_write", "formal_state_write", "cron_change"],
        "evidence_required": ["mutation_diff", "pre_post_hash", "window_status_trace"],
    },
    "formal_state_write_path": {
        "can_be_synthetic": False,
        "must_be_real": True,
        "dependency": ["active_window_mutation_path"],
        "required_inputs": ["approved_state_write_guard"],
        "required_outputs": ["formal_state_write_trace"],
        "forbidden_side_effects": ["qq_push", "verified_write", "cron_change"],
        "evidence_required": ["selected_fixtures_diff", "official_bet_locked_diff"],
    },
    "production_verified_path": {
        "can_be_synthetic": False,
        "must_be_real": True,
        "dependency": ["formal_state_write_path"],
        "required_inputs": ["settlement_authorization"],
        "required_outputs": ["verify_date_trace"],
        "forbidden_side_effects": ["qq_push", "cron_change", "unauthorized_settlement_rerun"],
        "evidence_required": ["verify_date_call_trace", "verified_file_diff"],
    },
    "production_qq_path": {
        "can_be_synthetic": True,
        "must_be_real": True,
        "dependency": ["production_verified_path"],
        "required_inputs": ["safe_sender_guard", "no_push_suppressed_route"],
        "required_outputs": ["qq_route_trace"],
        "forbidden_side_effects": ["real_qq_send", "cron_change", "verified_write", "formal_state_write"],
        "evidence_required": ["route_marker", "sender_guard_log", "suppressed_send_trace"],
    },
    "production_cron_path": {
        "can_be_synthetic": False,
        "must_be_real": True,
        "dependency": ["production_qq_path"],
        "required_inputs": ["cron_policy_approval"],
        "required_outputs": ["cron_plan_trace"],
        "forbidden_side_effects": ["cron_install", "cron_start", "qq_push", "verified_write", "formal_state_write"],
        "evidence_required": ["cron_plan_review", "policy_guard_log"],
    },
}

MARKER_FILES = {
    "d841": "v2_next_phase_decision_gate_{date}_{window}.json",
    "d840": "v2_phase_d_terminal_report_{date}_{window}.json",
    "d839": "v2_phase_d_terminal_readiness_gate_{date}_{window}.json",
    "d838": "v2_production_path_proof_pack_{date}_{window}.json",
    "d837": "v2_formal_state_write_path_proof_plan_{date}_{window}.json",
    "d836": "v2_production_verified_write_path_proof_plan_{date}_{window}.json",
    "d835": "v2_production_qq_path_proof_plan_{date}_{window}.json",
    "d834": "v2_production_cron_path_proof_plan_{date}_{window}.json",
    "d833": "v2_active_window_mutation_proof_plan_{date}_{window}.json",
    "d832": "v2_real_state_present_proof_plan_{date}_{window}.json",
    "d831": "v2_controlled_execution_decision_packet_{date}_{window}.json",
    "d820": "v2_controlled_resume_risk_acceptance_gate_{date}_{window}.json",
}

PROOF_SOURCES = {
    "real_state_present_case": "d832",
    "active_window_mutation_path": "d833",
    "production_cron_path": "d834",
    "production_qq_path": "d835",
    "production_verified_path": "d836",
    "formal_state_write_path": "d837",
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
        "d9_scope_matrix_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "all_six_targets_present": False,
        "all_six_status_unproven": False,
        "any_execution_allowed": False,
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
        "recommended_execution_order": TARGET_ORDER,
    }


def _proof_status(src: dict[str, Any]) -> str:
    return str(src.get("proof_current_status", "UNPROVEN"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    marker_paths = {
        key: STATUS_DIR / pattern.format(date=date_key, window=window)
        for key, pattern in MARKER_FILES.items()
    }
    markers = {key: _load(path) for key, path in marker_paths.items()}

    warnings: list[str] = []
    blockers: list[str] = []

    for key, src in markers.items():
        if not src:
            blockers.append(f"{key}_marker_missing")

    targets: list[dict[str, Any]] = []

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

        if str(markers["d841"].get("next_phase_decision_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
            blockers.append("D841_STATUS_INVALID")

        for target in TARGET_ORDER:
            src_key = PROOF_SOURCES[target]
            src = markers[src_key]
            ps = _proof_status(src)
            if ps != "UNPROVEN":
                blockers.append(f"PROOF_STATUS_NOT_UNPROVEN:{target}:{ps}")

            spec = TARGET_SPECS[target]
            targets.append(
                {
                    "proof_target": target,
                    "proof_current_status": "UNPROVEN",
                    "execution_allowed_now": False,
                    "can_be_synthetic": spec["can_be_synthetic"],
                    "must_be_real": spec["must_be_real"],
                    "dependency": spec["dependency"],
                    "required_inputs": spec["required_inputs"],
                    "required_outputs": spec["required_outputs"],
                    "forbidden_side_effects": spec["forbidden_side_effects"],
                    "evidence_required": spec["evidence_required"],
                    "rollback_required": True,
                    "watchdog_required": True,
                    "command_generation_allowed": True,
                    "command_execution_allowed": False,
                }
            )

        warnings.extend([f"UNPROVEN:{t}" for t in TARGET_ORDER])

    if blockers:
        status = "BLOCKER" if any(x.startswith("PIPELINE_READY_LEAK") or x.startswith("PRODUCTION_VERIFIED_LEAK") for x in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "all_six_targets_present": len(targets) == 6,
            "all_six_status_unproven": len(targets) == 6 and all(x.get("proof_current_status") == "UNPROVEN" for x in targets),
            "any_execution_allowed": any(_bool(x.get("execution_allowed_now"), False) or _bool(x.get("command_execution_allowed"), False) for x in targets),
            "targets": targets,
            "source_markers": {k: str(v) for k, v in marker_paths.items()},
            "d9_2_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "production_proof_evidence_schema_only",
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

    out_path = STATUS_DIR / f"v2_d9_proof_execution_scope_matrix_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
