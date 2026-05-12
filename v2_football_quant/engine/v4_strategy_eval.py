"""
V4 策略样本评估
==============
读取 data/paper_trading/v4_live_verified_*.json。
样本 < 50 时只提示样本不足；样本 >= 50 时输出基础策略评估。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

PAPER_DIR = BASE_DIR / "data" / "paper_trading"
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
MIN_SAMPLE = 50


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_v4_results() -> list[dict]:
    rows = []
    for path in sorted(PAPER_DIR.glob("v4_live_verified_*.json")):
        data = _load_json(path, {})
        for item in data.get("results", []) if isinstance(data, dict) else []:
            item = dict(item)
            item["_source"] = path.name
            rows.append(item)
    return rows


def _entry_meta(row: dict) -> dict:
    raw = row.get("raw_entry") or {}
    intel = raw.get("intelligence") or row.get("intelligence") or {}
    match_type = raw.get("match_type") or row.get("match_type") or intel.get("match_type") or ["UNKNOWN"]
    if isinstance(match_type, str):
        match_type = [match_type]
    if not isinstance(match_type, list) or not match_type:
        match_type = ["UNKNOWN"]
    return {
        "match_type": [str(x) for x in match_type],
        "primary_direction": raw.get("primary_direction") or row.get("primary_direction") or intel.get("primary_direction") or "UNKNOWN",
        "confidence": raw.get("confidence") or row.get("confidence") or intel.get("confidence"),
        "strategy_id": row.get("strategy_id") or raw.get("strategy_id") or "UNKNOWN",
        "a_source": raw.get("a_source") or row.get("a_source") or "UNKNOWN",
        "capture_tier": raw.get("capture_tier") or row.get("capture_tier") or "UNKNOWN",
    }


def _bucket_line(line) -> str:
    try:
        return f"Over {float(line):.2f}".rstrip("0").rstrip(".")
    except Exception:
        return "UNKNOWN"


def _bucket_confidence(value) -> str:
    try:
        v = float(value)
    except Exception:
        return "UNKNOWN"
    if v >= 80:
        return "80+"
    if v >= 65:
        return "65-79"
    if v >= 50:
        return "50-64"
    return "<50"


def _bucket_summary(bucket: dict, min_sample: int = MIN_SAMPLE) -> dict:
    n = bucket["n"]
    stake = bucket["stake"]
    pnl = bucket["pnl"]
    wins = bucket["wins"]
    pushes = bucket["pushes"]
    losses = bucket["losses"]
    return {
        "n": n,
        "sample_status": "READY" if n >= min_sample else "SAMPLE_TOO_SMALL",
        "min_sample": min_sample,
        "wins": wins,
        "pushes": pushes,
        "losses": losses,
        "hit_rate_pct": round(wins / n * 100, 2) if n else 0.0,
        "staked": round(stake, 4),
        "pnl": round(pnl, 4),
        "roi_pct": round(pnl / stake * 100, 2) if stake else 0.0,
    }


def evaluate(rows: list[dict]) -> dict:
    n = len(rows)
    total_stake = sum(float(x.get("stake", 0) or 0) for x in rows)
    total_pnl = sum(float(x.get("pnl", 0) or 0) for x in rows)
    wins = sum(1 for x in rows if float(x.get("pnl", 0) or 0) > 0)
    pushes = sum(1 for x in rows if float(x.get("pnl", 0) or 0) == 0)
    losses = sum(1 for x in rows if float(x.get("pnl", 0) or 0) < 0)
    by_line = defaultdict(lambda: {"n": 0, "pnl": 0.0, "stake": 0.0, "wins": 0})
    bucket_factory = lambda: {"n": 0, "pnl": 0.0, "stake": 0.0, "wins": 0, "pushes": 0, "losses": 0}
    by_match_type = defaultdict(bucket_factory)
    by_primary_direction = defaultdict(bucket_factory)
    by_confidence = defaultdict(bucket_factory)
    by_cohort = defaultdict(bucket_factory)

    def add_bucket(store, key, pnl, stake):
        b = store[key]
        b["n"] += 1
        b["pnl"] += pnl
        b["stake"] += stake
        b["wins"] += int(pnl > 0)
        b["pushes"] += int(pnl == 0)
        b["losses"] += int(pnl < 0)

    for row in rows:
        key = _bucket_line(row.get("entry_line"))
        b = by_line[key]
        pnl = float(row.get("pnl", 0) or 0)
        stake = float(row.get("stake", 0) or 0)
        b["n"] += 1
        b["pnl"] += pnl
        b["stake"] += stake
        b["wins"] += int(pnl > 0)
        meta = _entry_meta(row)
        for tag in meta["match_type"]:
            add_bucket(by_match_type, tag, pnl, stake)
        add_bucket(by_primary_direction, meta["primary_direction"], pnl, stake)
        add_bucket(by_confidence, _bucket_confidence(meta["confidence"]), pnl, stake)
        cohort = "OTHER"
        a_src = str(meta.get("a_source") or "").lower()
        tier = str(meta.get("capture_tier") or "").lower()
        if a_src == "strict":
            cohort = "A_strict"
        elif a_src == "relaxed":
            cohort = "A_relaxed"
        elif tier == "b_shadow":
            cohort = "B_shadow"
        add_bucket(by_cohort, cohort, pnl, stake)

    return {
        "generated_at": datetime.now().isoformat(),
        "sample_size": n,
        "sample_ready": n >= MIN_SAMPLE,
        "min_sample": MIN_SAMPLE,
        "wins": wins,
        "pushes": pushes,
        "losses": losses,
        "hit_rate_pct": round(wins / n * 100, 2) if n else 0.0,
        "total_staked": round(total_stake, 4),
        "total_pnl": round(total_pnl, 4),
        "roi_pct": round(total_pnl / total_stake * 100, 2) if total_stake else 0.0,
        "by_line": {
            k: {
                "n": v["n"],
                "wins": v["wins"],
                "hit_rate_pct": round(v["wins"] / v["n"] * 100, 2) if v["n"] else 0.0,
                "pnl": round(v["pnl"], 4),
                "roi_pct": round(v["pnl"] / v["stake"] * 100, 2) if v["stake"] else 0.0,
            }
            for k, v in sorted(by_line.items())
        },
        "by_match_type": {
            k: _bucket_summary(v)
            for k, v in sorted(by_match_type.items())
        },
        "by_primary_direction": {
            k: _bucket_summary(v)
            for k, v in sorted(by_primary_direction.items())
        },
        "by_confidence": {
            k: _bucket_summary(v)
            for k, v in sorted(by_confidence.items())
        },
        "by_cohort": {
            k: _bucket_summary(v)
            for k, v in sorted(by_cohort.items())
        },
        "decision": (
            "EVALUATE"
            if n >= MIN_SAMPLE
            else f"WAIT_SAMPLE_{n}/{MIN_SAMPLE}"
        ),
    }


def save_eval() -> dict:
    result = evaluate(load_v4_results())
    out = REPORT_DIR / "v4_strategy_eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(out), "result": result}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    result = save_eval() if args.save else {"result": evaluate(load_v4_results())}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
