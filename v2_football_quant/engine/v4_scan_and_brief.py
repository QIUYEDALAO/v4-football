#!/usr/bin/env python3
"""engine/v4_scan_and_brief.py — V4 唯一推送入口（含watchdog+内容守卫）
============================================================
QQ Bot 只输出 V4 HT简报（A/B/C/SKIP），禁止旧口径(SecondHalf/FullTime/market_scores)。
"""

from __future__ import annotations

import argparse
import sys
import time
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

REPORT_DIR = BASE_DIR / "data" / "daily_reports"
LOG_DIR = BASE_DIR / "data" / "runtime" / "logs"
LOCAL_TZ = timezone(timedelta(hours=8))

FORBIDDEN_KEYWORDS = [
    "SECOND_HALF_OVER", "FULLTIME_OVER", "market_scores",
    "球探扫描结果", "高评分", "全场大球", "下半场大球", "V33",
]
REQUIRED_KEYWORDS = [
    "A级上半场强推荐", "B级上半场达标推荐", "C级观察池",
    "HT_SKIP跳过", "无A/B上半场主推荐",
]


def _content_guard(text: str) -> bool:
    """内容守卫：只要包含禁止关键词，直接 BLOCK"""
    for kw in FORBIDDEN_KEYWORDS:
        if kw in text:
            print(f"[GUARD] BLOCKED: 简报包含禁止关键词 '{kw}'", flush=True)
            return False
    has_required = any(kw in text for kw in REQUIRED_KEYWORDS)
    if not has_required:
        print("[GUARD] BLOCKED: 简报缺少必需关键词", flush=True)
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--window", default="midday", choices=["midday","evening","night","late","early","manual"])
    parser.add_argument("--lookahead-hours", type=float, default=24.0)
    parser.add_argument("--push", default="always", choices=["always","conditional","never"])
    parser.add_argument("--scan-mode", default="fast", choices=["fast","full"])
    args = parser.parse_args()

    from engine.task_watchdog import v4_scan_watchdog
    from engine.v4_runner import run_v4_scan

    wd = v4_scan_watchdog(args.window)
    if not wd.acquire_lock():
        return

    now = datetime.now(LOCAL_TZ)
    wd.start(total_items=0)

    # 扫描日志重定向
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today_key = str(args.date).replace("-", "")
    log_path = LOG_DIR / f"v4_scan_{args.window}_{today_key}.log"
    log_fh = open(str(log_path), "w")
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = log_fh
    sys.stderr = log_fh

    try:
        result = run_v4_scan(
            run_tag=f"V4_{args.window.upper()}",
            lookahead_hours=args.lookahead_hours,
            scan_mode=args.scan_mode,
            recent_prewarm="off",
            scan_date=args.date,
            use_watchdog=False,
        )

        sys.stdout = old_stdout
        sys.stderr = old_stderr
        log_fh.close()

        if result.get("skipped"):
            wd.finish(status="SKIPPED_OVERLAP")
            return

        scout_path = REPORT_DIR / f"scout_v4_{today_key}.json"
        scout_ok = scout_path.exists() and scout_path.stat().st_size > 0 and \
                   datetime.fromtimestamp(scout_path.stat().st_mtime, tz=LOCAL_TZ) >= now

        if not scout_ok:
            wd.finish(status="FAILED", error="scout校验失败")
            return

        from engine.v4_openclaw_brief import build_brief
        brief_text = build_brief(args.date)
        brief_path = REPORT_DIR / f"v4_openclaw_brief_{today_key}.txt"
        brief_path.write_text(brief_text, encoding="utf-8")

        if not _content_guard(brief_text):
            wd.finish(status="FAILED", error="内容守卫拦截")
            return

        # push 逻辑
        if args.push == "never":
            print("[WATCHDOG] brief generated, push skipped (never)", flush=True)
        elif args.push == "conditional":
            should_push = False
            ab_count = brief_text.count("A级上半场强推荐") + brief_text.count("B级上半场达标推荐")
            if ab_count > 0 or brief_text.count("今日 V4 有 ") > 0:
                should_push = True
            if not should_push:
                print("[WATCHDOG] brief generated, push skipped by conditional rule", flush=True)
            else:
                print(brief_text, flush=True)
        else:
            print(brief_text, flush=True)

        wd.finish(status="DONE", output_files={
            "scout": str(scout_path), "brief": str(brief_path), "scan_log": str(log_path),
        })

    except Exception as e:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        log_fh.close()
        wd.finish(status="FAILED", error=str(e)[:200])
        raise


if __name__ == "__main__":
    main()
