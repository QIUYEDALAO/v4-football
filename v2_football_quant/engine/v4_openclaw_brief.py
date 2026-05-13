"""
V4 OpenClaw brief
=================

Daily push-style V4 HT recommendation brief.

Reads:
  data/daily_reports/scout_v4_YYYYMMDD.json
  previous day's v4_ht_recommend_validation_YYYYMMDD.json if available

Writes:
  data/daily_reports/v4_openclaw_brief_YYYYMMDD.txt

Usage:
  python3 engine/v4_openclaw_brief.py --date 20260514
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine.v4_match_intelligence import explain_match

REPORT_DIR = BASE_DIR / "data" / "daily_reports"


def _date_key(date_str: str) -> str:
    return str(date_str).replace("-", "")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _pct(v: Any) -> str:
    try:
        return f"{float(v) * 100:.0f}%"
    except Exception:
        return "-"


def _pct_value(numer: int, denom: int) -> str:
    return f"{(numer / denom * 100):.1f}%" if denom else "0.0%"


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _prev_key(key: str) -> str:
    try:
        d = datetime.strptime(key, "%Y%m%d").date()
        return (d - timedelta(days=1)).strftime("%Y%m%d")
    except Exception:
        return key


def _row_time(rec: dict[str, Any]) -> str:
    kickoff = str(rec.get("kickoff") or rec.get("date") or "")
    if not kickoff:
        return "-"
    try:
        dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
        return dt.strftime("%m-%d %H:%M")
    except Exception:
        return kickoff[-16:-3] if len(kickoff) >= 16 else kickoff


def _collect_rows(scout: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rec in scout:
        intel = explain_match(rec)
        ht_rec = intel.get("ht_recommendation") or {}
        f = rec.get("factors", {}) or {}
        scores = rec.get("market_scores") or f.get("market_scores") or {}
        grade = str(ht_rec.get("grade") or "SKIP").upper()
        tb = ht_rec.get("time_bins") or {}
        rows.append(
            {
                "fixture_id": rec.get("fixture_id"),
                "home": rec.get("home") or "-",
                "away": rec.get("away") or "-",
                "league": rec.get("league") or "-",
                "time": _row_time(rec),
                "grade": grade,
                "ht_score": _float(ht_rec.get("ht_score") or scores.get("HT_LIVE_OVER")),
                "h2h_rate": _float(ht_rec.get("h2h_ht_goal_rate") or f.get("h2h_ht_goal_rate")),
                "avg_goals": _float(ht_rec.get("ht_avg_goals") or f.get("h2h_avg_ht_goals")),
                "sample_size": int(_float(ht_rec.get("sample_size") or f.get("h2h_sample_size"))),
                "script_type": ht_rec.get("script_type") or "-",
                "time_bins": {
                    "0_15": _float(tb.get("0_15")),
                    "16_30": _float(tb.get("16_30")),
                    "31_45": _float(tb.get("31_45")),
                },
                "reasons": ht_rec.get("reasons") or [],
                "risks": ht_rec.get("risks") or [],
                "risk_top": ht_rec.get("risk_top") or "",
                "status": ht_rec.get("status") or intel.get("execution_status") or "-",
            }
        )
    rows.sort(key=lambda x: (x["time"], x["league"], x["home"]))
    return rows


def _skip_reason_key(reason: str) -> str:
    s = str(reason)
    if "HT有球率" in s or "有球率" in s:
        return "HT有球率不足"
    if "场均" in s or "进球" in s:
        return "上半场场均进球不足"
    if "11-45" in s or "压力" in s:
        return "11-45分钟压力不足"
    if "样本" in s:
        return "样本不足"
    if "方向" in s or "下半场" in s:
        return "方向更偏下半场"
    if "early_only" in s or "早球" in s:
        return "早球型风险"
    if "pullback" in s or "回调" in s:
        return "回调适配偏弱"
    return s[:24] if s else "其他"


def _format_main_row(idx: int, r: dict[str, Any]) -> list[str]:
    tb = r["time_bins"]
    reasons = " / ".join(r["reasons"][:3]) if r["reasons"] else "-"
    risks = " / ".join(r["risks"][:2]) if r["risks"] else "无明显高优先级风险"
    grade_label = "A级 · 上半场强推荐" if r["grade"] == "A" else "B级 · 上半场达标推荐"
    return [
        f"{idx}. {r['home']} vs {r['away']}",
        f"   {r['league']} · {r['time']} · #{r['fixture_id']}",
        f"   等级：{grade_label}",
        f"   HT评分 {r['ht_score']:.0f} | HT有球率 {_pct(r['h2h_rate'])} | 场均HT进球 {r['avg_goals']:.2f} | 样本 {r['sample_size']}",
        f"   剧本：{r['script_type']}",
        f"   分布：0-15m {_pct(tb['0_15'])} | 16-30m {_pct(tb['16_30'])} | 31-45m {_pct(tb['31_45'])}",
        f"   主因：{reasons}",
        f"   风险：{risks}",
        "   建议：今日上半场重点盯盘，具体入场时间由你人工判断。",
        "",
    ]


def _format_c_row(idx: int, r: dict[str, Any]) -> str:
    return (
        f"{idx}. {r['home']} vs {r['away']} — {r['league']} · {r['time']} | "
        f"HT评分{r['ht_score']:.0f} | HT有球率{_pct(r['h2h_rate'])} | {r['script_type']}"
    )


def _validation_lines(key: str) -> list[str]:
    prev = _prev_key(key)
    path = REPORT_DIR / f"v4_ht_recommend_validation_{prev}.json"
    val = _load_json(path, {})
    if not val:
        return ["📌 昨日V4验证", f"未找到昨日验证文件：{path.name}", ""]
    per = val.get("per_grade") or {}
    funnel = val.get("funnel") or {}
    bucket = val.get("bucket_quality") or {}
    lines = ["📌 昨日V4验证"]
    for g, label in [("A", "A级"), ("B", "B级"), ("C", "C级")]:
        m = per.get(g) or {}
        lines.append(
            f"{label}：{m.get('hit', 0)}/{m.get('completed', 0)} 命中，命中率 {m.get('hit_rate_pct', 0)}%"
        )
    lines.append(f"SKIP反杀率：{funnel.get('skip_backfire_rate_pct', 0)}%")
    lines.append(f"时间段命中率 when_goal：{bucket.get('bucket_hit_rate_when_goal_pct', 0)}%")
    lines.append("")
    return lines


def build_brief(date_str: str) -> str:
    key = _date_key(date_str)
    scout_path = REPORT_DIR / f"scout_v4_{key}.json"
    scout = _load_json(scout_path, [])
    if isinstance(scout, dict):
        scout = scout.get("results") or []
    if not isinstance(scout, list):
        scout = []

    rows = _collect_rows(scout)
    a_rows = [r for r in rows if r["grade"] == "A"]
    b_rows = [r for r in rows if r["grade"] == "B"]
    c_rows = [r for r in rows if r["grade"] == "C"]
    skip_rows = [r for r in rows if r["grade"] == "SKIP"]
    total = len(rows)
    ab_total = len(a_rows) + len(b_rows)
    ab_ratio = _pct_value(ab_total, total)

    skip_counter: Counter[str] = Counter()
    for r in skip_rows:
        reasons = r["reasons"] or r["risks"] or [r["risk_top"] or "其他"]
        for reason in reasons[:2]:
            skip_counter[_skip_reason_key(reason)] += 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = [
        f"⏰ V4 上半场情报扫描 — {key} {now}",
        "",
        "指标                         数值",
        f"🔥 A级强推荐                  {len(a_rows)} 场",
        f"🟢 B级达标推荐                {len(b_rows)} 场",
        f"👁️ C级观察                    {len(c_rows)} 场",
        f"⚪ HT_SKIP跳过                 {len(skip_rows)} 场",
        f"🌎 全量扫描                    {total} 场",
        f"📊 A+B覆盖率                   {ab_ratio}",
        "",
    ]

    lines.append("🔥 A级上半场强推荐")
    if a_rows:
        for i, r in enumerate(a_rows, 1):
            lines.extend(_format_main_row(i, r))
    else:
        lines.append("本次无A级强推荐。")
        lines.append("")

    lines.append("🟢 B级上半场达标推荐")
    if b_rows:
        for i, r in enumerate(b_rows, 1):
            lines.extend(_format_main_row(i, r))
    else:
        lines.append("本次无B级达标推荐。")
        lines.append("")

    lines.append(f"👁️ C级观察池：{len(c_rows)}场")
    if c_rows:
        for i, r in enumerate(c_rows[:20], 1):
            lines.append(_format_c_row(i, r))
        if len(c_rows) > 20:
            lines.append(f"... 另有 {len(c_rows) - 20} 场C级观察未展开")
    else:
        lines.append("本次无C级观察。")
    lines.append("")

    lines.append(f"⚪ 跳过统计：{len(skip_rows)}场")
    if skip_counter:
        for reason, n in skip_counter.most_common(8):
            lines.append(f"- {reason}：{n}场")
    else:
        lines.append("- 暂无跳过原因统计")
    lines.append("说明：HT_SKIP = 本场不进入上半场推荐，不需要你看盘。")
    lines.append("")

    lines.extend(_validation_lines(key))

    lines.append("本次结论：")
    if ab_total:
        lines.append(f"V4 今日有 {ab_total} 场上半场推荐，其中 A级{len(a_rows)}场，B级{len(b_rows)}场。")
    else:
        lines.append("V4 今日无A/B上半场主推荐，仅保留观察与跳过统计。")
    lines.append("HT_SKIP 不展示单场，默认直接跳过。")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD or YYYY-MM-DD")
    args = parser.parse_args()
    key = _date_key(args.date)
    text = build_brief(args.date)
    out_path = REPORT_DIR / f"v4_openclaw_brief_{key}.txt"
    _save_text(out_path, text)
    print(text)
    print(json.dumps({"output_path": str(out_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
