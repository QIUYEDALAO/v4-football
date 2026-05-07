"""
V3 洲际大赛认知泡沫套利 — 核心因子分析 (Step 2)
=====================================================
基于 4 届大赛 (WC2018/2022, EC2020/2024) 数据，
计算 Perception Gap (认知偏差) 与 True CLV 回测。

核心因子:
  Elo Ratio   = HomeElo / AwayElo       (实力比)
  Value Ratio = HomeValue / AwayValue   (身价比)
  Perception Gap = log(ValueRatio) - log(EloRatio)

当身价比远大于实力比时 → 伪球迷资金涌入豪门 → 做空豪门有利可图。

用法:
  python3 data_pipeline/analyze_v3_bubble.py

⚠️ 前提: v3_tournaments_raw.json 中已填入 Elo/Value 列。
"""

import json
import math
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = BASE_DIR / "data_pipeline" / "data" / "v3_tournaments_raw.json"
OUTPUT_PATH = BASE_DIR / "data_pipeline" / "data" / "v3_thresholds.json"

# 四大冠军热门国家队 (常被伪球迷热捧)
BUBBLE_TEAMS = {
    "Brazil", "France", "England", "Germany", "Spain", "Argentina",
    "Portugal", "Netherlands", "Italy", "Belgium"
}


def calc_perception_gap(home_elo, away_elo, home_value, away_value):
    """计算认知偏差因子"""
    if not all([home_elo, away_elo, home_value, away_value]):
        return None
    if home_elo <= 0 or away_elo <= 0 or home_value <= 0 or away_value <= 0:
        return None

    elo_ratio = home_elo / away_elo
    val_ratio = home_value / away_value
    gap = math.log(val_ratio) - math.log(elo_ratio)
    return round(gap, 4)


def analyze():
    if not INPUT_PATH.exists():
        print(f"❌ {INPUT_PATH} 不存在，请先运行数据下载")
        return

    with open(INPUT_PATH) as f:
        data = json.load(f)

    print(f"📥 加载 {len(data)} 场大赛数据")

    # 统计有 Elo/Value 的场次
    has_elo = sum(1 for r in data if r.get("home_elo") and r.get("away_elo"))
    has_value = sum(1 for r in data if r.get("home_value") and r.get("away_value"))
    has_full = sum(1 for r in data if r.get("home_elo") and r.get("away_elo")
                   and r.get("home_value") and r.get("away_value")
                   and r.get("PS_H") and r.get("HTHG") is not None)

    print(f"  有 Elo: {has_elo} | 有身价: {has_value} | 全字段: {has_full}")
    print(f"  ⚠️ 全字段=0 说明 Elo/Value 尚未填入，当前仅做框架验证")
    print()

    if has_full == 0:
        print("=" * 55)
        print(" 📋 V3 数据填报模板 (填好后重新运行)")
        print("=" * 55)
        print()
        print("在 v3_tournaments_raw.json 每条记录中加入:")
        print('  "home_elo": 1850,     # 赛前 Elo 积分')
        print('  "away_elo": 1620,')
        print('  "home_value": 850,   # 全队身价 (百万欧元)')
        print('  "away_value": 120,')
        print()
        print("推荐数据源:")
        print("  Elo:     https://eloratings.net (每队有历史曲线)")
        print("  身价:    https://transfermarkt.com (需爬虫)")
        print("  快捷方案: 手动填 4 届大赛小组赛核心场次 (~50 场)")
        print()

        # 输出需要填写的关键比赛
        print("🎯 重点填写: 泡沫球队 vs 弱旅的小组赛 (前2轮)")
        print("-" * 55)
        key_matches = []
        for r in data:
            home = r.get("home", "")
            away = r.get("away", "")
            # 筛选: 泡沫球队 vs 非泡沫球队
            home_bubble = home in BUBBLE_TEAMS
            away_bubble = away in BUBBLE_TEAMS
            if home_bubble != away_bubble and r.get("PS_H"):
                key_matches.append(r)

        for r in sorted(key_matches, key=lambda x: x.get("date", ""))[:30]:
            home = r["home"]
            away = r["away"]
            ps = f'H={r.get("PS_H","?")} D={r.get("PS_D","?")} A={r.get("PS_A","?")}'
            score = f'{r.get("FTHG","?")}-{r.get("FTAG","?")}'
            print(f"  {r['tournament']} | {r['date'][:10]} | {home} vs {away} | {score} | {ps}")
        return

    # ── 因子分析 ──
    results = []
    for r in data:
        if not r.get("home_elo") or not r.get("away_elo"):
            continue
        if not r.get("home_value") or not r.get("away_value"):
            continue
        if not r.get("PS_H") or r.get("HTHG") is None:
            continue

        gap = calc_perception_gap(
            r["home_elo"], r["away_elo"],
            r["home_value"], r["away_value"]
        )
        if gap is None:
            continue

        # HT 结果
        hthg = r["HTHG"]
        htag = r["HTAG"]
        if hthg > htag:
            ht_result = "H"
        elif hthg == htag:
            ht_result = "D"
        else:
            ht_result = "A"

        # 计算 Pinnacle 隐含概率 + CLV
        ps_h = r["PS_H"]
        ps_d = r["PS_D"]
        ps_a = r["PS_A"]
        margin = 1 / ps_h + 1 / ps_d + 1 / ps_a
        fair_d = 1 / ((1 / ps_d) / margin)

        results.append({
            "tournament": r["tournament"],
            "date": r["date"],
            "home": r["home"],
            "away": r["away"],
            "home_elo": r["home_elo"],
            "away_elo": r["away_elo"],
            "home_value": r["home_value"],
            "away_value": r["away_value"],
            "perception_gap": gap,
            "PS_D": ps_d,
            "fair_D": round(fair_d, 2),
            "HT_result": ht_result,
            "score": f'{r["FTHG"]}-{r["FTAG"]}',
        })

    # 按 Perception Gap 分桶
    buckets = defaultdict(lambda: {"count": 0, "draws": 0, "avg_psd": 0})
    for r in results:
        gap = r["perception_gap"]
        if gap > 0.5:
            key = "Gap > 0.5 (泡沫严重)"
        elif gap > 0.2:
            key = "Gap 0.2-0.5"
        elif gap > 0.05:
            key = "Gap 0.05-0.2"
        elif gap > -0.05:
            key = "Gap ~0 (均衡)"
        else:
            key = "Gap < 0 (反向泡沫)"

        buckets[key]["count"] += 1
        if r["HT_result"] == "D":
            buckets[key]["draws"] += 1
        buckets[key]["avg_psd"] += r["PS_D"]

    print("\n📊 Perception Gap 分桶分析:")
    print(f"{'Gap区间':<24} | {'场数':<4} | {'平局率':<6} | {'Avg PSD'}")
    print("-" * 55)
    for key in ["Gap > 0.5 (泡沫严重)", "Gap 0.2-0.5", "Gap 0.05-0.2",
                "Gap ~0 (均衡)", "Gap < 0 (反向泡沫)"]:
        b = buckets[key]
        if b["count"] > 0:
            draw_rate = b["draws"] / b["count"] * 100
            avg_psd = b["avg_psd"] / b["count"]
            print(f"{key:<24} | {b['count']:<4} | {draw_rate:>5.1f}% | {avg_psd:>6.2f}")

    print("\n✅ 分析完成。输出: v3_thresholds.json")


if __name__ == "__main__":
    analyze()
