"""
V4 交互式情报仪表盘
==================
读取 scout_v4_YYYYMMDD.json + live_watchlist_YYYYMMDD.json，生成本地 HTML。

用法:
  python3 engine/v4_dashboard.py --date 20260511
  python3 engine/v4_dashboard.py --date 2026-05-11 --open
"""

from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
DASHBOARD_DIR = BASE_DIR / "docs" / "v4_dashboards"

try:
    from engine.team_cn_map import strict_match as team_name_cn
except Exception:
    def team_name_cn(name: str) -> str:
        return name

try:
    from engine.v4_match_intelligence import explain_match
except Exception:
    def explain_match(record: dict) -> dict:
        return {
            "match_type": ["NO_CLEAR_EDGE"],
            "primary_direction": "SKIP",
            "trade_action": "跳过：只记录情报",
            "confidence": 0,
            "profile": "画像：解释器不可用",
            "summary": "结论：不作为交易候选",
            "why": [],
            "wait_for": [],
            "avoid_if": [],
            "execution_status": "球探观察",
            "is_live_radar": False,
            "action_code": "INFO_ONLY",
            "recommendation_bucket": "INFO_ONLY",
        }


MARKET_LABELS = {
    "HT_LIVE_OVER": "上半场走地",
    "SECOND_HALF_OVER": "下半场大球参考",
    "FULLTIME_OVER": "全场大球参考",
}

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _ops_window(date_key: str) -> tuple[datetime, datetime] | None:
    """
    运营日窗口：
    D日 12:00:00（含） -> D+1日 12:00:00（不含）
    例如：20260514 表示 05-14 12:00 到 05-15 11:59:59。
    """
    if not date_key or len(date_key) != 8:
        return None
    try:
        start = datetime.strptime(date_key, "%Y%m%d").replace(
            hour=12, minute=0, second=0, microsecond=0, tzinfo=LOCAL_TZ
        )
        end = start + timedelta(days=1)
        return start, end
    except Exception:
        return None


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _pct(x) -> str:
    try:
        return f"{float(x) * 100:.0f}%"
    except Exception:
        return "-"


def _float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _line_float(line) -> float:
    return _float(str(line).replace("Over", "").replace("Under", "").strip(), 0.0)


def _over_odds_float(line_row: dict) -> float:
    return _float(line_row.get("over"), 0.0)


def _parse_kickoff_local(kickoff: str) -> datetime | None:
    if not kickoff:
        return None
    try:
        dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(LOCAL_TZ)
    except Exception:
        return None


def _ko_time(kickoff: str) -> str:
    dt = _parse_kickoff_local(kickoff)
    if dt is not None:
        return dt.strftime("%H:%M")
    return kickoff[-8:-3] if len(kickoff) >= 5 else kickoff


def _ko_time_label(kickoff: str) -> str:
    dt = _parse_kickoff_local(kickoff)
    if dt is not None:
        return dt.strftime("%m-%d %H:%M")
    return kickoff or ""


def _ko_local_date_key(kickoff: str) -> str:
    dt = _parse_kickoff_local(kickoff)
    if dt is not None:
        return dt.strftime("%Y%m%d")
    return ""


def _in_session_window(kickoff: str, date_key: str) -> bool:
    if not date_key:
        return True
    ko_date = _ko_local_date_key(kickoff)
    return (ko_date == date_key) if ko_date else True


def _in_ops_window(kickoff: str, date_key: str) -> bool:
    """
    可选运营日窗口：
    D日12:00 -> D+1日11:59。
    """
    if not date_key:
        return True
    ko = _parse_kickoff_local(kickoff)
    if ko is None:
        return True
    window = _ops_window(date_key)
    if window is None:
        return True
    start, end = window
    return start <= ko < end


def _kickoff_sort_value(kickoff: str) -> int:
    ko = _parse_kickoff_local(kickoff)
    if ko is None:
        return 32503680000  # year 3000, put unknown kickoff at end
    return int(ko.timestamp())


def _story_label(tb: dict) -> str:
    p0_15 = _float(tb.get("0_15"))
    p16_30 = _float(tb.get("16_30"))
    p31_45 = _float(tb.get("31_45"))
    if p31_45 >= max(p0_15, p16_30) and p31_45 >= 0.45:
        return "慢热绝杀型"
    if p0_15 >= 0.35:
        return "开局冲击型"
    if p16_30 >= max(p0_15, p31_45):
        return "中段发力型"
    return "均衡波动型"


def _opening_pressure_text(factors: dict) -> str:
    threat = _float(factors.get("both_sides_ht_threat"))
    if threat >= 0.60:
        return f"🟢 高 (前场威胁 {_pct(threat)})"
    if threat >= 0.45:
        return f"🟡 中 (前场威胁 {_pct(threat)})"
    return f"⚠️ 低 (前场威胁 {_pct(threat)})"


def _poisson_ev(expected_goals: float, line: float, odds: float) -> tuple[float, float, float]:
    expected_goals = _float(expected_goals)
    line = _float(line)
    odds = _float(odds)
    if expected_goals <= 0 or odds <= 1.0:
        return 0.0, 0.0, 0.0

    import math
    p0 = math.exp(-expected_goals)
    p1 = expected_goals * p0
    p2 = 1 - p0 - p1

    if abs(line - 0.75) < 1e-9:
        ev05, fair05, win05 = _poisson_ev(expected_goals, 0.5, odds)
        ev10, fair10, win10 = _poisson_ev(expected_goals, 1.0, odds)
        return round((ev05 + ev10) / 2, 1), round((fair05 + fair10) / 2, 2), round((win05 + win10) / 2, 1)
    if abs(line - 1.25) < 1e-9:
        ev10, fair10, win10 = _poisson_ev(expected_goals, 1.0, odds)
        ev15, fair15, win15 = _poisson_ev(expected_goals, 1.5, odds)
        return round((ev10 + ev15) / 2, 1), round((fair10 + fair15) / 2, 2), round((win10 + win15) / 2, 1)

    if abs(line - 1.5) < 1e-9:
        win_prob = p2
        ev = (win_prob * odds) - 1
        fair_odds = 1 / win_prob if win_prob > 0 else 0.0
    elif abs(line - 1.0) < 1e-9:
        win_prob = p2
        push_prob = p1
        lose_prob = p0
        ev = (win_prob * (odds - 1)) - lose_prob
        fair_odds = (1 - push_prob) / win_prob if win_prob > 0 else 0.0
    elif abs(line - 0.5) < 1e-9:
        win_prob = 1 - p0
        ev = (win_prob * odds) - 1
        fair_odds = 1 / win_prob if win_prob > 0 else 0.0
    else:
        anchor = min([0.5, 1.0, 1.5], key=lambda x: abs(x - line))
        return _poisson_ev(expected_goals, anchor, odds)

    return round(ev * 100, 1), round(fair_odds, 2), round(win_prob * 100, 1)


def calculate_hotness(factors: dict) -> float:
    scores = factors.get("market_scores") or {}
    if scores:
        return round(max(_float(v) for v in scores.values()), 1)
    h2h_rate = _float(factors.get("h2h_ht_goal_rate"))
    recent_form = _float(factors.get("recent_form_avg"))
    tb = factors.get("time_bins", {}) or {}
    late_goal_prob = _float(tb.get("31_45"))
    ht_score = (h2h_rate * 0.5) + (recent_form * 0.3) + (late_goal_prob * 0.2)

    sh_tb = factors.get("second_half_bins", {}) or {}
    sh_score = (
        _float(factors.get("h2h_sh_goal_rate")) * 0.5
        + _float(factors.get("recent_sh_avg")) * 0.3
        + max([_float(v) for v in sh_tb.values()] or [0.0]) * 0.2
    )
    ft_score = (
        _float(factors.get("h2h_ft_over_1_5_rate")) * 0.55
        + _float(factors.get("recent_ft_over_1_5")) * 0.30
        + _float(factors.get("h2h_avg_ft_goals")) / 4.0 * 0.15
    )
    return round(max(ht_score, sh_score, ft_score) * 100, 1)


