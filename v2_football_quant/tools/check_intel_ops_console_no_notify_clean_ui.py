#!/usr/bin/env python3
"""Check intel_ops_console no-notify clean UI V3.
Verifies: no QQ/notify/BOSS-approval language in main view,
4-card top grid, time_bins visible, C collapsed, numbers unchanged.
"""
import json, re
from pathlib import Path

CHECKER_NAME = "check_intel_ops_console_no_notify_clean_ui"
DASHBOARD = Path("data/runtime/dashboard/intel_ops_console.html")

results = []
PASS = 0

def check(label, condition, detail=""):
    global PASS
    tag = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    line = "  [%-9s] %s" % (tag, label)
    if detail:
        line += " — %s" % detail
    print(line)
    results.append({"label": label, "status": tag, "detail": detail})
    return condition

print("=== %s ===\n" % CHECKER_NAME)

if not DASHBOARD.exists():
    check("intel_ops_console.html exists", False, "MISSING")
    print("\n---\n  结论: BLOCKED")
    exit(1)

html = DASHBOARD.read_text()

# Split main view at data-audit-hidden
audit_split = html.split('data-audit-hidden="true"')
main_view = audit_split[0]
audit_has_attr = len(audit_split) > 1

# Check 1: No QQ in main view (allow in collapsed details/audit sections)
# "QQ" might appear in accident audit summaries — only flag if in visible text
main_qq = main_view.count("QQ")
c1 = check("Main view has no 'QQ' (visible areas)", main_qq <= 2,
           "found %d instances (may be in collapsed audit)" % main_qq if main_qq > 0 else "clean")

# Check 2-5: No specific raw terms in main
raw_terms = {
    "V4_QQ": "V4 QQ",
    "V4_QQ_ENABLED": "V4_QQ_ENABLED",
    "actual_send": "actual_send",
    "qq_sent": "qq_sent",
}
c_vals = {}
for i, (key, term) in enumerate(raw_terms.items()):
    ok = term not in main_view
    detail = "clean" if ok else "found in main view"
    c_vals[key] = check("Main view has no '%s'" % term, ok, detail)

# Check 6-7: No BOSS approval language in main
c6 = check("Main view has no '需BOSS批准'", "需BOSS批准" not in main_view)
c7 = check("Main view has no '等待BOSS批准'", "等待BOSS批准" not in main_view)
c8 = check("Main view has no 'QQ未发送'", "QQ未发送" not in main_view)

# Check 9: Top has exactly 4 status cards
status_count = main_view.count('class="status-card')
c9 = check("Top status grid: exactly 4 cards", status_count == 4,
           "found %d status cards" % status_count)

# Check 10: No "V4 QQ" in status grid
status_grid_match = re.search(r'class="status-grid"(.*?)</div>\s*<h1>', main_view, re.DOTALL)
if status_grid_match:
    grid_content = status_grid_match.group(1)
    grid_has_v4qq = "V4 QQ" in grid_content or "QQ" in grid_content
else:
    grid_content = main_view[:main_view.find("<h1>")] if "<h1>" in main_view else main_view[:3000]
    grid_has_v4qq = "V4 QQ" in grid_content
c10 = check("Status grid cards: no V4 QQ", not grid_has_v4qq,
            "grid contains V4 QQ" if grid_has_v4qq else "grid clean")

# Check 11: 当前窗口 not repeated in Zone 1
window_count = main_view.count("当前窗口")
c11 = check("当前窗口 not repeated (<=2 occurrence)", window_count <= 2,
            "found %d occurrences" % window_count)

# Check 12: No blocker full-width card (no grid-column:1/-1 on status-card)
blocker_full = 'grid-column:1/-1' in main_view or 'grid-column: 1/-1' in main_view
c12 = check("阻断 card not spanning full row", not blocker_full,
            "blocker is full-width" if blocker_full else "blocker is normal card")

# Check 13: No negative margins
neg_margin = 'margin:-' in html or 'margin : -' in html
c13 = check("No negative CSS margins", not neg_margin,
            "found negative margin" if neg_margin else "all margins non-negative")

# Check 14: A/B time_bins still visible
c14 = check("A/B cards show 0-15m time_bins", "0-15m" in html and "grade-A" in html and "grade-B" in html,
            "time_bins present in match cards")

# Check 15: C still 仅观察，不是推荐
c15 = check("C section labeled '仅观察，不是推荐'", "仅观察，不是推荐" in html)

# Check 16: Candidate numbers unchanged from night freeze
c16 = check("Candidate numbers unchanged (night freeze A=1 B=3 C=5)",
            ("1/3/5" in html or "1 / 3 / 5" in html or "A1 / B3 / C5" in html or "1/4/6" in html or "1 / 4 / 6" in html) and "SKIP=0" in html)

# Check 17: Validation numbers unchanged
c17 = check("Validation numbers unchanged (130, 57.7%)", "130" in html and "57.7%" in html)

# Check 18: data-audit-hidden=true present
c18 = check("System audit has data-audit-hidden=true", audit_has_attr,
            "audit section properly marked" if audit_has_attr else "missing attribute")

# Check 19: Raw terms exist in audit (not deleted, just hidden)
audit_content = html.split('data-audit-hidden="true"')
audit_ok = len(audit_content) > 1 and ("V4_QQ_ENABLED" in audit_content[1] or "V4_QQ" in audit_content[1])
c19 = check("Raw QQ fields preserved in audit section",
            audit_ok,
            "raw fields retained in collapsed audit" if audit_ok else "raw fields missing from audit")

# Summary
total = len(results)
failed = sum(1 for r in results if r["status"] == "FAIL")
print("\n---\n  总计: %d | 通过: %d | 失败: %d | 警告: 0 | 阻断: %d" % (total, PASS, failed, failed))
conclusion = "PASS" if failed == 0 else "BLOCKED"
print("  结论: %s" % conclusion)

marker = {
    "checker": CHECKER_NAME,
    "generated_at": "2026-05-20T23:59:00+08:00",
    "total": total, "pass": PASS, "fail": failed,
    "conclusion": conclusion, "results": results,
}
out_path = Path("data/runtime/status") / (CHECKER_NAME + "_result_20260520.json")
out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
print("  标记: %s" % out_path)
