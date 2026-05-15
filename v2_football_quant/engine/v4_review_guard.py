#!/usr/bin/env python3
"""engine/v4_review_guard.py — V4复盘推送前守卫

检查 v4_review_structured_YYYYMMDD.json 和渲染后的 QQ 文本是否符合规范。

输出：
  data/runtime/status/v4_review_guard_YYYYMMDD.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
TEMPLATE = BASE_DIR / "templates" / "v4_daily_review_qq_template.md"

FORBIDDEN_WORDS = [
    "ROI", "CLV", "BET_LOCKED", "2.00-2.90", "V33",
    "FULLTIME_OVER", "SECOND_HALF_OVER", "market_scores",
    "A：7/7", "B：5/5", "A+B：12/12",
    "全场大", "下半场大",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    struct_path = REPORT_DIR / f"v4_review_structured_{args.date}.json"
    qq_path = REPORT_DIR / f"v4_review_qq_{args.date}.txt"

    issues = []
    status = "PASS"

    # 1. Check structured JSON exists
    if not struct_path.exists():
        issues.append("MISSING_STRUCTURED_JSON")
        status = "BLOCKER"
        _write_guard(args.date, status, issues)
        print(f"[GUARD] BLOCKER: structured JSON not found", flush=True)
        sys.exit(1)

    with open(struct_path) as f:
        data = json.load(f)

    oc = data.get("official_counts", {})
    a = oc.get("A", -1)
    b = oc.get("B", -1)
    c = oc.get("C", -1)
    s = oc.get("SKIP", -1)

    matches = data.get("matches", [])

    # 2. Check official_counts match formal brief
    if a < 0 or b < 0 or c < 0 or s < 0:
        issues.append(f"INVALID_OFFICIAL_COUNTS: A={a} B={b} C={c} SKIP={s}")

    # 3. Check match count
    total_slots = a + b + c + s
    if len(matches) != total_slots:
        issues.append(f"MATCH_COUNT_MISMATCH: structured={len(matches)} expected={total_slots}")

    # 4. Check per-match fields
    for i, m in enumerate(matches):
        if not m.get("official_bucket"):
            issues.append(f"MATCH_{i+1}_MISSING_OFFICIAL_BUCKET")
        if not m.get("ht_score") and m.get("ht_score") != "0-0":
            issues.append(f"MATCH_{i+1}_MISSING_HT_SCORE")
        if not m.get("data_source"):
            issues.append(f"MATCH_{i+1}_MISSING_DATA_SOURCE")
        goals = m.get("first_half_goal_minutes", [])
        if goals and not m.get("goals_0_15") and not m.get("goals_16_30") and not m.get("goals_31_45"):
            issues.append(f"MATCH_{i+1}_MISSING_TIME_DIST")

    # 5. Check time distribution
    td = data.get("time_distribution", {})
    if not td.get("ht_goal_total") and td.get("ht_goal_total") != 0:
        issues.append("MISSING_HT_GOAL_TOTAL")
    if td.get("goals_0_15", {}).get("count") is None:
        issues.append("MISSING_GOALS_0_15")
    if td.get("goals_16_30", {}).get("count") is None:
        issues.append("MISSING_GOALS_16_30")
    if td.get("goals_31_45", {}).get("count") is None:
        issues.append("MISSING_GOALS_31_45")

    fg = td.get("first_goal", {})
    if not fg:
        issues.append("MISSING_FIRST_GOAL_DISTRIBUTION")

    # 6. Check weather_context
    weather_unavail = 0
    for i, m in enumerate(matches):
        wc = m.get("weather_context", {})
        if not wc:
            issues.append(f"MATCH_{i+1}_MISSING_WEATHER_CONTEXT")
        elif not wc.get("weather_source"):
            issues.append(f"MATCH_{i+1}_MISSING_WEATHER_SOURCE")
        elif wc.get("weather_source") == "DATA_UNAVAILABLE":
            weather_unavail += 1
        else:
            # Has actual weather data - check for source
            risk = wc.get("weather_risk_level", "UNKNOWN")
            if risk == "HIGH" and not wc.get("weather_note"):
                issues.append(f"MATCH_{i+1}_HIGH_RISK_MISSING_NOTE")
    if weather_unavail > 0:
        issues.append(f"WEATHER_DATA_UNAVAILABLE: {weather_unavail}/{len(matches)} matches")
        # Not a blocker, just a warning

    # 7. Check diagnosis_summary
    ds = data.get("diagnosis_summary", {})
    if not ds:
        issues.append("MISSING_DIAGNOSIS_SUMMARY")

    # 7. Check rolling_stats
    rs = data.get("rolling_stats", {})
    if not rs:
        issues.append("MISSING_ROLLING_STATS")

    # 8. Check forbidden words in QQ text
    if qq_path.exists():
        qq_text = qq_path.read_text()
        for word in FORBIDDEN_WORDS:
            if word in qq_text:
                issues.append(f"FORBIDDEN_WORD_IN_QQ: {word}")

    # 9. Check QQ file has required sections
    if qq_path.exists():
        required_sections = [
            "无 A/B 主推荐" if a == 0 and b == 0 else "A+B",
            "逐场验证",
            "昨日汇总",
            "时间分布",
            "归因",
            "滚动统计",
            "结论",
        ]
        for section in required_sections:
            if section not in qq_text:
                issues.append(f"MISSING_SECTION: {section}")

    # Determine final status
    if issues:
        blocker_keywords = ["BLOCKER", "MISSING_STRUCTURED", "MATCH_COUNT", "FORBIDDEN"]
        has_blocker = any(k in str(issues) for k in blocker_keywords)
        status = "BLOCKER" if has_blocker else "WARNING"

    _write_guard(args.date, status, issues)

    print(f"📋 V4复盘守卫 | {args.date}", flush=True)
    print(f"   status: {status}", flush=True)
    if issues:
        for iss in issues:
            print(f"   ⚠️ {iss}", flush=True)
    else:
        print(f"   ✅ All checks passed", flush=True)

    if status == "BLOCKER":
        sys.exit(2)


def _write_guard(date_str: str, status: str, issues: list):
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    out = {
        "date": date_str,
        "guard_status": status,
        "issues": issues,
        "checked_at": datetime.now().isoformat(),
    }
    path = STATUS_DIR / f"v4_review_guard_{date_str}.json"
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
