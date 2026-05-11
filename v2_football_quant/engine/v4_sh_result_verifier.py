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

from engine import net_utils
from engine.asian_over_settlement import settle_asian_total

PAPER_DIR = BASE_DIR / "data" / "paper_trading"

FINAL_STATUSES = {"FT", "AET", "PEN", "WO"}


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


def api_get(endpoint: str) -> Optional[dict]:
    return net_utils.api_get(endpoint)


def fetch_fixture(fixture_id: int, api_client: Callable[[str], Optional[dict]] = api_get) -> Optional[dict]:
    resp = api_client(f"fixtures?id={fixture_id}")
    rows = (resp or {}).get("response") or []
    return rows[0] if rows else None


def settle_one(entry: dict, fixture_item: dict, default_stake: float = 1.0) -> Optional[dict]:
    status = ((fixture_item.get("fixture") or {}).get("status") or {}).get("short")
    if status not in FINAL_STATUSES:
        return None

    score = fixture_item.get("score") or {}
    ht = score.get("halftime") or {}
    ft = score.get("fulltime") or {}
    if ht.get("home") is None or ht.get("away") is None or ft.get("home") is None or ft.get("away") is None:
        return None

    sh_home = int(ft.get("home") or 0) - int(ht.get("home") or 0)
    sh_away = int(ft.get("away") or 0) - int(ht.get("away") or 0)
    sh_goals = max(0, sh_home + sh_away)

    line = _as_float(entry.get("entry_line"))
    odds = _as_float(entry.get("entry_over_odds"))
    if line is None or odds is None:
        return None
    stake = _as_float(entry.get("stake"), default_stake) or default_stake
    st = settle_asian_total(goals=sh_goals, line=line, odds=odds, stake=stake, side="OVER")

    return {
        "fixture_id": entry.get("fixture_id"),
        "home": entry.get("home"),
        "away": entry.get("away"),
        "league": entry.get("league"),
        "strategy_id": "V4_SH_LIVE_OVER",
        "verified_phase": "FULLTIME_SECOND_HALF",
        "verified_at": datetime.now().isoformat(),
        "fixture_status": status,
        "entry_line": line,
        "entry_over_odds": odds,
        "stake": stake,
        "ht_score": f"{int(ht.get('home') or 0)}-{int(ht.get('away') or 0)}",
        "ft_score": f"{int(ft.get('home') or 0)}-{int(ft.get('away') or 0)}",
        "sh_goals": sh_goals,
        "settlement": st.to_dict(),
        "is_hit": st.pnl > 0,
        "is_loss": st.pnl < 0,
        "is_push": st.pnl == 0,
        "pnl": round(st.pnl, 4),
        "roi_pct": round(st.pnl / stake * 100, 2) if stake else 0.0,
        "raw_entry": entry,
    }


def verify_sh_date(date_str: str, api_client: Callable[[str], Optional[dict]] = api_get, default_stake: float = 1.0) -> dict:
    key = _date_key(date_str)
    entry_path = PAPER_DIR / f"v4_second_half_entries_{key}.json"
    entries = _load_json(entry_path, [])
    if not entries:
        return {"error": f"SH入场文件为空: {entry_path}"}

    results = []
    pending = []
    for entry in entries:
        fid = entry.get("fixture_id")
        if not fid:
            continue
        fixture = fetch_fixture(int(fid), api_client)
        if not fixture:
            pending.append({"fixture_id": fid, "reason": "API_EMPTY"})
            continue
        settled = settle_one(entry, fixture, default_stake=default_stake)
        if settled is None:
            pending.append({"fixture_id": fid, "reason": "NOT_FINISHED"})
            continue
        results.append(settled)
        time.sleep(0.2)

    staked = sum(float(r.get("stake", 0) or 0) for r in results)
    pnl = sum(float(r.get("pnl", 0) or 0) for r in results)
    wins = sum(1 for r in results if float(r.get("pnl", 0) or 0) > 0)
    pushes = sum(1 for r in results if float(r.get("pnl", 0) or 0) == 0)
    losses = sum(1 for r in results if float(r.get("pnl", 0) or 0) < 0)
    summary = {
        "date": key,
        "verified_at": datetime.now().isoformat(),
        "strategy_id": "V4_SH_LIVE_OVER",
        "total_entries": len(entries),
        "completed": len(results),
        "pending": len(pending),
        "wins": wins,
        "pushes": pushes,
        "losses": losses,
        "hit_rate_pct": round(wins / len(results) * 100, 1) if results else 0.0,
        "total_staked": round(staked, 4),
        "total_pnl": round(pnl, 4),
        "roi_pct": round(pnl / staked * 100, 2) if staked else 0.0,
        "results": results,
        "pending_items": pending,
    }
    out = PAPER_DIR / f"v4_second_half_verified_{key}.json"
    _save_json(out, summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=600)
    parser.add_argument("--stake", type=float, default=1.0)
    args = parser.parse_args()
    if args.watch:
        while True:
            r = verify_sh_date(args.date, default_stake=args.stake)
            print(json.dumps({k: v for k, v in r.items() if k != "results"}, ensure_ascii=False, indent=2))
            time.sleep(args.interval)
    else:
        r = verify_sh_date(args.date, default_stake=args.stake)
        print(json.dumps({k: v for k, v in r.items() if k != "results"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

