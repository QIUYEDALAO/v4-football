"""
V4 /odds/live 快照库
====================
API-Football 的 /odds/live 不保存历史，所以我们必须自己轮询落盘。

目录结构:
  data/live_odds_snapshots/YYYYMMDD/index.json
  data/live_odds_snapshots/YYYYMMDD/{fixture_id}/HHMMSS.json
  data/live_odds_snapshots/YYYYMMDD/{fixture_id}/latest.json

用法:
  python3 engine/live_odds_snapshot.py --date 20260511 --once
  python3 engine/live_odds_snapshot.py --date 20260511 --watch --interval 30
  python3 engine/live_odds_snapshot.py --date 20260511 --fixture-id 123456 --once
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

from engine import net_utils

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
SNAP_DIR = BASE_DIR / "data" / "live_odds_snapshots"


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


def _extract_line(text: str) -> Optional[float]:
    nums = re.findall(r"\d+(?:\.\d+)?", text or "")
    if not nums:
        return None
    return _as_float(nums[-1])


def _normalize_line(line: float) -> float:
    return round(float(line), 2)


def api_get(endpoint: str) -> Optional[dict]:
    return net_utils.api_get(endpoint)


def fetch_fixture_state(fixture_id: int, api_client: Callable[[str], Optional[dict]] = api_get) -> dict:
    resp = api_client(f"fixtures?id={fixture_id}")
    data = (resp or {}).get("response") or []
    if not data:
        return {"fixture_id": fixture_id, "state": "API_EMPTY", "minute": None, "score": None}

    item = data[0]
    status = item.get("fixture", {}).get("status", {}) or {}
    goals = item.get("goals", {}) or {}
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
        "raw_status": status,
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


def extract_live_ht_ou_lines(live_odds_resp: dict) -> list[dict]:
    """从 /odds/live 响应提取半场大球线，只保留 Over。"""
    lines = []
    for bm in _walk_live_books(live_odds_resp):
        bookmaker = bm.get("name", "LIVE")
        for bet in bm.get("bets", []) or []:
            bet_name = str(bet.get("name") or bet.get("label") or bet.get("market") or "")
            bet_lower = bet_name.lower()
            values_text = json.dumps(bet.get("values", []) or bet.get("odds", []), ensure_ascii=False).lower()
            market_text = f"{bet_lower} {values_text}"
            if "over" not in market_text and "大" not in market_text:
                continue
            if not any(token in market_text for token in ("half", "1st", "first", "ht", "上半")):
                continue

            values = bet.get("values", []) or bet.get("odds", []) or []
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
                    "line": _normalize_line(line),
                    "over_odds": odd,
                    "market_name": bet_name,
                    "label": label,
                })
    lines.sort(key=lambda x: (0 if "pinnacle" in x["bookmaker"].lower() else 1, x["line"]))
    return lines


def fetch_live_ht_ou_lines(fixture_id: int, api_client: Callable[[str], Optional[dict]] = api_get) -> tuple[list[dict], dict]:
    resp = api_client(f"odds/live?fixture={fixture_id}")
    return extract_live_ht_ou_lines(resp or {}), (resp or {})


def build_snapshot(
    fixture_id: int,
    api_client: Callable[[str], Optional[dict]] = api_get,
    *,
    state: Optional[dict] = None,
    watch_item: Optional[dict] = None,
) -> dict:
    state = state or fetch_fixture_state(fixture_id, api_client)
    lines, raw_resp = fetch_live_ht_ou_lines(fixture_id, api_client)
    line_values = sorted({float(x["line"]) for x in lines})
    return {
        "fixture_id": fixture_id,
        "captured_at": datetime.now().isoformat(),
        "state": state,
        "line_count": len(lines),
        "line_values": line_values,
        "lines": lines,
        "watch_item": {
            "home": (watch_item or {}).get("home"),
            "away": (watch_item or {}).get("away"),
            "league": (watch_item or {}).get("league"),
            "market_focus": (watch_item or {}).get("market_focus"),
            "pre_ht_line": (watch_item or {}).get("pre_ht_line"),
        } if watch_item else {},
        "raw": raw_resp,
    }


def _snapshot_paths(date_key: str, fixture_id: int, captured_at: str) -> tuple[Path, Path]:
    ts = datetime.fromisoformat(captured_at).strftime("%H%M%S")
    fixture_dir = SNAP_DIR / date_key / str(fixture_id)
    return fixture_dir / f"{ts}.json", fixture_dir / "latest.json"


def _update_index(date_key: str, snapshot: dict, snapshot_path: Path, *, increment: bool = True):
    index_path = SNAP_DIR / date_key / "index.json"
    index = _load_json(index_path, {"date": date_key, "fixtures": {}})
    fid = str(snapshot["fixture_id"])
    existing = index.setdefault("fixtures", {}).get(fid, {})
    count = int(existing.get("snapshot_count", 0)) + (1 if increment else 0)
    duplicate_count = int(existing.get("duplicate_count", 0)) + (0 if increment else 1)
    first_seen = existing.get("first_seen") or snapshot.get("captured_at")
    index["fixtures"][fid] = {
        "fixture_id": snapshot["fixture_id"],
        "home": snapshot.get("watch_item", {}).get("home"),
        "away": snapshot.get("watch_item", {}).get("away"),
        "league": snapshot.get("watch_item", {}).get("league"),
        "first_seen": first_seen,
        "last_seen": snapshot.get("captured_at"),
        "snapshot_count": count,
        "duplicate_count": duplicate_count,
        "latest_state": snapshot.get("state", {}),
        "latest_line_values": snapshot.get("line_values", []),
        "latest_path": str(snapshot_path),
    }
    index["updated_at"] = datetime.now().isoformat()
    _save_json(index_path, index)


def save_snapshot(date_key: str, snapshot: dict) -> Path:
    path, latest_path = _snapshot_paths(date_key, int(snapshot["fixture_id"]), snapshot["captured_at"])
    previous = _load_json(latest_path, None)
    if previous and previous.get("state") == snapshot.get("state") and previous.get("lines") == snapshot.get("lines"):
        # 同一秒/同一状态重复轮询时仍更新 index 的 last_seen，但不制造重复文件。
        previous["last_duplicate_seen_at"] = datetime.now().isoformat()
        _save_json(latest_path, previous)
        _update_index(date_key, previous, latest_path, increment=False)
        return latest_path

    _save_json(path, snapshot)
    _save_json(latest_path, snapshot)
    _update_index(date_key, snapshot, path)
    return path


def save_live_snapshot(date_key: str, fixture_id: int, state: dict, lines: list[dict], raw_resp: dict, watch_item: Optional[dict] = None) -> Path:
    snapshot = {
        "fixture_id": fixture_id,
        "captured_at": datetime.now().isoformat(),
        "state": state,
        "line_count": len(lines),
        "line_values": sorted({float(x["line"]) for x in lines}),
        "lines": lines,
        "watch_item": watch_item or {},
        "raw": raw_resp,
    }
    return save_snapshot(date_key, snapshot)


def load_fixture_timeline(date_key: str, fixture_id: int) -> list[dict]:
    fixture_dir = SNAP_DIR / date_key / str(fixture_id)
    rows = []
    for path in sorted(fixture_dir.glob("*.json")):
        if path.name == "latest.json":
            continue
        rows.append(_load_json(path, {}))
    return rows


def summarize_fixture_timeline(date_key: str, fixture_id: int) -> dict:
    rows = load_fixture_timeline(date_key, fixture_id)
    if not rows:
        return {"fixture_id": fixture_id, "snapshot_count": 0}

    first_line = None
    lowest_line = None
    first_target = None
    for row in rows:
        values = row.get("line_values", [])
        if values and first_line is None:
            first_line = max(values)
        if values:
            low = min(values)
            lowest_line = low if lowest_line is None else min(lowest_line, low)
        if first_target is None:
            for target in (1.0, 0.75):
                target_lines = [x for x in row.get("lines", []) if x.get("line") == target]
                if target_lines:
                    line = sorted(target_lines, key=lambda x: x.get("over_odds", 0), reverse=True)[0]
                    first_target = {
                        "captured_at": row.get("captured_at"),
                        "minute": row.get("state", {}).get("minute"),
                        "line": line.get("line"),
                        "over_odds": line.get("over_odds"),
                        "bookmaker": line.get("bookmaker"),
                    }
                    break

    return {
        "fixture_id": fixture_id,
        "snapshot_count": len(rows),
        "first_seen": rows[0].get("captured_at"),
        "last_seen": rows[-1].get("captured_at"),
        "first_line": first_line,
        "lowest_line": lowest_line,
        "first_target_line": first_target,
    }


def _watchlist_for_date(date_key: str) -> list[dict]:
    return _load_json(REPORT_DIR / f"live_watchlist_{date_key}.json", [])


def capture_once(date_str: str, api_client: Callable[[str], Optional[dict]] = api_get, fixture_id: Optional[int] = None) -> dict:
    key = _date_key(date_str)
    watchlist = _watchlist_for_date(key)
    if fixture_id is not None:
        items = [x for x in watchlist if str(x.get("fixture_id")) == str(fixture_id)]
        if not items:
            items = [{"fixture_id": fixture_id}]
    else:
        items = watchlist

    saved = []
    for item in items:
        fid = int(item["fixture_id"])
        snapshot = build_snapshot(fid, api_client, watch_item=item)
        path = save_snapshot(key, snapshot)
        saved.append({
            "fixture_id": fid,
            "path": str(path),
            "line_count": snapshot.get("line_count", 0),
            "state": snapshot.get("state", {}),
        })
        time.sleep(0.3)

    return {
        "date": key,
        "count": len(saved),
        "saved": saved,
        "index_path": str(SNAP_DIR / key / "index.json"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--fixture-id", type=int, default=None)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()

    if args.watch:
        while True:
            result = capture_once(args.date, fixture_id=args.fixture_id)
            print(json.dumps({k: v for k, v in result.items() if k != "saved"}, ensure_ascii=False, indent=2))
            time.sleep(args.interval)
    else:
        result = capture_once(args.date, fixture_id=args.fixture_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
