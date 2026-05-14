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
ATTRIB_DIR = BASE_DIR / "data" / "v4_archive"


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
    diagnosis_counts = Counter()
    model_result_counts = Counter()
    root_cause_counts = Counter()
    noisy_labels = {"NOISY_WIN", "NOISY_LOSS"}
    ab_raw_total = 0
    ab_raw_hit = 0
    ab_denoised_total = 0
    ab_denoised_hit = 0
    recent_total = 0
    recent_hit = 0
    context_noise_total = 0
    time_source = defaultdict(lambda: {"total": 0, "hit": 0})
    script_type_perf = defaultdict(lambda: {"total": 0, "hit": 0})

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

        attrib_rows = _load_jsonl(ATTRIB_DIR / f"v4_result_attribution_{key}.jsonl")
        for row in attrib_rows:
            diagnosis = str(row.get("diagnosis") or "UNKNOWN")
            model_result = str(row.get("model_result") or "UNKNOWN")
            pre_grade = str(row.get("pre_grade") or "").upper()
            ht_goal = bool(row.get("ht_goal"))
            tbs = str(row.get("time_bin_source") or "NONE")
            stp = str(row.get("script_type") or "UNKNOWN")
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
            time_source[tbs]["total"] += 1
            script_type_perf[stp]["total"] += 1
            if ht_goal:
                time_source[tbs]["hit"] += 1
                script_type_perf[stp]["hit"] += 1
            if row.get("context_noise"):
                context_noise_total += 1
            if tbs == "RECENT_DISCOUNTED":
                recent_total += 1
                if ht_goal:
                    recent_hit += 1
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

    time_source_rows = []
    for k, v in time_source.items():
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
    for k, v in script_type_perf.items():
        script_rows.append(
            {
                "script_type": k,
                "samples": v["total"],
                "hit": v["hit"],
                "hit_rate_pct": _pct(v["hit"], v["total"]),
            }
        )
    script_rows.sort(key=lambda x: (-x["samples"], x["script_type"]))

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
        "attribution": {
            "model_result_counts": dict(model_result_counts),
            "diagnosis_counts": dict(diagnosis_counts),
            "root_cause_counts": dict(root_cause_counts),
            "ab_raw_hit_rate_pct": _pct(ab_raw_hit, ab_raw_total),
            "ab_denoised_hit_rate_pct": _pct(ab_denoised_hit, ab_denoised_total),
            "context_noise_samples": context_noise_total,
            "recent_discounted": {
                "samples": recent_total,
                "hit": recent_hit,
                "hit_rate_pct": _pct(recent_hit, recent_total),
            },
            "time_bin_source_performance": time_source_rows,
            "script_type_performance": script_rows,
        },
    }


