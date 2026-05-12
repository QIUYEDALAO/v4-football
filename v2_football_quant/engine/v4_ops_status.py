from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OPS_DIR = BASE_DIR / "data" / "ops"
HEARTBEATS_DIR = OPS_DIR / "heartbeats"
JOB_RUNS_DIR = OPS_DIR / "job_runs"
EXEC_DIR = BASE_DIR / "data" / "execution"
SNAP_DIR = BASE_DIR / "data" / "live_odds_snapshots"
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"
OPS_RULES_PATH = BASE_DIR / "config" / "ops_alert_rules.yaml"

DEFAULT_STALE_THRESHOLDS = {
    "A_candidate_capture": 90,
    "B_shadow_capture": 150,
    "C_slice_capture": 360,
    "v4_budget_audit": 2400,
    "v4_capture_audit": 2400,
}


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _session_date(now: datetime | None = None) -> str:
    """午夜 00:00-05:59 默认回退到前一天，和采集器会话日期保持一致。"""
    if now is None:
        now = datetime.now()
    if now.hour < 6:
        now = now - timedelta(days=1)
    return now.strftime("%Y%m%d")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f)


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


def _available_keys() -> list[str]:
    keys = set()
    for p in MONITOR_DIR.glob("v4_capture_tasks_*.json"):
        k = p.stem.split("_")[-1]
        if len(k) == 8 and k.isdigit():
            keys.add(k)
    for p in SNAP_DIR.glob("*"):
        if p.is_dir() and len(p.name) == 8 and p.name.isdigit():
            keys.add(p.name)
    return sorted(keys)


def _resolve_key(requested_key: str) -> tuple[str, bool]:
    # Midnight safety: if today's files are empty/not started, auto fall back
    # to latest available date to keep ops dashboard useful.
    task_exists = (MONITOR_DIR / f"v4_capture_tasks_{requested_key}.json").exists()
    snap_exists = (SNAP_DIR / requested_key).exists()
    if task_exists or snap_exists:
        return requested_key, False
    keys = _available_keys()
    if not keys:
        return requested_key, False
    latest = keys[-1]
    if latest != requested_key:
        return latest, True
    return requested_key, False


def _load_stale_thresholds() -> dict:
    rules = _load_json(OPS_RULES_PATH, {})
    heartbeat = (rules or {}).get("heartbeat") or {}
    merged = dict(DEFAULT_STALE_THRESHOLDS)
    for key in list(merged.keys()):
        conf_key = f"{key}_stale_sec"
        if conf_key in heartbeat:
            try:
                merged[key] = int(heartbeat[conf_key])
            except Exception:
                pass
    return merged


def _sec_ago(ts: str) -> int | None:
    try:
        t = datetime.fromisoformat(ts)
    except Exception:
        return None
    return int((datetime.now(t.tzinfo) - t).total_seconds())


