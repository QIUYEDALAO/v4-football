#!/usr/bin/env python3
"""engine/v4_review_renderer.py — V4复盘QQ模板渲染器 v1.0

读取 v4_review_structured_YYYYMMDD.json + templates/v4_daily_review_qq_template.md
严格按模板渲染，禁止AI自由改结构。

输出：
  data/daily_reports/v4_review_qq_YYYYMMDD.txt
"""

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = BASE_DIR / "templates" / "v4_daily_review_qq_template.md"
REPORT_DIR = BASE_DIR / "data" / "daily_reports"


def _num_emoji(n: int) -> str:
    emojis = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
    return emojis[n] if n < len(emojis) else f"{n+1}."


def _match_row(m: dict, idx: int) -> str:
    num_emoji = _num_emoji(idx)
    home = m.get("home", "?")
    away = m.get("away", "?")
    league = m.get("league", "?")
    fid = m.get("fixture_id", "?")
    bucket = m.get("official_bucket", "?")
    ht_score_val = m.get("ht_score_value", "N/A") or "N/A"
    ht_goal_rate = m.get("ht_goal_rate", "N/A") or "N/A"
    avg_ht = m.get("avg_ht_goals", "N/A") or "N/A"
    script = m.get("script_type", "SCRIPT_NOT_AVAILABLE")
    sd = m.get("script_distribution", {})
    pre_0 = sd.get("0_15", "?")
    pre_16 = sd.get("16_30", "?")
    pre_31 = sd.get("31_45", "?")

    risk_flags = m.get("risk_flags", [])
    risk_text = ", ".join(risk_flags) if risk_flags else "DATA_UNAVAILABLE"

    ht = m.get("ht_score", "?")
    ft = m.get("ft_score", "?")
    goals = m.get("first_half_goal_minutes", [])
    g0 = m.get("goals_0_15", 0)
    g16 = m.get("goals_16_30", 0)
    g31 = m.get("goals_31_45", 0)
    result = m.get("model_result", "?")
    diag = m.get("diagnosis", "?")

    if goals:
        mins_text = " ".join(f"{m}′" for m in goals)
    else:
        mins_text = "无"

    ds = m.get("data_source", "?")
    script_check = m.get("script_check", "SCRIPT_NOT_AVAILABLE")
    script_bias = m.get("script_bias", "SCRIPT_NOT_AVAILABLE")
    risk_review = m.get("risk_review", "无数据")

    wc = m.get("weather_context", {})
    wsrc = wc.get("weather_source", "DATA_UNAVAILABLE")
    if wsrc == "DATA_UNAVAILABLE":
        weather_sum = "DATA_UNAVAILABLE"
    else:
        cond = wc.get("weather_condition", "未知")
        temp = wc.get("temperature_c", "?")
        risk = wc.get("weather_risk_level", "UNKNOWN")
        weather_sum = f"{cond} {temp}℃ 风险{risk}"

    lines = [
        f"{num_emoji} {home} vs {away}",
        f"{league}｜fid={fid}",
        f"官方：{bucket}｜评分{ht_score_val}｜HT率{ht_goal_rate}｜场均HT{avg_ht}",
        f"赛前：{script}",
        f"预测：0-15 {pre_0}｜16-30 {pre_16}｜31-45 {pre_31}",
        f"风险：{risk_text}",
        "",
        f"赛果：HT {ht}｜FT {ft}",
        f"进球：{mins_text}",
        f"实际：0-15 {g0}｜16-30 {g16}｜31-45+ {g31}",
        "",
        f"结果：{result}｜{diag}",
        f"剧本：{script_check}｜{script_bias}",
        f"风险验证：{risk_review}",
        f"天气：{weather_sum}",
        f"来源：{ds}",
    ]
    return "\n".join(lines)


def _weather_summary(matches: list) -> str:
    """Generate weather rows or a summary line."""
    unavail_count = 0
    rows = []
    for i, m in enumerate(matches):
        wc = m.get("weather_context", {})
        source = wc.get("weather_source", "DATA_UNAVAILABLE")
        if source == "DATA_UNAVAILABLE":
            unavail_count += 1
        else:
            cond = wc.get("weather_condition", "未知")
            temp = wc.get("temperature_c", "?")
            pitch = wc.get("pitch_condition", "未知")
            risk = wc.get("weather_risk_level", "UNKNOWN")
            note = wc.get("weather_note", "")
            num = _num_emoji(i)
            rows.append(f"{num} {m['home']} vs {m['away']}\n天气：{cond}｜{temp}℃\n场地：{pitch}\n风险：{risk}\n{note}")

    if rows:
        return "\n\n".join(rows)

    if unavail_count == len(matches):
        return f"全部 {unavail_count} 场天气数据缺失，不参与本日归因"

    return f"{unavail_count}/{len(matches)} 场天气数据缺失，其余见逐场"


