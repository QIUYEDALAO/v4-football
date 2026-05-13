from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
V3_DIR = BASE_DIR / "data" / "v3_wc2026"

BUCKETS = [
    (0.50, 0.70),
    (0.70, 1.00),
    (1.00, 1.30),
    (1.30, 1.60),
    (1.60, 99.0),
]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _bucket_name(lo: float, hi: float) -> str:
    if hi >= 99:
        return f"{lo:.2f}+"
    return f"{lo:.2f}-{hi:.2f}"


def _pick_bucket(gap_abs: float) -> str | None:
    for lo, hi in BUCKETS:
        if lo <= gap_abs < hi:
            return _bucket_name(lo, hi)
    return None


def run_bucket_audit(date_key: str) -> dict[str, Any]:
    rows = _load_jsonl(V3_DIR / "v3_paper_results.jsonl")
    buckets: dict[str, dict[str, Any]] = {_bucket_name(lo, hi): {"n": 0, "not_lose": 0, "draw": 0, "favorite_win": 0, "clv_sum": 0.0} for lo, hi in BUCKETS}

    for r in rows:
        gap_abs = abs(_to_float(r.get("gap_abs"), abs(_to_float(r.get("gap"), 0.0))))
        b = _pick_bucket(gap_abs)
        if not b:
            continue
        x = buckets[b]
        x["n"] += 1
        x["clv_sum"] += _to_float(r.get("clv_pct"), 0.0)
        result = str(r.get("result_1x2") or "").upper()
        bubble_side = str(r.get("bubble_side") or "").upper()
        # favorite win == bubble side win
        if (bubble_side == "HOME" and result == "H") or (bubble_side == "AWAY" and result == "A"):
            x["favorite_win"] += 1
        if result == "D":
            x["draw"] += 1
            x["not_lose"] += 1
        elif (bubble_side == "HOME" and result == "A") or (bubble_side == "AWAY" and result == "H"):
            x["not_lose"] += 1

    out_rows = []
    for k, v in buckets.items():
        n = v["n"]
        out_rows.append(
            {
                "gap_bucket": k,
                "n": n,
                "not_lose_rate_pct": round(v["not_lose"] / n * 100, 2) if n else 0.0,
                "draw_rate_pct": round(v["draw"] / n * 100, 2) if n else 0.0,
                "favorite_win_rate_pct": round(v["favorite_win"] / n * 100, 2) if n else 0.0,
                "avg_clv_pct": round(v["clv_sum"] / n, 4) if n else 0.0,
            }
        )

    payload = {
        "date": date_key,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "rows": out_rows,
        "source": str(V3_DIR / "v3_paper_results.jsonl"),
    }
    out_path = V3_DIR / "v3_gap_bucket_audit.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    payload["output_path"] = str(out_path)
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="V3 gap bucket audit")
    ap.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    args = ap.parse_args()
    result = run_bucket_audit(args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

