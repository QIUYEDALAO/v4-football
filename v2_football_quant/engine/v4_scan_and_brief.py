#!/usr/bin/env python3
"""engine/v4_scan_and_brief.py — V4扫描+简报一体化（含watchdog保护）
============================================================
替代 cron 直接调 v4_runner.py，提供：
1. 并发锁 2. heartbeat 3. scout校验 4. 自动触发简报 5. 超时保护

用法:
  python3 engine/v4_scan_and_brief.py --date 20260515 --window midday --lookahead-hours 24 --push always
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

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
LOCAL_TZ = timezone(timedelta(hours=8))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--window", default="midday", choices=["midday", "evening", "night", "late", "early", "manual"])
    parser.add_argument("--lookahead-hours", type=float, default=24.0)
    parser.add_argument("--push", default="always", choices=["always", "conditional", "never"])
    parser.add_argument("--scan-mode", default="fast", choices=["fast", "full"])
    args = parser.parse_args()

    from engine.task_watchdog import v4_scan_watchdog
    from engine.v4_runner import run_v4_scan

    wd = v4_scan_watchdog(args.window)
    if not wd.acquire_lock():
        print(f"[WATCHDOG] V4扫描-{args.window} 已有实例运行，跳过", flush=True)
        return

    now = datetime.now(LOCAL_TZ)
    wd.start(total_items=0)

    try:
        # Step 1: 扫描
        t0 = time.perf_counter()
        result = run_v4_scan(
            run_tag=f"V4_{args.window.upper()}",
            lookahead_hours=args.lookahead_hours,
            scan_mode=args.scan_mode,
            recent_prewarm="off",
            scan_date=args.date,
        )

        if result.get("skipped"):
            wd.finish(status="SKIPPED_OVERLAP", error="concurrent scan")
            return

        elapsed = time.perf_counter() - t0
        today_key = str(args.date).replace("-", "")

        # Step 2: 校验 scout 文件
        scout_path = REPORT_DIR / f"scout_v4_{today_key}.json"
        scout_ok = (
            scout_path.exists()
            and scout_path.stat().st_size > 0
            and datetime.fromtimestamp(scout_path.stat().st_mtime, tz=LOCAL_TZ) >= now
        )

        if not scout_ok:
            wd.finish(status="FAILED", error="scout文件校验失败")
            print(f"[WATCHDOG] V4扫描-{args.window} FAILED: scout校验失败", flush=True)
            return

        # Step 3: 触发简报
        if args.push == "never":
            wd.finish(status="DONE", output_files={"scout": str(scout_path)})
            return

        if args.push == "conditional" and elapsed > 600:
            wd.finish(status="DONE", output_files={"scout": str(scout_path)},
                      error="conditional skip: scan took too long")
            return

        from engine.v4_openclaw_brief import build_brief
        brief_text = build_brief(args.date)
        brief_path = REPORT_DIR / f"v4_openclaw_brief_{today_key}.txt"
        brief_path.parent.mkdir(parents=True, exist_ok=True)
        brief_path.write_text(brief_text, encoding="utf-8")
        print(f"[WATCHDOG] 简报已生成: {brief_path}", flush=True)

        wd.finish(
            status="DONE",
            output_files={"scout": str(scout_path), "brief": str(brief_path)},
        )

    except Exception as e:
        wd.finish(status="FAILED", error=str(e)[:200])
        print(f"[WATCHDOG] V4扫描-{args.window} FAILED: {e}", flush=True)
        raise


if __name__ == "__main__":
    main()
