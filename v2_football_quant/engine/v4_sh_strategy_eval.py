from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PAPER_DIR = BASE_DIR / "data" / "paper_trading"
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
MIN_SAMPLE = 50


def _load(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_rows() -> list[dict]:
    rows = []
    for fp in sorted(PAPER_DIR.glob("v4_second_half_verified_*.json")):
        data = _load(fp, {})
        rows.extend(data.get("results", []))
    return rows


def evaluate(rows: list[dict]) -> dict:
    n = len(rows)
    staked = sum(float(x.get("stake", 0) or 0) for x in rows)
    pnl = sum(float(x.get("pnl", 0) or 0) for x in rows)
    wins = sum(1 for x in rows if float(x.get("pnl", 0) or 0) > 0)
    pushes = sum(1 for x in rows if float(x.get("pnl", 0) or 0) == 0)
    losses = sum(1 for x in rows if float(x.get("pnl", 0) or 0) < 0)
    return {
        "generated_at": datetime.now().isoformat(),
        "strategy_id": "V4_SH_LIVE_OVER",
        "sample_size": n,
        "sample_ready": n >= MIN_SAMPLE,
        "decision": "EVALUATE" if n >= MIN_SAMPLE else f"WAIT_SAMPLE_{n}/{MIN_SAMPLE}",
        "wins": wins,
        "pushes": pushes,
        "losses": losses,
        "hit_rate_pct": round(wins / n * 100, 2) if n else 0.0,
        "total_staked": round(staked, 4),
        "total_pnl": round(pnl, 4),
        "roi_pct": round(pnl / staked * 100, 2) if staked else 0.0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    rep = evaluate(load_rows())
    if args.save:
        out = REPORT_DIR / "v4_sh_strategy_eval.json"
        out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"path": str(out), "result": rep}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

