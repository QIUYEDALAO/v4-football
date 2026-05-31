from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

# Phase 3 rule freeze: V4-RF-CPL shadow-only grading
# - 10G7 entry gate + recent5 grading
# - recent5 heating exceptions (6/10+5/5 => B, 5/10+5/5 => C observe)
# - team balance adjustment (no min(home,away) hard cut)
# - h2h recent5 bonus-only (cannot downgrade, cannot create A/B)
# - opening market confirm/veto (cannot create A/B, only keep/downgrade shadow)


def _safe_rate(hit: int, sample: int) -> float | None:
    if sample <= 0:
        return None
    return round(hit / sample, 3)


def _parse_fixture_dt(match: dict) -> Optional[datetime]:
    fixture = match.get("fixture") or {}
    ts = fixture.get("timestamp")
    if isinstance(ts, (int, float)) and ts > 0:
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None
    raw = fixture.get("date")
    if not raw or not isinstance(raw, str):
        return None
    try:
        normalized = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def build_team_fh_samples(recent_resp: dict | None, team_id: int, max_n: int = 10) -> list[dict]:
    matches = []
    if isinstance(recent_resp, dict):
        rows = recent_resp.get("response")
        if isinstance(rows, list):
            matches = rows

    samples: list[dict] = []
    for m in matches:
        score = m.get("score") or {}
        ht = score.get("halftime") or {}
        ht_home = ht.get("home")
        ht_away = ht.get("away")
        # RF strict rule: halftime score must exist
        if ht_home is None or ht_away is None:
            continue

        teams = m.get("teams") or {}
        home_id = (teams.get("home") or {}).get("id")
        away_id = (teams.get("away") or {}).get("id")
        if str(home_id) == str(team_id):
            ht_for = int(ht_home)
            ht_against = int(ht_away)
        elif str(away_id) == str(team_id):
            ht_for = int(ht_away)
            ht_against = int(ht_home)
        else:
            continue

        samples.append(
            {
                "involved": (int(ht_home) + int(ht_away)) > 0,
                "scored": ht_for > 0,
                "conceded": ht_against > 0,
                "dt": _parse_fixture_dt(m),
            }
        )
        if len(samples) >= max_n:
            break
    return samples


def summarize_recent(samples: list[dict]) -> dict:
    n = len(samples)
    involved = sum(1 for x in samples if x.get("involved"))
    scored = sum(1 for x in samples if x.get("scored"))
    conceded = sum(1 for x in samples if x.get("conceded"))
    dts = [x.get("dt") for x in samples if isinstance(x.get("dt"), datetime)]
    if len(dts) >= 2:
        window_days = int((max(dts) - min(dts)).days)
    elif len(dts) == 1:
        window_days = 0
    else:
        window_days = None
    return {
        "sample_count": n,
        "involved_rate": _safe_rate(involved, n),
        "score_rate": _safe_rate(scored, n),
        "concede_rate": _safe_rate(conceded, n),
        "window_days": window_days,
    }


def freshness_status(home_days: Optional[int], away_days: Optional[int], home_n: int, away_n: int) -> str:
    if home_n <= 0 or away_n <= 0:
        return "UNKNOWN"
    if home_days is None or away_days is None:
        return "UNKNOWN"
    span = max(home_days, away_days)
    if span <= 90:
        return "FRESH"
    if span <= 120:
        return "NORMAL"
    if span <= 180:
        return "STALE"
    return "EXPIRED"


def _pct_text(v: float | None) -> str:
    if v is None:
        return "N/A"
    return f"{round(v * 100)}%"


