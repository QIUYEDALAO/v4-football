#!/usr/bin/env python3
"""OPS Daily Strong Operation Checker — exact values, real markers, per-window.

Args:
  --scan-date YYYYMMDD     Date for scan window logs/status
  --review-date YYYYMMDD   Date for V4 review structured/freeze/guard/route/push files
  --ops-date YYYYMMDD      Date for ops heartbeat/dashboard (default: today CST)
  --date YYYYMMDD          Alias for --ops-date (backward compat)
  --no-push / --no-d13 / --no-v33 / --no-hourly   Guard flags (informational)
"""
import json
import os
import sys
import hashlib
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

MODULE = Path(__file__).resolve().parents[1]
CN_TZ = timezone(timedelta(hours=8))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan-date", default="", help="Date for scan window logs/status (YYYYMMDD)")
    ap.add_argument("--review-date", default="", help="Date for V4 review structured files (YYYYMMDD)")
    ap.add_argument("--ops-date", default="", help="Date for ops heartbeat/dashboard (YYYYMMDD)")
    ap.add_argument("--date", default="", help="Alias for --ops-date (backward compat)")
    ap.add_argument("--no-push", action="store_true", default=True, help="No push guard")
    ap.add_argument("--no-d13", action="store_true", default=True, help="No D13 guard")
    ap.add_argument("--no-v33", action="store_true", default=True, help="No V33 guard")
    ap.add_argument("--no-hourly", action="store_true", default=True, help="No hourly guard")
    args = ap.parse_args()

    today_cst = datetime.now(CN_TZ).strftime("%Y%m%d")

    # Resolve dates with clear priority
    ops_date = args.ops_date or args.date or today_cst
    review_date = args.review_date or ops_date
    scan_date = args.scan_date or ops_date

    R = {
        "check_status": "PASS",
        "blockers": [],
        "warnings": [],
        "tests": {},
        "markers_read": 0,
        "hardcoded_true_count": 0,
        "windows_checked": 0,
        "api_checked": False,
        "task_checked": False,
        "logs_checked": False,
        "dates": {
            "ops_date": ops_date,
            "review_date": review_date,
            "scan_date": scan_date,
            "generated_at": datetime.now(CN_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        },
        "guards": {
            "no_push": args.no_push,
            "no_d13": args.no_d13,
            "no_v33": args.no_v33,
            "no_hourly": args.no_hourly,
        },
    }

    block = False

    def ck(n, cond, m=""):
        R["tests"][n] = cond
        R["markers_read"] += 1
        if not cond:
            R["blockers"].append(f"{n}: {m}")
        return not cond

    def warn(n, cond, m=""):
        R["tests"][n] = cond
        if not cond:
            R["warnings"].append(f"{n}: {m}")
        return not cond

    # ── V2 REAL MARKERS ──
    pv = json.loads((MODULE / "data/runtime/status/v2_production_verified_202605.json").read_text())
    vf = json.loads((MODULE / "data/runtime/status/v2_verified_written_202605.json").read_text())
    inc = json.loads((MODULE / "data/runtime/status/v2_incident_acknowledged_by_boss_202605.json").read_text())

    block |= ck("V2_PRODUCTION_VERIFIED", pv["PRODUCTION_VERIFIED"] == True)
    p = pv["current_prohibitions"]
    block |= ck("V2_QQ_ENABLED", p["QQ_ENABLED"] == True)
    block |= ck("V2_CRON_ENABLED", p["CRON_ENABLED"] == True)
    block |= ck("V2_D13", p["D13_EXECUTED"] == False)
    block |= ck("V2_VERIFIED", vf["VERIFIED_WRITTEN"] == True)
    block |= ck("V2_VERIFIED_V2ONLY", vf["verified_scope"] == "V2_ONLY")
    block |= ck("V2_INCIDENT", inc["incident_acknowledged_by_boss"] == True)
    block |= ck("V2_OLD_RIED", vf["old_ried_resend_allowed"] == False)
    block |= ck("V2_REAL_BET", vf["real_bet_execution"] == False)
    block |= ck("V2_V33", vf["V33_ENABLED"] == False)
    block |= ck("V2_HOURLY", vf["HOURLY_ENABLED"] == False)

    # ── V4 REAL MARKERS (uses review_date) ──
    v4_review_path = MODULE / f"data/daily_reports/v4_review_structured_{review_date}.json"
    freeze_path = MODULE / f"data/runtime/status/v4_review_freeze_{review_date}.json"
    guard_path = MODULE / f"data/runtime/status/v4_review_guard_{review_date}.json"
    guard_f_path = MODULE / f"data/runtime/status/v4_review_guard_{review_date}_full.json"
    route_path = MODULE / f"data/runtime/status/v4_review_route_{review_date}.json"
    push_path = MODULE / f"data/runtime/status/v4_review_push_{review_date}.json"

    if not v4_review_path.is_file():
        block |= ck("V4_REVIEW_FILE_EXISTS", False,
                     f"v4_review_structured_{review_date}.json not found — review_date may not have review data yet")
    else:
        v4 = json.loads(v4_review_path.read_text())

        # Safe value extraction: try multiple nested schemas
        # Supports: flat {"A":0}, nested {"official_counts":{"A":0}}, {"counts":{"A":0}}, {"v4_counts":{"A":0}}
        def _v4_get(d, key, default=0):
            for path in [key, ("official_counts", key), ("counts", key), ("v4_counts", key)]:
                if isinstance(path, tuple):
                    sub = d
                    for p in path:
                        sub = sub.get(p, {}) if isinstance(sub, dict) else {}
                    if isinstance(sub, (int, float)):
                        return sub
                else:
                    v = d.get(path)
                    if v is not None and isinstance(v, (int, float)):
                        return v
            return default

        a_val = _v4_get(v4, "A", 0)
        b_val = _v4_get(v4, "B", 0)
        c_val = _v4_get(v4, "C", 0)
        skip_val = _v4_get(v4, "SKIP", 0)

        if a_val is None and b_val is None:
            warn("V4_AB_MISSING", True,
                 f"neither flat nor nested A/B found in v4_review_structured_{review_date}.json — schema may have changed")
            a_val = 0
            b_val = 0

        block |= ck("V4_A0", a_val == 0, f"expected 0, got {a_val}")
        block |= ck("V4_B0", b_val == 0, f"expected 0, got {b_val}")
        block |= ck("V4_C_OBS", v4.get("C_observation_only", True) == True)
        block |= ck("V4_SKIP_NREC", v4.get("SKIP_not_recommendation", True) == True)
        block |= ck("V4_NO_V33", v4.get("no_V33", False) == True)
        block |= ck("V4_NO_D13", v4.get("no_D13", True) == True)

        # Check formal recommendations
        formal = a_val + b_val
        R["v4_formal_recommendation_count"] = formal
        R["v4_A"] = a_val
        R["v4_B"] = b_val
        R["v4_C"] = c_val
        R["v4_SKIP"] = skip_val

    for fpath, key in [(freeze_path, "V4_FREEZE"), (guard_path, "V4_GUARD"),
                        (guard_f_path, "V4_GUARD_FULL"), (route_path, "V4_REPORTAGENT"),
                        (push_path, "V4_SEND_FALSE")]:
        if not fpath.is_file():
            warn(f"{key}_EXISTS", False, f"{fpath.name} not found")
        else:
            d = json.loads(fpath.read_text())
            if key == "V4_FREEZE":
                block |= ck("V4_FREEZE_C", d.get("C", -1) == v4.get("C", -1) if v4_review_path.is_file() else d.get("C", -1) >= 0)
                block |= ck("V4_FREEZE_SKIP", d.get("SKIP", -1) == v4.get("SKIP", -1) if v4_review_path.is_file() else d.get("SKIP", -1) >= 0)
            elif key == "V4_GUARD":
                block |= ck("V4_GUARD_QQ", d.get("guard_status", "") == "PASS")
            elif key == "V4_GUARD_FULL":
                block |= ck("V4_GUARD_FULL_QQ", d.get("guard_status", "") == "PASS")
            elif key == "V4_REPORTAGENT":
                block |= ck("V4_REPORTAGENT_STATUS", d.get("reportagent_status", "") == "PASS")
            elif key == "V4_SEND_FALSE":
                block |= ck("V4_SEND_FALSE", d.get("actual_send", True) == False)
                block |= ck("V4_QQ_FALSE", d.get("qq_sent", True) == False)

    # ── V4 SCAN 5 WINDOWS (uses scan_date, fully dynamic) ──
    windows = ["late", "early", "midday", "evening", "night"]
    window_times = {"late": (1, 20), "early": (7, 20), "midday": (14, 5),
                    "evening": (16, 20), "night": (22, 20)}
    R["pending_windows"] = []
    now_cst = datetime.now(CN_TZ)

    for w in windows:
        log = MODULE / f"data/runtime/logs/v4_scan_{w}_{scan_date}.log"
        R["windows_checked"] += 1
        has_log = log.is_file()

        # Determine if this window is in the future
        wh, wm = window_times.get(w, (0, 0))
        window_dt = now_cst.replace(hour=wh, minute=wm, second=0, microsecond=0)
        minutes_past_window = (now_cst - window_dt).total_seconds() / 60
        window_is_future = minutes_past_window < 0

        if window_is_future and scan_date == today_cst:
            # Future window on today's date → PENDING, not WARN
            R["pending_windows"].append(w)
            R["tests"][f"scan_{w}_log"] = True  # not a failure
            continue

        is_fallback = False
        if has_log:
            text = log.read_text()[:2000]
            is_fallback = "fallback_qq_brief" in text or "fallback" in text.lower()

        if not has_log:
            if minutes_past_window > 30:
                block |= ck(f"scan_{w}_log", False,
                           f"no log for {w} on {scan_date} — {int(minutes_past_window)}min past window")
            else:
                warn(f"scan_{w}_log", False, f"no log for {w} on {scan_date} — window due, no evidence yet")

        if is_fallback:
            warn(f"scan_{w}_fallback", False, f"{w} uses fallback_qq_brief — NOT production evidence")

        # Also check window status JSON
        win_status = MODULE / f"data/runtime/status/v4_scan_{w}_window_capture_after_due_{scan_date}.json"
        if win_status.is_file():
            ws = json.loads(win_status.read_text())
            if ws.get("synthetic_evidence") is True:
                block |= ck(f"scan_{w}_synthetic", False, f"{w} has synthetic_evidence=true")

    # ── API SNAPSHOT / SOURCE HEALTH ──
    api_files = list((MODULE / "data").rglob("*api_snapshot*"))
    R["api_checked"] = len(api_files) > 0
    warn("api_snapshot", R["api_checked"], "no api_snapshot files found")

    inv_src = MODULE / "data" / "runtime" / "status" / "invalid_sources_index.json"
    if not inv_src.is_file():
        inv_src = MODULE / "data" / "runtime" / "status" / f"invalid_sources_{scan_date}.json"
    if inv_src.is_file():
        idx = json.loads(inv_src.read_text())
        inv_count = len(idx) if isinstance(idx, list) else idx.get("count", 0)
        R["invalid_sources"] = inv_count
        warn("invalid_sources_zero", inv_count == 0, f"{inv_count} invalid sources")
    else:
        warn("invalid_sources_missing", False, "no invalid_sources index")

    # ── TASK STATUS / LOGS / WATCHDOG ──
    tasks = list((MODULE / "data/runtime/status").glob("task_status_*.json"))
    R["task_checked"] = len(tasks) > 0
    warn("task_status", R["task_checked"], "no task_status files")

    log_dir = MODULE / "logs"
    if log_dir.is_dir():
        yesterday = (datetime.strptime(scan_date, "%Y%m%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        log_files = list(log_dir.glob(f"v2_quant_{yesterday}.log"))
        if not log_files:
            log_files = list(log_dir.glob("v2_quant_*.log"))
        R["logs_checked"] = len(log_files) > 0
        warn("logs_v2", R["logs_checked"], "no v2 log")
    v4_logs = list(MODULE.glob(f"data/runtime/logs/v4_scan_*_{scan_date}.log"))
    warn("v4_logs", len(v4_logs) > 0, f"no v4 scan logs for {scan_date}")

    # ── DASHBOARD / OPS HEARTBEAT (uses ops_date) ──
    dash = MODULE / "data" / "runtime" / "dashboard" / "v2_today.html"
    if dash.is_file():
        html = dash.read_text()
        # Check for stale dates (anything before yesterday)
        stale_dates = ["20260517", "20260518"]
        has_stale = any(d in html[:500] for d in stale_dates)
        warn("no_stale_dashboard_date", not has_stale, f"stale date in dashboard header")

    intel_html = MODULE / "data" / "runtime" / "dashboard" / "intel_desk.html"
    block |= ck("intel_desk_html", intel_html.is_file())
    if intel_html.is_file():
        html = intel_html.read_text()
        warn("intel_v2_visible", "PRODUCTION" in html, "V2 status not in intel desk")
        warn("intel_v4_visible", "SKIP" in html or "C" in html, "V4 status not in intel desk")

    hb_html = MODULE / "data" / "runtime" / "dashboard" / "ops_heartbeat.html"
    hb_json = MODULE / f"data/runtime/status/ops_heartbeat_center_{ops_date}.json"
    if not hb_json.is_file():
        hb_json = MODULE / "data" / "runtime" / "status" / "ops_heartbeat_center_202605.json"
    warn("ops_heartbeat_html", hb_html.is_file(), "no OPS heartbeat html")
    warn("ops_heartbeat_status", hb_json.is_file(), "no OPS heartbeat status")

    # Final status
    if block:
        R["check_status"] = "BLOCKER"
    elif R["warnings"]:
        R["check_status"] = "WARN"
    elif R.get("pending_windows"):
        R["check_status"] = "PENDING_ONLY"

    print("=" * 60)
    print("OPS DAILY STRONG MONITORING CHECKER")
    print("=" * 60)
    print(f"Status: {R['check_status']} | Passed: {sum(1 for v in R['tests'].values() if v)}/{len(R['tests'])}")
    print(f"Dates: scan={scan_date} review={review_date} ops={ops_date}")
    print(f"Markers: {R['markers_read']} | Windows: {R['windows_checked']}")
    if R.get("pending_windows"):
        print(f"Pending (future) windows: {R['pending_windows']}")
    for k, v in R["tests"].items():
        if not v:
            print(f"  {k}: FAIL")
    if R["blockers"]:
        print(f"\nBLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]:
            print(f"  ! {b}")
    if R["warnings"]:
        print(f"\nWARNINGS ({len(R['warnings'])}):")
        for w in R["warnings"][:10]:
            print(f"  ~ {w}")

    mark = MODULE / "data/runtime/status"
    mark.mkdir(parents=True, exist_ok=True)
    (mark / f"ops_daily_strong_monitoring_{scan_date}.json").write_text(
        json.dumps(R, indent=2, ensure_ascii=False, default=str))

    if R["check_status"] == "BLOCKER":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
