"""
排名与战意过滤
==============
基于 API-Football standings 判断球队是否处于:
  - 争冠 / 洲际资格 / 升级附加赛
  - 保级压力
  - 中游安全区

任务边界:
  - 本模块只做 standings 层面的战意判断
  - 赛季阶段由 season_phase.py 提供
"""

from __future__ import annotations

from typing import Callable, Optional

from engine.data_sources.api_coverage import infer_season


_STANDINGS_CACHE: dict[tuple[int, int], list[dict]] = {}


HIGH_TAGS = {
    "TITLE_RACE",
    "CONTINENT_RACE",
    "PROMOTION_RACE",
    "PLAYOFF_RACE",
    "RELEGATION_RISK",
}


def _safe_response(resp: Optional[dict]) -> list:
    if not resp or not isinstance(resp, dict):
        return []
    data = resp.get("response")
    return data if isinstance(data, list) else []


def _norm(text: str | None) -> str:
    return (text or "").lower()


def _flatten_standings(resp: Optional[dict]) -> list[dict]:
    rows = []
    for item in _safe_response(resp):
        league = item.get("league", {}) or {}
        standings = league.get("standings", []) or []
        for group_rows in standings:
            if isinstance(group_rows, dict):
                group_rows = [group_rows]
            for row in group_rows or []:
                normalized = dict(row)
                normalized["_league_name"] = league.get("name")
                normalized["_league_id"] = league.get("id")
                rows.append(normalized)
    return sorted(rows, key=lambda x: int(x.get("rank") or 999))


def fetch_standings(api_client: Callable[[str], Optional[dict]], league_id: int, season: int) -> list[dict]:
    key = (int(league_id), int(season))
    if key in _STANDINGS_CACHE:
        return _STANDINGS_CACHE[key]
    resp = api_client(f"standings?league={league_id}&season={season}")
    rows = _flatten_standings(resp)
    _STANDINGS_CACHE[key] = rows
    return rows


def _team_id(row: dict) -> Optional[int]:
    tid = row.get("team", {}).get("id")
    return int(tid) if tid is not None else None


def _points(row: dict) -> int:
    return int(row.get("points") or 0)


def _rank(row: dict) -> int:
    return int(row.get("rank") or 999)


def _description_tags(description: str) -> set[str]:
    text = _norm(description)
    tags = set()
    if any(k in text for k in ("relegation", "降级")):
        tags.add("RELEGATION_RISK")
    if any(k in text for k in ("champions league", "europa", "conference league", "libertadores", "sudamericana", "afc champions", "concacaf champions", "caf champions")):
        tags.add("CONTINENT_RACE")
    if any(k in text for k in ("promotion", "promoted", "升级")):
        tags.add("PROMOTION_RACE")
    if any(k in text for k in ("playoff", "play-off", "playoffs", "附加赛")):
        tags.add("PLAYOFF_RACE")
    if any(k in text for k in ("champion", "winner", "title", "冠军")) and "league" not in text:
        tags.add("TITLE_RACE")
    return tags


def _near_relegation(row: dict, standings: list[dict], danger_count: int = 3, points_window: int = 6) -> bool:
    if not standings:
        return False
    rank = _rank(row)
    total = len(standings)
    if rank >= max(1, total - danger_count + 1):
        return True
    safe_boundary_rank = max(1, total - danger_count)
    boundary = next((x for x in standings if _rank(x) == safe_boundary_rank), None)
    if not boundary:
        return False
    return rank == safe_boundary_rank and (_points(row) - _points(boundary)) <= points_window


def _near_title(row: dict, standings: list[dict], points_window: int = 6) -> bool:
    if not standings:
        return False
    leader = standings[0]
    return _rank(row) <= 3 and (_points(leader) - _points(row)) <= points_window


def _mid_table_safe(row: dict, tags: set[str], standings: list[dict]) -> bool:
    if tags:
        return False
    rank = _rank(row)
    total = len(standings)
    if total < 8:
        return False
    return 4 < rank < max(5, total - 3)


