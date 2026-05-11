"""
亚洲大小球结算工具
==================
V4 当前只买 Over，但这里同时保留 Under，方便以后复盘或扩展。

规则:
  - 整数盘: 赢 / 走水 / 输
  - 半球盘: 赢 / 输
  - 0.25盘: 拆成 0.0 + 0.5
  - 0.75盘: 拆成 0.5 + 1.0

示例:
  Over 1.0, 半场1球  → PUSH, pnl=0
  Over 0.75, 半场1球 → HALF_WIN, pnl=0.5*(odds-1)*stake
  Over 1.25, 半场1球 → HALF_LOSS, pnl=-0.5*stake
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class AsianSettlement:
    side: str
    line: float
    goals: int
    odds: float
    stake: float
    result: str
    pnl: float
    return_amount: float
    legs: list[dict]

    def to_dict(self) -> dict:
        return {
            "side": self.side,
            "line": self.line,
            "goals": self.goals,
            "odds": self.odds,
            "stake": self.stake,
            "result": self.result,
            "pnl": round(self.pnl, 4),
            "return_amount": round(self.return_amount, 4),
            "legs": self.legs,
        }


def parse_score_goals(score: str | None) -> Optional[int]:
    if not score:
        return None
    try:
        home, away = str(score).strip().split("-")
        return int(home) + int(away)
    except Exception:
        return None


def split_asian_line(line: float) -> list[float]:
    """把亚洲盘拆成一到两个结算腿。"""
    line = round(float(line), 2)
    base = int(line)
    frac = round(line - base, 2)
    if frac == 0.25:
        return [float(base), base + 0.5]
    if frac == 0.75:
        return [base + 0.5, base + 1.0]
    return [line]


def _settle_leg(goals: int, line: float, side: str) -> str:
    side = side.upper()
    diff = goals - line
    if side == "OVER":
        if diff > 0:
            return "WIN"
        if diff == 0:
            return "PUSH"
        return "LOSS"
    if side == "UNDER":
        if diff < 0:
            return "WIN"
        if diff == 0:
            return "PUSH"
        return "LOSS"
    raise ValueError(f"Unsupported side: {side}")


def _leg_pnl(result: str, stake: float, odds: float) -> float:
    if result == "WIN":
        return stake * (odds - 1.0)
    if result == "PUSH":
        return 0.0
    return -stake


def _combine_result(leg_results: list[str]) -> str:
    wins = leg_results.count("WIN")
    losses = leg_results.count("LOSS")
    pushes = leg_results.count("PUSH")
    if wins and not losses and not pushes:
        return "WIN"
    if losses and not wins and not pushes:
        return "LOSS"
    if pushes and not wins and not losses:
        return "PUSH"
    if wins and pushes and not losses:
        return "HALF_WIN"
    if losses and pushes and not wins:
        return "HALF_LOSS"
    return "MIXED"


def settle_asian_total(
    *,
    goals: int,
    line: float,
    odds: float,
    stake: float = 1.0,
    side: str = "OVER",
) -> AsianSettlement:
    if stake <= 0:
        raise ValueError("stake must be positive")
    if odds <= 1:
        raise ValueError("odds must be greater than 1")

    legs = split_asian_line(line)
    leg_stake = stake / len(legs)
    settled_legs = []
    total_pnl = 0.0
    for leg_line in legs:
        result = _settle_leg(int(goals), float(leg_line), side)
        pnl = _leg_pnl(result, leg_stake, float(odds))
        total_pnl += pnl
        settled_legs.append({
            "line": float(leg_line),
            "stake": round(leg_stake, 4),
            "result": result,
            "pnl": round(pnl, 4),
        })

    return AsianSettlement(
        side=side.upper(),
        line=round(float(line), 2),
        goals=int(goals),
        odds=float(odds),
        stake=float(stake),
        result=_combine_result([x["result"] for x in settled_legs]),
        pnl=round(total_pnl, 4),
        return_amount=round(stake + total_pnl, 4),
        legs=settled_legs,
    )


def settle_over_from_score(score: str, line: float, odds: float, stake: float = 1.0) -> AsianSettlement:
    goals = parse_score_goals(score)
    if goals is None:
        raise ValueError(f"Invalid score: {score}")
    return settle_asian_total(goals=goals, line=line, odds=odds, stake=stake, side="OVER")


if __name__ == "__main__":
    cases = [
        ("0-0", 0.75, 1.80, "LOSS"),
        ("1-0", 0.75, 1.80, "HALF_WIN"),
        ("1-0", 1.0, 1.80, "PUSH"),
        ("1-0", 1.25, 1.80, "HALF_LOSS"),
        ("2-0", 1.25, 1.80, "WIN"),
        ("1-1", 1.5, 1.80, "WIN"),
    ]
    for score, line, odds, expected in cases:
        actual = settle_over_from_score(score, line, odds)
        assert actual.result == expected, (score, line, actual)
    print("asian over settlement checks passed")
