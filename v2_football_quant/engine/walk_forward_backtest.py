from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PAPER_DIR = BASE_DIR / "data" / "paper_trading"
REPORT_DIR = BASE_DIR / "data" / "daily_reports"


@dataclass
class Split:
    name: str
    start: str
    end: str


def _load(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_verified_rows() -> list[dict]:
    rows: list[dict] = []
    for fp in sorted(PAPER_DIR.glob("v4_live_verified_*.json")):
        data = _load(fp, {})
        for r in data.get("results", []):
            rr = dict(r)
            rr["_date"] = (rr.get("verified_at") or "")[:10]
            rows.append(rr)
    return rows


def _in_range(d: str, start: str, end: str) -> bool:
    return bool(d) and start <= d <= end


def _eval(rows: list[dict]) -> dict:
    n = len(rows)
    staked = sum(float(x.get("stake", 0) or 0) for x in rows)
    pnl = sum(float(x.get("pnl", 0) or 0) for x in rows)
    wins = sum(1 for x in rows if float(x.get("pnl", 0) or 0) > 0)
    return {
        "n": n,
        "wins": wins,
        "hit_rate_pct": round(wins / n * 100, 2) if n else 0.0,
        "staked": round(staked, 4),
        "pnl": round(pnl, 4),
        "roi_pct": round(pnl / staked * 100, 2) if staked else 0.0,
    }


def run_walk_forward() -> dict:
    rows = _load_verified_rows()
    splits = [
        Split("train", "2024-01-01", "2024-06-30"),
        Split("tune", "2024-07-01", "2024-09-30"),
        Split("valid", "2024-10-01", "2024-12-31"),
        Split("lock_test", "2025-01-01", "2025-06-30"),
        Split("forward_sim", "2025-07-01", "2025-12-31"),
        Split("paper_live", "2026-01-01", "2026-12-31"),
    ]
    out = {"generated_at": datetime.now().isoformat(), "sample_size": len(rows), "splits": {}}
    for sp in splits:
        seg = [r for r in rows if _in_range(r.get("_date", ""), sp.start, sp.end)]
        out["splits"][sp.name] = {"start": sp.start, "end": sp.end, **_eval(seg)}
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    rep = run_walk_forward()
    if args.save:
        p = REPORT_DIR / "v4_walk_forward_report.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"path": str(p), "report": rep}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

