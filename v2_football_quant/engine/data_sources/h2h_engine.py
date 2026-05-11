"""
V4 H2H 引擎 — 基于 API-Football 历史交锋的多维画像
======================================================
核心因子: 近3年历史交锋上半场有进球率 ≥ 70% + 全场0-0 ≤ 2场
时间红线: 只取2020年起的交锋记录（斩断过期噪音）
辅助因子: 进球时间分桶 (time_bins) + 近期战绩交叉验证 (recent form) + 场均进球
近期动能门: (主队近5场HT有球率 + 客队近5场HT有球率) / 2 ≥ 70%

用法:
  from engine.data_sources.h2h_engine import evaluate_h2h_edge
  result = evaluate_h2h_edge(home_id, away_id, api_func)
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("V4_H2H_Engine")

H2H_YEAR_CUTOFF = 2020
H2H_MIN_SAMPLES = 3


def _parse_goal_events(api_client, fixture_id: int) -> dict:
    bins = {"0_15": False, "16_30": False, "31_45": False}
    try:
        resp = api_client(f"fixtures/events?fixture={fixture_id}")
        if not resp or "response" not in resp:
            return bins
        for event in resp["response"]:
            if event.get("type") != "Goal":
                continue
            elapsed = event.get("time", {}).get("elapsed", 0) or 0
            if elapsed > 45:
                continue
            if elapsed <= 15:
                bins["0_15"] = True
            elif elapsed <= 30:
                bins["16_30"] = True
            else:
                bins["31_45"] = True
    except Exception:
        pass
    return bins


def _query_recent_ht_over(api_client, team_id: int, last_n: int = 5) -> tuple:
    """查询某队最近 N 场完赛的上半场有球率和场均进球。Returns: (rate, avg_goals)"""
    try:
        resp = api_client(f"fixtures?team={team_id}&last={last_n}&status=FT")
        if not resp or "response" not in resp:
            return 0.0, 0.0
        matches = resp["response"]
        if not matches:
            return 0.0, 0.0
        ht_over = 0
        total_goals = 0
        for m in matches:
            ht = m.get("score", {}).get("halftime", {})
            h = ht.get("home") if ht and ht.get("home") is not None else 0
            a = ht.get("away") if ht and ht.get("away") is not None else 0
            total_goals += (h + a)
            if (h + a) > 0:
                ht_over += 1
        n = len(matches)
        return round(ht_over / n, 3), round(total_goals / n, 2)
    except Exception:
        return 0.0, 0.0


def evaluate_h2h_edge(home_id: int, away_id: int, api_client) -> dict:
    endpoint = f"fixtures/headtohead?h2h={home_id}-{away_id}"
    resp = api_client(endpoint)

    if not resp or "response" not in resp:
        return {"valid": False, "reason": "API_ERROR"}

    matches = resp["response"]
    total_h2h = len(matches)

    cutoff = datetime(H2H_YEAR_CUTOFF, 1, 1, tzinfo=timezone.utc)

    def _match_timestamp(m):
        ts = m.get("fixture", {}).get("timestamp", 0)
        if not ts:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    recent_3y = [m for m in matches if _match_timestamp(m) >= cutoff]
    n_3y = len(recent_3y)

    if n_3y < H2H_MIN_SAMPLES:
        return {"valid": False, "reason": f"时间窗内样本不足 (2020年以来仅{n_3y}场 < {H2H_MIN_SAMPLES})"}

    recent = sorted(recent_3y, key=lambda x: _match_timestamp(x), reverse=True)[:10]
    n = len(recent)

    ht_goal_count = 0
    ft_zero_count = 0
    total_ht_goals = 0
    expired_count = total_h2h - n_3y

    for m in recent:
        score = m.get("score", {})
        ht = score.get("halftime", {})
        ft = score.get("fulltime", {})
        ht_h = ht.get("home") if ht and ht.get("home") is not None else 0
        ht_a = ht.get("away") if ht and ht.get("away") is not None else 0
        ft_h = ft.get("home") if ft and ft.get("home") is not None else 0
        ft_a = ft.get("away") if ft and ft.get("away") is not None else 0
        total_ht_goals += (ht_h + ht_a)
        if (ht_h + ht_a) > 0:
            ht_goal_count += 1
        if (ft_h + ft_a) == 0:
            ft_zero_count += 1

    ht_rate = ht_goal_count / n
    avg_ht_goals = round(total_ht_goals / n, 2)

    if ht_rate < 0.7 or ft_zero_count > 2:
        return {"valid": False, "reason": f"未达标 (HT有球率={ht_rate:.0%}, 0-0场次={ft_zero_count})"}

    # 进球时间分桶
    time_bins = {"0_15": 0, "16_30": 0, "31_45": 0}
    for m in recent:
        fid = m.get("fixture", {}).get("id")
        if not fid:
            continue
        try:
            bins = _parse_goal_events(api_client, fid)
            if bins["0_15"]: time_bins["0_15"] += 1
            if bins["16_30"]: time_bins["16_30"] += 1
            if bins["31_45"]: time_bins["31_45"] += 1
        except Exception:
            pass
        time.sleep(0.15)

    for k in time_bins:
        time_bins[k] = round(time_bins[k] / n, 3)

    # 近期战绩（含场均进球）
    home_recent_ht_over, home_recent_avg_goals = _query_recent_ht_over(api_client, home_id, last_n=5)
    time.sleep(0.3)
    away_recent_ht_over, away_recent_avg_goals = _query_recent_ht_over(api_client, away_id, last_n=5)
    time.sleep(0.3)

    recent_form_avg = (home_recent_ht_over + away_recent_ht_over) / 2
    if recent_form_avg < 0.7:
        return {"valid": False, "reason": f"近期动能不足 (主{home_recent_ht_over:.0%}+客{away_recent_ht_over:.0%})/2={recent_form_avg:.0%} < 70%"}

    return {
        "valid": True,
        "strategy_id": "V4_FACTOR_EXPLORE",
        "market_type": "HT_OU_1.0",
        "factors": {
            "h2h_ht_goal_rate": round(ht_rate, 3),
            "h2h_avg_ht_goals": avg_ht_goals,
            "h2h_sample_size": n,
            "h2h_total": total_h2h,
            "h2h_3y_count": n_3y,
            "h2h_expired": expired_count,
            "ft_0_0_count": ft_zero_count,
            "time_bins": time_bins,
            "home_recent_ht_over": home_recent_ht_over,
            "home_recent_avg_goals": home_recent_avg_goals,
            "away_recent_ht_over": away_recent_ht_over,
            "away_recent_avg_goals": away_recent_avg_goals,
            "recent_form_avg": round(recent_form_avg, 3),
        },
        "metrics": {
            "h2h_total": total_h2h,
            "h2h_3y_count": n_3y,
            "h2h_analyzed": n,
            "h2h_expired": expired_count,
            "ht_goal_rate": round(ht_rate, 3),
            "ft_0_0_count": ft_zero_count,
        }
    }
