#!/usr/bin/env python3
"""Phase D.8.2-D.8.6 validation pack aggregator."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_controlled_resume_validation_pack.v1"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _norm_status(v: Any) -> str:
    return str(v or "MISSING").upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    args = parser.parse_args()
    date_key = str(args.date).replace("-", "")

    paths = {
        "d81": STATUS_DIR / f"v2_controlled_resume_plan_{date_key}.json",
        "d82": STATUS_DIR / f"v2_cron_dryrun_validation_{date_key}.json",
        "d83": STATUS_DIR / f"v2_no_push_production_dryrun_{date_key}.json",
        "d84": STATUS_DIR / f"v2_qq_route_dryrun_{date_key}.json",
        "d85": STATUS_DIR / f"v2_single_window_live_observe_plan_{date_key}.json",
        "d86": STATUS_DIR / f"v2_settlement_preflight_live_guard_observe_{date_key}.json",
    }

    data = {k: _load_json(p, {}) for k, p in paths.items()}
    missing = [k for k, p in paths.items() if not p.exists()]

    d81_status = _norm_status(data["d81"].get("plan_status"))
    d82_status = _norm_status(data["d82"].get("cron_dryrun_status"))
    d83_status = _norm_status(data["d83"].get("dryrun_status"))
    d84_status = _norm_status(data["d84"].get("qq_route_status"))
    d85_status = _norm_status(data["d85"].get("plan_status"))
    d86_status = _norm_status(data["d86"].get("plan_status"))

    statuses = {
        "d81_status": d81_status,
        "d82_status": d82_status,
        "d83_status": d83_status,
        "d84_status": d84_status,
        "d85_status": d85_status,
        "d86_status": d86_status,
    }

    warnings: list[str] = []
    risks: list[str] = []
    blockers: list[str] = []

    if missing:
        blockers.append("required_markers_missing")

    if any(s == "BLOCKER" for s in statuses.values()):
        pack_status = "BLOCKER"
    elif any(s in {"FAIL", "NOT_READY"} for s in statuses.values()):
        pack_status = "NOT_READY"
    elif any(s == "WARN" for s in statuses.values()):
        pack_status = "WARN"
    else:
        pack_status = "READY_FOR_BOSS_REVIEW"

    if pack_status == "WARN":
        warnings.append("one_or_more_sub_checks_warn")
    if pack_status == "NOT_READY":
        risks.append("sub_check_not_ready_or_fail")

    resume_execution_allowed = False
    cron_enable_allowed = False
    qq_push_allowed = False
    live_execution_allowed = False

    if data["d81"].get("resume_execution_allowed") is True:
        blockers.append("d81_resume_execution_allowed_true")
    if data["d81"].get("cron_change_allowed") is True:
        blockers.append("d81_cron_change_allowed_true")
    if data["d81"].get("qq_push_allowed") is True:
        blockers.append("d81_qq_push_allowed_true")

    if blockers:
        pack_status = "BLOCKER"

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "pack_status": pack_status,
        "current_level": "CODE_READY",
        "pipeline_ready": False,
        "production_verified": False,
        "resume_execution_allowed": resume_execution_allowed,
        "cron_enable_allowed": cron_enable_allowed,
        "qq_push_allowed": qq_push_allowed,
        "live_execution_allowed": live_execution_allowed,
        "boss_approval_required": True,
        "d82_status": d82_status,
        "d83_status": d83_status,
        "d84_status": d84_status,
        "d85_status": d85_status,
        "d86_status": d86_status,
        "risks": risks,
        "warnings": warnings,
        "blockers": blockers,
        "next_gate": "D.8.7_BOSS_APPROVAL_ONLY",
        "generated_at": datetime.now(CN).isoformat(),
    }

    out = STATUS_DIR / f"v2_controlled_resume_validation_pack_{date_key}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if pack_status == "BLOCKER":
        raise SystemExit(2)
    if pack_status == "NOT_READY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
