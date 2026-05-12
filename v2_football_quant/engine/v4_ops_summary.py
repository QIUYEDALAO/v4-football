from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from engine.v4_ops_alert import run_alerts
from engine.v4_ops_status import build_status
from engine.v4_validation_progress import build_progress

OPS_DIR = BASE_DIR / "data" / "ops"
TASK_PROGRESS_DIR = OPS_DIR / "task_progress"
DAILY_SUMMARY_DIR = OPS_DIR / "daily_ops_summary"


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def build_summary(date_str: str) -> dict:
    key = _date_key(date_str)
    month = key[:6]
    status = build_status(key)
    alerts = run_alerts(key)
    progress = build_progress(month)

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
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    args = parser.parse_args()
    print(json.dumps(build_summary(args.date), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
