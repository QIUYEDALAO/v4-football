from __future__ import annotations

from typing import Any, Callable, Optional


def _safe_get(resp: Optional[dict]) -> list[dict]:
    if not resp or not isinstance(resp, dict):
        return []
    rows = resp.get("response")
    return rows if isinstance(rows, list) else []


def fetch_fixture_context(fixture_id: int, api_get: Callable[[str], Optional[dict]]) -> dict[str, Any]:
    """
    P8 观测层：天气/场地/裁判。
    说明：API-Football天气字段覆盖不稳定，允许为空；先记录，再做边际检验。
    """
    rows = _safe_get(api_get(f"fixtures?id={fixture_id}"))
    if not rows:
        return {
            "weather": {"status": "UNAVAILABLE"},
            "pitch": {"status": "UNAVAILABLE"},
            "referee": {"status": "UNAVAILABLE"},
        }
    r = rows[0]
    fx = r.get("fixture", {}) or {}
    venue = fx.get("venue", {}) or {}
    league = r.get("league", {}) or {}

    # API-Football标准fixtures通常无稳定天气字段，先占位
    weather = {
        "status": "MISSING",
        "temperature": None,
        "rain_intensity": None,
        "wind_speed": None,
        "humidity": None,
        "weather_condition": None,
    }
    pitch = {
        "status": "PARTIAL",
        "grass_type": None,
        "artificial_turf": None,
        "pitch_condition": None,
        "stadium_altitude": None,
        "home_pitch_advantage": None,
        "venue_id": venue.get("id"),
        "venue_name": venue.get("name"),
        "venue_city": venue.get("city"),
    }
    referee = {
        "status": "PARTIAL" if fx.get("referee") else "MISSING",
        "referee_id": None,
        "referee_name": fx.get("referee"),
        "cards_per_game": None,
        "red_card_rate": None,
        "penalty_rate": None,
        "fouls_per_game": None,
        "first_half_card_rate": None,
    }
    return {
        "weather": weather,
        "pitch": pitch,
        "referee": referee,
        "league_country": league.get("country"),
    }

