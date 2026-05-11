"""
V4 走地半场大球监控器
=====================
读取 live_watchlist_YYYYMMDD.json，监控开赛 0-15 分钟：

  - 0-10 分钟已有进球: SKIP_EARLY_GOAL
  - 8-15 分钟仍 0-0: 检查 /odds/live
  - 盘口降到大 1.0 / 大 0.75 且水位合理: 记录纸盘 BUY_NOW

当前版本只做纸盘记录，不触发实盘。

用法:
  python3 engine/live_ht_over_monitor.py --date 20260511 --once
  python3 engine/live_ht_over_monitor.py --date 20260511 --watch --interval 30
"""

from __future__ import annotations

import argparse
import json
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
from engine.data_sources.live_tempo import evaluate_live_tempo
from engine.live_odds_snapshot import (
    extract_live_ht_ou_lines,
    fetch_live_ht_ou_lines,
    save_live_snapshot as save_snapshot_record,
)
from engine.v4_match_intelligence import explain_match
from engine.v4_data_logger import append_jsonl, decision_log_path
from engine.v4_data_logger import execution_sim_path, shadow_backtest_path
from engine.asian_ev import over_asian_ev
from engine.execution_cost_model import estimate_execution_cost
from engine.ht_goal_hazard_model import estimate_ht_goal_probs
from engine.league_hierarchical_threshold import league_threshold
from engine.risk_guard import evaluate_risk_guard
from engine.line_decay_model import estimate_best_entry_window

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"
PAPER_DIR = BASE_DIR / "data" / "paper_trading"
SNAP_DIR = BASE_DIR / "data" / "live_odds_snapshots"

