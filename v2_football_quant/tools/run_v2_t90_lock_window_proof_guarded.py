#!/usr/bin/env python3
"""T-90 Lock Window Proof — guarded wrapper, blocks non-T-90/T-45 runs"""
import json, subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--target-fixture", default="Ried")
    p.add_argument("--no-push", action="store_true", default=True)
    p.add_argument("--no-state-write", action="store_true", default=True)
    p.add_argument("--no-verified-write", action="store_true", default=True)
    p.add_argument("--no-cron", action="store_true", default=True)
    p.add_argument("--no-supervisor", action="store_true", default=True)
    args = p.parse_args()

    result = {"status": "RUNNING", "target": args.target_fixture, "T90_LOCK_WINDOW_RESULT": "PENDING",
              "qq_sent": False, "state_written": False, "verified_written": False,
              "proof_executed": False, "readonly_checker_ran": False}

    # Check stage
    now = datetime.now(); tz_cn = timezone(timedelta(hours=8))
    scan = MODULE / "data" / "daily_reports" / "full_scan_20260519.json"
    if not scan.is_file():
        result["status"] = "BLOCKED"; result["blocker_reason"] = "full_scan missing"
        print(json.dumps(result, ensure_ascii=False)); return 1

    data = json.loads(scan.read_text())
    target_data = None
    for c in data.get("candidates", []):
        if args.target_fixture.lower() in c.get("home","").lower():
            target_data = c; break

    if not target_data:
        result["status"] = "BLOCKED"; result["blocker_reason"] = "target fixture not found"
        print(json.dumps(result, ensure_ascii=False)); return 1

    mins = target_data.get("minutes_to_kickoff", 9999)
    scan_dt = datetime.fromisoformat(target_data.get("scan_time_local", "2026-05-19T21:18:00"))
    elapsed = (now - scan_dt).total_seconds() / 60
    remaining = mins - elapsed
    ko_dt = now + timedelta(minutes=remaining)

    result["kickoff_cst"] = ko_dt.astimezone(tz_cn).strftime("%Y-%m-%d %H:%M")
    result["minutes_to_ko"] = int(remaining)

    if remaining > 90:
        result["stage"] = "T_MINUS_3H" if remaining <= 180 else "PRE_T90"
        result["status"] = "WAIT"
        result["T90_LOCK_WINDOW_RESULT"] = "T90_LOCK_WINDOW_WAIT"
        result["reason"] = f"T-90 lock window not yet active ({int(remaining-90)}min to T-90)"
        print(json.dumps(result, ensure_ascii=False))
        print(f"\n[WAIT] T-90 window not active. stage={result['stage']} remaining={int(remaining)}min.", file=sys.stderr)
        return 0

    # T-90 or T-45 is active — run readonly proof
    result["stage"] = "T_MINUS_90M" if remaining > 45 else "T_MINUS_45M" if remaining > 15 else "T_MINUS_15M"
    result["lock_window_active"] = True
    result["status"] = "ACTIVE"

    lc = MODULE / "tools" / "check_v2_readonly_live_window.py"
    env = {"OPENCLAW_NO_PUSH": "1", "V2_OBSERVE_ONLY": "1", "PATH": __import__('os').environ.get("PATH","")}
    r = subprocess.run(["python3", str(lc), "--no-push", "--no-state-write", "--no-verified-write",
        "--no-cron", "--no-supervisor"], capture_output=True, text=True, timeout=120, cwd=str(MODULE), env=env)
    result["readonly_checker_ran"] = True
    result["readonly_checker_rc"] = r.returncode

    # Parse window status
    wl = MODULE / "data" / "runtime" / "status" / "v2_window_latest.json"
    if wl.is_file():
        wd = json.loads(wl.read_text())
        result["window_status"] = wd.get("status")
        result["BET_LOCKED_count"] = wd.get("locked_total", 0)
        result["window_summary"] = wd.get("window_summary", {})

    if result.get("BET_LOCKED_count", 0) > 0:
        result["T90_LOCK_WINDOW_RESULT"] = "T90_LOCK_WINDOW_BET_LOCKED_PROOF"
    else:
        result["T90_LOCK_WINDOW_RESULT"] = "T90_LOCK_WINDOW_NO_BET_LOCKED_PROOF"

    result["status"] = "DONE"
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
