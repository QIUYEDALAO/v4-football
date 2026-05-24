#!/usr/bin/env python3
from __future__ import annotations

from typing import Tuple


def _result_from_line(ht_goals: int, market_line: str) -> str:
    if market_line == "O0.75":
        return "LOSS" if ht_goals == 0 else ("HALF_WIN" if ht_goals == 1 else "WIN")
    if market_line == "O1":
        return "LOSS" if ht_goals == 0 else ("PUSH" if ht_goals == 1 else "WIN")
    if market_line == "O1.25":
        return "LOSS" if ht_goals == 0 else ("HALF_LOSS" if ht_goals == 1 else "WIN")
    if market_line == "O1.5":
        return "LOSS" if ht_goals in (0, 1) else "WIN"
    raise ValueError("unsupported market_line")


def _gross_pnl(stake: float, odds_water: float, result: str) -> float:
    if result == "WIN":
        return stake * odds_water
    if result == "HALF_WIN":
        return stake * odds_water * 0.5
    if result == "PUSH":
        return 0.0
    if result == "HALF_LOSS":
        return -stake * 0.5
    if result == "LOSS":
        return -stake
    if result == "PENDING":
        return 0.0
    raise ValueError("unsupported result")


def settle(stake: float, odds_water: float, market_line: str, ht_goal_count: int, rebate_rate: float = 0.025) -> dict:
    result = _result_from_line(int(ht_goal_count), market_line)
    gross = _gross_pnl(float(stake), float(odds_water), result)
    rebate = float(stake) * float(rebate_rate)
    net = gross + rebate
    return {
        "settlement_result": result,
        "gross_pnl": round(gross, 4),
        "rebate_rate": float(rebate_rate),
        "rebate": round(rebate, 4),
        "net_pnl": round(net, 4),
    }
