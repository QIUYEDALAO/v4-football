from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "research"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT = DATA_DIR / "strategy_candidates.jsonl"


def append_candidate(row: dict[str, Any]) -> None:
    base = {
        "strategy_id": row.get("strategy_id"),
        "feature_set": row.get("feature_set", []),
        "league_filter": row.get("league_filter", "ALL"),
        "market_direction": row.get("market_direction", "HT_LIVE_OVER"),
        "entry_minute_window": row.get("entry_minute_window", "8-15"),
        "line_filter": row.get("line_filter", ["0.75", "1.0"]),
        "odds_filter": row.get("odds_filter", "EV_NET_POSITIVE"),
        "sample_size": int(row.get("sample_size", 0)),
        "roi_train": float(row.get("roi_train", 0)),
        "roi_validation": float(row.get("roi_validation", 0)),
        "roi_test": float(row.get("roi_test", 0)),
        "p_value_raw": row.get("p_value_raw"),
        "p_value_fdr": row.get("p_value_fdr"),
        "max_drawdown": row.get("max_drawdown"),
        "logged_at": datetime.now().isoformat(),
    }
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(base, ensure_ascii=False) + "\n")


def _summary() -> dict:
    if not OUT.exists():
        return {"count": 0, "path": str(OUT)}
    count = 0
    last = None
    with open(OUT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            count += 1
            try:
                last = json.loads(line)
            except Exception:
                pass
    return {"count": count, "path": str(OUT), "last": last}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--strategy-id", default="V4_BASELINE")
    parser.add_argument("--sample-size", type=int, default=0)
    parser.add_argument("--roi-train", type=float, default=0.0)
    parser.add_argument("--roi-validation", type=float, default=0.0)
    parser.add_argument("--roi-test", type=float, default=0.0)
    args = parser.parse_args()

    if args.summary:
        print(json.dumps(_summary(), ensure_ascii=False, indent=2))
        return

    append_candidate({
        "strategy_id": args.strategy_id,
        "feature_set": ["ht_goal_hazard_model", "asian_ev", "execution_cost_model"],
        "sample_size": args.sample_size,
        "roi_train": args.roi_train,
        "roi_validation": args.roi_validation,
        "roi_test": args.roi_test,
    })
    print(json.dumps({"ok": True, "path": str(OUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

