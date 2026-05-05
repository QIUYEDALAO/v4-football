"""
V2 回测流水线 v0.1 (P0 Day 3)
================================
输入：2322场 Fixtures + H2H + Predictions
输出：backtest_results.csv（含评分、预测概率、实际赛果、模拟ROI）

过滤：
  - 只统计已完赛比赛 (FT/AET/PEN)
  - 只统计评分 > 75 且模型赔率 > 1.70 的推荐场次
  - 0-0 防守标记的降级场次自动排除
"""

import json
import csv
import os
from pathlib import Path
from datetime import datetime
from scoring_engine_v0 import score_match

DATA_DIR = Path(__file__).parent.parent / "data" / "raw_fixtures"
OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

# 白名单
with open(Path(__file__).parent.parent / "config" / "leagues_whitelist.json") as f:
    LEAGUE_CN = json.load(f)["leagueId"]


def run_backtest() -> dict:
    """主回测流程"""
    print("=" * 60)
    print("V2 回测流水线 v0.1")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 加载数据
    with open(DATA_DIR / "fixtures_list.json") as f:
        fixtures = json.load(f)

    h2h_dir = DATA_DIR / "h2h"
    pred_dir = DATA_DIR / "predictions"

    h2h_files = set(os.listdir(h2h_dir))
    pred_files = set(os.listdir(pred_dir))

    # 处理
    results = []
    scores_dist = []
    recommended = []
    hit, miss, skipped = 0, 0, 0

    total_processed = 0
    for item in fixtures:
        if not isinstance(item, dict):
            continue

        fid = str(item.get("id", ""))
        date_str = item.get("date", "")

        # 只处理有完赛数据的（ftHome/ftAway 存在=已完赛）
        ft_home = item.get("ftHome")
        ft_away = item.get("ftAway")
        if ft_home is None or ft_away is None:
            continue

        # 检查数据完整性
        if f"{fid}.json" not in h2h_files:
            skipped += 1
            continue
        if f"{fid}.json" not in pred_files:
            skipped += 1
            continue

        total_processed += 1

        # 加载 H2H 和 Predictions
        with open(h2h_dir / f"{fid}.json") as f:
            h2h_data = json.load(f)
        with open(pred_dir / f"{fid}.json") as f:
            pred_data = json.load(f)

        # 提取半场赛果（fixtures_list 已有）
        ht_home = item.get("htHome", 0) or 0
        ht_away = item.get("htAway", 0) or 0

        ht_total = ht_home + ht_away
        ht_has_goal = 1 if ht_total > 0 else 0

        # 评分
        try:
            scoring = score_match(item, h2h_data, pred_data)
        except Exception as e:
            skipped += 1
            continue

        scores_dist.append(scoring["total_score"])

        league = item.get("league", "?")
        league_name = LEAGUE_CN.get(str(league), str(league))
        home_name = item.get("home", "?")
        away_name = item.get("away", "?")

        row = {
            "fixture_id": fid,
            "date": date_str[:10] if date_str else "",
            "league_id": league,
            "league_name": league_name,
            "home_team": home_name,
            "away_team": away_name,
            "total_score": scoring["total_score"],
            "score_h2h": scoring["dimensions"]["h2h"],
            "score_form": scoring["dimensions"]["form"],
            "score_poisson": scoring["dimensions"]["poisson"],
            "score_timing": scoring["dimensions"]["goal_timing"],
            "score_ai": scoring["dimensions"]["ai_advice"],
            "model_prob": scoring["model_prob"],
            "model_odds": scoring["model_odds"],
            "zero_zero_warning": scoring["zero_zero_warning"],
            "is_recommended": scoring["is_recommended"],
            "h2h_rate": scoring["h2h_stats"]["ht_goal_rate"],
            "h2h_total": scoring["h2h_stats"]["total"],
            "h2h_ht_goal": scoring["h2h_stats"]["ht_goal"],
            "h2h_ht_zero": scoring["h2h_stats"]["ht_zero"],
            "att_avg": scoring["form_stats"]["att_avg"],
            "ht_expected": scoring["poisson_stats"]["ht_expected"],
            "actual_ht_home": ht_home,
            "actual_ht_away": ht_away,
            "actual_ht_goals": ht_total,
            "actual_ht_has_goal": ht_has_goal,
            # 预留赔率字段
            "real_opening_odds": None,
            "real_closing_odds": None,
            "clv_value": None,
        }

        results.append(row)

        if scoring["is_recommended"]:
            recommended.append(row)
            if ht_has_goal:
                hit += 1
            else:
                miss += 1

        if total_processed % 500 == 0:
            print(f"  已处理 {total_processed} 场...")

    # ===== 汇总 =====
    print(f"\n{'=' * 60}")
    print(f"处理完成！")
    print(f"  总计比赛: {len(fixtures)}")
    print(f"  已完赛且有数据: {total_processed}")
    print(f"  跳过: {skipped}")
    print(f"  推荐场次: {len(recommended)}")
    print(f"  命中: {hit}, 未命中: {miss}")
    print(f"  命中率(推荐): {hit / (hit + miss) * 100:.1f}%" if (hit + miss) > 0 else "  N/A")
    print(f"  平均评分: {sum(scores_dist) / len(scores_dist):.1f}" if scores_dist else "  N/A")

    # 模拟 ROI（按模型赔率算）
    sim_roi = 0
    sim_bets = 0
    for r in recommended:
        if r["actual_ht_has_goal"]:
            sim_roi += r["model_odds"] - 1  # 赢：赚赔率-1
        else:
            sim_roi -= 1  # 输：亏1单位
        sim_bets += 1

    print(f"\n[模拟ROI — 按模型理论赔率]")
    print(f"  投注次数: {sim_bets}")
    print(f"  总盈亏: {sim_roi:+.2f} 单位")
    print(f"  ROI: {sim_roi / sim_bets * 100:+.1f}%" if sim_bets > 0 else "  N/A")

    # 按联赛分组
    print(f"\n[按联赛分组 — 推荐场次]")
    lg_hit = {}
    for r in recommended:
        lg = r["league_name"]
        if lg not in lg_hit:
            lg_hit[lg] = {"hit": 0, "total": 0}
        lg_hit[lg]["total"] += 1
        if r["actual_ht_has_goal"]:
            lg_hit[lg]["hit"] += 1

    for lg in sorted(lg_hit.keys(), key=lambda x: -lg_hit[x]["total"]):
        d = lg_hit[lg]
        rate = d["hit"] / d["total"] * 100 if d["total"] > 0 else 0
        stars = "⭐" if rate >= 65 else ("✅" if rate >= 55 else "⚠️")
        print(f"  {stars} {lg}: {d['hit']}/{d['total']} ({rate:.0f}%)")

    # 保存 CSV
    csv_path = OUTPUT_DIR / "backtest_results_v0.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        if results:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    print(f"\n✅ CSV 已保存: {csv_path}")
    print(f"   总行数: {len(results)}")
    print(f"   推荐行数: {len(recommended)}")

    return {
        "total_processed": total_processed,
        "recommended": len(recommended),
        "hit": hit,
        "miss": miss,
        "sim_roi": sim_roi / sim_bets if sim_bets > 0 else 0,
    }


if __name__ == "__main__":
    run_backtest()
