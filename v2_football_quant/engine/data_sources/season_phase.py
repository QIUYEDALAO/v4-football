"""
赛季阶段推导
============
用 API-Football 联赛赛季 fixtures 推导当前比赛处于:
  EARLY / MID / LATE / FINAL_ROUND / UNKNOWN

这个模块不依赖排名，只判断赛季进度。排名和战意放在任务11。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from engine.data_sources.api_coverage import infer_season


_PHASE_CACHE: dict[tuple[int, int], dict] = {}


def _safe_response(resp: Optional[dict]) -> list:
    if not resp or not isinstance(resp, dict):
        return []
    data = resp.get("response")
    return data if isinstance(data, list) else []


def _fixture_ts(row: dict) -> int:
    return int(row.get("fixture", {}).get("timestamp") or 0)


def _kickoff_ts(kickoff: str | None) -> int:
    if not kickoff:
        return 0
    try:
        dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        return 0


def _status(row: dict) -> str:
    return str(row.get("fixture", {}).get("status", {}).get("short") or "")


def _empty_phase(league_id: int, season: int, reason: str) -> dict:
    return {
        "league_id": int(league_id),
        "season": int(season),
        "phase": "UNKNOWN",
        "progress_pct": 0.0,
        "completed": 0,
        "total": 0,
        "remaining": 0,
        "remaining_rounds_est": None,
        "adjustment": {"action": "KEEP", "score_delta": 0, "reason": reason},
        "reason": reason,
    }


def classify_phase(progress_pct: float, remaining_rounds_est: Optional[float]) -> str:
    if remaining_rounds_est is not None and remaining_rounds_est <= 3:
        return "FINAL_ROUND"
    if progress_pct < 0.20:
        return "EARLY"
    if progress_pct < 0.75:
        return "MID"
    return "LATE"


def phase_adjustment(phase: str) -> dict:
    if phase == "EARLY":
        return {
            "action": "CAUTION",
            "score_delta": -3,
            "reason": "赛季初期，球队状态样本未稳定",
        }
    if phase == "MID":
        return {
            "action": "KEEP",
            "score_delta": 0,
            "reason": "赛季中期，近期状态可信度较高",
        }
    if phase == "LATE":
        return {
            "action": "NEED_MOTIVATION_CHECK",
            "score_delta": -1,
            "reason": "赛季后段，需结合排名和战意",
        }
    if phase == "FINAL_ROUND":
        return {
            "action": "REQUIRE_MOTIVATION",
            "score_delta": -4,
            "reason": "最后三轮，必须结合战意过滤",
        }
    return {
        "action": "KEEP",
        "score_delta": 0,
        "reason": "赛季阶段未知，暂不调整",
    }


def compute_season_phase(
    league_id: int,
    season: int,
    api_client: Callable[[str], Optional[dict]],
    *,
    kickoff: str | None = None,
) -> dict:
    key = (int(league_id), int(season))
    if key not in _PHASE_CACHE:
        resp = api_client(f"fixtures?league={league_id}&season={season}&timezone=Asia/Shanghai")
        rows = _safe_response(resp)
        if not rows:
            _PHASE_CACHE[key] = _empty_phase(league_id, season, "NO_SEASON_FIXTURES")
        else:
            _PHASE_CACHE[key] = {"rows": rows}

    cached = _PHASE_CACHE[key]
    if "rows" not in cached:
        return cached

    rows = sorted(cached["rows"], key=_fixture_ts)
    total = len(rows)
    current_ts = _kickoff_ts(kickoff) or int(datetime.now(timezone.utc).timestamp())
    completed_statuses = {"FT", "AET", "PEN", "WO"}
    completed_before = [
        row for row in rows
        if _status(row) in completed_statuses and _fixture_ts(row) < current_ts
    ]
    remaining_from_current = [row for row in rows if _fixture_ts(row) >= current_ts]
    completed = len(completed_before)
    remaining = max(total - completed, 0)
    progress_pct = round(completed / total, 3) if total else 0.0

    teams = set()
    for row in rows:
        home_id = row.get("teams", {}).get("home", {}).get("id")
        away_id = row.get("teams", {}).get("away", {}).get("id")
        if home_id:
            teams.add(home_id)
        if away_id:
            teams.add(away_id)
    matches_per_round = max(len(teams) / 2, 1) if teams else None
    remaining_rounds_est = (
        round(len(remaining_from_current) / matches_per_round, 1)
        if matches_per_round
        else None
    )
    phase = classify_phase(progress_pct, remaining_rounds_est)

    return {
        "league_id": int(league_id),
        "season": int(season),
        "phase": phase,
        "progress_pct": progress_pct,
        "completed": completed,
        "total": total,
        "remaining": remaining,
        "remaining_rounds_est": remaining_rounds_est,
        "first_fixture_ts": _fixture_ts(rows[0]) if rows else None,
        "last_fixture_ts": _fixture_ts(rows[-1]) if rows else None,
        "adjustment": phase_adjustment(phase),
        "computed_at": datetime.now().isoformat(),
    }


def season_phase_for_fixture(fixture: dict, api_client: Callable[[str], Optional[dict]]) -> dict:
    league_id = int(fixture.get("league") or fixture.get("league_id") or 0)
    season = int(fixture.get("season") or infer_season(fixture.get("kickoff")))
    if not league_id:
        return _empty_phase(0, season, "NO_LEAGUE_ID")
    return compute_season_phase(league_id, season, api_client, kickoff=fixture.get("kickoff"))
