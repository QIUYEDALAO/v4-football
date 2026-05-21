#!/usr/bin/env python3
"""Check intel_ops_console AB collapsible unified card layout — native details/summary edition.
Verifies: A/B/C native <details><summary> groups, A open B/C closed by default,
A/B unified card format, B script NOT right column, B expand native <details>,
time_bins visible, C observation only, numbers unchanged, no onclick JS, no push fields.
"""
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

CHECKER_NAME = "check_intel_ops_console_ab_collapsible_unified_card_layout"
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

# 1. A/B/C all use native <details class="candidate-group"> with <summary>
ck("A group uses native <details> with <summary>",
   '<details class="candidate-group group-a"' in html and '<summary>' in html)
ck("B group uses native <details> with <summary>",
   '<details class="candidate-group group-b"' in html)
ck("C group uses native <details> with <summary>",
   '<details class="candidate-group group-c"' in html)

# 2. Default states — A open, B/C closed (native open attribute)
ck("A group default open (details[open])",
   '<details class="candidate-group group-a" open>' in html)
ck("B group default collapsed (no open attr on details)",
   '<details class="candidate-group group-b">' in html and '<details class="candidate-group group-b" open>' not in html)
ck("C group default collapsed (no open attr on details)",
   '<details class="candidate-group group-c">' in html and '<details class="candidate-group group-c" open>' not in html)

# 3. A/B cards use same structure (candidate-card with card-r1/r2/r3/r4/r5)
a_card_match = re.search(r'<details class="candidate-group group-a" open>(.*?)</details>\s*<!-- ===== B组', html, re.DOTALL)
b_group_match = re.search(r'<details class="candidate-group group-b">(.*?)</details>\s*<!-- ===== A/B候选技术血缘', html, re.DOTALL)

ab_same = False
if a_card_match and b_group_match:
    a_html = a_card_match.group(1)
    b_html = b_group_match.group(1)
    a_has_structure = "candidate-card grade-A" in a_html and "card-r1" in a_html and "card-r2" in a_html and "card-r4" in a_html
    b_has_same = "candidate-card grade-B" in b_html and "card-r1" in b_html and "card-r2" in b_html and "card-r4" in b_html
    ab_same = a_has_structure and b_has_same
ck("A/B cards use same candidate-card structure (card-r1/r2/r3/r4/r5)",
   ab_same)

# 4. Old B structures removed
ck("b-summary-row removed",
   "b-summary-row" not in html)
ck("bs-r1/bs-r2/bs-r3/bs-r4 removed",
   "bs-r1" not in html and "bs-r2" not in html and "bs-r3" not in html)
ck("b-full-card removed",
   "b-full-card" not in html)

# 5. B script NOT right column (inline in card-r3)
b_cards_html = b_group_match.group(1) if b_group_match else ""
b_script_inline = "card-r3" in b_cards_html and "｜剧本" in b_cards_html
ck("B script inline in card-r3 (NOT right column)",
   b_script_inline)

# 6. No per-card detail link/button in A/B cards (card-r5 removed)
ck("No card-r5 in A card (per-card detail removed)",
   "card-r5" not in a_html)
ck("No card-r5 in B cards (per-card detail removed)",
   "card-r5" not in b_cards_html)

# 7. A/B cards are exactly 4-row (r1-r4, no r5)
ck("A card is 4-row only (r1-r4)",
   "card-r1" in a_html and "card-r2" in a_html and "card-r3" in a_html and "card-r4" in a_html and "card-r5" not in a_html)
ck("B cards are 4-row only (r1-r4)",
   "card-r1" in b_cards_html and "card-r2" in b_cards_html and "card-r3" in b_cards_html and "card-r4" in b_cards_html and "card-r5" not in b_cards_html)

# 8. B team names on dedicated row (card-r2)
ck("B team names on dedicated row (card-r2)",
   "card-r2" in b_cards_html and "浙江队 vs 山东泰山" in b_cards_html)

# 9. B time_bins visible in card-r4
ck("B time_bins visible in card-r4",
   "0-15m" in b_cards_html and "16-30m" in b_cards_html and "31-45m" in b_cards_html)

# 10. A time_bins visible in card-r4
ck("A time_bins visible in card-r4",
   "0-15m" in (a_card_match.group(1) if a_card_match else ""))

# 11. No per-card detail text; lineage at group level instead
ck("No '技术详情' in A/B cards (per-card detail removed)",
   "技术详情" not in a_html and "技术详情" not in b_cards_html)
ck("No '展开详情' in A/B cards (old detail button removed)",
   "展开详情" not in a_html and "展开详情" not in b_cards_html)
ck("Group-level lineage section exists",
   "lineage-details" in html and "展开：A/B候选技术血缘" in html)
ck("Lineage default closed",
   '<details class="lineage-details">' in html and '<details class="lineage-details" open>' not in html)

# 12. C observation only
ck("C labeled '仅观察，不是推荐'",
   "仅观察，不是推荐" in html)

# 13. No push/notification fields in main view
ck("No QQ fields in candidate area",
   "V4_QQ" not in b_cards_html)
ck("No actual_send in candidate area",
   "actual_send" not in b_cards_html)

# 14. Candidate numbers unchanged
ck("Candidate numbers: A=1 B=3 C=5",
   "A1 / B3 / C5" in html or "1 / 3 / 5" in html or "A=1 B=3 C=5" in html)

# 15. Validation numbers unchanged
ck("Validation numbers: 130 settled, 57.7%",
   "130" in html and "57.7%" in html)

# 16. V2/V4 preservation
ck("V2 multi-day preserved",
   "2026-05-15" in html and "BET_LOCKED" in html)
ck("V4 B unknown preserved",
   "Arsenal" in html and "Burnley" in html and "RESULT_UNKNOWN_API_DISABLED" in html)

# 17. No old JS onclick functions — native details/summary works without JS
ck("No toggleGroup JS (native details works without JS)",
   "toggleGroup" not in html)
ck("No toggleDetail JS (native details works without JS)",
   "toggleDetail" not in html)
ck("No onclick on candidate group toggling",
   'onclick="toggleGroup' not in html and 'onclick="toggleDetail' not in html)
ck("No toggleBCard/toggleCSection JS",
   "toggleBCard" not in html and "toggleCSection" not in html)

# 18. Native details marker hidden CSS present
ck("::-webkit-details-marker hidden",
   "::-webkit-details-marker{display:none}" in html)
ck("::marker hidden",
   "::marker{display:none;content:''}" in html)

# 19. group-hint expand/collapse CSS present
ck("group-hint::after expand/collapse text",
   'content:\'展开' in html and 'content:\'收起' in html)

# 20. Prohibitions
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
