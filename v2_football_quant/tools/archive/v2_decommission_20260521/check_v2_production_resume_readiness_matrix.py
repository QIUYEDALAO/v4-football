#!/usr/bin/env python3
"""Phase D.8.28 — production resume readiness matrix (gap matrix only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_production_resume_readiness_matrix.v1"

GAPS = [
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
        "readiness_matrix_status": status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "production_resume_ready": False,
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


def _entry(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "current_status": "NOT_PROVEN",
        "required_evidence": f"proof_for_{name}",
        "blocking_level": "HIGH",
        "can_be_synthetic": name in {"active_window_mutation_path"},
        "must_be_real": name in {
            "real_state_present_case",
            "production_cron_path",
            "production_qq_path",
            "production_verified_path",
            "formal_state_write_path",
        },
        "allowed_to_execute_now": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    p_d827 = STATUS_DIR / f"v2_controlled_execution_simulation_plan_{date_key}_{window}.json"
    p_d825 = STATUS_DIR / f"v2_final_controlled_execution_approval_packet_{date_key}_{window}.json"
    d827 = _load(p_d827)
    d825 = _load(p_d825)

    warnings: list[str] = []
    blockers: list[str] = []

    if not d827:
        blockers.append("D827_MARKER_MISSING")
    if not d825:
        blockers.append("D825_MARKER_MISSING")

    if blockers:
        out = _base(date_key, window, "BLOCKER")
        out.update(
            {
                "source_markers": {"d827": str(p_d827), "d825": str(p_d825)},
                "readiness_matrix": [_entry(g) for g in GAPS],
                "remaining_blockers_count": len(GAPS),
                "d829_draft": {
                    "allowed_to_generate": True,
                    "allowed_to_execute": False,
                    "scope": "phase_d_final_decision_packet_only",
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
        out_path = STATUS_DIR / f"v2_production_resume_readiness_matrix_{date_key}_{window}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    if str(d827.get("simulation_plan_status", "")) not in {"READY_FOR_BOSS_REVIEW", "WARN"}:
        blockers.append("D827_STATUS_INVALID")

    for src_name, src in (("d827", d827), ("d825", d825)):
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

        pg = src.get("production_gates", {}) if isinstance(src.get("production_gates"), dict) else {}
        for g in (
            "production_resume_allowed_now",
            "cron_enable_allowed",
            "qq_push_allowed",
            "verified_write_allowed",
            "state_write_allowed",
        ):
            if _bool(pg.get(g), False):
                blockers.append(f"GATE_LEAK:{g}:{src_name}")

    d828 = d827.get("d828_draft", {}) if isinstance(d827.get("d828_draft"), dict) else {}
    if not _bool(d828.get("allowed_to_generate"), False):
        blockers.append("D828_ALLOWED_TO_GENERATE_FALSE")
    if _bool(d828.get("allowed_to_execute"), True):
        blockers.append("D828_ALLOWED_TO_EXECUTE_TRUE")

    # Build matrix from known unproven items
    unproven = d825.get("unproven_items", []) if isinstance(d825.get("unproven_items"), list) else []
    matrix = [_entry(g) for g in GAPS]
    unproven_set = set(str(x) for x in unproven)
    for e in matrix:
        if e["name"] in unproven_set:
            e["current_status"] = "UNPROVEN"
        else:
            e["current_status"] = "UNKNOWN_OR_NOT_RECORDED"
            warnings.append(f"MATRIX_ITEM_NOT_EXPLICIT_IN_D825:{e['name']}")

    remaining_blockers_count = len(matrix)
    warnings.extend([f"UNPROVEN:{x}" for x in GAPS])

    if blockers:
        status = "BLOCKER" if any(b.startswith("PIPELINE_READY_LEAK") or b.startswith("PRODUCTION_VERIFIED_LEAK") for b in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "source_markers": {"d827": str(p_d827), "d825": str(p_d825)},
            "readiness_matrix": matrix,
            "remaining_blockers_count": remaining_blockers_count,
            "d829_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "phase_d_final_decision_packet_only",
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

    out_path = STATUS_DIR / f"v2_production_resume_readiness_matrix_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
