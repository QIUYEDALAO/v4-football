"""
V4 下半场大球评估器
==================
半场结束后读取 scout_v4_YYYYMMDD.json，对 SECOND_HALF_OVER 候选做一次
半场实况评估：半场比分、上半场统计、红牌、下半场实时盘口。

当前只做纸盘观察，不触发实盘。

用法:
  python3 engine/second_half_evaluator.py --date 20260512 --once
  python3 engine/second_half_evaluator.py --date 20260512 --watch --interval 300
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from logger import logger
except ModuleNotFoundError:
    from engine.logger import logger

from engine import net_utils
from engine.v4_match_intelligence import explain_match
from engine.execution_cost_model import estimate_execution_cost

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"
PAPER_DIR = BASE_DIR / "data" / "paper_trading"
SH_GUARD_PATH = BASE_DIR / "config" / "sh_noisy_guard.yaml"

READY_STATUSES = {"HT", "2H"}
FINAL_STATUSES = {"FT", "AET", "PEN", "WO"}
TARGET_LINES = (1.0, 0.75)
ODDS_RANGES = {
    1.0: (1.65, 2.10),
    0.75: (1.55, 1.95),
}


def _load_guard() -> dict:
    if not SH_GUARD_PATH.exists():
        return {}
    with open(SH_GUARD_PATH, encoding="utf-8") as f:
        return json.load(f)


SH_GUARD = _load_guard()
SH_CFG = (SH_GUARD or {}).get("SH_strategy") or {}


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _as_float(value, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_response(resp: Optional[dict]) -> list:
    if not resp or not isinstance(resp, dict):
        return []
    data = resp.get("response")
    return data if isinstance(data, list) else []


def _num(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, str):
        value = value.replace("%", "").strip()
    try:
        return float(value)
    except Exception:
        return 0.0


def api_get(endpoint: str) -> Optional[dict]:
    return net_utils.api_get(endpoint)


def fetch_fixture_state(fixture_id: int, api_client: Callable[[str], Optional[dict]] = api_get) -> dict:
    resp = api_client(f"fixtures?id={fixture_id}")
    rows = _safe_response(resp)
    if not rows:
        return {"fixture_id": fixture_id, "state": "API_EMPTY", "minute": None, "score": None, "ht_score": None}

    item = rows[0]
    status = item.get("fixture", {}).get("status", {}) or {}
    goals = item.get("goals", {}) or {}
    score = item.get("score", {}) or {}
    ht = score.get("halftime", {}) or {}
    home_goals = int(goals.get("home") or 0)
    away_goals = int(goals.get("away") or 0)
    ht_home = ht.get("home")
    ht_away = ht.get("away")
    ht_score = f"{int(ht_home or 0)}-{int(ht_away or 0)}" if ht_home is not None and ht_away is not None else None
    return {
        "fixture_id": fixture_id,
        "state": status.get("short"),
        "minute": status.get("elapsed"),
        "score": f"{home_goals}-{away_goals}",
        "goals_home": home_goals,
        "goals_away": away_goals,
        "ht_score": ht_score,
        "ht_goals_home": int(ht_home or 0) if ht_home is not None else None,
        "ht_goals_away": int(ht_away or 0) if ht_away is not None else None,
        "raw_status": status,
    }


def stat_totals(stats_resp: dict) -> dict:
    totals = {
        "shots_on_goal": 0.0,
        "total_shots": 0.0,
        "corners": 0.0,
        "attacks": 0.0,
        "dangerous_attacks": 0.0,
    }
    by_team = []
    for team_stats in _safe_response(stats_resp):
        row = {"team": (team_stats.get("team") or {}).get("name")}
        for item in team_stats.get("statistics", []) or []:
            name = str(item.get("type") or "").lower()
            value = _num(item.get("value"))
            if "shots on goal" in name or "shots on target" in name:
                key = "shots_on_goal"
            elif "total shots" in name:
                key = "total_shots"
            elif "corner" in name:
                key = "corners"
            elif name == "attacks":
                key = "attacks"
            elif "dangerous attacks" in name:
                key = "dangerous_attacks"
            else:
                continue
            totals[key] += value
            row[key] = value
        by_team.append(row)
    return {"totals": totals, "by_team": by_team, "has_stats": any(v > 0 for v in totals.values())}


def event_summary(events_resp: dict) -> dict:
    goals = []
    red_cards = 0
    injuries = 0
    for event in _safe_response(events_resp):
        elapsed = int(event.get("time", {}).get("elapsed") or 0)
        if elapsed > 45:
            continue
        event_type = str(event.get("type") or "")
        detail = str(event.get("detail") or "")
        if event_type.lower() == "goal":
            goals.append({
                "minute": elapsed,
                "team": (event.get("team") or {}).get("name"),
                "detail": detail,
            })
        if "card" in event_type.lower() and "red" in detail.lower():
            red_cards += 1
        if event_type.lower() == "subst" and "injur" in detail.lower():
            injuries += 1
    return {
        "first_half_goals": goals,
        "first_half_goal_minutes": [x["minute"] for x in goals],
        "red_cards": red_cards,
        "injury_subs": injuries,
    }


def _walk_live_books(resp: dict) -> list[dict]:
    books = []
    for entry in (resp or {}).get("response", []) or []:
        if "bookmakers" in entry:
            books.extend(entry.get("bookmakers", []) or [])
        elif "odds" in entry:
            books.append({"name": entry.get("bookmaker", "LIVE"), "bets": entry.get("odds", [])})
        elif "bets" in entry:
            books.append({"name": entry.get("bookmaker", "LIVE"), "bets": entry.get("bets", [])})
    return books


def _extract_line(text: str) -> Optional[float]:
    nums = re.findall(r"\d+(?:\.\d+)?", text or "")
    if not nums:
        return None
    return _as_float(nums[-1])


def extract_live_sh_ou_lines(live_odds_resp: dict) -> list[dict]:
    """从 /odds/live 响应提取下半场大球线，只保留 Over。"""
    lines = []
    for bm in _walk_live_books(live_odds_resp):
        bookmaker = bm.get("name", "LIVE")
        for bet in bm.get("bets", []) or []:
            bet_name = str(bet.get("name") or bet.get("label") or bet.get("market") or "")
            values = bet.get("values", []) or bet.get("odds", []) or []
            market_text = f"{bet_name} {json.dumps(values, ensure_ascii=False)}".lower()
            if "over" not in market_text and "大" not in market_text:
                continue
            if not any(token in market_text for token in ("second half", "2nd half", "2h", "下半")):
                continue
            if any(token in market_text for token in ("first half", "1st half", "1h", "上半")):
                continue

            for val in values:
                label = str(val.get("value") or val.get("label") or val.get("name") or "")
                lower = label.lower()
                if "over" not in lower and "大" not in label:
                    continue
                odd = _as_float(val.get("odd") or val.get("odds") or val.get("price"))
                line = _extract_line(label) or _extract_line(bet_name)
                if odd is None or line is None:
                    continue
                lines.append({
                    "bookmaker": bookmaker,
                    "line": round(float(line), 2),
                    "over_odds": odd,
                    "market_name": bet_name,
                    "label": label,
                })
    lines.sort(key=lambda x: (0 if "pinnacle" in x["bookmaker"].lower() else 1, x["line"]))
    return lines


def fetch_live_sh_ou_lines(fixture_id: int, api_client: Callable[[str], Optional[dict]] = api_get) -> tuple[list[dict], dict]:
    resp = api_client(f"odds/live?fixture={fixture_id}")
    return extract_live_sh_ou_lines(resp or {}), (resp or {})


def choose_sh_entry_line(lines: list[dict]) -> Optional[dict]:
    for target in TARGET_LINES:
        lo, hi = ODDS_RANGES[target]
        candidates = [
            ln for ln in lines
            if abs(float(ln.get("line", 0)) - target) < 0.001
            and lo <= float(ln.get("over_odds", 0)) <= hi
        ]
        if candidates:
            return sorted(candidates, key=lambda x: x["over_odds"], reverse=True)[0]
    return None


def _estimate_sh_model_prob(pressure_score: float, context_signal: str) -> float:
    # Lightweight proxy until SH model calibration is available.
    base = 0.45 + min(max(pressure_score, 0.0), 100.0) / 200.0
    if context_signal in ("HT_0_0", "HT_ONE_GOAL"):
        base += 0.03
    return max(0.05, min(0.9, base))


def evaluate_first_half_pressure(stats: dict, events: dict) -> dict:
    totals = stats.get("totals", {})
    if events.get("red_cards", 0) > 0:
        return {"signal": "RED_CARD", "action": "SKIP", "score": 0, "reason": "上半场出现红牌"}
    if not stats.get("has_stats"):
        return {"signal": "STATS_UNKNOWN", "action": "WATCH", "score": 0, "reason": "缺少上半场技术统计"}

    score = 0.0
    score += min(totals.get("total_shots", 0) / 8.0, 1.0) * 30
    score += min(totals.get("shots_on_goal", 0) / 3.0, 1.0) * 25
    score += min(totals.get("corners", 0) / 4.0, 1.0) * 20
    score += min(totals.get("dangerous_attacks", 0) / 35.0, 1.0) * 25
    score = round(score, 1)

    if score >= 65:
        return {"signal": "PRESSURE_STRONG", "action": "ALLOW", "score": score, "reason": "上半场压迫强"}
    if score >= 45:
        return {"signal": "PRESSURE_OK", "action": "WATCH", "score": score, "reason": "上半场有一定压迫"}
    return {"signal": "PRESSURE_DULL", "action": "SKIP", "score": score, "reason": "上半场场面偏沉闷"}


def score_context(state: dict, item: dict) -> dict:
    ht_home = state.get("ht_goals_home")
    ht_away = state.get("ht_goals_away")
    if ht_home is None or ht_away is None:
        return {"signal": "NO_HT_SCORE", "action": "WAIT", "reason": "缺少半场比分"}

    ht_total = int(ht_home) + int(ht_away)
    goal_diff = abs(int(ht_home) - int(ht_away))
    motivation = item.get("motivation", {}) or {}
    motivation_gate = (motivation.get("gate") or {}).get("action")

    if ht_total == 0:
        return {"signal": "HT_0_0", "action": "ALLOW", "reason": "0-0 半场，若场面不沉闷可看下半场"}
    if ht_total == 1:
        return {"signal": "HT_ONE_GOAL", "action": "ALLOW", "reason": "半场一球，落后方追分空间仍在"}
    if ht_total == 2 and goal_diff == 0:
        return {"signal": "HT_1_1", "action": "WATCH", "reason": "1-1 开放，但下半场盘口可能偏贵"}
    if ht_total == 2 and goal_diff == 2:
        action = "WATCH" if motivation_gate in ("BOOST", "ALLOW_V4_LIVE") else "SKIP"
        return {"signal": "HT_2_0", "action": action, "reason": "两球差，需落后方强战意支撑"}
    if ht_total >= 3:
        return {"signal": "HT_HIGH_SCORE", "action": "WATCH", "reason": "半场已多球，谨慎看价格"}
    return {"signal": "HT_CONTEXT_UNKNOWN", "action": "WATCH", "reason": "半场比分结构需人工复核"}


def evaluate_sh_item(item: dict, date_key: str, api_client: Callable[[str], Optional[dict]] = api_get) -> dict:
    fixture_id = int(item["fixture_id"])
    intelligence = explain_match({**item, "market_focus": "SECOND_HALF_OVER"})
    base = {
        "fixture_id": fixture_id,
        "home": item.get("home"),
        "away": item.get("away"),
        "league": item.get("league"),
        "strategy_id": "V4_SH_LIVE_OVER",
        "checked_at": datetime.now().isoformat(),
        "market_focus": item.get("market_focus"),
        "intelligence": intelligence,
        "match_type": intelligence.get("match_type", []),
        "primary_direction": intelligence.get("primary_direction"),
        "confidence": intelligence.get("confidence"),
    }

    if item.get("market_focus") != "SECOND_HALF_OVER":
        return {**base, "action": "SH_SKIP_NOT_SH_FOCUS", "reason": "非下半场方向"}

    coverage_action = ((item.get("data_coverage") or {}).get("data_gate_action") or "")
    if coverage_action == "SKIP_DATA_WEAK":
        return {**base, "action": "SH_SKIP_DATA_WEAK", "reason": "API数据覆盖过弱"}

    state = fetch_fixture_state(fixture_id, api_client)
    status = state.get("state")
    if status in ("NS", "TBD", "1H"):
        return {**base, "action": "SH_WAIT_HALFTIME", "reason": f"尚未到半场: {status}", "state": state}
    if status in FINAL_STATUSES:
        return {**base, "action": "SH_SKIP_FINISHED", "reason": f"比赛已结束: {status}", "state": state}
    if status not in READY_STATUSES:
        return {**base, "action": "SH_WAIT_STATUS", "reason": f"状态暂不适合评估: {status}", "state": state}
    if not state.get("ht_score"):
        return {**base, "action": "SH_WAIT_HT_SCORE", "reason": "半场比分未回填", "state": state}

    stats = stat_totals(api_client(f"fixtures/statistics?fixture={fixture_id}") or {})
    events = event_summary(api_client(f"fixtures/events?fixture={fixture_id}") or {})
    pressure = evaluate_first_half_pressure(stats, events)
    context = score_context(state, item)

    if pressure.get("action") == "SKIP":
        return {**base, "action": "SH_SKIP_TEMPO", "reason": pressure.get("reason"), "state": state, "stats": stats, "events": events, "pressure": pressure, "score_context": context}
    if context.get("action") == "SKIP":
        return {**base, "action": "SH_SKIP_CONTEXT", "reason": context.get("reason"), "state": state, "stats": stats, "events": events, "pressure": pressure, "score_context": context}

    lines, raw_resp = fetch_live_sh_ou_lines(fixture_id, api_client)
    entry = choose_sh_entry_line(lines)
    if not entry:
        action = "SH_WATCH_PRICE"
        reason = "下半场盘口未到大1.0/大0.75合理水位"
        if not lines:
            reason = "未获取到下半场实时大球盘口"
        return {
            **base,
            "action": action,
            "reason": reason,
            "state": state,
            "stats": stats,
            "events": events,
            "pressure": pressure,
            "score_context": context,
            "live_lines": lines,
            "raw_live_odds": raw_resp,
        }

    pressure_score = float(pressure.get("score") or 0.0)
    model_prob = _estimate_sh_model_prob(pressure_score, str(context.get("signal") or ""))
    market_prob = 1.0 / float(entry["over_odds"]) if float(entry["over_odds"]) > 1.0 else 0.0
    edge = model_prob - market_prob
    ex = estimate_execution_cost(
        displayed_odds=float(entry["over_odds"]),
        ev_gross=edge,
        odds_alive_seconds=3.0,
        latency_seconds=1.5,
        market_freeze=False,
    )
    min_model_prob = float(((SH_CFG.get("thresholds") or {}).get("min_model_prob", 0.5)))
    min_ev_net = float(((SH_CFG.get("thresholds") or {}).get("min_ev_net", 0.0)))
    min_conservative_ev = float(((SH_CFG.get("thresholds") or {}).get("min_conservative_ev", 0.0)))

    noisy_reasons = []
    if bool(SH_CFG.get("forbid_signal_from_base_rate_only", True)) and pressure.get("action") != "ALLOW":
        noisy_reasons.append("pressure_not_allow")
    if model_prob < min_model_prob:
        noisy_reasons.append("model_prob_low")
    if ex.ev_net <= min_ev_net:
        noisy_reasons.append("ev_net_non_positive")
    if ex.conservative_ev <= min_conservative_ev:
        noisy_reasons.append("conservative_ev_non_positive")

    if noisy_reasons:
        action = "SH_NOISY"
        reason = "SH高命中不代表EV，当前为NOISY观察"
    elif ex.ev_net > 0 and ex.conservative_ev > 0 and pressure.get("action") == "ALLOW" and context.get("action") == "ALLOW":
        action = "SH_PAPER_ONLY"
        reason = "SH仅纸盘：市场概率与模型概率存在正向EV"
    elif ex.ev_net > 0:
        action = "SH_EV_CANDIDATE"
        reason = "SH存在正向EV候选，待更多约束通过"
    else:
        action = "SH_BLOCKED"
        reason = "SH风险或执行质量不达标"

    return {
        **base,
        "action": action,
        "reason": reason,
        "state": state,
        "stats": stats,
        "events": events,
        "pressure": pressure,
        "score_context": context,
        "entry_line": entry["line"],
        "entry_over_odds": entry["over_odds"],
        "entry_bookmaker": entry.get("bookmaker"),
        "model_prob": round(model_prob, 4),
        "market_prob": round(market_prob, 4),
        "edge": round(edge, 6),
        "ev_net": round(ex.ev_net, 6),
        "conservative_ev": round(ex.conservative_ev, 6),
        "execution_model": ex.to_dict(),
        "sh_noisy_reasons": noisy_reasons,
        "live_lines": lines,
        "raw_live_odds": raw_resp,
    }


def _merge_entries(path: Path, new_rows: list[dict]) -> list[dict]:
    existing = _load_json(path, [])
    seen = {str(x.get("fixture_id")) for x in existing if x.get("action") == "SH_BUY_NOW"}
    merged = list(existing)
    for row in new_rows:
        fid = str(row.get("fixture_id"))
        if row.get("action") == "SH_PAPER_ONLY" and fid not in seen:
            merged.append(row)
            seen.add(fid)
    return merged


def _item_from_fixture(fixture_id: int, api_client: Callable[[str], Optional[dict]] = api_get) -> dict:
    resp = api_client(f"fixtures?id={fixture_id}")
    rows = _safe_response(resp)
    if not rows:
        return {
            "fixture_id": fixture_id,
            "home": None,
            "away": None,
            "league": None,
            "market_focus": "SECOND_HALF_OVER",
            "data_coverage": {"data_gate_action": "WATCH_ONLY"},
        }
    row = rows[0]
    return {
        "fixture_id": fixture_id,
        "home": ((row.get("teams") or {}).get("home") or {}).get("name"),
        "away": ((row.get("teams") or {}).get("away") or {}).get("name"),
        "league": ((row.get("league") or {}).get("name")),
        "market_focus": "SECOND_HALF_OVER",
        "data_coverage": {"data_gate_action": "WATCH_ONLY"},
    }


def evaluate_single_fixture(
    date_str: str,
    fixture_id: int,
    api_client: Callable[[str], Optional[dict]] = api_get,
) -> dict:
    key = _date_key(date_str)
    scout = _load_json(REPORT_DIR / f"scout_v4_{key}.json", [])
    item = None
    for row in scout if isinstance(scout, list) else []:
        if str(row.get("fixture_id")) == str(fixture_id):
            item = row
            break
    if not item:
        item = _item_from_fixture(int(fixture_id), api_client)
    # 单场临场分析强制按下半场评估，不受旧 scout 方向字段影响。
    item = {**item, "market_focus": "SECOND_HALF_OVER"}
    result = evaluate_sh_item(item, key, api_client)
    status_path = MONITOR_DIR / f"v4_second_half_single_{key}_{fixture_id}.json"
    _save_json(status_path, result)
    if result.get("action") == "SH_PAPER_ONLY":
        entry_path = PAPER_DIR / f"v4_second_half_entries_{key}.json"
        _save_json(entry_path, _merge_entries(entry_path, [result]))
    return {"date": key, "fixture_id": fixture_id, "status_path": str(status_path), "result": result}


def run_once(date_str: str, api_client: Callable[[str], Optional[dict]] = api_get) -> dict:
    key = _date_key(date_str)
    scout_path = REPORT_DIR / f"scout_v4_{key}.json"
    scout = _load_json(scout_path, [])
    if not scout:
        return {"error": f"无 V4 情报文件或文件为空: {scout_path}"}

    candidates = [x for x in scout if isinstance(x, dict) and x.get("market_focus") == "SECOND_HALF_OVER"]
    statuses = []
    entries = []
    for item in candidates:
        result = evaluate_sh_item(item, key, api_client)
        statuses.append(result)
        if result.get("action") == "SH_PAPER_ONLY":
            entries.append(result)
        logger.info(f"[V4_SH] {result.get('fixture_id')} {result.get('action')} | {result.get('reason')}")
        time.sleep(0.3)

    status_path = MONITOR_DIR / f"v4_second_half_status_{key}.json"
    _save_json(status_path, {
        "date": key,
        "updated_at": datetime.now().isoformat(),
        "candidate_count": len(candidates),
        "statuses": statuses,
    })

    entry_path = PAPER_DIR / f"v4_second_half_entries_{key}.json"
    if entries:
        _save_json(entry_path, _merge_entries(entry_path, entries))
        # 同步写 jsonl，便于后续统计与流式处理
        jsonl_path = PAPER_DIR / f"sh_live_over_{key}.jsonl"
        with open(jsonl_path, "a", encoding="utf-8") as f:
            for row in entries:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "date": key,
        "candidate_count": len(candidates),
        "buy_count": len(entries),
        "status_path": str(status_path),
        "entry_path": str(entry_path) if entries else None,
        "action_counts": {a: sum(1 for x in statuses if x.get("action") == a) for a in sorted({x.get("action") for x in statuses})},
        "statuses": statuses,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--fixture-id", type=int, default=None, help="只评估一场比赛，可不依赖 scout 文件")
    parser.add_argument("--once", action="store_true", help="只检查一次")
    parser.add_argument("--watch", action="store_true", help="循环监控")
    parser.add_argument("--interval", type=int, default=300, help="循环间隔秒")
    args = parser.parse_args()

    if args.fixture_id and args.watch:
        while True:
            result = evaluate_single_fixture(args.date, args.fixture_id)
            compact = {k: v for k, v in result.items() if k != "result"}
            compact["action"] = (result.get("result") or {}).get("action")
            compact["reason"] = (result.get("result") or {}).get("reason")
            print(json.dumps(compact, ensure_ascii=False, indent=2))
            time.sleep(args.interval)
    elif args.fixture_id:
        result = evaluate_single_fixture(args.date, args.fixture_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.watch:
        while True:
            result = run_once(args.date)
            print(json.dumps({k: v for k, v in result.items() if k != "statuses"}, ensure_ascii=False, indent=2))
            time.sleep(args.interval)
    else:
        result = run_once(args.date)
        print(json.dumps({k: v for k, v in result.items() if k != "statuses"}, ensure_ascii=False, indent=2))

    # ── 自动刷新仪表盘 ──
    try:
        from engine.v4_dashboard import render_dashboard
        render_dashboard(args.date)
    except Exception:
        pass


if __name__ == "__main__":
    main()
