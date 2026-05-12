"""
API-Football 数据覆盖检查器
===========================
把“这场比赛理论上能不能支撑 V4”显式写进报告。

注意:
  - /odds/live 是实时端点，赛前无法证明一定有数据，只能标记为 MATCHTIME_CHECK。
  - lineups/statistics/events/injuries 的覆盖以 league-season coverage 为主。
  - 赛前盘口和 H2H 则用当前响应/已计算结果确认。
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional


_LEAGUE_COVERAGE_CACHE: dict[tuple[int, int], dict] = {}


def _safe_response(resp: Optional[dict]) -> list:
    if not resp or not isinstance(resp, dict):
        return []
    data = resp.get("response")
    return data if isinstance(data, list) else []


def _nested_bool(data: dict, path: tuple[str, ...]) -> bool:
    cur = data
    for key in path:
        if not isinstance(cur, dict):
            return False
        cur = cur.get(key, {})
    return bool(cur)


def infer_season(kickoff: str | None = None) -> int:
    """按自然年兜底推断 season。跨年联赛用 API 返回覆盖时会自行修正。"""
    if kickoff:
        try:
            return datetime.fromisoformat(kickoff.replace("Z", "+00:00")).year
        except Exception:
            pass
    return datetime.now().year


def fetch_league_coverage(api_client: Callable[[str], Optional[dict]], league_id: int, season: int) -> dict:
    key = (int(league_id), int(season))
    if key in _LEAGUE_COVERAGE_CACHE:
        return _LEAGUE_COVERAGE_CACHE[key]

    resp = api_client(f"leagues?id={league_id}&season={season}")
    rows = _safe_response(resp)
    coverage = {}
    if rows:
        coverage = rows[0].get("coverage", {}) or {}
    _LEAGUE_COVERAGE_CACHE[key] = coverage
    return coverage


def evaluate_fixture_coverage(
    fixture: dict,
    api_client: Callable[[str], Optional[dict]],
    *,
    h2h_result: Optional[dict] = None,
    pre_odds_resp: Optional[dict] = None,
    ht_ou_lines: Optional[list] = None,
) -> dict:
    league_id = int(fixture.get("league") or fixture.get("league_id") or 0)
    season = int(fixture.get("season") or infer_season(fixture.get("kickoff")))
    coverage = fetch_league_coverage(api_client, league_id, season) if league_id else {}

    factors = (h2h_result or {}).get("factors", {})
    has_h2h = bool(factors.get("h2h_sample_size", 0) > 0)
    has_recent_profile = bool(
        factors.get("home_recent_ht_over", 0) > 0
        or factors.get("away_recent_ht_over", 0) > 0
        or factors.get("home_recent_avg_goals", 0) > 0
        or factors.get("away_recent_avg_goals", 0) > 0
    )
    has_pre_odds = bool(ht_ou_lines) or bool(_safe_response(pre_odds_resp))

    supported = {
        "events": _nested_bool(coverage, ("fixtures", "events")),
        "lineups": _nested_bool(coverage, ("fixtures", "lineups")),
        "statistics": _nested_bool(coverage, ("fixtures", "statistics_fixtures")),
        "players": _nested_bool(coverage, ("players",)),
        "injuries": _nested_bool(coverage, ("injuries",)),
        "odds": _nested_bool(coverage, ("odds",)),
        "standings": _nested_bool(coverage, ("standings",)),
    }

    # Split "data observability" from "market tradability":
    # - coverage_level: 能否稳定拿到比分/事件/统计/阵容等结构化数据
    # - data_gate_action: 是否具备交易所需盘口条件（含赛前盘口）
    data_score = 0
    data_score += 2 if has_recent_profile else 0
    data_score += 1 if has_h2h else 0
    data_score += 1 if supported["events"] else 0
    data_score += 1 if supported["lineups"] else 0
    data_score += 1 if supported["statistics"] else 0
    data_score += 1 if supported["injuries"] else 0

    market_score = 0
    market_score += 2 if has_pre_odds else 0
    market_score += 1 if supported["odds"] else 0

    score = data_score + market_score

    if data_score >= 6:
        level = "FULL"
    elif data_score >= 4:
        level = "GOOD"
    elif data_score >= 2:
        level = "BASIC"
    else:
        level = "WEAK"

    if level == "WEAK":
        action = "SKIP_DATA_WEAK"
    elif has_pre_odds:
        action = "ALLOW_V4_LIVE"
    else:
        action = "WATCH_MARKET_MISSING"

    missing = []
    if not has_recent_profile:
        missing.append("recent_team_profile")
    if not has_pre_odds:
        missing.append("pre_match_odds")
    for key, enabled in supported.items():
        if key in ("players", "standings"):
            continue
        if not enabled:
            missing.append(key)

    return {
        "league_id": league_id,
        "season": season,
        "coverage_level": level,
        "data_gate_action": action,
        "score": score,
        "data_score": data_score,
        "market_score": market_score,
        "has_h2h": has_h2h,
        "has_recent_profile": has_recent_profile,
        "has_pre_odds": has_pre_odds,
        "live_odds_status": "MATCHTIME_CHECK",
        "supported": supported,
        "missing": missing,
    }
