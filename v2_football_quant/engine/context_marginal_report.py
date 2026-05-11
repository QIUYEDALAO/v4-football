from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
PAPER_DIR = BASE_DIR / "data" / "paper_trading"


def _load(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _collect_context() -> dict[int, dict]:
    ctx: dict[int, dict] = {}
    for fp in sorted(REPORT_DIR.glob("scout_v4_*.json")):
        rows = _load(fp, [])
        for r in rows if isinstance(rows, list) else []:
            fid = r.get("fixture_id")
            if not fid:
                continue
            ctx[int(fid)] = r.get("context_observation") or {}
    return ctx


def _collect_results() -> list[dict]:
    rows: list[dict] = []
    for fp in sorted(PAPER_DIR.glob("v4_live_verified_*.json")):
        d = _load(fp, {})
        rows.extend(d.get("results", []))
    return rows


def _bucket(rows: list[dict], name: str):
    n = len(rows)
    wins = sum(1 for r in rows if float(r.get("pnl", 0) or 0) > 0)
    staked = sum(float(r.get("stake", 0) or 0) for r in rows)
    pnl = sum(float(r.get("pnl", 0) or 0) for r in rows)
    return {
        "name": name,
        "n": n,
        "hit_rate_pct": round(wins / n * 100, 2) if n else 0.0,
        "roi_pct": round(pnl / staked * 100, 2) if staked else 0.0,
    }


def build_report() -> dict:
    ctx = _collect_context()
    rs = _collect_results()
    has_ref = []
    no_ref = []
    has_venue = []
    no_venue = []
    for r in rs:
        fid = int(r.get("fixture_id") or 0)
        c = ctx.get(fid, {})
        ref = (c.get("referee") or {}).get("referee_name")
        venue = (c.get("pitch") or {}).get("venue_name")
        (has_ref if ref else no_ref).append(r)
        (has_venue if venue else no_venue).append(r)
    return {
        "generated_at": datetime.now().isoformat(),
        "sample_size": len(rs),
        "referee_availability": {
            "has_referee": _bucket(has_ref, "has_referee"),
            "no_referee": _bucket(no_ref, "no_referee"),
        },
        "venue_availability": {
            "has_venue": _bucket(has_venue, "has_venue"),
            "no_venue": _bucket(no_venue, "no_venue"),
        },
        "note": "P8阶段为观测层检验，非因果结论；样本不足时仅作记录。",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    rep = build_report()
    if args.save:
        p = REPORT_DIR / "v4_context_marginal_report.json"
        p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"path": str(p), "report": rep}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