def _decision(report: dict[str, Any]) -> list[str]:
    per = report["per_grade"]
    cov = report["coverage_monitor"]["ab_ratio_pct"]
    attr = report.get("attribution") or {}
    dcnt = attr.get("diagnosis_counts") or {}
    rcnt = attr.get("root_cause_counts") or {}
    recent = (attr.get("recent_discounted") or {})
    total_attr = sum(int(v or 0) for v in dcnt.values())
    noisy_cnt = int(dcnt.get("NOISY_WIN", 0)) + int(dcnt.get("NOISY_LOSS", 0))
    noisy_ratio = (noisy_cnt / total_attr * 100.0) if total_attr else 0.0
    lines = []
    if report["monotonicity"]["status"] != "PASS":
        lines.append("分级单调性失败：需要回看 A/B/C 阈值。")
    if cov < 5:
        lines.append("A+B覆盖率偏低：规则过严，可考虑降低B级门槛。")
    elif cov > 15:
        lines.append("A+B覆盖率偏高：规则过松，应提高A/B门槛。")
    if per["SKIP"]["hit_rate_pct"] > 35:
        lines.append("SKIP反杀率偏高：跳过规则过严或某些联赛需放宽。")
    if int(dcnt.get("MODEL_OVERCONFIDENT", 0)) >= int(dcnt.get("MODEL_TOO_STRICT", 0)) + 3:
        lines.append("MODEL_OVERCONFIDENT 偏高：A/B/C 规则可能偏松，建议提高阈值。")
    if int(dcnt.get("MODEL_TOO_STRICT", 0)) >= int(dcnt.get("MODEL_OVERCONFIDENT", 0)) + 3:
        lines.append("MODEL_TOO_STRICT 偏高：SKIP 规则可能偏严，建议放宽 C/B 边界。")
    if noisy_ratio >= 25.0:
        lines.append("NOISY_WIN/NOISY_LOSS 占比高：本月偶然性偏强，先观测，避免过度改规则。")
    if int(recent.get("samples", 0)) >= 10:
        if float(recent.get("hit_rate_pct", 0.0)) >= 60.0:
            lines.append("RECENT_DISCOUNTED 命中率稳定较高：继续保留 recent ×0.75 回填。")
        elif float(recent.get("hit_rate_pct", 0.0)) < 50.0:
            lines.append("RECENT_DISCOUNTED 命中率偏低：建议该来源最高仅到 C，不升 B。")
    if int(rcnt.get("MATCH_FLOW", 0)) >= 5:
        lines.append("MATCH_FLOW 失败偏多：建议增强赛中节奏确认。")
    if int(rcnt.get("TIME_DISTRIBUTION", 0)) >= 5:
        lines.append("TIME_DISTRIBUTION 偏差偏多：建议校准时间分布逻辑。")
    if int(rcnt.get("WEATHER_NOISE", 0)) >= 3:
        lines.append("WEATHER_NOISE 偏多：先继续观测天气样本，不直接改评分。")
    if int(dcnt.get("UNLUCKY_MISS", 0)) >= 5 and int(rcnt.get("MATCH_FLOW", 0)) < 3:
        lines.append("UNLUCKY_MISS 偏多且比赛过程并不差：优先视为正常波动，不急于改规则。")
    if int(dcnt.get("LUCKY_HIT", 0)) >= 5:
        lines.append("LUCKY_HIT 偏多：命中含运气成分，需继续扩样观察。")
    if int(rcnt.get("DATA_QUALITY", 0)) >= 5:
        lines.append("DATA_QUALITY 问题偏多：优先补采与提升覆盖。")
    if int(rcnt.get("LINEUP_CHANGE", 0)) >= 3:
        lines.append("LINEUP_CHANGE 偏多：建议加强首发变动监控与归因采样。")
    if int(rcnt.get("MOTIVATION_MISREAD", 0)) >= 3:
        lines.append("MOTIVATION_MISREAD 偏多：建议复核战意标签与赛季阶段识别。")
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
    attr = report.get("attribution") or {}
    dcnt = attr.get("diagnosis_counts") or {}
    rcnt = attr.get("root_cause_counts") or {}
    recent = attr.get("recent_discounted") or {}
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
        "三、赛后归因",
        "",
        "标签                      场次",
        f"MODEL_VALID_STRONG       {dcnt.get('MODEL_VALID_STRONG', 0)}",
        f"MODEL_VALID               {dcnt.get('MODEL_VALID', 0)}",
        f"UNLUCKY_MISS              {dcnt.get('UNLUCKY_MISS', 0)}",
        f"LUCKY_HIT                 {dcnt.get('LUCKY_HIT', 0)}",
        f"MODEL_OVERCONFIDENT       {dcnt.get('MODEL_OVERCONFIDENT', 0)}",
        f"MODEL_TOO_STRICT          {dcnt.get('MODEL_TOO_STRICT', 0)}",
        f"NOISY_WIN                 {dcnt.get('NOISY_WIN', 0)}",
        f"NOISY_LOSS                {dcnt.get('NOISY_LOSS', 0)}",
        f"DATA_QUALITY_ISSUE        {dcnt.get('DATA_QUALITY_ISSUE', 0)}",
        "",
        f"A/B/C 原始命中率：{attr.get('ab_raw_hit_rate_pct', 0.0)}%",
        f"A/B/C 去噪命中率：{attr.get('ab_denoised_hit_rate_pct', 0.0)}%",
        f"RECENT_DISCOUNTED：样本{recent.get('samples', 0)}，命中{recent.get('hit', 0)}，{recent.get('hit_rate_pct', 0.0)}%",
        f"context_noise 样本数：{attr.get('context_noise_samples', 0)}",
        "",
        "四、time_bin_source 表现（Top 8）",
        "",
    ]
    for item in (attr.get("time_bin_source_performance") or [])[:8]:
        lines.append(f"- {item['time_bin_source']}：样本{item['samples']}，命中{item['hit']}，{item['hit_rate_pct']}%")
    lines += [
        "",
        "五、script_type 表现（Top 8）",
        "",
    ]
    for item in (attr.get("script_type_performance") or [])[:8]:
        lines.append(f"- {item['script_type']}：样本{item['samples']}，命中{item['hit']}，{item['hit_rate_pct']}%")
    lines += [
        "",
        "六、Root Cause 分布",
        "",
    ]
    for k in ["MODEL_FEATURE", "TIME_DISTRIBUTION", "MATCH_FLOW", "MARKET_SIGNAL", "EVENT_NOISE", "CONTEXT_NOISE", "WEATHER_NOISE", "LINEUP_CHANGE", "MOTIVATION_MISREAD", "DATA_QUALITY", "NORMAL_VARIANCE"]:
        lines.append(f"- {k}: {rcnt.get(k, 0)}")
    lines += [
        "",
        "七、联赛校准",
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
        "八、规则调整建议",
    ]
    for x in _decision(report):
        lines.append(f"- {x}")
    lines += [
        "",
        "九、下月策略结论",
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
