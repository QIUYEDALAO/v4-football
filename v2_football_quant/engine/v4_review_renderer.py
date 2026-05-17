#!/usr/bin/env python3
"""engine/v4_review_renderer.py — V4复盘模板渲染器 v1.1

读取 v4_review_structured_YYYYMMDD.json + 模板文件，严格按模板渲染。

mode=full:
  data/daily_reports/v4_review_full_YYYYMMDD.txt — 全部49场逐场展示

mode=qq:
  data/daily_reports/v4_review_qq_YYYYMMDD.txt — A/B摘要+有限高亮，C/SKIP仅汇总

用法:
  python3 engine/v4_review_renderer.py --date 20260516 --mode full
  python3 engine/v4_review_renderer.py --date 20260516 --mode qq
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FULL_TEMPLATE = BASE_DIR / "templates" / "v4_daily_review_full_template.md"
QQ_TEMPLATE = BASE_DIR / "templates" / "v4_daily_review_qq_template.md"
QQ_BRIEF_TEMPLATE = BASE_DIR / "templates" / "v4_daily_review_qq_brief.md"
REPORT_DIR = BASE_DIR / "data" / "daily_reports"


# ── Display label mapping ──
_DIAG_LABELS = {
    "MODEL_VALID": "模型有效",
    "MODEL_TOO_STRICT": "模型过严",
    "MODEL_OVERCONFIDENT": "模型过度自信",
    "NOISY_WIN": "噪音命中",
    "NOISY_LOSS": "噪音失败",
    "DATA_QUALITY_ISSUE": "数据质量问题",
    "CONTEXT_CHANGED": "环境变化",
}

_SOURCE_LABELS = {
    "DATA_UNAVAILABLE": "数据缺失",
    "API_HALFTIME_SCORE": "API半场比分",
    "API_EVENTS": "API事件",
    "API_HALFTIME_SCORE+API_EVENTS": "API半场比分+事件",
    "API_FIXTURES": "API数据",
    "MANUAL_CONFIRMED_BY_BOSS": "BOSS人工确认",
}


def _lbl(v, mapping: dict) -> str:
    if v is None:
        return "数据缺失"
    s = str(v)
    for raw, label in mapping.items():
        if raw in s:
            return label
    return s


def _strip_fid(url_or_num):
    """Return fixture_id as string."""
    s = str(url_or_num)
    if "?" in s:
        for pair in s.split("?"):
            if "id=" in pair:
                return pair.split("id=")[-1].strip()
    if s.startswith("?"):
        return s[1:]
    return s


def _match_row_full(m: dict, idx: int) -> str:
    """Full per-match rendering (used in full report)."""
    home = m.get("home", "?")
    away = m.get("away", "?")
    league = m.get("league", "?")
    fid = _strip_fid(m.get("fixture_id", "?"))
    bucket = m.get("official_bucket", "?")
    ht = m.get("ht_score", "数据缺失")
    ft = m.get("ft_score", "数据缺失")
    goals = m.get("first_half_goal_minutes", [])
    g0 = m.get("goals_0_15", 0)
    g16 = m.get("goals_16_30", 0)
    g31 = m.get("goals_31_45", 0)
    result = m.get("model_result", "数据缺失")
    diag = m.get("diagnosis", "数据缺失")
    ds = m.get("data_source", "数据缺失")
    script_check = m.get("script_check", "SCRIPT_NOT_AVAILABLE")
    risk_review = m.get("risk_review", "风险数据未存档")

    diag_cn = _lbl(diag, _DIAG_LABELS)
    source_cn = _lbl(ds, _SOURCE_LABELS)

    if goals:
        goals_text = "、".join(f"{g}′" for g in goals)
    else:
        goals_text = "无"

    # Clean up script/risk
    if script_check in ("SCRIPT_NOT_AVAILABLE", "False", False, None):
        script_text = "剧本未存档"
    else:
        script_text = str(script_check)

    if not risk_review or risk_review in ("", "False", False, None):
        risk_text = "风险数据未存档"
    else:
        risk_text = str(risk_review)

    separator = "\n" + "━" * 20 + "\n" if idx > 0 else ""
    return (
        f"{separator}"
        f"{idx+1}. {home} vs {away}\n"
        f"{league}｜fid={fid}\n"
        f"官方：{bucket}\n"
        f"赛果：HT {ht}｜FT {ft}\n"
        f"进球：{goals_text}\n"
        f"实际：0-15 {g0}｜16-30 {g16}｜31-45+ {g31}\n"
        f"结果：{diag_cn}\n"
        f"剧本：{script_text}\n"
        f"风险：{risk_text}\n"
        f"来源：{source_cn}"
    )


def _ab_detail_qq(ab_matches: list) -> str:
    """Generate A/B detail section for QQ report.
    - Show unhit/abnormal matches first
    - Show up to 5 representative hits
    - Then '其余A/B已入库，详见full report'
    """
    if not ab_matches:
        return ""

    # Separate hits and misses
    hits = [m for m in ab_matches if "MISS" not in m.get("model_result", "")
            and "OVERCONFIDENT" not in m.get("diagnosis", "")]
    misses = [m for m in ab_matches if "MISS" in m.get("model_result", "")
              or "OVERCONFIDENT" in m.get("diagnosis", "")]

    lines = []
    lines.append("【A/B重点逐场】")

    # First: misses/abnormal
    if misses:
        lines.append("\n--- 未命中 / 异常 ---")
        for i, m in enumerate(misses[:], 1):
            g = "无" if not m.get("first_half_goal_minutes") else "、".join(f"{g}′" for g in m["first_half_goal_minutes"])
            diag = _lbl(m.get("diagnosis", ""), _DIAG_LABELS)
            lines.append(
                f"{i}. {m['home']} vs {m['away']}\n"
                f"   {m['league']} | {m.get('official_bucket','')}级\n"
                f"   HT {m.get('ht_score','数据缺失')} | FT {m.get('ft_score','数据缺失')}\n"
                f"   进球：{g} | 诊断：{diag}"
            )

    # Then: up to 5 representative hits
    representative_hits = hits[:5]
    if representative_hits:
        lines.append("\n--- 代表性命中 ---")
        for i, m in enumerate(representative_hits, 1):
            g = "无" if not m.get("first_half_goal_minutes") else "、".join(f"{g}′" for g in m["first_half_goal_minutes"])
            lines.append(
                f"{i}. {m['home']} vs {m['away']}\n"
                f"   {m['league']} | {m.get('official_bucket','')}级\n"
                f"   HT {m.get('ht_score','数据缺失')} | 进球：{g}"
            )

    # Remaining hits count
    remaining_hits = len(hits) - len(representative_hits)
    if remaining_hits > 0:
        lines.append(f"\n其余{remaining_hits}场A/B已入库，详见full report。")

    return "\n".join(lines)


def _render_full(data, args):
    """Render full detailed report (all 49 matches per-match)."""
    if not FULL_TEMPLATE.exists():
        print(f"[RENDERER] ERROR: full template not found: {FULL_TEMPLATE}", flush=True)
        sys.exit(1)

    template = FULL_TEMPLATE.read_text()
    matches = data.get("matches", [])
    oc = data.get("official_counts", {})
    summary = data.get("summary", {})
    td = data.get("time_distribution", {})
    sv = data.get("script_validation", {})
    pms = data.get("pre_match_signal", {})
    ds = data.get("diagnosis_summary", {})
    rs = data.get("rolling_stats", {})
    sc = data.get("script_validation_cn", {})

    match_rows = "\n".join(_match_row_full(m, i) for i, m in enumerate(matches))

    for g in ["a", "b", "c"]:
        gd = summary.get(g, {})
        if isinstance(gd.get("rate"), str):
            gd["rate_str"] = gd["rate"]
        elif gd.get("rate") is None:
            gd["rate_str"] = "N/A"
        else:
            gd["rate_str"] = f"{gd['rate']}%"

    skip_correct = summary.get("skip_correct", 0)
    skip_total = summary.get("skip_total", 0)
    skip_backfire = summary.get("skip_backfire", 0)
    skip_correct_rate = "N/A"
    if skip_total and skip_total > 0:
        skip_correct_rate = f"{skip_correct / skip_total * 100:.1f}%"

    g0d = td.get("goals_0_15", {})
    g16d = td.get("goals_16_30", {})
    g31d = td.get("goals_31_45", {})
    fg = td.get("first_goal", {})

    a = oc.get("A", 0)
    b = oc.get("B", 0)
    ab_count = a + b
    ab_concl = f"A+B：{ab_count}场主推荐" if ab_count > 0 else "本日无 A/B 主推荐"
    skip_obs = "SKIP 反杀偏高，月报观察" if skip_total > 0 and skip_backfire > 0 else "SKIP 反杀在正常范围"
    script_obs = "赛前剧本数据缺失" if sv.get("script_na", 0) > 0 else "剧本验证通过"
    dq_note = f"数据质量：{ds.get('DATA_QUALITY_ISSUE', 0)}场存在数据不足" if ds.get("DATA_QUALITY_ISSUE", 0) > 0 else "数据质量：可接受"

    r = {
        "{{review_date}}": data.get("review_date", args.date),
        "{{a_count}}": str(a),
        "{{b_count}}": str(b),
        "{{c_count}}": str(oc.get("C", 0)),
        "{{skip_count}}": str(oc.get("SKIP", 0)),
        "{{ab_count}}": str(ab_count),
        "{{recommendation_summary}}": data.get("recommendation_summary", ""),
        "{{official_brief_file}}": data.get("official_source", f"v4_openclaw_brief_{args.date}.txt"),
        "{{match_rows}}": match_rows,
        "{{a_hit}}": str(summary.get("a", {}).get("hit", 0)),
        "{{a_total}}": str(summary.get("a", {}).get("total", 0)),
        "{{a_hit_rate}}": summary.get("a", {}).get("rate_str", "N/A"),
        "{{b_hit}}": str(summary.get("b", {}).get("hit", 0)),
        "{{b_total}}": str(summary.get("b", {}).get("total", 0)),
        "{{b_hit_rate}}": summary.get("b", {}).get("rate_str", "N/A"),
        "{{c_hit}}": str(summary.get("c", {}).get("hit", 0)),
        "{{c_total}}": str(summary.get("c", {}).get("total", 0)),
        "{{c_hit_rate}}": summary.get("c", {}).get("rate_str", "N/A"),
        "{{skip_correct}}": str(summary.get("skip_correct", 0)),
        "{{skip_total}}": str(summary.get("skip_total", 0)),
        "{{skip_correct_rate}}": skip_correct_rate,
        "{{skip_backfire}}": str(summary.get("skip_backfire", 0)),
        "{{skip_backfire_rate}}": str(summary.get("skip_backfire_rate", "N/A")),
        "{{daily_summary_note}}": data.get("daily_summary_note", ""),
        "{{sample_count}}": str(td.get("sample_count", 0)),
        "{{ht_goal_total}}": str(td.get("ht_goal_total", 0)),
        "{{goals_0_15_total}}": str(g0d.get("count", 0)),
        "{{goals_0_15_minutes}}": g0d.get("minutes", ""),
        "{{goals_16_30_total}}": str(g16d.get("count", 0)),
        "{{goals_16_30_minutes}}": g16d.get("minutes", ""),
        "{{goals_31_45_total}}": str(g31d.get("count", 0)),
        "{{goals_31_45_minutes}}": g31d.get("minutes", ""),
        "{{first_goal_0_15}}": str(fg.get("0_15", 0)),
        "{{first_goal_16_30}}": str(fg.get("16_30", 0)),
        "{{first_goal_31_45}}": str(fg.get("31_45", 0)),
        "{{no_ht_goal_count}}": str(fg.get("none", 0)),
        "{{data_missing_count}}": "0",
        "{{script_hit}}": str(sv.get("script_hit", 0)),
        "{{script_partial}}": str(sv.get("script_partial", 0)),
        "{{script_miss}}": str(sv.get("script_miss", 0)),
        "{{no_ht_goal_to_validate}}": str(sv.get("no_ht_goal", 0)),
        "{{script_not_available}}": str(sv.get("script_na", 0)),
        "{{matched_count}}": str(sv.get("matched_count", 0)),
        "{{earlier_than_expected}}": str(sv.get("earlier_than_expected", 0)),
        "{{later_than_expected}}": str(sv.get("later_than_expected", 0)),
        "{{too_strict_script}}": str(sv.get("too_strict_script", 0)),
        "{{script_no_data}}": str(sv.get("script_no_data", 0)),
        "{{script_review_note}}": sv.get("note", ""),
        "{{ab_sample_count}}": str(pms.get("ab_sample_count", 0)),
        "{{avg_ht_score}}": pms.get("avg_ht_score", "N/A"),
        "{{avg_ht_goal_rate}}": pms.get("avg_ht_goal_rate", "N/A"),
        "{{avg_avg_ht_goals}}": pms.get("avg_avg_ht_goals", "N/A"),
        "{{market_support_count}}": str(pms.get("market_support_count", 0)),
        "{{fulltime_stronger_count}}": str(pms.get("fulltime_stronger_count", 0)),
        "{{risk_validated_count}}": str(pms.get("risk_validated_count", 0)),
        "{{pre_match_signal_note}}": pms.get("note", ""),
        "{{weather_rows_or_summary}}": f"全部{len(matches)}场天气数据缺失，不参与本日归因",
        "{{rolling_7d_ab}}": rs.get("7d_ab", "样本不足"),
        "{{rolling_7d_c}}": rs.get("7d_c", "样本不足"),
        "{{rolling_7d_skip_backfire}}": rs.get("7d_skip_backfire", "样本不足"),
        "{{rolling_7d_script}}": rs.get("7d_script", "样本不足"),
        "{{rolling_14d_summary}}": rs.get("14d_summary", "样本不足"),
        "{{rolling_30d_summary}}": rs.get("30d_summary", "样本不足"),
        "{{cumulative_summary}}": rs.get("cumulative", "样本不足"),
        "{{rolling_source_files}}": data.get("rolling_source_files", "N/A"),
        "{{model_valid_count}}": str(ds.get("MODEL_VALID", 0)),
        "{{model_too_strict_count}}": str(ds.get("MODEL_TOO_STRICT", 0)),
        "{{model_overconfident_count}}": str(ds.get("MODEL_OVERCONFIDENT", 0)),
        "{{noisy_win_count}}": str(ds.get("NOISY_WIN", 0)),
        "{{noisy_loss_count}}": str(ds.get("NOISY_LOSS", 0)),
        "{{data_quality_issue_count}}": str(ds.get("DATA_QUALITY_ISSUE", 0)),
        "{{weather_risk_count}}": str(ds.get("WEATHER_RISK", 0)),
        "{{diagnosis_note}}": data.get("diagnosis_note", ""),
        "{{rule_decision}}": "不改规则",
        "{{ab_conclusion}}": ab_concl,
        "{{skip_observation}}": skip_obs,
        "{{script_observation}}": script_obs,
        "{{data_quality_note}}": dq_note,
        "{{sample_warning}}": "不因少量样本改规则",
    }

    output = template
    for k, v in r.items():
        output = output.replace(k, v)

    out_path = REPORT_DIR / f"v4_review_full_{args.date}.txt"
    out_path.write_text(output, encoding="utf-8")
    print(f"[RENDERER] ✅ rendered (full) → {out_path} ({len(output)} bytes)", flush=True)


def _render_qq(data, args):
    """Render QQ daily brief.
    - A/B summary with limited detail (unhits first + up to 5 rep hits)
    - C/SKIP summary only (no per-match)
    - No full report sections
    """
    oc = data.get("official_counts", {})
    a = oc.get("A", 0)
    b = oc.get("B", 0)
    c = oc.get("C", 0)
    s = oc.get("SKIP", 0)
    ab_count = a + b
    summary = data.get("summary", {})
    rs = data.get("rolling_stats", {})

    # If no A/B, use brief template
    if a == 0 and b == 0:
        if not QQ_BRIEF_TEMPLATE.exists():
            print(f"[RENDERER] ERROR: brief template not found: {QQ_BRIEF_TEMPLATE}", flush=True)
            sys.exit(1)
        template = QQ_BRIEF_TEMPLATE.read_text()
        c_data = summary.get("c", {})
        c_hit = c_data.get("hit", 0)
        c_total = c_data.get("total", 0)
        c_rate = c_data.get("rate", "N/A") if not isinstance(c_data.get("rate"), str) or c_total == 0 else c_data["rate"]

        r = {
            "{{review_date}}": data.get("review_date", args.date),
            "{{a_count}}": "0",
            "{{b_count}}": "0",
            "{{ab_summary}}": "无 A/B 主推荐，不计算 A/B 命中率",
            "{{ab_detail_section}}": "",
            "{{c_hit}}": str(c_hit),
            "{{c_total}}": str(c_total),
            "{{c_hit_rate}}": c_rate if isinstance(c_rate, str) else f"{c_rate}%",
            "{{skip_backfire}}": str(summary.get("skip_backfire", 0)),
            "{{skip_total}}": str(summary.get("skip_total", 0)),
            "{{skip_backfire_rate}}": str(summary.get("skip_backfire_rate", "N/A")),
            "{{rolling_7d_ab}}": rs.get("7d_ab", "样本不足"),
            "{{rolling_7d_c}}": rs.get("7d_c", "样本不足"),
            "{{rolling_7d_skip_backfire}}": rs.get("7d_skip_backfire", "样本不足"),
            "{{rule_decision}}": "不改规则，继续观察",
            "{{sample_warning}}": "不因少量样本改规则",
        }
        output = template
        for k, v in r.items():
            output = output.replace(k, v)
    else:
        # A/B day: use QQ brief with A/B detail and C/SKIP summary
        if not QQ_TEMPLATE.exists():
            print(f"[RENDERER] ERROR: QQ template not found: {QQ_TEMPLATE}", flush=True)
            sys.exit(1)
        template = QQ_TEMPLATE.read_text()

        matches = data.get("matches", [])
        ab_matches = [m for m in matches if m.get("official_bucket") in ("A", "B")]
        ab_detail = _ab_detail_qq(ab_matches)

        c_data = summary.get("c", {})
        c_hit = c_data.get("hit", 0)
        c_total = c_data.get("total", 0)
        c_rate = c_data.get("rate", "N/A") if isinstance(c_data.get("rate"), str) else f"{c_data.get('hit',0)}/{c_data.get('total',0)}"
        sb = summary.get("skip_backfire", 0)
        st = summary.get("skip_total", 0)

        a_hit = summary.get("a", {}).get("hit", 0)
        b_hit = summary.get("b", {}).get("hit", 0)
        ab_hit = a_hit + b_hit
        ab_summary = f"A：{a_hit}/{a} · B：{b_hit}/{b} · A+B：{ab_hit}/{ab_count}" if ab_count > 0 else "无 A/B 主推荐"

        r = {
            "{{review_date}}": data.get("review_date", args.date),
            "{{a_count}}": str(a),
            "{{b_count}}": str(b),
            "{{ab_summary}}": f"A：{a_hit}/{a} · B：{b_hit}/{b} · A+B：{ab_hit}/{ab_count}",
            "{{ab_detail_section}}": ab_detail,
            "{{c_hit}}": str(c_hit),
            "{{c_total}}": str(c_total),
            "{{c_hit_rate}}": c_rate if isinstance(c_rate, str) else f"{c_rate}%",
            "{{skip_backfire}}": str(sb),
            "{{skip_total}}": str(st),
            "{{skip_backfire_rate}}": str(summary.get("skip_backfire_rate", "N/A")),
            "{{rolling_7d_ab}}": rs.get("7d_ab", "样本不足"),
            "{{rolling_7d_c}}": rs.get("7d_c", "样本不足"),
            "{{rolling_7d_skip_backfire}}": rs.get("7d_skip_backfire", "样本不足"),
            "{{rule_decision}}": "不改规则",
            "{{sample_warning}}": "不因少量样本改规则",
        }
        output = template
        for k, v in r.items():
            output = output.replace(k, v)

    out_path = REPORT_DIR / f"v4_review_qq_{args.date}.txt"
    out_path.write_text(output, encoding="utf-8")
    print(f"[RENDERER] ✅ rendered (qq) → {out_path} ({len(output)} bytes)", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--mode", choices=["full", "qq"], required=True)
    args = parser.parse_args()

    struct_path = REPORT_DIR / f"v4_review_structured_{args.date}.json"
    if not struct_path.exists():
        print(f"[RENDERER] ERROR: structured file not found: {struct_path}", flush=True)
        sys.exit(1)

    with open(struct_path) as f:
        data = json.load(f)

    if args.mode == "full":
        _render_full(data, args)
    else:
        _render_qq(data, args)


if __name__ == "__main__":
    main()
