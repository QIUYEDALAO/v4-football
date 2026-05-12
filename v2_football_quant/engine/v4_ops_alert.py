from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ALERT_DIR = BASE_DIR / "data" / "ops" / "alerts"
CAP_AUDIT_DIR = BASE_DIR / "data" / "capture_audit"


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def run_alerts(date_str: str) -> dict:
    key = _date_key(date_str)
    api = _load_json(CAP_AUDIT_DIR / f"v4_api_budget_audit_{key}.json", {})
    cap = _load_json(CAP_AUDIT_DIR / f"v4_live_capture_audit_{key}.json", {})

    alerts = []
    used = int(api.get("daily_calls_used", 0))
    hard = int(api.get("hard_limit", 75000))
    peak = int(api.get("peak_requests_per_minute", 0))
    if hard > 0 and used / hard >= 0.85:
        alerts.append({"level": "WARN", "rule": "budget_soft", "msg": f"API usage {used}/{hard}"})
    if peak >= 320:
        alerts.append({"level": "WARN", "rule": "rpm_warn", "msg": f"peak rpm {peak}"})
    if int(api.get("http_429_count", 0)) > 0:
        alerts.append({"level": "WARN", "rule": "http_429", "msg": f"429={api.get('http_429_count')}"})

    a_stats = cap.get("a_candidate_stats", {})
    if int(a_stats.get("a_source_breakdown", {}).get("strict", 0)) < 1:
        alerts.append({"level": "WARN", "rule": "a_strict_zero", "msg": "A_strict still zero"})
    if int((cap.get("watchlist_candidates") or 0)) == 0:
        alerts.append({"level": "INFO", "rule": "watchlist_empty", "msg": "watchlist empty"})

    out = {
        "date": key,
        "generated_at": datetime.now().isoformat(),
        "alert_count": len(alerts),
        "alerts": alerts,
    }
    out_path = ALERT_DIR / f"ops_alerts_{key}.jsonl"
    for a in alerts:
        _append_jsonl(out_path, {"date": key, "ts": datetime.now().isoformat(), **a})
    out["alerts_path"] = str(out_path)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    args = parser.parse_args()
    print(json.dumps(run_alerts(args.date), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
