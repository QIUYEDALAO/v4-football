from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
SNAP_DIR = BASE_DIR / "data" / "live_odds_snapshots"
AUDIT_DIR = BASE_DIR / "data" / "capture_audit"
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"


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


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def build_audit(date_str: str) -> dict:
    key = _date_key(date_str)
    watchlist = _load_json(REPORT_DIR / f"live_watchlist_{key}.json", [])
    watch_ids = {int(x.get("fixture_id")) for x in watchlist if x.get("fixture_id")}
    task_file = MONITOR_DIR / f"v4_capture_tasks_{key}.json"
    tasks_obj = _load_json(task_file, {})
    tasks = tasks_obj.get("tasks", []) if isinstance(tasks_obj, dict) else []

    day_dir = SNAP_DIR / key
    raw_rows = _load_jsonl(day_dir / "live_odds_raw.jsonl")
    norm_rows = _load_jsonl(day_dir / "live_odds_normalized.jsonl")
    miss_rows = _load_jsonl(day_dir / "live_market_missing.jsonl")

    raw_by_fixture = defaultdict(int)
    live_ok_fixtures = set()
    raw_ok_rows = 0
    raw_ok_snapshots = set()
    for r in raw_rows:
        fid = r.get("fixture_id")
        if not fid:
            continue
        raw_by_fixture[int(fid)] += 1
        if r.get("capture_status") == "OK":
            live_ok_fixtures.add(int(fid))
            raw_ok_rows += 1
            snap = r.get("snapshot_utc")
            if snap:
                raw_ok_snapshots.add((int(fid), str(snap)))

    norm_by_fixture = defaultdict(int)
    lines_counter = Counter()
    norm_snapshots = set()
    for r in norm_rows:
        fid = r.get("fixture_id")
        if fid:
            norm_by_fixture[int(fid)] += 1
            snap = r.get("snapshot_utc")
            if snap:
                norm_snapshots.add((int(fid), str(snap)))
        try:
            lines_counter[str(float(r.get("line")))] += 1
        except Exception:
            pass

    miss_counter = Counter((r.get("missing_reason") or "UNKNOWN") for r in miss_rows)

    monitored = len(live_ok_fixtures)
    watch_count = len(watch_ids)
    monitor_coverage = round(monitored / watch_count * 100, 2) if watch_count else 0.0

    expected_per_fixture = 41
    completeness = []
    for fid in sorted(live_ok_fixtures):
        got = raw_by_fixture.get(fid, 0)
        completeness.append(got / expected_per_fixture * 100)
    avg_completeness = round(sum(completeness) / len(completeness), 2) if completeness else 0.0

    only_ft_like = 0
    for fid in live_ok_fixtures:
        if norm_by_fixture.get(fid, 0) == 0 and raw_by_fixture.get(fid, 0) > 0:
            only_ft_like += 1

    a_tasks = [x for x in tasks if x.get("tier") == "A_candidate"]
    a_source_counts = Counter(str(x.get("a_source") or "unknown") for x in a_tasks)
    a_fixture_ids = {int(x.get("fixture_id")) for x in a_tasks if x.get("fixture_id")}
    a_live_covered = len(a_fixture_ids & live_ok_fixtures)
    a_coverage_pct = round(a_live_covered / len(a_fixture_ids) * 100, 2) if a_fixture_ids else 0.0

    out = {
        "date": key,
        "generated_at": datetime.now().isoformat(),
        "watchlist_candidates": watch_count,
        "entered_monitoring": monitored,
        "monitor_coverage_pct": monitor_coverage,
        "avg_raw_snapshots_per_monitored_fixture": round(sum(raw_by_fixture[fid] for fid in live_ok_fixtures) / monitored, 2) if monitored else 0.0,
        "expected_snapshots_per_fixture_0_20": expected_per_fixture,
        "avg_snapshot_completeness_pct": avg_completeness,
        "fixtures_with_ht_ou_normalized": len([1 for fid in live_ok_fixtures if norm_by_fixture.get(fid, 0) > 0]),
        "raw_ok_rows": raw_ok_rows,
        "normalized_rows_per_ok_snapshot": round(len(norm_rows) / raw_ok_rows, 4) if raw_ok_rows else 0.0,
        "ok_snapshot_with_normalized_pct": round(len(raw_ok_snapshots & norm_snapshots) / len(raw_ok_snapshots) * 100, 2) if raw_ok_snapshots else 0.0,
        "fixtures_without_ht_ou": only_ft_like,
        "normalized_rows": len(norm_rows),
        "missing_rows": len(miss_rows),
        "line_distribution": dict(lines_counter),
        "missing_reason_top": miss_counter.most_common(10),
        "a_candidate_stats": {
            "a_task_count": len(a_tasks),
            "a_source_breakdown": dict(a_source_counts),
            "a_fixture_count": len(a_fixture_ids),
            "a_live_covered": a_live_covered,
            "a_live_coverage_pct": a_coverage_pct,
        },
        "task_file": str(task_file),
        "raw_path": str(day_dir / "live_odds_raw.jsonl"),
        "normalized_path": str(day_dir / "live_odds_normalized.jsonl"),
        "missing_path": str(day_dir / "live_market_missing.jsonl"),
    }

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AUDIT_DIR / f"v4_live_capture_audit_{key}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    out["audit_path"] = str(out_path)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=_session_date(), help="YYYYMMDD 或 YYYY-MM-DD")
    args = parser.parse_args()

    result = build_audit(args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
