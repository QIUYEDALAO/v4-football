from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ALERT_DIR = BASE_DIR / "data" / "ops" / "alerts"
CAP_AUDIT_DIR = BASE_DIR / "data" / "capture_audit"
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"
OPS_RULES_PATH = BASE_DIR / "config" / "ops_alert_rules.yaml"


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
    rules = _load_json(OPS_RULES_PATH, {})
    api_rules = (rules or {}).get("api_budget") or {}
    volume_rules = (rules or {}).get("task_volume") or {}
    quality_rules = (rules or {}).get("capture_quality") or {}

    api = _load_json(CAP_AUDIT_DIR / f"v4_api_budget_audit_{key}.json", {})
    cap = _load_json(CAP_AUDIT_DIR / f"v4_live_capture_audit_{key}.json", {})
    task = _load_json(MONITOR_DIR / f"v4_capture_tasks_{key}.json", {})

    alerts = []
    used = int(api.get("daily_calls_used", 0))
    hard = int(api.get("hard_limit", 75000))
    peak = int(api.get("peak_requests_per_minute", 0))
    soft_limit_pct = float(api_rules.get("soft_limit_pct", 85))
    hard_limit_pct = float(api_rules.get("hard_limit_pct", 95))
    rpm_warn = int(api_rules.get("rpm_warn", 320))
    rpm_critical = int(api_rules.get("rpm_critical", 380))
    http_429_warn = int(api_rules.get("http_429_warn", 1))
    if hard > 0 and used / hard >= soft_limit_pct / 100.0:
        alerts.append({"level": "WARN", "rule": "budget_soft", "msg": f"API usage {used}/{hard}"})
    if hard > 0 and used / hard >= hard_limit_pct / 100.0:
        alerts.append({"level": "CRITICAL", "rule": "budget_hard", "msg": f"API usage near hard limit {used}/{hard}"})
    if peak >= rpm_critical:
        alerts.append({"level": "CRITICAL", "rule": "rpm_critical", "msg": f"peak rpm {peak}"})
    elif peak >= rpm_warn:
        alerts.append({"level": "WARN", "rule": "rpm_warn", "msg": f"peak rpm {peak}"})
    if int(api.get("http_429_count", 0)) >= http_429_warn:
        alerts.append({"level": "WARN", "rule": "http_429", "msg": f"429={api.get('http_429_count')}"})

    a_stats = cap.get("a_candidate_stats", {})
    min_a_strict = int(volume_rules.get("min_a_strict", 1))
    min_b_shadow = int(volume_rules.get("min_b_shadow", 80))
    min_c_slice = int(volume_rules.get("min_c_slice", 50))
    strict_count = int(a_stats.get("a_source_breakdown", {}).get("strict", 0))
    if strict_count < min_a_strict:
        alerts.append({"level": "WARN", "rule": "a_strict_zero", "msg": "A_strict still zero"})

    tier_counts = task.get("tier_counts", {}) if isinstance(task, dict) else {}
    b_shadow = int(tier_counts.get("B_shadow", 0))
    c_slice = int(tier_counts.get("C_slice", 0))
    if b_shadow < min_b_shadow:
        alerts.append({"level": "WARN", "rule": "b_shadow_low", "msg": f"B_shadow low: {b_shadow} < {min_b_shadow}"})
    if c_slice < min_c_slice:
        alerts.append({"level": "WARN", "rule": "c_slice_low", "msg": f"C_slice low: {c_slice} < {min_c_slice}"})

    entered_monitoring = int(cap.get("entered_monitoring", 0) or 0)
    ht_ou_rows = int(cap.get("fixtures_with_ht_ou_normalized", 0) or 0)
    ht_ou_pct = (ht_ou_rows / entered_monitoring * 100.0) if entered_monitoring else 0.0
    ht_ou_min = float(quality_rules.get("ht_ou_identified_pct_min", 30))
    if ht_ou_pct < ht_ou_min:
        alerts.append({"level": "WARN", "rule": "ht_ou_identified_low", "msg": f"HT O/U identified {ht_ou_pct:.2f}% < {ht_ou_min:.2f}%"})

    line_dist = cap.get("line_distribution", {}) if isinstance(cap, dict) else {}
    asian_hits = int(line_dist.get("0.75", 0)) + int(line_dist.get("1.0", 0)) + int(line_dist.get("1.25", 0))
    normalized_rows = int(cap.get("normalized_rows", 0) or 0)
    asian_pct = (asian_hits / normalized_rows * 100.0) if normalized_rows else 0.0
    asian_min = float(quality_rules.get("asian_line_coverage_pct_min", 20))
    if asian_pct < asian_min:
        alerts.append({"level": "WARN", "rule": "asian_line_coverage_low", "msg": f"Asian line coverage {asian_pct:.2f}% < {asian_min:.2f}%"})

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