def tier(score: float) -> str:
    if score >= 90:
        return "S"
    if score >= 80:
        return "A"
    return "B"


def _best_line(lines: list[dict]) -> dict:
    if not lines:
        return {}
    preferred_order = [1.0, 1.25, 0.75, 1.5, 0.5, 1.75]
    line_rank = {v: i for i, v in enumerate(preferred_order)}

    scored = []
    for ln in lines:
        line_val = _line_float(ln.get("line"))
        over_dec = _over_odds_float(ln)
        # Asian principal line: over水位最接近1（HK赔率）≈ decimal最接近2.00。
        if over_dec > 1.0:
            water = over_dec - 1.0
            water_distance = abs(water - 1.0)
        else:
            # 无法识别赔率时，降低优先级，走线值兜底
            water_distance = 999.0
        scored.append((water_distance, line_rank.get(line_val, 999), abs(line_val - 1.25), ln))

    scored.sort(key=lambda x: (x[0], x[1], x[2]))
    return scored[0][3] if scored else {}


def _line_text(lines: list[dict]) -> str:
    parts = []
    for ln in sorted(lines, key=lambda x: _line_float(x.get("line"))):
        line = ln.get("line", "?")
        over = ln.get("over", "-")
        parts.append(f"大{line}@{over}")
    return " | ".join(parts) if parts else "暂无盘口"


def _injury_text(injury: dict) -> str:
    if not injury:
        return "未知"
    home = injury.get("home", {})
    away = injury.get("away", {})
    if home.get("status") == "healthy" and away.get("status") == "healthy":
        return "双方全员健康"
    bits = []
    for label, item in [("主", home), ("客", away)]:
        n = item.get("missing_count")
        if n:
            bits.append(f"{label}缺{n}")
    return " / ".join(bits) if bits else "无核心伤停"


def _lineup_text(lineup_gate: dict | None) -> str:
    if not lineup_gate:
        return "未检查"
    action = lineup_gate.get("lineup_action", "UNKNOWN")
    reason = lineup_gate.get("lineup_reason", "")
    detail = []
    for label, side in (("主", lineup_gate.get("home", {}) or {}), ("客", lineup_gate.get("away", {}) or {})):
        if side.get("lineup_signal") in ("LINEUP_PENDING", "LINEUP_UNKNOWN"):
            continue
        detail.append(
            f"{label}攻核{side.get('attack_core_present','-')}/{side.get('attack_core_count','-')}"
            f" 防核{side.get('defense_core_present','-')}/{side.get('defense_core_count','-')}"
            f" {side.get('attack_signal','-')}/{side.get('defense_signal','-')}"
        )
    suffix = " · " + " | ".join(detail) if detail else ""
    return f"{action} · {reason}{suffix}"


def _enrich_records(
    scout: list[dict],
    watchlist: list[dict],
    live_status: dict | list | None = None,
    entries: list[dict] | None = None,
    date_key: str = "",
    window_mode: str = "natural",
) -> list[dict]:
    watch_by_id = {str(x.get("fixture_id")): x for x in watchlist}
    status_rows = live_status.get("statuses", []) if isinstance(live_status, dict) else (live_status or [])
    status_by_id = {str(x.get("fixture_id")): x for x in status_rows}
    entry_by_id = {str(x.get("fixture_id")): x for x in (entries or [])}
    rows = []
    for rec in scout:
        ko = str(rec.get("kickoff", "") or "")
        if date_key:
            if window_mode == "ops":
                ok = _in_ops_window(ko, date_key)
            else:
                ok = _in_session_window(ko, date_key)
            if not ok:
                continue
        f = rec.get("factors", {}) or {}
        lines = rec.get("ht_ou_lines", []) or []
        score = calculate_hotness(f)
        watch = watch_by_id.get(str(rec.get("fixture_id")))
        live = status_by_id.get(str(rec.get("fixture_id")))
        entry = entry_by_id.get(str(rec.get("fixture_id")))
        best = _best_line(lines)
        tb = f.get("time_bins", {}) or {}
        row = {
            **rec,
            "hotness_score": score,
            "tier": tier(score),
            "is_watch": bool(watch),
            "live_status": live,
            "live_entry": entry,
            "pre_ht_line": best.get("line", ""),
            "pre_ht_line_float": _line_float(best.get("line")),
            "pre_over_odds": best.get("over", ""),
            "time_hotspot": max(tb, key=tb.get) if tb else "",
            "lineup_gate": rec.get("lineup_gate") or (watch or {}).get("lineup_gate"),
        }
        rows.append(row)
    return sorted(rows, key=lambda x: x.get("kickoff", ""))


