"""
V4 半场结果自动回填
==================
读取 v4_live_entries_YYYYMMDD.json，在比赛进入 HT/2H/FT 后拉取半场比分，
用亚洲大小球规则结算 V4_HT_LIVE_PULLBACK 纸盘入场结果。

用法:
  python3 engine/v4_ht_result_verifier.py --date 20260511 --once
  python3 engine/v4_ht_result_verifier.py --date 20260511 --watch --interval 300
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
from engine.asian_over_settlement import settle_asian_total

PAPER_DIR = BASE_DIR / "data" / "paper_trading"

HALFTIME_READY_STATUSES = {"HT", "2H", "FT", "AET", "PEN", "WO", "SUSP", "INT"}
NOT_READY_STATUSES = {"TBD", "NS", "1H"}


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


def extract_halftime_score(fixture_item: dict) -> tuple[Optional[str], Optional[int], Optional[str]]:
    fixture = fixture_item.get("fixture", {}) or {}
    status = (fixture.get("status", {}) or {}).get("short")
    score = fixture_item.get("score", {}) or {}
    ht = score.get("halftime", {}) or {}
    home = ht.get("home")
    away = ht.get("away")

    if status in NOT_READY_STATUSES:
        return None, None, f"NOT_HALFTIME:{status}"
    if status not in HALFTIME_READY_STATUSES:
        return None, None, f"UNSUPPORTED_STATUS:{status}"
    if home is None or away is None:
        return None, None, "HT_SCORE_EMPTY"

    ht_home = int(home or 0)
    ht_away = int(away or 0)
    return f"{ht_home}-{ht_away}", ht_home + ht_away, None


def settle_entry_from_fixture(entry: dict, fixture_item: dict, default_stake: float = 1.0) -> Optional[dict]:
    ht_score, ht_goals, reason = extract_halftime_score(fixture_item)
    if reason:
        return None

    line = _as_float(entry.get("entry_line"))
    odds = _as_float(entry.get("entry_over_odds"))
    if line is None or odds is None:
        raise ValueError(f"entry line/odds invalid: fixture_id={entry.get('fixture_id')}")

    stake = _as_float(entry.get("stake"), default_stake) or default_stake
    settlement = settle_asian_total(
        goals=int(ht_goals or 0),
        line=line,
        odds=odds,
        stake=stake,
        side="OVER",
    )

    status = (fixture_item.get("fixture", {}) or {}).get("status", {}) or {}
    return {
        "fixture_id": entry.get("fixture_id"),
        "home": entry.get("home"),
        "away": entry.get("away"),
        "league": entry.get("league"),
        "strategy_id": entry.get("strategy_id", "V4_HT_LIVE_PULLBACK"),
        "verified_phase": "HALFTIME",
        "verified_at": datetime.now().isoformat(),
        "fixture_status": status.get("short"),
        "fixture_elapsed": status.get("elapsed"),
        "entry_minute": entry.get("entry_minute"),
        "entry_score": entry.get("entry_score"),
        "entry_line": line,
        "entry_over_odds": odds,
        "entry_bookmaker": entry.get("entry_bookmaker"),
        "stake": stake,
        "ht_score": ht_score,
        "ht_goals": ht_goals,
        "settlement": settlement.to_dict(),
        "is_hit": settlement.pnl > 0,
        "is_loss": settlement.pnl < 0,
        "is_push": settlement.pnl == 0,
        "pnl": round(settlement.pnl, 4),
        "roi_pct": round(settlement.pnl / stake * 100, 2) if stake else 0.0,
        "raw_entry": entry,
    }


def verify_ht_date(
    date_str: str,
    api_client: Callable[[str], Optional[dict]] = api_get,
    default_stake: float = 1.0,
) -> dict:
    key = _date_key(date_str)
    entry_path = PAPER_DIR / f"v4_live_entries_{key}.json"
    entries = _load_json(entry_path, [])
    if not entries:
        return {"error": f"V4走地纸盘文件不存在或为空: {entry_path}"}

    results = []
    pending_items = []
    errors = []
    total_pnl = 0.0
    total_staked = 0.0

    for entry in entries:
        fid = entry.get("fixture_id")
        if not fid:
            errors.append({"fixture_id": None, "reason": "ENTRY_NO_FIXTURE_ID", "entry": entry})
            continue

        fixture = fetch_fixture(int(fid), api_client)
        if not fixture:
            pending_items.append({"fixture_id": fid, "reason": "API_EMPTY"})
            continue

        ht_score, _, pending_reason = extract_halftime_score(fixture)
        if pending_reason:
            pending_items.append({"fixture_id": fid, "reason": pending_reason})
            continue

        try:
            settled = settle_entry_from_fixture(entry, fixture, default_stake=default_stake)
        except Exception as exc:
            errors.append({"fixture_id": fid, "reason": str(exc)})
            continue

        if settled:
            results.append(settled)
            total_pnl += float(settled.get("pnl", 0))
            total_staked += float(settled.get("stake", 0))
            logger.info(
                f"[V4_HT_VERIFY] {fid} HT:{ht_score} "
                f"{settled['settlement']['result']} PnL:{settled['pnl']:+.2f}"
            )
        time.sleep(0.2)

    completed = len(results)
    wins = sum(1 for r in results if r.get("pnl", 0) > 0)
    pushes = sum(1 for r in results if r.get("pnl", 0) == 0)
    losses = sum(1 for r in results if r.get("pnl", 0) < 0)
    summary = {
        "date": key,
        "verified_at": datetime.now().isoformat(),
        "strategy_id": "V4_HT_LIVE_PULLBACK",
        "verification_mode": "HALFTIME_AUTO",
        "total_entries": len(entries),
        "completed": completed,
        "pending": len(pending_items),
        "errors": len(errors),
        "wins": wins,
        "pushes": pushes,
        "losses": losses,
        "hit_rate_pct": round(wins / completed * 100, 1) if completed else 0.0,
        "total_staked": round(total_staked, 4),
        "total_pnl": round(total_pnl, 4),
        "roi_pct": round(total_pnl / total_staked * 100, 2) if total_staked else 0.0,
        "results": results,
        "pending_items": pending_items,
        "error_items": errors,
    }

    out_path = PAPER_DIR / f"v4_live_verified_{key}.json"
    _save_json(out_path, summary)
    logger.info(
        f"V4半场自动验证完成: {key} | W/P/L={wins}/{pushes}/{losses} | "
        f"pending={len(pending_items)} | ROI:{summary['roi_pct']:+.2f}% → {out_path}"
    )
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--once", action="store_true", help="只验证一次")
    parser.add_argument("--watch", action="store_true", help="循环验证，适合半场后自动回填")
    parser.add_argument("--interval", type=int, default=300, help="循环间隔秒")
    parser.add_argument("--stake", type=float, default=1.0, help="默认纸盘投注单位")
    parser.add_argument("--max-runs", type=int, default=0, help="watch 模式最多运行次数，0 表示不限")
    args = parser.parse_args()

    if args.watch:
        runs = 0
        while True:
            result = verify_ht_date(args.date, default_stake=args.stake)
            print(json.dumps({k: v for k, v in result.items() if k != "results"}, ensure_ascii=False, indent=2))
            runs += 1
            if args.max_runs and runs >= args.max_runs:
                break
            time.sleep(args.interval)
    else:
        result = verify_ht_date(args.date, default_stake=args.stake)
        print(json.dumps({k: v for k, v in result.items() if k != "results"}, ensure_ascii=False, indent=2))

    # ── 自动刷新仪表盘 ──
    try:
        from engine.v4_dashboard import render_dashboard
        render_dashboard(args.date)
    except Exception:
        pass


if __name__ == "__main__":
    main()
