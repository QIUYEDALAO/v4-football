#!/usr/bin/env python3
"""tools/audit_openclaw_architecture.py

OpenClaw 架构合规审计工具。
检查废弃口径、API Key 明文、V33污染、旧 HOURLY 复燃等。

分类：
- BLOCKER: 运行态污染（engine/正式推送链路/cron/QQ模板/核心文件）
- ALLOWED_REFERENCE: 治理文档/审计工具中的说明性引用
- INFO: 归档中的旧内容
- SECRET_BLOCKER: 疑似真实 Key/Token/Secret 泄露

输出：data/runtime/openclaw_arch_audit_YYYYMMDD.json
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE / "data" / "runtime"

# ── 路径分类 ──

REAL_BLOCKER_PATHS = [
    "MEMORY.md",
    "STATE_CURRENT.md",
    "AGENTS.md",
    "BOOT.md",
    "HEARTBEAT.md",
    "USER.md",
    "SOUL.md",
    "TOOLS.md",
]

ALLOWED_REFERENCE_PATHS = [
    "docs/DEPRECATION_REGISTRY.md",
    "docs/OPENCLAW_AGENT_ARCHITECTURE.md",
    "docs/OPENCLAW_CRON_POLICY.md",
    "docs/OPENCLAW_QQ_POLICY.md",
    "docs/OPENCLAW_REPORT_POLICY.md",
    "docs/OPENCLAW_INCIDENT_RESPONSE.md",
    "docs/OPENCLAW_SECRETS_POLICY.md",
    "docs/OPENCLAW_TOOL_POLICY.md",
    "docs/OPENCLAW_WORKSPACE_POLICY.md",
]

ALLOWED_REFERENCE_PREFIXES = [
    "tools/audit_openclaw_architecture.py",
    "tools/check_cron_policy.py",
    "data/runtime/openclaw_arch_audit_",
]

INFO_PREFIXES = [
    "archive/",
]

# ── 废弃词清单 ──

# 检查路径（根目录文件 + docs/engine/tools）
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
    (r"FULLTIME_OVER", "FULLTIME_OVER使用"),
    (r"SECOND_HALF_OVER", "SECOND_HALF_OVER使用"),
    (r"market_scores", "market_scores引用"),
    (r"daily_runner\.py.*--run_tag HOURLY", "旧HOURLY命令"),
    (r"HOURLY 快速扫描", "HOURLY快速扫描"),
    (r"v4_runner\.py", "v4_runner.py直跑"),
    (r"v4_dashboard\.py", "v4_dashboard.py推送"),
]

# 仅当出现在 engine/ data/daily_reports cron 配置时才标记
ENGINE_LIVE_PATTERNS = [
    r"V33(?![a-zA-Z])",
    r"v33(?![a-zA-Z])",
    r"皇冠",
    r"交叉参考",
    r"FULLTIME_OVER",
    r"SECOND_HALF_OVER",
    r"market_scores",
    r"daily_runner\.py.*--run_tag HOURLY",
    r"HOURLY 快速扫描",
    r"v4_runner\.py",
    r"v4_dashboard\.py",
]

ALLOWED_MARKET_SCORES = [
    "data/daily_reports/scout_",
    "data/daily_reports/full_scan_",
    "data/runtime/",
]


def _is_deprecation_context(text: str, pattern: str) -> bool:
    """判断匹配到的废弃词是否在禁止性说明的上下文中"""
    deprecation_markers = [
        "已废弃", "废弃口径", "禁止", "禁止引用", "不得引用",
        "不得使用", "不得出现", "已下线", "不再使用",
        "已彻底禁用", "已清理", "已删除",
        "不参与推送", "不作为", "不承认",
        "禁止运行", "禁止在 cron", "禁止在",
        "V33污染", "旧 HOURLY",
    ]
    # 查找匹配行附近200字符（对比100，覆盖更远的上下文）
    for m in re.finditer(pattern, text):
        start = max(0, m.start() - 200)
        end = min(len(text), m.end() + 200)
        context = text[start:end]
        for marker in deprecation_markers:
            if marker in context:
                return True
    return False


def classify_path(rel_path: str) -> str:
    """分类路径：blocker / allowed_ref / info / live"""
    # Check exact match first
    for bp in REAL_BLOCKER_PATHS:
        if rel_path == bp:
            return "blocker"
    for ap in ALLOWED_REFERENCE_PATHS:
        if rel_path == ap:
            return "allowed_ref"
    for ap in ALLOWED_REFERENCE_PREFIXES:
        if rel_path.startswith(ap):
            return "allowed_ref"
    for ip in INFO_PREFIXES:
        if rel_path.startswith(ip):
            return "info"
    # Default to live (engine, data_reports, etc.)
    return "live"


def check_file(path: Path) -> list[dict]:
    findings = []
    if not path.exists():
        return findings

    if path.is_dir():
        for fp in sorted(path.rglob("*")):
            if fp.is_file() and fp.suffix in (".md", ".py", ".txt", ".json", ".sh"):
                findings.extend(check_file(fp))
        return findings

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    rel = str(path.relative_to(BASE))
    path_class = classify_path(rel)

    # Scan engine/ and data/daily_reports for live usage
    is_live = path_class == "live"
    is_blocker_root = path_class == "blocker"
    is_allowed_ref = path_class == "allowed_ref"
    is_info = path_class == "info"

    for pattern, label in RED_FLAGS:
        matches = re.findall(pattern, text)
        if not matches:
            continue

        # market_scores allowed in scout/full_scan/runtime files
        if "market_scores" in label:
            allowed = False
            for ap in ALLOWED_MARKET_SCORES:
                if ap in rel:
                    allowed = True
                    break
            if allowed:
                continue

        # Determine severity
        if is_info:
            severity = "INFO"
        elif is_allowed_ref:
            severity = "ALLOWED_REFERENCE"
        elif is_blocker_root and label in ("V33引用", "v33引用"):
            # 上下文检测：判断是禁止性说明还是仍然引用
            if _is_deprecation_context(text, pattern):
                severity = "ALLOWED_REFERENCE"
            else:
                severity = "BLOCKER"
        elif is_blocker_root and label == "旧HOURLY命令":
            if _is_deprecation_context(text, r"HOURLY"):
                severity = "ALLOWED_REFERENCE"
            else:
                severity = "BLOCKER"
        elif is_live and label in ("V33引用", "v33引用", "旧HOURLY命令"):
            severity = "BLOCKER"
        elif is_live:
            severity = "WARNING"
        elif is_blocker_root:
            severity = "WARNING"
        else:
            severity = "ALLOWED_REFERENCE"

        findings.append({
            "file": rel,
            "pattern": label,
            "count": len(matches),
            "severity": severity,
        })

    return findings


def check_openclaw_json() -> list[dict]:
    """检查 openclaw.json — 只检测疑似真实明文 Key/Token/Secret"""
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
    ]

    for pattern, label in key_patterns:
        if re.search(pattern, text):
            findings.append({
                "file": "~/.openclaw/openclaw.json",
                "pattern": label,
                "count": 1,
                "severity": "SECRET_BLOCKER",
            })

    return findings


def check_cron_forbidden() -> list[dict]:
    """检查 cron 禁止命令 — 这些是运行态 BLOCKER"""
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
                    "severity": "SECRET_BLOCKER",
                })
    return findings


def check_engine_and_reports() -> list[dict]:
    """检查 engine/ 和 data/daily_reports 中的废弃词"""
    findings = []
    check_dirs = [
        BASE / "engine",
        BASE / "data" / "daily_reports",
    ]
    for cd in check_dirs:
        if not cd.exists():
            continue
        for fp in sorted(cd.rglob("*")):
            if fp.is_file() and fp.suffix in (".py", ".txt", ".json", ".sh"):
                try:
                    text = fp.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                rel = str(fp.relative_to(BASE))
                for pattern, label in RED_FLAGS:
                    matches = re.findall(pattern, text)
                    if not matches:
                        continue
                    # market_scores allowed in scout files
                    if "market_scores" in label:
                        allowed = False
                        for ap in ALLOWED_MARKET_SCORES:
                            if ap in rel:
                                allowed = True
                                break
                        if allowed:
                            continue
                    findings.append({
                        "file": rel,
                        "pattern": label,
                        "count": len(matches),
                        "severity": "BLOCKER",
                    })
    return findings


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")

    all_findings = []
    all_findings.extend(check_cron_forbidden())
    all_findings.extend(check_openclaw_json())
    all_findings.extend(check_engine_and_reports())
    for cp in CHECK_PATHS:
        all_findings.extend(check_file(cp))

    # Aggregate counts
    real_blocker_count = len([f for f in all_findings if f["severity"] == "BLOCKER"])
    secret_blocker_count = len([f for f in all_findings if f["severity"] == "SECRET_BLOCKER"])
    allowed_ref_count = len([f for f in all_findings if f["severity"] == "ALLOWED_REFERENCE"])
    info_count = len([f for f in all_findings if f["severity"] == "INFO"])
    warning_count = len([f for f in all_findings if f["severity"] == "WARNING"])

    if real_blocker_count > 0 or secret_blocker_count > 0:
        final_status = "BLOCKER"
    elif allowed_ref_count > 0 or info_count > 0:
        final_status = "PASS_WITH_REFERENCES"
    else:
        final_status = "PASS"

    result = {
        "date": today,
        "total_findings": len(all_findings),
        "summary": {
            "real_blocker_count": real_blocker_count,
            "secret_blocker_count": secret_blocker_count,
            "allowed_reference_count": allowed_ref_count,
            "info_count": info_count,
            "warning_count": warning_count,
        },
        "final_status": final_status,
        "findings": all_findings,
    }

    out_path = OUTPUT_DIR / f"openclaw_arch_audit_{today}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"📋 OpenClaw 架构审计 | {today}")
    print(f"   final_status: {final_status}")
    print(f"   总计: {len(all_findings)}")
    print(f"   🔴 real BLOCKER: {real_blocker_count}")
    print(f"   🟠 SECRET:  {secret_blocker_count}")
    print(f"   🟡 WARNING: {warning_count}")
    if allowed_ref_count > 0:
        print(f"   ⚪ ALLOWED_REF: {allowed_ref_count} (治理说明，不计入BLOCKER)")
    if info_count > 0:
        print(f"   ⚪ INFO: {info_count} (归档内容，不计入BLOCKER)")
    print(f"   输出: {out_path}")

    if real_blocker_count > 0:
        print("\n--- BLOCKER (运行态污染) ---")
        for f in all_findings:
            if f["severity"] == "BLOCKER":
                print(f"  🔴 {f['file']}: {f['pattern']} ({f['count']}x)")
    if secret_blocker_count > 0:
        print("\n--- SECRET_BLOCKER (疑似密钥泄露) ---")
        for f in all_findings:
            if f["severity"] == "SECRET_BLOCKER":
                print(f"  🟠 {f['file']}: {f['pattern']}")
    if warning_count > 0:
        print("\n--- WARNING (非核心文件中出现废弃词) ---")
        for f in all_findings:
            if f["severity"] == "WARNING":
                print(f"  🟡 {f['file']}: {f['pattern']} ({f['count']}x)")

    print()
    if final_status == "PASS":
        print("✅ 审计通过")
    elif final_status == "PASS_WITH_REFERENCES":
        print("✅ 审计通过（仅治理说明/归档引用，无运行态BLOCKER）")
    else:
        print("❌ 审计未通过，需处理 real BLOCKER / SECRET_BLOCKER")


if __name__ == "__main__":
    main()
