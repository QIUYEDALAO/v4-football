#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
DASH = ROOT / "data/runtime/dashboard"
DOCS = ROOT / "docs"

TZ = timezone(timedelta(hours=8))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_quality(n: int) -> tuple[str, str, str]:
    if n < 5:
        return "VERY_LOW", "LOW", "NO_ACTION_LOW_SAMPLE"
    if n < 10:
        return "LOW", "LOW", "GOOD_BUT_SMALL_SAMPLE"
    if n < 20:
        return "MEDIUM_LOW", "MEDIUM_LOW", "KEEP_OBSERVE"
    if n < 50:
        return "MEDIUM", "MEDIUM", "WATCHLIST"
    return "HIGH", "HIGH", "SHADOW_UPGRADE_CANDIDATE"


def simulate_pnl(ht_goals: int, line: str, odds_water: float) -> float:
    if line == "O0.75":
        if ht_goals == 0:
            return -1.0
        if ht_goals == 1:
            return 0.5 * odds_water
        return 1.0 * odds_water
    if line == "O1":
        if ht_goals == 0:
            return -1.0
        if ht_goals == 1:
            return 0.0
        return 1.0 * odds_water
    if line == "O1.25":
        if ht_goals == 0:
            return -1.0
        if ht_goals == 1:
            return -0.5
        return 1.0 * odds_water
    if line == "O1.5":
        if ht_goals <= 1:
            return -1.0
        return 1.0 * odds_water
    raise ValueError(line)


