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
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

LOCAL_TZ = timezone(timedelta(hours=8))
REPORT_DIR = BASE_DIR / "data" / "daily_reports"
ARCHIVE_DIR = BASE_DIR / "data" / "v4_archive"
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"


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

        # 显式继承环境变量（确保子进程能获取 API Key）
        _env = os.environ.copy()
        # 兼容：如果只有 OPENCLAW_APIFOOTBALL_KEY，注入 APIFOOTBALL_KEY
        if "APIFOOTBALL_KEY" not in _env and "OPENCLAW_APIFOOTBALL_KEY" in _env:
            _env["APIFOOTBALL_KEY"] = _env["OPENCLAW_APIFOOTBALL_KEY"]

        # Step 1: 赛后验证
        result_val = subprocess.run(
            [sys.executable, "-u", str(BASE_DIR / "engine" / "v4_ht_result_validator.py"), "--date", args.date],
            capture_output=True, text=True, timeout=300,
            cwd=str(BASE_DIR), env=_env,
        )
        if result_val.returncode != 0:
            status = "PARTIAL_DONE"
            error_msg += f"validator err: {result_val.stderr[:100]}; "

        # Step 2: 归因分析
        result_att = subprocess.run(
            [sys.executable, "-u", str(BASE_DIR / "engine" / "v4_result_attribution.py"), "--date", args.date],
            capture_output=True, text=True, timeout=300,
            cwd=str(BASE_DIR), env=_env,
        )
        if result_att.returncode != 0:
            status = "PARTIAL_DONE"
            error_msg += f"attribution err: {result_att.stderr[:100]}; "

        # ── API Key 可用性检查 ──
        _has_api_key = bool(os.environ.get("APIFOOTBALL_KEY") or os.environ.get("OPENCLAW_APIFOOTBALL_KEY"))
        # 检查 validation 结果中是否有实际数据
        _val_data_available = False
        if validation_path.exists():
            try:
                _val = json.loads(validation_path.read_text())
                _pending = _val.get("pending_matches", 0)
                _total = _val.get("total_matches", 0)
                _val_data_available = (_total - _pending) > 0
            except Exception:
                pass

        # ── 细分状态 ──
        _review_exists = (REPORT_DIR / f"v4_review_{key}.txt").exists()
        _qq_exists = (REPORT_DIR / f"v4_review_qq_{key}.txt").exists()
        _guard_full = (STATUS_DIR / f"v4_review_guard_full_{key}.json").exists()
        _guard_qq = (STATUS_DIR / f"v4_review_guard_qq_{key}.json").exists()

        _validation_status = "DONE" if validation_path.exists() else "FAILED"
        _attribution_status = "DONE" if attribution_path.exists() else "FAILED"

        if not _has_api_key:
            _validation_status = "API_NO_KEY"
            _attribution_status = "API_NO_KEY"
            _readiness_status = "REVIEW_STATUS_UNVERIFIED"
            _renderer_status = "SKIPPED_API_UNVERIFIED"
        elif not _val_data_available:
            _readiness_status = "REVIEW_NOT_READY"
            _renderer_status = "SKIPPED_NOT_READY"
        else:
            _readiness_status = "FIXTURES_AVAILABLE"
            _renderer_status = "PENDING" if not _review_exists else "DONE"

        _guard_status = "DONE" if _guard_qq else (_renderer_status if _renderer_status in ("SKIPPED_NOT_READY", "SKIPPED_API_UNVERIFIED") else "PENDING")
        _push_status = "DONE" if _guard_qq else (_renderer_status if _renderer_status in ("SKIPPED_NOT_READY", "SKIPPED_API_UNVERIFIED") else "PENDING")

        # 整体状态：不是简单 DONE
        if _readiness_status in ("REVIEW_STATUS_UNVERIFIED", "REVIEW_NOT_READY"):
            _overall_status = _readiness_status
        elif _guard_qq:
            _overall_status = "REVIEW_DONE"
        elif _qq_exists:
            _overall_status = "REVIEW_HALF_DONE"
        else:
            _overall_status = "REVIEW_PARTIAL"

        output_files = {
            "validation": str(validation_path) if validation_path.exists() else None,
            "attribution": str(attribution_path) if attribution_path.exists() else None,
            "review": str(REPORT_DIR / f"v4_review_{key}.txt") if _review_exists else None,
            "qq_review": str(REPORT_DIR / f"v4_review_qq_{key}.txt") if _qq_exists else None,
            "readiness": str(STATUS_DIR / f"v4_review_readiness_{key}.json") if (STATUS_DIR / f"v4_review_readiness_{key}.json").exists() else None,
        }
        wd.finish(status=_overall_status, error=error_msg[:200] or None, output_files=output_files)

        # ── stdout 摘要输出（供cron/agent读取，非AI总结）──
        print(f"【V4 情报系统】", flush=True)
        print(f"V4复盘阶段完成", flush=True)
        print(f"date={args.date}", flush=True)
        print(f"has_api_key={_has_api_key}", flush=True)
        print(f"val_data_available={_val_data_available}", flush=True)
        print(f"validation_status={_validation_status}", flush=True)
        print(f"attribution_status={_attribution_status}", flush=True)
        print(f"readiness_status={_readiness_status}", flush=True)
        print(f"renderer_status={_renderer_status}", flush=True)
        print(f"guard_status={_guard_status}", flush=True)
        print(f"push_status={_push_status}", flush=True)
        print(f"validation_file={output_files['validation'] or 'NOT_FOUND'}", flush=True)
        print(f"attribution_file={output_files['attribution'] or 'NOT_FOUND'}", flush=True)
        print(f"review_file={output_files['review'] or 'NOT_FOUND'}", flush=True)
        print(f"qq_file={output_files['qq_review'] or 'NOT_FOUND'}", flush=True)
        print(f"status={_overall_status}", flush=True)

    except Exception as e:
        wd.finish(status="FAILED", error=str(e)[:200])
        raise


if __name__ == "__main__":
    main()