def _rows_json(rows: list[dict]) -> str:
    compact = []
    for r in rows:
        f = r.get("factors", {}) or {}
        tb = f.get("time_bins", {}) or {}
        sh_tb = f.get("second_half_bins", {}) or {}
        rcov = r.get("data_coverage", {}) or {}
        baseline = r.get("league_baseline", {}) or {}
        baseline_adj = baseline.get("adjustment", {}) or {}
        season_phase = r.get("season_phase", {}) or {}
        phase_adj = season_phase.get("adjustment", {}) or {}
        motivation = r.get("motivation", {}) or {}
        motivation_gate = motivation.get("gate", {}) or {}
        home_mot = motivation.get("home", {}) or {}
        away_mot = motivation.get("away", {}) or {}
        schedule_pressure = r.get("schedule_pressure", {}) or {}
        home_sched = schedule_pressure.get("home", {}) or {}
        away_sched = schedule_pressure.get("away", {}) or {}
        live_status = r.get("live_status") or {}
        live_entry = r.get("live_entry") or {}
        entry_line = str(live_entry.get("entry_line", "") or "").strip()
        entry_odds = str(live_entry.get("entry_over_odds", "") or "").strip()
        has_live_line = entry_line not in ("", "-", "None", "null")
        has_live_odds = entry_odds not in ("", "-", "None", "null")
        display_line = entry_line if has_live_line else str(r.get("pre_ht_line", "") or "")
        display_odds = entry_odds if has_live_odds else str(r.get("pre_over_odds", "") or "")
        display_source = "走地" if has_live_line else "赛前参考"
        line_num = _line_float(display_line)
        odds_num = _float(display_odds)
        model_xg = _float(f.get("h2h_avg_ht_goals"))
        implied_pct = (100.0 / odds_num) if odds_num > 1 else 0.0
        ev_pct, fair_odds, win_prob = _poisson_ev(model_xg, line_num, odds_num)
        story_label = _story_label(tb)
        pressure_text = _opening_pressure_text(f)
        p0_15 = _float(tb.get("0_15"))
        p16_30 = _float(tb.get("16_30"))
        p31_45 = _float(tb.get("31_45"))
        threat_val = _float(f.get("both_sides_ht_threat"))
        ev_conclusion = "仅作为赛前情报参考，不作为自动下注指令。"
        action_plan_1 = "👉 建议: 先看HT推荐等级和时间分布。"
        action_plan_2 = "👉 执行: 是否投注与入场时机由你人工决定。"
        action_plan_3 = "👉 验证: 赛后核对 HT是否有球 与 时间段命中。"
        scores = r.get("market_scores") or f.get("market_scores") or {}
        market_focus = r.get("market_focus") or "HT_LIVE_OVER"
        intelligence = explain_match(r)
        recommendation_bucket = intelligence.get("display_bucket") or intelligence.get("recommendation_bucket", "INFO_ONLY")
        is_live_radar = bool(intelligence.get("is_live_radar"))
        execution_status = intelligence.get("execution_status", "球探观察")
        trade_action = intelligence.get("trade_action", "跳过：只记录情报")
        action_code = intelligence.get("action_code", "SKIP")
        risk_level = intelligence.get("risk_level", "MID")
        ht_decision = intelligence.get("ht_decision") or {}
        ht_rec = intelligence.get("ht_recommendation") or {}
        sh_observation = intelligence.get("sh_observation") or None
        live_action = live_status.get("action", "-")
        if live_action == "SKIP_RISK_GUARD":
            action_code = "RISK_BLOCKED"
            risk_level = "HIGH"
            recommendation_bucket = "HT_MAIN" if market_focus == "HT_LIVE_OVER" else recommendation_bucket
        # 时间分布统一使用推荐器输出的 effective time bins
        rec_tb = (ht_rec.get("time_bins") or {}) if isinstance(ht_rec, dict) else {}
        if rec_tb:
            p0_15 = _float(rec_tb.get("0_15"))
            p16_30 = _float(rec_tb.get("16_30"))
            p31_45 = _float(rec_tb.get("31_45"))
            story_label = ht_rec.get("script_type") or _story_label(rec_tb)
        if action_code == "RISK_BLOCKED":
            strategy_state = "回避"
            strategy_state_class = "plan-red"
            strategy_state_text = "🔴 风控拦截: 暂停执行，等待风险解除。"
        elif (ht_rec.get("grade") or "").upper() == "A":
            strategy_state = "可打"
            strategy_state_class = "plan-green"
            strategy_state_text = "🟢 推荐: A级上半场情报，优先关注。"
        elif (ht_rec.get("grade") or "").upper() == "SKIP":
            strategy_state = "回避"
            strategy_state_class = "plan-red"
            strategy_state_text = "🔴 跳过: 上半场不推荐。"
        else:
            strategy_state = "观望"
            strategy_state_class = "plan-yellow"
            strategy_state_text = "🟡 观望: 作为情报观察样本。"
        decision_summary = f"{intelligence.get('profile', '')}。{intelligence.get('summary', '')}"
        match_profile = intelligence.get("profile", "")
        home = r.get("home") or ""
        away = r.get("away") or ""
        home_cn = team_name_cn(home)
        away_cn = team_name_cn(away)
        rec_grade = (ht_rec.get("grade") or "").upper()
        is_ht_recommend = rec_grade in ("A", "B")
        is_ht_observe = rec_grade == "C"
        is_ht_skip = rec_grade == "SKIP" or recommendation_bucket == "HT_SKIP"
        is_sh_observe = recommendation_bucket == "SH_OBSERVE" or bool(sh_observation)
        is_ht_pool = is_ht_recommend or is_ht_observe or is_ht_skip
        if is_ht_recommend and rec_grade == "A":
            tier_head = "A级 | 上半场强推荐"
        elif is_ht_recommend and rec_grade == "B":
            tier_head = "B级 | 上半场达标推荐"
        elif is_ht_observe:
            tier_head = "C级 | 仅情报观察"
        elif is_ht_skip:
            tier_head = "HT跳过 | 条件不足"
        elif is_sh_observe:
            tier_head = "SH观察池 | 非HT推荐"
        else:
            tier_head = "HT_SKIP | 上半场不推荐"
        if is_ht_recommend:
            display_bucket = "HT_MAIN"
        elif is_ht_observe:
            display_bucket = "HT_OBSERVE"
        elif is_ht_skip:
            display_bucket = "HT_SKIP"
        elif is_sh_observe:
            display_bucket = "SH_OBSERVE"
        else:
            display_bucket = "INFO_ONLY"
        if is_ht_recommend:
            action_plan_1 = "👉 建议: 今日上半场重点盯盘。"
            action_plan_2 = "👉 执行: 根据你自己的盘口/赔率偏好决定是否入场。"
            action_plan_3 = "👉 验证: 赛后核对HT是否有球与时间段命中。"
        elif is_ht_observe:
            action_plan_1 = "👉 建议: 保留观察，不进入主推荐。"
            action_plan_2 = "👉 执行: 临场如节奏异常增强，可人工升级关注。"
            action_plan_3 = "👉 验证: 赛后记录时间段命中率。"
        elif is_ht_skip:
            action_plan_1 = "👉 HT处理: 本场不进入上半场推荐。"
            action_plan_2 = "👉 原因: 上半场基因不足或条件不达标。"
            action_plan_3 = "👉 后续: 仅保留信息，不设上半场触发。"
        compact.append({
            "fixture_id": r.get("fixture_id"),
            "home": home_cn,
            "away": away_cn,
            "homeEn": home,
            "awayEn": away,
            "league": r.get("league"),
            "time": _ko_time(r.get("kickoff", "")),
            "timeLabel": _ko_time_label(r.get("kickoff", "")),
            "kickoffSort": _kickoff_sort_value(r.get("kickoff", "")),
            "hotness": r.get("hotness_score"),
            "tier": r.get("tier"),
            "tierHead": tier_head,
            "is_watch": is_live_radar,
            "executionStatus": execution_status,
            "tradeAction": trade_action,
            "actionCode": action_code,
            "riskLevel": risk_level,
            "evLabel": intelligence.get("ev_label", "EV观察"),
            "executionLabel": intelligence.get("execution_label", "仅观察"),
            "decisionSummary": decision_summary,
            "matchProfile": match_profile,
            "intelligence": intelligence,
            "matchTypes": " / ".join(intelligence.get("match_type", [])),
            "primaryDirection": intelligence.get("primary_direction", "-"),
            "confidence": intelligence.get("confidence", 0),
            "whyText": "；".join(intelligence.get("why", [])),
            "whyTop": intelligence.get("why", [])[:3],
            "waitForText": "；".join(intelligence.get("wait_for", [])),
            "avoidIfText": "；".join(intelligence.get("avoid_if", [])),
            "riskTop": intelligence.get("avoid_if", [])[:2],
            "liveAction": live_status.get("action", "-"),
            "liveReason": live_status.get("reason", "-"),
            "liveScore": (live_status.get("state") or {}).get("score", "-"),
            "liveMinute": (live_status.get("state") or {}).get("minute", "-"),
            "entryLine": live_entry.get("entry_line", "-"),
            "entryOdds": live_entry.get("entry_over_odds", "-"),
            "marketFocus": market_focus,
            "marketLabel": MARKET_LABELS.get(market_focus, market_focus),
            "recommendationBucket": display_bucket,
            "isHtMain": bool(is_ht_pool),
            "isHtRecommendation": bool(is_ht_recommend),
            "isHtObserve": bool(is_ht_observe),
            "isHtSkip": bool(is_ht_skip),
            "isShObserve": bool(is_sh_observe),
            "htDecisionAction": ht_decision.get("action", ""),
            "htDecisionReason": ht_decision.get("reason", ""),
            "htRecGrade": rec_grade or "-",
            "htRecStatus": ht_rec.get("status", "-"),
            "htRecReason": ht_rec.get("reason", ""),
            "htRecScriptType": ht_rec.get("script_type", "-"),
            "htRecReasons": "；".join(ht_rec.get("reasons", []) or []),
            "htRecRisks": "；".join(ht_rec.get("risks", []) or []),
            "htRecRiskTop": ht_rec.get("risk_top", ""),
            "htRecRiskSeverity": ht_rec.get("risk_severity", ""),
            "htRecSampleSize": ht_rec.get("sample_size", 0),
            "htRecRuleVersion": ht_rec.get("rule_version", "-"),
            "htRecTimeBinsSource": ht_rec.get("time_bins_source", "-"),
            "htRecDirectionFocus": ht_rec.get("direction_focus", "-"),
            "bestFocusByScore": r.get("best_focus_by_score") or f.get("best_focus_by_score") or "",
            "htScore": _float(scores.get("HT_LIVE_OVER")),
            "shScore": _float(scores.get("SECOND_HALF_OVER")),
            "ftScore": _float(scores.get("FULLTIME_OVER")),
            "phaseBias": f.get("phase_bias", "BALANCED"),
            "h2h": _float(f.get("h2h_ht_goal_rate")),
            "h2hText": _pct(f.get("h2h_ht_goal_rate")),
            "h2hCountText": f"{f.get('h2h_ht_goal_count', '-')}/{f.get('h2h_sample_size', '-')}",
            "htStrictPass": bool(f.get("ht_strict_pass")),
            "htGateModel": f.get("ht_gate_model", ""),
            "recentTimingFit": f.get("recent_timing_fit", "-"),
            "dataCoverageLevel": rcov.get("coverage_level", "-"),
            "dataGateAction": rcov.get("data_gate_action", "-"),
            "leagueHtEnv": baseline.get("ht_env", "-"),
            "leagueShEnv": baseline.get("sh_env", "-"),
            "leagueHtRate": _pct(baseline.get("ht_goal_rate")),
            "leagueShRate": _pct(baseline.get("sh_goal_rate")),
            "leagueFtRate": _pct(baseline.get("ft_over_1_5_rate")),
            "leagueSample": baseline.get("sample_size", 0),
            "leagueAdjustment": baseline_adj.get("action", "-"),
            "seasonPhase": season_phase.get("phase", "-"),
            "seasonProgress": _pct(season_phase.get("progress_pct")),
            "seasonCompleted": season_phase.get("completed", 0),
            "seasonTotal": season_phase.get("total", 0),
            "remainingRounds": season_phase.get("remaining_rounds_est", "-"),
            "phaseAdjustment": phase_adj.get("action", "-"),
            "motivationGate": motivation_gate.get("action", "-"),
            "motivationReason": motivation_gate.get("reason", "-"),
            "motivationScore": motivation_gate.get("score", "-"),
            "homeRank": home_mot.get("rank", "-"),
            "awayRank": away_mot.get("rank", "-"),
            "homeMotTags": ", ".join(home_mot.get("tags", []) or ["-"]),
            "awayMotTags": ", ".join(away_mot.get("tags", []) or ["-"]),
            "scheduleAction": schedule_pressure.get("action", "-"),
            "scheduleLevel": schedule_pressure.get("level", "-"),
            "scheduleReason": schedule_pressure.get("reason", "-"),
            "homeSchedule": f"{home_sched.get('games_next_7d','-')}场/7天 · 最短{home_sched.get('min_gap_days','-')}天",
            "awaySchedule": f"{away_sched.get('games_next_7d','-')}场/7天 · 最短{away_sched.get('min_gap_days','-')}天",
            "shText": _pct(f.get("h2h_sh_goal_rate")),
            "ftOverText": _pct(f.get("h2h_ft_over_1_5_rate")),
            "avgGoals": f.get("h2h_avg_ht_goals", "-"),
            "avgShGoals": f.get("h2h_avg_sh_goals", "-"),
            "avgFtGoals": f.get("h2h_avg_ft_goals", "-"),
            "momentum": _float(f.get("recent_form_avg")),
            "momentumText": _pct(f.get("recent_form_avg")),
            "homeHtScored": _pct(f.get("home_recent_ht_scored")),
            "homeHtConceded": _pct(f.get("home_recent_ht_conceded")),
            "awayHtScored": _pct(f.get("away_recent_ht_scored")),
            "awayHtConceded": _pct(f.get("away_recent_ht_conceded")),
            "homeAttackVsAwayDefense": _pct(f.get("home_attack_vs_away_defense")),
            "awayAttackVsHomeDefense": _pct(f.get("away_attack_vs_home_defense")),
            "htAttackVsDefense": _pct(f.get("ht_attack_vs_defense")),
            "bothSidesHtThreat": _pct(f.get("both_sides_ht_threat")),
            "secondMomentumText": _pct(f.get("recent_sh_avg")),
            "homeRecent": _pct(f.get("home_recent_ht_over")),
            "awayRecent": _pct(f.get("away_recent_ht_over")),
            "homeRecentSh": _pct(f.get("home_recent_sh_over")),
            "awayRecentSh": _pct(f.get("away_recent_sh_over")),
            "bins": {
                "0-10": _pct(tb.get("0_10")),
                "11-15": _pct(tb.get("11_15")),
                "0-15": _pct(tb.get("0_15")),
                "11-30": _pct(tb.get("11_30")),
                "11-45": _pct(tb.get("11_45")),
                "16-30": _pct(tb.get("16_30")),
                "16-45": _pct(tb.get("16_45")),
                "31-45": _pct(tb.get("31_45")),
            },
            "lateFhPressure": _pct(f.get("late_fh_pressure")),
            "pullbackFit": f.get("pullback_fit", "-"),
            "earlyOnlyFlag": bool(f.get("early_only_flag")),
            "binsSecond": {
                "46-60": _pct(sh_tb.get("46_60")),
                "61-75": _pct(sh_tb.get("61_75")),
                "76-90": _pct(sh_tb.get("76_90")),
            },
            "hotspot": r.get("time_hotspot", ""),
            "line": r.get("pre_ht_line", ""),
            "lineFloat": r.get("pre_ht_line_float", 0),
            "overOdds": r.get("pre_over_odds", ""),
            "displayLine": display_line,
            "displayOdds": display_odds,
            "displayLineSource": display_source,
            "storyLabel": story_label,
            "pressureText": pressure_text,
            "modelXg": round(model_xg, 2),
            "lineNum": line_num,
            "oddsNum": round(odds_num, 2) if odds_num else 0.0,
            "impliedPct": round(implied_pct, 1),
            "evPct": ev_pct,
            "fairOdds": fair_odds,
            "winProb": win_prob,
            "evConclusion": ev_conclusion,
            "actionPlan1": action_plan_1,
            "actionPlan2": action_plan_2,
            "actionPlan3": action_plan_3,
            "strategyState": strategy_state,
            "strategyStateClass": strategy_state_class,
            "strategyStateListClass": "list-state-green" if strategy_state_class == "plan-green" else ("list-state-red" if strategy_state_class == "plan-red" else "list-state-yellow"),
            "strategyStateText": strategy_state_text,
            "p0_15": _pct(p0_15),
            "p16_30": _pct(p16_30),
            "p31_45": _pct(p31_45),
            "linesText": _line_text(r.get("ht_ou_lines", [])),
            "injuryText": _injury_text(r.get("injury", {})),
            "lineupText": _lineup_text(r.get("lineup_gate")),
            "lineupAction": (r.get("lineup_gate") or {}).get("lineup_action", "NOT_CHECKED"),
        })
    return json.dumps(compact, ensure_ascii=False)


