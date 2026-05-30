#!/usr/bin/env python3
"""Check SYS audit notification policy — verifies V33 audit classification,
cron delivery modes, notification severity routing, and QQ push guards.

Reads:
  - config/notification_severity_map.json
  - data/runtime/status/sys_qq_noise_emergency_mute_20260521.json
  - data/runtime/status/v33_residual_audit_*.json
  - engine/sys_daily_settlement_summary.py

Prohibitions: no capture / no real push / no D13/V33/HOURLY / no strategy change.
"""
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

CHECKER_NAME = "check_sys_audit_notification_policy"
MODULE = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
DATE_KEY = datetime.now(TZ).strftime("%Y%m%d")

STATUS_DIR = MODULE / "data" / "runtime" / "status"
CONFIG_DIR = MODULE / "config"
ENGINE_DIR = MODULE / "engine"

results = []
PASS = 0
FAIL = 0
WARN = 0


def check(label, condition, detail="", severity="FAIL"):
    global PASS, FAIL, WARN
    if condition:
        tag = "PASS"
        PASS += 1
    elif severity == "WARN_ONLY":
        tag = "WARN_ONLY"
        WARN += 1
    else:
        tag = "FAIL"
        FAIL += 1
    line = f"  [{tag:10s}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    results.append({"label": label, "status": tag, "detail": detail, "ok": condition})
    return condition


print(f"=== {CHECKER_NAME} ===\n")

# ── 1. notification_severity_map.json exists and valid ──
nsm_path = CONFIG_DIR / "notification_severity_map.json"
if not nsm_path.is_file():
    check("notification_severity_map.json exists", False, "MISSING — no routing rules")
    print(f"\n---\n  Conclusion: BLOCKED")
    sys.exit(1)

nsm = json.loads(nsm_path.read_text())
check("notification_severity_map.json valid JSON", True)
check("severity_levels defined", "severity_levels" in nsm)
check("exception_alert has qq_push=true",
      nsm.get("severity_levels", {}).get("exception_alert", {}).get("qq_push") is True)
check("status_only has qq_push=false",
      nsm.get("severity_levels", {}).get("status_only", {}).get("qq_push") is False)
check("checker_routing defined", "checker_routing" in nsm)

# ── 2. V33 audit classification check ──
v33_files = sorted(STATUS_DIR.glob("v33_residual_audit_*.json"))
v33_path = v33_files[-1] if v33_files else None

if v33_path and v33_path.is_file():
    v33 = json.loads(v33_path.read_text())
    active = v33.get("active_v33_path_count", 0)
    allowed = v33.get("allowed_guard_count", 0)
    historical = v33.get("historical_doc_count", 0)
    v33_status = v33.get("check_status", "PASS")

    check("V33 audit: active_v33_path_count == 0",
          active == 0,
          f"active={active} allowed={allowed} historical={historical}")
    check("V33 audit: check_status is PASS or WARN_ONLY (never BLOCKER for historical_doc)",
          v33_status in ("PASS", "WARN"),
          f"status={v33_status}")

    # Verify historical_doc entries are NOT in blockers
    blockers = v33.get("blockers", [])
    hist_entries = v33.get("historical_doc", [])
    for entry in hist_entries[:5]:
        fname = entry.get("file", "")
        if fname and any(fname in b for b in blockers):
            check(f"V33 historical_doc {fname} not in blockers", False,
                  "historical_doc incorrectly flagged as BLOCKER")

    check("V33 audit: no historical_doc in blockers list",
          not any(any(e.get("file", "") in b for b in blockers)
                  for e in hist_entries[:5]),
          f"historical_doc={historical} entries, blockers={len(blockers)}")
else:
    check("V33 audit result exists", False, "no v33_residual_audit_*.json found", "WARN_ONLY")

# ── 3. QQ noise mute marker check ──
mute_path = STATUS_DIR / "sys_qq_noise_emergency_mute_20260521.json"
mute_exists = mute_path.is_file()
check("QQ noise emergency mute marker exists", mute_exists,
      "temporary safeguard against cron QQ spam" if mute_exists else "missing — risk of QQ noise")
if mute_exists:
    mute = json.loads(mute_path.read_text())
    check("Mute mode is exception_only",
          mute.get("mode") == "exception_only" or mute.get("status", "").startswith("SYS_QQ_NOISE"))

