from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"
SNAP_DIR = BASE_DIR / "data" / "live_odds_snapshots"
OUT_DIR = BASE_DIR / "data" / "capture_audit"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _read_jsonl(path: Path) -> list[dict]:
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


def build_report(date_key: str) -> dict:
    scout = _load_json(REPORT_DIR / f"scout_v4_{date_key}.json", [])
    tasks = _load_json(MONITOR_DIR / f"v4_capture_tasks_{date_key}.json", {})
    raw_rows = _read_jsonl(SNAP_DIR / date_key / "live_odds_raw.jsonl")
    norm_rows = _read_jsonl(SNAP_DIR / date_key / "live_odds_normalized.jsonl")
    miss_rows = _read_jsonl(SNAP_DIR / date_key / "live_market_missing.jsonl")

    counter = Counter()
    for row in scout if isinstance(scout, list) else []:
        factors = row.get("factors") or {}
        ms = row.get("market_scores") or {}
        pre_lines = row.get("ht_ou_lines") or []
        ht_score = float(ms.get("HT_LIVE_OVER") or 0.0)
        pullback_fit = str(factors.get("pullback_fit") or "WEAK").upper()
        early_only = bool(factors.get("early_only_flag", False))
        pressure = float((factors.get("time_bins") or {}).get("11_45") or 0.0)
        max_line = 0.0
        for ln in pre_lines:
            try:
                max_line = max(max_line, float((ln or {}).get("line")))
            except Exception:
                continue
        if row.get("market_focus") != "HT_LIVE_OVER":
            counter["market_focus_not_ht_live_over"] += 1
        if ht_score < 55:
            counter["ht_live_over_below_55"] += 1
        if max_line < 1.25:
            counter["prematch_ht_line_below_1_25"] += 1
        if pullback_fit not in ("STRONG", "OK"):
            counter["pullback_fit_weak"] += 1
        if early_only:
            counter["early_only_flag_true"] += 1
        if pressure < 0.5:
            counter["pressure_11_45_low"] += 1

    miss_reason = Counter((x.get("missing_reason") or "UNKNOWN") for x in miss_rows)
    for k, v in miss_reason.items():
        counter[f"missing_reason::{k}"] += v

    fixture_norm = {int(x.get("fixture_id")) for x in norm_rows if x.get("fixture_id")}
    fixture_raw = {int(x.get("fixture_id")) for x in raw_rows if x.get("fixture_id")}
    for fid in sorted(fixture_raw - fixture_norm):
        counter["live_has_raw_but_no_ht_line"] += 1

    out = {
        "date": date_key,
        "generated_at": datetime.now().isoformat(),
        "universe_total": int(tasks.get("universe_total", 0) or 0),
        "a_strict_v3": int((tasks.get("a_channel_breakdown") or {}).get("strict_candidates", 0) or 0),
        "a_relaxed": int((tasks.get("a_channel_breakdown") or {}).get("relaxed_candidates", 0) or 0),
        "b_shadow": int((tasks.get("tier_counts") or {}).get("B_shadow", 0) or 0),
        "c_slice": int((tasks.get("tier_counts") or {}).get("C_slice", 0) or 0),
        "ht_no_signal_reason_top": counter.most_common(20),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"ht_no_signal_diagnosis_{date_key}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    out["output_path"] = str(path)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    args = parser.parse_args()
    key = args.date.replace("-", "")
    print(json.dumps(build_report(key), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
