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


def choose_entry_line(lines: list[dict]) -> Optional[dict]:
    """选择可进场盘口，优先大1.0，其次大0.75。"""
    for target in TARGET_LINES:
        lo, hi = ODDS_RANGES[target]
        candidates = [
            ln for ln in lines
            if abs(float(ln.get("line", 0)) - target) < 0.001
            and lo <= float(ln.get("over_odds", 0)) <= hi
        ]
        if candidates:
            # 同线位选赔率更高但仍在合理区间的
            return sorted(candidates, key=lambda x: x["over_odds"], reverse=True)[0]
    return None


def save_live_snapshot(date_key: str, fixture_id: int, state: dict, lines: list[dict], raw_resp: dict):
    """保存 live odds 快照。任务6后由正式快照库负责索引和去重。"""
    return save_snapshot_record(date_key, fixture_id, state, lines, raw_resp)


def evaluate_watch_item(item: dict, date_key: str, api_client: Callable[[str], Optional[dict]] = api_get) -> dict:
    fixture_id = int(item["fixture_id"])
    base = {
        "fixture_id": fixture_id,
        "home": item.get("home"),
        "away": item.get("away"),
        "league": item.get("league"),
        "strategy_id": "V4_HT_LIVE_PULLBACK",
        "checked_at": datetime.now().isoformat(),
        "pre_ht_line": item.get("pre_ht_line"),
        "lineup_action": item.get("lineup_action"),
    }

    if item.get("market_focus") != "HT_LIVE_OVER":
        return {**base, "action": "SKIP_NOT_HT_FOCUS", "reason": "非上半场走地方向"}

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
    entry = choose_entry_line(lines)
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
    }


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
    for item in watchlist:
        result = evaluate_watch_item(item, key, api_client)
        statuses.append(result)
        if result.get("action") == "BUY_NOW":
            entries.append(result)
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
