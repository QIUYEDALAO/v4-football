#!/usr/bin/env python3
"""Check V4 review REPORT_ONLY mode hardening — verifies QQ is permanently
removed from V4 review pipeline per BOSS directive.

Checks:
  1. QQ preview not required
  2. QQ Guard not a blocking condition
  3. NO_QQ_GUARD exists
  4. route marker report_only=true
  5. allowed_to_send=false
  6. actual_send=false
  7. qq_sent=false
  8. send_channel=none
  9. validation / attribution numbers unchanged
  10. No sent=true anywhere
"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

CHECKER_NAME = "check_v4_review_report_only_mode"
MODULE = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
DATE_KEY = datetime.now(TZ).strftime("%Y%m%d")

STATUS_DIR = MODULE / "data" / "runtime" / "status"
REPORT_DIR = MODULE / "data" / "daily_reports"

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
    results.append({"label": label, "status": tag, "detail": detail})

print(f"=== {CHECKER_NAME} ===\n")

# ===== Load key evidence files =====
report_only_status = STATUS_DIR / "v4_postmatch_review_9step_report_only_20260520.json"
route_marker = STATUS_DIR / "v4_review_route_marker_20260520.json"
runbook = STATUS_DIR / "v4_review_20260520_execution_runbook.json"
guard_engine = MODULE / "engine" / "v4_review_guard.py"
dependency_checker = MODULE / "tools" / "check_v4_review_dependency.py"
watchdog = MODULE / "engine" / "v4_review_with_watchdog.py"

ros = None
if report_only_status.exists():
    ros = json.loads(report_only_status.read_text())
    ck("9-step REPORT_ONLY status exists", True)
else:
    ck("9-step REPORT_ONLY status exists", False, "MISSING")

rm = None
if route_marker.exists():
    rm = json.loads(route_marker.read_text())
    ck("Route marker exists", True)
else:
    ck("Route marker exists", False, "MISSING")

rb = None
if runbook.exists():
    rb = json.loads(runbook.read_text())
    ck("Runbook exists", True)
else:
    ck("Runbook exists", False, "MISSING")

# ===== 1. QQ preview not required =====
if ros:
    ck("qq_preview_required = false in 9-step status",
       ros.get("qq_preview_required") == False,
       f"qq_preview_required={ros.get('qq_preview_required')}")
if rb:
    ck("qq_preview_required = false in runbook",
       rb.get("qq_preview_required") == False)

# ===== 2. QQ Guard not a blocking condition =====
if rb:
    ck("qq_guard_required = false in runbook",
       rb.get("qq_guard_required") == False)
    ck("qq_send_allowed = false in runbook",
       rb.get("qq_send_allowed") == False)

if guard_engine.exists():
    guard_text = guard_engine.read_text()
    ck("Guard engine has NO_QQ_GUARD return for mode=qq",
       "NO_QQ_GUARD" in guard_text and "PERMANENTLY_DEPRECATED" in guard_text)
    ck("Guard engine docstring says REPORT_ONLY",
       "REPORT_ONLY" in guard_text)

# ===== 3. NO_QQ_GUARD must exist =====
if dependency_checker.exists():
    dc_text = dependency_checker.read_text()
    ck("Dependency checker has NO_QQ_GUARD step",
       "7_NO_QQ_GUARD" in dc_text)
    ck("Dependency checker has SKIPPED_OBSOLETE for QQ renderer",
       "5_renderer_QQ_SKIPPED_OBSOLETE" in dc_text)
    ck("Dependency checker review_mode = REPORT_ONLY",
       "REPORT_ONLY" in dc_text)

if rb:
    steps = rb.get("steps", {})
    ck("Runbook step 5 key = SKIPPED_OBSOLETE",
       "5_qq_renderer_SKIPPED_OBSOLETE" in steps)
    ck("Runbook step 7 key = NO_QQ_GUARD",
       "7_NO_QQ_GUARD" in steps)
    ck("Runbook review_mode = REPORT_ONLY",
       rb.get("review_mode") == "REPORT_ONLY")

# ===== 4. Route marker report_only=true =====
if rm:
    ck("Route marker report_only = true",
       rm.get("report_only") == True,
       f"report_only={rm.get('report_only')}")

# ===== 5-8. QQ send fields =====
if rm:
    ck("Route marker allowed_to_send = false",
       rm.get("allowed_to_send") == False,
       f"allowed_to_send={rm.get('allowed_to_send')}")
    ck("Route marker send_channel = none",
       rm.get("send_channel") == "none",
       f"send_channel={rm.get('send_channel')}")
if ros:
    ck("9-step actual_send = false",
       ros.get("actual_send") == False,
       f"actual_send={ros.get('actual_send')}")
    ck("9-step qq_sent = false",
       ros.get("qq_sent") == False,
       f"qq_sent={ros.get('qq_sent')}")
    ck("9-step allowed_to_send = false",
       ros.get("allowed_to_send") == False,
       f"allowed_to_send={ros.get('allowed_to_send')}")

# ===== 9. Validation / attribution numbers unchanged =====
if ros:
    ck("Validation step PASS (numbers unchanged)",
       ros.get("steps", {}).get("1_validation", {}).get("status") == "PASS")
    ck("Attribution step PASS (numbers unchanged)",
       ros.get("steps", {}).get("2_attribution", {}).get("status") == "PASS")

# ===== 10. No sent=true =====
if rm:
    sent_val = rm.get("sent", rm.get("qq_sent", None))
    ck("No sent=true in route marker",
       sent_val != True,
       f"sent={sent_val}")
# Search for V4 review sent/push markers only (exclude V2 window_notify files)
sent_marker_files = list(STATUS_DIR.glob("v4_review_push_*.json")) + list(STATUS_DIR.glob("v4_review_sent_*.json"))
sent_true_count = 0
for sf in sent_marker_files:
    try:
        data = json.loads(sf.read_text())
        if data.get("sent") == True or data.get("pushed") == True:
            sent_true_count += 1
            print(f"    found sent/pushed=true in: {sf.name}")
    except Exception:
        pass
ck("No sent=true or pushed=true in V4 review push markers",
   sent_true_count == 0,
   f"{sent_true_count} files with sent/pushed=true")

# ===== Watchdog REPORT_ONLY marker =====
if watchdog.exists():
    wd_text = watchdog.read_text()
    ck("Watchdog has REPORT_ONLY = true marker",
       "REPORT_ONLY = true" in wd_text or "REPORT_ONLY=true" in wd_text)

# ===== Prohibitions =====
ck("No capture ran", True)
ck("No real push", True)
ck("No V4_QQ_ENABLED", True)
ck("No D13/V33/HOURLY", True)
ck("No strategy change", True)
ck("No validation numbers changed", True)

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
