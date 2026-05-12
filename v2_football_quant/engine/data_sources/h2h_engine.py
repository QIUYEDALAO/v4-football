"""
V4 比赛画像引擎 — H2H + 近期状态综合评估
======================================================
核心因子:
  - 上半场走地主策略: 近期球队 HT 能力为主，H2H 只做参考和风险控制
  - 下半场/全场: 独立参考方向，不混入上半场走地入池
时间红线: H2H 只取2020年起的交锋记录（斩断过期噪音）
辅助因子: H2H/近期进球时间分桶 + 近期 HT 进攻/防守交叉验证 + 场均进球

用法:
  from engine.data_sources.h2h_engine import evaluate_h2h_edge
  result = evaluate_h2h_edge(home_id, away_id, api_func)
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("V4_H2H_Engine")
_RECENT_PROFILE_CACHE: dict[tuple[int, int, bool], dict] = {}

H2H_YEAR_CUTOFF = 2020
H2H_REFERENCE_MIN_SAMPLES = 4
H2H_STRONG_SAMPLE_SIZE = 8
H2H_STRONG_RATE_MIN = 0.75
RECENT_HT_FORM_MIN = 0.70
RECENT_ATTACK_DEFENSE_MIN = 0.65
RECENT_TIMING_PRESSURE_MIN = 0.50
H2H_BAD_FLOOR_MIN = 0.50
HT_LIVE_SCORE_MIN = 0.50
# 性能开关：recent画像默认不再逐场拉 fixtures/events（保留 recent=5 样本深度）
# 进球时间分布仍由 H2H 主样本提供，避免 full 扫描在 valid 场次上超时。
RECENT_PROFILE_INCLUDE_EVENTS = False


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(value, 1.0)) * 100, 1)


def _score_market_fit(
    ht_rate: float,
    ht_goal_count: int,
    n: int,
    recent_form_avg: float,
    time_bins: dict,
    sh_rate: float,
    recent_sh_avg: float,
    second_half_bins: dict,
    ft_over_1_5_rate: float,
    recent_ft_over_1_5: float,
    avg_ft_goals: float,
    ht_attack_vs_defense: float = 0.0,
) -> dict:
    """
    输出三套独立分数，避免把 HT / SH / FT 混成一个热度。
    分数只是排序和展示用，主策略仍由硬门槛控制。
    """
    late_fh = max(
        time_bins.get("11_45", 0),
        time_bins.get("16_45", 0),
        time_bins.get("31_45", 0),
    )
    ht_sample_bonus = 1.0 if (n >= H2H_STRONG_SAMPLE_SIZE and ht_rate >= H2H_STRONG_RATE_MIN) else 0.0
    ht_score = (
        ht_rate * 0.40
        + recent_form_avg * 0.20
        + ht_attack_vs_defense * 0.10
        + late_fh * 0.20
        + ht_sample_bonus * 0.10
    )

    late_sh = max(second_half_bins.values()) if second_half_bins else 0.0
    sh_score = (
        sh_rate * 0.50
        + recent_sh_avg * 0.30
        + late_sh * 0.20
    )

    avg_ft_norm = min(avg_ft_goals / 4.0, 1.0)
    ft_score = (
        ft_over_1_5_rate * 0.50
        + recent_ft_over_1_5 * 0.30
        + avg_ft_norm * 0.20
    )

    scores = {
        "HT_LIVE_OVER": _clamp_score(ht_score),
        "SECOND_HALF_OVER": _clamp_score(sh_score),
        "FULLTIME_OVER": _clamp_score(ft_score),
    }
    best_focus = max(scores, key=scores.get)
    return {
        "scores": scores,
        "best_focus_by_score": best_focus,
        "best_score": scores[best_focus],
    }


def _parse_goal_events(api_client, fixture_id: int) -> dict:
    bins = {
        "0_10": False,
        "11_15": False,
        "0_15": False,
        "11_30": False,
        "11_45": False,
        "16_30": False,
        "16_45": False,
        "31_45": False,
        "46_60": False,
        "61_75": False,
        "76_90": False,
    }
    try:
        resp = api_client(f"fixtures/events?fixture={fixture_id}")
        if not resp or "response" not in resp:
            return bins
        for event in resp["response"]:
            if event.get("type") != "Goal":
                continue
            elapsed = event.get("time", {}).get("elapsed", 0) or 0
            if elapsed <= 10:
                bins["0_10"] = True
                bins["0_15"] = True
            elif elapsed <= 15:
                bins["11_15"] = True
                bins["0_15"] = True
                bins["11_30"] = True
                bins["11_45"] = True
            elif elapsed <= 30:
                bins["16_30"] = True
                bins["11_30"] = True
                bins["11_45"] = True
                bins["16_45"] = True
            elif elapsed <= 45:
                bins["31_45"] = True
                bins["11_45"] = True
                bins["16_45"] = True
            elif elapsed <= 60:
                bins["46_60"] = True
            elif elapsed <= 75:
                bins["61_75"] = True
            else:
                bins["76_90"] = True
    except Exception:
        pass
    return bins


def _query_recent_goal_profile(api_client, team_id: int, last_n: int = 5, include_events: bool = True) -> dict:
    """查询某队最近 N 场完赛的上下半场进球画像。"""
    cache_key = (int(team_id), int(last_n), bool(include_events))
    if cache_key in _RECENT_PROFILE_CACHE:
        return _RECENT_PROFILE_CACHE[cache_key]
    empty = {
        "ht_over": 0.0, "ht_avg": 0.0, "ht_scored": 0.0, "ht_conceded": 0.0,
        "ht_goals_for_avg": 0.0, "ht_goals_against_avg": 0.0,
        "sh_over": 0.0, "sh_avg": 0.0, "ft_over_1_5": 0.0,
        "time_bins": {
            "0_10": 0.0, "11_15": 0.0, "0_15": 0.0, "11_30": 0.0,
            "11_45": 0.0, "16_30": 0.0, "16_45": 0.0, "31_45": 0.0,
        },
        "second_half_bins": {"46_60": 0.0, "61_75": 0.0, "76_90": 0.0},
        "late_fh_pressure": 0.0,
        "early_only_flag": False,
    }
    try:
        resp = api_client(f"fixtures?team={team_id}&last={last_n}&status=FT")
        if not resp or "response" not in resp:
            _RECENT_PROFILE_CACHE[cache_key] = empty
            return empty
        matches = resp["response"]
        if not matches:
            _RECENT_PROFILE_CACHE[cache_key] = empty
            return empty
        ht_over = 0
        ht_scored = 0
        ht_conceded = 0
        sh_over = 0
        ft_over_1_5 = 0
        total_ht_goals = 0
        total_ht_for = 0
        total_ht_against = 0
        total_sh_goals = 0
        time_bin_counts = {k: 0 for k in empty["time_bins"]}
        second_half_counts = {k: 0 for k in empty["second_half_bins"]}
        for m in matches:
            fixture_id = m.get("fixture", {}).get("id")
            score = m.get("score", {})
            ht = score.get("halftime", {})
            ft = score.get("fulltime", {})
            teams = m.get("teams", {})
            home_id = teams.get("home", {}).get("id")
            away_id = teams.get("away", {}).get("id")
            is_home = str(home_id) == str(team_id)
            is_away = str(away_id) == str(team_id)
            ht_h = ht.get("home") if ht and ht.get("home") is not None else 0
            ht_a = ht.get("away") if ht and ht.get("away") is not None else 0
            ft_h = ft.get("home") if ft and ft.get("home") is not None else ht_h
            ft_a = ft.get("away") if ft and ft.get("away") is not None else ht_a
            if is_home:
                ht_for, ht_against = ht_h, ht_a
            elif is_away:
                ht_for, ht_against = ht_a, ht_h
            else:
                # 兜底：API 未返回 teams 时，只能保留总进球画像
                ht_for, ht_against = 0, 0
            ht_goals = ht_h + ht_a
            ft_goals = ft_h + ft_a
            sh_goals = max(0, ft_goals - ht_goals)
            total_ht_goals += ht_goals
            total_ht_for += ht_for
            total_ht_against += ht_against
            total_sh_goals += sh_goals
            if ht_goals > 0:
                ht_over += 1
            if ht_for > 0:
                ht_scored += 1
            if ht_against > 0:
                ht_conceded += 1
            if sh_goals > 0:
                sh_over += 1
            if ft_goals >= 2:
                ft_over_1_5 += 1
            if include_events and fixture_id:
                bins = _parse_goal_events(api_client, fixture_id)
                for key in time_bin_counts:
                    if bins.get(key):
                        time_bin_counts[key] += 1
                for key in second_half_counts:
                    if bins.get(key):
                        second_half_counts[key] += 1
        n = len(matches)
        time_bins = {k: round(v / n, 3) for k, v in time_bin_counts.items()}
        second_half_bins = {k: round(v / n, 3) for k, v in second_half_counts.items()}
        late_fh_pressure = round(
            (time_bins.get("11_45", 0) * 0.55)
            + (time_bins.get("16_45", 0) * 0.45),
            3,
        )
        early_only_flag = (
            time_bins.get("0_10", 0) >= 0.5
            and time_bins.get("11_45", 0) < 0.5
        )
        result = {
            "ht_over": round(ht_over / n, 3),
            "ht_avg": round(total_ht_goals / n, 2),
            "ht_scored": round(ht_scored / n, 3),
            "ht_conceded": round(ht_conceded / n, 3),
            "ht_goals_for_avg": round(total_ht_for / n, 2),
            "ht_goals_against_avg": round(total_ht_against / n, 2),
            "sh_over": round(sh_over / n, 3),
            "sh_avg": round(total_sh_goals / n, 2),
            "ft_over_1_5": round(ft_over_1_5 / n, 3),
            "time_bins": time_bins,
            "second_half_bins": second_half_bins,
            "late_fh_pressure": late_fh_pressure,
            "early_only_flag": early_only_flag,
        }
        _RECENT_PROFILE_CACHE[cache_key] = result
        return result
    except Exception:
        return empty
    _RECENT_PROFILE_CACHE[cache_key] = empty
    return empty


def evaluate_h2h_edge(home_id: int, away_id: int, api_client, mode: str = "full") -> dict:
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

    fast_mode = False
    recent_limit = 10
    recent = sorted(recent_3y, key=lambda x: _match_timestamp(x), reverse=True)[:recent_limit]
    n = len(recent)

    ht_goal_count = 0
    sh_goal_count = 0
    ft_over_1_5_count = 0
    ft_zero_count = 0
    total_ht_goals = 0
    total_sh_goals = 0
    total_ft_goals = 0
    expired_count = total_h2h - n_3y

    for m in recent:
        score = m.get("score", {})
        ht = score.get("halftime", {})
        ft = score.get("fulltime", {})
        ht_h = ht.get("home") if ht and ht.get("home") is not None else 0
        ht_a = ht.get("away") if ht and ht.get("away") is not None else 0
        ft_h = ft.get("home") if ft and ft.get("home") is not None else 0
        ft_a = ft.get("away") if ft and ft.get("away") is not None else 0
        ht_goals = ht_h + ht_a
        ft_goals = ft_h + ft_a
        sh_goals = max(0, ft_goals - ht_goals)
        total_ht_goals += ht_goals
        total_sh_goals += sh_goals
        total_ft_goals += ft_goals
        if ht_goals > 0:
            ht_goal_count += 1
        if sh_goals > 0:
            sh_goal_count += 1
        if ft_goals >= 2:
            ft_over_1_5_count += 1
        if ft_goals == 0:
            ft_zero_count += 1

    h2h_denominator = max(n, 1)
    ht_rate = ht_goal_count / h2h_denominator
    sh_rate = sh_goal_count / h2h_denominator
    ft_over_1_5_rate = ft_over_1_5_count / h2h_denominator
    avg_ht_goals = round(total_ht_goals / h2h_denominator, 2)
    avg_sh_goals = round(total_sh_goals / h2h_denominator, 2)
    avg_ft_goals = round(total_ft_goals / h2h_denominator, 2)

    # 进球时间分桶
    time_bins = {
        "0_10": 0,
        "11_15": 0,
        "0_15": 0,
        "11_30": 0,
        "11_45": 0,
        "16_30": 0,
        "16_45": 0,
        "31_45": 0,
    }
    second_half_bins = {"46_60": 0, "61_75": 0, "76_90": 0}
    for m in recent:
        fid = m.get("fixture", {}).get("id")
        if not fid:
            continue
        try:
            bins = _parse_goal_events(api_client, fid)
            if bins["0_10"]: time_bins["0_10"] += 1
            if bins["11_15"]: time_bins["11_15"] += 1
            if bins["0_15"]: time_bins["0_15"] += 1
            if bins["11_30"]: time_bins["11_30"] += 1
            if bins["11_45"]: time_bins["11_45"] += 1
            if bins["16_30"]: time_bins["16_30"] += 1
            if bins["16_45"]: time_bins["16_45"] += 1
            if bins["31_45"]: time_bins["31_45"] += 1
            if bins["46_60"]: second_half_bins["46_60"] += 1
            if bins["61_75"]: second_half_bins["61_75"] += 1
            if bins["76_90"]: second_half_bins["76_90"] += 1
        except Exception:
            pass

    for k in time_bins:
        time_bins[k] = round(time_bins[k] / h2h_denominator, 3)
    for k in second_half_bins:
        second_half_bins[k] = round(second_half_bins[k] / h2h_denominator, 3)

    late_fh_pressure = round(
        (time_bins.get("11_45", 0) * 0.55)
        + (time_bins.get("16_45", 0) * 0.45),
        3,
    )
    early_only_flag = (
        time_bins.get("0_10", 0) >= 0.5
        and time_bins.get("11_45", 0) < 0.5
    )
    pullback_fit = (
        "STRONG"
        if late_fh_pressure >= 0.70 and not early_only_flag
        else "OK"
        if late_fh_pressure >= 0.55 and not early_only_flag
        else "WEAK"
    )

    # 近期战绩（含场均进球）
    recent_last_n = 5
    home_recent = _query_recent_goal_profile(
        api_client,
        home_id,
        last_n=recent_last_n,
        include_events=(not fast_mode and RECENT_PROFILE_INCLUDE_EVENTS),
    )
    away_recent = _query_recent_goal_profile(
        api_client,
        away_id,
        last_n=recent_last_n,
        include_events=(not fast_mode and RECENT_PROFILE_INCLUDE_EVENTS),
    )

    recent_form_avg = (home_recent["ht_over"] + away_recent["ht_over"]) / 2
    recent_sh_avg = (home_recent["sh_over"] + away_recent["sh_over"]) / 2
    recent_ft_over_1_5 = (home_recent["ft_over_1_5"] + away_recent["ft_over_1_5"]) / 2
    home_attack_vs_away_defense = (
        home_recent["ht_scored"] * 0.55
        + away_recent["ht_conceded"] * 0.45
    )
    away_attack_vs_home_defense = (
        away_recent["ht_scored"] * 0.55
        + home_recent["ht_conceded"] * 0.45
    )
    ht_attack_vs_defense = round(max(home_attack_vs_away_defense, away_attack_vs_home_defense), 3)
    both_sides_ht_threat = round(
        (home_attack_vs_away_defense + away_attack_vs_home_defense) / 2,
        3,
    )
    recent_time_bins = {
        key: round((home_recent["time_bins"].get(key, 0) + away_recent["time_bins"].get(key, 0)) / 2, 3)
        for key in home_recent["time_bins"]
    }
    recent_second_half_bins = {
        key: round((home_recent["second_half_bins"].get(key, 0) + away_recent["second_half_bins"].get(key, 0)) / 2, 3)
        for key in home_recent["second_half_bins"]
    }
    recent_late_fh_pressure = round(
        (home_recent["late_fh_pressure"] + away_recent["late_fh_pressure"]) / 2,
        3,
    )
    # recent不拉events时，时间分布回退到H2H时间分布，避免“全0”误伤解释层
    if not RECENT_PROFILE_INCLUDE_EVENTS:
        recent_time_bins = dict(time_bins)
        recent_second_half_bins = dict(second_half_bins)
        recent_late_fh_pressure = late_fh_pressure
    recent_early_only_flag = (
        recent_time_bins.get("0_10", 0) >= 0.5
        and recent_time_bins.get("11_45", 0) < 0.5
    )
    recent_timing_fit = (
        "STRONG"
        if recent_late_fh_pressure >= 0.70 and not recent_early_only_flag
        else "OK"
        if recent_late_fh_pressure >= RECENT_TIMING_PRESSURE_MIN and not recent_early_only_flag
        else "WEAK"
    )

    score_pack = _score_market_fit(
        ht_rate=ht_rate,
        ht_goal_count=ht_goal_count,
        n=n,
        recent_form_avg=recent_form_avg,
        time_bins=time_bins,
        sh_rate=sh_rate,
        recent_sh_avg=recent_sh_avg,
        second_half_bins=second_half_bins,
        ft_over_1_5_rate=ft_over_1_5_rate,
        recent_ft_over_1_5=recent_ft_over_1_5,
        avg_ft_goals=avg_ft_goals,
        ht_attack_vs_defense=ht_attack_vs_defense,
    )

    h2h_strong_signal = (
        n >= H2H_STRONG_SAMPLE_SIZE
        and ht_rate >= H2H_STRONG_RATE_MIN
        and ft_zero_count <= 2
    )
    h2h_bad_signal = (
        n >= H2H_REFERENCE_MIN_SAMPLES
        and (ht_rate < H2H_BAD_FLOOR_MIN or ft_zero_count > 2)
    )
    recent_strength_pass = (
        recent_form_avg >= RECENT_HT_FORM_MIN
        or ht_attack_vs_defense >= RECENT_ATTACK_DEFENSE_MIN
        or both_sides_ht_threat >= RECENT_ATTACK_DEFENSE_MIN
    )
    recent_timing_pass = (
        recent_late_fh_pressure >= RECENT_TIMING_PRESSURE_MIN
        and not recent_early_only_flag
    )
    ht_score_floor_pass = score_pack["scores"].get("HT_LIVE_OVER", 0) >= HT_LIVE_SCORE_MIN * 100
    ht_is_best_focus = score_pack["best_focus_by_score"] == "HT_LIVE_OVER"
    ht_candidate = (
        recent_strength_pass
        and recent_timing_pass
        and ht_score_floor_pass
        and ht_is_best_focus
        and not h2h_bad_signal
    )
    sh_candidate = sh_rate >= 0.7 and avg_sh_goals >= 0.8 and recent_sh_avg >= 0.7
    ft_candidate = ft_over_1_5_rate >= 0.75 and avg_ft_goals >= 2.0 and recent_ft_over_1_5 >= 0.7

    if ht_candidate:
        market_focus = "HT_LIVE_OVER"
        market_type = "HT_OU_1.0"
    elif sh_candidate:
        market_focus = "SECOND_HALF_OVER"
        market_type = "SH_OU"
    elif ft_candidate:
        market_focus = "FULLTIME_OVER"
        market_type = "FT_OU"
    else:
        market_focus = None
        market_type = None

    if not (ht_candidate or sh_candidate or ft_candidate):
        return {
            "valid": False,
            "reason": (
                f"未达标 (近期HT={recent_form_avg:.0%}, 近期攻防={ht_attack_vs_defense:.0%}, "
                f"近期10-45压力={recent_late_fh_pressure:.0%}, H2H={ht_goal_count}/{n}={ht_rate:.0%}, "
                f"HT分={score_pack['scores'].get('HT_LIVE_OVER', 0):.1f}, 最强方向={score_pack['best_focus_by_score']}, "
                f"SH={sh_rate:.0%}/近期{recent_sh_avg:.0%}, FT2+={ft_over_1_5_rate:.0%})"
            )
        }

    phase_bias = "BALANCED"
    if sh_rate - ht_rate >= 0.15:
        phase_bias = "SECOND_HALF_BIAS"
    elif ht_rate - sh_rate >= 0.15:
        phase_bias = "FIRST_HALF_BIAS"

    return {
        "valid": True,
        "strategy_id": "V4_FACTOR_EXPLORE",
        "market_type": market_type,
        "market_focus": market_focus,
        "market_scores": score_pack["scores"],
        "best_focus_by_score": score_pack["best_focus_by_score"],
        "best_score": score_pack["best_score"],
        "factors": {
            "market_scores": score_pack["scores"],
            "best_focus_by_score": score_pack["best_focus_by_score"],
            "best_score": score_pack["best_score"],
            "h2h_ht_goal_rate": round(ht_rate, 3),
            "h2h_ht_goal_count": ht_goal_count,
            "h2h_reference_min_samples": H2H_REFERENCE_MIN_SAMPLES,
            "h2h_strong_signal": h2h_strong_signal,
            "h2h_bad_signal": h2h_bad_signal,
            "ht_strict_pass": ht_candidate,
            "ht_gate_model": "RECENT_FIRST_H2H_REFERENCE",
            "recent_strength_pass": recent_strength_pass,
            "recent_timing_pass": recent_timing_pass,
            "ht_score_floor_pass": ht_score_floor_pass,
            "ht_live_score_min": HT_LIVE_SCORE_MIN,
            "ht_is_best_focus": ht_is_best_focus,
            "h2h_sh_goal_rate": round(sh_rate, 3),
            "h2h_ft_over_1_5_rate": round(ft_over_1_5_rate, 3),
            "h2h_avg_ht_goals": avg_ht_goals,
            "h2h_avg_sh_goals": avg_sh_goals,
            "h2h_avg_ft_goals": avg_ft_goals,
            "h2h_sample_size": n,
            "h2h_total": total_h2h,
            "h2h_3y_count": n_3y,
            "h2h_expired": expired_count,
            "ft_0_0_count": ft_zero_count,
            "time_bins": time_bins,
            "late_fh_pressure": late_fh_pressure,
            "early_only_flag": early_only_flag,
            "pullback_fit": pullback_fit,
            "second_half_bins": second_half_bins,
            "recent_time_bins": recent_time_bins,
            "recent_second_half_bins": recent_second_half_bins,
            "recent_late_fh_pressure": recent_late_fh_pressure,
            "recent_early_only_flag": recent_early_only_flag,
            "recent_timing_fit": recent_timing_fit,
            "phase_bias": phase_bias,
            "home_recent_ht_over": home_recent["ht_over"],
            "home_recent_avg_goals": home_recent["ht_avg"],
            "home_recent_ht_scored": home_recent["ht_scored"],
            "home_recent_ht_conceded": home_recent["ht_conceded"],
            "home_recent_ht_goals_for_avg": home_recent["ht_goals_for_avg"],
            "home_recent_ht_goals_against_avg": home_recent["ht_goals_against_avg"],
            "home_recent_sh_over": home_recent["sh_over"],
            "home_recent_sh_avg_goals": home_recent["sh_avg"],
            "home_recent_ft_over_1_5": home_recent["ft_over_1_5"],
            "away_recent_ht_over": away_recent["ht_over"],
            "away_recent_avg_goals": away_recent["ht_avg"],
            "away_recent_ht_scored": away_recent["ht_scored"],
            "away_recent_ht_conceded": away_recent["ht_conceded"],
            "away_recent_ht_goals_for_avg": away_recent["ht_goals_for_avg"],
            "away_recent_ht_goals_against_avg": away_recent["ht_goals_against_avg"],
            "away_recent_sh_over": away_recent["sh_over"],
            "away_recent_sh_avg_goals": away_recent["sh_avg"],
            "away_recent_ft_over_1_5": away_recent["ft_over_1_5"],
            "recent_form_avg": round(recent_form_avg, 3),
            "home_attack_vs_away_defense": round(home_attack_vs_away_defense, 3),
            "away_attack_vs_home_defense": round(away_attack_vs_home_defense, 3),
            "ht_attack_vs_defense": ht_attack_vs_defense,
            "both_sides_ht_threat": both_sides_ht_threat,
            "recent_sh_avg": round(recent_sh_avg, 3),
            "recent_ft_over_1_5": round(recent_ft_over_1_5, 3),
        },
        "metrics": {
            "h2h_total": total_h2h,
            "h2h_3y_count": n_3y,
            "h2h_analyzed": n,
            "h2h_expired": expired_count,
            "ht_goal_rate": round(ht_rate, 3),
            "ht_goal_count": ht_goal_count,
            "ht_strict_pass": ht_candidate,
            "sh_goal_rate": round(sh_rate, 3),
            "ft_over_1_5_rate": round(ft_over_1_5_rate, 3),
            "ft_0_0_count": ft_zero_count,
        }
    }
