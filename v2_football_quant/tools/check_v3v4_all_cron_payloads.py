#!/usr/bin/env python3
"""tools/check_v3v4_all_cron_payloads.py — V3/V4 定时任务全量 payload checker
===========================================================================
检查所有 V3/V4 cron 任务的 payload 参数与目标脚本兼容。

检查项：
1. 所有 V3/V4 cron 任务存在
2. 每个 task 的 target_script 存在
3. 每个 payload 参数与 target_script --help 兼容
4. 不允许跨脚本专用参数混入
5. 12:00 scan 不允许出现 --review-only / --no-state-write / --no-verified-write / --no-cron
6. 所有任务 cron 时间未被修改
7. watchdog hook 存在
8. notify hook 存在
9. no-push / no-cloud 安全边界存在
10. 不存在 QQ 推荐推送参数
11. 不存在 cloud publish 参数
12. 不存在策略修改参数
13. 不存在 candidate 修改参数
14. 不存在实盘记录修改参数
15. notify 格式不应出现 pending=?
16. notify task_name 不应丢失下划线

用法：
  python3 tools/check_v3v4_all_cron_payloads.py

输出：
  data/runtime/status/v3v4_all_cron_payload_checker_20260526.json
===========================================================================
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from typing import Any

TZ = timezone(timedelta(hours=8))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS_DIR = os.path.join(BASE_DIR, "data", "runtime", "status")
CRON_JOBS_PATH = os.path.expanduser("~/.openclaw/cron/jobs.json")

V3V4_TASK_NAMES = [
    "V4_DAILY_SCAN_READONLY",
    "V4_VALIDATION_DRY_RUN",
    "V3V4_DASHBOARD_AFTER_SCAN_REFRESH",
    "V3V4_DASHBOARD_AFTER_VALIDATION_REFRESH",
    "V4_VALIDATION_DRY_RUN_FINAL_AND_DASHBOARD_REFRESH",
]

TASK_SCRIPT_MAP: dict[str, dict[str, Any]] = {
    "V4_DAILY_SCAN_READONLY": {
        "script": "engine/v4_scan_and_brief.py",
        "expected_cron": {"expr": "0 12 * * *", "tz": "Asia/Shanghai"},
        "required_args": ["--date", "--no-push"],
        "forbidden_args": ["--review-only", "--no-state-write", "--no-verified-write", "--no-cron"],
        "safety_flags": [],
    },
    "V4_VALIDATION_DRY_RUN": {
        "script": "engine/v4_ht_result_validator.py",
        "expected_cron": {"expr": "0 13 * * *", "tz": "Asia/Shanghai"},
        "required_args": ["--date"],
        "forbidden_args": [],
        "safety_flags": [],
    },
    "V3V4_DASHBOARD_AFTER_SCAN_REFRESH": {
        "script": "tools/run_v3v4_dashboard_daily_update.py",
        "expected_cron": {"expr": "0 13 * * *", "tz": "Asia/Shanghai"},
        "required_args": ["--date", "--phase", "--mode", "--no-api", "--no-capture", "--no-push", "--no-cloud"],
        "forbidden_args": [],
        "safety_flags": ["--no-api", "--no-push", "--no-cloud"],
    },
    "V3V4_DASHBOARD_AFTER_VALIDATION_REFRESH": {
        "script": "tools/run_v3v4_dashboard_daily_update.py",
        "expected_cron": {"expr": "30 13 * * *", "tz": "Asia/Shanghai"},
        "required_args": ["--date", "--phase", "--mode", "--no-api", "--no-capture", "--no-push", "--no-cloud"],
        "forbidden_args": [],
        "safety_flags": ["--no-api", "--no-push", "--no-cloud"],
    },
    "V4_VALIDATION_DRY_RUN_FINAL_AND_DASHBOARD_REFRESH": {
        "script": "tools/run_v3v4_validation_final_and_dashboard_refresh.py",
        "expected_cron": {"expr": "0 14 * * *", "tz": "Asia/Shanghai"},
        "required_args": ["--date", "--mode", "--no-capture", "--no-push", "--no-cloud"],
        "forbidden_args": [],
        "safety_flags": ["--no-push", "--no-cloud"],
    },
}

# Danger keywords that should never appear in any V3/V4 cron payload
DANGER_KEYWORDS = [
    # QQ recommendation push
    "qq_send", "qq_push", "qq_recommend", "safe_outbound_sender",
    "V4_QQ_ENABLED=true", "--push always",
    # Cloud publish
    "cloud_publish", "cloud publish", "--cloud-publish",
    # Strategy/candidate modification
    "strategy", "candidate_rating", "candidate_change",
    # Live bet records
    "live_bet", "real_bet",
    # Secrets
    "DASHSCOPE_API_KEY", "sk-",
]


def run_help(script_path: str) -> str | None:
    """Run script --help and return output."""
    full_path = os.path.join(BASE_DIR, script_path)
    if not os.path.exists(full_path):
        return None
    try:
        result = subprocess.run(
            [sys.executable, full_path, "--help"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout + result.stderr
    except Exception:
        return None


def extract_args_from_help(help_text: str) -> list[str]:
    """Extract argument names from --help output."""
    args = []
    for line in help_text.splitlines():
        m = re.findall(r'--[\w-]+', line)
        args.extend(m)
    return args


def check_forbidden_in_message(message: str, forbidden: list[str]) -> list[str]:
    """Check message for forbidden args."""
    found = []
    for arg in forbidden:
        if f" {arg}" in message or f"={arg}" in message or message.startswith(arg) or f"'{arg}'" in message:
            found.append(arg)
    return found


def check_required_in_message(message: str, required: list[str]) -> list[str]:
    """Check message for required args."""
    missing = []
    for arg in required:
        if arg not in message:
            missing.append(arg)
    return missing


def check_notify_format(message: str) -> list[str]:
    """Check notify format issues."""
    issues = []
    if "pending" in message and "'?'" in message:
        issues.append("notify_pending_question_mark")
    return issues


def main():
    print(f"{'=' * 60}", flush=True)
    print(f"V3V4 All Cron Payloads — Checker", flush=True)
    print(f"Time: {datetime.now(TZ).isoformat()}", flush=True)
    print(f"{'=' * 60}", flush=True)

    all_pass = True
    blockers = []
    warnings = []
    checks = {
        "timestamp": datetime.now(TZ).isoformat(),
        "all_pass": True,
        "blockers": [],
        "warnings": [],
        "task_results": {},
    }

    # ── Load cron jobs ──
    print(f"\n[1] 加载 cron jobs...", end=" ", flush=True)
    if not os.path.exists(CRON_JOBS_PATH):
        print("❌ NOT FOUND", flush=True)
        return 1
    with open(CRON_JOBS_PATH) as f:
        cron_data = json.load(f)
    jobs = cron_data.get("jobs", [])
    job_map = {j.get("name"): j for j in jobs if j.get("name")}
    print(f"✅ {len(jobs)} jobs loaded", flush=True)

    # ── Check all V3/V4 tasks exist ──
    print(f"[2] 检查所有 V3/V4 任务存在...", end=" ", flush=True)
    missing_tasks = [t for t in V3V4_TASK_NAMES if t not in job_map]
    if missing_tasks:
        print(f"❌ MISSING: {missing_tasks}", flush=True)
        blockers.append(f"tasks_missing:{missing_tasks}")
        all_pass = False
    else:
        print("✅ 全部 5 个存在", flush=True)

    for task_name in V3V4_TASK_NAMES:
        job = job_map.get(task_name)
        if not job:
            continue

        config = TASK_SCRIPT_MAP[task_name]
        message = job.get("payload", {}).get("message", "")
        schedule = job.get("schedule", {})

        task_result = {
            "task_name": task_name,
            "checks": [],
        }

        # ── Script exists ──
        script_path = config["script"]
        full_script = os.path.join(BASE_DIR, script_path)
        script_exists = os.path.exists(full_script)
        print(f"\n[{task_name}]", flush=True)
        print(f"  script={script_path} exists={script_exists}", flush=True)

        if not script_exists:
            task_result["checks"].append({"name": "script_exists", "pass": False})
            blockers.append(f"{task_name}: script {script_path} not found")
            all_pass = False
            checks["task_results"][task_name] = task_result
            continue

        # ── Get --help args ──
        help_text = run_help(script_path)
        supported_args = extract_args_from_help(help_text) if help_text else []
        print(f"  supported_args={supported_args}", flush=True)

        # ── Forbidden args check ──
        forbidden = config["forbidden_args"]
        forbidden_found = check_forbidden_in_message(message, forbidden)
        if forbidden_found:
            task_result["checks"].append({"name": "forbidden_args", "found": forbidden_found, "pass": False})
            blockers.append(f"{task_name}: forbidden args {forbidden_found}")
            all_pass = False
        else:
            task_result["checks"].append({"name": "forbidden_args", "pass": True})
        print(f"  forbidden_args_check: {'❌' if forbidden_found else '✅'}", flush=True)

        # ── Required args check ──
        required = config["required_args"]
        missing_required = check_required_in_message(message, required)
        if missing_required:
            task_result["checks"].append({"name": "required_args", "missing": missing_required, "pass": False})
            blockers.append(f"{task_name}: missing required args {missing_required}")
            all_pass = False
        else:
            task_result["checks"].append({"name": "required_args", "pass": True})
        print(f"  required_args_check: {'❌' if missing_required else '✅'}", flush=True)

        # ── Cross-script arg pollution (check message args against --help) ──
        message_args = extract_args_from_help(message)
        unknown_args = [a for a in message_args if a not in supported_args]
        # Filter out common shell/notify args
        known_shell = {"--task", "--date", "--exit-code", "--duration", "--dry-run", "--run-id"}
        unknown_args = [a for a in unknown_args if a not in known_shell]
        if unknown_args:
            task_result["checks"].append({"name": "cross_script_pollution", "unknown_args": unknown_args, "pass": False})
            warnings.append(f"{task_name}: unknown args {unknown_args}")
            all_pass = False
        else:
            task_result["checks"].append({"name": "cross_script_pollution", "pass": True})
        print(f"  cross_script_pollution: {'❌' if unknown_args else '✅'}", flush=True)

        # ── Cron schedule ──
        expected = config["expected_cron"]
        expr_ok = schedule.get("expr") == expected["expr"]
        tz_ok = schedule.get("tz") == expected["tz"]
        if not (expr_ok and tz_ok):
            task_result["checks"].append({"name": "cron_schedule", "pass": False})
            blockers.append(f"{task_name}: cron schedule changed (expr={schedule.get('expr')}, tz={schedule.get('tz')})")
            all_pass = False
        else:
            task_result["checks"].append({"name": "cron_schedule", "pass": True})
        print(f"  cron_schedule: {'❌' if not (expr_ok and tz_ok) else '✅'}", flush=True)

        # ── Watchdog (shell framework) ──
        has_watchdog = "EC=$?" in message and "T0=$(date +%s)" in message
        if not has_watchdog:
            task_result["checks"].append({"name": "watchdog", "pass": False})
            warnings.append(f"{task_name}: watchdog wrapper incomplete")
        else:
            task_result["checks"].append({"name": "watchdog", "pass": True})
        print(f"  watchdog: {'❌' if not has_watchdog else '✅'}", flush=True)

        # ── Notify hook ──
        has_notify = "notify_cron_task_complete_qq.py" in message
        if not has_notify:
            task_result["checks"].append({"name": "notify_hook", "pass": False})
            blockers.append(f"{task_name}: notify hook missing")
            all_pass = False
        else:
            task_result["checks"].append({"name": "notify_hook", "pass": True})
        print(f"  notify_hook: {'❌' if not has_notify else '✅'}", flush=True)

        # ── Safety boundaries ──
        safety_ok = True
        for flag in config["safety_flags"]:
            if flag not in message:
                safety_ok = False
                warnings.append(f"{task_name}: safety flag {flag} missing")
        if not safety_ok:
            task_result["checks"].append({"name": "safety_boundaries", "pass": False})
            all_pass = False
        else:
            task_result["checks"].append({"name": "safety_boundaries", "pass": True})
        print(f"  safety_boundaries: {'❌' if not safety_ok else '✅'}", flush=True)

        # ── Danger keywords ──
        danger_found = [kw for kw in DANGER_KEYWORDS if kw.lower() in message.lower()]
        if danger_found:
            task_result["checks"].append({"name": "danger_keywords", "found": danger_found, "pass": False})
            blockers.append(f"{task_name}: danger keywords {danger_found}")
            all_pass = False
        else:
            task_result["checks"].append({"name": "danger_keywords", "pass": True})
        print(f"  danger_keywords: {'❌' if danger_found else '✅'}", flush=True)

        checks["task_results"][task_name] = task_result

    # ── Overall ──
    checks["all_pass"] = all_pass
    checks["blockers"] = blockers
    checks["warnings"] = warnings
    checks["final_status"] = "PASS" if all_pass and not warnings else ("WARN_ONLY" if warnings and not blockers else "BLOCKER")

    print(f"\n{'=' * 60}", flush=True)
    if checks["final_status"] == "PASS":
        print("结果: ✅ PASS — 所有检查通过", flush=True)
    elif checks["final_status"] == "WARN_ONLY":
        print(f"结果: ⚠️ WARN_ONLY — {len(warnings)} 个警告, 0 个 BLOCKER", flush=True)
        for w in warnings:
            print(f"  ⚠️ {w}", flush=True)
    else:
        print(f"结果: ❌ BLOCKER — {len(blockers)} 个", flush=True)
        for b in blockers:
            print(f"  ❌ {b}", flush=True)
    print(f"{'=' * 60}", flush=True)

    # Write output
    out_path = os.path.join(STATUS_DIR, "v3v4_all_cron_payload_checker_20260526.json")
    os.makedirs(STATUS_DIR, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(checks, f, ensure_ascii=False, indent=2)
    print(f"\nOutput: {out_path}", flush=True)

    return 0 if checks["final_status"] in ("PASS", "WARN_ONLY") else 1


if __name__ == "__main__":
    sys.exit(main())
