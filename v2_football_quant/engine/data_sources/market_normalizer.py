from __future__ import annotations

import re
from typing import Optional

HT_OU_KEYWORDS = [
    "1st half goals",
    "first half goals",
    "half time goals",
    "1st half over/under",
    "first half over/under",
    "half time over/under",
    "1st half asian total",
    "asian total goals 1st half",
    "goal line 1st half",
]

LINE_ALLOWLIST = {0.5, 0.75, 1.0, 1.25, 1.5, 1.75}


def _as_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_line(value: float) -> float:
    return round(float(value), 2)


def extract_line(text: str) -> Optional[float]:
    nums = re.findall(r"\d+(?:\.\d+)?", text or "")
    if not nums:
        return None
    return _as_float(nums[-1])


def is_ht_ou_market_name(name: str) -> bool:
    lower = (name or "").strip().lower()
    if not lower:
        return False
    if any(k in lower for k in HT_OU_KEYWORDS):
        return True
    # 兜底匹配：半场 + 大小
    has_half = any(k in lower for k in ("1st half", "first half", "half time", "ht", "上半"))
    has_ou = any(k in lower for k in ("over/under", "over under", "goal line", "asian total", "大小", "大/小"))
    return has_half and has_ou


def is_allowed_line(line: Optional[float]) -> bool:
    if line is None:
        return False
    return normalize_line(line) in LINE_ALLOWLIST
