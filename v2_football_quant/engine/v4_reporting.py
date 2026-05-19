#!/usr/bin/env python3
"""
V4-G: Reporting Module

Pure functions for V4 daily/weekly/monthly report generation and mobile QQ brief.
No API calls, no writes, no QQ, no state, no verified, no rule changes.

Usage:
  python3 engine/v4_reporting.py --validate-only
  python3 engine/v4_reporting.py --dry-run --type daily --records-file <path>

Guard markers:
  NO_API = true
  NO_WRITE = true
  NO_QQ = true
  NO_STATE = true
  NO_VERIFIED = true
  NO_RULE_CHANGE = true
"""

import argparse
import json
import sys
from typing import Any


def validate_report_input(payload: dict) -> list[str]:
    """Validate report payload has required fields."""
    errors = []
    required = ["report_type", "date"]
    for field in required:
        if field not in payload:
            errors.append(f"Missing required field: '{field}'")
    rtype = payload.get("report_type")
    if rtype not in ("daily", "weekly", "monthly"):
        errors.append(f"Invalid report_type: {rtype}. Must be daily/weekly/monthly")
    return errors


def build_daily_report(payload: dict) -> dict:
    """Build a daily report summary (full version)."""
    return {
        "report_type": "daily",
        "schema": "V4_REPORTING_SCHEMA",
        "date": payload.get("date", ""),
        "window": payload.get("window", "daily"),
        "A_count": payload.get("A_count", 0),
        "B_count": payload.get("B_count", 0),
        "C_count": payload.get("C_count", 0),
        "SKIP_count": payload.get("SKIP_count", 0),
        "unknown_count": payload.get("unknown_count", 0),
        "api_disabled_count": payload.get("api_disabled_count", 0),
        "A_B_primary": payload.get("A_B_primary", {}),
        "C_observation": payload.get("C_observation", {}),
        "SKIP_behavior": payload.get("SKIP_behavior", {}),
        "guard_summary": payload.get("guard_summary", {}),
        "risk_summary": payload.get("risk_summary", ""),
        "rolling_snapshot": payload.get("rolling_snapshot", {}),
        "report_allowed": True,
        "qq_allowed": False,
        "production_verified": False,
        "rule_change_allowed": False,
    }


def build_mobile_qq_brief(payload: dict) -> str:
    """Build a mobile-friendly QQ brief (short text, no tables)."""
    date = payload.get("date", "unknown")
    a_cnt = payload.get("A_count", 0)
    b_cnt = payload.get("B_count", 0)
    ab_hit = payload.get("ab_hit", 0)
    ab_total = payload.get("ab_total", 0)
    ab_rate = f"{ab_hit}/{ab_total}" if ab_total > 0 else "N/A"
    c_cnt = payload.get("C_count", 0)
    skip_cnt = payload.get("SKIP_count", 0)
    guard = payload.get("guard_status", "PASS")

    lines = [
        "【V4 情报系统】",
        f"📌 昨日V4复盘 · {date}",
        f"Guard: {guard} | No-Push: true",
        "",
        "【正式推荐】",
        f"A：{a_cnt}｜B：{b_cnt}",
        f"A/B正式结论：{ab_total}场（命中{ab_hit}/{ab_total} · {ab_rate}）",
        "",
        "【C/SKIP汇总】",
        f"C级（观察）：{c_cnt}场",
        f"SKIP：{skip_cnt}场",
        "详细已入库。",
        "",
        "【结论】",
        "样本量评估中。规则未调整。",
        "⚠️ 赛后归因报告，不代表今日实盘推荐",
    ]
    return "\n".join(lines)


def build_weekly_report(payload: dict) -> dict:
    """Build a weekly report summary."""
    return {
        "report_type": "weekly",
        "schema": "V4_REPORTING_SCHEMA",
        "week_start": payload.get("week_start", ""),
        "week_end": payload.get("week_end", ""),
        "total_samples": payload.get("total_samples", 0),
        "A_B_primary": payload.get("A_B_primary", {}),
        "C_observation": payload.get("C_observation", {}),
        "SKIP_behavior": payload.get("SKIP_behavior", {}),
        "unknown_excluded": payload.get("unknown_excluded", 0),
        "api_disabled_excluded": payload.get("api_disabled_excluded", 0),
        "rolling_7d_summary": payload.get("rolling_7d_summary", {}),
        "rule_change_allowed": False,
        "production_verified": False,
    }


def build_monthly_report(payload: dict) -> dict:
    """Build a monthly report summary."""
    return {
        "report_type": "monthly",
        "schema": "V4_REPORTING_SCHEMA",
        "month": payload.get("month", ""),
        "rolling_30d_summary": payload.get("rolling_30d_summary", {}),
        "sample_size_summary": payload.get("sample_size_summary", ""),
        "grade_split": payload.get("grade_split", {}),
        "data_quality_summary": payload.get("data_quality_summary", ""),
        "rule_change_recommendation_allowed": False,
        "verified_write_allowed": False,
        "production_verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--type", choices=["daily", "weekly", "monthly"], default="daily")
    parser.add_argument("--records-file", default=None)
    args = parser.parse_args()

    if args.validate_only:
        print("[VALIDATE-ONLY] Reporting module ready.")
        print("[VALIDATE-ONLY] No API, no writes, no QQ, no side effects.")
        return

    if not args.records_file:
        print("[ERROR] --records-file required (or use --validate-only)")
        sys.exit(1)

    with open(args.records_file, "r") as f:
        raw = json.load(f)

    errors = validate_report_input(raw)
    if errors:
        for e in errors:
            print(f"[ERROR] {e}")
        sys.exit(1)

    builders = {
        "daily": build_daily_report,
        "weekly": build_weekly_report,
        "monthly": build_monthly_report,
    }
    result = builders[args.type](raw)
    if args.dry_run:
        result["dry_run"] = True
        result["file_written"] = False
        result["qq_sent"] = False

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("\n[DRY-RUN] Report computed but NOT written.")
        print("[DRY-RUN] No QQ, no verified, no state changes.")


if __name__ == "__main__":
    main()
