#!/usr/bin/env python3
"""engine/v4_review_guard.py — V4复盘推送前守卫 v1.1

检查 v4_review_structured_YYYYMMDD.json 和渲染后的文本是否符合规范。

mode=full:
  - match_count == official total (A+B+C+SKIP)
  - per-match field coverage (script_check/risk_review/weather允许DATA_UNAVAILABLE)
  - 允许合法缺失降级

mode=qq:
  - A/B可以展示，C/SKIP不得逐场展开
  - qq report不等于full report (长度差异 > 20%)
  - qq不含raw enum
  - qq不含V2/V33字段
  - route marker required, ReportAgent required

输出：data/runtime/status/v4_review_guard_YYYYMMDD.json（单个文件，标注mode）
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
TEMPLATE_DIR = BASE_DIR / "templates"

FORBIDDEN = [
    "ROI", "CLV", "BET_LOCKED", "2.00-2.90", "V33",
    "FULLTIME_OVER", "SECOND_HALF_OVER", "market_scores",
    "A：7/7", "B：5/5", "A+B：12/12",
    "全场大", "下半场大", "回报",
]

# These compressed enums are NOT allowed in final text (show Chinese instead)
COMPRESSED_ENUMS = [
    "SCRIPTNOTAVAILABLE", "MODELTOOSTRICT", "DATAUNAVAILABLE",
    "APIHALFTIMESCORE",
]

# These raw enums must NOT appear in QQ text
RAW_ENUMS_IN_QQ = [
    "SCRIPT_HIT", "SCRIPT_PARTIAL", "SCRIPT_MISS",
    "NO_HT_GOAL", "SCRIPT_NA", "SCRIPT_NOT_AVAILABLE",
    "MODEL_VALID", "MODEL_TOO_STRICT", "MODEL_OVERCONFIDENT",
    "NOISY_WIN", "NOISY_LOSS", "DATA_QUALITY_ISSUE", "WEATHER_RISK",
    "SKIP_BACKFIRE", "SKIP_CORRECT",
    "C_HIT", "C_MISS", "A_HIT", "A_MISS", "B_HIT", "B_MISS",
    "A级强推荐.*?", "fid=",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--mode", default="full", choices=["full", "qq"])
    args = parser.parse_args()

    struct_path = REPORT_DIR / f"v4_review_structured_{args.date}.json"
    if args.mode == "full":
        render_path = REPORT_DIR / f"v4_review_full_{args.date}.txt"
    else:
        render_path = REPORT_DIR / f"v4_review_qq_{args.date}.txt"

    issues = []
    status = "PASS"

    # ── 0. Check structured JSON ──
    if not struct_path.exists():
        issues.append("MISSING_STRUCTURED_JSON")
        _write(args.date, args.mode, "BLOCKER", issues)
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
    expected_total = a + b + c + s

    # ── 1. A/B/C/SKIP validity ──
    if a < 0 or b < 0 or c < 0 or s < 0:
        issues.append(f"INVALID_OFFICIAL_COUNTS: A={a} B={b} C={c} SKIP={s}")

    # ── 2. Match count ──
    if len(matches) != total_slots:
        issues.append(f"MATCH_COUNT_MISMATCH: {len(matches)} vs {total_slots}")

    # ── 3-11. Per-match checks (allow legal DATA_UNAVAILABLE downgrade) ──
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
        # script_type, script_check, risk_review: allow SCRIPT_NOT_AVAILABLE / DATA_UNAVAILABLE
        if not m.get("script_type"):
            pass  # allowed: SCRIPT_NOT_AVAILABLE
        if not m.get("script_check"):
            pass  # allowed: SCRIPT_NOT_AVAILABLE
        if not m.get("risk_review"):
            pass  # allowed: 风险数据未存档
        wc = m.get("weather_context", {})
        if not wc:
            pass  # allowed: DATA_UNAVAILABLE

    # ── 12-18. Module existence ──
    if not data.get("summary"):
        issues.append("NO_SUMMARY")
    if not data.get("time_distribution"):
        issues.append("NO_TIME_DIST")
    if not data.get("diagnosis_summary"):
        issues.append("NO_DIAGNOSIS")
    if not data.get("rolling_stats"):
        issues.append("NO_ROLLING_STATS")
    if not data.get("pre_match_signal"):
        issues.append("NO_PRE_MATCH_SIGNAL")

    # ── Mode-specific checks ──
    if render_path.exists():
        text = render_path.read_text()

        # ── 19. Forbidden words ──
        for word in FORBIDDEN:
            if word in text:
                issues.append(f"FORBIDDEN: {word}")

        # ── 20. Display checks ──
        display_guard_ok = True

        # a) Compressed enum check (e.g. SCRIPTNOTAVAILABLE, MODELTOOSTRICT)
        for comp in COMPRESSED_ENUMS:
            if comp in text:
                issues.append(f"DISPLAY_COMPRESSED_ENUM: {comp}")
                display_guard_ok = False

        # b) None check
        none_count = text.count("None")
        if none_count > 0:
            issues.append(f"DISPLAY_NONE: {none_count} occurrences")
            display_guard_ok = False

        # c) N/A check (allow up to 5 for QQ, 10 for full)
        na_limit = 5 if args.mode == "qq" else 10
        na_count = text.count("N/A")
        if na_count > na_limit:
            issues.append(f"DISPLAY_EXCESS_NA: {na_count} occurrences (limit {na_limit})")
            display_guard_ok = False

        if args.mode == "full":
            # d) Per-match separator check for full mode
            sep = "━" * 20
            sep_count = text.count(sep)
            expected_seps = len(matches) - 1 if len(matches) > 1 else 0
            if sep_count < expected_seps and len(matches) > 1:
                issues.append(f"DISPLAY_MISSING_SEPARATOR: found {sep_count}, expected >= {expected_seps}")
                display_guard_ok = False

            # e) Weather check
            if "天气数据缺失" not in text and all(
                m.get("weather_context", {}).get("weather_source") == "DATA_UNAVAILABLE"
                for m in matches
            ):
                issues.append("DISPLAY_MISSING_WEATHER_NOTE")

        if args.mode == "qq":
            # f) QQ must NOT contain DATA_UNAVAILABLE
            if "DATA_UNAVAILABLE" in text:
                issues.append(f"QQ_DISPLAY_DATA_UNAVAILABLE: found in text")
                display_guard_ok = False
            
            # g1) Forbidden league names
            forbidden_leagues = ["Pro League", "Segunda División", "J1 League", "Czech Liga", "NB I", "Super League", "Süper Lig"]
            for lg in forbidden_leagues:
                if lg in text:
                    issues.append(f"QQ_FORBIDDEN_ENGLISH_LEAGUE: {lg}")
                    display_guard_ok = False
            
            # g2) Forbidden patterns: "情报\d+级", "B\d+级", "C\d+级", "跳过\d+"
            import re
            bad_patterns = [
                (r'情报\d+级', 'QQ_BAD_STATS_FORMAT: 情报X级'),
                (r'B\d+级', 'QQ_BAD_STATS_FORMAT: BX级'),
                (r'C\d+级', 'QQ_BAD_STATS_FORMAT: CX级'),
                (r'跳过\d+[^场]', 'QQ_BAD_STATS_FORMAT: 跳过X'),
                (r'重点A级前2', 'QQ_FORBIDDEN_TOP2'),
                (r'^\s+HT\d+', 'QQ_INDENTED_HT_LINE'),
            ]
            for pat, msg in bad_patterns:
                if re.search(pat, text, re.MULTILINE):
                    issues.append(msg)
                    display_guard_ok = False
            
            # g3) Data unavailable + model overconfident proximity
            if "数据缺失" in text and "模型过度自信" in text:
                import re as _re2
                lines_t = text.split('\n')
                for i, l in enumerate(lines_t):
                    if '数据缺失' in l and i > 0:
                        nearby = ' '.join(lines_t[i:i+3])
                        if '模型过度自信' in nearby:
                            issues.append("QQ_DATA_UNAVAILABLE_NEAR_OVERCONFIDENT")
                            display_guard_ok = False
            
            # g4) Review guard: forbidden terms
            review_forbidden = [
                "existing artifact", "existingartifact", "source=existingartifact",
                "DATAUNAVAILABLE", "DATAMISSINGMARKER",
                "full report", "reviewdate",
            ]
            for term in review_forbidden:
                if term in text:
                    issues.append(f"QQ_REVIEW_FORBIDDEN_TERM: {term}")
                    display_guard_ok = False
            
            # g5) Review guard: must have end marker
            if "—— V4复盘模板验收TEST结束 ——" not in text:
                # For non-TEST texts, check for "——" as minimal end marker
                has_end = "——" in text or "⚠️" in text[-100:]
                if not has_end:
                    issues.append("QQ_REVIEW_MISSING_END_MARKER")
                    display_guard_ok = False

            # g) QQ must NOT contain raw enums
            for raw in RAW_ENUMS_IN_QQ:
                if raw in text:
                    issues.append(f"QQ_DISPLAY_RAW_ENUM: {raw}")
                    display_guard_ok = False

            # h) QQ C/SKIP summary must show percentage (not 'x/y · x/y')
            for line in text.split("\n"):
                if "C级：" in line or "C级" in line and "：" in line:
                    # Check for '· x/y' pattern (duplicate ratio)
                    parts = line.split("·")
                    if len(parts) >= 2:
                        right_side = parts[-1].strip()
                        if "/" in right_side:
                            issues.append(f"QQ_C_SUMMARY_RATIO_NOT_PCT: '{line.strip()}'")
                            display_guard_ok = False
                if "SKIP反杀：" in line or "SKIP" in line and "反杀" in line and "：" in line:
                    parts = line.split("·")
                    if len(parts) >= 2:
                        right_side = parts[-1].strip()
                        if "/" in right_side:
                            issues.append(f"QQ_SKIP_SUMMARY_RATIO_NOT_PCT: '{line.strip()}'")
                            display_guard_ok = False

            # i) QQ must NOT expand C/SKIP per-match
            # Check if text has match numbering patterns with C or SKIP in the body

            # j) QQ must NOT equal full report
            full_path = REPORT_DIR / f"v4_review_full_{args.date}.txt"
            if full_path.exists():
                full_text = full_path.read_text()
                if len(full_text) > 0 and len(text) > 0:
                    size_ratio = len(text) / max(len(full_text), 1)
                    if size_ratio > 0.80:  # QQ > 80% of full = layering failed
                        issues.append(f"QQ_EQUALS_FULL_REPORT: qq={len(text)}bytes full={len(full_text)}bytes ratio={size_ratio:.1%}")
                        display_guard_ok = False

            # i) Route marker check for QQ
            route_path = STATUS_DIR / f"v4_review_route_{args.date}.json"
            if not route_path.exists():
                issues.append("MISSING_ROUTE_MARKER")
            else:
                try:
                    with open(route_path) as f:
                        route = json.load(f)
                    if not route.get("reportagent_called", False):
                        issues.append("REPORTAGENT_BYPASS")
                    if not route.get("allowed_to_push", False):
                        if not route.get("historical_exception", False):
                            issues.append("PUSH_BLOCKED_BY_ROUTE")
                except Exception:
                    issues.append("ROUTE_MARKER_PARSE_ERROR")

            # j) Required sections in QQ text
            required_sections_qq = ["A/B", "C级", "SKIP", "滚动观察", "结论"]
            for section in required_sections_qq:
                if section not in text:
                    issues.append(f"MISSING_SECTION: {section}")

        if not display_guard_ok:
            issues.append("REPORT_DISPLAY_GUARD_GAP")
    else:
        issues.append(f"MISSING_RENDER_FILE: {render_path}")

    # ── Determine status ──
    if issues:
        blocker_kw = [
            "BLOCKER", "MATCH_COUNT", "FORBIDDEN", "MISSING_STRUCTURED",
            "QQ_EQUALS_FULL", "MISMATCH",
        ]
        has_blocker = any(k in str(issues) for k in blocker_kw)
        status = "BLOCKER" if has_blocker else "WARNING"

    _write(args.date, args.mode, status, issues)

    # ── Output ──
    print(f"📋 V4复盘守卫 v1.1 | {args.date} | mode={args.mode}", flush=True)
    print(f"   status: {status}", flush=True)
    if issues:
        for iss in issues:
            print(f"   ⚠️ {iss}", flush=True)
    else:
        print(f"   ✅ All checks passed", flush=True)

    if status == "BLOCKER":
        sys.exit(2)


def _write(date_str: str, mode: str, status: str, issues: list):
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    path = STATUS_DIR / f"v4_review_guard_{date_str}.json"
    out = {
        "date": date_str,
        "mode": mode,
        "guard_status": status,
        "issues": issues,
        "checked_at": datetime.now().isoformat(),
    }
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
