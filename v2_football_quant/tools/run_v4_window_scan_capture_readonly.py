#!/usr/bin/env python3
"""V4 Window Scan Readonly Wrapper — before/after hash, binds evidence to real run"""
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

    if args.preflight:
        print(json.dumps({"status":"PENDING" if now<sched else "DUE","window":args.window,
            "capture_ran":False,"evidence_written":False,"runner_exists":SCAN_RUNNER.is_file(),
            "synthetic_evidence":False}, ensure_ascii=False))
        return 0

    if now < sched:
        print(json.dumps({"status":"WAIT","window":args.window,
            "minutes_to_window":int((sched-now).total_seconds()/60),"capture_ran":False},ensure_ascii=False))
        return 0

    # ── CAPTURE: record before/after hash ──
    runner_started_at = now.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    scout_before_hash = hashlib.md5(scout_path.read_bytes()).hexdigest() if scout_path.is_file() else None
    scout_before_mtime = scout_path.stat().st_mtime if scout_path.is_file() else None

    result = {"window":args.window,"scan_date":args.scan_date,"capture_ran":True,
        "synthetic_evidence":False,"runner_started_at":runner_started_at,
        "scout_before_hash":scout_before_hash,"scout_before_exists":scout_path.is_file(),
        "production_evidence":False,"evidence_source":None,"actual_send":False,"qq_sent":False,
        "A":None,"B":None,"C":None,"SKIP":None,"status":"RUNNING"}

    if SCAN_RUNNER.is_file():
        env = {**os.environ, "OPENCLAW_NO_PUSH":"1","V2_OBSERVE_ONLY":"1","NO_PROXY":"*"}
        r = subprocess.run(["python3",str(SCAN_RUNNER),"--window",args.window],
            capture_output=True,text=True,timeout=300,cwd=str(MODULE),env=env)
        result["runner_rc"] = r.returncode
    else:
        result["runner_rc"] = -1

    runner_finished_at = datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    scout_after_hash = hashlib.md5(scout_path.read_bytes()).hexdigest() if scout_path.is_file() else None
    scout_after_mtime = scout_path.stat().st_mtime if scout_path.is_file() else None
    result["runner_finished_at"] = runner_finished_at
    result["scout_after_hash"] = scout_after_hash
    result["scout_after_exists"] = scout_path.is_file()

    # ── Determine production_evidence ──
    scout_updated = (scout_after_hash is not None and scout_after_hash != scout_before_hash)
    if scout_updated and result.get("runner_rc",-1) == 0:
        result["production_evidence"] = True
        result["evidence_source"] = "real_runner_output"
        result["evidence_bound_to_this_run"] = True
        try:
            scout = json.loads(scout_path.read_text())
            matches = scout if isinstance(scout,list) else scout.get("matches",[])
            grades = {}
            for m in matches:
                g = m.get("grade",m.get("pre_grade",m.get("ht_recommendation","")))
                grades[g] = grades.get(g,0) + 1
            result["A"] = grades.get("A",0); result["B"] = grades.get("B",0)
            result["C"] = grades.get("C",0); result["SKIP"] = grades.get("SKIP",0)+grades.get("HT_SKIP",0)
            result["total"] = sum(grades.values())
            result["formal_recommendation_count"] = result["A"]+result["B"]
            result["future_ab_trigger"] = result["formal_recommendation_count"] > 0
        except:
            result["status"] = "WARN"; result["warnings"] = ["scout_parse_failed"]
    elif scout_after_hash and not scout_updated:
        result["status"] = "WARN"
        result["warnings"] = ["scout_not_updated_by_this_run — old scout cannot be early evidence"]
        result["evidence_source"] = "STALE_SCOUT_NOT_UPDATED"
    elif not scout_after_hash:
        result["status"] = "WARN"
        result["warnings"] = ["no_scout_after_runner"]

    # Write markers
    win_log.parent.mkdir(parents=True, exist_ok=True)
    win_log.write_text(f"V4 {args.window} scan {args.scan_date} | {runner_started_at} | "
        f"before={scout_before_hash[:12] if scout_before_hash else 'NONE'} "
        f"after={scout_after_hash[:12] if scout_after_hash else 'NONE'} | "
        f"updated={scout_updated} | evidence={result['production_evidence']} | synthetic=false\n")

    win_status.parent.mkdir(parents=True, exist_ok=True)
    win_status.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    win_push.parent.mkdir(parents=True, exist_ok=True)
    win_push.write_text(json.dumps({
        "window":args.window,"scan_date":args.scan_date,"shadow_only":True,
        "actual_send":False,"qq_sent":False,"scout_after_hash":scout_after_hash
    }, indent=2))

    result["status"] = "PASS" if result["production_evidence"] else "WARN"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__=="__main__": sys.exit(main())
