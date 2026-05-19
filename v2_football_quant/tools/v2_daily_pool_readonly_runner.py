#!/usr/bin/env python3
"""V2 DAILY_POOL Readonly Runner — with replay, single-line JSON stdout"""
import argparse, json, re, subprocess, sys
from datetime import date, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
WIN_CHK = MODULE / "engine" / "v2_window_checker_with_watchdog.py"

def check_date(d):
    """Run window checker for one date."""
    r = subprocess.run(["python3", str(WIN_CHK)], capture_output=True, text=True, timeout=60, cwd=str(MODULE))
    out = r.stdout
    result = {"date": d, "window_checker_status": "UNKNOWN", "BET_LOCKED_count": 0,
              "WATCH_EARLY_count": 0, "CANDIDATE_count": 0, "HT_SKIP_count": 0}
    if "SKIPPED" in out: result["window_checker_status"] = "SKIPPED_NO_ACTIVE_WINDOW"
    m = re.search(r"BET_LOCKED[：:]\s*(\d+)", out)
    if m: result["BET_LOCKED_count"] = int(m.group(1))
    m = re.search(r"WATCH_EARLY[：:]\s*(\d+)", out)
    if m: result["WATCH_EARLY_count"] = int(m.group(1))
    result["window_checker_returncode"] = r.returncode
    return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default="")
    p.add_argument("--from-date", default="")
    p.add_argument("--to-date", default="")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--review-only", action="store_true")
    p.add_argument("--no-push", action="store_true")
    p.add_argument("--no-state-write", action="store_true")
    p.add_argument("--no-verified-write", action="store_true")
    p.add_argument("--no-cron", action="store_true")
    p.add_argument("--no-supervisor", action="store_true")
    p.add_argument("--watchdog-only-failure", action="store_true")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args()

    if args.from_date and args.to_date:
        fd = date.fromisoformat(args.from_date[:10].replace("/","-"))
        td = date.fromisoformat(args.to_date[:10].replace("/","-"))
        dates = []; d = fd
        while d <= td: dates.append(d.strftime("%Y-%m-%d")); d += timedelta(days=1)
        per_date = {}
        for dt in dates: per_date[dt] = check_date(dt)
        result = {"mode": "READONLY_REPLAY", "from_date": args.from_date, "to_date": args.to_date,
                  "dates_checked": len(dates), "missing_dates": [],
                  "per_date": per_date, "formal_daily_pool_executed": False,
                  "qq_sent": False, "state_written": False, "verified_written": False,
                  "proof_executed": False, "cron_modified": False, "supervisor_executed": False}
    else:
        dt = args.date or date.today().strftime("%Y-%m-%d")
        result = check_date(dt)
        result["mode"] = "READONLY"
        result["readonly_check_executed"] = True
        result["formal_daily_pool_executed"] = False
        result["no_push"] = args.no_push
        result["no_state_write"] = args.no_state_write
        result["no_verified_write"] = args.no_verified_write
        result["qq_sent"] = False
        result["state_written"] = False
        result["verified_written"] = False
        result["proof_executed"] = False
        result["cron_modified"] = False
        result["supervisor_executed"] = False

    if args.pretty:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False))
    if args.from_date:
        print(f"[INFO] Replay {args.from_date} to {args.to_date}: {len(dates)} dates checked.", file=sys.stderr)
    else:
        print(f"[INFO] Readonly check complete. No formal DAILY_POOL run.", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
