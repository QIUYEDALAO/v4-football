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
        print("【V4 情报系统】", flush=True)
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

        # ── 守卫：检查正式 brief 是否与 validation scope 一致 ──
        brief_path = REPORT_DIR / f"v4_openclaw_brief_{key}.txt"
        brief_a = 0
        brief_b = 0
        if brief_path.exists():
            brief_text = brief_path.read_text()
            import re
            a_match = re.search(r'A级.*?强推荐[：:]\s*(\d+)', brief_text)
            b_match = re.search(r'B级.*?达标推荐[：:]\s*(\d+)', brief_text)
            if a_match:
                brief_a = int(a_match.group(1))
            if b_match:
                brief_b = int(b_match.group(1))
            if brief_a == 0 and brief_b == 0:
                print(f"[GUARD] REVIEW_SCOPE_MISMATCH: brief A={brief_a} B={brief_b} — 无A/B主推荐，禁用validation全量样本生成命中率", flush=True)
                print(f"[GUARD] validation/attribution 仅作为正式样本赛果补充，不得决定样本范围", flush=True)
                print(f"[GUARD] 警告：请勿使用此日validation统计数据作为正式复盘命中率", flush=True)
        else:
            print(f"[GUARD] DATA_MISSING: 未找到正式 brief 文件 {brief_path}，无法生成命中率报告", flush=True)

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
            "review": str(REPORT_DIR / f"v4_review_{key}.txt") if (REPORT_DIR / f"v4_review_{key}.txt").exists() else None,
            "qq_review": str(REPORT_DIR / f"v4_review_qq_{key}.txt") if (REPORT_DIR / f"v4_review_qq_{key}.txt").exists() else None,
        }
        wd.finish(status=status, error=error_msg[:200] or None, output_files=output_files)

        # ── stdout 摘要输出（供cron/agent读取，非AI总结）──
        print(f"【V4 情报系统】", flush=True)
        print(f"V4复盘完成", flush=True)
        print(f"date={args.date}", flush=True)
        print(f"validation_file={output_files['validation'] or 'NOT_FOUND'}", flush=True)
        print(f"attribution_file={output_files['attribution'] or 'NOT_FOUND'}", flush=True)
        print(f"review_file={output_files['review'] or 'NOT_FOUND'}", flush=True)
        print(f"qq_file={output_files['qq_review'] or 'NOT_FOUND'}", flush=True)
        print(f"status={status}", flush=True)

    except Exception as e:
        wd.finish(status="FAILED", error=str(e)[:200])
        raise


if __name__ == "__main__":
    main()