def build_recent_form_shadow_from_recent(
    home_recent_resp: dict | None,
    home_id: int,
    away_recent_resp: dict | None,
    away_id: int,
) -> dict[str, Any]:
    home10_samples = build_team_fh_samples(home_recent_resp, home_id, max_n=10)
    away10_samples = build_team_fh_samples(away_recent_resp, away_id, max_n=10)
    home5_samples = home10_samples[:5]
    away5_samples = away10_samples[:5]

    home10 = summarize_recent(home10_samples)
    away10 = summarize_recent(away10_samples)
    home5 = summarize_recent(home5_samples)
    away5 = summarize_recent(away5_samples)

    h10_inv = home10["involved_rate"]
    a10_inv = away10["involved_rate"]
    h5_inv = home5["involved_rate"]
    a5_inv = away5["involved_rate"]

    combined10 = round((h10_inv + a10_inv) / 2, 3) if h10_inv is not None and a10_inv is not None else None
    combined5 = round((h5_inv + a5_inv) / 2, 3) if h5_inv is not None and a5_inv is not None else None

    freshness = freshness_status(
        home10["window_days"],
        away10["window_days"],
        home10["sample_count"],
        away10["sample_count"],
    )

    if home5["sample_count"] < 5 or away5["sample_count"] < 5:
        momentum = "LOW_SAMPLE"
    elif combined10 is None or combined5 is None:
        momentum = "DATA_MISSING"
    else:
        delta = combined5 - combined10
        if delta > 0.10:
            momentum = "HEATING_UP"
        elif delta < -0.10:
            momentum = "COOLING_DOWN"
        else:
            momentum = "STABLE"

    primary_score: float | None = None
    primary_level = "DATA_MISSING"
    primary_reason = "近10样本缺失，RF 不参与"

    if combined10 is not None:
        if home10["sample_count"] < 3 or away10["sample_count"] < 3:
            primary_level = "LOW_SAMPLE"
            primary_reason = (
                f"近10样本不足（home={home10['sample_count']}, away={away10['sample_count']}），RF 不参与"
            )
        elif combined5 is None or home5["sample_count"] < 5 or away5["sample_count"] < 5:
            primary_level = "LOW_SAMPLE"
            primary_reason = (
                f"近10 FH参与率 {_pct_text(combined10)}，近5样本不足（home={home5['sample_count']}, away={away5['sample_count']}）"
            )
        else:
            primary_score = round((combined10 * 0.70 + combined5 * 0.30) * 100, 1)
            if primary_score >= 70:
                primary_level = "STRONG"
            elif primary_score >= 55:
                primary_level = "MEDIUM"
            else:
                primary_level = "WEAK"
            if freshness == "STALE":
                primary_level = "STALE_SAMPLE"
            elif freshness == "EXPIRED":
                primary_level = "EXPIRED_SAMPLE"
            momentum_text = {
                "HEATING_UP": "升温",
                "STABLE": "稳定",
                "COOLING_DOWN": "降温",
                "LOW_SAMPLE": "样本不足",
                "DATA_MISSING": "数据缺失",
            }.get(momentum, momentum)
            primary_reason = f"近10 FH参与率 {_pct_text(combined10)}，近5 {momentum_text}，样本 {freshness}"
            if freshness in ("STALE", "EXPIRED"):
                primary_reason = (
                    f"近10跨度 {max(home10['window_days'] or 0, away10['window_days'] or 0)} 天，样本 {freshness}，仅参考"
                )

    return {
        "home_recent10_fh_involved_rate": h10_inv,
        "away_recent10_fh_involved_rate": a10_inv,
        "combined_recent10_fh_involved_rate": combined10,
        "home_recent10_fh_score_rate": home10["score_rate"],
        "away_recent10_fh_score_rate": away10["score_rate"],
        "home_recent10_fh_concede_rate": home10["concede_rate"],
        "away_recent10_fh_concede_rate": away10["concede_rate"],
        "recent10_sample_count_home": home10["sample_count"],
        "recent10_sample_count_away": away10["sample_count"],
        "recent10_window_days_home": home10["window_days"],
        "recent10_window_days_away": away10["window_days"],
        "recent_freshness_status": freshness,
        "home_recent5_fh_involved_rate": h5_inv,
        "away_recent5_fh_involved_rate": a5_inv,
        "combined_recent5_fh_involved_rate": combined5,
        "home_recent5_fh_score_rate": home5["score_rate"],
        "away_recent5_fh_score_rate": away5["score_rate"],
        "home_recent5_fh_concede_rate": home5["concede_rate"],
        "away_recent5_fh_concede_rate": away5["concede_rate"],
        "recent5_momentum_status": momentum,
        "recent_form_primary_score": primary_score,
        "recent_form_primary_level": primary_level,
        "recent_form_primary_reason": primary_reason,
    }


