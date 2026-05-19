#!/usr/bin/env python3
"""V2 DAILY_POOL Readonly Runner — safe no-push/no-state/no-verified harness"""
import argparse, json, re, subprocess, sys, time
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--review-only", action="store_true")
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--no-state-write", action="store_true")
    parser.add_argument("--no-verified-write", action="store_true")
    parser.add_argument("--no-cron", action="store_true")
    parser.add_argument("--no-supervisor", action="store_true")
    parser.add_argument("--watchdog-only-failure", action="store_true")
    parser.add_argument("--preserve-logs", action="store_true")
    args = parser.parse_args()

    result = {
        "date": args.date, "mode": "READONLY",
        "daily_pool_executed": False, "readonly_check_executed": True,
        "dry_run": args.dry_run or args.review_only,
        "review_only": args.review_only,
        "no_push": args.no_push, "no_state_write": args.no_state_write,
        "no_verified_write": args.no_verified_write,
        "no_cron": args.no_cron, "no_supervisor": args.no_supervisor,
        "BET_LOCKED_count": 0, "WATCH_EARLY_count": 0,
        "CANDIDATE_count": 0, "HT_SKIP_count": 0,
        "qq_sent": False, "state_written": False, "verified_written": False,
        "proof_executed": False, "cron_modified": False, "supervisor_executed": False,
        "formal_recommendation": "NONE (readonly mode)",
    }

    MODULE = Path(__file__).resolve().parents[1]
    chk = MODULE / "engine" / "v2_window_checker_with_watchdog.py"
    if chk.is_file():
        r = subprocess.run(["python3", str(chk)], capture_output=True, text=True, timeout=60, cwd=str(MODULE))
        out = r.stdout
        result["window_checker_returncode"] = r.returncode
        if "SKIPPED" in out:
            result["window_checker_status"] = "SKIPPED_NO_ACTIVE_WINDOW"
        m = re.search(r"BET_LOCKED[：:]\s*(\d+)", out)
        if m: result["BET_LOCKED_count"] = int(m.group(1))
        m = re.search(r"WATCH_EARLY[：:]\s*(\d+)", out)
        if m: result["WATCH_EARLY_count"] = int(m.group(1))

    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\n[INFO] Readonly check complete. No formal DAILY_POOL run.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