def build_status(date_str: str) -> dict:
    key = _date_key(date_str)
    resolved_key, fallback_used = _resolve_key(key)
    key = resolved_key
    task = _load_json(MONITOR_DIR / f"v4_capture_tasks_{key}.json", {})
    api = _load_json(BASE_DIR / "data" / "capture_audit" / f"v4_api_budget_audit_{key}.json", {})
    cap = _load_json(BASE_DIR / "data" / "capture_audit" / f"v4_live_capture_audit_{key}.json", {})

    stale_thresholds = _load_stale_thresholds()
    jobs = []
    stale_count = 0
    for hb_file in sorted(HEARTBEATS_DIR.glob("*.json")):
        hb = _load_json(hb_file, {})
        name = hb.get("job_name") or hb_file.stem
        status = hb.get("status") or "UNKNOWN"
        ts = hb.get("ts")
        ago = _sec_ago(ts) if ts else None
        threshold = stale_thresholds.get(name, 300)
        if status == "RUNNING" and ago is not None and ago > threshold:
            status = "STALE"
            stale_count += 1
        jobs.append({"job_name": name, "status": status, "last_heartbeat_sec_ago": ago, "threshold_sec": threshold})

    # Fallback: if heartbeat files are missing, use latest job_runs as status source.
    if not jobs:
        run_index = JOB_RUNS_DIR / f"job_runs_{key}.jsonl"
        run_rows = _read_jsonl(run_index)
        latest_by_job = {}
        for r in run_rows:
            name = str(r.get("job_name") or "")
            if not name:
                continue
            ts = str(r.get("ended_at") or r.get("started_at") or "")
            prev = latest_by_job.get(name)
            if prev is None or ts > str(prev.get("ended_at") or prev.get("started_at") or ""):
                latest_by_job[name] = r
        for name, r in sorted(latest_by_job.items()):
            status = str(r.get("status") or "UNKNOWN")
            jobs.append({
                "job_name": name,
                "status": status,
                "last_heartbeat_sec_ago": None,
                "threshold_sec": stale_thresholds.get(name, 300),
            })

    entered_monitoring = int(cap.get("entered_monitoring", 0) or 0)
    fixtures_with_ht_ou = int(cap.get("fixtures_with_ht_ou_normalized", 0) or 0)
    ht_ou_identified_pct = round(fixtures_with_ht_ou / entered_monitoring * 100, 2) if entered_monitoring else 0.0

    raw_rows_path = SNAP_DIR / key / "live_odds_raw.jsonl"
    raw_rows = _read_jsonl(raw_rows_path)
    tier_map_by_fixture = {}
    for t in task.get("tasks", []) if isinstance(task, dict) else []:
        fid = int(t.get("fixture_id") or 0)
        if fid:
            tier_map_by_fixture[fid] = str(t.get("tier") or "")
    by_tier_rows = {"A_candidate": 0, "B_shadow": 0, "C_slice": 0}
    for r in raw_rows:
        tier = str(r.get("capture_tier") or "")
        if not tier:
            fid = int(r.get("fixture_id") or 0)
            tier = tier_map_by_fixture.get(fid, "")
        if tier in by_tier_rows:
            by_tier_rows[tier] += 1

    task_counts = task.get("tier_counts", {}) if isinstance(task, dict) else {}
    task_progress = []
    for tier in ("A_candidate", "B_shadow", "C_slice"):
        planned = int(task_counts.get(tier, 0) or 0)
        # First stage target is 41 snapshots in 0-20m.
        expected_rows = planned * 41
        actual_rows = int(by_tier_rows.get(tier, 0))
        pct = round(actual_rows / expected_rows * 100, 2) if expected_rows else 0.0
        task_progress.append({
            "tier": tier,
            "planned_tasks": planned,
            "expected_rows": expected_rows,
            "actual_rows": actual_rows,
            "progress_pct": pct,
            "failed_tasks": 0,
        })

    run_index = JOB_RUNS_DIR / f"job_runs_{key}.jsonl"
    run_rows = _read_jsonl(run_index)
    duplicate_starts = 0
    for r in run_rows:
        if str(r.get("status")) == "BLOCKED" and str(r.get("error")) == "LOCK_EXISTS":
            duplicate_starts += 1

    out = {
        "date": key,
        "requested_date": _date_key(date_str),
        "resolved_date": key,
        "date_fallback_used": fallback_used,
        "generated_at": datetime.now().isoformat(),
        "jobs": jobs,
        "stale_jobs": stale_count,
        "api_used": api.get("daily_calls_used", 0),
        "api_limit": api.get("hard_limit", 75000),
        "http_429": api.get("http_429_count", 0),
        "raw_rows": len(raw_rows),
        "normalized_rows": _count_jsonl(SNAP_DIR / key / "live_odds_normalized.jsonl"),
        "missing_rows": _count_jsonl(SNAP_DIR / key / "live_market_missing.jsonl"),
        "tier_counts": task.get("tier_counts", {}),
        "a_breakdown": task.get("a_channel_breakdown", {}),
        "universe_total": int(task.get("universe_total", 0) or 0),
        "eligible_live_total": int(task.get("eligible_live_total", 0) or 0),
        "universe_files_used": task.get("universe_files_used", []),
        "universe_files_expected": task.get("universe_files_expected", []),
        "universe_files_missing": task.get("universe_files_missing", []),
        "excluded_reason_counts": task.get("excluded_reason_counts", {}),
        "ht_ou_identified_pct": ht_ou_identified_pct,
        "normalized_rows_per_ok_snapshot": float(cap.get("normalized_rows_per_ok_snapshot", 0.0) or 0.0),
        "ok_snapshot_with_normalized_pct": float(cap.get("ok_snapshot_with_normalized_pct", 0.0) or 0.0),
        "duplicate_cron_starts": duplicate_starts,
        "task_progress": task_progress,
    }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=_session_date())
    args = parser.parse_args()
    result = build_status(args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
