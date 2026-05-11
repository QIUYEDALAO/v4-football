from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HazardProb:
    p0_goal: float
    p1_goal: float
    p2plus_goal: float

    def to_dict(self) -> dict:
        return {
            "p0_goal": round(self.p0_goal, 6),
            "p1_goal": round(self.p1_goal, 6),
            "p2plus_goal": round(self.p2plus_goal, 6),
        }


def estimate_ht_goal_probs(
    *,
    minute: int,
    league_ht_baseline: float,
    recent_attack_defense: float,
    h2h_rate: float,
    line: float,
    over_odds: float,
    no_red_card: bool = True,
    live_tempo_score: float = 0.5,
) -> HazardProb:
    """分钟条件概率（规则版，可迭代到统计学习版）。"""
    m = max(0, min(45, int(minute)))
    rem = max(1, 45 - m)
    base = 0.32 + 0.38 * league_ht_baseline + 0.20 * recent_attack_defense + 0.10 * h2h_rate
    time_adj = rem / 45.0
    odds_adj = max(0.85, min(1.15, 2.0 / max(1.01, over_odds)))
    line_adj = 1.08 if line <= 0.75 else (1.02 if line <= 1.0 else 0.95)
    tempo_adj = 0.9 + 0.25 * max(0.0, min(1.0, live_tempo_score))
    red_adj = 1.0 if no_red_card else 0.7
    p_any = max(0.05, min(0.92, base * time_adj * odds_adj * line_adj * tempo_adj * red_adj))

    # 分解为 0/1/2+
    p2 = max(0.03, min(0.45, p_any * (0.22 + 0.45 * live_tempo_score)))
    p1 = max(0.10, min(0.75, p_any - p2))
    p0 = max(0.0, 1.0 - p1 - p2)
    s = p0 + p1 + p2
    return HazardProb(p0 / s, p1 / s, p2 / s)

