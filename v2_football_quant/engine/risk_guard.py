from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskDecision:
    allow: bool
    reason: str
    max_stake_fraction: float

    def to_dict(self) -> dict:
        return {
            "allow": self.allow,
            "reason": self.reason,
            "max_stake_fraction": round(self.max_stake_fraction, 6),
        }


def evaluate_risk_guard(
    *,
    open_positions: int,
    same_league_open: int,
    same_country_open: int,
    day_loss_pct: float,
    consecutive_losses: int,
) -> RiskDecision:
    if day_loss_pct <= -2.0:
        return RiskDecision(False, "DAILY_STOP_LOSS_REACHED", 0.0)
    if consecutive_losses >= 8:
        return RiskDecision(False, "CONSECUTIVE_LOSS_STOP", 0.0)
    if open_positions >= 8:
        return RiskDecision(False, "PORTFOLIO_EXPOSURE_LIMIT", 0.0)
    if same_country_open >= 5:
        return RiskDecision(False, "COUNTRY_EXPOSURE_LIMIT", 0.0)
    if same_league_open >= 3:
        return RiskDecision(False, "LEAGUE_EXPOSURE_LIMIT", 0.0)
    stake = 0.005
    if consecutive_losses >= 5:
        stake *= 0.5
        return RiskDecision(True, "LOSS_STREAK_REDUCED_STAKE", stake)
    return RiskDecision(True, "RISK_OK", stake)

