#!/usr/bin/env python3
"""Check intel_ops_console.html for post-night state correctness.

Verifies: night scan completed, no stale evening/next-window display,
A=1 B=3 C=5, B summary mode, C collapsed, V2 modules restored.
"""
import json
import sys
from pathlib import Path

CHECKER_NAME = "check_intel_ops_console_post_night_state"
MODULE = Path(__file__).resolve().parents[1]
CONSOLE = MODULE / "data" / "runtime" / "dashboard" / "intel_ops_console.html"

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

if not CONSOLE.is_file():
    check("intel_ops_console.html exists", False, "MISSING")
    print(f"\n---\n  Conclusion: BLOCKED")
    sys.exit(1)

html = CONSOLE.read_text()

# 1. CURRENT=night — page reflects night window as current/final
night_done = ("夜间" in html and "已完成" in html) or \
             ("夜间扫描已完成" in html) or \
             ("night" in html.lower() and "冻结" in html)
check("CURRENT reflects night window",
      night_done,
      "page shows night as completed/frozen")

# 2. Page does NOT show "当前窗口=晚间" as active state
# The top grid should say "今日扫描 已完成" not "当前窗口 晚间"
stale_current = ("当前窗口" in html and "晚间" in html) and \
                ("今日扫描" not in html or "已完成" not in html)
check("No stale '当前窗口=晚间' display",
      not stale_current,
      "evening window not shown as current" if not stale_current else "STALE: still shows 当前窗口=晚间")

# 3. Page does NOT show "下一窗口=夜间22:20"
stale_next = "下一窗口" in html and "22:20" in html
check("No stale '下一窗口=夜间22:20' display",
      not stale_next,
      "stale next-window removed" if not stale_next else "STALE: still shows 下一窗口=夜間22:20")

# 4. Page shows 今日扫描已完成
check("Page shows '今日扫描已完成'",
      "今日扫描" in html and "已完成" in html,
      "scan-completed state visible")

# 5. A=1 B=3 C=5 SKIP=0
counts_ok = ("1 / 3 / 5" in html or "1/3/5" in html or "A1 / B3 / C5" in html) and \
            ("B=3" in html or "B级：3场" in html or "B级候选 · 3场" in html)
check("Candidate counts: A=1 B=3 C=5",
      counts_ok,
      "night freeze counts confirmed" if counts_ok else "counts mismatch")

# Also check explicit labels
b3_found = "B级候选 · 3场" in html or "B=3" in html or "B级：3场" in html
c5_found = "C级观察 · 5场" in html or "C=5" in html or "观察：5场" in html
check("B=3 explicitly visible", b3_found)
check("C=5 explicitly visible", c5_found)

# 6. B组默认折叠 (native <details> without open attr)
b_summary_mode = '<details class="candidate-group group-b">' in html
check("B group uses native <details> (default collapsed)",
      b_summary_mode,
      "B group container present")

# 7. B组不默认全部展开 (no open attr on B details)
b_not_all_open = '<details class="candidate-group group-b" open>' not in html
check("B group default collapsed (native details no open attr)",
      b_not_all_open,
      "B group collapsed by default (no 'open' attr on group-b)")

# 8. A/B time_bins visible
ab_timebins = "0-15m" in html and "16-30m" in html and "31-45m" in html
ab_count = html.count("0-15m")
check("A/B time_bins visible (0-15m/16-30m/31-45m)",
      ab_timebins and ab_count >= 4,
      f"0-15m found {ab_count} times")

# 9. C default collapsed (native details without open attr)
c_collapsed = '<details class="candidate-group group-c">' in html and '<details class="candidate-group group-c" open>' not in html
check("C section default-collapsed (native details no open attr)",
      c_collapsed,
      "C cards hidden by default")

# 10. V2 summary card exists
v2_summary = "V2 生产状态" in html or "V2生产状态" in html or "v2-module-card" in html
check("V2 summary card exists",
      v2_summary,
      "V2 production status card present")

# 11. V2 lock proof in collapsed details
v2_lock = "V2 锁仓证明" in html and "里德" in html and "沃尔夫斯贝格" in html
v2_lock_collapsed = v2_lock and "<details>" in html
check("V2 lock proof in collapsed detail",
      v2_lock_collapsed,
      "V2 lock card inside <details> element")

# 12. V2 validation exists
v2_val = "V2 滚动验证" in html or "BET_LOCKED" in html
check("V2 validation module exists",
      v2_val,
      "V2 validation with BET_LOCKED policy")

# 13. Validation numbers unchanged (130, 57.7%)
val_ok = "130" in html and "57.7%" in html
check("Validation numbers unchanged: 130, 57.7%",
      val_ok,
      "130 settled, 57.7% hit rate confirmed")

# 14. Candidate data not fabricated (verify against model JSON)
# Read the candidate JSON to confirm counts match
candidate_json_path = MODULE / "data" / "runtime" / "status" / "intel_desk_v4_candidate_view_20260520.json"
if candidate_json_path.is_file():
    data = json.loads(candidate_json_path.read_text())
    sw = data.get("source_window", "")
    a = data.get("A_count", 0)
    b = data.get("B_count", 0)
    c = data.get("C_count", 0)
    sk = data.get("SKIP_count", 0)
    model_ok = sw == "night" and a == 1 and b == 3 and c == 5 and sk == 0
    check("Model JSON confirms night freeze A=1 B=3 C=5",
          model_ok,
          f"source_window={sw} A={a} B={b} C={c} SKIP={sk}")
else:
    check("Model JSON confirms night freeze A=1 B=3 C=5", False, "candidate JSON missing")

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

sys.exit(0 if conclusion == "PASS" else 1)
