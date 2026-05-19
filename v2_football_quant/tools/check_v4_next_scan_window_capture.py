#!/usr/bin/env python3
"""V4 Next Scan Window Capture Checker — reads REAL scan output, NEVER writes synthetic evidence"""
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

    result = {
        "window": args.window, "scan_date": args.scan_date,
        "checked_at": now.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "window_due": now >= sched,
        "capture_ran": False, "synthetic_evidence_written": False,
        "production_evidence": False, "hardcoded_counts": False,
        "A": None, "B": None, "C": None, "SKIP": None,
        "actual_send": False, "qq_sent": False,
        "fallback_used": False, "no_push": True,
        "no_d13": True, "no_v33": True, "no_hourly": True,
        "status": "WAIT", "blockers": [], "warnings": []
    }

    # Preflight: only check paths, never run
    if args.preflight:
        result["status"] = "PENDING" if not result["window_due"] else "DUE"
        result["capture_ran"] = False
        result["synthetic_evidence_written"] = False
        result["scan_runner_exists"] = SCAN_RUNNER.is_file()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # Not yet due → WAIT
    if not result["window_due"]:
        mins = int((sched - now).total_seconds() / 60)
        result["minutes_to_window"] = mins
        result["next_run_time"] = sched.strftime("%Y-%m-%d %H:%M CST")
        result["status"] = "WAIT"
        print(json.dumps(result, ensure_ascii=False))
        return 0

    # Window due → check if real evidence already exists
    scout_path = MODULE / f"data/daily_reports/scout_v4_{args.scan_date}.json"
    log_path = MODULE / f"data/runtime/logs/v4_scan_{args.window}_{args.scan_date}.log"
    push_path = MODULE / f"data/runtime/status/v4_scan_{args.window}_push_{args.scan_date}.json"

    if scout_path.is_file():
        # Real evidence exists — read it
        result["capture_ran"] = True
        result["production_evidence"] = True
        try:
            scout = json.loads(scout_path.read_text())
            matches = scout if isinstance(scout, list) else scout.get("matches", [])
            grades = {}
            for m in matches:
                g = m.get("grade", m.get("pre_grade", m.get("ht_recommendation", "")))
                grades[g] = grades.get(g, 0) + 1
            result["A"] = grades.get("A", 0)
            result["B"] = grades.get("B", 0)
            result["C"] = grades.get("C", 0)
            result["SKIP"] = grades.get("SKIP", 0) + grades.get("HT_SKIP", 0)
            result["total"] = sum(grades.values())
            result["hardcoded_counts"] = False
        except:
            result["warnings"].append("scout_parse_failed")
        
        if push_path.is_file():
            push = json.loads(push_path.read_text())
            result["actual_send"] = push.get("actual_send", False)
            result["qq_sent"] = push.get("qq_sent", False)
        
        result["status"] = "PASS" if not result["warnings"] else "WARN"
        print(json.dumps(result, ensure_ascii=False))
        return 0

    # No real evidence → try running scan runner (readonly)
    if SCAN_RUNNER.is_file():
        minutes_past = (now - sched).total_seconds() / 60
        if minutes_past > 30:
            result["status"] = "BLOCKER"
            result["blockers"].append(f"{args.window} window {int(minutes_past)}min past, no evidence, no runner output")
            print(json.dumps(result, ensure_ascii=False))
            return 2
        
        # Run scan runner in readonly mode
        env = {**os.environ, "OPENCLAW_NO_PUSH": "1", "V2_OBSERVE_ONLY": "1"}
        r = subprocess.run(["python3", str(SCAN_RUNNER)], capture_output=True, text=True,
                          timeout=120, cwd=str(MODULE), env=env)
        result["scan_runner_rc"] = r.returncode
        result["capture_ran"] = True

        # Re-check for real evidence after runner
        if scout_path.is_file():
            result["production_evidence"] = True
            result["status"] = "PASS"
        else:
            result["status"] = "WARN"
            result["warnings"].append("scan_runner_ran_but_no_scout_output")
    else:
        result["status"] = "BLOCKER"
        result["blockers"].append("scan_runner_missing")
        print(json.dumps(result, ensure_ascii=False))
        return 2

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] in ("PASS","WARN") else 1

if __name__=="__main__": sys.exit(main())
