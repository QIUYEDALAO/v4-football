#!/usr/bin/env python3
"""V2 Readonly Live Window Checker — READY_WAIT when no active window"""
import json, subprocess, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def main():
    import argparse
    p = argparse.ArgumentParser()
    for f in ["no-push","no-state-write","no-verified-write","no-cron","no-supervisor"]:
        p.add_argument(f"--{f}", action="store_true")
    args = p.parse_args()

    R = {"check_status":"PASS","active_window":False,"readonly_runner_result":None,
         "status":"READY_WAIT_ACTIVE_WINDOW","blockers":[],"warnings":[]}
    block = False

    # Run window checker to see if active window exists
    win_chk = MODULE / "engine" / "v2_window_checker_with_watchdog.py"
    if win_chk.is_file():
        env = {**__import__('os').environ, "OPENCLAW_NO_PUSH": "1", "V2_OBSERVE_ONLY": "1"}
        r = subprocess.run(["python3", str(win_chk), "--no-push", "--observe-only", "--no-formal-state-write", "--no-verified-write"],
                          capture_output=True, text=True, timeout=60, cwd=str(MODULE), env=env)
        out = r.stdout
        if "SKIPPED" not in out and "NO_ACTIVE" not in out:
            R["active_window"] = True

    if R["active_window"]:
        # Run readonly runner with full safety
        runner = MODULE / "tools" / "v2_daily_pool_readonly_runner.py"
        r = subprocess.run(["python3", str(runner), "--dry-run", "--no-push", "--no-state-write",
            "--no-verified-write", "--no-cron", "--no-supervisor", "--watchdog-only-failure"],
            capture_output=True, text=True, timeout=90, cwd=str(MODULE))
        try:
            j = json.loads(r.stdout.strip().split("\n")[0])
            R["readonly_runner_result"] = j
            R["status"] = "ACTIVE_WINDOW_CHECKED"
        except: R["warnings"].append("readonly runner parse failed")
    else:
        R["status"] = "READY_WAIT_ACTIVE_WINDOW"
        R["warnings"].append("No active window — waiting for next window")

    # Guard checks
    if R.get("readonly_runner_result", {}):
        for f in ["qq_sent","state_written","verified_written","proof_executed"]:
            if R["readonly_runner_result"].get(f, True):
                R["blockers"].append(f"Runner: {f}=true"); block = True

    if block: R["check_status"]="BLOCKER"
    print("="*50); print("V2 READONLY LIVE WINDOW CHECKER"); print("="*50)
    print(f"Status: {R['check_status']} | Window: {R['status']} | Active: {R['active_window']}")
    if R.get("readonly_runner_result"):
        j = R["readonly_runner_result"]
        print(f"BL: {j.get('BET_LOCKED_count',0)} | qq: {j.get('qq_sent')} | state: {j.get('state_written')}")
    if R["blockers"]: print(f"\nBLOCKERS: {R['blockers']}"); sys.exit(1)
    if R["warnings"]: print(f"\nWARNINGS: {R['warnings']}")
    md = MODULE/"data"/"runtime"/"status"; md.mkdir(parents=True,exist_ok=True)
    (md/"v2_readonly_live_window_check.json").write_text(json.dumps(R,indent=2,ensure_ascii=False))
    sys.exit(0)

if __name__=="__main__": main()
