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
        print("【V2 量化系统】", flush=True)
        print(f"[WATCHDOG] V2结算 已有实例运行，跳过", flush=True)
        return

    wd.start(total_items=0)

    try:
        from engine import paper_trading

        # 转换日期格式 20260514 → 2026-05-14
        date_str = str(args.date).replace("-", "")
        formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        paper_trading.verify_date(formatted_date)

        # 检查结算文件并判断 pending
        key = str(args.date).replace("-", "")
        verified_path = BASE_DIR / "data" / "paper_trading" / f"verified_{key}.json"
        if not verified_path.exists() or verified_path.stat().st_size == 0:
            wd.finish(status="PARTIAL_DONE", error="verified文件缺失",
                      output_files={"verified": str(verified_path) if verified_path.exists() else None})
        else:
            verified = json.loads(verified_path.read_text())
            pending = verified.get("pending", 0)
            total_completed = verified.get("total_completed", 0)
            total_predicted = verified.get("total_predicted", 0)
            if pending > 0:
                wd.finish(status="PARTIAL_DONE",
                          error=f"仍有 {pending} 场未结算",
                          output_files={"verified": str(verified_path)})
            elif total_completed == 0:
                wd.finish(status="PARTIAL_DONE", error="total_completed为0",
                          output_files={"verified": str(verified_path)})
            else:
                wd.finish(status="DONE", output_files={"verified": str(verified_path)})
    except Exception as e:
        wd.finish(status="FAILED", error=str(e)[:200])
        raise


if __name__ == "__main__":
    main()
