from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AsianEvResult:
    line: float
    odds: float
    p0: float
    p1: float
    p2plus: float
    ev: float
    expected_pnl_per_1u: float
    kelly_fraction: float

    def to_dict(self) -> dict:
        return {
            "line": self.line,
            "odds": self.odds,
            "p0": round(self.p0, 6),
            "p1": round(self.p1, 6),
            "p2plus": round(self.p2plus, 6),
            "ev": round(self.ev, 6),
            "expected_pnl_per_1u": round(self.expected_pnl_per_1u, 6),
            "kelly_fraction": round(self.kelly_fraction, 6),
        }


def _norm_probs(p0: float, p1: float, p2plus: float) -> tuple[float, float, float]:
    s = max(p0 + p1 + p2plus, 1e-12)
    return p0 / s, p1 / s, p2plus / s


def over_asian_ev(line: float, odds: float, p0: float, p1: float, p2plus: float) -> AsianEvResult:
    p0, p1, p2plus = _norm_probs(p0, p1, p2plus)
    b = odds - 1.0
    if line == 0.75:
        ev = p0 * (-1.0) + p1 * (0.5 * b) + p2plus * b
    elif line == 1.0:
        ev = p0 * (-1.0) + p1 * 0.0 + p2plus * b
    elif line == 1.25:
        ev = p0 * (-1.0) + p1 * (-0.5) + p2plus * b
    elif line == 1.5:
        ev = (p0 + p1) * (-1.0) + p2plus * b
    else:
        raise ValueError(f"unsupported line: {line}")

    # Conservative proxy Kelly: collapse to binary (profit event vs non-profit event)
    p_win_like = p2plus if line >= 1.0 else (p1 * 0.5 + p2plus)
    q = 1.0 - p_win_like
    kelly = max(0.0, (b * p_win_like - q) / b) if b > 0 else 0.0
    return AsianEvResult(
        line=float(line),
        odds=float(odds),
        p0=p0,
        p1=p1,
        p2plus=p2plus,
        ev=ev,
        expected_pnl_per_1u=ev,
        kelly_fraction=min(kelly, 1.0),
    )

