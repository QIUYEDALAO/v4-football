from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
V3_DIR = BASE_DIR / "data" / "v3_wc2026"
CONFIG_PATH = BASE_DIR / "config" / "v3_wc_config.json"


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


def _load_cfg() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _calc_clv_pct(entry_odds: float, close_odds: float) -> float:
    if entry_odds <= 0 or close_odds <= 0:
        return 0.0
    # Better price is larger odds for back position.
    return (entry_odds / close_odds - 1.0) * 100.0


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"bets": 0, "avg_true_clv_pct": 0.0, "positive_rate_pct": 0.0}
    clvs = [_to_float(r.get("clv_pct")) for r in rows]
    pos = sum(1 for x in clvs if x > 0)
    return {
        "bets": len(rows),
        "avg_true_clv_pct": round(sum(clvs) / len(clvs), 4),
        "positive_rate_pct": round(pos / len(clvs) * 100.0, 2),
    }


def run_audit(date_key: str) -> dict[str, Any]:
    V3_DIR.mkdir(parents=True, exist_ok=True)
    results_path = V3_DIR / "v3_paper_results.jsonl"
    rows = _load_jsonl(results_path)

    normalized = []
    for r in rows:
        x = dict(r)
        stage = str(x.get("wc_stage") or "").upper()
        entry = _to_float(x.get("entry_odds"), 0.0)
        close = _to_float(x.get("close_odds"), 0.0)
        clv = _to_float(x.get("clv_pct"), None)
        if clv is None:
            clv = _calc_clv_pct(entry, close)
        x["wc_stage"] = stage or "UNKNOWN_STAGE"
        x["clv_pct"] = round(clv, 4)
        normalized.append(x)

    md1 = [x for x in normalized if x.get("wc_stage") == "MD1"]
    md2 = [x for x in normalized if x.get("wc_stage") == "MD2"]
    md2_last10 = md2[-10:] if len(md2) >= 10 else md2

    md1_comp_values = [_to_float(x.get("data_completeness_pct"), 0.0) for x in md1]
    md1_comp_avg = round(sum(md1_comp_values) / len(md1_comp_values), 2) if md1_comp_values else 0.0
    cfg = _load_cfg()
    min_comp = _to_float(((cfg.get("md1_gate") or {}).get("min_data_completeness_pct")), 90.0)

    out = {
        "date": date_key,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source_path": str(results_path),
        "total_bets": len(normalized),
        "MD1_stats": _summarize(md1),
        "MD2_stats": _summarize(md2),
        "MD2_rolling_10": _summarize(md2_last10),
        "MD1_data_completeness_pct": md1_comp_avg,
    }
    out["micro_gate"] = {
        "md1_bets_ge_10": out["MD1_stats"]["bets"] >= 10,
        "md1_clv_ge_0": out["MD1_stats"]["avg_true_clv_pct"] >= 0.0,
        "md1_data_completeness_ge_90": md1_comp_avg >= min_comp,
        "status": "PASS"
        if (
            out["MD1_stats"]["bets"] >= 10
            and out["MD1_stats"]["avg_true_clv_pct"] >= 0.0
            and md1_comp_avg >= min_comp
        )
        else "BLOCK",
    }

    out_path = V3_DIR / "v3_clv_audit.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    out["output_path"] = str(out_path)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="V3 CLV audit")
    ap.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    args = ap.parse_args()
    result = run_audit(args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
