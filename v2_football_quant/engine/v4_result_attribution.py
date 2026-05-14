"""
V4 赛后归因系统
================
仅用于复盘归因，不参与实时评分。

用法：
  python3 engine/v4_result_attribution.py --date 20260514
  python3 engine/v4_result_attribution.py --date 20260514 --fixture 123456
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine import net_utils
from engine.v4_match_intelligence import explain_match

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
ARCHIVE_DIR = BASE_DIR / "data" / "v4_archive"


def _date_key(v: str) -> str:
    return str(v).replace("-", "")


def _load_json(path: Path, default: Any):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    rows.append(obj)
            except Exception:
                continue
    return rows


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _api_get(endpoint: str) -> dict:
    return net_utils.api_get(endpoint) or {}


def _first_ht_goal_minute(events: list[dict]) -> tuple[int | None, str]:
    mins = []
    for ev in events:
        et = str(ev.get("type") or "").strip().lower()
        detail = str(ev.get("detail") or "").strip().lower()
        if et != "goal":
            continue
        elapsed = _safe_int((ev.get("time") or {}).get("elapsed"), -1)
        extra = _safe_int((ev.get("time") or {}).get("extra"), 0)
        if elapsed < 0:
            continue
        if elapsed > 45:
            continue
        if "missed" in detail or "cancel" in detail or "disallowed" in detail:
            continue
        # 45+N 记录为 45+N，用于补时噪音识别
        minute = elapsed + (extra if elapsed == 45 and extra > 0 else 0)
        mins.append(minute)
    if not mins:
        return None, "NONE"
    m = min(mins)
    if m <= 15:
        return m, "0_15"
    if m <= 30:
        return m, "16_30"
    return m, "31_45"


def _top_predicted_bucket(pred_bins: dict[str, float]) -> str:
    bins = {
        "0_15": _safe_float(pred_bins.get("0_15"), 0.0),
        "16_30": _safe_float(pred_bins.get("16_30"), 0.0),
        "31_45": _safe_float(pred_bins.get("31_45"), 0.0),
    }
    return max(bins, key=bins.get)


def _event_noise_tags(events: list[dict], first_ht_goal_minute: int | None) -> list[str]:
    tags: set[str] = set()
    for ev in events:
        et = str(ev.get("type") or "").strip().lower()
        detail = str(ev.get("detail") or "").strip().lower()
        elapsed = _safe_int((ev.get("time") or {}).get("elapsed"), -1)
        extra = _safe_int((ev.get("time") or {}).get("extra"), 0)
        minute = elapsed + (extra if elapsed == 45 and extra > 0 else 0)
        in_ht = elapsed >= 0 and elapsed <= 45
        if not in_ht:
            continue

        if et == "card" and ("red card" in detail or "second yellow" in detail):
            tags.add("RED_CARD")
        if et == "goal" and "penalty" in detail:
            tags.add("PENALTY")
        if et == "goal" and "own goal" in detail:
            tags.add("OWN_GOAL")
        if et == "var" and "penalty" in detail:
            tags.add("VAR_PENALTY")
        if et == "subst" and "injury" in detail:
            tags.add("INJURY_SUB")
        if et == "goal" and elapsed == 45 and extra >= 1:
            tags.add("LATE_STOPPAGE_GOAL")
    if first_ht_goal_minute is not None and first_ht_goal_minute <= 3:
        tags.add("EARLY_GOAL_RANDOM")
    return sorted(tags)


def _event_noise_detail(events: list[dict], first_ht_goal_minute: int | None) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "red_card_minute": None,
        "penalty_minute": None,
        "own_goal_minute": None,
        "injury_sub_minute": None,
        "stoppage_goal": False,
        "noise_before_goal": False,
        "noise_after_goal": False,
    }
    noise_minutes: list[int] = []
    for ev in events:
        et = str(ev.get("type") or "").strip().lower()
        info = str(ev.get("detail") or "").strip().lower()
        elapsed = _safe_int((ev.get("time") or {}).get("elapsed"), -1)
        extra = _safe_int((ev.get("time") or {}).get("extra"), 0)
        minute = elapsed + (extra if elapsed == 45 and extra > 0 else 0)
        if elapsed < 0 or elapsed > 45:
            continue
        if et == "card" and ("red card" in info or "second yellow" in info):
            if detail["red_card_minute"] is None:
                detail["red_card_minute"] = minute
            noise_minutes.append(minute)
        if et == "goal" and "penalty" in info:
            if detail["penalty_minute"] is None:
                detail["penalty_minute"] = minute
            noise_minutes.append(minute)
        if et == "goal" and "own goal" in info:
            if detail["own_goal_minute"] is None:
                detail["own_goal_minute"] = minute
            noise_minutes.append(minute)
        if et == "subst" and "injury" in info:
            if detail["injury_sub_minute"] is None:
                detail["injury_sub_minute"] = minute
            noise_minutes.append(minute)
        if et == "goal" and elapsed == 45 and extra >= 1:
            detail["stoppage_goal"] = True
            noise_minutes.append(minute)
    if first_ht_goal_minute is not None:
        detail["noise_before_goal"] = any(m <= first_ht_goal_minute for m in noise_minutes)
        detail["noise_after_goal"] = any(m > first_ht_goal_minute for m in noise_minutes)
    else:
        detail["noise_before_goal"] = bool(noise_minutes)
    return detail


def _weather_dimension(rec: dict) -> dict[str, Any]:
    ctx = rec.get("context_observation") or {}
    weather = (ctx.get("weather") or {}) if isinstance(ctx, dict) else {}
    status = str(weather.get("status") or "")
    if status in ("SKIPPED_FAST_MODE", "MISSING", "ERROR"):
        return {
            "weather_available": False,
            "source": status or "unknown",
            "temperature_c": None,
            "rain_mm": None,
            "wind_speed_mps": None,
            "humidity": None,
            "condition": None,
            "weather_risk_level": "UNKNOWN",
            "weather_tags": ["NORMAL_WEATHER"],
        }

    temp_c = weather.get("temperature_c", weather.get("temp_c", weather.get("temp")))
    rain_mm = weather.get("rain_mm", weather.get("precipitation_mm", weather.get("rain")))
    wind = weather.get("wind_speed_mps", weather.get("wind_speed", weather.get("wind_mps")))
    humidity = weather.get("humidity", weather.get("humidity_pct"))
    condition = str(weather.get("condition") or weather.get("description") or "").lower() or None

    t = _safe_float(temp_c, 999.0)
    r = _safe_float(rain_mm, 0.0)
    w = _safe_float(wind, 0.0)
    h = _safe_float(humidity, 0.0)

    tags: list[str] = []
    if r >= 8:
        tags.append("HEAVY_RAIN")
    elif r >= 2:
        tags.append("MODERATE_RAIN")
    elif r > 0:
        tags.append("LIGHT_RAIN")
    if w >= 10:
        tags.append("STRONG_WIND")
    if t <= 0:
        tags.append("EXTREME_COLD")
    if t >= 32:
        tags.append("EXTREME_HEAT")
    if h >= 85:
        tags.append("HIGH_HUMIDITY")
    if r >= 2 and h >= 80:
        tags.append("WET_PITCH_RISK")
    if not tags:
        tags = ["NORMAL_WEATHER"]

    if any(x in tags for x in ("HEAVY_RAIN", "STRONG_WIND", "EXTREME_COLD", "EXTREME_HEAT")):
        risk = "HIGH"
    elif any(x in tags for x in ("MODERATE_RAIN", "HIGH_HUMIDITY", "WET_PITCH_RISK")):
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return {
        "weather_available": True,
        "source": str(weather.get("source") or "external_weather_api"),
        "temperature_c": None if temp_c is None else round(_safe_float(temp_c, 0.0), 2),
        "rain_mm": None if rain_mm is None else round(_safe_float(rain_mm, 0.0), 2),
        "wind_speed_mps": None if wind is None else round(_safe_float(wind, 0.0), 2),
        "humidity": None if humidity is None else round(_safe_float(humidity, 0.0), 2),
        "condition": condition,
        "weather_risk_level": risk,
        "weather_tags": tags,
    }


def _context_noise_tags(rec: dict, weather_dimension: dict[str, Any]) -> list[str]:
    tags: set[str] = set()
    ctx = rec.get("context_observation") or {}
    pitch = ctx.get("pitch") or {}
    referee = ctx.get("referee") or {}
    p_text = json.dumps(pitch, ensure_ascii=False).lower()
    r_text = json.dumps(referee, ensure_ascii=False).lower()

    # weather tags 进入归因上下文，不参与实时评分
    for tag in weather_dimension.get("weather_tags") or []:
        if tag != "NORMAL_WEATHER":
            tags.add(tag)
    if any(x in p_text for x in ("bad", "poor", "mud", "waterlog", "烂", "湿滑")):
        tags.add("BAD_PITCH")
    if any(x in p_text for x in ("artificial", "turf", "人造草")):
        tags.add("ARTIFICIAL_TURF")
    if _safe_float(referee.get("avg_cards"), 0.0) >= 5.0 or "high card" in r_text or "高牌" in r_text:
        tags.add("REF_CARD_HIGH")
    if _safe_float(referee.get("avg_penalties"), 0.0) >= 0.35 or "high penalty" in r_text or "高点球" in r_text:
        tags.add("REF_PENALTY_HIGH")
    return sorted(tags)


def _market_dimension(rec: dict, pre_grade: str) -> dict[str, Any]:
    lines = rec.get("ht_ou_lines") or []
    market_focus = str(rec.get("market_focus") or "")
    best_line = None
    over_odds = None
    under_odds = None
    if isinstance(lines, list) and lines:
        row = lines[0]
        best_line = _safe_float(row.get("line"), None)
        over_odds = _safe_float(row.get("over"), None)
        under_odds = _safe_float(row.get("under"), None)
        try:
            row = min(lines, key=lambda x: abs(_safe_float(x.get("line"), 999) - 1.0))
            best_line = _safe_float(row.get("line"), best_line)
            over_odds = _safe_float(row.get("over"), over_odds)
            under_odds = _safe_float(row.get("under"), under_odds)
        except Exception:
            pass

    if not lines:
        market_signal = "MARKET_DATA_MISSING"
        tags = ["MARKET_DATA_MISSING"]
    elif market_focus == "HT_LIVE_OVER":
        market_signal = "HT_MARKET_SUPPORT"
        tags = ["HT_MARKET_SUPPORT"]
    else:
        market_signal = "MARKET_DIRECTION_CONFLICT" if pre_grade in ("A", "B") else "HT_MARKET_NEUTRAL"
        tags = [market_signal]

    if best_line is not None and best_line >= 1.5:
        tags.append("LINE_TOO_HIGH")
    elif best_line is not None and best_line <= 0.5:
        tags.append("LINE_TOO_LOW")

    return {
        "ht_ou_available": bool(lines),
        "best_ht_line": best_line,
        "over_odds": over_odds,
        "under_odds": under_odds,
        "line_bucket": f"{best_line:.2f}" if isinstance(best_line, float) else None,
        "market_focus": market_focus or None,
        "direction_conflict": market_focus not in ("", "HT_LIVE_OVER"),
        "market_signal": market_signal,
        "market_tags": tags,
    }


def _motivation_dimension(rec: dict) -> dict[str, Any]:
    mot = rec.get("motivation") or {}
    gate = mot.get("gate") or {}
    home = mot.get("home") or {}
    away = mot.get("away") or {}
    lvl = "UNKNOWN"
    if str(gate.get("action") or "") in ("BOOST", "ALLOW_V4_LIVE"):
        lvl = "HIGH"
    elif str(gate.get("action") or "") in ("KEEP", "KEEP_WATCH"):
        lvl = "MEDIUM"
    elif str(gate.get("action") or "") in ("WATCH_ONLY", "DROP"):
        lvl = "LOW"
    return {
        "available": bool(mot),
        "home_rank": home.get("rank"),
        "home_points": home.get("points"),
        "away_rank": away.get("rank"),
        "away_points": away.get("points"),
        "home_tags": home.get("tags") or [],
        "away_tags": away.get("tags") or [],
        "motivation_gate_action": gate.get("action"),
        "motivation_level": lvl,
    }


def _lineup_dimension(rec: dict) -> dict[str, Any]:
    gate = rec.get("lineup_gate") or {}
    home = gate.get("home") or {}
    away = gate.get("away") or {}
    action = str(gate.get("lineup_action") or rec.get("lineup_action") or "LINEUP_UNKNOWN")
    if action in ("BOOST", "KEEP_WATCH"):
        risk = "LOW"
    elif action in ("WATCH_CAUTION", "KEEP_WATCH_LIGHT", "LINEUP_PENDING"):
        risk = "MEDIUM"
    else:
        risk = "HIGH"
    return {
        "lineup_available": bool(gate),
        "lineup_action": action,
        "home_attack_unit_available": home.get("attack_unit_available"),
        "away_attack_unit_available": away.get("attack_unit_available"),
        "home_rotation_count": home.get("rotation_count"),
        "away_rotation_count": away.get("rotation_count"),
        "lineup_risk_level": risk,
    }


def _flow_quality(shots_total: float, shots_on_target_total: float, corners_total: float, dangerous_attacks_total: float) -> str:
    if shots_total >= 6 or shots_on_target_total >= 3 or corners_total >= 4 or dangerous_attacks_total >= 25:
        return "GOOD"
    if shots_total >= 4 or shots_on_target_total >= 2 or corners_total >= 2 or dangerous_attacks_total >= 15:
        return "OK"
    return "POOR"


def _load_live_stats_index(date_key: str) -> dict[int, list[dict[str, Any]]]:
    path = ARCHIVE_DIR / f"live_stats_snapshot_{date_key}.jsonl"
    rows = _load_jsonl(path)
    idx: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        fid = _safe_int(row.get("fixture_id"), 0)
        if not fid:
            continue
        idx.setdefault(fid, []).append(row)
    for fid, lst in idx.items():
        lst.sort(key=lambda x: _safe_int(x.get("minute"), 0))
    return idx


def _match_flow_dimension(fixture_id: int, stats_index: dict[int, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = stats_index.get(int(fixture_id), [])
    rows = [r for r in rows if _safe_int(r.get("minute"), 0) <= 45]
    if not rows:
        return {
            "stats_available": False,
            "snapshot_minute": None,
            "ht_shots_total": 0.0,
            "ht_shots_on_target_total": 0.0,
            "ht_corners_total": 0.0,
            "ht_dangerous_attacks_total": 0.0,
            "tempo_supported": False,
            "pressure_supported": False,
            "flow_quality": "UNKNOWN",
        }
    row = rows[-1]
    shots_total = _safe_float(row.get("shots_total"), _safe_float(row.get("ht_shots_total"), 0.0))
    sot_total = _safe_float(row.get("shots_on_target_total"), _safe_float(row.get("ht_shots_on_target_total"), 0.0))
    corners_total = _safe_float(row.get("corners_total"), _safe_float(row.get("ht_corners_total"), 0.0))
    danger_total = _safe_float(row.get("dangerous_attacks_total"), _safe_float(row.get("ht_dangerous_attacks_total"), 0.0))
    flow = _flow_quality(shots_total, sot_total, corners_total, danger_total)
    return {
        "stats_available": True,
        "snapshot_minute": _safe_int(row.get("minute"), None),
        "ht_shots_total": shots_total,
        "ht_shots_on_target_total": sot_total,
        "ht_corners_total": corners_total,
        "ht_dangerous_attacks_total": danger_total,
        "tempo_supported": flow in ("GOOD", "OK"),
        "pressure_supported": flow == "GOOD",
        "flow_quality": flow,
    }


def _variance_dimension(pre_grade: str, ht_goal: bool, flow_quality: str) -> dict[str, Any]:
    luck_class = "NORMAL_VARIANCE"
    if pre_grade in ("A", "B", "C") and not ht_goal and flow_quality == "GOOD":
        luck_class = "UNLUCKY_MISS"
    elif pre_grade in ("A", "B", "C") and ht_goal and flow_quality == "POOR":
        luck_class = "LUCKY_HIT"
    elif pre_grade == "SKIP" and not ht_goal and flow_quality in ("POOR", "UNKNOWN"):
        luck_class = "FAIR_RESULT"
    elif pre_grade in ("A", "B", "C") and ht_goal and flow_quality in ("GOOD", "OK"):
        luck_class = "FAIR_RESULT"
    return {
        "luck_class": luck_class,
        "process_good_but_no_goal": pre_grade in ("A", "B", "C") and (not ht_goal) and flow_quality == "GOOD",
        "process_bad_but_goal": pre_grade in ("A", "B", "C") and ht_goal and flow_quality == "POOR",
    }


def _root_cause(
    diagnosis: str,
    pre_grade: str,
    ht_goal: bool,
    event_noise: list[str],
    context_noise: list[str],
    weather_dimension: dict[str, Any],
    market_dimension: dict[str, Any],
    bucket_hit: bool,
    match_flow_dimension: dict[str, Any],
    lineup_dimension: dict[str, Any],
    motivation_dimension: dict[str, Any],
    variance_dimension: dict[str, Any],
) -> tuple[str, list[str], str]:
    secondary: list[str] = []
    weather_tags = set(weather_dimension.get("weather_tags") or [])
    weather_noise = any(t in weather_tags for t in ("HEAVY_RAIN", "MODERATE_RAIN", "STRONG_WIND", "EXTREME_COLD", "EXTREME_HEAT", "WET_PITCH_RISK"))
    flow_quality = str(match_flow_dimension.get("flow_quality") or "UNKNOWN")
    lineup_action = str(lineup_dimension.get("lineup_action") or "")
    mot_tags = set((motivation_dimension.get("home_tags") or []) + (motivation_dimension.get("away_tags") or []))
    luck_class = str(variance_dimension.get("luck_class") or "NORMAL_VARIANCE")
    if diagnosis == "DATA_QUALITY_ISSUE":
        return "DATA_QUALITY", ["NORMAL_VARIANCE"], "HIGH"
    if lineup_action in ("DROP_ATTACK_WEAK", "DROP_HEAVY_ROTATION"):
        return "LINEUP_CHANGE", ["MATCH_FLOW"], "MEDIUM"
    if "MID_TABLE_SAFE" in mot_tags and not ht_goal and pre_grade in ("A", "B", "C"):
        return "MOTIVATION_MISREAD", ["MODEL_FEATURE"], "MEDIUM"
    if weather_noise and not ht_goal and pre_grade in ("A", "B", "C"):
        secondary = ["CONTEXT_NOISE"]
        return "WEATHER_NOISE", secondary, "MEDIUM"
    if any(x in event_noise for x in ("RED_CARD", "PENALTY", "OWN_GOAL", "VAR_PENALTY", "INJURY_SUB", "LATE_STOPPAGE_GOAL")):
        secondary = ["MATCH_FLOW"] if bucket_hit is False else ["NORMAL_VARIANCE"]
        return "EVENT_NOISE", secondary, "HIGH"
    if diagnosis in ("UNLUCKY_MISS", "LUCKY_HIT"):
        return "NORMAL_VARIANCE", ["MATCH_FLOW"], "LOW"
    if flow_quality == "POOR" and pre_grade in ("A", "B", "C") and not ht_goal:
        return "MATCH_FLOW", ["TIME_DISTRIBUTION"], "MEDIUM"
    if market_dimension.get("market_signal") == "MARKET_DIRECTION_CONFLICT":
        return "MARKET_SIGNAL", ["MODEL_FEATURE"], "MEDIUM"
    if diagnosis == "MODEL_OVERCONFIDENT":
        return "MODEL_FEATURE", ["TIME_DISTRIBUTION"], "MEDIUM"
    if diagnosis == "MODEL_TOO_STRICT":
        return "MODEL_FEATURE", ["MARKET_SIGNAL"], "MEDIUM"
    if diagnosis in ("NOISY_WIN", "NOISY_LOSS"):
        return "CONTEXT_NOISE", ["NORMAL_VARIANCE"], "LOW"
    if pre_grade in ("A", "B", "C") and ht_goal and not bucket_hit:
        return "TIME_DISTRIBUTION", ["NORMAL_VARIANCE"], "LOW"
    if pre_grade == "SKIP" and ht_goal:
        return "MODEL_FEATURE", ["NORMAL_VARIANCE"], "MEDIUM"
    if luck_class in ("UNLUCKY_MISS", "LUCKY_HIT"):
        return "NORMAL_VARIANCE", [], "LOW"
    return "NORMAL_VARIANCE", secondary, "LOW"


def _model_result(pre_grade: str, ht_goal: bool) -> str:
    if pre_grade in ("A", "B", "C"):
        return "MODEL_HIT" if ht_goal else "MODEL_MISS"
    return "MODEL_SKIP_BACKFIRE" if ht_goal else "MODEL_SKIP_CORRECT"


def _diagnosis(
    pre_grade: str,
    ht_goal: bool,
    event_noise: list[str],
    context_noise: list[str],
    time_bin_source: str,
    pred_bins: dict[str, float],
    sample_size: int,
    coverage_level: str,
    bucket_hit: bool,
    match_flow_dimension: dict[str, Any],
) -> str:
    noisy_win_tags = {"PENALTY", "OWN_GOAL", "LATE_STOPPAGE_GOAL", "VAR_PENALTY"}
    noisy_loss_tags = {"RED_CARD", "INJURY_SUB"}
    flow_quality = str(match_flow_dimension.get("flow_quality") or "UNKNOWN")
    if sample_size < 3:
        return "DATA_QUALITY_ISSUE"
    if time_bin_source in ("NONE", "", "-"):
        return "DATA_QUALITY_ISSUE"
    if sum(_safe_float(v, 0.0) for v in pred_bins.values()) <= 0:
        return "DATA_QUALITY_ISSUE"
    if coverage_level in ("UNKNOWN", ""):
        return "DATA_QUALITY_ISSUE"

    if pre_grade in ("A", "B", "C") and ht_goal:
        if noisy_win_tags.intersection(event_noise):
            return "NOISY_WIN"
        if flow_quality == "POOR":
            return "LUCKY_HIT"
        if bucket_hit and flow_quality == "GOOD":
            return "MODEL_VALID_STRONG"
        return "MODEL_VALID"
    if pre_grade in ("A", "B", "C") and not ht_goal:
        if noisy_loss_tags.intersection(event_noise) or context_noise:
            return "NOISY_LOSS"
        if flow_quality == "GOOD":
            return "UNLUCKY_MISS"
        return "MODEL_OVERCONFIDENT"
    if pre_grade == "SKIP" and ht_goal:
        if noisy_win_tags.intersection(event_noise) or noisy_loss_tags.intersection(event_noise):
            return "NOISY_WIN"
        return "MODEL_TOO_STRICT"
    if pre_grade == "SKIP" and not ht_goal:
        return "MODEL_VALID"
    return "CONTEXT_CHANGED"


def _format_single(row: dict) -> str:
    pred_peak = _top_predicted_bucket(row.get("predicted_bins") or {})
    return "\n".join(
        [
            "📌 V4 单场复盘",
            "",
            f"{row.get('home')} vs {row.get('away')}",
            "",
            "赛前：",
            f"等级 {row.get('pre_grade')}",
            f"HT评分 {row.get('pre_ht_score')}",
            f"time_bin_source {row.get('time_bin_source')}",
            f"预测剧本：{row.get('script_type')}",
            f"预测时间段（最高）：{pred_peak}",
            "",
            "赛果：",
            f"HT {row.get('ht_scoreline')}",
            f"FT {row.get('ft_scoreline')}",
            f"首球 {row.get('first_ht_goal_minute') if row.get('first_ht_goal_minute') is not None else '-'}'",
            f"命中时间段：{'是' if row.get('bucket_hit') else '否'}",
            "",
            "事件：",
            f"event_noise: {', '.join(row.get('event_noise') or ['无'])}",
            f"context_noise: {', '.join(row.get('context_noise') or ['无'])}",
            f"flow_quality: {(row.get('match_flow_dimension') or {}).get('flow_quality', 'UNKNOWN')}",
            f"weather_tags: {', '.join((row.get('weather_dimension') or {}).get('weather_tags') or ['NORMAL_WEATHER'])}",
            "",
            "归因：",
            f"{row.get('model_result')}",
            f"{row.get('diagnosis')}",
            f"root_cause: {row.get('root_cause_dimension')} ({row.get('root_cause_confidence')})",
            f"secondary: {', '.join(row.get('secondary_dimensions') or ['-'])}",
            "",
            "结论：",
            row.get("diagnosis_summary", "见诊断标签"),
        ]
    )


def run(date_str: str, fixture_id: int | None = None, sleep_ms: int = 120) -> dict[str, Any]:
    key = _date_key(date_str)
    scout_path = REPORT_DIR / f"scout_v4_{key}.json"
    scout = _load_json(scout_path, [])
    if isinstance(scout, dict):
        scout = scout.get("results") or []
    if not isinstance(scout, list) or not scout:
        return {"error": f"scout文件不存在或为空: {scout_path}"}

    stats_index = _load_live_stats_index(key)
    out_rows = []
    selected = [r for r in scout if (fixture_id is None or int(r.get("fixture_id") or 0) == int(fixture_id))]
    for rec in selected:
        fid = int(rec.get("fixture_id") or 0)
        if not fid:
            continue
        intel = explain_match(rec)
        ht_rec = intel.get("ht_recommendation") or {}
        pre_grade = str(ht_rec.get("grade") or "SKIP").upper()
        pre_ht_score = _safe_float(ht_rec.get("ht_score"), 0.0)
        pre_market_focus = str(rec.get("market_focus") or "-")
        time_bin_source = str(ht_rec.get("time_bins_source") or "NONE")
        script_type = str(ht_rec.get("script_type") or "-")
        pred_bins = ht_rec.get("time_bins") or {"0_15": 0.0, "16_30": 0.0, "31_45": 0.0}
        predicted_top_bucket = _top_predicted_bucket(pred_bins)
        sample_size = _safe_int(ht_rec.get("sample_size"), 0)
        coverage_level = str(((rec.get("data_coverage") or {}).get("coverage_level") or "")).upper()
        weather_dimension = _weather_dimension(rec)
        market_dimension = _market_dimension(rec, pre_grade=pre_grade)
        motivation_dimension = _motivation_dimension(rec)
        lineup_dimension = _lineup_dimension(rec)
        match_flow_dimension = _match_flow_dimension(fid, stats_index)

        f_resp = _api_get(f"fixtures?id={fid}")
        f_rows = f_resp.get("response") or []
        if not f_rows:
            continue
        item = f_rows[0]
        score = item.get("score") or {}
        ht = score.get("halftime") or {}
        ft = score.get("fulltime") or {}
        ht_home = _safe_int(ht.get("home"), 0)
        ht_away = _safe_int(ht.get("away"), 0)
        ft_home = _safe_int(ft.get("home"), 0)
        ft_away = _safe_int(ft.get("away"), 0)
        ht_goal = (ht_home + ht_away) > 0

        e_resp = _api_get(f"fixtures/events?fixture={fid}")
        events = e_resp.get("response") or []
        first_min, hit_bucket = _first_ht_goal_minute(events)
        bucket_hit = bool(ht_goal and first_min is not None and hit_bucket == predicted_top_bucket)
        event_noise = _event_noise_tags(events, first_min)
        event_noise_detail = _event_noise_detail(events, first_min)
        context_noise = _context_noise_tags(rec, weather_dimension=weather_dimension)

        model_result = _model_result(pre_grade, ht_goal)
        diagnosis = _diagnosis(
            pre_grade=pre_grade,
            ht_goal=ht_goal,
            event_noise=event_noise,
            context_noise=context_noise,
            time_bin_source=time_bin_source,
            pred_bins=pred_bins,
            sample_size=sample_size,
            coverage_level=coverage_level,
            bucket_hit=bucket_hit,
            match_flow_dimension=match_flow_dimension,
        )
        variance_dimension = _variance_dimension(pre_grade, ht_goal, str(match_flow_dimension.get("flow_quality") or "UNKNOWN"))
        if diagnosis == "MODEL_VALID":
            diag_summary = "模型判断有效，且无明显偶然性干扰。"
        elif diagnosis == "MODEL_VALID_STRONG":
            diag_summary = "模型强命中：命中时间段且比赛过程质量良好。"
        elif diagnosis == "MODEL_OVERCONFIDENT":
            diag_summary = "推荐未中且无明显噪音，模型偏乐观。"
        elif diagnosis == "MODEL_TOO_STRICT":
            diag_summary = "SKIP反杀且无明显噪音，跳过规则偏严。"
        elif diagnosis == "NOISY_WIN":
            diag_summary = "命中包含噪音事件，避免误判为稳定优势。"
        elif diagnosis == "NOISY_LOSS":
            diag_summary = "未命中受噪音事件影响，不宜直接调严规则。"
        elif diagnosis == "UNLUCKY_MISS":
            diag_summary = "过程支持但未进球，属于正常波动下的倒霉未中。"
        elif diagnosis == "LUCKY_HIT":
            diag_summary = "过程偏弱但命中，存在运气成分。"
        elif diagnosis == "DATA_QUALITY_ISSUE":
            diag_summary = "样本/分布/覆盖质量不足，先补数据。"
        else:
            diag_summary = "赛前赛中上下文变化，建议人工复核。"
        root_dim, second_dims, root_conf = _root_cause(
            diagnosis=diagnosis,
            pre_grade=pre_grade,
            ht_goal=ht_goal,
            event_noise=event_noise,
            context_noise=context_noise,
            weather_dimension=weather_dimension,
            market_dimension=market_dimension,
            bucket_hit=bucket_hit,
            match_flow_dimension=match_flow_dimension,
            lineup_dimension=lineup_dimension,
            motivation_dimension=motivation_dimension,
            variance_dimension=variance_dimension,
        )

        row = {
            "fixture_id": fid,
            "date": datetime.strptime(key, "%Y%m%d").strftime("%Y-%m-%d"),
            "home": rec.get("home"),
            "away": rec.get("away"),
            "league": rec.get("league"),
            "pre_grade": pre_grade,
            "pre_ht_score": round(pre_ht_score, 1),
            "pre_market_focus": pre_market_focus,
            "time_bin_source": time_bin_source,
            "script_type": script_type,
            "predicted_bins": {
                "0_15": round(_safe_float(pred_bins.get("0_15"), 0.0), 4),
                "16_30": round(_safe_float(pred_bins.get("16_30"), 0.0), 4),
                "31_45": round(_safe_float(pred_bins.get("31_45"), 0.0), 4),
            },
            "predicted_top_bucket": predicted_top_bucket,
            "ht_goal": ht_goal,
            "ht_scoreline": f"{ht_home}-{ht_away}",
            "ft_scoreline": f"{ft_home}-{ft_away}",
            "first_ht_goal_minute": first_min,
            "hit_bucket": hit_bucket,
            "bucket_hit": bucket_hit,
            "event_noise": event_noise,
            "event_noise_detail": event_noise_detail,
            "context_noise": context_noise,
            "weather_dimension": weather_dimension,
            "market_dimension": market_dimension,
            "motivation_dimension": motivation_dimension,
            "lineup_dimension": lineup_dimension,
            "match_flow_dimension": match_flow_dimension,
            "variance_dimension": variance_dimension,
            "model_result": model_result,
            "diagnosis": diagnosis,
            "diagnosis_summary": diag_summary,
            "root_cause_dimension": root_dim,
            "secondary_dimensions": second_dims,
            "root_cause_confidence": root_conf,
        }
        out_rows.append(row)
        time.sleep(max(sleep_ms, 0) / 1000.0)

    out_path: Path | None = None
    if fixture_id is None:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        out_path = ARCHIVE_DIR / f"v4_result_attribution_{key}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for row in out_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "date": key,
        "rows": len(out_rows),
        "output_path": str(out_path) if out_path else None,
        "main_file_written": fixture_id is None,
        "model_result_counts": {},
        "diagnosis_counts": {},
        "root_cause_counts": {},
    }
    for row in out_rows:
        summary["model_result_counts"][row["model_result"]] = summary["model_result_counts"].get(row["model_result"], 0) + 1
        summary["diagnosis_counts"][row["diagnosis"]] = summary["diagnosis_counts"].get(row["diagnosis"], 0) + 1
        rcd = str(row.get("root_cause_dimension") or "UNKNOWN")
        summary["root_cause_counts"][rcd] = summary["root_cause_counts"].get(rcd, 0) + 1

    if fixture_id is not None and out_rows:
        summary["single_report"] = _format_single(out_rows[0])
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD or YYYY-MM-DD")
    parser.add_argument("--fixture", type=int, default=None, help="单场复盘 fixture_id")
    parser.add_argument("--sleep-ms", type=int, default=120, help="API节流毫秒")
    args = parser.parse_args()
    result = run(args.date, fixture_id=args.fixture, sleep_ms=args.sleep_ms)
    if result.get("single_report"):
        print(result["single_report"])
        print("\n" + "-" * 50 + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "single_report"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
