#!/usr/bin/env python3
"""engine/v4_progress_reporter.py — V4扫描进度独立报告
======================================================
只读 task_status，不读 scout/比赛/推荐。
每3-5分钟由 cron 触发一次。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
LOCAL_TZ = timezone(timedelta(hours=8))

WINDOWS = ["early", "midday", "evening", "night", "late"]


def main():
    for window in WINDOWS:
        path = STATUS_DIR / f"task_status_v4_scan_{window}.json"
        if not path.exists():
            continue
        try:
            s = json.loads(path.read_text())
        except Exception:
            continue

        status = s.get("status", "UNKNOWN")
        if status not in ("RUNNING", "DELAYED"):
            continue

        elapsed = s.get("elapsed_seconds", 0)
        p = s.get("progress", {})
        current = p.get("current", "?")
        total = p.get("total", "?")
        item = p.get("current_item", "-")
        api = s.get("api_usage", {}).get("calls_used_this_task", 0)

        print(f"【V4扫描进度】")
        print(f"窗口：{window}")
        print(f"状态：{status}")
        print(f"已运行：{elapsed // 60}分钟")
        print(f"进度：{current}/{total}")
        print(f"当前阶段：{item}")
        print(f"API调用：{api}")
        print(f"说明：{'继续等待' if status == 'RUNNING' else '已标记延迟'}")
        return

    # No active scan
    # print("[V4] 当前无进行中的扫描") — suppress to keep quiet


if __name__ == "__main__":
    main()
