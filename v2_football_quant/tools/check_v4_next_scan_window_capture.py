#!/usr/bin/env python3
"""V4 Window-Specific Capture Checker — requires window evidence, not just date-level scout"""
import argparse, json, os, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
SCAN_RUNNER = MODULE / "engine" / "v4_scan_and_brief.py"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--window", required=True, choices=["late","early","midday","evening","night"])
    p.add_argument("--scan-date", required=True)
    p.add_argument("--preflight", action="store_true")
    p.add_argument("--no-push", action="store_true", default=True)
    p.add_argument("--no-d13", action="store_true", default=True)
    p.add_argument("--no-v33", action="store_true", default=True)
    p.add_argument("--no-hourly", action="store_true", default=True)
    args = p.parse_args()

    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    windows = {"late":(1,20),"early":(7,20),"midday":(14,5),"evening":(16,20),"night":(22,20)}
    h,m = windows.get(args.window, (0,0))
    sched = now.replace(hour=h, minute=m, second=0, microsecond=0)
    window_due = now >= sched
    minutes_past = (now - sched).total_seconds() / 60 if window_due else 0

    result = {
        "window": args.window, "scan_date": args.scan_date,
        "checked_at": now.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "window_due": window_due, "capture_ran": False,
        "synthetic_evidence_written": False, "production_evidence": False,
        "date_level_scout_only": False, "window_specific_required": True,
        "late_as_early_blocked": True,
        "A": None, "B": None, "C": None, "SKIP": None, "total": None,
        "formal_recommendation_count": 0, "future_ab_trigger": False,
        "actual_send": False, "qq_sent": False, "fallback_used": False,
        "no_push": True, "no_d13": True, "no_v33": True, "no_hourly": True,
        "status": "WAIT", "blockers": [], "warnings": []
    }

    # Paths
    scout_path = MODULE / f"data/daily_reports/scout_v4_{args.scan_date}.json"
    win_log = MODULE / f"data/runtime/logs/v4_scan_{args.window}_{args.scan_date}.log"
    win_status = MODULE / f"data/runtime/status/v4_scan_{args.window}_window_capture_after_due_{args.scan_date}.json"
    win_push = MODULE / f"data/runtime/status/v4_scan_{args.window}_push_{args.scan_date}.json"

    # Preflight: paths check only
    if args.preflight:
        result["scan_runner_exists"] = SCAN_RUNNER.is_file()
        result["window_log_path"] = str(win_log)
        result["window_status_path"] = str(win_status)
        result["scout_path"] = str(scout_path)
        result["status"] = "PENDING" if not window_due else "DUE"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # Not yet due → WAIT
    if not window_due:
        result["minutes_to_window"] = int((sched - now).total_seconds() / 60)
        result["status"] = "WAIT"
        print(json.dumps(result, ensure_ascii=False))
        return 0

    # ── WINDOW DUE ──
    # Check for WINDOW-SPECIFIC evidence (not just date-level scout)
    has_scout = scout_path.is_file()
    has_win_log = win_log.is_file()
    has_win_status = win_status.is_file()
    
    # Verify window-specific files belong to THIS window
    win_evidence_ok = False
    if has_win_log:
        log_content = win_log.read_text()[:500]
        win_evidence_ok = f"scan_{args.window}" in log_content or args.window in log_content.lower()
    if has_win_status and not win_evidence_ok:
        try:
            ws = json.loads(win_status.read_text())
            win_evidence_ok = ws.get("window") == args.window
        except: pass

    # Date-level scout alone → WARN (not enough)
    if has_scout and not win_evidence_ok:
        result["date_level_scout_only"] = True
        result["status"] = "WARN"
        result["warnings"].append(f"date-level scout exists but no {args.window}-specific evidence. scout alone ≠ production_evidence for {args.window}")
        # Still read grades from scout for reporting
        try:
            scout = json.loads(scout_path.read_text())
            matches = scout if isinstance(scout, list) else scout.get("matches", [])
            grades = {}
            for m in matches:
                g = m.get("grade", m.get("pre_grade", m.get("ht_recommendation", "")))
                grades[g] = grades.get(g, 0) + 1
            result["A"] = grades.get("A", 0); result["B"] = grades.get("B", 0)
            result["C"] = grades.get("C", 0); result["SKIP"] = grades.get("SKIP", 0) + grades.get("HT_SKIP", 0)
            result["total"] = sum(grades.values())
            result["formal_recommendation_count"] = result["A"] + result["B"]
        except: result["warnings"].append("scout_parse_failed")
        result["production_evidence"] = False
        print(json.dumps(result, ensure_ascii=False))
        return 0

    # Window-specific evidence exists → read real data
    if has_scout and win_evidence_ok:
        result["capture_ran"] = True
        result["production_evidence"] = True
        try:
            scout = json.loads(scout_path.read_text())
            matches = scout if isinstance(scout, list) else scout.get("matches", [])
            grades = {}
            for m in matches:
                g = m.get("grade", m.get("pre_grade", m.get("ht_recommendation", "")))
                grades[g] = grades.get(g, 0) + 1
            result["A"] = grades.get("A", 0); result["B"] = grades.get("B", 0)
            result["C"] = grades.get("C", 0); result["SKIP"] = grades.get("SKIP", 0) + grades.get("HT_SKIP", 0)
            result["total"] = sum(grades.values())
            result["formal_recommendation_count"] = result["A"] + result["B"]
            result["future_ab_trigger"] = result["formal_recommendation_count"] > 0
        except Exception as e:
            result["warnings"].append(f"scout_parse: {e}")

        # Read push/shadow marker
        if win_push.is_file():
            push = json.loads(win_push.read_text())
            result["actual_send"] = push.get("actual_send", False)
            result["qq_sent"] = push.get("qq_sent", False)

        result["status"] = "PASS" if not result["warnings"] else "WARN"
        print(json.dumps(result, ensure_ascii=False))
        return 0

    # No evidence at all → try runner or BLOCKER
    if SCAN_RUNNER.is_file() and minutes_past <= 30:
        env = {**os.environ, "OPENCLAW_NO_PUSH": "1", "V2_OBSERVE_ONLY": "1"}
        r = subprocess.run(["python3", str(SCAN_RUNNER)], capture_output=True, text=True,
                          timeout=120, cwd=str(MODULE), env=env)
        result["capture_ran"] = True
        result["scan_runner_rc"] = r.returncode
        # Re-check after runner
        if scout_path.is_file():
            result["status"] = "WARN"
            result["warnings"].append("runner_ran_but_no_window_specific_marker_yet")
        else:
            result["status"] = "WARN"
            result["warnings"].append("runner_ran_no_output")
    else:
        if minutes_past > 30:
            result["status"] = "BLOCKER"
            result["blockers"].append(f"{args.window} {int(minutes_past)}min past, no evidence")
        else:
            result["status"] = "WARN"
            result["warnings"].append("no evidence, runner not available")

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] in ("PASS","WARN","WAIT") else (2 if result["status"]=="BLOCKER" else 1)

if __name__=="__main__": sys.exit(main())
