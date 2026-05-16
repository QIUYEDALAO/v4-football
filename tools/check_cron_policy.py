#!/usr/bin/env python3
"""tools/check_cron_policy.py

检查当前 cron 调度是否符合 OpenClaw Cron Policy。
输出：data/runtime/cron_policy_check_YYYYMMDD.json
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE / "data" / "runtime"

REQUIRED_JOBS = [
    ("V2窗口检查器", "05/35 每小时"),
    ("V2每日结算", "12:10"),
    ("V2每日结算-补跑", "15:35"),
    ("V2建池-每日", "13:15"),
    ("V2早场兜底", "07:35"),
    ("V2晚场兜底", "18:35"),
    ("V2夜间兜底", "23:35"),
    ("V4每日复盘", "12:35"),
    ("SYS每日结算汇总", "13:00"),
    ("V4扫描-凌晨", "01:20"),
    ("V4扫描-早场", "07:20"),
    ("V4扫描-午间", "14:05"),
    ("V4扫描-傍晚", "16:20"),
    ("V4扫描-晚间", "22:20"),
    ("V4赛中快照", "比赛期间"),
    ("每日状态更新", "17:25"),
    ("SYS-架构审计守卫", "08:40/17:40/23:40"),
    ("V4周报", "每周日"),
    ("V4月报", "每月1日"),
]

# 核心时间链路 — 任一缺失或时间不匹配 → FAIL
CORE_TIME_LINK = [
    ("V2每日结算", "12:10", "10 12 * * *"),
    ("V4每日复盘", "12:35", "35 12 * * *"),
    ("SYS每日结算汇总", "13:00", "0 13 * * *"),
    ("V2建池-每日", "13:15", "15 13 * * *"),
    ("V4扫描-午间", "14:05", "5 14 * * *"),
]

NOTIFICATION_JOBS = [
    "SYS-架构审计守卫",  # BLOCKER/FAIL → systemEvent
    "SYS每日结算汇总",    # 13:00 统一推送（内部 systemEvent）
    "V2每日结算",        # 异常时 AlertAgent 系统报
    "V4扫描-午间",       # push=always
    "V4扫描-傍晚",       # push=conditional (A/B or异常)
    "V4扫描-晚间",       # push=conditional
    "V4扫描-早场",       # push=conditional
    "V4扫描-凌晨",       # push=conditional
]

FORBIDDEN_CMDS = [
    "daily_runner.py --run_tag HOURLY",
    "daily_runner.py --run_tag EARLY_CATCHUP",
    "daily_runner.py --run_tag EVENING_CATCHUP",
    "daily_runner.py --run_tag NIGHT_CATCHUP",
    "v4_runner.py",
    "v4_dashboard.py",
]

TIMEOUT_RULES = {
    "V4扫描": 4500,
    "V2窗口": 480,
    "V2结算": 2700,
    "V4复盘": 1200,
}


def main():
    cron_path = os.path.expanduser("~/.openclaw/cron/jobs.json")
    if not os.path.exists(cron_path):
        print("❌ cron jobs.json not found")
        sys.exit(1)

    with open(cron_path) as f:
        data = json.load(f)

    jobs = data.get("jobs", [])
    result = {
        "date": datetime.now().strftime("%Y%m%d"),
        "total_jobs": len(jobs),
        "required_found": [],
        "required_missing": [],
        "forbidden_found": [],
        "timeout_issues": [],
        "enabled_v2_watchdog": False,
        "status": "PASS",
    }

    # Check required jobs — 精确名称+时间双重校验
    for name, slot in REQUIRED_JOBS:
        found = False
        for j in jobs:
            job_name = j.get("name", "")
            # V2窗口检查器特殊匹配
            if name == "V2窗口检查器" and "V2窗口" in job_name:
                found = True
                result["required_found"].append(f"{job_name} ({slot})")
                break
            # 精确名称匹配（必须完全一致）
            if job_name == name:
                found = True
                result["required_found"].append(f"{job_name} ({slot})")
                break
        if not found:
            result["required_missing"].append(f"{name} ({slot})")

    # Check core time link — 精准校验时间和脚本
    result["core_link_issues"] = []
    for link_name, link_slot, link_expr in CORE_TIME_LINK:
        found = False
        for j in jobs:
            job_name = j.get("name", "")
            job_expr = j.get("schedule", {}).get("expr", "")
            if job_name == link_name:
                found = True
                if job_expr != link_expr:
                    result["core_link_issues"].append(
                        f"{link_name}: 期望expr={link_expr}，实际={job_expr}"
                    )
                break
        if not found:
            result["core_link_issues"].append(f"{link_name}: 任务缺失")

    # Check delivery.mode=none for all jobs
    result["delivery_mode_issues"] = []
    for j in jobs:
        name = j.get("name", "")
        dm = j.get("delivery", {}).get("mode", "inherit")
        if dm == "announce":
            result["delivery_mode_issues"].append(f"{name}: delivery.mode=announce")
        elif dm not in ("none", "inherit"):
            result["delivery_mode_issues"].append(f"{name}: delivery.mode={dm}")

    # Check announce count
    announce_count = sum(1 for j in jobs if j.get("delivery", {}).get("mode") == "announce")
    result["announce_count"] = announce_count

    # Check V2窗口检查器 specifically — must always be enabled
    for j in jobs:
        if "V2窗口" in j.get("name", ""):
            result["enabled_v2_watchdog"] = j.get("enabled", False)
            break

    # Check forbidden commands
    for j in jobs:
        msg = j.get("payload", {}).get("message", "")
        name = j.get("name", "")
        for fb in FORBIDDEN_CMDS:
            if fb in msg:
                result["forbidden_found"].append(f"{name}: {fb}")

    # Check timeout rules
    for j in jobs:
        name = j.get("name", "")
        to = j.get("payload", {}).get("timeoutSeconds", None)
        for rule_key, expected in TIMEOUT_RULES.items():
            if rule_key in name:
                if to is None or to < expected:
                    result["timeout_issues"].append(
                        f"{name}: timeout={to}s (expected >= {expected}s)"
                    )

    # Check NOTIFICATION_GAP: delivery.mode must not be announce
    announce_count = sum(1 for j in jobs if j.get("delivery", {}).get("mode") == "announce")
    result["announce_count"] = announce_count
    result["notification_gaps"] = []
    result["delivery_issues"] = []
    for notif_name in NOTIFICATION_JOBS:
        found = False
        for j in jobs:
            if j.get("name") == notif_name or ("V4扫描" in notif_name and "V4扫描" in j.get("name", "")):
                found = True
                break
        if not found:
            result["notification_gaps"].append(notif_name)
    # Also check that SYS审计守卫 has conditional push for BLOCKER
    sys_guard_found = False
    sys_guard_has_conditional = False
    for j in jobs:
        if "SYS-架构审计守卫" in j.get("name", ""):
            sys_guard_found = True
            msg = j.get("payload", {}).get("message", "")
            if "BLOCKER" in msg and "架构审计异常" in msg:
                sys_guard_has_conditional = True
            break
    if not sys_guard_has_conditional and sys_guard_found:
        result["notification_gaps"].append("SYS-架构审计守卫: BLOCKER通知配置")

    # Determine status
    if result["forbidden_found"]:
        result["status"] = "BLOCKER"
    elif result["required_missing"]:
        result["status"] = "FAIL"  # 缺失必要任务 → FAIL，不降到WARNING
    elif result["core_link_issues"]:
        result["status"] = "FAIL"  # 核心链路异常 → FAIL
    elif result["delivery_mode_issues"]:
        result["status"] = "FAIL"  # announce残留或非none模式 → FAIL
    elif result["timeout_issues"]:
        result["status"] = "WARNING"
    elif result["notification_gaps"]:
        result["status"] = "NOTIFICATION_GAP"
    else:
        result["status"] = "PASS"

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"cron_policy_check_{result['date']}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"📋 Cron Policy Check | {result['date']}")
    print(f"   总任务数: {result['total_jobs']}")
    print(f"   必要任务: {len(result['required_found'])} found, {len(result['required_missing'])} missing")
    print(f"   禁止命令: {len(result['forbidden_found'])}")
    print(f"   超时问题: {len(result['timeout_issues'])}")
    print(f"   V2窗口检查器启用: {result['enabled_v2_watchdog']}")
    print(f"   状态: {result['status']}")
    print(f"   输出: {out_path}")

    if result["required_missing"]:
        for m in result["required_missing"]:
            print(f"  ❌ 缺失: {m}")
    if result["core_link_issues"]:
        for c in result["core_link_issues"]:
            print(f"  ❌ 核心链路: {c}")
    if result["delivery_mode_issues"]:
        for d in result["delivery_mode_issues"]:
            print(f"  ❌ 投递模式: {d}")
    if result["forbidden_found"]:
        for f in result["forbidden_found"]:
            print(f"  🔴 禁止命令: {f}")
    if result["timeout_issues"]:
        for t in result["timeout_issues"]:
            print(f"  🟡 超时问题: {t}")


if __name__ == "__main__":
    main()
