#!/usr/bin/env python3
"""tools/audit_openclaw_architecture.py

OpenClaw 架构合规审计工具。
检查废弃口径、API Key 明文、V33污染、旧 HOURLY 复燃等。

输出：data/runtime/openclaw_arch_audit_YYYYMMDD.json
"""

import json
import os
import re
import glob
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE / "data" / "runtime"

CHECK_PATHS = [
    BASE / "MEMORY.md",
    BASE / "STATE_CURRENT.md",
    BASE / "AGENTS.md",
    BASE / "SOUL.md",
    BASE / "USER.md",
    BASE / "TOOLS.md",
    BASE / "HEARTBEAT.md",
    BASE / "BOOT.md",
    BASE / "docs",
    BASE / "engine",
    BASE / "tools",
    BASE / "data" / "runtime",
    BASE / "data" / "daily_reports",
]

RED_FLAGS = [
    (r"V33(?![a-zA-Z])", "V33引用"),
    (r"v33(?![a-zA-Z])", "v33引用"),
    (r"皇冠", "皇冠引用"),
    (r"交叉参考", "交叉参考"),
    (r"FULLTIME_OVER", "FULLTIME_OVER"),
    (r"SECOND_HALF_OVER", "SECOND_HALF_OVER"),
    (r"market_scores", "market_scores引用"),
    (r"daily_runner\.py.*--run_tag HOURLY", "旧HOURLY命令"),
    (r"HOURLY 快速扫描", "HOURLY快速扫描"),
    (r"v4_runner\.py", "v4_runner.py直跑"),
    (r"v4_dashboard\.py", "v4_dashboard.py推送"),
    (r"sk-[A-Za-z0-9]{5,}", "疑似API Key (sk-)"),
]

V33_EXEMPT = [
    "DEPRECATION_REGISTRY.md",
    "openclaw_arch_audit",
]

ALLOWED_MARKET_SCORES = [
    "data/daily_reports/scout_",
    "data/daily_reports/full_scan_",
    "data/runtime/",
]


def check_file(path: Path) -> list[dict]:
    findings = []
    if not path.exists():
        return findings

    if path.is_dir():
        for fp in sorted(path.rglob("*")):
            if fp.is_file() and fp.suffix in (".md", ".py", ".txt", ".json", ".sh"):
                findings.extend(check_file(fp))
        return findings

    # Skip exempt files
    for exempt in V33_EXEMPT:
        if exempt in str(path):
            return findings

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    for pattern, label in RED_FLAGS:
        matches = re.findall(pattern, text)
        if not matches:
            continue

        # Check if in allowed scope
        if "market_scores" in label:
            allowed = False
            for ap in ALLOWED_MARKET_SCORES:
                if ap in str(path):
                    allowed = True
                    break
            if allowed:
                continue

        findings.append({
            "file": str(path.relative_to(BASE)),
            "pattern": label,
            "count": len(matches),
            "severity": "BLOCKER" if label in ("V33引用", "v33引用", "旧HOURLY命令") else "WARNING",
        })

    return findings


def check_openclaw_json() -> list[dict]:
    """检查 openclaw.json 是否有明文 Key"""
    findings = []
    path = os.path.expanduser("~/.openclaw/openclaw.json")
    if not os.path.exists(path):
        return findings
    try:
        text = open(path).read()
    except Exception:
        return findings

    key_patterns = [
        (r'sk-[A-Za-z0-9]{10,}', "疑似DeepSeek API Key"),
        (r'[Aa][Pp][Ii][Kk]ey["\']?\s*:\s*["\'][A-Za-z0-9_\-\.]{16,}["\']', "疑似API Key明文"),
        (r'[Ss]ecret["\']?\s*:\s*["\'][A-Za-z0-9_\-\.]{16,}["\']', "疑似Secret明文"),
        (r'[Tt]oken["\']?\s*:\s*["\'][A-Za-z0-9_\-\.]{16,}["\']', "疑似Token明文"),
    ]
    for pattern, label in key_patterns:
        if re.search(pattern, text):
            findings.append({
                "file": "~/.openclaw/openclaw.json",
                "pattern": label,
                "count": 1,
                "severity": "BLOCKER",
            })
    return findings


def check_cron_forbidden() -> list[dict]:
    """检查 cron 禁止命令"""
    findings = []
    cron_path = os.path.expanduser("~/.openclaw/cron/jobs.json")
    if not os.path.exists(cron_path):
        return findings
    try:
        with open(cron_path) as f:
            data = json.load(f)
    except Exception:
        return findings

    forbidden = [
        "daily_runner.py --run_tag HOURLY",
        "daily_runner.py --run_tag EARLY_CATCHUP",
        "daily_runner.py --run_tag EVENING_CATCHUP",
        "daily_runner.py --run_tag NIGHT_CATCHUP",
        "v4_runner.py",
        "v4_dashboard.py",
    ]

    for job in data.get("jobs", []):
        msg = job.get("payload", {}).get("message", "")
        name = job.get("name", "?")
        for fb in forbidden:
            if fb in msg:
                findings.append({
                    "file": f"cron job [{name}]",
                    "pattern": f"禁止命令: {fb}",
                    "count": 1,
                    "severity": "BLOCKER",
                })
    return findings


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")

    all_findings = []
    all_findings.extend(check_cron_forbidden())
    all_findings.extend(check_openclaw_json())
    for cp in CHECK_PATHS:
        all_findings.extend(check_file(cp))

    result = {
        "date": today,
        "total_findings": len(all_findings),
        "blockers": len([f for f in all_findings if f["severity"] == "BLOCKER"]),
        "warnings": len([f for f in all_findings if f["severity"] == "WARNING"]),
        "status": "BLOCKER" if any(f["severity"] == "BLOCKER" for f in all_findings) else "PASS",
        "findings": all_findings,
    }

    out_path = OUTPUT_DIR / f"openclaw_arch_audit_{today}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"📋 OpenClaw 架构审计 | {today}")
    print(f"   发现: {result['total_findings']} ({result['blockers']} BLOCKER, {result['warnings']} WARNING)")
    print(f"   状态: {result['status']}")
    print(f"   输出: {out_path}")

    if result["blockers"] > 0:
        print("\n--- BLOCKER ---")
        for f in result["findings"]:
            if f["severity"] == "BLOCKER":
                print(f"  🔴 {f['file']}: {f['pattern']}")
    if result["warnings"] > 0:
        print("\n--- WARNING ---")
        for f in result["findings"]:
            if f["severity"] == "WARNING":
                print(f"  🟡 {f['file']}: {f['pattern']}")


if __name__ == "__main__":
    main()
