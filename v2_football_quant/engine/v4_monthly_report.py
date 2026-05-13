"""
V4 monthly report
=================

Aggregates daily V4 HT validation files for strategy calibration.

Reads:
  data/daily_reports/v4_ht_recommend_validation_YYYYMMDD.json

Writes:
  data/monthly_reports/v4_monthly_report_YYYYMM.txt
  data/monthly_reports/v4_monthly_report_YYYYMM.json

Usage:
  python3 engine/v4_monthly_report.py --month 202605
"""

from __future__ import annotations

import argparse
import calendar
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DAILY_DIR = BASE_DIR / "data" / "daily_reports"
MONTHLY_DIR = BASE_DIR / "data" / "monthly_reports"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _pct(n: int, d: int) -> float:
    return round(n / d * 100, 1) if d else 0.0


def _month_days(month: str) -> list[str]:
    y = int(month[:4])
    m = int(month[4:6])
    last = calendar.monthrange(y, m)[1]
    return [date(y, m, d).strftime("%Y%m%d") for d in range(1, last + 1)]


def _acc() -> dict[str, int]:
    return {"total": 0, "completed": 0, "hit": 0, "bucket_hit": 0, "goal_hits": 0}


def aggregate(month: str) -> dict[str, Any]:
    days = _month_days(month)
    grades = defaultdict(_acc)
    grade_counts = Counter()
    scripts = defaultdict(_acc)
    league = defaultdict(lambda: {"ab_completed": 0, "ab_hit": 0, "skip_completed": 0, "skip_hit": 0})
    rule_versions = Counter()
    loaded = []
    total_matches = 0

    for key in days:
        val = _load_json(DAILY_DIR / f"v4_ht_recommend_validation_{key}.json", {})
        if not val:
            continue
        loaded.append(key)
        rule_versions[str(val.get("rule_version") or "-")] += 1
        total_matches += int(val.get("total_matches") or 0)
        for g, n in (val.get("grade_counts") or {}).items():
            grade_counts[g] += int(n or 0)

        for detail in val.get("details") or []:
            g = str(detail.get("grade") or "SKIP")
            pending = bool(detail.get("pending"))
            if pending:
                continue
            hit = detail.get("hit") is True
            bucket_hit = detail.get("bucket_hit") is True
            grades[g]["total"] += 1
            grades[g]["completed"] += 1
            if hit:
                grades[g]["hit"] += 1
                grades[g]["goal_hits"] += 1
            if bucket_hit:
                grades[g]["bucket_hit"] += 1
            # Validator details do not currently include script_type; keep hook for future.
            script = str(detail.get("script_type") or "UNKNOWN")
            scripts[script]["total"] += 1
            scripts[script]["completed"] += 1
            if hit:
                scripts[script]["hit"] += 1
                scripts[script]["goal_hits"] += 1
            if bucket_hit:
                scripts[script]["bucket_hit"] += 1

        for item in val.get("league_calibration") or []:
            lg = str(item.get("league") or "-")
            ab_completed = int(item.get("ab_completed") or 0)
            ab_hit = round(ab_completed * float(item.get("ab_hit_rate_pct") or 0) / 100)
            skip_completed = int(item.get("skip_completed") or 0)
            skip_hit = round(skip_completed * float(item.get("skip_hit_rate_pct") or 0) / 100)
            league[lg]["ab_completed"] += ab_completed
            league[lg]["ab_hit"] += ab_hit
            league[lg]["skip_completed"] += skip_completed
            league[lg]["skip_hit"] += skip_hit

    per_grade = {}
    for g in ("A", "B", "C", "SKIP"):
        m = grades[g]
        per_grade[g] = {
            **m,
            "hit_rate_pct": _pct(m["hit"], m["completed"]),
            "bucket_hit_rate_when_goal_pct": _pct(m["bucket_hit"], m["goal_hits"]),
        }

    league_rows = []
    for lg, m in league.items():
        ab_rate = _pct(m["ab_hit"], m["ab_completed"])
        skip_rate = _pct(m["skip_hit"], m["skip_completed"])
        if m["ab_completed"] < 20:
            status = "YELLOW"
        elif ab_rate > skip_rate and ab_rate >= 55:
            status = "GREEN"
        elif ab_rate <= skip_rate:
            status = "RED"
        else:
            status = "YELLOW"
        league_rows.append({"league": lg, **m, "ab_hit_rate_pct": ab_rate, "skip_hit_rate_pct": skip_rate, "status": status})
    league_rows.sort(key=lambda x: (-x["ab_completed"], x["league"]))

    rates = [per_grade[g]["hit_rate_pct"] for g in ("A", "B", "C", "SKIP")]
    monotonic = all(rates[i] >= rates[i + 1] for i in range(len(rates) - 1))
    ab_total = grade_counts["A"] + grade_counts["B"]

    return {
        "month": month,
        "dates_loaded": loaded,
        "rule_versions": dict(rule_versions),
        "total_matches": total_matches,
        "grade_counts": dict(grade_counts),
        "per_grade": per_grade,
        "monotonicity": {"status": "PASS" if monotonic else "FAIL", "rates": rates},
        "coverage_monitor": {"ab_ratio_pct": _pct(ab_total, total_matches), "target_min_pct": 5.0, "target_max_pct": 15.0},
        "league_calibration": league_rows,
    }


