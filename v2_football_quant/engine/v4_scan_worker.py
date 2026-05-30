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
    parser.add_argument("--include-outside-57", action="store_true", help="扫描全部联赛（含白名单之外）")
    parser.add_argument("--fixture-universe", default="whitelist", choices=["whitelist", "all_eligible"],
                        help="Fixture universe mode")
    parser.add_argument("--collection-mode", default="official_legacy", choices=["official_legacy", "rf_lazy_shadow"])
    parser.add_argument("--max-fixtures", type=int, default=None)
    args = parser.parse_args()
    if args.max_fixtures is not None and int(args.max_fixtures) <= 0:
        parser.error("--max-fixtures must be a positive integer")

    from engine.v4_runner import run_v4_scan

    result = run_v4_scan(
        run_tag=f"V4_{args.window.upper()}",
        lookahead_hours=args.lookahead_hours,
        scan_mode=args.scan_mode,
        recent_prewarm="off",
        scan_date=args.date,
        use_watchdog=False,
        generate_dashboard=False,
        include_outside_57=args.include_outside_57,
        fixture_universe=args.fixture_universe,
        collection_mode=args.collection_mode,
        max_fixtures=args.max_fixtures,
    )

    if result is None:
        sys.exit(0)
    if isinstance(result, dict) and result.get("skipped"):
        sys.exit(42)

    sys.exit(0)


if __name__ == "__main__":
    main()
