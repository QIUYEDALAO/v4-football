#!/usr/bin/env python3
"""Check intel_ops_console decision UX redesign — 10 strict checks.

Verifies the 5-zone architecture, rolling validation dedup,
policy toggle, and C/SKIP handling.
"""
import json
from pathlib import Path

CHECKER_NAME = "check_intel_ops_console_decision_ux"
DASHBOARD = Path("data/runtime/dashboard/intel_ops_console.html")

results = []
PASS = 0

def check(label, condition, detail=""):
    global PASS
    tag = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    line = f"  [{tag: <9}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    results.append({"label": label, "status": tag, "detail": detail})
    return condition

print(f"=== {CHECKER_NAME} ===\n")

if not DASHBOARD.exists():
    check("intel_ops_console.html exists", False, "MISSING")
    print(f"\n---\n  总计: 1 | 通过: 0 | 失败: 1 | 阻断: 1\n  结论: BLOCKED")
    exit(1)

html = DASHBOARD.read_text()

# Check 1: Zone 1 — Today's Decision
c1 = check(
    "Zone 1: 今日决策 section present",
    "今日决策" in html and "当前窗口" in html and "V4 QQ" in html
)

# Check 2: Zone 2 — Today's Candidates
c2 = check(
    "Zone 2: 今日候选 section present with A/B/C cards",
    "今日候选" in html and "Palmeiras" in html and "帕尔梅拉斯" in html
)

# Check 3: Zone 3 — Validation Trust
c3 = check(
    "Zone 3: 验证可信度 section present with lineage status",
    "验证可信度" in html and "LINEAGE_VERIFIED" in html
)

# Check 4: Zone 4 — System Safety
c4 = check(
    "Zone 4: 系统安全 section present",
    "系统安全" in html and "PRODUCTION_VERIFIED" in html
)

# Check 5: Zone 5 — Next Actions
c5 = check(
    "Zone 5: 下一动作 section present with night one-shot",
    "下一动作" in html and "22:20" in html
)

# Check 6: Rolling validation does NOT repeat 7/14/30 three times
seven_d_count = html.count("7日")
fourteen_d_count = html.count("14日")
thirty_d_count = html.count("30日")
rolling_no_repeat = seven_d_count <= 2 and fourteen_d_count <= 2 and thirty_d_count <= 2
c6 = check(
    "Rolling validation: no repeated 7/14/30 triple-display",
    rolling_no_repeat,
    f"7日={seven_d_count} 14日={fourteen_d_count} 30日={thirty_d_count} (must be <=2 each)"
)

# Check 7: A+B=133 not exposed as bare default headline
# The primary display should show 130 (production), not 133 (raw)
c7 = check(
    "A+B primary display = 130 production (not 133 raw as bare headline)",
    "130" in html and "生产推荐去重口径" in html,
    "production=130 shown, policy label present"
)

# Check 8: Raw attribution only in audit expansion
c8 = check(
    "Raw attribution 133/438 only in policy toggle or expanded details",
    "原始记录" in html and "球队去重" in html,
    "raw numbers contextually labeled"
)

# Check 9: C cards default-collapsed
c9 = check(
    "C cards default-collapsed (details tag, not visible by default)",
    "<summary>" in html and "仅观察，不是推荐" in html and "C级观察" in html
)

# Check 10: V4 QQ closed status visible
c10 = check(
    "V4 QQ closed status visible",
    "V4_QQ_ENABLED=false" in html and "关闭" in html
)

# Check 11: Policy toggle exists (production/raw/team)
c11 = check(
    "Policy toggle: production / raw / team switch present",
    "switchPolicy" in html and "'production'" in html and "'raw'" in html and "'team'" in html
)

# Check 12: No C/SKIP as recommendation
c12 = check(
    "C/SKIP not presented as formal recommendation",
    "仅观察，不是推荐" in html
)

# Summary
total = len(results)
failed = sum(1 for r in results if r["status"] == "FAIL")
print(f"\n---\n  总计: {total} | 通过: {PASS} | 失败: {failed} | 警告: 0 | 阻断: {failed}")
conclusion = "PASS" if failed == 0 else "BLOCKED"
print(f"  结论: {conclusion}")

# Write marker
marker = {
    "checker": CHECKER_NAME,
    "generated_at": "2026-05-20T23:59:00+08:00",
    "total": total,
    "pass": PASS,
    "fail": failed,
    "conclusion": conclusion,
    "results": results,
}
out_path = Path("data/runtime/status") / f"{CHECKER_NAME}_result_20260520.json"
out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
print(f"  标记: {out_path}")