def _decision(report: dict[str, Any]) -> list[str]:
    per = report["per_grade"]
    cov = report["coverage_monitor"]["ab_ratio_pct"]
    lines = []
    if report["monotonicity"]["status"] != "PASS":
        lines.append("分级单调性失败：需要回看 A/B/C 阈值。")
    if cov < 5:
        lines.append("A+B覆盖率偏低：规则过严，可考虑降低B级门槛。")
    elif cov > 15:
        lines.append("A+B覆盖率偏高：规则过松，应提高A/B门槛。")
    if per["SKIP"]["hit_rate_pct"] > 35:
        lines.append("SKIP反杀率偏高：跳过规则过严或某些联赛需放宽。")
    red = [x for x in report["league_calibration"] if x["status"] == "RED"]
    if red:
        lines.append("存在RED联赛：建议下月对这些联赛提高阈值或降级观察。")
    if not lines:
        lines.append("当前规则版本可继续使用；下月保持验证。")
    return lines


def render(report: dict[str, Any]) -> str:
    gc = report["grade_counts"]
    per = report["per_grade"]
    cov = report["coverage_monitor"]
    lines = [
        "📈 V4_HT 月度策略校准报告",
        f"周期：{report['month']}",
        f"规则版本：{', '.join(report['rule_versions'].keys()) or '-'}",
        "",
        "一、月度总览",
        "",
        "指标                         数值",
        f"🌎 全量比赛                    {report['total_matches']} 场",
        f"🔥 A级推荐                     {gc.get('A', 0)} 场",
        f"🟢 B级推荐                     {gc.get('B', 0)} 场",
        f"👁️ C级观察                     {gc.get('C', 0)} 场",
        f"⚪ HT_SKIP                     {gc.get('SKIP', 0)} 场",
        f"📊 A+B覆盖率                   {cov['ab_ratio_pct']}%",
        "",
        "二、月度分级验证",
        "",
        "等级        完赛    命中    命中率    时间段命中when_goal",
    ]
    for g, label in [("A", "A级"), ("B", "B级"), ("C", "C级"), ("SKIP", "SKIP")]:
        m = per[g]
        lines.append(f"{label:<10} {m['completed']:<7} {m['hit']:<7} {m['hit_rate_pct']}%      {m['bucket_hit_rate_when_goal_pct']}%")
    lines += [
        "",
        f"分级单调性：{report['monotonicity']['status']}",
        "",
        "三、联赛校准",
        "",
        "联赛        A+B完赛    A+B命中率    SKIP反杀率    状态",
    ]
    for item in report["league_calibration"][:20]:
        lines.append(
            f"{item['league']:<12} {item['ab_completed']:<10} {item['ab_hit_rate_pct']}%        "
            f"{item['skip_hit_rate_pct']}%        {item['status']}"
        )
    lines += [
        "",
        "四、规则调整建议",
    ]
    for x in _decision(report):
        lines.append(f"- {x}")
    lines += [
        "",
        "五、下月策略结论",
        "月报只负责是否改规则；不负责每日看盘。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True, help="YYYYMM")
    args = parser.parse_args()
    report = aggregate(args.month)
    text = render(report)
    MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
    (MONTHLY_DIR / f"v4_monthly_report_{args.month}.txt").write_text(text, encoding="utf-8")
    (MONTHLY_DIR / f"v4_monthly_report_{args.month}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