def classify_team_motivation(row: Optional[dict], standings: list[dict]) -> dict:
    if not row:
        return {
            "team_id": None,
            "rank": None,
            "points": None,
            "description": "",
            "tags": ["UNKNOWN_STANDING"],
            "score": 0,
            "level": "UNKNOWN",
        }

    tags = _description_tags(row.get("description"))
    if _near_title(row, standings):
        tags.add("TITLE_RACE")
    if _near_relegation(row, standings):
        tags.add("RELEGATION_RISK")
    if _mid_table_safe(row, tags, standings):
        tags.add("MID_TABLE_SAFE")

    score = 45
    if "TITLE_RACE" in tags:
        score = max(score, 90)
    if "RELEGATION_RISK" in tags:
        score = max(score, 82)
    if "PROMOTION_RACE" in tags:
        score = max(score, 82)
    if "CONTINENT_RACE" in tags:
        score = max(score, 76)
    if "PLAYOFF_RACE" in tags:
        score = max(score, 68)
    if "MID_TABLE_SAFE" in tags:
        score = min(score, 25)

    level = "HIGH" if score >= 70 else "MEDIUM" if score >= 45 else "LOW"
    return {
        "team_id": _team_id(row),
        "team": row.get("team", {}).get("name"),
        "rank": _rank(row),
        "points": _points(row),
        "goals_diff": row.get("goalsDiff"),
        "description": row.get("description") or "",
        "tags": sorted(tags),
        "score": score,
        "level": level,
    }


def _gate_action(phase: str, home: dict, away: dict) -> dict:
    tags = set(home.get("tags", [])) | set(away.get("tags", []))
    high_count = sum(1 for side in (home, away) if set(side.get("tags", [])) & HIGH_TAGS)
    both_safe = (
        "MID_TABLE_SAFE" in home.get("tags", [])
        and "MID_TABLE_SAFE" in away.get("tags", [])
    )
    max_score = max(int(home.get("score", 0)), int(away.get("score", 0)))
    avg_score = round((int(home.get("score", 0)) + int(away.get("score", 0))) / 2, 1)

    if "UNKNOWN_STANDING" in tags and phase in ("LATE", "FINAL_ROUND"):
        return {
            "action": "WATCH_ONLY",
            "score": avg_score,
            "reason": "赛季后段缺少排名数据，降级观察",
        }
    if phase in ("LATE", "FINAL_ROUND"):
        if both_safe:
            return {
                "action": "WATCH_ONLY",
                "score": avg_score,
                "reason": "双方中游安全区，战意不足",
            }
        if high_count >= 2:
            return {
                "action": "BOOST",
                "score": max(85, avg_score),
                "reason": "双方都有明确排名目标",
            }
        if high_count == 1 or max_score >= 70:
            return {
                "action": "ALLOW_V4_LIVE",
                "score": max(70, max_score),
                "reason": "至少一方有明确排名目标",
            }
        return {
            "action": "WATCH_ONLY",
            "score": avg_score,
            "reason": "赛季后段但排名目标不清晰",
        }

    if high_count >= 2:
        return {"action": "BOOST", "score": max(80, avg_score), "reason": "双方战意较强"}
    if high_count == 1:
        return {"action": "KEEP", "score": max(60, max_score), "reason": "单方战意较强"}
    return {"action": "KEEP", "score": avg_score, "reason": "非赛季末，排名因素不强制过滤"}


def evaluate_match_motivation(
    fixture: dict,
    api_client: Callable[[str], Optional[dict]],
    *,
    season_phase: Optional[dict] = None,
) -> dict:
    league_id = int(fixture.get("league") or fixture.get("league_id") or 0)
    season = int(fixture.get("season") or infer_season(fixture.get("kickoff")))
    home_id = int(fixture.get("homeId") or fixture.get("home_id") or 0)
    away_id = int(fixture.get("awayId") or fixture.get("away_id") or 0)
    phase = (season_phase or {}).get("phase", "UNKNOWN")

    if not league_id:
        return {
            "league_id": 0,
            "season": season,
            "phase": phase,
            "gate": {"action": "KEEP", "score": 0, "reason": "NO_LEAGUE_ID"},
            "home": classify_team_motivation(None, []),
            "away": classify_team_motivation(None, []),
        }

    standings = fetch_standings(api_client, league_id, season)
    home_row = next((x for x in standings if _team_id(x) == home_id), None)
    away_row = next((x for x in standings if _team_id(x) == away_id), None)
    home = classify_team_motivation(home_row, standings)
    away = classify_team_motivation(away_row, standings)
    gate = _gate_action(phase, home, away)

    return {
        "league_id": league_id,
        "season": season,
        "phase": phase,
        "standings_sample_size": len(standings),
        "home": home,
        "away": away,
        "gate": gate,
        "match_tags": sorted(set(home.get("tags", [])) | set(away.get("tags", []))),
    }
