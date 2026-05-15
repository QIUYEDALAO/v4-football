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
    ("V4扫描-凌晨", "01:20"),
    ("V4扫描-早场", "07:20"),
    ("V2早场兜底", "07:35"),
    ("V4每日复盘", "10:30"),
    ("V2每日结算", "12:10"),
    ("V2建池-每日", "12:35"),
    ("V4扫描-午间", "13:20"),
    ("V2每日结算-补跑", "15:35"),
    ("V4扫描-傍晚", "16:20"),
    ("V4扫描-晚间", "22:20"),
    ("V2晚场兜底", "18:35"),
    ("V2夜间兜底", "23:35"),
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

    # Check required jobs
    for name, slot in REQUIRED_JOBS:
        found = False
        for j in jobs:
            if "V2窗口" in j.get("name", "") and "窗口" in name:
                found = True
                result["required_found"].append(f"{name} ({slot})")
                break
            if j.get("name") == name:
                found = True
                result["required_found"].append(f"{name} ({slot})")
                break
        if not found:
            result["required_missing"].append(f"{name} ({slot})")

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

    # Determine status
    if result["forbidden_found"]:
        result["status"] = "BLOCKER"
    elif result["required_missing"]:
        result["status"] = "WARNING"
    elif result["timeout_issues"]:
        result["status"] = "WARNING"
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
            print(f"  ⚠️ 缺失: {m}")
    if result["forbidden_found"]:
        for f in result["forbidden_found"]:
            print(f"  🔴 禁止命令: {f}")
    if result["timeout_issues"]:
        for t in result["timeout_issues"]:
            print(f"  🟡 超时问题: {t}")


if __name__ == "__main__":
    main()
