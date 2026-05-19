#!/usr/bin/env python3
"""V2 DAILY_POOL Readonly Safety Checker"""
import json, subprocess, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
RUNNER = MODULE / "tools" / "v2_daily_pool_readonly_runner.py"

def main():
    R = {"check_status":"PASS","runner_exists":RUNNER.is_file(),"help_ok":False,
         "current_date_ok":False,"replay_ok":False,"json_parse_pass":False,
         "blockers":[],"warnings":[]}
    block = False
    if not RUNNER.is_file(): R["blockers"].append("Runner missing"); block = True; _finish(R,block)

    # Help check
    r = subprocess.run(["python3",str(RUNNER),"--help"],capture_output=True,text=True,timeout=30,cwd=str(MODULE))
    out = r.stdout
    requires = ["--date","--from-date","--to-date","--dry-run","--no-push","--no-state-write",
                "--no-verified-write","--no-cron","--no-supervisor"]
    missing = [a for a in requires if a not in out]
    R["help_ok"] = not missing
    if missing: R["blockers"].append(f"Missing flags: {missing}"); block = True

    # Current date dry-run
    r = subprocess.run(["python3",str(RUNNER),"--date","2026-05-20","--dry-run","--no-push",
        "--no-state-write","--no-verified-write","--no-cron","--no-supervisor",
        "--watchdog-only-failure"],capture_output=True,text=True,timeout=60,cwd=str(MODULE))
    try:
        j = json.loads(r.stdout.strip().split("\n")[0])
        R["current_date_ok"] = True; R["json_parse_pass"] = True
        for f in ["formal_daily_pool_executed","qq_sent","state_written","verified_written",
                  "proof_executed","cron_modified","supervisor_executed"]:
            if j.get(f,True): R["blockers"].append(f"{f} is true"); block = True
    except Exception as e: R["blockers"].append(f"Current date JSON parse: {e}"); block = True

    # Replay 05/17-05/20
    r = subprocess.run(["python3",str(RUNNER),"--from-date","2026-05-17","--to-date","2026-05-20",
        "--dry-run","--no-push","--no-state-write","--no-verified-write","--no-cron",
        "--no-supervisor","--watchdog-only-failure"],capture_output=True,text=True,timeout=60,cwd=str(MODULE))
    try:
        j = json.loads(r.stdout.strip().split("\n")[0])
        R["replay_ok"] = True; R["replay_dates"] = j.get("dates_checked",0)
    except Exception as e: R["blockers"].append(f"Replay JSON parse: {e}"); block = True

    _finish(R,block)

def _finish(R,block):
    if block: R["check_status"] = "BLOCKER"
    elif R["warnings"]: R["check_status"] = "WARN"
    print("="*50); print("V2 DAILY_POOL READONLY SAFETY CHECKER"); print("="*50)
    print(f"Status: {R['check_status']}")
    for k in ["runner_exists","help_ok","current_date_ok","replay_ok","json_parse_pass"]:
        print(f"  {k}: {R[k]}")
    if R["blockers"]:
        print(f"\nBLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]: print(f"  ! {b}")
        sys.exit(1)
    md = MODULE/"data"/"runtime"/"status"; md.mkdir(parents=True,exist_ok=True)
    (md/"v2_daily_pool_readonly_safety_check.json").write_text(json.dumps(R,indent=2,ensure_ascii=False))
    print(f"\nMarker: {md}/v2_daily_pool_readonly_safety_check.json (NOT committed)")
    sys.exit(0)

if __name__=="__main__": main()
