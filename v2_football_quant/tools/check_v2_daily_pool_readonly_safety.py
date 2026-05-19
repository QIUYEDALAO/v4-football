#!/usr/bin/env python3
"""V2 DAILY_POOL Readonly Safety Checker — validates current + historical modes"""
import json, subprocess, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
RUNNER = MODULE / "tools" / "v2_daily_pool_readonly_runner.py"

def main():
    R = {"check_status": "PASS", "runner_exists": RUNNER.is_file(),
         "help_ok": False, "current_mode_ok": False, "historical_mode_ok": False,
         "json_parse_pass": False, "blockers": [], "warnings": []}
    block = False
    if not RUNNER.is_file():
        R["blockers"].append("Runner missing"); _finish(R, True)

    r = subprocess.run(["python3", str(RUNNER), "--help"], capture_output=True, text=True, timeout=30, cwd=str(MODULE))
    out = r.stdout
    requires = ["--date", "--from-date", "--to-date", "--dry-run", "--no-push",
                "--no-state-write", "--no-verified-write", "--no-cron", "--no-supervisor"]
    missing = [a for a in requires if a not in out]
    R["help_ok"] = not missing
    if missing: R["blockers"].append(f"Missing flags: {missing}"); block = True

    # Current mode
    try:
        r = subprocess.run(["python3", str(RUNNER), "--date", "2026-05-20", "--dry-run",
            "--no-push", "--no-state-write", "--no-verified-write", "--no-cron",
            "--no-supervisor", "--watchdog-only-failure"], capture_output=True, text=True, timeout=60, cwd=str(MODULE))
        j = json.loads(r.stdout.strip().split("\n")[0])
        R["json_parse_pass"] = True
        if j.get("evidence_mode") != "CURRENT_WINDOW_CHECKER":
            R["blockers"].append("Current mode missing CURRENT_WINDOW_CHECKER"); block = True
        if j.get("mode") != "READONLY_CURRENT":
            R["blockers"].append(f"Wrong current mode: {j.get('mode')}"); block = True
        for f in ["formal_daily_pool_executed", "qq_sent", "state_written", "verified_written",
                  "proof_executed", "cron_modified", "supervisor_executed"]:
            if j.get(f, True): R["blockers"].append(f"Current: {f}=true"); block = True
        R["current_mode_ok"] = True
    except Exception as e: R["blockers"].append(f"Current parse: {e}"); block = True

    # Historical mode
    try:
        r = subprocess.run(["python3", str(RUNNER), "--from-date", "2026-05-17",
            "--to-date", "2026-05-20", "--dry-run", "--no-push", "--no-state-write",
            "--no-verified-write", "--no-cron", "--no-supervisor", "--watchdog-only-failure"],
            capture_output=True, text=True, timeout=60, cwd=str(MODULE))
        j = json.loads(r.stdout.strip().split("\n")[0])
        if j.get("evidence_mode") != "HISTORICAL_FILE_SCAN":
            R["blockers"].append(f"Historical mode wrong evidence_mode: {j.get('evidence_mode')}"); block = True
        if j.get("mode") != "READONLY_HISTORICAL_EVIDENCE_SCAN":
            R["blockers"].append(f"Wrong historical mode: {j.get('mode')}"); block = True
        if "evidence_paths" not in j:
            R["blockers"].append("Historical: missing evidence_paths"); block = True
        if "missing_daily_pool_dates" not in j:
            R["blockers"].append("Historical: missing missing_daily_pool_dates"); block = True
        # Must NOT have current checker field top-level
        if "window_checker_status" in j and j["window_checker_status"] == "SKIPPED_NO_ACTIVE_WINDOW":
            if j.get("evidence_mode") != "CURRENT_WINDOW_CHECKER":
                R["warnings"].append("Historical has stray SKIPPED_NO_ACTIVE_WINDOW")
        # Check per_date classifications are meaningful
        for dt, v in j.get("per_date", {}).items():
            sc = v.get("status_classification", "")
            if sc == "SKIPPED_NO_ACTIVE_WINDOW" and not v.get("window_evidence_found"):
                R["blockers"].append(f"Historical {dt}: SKIPPED_NO_ACTIVE_WINDOW without evidence"); block = True
        # Guards
        for f in ["formal_daily_pool_executed", "qq_sent", "state_written", "verified_written",
                  "proof_executed", "cron_modified", "supervisor_executed"]:
            if j.get(f, True): R["blockers"].append(f"Historical: {f}=true"); block = True
        R["historical_mode_ok"] = True
        R["historical_missing_dates"] = j.get("missing_daily_pool_dates", [])
    except Exception as e: R["blockers"].append(f"Historical parse: {e}"); block = True

    _finish(R, block)

def _finish(R, block):
    if block: R["check_status"] = "BLOCKER"
    elif R["warnings"]: R["check_status"] = "WARN"
    print("=" * 50)
    print("V2 DAILY_POOL READONLY SAFETY CHECKER")
    print("=" * 50)
    print(f"Status: {R['check_status']}")
    for k in ["runner_exists", "help_ok", "current_mode_ok", "historical_mode_ok", "json_parse_pass"]:
        print(f"  {k}: {R[k]}")
    if R.get("historical_missing_dates"):
        print(f"  historical_missing: {R['historical_missing_dates']}")
    if R["blockers"]:
        print(f"\nBLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]: print(f"  ! {b}")
        sys.exit(1)
    if R["warnings"]:
        print(f"\nWARNINGS ({len(R['warnings'])}):")
        for w in R["warnings"]: print(f"  ~ {w}")
    md = MODULE / "data" / "runtime" / "status"
    md.mkdir(parents=True, exist_ok=True)
    (md / "v2_daily_pool_readonly_safety_check.json").write_text(json.dumps(R, indent=2, ensure_ascii=False))
    print(f"\nMarker written (not committed): {md}/v2_daily_pool_readonly_safety_check.json")
    sys.exit(0)

if __name__ == "__main__":
    main()
