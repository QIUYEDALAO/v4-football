#!/usr/bin/env python3
"""engine/v4_review_renderer.py — V4复盘QQ模板渲染器

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
TEMPLATE_DIR = BASE_DIR / "templates"
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
TEMPLATE = TEMPLATE_DIR / "v4_daily_review_qq_template.md"


def _match_row(m: dict, idx: int) -> str:
    num = idx + 1
    home = m.get("home", "?")
    away = m.get("away", "?")
    league = m.get("league", "?")
    fid = m.get("fixture_id", "?")
    bucket = m.get("official_bucket", "?")
    ht = m.get("ht_score", "?")
    ft = m.get("ft_score", "?")
    minutes = m.get("first_half_goal_minutes", [])
    g0 = m.get("goals_0_15", 0)
    g16 = m.get("goals_16_30", 0)
    g31 = m.get("goals_31_45", 0)
    result = m.get("model_result", "?")
    diag = m.get("diagnosis", "?")

    if minutes:
        mins_text = " ".join(f"{m}′" for m in minutes)
        goal_line = f"进球：{mins_text}"
    else:
        goal_line = "进球：无"

    lines = [
        f"⑩ {home} vs {away}",
        f"{league} | fid={fid}",
        f"{bucket} · HT {ht} · FT {ft}",
        goal_line,
        f"分布：0-15 {g0}｜16-30 {g16}｜31-45+ {g31}",
        f"{result} · {diag}",
    ]
    return "\n".join(lines)


def _num_emoji(n: int) -> str:
    emojis = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
    return emojis[n] if n < len(emojis) else f"{n+1}."


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

    # ── Build match rows ──
    matches = data.get("matches", [])
    match_rows = "\n\n".join(
        _match_row(m, i).replace("⑩", _num_emoji(i)) for i, m in enumerate(matches)
    )

    # ── Summary ──
    oc = data.get("official_counts", {})
    a_c = oc.get("A", 0)
    b_c = oc.get("B", 0)
    c_c = oc.get("C", 0)
    s_c = oc.get("SKIP", 0)
    total = a_c + b_c + c_c + s_c

    if a_c == 0 and b_c == 0:
        ab_summary = "无 A/B 主推荐"
    else:
        ab_summary = f"A+B主推荐：{a_c + b_c}场"

    summary = data.get("summary", {})
    c_sum = summary.get("c", {})
    c_hit = c_sum.get("hit", "?")
    c_total = c_sum.get("total", "?")
    c_rate = c_sum.get("rate", "?")
    sb = summary.get("skip_backfire", "?")
    st = summary.get("skip_total", "?")
    sbr = summary.get("skip_backfire_rate", "?")

    # ── Time distribution ──
    td = data.get("time_distribution", {})
    htg = td.get("ht_goal_total", 0)
    sc = td.get("sample_count", total)

    g0 = td.get("goals_0_15", {})
    g16 = td.get("goals_16_30", {})
    g31 = td.get("goals_31_45", {})

    fg = td.get("first_goal", {})
    sbfg = td.get("skip_backfire_first_goal", {})

    # ── Diagnosis ──
    ds = data.get("diagnosis_summary", {})

    # ── Rolling ──
    rs = data.get("rolling_stats", {})

    # ── Conclusion ──
    if a_c == 0 and b_c == 0:
        ab_conclusion = "本日无 A/B 主推荐"
    else:
        ab_conclusion = f"A+B：{a_c + b_c}场主推荐（不计5/14本日命中率）"

    skip_obs = "SKIP 反杀偏高，月报观察" if sb and st and st > 0 else "SKIP 反杀在正常范围内"
    sample_warning = "不因少量样本改规则"

    # ── Render ──
    output = template
    replacements = {
        "{{review_date}}": data.get("review_date", args.date),
        "{{a_count}}": str(a_c),
        "{{b_count}}": str(b_c),
        "{{c_count}}": str(c_c),
        "{{skip_count}}": str(s_c),
        "{{ab_summary}}": ab_summary,
        "{{match_rows}}": match_rows,
        "{{c_hit}}": str(c_hit),
        "{{c_total}}": str(c_total),
        "{{c_hit_rate}}": c_rate if isinstance(c_rate, str) else f"{c_rate}%",
        "{{skip_backfire}}": str(sb),
        "{{skip_total}}": str(st),
        "{{skip_backfire_rate}}": sbr if isinstance(sbr, str) else f"{sbr}%",
        "{{sample_count}}": str(sc),
        "{{ht_goal_total}}": str(htg),
        "{{goals_0_15}}": str(g0.get("count", 0)),
        "{{goals_0_15_minutes}}": g0.get("minutes", ""),
        "{{goals_16_30}}": str(g16.get("count", 0)),
        "{{goals_16_30_minutes}}": g16.get("minutes", ""),
        "{{goals_31_45}}": str(g31.get("count", 0)),
        "{{goals_31_45_minutes}}": g31.get("minutes", ""),
        "{{first_goal_0_15}}": str(fg.get("0_15", 0)),
        "{{first_goal_16_30}}": str(fg.get("16_30", 0)),
        "{{first_goal_31_45}}": str(fg.get("31_45", 0)),
        "{{no_ht_goal_count}}": str(fg.get("none", 0)),
        "{{skip_backfire_first_0_15}}": str(sbfg.get("0_15", {}).get("count", 0)),
        "{{skip_backfire_first_0_15_matches}}": sbfg.get("0_15", {}).get("matches", ""),
        "{{skip_backfire_first_16_30}}": str(sbfg.get("16_30", {}).get("count", 0)),
        "{{skip_backfire_first_16_30_matches}}": sbfg.get("16_30", {}).get("matches", ""),
        "{{skip_backfire_first_31_45}}": str(sbfg.get("31_45", {}).get("count", 0)),
        "{{skip_backfire_first_31_45_matches}}": sbfg.get("31_45", {}).get("matches", ""),
        "{{model_too_strict_count}}": str(ds.get("MODEL_TOO_STRICT", 0)),
        "{{noisy_win_count}}": str(ds.get("NOISY_WIN", 0)),
        "{{model_overconfident_count}}": str(ds.get("MODEL_OVERCONFIDENT", 0)),
        "{{data_quality_issue_count}}": str(ds.get("DATA_QUALITY_ISSUE", 0)),
        "{{rolling_7d_ab}}": rs.get("7d_ab", "样本不足，仅观察"),
        "{{rolling_7d_c}}": rs.get("7d_c", "样本不足，仅观察"),
        "{{rolling_7d_skip_backfire}}": rs.get("7d_skip_backfire", "样本不足，仅观察"),
        "{{rolling_14d_summary}}": rs.get("14d_summary", "样本不足，仅观察"),
        "{{rolling_30d_summary}}": rs.get("30d_summary", "样本不足，仅观察"),
        "{{cumulative_summary}}": rs.get("cumulative", "样本不足，仅观察"),
        "{{rule_decision}}": "不改规则",
        "{{ab_conclusion}}": ab_conclusion,
        "{{skip_observation}}": skip_obs,
        "{{sample_warning}}": sample_warning,
    }

    for placeholder, value in replacements.items():
        output = output.replace(placeholder, value)

    # ── Write output ──
    out_path = REPORT_DIR / f"v4_review_qq_{args.date}.txt"
    out_path.write_text(output, encoding="utf-8")
    print(f"[RENDERER] ✅ rendered → {out_path}", flush=True)
    print(f"[RENDERER] template: {TEMPLATE}", flush=True)
    print(f"[RENDERER] input: {struct_path}", flush=True)


if __name__ == "__main__":
    main()