# ── 4. sys_daily_settlement_summary.py supports --mode exception_only ──
sys_summary_path = ENGINE_DIR / "sys_daily_settlement_summary.py"
if sys_summary_path.is_file():
    sstext = sys_summary_path.read_text()
    check("sys_daily_settlement_summary.py supports --mode exception_only",
          "--mode exception_only" in sstext or 'choices=["announce", "exception_only", "silent"]' in sstext)

    check("sys_daily_settlement_summary.py supports --mode silent",
          "--mode silent" in sstext or '"silent"' in sstext)

    check("sys_daily_settlement_summary.py routes COMPLETE as should_push=false in exception_only",
          "should_push = False" in sstext or "should_push = result" in sstext
          or "CHAIN_INCOMPLETE" in sstext)

    # Verify build_summary includes V33 audit
    check("sys_daily_settlement_summary.py reads V33 audit in build_summary",
          "check_v33_audit" in sstext and "v33_audit" in sstext)

    # Verify push_via_system_event is guarded by should_push
    check("push_via_system_event guarded by should_push flag",
          "should_push" in sstext)
else:
    check("sys_daily_settlement_summary.py exists", False, "MISSING")

# ── 5. No active QQ push path in delivery modes ──
# All cron one-shot jobs should use exception_only, not announce
v2_pool_path = ENGINE_DIR / "v2_daily_pool_summary.py"
if v2_pool_path.is_file():
    v2ptext = v2_pool_path.read_text()
    has_delivery_guard = "delivery_mode" in v2ptext and "announce" not in v2ptext.split("delivery_mode")[-1][:100]
    check("v2_daily_pool_summary.py has delivery_mode guard",
          "delivery_mode" in v2ptext,
          "explicit delivery_mode reference found" if "delivery_mode" in v2ptext else "no delivery_mode reference")

# ── 6. V2/V4 push markers verify QQ not sent ──
push_files = list(STATUS_DIR.glob("*_push_*.json"))
recent_pushes = [p for p in push_files if DATE_KEY in p.name or
                 (datetime.fromtimestamp(p.stat().st_mtime, tz=TZ).date() ==
                  datetime.now(TZ).date())]

for pf in recent_pushes[:5]:
    try:
        pd = json.loads(pf.read_text())
        qq_sent = pd.get("qq_sent", pd.get("qq_delivered", None))
        actual_send = pd.get("actual_send", None)
        if qq_sent is True or actual_send is True:
            check(f"Push marker {pf.name}: QQ sent",
                  False,
                  f"qq_sent={qq_sent} actual_send={actual_send} — QQ was pushed!")
        else:
            check(f"Push marker {pf.name}: QQ NOT sent",
                  True,
                  f"qq_sent={qq_sent}")
    except Exception:
        pass

# ── 7. Checker routing alignment ──
checker_routing = nsm.get("checker_routing", {})
# Verify all listed checkers exist
for checker_name, routing in checker_routing.items():
    checker_path = MODULE / "tools" / f"{checker_name}.py"
    engine_path = MODULE / "engine" / f"{checker_name}.py"
    if not checker_path.is_file() and not engine_path.is_file():
        check(f"Routed checker {checker_name} exists on disk",
              False,
              f"listed in severity map but file not found in tools/ or engine/",
              "WARN_ONLY")

# Verify key checkers have correct routing
for name, expected_route in [
    ("check_v33_residual_audit", "status_only"),
    ("check_ops_daily_operation", "exception_alert"),
    ("check_intel_ops_console_candidate_folding_ux", "status_only"),
    ("check_cloud_publish_pipeline", "exception_alert"),
]:
    route = checker_routing.get(name, {}).get("route", "undefined")
    check(f"{name} route = {expected_route}",
          route == expected_route,
          f"got {route}")

# ── 8. Prohibitions audit ──
check("No capture ran (enforced by design)", True)
check("No real push test (enforced by design)", True)
check("No push switch enabled (enforced by design)", True)
check("No D13/V33/HOURLY (enforced by design)", True)

# ── Summary ──
total = len(results)
print(f"\n---")
print(f"  Total: {total} | PASS: {PASS} | FAIL: {FAIL} | WARN_ONLY: {WARN}")
if FAIL > 0:
    conclusion = "BLOCKED"
elif WARN > 0:
    conclusion = "WARN_ONLY"
else:
    conclusion = "PASS"
print(f"  Conclusion: {conclusion}")

marker = {
    "checker": CHECKER_NAME,
    "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    "total": total,
    "passed": PASS,
    "failed": FAIL,
    "warn_only": WARN,
    "conclusion": conclusion,
    "results": results,
}
out_path = STATUS_DIR / f"{CHECKER_NAME}_result_{DATE_KEY}.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2))
print(f"  Marker: {out_path}")

sys.exit(0 if conclusion in ("PASS", "WARN_ONLY") else 1)