def _str_or_default(v, default="N/A"):
    if v is None:
        return "N/A"
    return str(v)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    struct_path = REPORT_DIR / f"v4_review_structured_{args.date}.json"
    if not struct_path.exists():
        print(f"[RENDERER] ERROR: structured file not found: {struct_path}", flush=True)
        sys.exit(1)

    if not TEMPLATE.exists():
        print(f"[RENDERER] ERROR: template not found: {TEMPLATE}", flush=True)
        sys.exit(1)

    with open(struct_path) as f:
        data = json.load(f)

    template = TEMPLATE.read_text()

    # ── Match rows ──
    matches = data.get("matches", [])
    match_rows = "\n\n".join(_match_row(m, i) for i, m in enumerate(matches))

    # ── Official counts ──
    oc = data.get("official_counts", {})
    a = oc.get("A", 0)
    b = oc.get("B", 0)
    c = oc.get("C", 0)
    s = oc.get("SKIP", 0)
    ab_count = a + b

    # ── Summary ──
    summary = data.get("summary", {})
    for g in ["a", "b", "c"]:
        gd = summary.get(g, {})
        if gd.get("rate") is None:
            gd["rate_str"] = "N/A（无样本）"
        else:
            gd["rate_str"] = str(gd["rate"]) if isinstance(gd["rate"], str) else f"{gd['rate']}%"
    skip_correct = summary.get("skip_correct", 0)
    skip_total = summary.get("skip_total", 0)
    skip_backfire = summary.get("skip_backfire", 0)
    skip_backfire_rate = summary.get("skip_backfire_rate", "?")
    skip_correct_rate = "N/A"
    if skip_total and skip_total > 0:
        skip_correct_rate = f"{skip_correct/skip_total*100:.1f}%"

    # ── Time distribution ──
    td = data.get("time_distribution", {})
    g0d = td.get("goals_0_15", {})
    g16d = td.get("goals_16_30", {})
    g31d = td.get("goals_31_45", {})
    fg = td.get("first_goal", {})

    # ── Script validation ──
    sv = data.get("script_validation", {})

    # ── Pre-match signal ──
    pms = data.get("pre_match_signal", {})

    # ── Diagnosis ──
    ds = data.get("diagnosis_summary", {})

    # ── Rolling ──
    rs = data.get("rolling_stats", {})

    # ── Conclusion ──
    if a == 0 and b == 0:
        ab_concl = "本日无 A/B 主推荐"
        rec_summary = "今日 V4 无A/B上半场主推荐"
    else:
        ab_concl = f"A+B：{ab_count}场主推荐"
        rec_summary = f"A级{a}场 + B级{b}场"

    skip_obs = "SKIP 反杀偏高，月报观察" if skip_total and skip_total > 0 and skip_backfire > 0 else "SKIP 反杀在正常范围"
    script_obs = "赛前剧本数据缺失" if sv.get("script_na", 0) > 0 else "剧本验证通过"

    sample_warn = "不因少量样本改规则"
    dq_note = ""
    if ds.get("DATA_QUALITY_ISSUE", 0) > 0:
        dq_note = f"数据质量：{ds['DATA_QUALITY_ISSUE']}场存在数据不足"
    else:
        dq_note = "数据质量：可接受"

    weather_rows_or_summary = _weather_summary(matches)

    # ── Build replacements ──
    r = {
        "{{review_date}}": data.get("review_date", args.date),
        "{{a_count}}": str(a),
        "{{b_count}}": str(b),
        "{{c_count}}": str(c),
        "{{skip_count}}": str(s),
        "{{ab_count}}": str(ab_count),
        "{{recommendation_summary}}": rec_summary,
        "{{official_brief_file}}": data.get("official_source", f"v4_openclaw_brief_{args.date}.txt"),
        "{{guard_status}}": data.get("guard_status", "PASS"),
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
        "{{skip_correct}}": str(skip_correct),
        "{{skip_total}}": str(skip_total),
        "{{skip_correct_rate}}": skip_correct_rate,
        "{{skip_backfire}}": str(skip_backfire),
        "{{skip_backfire_rate}}": str(skip_backfire_rate),
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
        "{{weather_rows_or_summary}}": weather_rows_or_summary,
        "{{rolling_7d_ab}}": rs.get("7d_ab", "样本不足，仅观察"),
        "{{rolling_7d_c}}": rs.get("7d_c", "样本不足，仅观察"),
        "{{rolling_7d_skip_backfire}}": rs.get("7d_skip_backfire", "样本不足，仅观察"),
        "{{rolling_7d_script}}": rs.get("7d_script", "样本不足，仅观察"),
        "{{rolling_14d_summary}}": rs.get("14d_summary", "样本不足，仅观察"),
        "{{rolling_30d_summary}}": rs.get("30d_summary", "样本不足，仅观察"),
        "{{cumulative_summary}}": rs.get("cumulative", "样本不足，仅观察"),
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
        "{{sample_warning}}": sample_warn,
    }

    output = template
    for placeholder, value in r.items():
        output = output.replace(placeholder, value)

    out_path = REPORT_DIR / f"v4_review_qq_{args.date}.txt"
    out_path.write_text(output, encoding="utf-8")
    print(f"[RENDERER] ✅ rendered → {out_path}", flush=True)
    print(f"[RENDERER] template: {TEMPLATE}", flush=True)
    print(f"[RENDERER] input: {struct_path}", flush=True)


if __name__ == "__main__":
    main()
