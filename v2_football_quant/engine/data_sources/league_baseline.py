"""
联赛 HT/SH/FT 基准
=================
用 API-Football 已完赛 fixtures 计算联赛进球环境。

用途:
  - 不同联赛不能共用同一套 HT 阈值
  - V4 上半场走地需要知道该联赛本身是 HT 友好、中性，还是偏冷
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from engine.data_sources.api_coverage import infer_season


_BASELINE_CACHE: dict[tuple[int, int], dict] = {}

MIN_BASELINE_SAMPLE = 20
HT_FRIENDLY_RATE = 0.60
HT_COLD_RATE = 0.50


def _safe_response(resp: Optional[dict]) -> list:
    if not resp or not isinstance(resp, dict):
        return []
    data = resp.get("response")
    return data if isinstance(data, list) else []


def _score_pair(score: dict, key: str) -> tuple[int, int]:
    part = score.get(key, {}) or {}
    home = part.get("home") if part.get("home") is not None else 0
    away = part.get("away") if part.get("away") is not None else 0
    return int(home or 0), int(away or 0)


def _empty_baseline(league_id: int, season: int, reason: str) -> dict:
    return {
        "league_id": int(league_id),
        "season": int(season),
        "sample_size": 0,
        "ht_goal_rate": 0.0,
        "sh_goal_rate": 0.0,
        "ft_over_1_5_rate": 0.0,
        "avg_ht_goals": 0.0,
        "avg_sh_goals": 0.0,
        "avg_ft_goals": 0.0,
        "ht_env": "UNKNOWN",
        "sh_env": "UNKNOWN",
        "confidence": "LOW",
        "reason": reason,
    }


def classify_ht_env(ht_goal_rate: float, sample_size: int) -> str:
    if sample_size < MIN_BASELINE_SAMPLE:
        return "UNKNOWN"
    if ht_goal_rate >= HT_FRIENDLY_RATE:
        return "FRIENDLY"
    if ht_goal_rate < HT_COLD_RATE:
        return "COLD"
    return "NEUTRAL"


def classify_sh_env(sh_goal_rate: float, sample_size: int) -> str:
    if sample_size < MIN_BASELINE_SAMPLE:
        return "UNKNOWN"
    if sh_goal_rate >= 0.72:
        return "FRIENDLY"
    if sh_goal_rate < 0.60:
        return "COLD"
    return "NEUTRAL"


def baseline_adjustment(baseline: dict) -> dict:
    """返回对 V4 入池/评分的轻量调整建议。"""
    env = baseline.get("ht_env")
    sample_size = int(baseline.get("sample_size", 0) or 0)
    if sample_size < MIN_BASELINE_SAMPLE:
        return {
            "action": "KEEP",
            "score_delta": 0,
            "reason": "联赛样本不足，暂不调整",
        }
    if env == "FRIENDLY":
        return {
            "action": "BOOST",
            "score_delta": 3,
            "reason": "联赛HT环境友好",
        }
    if env == "COLD":
        return {
            "action": "WATCH_ONLY",
            "score_delta": -6,
            "reason": "联赛HT环境偏冷，自动监控降级为观察",
        }
    return {
        "action": "KEEP",
        "score_delta": 0,
        "reason": "联赛HT环境中性",
    }


def compute_league_baseline(
    league_id: int,
    season: int,
    api_client: Callable[[str], Optional[dict]],
    *,
    max_rows: int = 500,
) -> dict:
    key = (int(league_id), int(season))
    if key in _BASELINE_CACHE:
        return _BASELINE_CACHE[key]

    resp = api_client(f"fixtures?league={league_id}&season={season}&status=FT&timezone=Asia/Shanghai")
    rows = _safe_response(resp)
    if not rows:
        baseline = _empty_baseline(league_id, season, "NO_FINISHED_FIXTURES")
        _BASELINE_CACHE[key] = baseline
        return baseline

    rows = sorted(
        rows,
        key=lambda x: x.get("fixture", {}).get("timestamp", 0),
        reverse=True,
    )[:max_rows]

    ht_goal = 0
    sh_goal = 0
    ft_over_1_5 = 0
    total_ht_goals = 0
    total_sh_goals = 0
    total_ft_goals = 0
    usable = 0

    for row in rows:
        score = row.get("score", {}) or {}
        ht_h, ht_a = _score_pair(score, "halftime")
        ft_h, ft_a = _score_pair(score, "fulltime")
        ht_goals = ht_h + ht_a
        ft_goals = ft_h + ft_a
        if ft_goals == 0 and row.get("goals"):
            goals = row.get("goals", {}) or {}
            ft_goals = int(goals.get("home") or 0) + int(goals.get("away") or 0)
        sh_goals = max(0, ft_goals - ht_goals)
        usable += 1
        total_ht_goals += ht_goals
        total_sh_goals += sh_goals
        total_ft_goals += ft_goals
        if ht_goals > 0:
            ht_goal += 1
        if sh_goals > 0:
            sh_goal += 1
        if ft_goals >= 2:
            ft_over_1_5 += 1

    if usable == 0:
        baseline = _empty_baseline(league_id, season, "NO_USABLE_SCORE")
        _BASELINE_CACHE[key] = baseline
        return baseline

    ht_rate = round(ht_goal / usable, 3)
    sh_rate = round(sh_goal / usable, 3)
    baseline = {
        "league_id": int(league_id),
        "season": int(season),
        "sample_size": usable,
        "ht_goal_rate": ht_rate,
        "sh_goal_rate": sh_rate,
        "ft_over_1_5_rate": round(ft_over_1_5 / usable, 3),
        "avg_ht_goals": round(total_ht_goals / usable, 2),
        "avg_sh_goals": round(total_sh_goals / usable, 2),
        "avg_ft_goals": round(total_ft_goals / usable, 2),
        "ht_env": classify_ht_env(ht_rate, usable),
        "sh_env": classify_sh_env(sh_rate, usable),
        "confidence": "HIGH" if usable >= 80 else "MEDIUM" if usable >= MIN_BASELINE_SAMPLE else "LOW",
        "computed_at": datetime.now().isoformat(),
    }
    baseline["adjustment"] = baseline_adjustment(baseline)
    _BASELINE_CACHE[key] = baseline
    return baseline


def baseline_for_fixture(fixture: dict, api_client: Callable[[str], Optional[dict]]) -> dict:
    league_id = int(fixture.get("league") or fixture.get("league_id") or 0)
    season = int(fixture.get("season") or infer_season(fixture.get("kickoff")))
    if not league_id:
        return _empty_baseline(0, season, "NO_LEAGUE_ID")
    return compute_league_baseline(league_id, season, api_client)
