"""
赛中前10分钟节奏判断
====================
基于 API-Football:
  - fixtures/statistics?fixture=
  - fixtures/events?fixture=

用于 V4 走地入场前的最后一道轻量闸门。
"""

from __future__ import annotations

from typing import Callable, Optional


def _safe_response(resp: Optional[dict]) -> list:
    if not resp or not isinstance(resp, dict):
        return []
    data = resp.get("response")
    return data if isinstance(data, list) else []


def _num(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, str):
        value = value.replace("%", "").strip()
    try:
        return float(value)
    except Exception:
        return 0.0


def _stat_map(stats_resp: dict) -> dict:
    totals = {
        "shots_on_goal": 0.0,
        "total_shots": 0.0,
        "corners": 0.0,
        "attacks": 0.0,
        "dangerous_attacks": 0.0,
    }
    for team_stats in _safe_response(stats_resp):
        for item in team_stats.get("statistics", []) or []:
            name = str(item.get("type") or "").lower()
            value = _num(item.get("value"))
            if "shots on goal" in name or "shots on target" in name:
                totals["shots_on_goal"] += value
            elif "total shots" in name:
                totals["total_shots"] += value
            elif "corner" in name:
                totals["corners"] += value
            elif name == "attacks":
                totals["attacks"] += value
            elif "dangerous attacks" in name:
                totals["dangerous_attacks"] += value
    return totals


def _red_cards(events_resp: dict, max_minute: int = 15) -> int:
    count = 0
    for event in _safe_response(events_resp):
        elapsed = int(event.get("time", {}).get("elapsed") or 0)
        if elapsed > max_minute:
            continue
        detail = str(event.get("detail") or "").lower()
        event_type = str(event.get("type") or "").lower()
        if "card" in event_type and "red" in detail:
            count += 1
    return count


def evaluate_live_tempo(
    fixture_id: int,
    api_client: Callable[[str], Optional[dict]],
    *,
    minute: Optional[int] = None,
) -> dict:
    stats_resp = api_client(f"fixtures/statistics?fixture={fixture_id}")
    events_resp = api_client(f"fixtures/events?fixture={fixture_id}")
    stats = _stat_map(stats_resp or {})
    reds = _red_cards(events_resp or {}, max_minute=max(int(minute or 15), 15))

    has_stats = any(v > 0 for v in stats.values())
    if reds > 0:
        return {
            "signal": "RED_CARD",
            "action": "SKIP",
            "reason": "前段出现红牌，跳过",
            "red_cards": reds,
            "stats": stats,
            "has_stats": has_stats,
        }

    if not has_stats:
        return {
            "signal": "TEMPO_UNKNOWN",
            "action": "ALLOW",
            "reason": "缺少赛中统计，按盘口和比分继续判断",
            "red_cards": reds,
            "stats": stats,
            "has_stats": False,
        }

    pressure_score = 0
    pressure_score += min(stats["total_shots"] / 3.0, 1.0) * 35
    pressure_score += min(stats["shots_on_goal"] / 1.0, 1.0) * 25
    pressure_score += min(stats["corners"] / 1.0, 1.0) * 15
    pressure_score += min(stats["dangerous_attacks"] / 12.0, 1.0) * 25
    pressure_score = round(pressure_score, 1)

    if pressure_score >= 45:
        signal = "TEMPO_OK"
        action = "ALLOW"
        reason = "前段节奏达标"
    else:
        signal = "TEMPO_DULL"
        action = "SKIP"
        reason = "前段节奏偏沉闷"

    return {
        "signal": signal,
        "action": action,
        "reason": reason,
        "pressure_score": pressure_score,
        "red_cards": reds,
        "stats": stats,
        "has_stats": has_stats,
    }
