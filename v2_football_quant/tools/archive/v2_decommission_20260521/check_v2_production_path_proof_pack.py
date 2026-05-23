#!/usr/bin/env python3
"""Phase D.8.38 — production path proof pack consolidation (read-only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_production_path_proof_pack.v1"

PROOF_MARKERS = {
    "real_state_present_case": "v2_real_state_present_proof_plan_{date}_{window}.json",
    "active_window_mutation_path": "v2_active_window_mutation_proof_plan_{date}_{window}.json",
    "production_cron_path": "v2_production_cron_path_proof_plan_{date}_{window}.json",
    "production_qq_path": "v2_production_qq_path_proof_plan_{date}_{window}.json",
    "production_verified_path": "v2_production_verified_write_path_proof_plan_{date}_{window}.json",
    "formal_state_write_path": "v2_formal_state_write_path_proof_plan_{date}_{window}.json",
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
        "proof_pack_status": status,
        "proof_pack_scope": "consolidation_only",
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "all_six_plans_present": False,
        "all_six_proof_status": "UNPROVEN",
        "any_proof_marked_proven": False,
        "unproven_items_count": 6,
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
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    paths: dict[str, Path] = {
        k: STATUS_DIR / pattern.format(date=date_key, window=window) for k, pattern in PROOF_MARKERS.items()
    }
    markers: dict[str, dict[str, Any]] = {k: _load(p) for k, p in paths.items()}

    warnings: list[str] = []
    blockers: list[str] = []

    for key, src in markers.items():
        if not src:
            blockers.append(f"{key}_marker_missing")

    if blockers:
        out = _base(date_key, window, "BLOCKER")
        out.update(
            {
                "source_markers": {k: str(v) for k, v in paths.items()},
                "all_six_plans_present": False,
                "proof_items": [],
                "d839_draft": {
                    "allowed_to_generate": True,
                    "allowed_to_execute": False,
                    "scope": "phase_d_terminal_readiness_gate_only",
                },
                "warnings": warnings,
                "blockers": blockers,
                "generated_at": datetime.now(CN).isoformat(),
            }
        )
        out_path = STATUS_DIR / f"v2_production_path_proof_pack_{date_key}_{window}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    proof_items: list[dict[str, Any]] = []
    any_proven = False

    for key, src in markers.items():
        if _bool(src.get("pipeline_ready"), False):
            blockers.append(f"PIPELINE_READY_LEAK:{key}")
        if _bool(src.get("production_verified"), False):
            blockers.append(f"PRODUCTION_VERIFIED_LEAK:{key}")

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
                blockers.append(f"FORBIDDEN_TRUE:{field}:{key}")

        for g in (
            "production_resume_allowed_now",
            "cron_enable_allowed",
            "qq_push_allowed",
            "verified_write_allowed",
            "state_write_allowed",
        ):
            if _gate(src, g):
                blockers.append(f"GATE_LEAK:{g}:{key}")

        proof_status = str(src.get("proof_current_status", "UNPROVEN"))
        if proof_status == "PROVEN":
            any_proven = True
            blockers.append(f"UNEXPECTED_PROVEN:{key}")
        if proof_status != "UNPROVEN":
            warnings.append(f"PROOF_STATUS_NOT_UNPROVEN:{key}:{proof_status}")

        proof_items.append({"proof_target": key, "proof_current_status": proof_status})

    warnings.extend([f"UNPROVEN:{k}" for k in PROOF_MARKERS.keys()])

    if blockers:
        status = "BLOCKER" if any(x.startswith("PIPELINE_READY_LEAK") or x.startswith("PRODUCTION_VERIFIED_LEAK") for x in blockers) else "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "READY_FOR_BOSS_REVIEW"

    out = _base(date_key, window, status)
    out.update(
        {
            "source_markers": {k: str(v) for k, v in paths.items()},
            "all_six_plans_present": True,
            "all_six_proof_status": "UNPROVEN" if not any_proven else "MIXED",
            "any_proof_marked_proven": any_proven,
            "proof_items": proof_items,
            "unproven_items_count": sum(1 for x in proof_items if x.get("proof_current_status") == "UNPROVEN"),
            "d839_draft": {
                "allowed_to_generate": True,
                "allowed_to_execute": False,
                "scope": "phase_d_terminal_readiness_gate_only",
            },
            "warnings": warnings,
            "blockers": blockers,
            "generated_at": datetime.now(CN).isoformat(),
        }
    )

    out_path = STATUS_DIR / f"v2_production_path_proof_pack_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
