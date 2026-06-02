#!/usr/bin/env python3
"""Check validation AB133 forensic recount — 10 strict checks.

Ensures the A+B=133 number is properly decomposed into three policies,
duplicates are audited, date windows are proven, and dashboard reflects
the production recommendation policy as primary.
"""
import json
from pathlib import Path

CHECKER_NAME = "check_validation_ab133_forensic_recount"
STATUS_DIR = Path("data/runtime/status")
DASHBOARD = Path("data/runtime/dashboard/v4_control_center.html")

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

# Check 1: Three policy recount file exists
fp = STATUS_DIR / "validation_ab133_recount_by_policy_20260520.json"
c1 = check(
    "Three-policy recount JSON exists",
    fp.exists(),
    str(fp) if fp.exists() else "MISSING"
)

if fp.exists():
    data = json.loads(fp.read_text())
    pa = data.get("policy_A_raw_record", {})
    pb = data.get("policy_B_unique_fixture_match", {})
    pc = data.get("policy_C_production_recommendation", {})

    # Check 2: All three policies present
    c2 = check(
        "Policy A (raw) present with A+B count",
        "A_plus_B_count" in pa,
        f"A+B={pa.get('A_plus_B_count')}"
    )

    c3 = check(
        "Policy B (unique fixture) present with A+B count",
        "A_plus_B_count" in pb,
        f"A+B={pb.get('A_plus_B_count')}"
    )

    c4 = check(
        "Policy C (production recommendation) present with A+B count",
        "A_plus_B_count" in pc,
        f"A+B={pc.get('A_plus_B_count')}"
    )

    # Check 5: Policy C != Policy A raw (different numbers after excluding unknown)
    c5 = check(
        "Policy C differs from Policy A (unknown excluded)",
        pc.get("A_plus_B_count") != pa.get("A_plus_B_count"),
        f"Raw={pa.get('A_plus_B_count')} vs Production={pc.get('A_plus_B_count')}"
    )

    # Check 6: Dashboard recommendation specifies Policy C as default
    dr = data.get("dashboard_recommendation", {})
    c6 = check(
        "Dashboard default = production_recommendation_policy",
        "production_recommendation_policy" in dr.get("default_display", ""),
        dr.get("default_display", "")
    )

# Check 7: Duplicate audit exists and shows 0 actual duplicate
dup_fp = STATUS_DIR / "validation_ab133_duplicate_audit_20260520.json"
if dup_fp.exists():
    dup = json.loads(dup_fp.read_text())
    checks = dup.get("checks", {})
    dd_fid_date = checks.get("duplicate_by_fixture_id_and_date", {})
    dd_mw = checks.get("multi_window_count", {})

    c7 = check(
        "Duplicate audit: zero same fixture_id+date duplicates",
        dd_fid_date.get("count", -1) == 0,
        f"count={dd_fid_date.get('count')}"
    )

    c8 = check(
        "Duplicate audit: zero multi-window (same fixture+date in multiple files)",
        dd_mw.get("count", -1) == 0,
        f"count={dd_mw.get('count')}"
    )
else:
    c7 = check("Duplicate audit JSON exists", False, "MISSING")
    c8 = check("Duplicate audit multi-window check", False, "SKIPPED — no file")

# Check 9: Date window audit exists and windows identical with reason
dw_fp = STATUS_DIR / "validation_ab133_date_window_audit_20260520.json"
if dw_fp.exists():
    dw = json.loads(dw_fp.read_text())
    c9 = check(
        "Date window audit: three windows identical with data-coverage reason",
        dw.get("three_windows_identical") is True and bool(dw.get("three_windows_identical_reason")),
        f"identical={dw.get('three_windows_identical')}, reason_len={len(dw.get('three_windows_identical_reason',''))}"
    )
else:
    c9 = check("Date window audit JSON exists", False, "MISSING")

# Check 10: Dashboard HTML reflects forensic recount (not just raw "样本133")
if DASHBOARD.exists():
    html = DASHBOARD.read_text()
    has_production_policy = "生产推荐" in html and ("130" in html or "已结算" in html)
    has_raw_record_ref = "原始记录" in html
    has_team_dedup = "球队去重" in html
    # Also accept new design: 生产推荐去重口径
    if not has_production_policy:
        has_production_policy = "生产推荐去重口径" in html

    c10 = check(
        "Dashboard shows production policy with raw record + team dedup context",
        has_production_policy and has_raw_record_ref and has_team_dedup,
        f"production={has_production_policy} raw={has_raw_record_ref} team_dedup={has_team_dedup}"
    )
else:
    c10 = check("Dashboard HTML exists", False, "MISSING")

# Summary
total = len(results)
failed = sum(1 for r in results if r["status"] == "FAIL")
print(f"\n---\n  总计: {total} | 通过: {PASS} | 失败: {failed} | 警告: 0 | 阻断: {failed}")
conclusion = "PASS" if failed == 0 else "BLOCKED"
print(f"  结论: {conclusion}")

# Write marker
marker = {
    "checker": CHECKER_NAME,
    "generated_at": "2026-05-20T23:58:00+08:00",
    "total": total,
    "pass": PASS,
    "fail": failed,
    "conclusion": conclusion,
    "results": results,
}
out_path = STATUS_DIR / f"{CHECKER_NAME}_result_20260520.json"
out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
print(f"  标记: {out_path}")
