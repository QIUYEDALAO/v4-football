"""
V4 H2H 引擎 — 基于 API-Football 历史交锋的大球评估
======================================================
核心因子: 近10场历史交锋上半场有进球率 ≥ 80% + 全场0-0 ≤ 2场

用法:
  from engine.data_sources.h2h_engine import evaluate_h2h_edge
  result = evaluate_h2h_edge(home_id, away_id, api_func)
"""

import time
import logging
from typing import Optional

logger = logging.getLogger("V4_H2H_Engine")


def evaluate_h2h_edge(home_id: int, away_id: int, api_client) -> dict:
    """
    V4 核心勘探因子：基于 API-Football 历史交锋的大球评估。

    Returns:
        {"valid": bool, "strategy_id": "V4_OU_H2H"|None, "metrics": {...}}
    """
    endpoint = f"fixtures/headtohead?h2h={home_id}-{away_id}"
    resp = api_client(endpoint)

    if not resp or "response" not in resp:
        return {"valid": False, "reason": "API_ERROR"}

    matches = resp["response"]
    total_h2h = len(matches)

    # 规则 1: 样本量护城河
    if total_h2h < 4:
        return {"valid": False, "reason": f"样本量不足 (N={total_h2h} < 4)"}

    # 只取最近 10 场 (防止十年前数据污染)
    recent = sorted(matches, key=lambda x: x.get("fixture", {}).get("timestamp", 0), reverse=True)[:10]

    ht_goal_count = 0
    ft_zero_count = 0

    for m in recent:
        score = m.get("score", {})
        ht = score.get("halftime", {})
        ft = score.get("fulltime", {})

        ht_h = ht.get("home") if ht and ht.get("home") is not None else 0
        ht_a = ht.get("away") if ht and ht.get("away") is not None else 0
        ft_h = ft.get("home") if ft and ft.get("home") is not None else 0
        ft_a = ft.get("away") if ft and ft.get("away") is not None else 0

        if (ht_h + ht_a) > 0:
            ht_goal_count += 1
        if (ft_h + ft_a) == 0:
            ft_zero_count += 1

    n = len(recent)
    ht_rate = ht_goal_count / n

    # 规则 2 & 3: V38 铁律
    if ht_rate >= 0.8 and ft_zero_count <= 2:
        return {
            "valid": True,
            "strategy_id": "V4_OU_H2H",
            "market_type": "FT_OU_2_5",
            "metrics": {
                "h2h_total": total_h2h,
                "h2h_analyzed": n,
                "ht_goal_rate": round(ht_rate, 3),
                "ft_0_0_count": ft_zero_count,
            }
        }

    return {"valid": False, "reason": f"未达标 (HT有球率={ht_rate:.0%}, 0-0场次={ft_zero_count})"}
