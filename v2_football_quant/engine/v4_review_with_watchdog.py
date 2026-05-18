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
            capture_output=True, text=True, timeout=900,
            cwd=str(BASE_DIR), env=_env,
        )
        if result_val.returncode != 0:
            status = "PARTIAL_DONE"
            error_msg += f"validator err: {result_val.stderr[:100]}; "

        # Step 2: 归因分析
        result_att = subprocess.run(
            [sys.executable, "-u", str(BASE_DIR / "engine" / "v4_result_attribution.py"), "--date", args.date],
            capture_output=True, text=True, timeout=600,
            cwd=str(BASE_DIR), env=_env,
        )
        if result_att.returncode != 0:
            status = "PARTIAL_DONE"
            error_msg += f"attribution err: {result_att.stderr[:100]}; "

        # Step 3: 生成 structured JSON（从validation构建，覆盖A/B/C/SKIP全量）
        val_exists = validation_path.exists()
        if val_exists:
            result_struct = subprocess.run(
                [sys.executable, "-u", str(BASE_DIR / "engine" / "gen_structured.py"), "--date", args.date],
                capture_output=True, text=True, timeout=1200,
                cwd=str(BASE_DIR), env=_env,
            )
            if result_struct.returncode != 0:
                status = "PARTIAL_DONE"
                error_msg += f"gen_structured err: {result_struct.stderr[:200]}; "
            else:
                print(f"[PIPELINE] gen_structured OK: {result_struct.stdout.strip()[:200]}", flush=True)
        else:
            error_msg += "validation missing, cannot gen_structured; "

        # Step 4: renderer --mode full
        result_rend_full = subprocess.run(
            [sys.executable, "-u", str(BASE_DIR / "engine" / "v4_review_renderer.py"),
             "--date", args.date, "--mode", "full"],
            capture_output=True, text=True, timeout=120,
            cwd=str(BASE_DIR),
        )
        if result_rend_full.returncode != 0:
            status = "PARTIAL_DONE"
            error_msg += f"renderer_full err: {result_rend_full.stderr[:100]}; "
        else:
            print(f"[PIPELINE] renderer full OK", flush=True)

        # Step 5: renderer --mode qq
        result_rend_qq = subprocess.run(
            [sys.executable, "-u", str(BASE_DIR / "engine" / "v4_review_renderer.py"),
             "--date", args.date, "--mode", "qq"],
            capture_output=True, text=True, timeout=120,
            cwd=str(BASE_DIR),
        )
        if result_rend_qq.returncode != 0:
            status = "PARTIAL_DONE"
            error_msg += f"renderer_qq err: {result_rend_qq.stderr[:100]}; "
        else:
            print(f"[PIPELINE] renderer qq OK", flush=True)

        # Step 6: guard --mode full
        result_guard_full = subprocess.run(
            [sys.executable, "-u", str(BASE_DIR / "engine" / "v4_review_guard.py"),
             "--date", args.date, "--mode", "full"],
            capture_output=True, text=True, timeout=60,
            cwd=str(BASE_DIR),
        )
        if result_guard_full.returncode not in (0, 2):
            error_msg += f"guard_full err: {result_guard_full.stderr[:100]}; "
        print(f"[PIPELINE] guard full: {result_guard_full.stdout.strip()[:200]}", flush=True)

        # Step 7: guard --mode qq
        result_guard_qq = subprocess.run(
            [sys.executable, "-u", str(BASE_DIR / "engine" / "v4_review_guard.py"),
             "--date", args.date, "--mode", "qq"],
            capture_output=True, text=True, timeout=60,
            cwd=str(BASE_DIR),
        )
        if result_guard_qq.returncode not in (0, 2):
            error_msg += f"guard_qq err: {result_guard_qq.stderr[:100]}; "
        print(f"[PIPELINE] guard qq: {result_guard_qq.stdout.strip()[:200]}", flush=True)

        # Step 8: route marker (always allowed_to_push=false, waits for BOSS)
        _full_pass_path = STATUS_DIR / f"v4_review_guard_{key}.json"
        _guard_file_data = {}
        if _full_pass_path.exists():
            try:
                _guard_file_data = json.loads(_full_pass_path.read_text())
            except Exception:
                pass
        _full_pass = _guard_file_data.get("guard_status") == "PASS" if _guard_file_data.get("mode") == "full" else False
        _qq_pass = _guard_file_data.get("guard_status") == "PASS" if _guard_file_data.get("mode") == "qq" else False
        _overall_pass = _full_pass and _qq_pass

        route = {
            "date": key,
            "reportagent_called": False,
            "reportagent_status": "PENDING",
            "full_guard": _full_pass,
            "qq_guard": _qq_pass,
            "allowed_to_push": False,
            "reason": "PENDING_SAFE_QQ_OUTBOUND + BOSS_CONFIRM" if _overall_pass else f"guard BLOCKER ({_guard_file_data.get('guard_status', 'UNKNOWN')})",
            "created_at": datetime.now(LOCAL_TZ).isoformat(),
        }
        route_path = STATUS_DIR / f"v4_review_route_{key}.json"
        with open(route_path, "w") as f:
            json.dump(route, f, ensure_ascii=False, indent=2)
        print(f"[PIPELINE] route marker: {_overall_pass} | allowed_to_push=False", flush=True)

        # Step 9: sent marker (never pushes automatically)
        import hashlib
        _qq_path = REPORT_DIR / f"v4_review_qq_{key}.txt"
        _hash = ""
        if _qq_path.exists():
            _hash = hashlib.md5(_qq_path.read_bytes()).hexdigest()
        _guard_label = "PASS" if _overall_pass else "BLOCKER"
        sent = {
            "date": key,
            "status": "NOT_SENT",
            "delivery_result": "not_executed",
            "pushed": False,
            "reason": f"guard {_guard_label}, allowed_to_push=False, waiting BOSS confirm",
            "template_id": "v4_daily_review_qq_v1",
            "message_hash": _hash,
            "version": "qq_daily_v1.0",
            "qq_delivered": False,
            "created_at": datetime.now(LOCAL_TZ).isoformat(),
        }
        sent_path = STATUS_DIR / f"v4_review_push_{key}.json"
        with open(sent_path, "w") as f:
            json.dump(sent, f, ensure_ascii=False, indent=2)
        print(f"[PIPELINE] sent marker: pushed=False, hash={_hash[:12]}...", flush=True)

    except Exception as e:
        wd.finish(status="FAILED", error=str(e)[:200])
        raise


if __name__ == "__main__":
    main()
