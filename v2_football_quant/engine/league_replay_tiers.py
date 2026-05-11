from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HIST_PATH = BASE_DIR / "data" / "historical" / "fd_history_matches.jsonl"
REPORT_DIR = BASE_DIR / "data" / "daily_reports"


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


def _pnl_proxy(ht_goals: int, odds: float = 1.80) -> float:
    # 近似：Over1.0
    if ht_goals >= 2:
        return odds - 1.0
    if ht_goals == 1:
        return 0.0
    return -1.0


def _tier(sample: int, roi: float) -> str:
    if sample >= 800 and roi >= 8.0:
        return "S"
    if sample >= 500 and roi >= 5.0:
        return "A"
    if sample >= 250 and roi >= 2.0:
        return "B"
    if sample >= 120 and roi >= 0.0:
        return "C"
    return "D"


def build_report() -> dict:
    rows = _load_rows()
    by_league: dict[str, dict] = {}
    for r in rows:
        lg = str(r.get("league_code") or "UNKNOWN")
        rec = by_league.setdefault(lg, {"league_code": lg, "league_name": r.get("league_name"), "n": 0, "staked": 0.0, "pnl": 0.0, "wins": 0})
        ht_goals = int(r.get("ht_goals") or 0)
        pnl = _pnl_proxy(ht_goals)
        rec["n"] += 1
        rec["staked"] += 1.0
        rec["pnl"] += pnl
        rec["wins"] += int(pnl > 0)

    league_rows = []
    for rec in by_league.values():
        n = rec["n"]
        staked = rec["staked"]
        pnl = rec["pnl"]
        roi = (pnl / staked * 100) if staked else 0.0
        league_rows.append({
            "league_code": rec["league_code"],
            "league_name": rec.get("league_name"),
            "sample_size": n,
            "wins": rec["wins"],
            "hit_rate_pct": round(rec["wins"] / n * 100, 2) if n else 0.0,
            "roi_pct": round(roi, 2),
            "tier": _tier(n, roi),
            "status": (
                "AUTO_TRADE" if _tier(n, roi) == "S" else
                "PAPER_ONLY" if _tier(n, roi) in ("A", "B") else
                "WATCH_ONLY" if _tier(n, roi) == "C" else
                "DISABLED"
            ),
        })
    league_rows.sort(key=lambda x: (-x["roi_pct"], -x["sample_size"]))
    return {
        "generated_at": datetime.now().isoformat(),
        "sample_size": len(rows),
        "league_count": len(league_rows),
        "leagues": league_rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    rep = build_report()
    if args.save:
        p = REPORT_DIR / "v4_league_replay_tiers.json"
        p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"path": str(p), "report": {"sample_size": rep["sample_size"], "league_count": rep["league_count"]}}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

