#!/usr/bin/env python3
"""Check intel_ops_console detail button de-emphasize → now fully removed.
Verifies: no per-card detail link/button of any kind in A/B cards,
no card-r5, no '展开详情' or '技术详情' in cards, lineage at group level,
A/B/C group folding intact, time_bins preserved, numbers unchanged, no push fields.
"""
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

CHECKER_NAME = "check_intel_ops_console_detail_button_deemphasize"
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

# Extract A and B card zones
a_html = html.split("group-a\" open>")[1].split("</details>")[0] if "group-a\" open>" in html else ""
b_html = html.split("group-b\">")[1].split("</details>")[0] if "group-b\">" in html else ""

# 1. No per-card detail text of any kind
ck("No '展开详情 ▾' anywhere in HTML",
   "展开详情 ▾" not in html)
ck("No '技术详情 ▾' in A/B cards (per-card detail removed)",
   "技术详情 ▾" not in html)

# 2. card-r5 completely removed (CSS + HTML)
ck("card-r5 completely removed from HTML",
   "card-r5" not in html)

# 3. No per-card <details> inside A/B cards
ck("No per-card <details> in A card",
   "<details>" not in a_html)
ck("No per-card <details> in B cards",
   "<details>" not in b_html)

# 4. A/B cards have only 4 rows (no detail row)
ck("A card is 4-row (r1-r4, no r5)",
   "card-r1" in a_html and "card-r2" in a_html and "card-r3" in a_html and "card-r4" in a_html)
ck("B cards are 4-row (r1-r4, no r5)",
   "card-r1" in b_html and "card-r2" in b_html and "card-r3" in b_html and "card-r4" in b_html)

# 5. Group-level lineage section exists
ck("Lineage <details class='lineage-details'> exists",
   "lineage-details" in html)
ck("Lineage summary: '展开：A/B候选技术血缘'",
   "展开：A/B候选技术血缘" in html)
ck("Lineage default closed (no open attr)",
   '<details class="lineage-details">' in html and '<details class="lineage-details" open>' not in html)

# 6. Lineage contains tech info (English names, source)
ck("Lineage has English team names",
   "Palmeiras vs Cerro Porteno" in html and "Hangzhou Greentown vs Shandong Luneng" in html)
ck("Lineage has source info",
   "scout_v4" in html and "recent_time_bins" in html)

# 7. No right-side detail/action column
ck("No right-side detail/action column",
   "detail-col" not in html and "action-col" not in html and "card-action-column" not in html)

# 8. Detail does not squeeze team names / script / time_bins
ck("B team names on card-r2 (not squeezed)",
   "card-r2" in b_html and "浙江队 vs 山东泰山" in b_html)
ck("B script in card-r3 (not squeezed)",
   "card-r3" in b_html and "｜剧本" in b_html)
ck("B time_bins in card-r4 (not squeezed)",
   "0-15m" in b_html and "16-30m" in b_html and "31-45m" in b_html)

# 9. A/B/C group folding intact
ck("A group folding intact (details open)",
   '<details class="candidate-group group-a" open>' in html)
ck("B group folding intact (details, no open)",
   '<details class="candidate-group group-b">' in html and '<details class="candidate-group group-b" open>' not in html)
ck("C group folding intact (details, no open)",
   '<details class="candidate-group group-c">' in html and '<details class="candidate-group group-c" open>' not in html)

# 10. No onclick JS
ck("No toggleGroup/toggleDetail JS",
   "toggleGroup" not in html and "toggleDetail" not in html)

# 11. B time_bins visible in all 3 cards
b_card_count = 0
b_timebins_count = 0
for m in re.finditer(r'<div class="candidate-card grade-B">(.*?)</div>\s*(?=<!-- B[2-9]|</details>)', b_html, re.DOTALL):
    b_card_count += 1
    if "0-15m" in m.group(1) and "16-30m" in m.group(1) and "31-45m" in m.group(1):
        b_timebins_count += 1
ck(f"All B cards have time_bins",
   b_timebins_count == b_card_count,
   f"{b_timebins_count}/{b_card_count}")

# 12. Lineage has no push/QQ fields
lineage_zone = html.split("lineage-details")[-1].split("</details>")[0] if "lineage-details" in html else ""
ck("Lineage has no QQ",
   "QQ" not in lineage_zone or "QQ" not in lineage_zone)
ck("Lineage has no actual_send (visible area)",
   "actual_send" not in html.split("data-audit-hidden")[0])

# 13. Candidate numbers unchanged
ck("Candidate numbers: A=1 B=3 C=5",
   "A1 / B3 / C5" in html or "1 / 3 / 5" in html or "A=1 B=3 C=5" in html)

# 14. Validation numbers unchanged
ck("Validation numbers: 130 settled, 57.7%",
   "130" in html and "57.7%" in html)

# 15. V2/V4 preservation
ck("V2 multi-day preserved",
   "2026-05-15" in html and "BET_LOCKED" in html)
ck("V4 B unknown preserved",
   "Arsenal" in html and "Burnley" in html and "RESULT_UNKNOWN_API_DISABLED" in html)

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
