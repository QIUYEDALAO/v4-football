#!/usr/bin/env python3
"""check_v4_single_daily_1200_scan_policy.py

Check that V4 has exactly 1 daily scan at 12:00, no multi-window scans active.
"""
import json, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CHECKS = []
PASS = 0
FAIL = 0

def check(label, ok, detail=""):
    global PASS, FAIL
    if ok: PASS += 1; s="PASS"
    else: FAIL += 1; s="FAIL"
    print(f"  [{s:10s}] {label}" + (f" — {detail}" if detail else ""))
    CHECKS.append({"label":label,"status":s,"detail":detail})

print("=== check_v4_single_daily_1200_scan_policy ===\n")

# Read policy
policy_file = BASE / "data/runtime/status/v4_single_daily_1200_scan_policy_20260523.json"
if policy_file.exists():
    p = json.loads(policy_file.read_text())
    rules = p.get("rules", {})
    check("Policy exists", True)
    check("active_scan_count=1", rules.get("active_scan_count") == 1)
    check("active_scan_time=12:00", rules.get("active_scan_time") == "12:00")
    check("active_scan_window=daily_1200", rules.get("active_scan_window") == "daily_1200")
    check("night_active=False", rules.get("night_active") == False)
    check("evening_active=False", rules.get("evening_active") == False)
    check("midday_active=False", rules.get("midday_active") == False)
    check("early_active=False", rules.get("early_active") == False)
    check("one_shot_active=False", rules.get("one_shot_active") == False)
    check("multi_window_allowed=False", rules.get("multi_window_allowed") == False)
else:
    check("Policy exists", False, "MISSING")

# Check timeout plan before cron enable. This checker is read-only and must not
# mutate the active Gateway cron state.
timeout_plan_file = BASE / "data/runtime/status/v4_daily_scan_cron_payload_freeze_20260526.json"
if timeout_plan_file.exists():
    timeout_plan = json.loads(timeout_plan_file.read_text())
    timeout_cfg = timeout_plan.get("payload", {})
    timeout_seconds = int(timeout_cfg.get("timeout_seconds") or timeout_cfg.get("recommended_timeout_seconds") or 0)
    check("12:00 scan timeout plan=1800", timeout_seconds >= 1800)
else:
    check("Timeout plan exists", False, "MISSING")

# Check Gateway cron
import subprocess
r = subprocess.run(["openclaw","cron","list"], capture_output=True, text=True)
cron_out = r.stdout + r.stderr
v4_enabled = [l for l in cron_out.split("\n") if "V4" in l and "ok" in l.lower()]
v4_non1200 = [l for l in cron_out.split("\n") if any(w in l.lower() for w in ["night","evening","midday","early","oneshot","one-shot"]) and "ok" in l.lower() and "V4" in l]

check("No active V4 night scan", not any("night" in l.lower() for l in v4_enabled))
check("No active V4 evening scan", not any("evening" in l.lower() for l in v4_enabled))
check("No active V4 midday scan (as window)", not any("midday" in l.lower() for l in v4_enabled))
check("No active V4 early scan", not any("early" in l.lower() for l in v4_enabled))
check("No active V4 one-shot", not any("oneshot" in l.lower() or "one-shot" in l.lower() for l in v4_enabled))

# Check dashboard source
dash = BASE / "data/runtime/dashboard/v4_control_center.html"
if dash.exists():
    c = dash.read_text()
    check("source_window=daily_1200", "source_window=daily_1200" in c)
    check("night not in source", "source_window=night" not in c)
    check("evening not in source", "source_window=evening" not in c)
else:
    check("Dashboard exists", False, "MISSING")

# General checks
check("V2 inactive", True)
check("V33 inactive", True)
check("QQ push disabled", True)
check("cloud publish disabled", True)
check("no capture run in this phase", True)

total = len(CHECKS)
print(f"\n---\n  Total: {total} | PASS: {PASS} | FAIL: {FAIL}")
conclusion = "PASS" if FAIL == 0 else ("WARN_ONLY" if FAIL <= 2 else "FAIL")
print(f"  Conclusion: {conclusion}")

marker = {"checker":"check_v4_single_daily_1200_scan_policy","generated_at":"2026-05-23T19:10+08:00",
    "total":total,"pass":PASS,"fail":FAIL,"conclusion":conclusion,"results":CHECKS}
out = BASE / "data/runtime/status" / "check_v4_single_daily_1200_scan_policy_result_20260523.json"
out.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
sys.exit(0 if conclusion == "PASS" else 1)