def build(args: argparse.Namespace) -> int:
    src = STATUS / "v4_ab_130_sample_inventory_20260525.json"
    if not src.exists():
        print("BLOCKER: missing source inventory", src)
        return 2
    inv = load_json(src)
    records = inv.get("records", [])

    # Step 1 freeze official AB settled only
    frozen = []
    blockers = []
    for r in records:
        grade = str(r.get("grade", "")).upper()
        if grade not in {"A", "B"}:
            continue
        if not bool(r.get("valid_for_cumulative", False)):
            continue
        if str(r.get("result_status", "")).lower() != "resolved":
            continue
        if not bool(r.get("is_57_league", True)):
            blockers.append("outside_57_mixed")
            continue
        if r.get("ht_goal_count") is None:
            continue
        frozen.append({
            "fixture_id": r.get("fixture_id"),
            "match_date": r.get("match_date"),
            "league": r.get("league") or "UNKNOWN",
            "country": r.get("country") or "UNKNOWN",
            "home": r.get("home") or "UNKNOWN",
            "away": r.get("away") or "UNKNOWN",
            "grade": grade,
            "ht_score": r.get("ht_score") or "",
            "ht_goal_count": int(r.get("ht_goal_count") or 0),
            "result_hit": bool(r.get("result_hit")),
            "script_type": r.get("script_type") or "UNKNOWN",
            "script_result": r.get("script_result") or "UNKNOWN",
            "source_file": r.get("source_file") or "UNKNOWN",
            "valid_for_league_stats": True,
            "ht_score_model": float(r.get("ht_score_model") or 0.0),
            "market_line": float(r.get("market_line") or 1.0),
            "odds_water": float(r.get("odds_water") or 0.80),
            "odds_source": "record_or_paper_default_0.80" if r.get("odds_water") else "paper_default_0.80",
        })

    A = sum(1 for r in frozen if r["grade"] == "A")
    B = sum(1 for r in frozen if r["grade"] == "B")
    AB = len(frozen)

    inv_out = {
        "phase": "V4-LEAGUE-HIT-RATE-AND-ROI-DIAGNOSTIC-20260526",
        "generated_at": datetime.now(TZ).isoformat(),
        "source_inventory": str(src.relative_to(ROOT)),
        "A_settled": A,
        "B_settled": B,
        "AB_settled": AB,
        "records": frozen,
        "blockers": sorted(set(blockers)),
    }
    inv_path = STATUS / "v4_league_hit_rate_inventory_20260526.json"
    inv_path.write_text(json.dumps(inv_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Step 2/3/4 league stats + roi + guard
    g = defaultdict(list)
    for r in frozen:
        g[(r["league"], r["country"])].append(r)

    leagues = []
    for (league, country), rows in sorted(g.items(), key=lambda x: (x[0][0], x[0][1])):
        n = len(rows)
        a_rows = [x for x in rows if x["grade"] == "A"]
        b_rows = [x for x in rows if x["grade"] == "B"]
        hit_a = sum(1 for x in a_rows if x["result_hit"])
        hit_b = sum(1 for x in b_rows if x["result_hit"])
        hit_ab = sum(1 for x in rows if x["result_hit"])
        g0 = sum(1 for x in rows if x["ht_goal_count"] == 0)
        g1 = sum(1 for x in rows if x["ht_goal_count"] == 1)
        g2 = sum(1 for x in rows if x["ht_goal_count"] >= 2)

        roi_map = {}
        for line, key in [("O0.75", "o075_roi_with_rebate"), ("O1", "o1_roi_with_rebate"), ("O1.25", "o125_roi_with_rebate"), ("O1.5", "o15_roi_with_rebate")]:
            gross = sum(simulate_pnl(x["ht_goal_count"], line, float(x.get("odds_water") or 0.80)) for x in rows)
            turnover = float(n)
            rebate = turnover * 0.025
            net_roi = (gross + rebate) / turnover if turnover else 0.0
            roi_map[key] = round(net_roi, 6)

        quality, conf, action = classify_quality(n)
        if n >= 50 and roi_map["o15_roi_with_rebate"] < -0.05:
            action = "SHADOW_DOWNGRADE_CANDIDATE"
        elif n >= 50 and roi_map["o075_roi_with_rebate"] > 0.08:
            action = "SHADOW_UPGRADE_CANDIDATE"

        leagues.append({
            "league": league,
            "country": country,
            "sample_total_ab": n,
            "sample_a": len(a_rows),
            "sample_b": len(b_rows),
            "hit_a": hit_a,
            "hit_b": hit_b,
            "hit_ab": hit_ab,
            "hit_rate_a": round((hit_a / len(a_rows)) if a_rows else 0.0, 6),
            "hit_rate_b": round((hit_b / len(b_rows)) if b_rows else 0.0, 6),
            "hit_rate_ab": round((hit_ab / n) if n else 0.0, 6),
            "ht_0_goal_count": g0,
            "ht_1_goal_count": g1,
            "ht_2plus_goal_count": g2,
            "ht_0_goal_rate": round(g0 / n, 6) if n else 0.0,
            "ht_1_goal_rate": round(g1 / n, 6) if n else 0.0,
            "ht_2plus_goal_rate": round(g2 / n, 6) if n else 0.0,
            **roi_map,
            "avg_ht_model_score": round(mean([float(x.get("ht_score_model") or 0.0) for x in rows]), 4) if rows else 0.0,
            "script_hit_rate": round(sum(1 for x in rows if str(x.get("script_result")).upper() == "HIT") / n, 6) if n else 0.0,
            "first_match_date": min(x["match_date"] for x in rows),
            "last_match_date": max(x["match_date"] for x in rows),
            "sample_quality": quality,
            "confidence_level": conf,
            "recommended_action": action,
            "odds_source": "paper_default_0.80",
            "observation_only": False,
        })

    high = [x for x in leagues if x["sample_total_ab"] >= 20]
    mid = [x for x in leagues if 10 <= x["sample_total_ab"] < 20]
    low = [x for x in leagues if x["sample_total_ab"] < 10]

    high_sorted = sorted(high, key=lambda x: (x["o1_roi_with_rebate"], x["hit_rate_ab"]), reverse=True)
    mid_sorted = sorted(mid, key=lambda x: (x["o1_roi_with_rebate"], x["hit_rate_ab"]), reverse=True)
    low_sorted = sorted(low, key=lambda x: x["sample_total_ab"], reverse=True)

    stats = {
        "phase": "V4-LEAGUE-HIT-RATE-AND-ROI-DIAGNOSTIC-20260526",
        "generated_at": datetime.now(TZ).isoformat(),
        "sample_scope": "official_57_ab_settled_only",
        "A_settled": A,
        "B_settled": B,
        "AB_settled": AB,
        "outside_57_mixed": False,
        "leagues": leagues,
        "league_groups": {
            "sample_ge_20": high_sorted,
            "sample_10_19": mid_sorted,
            "sample_lt_10": low_sorted,
        },
        "policy": {
            "no_production_change": True,
            "no_small_sample_ban": True,
            "paper_roi_only": True,
        },
    }
    stats_path = STATUS / "v4_league_hit_rate_stats_20260526.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def row_card(x: dict) -> str:
        return f"""
        <div class='card'>
          <div class='title'>{x['league']} <span class='country'>{x['country']}</span></div>
          <div class='meta'>样本 {x['sample_total_ab']} | A/B {x['sample_a']}/{x['sample_b']} | 推荐 {x['recommended_action']}</div>
          <div class='line'>命中 A/B/AB: {x['hit_rate_a']*100:.1f}% / {x['hit_rate_b']*100:.1f}% / {x['hit_rate_ab']*100:.1f}%</div>
          <div class='line'>HT分布 0/1/2+: {x['ht_0_goal_count']}/{x['ht_1_goal_count']}/{x['ht_2plus_goal_count']}</div>
          <div class='line'>ROI(含返水) O0.75/O1/O1.25/O1.5: {x['o075_roi_with_rebate']:.3f} / {x['o1_roi_with_rebate']:.3f} / {x['o125_roi_with_rebate']:.3f} / {x['o15_roi_with_rebate']:.3f}</div>
          <div class='line'>日期范围 {x['first_match_date']} ~ {x['last_match_date']}</div>
        </div>
        """

    html = f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>V4 联赛命中率与ROI诊断</title>
    <style>
    body{{margin:0;background:#0b1220;color:#eaf1ff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:12px;max-width:920px;margin-inline:auto}}
    .panel{{background:#121c31;border:1px solid #24324d;border-radius:12px;padding:10px;margin:8px 0}}
    .card{{background:#0f1729;border:1px solid #24324d;border-radius:10px;padding:8px;margin:8px 0}}
    .title{{font-weight:700}} .country{{color:#93a5bf;font-weight:400}} .meta,.line{{font-size:12px;color:#c9d7ef;margin-top:3px}}
    h1,h2{{margin:6px 0}}
    </style></head><body>
    <h1>V4 联赛命中率与 ROI 诊断</h1>
    <div class='panel'>总样本 A/B/AB: {A}/{B}/{AB}<br>样本口径：只统计 official 57 A/B settled；排除 C/SKIP/UNKNOWN/outside_57。<br>诊断用途，不自动改策略。</div>
    <div class='panel'><a href='/live_bet_tracker.html' style='color:#87b7ff'>返回实盘记录页</a></div>
    <h2>样本 >=20 联赛</h2>{''.join(row_card(x) for x in high_sorted) if high_sorted else "<div class='panel'>无</div>"}
    <h2>样本 10-19 联赛（弱参考）</h2>{''.join(row_card(x) for x in mid_sorted) if mid_sorted else "<div class='panel'>无</div>"}
    <h2>样本 <10 联赛（仅观察）</h2>{''.join(row_card(x) for x in low_sorted) if low_sorted else "<div class='panel'>无</div>"}
    </body></html>"""

    html_path = DASH / "v4_league_hit_rate.html"
    html_path.write_text(html, encoding="utf-8")

    # Step 10 status summary
    summary = {
        "phase": "V4-LEAGUE-HIT-RATE-AND-ROI-DIAGNOSTIC-20260526",
        "generated_at": datetime.now(TZ).isoformat(),
        "outputs": {
            "inventory": str(inv_path.relative_to(ROOT)),
            "stats": str(stats_path.relative_to(ROOT)),
            "html": str(html_path.relative_to(ROOT)),
        },
        "A_settled": A,
        "B_settled": B,
        "AB_settled": AB,
        "warn_only": [],
        "blockers": sorted(set(blockers)),
    }
    (STATUS / "v4_league_hit_rate_and_roi_diagnostic_20260526.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"A": A, "B": B, "AB": AB, "leagues": len(leagues), "html": str(html_path)}, ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="20260526")
    args = ap.parse_args()
    return build(args)


if __name__ == "__main__":
    raise SystemExit(main())
