#!/usr/bin/env python3
"""engine/v4_review_with_watchdog.py — V4复盘wrapper（watchdog保护）
============================================================
用法:
  python3 engine/v4_review_with_watchdog.py --date 20260514 --mode main
  python3 engine/v4_review_with_watchdog.py --date 20260514 --mode retry
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

LOCAL_TZ = timezone(timedelta(hours=8))
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
ARCHIVE_DIR = BASE_DIR / "data" / "v4_archive"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--mode", default="main", choices=["main", "retry"])
    args = parser.parse_args()

    from engine.task_watchdog import v4_review_watchdog

    wd = v4_review_watchdog()
    if not wd.acquire_lock():
        print("[WATCHDOG] V4复盘 已有实例运行，跳过", flush=True)
        return

    key = str(args.date).replace("-", "")
    validation_path = REPORT_DIR / f"v4_ht_recommend_validation_{key}.json"
    attribution_path = ARCHIVE_DIR / f"v4_result_attribution_{key}.jsonl"

    total_items = 0
    scout_path = REPORT_DIR / f"scout_v4_{key}.json"
    if scout_path.exists():
        try:
            scout = json.loads(scout_path.read_text())
            total_items = len(scout) if isinstance(scout, list) else len(scout.get("results", []))
        except Exception:
            pass

    wd.start(total_items=total_items)

    try:
        import subprocess
        status = "DONE"
        error_msg = ""

        # Step 1: 赛后验证
        result_val = subprocess.run(
            [sys.executable, "-u", str(BASE_DIR / "engine" / "v4_ht_result_validator.py"), "--date", args.date],
            capture_output=True, text=True, timeout=300,
            cwd=str(BASE_DIR),
        )
        if result_val.returncode != 0:
            status = "PARTIAL_DONE"
            error_msg += f"validator err: {result_val.stderr[:100]}; "

        # Step 2: 归因分析
        result_att = subprocess.run(
            [sys.executable, "-u", str(BASE_DIR / "engine" / "v4_result_attribution.py"), "--date", args.date],
            capture_output=True, text=True, timeout=300,
            cwd=str(BASE_DIR),
        )
        if result_att.returncode != 0:
            status = "PARTIAL_DONE"
            error_msg += f"attribution err: {result_att.stderr[:100]}; "

        output_files = {
            "validation": str(validation_path) if validation_path.exists() else None,
            "attribution": str(attribution_path) if attribution_path.exists() else None,
        }
        wd.finish(status=status, error=error_msg[:200] or None, output_files=output_files)

    except Exception as e:
        wd.finish(status="FAILED", error=str(e)[:200])
        raise


if __name__ == "__main__":
    main()