def _to_float(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def _to_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default


def _rate_to_count(rate: Any, sample: int, max_cap: int) -> Optional[int]:
    rv = _to_float(rate)
    if rv is None or sample <= 0:
        return None
    cnt = int(round(rv * sample))
    cnt = max(0, min(sample, cnt))
    return max(0, min(max_cap, cnt))


def _side_level(recent10_cnt: int, recent5_cnt: int) -> str:
    if recent10_cnt >= 7 and recent5_cnt == 5:
        return "HOT_DRIVER"
    if recent10_cnt >= 7 and recent5_cnt >= 4:
        return "STRONG_DRIVER"
    return "NONE"


def _weak_side_status(recent10_cnt: int, recent5_cnt: int) -> str:
    if recent10_cnt <= 4 and recent5_cnt <= 2:
        return "DANGEROUS_DRAG"
    if recent10_cnt >= 7 and recent5_cnt >= 4:
        return "SUPPORTIVE"
    if recent10_cnt >= 6 and recent5_cnt >= 3:
        return "ACCEPTABLE"
    if recent10_cnt >= 6 and recent5_cnt <= 2:
        return "COOLING"
    if recent10_cnt == 5 or recent5_cnt <= 3:
        return "WEAK"
    return "NONE"


def _grade_rank(g: str) -> int:
    return {"A": 4, "B": 3, "C": 2, "SKIP": 1, "LOW_SAMPLE": 0, "DATA_MISSING": 0}.get(g, 0)


def _downgrade_once(g: str) -> str:
    if g == "A":
        return "B"
    if g == "B":
        return "C"
    if g == "C":
        return "SKIP"
    return g


def _is_extreme_veto(ht_line: Optional[float], over_odds: Optional[float], market_status: str) -> bool:
    if market_status != "MARKET_HARD_VETO":
        return False
    if ht_line is not None and ht_line <= 0.25:
        return True
    if over_odds is not None and over_odds >= 2.55:
        return True
    if ht_line is not None and over_odds is not None and ht_line <= 0.5 and over_odds >= 2.40:
        return True
    return False


def _apply_market_promotion_policy(
    *,
    base_grade: str,
    market_status: str,
    confidence_before_market: int,
    ht_line: Optional[float],
    over_odds: Optional[float],
) -> dict[str, Any]:
    """RF-first market policy: downgrade/risk by conflict level, no broad hard kill."""
    if ht_line is not None and 3.0 < ht_line <= 30.0:
        ht_line = ht_line / 10.0
    if over_odds is not None and 10.0 <= over_odds < 1000.0:
        over_odds = 1.0 + (over_odds / 100.0)

    policy_version = "V4_RF_MARKET_POLICY_20260531"
    conflict_level = "MARKET_CONFIRM"
    action = "KEEP"
    veto_severity = "NONE"
    veto_reason = ""
    adjusted = base_grade
    reason = "盘口仅作确认，不单独制造A/B"

    if market_status == "MARKET_NO_MARKET":
        conflict_level = "MARKET_NO_MARKET"
        action = "NO_MARKET_SKIP"
        adjusted = "SKIP"
        reason = "无盘口，shadow 标注SKIP且不进入待投"
    elif market_status == "MARKET_NO_DATA":
        conflict_level = "MARKET_NO_DATA"
        action = "NO_DATA_DOWNGRADE"
        if adjusted == "A":
            adjusted = "B"
        elif adjusted == "B":
            adjusted = "B" if confidence_before_market >= 70 else "C"
        elif adjusted == "C":
            adjusted = "C" if confidence_before_market >= 55 else "SKIP"
        reason = "盘口缺失，不升A；强RF保留B/C观察"
    elif market_status in {"MARKET_STRONG_CONFIRM", "MARKET_WEAK_CONFIRM"}:
        conflict_level = "MARKET_CONFIRM"
        action = "KEEP"
        reason = "盘口确认，仅提升信心不改主因子级别"
    elif market_status == "MARKET_NEUTRAL":
        conflict_level = "MARKET_LIGHT_CONFLICT"
        action = "LIGHT_DOWNGRADE"
        adjusted = _downgrade_once(adjusted)
        reason = "盘口中性偏保守，轻度降级"
    elif market_status == "MARKET_WEAK_VETO":
        conflict_level = "MARKET_LIGHT_CONFLICT"
        action = "LIGHT_DOWNGRADE"
        adjusted = _downgrade_once(adjusted)
        reason = "盘口轻微反向，降一级进入观察层"
    elif market_status == "MARKET_HARD_VETO":
        if _is_extreme_veto(ht_line, over_odds, market_status):
            conflict_level = "MARKET_EXTREME_VETO"
            action = "EXTREME_VETO_SKIP"
            veto_severity = "EXTREME"
            adjusted = "SKIP"
            reason = "极端盘口异常，触发EXTREME_VETO直接SKIP"
            veto_reason = "EXTREME_VETO"
        else:
            conflict_level = "MARKET_STRONG_CONFLICT"
            action = "STRONG_DOWNGRADE"
            veto_severity = "STRONG"
            if adjusted == "A":
                adjusted = "C" if confidence_before_market >= 55 else "SKIP"
            elif adjusted == "B":
                adjusted = "C" if confidence_before_market >= 45 else "SKIP"
            elif adjusted == "C":
                adjusted = "SKIP"
            reason = "明显盘口反向，强RF降至C观察，弱RF可SKIP"
            veto_reason = "STRONG_CONFLICT"

    if veto_reason == "":
        veto_reason = conflict_level
    return {
        "market_adjusted_shadow_grade": adjusted,
        "market_adjustment_reason": reason,
        "opening_market_conflict_level": conflict_level,
        "opening_market_action": action,
        "market_veto_severity": veto_severity,
        "market_veto_reason": veto_reason,
        "market_policy_version": policy_version,
        "dryrun_action": action,
    }


def _market_support_status(record: dict) -> dict[str, Any]:
    no_market_excluded = bool(record.get("no_market_excluded")) or str(record.get("pending_action", "")).startswith("无盘口")
    ht_line = _to_float(record.get("prematch_ht_line"))
    over_odds = _to_float(record.get("prematch_over_odds"))
    under_odds = _to_float(record.get("prematch_under_odds"))
    available = any(v is not None for v in (ht_line, over_odds, under_odds))

    if no_market_excluded:
        status = "MARKET_NO_MARKET"
    elif not available:
        status = "MARKET_NO_DATA"
    else:
        if (ht_line is not None and ht_line <= 0.5) or (over_odds is not None and over_odds >= 2.20):
            status = "MARKET_HARD_VETO"
        elif (ht_line is not None and ht_line < 1.0) or (over_odds is not None and over_odds > 2.05):
            status = "MARKET_WEAK_VETO"
        elif (ht_line is not None and ht_line >= 1.25) and (over_odds is None or over_odds <= 1.85):
            status = "MARKET_STRONG_CONFIRM"
        elif (ht_line is not None and ht_line >= 1.0) and (over_odds is None or over_odds <= 1.95):
            status = "MARKET_WEAK_CONFIRM"
        else:
            status = "MARKET_NEUTRAL"

    confirm_level = {
        "MARKET_STRONG_CONFIRM": "HIGH",
        "MARKET_WEAK_CONFIRM": "LOW",
    }.get(status, "NONE")
    veto_level = {
        "MARKET_HARD_VETO": "HARD",
        "MARKET_WEAK_VETO": "WEAK",
    }.get(status, "NONE")
    reason = {
        "MARKET_STRONG_CONFIRM": "初盘上半场线位支持强确认",
        "MARKET_WEAK_CONFIRM": "初盘上半场线位支持弱确认",
        "MARKET_NEUTRAL": "初盘对上半场方向中性",
        "MARKET_WEAK_VETO": "初盘线位偏弱，给出弱反向",
        "MARKET_HARD_VETO": "初盘线位明显反向，给出强veto",
        "MARKET_NO_DATA": "缺少可用初盘数据",
        "MARKET_NO_MARKET": "无盘口，shadow 不进入待投",
    }[status]

    return {
        "opening_market_available": available,
        "opening_market_snapshot_time": record.get("logged_at") or record.get("generated_at") or "UNKNOWN",
        "opening_market_source": "prematch_snapshot_from_scan",
        "opening_ft_ou_line": None,
        "opening_ft_ou_over_odds": None,
        "opening_ft_ou_under_odds": None,
        "opening_ht_ou_line": ht_line,
        "opening_ht_ou_over_odds": over_odds,
        "opening_ht_ou_under_odds": under_odds,
        "opening_ah_line": None,
        "opening_favorite_side": "UNKNOWN",
        "opening_market_support_status": status,
        "opening_market_confirm_level": confirm_level,
        "opening_market_veto_level": veto_level,
        "opening_market_reason": reason,
        "opening_market_role": "CONFIRM_OR_VETO_SHADOW_ONLY",
        "opening_market_data_status": "HAS_DATA" if available else ("NO_MARKET" if no_market_excluded else "NO_DATA"),
    }


def build_rf_shadow_grade_layer(record: dict, factors: dict | None = None) -> dict[str, Any]:
    factors = factors or {}

    h10_n = _to_int(record.get("recent10_sample_count_home"), 0)
    a10_n = _to_int(record.get("recent10_sample_count_away"), 0)
    h10_cnt = _rate_to_count(record.get("home_recent10_fh_involved_rate"), h10_n, 10)
    a10_cnt = _rate_to_count(record.get("away_recent10_fh_involved_rate"), a10_n, 10)

    h5_n = min(5, h10_n) if h10_n > 0 else 0
    a5_n = min(5, a10_n) if a10_n > 0 else 0
    h5_cnt = _rate_to_count(record.get("home_recent5_fh_involved_rate"), h5_n, 5)
    a5_cnt = _rate_to_count(record.get("away_recent5_fh_involved_rate"), a5_n, 5)

    c10_rate = _to_float(record.get("combined_recent10_fh_involved_rate"))
    c5_rate = _to_float(record.get("combined_recent5_fh_involved_rate"))
    c10_cnt = int(round(c10_rate * 10)) if c10_rate is not None else None
    c5_cnt = int(round(c5_rate * 5)) if c5_rate is not None else None

    market = _market_support_status(record)
    market_status = market["opening_market_support_status"]

    missing_core = c10_cnt is None or c5_cnt is None
    low_sample = min(h10_n, a10_n) < 5

    rf_recent10_gate_status = "RECENT10_DATA_MISSING"
    rf_entry_rule = "ENTRY_DATA_MISSING"
    rf_heating_exception = False
    rf_heating_exception_reason = ""

    if not missing_core:
        if c10_cnt >= 7:
            rf_recent10_gate_status = "RECENT10_GATE_PASS_7_OF_10"
            rf_entry_rule = "ENTRY_PASS_10G7"
        elif c10_cnt == 6 and c5_cnt == 5:
            rf_recent10_gate_status = "RECENT10_GATE_BREAK_6_OF_10"
            rf_entry_rule = "ENTRY_BREAK_B_6OF10_5OF5"
            rf_heating_exception = True
            rf_heating_exception_reason = "近5强势升温，近10基础不足，破格B"
        elif c10_cnt == 5 and c5_cnt == 5:
            rf_recent10_gate_status = "RECENT10_GATE_OBSERVE_5_OF_10"
            rf_entry_rule = "ENTRY_C_OBSERVE_5OF10_5OF5"
            rf_heating_exception = True
            rf_heating_exception_reason = "短期升温观察，稳定性不足"
        elif c10_cnt <= 4:
            rf_recent10_gate_status = "RECENT10_GATE_BLOCK_LE_4_OF_10"
            rf_entry_rule = "ENTRY_BLOCK_LE4"
        else:
            rf_recent10_gate_status = "RECENT10_GATE_PARTIAL"
            rf_entry_rule = "ENTRY_PARTIAL"

    rf_recent5_grade_status = "RECENT5_DATA_MISSING"
    if c5_cnt is not None:
        if c5_cnt == 5:
            rf_recent5_grade_status = "RECENT5_A_BASE_5_OF_5"
        elif c5_cnt == 4:
            rf_recent5_grade_status = "RECENT5_B_BASE_4_OF_5"
        elif c5_cnt == 3:
            rf_recent5_grade_status = "RECENT5_C_OBSERVE_3_OF_5"
        else:
            rf_recent5_grade_status = "RECENT5_WEAK_LE_2_OF_5"

    # Base grade from recent10 gate + recent5 grade
    if missing_core:
        rf_shadow_grade = "DATA_MISSING"
    elif low_sample:
        rf_shadow_grade = "LOW_SAMPLE"
    elif market_status == "MARKET_NO_MARKET":
        rf_shadow_grade = "SKIP"
    elif c10_cnt <= 4:
        rf_shadow_grade = "C" if (c5_cnt or 0) >= 3 else "SKIP"
    elif c10_cnt == 5 and c5_cnt == 5:
        rf_shadow_grade = "C"
    elif c10_cnt == 6 and c5_cnt == 5:
        rf_shadow_grade = "B"
    elif c10_cnt >= 7:
        if c5_cnt == 5:
            rf_shadow_grade = "A"
        elif c5_cnt == 4:
            rf_shadow_grade = "B"
        elif c5_cnt == 3:
            rf_shadow_grade = "C"
        else:
            rf_shadow_grade = "SKIP"
    else:
        rf_shadow_grade = "C"

    # Team balance
    home_lvl = _side_level(h10_cnt or 0, h5_cnt or 0)
    away_lvl = _side_level(a10_cnt or 0, a5_cnt or 0)
    rf_balance_status = "NO_DRIVER"
    rf_balance_driver_side = "NONE"
    rf_balance_driver_level = "NONE"
    rf_balance_weak_side_status = "NONE"
    rf_balance_adjustment = "NO_CHANGE"
    rf_balance_reason = "无强侧驱动，按普通RF入池规则"

    if home_lvl in {"HOT_DRIVER", "STRONG_DRIVER"} and away_lvl in {"HOT_DRIVER", "STRONG_DRIVER"}:
        rf_balance_status = "BALANCED_ACTIVE"
        rf_balance_driver_side = "BOTH"
        rf_balance_driver_level = "HOT_DRIVER" if home_lvl == "HOT_DRIVER" and away_lvl == "HOT_DRIVER" else "STRONG_DRIVER"
        rf_balance_reason = "双方均为强驱动，双边活跃"
    else:
        driver_side = None
        driver_level = None
        weak10 = 0
        weak5 = 0
        if home_lvl in {"HOT_DRIVER", "STRONG_DRIVER"}:
            driver_side = "HOME"
            driver_level = home_lvl
            weak10, weak5 = (a10_cnt or 0), (a5_cnt or 0)
        elif away_lvl in {"HOT_DRIVER", "STRONG_DRIVER"}:
            driver_side = "AWAY"
            driver_level = away_lvl
            weak10, weak5 = (h10_cnt or 0), (h5_cnt or 0)
        if driver_side:
            rf_balance_driver_side = driver_side
            rf_balance_driver_level = driver_level
            weak_status = _weak_side_status(weak10, weak5)
            rf_balance_weak_side_status = weak_status
            if driver_level == "HOT_DRIVER":
                if weak_status == "SUPPORTIVE":
                    rf_balance_status = "HOT_DRIVER_SUPPORTIVE"
                    rf_balance_adjustment = "KEEP_A_BASE"
                    rf_balance_reason = "强侧驱动+弱侧支持，可维持A基础"
                elif weak_status == "ACCEPTABLE":
                    rf_balance_status = "HOT_DRIVER_ACCEPTABLE"
                    rf_balance_adjustment = "DOWNGRADE_TO_B"
                    rf_balance_reason = "强侧驱动，弱侧保底，不给A但不排除"
                elif weak_status == "COOLING":
                    rf_balance_status = "HOT_DRIVER_COOLING"
                    rf_balance_adjustment = "DOWNGRADE_TO_C"
                    rf_balance_reason = "强侧驱动但弱侧降温，降至观察层"
                elif weak_status == "WEAK":
                    rf_balance_status = "HOT_DRIVER_WEAK"
                    rf_balance_adjustment = "REQUIRE_DOMINANT_FAVORITE_CONFIRMATION"
                    rf_balance_reason = "强侧驱动但弱侧偏弱，需要单边压制确认"
                else:
                    rf_balance_status = "HOT_DRIVER_DANGEROUS_DRAG"
                    rf_balance_adjustment = "SKIP_OR_C"
                    rf_balance_reason = "弱侧危险拖累，默认C/SKIP"
            elif driver_level == "STRONG_DRIVER" and weak_status == "ACCEPTABLE":
                rf_balance_status = "STRONG_DRIVER_ACCEPTABLE"
                rf_balance_adjustment = "DOWNGRADE_TO_C"
                rf_balance_reason = "强驱动但非HOT，弱侧仅保底，降为B/C观察"

    balance_adjusted_grade = rf_shadow_grade
    if balance_adjusted_grade in {"A", "B", "C"}:
        if rf_balance_adjustment == "DOWNGRADE_TO_B":
            # Team-balance rule: HOT_DRIVER + ACCEPTABLE should settle at B (not A, not SKIP).
            balance_adjusted_grade = "B"
        elif rf_balance_adjustment == "DOWNGRADE_TO_C":
            if balance_adjusted_grade == "A":
                balance_adjusted_grade = "C"
            elif balance_adjusted_grade == "B":
                balance_adjusted_grade = "C"
        elif rf_balance_adjustment in {"SKIP_OR_C", "REQUIRE_DOMINANT_FAVORITE_CONFIRMATION"}:
            balance_adjusted_grade = "C" if (c5_cnt or 0) >= 3 else "SKIP"

    # H2H recent5 bonus-only (no downgrade, no grade manufacture)
    h2h_sample_base = _to_int(factors.get("h2h_official_sample_size"), _to_int(factors.get("h2h_sample_size"), 0))
    h2h_recent5_sample_count = min(5, max(0, h2h_sample_base))
    h2h_rate = _to_float(factors.get("h2h_ht_goal_rate"))
    h2h_recent5_fh_involved_count = _rate_to_count(h2h_rate, h2h_recent5_sample_count, 5) or 0
    h2h_total = _to_int(factors.get("h2h_total"), 0)
    h2h_3y_count = _to_int(factors.get("h2h_3y_count"), h2h_sample_base)
    h2h_sample_age_status = "H2H_STALE" if (h2h_total > 0 and h2h_3y_count <= 0) else "H2H_FRESH"

    if h2h_recent5_sample_count < 3:
        h2h_recent5_support_status = "H2H_LOW_SAMPLE"
        h2h_recent5_bonus_level = "NONE"
        h2h_recent5_bonus_reason = "H2H样本不足，忽略"
        h2h_assist_status = "H2H_IGNORED"
        h2h_assist_strength = "NONE"
        h2h_ignored_reason = "LOW_SAMPLE"
    elif h2h_sample_age_status == "H2H_STALE":
        h2h_recent5_support_status = "H2H_STALE"
        h2h_recent5_bonus_level = "NONE"
        h2h_recent5_bonus_reason = "H2H样本过旧，忽略"
        h2h_assist_status = "H2H_IGNORED"
        h2h_assist_strength = "NONE"
        h2h_ignored_reason = "STALE"
    elif h2h_recent5_fh_involved_count >= 4:
        h2h_recent5_support_status = "H2H_STRONG_BONUS"
        h2h_recent5_bonus_level = "STRONG_BONUS"
        h2h_recent5_bonus_reason = "H2H近5支持强，仅加分不降级"
        h2h_assist_status = "H2H_ASSIST_ACTIVE"
        h2h_assist_strength = "STRONG"
        h2h_ignored_reason = ""
    elif h2h_recent5_fh_involved_count == 3:
        h2h_recent5_support_status = "H2H_LIGHT_BONUS"
        h2h_recent5_bonus_level = "LIGHT_BONUS"
        h2h_recent5_bonus_reason = "H2H近5支持轻度，仅加分不降级"
        h2h_assist_status = "H2H_ASSIST_ACTIVE"
        h2h_assist_strength = "LIGHT"
        h2h_ignored_reason = ""
    else:
        h2h_recent5_support_status = "H2H_NO_BONUS"
        h2h_recent5_bonus_level = "NO_BONUS"
        h2h_recent5_bonus_reason = "H2H不支持，不降级"
        h2h_assist_status = "H2H_IGNORED"
        h2h_assist_strength = "NONE"
        h2h_ignored_reason = "NO_BONUS"

    rf_shadow_score = _to_float(record.get("recent_form_primary_score"))
    if rf_shadow_score is None and c10_rate is not None and c5_rate is not None:
        rf_shadow_score = round((c10_rate * 0.7 + c5_rate * 0.3) * 100, 1)

    # Confidence pre-market: H2H bonus-only, no H2H downgrade
    confidence = int(round(rf_shadow_score or 50.0))
    if h2h_recent5_support_status == "H2H_STRONG_BONUS":
        confidence += 8
    elif h2h_recent5_support_status == "H2H_LIGHT_BONUS":
        confidence += 3
    if low_sample:
        confidence -= 12
    confidence_before_market = max(0, min(100, confidence))

    # Opening market policy (shadow only; RF is primary)
    market_policy = _apply_market_promotion_policy(
        base_grade=balance_adjusted_grade,
        market_status=market_status,
        confidence_before_market=confidence_before_market,
        ht_line=_to_float(record.get("prematch_ht_line")),
        over_odds=_to_float(record.get("prematch_over_odds")),
    )
    market_adjusted_shadow_grade = market_policy["market_adjusted_shadow_grade"]
    market_adjustment_reason = market_policy["market_adjustment_reason"]

    # route and confidence
    if market_status == "MARKET_NO_MARKET":
        rf_shadow_route = "NO_MARKET"
    elif missing_core:
        rf_shadow_route = "DATA_MISSING"
    elif rf_balance_adjustment == "REQUIRE_DOMINANT_FAVORITE_CONFIRMATION":
        rf_shadow_route = "DOMINANT_FAVORITE_PENDING"
    elif market_status in {"MARKET_HARD_VETO", "MARKET_WEAK_VETO"}:
        rf_shadow_route = "MARKET_VETO"
    elif rf_heating_exception:
        rf_shadow_route = "RECENT5_HEATING_EXCEPTION"
    elif rf_balance_driver_level == "HOT_DRIVER":
        rf_shadow_route = "HOT_DRIVER"
    elif rf_balance_driver_level == "STRONG_DRIVER":
        rf_shadow_route = "STRONG_DRIVER"
    else:
        rf_shadow_route = "BILATERAL_ACTIVE"

    confidence = int(confidence_before_market)
    if market_status == "MARKET_STRONG_CONFIRM":
        confidence += 8
    elif market_status == "MARKET_WEAK_CONFIRM":
        confidence += 3
    elif market_status == "MARKET_NEUTRAL":
        confidence -= 4
    elif market_status == "MARKET_WEAK_VETO":
        confidence -= 12
    elif market_status == "MARKET_HARD_VETO":
        confidence -= 25
    elif market_status in {"MARKET_NO_DATA", "MARKET_NO_MARKET"}:
        confidence -= 8
    if low_sample:
        confidence -= 12
    rf_shadow_confidence = max(0, min(100, confidence))

    rf_shadow_reason = (
        f"近10门槛={rf_recent10_gate_status}; 近5评级={rf_recent5_grade_status}; "
        f"Balance={rf_balance_status}; H2H={h2h_recent5_support_status}; Market={market_status}"
    )

    return {
        "rf_shadow_grade": rf_shadow_grade,
        "rf_shadow_score": rf_shadow_score if rf_shadow_score is not None else "DATA_MISSING",
        "rf_shadow_route": rf_shadow_route,
        "rf_shadow_reason": rf_shadow_reason,
        "rf_shadow_confidence": rf_shadow_confidence,
        "rf_entry_rule": rf_entry_rule,
        "rf_recent10_gate_status": rf_recent10_gate_status,
        "rf_recent5_grade_status": rf_recent5_grade_status,
        "rf_heating_exception": rf_heating_exception,
        "rf_heating_exception_reason": rf_heating_exception_reason or "N/A",
        "rf_balance_status": rf_balance_status,
        "rf_balance_driver_side": rf_balance_driver_side,
        "rf_balance_driver_level": rf_balance_driver_level,
        "rf_balance_weak_side_status": rf_balance_weak_side_status,
        "rf_balance_adjustment": rf_balance_adjustment,
        "rf_balance_reason": rf_balance_reason,
        "h2h_recent5_fh_involved_count": h2h_recent5_fh_involved_count,
        "h2h_recent5_sample_count": h2h_recent5_sample_count,
        "h2h_recent5_support_status": h2h_recent5_support_status,
        "h2h_recent5_bonus_level": h2h_recent5_bonus_level,
        "h2h_recent5_bonus_reason": h2h_recent5_bonus_reason,
        "h2h_assist_status": h2h_assist_status,
        "h2h_assist_strength": h2h_assist_strength,
        "h2h_assist_reason": h2h_recent5_bonus_reason,
        "h2h_sample_age_status": h2h_sample_age_status,
        "h2h_low_sample": h2h_recent5_support_status == "H2H_LOW_SAMPLE",
        "h2h_ignored_reason": h2h_ignored_reason or "N/A",
        **market,
        "opening_market_conflict_level": market_policy["opening_market_conflict_level"],
        "opening_market_action": market_policy["opening_market_action"],
        "market_veto_severity": market_policy["market_veto_severity"],
        "market_veto_reason": market_policy["market_veto_reason"],
        "market_policy_version": market_policy["market_policy_version"],
        "dryrun_action": market_policy["dryrun_action"],
        "market_adjusted_shadow_grade": market_adjusted_shadow_grade,
        "market_adjustment_reason": market_adjustment_reason,
    }
