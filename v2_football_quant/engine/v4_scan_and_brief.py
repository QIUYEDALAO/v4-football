#!/usr/bin/env python3
"""engine/v4_scan_and_brief.py — V4扫描+简报一体化（含watchdog保护）
============================================================
QQ Bot 推送只输出 V4简报内容，不输出扫描日志/市场评分/旧口径。
"""

from __future__ import annotations

import argparse
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
        return  # 已有实例运行，静默跳过

    now = datetime.now(LOCAL_TZ)
    wd.start(total_items=0)

    try:
        # Step 1: 扫描
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
            return

        # Step 3: 生成简报
        from engine.v4_openclaw_brief import build_brief
        brief_text = build_brief(args.date)
        brief_path = REPORT_DIR / f"v4_openclaw_brief_{today_key}.txt"
        brief_path.parent.mkdir(parents=True, exist_ok=True)
        brief_path.write_text(brief_text, encoding="utf-8")

        # Step 4: 输出简报作为 QQ Bot 推送内容
        print(brief_text, flush=True)

        wd.finish(status="DONE", output_files={"scout": str(scout_path), "brief": str(brief_path)})

    except Exception as e:
        wd.finish(status="FAILED", error=str(e)[:200])
        raise


if __name__ == "__main__":
    main()
