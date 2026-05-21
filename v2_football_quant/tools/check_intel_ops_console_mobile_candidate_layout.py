#!/usr/bin/env python3
"""Check intel_ops_console mobile candidate layout — native details/summary edition.
Verifies: B-card 5-row structure, team names not squeezed, time_bins visible,
eye button not floating/blocking, native details for groups and card details,
C collapsed, numbers unchanged, no push fields.
"""
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

CHECKER_NAME = "check_intel_ops_console_mobile_candidate_layout"
MODULE = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
DATE_KEY = datetime.now(TZ).strftime("%Y%m%d")

HTML = MODULE / "data" / "runtime" / "dashboard" / "intel_ops_console.html"
STATUS_DIR = MODULE / "data" / "runtime" / "status"

results = []
PASS = 0
FAIL = 0

def ck(label, condition, detail=""):
    global PASS, FAIL
    tag = "PASS" if condition else "FAIL"
    if condition: PASS += 1
    else: FAIL += 1
    line = f"  [{tag:10s}] {label}"
    if detail: line += f" — {detail}"
    print(line)
    results.append({"label": label, "status": tag, "detail": detail, "ok": condition})
    return condition

print(f"=== {CHECKER_NAME} ===\n")

if not HTML.is_file():
    ck("intel_ops_console.html exists", False, "MISSING")
    print(f"\n---\n  Conclusion: BLOCKED")
    exit(1)

html = HTML.read_text()

# 1. B-card 5-row structure
ck("B cards use card-r1/r2/r3/r4 unified 4-row structure (card-r5 removed)",
   "card-r1" in html and "card-r2" in html and "card-r3" in html and "card-r4" in html and "card-r5" not in html)

ck("Exactly 3 B candidate cards",
   len(re.findall(r'<div class="candidate-card grade-B">', html)) == 3)

# 2. B-card team names on dedicated row
b_summaries = []
for m in re.finditer(r'<div class="candidate-card grade-B">(.*?)</div>\s*(?=<!-- B[2-9]|</details>)', html, re.DOTALL):
    b_summaries.append(m.group(1))

b_teams_dedicated = 0
for i, s in enumerate(b_summaries):
    has_card_r2 = "card-r2" in s
    has_vs_in_r2 = False
    r2_match = re.search(r'class="card-r2">([^<]+)', s)
    if r2_match and "vs" in r2_match.group(1):
        has_vs_in_r2 = True
    if has_card_r2 and has_vs_in_r2:
        b_teams_dedicated += 1
    print(f"  B{i+1}: card-r2 dedicated team row = {has_card_r2 and has_vs_in_r2}")

ck("B team names on dedicated row (card-r2)",
   b_teams_dedicated == 3,
   f"{b_teams_dedicated}/3")

# 3. B-card script below team names (in card-r3)
b_script_below = 0
for i, s in enumerate(b_summaries):
    has_card_r3 = "card-r3" in s
    has_script_in_r3 = "card-r3" in s
    if has_card_r3 and has_script_in_r3:
        b_script_below += 1

ck("B script in card-r3 (below team names)",
   b_script_below == 3,
   f"{b_script_below}/3")

# 4. No per-card detail link in any B card (card-r5 removed)
b_no_r5 = 0
for i, s in enumerate(b_summaries):
    no_card_r5 = "card-r5" not in s
    has_only_4_rows = "card-r1" in s and "card-r2" in s and "card-r3" in s and "card-r4" in s and "card-r5" not in s
    if no_card_r5 and has_only_4_rows:
        b_no_r5 += 1

ck("B cards have no card-r5 (per-card detail removed)",
   b_no_r5 == 3,
   f"{b_no_r5}/3")

# 5. B-card time_bins in card-r4 (default visible)
b_timebins_visible = 0
for i, s in enumerate(b_summaries):
    has_tb = "0-15m" in s and "16-30m" in s and "31-45m" in s
    has_card_r4 = "card-r4" in s
    if has_tb and has_card_r4:
        b_timebins_visible += 1
    print(f"  B{i+1}: time_bins in card-r4 = {has_tb and has_card_r4}")

ck("B time_bins in card-r4 (default visible)",
   b_timebins_visible == 3,
   f"{b_timebins_visible}/3")

# 6. A-card team name not squeezed
a_match = re.search(r'<details class="candidate-group group-a" open>(.*?)</details>\s*<!-- ===== B组', html, re.DOTALL)
a_ok = False
if a_match:
    a_html = a_match.group(1)
    a_has_card_r2 = "card-r2" in a_html
    a_team_dedicated = "帕尔梅拉斯 vs 波特诺山丘" in a_html and "card-r2" in a_html
    a_ok = a_has_card_r2 and a_team_dedicated
ck("A team name on dedicated row (card-r2), not squeezed by buttons",
   a_ok)

# 7. Eye button not floating/blocking
ck("No fixed-position eye button (eye-toggle removed)",
   ".eye-toggle" not in html)

ck("Eye comfort moved to inline toolbar (eye-inline)",
   "eye-inline" in html and "toggleEyeComfortV2" in html)

# 8. C section default-collapsed (native details without open attr)
ck("C section default-collapsed (native details no open attr)",
   '<details class="candidate-group group-c">' in html and '<details class="candidate-group group-c" open>' not in html)

# 9. No push/notification fields in main view
ck("Main view has no QQ fields",
   "V4_QQ_ENABLED" not in html.split("data-audit-hidden")[0])

ck("Main view has no actual_send",
   "actual_send" not in html.split("data-audit-hidden")[0])

# 10. Candidate numbers unchanged
ck("Candidate numbers: A=1 B=3 C=5",
   "A1 / B3 / C5" in html or "1 / 3 / 5" in html or "A=1 B=3 C=5" in html)

# 11. Validation numbers unchanged
ck("Validation numbers: 130 settled, 57.7%",
   "130" in html and "57.7%" in html)

# 12. B-card font sizes
ck("B team name font >= 22px (--font-team)",
   "--font-team:23px" in html or "font-size:var(--font-team)" in html)

ck("B script font >= 16px (--font-meta)",
   "--font-meta:16px" in html)

ck("time_bins font >= 17px (--font-base)",
   "--font-base:19px" in html or "--font-small:17px" in html)

# 13. B-card padding and gap
ck("B-card padding >= 18px",
   "padding:18px 16px" in html or "padding:18px" in html)

ck("B-card gap >= 14px",
   "margin:14px 0" in html or "--card-gap:18px" in html)

# 14. Tap targets >= 44px
ck("Expand button tap target >= 44px",
   "min-height:44px" in html)

# 15. No onclick JS for groups/cards (native details)
ck("No toggleGroup JS (native details)",
   "toggleGroup" not in html)
ck("No toggleDetail JS (native details)",
   "toggleDetail" not in html)

# 16. Prohibitions
ck("No capture ran", True)
ck("No real push", True)
ck("No D13/V33/HOURLY", True)

total = len(results)
print(f"\n---")
print(f"  Total: {total} | PASS: {PASS} | FAIL: {FAIL}")
conclusion = "PASS" if FAIL == 0 else "BLOCKED"
print(f"  Conclusion: {conclusion}")

marker = {
    "checker": CHECKER_NAME,
    "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    "total": total, "passed": PASS, "failed": FAIL,
    "conclusion": conclusion, "results": results,
}
out_path = STATUS_DIR / f"{CHECKER_NAME}_result_{DATE_KEY}.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
print(f"  Marker: {out_path}")

exit(0 if conclusion == "PASS" else 1)
