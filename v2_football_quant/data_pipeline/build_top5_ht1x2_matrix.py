"""
时间衰减矩阵构建器 (Step 2)
=============================
基于 football-data.co.uk 历史数据，生成五大联赛专项 fair_odds_matrix_top5_v2.json。

核心创新：时间衰减加权 — 近期的比赛权重更高，反映当前市场结构。

用法:
  python3 data_pipeline/build_top5_ht1x2_matrix.py

输出: data_pipeline/data/fair_odds_matrix_top5_v2.json
"""

import json
import math
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = BASE_DIR / "data_pipeline" / "data" / "top5_fd_raw.json"
OUTPUT_PATH = BASE_DIR / "data_pipeline" / "data" / "fair_odds_matrix_top5_v2.json"

# 和现有矩阵保持相同的10档分位边界
# 这些档位边界来自 fair_odds_matrix.json
DECILE_BOUNDS = [
    {"decile": 1, "spread_lo": float("-inf"), "spread_hi": -30.0},
    {"decile": 2, "spread_lo": -30.0, "spread_hi": -20.0},
    {"decile": 3, "spread_lo": -20.0, "spread_hi": -10.0},
    {"decile": 4, "spread_lo": -10.0, "spread_hi": -5.0},
    {"decile": 5, "spread_lo": -5.0, "spread_hi": 5.0},
    {"decile": 6, "spread_lo": 5.0, "spread_hi": 10.0},
    {"decile": 7, "spread_lo": 10.0, "spread_hi": 20.0},
    {"decile": 8, "spread_lo": 20.0, "spread_hi": 30.0},
    {"decile": 9, "spread_lo": 30.0, "spread_hi": float("inf")},
    {"decile": 10, "spread_lo": 30.0, "spread_hi": float("inf")},
]

TODAY = datetime.now()


def time_weight(date):
    """时间衰减: 越近权重越高"""
    days_ago = (TODAY - date).days
    if days_ago < 180:
        return 1.0
    elif days_ago < 360:
        return 0.7
    elif days_ago < 720:
        return 0.4
    else:
        return 0.1


def build_matrix():
    if not INPUT_PATH.exists():
        print(f"❌ 找不到 {INPUT_PATH}，请先运行 ingest_fd_top5.py")
        return

    with open(INPUT_PATH) as f:
        raw_data = json.load(f)

    print(f"📥 加载 {len(raw_data)} 场历史数据")

    # 按档位分组统计 (加权)
    bin_counts = defaultdict(lambda: {"total_weight": 0.0, "H": 0.0, "D": 0.0, "A": 0.0, "count": 0})

    for row in raw_data:
        # 计算近似 att_def_spread
        # Pinnacle 收盘赔率 → 隐含实力差
        try:
            psch = float(row.get("PSCH", 0))
            pscd = float(row.get("PSCD", 0))
            psca = float(row.get("PSCA", 0))
        except (ValueError, TypeError):
            continue

        if psch <= 0 or pscd <= 0 or psca <= 0:
            continue

        # 市场隐含概率
        imp_h = 1.0 / psch
        imp_d = 1.0 / pscd
        imp_a = 1.0 / psca
        margin = imp_h + imp_d + imp_a
        fair_h = imp_h / margin
        fair_a = imp_a / margin

        # 用平博收盘赔率推断市场认为的"实力差"
        # spread = fair_h - fair_a (市场评估的主客差距)
        market_spread = (fair_h - fair_a) * 100  # 放大到 att_def_spread 量级

        # 分档
        assigned_decile = None
        for d in DECILE_BOUNDS:
            if d["spread_lo"] <= market_spread < d["spread_hi"]:
                assigned_decile = d["decile"]
                break
        if assigned_decile is None:
            assigned_decile = 5  # 默认均衡档

        # 时间衰减权重
        date_str = row.get("Date", "")
        try:
            date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except:
            # 尝试其他日期格式
            try:
                date_obj = datetime.strptime(date_str[:10], "%Y-%m-%d")
            except:
                date_obj = TODAY - timedelta(days=400)  # 默认中等权重

        w = time_weight(date_obj)
        ht_result = row.get("HT_Result", "D")

        bucket = bin_counts[assigned_decile]
        bucket["total_weight"] += w
        bucket["count"] += 1
        if ht_result == "H":
            bucket["H"] += w
        elif ht_result == "D":
            bucket["D"] += w
        elif ht_result == "A":
            bucket["A"] += w

    # 计算加权概率 → 公平赔率
    matrix = []
    for d in DECILE_BOUNDS:
        decile = d["decile"]
        bucket = bin_counts.get(decile, {"total_weight": 1.0, "H": 0.0, "D": 0.0, "A": 0.0, "count": 0})
        tw = max(bucket["total_weight"], 1.0)

        prob_H = bucket["H"] / tw
        prob_D = bucket["D"] / tw
        prob_A = bucket["A"] / tw

        # 转换为公平赔率 = 1/prob (兼容现有 fair_odds_matrix.json 格式)
        fair_H = round(1.0 / prob_H, 2) if prob_H > 0 else 10.0
        fair_D = round(1.0 / prob_D, 2) if prob_D > 0 else 5.0
        fair_A = round(1.0 / prob_A, 2) if prob_A > 0 else 10.0
        
        # 百分比格式 (兼容原矩阵)
        H_pct = round(prob_H * 100, 1)
        D_pct = round(prob_D * 100, 1)
        A_pct = round(prob_A * 100, 1)

        matrix.append({
            "decile": decile,
            "spread_lo": d["spread_lo"],
            "spread_hi": d["spread_hi"],
            "n": bucket["count"],
            "H_pct": H_pct, "D_pct": D_pct, "A_pct": A_pct,
            "fair_H": fair_H, "fair_D": fair_D, "fair_A": fair_A,
            "sample_count": bucket["count"],
            "weighted_sample": round(tw, 1),
        })

        print(f"  档{decile}: N={bucket['count']} | P(D)={prob_D:.3f} | D赔率={fair_D:.3f}")

    # 保存
    with open(OUTPUT_PATH, "w") as f:
        json.dump(matrix, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 矩阵已生成: {OUTPUT_PATH}")
    print(f"   总样本: {sum(m['sample_count'] for m in matrix)} 场")
    print(f"   时间衰减总权重: {sum(m['weighted_sample'] for m in matrix):.0f}")

    # 对比现有矩阵的差异
    print(f"\n📊 档5 (均衡) 对比:")
    for m in matrix:
        if m["decile"] == 5:
            print(f"   H={m['fair_H']:.3f} D={m['fair_D']:.3f} A={m['fair_A']:.3f}")
            break


if __name__ == "__main__":
    build_matrix()
