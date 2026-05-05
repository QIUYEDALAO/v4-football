"""
CLV (Closing Line Value) 计算器 v0.1
======================================
核心公式：CLV = (closing_odds - placed_odds) / placed_odds

CLV > 0  → 战胜市场（买入时赔率好于收盘价）
CLV < 0  → 被市场碾压

用法：
  from clv import calc_clv, calc_clv_from_odds

  clv = calc_clv(placed_odds=2.0, closing_odds=2.1)  # → 0.05
"""

from typing import Optional


def calc_clv(placed_odds: float, closing_odds: float) -> Optional[float]:
    """
    单场 CLV 计算。
    
    Args:
        placed_odds: 投注时的 decimal odds
        closing_odds: 临场收盘 decimal odds (赛前30min内)
    
    Returns:
        CLV 值，None 如果输入无效
    """
    if placed_odds <= 0 or closing_odds <= 0:
        return None
    return (closing_odds - placed_odds) / placed_odds


def calc_clv_batch(records: list[dict]) -> float:
    """
    批量 CLV 均值计算。
    
    Args:
        records: [{placed_odds, closing_odds}, ...]
    
    Returns:
        平均 CLV
    """
    clvs = []
    for r in records:
        clv = calc_clv(r.get("placed_odds", 0), r.get("closing_odds", 0))
        if clv is not None:
            clvs.append(clv)
    return sum(clvs) / len(clvs) if clvs else 0.0


def implied_prob(decimal_odds: float) -> Optional[float]:
    """赔率 → 隐含概率"""
    if decimal_odds <= 0:
        return None
    return 1.0 / decimal_odds


def overround(odds_list: list[float]) -> float:
    """
    计算庄家返水率。
    
    Args:
        odds_list: 同一市场的所有赔率（如 [2.0, 1.8]）
    
    Returns:
        overround (1 = 100%返水, >1 = 庄家抽水后的市场总概率)
    """
    if not odds_list:
        return 0.0
    return sum(1.0 / o for o in odds_list if o > 0)


def fair_odds(odds_list: list[float]) -> list[float]:
    """去除庄家抽水后的公平赔率"""
    ov = overround(odds_list)
    if ov == 0:
        return []
    return [o * ov for o in odds_list]


def ev(placed_odds: float, fair_prob: float) -> Optional[float]:
    """
    期望价值 (Expected Value)。
    
    Args:
        placed_odds: 投注赔率
        fair_prob: 公平概率 (0~1)
    
    Returns:
        EV (正值=有利可图)
    """
    if placed_odds <= 0:
        return None
    return placed_odds * fair_prob - 1.0


# ===== 测试 =====
if __name__ == "__main__":
    # 单场 CLV
    clv = calc_clv(2.0, 2.1)
    print(f"CLV (2.0 -> 2.1): {clv:.4f}")  # → 0.05

    # 批量
    batch = [
        {"placed_odds": 2.0, "closing_odds": 2.1},
        {"placed_odds": 1.8, "closing_odds": 1.7},
        {"placed_odds": 3.0, "closing_odds": 2.8},
    ]
    avg_clv = calc_clv_batch(batch)
    print(f"Avg CLV: {avg_clv:.4f}")  # → -0.0167

    # EV
    ev_val = ev(2.0, 0.55)
    print(f"EV (2.0 @ 55%): {ev_val:.4f}")  # → 0.10

    # overround
    ov = overround([2.0, 1.8])
    print(f"Overround: {ov:.4f}")  # → 1.0556
    print(f"Fair odds: {fair_odds([2.0, 1.8])}")
