from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PAPER_DIR = BASE_DIR / "data" / "paper_trading"
REPORT_DIR = BASE_DIR / "data" / "daily_reports"


def _load(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _bucket(p: float) -> str:
    low = int(p * 100 // 5 * 5)
    high = min(100, low + 5)
    return f"{low}-{high}%"


def build_report() -> dict:
    rows = []
    for fp in sorted(PAPER_DIR.glob("v4_live_verified_*.json")):
        data = _load(fp, {})
        for r in data.get("results", []):
            raw = r.get("raw_entry") or {}
            conf = raw.get("confidence")
            if conf is None:
                continue
            pred = max(0.01, min(0.99, float(conf) / 100.0))
            actual = 1.0 if float(r.get("pnl", 0)) > 0 else 0.0
            rows.append((pred, actual))

    buckets: dict[str, dict] = {}
    for pred, actual in rows:
        key = _bucket(pred)
        b = buckets.setdefault(key, {"n": 0, "pred_sum": 0.0, "actual_sum": 0.0})
        b["n"] += 1
        b["pred_sum"] += pred
        b["actual_sum"] += actual

    table = []
    for k in sorted(buckets.keys(), key=lambda x: int(x.split("-")[0])):
        b = buckets[k]
        n = b["n"]
        pred_rate = b["pred_sum"] / n
        actual_rate = b["actual_sum"] / n
        table.append({
            "bucket": k,
            "samples": n,
            "predicted_hit_rate_pct": round(pred_rate * 100, 2),
            "actual_hit_rate_pct": round(actual_rate * 100, 2),
            "bias_pct": round((actual_rate - pred_rate) * 100, 2),
        })
    return {"sample_size": len(rows), "calibration_table": table}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.save:
        out = REPORT_DIR / "v4_calibration_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"path": str(out), "report": report}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

