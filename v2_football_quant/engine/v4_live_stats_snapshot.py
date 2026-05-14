"""
V4 赛中统计快照采集
====================
仅用于赛后归因增强，不参与实时评分。

用法：
  python3 engine/v4_live_stats_snapshot.py --date 20260514
  python3 engine/v4_live_stats_snapshot.py --date 20260514 --minutes 15,30,45
  python3 engine/v4_live_stats_snapshot.py --date 20260514 --fixture 123456
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine import net_utils

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
ARCHIVE_DIR = BASE_DIR / "data" / "v4_archive"


def _date_key(v: str) -> str:
    return str(v).replace("-", "")


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    if isinstance(v, str):
        v = v.replace("%", "").strip()
    try:
        return float(v)
    except Exception:
        return default


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                continue
    return out


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _api_get(endpoint: str) -> dict[str, Any]:
    return net_utils.api_get(endpoint) or {}


def _safe_rows(resp: dict[str, Any]) -> list[dict[str, Any]]:
    rows = (resp or {}).get("response")
    return rows if isinstance(rows, list) else []


def _fixture_state(fixture_id: int) -> dict[str, Any]:
    rows = _safe_rows(_api_get(f"fixtures?id={fixture_id}"))
    if not rows:
        return {"ok": False, "minute": None, "status": "API_EMPTY"}
    item = rows[0]
    status = (item.get("fixture") or {}).get("status") or {}
    minute = status.get("elapsed")
    return {
        "ok": True,
        "minute": _safe_int(minute, -1) if minute is not None else None,
        "status": str(status.get("short") or ""),
    }


def _stats_snapshot(fixture_id: int) -> dict[str, Any]:
    rows = _safe_rows(_api_get(f"fixtures/statistics?fixture={fixture_id}"))
    if not rows:
        return {
            "stats_available": False,
            "shots_home": 0.0,
            "shots_away": 0.0,
            "shots_on_target_home": 0.0,
            "shots_on_target_away": 0.0,
            "corners_home": 0.0,
            "corners_away": 0.0,
            "dangerous_attacks_home": 0.0,
            "dangerous_attacks_away": 0.0,
            "possession_home": 0.0,
            "possession_away": 0.0,
        }

    out = {
        "stats_available": True,
        "shots_home": 0.0,
        "shots_away": 0.0,
        "shots_on_target_home": 0.0,
        "shots_on_target_away": 0.0,
        "corners_home": 0.0,
        "corners_away": 0.0,
        "dangerous_attacks_home": 0.0,
        "dangerous_attacks_away": 0.0,
        "possession_home": 0.0,
        "possession_away": 0.0,
    }
    for idx, team_stats in enumerate(rows[:2]):
        side = "home" if idx == 0 else "away"
        for s in team_stats.get("statistics", []) or []:
            name = str(s.get("type") or "").lower()
            val = _safe_float(s.get("value"), 0.0)
            if "total shots" in name:
                out[f"shots_{side}"] = val
            elif "shots on goal" in name or "shots on target" in name:
                out[f"shots_on_target_{side}"] = val
            elif "corner" in name:
                out[f"corners_{side}"] = val
            elif "dangerous attacks" in name:
                out[f"dangerous_attacks_{side}"] = val
            elif "ball possession" in name or "possession" in name:
                out[f"possession_{side}"] = val
    return out


def run(date_str: str, minutes: list[int], fixture_id: int | None = None, sleep_ms: int = 120) -> dict[str, Any]:
    key = _date_key(date_str)
    scout_path = REPORT_DIR / f"scout_v4_{key}.json"
    scout = _load_json(scout_path, [])
    if isinstance(scout, dict):
        scout = scout.get("results") or []
    if not isinstance(scout, list) or not scout:
        return {"error": f"scout文件不存在或为空: {scout_path}"}

    out_path = ARCHIVE_DIR / f"live_stats_snapshot_{key}.jsonl"
    existing = _load_jsonl(out_path)
    existing_keys = {
        (int(r.get("fixture_id") or 0), int(r.get("minute") or 0))
        for r in existing
        if r.get("fixture_id") is not None and r.get("minute") is not None
    }

    selected = [r for r in scout if (fixture_id is None or int(r.get("fixture_id") or 0) == int(fixture_id))]
    written = 0
    skipped_existing = 0
    skipped_not_reached = 0
    skipped_state = 0

    for rec in selected:
        fid = int(rec.get("fixture_id") or 0)
        if not fid:
            continue
        st = _fixture_state(fid)
        if not st.get("ok"):
            skipped_state += 1
            continue
        status = str(st.get("status") or "")
        elapsed = st.get("minute")
        if elapsed is None or elapsed < 0:
            skipped_state += 1
            continue

        snapshot = _stats_snapshot(fid)
        scan_time = datetime.now(timezone.utc).isoformat()
        for minute in minutes:
            k = (fid, minute)
            if k in existing_keys:
                skipped_existing += 1
                continue
            if elapsed < minute:
                skipped_not_reached += 1
                continue
            row = {
                "fixture_id": fid,
                "date": key,
                "league": rec.get("league"),
                "home": rec.get("home"),
                "away": rec.get("away"),
                "minute": minute,
                "observed_elapsed_minute": elapsed,
                "status_short": status,
                "scan_time": scan_time,
                "shots_home": snapshot.get("shots_home", 0.0),
                "shots_away": snapshot.get("shots_away", 0.0),
                "shots_on_target_home": snapshot.get("shots_on_target_home", 0.0),
                "shots_on_target_away": snapshot.get("shots_on_target_away", 0.0),
                "corners_home": snapshot.get("corners_home", 0.0),
                "corners_away": snapshot.get("corners_away", 0.0),
                "dangerous_attacks_home": snapshot.get("dangerous_attacks_home", 0.0),
                "dangerous_attacks_away": snapshot.get("dangerous_attacks_away", 0.0),
                "possession_home": snapshot.get("possession_home", 0.0),
                "possession_away": snapshot.get("possession_away", 0.0),
                "shots_total": round(_safe_float(snapshot.get("shots_home")) + _safe_float(snapshot.get("shots_away")), 3),
                "shots_on_target_total": round(_safe_float(snapshot.get("shots_on_target_home")) + _safe_float(snapshot.get("shots_on_target_away")), 3),
                "corners_total": round(_safe_float(snapshot.get("corners_home")) + _safe_float(snapshot.get("corners_away")), 3),
                "dangerous_attacks_total": round(_safe_float(snapshot.get("dangerous_attacks_home")) + _safe_float(snapshot.get("dangerous_attacks_away")), 3),
                "stats_available": bool(snapshot.get("stats_available")),
                "source": "fixtures/statistics",
            }
            _append_jsonl(out_path, row)
            existing_keys.add(k)
            written += 1
        time.sleep(max(0, sleep_ms) / 1000.0)

    return {
        "date": key,
        "minutes": minutes,
        "rows_written": written,
        "skipped_existing": skipped_existing,
        "skipped_not_reached": skipped_not_reached,
        "skipped_state": skipped_state,
        "output_path": str(out_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD or YYYY-MM-DD")
    parser.add_argument("--minutes", default="15,30,45", help="逗号分隔，默认15,30,45")
    parser.add_argument("--fixture", type=int, default=None, help="仅采集单场fixture")
    parser.add_argument("--sleep-ms", type=int, default=120, help="API节流毫秒")
    args = parser.parse_args()
    minutes = []
    for x in str(args.minutes).split(","):
        x = x.strip()
        if not x:
            continue
        try:
            minutes.append(int(x))
        except Exception:
            continue
    if not minutes:
        minutes = [15, 30, 45]
    result = run(args.date, sorted(set(minutes)), fixture_id=args.fixture, sleep_ms=args.sleep_ms)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

