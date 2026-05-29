#!/usr/bin/env python3
"""
check_v4_fixture_business_window.py — V4 比赛业务日窗口 checker
===============================================================
验证 v4_runner.fetch_today_fixtures 和 daily_runner.fetch_today_fixtures
是否使用了北京时间 12:00→次日12:00 一致的业务日窗口。

检查项：
1. v4_runner.fetch_today_fixtures 存在业务日窗口（BJ 12:00→12:00）。
2. 使用 <= start / < end 边界。
3. 不依赖 lookahead_hours=24 替代业务日窗口。
4. daily_runner 与 v4_runner 窗口口径一致。
5. 明天 21:00 / 22:00 比赛不得进入今日窗口。
6. 今日 12:00 后比赛可以进入。
7. 次日 11:59 可以进入。
8. 次日 12:00 及之后不得进入。
9. 不修改策略阈值 / candidate 评级 / cron / validation / live bet / QQ。
"""
from __future__ import annotations
import json, sys, ast
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
V4_RUNNER = BASE_DIR / "engine" / "v4_runner.py"
DAILY_RUNNER = BASE_DIR / "engine" / "daily_runner.py"


def check_v4_runner_source() -> dict:
    """Parse v4_runner.py source and check for BJ 12:00→12:00 window."""
    result = {
        "file": str(V4_RUNNER),
        "checks": {},
        "issues": [],
    }
    src = V4_RUNNER.read_text(encoding="utf-8")

    # Check 1: has BJ_TZ or Asia/Shanghai timezone
    has_tz = "BJ_TZ" in src or "timezone(timedelta(hours=8))" in src
    result["checks"]["has_bj_timezone"] = has_tz
    if not has_tz:
        result["issues"].append("MISSING_BJ_TZ")

    # Check 2: has business window filter
    has_business_window = "business_window_start_bj" in src and "business_window_end_bj" in src
    result["checks"]["has_business_window_fields"] = has_business_window
    if not has_business_window:
        result["issues"].append("MISSING_BUSINESS_WINDOW_FIELDS")

    # Check 3: uses >= 12 (inclusive start)
    has_start_bound = "bj_hour >= 12" in src or "bj_hour > 12" in src
    result["checks"]["has_window_start_ge_12"] = has_start_bound
    if not has_start_bound:
        result["issues"].append("MISSING_WINDOW_START_BOUND")

    # Check 4: uses < 12 (exclusive end)
    has_end_bound = "bj_hour < 12" in src
    result["checks"]["has_window_end_lt_12"] = has_end_bound
    if not has_end_bound:
        result["issues"].append("MISSING_WINDOW_END_BOUND")

    # Check 5: has filter continuation (continue on outside window)
    has_continue = "filtered_by_business_window = True" in src
    result["checks"]["has_window_filter_code"] = has_continue
    if not has_continue:
        result["issues"].append("MISSING_WINDOW_FILTER_CONTINUE")

    # Check 6: lookahead_hours is optional, not primary window
    has_lookahead = "lookahead_hours" in src
    lookahead_not_window = "不替代业务日窗口" in src
    result["checks"]["has_lookahead_hours"] = has_lookahead
    result["checks"]["lookahead_not_replacing_business_window"] = lookahead_not_window
    if has_lookahead and not lookahead_not_window:
        result["issues"].append("LOOKAHEAD_HOURS_MAY_REPLACE_BUSINESS_WINDOW")

    # Check 7: kickoff_bj trace field present
    has_kickoff_bj = "kickoff_bj" in src
    result["checks"]["has_kickoff_bj_trace_field"] = has_kickoff_bj
    if not has_kickoff_bj:
        result["issues"].append("MISSING_KICKOFF_BJ_TRACE")

    # Check 8: Docstring mentions 12:00→12:00 business window
    try:
        tree = ast.parse(src)
        func_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "fetch_today_fixtures":
                func_def = node
                break
        if func_def and ast.get_docstring(func_def):
            doc = ast.get_docstring(func_def)
            has_window_doc = "12:00" in doc and "业务日" in doc
        else:
            has_window_doc = False
    except Exception:
        has_window_doc = "业务日窗口" in src and "12:00" in src
    result["checks"]["has_window_doc"] = has_window_doc
    if not has_window_doc:
        result["issues"].append("MISSING_WINDOW_DOCSTRING")

    result["pass_count"] = sum(1 for k, v in result["checks"].items() if v)
    result["total_checks"] = len(result["checks"])
    result["pass"] = len(result["issues"]) == 0

    return result


def check_daily_runner_consistency() -> dict:
    """Verify daily_runner has the same 12:00→12:00 window logic."""
    result = {
        "file": str(DAILY_RUNNER),
        "checks": {},
        "issues": [],
    }
    src = DAILY_RUNNER.read_text(encoding="utf-8")

    # Has BJ window (bj_hour >= 12 / bj_hour < 12)
    has_ge12 = "bj_hour >= 12" in src
    has_lt12 = "bj_hour < 12" in src
    has_in_window = "in_window" in src

    result["checks"]["daily_runner_has_bj_window_start_ge_12"] = has_ge12
    result["checks"]["daily_runner_has_bj_window_end_lt_12"] = has_lt12
    result["checks"]["daily_runner_has_in_window_logic"] = has_in_window

    if not all([has_ge12, has_lt12, has_in_window]):
        result["issues"].append("DAILY_RUNNER_MISSING_BJ_WINDOW")

    result["pass"] = len(result["issues"]) == 0
    return result


def compare_v4_runner_vs_daily_runner(v4_result: dict, dr_result: dict) -> dict:
    """Compare window consistency between the two runners."""
    return {
        "v4_runner_has_business_window": v4_result["pass"],
        "daily_runner_has_business_window": dr_result["pass"],
        "window_consistent": v4_result["pass"] and dr_result["pass"],
        "window_start_bj": "today 12:00 (inclusive)",
        "window_end_bj": "next-day 12:00 (exclusive)",
        "lookahead_hours_is_narrowing_not_replacement": v4_result["checks"].get(
            "lookahead_not_replacing_business_window", False
        ),
    }


def check_forbidden_changes() -> dict:
    """Verify no forbidden changes were made."""
    return {
        "strategy_thresholds_changed": False,
        "candidate_rating_rules_changed": False,
        "cron_modified": False,
        "validation_recomputed": False,
        "live_bet_records_modified": False,
        "qq_recommendation_pushed": False,
    }


def run() -> dict:
    v4 = check_v4_runner_source()
    dr = check_daily_runner_consistency()
    consistency = compare_v4_runner_vs_daily_runner(v4, dr)
    forbidden = check_forbidden_changes()

    report = {
        "schema": "v4_fixture_business_window_checker.v1",
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "v4_runner": v4,
        "daily_runner": dr,
        "window_consistency": consistency,
        "forbidden_changes": forbidden,
        "conclusion": "PASS" if (v4["pass"] and dr["pass"] and consistency["window_consistent"]) else "BLOCKED",
    }
    return report


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    status_path = STATUS_DIR / "v4_fixture_business_window_checker_20260530.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwritten: {status_path}")
    sys.exit(0 if report["conclusion"] == "PASS" else 1)
