"""
未来赛程压力
============
用 API-Football fixtures?team=&next=3 判断球队未来三场压力。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional


_CACHE: dict[int, dict] = {}


def _safe_response(resp: Optional[dict]) -> list:
    if not resp or not isinstance(resp, dict):
        return []
    data = resp.get("response")
    return data if isinstance(data, list) else []


def _parse_dt(text: str | None) -> Optional[datetime]:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _days_between(a: Optional[datetime], b: Optional[datetime]) -> Optional[float]:
    if not a or not b:
        return None
    return round((b - a).total_seconds() / 86400, 2)


def _team_schedule(team_id: int, api_client: Callable[[str], Optional[dict]]) -> dict:
    if team_id in _CACHE:
        return _CACHE[team_id]
    resp = api_client(f"fixtures?team={team_id}&next=3&timezone=Asia/Shanghai")
    fixtures = _safe_response(resp)
    rows = []
    for fx in fixtures:
        f = fx.get("fixture", {}) or {}
        lg = fx.get("league", {}) or {}
        teams = fx.get("teams", {}) or {}
        rows.append({
            "fixture_id": f.get("id"),
            "date": f.get("date"),
            "league": lg.get("name"),
            "home": teams.get("home", {}).get("name"),
            "away": teams.get("away", {}).get("name"),
        })
    out = {"team_id": team_id, "next": rows}
    _CACHE[team_id] = out
    return out


def evaluate_team_schedule_pressure(
    team_id: int,
    api_client: Callable[[str], Optional[dict]],
    *,
    current_kickoff: str | None = None,
) -> dict:
    data = _team_schedule(team_id, api_client)
    current_dt = _parse_dt(current_kickoff) or datetime.now(timezone.utc)
    next_rows = data.get("next", [])
    gaps = []
    for row in next_rows:
        gap = _days_between(current_dt, _parse_dt(row.get("date")))
        if gap is not None and gap >= 0:
            gaps.append(gap)
    min_gap = min(gaps) if gaps else None
    games_7d = sum(1 for x in gaps if x <= 7)
    games_10d = sum(1 for x in gaps if x <= 10)

    if min_gap is not None and min_gap <= 3 and games_7d >= 2:
        level = "HIGH"
        action = "WATCH_CAUTION"
        reason = "未来7天内赛程密集，存在轮换风险"
        score_delta = -4
    elif games_10d >= 3:
        level = "MEDIUM"
        action = "KEEP_CAUTION"
        reason = "未来10天三赛，轻微轮换风险"
        score_delta = -2
    else:
        level = "LOW"
        action = "KEEP"
        reason = "未来赛程压力正常"
        score_delta = 0

    return {
        "team_id": team_id,
        "level": level,
        "action": action,
        "reason": reason,
        "score_delta": score_delta,
        "min_gap_days": min_gap,
        "games_next_7d": games_7d,
        "games_next_10d": games_10d,
        "next": next_rows,
    }


def evaluate_match_schedule_pressure(
    fixture: dict,
    api_client: Callable[[str], Optional[dict]],
) -> dict:
    home_id = int(fixture.get("homeId") or fixture.get("home_id") or 0)
    away_id = int(fixture.get("awayId") or fixture.get("away_id") or 0)
    kickoff = fixture.get("kickoff")
    home = evaluate_team_schedule_pressure(home_id, api_client, current_kickoff=kickoff) if home_id else {}
    away = evaluate_team_schedule_pressure(away_id, api_client, current_kickoff=kickoff) if away_id else {}
    levels = {home.get("level"), away.get("level")}
    if "HIGH" in levels:
        action = "WATCH_CAUTION"
        level = "HIGH"
        reason = "至少一方未来赛程高压"
    elif "MEDIUM" in levels:
        action = "KEEP_CAUTION"
        level = "MEDIUM"
        reason = "至少一方未来赛程中等压力"
    else:
        action = "KEEP"
        level = "LOW"
        reason = "双方未来赛程压力正常"
    return {
        "level": level,
        "action": action,
        "reason": reason,
        "home": home,
        "away": away,
    }
