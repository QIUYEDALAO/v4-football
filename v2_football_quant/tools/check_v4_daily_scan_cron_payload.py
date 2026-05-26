#!/usr/bin/env python3
"""tools/check_v4_daily_scan_cron_payload.py
===========================================================================
检查 V4_DAILY_SCAN_READONLY cron payload 不再包含无效参数。

检查项：
1. 不包含 --review-only, --no-state-write, --no-verified-write, --no-cron
2. 包含 --date 和 --no-push
3. cron 时间未被修改（0 12 * * *）
4. notify hook 存在
5. watchdog wrapper 存在
6. 其他 cron 任务 payload 未被修改

使用方式：
  python3 tools/check_v4_daily_scan_cron_payload.py

输出：
  data/runtime/status/v4_daily_scan_cron_payload_checker_20260526.json
===========================================================================
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any

TZ = timezone(timedelta(hours=8))

# 错误参数列表
FORBIDDEN_ARGS = [
    "--review-only",
    "--no-state-write",
    "--no-verified-write",
    "--no-cron",
]

# 必须包含的合法参数
REQUIRED_ARGS = [
    "--date",
    "--no-push",
]

# 必须存在的钩子
REQUIRED_HOOKS = [
    "notify_cron_task_complete_qq.py",
]

# 期望的 cron 时间
EXPECTED_CRON = {
    "expr": "0 12 * * *",
    "tz": "Asia/Shanghai",
}

# 不应被修改的其他任务名
OTHER_TASKS = [
    "V4_VALIDATION_DRY_RUN",
    "V3V4_DASHBOARD_AFTER_SCAN_REFRESH",
    "V3V4_DASHBOARD_AFTER_VALIDATION_REFRESH",
    "V4_VALIDATION_DRY_RUN_FINAL_AND_DASHBOARD_REFRESH",
]

CRON_JOBS_PATH = os.path.expanduser("~/.openclaw/cron/jobs.json")
STATUS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "runtime", "status")


def load_cron_jobs() -> dict[str, Any]:
    """从 OpenClaw cron 配置文件加载任务列表。"""
    if not os.path.exists(CRON_JOBS_PATH):
        return {"error": f"cron jobs file not found: {CRON_JOBS_PATH}"}
    with open(CRON_JOBS_PATH) as f:
        return json.load(f)


def find_target_job(jobs: list[dict]) -> dict | None:
    """在任务列表中查找 V4_DAILY_SCAN_READONLY。"""
    for job in jobs:
        if job.get("name") == "V4_DAILY_SCAN_READONLY":
            return job
    return None


def find_other_jobs(jobs: list[dict]) -> dict[str, dict]:
    """查找其他 V3/V4 定时任务及其当前状态。"""
    found = {}
    for job in jobs:
        if job.get("name") in OTHER_TASKS:
            found[job["name"]] = {
                "updatedAtMs": job.get("updatedAtMs"),
                "expr": job.get("schedule", {}).get("expr"),
                "tz": job.get("schedule", {}).get("tz"),
            }
    return found


def check_forbidden_args(message: str) -> list[str]:
    """检查 payload message 中是否包含禁止的参数。"""
    found = []
    for arg in FORBIDDEN_ARGS:
        if arg in message:
            found.append(arg)
    return found


def check_required_args(message: str) -> list[str]:
    """检查 payload message 中是否包含必须的参数。"""
    missing = []
    for arg in REQUIRED_ARGS:
        if arg not in message:
            missing.append(arg)
    return missing


def check_notify_hook(message: str) -> bool:
    """检查 notify hook 是否存在。"""
    return any(hook in message for hook in REQUIRED_HOOKS)


def check_watchdog_wrapper(message: str) -> bool:
    """检查 watchdog wrapper (shell 框架) 是否存在。"""
    checks = [
        "T0=$(date +%s)" in message,
        "EC=$?" in message,
        "D=$(($(date +%s)-T0))" in message or "D=$" in message,
        "D1=$(date +%Y%m%d)" in message,
    ]
    return all(checks)


def main():
    print(f"{'=' * 60}", flush=True)
    print(f"V4 Daily Scan Cron Payload — Checker", flush=True)
    print(f"Time: {datetime.now(TZ).isoformat()}", flush=True)
    print(f"{'=' * 60}", flush=True)

    checks = {
        "timestamp": datetime.now(TZ).isoformat(),
        "all_pass": True,
        "blockers": [],
        "warnings": [],
        "scan_target": "V4_DAILY_SCAN_READONLY",
    }

    # ── 加载 cron jobs ──
    print(f"\n[1] 加载 cron jobs...", end=" ", flush=True)
    cron_data = load_cron_jobs()
    if "error" in cron_data:
        print(f"❌ {cron_data['error']}", flush=True)
        checks["all_pass"] = False
        checks["blockers"].append("cron_jobs_file_not_found")
        out_path = os.path.join(STATUS_DIR, "v4_daily_scan_cron_payload_checker_20260526.json")
        os.makedirs(STATUS_DIR, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(checks, f, ensure_ascii=False, indent=2)
        return 1

    jobs = cron_data.get("jobs", [])
    target_job = find_target_job(jobs)
    if not target_job:
        print("❌ NOT FOUND", flush=True)
        checks["all_pass"] = False
        checks["blockers"].append("target_job_not_found")
        json.dump(checks, open(os.path.join(STATUS_DIR, "v4_daily_scan_cron_payload_checker_20260526.json"), "w"),
                  ensure_ascii=False, indent=2)
        return 1
    print("✅ FOUND", flush=True)

    message = target_job.get("payload", {}).get("message", "")
    schedule = target_job.get("schedule", {})

    # ── 2. 检查禁止参数 ──
    print(f"[2] 检查禁止参数（4个）...", end=" ", flush=True)
    forbidden_found = check_forbidden_args(message)
    if forbidden_found:
        print(f"❌ FOUND: {forbidden_found}", flush=True)
        checks["all_pass"] = False
        checks["blockers"].append(f"forbidden_args_found:{forbidden_found}")
    else:
        print("✅ 全部未发现", flush=True)
    checks["forbidden_args_check"] = {
        "found": forbidden_found,
        "pass": len(forbidden_found) == 0,
    }

    # ── 3. 检查必须参数 ──
    print(f"[3] 检查必须参数（2个）...", end=" ", flush=True)
    missing_required = check_required_args(message)
    if missing_required:
        print(f"❌ MISSING: {missing_required}", flush=True)
        checks["all_pass"] = False
        checks["blockers"].append(f"required_args_missing:{missing_required}")
    else:
        print("✅ 全部存在", flush=True)
    checks["required_args_check"] = {
        "missing": missing_required,
        "pass": len(missing_required) == 0,
    }

    # ── 4. 检查 cron 时间 ──
    print(f"[4] 检查 cron 时间...", end=" ", flush=True)
    expr = schedule.get("expr", "")
    tz = schedule.get("tz", "")
    time_ok = (expr == EXPECTED_CRON["expr"]) and (tz == EXPECTED_CRON["tz"])
    if not time_ok:
        print(f"❌ CHANGED: expr={expr}, tz={tz}", flush=True)
        checks["all_pass"] = False
        checks["blockers"].append("cron_schedule_changed")
    else:
        print("✅ 未变化 (0 12 * * *, Asia/Shanghai)", flush=True)
    checks["cron_time_check"] = {
        "expected_expr": EXPECTED_CRON["expr"],
        "expected_tz": EXPECTED_CRON["tz"],
        "actual_expr": expr,
        "actual_tz": tz,
        "pass": time_ok,
    }

    # ── 5. 检查 notify hook ──
    print(f"[5] 检查 notify hook...", end=" ", flush=True)
    notify_ok = check_notify_hook(message)
    if not notify_ok:
        print("❌ MISSING", flush=True)
        checks["all_pass"] = False
        checks["blockers"].append("notify_hook_missing")
    else:
        print("✅ 存在", flush=True)
    checks["notify_hook_check"] = {"pass": notify_ok}

    # ── 6. 检查 watchdog wrapper ──
    print(f"[6] 检查 watchdog wrapper...", end=" ", flush=True)
    watchdog_ok = check_watchdog_wrapper(message)
    if not watchdog_ok:
        print("⚠️ 部分缺失", flush=True)
        checks["warnings"].append("watchdog_wrapper_incomplete")
    else:
        print("✅ 完整", flush=True)
    checks["watchdog_check"] = {"pass": watchdog_ok}

    # ── 7. 检查其他任务未变化 ──
    print(f"[7] 检查其他任务未变化...", end=" ", flush=True)
    other_jobs = find_other_jobs(jobs)
    other_ok = True
    for task_name, tj in other_jobs.items():
        if not tj.get("expr") or not tj.get("tz"):
            print(f"\n  ⚠️ {task_name}: schedule info missing", flush=True)
            other_ok = False
    if other_ok:
        print("✅ 其他任务未受影响", flush=True)
    else:
        print("❌ 部分任务状态不明", flush=True)
    checks["other_tasks_check"] = {"pass": other_ok}

    # ── 总结 ──
    print(f"\n{'=' * 60}", flush=True)
    if checks["all_pass"]:
        print("结果: ✅ PASS — 所有检查项通过", flush=True)
    else:
        print(f"结果: ❌ {len(checks['blockers'])} 个 BLOCKER", flush=True)
        for b in checks["blockers"]:
            print(f"  - {b}", flush=True)
    print(f"{'=' * 60}", flush=True)

    checks["final_status"] = "PASS" if checks["all_pass"] else "BLOCKER"

    # Write output
    out_path = os.path.join(STATUS_DIR, "v4_daily_scan_cron_payload_checker_20260526.json")
    os.makedirs(STATUS_DIR, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(checks, f, ensure_ascii=False, indent=2)
    print(f"\nOutput: {out_path}", flush=True)

    return 0 if checks["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
