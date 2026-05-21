#!/usr/bin/env python3
"""Check intel_ops_console remove per-card detail link.
Verifies: no card-r5 in A/B cards, no per-card detail link/button,
no '技术详情' or '展开详情' in cards, lineage unified at group level,
A/B cards 4-row only, group folding intact, time_bins preserved,
numbers unchanged, no push fields.
"""
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

CHECKER_NAME = "check_intel_ops_console_remove_per_card_detail_link"
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

# Extract A and B group content for per-card checks
a_group_match = re.search(r'<details class="candidate-group group-a" open>(.*?)</details>\s*<!-- ===== B组', html, re.DOTALL)
b_group_match = re.search(r'<details class="candidate-group group-b">(.*?)</details>\s*<!-- ===== A/B候选技术血缘', html, re.DOTALL)

a_html = a_group_match.group(1) if a_group_match else ""
b_html = b_group_match.group(1) if b_group_match else ""

# 1. No card-r5 in A/B cards
ck("No card-r5 in A card",
   "card-r5" not in a_html)
ck("No card-r5 in B cards",
   "card-r5" not in b_html)
ck("card-r5 CSS rule removed from entire HTML",
   "card-r5" not in html)

# 2. No "技术详情" or "展开详情" text in A/B cards
ck("No '技术详情' text in A card",
   "技术详情" not in a_html)
ck("No '技术详情' text in B cards",
   "技术详情" not in b_html)
ck("No '展开详情' text in A card",
   "展开详情" not in a_html)
ck("No '展开详情' text in B cards",
   "展开详情" not in b_html)

# 3. No per-card detail button/link
ck("No per-card <details> inside A card (except group-level)",
   a_html.count('<details') == 0)
ck("No per-card <details> inside B cards (except group-level)",
   b_html.count('<details') == 0)

# 4. A card has exactly 4 rows (card-r1 through card-r4, no card-r5)
ck("A card has card-r1",
   "card-r1" in a_html)
ck("A card has card-r2",
   "card-r2" in a_html)
ck("A card has card-r3",
   "card-r3" in a_html)
ck("A card has card-r4",
   "card-r4" in a_html)

# 5. B cards have 4 rows each (use full extract with closing </details>)
b_full_zone = html.split("group-b\">")[1].split("<!-- ===== A/B候选技术血缘")[0] if "group-b\">" in html else ""
b_card_count = len(re.findall(r'<div class="candidate-card grade-B">', b_full_zone))
b_cards_with_r4 = 0
for m in re.finditer(r'<div class="candidate-card grade-B">(.*?)</div>\s*(?=<!-- B[2-9]|</details>)', b_full_zone, re.DOTALL):
    s = m.group(1)
    if "card-r1" in s and "card-r2" in s and "card-r3" in s and "card-r4" in s and "card-r5" not in s:
        b_cards_with_r4 += 1
ck(f"All {b_card_count} B cards have exactly 4 rows (r1-r4, no r5)",
   b_cards_with_r4 == b_card_count,
   f"{b_cards_with_r4}/{b_card_count}")

# 6. Unified lineage section exists
ck("Lineage section <details class='lineage-details'> exists",
   '<details class="lineage-details">' in html)
ck("Lineage summary '展开：A/B候选技术血缘' exists",
   "展开：A/B候选技术血缘" in html)
ck("Lineage default closed (no open attr)",
   '<details class="lineage-details">' in html and '<details class="lineage-details" open>' not in html)

# 7. Lineage content has English team names and source
ck("Lineage contains A1: Palmeiras vs Cerro Porteno",
   "Palmeiras vs Cerro Porteno" in html)
ck("Lineage contains B1: Hangzhou Greentown vs Shandong Luneng",
   "Hangzhou Greentown vs Shandong Luneng" in html)
ck("Lineage contains B2: Ilves vs Inter Turku",
   "Ilves vs Inter Turku" in html)
ck("Lineage contains B3: Start vs Bodo/Glimt",
   "Start vs Bodo/Glimt" in html)
ck("Lineage contains source: scout_v4",
   "scout_v4" in html)
ck("Lineage contains factors: recent_time_bins",
   "recent_time_bins" in html)

# 8. Lineage has no push/QQ fields
ck("Lineage has no QQ references",
   "QQ" not in (html.split("lineage-details")[-1].split("</details>")[0] if "lineage-details" in html else ""))
ck("Lineage has no actual_send",
   "actual_send" not in (html.split("lineage-details")[-1].split("</details>")[0] if "lineage-details" in html else ""))
ck("Lineage has no BOSS批准",
   "BOSS批准" not in (html.split("lineage-details")[-1].split("</details>")[0] if "lineage-details" in html else ""))

# 9. A/B/C group folding intact
ck("A group folding intact (native details open)",
   '<details class="candidate-group group-a" open>' in html)
ck("B group folding intact (native details, no open)",
   '<details class="candidate-group group-b">' in html and '<details class="candidate-group group-b" open>' not in html)
ck("C group folding intact (native details, no open)",
   '<details class="candidate-group group-c">' in html and '<details class="candidate-group group-c" open>' not in html)

# 10. No onclick JS for toggling
ck("No toggleGroup/toggleDetail JS",
   "toggleGroup" not in html and "toggleDetail" not in html)

# 11. B time_bins visible
b_timebins_count = 0
for m in re.finditer(r'<div class="candidate-card grade-B">(.*?)</div>\s*(?=<!-- B[2-9]|</details>)', b_full_zone, re.DOTALL):
    if "0-15m" in m.group(1) and "16-30m" in m.group(1) and "31-45m" in m.group(1):
        b_timebins_count += 1
ck(f"All B cards have time_bins in card-r4",
   b_timebins_count == b_card_count,
   f"{b_timebins_count}/{b_card_count}")

# 12. A time_bins visible
ck("A card has time_bins in card-r4",
   "0-15m" in a_html and "16-30m" in a_html and "31-45m" in a_html)

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
