from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExecutionCostResult:
    displayed_odds: float
    simulated_fill_odds: float
    slippage: float
    latency_seconds: float
    latency_cost: float
    requote_cost: float
    ev_gross: float
    ev_net: float
    conservative_ev: float
    fill_probability: float

    def to_dict(self) -> dict:
        return {
            "displayed_odds": round(self.displayed_odds, 4),
            "simulated_fill_odds": round(self.simulated_fill_odds, 4),
            "slippage": round(self.slippage, 4),
            "latency_seconds": round(self.latency_seconds, 3),
            "latency_cost": round(self.latency_cost, 6),
            "requote_cost": round(self.requote_cost, 6),
            "ev_gross": round(self.ev_gross, 6),
            "ev_net": round(self.ev_net, 6),
            "conservative_ev": round(self.conservative_ev, 6),
            "fill_probability": round(self.fill_probability, 4),
        }


def estimate_execution_cost(
    *,
    displayed_odds: float,
    ev_gross: float,
    odds_alive_seconds: float | None = None,
    latency_seconds: float = 1.5,
    market_freeze: bool = False,
) -> ExecutionCostResult:
    alive = max(float(odds_alive_seconds or 3.0), 0.2)
    latency = max(float(latency_seconds), 0.0)
    freeze_penalty = 0.02 if market_freeze else 0.0
    # simple slippage proxy: latency relative to quote life
    slip = min(0.08, 0.01 + 0.04 * min(1.0, latency / alive) + freeze_penalty)
    fill_odds = max(1.01, displayed_odds - slip)
    latency_cost = min(0.03, latency * 0.003)
    requote_cost = 0.01 if market_freeze else 0.003
    ev_net = ev_gross - slip - latency_cost - requote_cost
    fill_prob = 0.35 if market_freeze else max(0.5, 1.0 - latency / (alive + 0.5))
    conservative_ev = ev_net * fill_prob
    return ExecutionCostResult(
        displayed_odds=displayed_odds,
        simulated_fill_odds=fill_odds,
        slippage=slip,
        latency_seconds=latency,
        latency_cost=latency_cost,
        requote_cost=requote_cost,
        ev_gross=ev_gross,
        ev_net=ev_net,
        conservative_ev=conservative_ev,
        fill_probability=fill_prob,
    )

