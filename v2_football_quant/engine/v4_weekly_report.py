"""
V4 weekly report
================

Aggregates existing V4 daily validation files.

Reads:
  data/daily_reports/v4_ht_recommend_validation_YYYYMMDD.json

Writes:
  data/weekly_reports/v4_weekly_report_START_END.txt
  data/weekly_reports/v4_weekly_report_START_END.json

Usage:
  python3 engine/v4_weekly_report.py --start 20260513 --end 20260519
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DAILY_DIR = BASE_DIR / "data" / "daily_reports"
WEEKLY_DIR = BASE_DIR / "data" / "weekly_reports"
ATTRIB_DIR = BASE_DIR / "data" / "v4_archive"
VALIDATION_DIR = BASE_DIR / "data" / "runtime" / "validation"
TREND_DIR = BASE_DIR / "data" / "runtime" / "league_watchlist_trends"


def _date_key(s: str) -> str:
    return str(s).replace("-", "")


def _date_range(start: str, end: str) -> list[str]:
    a = datetime.strptime(_date_key(start), "%Y%m%d").date()
    b = datetime.strptime(_date_key(end), "%Y%m%d").date()
    out = []
    while a <= b:
        out.append(a.strftime("%Y%m%d"))
        a += timedelta(days=1)
    return out


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        rows.append(obj)
                except Exception:
                    continue
    except Exception:
        return []
    return rows


def _pct(n: int, d: int) -> float:
    return round(n / d * 100, 1) if d else 0.0


def _load_league_observation(start: str, end: str) -> dict[str, Any]:
    key = f"{_date_key(start)}_{_date_key(end)}"
    watchlist = _load_json(WEEKLY_DIR / f"v4_league_watchlist_report_{key}.json", {})
    ledger = _load_json(VALIDATION_DIR / "v4_league_performance_ledger_latest.json", {})
    if watchlist:
        return {
            "status": "OK",
            "source": str(WEEKLY_DIR / f"v4_league_watchlist_report_{key}.json"),
            "trend_anchor_date": watchlist.get("trend_anchor_date") or "DATA_MISSING",
            "keep_count": len(watchlist.get("keep_leagues") or []),
            "watch_count": len(watchlist.get("watch_leagues") or []),
            "low_trust_alert_count": len(watchlist.get("low_trust_alert_leagues") or []),
            "low_sample_count": len(watchlist.get("low_sample_leagues") or []),
            "do_not_conclude_count": len(watchlist.get("do_not_conclude_leagues") or []),
            "pending_only_count": len(watchlist.get("pending_only_leagues") or []),
            "policy_note": "联赛标签仅供观察，不自动影响 official grade。",
        }
    if ledger:
        return {
            "status": "OK",
            "source": str(VALIDATION_DIR / "v4_league_performance_ledger_latest.json"),
            "trend_anchor_date": ledger.get("trend_anchor_date") or "DATA_MISSING",
            "keep_count": int(ledger.get("keep_count") or 0),
            "watch_count": int(ledger.get("watch_count") or 0),
            "low_trust_alert_count": int(ledger.get("low_trust_count") or 0),
            "low_sample_count": int(ledger.get("low_sample_count") or 0),
            "do_not_conclude_count": int(ledger.get("do_not_conclude_count") or 0),
            "pending_only_count": int(ledger.get("pending_only_count") or 0),
            "policy_note": "联赛标签仅供观察，不自动影响 official grade。",
        }
    return {
        "status": "WARN_ONLY",
        "source": "DATA_MISSING",
        "trend_anchor_date": "DATA_MISSING",
        "keep_count": 0,
        "watch_count": 0,
        "low_trust_alert_count": 0,
        "low_sample_count": 0,
        "do_not_conclude_count": 0,
        "pending_only_count": 0,
        "policy_note": "联赛长期观察层缺失，不阻断周报主流程。",
    }


def _load_league_watchlist_trend() -> dict[str, Any]:
    trend = _load_json(TREND_DIR / "v4_league_watchlist_trend_latest.json", {})
    if not trend:
        return {
            "status": "WARN_ONLY",
            "baseline_only": True,
            "baseline_only_reason": "趋势报告缺失，无法判断变化。",
            "tag_worsened_count": 0,
            "tag_improved_count": 0,
            "new_low_trust_alert_count": 0,
            "pending_to_validated_count": 0,
            "sample_count_delta_top": [],
            "policy_note": "趋势仅供观察，不自动影响 official grade。",
        }
    risk = trend.get("risk_summary") or {}
    return {
        "status": "OK",
        "baseline_only": bool(trend.get("baseline_only")),
        "baseline_only_reason": trend.get("baseline_only_reason") or "",
        "tag_worsened_count": int(risk.get("tag_worsened_count") or 0),
        "tag_improved_count": int(risk.get("tag_improved_count") or 0),
        "new_low_trust_alert_count": int(risk.get("new_low_trust_alert_count") or 0),
        "pending_to_validated_count": int(risk.get("pending_to_validated_count") or 0),
        "sample_count_delta_top": trend.get("sample_count_delta_top") or [],
        "policy_note": "趋势仅供观察，不自动影响 official grade。",
    }


def _grade_accumulator() -> dict[str, int]:
    return {"total": 0, "completed": 0, "pending": 0, "hit": 0, "bucket_hit": 0, "goal_hits": 0}


def aggregate(start: str, end: str) -> dict[str, Any]:
    days = _date_range(start, end)
    grades = defaultdict(_grade_accumulator)
    grade_counts = Counter()
    league = defaultdict(lambda: {"ab_completed": 0, "ab_hit": 0, "skip_completed": 0, "skip_hit": 0})
    dates_loaded = []
    rule_versions = Counter()

    total_matches = 0
    total_pending = 0
    diagnosis_counts = Counter()
    model_result_counts = Counter()
    root_cause_counts = Counter()
    time_bin_source_stats = defaultdict(lambda: {"total": 0, "hit": 0})
    script_type_stats = defaultdict(lambda: {"total": 0, "hit": 0})
    ab_raw_total = 0
    ab_raw_hit = 0
    ab_denoised_total = 0
    ab_denoised_hit = 0
    noisy_labels = {"NOISY_WIN", "NOISY_LOSS"}

    for key in days:
        path = DAILY_DIR / f"v4_ht_recommend_validation_{key}.json"
        val = _load_json(path, {})
        if not val:
            continue
        dates_loaded.append(key)
        rule_versions[str(val.get("rule_version") or "-")] += 1
        total_matches += int(val.get("total_matches") or 0)
        total_pending += int(val.get("pending_matches") or 0)
        for g, n in (val.get("grade_counts") or {}).items():
            grade_counts[g] += int(n or 0)
        for g in ("A", "B", "C", "SKIP"):
            m = (val.get("per_grade") or {}).get(g) or {}
            grades[g]["total"] += int(m.get("total") or 0)
            grades[g]["completed"] += int(m.get("completed") or 0)
            grades[g]["pending"] += int(m.get("pending") or 0)
            grades[g]["hit"] += int(m.get("hit") or 0)
            grades[g]["bucket_hit"] += int(m.get("bucket_hit") or 0)
            grades[g]["goal_hits"] += int(m.get("hit") or 0)

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

        attrib_rows = _load_jsonl(ATTRIB_DIR / f"v4_result_attribution_{key}.jsonl")
        for row in attrib_rows:
            diagnosis = str(row.get("diagnosis") or "UNKNOWN")
            model_result = str(row.get("model_result") or "UNKNOWN")
            pre_grade = str(row.get("pre_grade") or "").upper()
            ht_goal = bool(row.get("ht_goal"))
            diagnosis_counts[diagnosis] += 1
            model_result_counts[model_result] += 1
            root = str(row.get("root_cause_dimension") or "").strip()
            if not root:
                if diagnosis == "DATA_QUALITY_ISSUE":
                    root = "DATA_QUALITY"
                elif diagnosis in ("NOISY_WIN", "NOISY_LOSS"):
                    root = "EVENT_NOISE"
                elif diagnosis == "MODEL_OVERCONFIDENT":
                    root = "MODEL_FEATURE"
                elif diagnosis == "MODEL_TOO_STRICT":
                    root = "MODEL_FEATURE"
                else:
                    root = "NORMAL_VARIANCE"
            root_cause_counts[root] += 1
            source = str(row.get("time_bin_source") or "NONE")
            script = str(row.get("script_type") or "UNKNOWN")
            time_bin_source_stats[source]["total"] += 1
            script_type_stats[script]["total"] += 1
            if ht_goal:
                time_bin_source_stats[source]["hit"] += 1
                script_type_stats[script]["hit"] += 1
            if pre_grade in ("A", "B", "C"):
                ab_raw_total += 1
                if ht_goal:
                    ab_raw_hit += 1
                if diagnosis not in noisy_labels:
                    ab_denoised_total += 1
                    if ht_goal:
                        ab_denoised_hit += 1

    per_grade = {}
    for g in ("A", "B", "C", "SKIP"):
        m = grades[g]
        per_grade[g] = {
            **m,
            "hit_rate_pct": _pct(m["hit"], m["completed"]),
            "bucket_hit_rate_all_pct": _pct(m["bucket_hit"], m["completed"]),
            "bucket_hit_rate_when_goal_pct": _pct(m["bucket_hit"], m["goal_hits"]),
        }

    rates = [per_grade[g]["hit_rate_pct"] for g in ("A", "B", "C", "SKIP")]
    monotonic = all(rates[i] >= rates[i + 1] for i in range(len(rates) - 1))

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

    ab_total = grade_counts["A"] + grade_counts["B"]
    ab_ratio = _pct(ab_total, total_matches)

    time_source_rows = []
    for k, v in time_bin_source_stats.items():
        time_source_rows.append(
            {
                "time_bin_source": k,
                "samples": v["total"],
                "hit": v["hit"],
                "hit_rate_pct": _pct(v["hit"], v["total"]),
            }
        )
    time_source_rows.sort(key=lambda x: (-x["samples"], x["time_bin_source"]))

    script_rows = []
    for k, v in script_type_stats.items():
        script_rows.append(
            {
                "script_type": k,
                "samples": v["total"],
                "hit": v["hit"],
                "hit_rate_pct": _pct(v["hit"], v["total"]),
            }
        )
    script_rows.sort(key=lambda x: (-x["samples"], x["script_type"]))
    league_observation = _load_league_observation(start, end)
    league_trend_observation = _load_league_watchlist_trend()

    return {
        "start": _date_key(start),
        "end": _date_key(end),
        "dates_loaded": dates_loaded,
        "rule_versions": dict(rule_versions),
        "total_matches": total_matches,
        "pending_matches": total_pending,
        "grade_counts": dict(grade_counts),
        "per_grade": per_grade,
        "monotonicity": {"status": "PASS" if monotonic else "FAIL", "rates": rates},
        "coverage_monitor": {"ab_ratio_pct": ab_ratio, "target_min_pct": 5.0, "target_max_pct": 15.0},
        "league_calibration": league_rows,
        "attribution": {
            "model_result_counts": dict(model_result_counts),
            "diagnosis_counts": dict(diagnosis_counts),
            "root_cause_counts": dict(root_cause_counts),
            "ab_raw_hit_rate_pct": _pct(ab_raw_hit, ab_raw_total),
            "ab_denoised_hit_rate_pct": _pct(ab_denoised_hit, ab_denoised_total),
            "time_bin_source_performance": time_source_rows,
            "script_type_performance": script_rows,
        },
        "league_ledger_observation": league_observation,
        "league_watchlist_trend_observation": league_trend_observation,
    }


def render(report: dict[str, Any]) -> str:
    gc = report["grade_counts"]
    per = report["per_grade"]
    cov = report["coverage_monitor"]
    attr = report.get("attribution") or {}
    dcnt = attr.get("diagnosis_counts") or {}
    rcnt = attr.get("root_cause_counts") or {}
    lines = [
        "📊 V4_HT 周度验证报告",
        f"周期：{report['start']} ~ {report['end']}",
        f"规则版本：{', '.join(report['rule_versions'].keys()) or '-'}",
        "",
        "一、推荐概览",
        "",
        "指标                         数值",
        f"🌎 全量比赛                    {report['total_matches']} 场",
        f"🔥 A级推荐                     {gc.get('A', 0)} 场",
        f"🟢 B级推荐                     {gc.get('B', 0)} 场",
        f"👁️ C级观察                     {gc.get('C', 0)} 场",
        f"⚪ HT_SKIP                     {gc.get('SKIP', 0)} 场",
        f"📊 A+B覆盖率                   {cov['ab_ratio_pct']}%",
        "",
        "二、分级命中",
        "",
        "等级        场次    完赛    命中    命中率",
    ]
    for g, label in [("A", "A级"), ("B", "B级"), ("C", "C级"), ("SKIP", "SKIP")]:
        m = per[g]
        lines.append(f"{label:<10} {m['total']:<7} {m['completed']:<7} {m['hit']:<7} {m['hit_rate_pct']}%")
    lines += [
        "",
        f"分级单调性：{report['monotonicity']['status']}",
        "",
        "三、时间段命中",
        "",
        f"A级有球样本内时间段命中率：{per['A']['bucket_hit_rate_when_goal_pct']}%",
        f"B级有球样本内时间段命中率：{per['B']['bucket_hit_rate_when_goal_pct']}%",
        "",
        "四、联赛表现 Top / Bottom",
        "",
    ]
    for item in report["league_calibration"][:10]:
        lines.append(
            f"- {item['league']}：A+B完赛{item['ab_completed']}，命中率{item['ab_hit_rate_pct']}%，"
            f"SKIP反杀{item['skip_hit_rate_pct']}%，状态{item['status']}"
        )
    lines += [
        "",
        "五、赛后归因",
        "",
        "标签                  场次",
        f"MODEL_VALID_STRONG    {dcnt.get('MODEL_VALID_STRONG', 0)}",
        f"MODEL_VALID           {dcnt.get('MODEL_VALID', 0)}",
        f"UNLUCKY_MISS          {dcnt.get('UNLUCKY_MISS', 0)}",
        f"LUCKY_HIT             {dcnt.get('LUCKY_HIT', 0)}",
        f"MODEL_OVERCONFIDENT   {dcnt.get('MODEL_OVERCONFIDENT', 0)}",
        f"MODEL_TOO_STRICT      {dcnt.get('MODEL_TOO_STRICT', 0)}",
        f"NOISY_WIN             {dcnt.get('NOISY_WIN', 0)}",
        f"NOISY_LOSS            {dcnt.get('NOISY_LOSS', 0)}",
        f"DATA_QUALITY_ISSUE    {dcnt.get('DATA_QUALITY_ISSUE', 0)}",
        "",
        f"A/B/C 原始命中率：{attr.get('ab_raw_hit_rate_pct', 0.0)}%",
        f"A/B/C 去噪命中率：{attr.get('ab_denoised_hit_rate_pct', 0.0)}%",
        "",
        "time_bin_source 表现（Top 6）：",
    ]
    for item in (attr.get("time_bin_source_performance") or [])[:6]:
        lines.append(f"- {item['time_bin_source']}：样本{item['samples']}，命中{item['hit']}，{item['hit_rate_pct']}%")
    lines += [
        "",
        "script_type 表现（Top 6）：",
    ]
    for item in (attr.get("script_type_performance") or [])[:6]:
        lines.append(f"- {item['script_type']}：样本{item['samples']}，命中{item['hit']}，{item['hit_rate_pct']}%")
    lines += [
        "",
        "六、Root Cause 分布",
        "",
    ]
    for k in ["MODEL_FEATURE", "TIME_DISTRIBUTION", "MATCH_FLOW", "MARKET_SIGNAL", "EVENT_NOISE", "CONTEXT_NOISE", "WEATHER_NOISE", "LINEUP_CHANGE", "MOTIVATION_MISREAD", "DATA_QUALITY", "NORMAL_VARIANCE"]:
        lines.append(f"- {k}: {rcnt.get(k, 0)}")
    obs = report.get("league_ledger_observation") or {}
    trend = report.get("league_watchlist_trend_observation") or {}
    lines += [
        "",
        "七、本周结论",
        "如果分级单调性 PASS 且 A+B 覆盖率在 5%-15%，当前规则继续运行；否则进入月度校准候选。",
        "",
        "八、联赛长期观察（League Ledger）",
        f"- 状态：{obs.get('status', 'WARN_ONLY')}",
        f"- 来源：{obs.get('source', 'DATA_MISSING')}",
        f"- trend_anchor_date：{obs.get('trend_anchor_date', 'DATA_MISSING')}",
        f"- KEEP：{obs.get('keep_count', 0)}",
        f"- WATCH：{obs.get('watch_count', 0)}",
        f"- LOW_TRUST_ALERT：{obs.get('low_trust_alert_count', 0)}",
        f"- LOW_SAMPLE：{obs.get('low_sample_count', 0)}",
        f"- DO_NOT_CONCLUDE：{obs.get('do_not_conclude_count', 0)}",
        f"- PENDING_ONLY：{obs.get('pending_only_count', 0)}",
        f"- 说明：{obs.get('policy_note', '联赛标签仅供观察，不自动影响 official grade。')}",
        "",
        "九、联赛 Watchlist 趋势变化",
        f"- 状态：{trend.get('status', 'WARN_ONLY')}",
    ]
    if trend.get("baseline_only"):
        lines.append(f"- {trend.get('baseline_only_reason', '当前仅有 baseline 快照，不能判断趋势。')}")
    else:
        lines.extend(
            [
                f"- 标签恶化：{trend.get('tag_worsened_count', 0)}",
                f"- 标签改善：{trend.get('tag_improved_count', 0)}",
                f"- 新增 LOW_TRUST_ALERT：{trend.get('new_low_trust_alert_count', 0)}",
                f"- pending 转 validated：{trend.get('pending_to_validated_count', 0)}",
            ]
        )
        top = trend.get("sample_count_delta_top") or []
        if top:
            lines.append(f"- 样本增长最多：{top[0].get('league')} (Δvalidated={top[0].get('delta_validated_count')})")
    lines += [
        f"- 说明：{trend.get('policy_note', '趋势仅供观察，不自动影响 official grade。')}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()
    report = aggregate(args.start, args.end)
    text = render(report)
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    key = f"{_date_key(args.start)}_{_date_key(args.end)}"
    (WEEKLY_DIR / f"v4_weekly_report_{key}.txt").write_text(text, encoding="utf-8")
    (WEEKLY_DIR / f"v4_weekly_report_{key}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
