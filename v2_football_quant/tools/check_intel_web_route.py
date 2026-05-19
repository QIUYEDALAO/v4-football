#!/usr/bin/env python3
"""Intel Web Route Checker — validates web dashboard health"""
import json, os, subprocess, sys, time
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
DASH_DIR = MODULE / "data" / "runtime" / "dashboard"

def main():
    R = {"check_status":"PASS","server_running":False,"v2_today_exists":False,
         "index_exists":False,"latest_html_exists":False,"no_cache":False,
         "generated_at_ok":False,"v2_current_ok":False,"v2_historical_ok":False,
         "v4_today_ok":False,"guards_ok":False,"stale_0517_clean":False,
         "blockers":[],"warnings":[]}
    block = False

    # Server check
    r = subprocess.run(["lsof","-iTCP:8765","-sTCP:LISTEN","-n","-P"],capture_output=True,text=True,timeout=5)
    R["server_running"] = "LISTEN" in r.stdout

    for f, key in [("v2_today.html","v2_today_exists"),("index.html","index_exists")]:
        R[key] = (DASH_DIR/f).is_file()
        if not R[key]: R["blockers"].append(f"Missing: {f}"); block = True

    # Latest HTML
    latest = MODULE / "reports" / "intel_desk" / "INTEL_DASHBOARD_LATEST.html"
    R["latest_html_exists"] = latest.is_file()

    # Check v2_today content
    v2f = DASH_DIR / "v2_today.html"
    if v2f.is_file():
        html = v2f.read_text()
        R["no_cache"] = "no-cache" in html and "no-store" in html
        R["generated_at_ok"] = "生成" in html
        R["v2_current_ok"] = "BET_LOCKED" in html and "SKIPPED" in html
        R["v2_historical_ok"] = "DAILY_POOL" in html
        R["v4_today_ok"] = "observation-only" in html and "not recommendation" in html
        R["guards_ok"] = "qq_sent" in html and "false" in html
        # Check no stale 05/17 as today's date
        import re
        stale = re.findall(r'日期[：:]\s*20260517|生成时间[：:].*2026-05-18', html)
        R["stale_0517_clean"] = len(stale) == 0
        if not R["stale_0517_clean"]: R["blockers"].append("Stale 05/17 as current date!"); block = True

    if block: R["check_status"]="BLOCKER"
    elif R["warnings"]: R["check_status"]="WARN"
    print("="*50); print("INTEL WEB ROUTE CHECKER"); print("="*50)
    print(f"Status: {R['check_status']}")
    for k in ["server_running","v2_today_exists","index_exists","latest_html_exists","no_cache",
              "generated_at_ok","v2_current_ok","v2_historical_ok","v4_today_ok","guards_ok","stale_0517_clean"]:
        print(f"  {k}: {R[k]}")
    if R["blockers"]: print(f"\nBLOCKERS: {R['blockers']}"); sys.exit(1)
    if R["warnings"]: print(f"\nWARNINGS: {R['warnings']}")
    sys.exit(0)

if __name__=="__main__": main()
