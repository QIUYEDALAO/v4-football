#!/usr/bin/env python3
"""Phase D.8.7 — V2 Limited Resume Boss Approval Packet checker."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_limited_resume_approval_packet.v1"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _s(v: Any) -> str:
    return str(v or "MISSING").upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    args = parser.parse_args()
    date_key = str(args.date).replace("-", "")

    p_d81 = STATUS_DIR / f"v2_controlled_resume_plan_{date_key}.json"
    p_d82 = STATUS_DIR / f"v2_cron_dryrun_validation_{date_key}.json"
    p_d83 = STATUS_DIR / f"v2_no_push_production_dryrun_{date_key}.json"
    p_d84 = STATUS_DIR / f"v2_qq_route_dryrun_{date_key}.json"
    p_d85 = STATUS_DIR / f"v2_single_window_live_observe_plan_{date_key}.json"
    p_d86 = STATUS_DIR / f"v2_settlement_preflight_live_guard_observe_{date_key}.json"
    p_pack = STATUS_DIR / f"v2_controlled_resume_validation_pack_{date_key}.json"
    p_ready = STATUS_DIR / f"v2_production_resume_readiness_{date_key}.json"
    p_wrapper = STATUS_DIR / f"v2_settlement_preflight_wrapper_block_test_{date_key}.json"
    p_shadow = STATUS_DIR / f"v2_settlement_shadow_guard_{date_key}.json"
    p_comp = STATUS_DIR / f"phase_d_completion_check_{date_key}.json"

    d81 = _load_json(p_d81, {})
    d82 = _load_json(p_d82, {})
    d83 = _load_json(p_d83, {})
    d84 = _load_json(p_d84, {})
    d85 = _load_json(p_d85, {})
    d86 = _load_json(p_d86, {})
    pack = _load_json(p_pack, {})
    ready = _load_json(p_ready, {})
    wrapper = _load_json(p_wrapper, {})
    shadow = _load_json(p_shadow, {})
    comp = _load_json(p_comp, {})

    warnings: list[str] = []
    blockers: list[str] = []

    if not p_pack.exists():
        blockers.append("validation_pack_marker_missing")

    # source statuses
    d81_status = _s(d81.get("plan_status"))
    d82_status = _s(d82.get("cron_dryrun_status"))
    d83_status = _s(d83.get("dryrun_status"))
    d84_status = _s(d84.get("qq_route_status"))
    d85_status = _s(d85.get("plan_status"))
    d86_status = _s(d86.get("plan_status"))
    pack_status = _s(pack.get("pack_status"))

    # strict forbidden booleans
    if bool(pack.get("resume_execution_allowed", False)):
        blockers.append("pack_resume_execution_allowed_true")
    if bool(pack.get("cron_enable_allowed", False)):
        blockers.append("pack_cron_enable_allowed_true")
    if bool(pack.get("qq_push_allowed", False)):
        blockers.append("pack_qq_push_allowed_true")
    if bool(pack.get("production_verified", False)):
        blockers.append("pack_production_verified_true")

    if bool(d81.get("resume_execution_allowed", False)):
        blockers.append("d81_resume_execution_allowed_true")
    if bool(d81.get("cron_change_allowed", False)):
        blockers.append("d81_cron_change_allowed_true")
    if bool(d81.get("qq_push_allowed", False)):
        blockers.append("d81_qq_push_allowed_true")

    if bool(ready.get("production_verified", False)):
        blockers.append("readiness_production_verified_true")

    if str(wrapper.get("status", "")).upper() != "PASS":
        blockers.append("wrapper_block_test_not_pass")

    if str(shadow.get("status", "")).upper() != "FAIL":
        blockers.append("historical_shadow_fail_not_preserved")

    if bool(comp.get("known_historical_fail", False)) is not True:
        blockers.append("known_historical_fail_not_archived")

    # risk classification
    warn_risks: list[str] = []
    warn_risks.extend([str(x) for x in d82.get("risks", []) if isinstance(x, str)])
    warn_risks.extend([str(x) for x in d83.get("warnings", []) if isinstance(x, str)])
    warn_risks.extend([str(x) for x in d84.get("risks", []) if isinstance(x, str)])
    warn_risks.extend([str(x) for x in d85.get("warnings", []) if isinstance(x, str)])
    warn_risks.extend([str(x) for x in pack.get("warnings", []) if isinstance(x, str)])
    # uniq keep order
    seen=set(); warn_risks=[x for x in warn_risks if not (x in seen or seen.add(x))]

    accepted_plan_risks = [
        "manual QQ push path exists but remains disabled by no-push policy",
        "safe_outbound_sender guard signature requires hardening before any live QQ enablement",
        "single-window live observe remains plan-only (execution blocked)",
        "validation pack is WARN and requires explicit boss review",
    ]

    if pack_status == "MISSING":
        blockers.append("pack_status_missing")

    if blockers:
        approval_status = "BLOCKER"
    elif pack_status in {"BLOCKER", "NOT_READY", "FAIL"}:
        approval_status = "NOT_READY"
    elif pack_status == "WARN" or any(s == "WARN" for s in [d82_status,d83_status,d84_status,d85_status,d86_status]):
        approval_status = "WARN"
    else:
        approval_status = "READY_FOR_BOSS_REVIEW"

    if approval_status == "WARN":
        warnings.append("approval_packet_contains_warn_risks")

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "approval_packet_status": approval_status,
        "limited_resume_approved": False,
        "resume_execution_allowed": False,
        "cron_enable_allowed": False,
        "qq_push_allowed": False,
        "boss_approval_required": True,
        "ready_for_boss_review": approval_status in {"READY_FOR_BOSS_REVIEW", "WARN"},
        "source_pack": {
            "d81_plan_status": d81_status,
            "d82_cron_status": d82_status,
            "d83_no_push_status": d83_status,
            "d84_qq_route_status": d84_status,
            "d85_live_plan_status": d85_status,
            "d86_preflight_live_guard_status": d86_status,
            "validation_pack_status": pack_status,
        },
        "risk_classification": {
            "blocking_risks": blockers.copy(),
            "warn_risks": warn_risks,
            "accepted_plan_risks": accepted_plan_risks,
        },
        "approval_requirements": {
            "explicit_boss_approval_required": True,
            "cron_enable_requires_separate_command": True,
            "qq_push_requires_separate_command": True,
            "production_verified_forbidden": True,
            "rollback_required": True,
        },
        "d88_draft": {
            "allowed_to_generate": True,
            "allowed_to_execute": False,
            "scope": "single-window controlled resume only after BOSS approval",
        },
        "rollback_gate": {
            "disable_cron_immediately": True,
            "keep_preflight_fail_closed": True,
            "no_ai_kill_retry": True,
            "report_watchdog_only": True,
            "preserve_logs": True,
        },
        "warnings": warnings,
        "blockers": blockers,
        "generated_at": datetime.now(CN).isoformat(),
    }

    out = STATUS_DIR / f"v2_limited_resume_approval_packet_{date_key}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if approval_status == "BLOCKER":
        raise SystemExit(2)
    if approval_status == "NOT_READY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
