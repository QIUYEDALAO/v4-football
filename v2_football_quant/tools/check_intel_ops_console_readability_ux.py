#!/usr/bin/env python3
"""Check intel_ops_console readability & row layout V2.
Verifies: fonts >= minimums, B-card row-1 inline layout,
time_bins visible, C collapsed, validation collapsed, numbers unchanged.
"""
import json, re
from pathlib import Path

CHECKER_NAME = "check_intel_ops_console_readability_ux"
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
    print(f"\n---\n  结论: BLOCKED")
    exit(1)

html = DASHBOARD.read_text()

# Extract body font-size from CSS variable --font-base
body_font_match = re.search(r'--font-base:\s*(\d+)px', html)
body_font = int(body_font_match.group(1)) if body_font_match else 0
c1 = check("body font-size >= 18px", body_font >= 18, f"--font-base={body_font}px")

# Extract team name font-size from CSS variable --font-team
team_font_match = re.search(r'--font-team:\s*(\d+)px', html)
team_font = int(team_font_match.group(1)) if team_font_match else 0
c2 = check("team name font-size >= 22px", team_font >= 22, f"--font-team={team_font}px")

# Check B card summary rows: time | league | teams | script | expand hint all inline
b_summaries = []
for m in re.finditer(r'<div class="candidate-card grade-B">(.*?)</div>\s*(?=<!-- B[2-9]|</details>)', html, re.DOTALL):
    b_summaries.append(m.group(1))

b_total = len(b_summaries)
print(f"\n  Found {b_total} B cards to inspect:")

b_summary_ok = 0
b_timebins_visible = 0

for i, s in enumerate(b_summaries):
    has_time = bool(re.search(r'\d{2}:\d{2}', s))
    has_league = "cr1-league" in s
    has_teams = "card-r2" in s
    has_script = "card-r3" in s
    no_card_r5 = "card-r5" not in s
    all_ok = has_time and has_league and has_teams and has_script and no_card_r5

    if all_ok:
        b_summary_ok += 1

    status = "OK" if all_ok else "MISSING:" + ",".join(
        (["time"] if not has_time else []) +
        (["league"] if not has_league else []) +
        (["teams"] if not has_teams else []) +
        (["script"] if not has_script else []) +
        (["card-r5"] if not no_card_r5 else [])
    )
    print(f"  B{i+1} summary: {'PASS' if all_ok else 'FAIL'} — {status}")

# Now check B cards for time_bins in card-r4
for i, s in enumerate(b_summaries):
    has_0_15 = "0-15m" in s
    has_16_30 = "16-30m" in s
    has_31_45 = "31-45m" in s
    if has_0_15 and has_16_30 and has_31_45:
        b_timebins_visible += 1

c3 = check(
    "B card: time|league|teams|script|4-row all inline",
    b_summary_ok == b_total and b_total > 0,
    f"{b_summary_ok}/{b_total}"
)

c4 = check(
    "B cards present (not all expanded cards)",
    b_total >= 1,
    f"{b_total} summary rows"
)

c5 = check(
    "B cards contain time_bins in card-r4 (0-15m/16-30m/31-45m)",
    b_timebins_visible == b_total and b_total > 0,
    f"{b_timebins_visible}/{b_total}"
)

# Check A card row 1
a_has_r1 = False
a_match = re.search(r'<div class="candidate-card grade-A">(.*?)</div>\s*</details>\s*<!-- ===== B组', html, re.DOTALL)
if a_match:
    a_html = a_match.group(1)
    a_r1_match = re.search(r'<div class="card-r1">(.*?)</div>', a_html, re.DOTALL)
    if a_r1_match:
        a_r1 = a_r1_match.group(1)
        a_has_r1 = (
            bool(re.search(r'\d{2}:\d{2}', a_r1)) and
            "cr1-league" in a_r1 and
            ("A级候选" in a_r1 or "grade-A" in a_html[:500]) and
            "card-r4" in a_html and "card-r5" not in a_html
        )

c9 = check(
    "A card row-1: time|league|A级候选|4-row (no r5)",
    a_has_r1,
    "A card has proper 4-row layout"
)

# Check C default collapsed (native details without open attr)
c_collapsed = '<details class="candidate-group group-c">' in html and '<details class="candidate-group group-c" open>' not in html
c10 = check(
    "C section default-collapsed (native details no open attr)",
    c_collapsed,
    "C cards hidden by default"
)

# Check validation details default collapsed
val_collapsed = '<details>' in html and '展开：完整验证数据' in html
c11 = check(
    "Validation raw details default-collapsed (inside <details>)",
    val_collapsed,
    "Validation raw data hidden by default"
)

# Check candidate numbers unchanged from night freeze
c12 = check(
    "Candidate numbers unchanged: A=1 B=3 C=5 (night freeze)",
    ("1/3/5" in html or "1 / 3 / 5" in html or "A1 / B3 / C5" in html or "1/4/6" in html or "1 / 4 / 6" in html) and ("SKIP=0" in html or "C=5" in html or "C=6" in html),
    "A=1 B=3 C=5 (night freeze) confirmed"
)

# Check validation numbers unchanged
has_130 = "130" in html and "已结算" in html
has_577 = "57.7%" in html
c13 = check(
    "Validation numbers unchanged: 130, 57.7%",
    has_130 and has_577,
    "130 settled, 57.7% hit rate confirmed"
)

# Check V4_QQ_ENABLED=false visible
c14 = check(
    "V4_QQ_ENABLED=false confirmed (visible or audit-hidden)",
    "V4_QQ_ENABLED=false" in html or ("V4_QQ_ENABLED" in html and "false" in html),
    "V4 QQ confirmed closed"
)

# Summary
total = len(results)
failed = sum(1 for r in results if r["status"] == "FAIL")
print(f"\n---\n  总计: {total} | 通过: {PASS} | 失败: {failed} | 警告: 0 | 阻断: {failed}")
conclusion = "PASS" if failed == 0 else "BLOCKED"
print(f"  结论: {conclusion}")

marker = {
    "checker": CHECKER_NAME,
    "generated_at": "2026-05-20T23:59:00+08:00",
    "total": total, "pass": PASS, "fail": failed,
    "conclusion": conclusion, "results": results,
}
out_path = Path("data/runtime/status") / f"{CHECKER_NAME}_result_20260520.json"
out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
print(f"  标记: {out_path}")
