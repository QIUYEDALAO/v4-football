#!/usr/bin/env python3
"""engine/v4_scan_worker.py — V4 扫描子进程
======================================
只负责扫描，不推送、不 watchdog。
允许被父进程 kill。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--window", default="midday")
    parser.add_argument("--lookahead-hours", type=float, default=24.0)
    parser.add_argument("--scan-mode", default="fast", choices=["fast", "full"])
    args = parser.parse_args()

    from engine.v4_runner import run_v4_scan

    result = run_v4_scan(
        run_tag=f"V4_{args.window.upper()}",
        lookahead_hours=args.lookahead_hours,
        scan_mode=args.scan_mode,
        recent_prewarm="off",
        scan_date=args.date,
        use_watchdog=False,
        generate_dashboard=False,
    )

    if result.get("skipped"):
        sys.exit(42)

    sys.exit(0)


if __name__ == "__main__":
    main()
