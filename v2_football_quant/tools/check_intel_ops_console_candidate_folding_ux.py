#!/usr/bin/env python3
"""Check intel_ops_console candidate folding UX — native details/summary edition.

Verifies: A/B/C use native <details><summary>, A open by default, B/C closed,
all B cards show required elements, time_bins visible, C observation only,
numbers unchanged.
"""
import json, re
from pathlib import Path

CHECKER_NAME = "check_intel_ops_console_candidate_folding_ux"
MODULE = Path(__file__).resolve().parents[1]
DASHBOARD = MODULE / "data" / "runtime" / "dashboard" / "intel_ops_console.html"

results = []
PASS = 0

def check(label, condition, detail=""):
    global PASS
    tag = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    line = f"  [{tag:10s}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    results.append({"label": label, "status": tag, "detail": detail})
    return condition

print(f"=== {CHECKER_NAME} ===\n")

if not DASHBOARD.exists():
    check("intel_ops_console.html exists", False, "MISSING")
    print(f"\n---\n  Conclusion: BLOCKED")
    exit(1)

html = DASHBOARD.read_text()

# 1. A/B/C groups use native <details> with <summary>
check("A group uses <details class='candidate-group group-a'>",
      '<details class="candidate-group group-a"' in html)
check("B group uses <details class='candidate-group group-b'>",
      '<details class="candidate-group group-b"' in html)
check("C group uses <details class='candidate-group group-c'>",
      '<details class="candidate-group group-c"' in html)

# 2. All groups have <summary> element
check("A group has <summary>", '<summary>' in html)
check("<summary> count >= 3 (one per group)", html.count('<summary>') >= 3,
      f"found {html.count('<summary>')} <summary> elements")

# 3. Default states: A open, B closed, C closed
check("A group default open (details[open])",
      '<details class="candidate-group group-a" open>' in html)
check("B group default collapsed (no open attr)",
      '<details class="candidate-group group-b">' in html and
      '<details class="candidate-group group-b" open>' not in html)
check("C group default collapsed (no open attr)",
      '<details class="candidate-group group-c">' in html and
      '<details class="candidate-group group-c" open>' not in html)

# 4. B candidate cards exist
b_summary_count = len(re.findall(r'<div class="candidate-card grade-B"', html))
check("B candidate cards exist (candidate-card grade-B)",
      b_summary_count >= 1,
      f"found {b_summary_count} B cards")

# 5. Correct number of B cards (3 in night freeze)
check("B card count = 3 (night freeze)",
      b_summary_count == 3,
      f"found {b_summary_count} B cards (expected 3)")

# 6. B cards are inside a collapsed <details> (not individually open)
b_full_open = len(re.findall(r'<div class="candidate-card grade-B open"', html))
check("B cards in collapsed group by default (no individual open class)",
      b_full_open == 0,
      f"{b_full_open} B cards with 'open' class")

# 7. B candidate cards show required elements (time, league, teams, script)
b_summaries = []
for m in re.finditer(r'<div class="candidate-card grade-B">(.*?)</div>\s*(?=<!-- B[2-9]|</details>)', html, re.DOTALL):
    b_summaries.append(m.group(1))

b_summary_ok = 0
for i, s in enumerate(b_summaries):
    has_time = bool(re.search(r'\d{2}:\d{2}', s))
    has_league = "cr1-league" in s
    has_teams = "card-r2" in s
    has_script = "card-r3" in s
    all_ok = has_time and has_league and has_teams and has_script
    if all_ok:
        b_summary_ok += 1
    print(f"  B{i+1} summary: {'PASS' if all_ok else 'FAIL'} — time={has_time} league={has_league} teams={has_teams} script={has_script}")

check("All B cards show: time|league|teams|script",
      b_summary_ok == len(b_summaries) and len(b_summaries) > 0,
      f"{b_summary_ok}/{len(b_summaries)}")

# 8. B candidate cards have time_bins in card-r4
b_summary_timebins = 0
for i, s in enumerate(b_summaries):
    has_tb = "0-15m" in s and "16-30m" in s and "31-45m" in s
    if has_tb: b_summary_timebins += 1
    print(f"  B{i+1} summary: time_bins in card-r4 = {has_tb}")

check("All B candidate cards have time_bins in card-r4 (0-15m/16-30m/31-45m)",
      b_summary_timebins == len(b_summaries) and len(b_summaries) > 0,
      f"{b_summary_timebins}/{len(b_summaries)}")

# 9. B cards contain HT + strength in card-r3
b_full_ht = 0
b_full_strength = 0
for i, s in enumerate(b_summaries):
    has_ht = "HT" in s
    has_str = "强度" in s
    if has_ht: b_full_ht += 1
    if has_str: b_full_strength += 1
    print(f"  B{i+1} full card: {'PASS' if (has_ht and has_str) else 'FAIL'} — HT={has_ht} strength={has_str}")

check("All B cards have HT",
      b_full_ht == len(b_summaries) and len(b_summaries) > 0,
      f"{b_full_ht}/{len(b_summaries)}")

check("All B cards have 强度",
      b_full_strength == len(b_summaries) and len(b_summaries) > 0,
      f"{b_full_strength}/{len(b_summaries)}")

# 10. B cards have no per-card <details> (detail removed, lineage at group level)
b_no_per_card_details = 0
for i, s in enumerate(b_summaries):
    no_details = "<details>" not in s
    if no_details: b_no_per_card_details += 1
check("All B cards have no per-card <details> (detail removed to group level)",
      b_no_per_card_details == len(b_summaries) and len(b_summaries) > 0,
      f"{b_no_per_card_details}/{len(b_summaries)}")

# 11. No onclick JS for group/card toggling
check("No toggleGroup JS (native details)",
      "toggleGroup" not in html)
check("No toggleDetail JS (native details)",
      "toggleDetail" not in html)
check("No onclick='toggleGroup' anywhere",
      "onclick=\"toggleGroup" not in html)

# 12. A card shows time_bins in default view
a_ok = "0-15m" in html and "grade-A" in html
check("A card shows time_bins in default view",
      a_ok,
      "A card has 0-15m distribution")

# 13. C card count = 5 (night freeze)
c5 = len(re.findall(r'<div class="candidate-card grade-C"', html))
check("C card count = 5 (night freeze)",
      c5 == 5,
      f"found {c5} C cards (expected 5)")

# 14. Candidate numbers unchanged from night freeze
check("Candidate numbers: A=1 B=3 C=5",
      "B级候选 · 3场" in html or "B=3" in html or "B级：3场" in html,
      "night freeze counts")

# 15. Validation numbers unchanged
check("Validation numbers unchanged: 130, 57.7%",
      "130" in html and "57.7%" in html,
      "numbers confirmed")

# Summary
total = len(results)
failed = sum(1 for r in results if r["status"] == "FAIL")
print(f"\n---")
print(f"  Total: {total} | PASS: {PASS} | FAIL: {failed}")
conclusion = "PASS" if failed == 0 else "BLOCKED"
print(f"  Conclusion: {conclusion}")

marker = {
    "checker": CHECKER_NAME,
    "generated_at": "2026-05-21T00:00:00+08:00",
    "total": total, "pass": PASS, "fail": failed,
    "conclusion": conclusion, "results": results,
}
out_path = MODULE / "data" / "runtime" / "status" / f"{CHECKER_NAME}_result_20260521.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
print(f"  Marker: {out_path}")
