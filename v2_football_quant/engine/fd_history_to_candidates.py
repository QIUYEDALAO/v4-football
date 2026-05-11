from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from engine.strategy_candidates_tracker import append_candidate
HIST_PATH = BASE_DIR / "data" / "historical" / "fd_history_matches.jsonl"


def _load_rows() -> list[dict]:
    if not HIST_PATH.exists():
        return []
    rows = []
    with open(HIST_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _roi_proxy(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    pnl = 0.0
    for r in rows:
        ht_goals = int(r.get("ht_goals") or 0)
        pnl += 0.8 if ht_goals > 0 else -1.0
    return pnl / len(rows) * 100


def run(strategy_id: str = "FD_PROXY_HT_GOAL") -> dict:
    rows = _load_rows()
    if not rows:
        return {"ok": False, "reason": f"no_history_file:{HIST_PATH}"}
    roi = _roi_proxy(rows)
    append_candidate({
        "strategy_id": strategy_id,
        "feature_set": ["football-data.co.uk", "ht_goal_proxy"],
        "league_filter": "TOP5_DEFAULT",
        "market_direction": "HT_GOAL_PROXY",
        "entry_minute_window": "N/A",
        "line_filter": ["N/A"],
        "odds_filter": "fixed_1.80_proxy",
        "sample_size": len(rows),
        "roi_train": roi,
        "roi_validation": roi,
        "roi_test": roi,
    })
    return {"ok": True, "sample_size": len(rows), "roi_proxy_pct": round(roi, 2)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy-id", default="FD_PROXY_HT_GOAL")
    args = parser.parse_args()
    print(json.dumps(run(args.strategy_id), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
