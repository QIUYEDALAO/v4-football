#!/usr/bin/env python3
"""engine/v2_settle_with_watchdog.py — V2结算wrapper（watchdog保护）
============================================================
用法:
  python3 engine/v2_settle_with_watchdog.py --date 20260514 --mode main
  python3 engine/v2_settle_with_watchdog.py --date 20260514 --mode retry
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine.task_watchdog import v2_settle_watchdog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--mode", default="main", choices=["main", "retry"])
    args = parser.parse_args()

    wd = v2_settle_watchdog()
    if not wd.acquire_lock():
        print(f"[WATCHDOG] V2结算 已有实例运行，跳过", flush=True)
        return

    wd.start(total_items=0)

    try:
        from engine import paper_trading
        # paper_trading.py 的 verify_yesterday 直接跑
        old_argv = sys.argv
        sys.argv = ["paper_trading.py", "--verify-yesterday"]
        paper_trading.main()
        sys.argv = old_argv

        # 检查结算文件
        key = str(args.date).replace("-", "")
        verified_path = BASE_DIR / "data" / "paper_trading" / f"verified_{key}.json"
        if verified_path.exists() and verified_path.stat().st_size > 0:
            wd.finish(status="DONE", output_files={"verified": str(verified_path)})
        else:
            wd.finish(status="PARTIAL_DONE", error="verified文件缺失",
                      output_files={"verified": str(verified_path) if verified_path.exists() else None})
    except Exception as e:
        wd.finish(status="FAILED", error=str(e)[:200])
        raise


if __name__ == "__main__":
    main()
