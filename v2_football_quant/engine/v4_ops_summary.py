from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from engine.v4_ops_alert import run_alerts
from engine.v4_ops_status import build_status
from engine.v4_validation_progress import build_progress
from engine.team_cn_unmapped_daily_report import run as run_team_unmapped_daily

OPS_DIR = BASE_DIR / "data" / "ops"
TASK_PROGRESS_DIR = OPS_DIR / "task_progress"
DAILY_SUMMARY_DIR = OPS_DIR / "daily_ops_summary"


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _session_date(now: datetime | None = None) -> str:
    """午夜 00:00-05:59 默认回退到前一天，和采集器会话日期保持一致。"""
    if now is None:
        now = datetime.now()
    if now.hour < 6:
        now = now - timedelta(days=1)
    return now.strftime("%Y%m%d")


def build_summary(date_str: str) -> dict:
    key = _date_key(date_str)
    month = key[:6]
    status = build_status(key)
    alerts = run_alerts(key)
    progress = build_progress(month)
    unmapped = run_team_unmapped_daily(key, update_map=True)

    task_progress = {
        "date": key,
        "generated_at": datetime.now().isoformat(),
        "task_progress": status.get("task_progress", []),
        "tier_counts": status.get("tier_counts", {}),
        "a_breakdown": status.get("a_breakdown", {}),
        "stale_jobs": status.get("stale_jobs", 0),
        "duplicate_cron_starts": status.get("duplicate_cron_starts", 0),
    }
    TASK_PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    task_path = TASK_PROGRESS_DIR / f"v4_task_progress_{key}.json"
    with open(task_path, "w", encoding="utf-8") as f:
        json.dump(task_progress, f, ensure_ascii=False, indent=2)

    summary = {
        "date": key,
        "generated_at": datetime.now().isoformat(),
        "api_used": status.get("api_used", 0),
        "api_limit": status.get("api_limit", 75000),
        "http_429": status.get("http_429", 0),
        "raw_rows": status.get("raw_rows", 0),
        "normalized_rows": status.get("normalized_rows", 0),
        "missing_rows": status.get("missing_rows", 0),
        "ht_ou_identified_pct": status.get("ht_ou_identified_pct", 0.0),
        "stale_jobs": status.get("stale_jobs", 0),
        "duplicate_cron_starts": status.get("duplicate_cron_starts", 0),
        "alerts": alerts.get("alerts", []),
        "validation_status": progress.get("status"),
        "validation_behind_items": progress.get("behind_items", []),
        "validation_days_to_deadline": progress.get("days_to_deadline"),
        "team_cn_unmapped_count": unmapped.get("unmapped_count", 0),
        "team_cn_unmapped_report_path": unmapped.get("report_path"),
        "team_cn_map_path": ((unmapped.get("map_update") or {}).get("map_path")),
        "task_progress_path": str(task_path),
    }
    DAILY_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = DAILY_SUMMARY_DIR / f"v4_daily_ops_summary_{key}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    summary["summary_path"] = str(summary_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=_session_date())
    args = parser.parse_args()
    print(json.dumps(build_summary(args.date), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
