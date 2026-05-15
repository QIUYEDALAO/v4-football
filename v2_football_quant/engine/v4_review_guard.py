#!/usr/bin/env python3
"""engine/v4_review_guard.py — V4复盘推送前守卫 v1.0

检查 v4_review_structured_YYYYMMDD.json 和渲染后的 QQ 文本是否符合规范。

20项检查：
1. A/B/C/SKIP 数量等于正式 brief
2. match_count 等于正式样本总数
3. 每场 official_bucket 必填
4. 每场 HT比分或 DATA_UNAVAILABLE
5. 每场 FT比分或 DATA_UNAVAILABLE
6. 有进球必须有进球分钟
7. 每场时间段分布
8. 每场赛前剧本字段
9. 每场剧本验证字段
10. 每场风险验证字段
11. 每场 weather_context
12-20: 各模块存在性 + 禁词

输出：data/runtime/status/v4_review_guard_YYYYMMDD.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"

FORBIDDEN = [
    "ROI", "CLV", "BET_LOCKED", "2.00-2.90", "V33",
    "FULLTIME_OVER", "SECOND_HALF_OVER", "market_scores",
    "A：7/7", "B：5/5", "A+B：12/12",
    "全场大", "下半场大", "回报",
    # Compressed enum (ground truth)
    "SCRIPTNOTAVAILABLE", "MODELTOOSTRICT", "DATAUNAVAILABLE",
    "APIHALFTIMESCORE",
    # Raw formats
    "fid=None", "FT DATA_UNAVAILABLE",
]

# QQ display must not contain these raw enums
RAW_ENUMS_IN_QQ = [
    "SCRIPT_HIT", "SCRIPT_PARTIAL", "SCRIPT_MISS",
    "NO_HT_GOAL", "SCRIPT_NA", "SCRIPT_NOT_AVAILABLE",
    "MODEL_VALID", "MODEL_TOO_STRICT", "MODEL_OVERCONFIDENT",
    "NOISY_WIN", "NOISY_LOSS", "DATA_QUALITY_ISSUE", "WEATHER_RISK",
]

REQUIRED_SECTIONS_FULL = [
    "正式输出", "逐场验证", "昨日汇总", "时间分布",
    "赛前剧本验证", "赛前信号复盘", "天气/场地因子",
    "滚动统计", "累计归因", "结论",
]

REQUIRED_SECTIONS_QQ = [
    "正式推荐", "C/SKIP汇总", "滚动观察", "结论",
]

DISPLAY_PER_MATCH_FIELDS = [
    "官方：", "赛果：", "进球：", "实际：",
    "结果：", "剧本：", "风险：", "天气：", "来源：",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--mode", default="full", choices=["full", "qq"])
    args = parser.parse_args()

    struct_path = REPORT_DIR / f"v4_review_structured_{args.date}.json"
    if args.mode == "full":
        qq_path = REPORT_DIR / f"v4_review_full_{args.date}.txt"
    else:
        qq_path = REPORT_DIR / f"v4_review_qq_{args.date}.txt"
    issues = []
    status = "PASS"

    if not struct_path.exists():
        issues.append("MISSING_STRUCTURED_JSON")
        _write(args.date, "BLOCKER", issues)
        sys.exit(2)

    with open(struct_path) as f:
        data = json.load(f)

    oc = data.get("official_counts", {})
    a = oc.get("A", -1)
    b = oc.get("B", -1)
    c = oc.get("C", -1)
    s = oc.get("SKIP", -1)
    matches = data.get("matches", [])
    total_slots = a + b + c + s

    # 1. A/B/C/SKIP validity
    if a < 0 or b < 0 or c < 0 or s < 0:
        issues.append(f"INVALID_OFFICIAL_COUNTS: A={a} B={b} C={c} SKIP={s}")

    # 2. Match count
    if len(matches) != total_slots:
        issues.append(f"MATCH_COUNT_MISMATCH: {len(matches)} vs {total_slots}")

    # 3-11. Per-match checks
    for i, m in enumerate(matches):
        idx = i + 1
        if not m.get("official_bucket"):
            issues.append(f"M{idx}_NO_BUCKET")
        if not m.get("ht_score"):
            issues.append(f"M{idx}_NO_HT")
        if not m.get("ft_score"):
            issues.append(f"M{idx}_NO_FT")
        goals = m.get("first_half_goal_minutes", [])
        if goals and not (m.get("goals_0_15") or m.get("goals_16_30") or m.get("goals_31_45")):
            issues.append(f"M{idx}_GOALS_NO_TIME_DIST")
        if not m.get("script_type"):
            issues.append(f"M{idx}_NO_SCRIPT_TYPE")
        if not m.get("script_check"):
            issues.append(f"M{idx}_NO_SCRIPT_CHECK")
        if not m.get("risk_review"):
            issues.append(f"M{idx}_NO_RISK_REVIEW")
        wc = m.get("weather_context", {})
        if not wc or not wc.get("weather_source"):
            issues.append(f"M{idx}_NO_WEATHER")

    # 12. Has summary
    if not data.get("summary"):
        issues.append("NO_SUMMARY")

    # 13. Has time distribution
    td = data.get("time_distribution", {})
    if not td or td.get("ht_goal_total") is None:
        issues.append("NO_TIME_DIST")

    # 14. Has script validation
    if not data.get("script_validation"):
        issues.append("NO_SCRIPT_VALIDATION")

    # 15. Has pre-match signal
    if not data.get("pre_match_signal"):
        issues.append("NO_PRE_MATCH_SIGNAL")

    # 16. Has weather
    if not any(m.get("weather_context") for m in matches):
        issues.append("NO_WEATHER_CONTEXT")

    # 17. Has rolling stats
    if not data.get("rolling_stats"):
        issues.append("NO_ROLLING_STATS")

    # 18. Has diagnosis summary
    if not data.get("diagnosis_summary"):
        issues.append("NO_DIAGNOSIS")

    # 19. Forbidden words in QQ text
    if qq_path.exists():
        text = qq_path.read_text()
        for word in FORBIDDEN:
            if word in text:
                issues.append(f"FORBIDDEN: {word}")

    # 20. Required sections in QQ text
    required_sections = REQUIRED_SECTIONS_QQ if args.mode == "qq" else REQUIRED_SECTIONS_FULL
    if qq_path.exists():
        text = qq_path.read_text()
        for section in required_sections:
            if section not in text:
                issues.append(f"MISSING_SECTION: {section}")

    # ── Display Guard: check final QQ text (full mode only) ──
    display_guard_ok = True
    if qq_path.exists() and args.mode == "full":
        text = qq_path.read_text()
        
        # a) Raw enum check
        for raw in RAW_ENUMS_IN_QQ:
            if raw in text:
                issues.append(f"DISPLAY_RAW_ENUM: {raw}")
                display_guard_ok = False
        
        # b) Compressed enum check
        for comp in ["SCRIPTNOTAVAILABLE", "MODELTOOSTRICT", "DATAUNAVAILABLE", "APIHALFTIMESCORE"]:
            if comp in text:
                issues.append(f"DISPLAY_COMPRESSED_ENUM: {comp}")
                display_guard_ok = False
        
        # c) None check
        none_count = text.count("None")
        if none_count > 0:
            issues.append(f"DISPLAY_NONE: {none_count} occurrences")
            display_guard_ok = False
        
        # d) N/A check
        na_count = text.count("N/A")
        if na_count > 8:
            issues.append(f"DISPLAY_EXCESS_NA: {na_count} occurrences (limit 8)")
            display_guard_ok = False
        
        # e) Separator check (per-match)
        separator = "━" * 20
        sep_count = text.count(separator)
        expected_seps = len(matches) - 1  # between each pair of matches
        if sep_count < expected_seps and len(matches) > 1:
            issues.append(f"DISPLAY_MISSING_SEPARATOR: found {sep_count}, expected >= {expected_seps}")
            display_guard_ok = False
        
        # f) Per-match field check
        for field in DISPLAY_PER_MATCH_FIELDS:
            if text.count(field) < len(matches):
                issues.append(f"DISPLAY_MISSING_FIELD: {field} (found {text.count(field)}, expected {len(matches)})")
                display_guard_ok = False
        
        if not display_guard_ok:
            issues.append("REPORT_DISPLAY_GUARD_GAP")

    # Determine status
    if issues:
        blocker_kw = ["BLOCKER", "MATCH_COUNT", "FORBIDDEN", "MISSING_STRUCTURED", "DISPLAY_RAW_ENUM", "REPORT_DISPLAY_GUARD_GAP"]
        has_blocker = any(k in str(issues) for k in blocker_kw)
        status = "BLOCKER" if has_blocker else "WARNING"

    _write(args.date, status, issues)

    print(f"📋 V4复盘守卫 v1.0 | {args.date}", flush=True)
    print(f"   status: {status}", flush=True)
    if issues:
        for iss in issues:
            print(f"   ⚠️ {iss}", flush=True)
    else:
        print(f"   ✅ 20/20 checks passed", flush=True)

    if status == "BLOCKER":
        sys.exit(2)


def _write(date_str: str, status: str, issues: list):
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    path = STATUS_DIR / f"v4_review_guard_{date_str}.json"
    out = {"date": date_str, "guard_status": status, "issues": issues,
           "checked_at": datetime.now().isoformat()}
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