def render_dashboard(date_str: str, window_mode: str = "natural") -> Path:
    key = _date_key(date_str)
    scout_path = REPORT_DIR / f"scout_v4_{key}.json"
    scout = _load_json(scout_path, [])
    watchlist = _load_json(REPORT_DIR / f"live_watchlist_{key}.json", [])
    live_status = _load_json(BASE_DIR / "data" / "live_monitor" / f"v4_live_status_{key}.json", {})
    live_entries = _load_json(BASE_DIR / "data" / "paper_trading" / f"v4_live_entries_{key}.json", [])
    review = _load_json(REPORT_DIR / f"v4_review_{key}.json", {})
    validation = _load_json(REPORT_DIR / f"v4_ht_recommend_validation_{key}.json", {})
    if not scout:
        raise FileNotFoundError(f"没有可渲染的 V4 情报数据: {scout_path}")
    rows = _enrich_records(
        scout if isinstance(scout, list) else [],
        watchlist if isinstance(watchlist, list) else [],
        live_status,
        live_entries if isinstance(live_entries, list) else [],
        key,
        window_mode,
    )

    counts = {"S": 0, "A": 0, "B": 0}
    for r in rows:
        counts[r["tier"]] += 1

    # 健康面板：验证文件 > 复盘文件 > 空
    hp = {}
    if isinstance(validation, dict) and validation.get("total_matches"):
        grades = validation.get("per_grade", {})
        funnel = validation.get("funnel", {}) or {}
        monotonic = validation.get("monotonicity", {}) or {}
        cov = validation.get("coverage_monitor", {}) or {}
        total = validation.get("total_matches", 0)
        pending = validation.get("pending_matches", total)
        completed = total - pending
        c_data = grades.get("C", {})
        ab_rate = round(float(funnel.get("a_plus_b_hit_rate_pct", 0.0)), 1)
        c_rate = round(c_data.get("hit_rate_pct", 0), 1)
        flags = []
        if str(monotonic.get("status", "UNKNOWN")) == "FAIL":
            flags.append("分级单调性失败")
        cov_health = str(cov.get("health", "OK"))
        if cov_health == "LOW":
            flags.append("A+B覆盖率偏低")
        elif cov_health == "HIGH":
            flags.append("A+B覆盖率偏高")
        health_status = "GREEN"
        if completed == 0:
            health_status = "UNKNOWN"
        elif flags:
            health_status = "YELLOW"
        hp = {
            "health_status": health_status,
            "kill_criteria_flags": flags,
            "sample_progress": {
                "sample_size": completed,
                "min_sample": total,
                "progress_pct": round(completed / max(total, 1) * 100, 1),
            },
            "execution_quality": {
                "conservative_fill_roi_pct": ab_rate,
                "slippage_adjusted_roi_pct": c_rate,
            },
        }
    elif isinstance(review, dict):
        hp = review.get("health_panel", {}) or {}
    sp = hp.get("sample_progress", {}) if isinstance(hp, dict) else {}
    ex = hp.get("execution_quality", {}) if isinstance(hp, dict) else {}
    flags = hp.get("kill_criteria_flags", []) if isinstance(hp, dict) else []
    health_status = str(hp.get("health_status", "UNKNOWN"))
    health_class = "health-yellow"
    if health_status == "GREEN":
        health_class = "health-green"
    elif health_status == "RED":
        health_class = "health-red"
    flags_text = "；".join(flags) if flags else "无触发"

    data_json = _rows_json(rows)
    title = f"V4 作战仪表盘 | {date_str}"
    mode_text = "北京时间自然日 00:00-23:59" if window_mode != "ops" else "运营日 12:00-次日11:59"
    
    # 发现所有可用日期，嵌入全量数据以便日期切换
    available_dates = sorted(
        {p.stem.replace("scout_v4_", "") for p in REPORT_DIR.glob("scout_v4_*.json")},
        reverse=True
    )
    date_options = "".join(
        f'<option value="{d}"{" selected" if d == date_str else ""}>{d[:4]}-{d[4:6]}-{d[6:8]}</option>'
        for d in available_dates
    ) if available_dates else f'<option>{date_str}</option>'
    
    # 嵌入所有日期的数据
    all_rows_json = {}
    for d in available_dates:
        d_scout = _load_json(REPORT_DIR / f"scout_v4_{d}.json", [])
        d_watch = _load_json(REPORT_DIR / f"live_watchlist_{d}.json", [])
        d_live = _load_json(BASE_DIR / "data" / "live_monitor" / f"v4_live_status_{d}.json", {})
        d_entry = _load_json(BASE_DIR / "data" / "paper_trading" / f"v4_live_entries_{d}.json", [])
        d_review = _load_json(REPORT_DIR / f"v4_review_{d}.json", {})
        d_valid = _load_json(REPORT_DIR / f"v4_ht_recommend_validation_{d}.json", {})
        try:
            d_rows = _enrich_records(
                d_scout if isinstance(d_scout, list) else [],
                d_watch if isinstance(d_watch, list) else [],
                d_live, d_entry if isinstance(d_entry, list) else [],
                d, window_mode,
            )
            d_json_rows = json.loads(_rows_json(d_rows))
            # 健康面板
            d_hp = {}
            if isinstance(d_valid, dict) and d_valid.get("total_matches"):
                grades = d_valid.get("per_grade", {})
                funnel = d_valid.get("funnel", {}) or {}
                monotonic = d_valid.get("monotonicity", {}) or {}
                cov = d_valid.get("coverage_monitor", {}) or {}
                total = d_valid.get("total_matches", 0)
                pending = d_valid.get("pending_matches", total)
                completed = total - pending
                c_data = grades.get("C", {})
                flags = []
                if str(monotonic.get("status", "UNKNOWN")) == "FAIL":
                    flags.append("分级单调性失败")
                cov_health = str(cov.get("health", "OK"))
                if cov_health == "LOW":
                    flags.append("A+B覆盖率偏低")
                elif cov_health == "HIGH":
                    flags.append("A+B覆盖率偏高")
                d_hp = {
                    "status": "GREEN" if completed > 0 and not flags else ("YELLOW" if completed > 0 else "UNKNOWN"),
                    "completed": completed, "total": total,
                    "pct": round(completed / max(total, 1) * 100, 1),
                    "abRate": round(float(funnel.get("a_plus_b_hit_rate_pct", 0.0)), 1),
                    "cRate": round(c_data.get("hit_rate_pct", 0), 1),
                    "flags": "；".join(flags) if flags else "无触发",
                }
            elif isinstance(d_review, dict):
                rhp = d_review.get("health_panel", {}) or {}
                sp = rhp.get("sample_progress", {}) or {}
                ex = rhp.get("execution_quality", {}) or {}
                d_hp = {
                    "status": rhp.get("health_status", "UNKNOWN"),
                    "completed": sp.get("sample_size", 0), "total": sp.get("min_sample", 0),
                    "pct": sp.get("progress_pct", 0),
                    "abRate": ex.get("conservative_fill_roi_pct", 0),
                    "cRate": ex.get("slippage_adjusted_roi_pct", 0),
                    "flags": "无触发",
                }
            all_rows_json[d] = {"rows": d_json_rows, "health": d_hp}
        except Exception:
            all_rows_json[d] = {"rows": [], "health": {}}
    
    all_data_json = json.dumps(all_rows_json, ensure_ascii=False)
    
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg:#f7f8fb; --panel:#ffffff; --ink:#1f2937; --muted:#6b7280;
      --line:#e5e7eb; --accent:#0f766e; --hot:#b45309; --bad:#b91c1c;
      --good:#15803d; --watch:#1d4ed8;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--ink); }}
    header {{ position:sticky; top:0; z-index:5; background:rgba(247,248,251,.96); border-bottom:1px solid var(--line); backdrop-filter:blur(8px); }}
    .wrap {{ max-width:1280px; margin:0 auto; padding:18px 20px; }}
    h1 {{ margin:0 0 8px; font-size:24px; letter-spacing:0; }}
    .summary {{ display:flex; flex-wrap:wrap; gap:10px; color:var(--muted); font-size:14px; }}
    .pill {{ border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:7px 10px; }}
    .filters {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; justify-content:center; }}
    .filters select {{ width:200px; border:1px solid var(--line); border-radius:8px; background:#fff; padding:8px 10px; font-size:14px; }}
    input, select {{ border:1px solid var(--line); border-radius:8px; background:#fff; padding:10px 11px; font-size:14px; }}
    main {{ max-width:1280px; margin:0 auto; padding:18px 20px 36px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(360px, 1fr)); gap:14px; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; box-shadow:0 1px 2px rgba(15,23,42,.04); }}
    .battle-head {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; white-space: pre-wrap; line-height:1.45; font-size:13px; background:#fbfcff; border:1px solid var(--line); border-radius:8px; padding:10px; margin-bottom:10px; }}
    .card-top {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }}
    .match {{ font-weight:700; font-size:17px; line-height:1.25; }}
    .meta {{ color:var(--muted); font-size:13px; margin-top:4px; }}
    .score {{ min-width:58px; text-align:center; border-radius:8px; padding:8px 6px; font-weight:800; color:#fff; background:var(--hot); }}
    .score small {{ display:block; font-size:11px; font-weight:600; opacity:.9; }}
    .tags {{ display:flex; flex-wrap:wrap; gap:6px; margin:12px 0; }}
    .tag {{ border-radius:7px; padding:5px 7px; font-size:12px; background:#eef2ff; color:#3730a3; }}
    .tag.watch {{ background:#dbeafe; color:var(--watch); }}
    .tag.good {{ background:#dcfce7; color:var(--good); }}
    .tag.warn {{ background:#fef3c7; color:#92400e; }}
    .metrics {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; }}
    .scores {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; margin-top:10px; }}
    .scorebox {{ border:1px solid var(--line); border-radius:8px; padding:8px; background:#fbfdff; }}
    .scorebox label {{ display:block; color:var(--muted); font-size:12px; margin-bottom:4px; }}
    .scorebox b {{ font-size:16px; }}
    .metric {{ border:1px solid var(--line); border-radius:8px; padding:9px; }}
    .metric label {{ display:block; color:var(--muted); font-size:12px; margin-bottom:4px; }}
    .metric b {{ font-size:16px; }}
    .verdict {{ margin-top:10px; padding:10px 12px; border-radius:8px; background:#f8fafc; border:1px solid var(--line); font-weight:700; color:#111827; }}
    .section {{ margin-top:12px; border-top:1px solid var(--line); padding-top:11px; }}
    .section-title {{ color:var(--muted); font-size:12px; margin-bottom:6px; }}
    .detail {{ font-size:13px; line-height:1.55; }}
    .plan-strip {{ margin-top:10px; border-radius:8px; padding:8px 10px; font-size:12px; font-weight:700; border:1px solid var(--line); }}
    .plan-green {{ background:#dcfce7; color:#166534; border-color:#86efac; }}
    .plan-yellow {{ background:#fef3c7; color:#92400e; border-color:#fcd34d; }}
    .plan-red {{ background:#fee2e2; color:#991b1b; border-color:#fca5a5; }}
    .audit {{ margin-top:12px; border-top:1px solid var(--line); padding-top:10px; }}
    .audit summary {{ cursor:pointer; color:var(--accent); font-size:13px; font-weight:700; }}
    .list-wrap {{ display:flex; flex-direction:column; gap:8px; }}
    .list-row {{ display:grid; grid-template-columns: 78px 1fr 140px 64px; gap:10px; align-items:center; background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:10px 12px; }}
    .list-time {{ color:var(--muted); font-weight:700; font-size:13px; text-align:center; }}
    .list-match {{ font-size:14px; font-weight:700; }}
    .list-league {{ color:var(--muted); font-size:12px; margin-top:2px; }}
    .list-action {{ font-size:12px; text-align:right; color:#334155; }}
    .list-state {{ margin-top:3px; font-size:11px; font-weight:700; }}
    .list-state-green {{ color:#166534; }}
    .list-state-yellow {{ color:#92400e; }}
    .list-state-red {{ color:#991b1b; }}
    .list-score {{ text-align:right; font-weight:800; color:#7c2d12; }}
    .health-panel {{ margin-top:12px; border:1px solid var(--line); border-radius:8px; padding:10px 12px; background:#fff; }}
    .health-head {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:8px; }}
    .health-dot {{ width:10px; height:10px; border-radius:999px; display:inline-block; }}
    .health-green .health-dot {{ background:#16a34a; }}
    .health-yellow .health-dot {{ background:#ca8a04; }}
    .health-red .health-dot {{ background:#dc2626; }}
    .health-grid {{ display:grid; grid-template-columns:repeat(4,minmax(120px,1fr)); gap:8px; }}
    .health-item {{ border:1px solid var(--line); border-radius:8px; padding:8px; }}
    .health-item small {{ display:block; color:var(--muted); font-size:11px; }}
    .health-item b {{ font-size:14px; }}
    .quick {{ display:grid; grid-template-columns:1.4fr repeat(3, .75fr); gap:8px; margin-top:10px; }}
    .quick .metric:first-child b {{ font-size:14px; }}
    .hidden {{ display:none; }}
    .empty {{ color:var(--muted); text-align:center; padding:40px; background:var(--panel); border:1px solid var(--line); border-radius:8px; }}
    @media (max-width: 860px) {{ .filters select {{ width:100%; }} .grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <h1>V4 HT PREMATCH RECOMMEND — 今日情报台</h1>
      <div class="summary">
        <span class="pill" style="min-width:130px">📅 <select id="datePicker" onchange="switchDate(this.value)" style="border:none;background:transparent;font-size:inherit;font-weight:700;cursor:pointer;color:var(--ink);">
          {date_options}
        </select></span>
        <span class="pill"><b id="visibleCount">0</b> / {len(rows)} 场</span>
        <span class="pill">时间口径：{html.escape(mode_text)}</span>
        <span class="pill">A级: <b id="cntHTA">0</b> · B级: <b id="cntHTB">0</b> · C级: <b id="cntHTC">0</b> · SKIP: <b id="cntHTSkip">0</b></span>
        <span class="pill">覆盖率(A+B): <b id="cntABRatio">0%</b> <span id="cntABHealth"></span></span>
      </div>
      <div class="health-panel health-yellow" id="healthPanel">
        <div class="health-head">
          <span class="health-dot"></span>
          <b id="healthStatus">策略健康：UNKNOWN</b>
          <span class="pill" id="healthFlags">Kill Flags: 无触发</span>
        </div>
        <div class="health-grid">
          <div class="health-item"><small>赛后验证进度</small><b id="healthProgress">0/0</b></div>
          <div class="health-item"><small>验证完成率</small><b id="healthPct">0%</b></div>
          <div class="health-item"><small>A+B级HT命中率</small><b id="healthAB">0%</b></div>
          <div class="health-item"><small>C级HT命中率</small><b id="healthC">0%</b></div>
        </div>
        </div>
      </div>
      <div class="filters">
        <select id="pool">
          <option value="ht_main" selected>今日上半场推荐(A/B)</option>
          <option value="ht_observe">上半场观察(C)</option>
          <option value="sh_observe">下半场观察池</option>
          <option value="info_only">其他情报</option>
          <option value="all">完整情报池(高级)</option>
        </select>
        <select id="sort">
          <option value="hotness">按评分推荐</option>
          <option value="time" selected>按比赛开始时间</option>
        </select>
        <select id="view">
          <option value="cards" selected>卡片模式</option>
          <option value="list">列表模式</option>
        </select>
      </div>
      <div class="health-panel" style="margin-top:10px">
        <div class="health-head">
          <b>跳过统计（HT_SKIP）</b>
          <span class="pill">今日跳过：<b id="skipCount">0</b> 场</span>
        </div>
        <div id="skipReasons" class="detail">-</div>
      </div>
    </div>
  </header>
  <main>
    <div id="cards" class="grid"></div>
    <div id="list" class="list-wrap hidden"></div>
    <div id="empty" class="empty hidden">没有符合过滤条件的比赛</div>
  </main>
  <script>
    const allData = {all_data_json};
    let rows = allData['{date_str}'] ? (allData['{date_str}'].rows || []) : [];
    let currentDate = '{date_str}';
    const state = {{ sort:'time', view:'cards', pool:'ht_main' }};
    const el = id => document.getElementById(id);
    function actionOf(row) {{ return row.actionCode || 'SKIP'; }}
    function tierOf(row) {{
      if (row.hotness >= 85) return 'A+';
      if (row.hotness >= 70) return 'A';
      if (row.hotness >= 55) return 'B';
      return 'C';
    }}
    function actionColor(action) {{
      if (action === 'HT_A' || action === 'HT_B') return 'good';
      if (action === 'HT_C') return 'warn';
      if (action === 'SH_OBSERVE_ONLY') return 'watch';
      if (action && action.startsWith('HT_SKIP')) return 'watch';
      return '';
    }}

    function clsFor(row) {{
      if (row.tier === 'S') return 'good';
      if (row.is_watch) return 'watch';
      return 'warn';
    }}
    function card(row) {{
      const action = actionOf(row);
      const t = tierOf(row);
      return `<article class="card">
        <div class="card-top">
          <div>
            <div class="match">${{row.home}} vs ${{row.away}}</div>
            <div class="meta">${{row.league}} · ${{row.timeLabel || row.time || '--:--'}} · #${{row.fixture_id}} · ${{row.liveMinute || '-'}}' ${{row.liveScore || '-'}}</div>
          </div>
          <div class="score">${{row.hotness}}<small>全局热度</small></div>
        </div>
        <div class="tags">
          <span class="tag ${{actionColor(action)}}">${{action}}</span>
          <span class="tag">初盘 大${{row.lineNum || row.displayLine || '?'}} @${{row.oddsNum || row.displayOdds || '-'}}</span>
          <span class="tag">HT评分 ${{row.htScore || '-'}}</span>
          <span class="tag">HT有球率 ${{row.h2hText || '-'}}</span>
          <span class="tag">样本 ${{row.htRecSampleSize || 0}}</span>
          <span class="tag">分布 ${{row.htRecScriptType || '-'}}</span>
          <span class="tag">分布源 ${{row.htRecTimeBinsSource || '-'}}</span>
          <span class="tag">规则 ${{row.htRecRuleVersion || '-'}}</span>
        </div>
        <div class="verdict">HT推荐结论：${{row.htRecGrade || '-'}}级 · ${{row.htRecReason || row.htDecisionReason || '-'}}${{(row.isShObserve && !row.isHtMain) ? ' ｜ SH观察：不计入HT主推荐' : ''}}</div>
        <div class="detail">
          📋 <b>历史基因</b>: HT有球率 ${{row.h2hText}} | 场均进球 ${{row.modelXg || row.avgGoals}} 球<br>
          ⏱ <b>进球剧本</b>: ${{row.storyLabel || '-'}} (0-15m ${{row.p0_15 || '-'}} | 16-30m ${{row.p16_30 || '-'}} | 31-45m ${{row.p31_45 || '-'}})<br>
          ⚔️ <b>开局施压</b>: ${{row.pressureText || '-'}}
        </div>
        <div class="section">
          <div class="section-title">🎯 推荐理由</div>
          <div class="detail">${{row.htRecReasons || row.whyText || '-'}}
          </div>
        </div>
        <div class="section">
          <div class="section-title">💡 执行与风险</div>
          <div class="detail">${{row.actionPlan1 || '-'}}<br>${{row.actionPlan2 || '-'}}<br>${{row.actionPlan3 || '-'}}<br>
          风险: ${{row.htRecRiskTop || row.htRecRisks || (row.avoidIfText || '-').split('；').slice(0,2).join(' / ')}}</div>
        </div>
        <div class="plan-strip ${{row.strategyStateClass || 'plan-yellow'}}">赛后验证：记录 HT是否有球 + 命中时间段（0-15/16-30/31-45）</div>
        <details class="audit"><summary>查看完整数据</summary>
          <div class="section"><div class="section-title">H2H / 近期</div>
            <div class="detail">H2H HT率 ${{row.h2hText}} (${{row.h2hCountText}}) · 场均HT球 ${{row.avgGoals}} · 近期动能 ${{row.momentumText}}</div>
          </div>
          <div class="section"><div class="section-title">上半场进球时间分布</div>
            <div class="detail">0-10: ${{row.bins['0-10']}} · 11-30: ${{row.bins['11-30']}} · 11-45: ${{row.bins['11-45']}} · 16-45: ${{row.bins['16-45']}}<br>回调适配: ${{row.pullbackFit}} · 近期时间适配: ${{row.recentTimingFit}} · 11-45压力: ${{row.lateFhPressure}} ${{row.earlyOnlyFlag ? '· 开场闪击型' : ''}}</div>
          </div>
          <div class="section"><div class="section-title">API数据覆盖</div>
            <div class="detail">${{row.dataCoverageLevel}} · ${{row.dataGateAction}} · ${{row.htGateModel || '-'}}</div>
          </div>
          <div class="section"><div class="section-title">联赛基准</div>
            <div class="detail">HT环境 ${{row.leagueHtEnv}} · HT ${{row.leagueHtRate}} · SH ${{row.leagueShRate}} · FT2+ ${{row.leagueFtRate}} · 样本 ${{row.leagueSample}} · 调整 ${{row.leagueAdjustment}}</div>
          </div>
          <div class="section"><div class="section-title">赛季阶段</div>
            <div class="detail">${{row.seasonPhase}} · 进度 ${{row.seasonProgress}} · ${{row.seasonCompleted}}/${{row.seasonTotal}} · 剩余约 ${{row.remainingRounds}} 轮 · 调整 ${{row.phaseAdjustment}}</div>
          </div>
          <div class="section"><div class="section-title">排名战意</div>
            <div class="detail">${{row.motivationGate}} · 分数 ${{row.motivationScore}} · ${{row.motivationReason}}<br>${{row.home}} #${{row.homeRank}}: ${{row.homeMotTags}} · ${{row.away}} #${{row.awayRank}}: ${{row.awayMotTags}}</div>
          </div>
          <div class="section"><div class="section-title">赛程压力</div>
            <div class="detail">${{row.scheduleLevel}} · ${{row.scheduleAction}} · ${{row.scheduleReason}}<br>${{row.home}}：${{row.homeSchedule}} · ${{row.away}}：${{row.awaySchedule}}</div>
          </div>
          <div class="section"><div class="section-title">走地状态</div>
            <div class="detail">${{row.liveAction}} · ${{row.liveReason}}<br>分钟 ${{row.liveMinute}} · 比分 ${{row.liveScore}} · 入场 大${{row.entryLine}} @${{row.entryOdds}}</div>
          </div>
          <div class="section"><div class="section-title">近期HT攻防动能</div>
            <div class="detail">${{row.home}}：进球 ${{row.homeHtScored}} / 失球 ${{row.homeHtConceded}} · ${{row.away}}：进球 ${{row.awayHtScored}} / 失球 ${{row.awayHtConceded}}<br>主攻客防 ${{row.homeAttackVsAwayDefense}} · 客攻主防 ${{row.awayAttackVsHomeDefense}} · 最强组合 ${{row.htAttackVsDefense}}</div>
          </div>
          <div class="section"><div class="section-title">下半场 / 全场参考（独立观察）</div>
            <div class="detail">SH有球: ${{row.shText}} · 场均SH球: ${{row.avgShGoals}} · FT 2+球: ${{row.ftOverText}}<br>46-60: ${{row.binsSecond['46-60']}} · 61-75: ${{row.binsSecond['61-75']}} · 76-90: ${{row.binsSecond['76-90']}}</div>
          </div>
          <div class="section"><div class="section-title">赛前大球盘口全量</div><div class="detail">${{row.linesText}}</div></div>
          <div class="section"><div class="section-title">伤停 / 首发闸门</div><div class="detail">${{row.injuryText}}<br>${{row.lineupText}}</div></div>
        </details>
      </article>`;
    }}
    function filtered() {{
      let out = rows.slice();
      if (state.pool === 'ht_main') {{
        out = out.filter(r => !!r.isHtRecommendation);
      }} else if (state.pool === 'ht_observe') {{
        out = out.filter(r => !!r.isHtObserve);
      }} else if (state.pool === 'sh_observe') {{
        out = out.filter(r => !!r.isShObserve);
      }} else if (state.pool === 'info_only') {{
        out = out.filter(r => !r.isHtMain && !r.isShObserve);
      }}
      out.sort((a,b) => {{
        if (state.sort === 'time') {{
          const ka = Number(a.kickoffSort || 32503680000);
          const kb = Number(b.kickoffSort || 32503680000);
          if (ka !== kb) return ka - kb;
          return Number(a.fixture_id || 0) - Number(b.fixture_id || 0);
        }}
        return Number(b.hotness) - Number(a.hotness);
      }});
      return out;
    }}
    function listRow(row) {{
      const action = actionOf(row);
      return `<div class="list-row">
        <div class="list-time">${{row.timeLabel || row.time || '--:--'}}</div>
        <div>
          <div class="list-match">${{row.home}} vs ${{row.away}}</div>
          <div class="list-league">${{row.league}} · #${{row.fixture_id}}</div>
        </div>
        <div class="list-action">HT ${{row.htRecGrade || '-'}}级<br>HT率 ${{row.h2hText || '-'}} · 11-45 ${{row.bins['11-45'] || '-'}}<br><div class="list-state ${{row.strategyStateListClass || 'list-state-yellow'}}">${{row.htRecReason || row.strategyState || '观察'}}</div></div>
        <div class="list-score">${{row.hotness}}</div>
      </div>`;
    }}
    function switchDate(date) {{
      if (date === currentDate) return;
      const entry = allData[date];
      if (!entry) return;
      rows = entry.rows || [];
      currentDate = date;
      updateHealth(date);
      render();
    }}
    function updateHealth(date) {{
      const h = (allData[date] && allData[date].health) || {{}};
      const status = h.status || 'UNKNOWN';
      const panel = document.getElementById('healthPanel');
      panel.className = 'health-panel ' + (status === 'GREEN' ? 'health-green' : status === 'RED' ? 'health-red' : 'health-yellow');
      document.getElementById('healthStatus').textContent = '策略健康：' + status;
      document.getElementById('healthFlags').textContent = 'Flags: ' + (h.flags || '无触发');
      document.getElementById('healthProgress').textContent = (h.completed || 0) + '/' + (h.total || 0);
      document.getElementById('healthPct').textContent = (h.pct || 0) + '%';
      document.getElementById('healthAB').textContent = (h.abRate || 0) + '%';
      document.getElementById('healthC').textContent = (h.cRate || 0) + '%';
    }}
    function render() {{
      const htA = rows.filter(r => (r.htRecGrade || '') === 'A').length;
      const htB = rows.filter(r => (r.htRecGrade || '') === 'B').length;
      const htC = rows.filter(r => !!r.isHtObserve).length;
      const htSkip = rows.filter(r => !!r.isHtSkip).length;
      const skipRows = rows.filter(r => !!r.isHtSkip);
      const skipReasonMap = new Map();
      for (const r of skipRows) {{
        const reason = (r.htRecReason || r.htDecisionReason || '未注明原因').trim();
        skipReasonMap.set(reason, (skipReasonMap.get(reason) || 0) + 1);
      }}
      const skipReasonTop = Array.from(skipReasonMap.entries())
        .sort((a,b) => b[1]-a[1])
        .slice(0, 6)
        .map(([k,v]) => `${{k}}: ${{v}}场`);
      const total = rows.length || 1;
      const abRatio = ((htA + htB) / total) * 100;
      el('cntHTA').textContent = String(htA);
      el('cntHTB').textContent = String(htB);
      el('cntHTC').textContent = String(htC);
      el('cntHTSkip').textContent = String(htSkip);
      el('skipCount').textContent = String(htSkip);
      el('skipReasons').textContent = skipReasonTop.length ? skipReasonTop.join(' | ') : '暂无';
      el('cntABRatio').textContent = abRatio.toFixed(1) + '%';
      let abHealth = 'OK';
      if (abRatio < 5) abHealth = '偏低';
      else if (abRatio > 15) abHealth = '偏高';
      el('cntABHealth').textContent = '[' + abHealth + ']';
      const out = filtered();
      el('visibleCount').textContent = out.length;
      if (out.length === 0) {{
        if (state.pool === 'ht_main') {{
          el('empty').textContent = '今日暂无 HT_A/HT_B 推荐';
        }} else {{
          el('empty').textContent = '没有符合过滤条件的比赛';
        }}
      }}
      el('empty').classList.toggle('hidden', out.length > 0);
      el('cards').classList.toggle('hidden', state.view !== 'cards');
      el('list').classList.toggle('hidden', state.view !== 'list');
      el('cards').innerHTML = out.map(card).join('');
      el('list').innerHTML = out.map(listRow).join('');
    }}
    ['pool','sort','view'].forEach(id => {{
      el(id).addEventListener('input', e => {{ state[id] = e.target.value; render(); }});
    }});
    updateHealth(currentDate);
    render();
  </script>
</body>
</html>
"""
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "_ops" if window_mode == "ops" else ""
    out_path = DASHBOARD_DIR / f"v4_dashboard_{key}{suffix}.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    latest_path = DASHBOARD_DIR / "v4_dashboard_latest.html"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--window-mode", choices=["natural", "ops"], default="natural", help="日期窗口：natural=自然日(默认)，ops=运营日(12:00-次日11:59)")
    parser.add_argument("--open", action="store_true", help="生成后用系统浏览器打开")
    args = parser.parse_args()
    out_path = render_dashboard(args.date, args.window_mode)
    print(f"V4 dashboard saved: {out_path}")
    # 自动拷贝到 canvas 嵌入目录（权限不足时忽略）
    try:
        canvas_path = BASE_DIR.parent.parent / "canvas" / "documents" / "v4_dashboard" / "index.html"
        canvas_path.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(out_path, canvas_path)
        print(f"Canvas: {canvas_path}")
    except Exception:
        pass
    if args.open:
        subprocess.run(["open", str(out_path)], check=False)


if __name__ == "__main__":
    main()
