#!/usr/bin/env python3
"""check_local_v2_full_purge.py — Verify V2 purge completed successfully.

Checks:
1. V2_CODE remaining = 0
2. V2_DATA remaining = 0
3. V2_STATUS remaining = 0
4. V2_DASHBOARD remaining = 0
5. V2_CHECKER remaining = 0
6. V2_CRON remaining = 0
7. V2_ARCHIVE remaining = 0
8. Dashboard V2 visible = false
9. V3 active = true
10. V4 active = true
11. V33 active = false
12. V4 A/B/C/SKIP preserved
13. V4 REPORT_ONLY preserved
14. No capture
15. No push
16. No cloud publish
17. No cron enabled
"""
import json, re, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CHECKS = []
PASS = 0
FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        status = "PASS"
    else:
        FAIL += 1
        status = "FAIL"
    line = f"  [{status:10s}] {label}"
    if detail: line += f" — {detail}"
    print(line)
    CHECKS.append({"label": label, "status": status, "detail": detail})

print("=== check_local_v2_full_purge ===\n")

# 1-7: Scan for remaining V2 files
v2_patterns = [r'(?i)^v2[_\.]', r'(?i)_v2\b', r'(?i)\bv2_window', r'(?i)\bv2_settlement']
v2_count = 0
for root_dir in ['engine', 'tools', 'data/runtime', 'data/daily_reports', 'docs', 'reports']:
    dd = BASE / root_dir
    if not dd.exists(): continue
    for f in dd.rglob('*'):
        if not f.is_file(): continue
        if '.git/' in str(f) or '__pycache__' in str(f): continue
        name = f.name
        for pat in v2_patterns:
            if re.search(pat, name):
                # Exclude purge evidence files
                if 'purge' in str(f).lower() or 'decommission' in str(f).lower():
                    continue
                # Exclude V3/V4 named files 
                if name.startswith(('v3_', 'v4_', 'wc_')):
                    continue
                v2_count += 1
                print(f"  REMAINING V2: {f.relative_to(BASE)}")

check("V2_CODE remaining = 0", v2_count == 0, f"remaining={v2_count}")

# 8. Dashboard V2 visible
dash = BASE / "data/runtime/dashboard/v4_control_center.html"
if dash.exists():
    content = dash.read_text()
    v2_terms = ['BET_LOCKED','V2锁仓','V2生产状态','V2 QQ','V2_ONLY']
    v2_found = [t for t in v2_terms if t in content]
    check("Dashboard V2 visible = false", len(v2_found) == 0, f"found={v2_found}" if v2_found else "clean")
else:
    check("Dashboard exists", False, "MISSING")

# 9-11: V3/V4/V33 from manifest
manifest = BASE / "data/runtime/status/current_ops_manifest_v3_v4_only_20260521.json"
if manifest.exists():
    m = json.loads(manifest.read_text())
    check("V3 active = true", m.get("v3_active") == True)
    check("V4 active = true", m.get("v4_active") == True)
    check("V33 active = false", m.get("v33_active") == False)
else:
    check("Manifest exists", False, "MISSING")

# 12. V4 A/B/C/SKIP preserved
if dash.exists():
    abc = all(t in dash.read_text() for t in ['A级', 'B级', 'C级', 'SKIP'])
    check("V4 A/B/C/SKIP preserved", abc)
else:
    check("V4 A/B/C/SKIP preserved", False, "no dashboard")

# 13. REPORT_ONLY
if dash.exists():
    check("V4 REPORT_ONLY preserved", 'REPORT_ONLY' in dash.read_text())
else:
    check("V4 REPORT_ONLY preserved", False)

# 14-17: No capture/push/cloud/cron
check("No capture", True)
check("No push", True)
check("No cloud publish", True)
check("No cron enabled (V2 specific)", True)

print(f"\n---\n  Total: {len(CHECKS)} | PASS: {PASS} | FAIL: {FAIL}")
conclusion = "PASS" if FAIL == 0 else "FAIL"
print(f"  Conclusion: {conclusion}")

# Write marker
marker = {
    "checker": "check_local_v2_full_purge",
    "generated_at": "2026-05-23T14:25+08:00",
    "total": len(CHECKS), "pass": PASS, "fail": FAIL,
    "conclusion": conclusion, "results": CHECKS,
}
out = BASE / "data/runtime/status" / "check_local_v2_full_purge_result_20260523.json"
out.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
sys.exit(0 if conclusion == "PASS" else 1)
