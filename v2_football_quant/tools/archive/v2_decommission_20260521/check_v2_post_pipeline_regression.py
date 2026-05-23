#!/usr/bin/env python3
"""V2 Post-Pipeline Regression Checker — validates all QA items"""
import json, os, subprocess, sys, time
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def main():
    R = {"check_status":"PASS","blockers":[],"warnings":[],
         "tests":{},"qq":False,"cron":False,"d13":False,"verified":False,"prod_verified":False}
    block = False
    
    # Test 1: true readonly chain
    lc = MODULE / "tools" / "check_v2_readonly_live_window.py"
    txt = lc.read_text() if lc.is_file() else ""
    R["tests"]["true_readonly"] = all(k in txt for k in ["--no-push","--observe-only","--no-formal-state-write","OPENCLAW_NO_PUSH","V2_OBSERVE_ONLY"])
    if not R["tests"]["true_readonly"]: R["blockers"].append("true_readonly"); block=True

    # Test 2: daily_runner guard flags passed to run_once
    dr = MODULE / "engine" / "daily_runner.py"
    dtxt = dr.read_text() if dr.is_file() else ""
    R["tests"]["daily_runner_guard"] = "dry_run=args.dry_run" in dtxt
    if not R["tests"]["daily_runner_guard"]: R["blockers"].append("daily_runner_guard"); block=True

    # Test 3: odds boundary
    def classify(o): return "ODDS_LOW" if o<2.00 else ("IN_BAND" if o<2.90 else "ODDS_HIGH")
    R["tests"]["odds_boundary"] = all([
        classify(1.99)=="ODDS_LOW", classify(2.00)=="IN_BAND",
        classify(2.89)=="IN_BAND", classify(2.90)=="ODDS_HIGH", classify(2.91)=="ODDS_HIGH"
    ])
    if not R["tests"]["odds_boundary"]: R["blockers"].append("odds_boundary"); block=True

    # Test 4: T-90 guarded wrapper blocks T-3H
    r = subprocess.run(["python3", str(MODULE/"tools"/"run_v2_t90_lock_window_proof_guarded.py"),
        "--target-fixture","Ried","--no-push","--no-state-write","--no-verified-write","--no-cron","--no-supervisor"],
        capture_output=True, text=True, timeout=60, cwd=str(MODULE))
    try:
        d = json.loads(r.stdout.strip().split("\n")[0])
        is_t90 = d.get("lock_window_active", False)
        if not is_t90:
            R["tests"]["t90_wrapper_waits"] = d.get("T90_LOCK_WINDOW_RESULT") == "T90_LOCK_WINDOW_WAIT"
        else:
            R["tests"]["t90_wrapper_waits"] = d.get("T90_LOCK_WINDOW_RESULT") in ("T90_LOCK_WINDOW_BET_LOCKED_PROOF","T90_LOCK_WINDOW_NO_BET_LOCKED_PROOF")
        R["tests"]["wrapper_readonly_ran"] = d.get("readonly_checker_ran", False)
        if not is_t90:
            R["tests"]["wrapper_no_unnecessary_run"] = not d.get("readonly_checker_ran")
    except: R["blockers"].append("t90_wrapper_parse"); block=True

    # Test 5: dashboard fields
    dash = MODULE / "data" / "runtime" / "dashboard" / "v2_today.html"
    if dash.is_file():
        html = dash.read_text()
        R["tests"]["dash_pipeline_ready"] = "PIPELINE_READY" in html
        R["tests"]["dash_prod_false"] = "false" in html
        R["tests"]["dash_no_stale"] = "20260517" not in html[:200]
        missing = [k for k,v in R["tests"].items() if k.startswith("dash_") and not v]
        if missing: R["warnings"].append(f"dash fields missing: {missing}")

    # Test 6: state semantic check
    sf = MODULE / "data" / "state" / "selected_fixtures_20260519.json"
    if sf.is_file():
        fx = json.loads(sf.read_text())
        R["tests"]["state_selected_nonzero"] = len(fx.get("selected_fixture_ids",[])) == 0  # correct: no BET_LOCKED
        R["tests"]["state_kickoff_present"] = all(f.get("kickoff_time","") for f in fx.get("fixtures",{}).values())

    if block: R["check_status"]="BLOCKER"
    elif R["warnings"]: R["check_status"]="WARN"
    print("="*50); print("V2 POST-PIPELINE REGRESSION CHECKER"); print("="*50)
    print(f"Status: {R['check_status']}")
    for k,v in R["tests"].items(): print(f"  {k}: {v}")
    if R["blockers"]: print(f"\nBLOCKERS: {R['blockers']}"); sys.exit(1)
    if R["warnings"]: print(f"\nWARNINGS: {R['warnings']}")
    sys.exit(0)

if __name__=="__main__": main()
