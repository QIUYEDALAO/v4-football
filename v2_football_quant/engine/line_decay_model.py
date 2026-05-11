from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MinuteEdge:
    minute: int
    market_prob: float
    true_prob: float
    edge: float


@dataclass
class DecayResult:
    best_entry_minute: int
    best_entry_window: str
    min_acceptable_odds: float
    max_acceptable_line: float
    confidence: float
    points: list[MinuteEdge]

    def to_dict(self) -> dict:
        return {
            "best_entry_minute": self.best_entry_minute,
            "best_entry_window": self.best_entry_window,
            "min_acceptable_odds": round(self.min_acceptable_odds, 3),
            "max_acceptable_line": round(self.max_acceptable_line, 2),
            "confidence": round(self.confidence, 3),
            "points": [
                {
                    "minute": p.minute,
                    "market_prob": round(p.market_prob, 5),
                    "true_prob": round(p.true_prob, 5),
                    "edge": round(p.edge, 5),
                }
                for p in self.points
            ],
        }


def estimate_best_entry_window(
    *,
    current_minute: int,
    base_true_prob: float,
    displayed_odds: float,
    line: float,
) -> DecayResult:
    points: list[MinuteEdge] = []
    best = None
    for m in range(6, 19):
        market_prob = min(0.95, max(0.05, 1.0 / max(1.01, displayed_odds + (m - current_minute) * 0.03)))
        decay = max(0.65, 1.0 - (m - 6) * 0.02)
        true_prob = min(0.95, max(0.05, base_true_prob * decay))
        edge = true_prob - market_prob
        pt = MinuteEdge(m, market_prob, true_prob, edge)
        points.append(pt)
        if best is None or edge > best.edge:
            best = pt
    assert best is not None
    w0 = max(6, best.minute - 1)
    w1 = min(18, best.minute + 2)
    conf = min(0.9, max(0.45, 0.55 + best.edge))
    return DecayResult(
        best_entry_minute=best.minute,
        best_entry_window=f"{w0}-{w1}",
        min_acceptable_odds=max(1.5, displayed_odds - 0.08),
        max_acceptable_line=min(1.5, line + 0.25),
        confidence=conf,
        points=points,
    )