TARGET_LINES = (1.0, 0.75)
ODDS_RANGES = {
    1.0: (1.65, 2.05),
    0.75: (1.60, 1.90),
}
ENTRY_MINUTE_FROM = 8
ENTRY_MINUTE_TO = 15
MIN_EV_NET = 0.0
MIN_CONSERVATIVE_EV = 0.0


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _as_float(value, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def api_get(endpoint: str) -> Optional[dict]:
    return net_utils.api_get(endpoint)


def fetch_fixture_state(fixture_id: int, api_client: Callable[[str], Optional[dict]] = api_get) -> dict:
    """拉取实时比分/分钟。"""
    resp = api_client(f"fixtures?id={fixture_id}")
    data = (resp or {}).get("response") or []
    if not data:
        return {"fixture_id": fixture_id, "state": "API_EMPTY", "minute": None, "score": None}

    item = data[0]
    fixture = item.get("fixture", {})
    status = fixture.get("status", {})
    goals = item.get("goals", {}) or {}
    score = item.get("score", {}) or {}
    ht = score.get("halftime", {}) or {}

    home_goals = goals.get("home")
    away_goals = goals.get("away")
    if home_goals is None:
        home_goals = 0
    if away_goals is None:
        away_goals = 0

    return {
        "fixture_id": fixture_id,
        "state": status.get("short"),
        "elapsed": status.get("elapsed"),
        "minute": status.get("elapsed"),
        "score": f"{home_goals}-{away_goals}",
        "goals_home": int(home_goals or 0),
        "goals_away": int(away_goals or 0),
        "ht_score": (
            f"{ht.get('home')}-{ht.get('away')}"
            if ht.get("home") is not None and ht.get("away") is not None
            else None
        ),
        "raw_status": status,
    }


def choose_entry_line(
    lines: list[dict],
    *,
    minute: int,
    item: dict,
    tempo: dict,
    red_card: bool,
) -> Optional[dict]:
    """EV进场引擎：候选线 -> 条件概率 -> EV -> 执行成本 -> 最终入场。"""
    best = None
    league_baseline = ((item.get("league_baseline") or {}).get("ht_goal_rate")) or 0.6
    factors = item.get("factors") or {}
    recent_attack = max(
        _as_float(factors.get("home_attack_vs_away_defense"), 0.5),
        _as_float(factors.get("away_attack_vs_home_defense"), 0.5),
    )
    h2h_rate = _as_float(factors.get("h2h_ht_goal_rate"), 0.6)
    tempo_score = _as_float(tempo.get("tempo_score"), 0.5)

    for ln in lines:
        line = _as_float(ln.get("line"))
        odds = _as_float(ln.get("over_odds"))
        if line is None or odds is None:
            continue
        if line not in (0.75, 1.0, 1.25, 1.5):
            continue
        if line in ODDS_RANGES:
            lo, hi = ODDS_RANGES[line]
            if not (lo <= odds <= hi):
                continue
        hz = estimate_ht_goal_probs(
            minute=minute,
            league_ht_baseline=league_baseline,
            recent_attack_defense=recent_attack,
            h2h_rate=h2h_rate,
            line=line,
            over_odds=odds,
            no_red_card=not red_card,
            live_tempo_score=tempo_score,
        )
        ev = over_asian_ev(line=line, odds=odds, p0=hz.p0_goal, p1=hz.p1_goal, p2plus=hz.p2plus_goal)
        ex = estimate_execution_cost(
            displayed_odds=odds,
            ev_gross=ev.ev,
            odds_alive_seconds=3.0,
            latency_seconds=1.5,
            market_freeze=False,
        )
        if ex.ev_net <= MIN_EV_NET or ex.conservative_ev <= MIN_CONSERVATIVE_EV:
            continue
        candidate = {
            **ln,
            "line": line,
            "over_odds": odds,
            "prob_model": hz.to_dict(),
            "ev_gross": ev.ev,
            "ev_net": ex.ev_net,
            "conservative_ev": ex.conservative_ev,
            "execution_model": ex.to_dict(),
        }
        if best is None or candidate["conservative_ev"] > best["conservative_ev"]:
            best = candidate
    return best


def save_live_snapshot(date_key: str, fixture_id: int, state: dict, lines: list[dict], raw_resp: dict):
    """保存 live odds 快照。任务6后由正式快照库负责索引和去重。"""
    return save_snapshot_record(date_key, fixture_id, state, lines, raw_resp)


def evaluate_watch_item(item: dict, date_key: str, api_client: Callable[[str], Optional[dict]] = api_get) -> dict:
    fixture_id = int(item["fixture_id"])
    intelligence = explain_match(item)
    base = {
        "fixture_id": fixture_id,
        "home": item.get("home"),
        "away": item.get("away"),
        "league": item.get("league"),
        "strategy_id": "V4_HT_LIVE_PULLBACK",
        "checked_at": datetime.now().isoformat(),
        "pre_ht_line": item.get("pre_ht_line"),
        "lineup_action": item.get("lineup_action"),
        "intelligence": intelligence,
        "match_type": intelligence.get("match_type", []),
        "primary_direction": intelligence.get("primary_direction"),
        "confidence": intelligence.get("confidence"),
    }

    if item.get("market_focus") != "HT_LIVE_OVER":
        return {**base, "action": "SKIP_NOT_HT_FOCUS", "reason": "非上半场走地方向"}

    lg = item.get("league_baseline") or {}
    lt = league_threshold(
        league_id=str(item.get("league_id") or ""),
        league_name=str(item.get("league") or ""),
        sample_size=int(lg.get("sample_size") or 0),
        league_ht_baseline=float(lg.get("ht_goal_rate") or 0.0),
        model_edge=0.0,
    )
    base["league_threshold"] = lt.to_dict()
    if lt.status in ("WATCH_ONLY", "DISABLED"):
        return {**base, "action": "SKIP_LEAGUE_STATUS", "reason": f"联赛状态{lt.status}，仅观察"}

    if str(item.get("lineup_action", "")).startswith("DROP"):
        return {**base, "action": "SKIP_LINEUP_DROP", "reason": f"首发闸门: {item.get('lineup_action')}"}

    state = fetch_fixture_state(fixture_id, api_client)
    minute = state.get("minute")
    total_goals = int(state.get("goals_home", 0)) + int(state.get("goals_away", 0))
    status = state.get("state")

    if status in ("NS", "TBD"):
        return {**base, "action": "WAIT_KICKOFF", "reason": "比赛未开始", "state": state}

    if status not in ("1H", "HT"):
        return {**base, "action": "SKIP_NOT_LIVE_1H", "reason": f"非上半场实时状态: {status}", "state": state}

    if total_goals > 0:
        return {**base, "action": "SKIP_EARLY_GOAL", "reason": f"等待期已有进球 {state.get('score')}", "state": state}

    if minute is None:
        return {**base, "action": "WAIT_NO_MINUTE", "reason": "缺少实时分钟", "state": state}

    if minute < ENTRY_MINUTE_FROM:
        return {**base, "action": "WATCHING_0_10", "reason": f"{minute}分钟 0-0，未到进场窗口", "state": state}

    if minute > ENTRY_MINUTE_TO:
        return {**base, "action": "SKIP_WINDOW_CLOSED", "reason": f"{minute}分钟仍未触发买点", "state": state}

    rg = evaluate_risk_guard(
        open_positions=0,
        same_league_open=0,
        same_country_open=0,
        day_loss_pct=0.0,
        consecutive_losses=0,
    )
    base["risk_guard"] = rg.to_dict()
    if not rg.allow:
        return {**base, "action": "SKIP_RISK_GUARD", "reason": rg.reason, "state": state}

    tempo = evaluate_live_tempo(fixture_id, api_client, minute=minute)
    if tempo.get("action") == "SKIP":
        return {
            **base,
            "action": "SKIP_TEMPO_GATE",
            "reason": tempo.get("reason", "赛中节奏不达标"),
            "state": state,
            "tempo": tempo,
        }

    lines, raw_resp = fetch_live_ht_ou_lines(fixture_id, api_client)
    save_live_snapshot(date_key, fixture_id, state, lines, raw_resp)
    red_card = bool((state.get("raw_status") or {}).get("red"))
    entry = choose_entry_line(
        lines,
        minute=int(minute),
        item=item,
        tempo=tempo,
        red_card=red_card,
    )
    if not entry:
        return {
            **base,
            "action": "WAIT_LINE_NOT_READY",
            "reason": "未出现大1.0/大0.75合理水位",
            "state": state,
            "live_lines": lines,
        }

    return {
        **base,
        "action": "BUY_NOW",
        "reason": f"{minute}分钟 0-0，盘口到位",
        "state": state,
        "entry_minute": minute,
        "entry_score": state.get("score"),
        "entry_line": entry["line"],
        "entry_over_odds": entry["over_odds"],
        "entry_bookmaker": entry.get("bookmaker"),
        "tempo": tempo,
        "live_lines": lines,
        "prob_model": entry.get("prob_model"),
        "ev_gross": entry.get("ev_gross"),
        "ev_net": entry.get("ev_net"),
        "conservative_ev": entry.get("conservative_ev"),
        "execution_model": entry.get("execution_model"),
        "stake_fraction": rg.max_stake_fraction,
        "line_decay": estimate_best_entry_window(
            current_minute=int(minute),
            base_true_prob=float((entry.get("prob_model") or {}).get("p1_goal", 0.0)) + float((entry.get("prob_model") or {}).get("p2plus_goal", 0.0)),
            displayed_odds=float(entry.get("over_odds")),
            line=float(entry.get("line")),
        ).to_dict(),
    }


def _to_decision_log_row(result: dict, model_version: str = "V4.0_RULE", rule_version: str = "V4_HT_LIVE_PULLBACK") -> dict:
    state = result.get("state") or {}
    tempo = result.get("tempo") or {}
    line = result.get("entry_line")
    odds = result.get("entry_over_odds")
    minute = result.get("entry_minute", state.get("minute"))
    score = result.get("entry_score", state.get("score"))
    return {
        "fixture_id": result.get("fixture_id"),
        "timestamp": datetime.now().isoformat(),
        "match_minute": minute,
        "score": score,
        "line": line,
        "odds": odds,
        "live_tempo_status": tempo.get("tempo_status") or tempo.get("action"),
        "lineup_status": result.get("lineup_action"),
        "red_card_status": state.get("raw_status", {}).get("red"),
        "injury_status": "NOT_CHECKED",
        "model_version": model_version,
        "rule_version": rule_version,
        "decision": result.get("action"),
        "decision_reason": result.get("reason"),
        "ev_gross": result.get("ev_gross"),
        "ev_net": result.get("ev_net"),
        "conservative_ev": result.get("conservative_ev"),
    }


def _line_to_prob_proxy(line: float, odds: float) -> tuple[float, float, float]:
    """无模型时的临时概率代理：仅用于P0影子记录，不用于实盘决策。"""
    implied = 1.0 / max(odds, 1.01)
    if line >= 1.5:
        p2 = min(0.55, implied * 0.75)
    elif line >= 1.25:
        p2 = min(0.58, implied * 0.8)
    elif line >= 1.0:
        p2 = min(0.62, implied * 0.85)
    else:
        p2 = min(0.66, implied * 0.9)
    p1 = min(0.45, max(0.12, 0.55 - p2 * 0.5))
    p0 = max(0.0, 1.0 - p1 - p2)
    s = p0 + p1 + p2
    return p0 / s, p1 / s, p2 / s


def _build_shadow_rows(result: dict, item: dict) -> list[dict]:
    state = result.get("state") or {}
    minute = state.get("minute")
    score = state.get("score")
    if minute is None or score != "0-0":
        return []
    if minute < ENTRY_MINUTE_FROM or minute > ENTRY_MINUTE_TO:
        return []
    lines = result.get("live_lines") or []
    rows: list[dict] = []
    for ln in lines:
        line = _as_float(ln.get("line"))
        odds = _as_float(ln.get("over_odds"))
        if line is None or odds is None:
            continue
        if line not in (0.75, 1.0, 1.25, 1.5):
            continue
        p0, p1, p2 = _line_to_prob_proxy(line, odds)
        ev_res = over_asian_ev(line=line, odds=odds, p0=p0, p1=p1, p2plus=p2)
        old_rule = (line in TARGET_LINES) and (ODDS_RANGES[line][0] <= odds <= ODDS_RANGES[line][1])
        rows.append({
            "fixture_id": result.get("fixture_id"),
            "minute": minute,
            "score_at_minute": score,
            "available_line": line,
            "available_over_odds": odds,
            "available_under_odds": _as_float(ln.get("under_odds")),
            "would_enter_by_old_rule": old_rule,
            "would_enter_by_ev_rule": ev_res.ev > 0,
            "ev_gross": round(ev_res.ev, 6),
            "ht_goals_after_entry": None,
            "asian_result": "PENDING",
            "paper_pnl": None,
            "source_strategy": item.get("strategy_id", "V4_HT_LIVE_PULLBACK"),
            "logged_at": datetime.now().isoformat(),
        })
    return rows


def _merge_entries(path: Path, new_rows: list[dict]) -> list[dict]:
    existing = _load_json(path, [])
    seen = {str(x.get("fixture_id")) for x in existing if x.get("action") == "BUY_NOW"}
    merged = list(existing)
    for row in new_rows:
        if row.get("action") == "BUY_NOW" and str(row.get("fixture_id")) not in seen:
            merged.append(row)
            seen.add(str(row.get("fixture_id")))
    return merged


def run_once(date_str: str, api_client: Callable[[str], Optional[dict]] = api_get) -> dict:
    key = _date_key(date_str)
    watch_path = REPORT_DIR / f"live_watchlist_{key}.json"
    watchlist = _load_json(watch_path, [])
    if not watchlist:
        return {"error": f"无滚球雷达文件或文件为空: {watch_path}"}

    statuses = []
    entries = []
    decision_path = decision_log_path(key)
    shadow_path = shadow_backtest_path(key)
    exec_path = execution_sim_path(key)
    for item in watchlist:
        result = evaluate_watch_item(item, key, api_client)
        statuses.append(result)
        append_jsonl(decision_path, _to_decision_log_row(result))
        for row in _build_shadow_rows(result, item):
            append_jsonl(shadow_path, row)
        if result.get("action") == "BUY_NOW":
            entries.append(result)
            ev_proxy = over_asian_ev(
                line=float(result.get("entry_line")),
                odds=float(result.get("entry_over_odds")),
                p0=0.35,
                p1=0.32,
                p2plus=0.33,
            )
            exec_cost = estimate_execution_cost(
                displayed_odds=float(result.get("entry_over_odds")),
                ev_gross=ev_proxy.ev,
                odds_alive_seconds=3.0,
                latency_seconds=1.5,
                market_freeze=False,
            )
            append_jsonl(exec_path, {
                "fixture_id": result.get("fixture_id"),
                "minute": result.get("entry_minute"),
                "quote_seen_time": result.get("checked_at"),
                "system_decision_time": datetime.now().isoformat(),
                "displayed_odds": result.get("entry_over_odds"),
                "simulated_fill_odds": exec_cost.simulated_fill_odds,
                "odds_alive_seconds": 3.0,
                "market_freeze": False,
                "accepted_amount_estimate": 1.0,
                "rejected_amount_estimate": 0.0,
                "slippage": exec_cost.slippage,
                "latency_seconds": exec_cost.latency_seconds,
                "ev_gross": round(ev_proxy.ev, 6),
                "ev_net": round(exec_cost.ev_net, 6),
                "conservative_ev": round(exec_cost.conservative_ev, 6),
                "logged_at": datetime.now().isoformat(),
            })
        logger.info(f"[V4_LIVE] {result.get('fixture_id')} {result.get('action')} | {result.get('reason')}")
        time.sleep(0.3)

    status_path = MONITOR_DIR / f"v4_live_status_{key}.json"
    _save_json(status_path, {
        "date": key,
        "updated_at": datetime.now().isoformat(),
        "statuses": statuses,
    })

    entry_path = PAPER_DIR / f"v4_live_entries_{key}.json"
    if entries:
        _save_json(entry_path, _merge_entries(entry_path, entries))

    return {
        "date": key,
        "watchlist_count": len(watchlist),
        "buy_count": len(entries),
        "status_path": str(status_path),
        "entry_path": str(entry_path) if entries else None,
        "decision_log_path": str(decision_path),
        "shadow_backtest_path": str(shadow_path),
        "execution_sim_path": str(exec_path),
        "statuses": statuses,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--once", action="store_true", help="只检查一次")
    parser.add_argument("--watch", action="store_true", help="循环监控")
    parser.add_argument("--interval", type=int, default=30, help="循环间隔秒")
    args = parser.parse_args()

    if args.watch:
        while True:
            result = run_once(args.date)
            print(json.dumps({k: v for k, v in result.items() if k != "statuses"}, ensure_ascii=False, indent=2))
            time.sleep(args.interval)
    else:
        result = run_once(args.date)
        print(json.dumps({k: v for k, v in result.items() if k != "statuses"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
