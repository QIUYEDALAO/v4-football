from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LeagueThreshold:
    league_id: str
    league_name: str
    sample_size: int
    league_ht_baseline: float
    model_edge: float
    recommended_min_score: float
    recommended_min_ev: float
    confidence_level: str
    status: str  # AUTO_TRADE / PAPER_ONLY / WATCH_ONLY / DISABLED

    def to_dict(self) -> dict:
        return {
            "league_id": self.league_id,
            "league_name": self.league_name,
            "sample_size": self.sample_size,
            "league_ht_baseline": round(self.league_ht_baseline, 4),
            "model_edge": round(self.model_edge, 6),
            "recommended_min_score": round(self.recommended_min_score, 2),
            "recommended_min_ev": round(self.recommended_min_ev, 6),
            "confidence_level": self.confidence_level,
            "status": self.status,
        }


def league_threshold(
    *,
    league_id: str,
    league_name: str,
    sample_size: int,
    league_ht_baseline: float,
    model_edge: float,
) -> LeagueThreshold:
    s = int(sample_size or 0)
    b = float(league_ht_baseline or 0.0)
    e = float(model_edge or 0.0)
    if s >= 150 and e > 0.01 and b >= 0.65:
        status = "AUTO_TRADE"
        conf = "HIGH"
        min_score = 62.0
        min_ev = 0.005
    elif s >= 80 and e > -0.005:
        status = "PAPER_ONLY"
        conf = "MEDIUM"
        min_score = 66.0
        min_ev = 0.01
    elif s >= 30:
        status = "WATCH_ONLY"
        conf = "LOW"
        min_score = 70.0
        min_ev = 0.015
    else:
        status = "WATCH_ONLY"
        conf = "LOW"
        min_score = 72.0
        min_ev = 0.02
    if e < -0.03 and s >= 50:
        status = "DISABLED"
        conf = "LOW"
        min_ev = 0.03
    return LeagueThreshold(
        league_id=league_id,
        league_name=league_name,
        sample_size=s,
        league_ht_baseline=b,
        model_edge=e,
        recommended_min_score=min_score,
        recommended_min_ev=min_ev,
        confidence_level=conf,
        status=status,
    )

