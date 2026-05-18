#!/usr/bin/env python3
"""Phase D.8.6 — Settlement preflight live guard observe plan checker (plan-only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
DOC = BASE_DIR / "docs" / "V2_SETTLEMENT_PREFLIGHT_LIVE_GUARD_OBSERVE.md"
CN = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_settlement_preflight_live_guard_observe.v1"

REQUIRED_PHRASES = [
    "settlement 入口必须先执行 preflight",
    "official_bet_locked=0",
    "new_locks_count=0",
    "lock_owner",
    "missed_candidates",
    "source marker 缺失",
    "不得调用 `verify_date`",
    "不得写 `verified`",
    "BLOCKED_PREFLIGHT",
    "不得自动写 `PRODUCTION_VERIFIED`",
    "失败只报告 watchdog 状态",
    "不允许 AI 自由 kill/retry",
]

FORBIDDEN_PHRASES = [
    "live_guard_execution_allowed=true",
    "preflight_required=false",
    "fail_closed_required=false",
    "verified_write_blocked_when_preflight_blocks=false",
    "PRODUCTION_VERIFIED=true",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    args = parser.parse_args()
    date_key = str(args.date).replace("-", "")

    warnings: list[str] = []
    blockers: list[str] = []
    missing_required: list[str] = []
    forbidden_hit: list[str] = []

    if not DOC.exists():
        blockers.append("settlement_live_guard_plan_doc_missing")
        text = ""
    else:
        text = DOC.read_text(encoding="utf-8", errors="replace")

    for p in REQUIRED_PHRASES:
        if p not in text:
            missing_required.append(p)

    for p in FORBIDDEN_PHRASES:
        if p in text:
            forbidden_hit.append(p)

    if missing_required:
        warnings.append("required_guard_plan_phrases_missing")
    if forbidden_hit:
        warnings.append("forbidden_guard_plan_phrase_detected")

    if blockers:
        plan_status = "BLOCKER"
    elif forbidden_hit:
        plan_status = "NOT_READY"
    elif missing_required:
        plan_status = "WARN"
    else:
        plan_status = "READY_FOR_BOSS_REVIEW"

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "live_guard_execution_allowed": False,
        "preflight_required": True,
        "fail_closed_required": True,
        "verify_date_blocked_when_preflight_blocks": True,
        "verified_write_blocked_when_preflight_blocks": True,
        "watchdog_status_required": True,
        "production_verified": False,
        "boss_approval_required": True,
        "plan_status": plan_status,
        "required_phrases": REQUIRED_PHRASES,
        "missing_required_phrases": missing_required,
        "forbidden_phrases_hit": forbidden_hit,
        "warnings": warnings,
        "blockers": blockers,
        "generated_at": datetime.now(CN).isoformat(),
    }

    out = STATUS_DIR / f"v2_settlement_preflight_live_guard_observe_{date_key}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if plan_status == "BLOCKER":
        raise SystemExit(2)
    if plan_status == "NOT_READY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
