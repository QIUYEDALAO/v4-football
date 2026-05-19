#!/usr/bin/env python3
"""V4 Window Scan Capture Readonly Wrapper — runs real scanner, writes window-specific marker"""
import argparse, json, hashlib, os, subprocess, sys, time
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

    scout_path = MODULE / f"data/daily_reports/scout_v4_{args.scan_date}.json"
    win_log = MODULE / f"data/runtime/logs/v4_scan_{args.window}_{args.scan_date}.log"
    win_status = MODULE / f"data/runtime/status/v4_scan_{args.window}_window_capture_after_due_{args.scan_date}.json"
    win_push = MODULE / f"data/runtime/status/v4_scan_{args.window}_push_{args.scan_date}.json"

    # Preflight only
    if args.preflight:
        print(json.dumps({
            "status": "PENDING" if now < sched else "DUE",
            "window": args.window, "scan_date": args.scan_date,
            "capture_ran": False, "runner_exists": SCAN_RUNNER.is_file(),
            "paths_ready": True, "synthetic_evidence": False
        }, ensure_ascii=False))
        return 0

    # Not due → WAIT
    if now < sched:
        print(json.dumps({
            "status": "WAIT", "window": args.window,
            "minutes_to_window": int((sched-now).total_seconds()/60),
            "capture_ran": False
        }, ensure_ascii=False))
        return 0

    # Run real scanner
    result = {"window": args.window, "scan_date": args.scan_date,
              "captured_at": now.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
              "capture_ran": True, "synthetic_evidence": False,
              "production_evidence": False, "actual_send": False, "qq_sent": False,
              "A": None, "B": None, "C": None, "SKIP": None, "status": "RUNNING"}

    if SCAN_RUNNER.is_file():
        env = {**os.environ, "OPENCLAW_NO_PUSH": "1", "V2_OBSERVE_ONLY": "1"}
        r = subprocess.run(["python3", str(SCAN_RUNNER)], capture_output=True, text=True,
                          timeout=120, cwd=str(MODULE), env=env)
        result["runner_rc"] = r.returncode

    # Read real scout output
    if scout_path.is_file():
        scout_hash = hashlib.md5(scout_path.read_bytes()).hexdigest()
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
            result["production_evidence"] = True
        except:
            result["status"] = "WARN"
            result["warnings"] = ["scout_parse_failed"]

    # Write window-specific markers (referencing real scout hash, NOT synthetic)
    win_log.parent.mkdir(parents=True, exist_ok=True)
    win_log.write_text(f"V4 {args.window} scan {args.scan_date} | captured={result['captured_at']} | "
                       f"scout_hash={scout_hash if scout_path.is_file() else 'NONE'} | "
                       f"production_evidence={result['production_evidence']} | synthetic=false\n")

    win_status.parent.mkdir(parents=True, exist_ok=True)
    win_status.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    win_push.parent.mkdir(parents=True, exist_ok=True)
    win_push.write_text(json.dumps({
        "window": args.window, "scan_date": args.scan_date,
        "actual_send": False, "qq_sent": False, "shadow_only": True,
        "scout_hash": scout_hash if scout_path.is_file() else None
    }, indent=2, ensure_ascii=False))

    result["status"] = "PASS" if result["production_evidence"] else "WARN"
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__=="__main__": sys.exit(main())
