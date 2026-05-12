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
SNAP_ROOT = BASE_DIR / "data" / "live_odds_snapshots"
JOB_RUNS_DIR = BASE_DIR / "data" / "ops" / "job_runs"

ALERT_RULE_CN = {
    "budget_soft": "API用量接近软上限",
    "budget_hard": "API用量接近硬上限",
    "rpm_warn": "每分钟请求速率预警",
    "rpm_critical": "每分钟请求速率严重超限",
    "http_429": "出现429限流错误",
    "cron_duplicate_start": "Cron重复触发（已被锁拦截）",
    "a_strict_zero": "A严格样本为0",
    "b_shadow_low": "B影子样本不足",
    "c_slice_low": "C切片样本不足",
    "ht_ou_identified_low": "HT O/U识别率过低",
    "raw_snapshot_completion_low": "原始快照完整率过低",
    "asian_line_coverage_low": "0.75/1.0/1.25亚洲线覆盖率过低",
    "missing_reason_unknown_high": "缺失原因UNKNOWN占比过高",
    "normalized_zero_minutes": "标准化数据连续为空",
    "normalized_stale_minutes": "标准化数据更新滞后",
    "watchlist_empty": "今日watchlist为空",
}


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

    # Cron duplicate starts: LOCK_EXISTS means repeated trigger while previous run not finished.
    runs_path = JOB_RUNS_DIR / f"job_runs_{key}.jsonl"
    dup_count = 0
    if runs_path.exists():
        with open(runs_path, encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if str(row.get("status")) == "BLOCKED" and str(row.get("error")) == "LOCK_EXISTS":
                    dup_count += 1
    if dup_count > 0:
        alerts.append({"level": "WARN", "rule": "cron_duplicate_start", "msg": f"LOCK_EXISTS blocked runs={dup_count}"})

    a_stats = cap.get("a_candidate_stats", {})
    min_a_strict = int(volume_rules.get("min_a_strict", 1))
    min_b_shadow = int(volume_rules.get("min_b_shadow", 80))
    min_c_slice = int(volume_rules.get("min_c_slice", 50))
    min_b_ratio = float(volume_rules.get("min_b_shadow_ratio_of_eligible", 0.0))
    min_c_ratio = float(volume_rules.get("min_c_slice_ratio_of_eligible", 0.0))
    strict_count = int(a_stats.get("a_source_breakdown", {}).get("strict", 0))
    if strict_count < min_a_strict:
        alerts.append({"level": "WARN", "rule": "a_strict_zero", "msg": "A_strict still zero"})

    tier_counts = task.get("tier_counts", {}) if isinstance(task, dict) else {}
    eligible_live_total = int(task.get("eligible_live_total", 0) or 0)
    b_shadow = int(tier_counts.get("B_shadow", 0))
    c_slice = int(tier_counts.get("C_slice", 0))
    effective_min_b = min_b_shadow
    effective_min_c = min_c_slice
    if eligible_live_total > 0 and min_b_ratio > 0:
        effective_min_b = min(effective_min_b, int(round(eligible_live_total * min_b_ratio)))
    if eligible_live_total > 0 and min_c_ratio > 0:
        effective_min_c = min(effective_min_c, int(round(eligible_live_total * min_c_ratio)))
    if b_shadow < effective_min_b:
        alerts.append({"level": "WARN", "rule": "b_shadow_low", "msg": f"B_shadow low: {b_shadow} < {effective_min_b} (eligible={eligible_live_total})"})
    if c_slice < effective_min_c:
        alerts.append({"level": "WARN", "rule": "c_slice_low", "msg": f"C_slice low: {c_slice} < {effective_min_c} (eligible={eligible_live_total})"})

    entered_monitoring = int(cap.get("entered_monitoring", 0) or 0)
    ht_ou_rows = int(cap.get("fixtures_with_ht_ou_normalized", 0) or 0)
    ht_ou_pct = (ht_ou_rows / entered_monitoring * 100.0) if entered_monitoring else 0.0
    ht_ou_min = float(quality_rules.get("ht_ou_identified_pct_min", 30))
    if ht_ou_pct < ht_ou_min:
        alerts.append({"level": "WARN", "rule": "ht_ou_identified_low", "msg": f"HT O/U identified {ht_ou_pct:.2f}% < {ht_ou_min:.2f}%"})

    raw_completion_min = float(quality_rules.get("raw_snapshot_completion_pct_min", 80))
    raw_completion = float(cap.get("avg_snapshot_completeness_pct", 0.0) or 0.0)
    if raw_completion < raw_completion_min:
        alerts.append({"level": "WARN", "rule": "raw_snapshot_completion_low", "msg": f"Raw completion {raw_completion:.2f}% < {raw_completion_min:.2f}%"})

    line_dist = cap.get("line_distribution", {}) if isinstance(cap, dict) else {}
    asian_hits = int(line_dist.get("0.75", 0)) + int(line_dist.get("1.0", 0)) + int(line_dist.get("1.25", 0))
    normalized_rows = int(cap.get("normalized_rows", 0) or 0)
    asian_pct = (asian_hits / normalized_rows * 100.0) if normalized_rows else 0.0
    asian_min = float(quality_rules.get("asian_line_coverage_pct_min", 20))
    if asian_pct < asian_min:
        alerts.append({"level": "WARN", "rule": "asian_line_coverage_low", "msg": f"Asian line coverage {asian_pct:.2f}% < {asian_min:.2f}%"})

    unknown_max = float(quality_rules.get("missing_reason_unknown_pct_max", 10))
    missing_rows = int(cap.get("missing_rows", 0) or 0)
    unknown_n = 0
    for item in cap.get("missing_reason_top", []) or []:
        if isinstance(item, list) and len(item) == 2 and str(item[0]).upper() == "UNKNOWN":
            unknown_n = int(item[1] or 0)
            break
    unknown_pct = (unknown_n / missing_rows * 100.0) if missing_rows else 0.0
    if unknown_pct > unknown_max:
        alerts.append({"level": "WARN", "rule": "missing_reason_unknown_high", "msg": f"UNKNOWN missing reason {unknown_pct:.2f}% > {unknown_max:.2f}%"})

    zero_norm_minutes = int(quality_rules.get("normalized_zero_minutes", 30))
    day_dir = SNAP_ROOT / key
    raw_path = day_dir / "live_odds_raw.jsonl"
    norm_path = day_dir / "live_odds_normalized.jsonl"
    if raw_path.exists():
        raw_mtime = raw_path.stat().st_mtime
        norm_mtime = norm_path.stat().st_mtime if norm_path.exists() else 0.0
        raw_rows = 0
        norm_rows = 0
        with open(raw_path, encoding="utf-8") as f:
            raw_rows = sum(1 for _ in f)
        if norm_path.exists():
            with open(norm_path, encoding="utf-8") as f:
                norm_rows = sum(1 for _ in f)
        if raw_rows > 0 and norm_rows == 0:
            minutes = int((datetime.now().timestamp() - raw_mtime) / 60)
            if minutes >= zero_norm_minutes:
                alerts.append({"level": "WARN", "rule": "normalized_zero_minutes", "msg": f"normalized rows still 0 for ~{minutes} minutes"})
        elif raw_rows > 0 and norm_rows > 0 and raw_mtime - norm_mtime >= zero_norm_minutes * 60:
            minutes = int((raw_mtime - norm_mtime) / 60)
            alerts.append({"level": "WARN", "rule": "normalized_stale_minutes", "msg": f"normalized not updated for ~{minutes} minutes while raw updates"})

    if int((cap.get("watchlist_candidates") or 0)) == 0:
        alerts.append({"level": "INFO", "rule": "watchlist_empty", "msg": "watchlist empty"})

    out = {
        "date": key,
        "generated_at": datetime.now().isoformat(),
        "alert_count": len(alerts),
        "alerts": alerts,
    }
    out_path = ALERT_DIR / f"ops_alerts_{key}.jsonl"
    alerts_cn = []
    for a in alerts:
        row = {
            "date": key,
            "ts": datetime.now().isoformat(),
            **a,
            "rule_cn": ALERT_RULE_CN.get(str(a.get("rule") or ""), "未定义规则说明"),
        }
        _append_jsonl(out_path, row)
        alerts_cn.append(row)
    out["alerts_path"] = str(out_path)
    out["alerts_cn"] = alerts_cn
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    args = parser.parse_args()
    print(json.dumps(run_alerts(args.date), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
