#!/usr/bin/env python3
"""Phase D.8.5 — Single-window live observe plan checker (plan-only)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
DOC = BASE_DIR / "docs" / "V2_SINGLE_WINDOW_LIVE_OBSERVE_PLAN.md"
CN = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_single_window_live_observe_plan.v1"

REQUIRED_PHRASES = [
    "单窗口",
    "no-settlement-write",
    "no-QQ-push",
    "no-PRODUCTION_VERIFIED",
    "preflight fail-closed",
    "watchdog",
    "rollback",
    "失败仅报告 watchdog 状态",
    "不允许 AI 自由 kill/retry",
    "不允许补推",
    "不允许补记",
    "不允许手动修历史 verified",
]

FORBIDDEN_PHRASES = [
    "live_observe_execution_allowed=true",
    "settlement_write_allowed=true",
    "qq_push_allowed=true",
    "PRODUCTION_VERIFIED=true",
    "自动恢复生产",
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
        blockers.append("live_observe_plan_doc_missing")
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
        warnings.append("required_plan_phrases_missing")
    if forbidden_hit:
        warnings.append("forbidden_plan_phrase_detected")

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
        "live_observe_execution_allowed": False,
        "settlement_write_allowed": False,
        "qq_push_allowed": False,
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

    out = STATUS_DIR / f"v2_single_window_live_observe_plan_{date_key}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if plan_status == "BLOCKER":
        raise SystemExit(2)
    if plan_status == "NOT_READY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
