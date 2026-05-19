#!/usr/bin/env python3
"""Intel Desk Checker — validates local dashboard files"""
import json, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]; IDIR = MODULE / "reports" / "intel_desk"

def main():
    R = {"check_status":"PASS","md_exists":False,"json_exists":False,"latest_exists":False,
         "json_parsed":False,"v2_section":False,"v4_section":False,"risk_section":False,
         "guards_ok":False,"blockers":[],"warnings":[]}
    block = False

    for f,key in [("INTEL_DASHBOARD_20260520.md","md_exists"),("INTEL_DASHBOARD_20260520.json","json_exists"),("INTEL_DASHBOARD_LATEST.md","latest_exists")]:
        R[key] = (IDIR/f).is_file()
        if not R[key]: R["blockers"].append(f"Missing: {f}"); block = True

    jf = IDIR / "INTEL_DASHBOARD_20260520.json"
    if jf.is_file():
        try:
            d = json.loads(jf.read_text())
            R["json_parsed"] = True
            R["v2_section"] = d.get("v2") is not None
            R["v4_section"] = "v4_today" in d
            R["risk_section"] = bool(d.get("risk"))
            g = d.get("guards",{})
            R["guards_ok"] = all(not g.get(f,True) for f in ["qq_sent","state_written","verified_written","proof_executed","d13","cron"])
            if not R["v2_section"]: R["blockers"].append("V2 section null/missing"); block = True
            if not R["guards_ok"]: R["blockers"].append("Guard violation in dashboard"); block = True
        except: R["blockers"].append("JSON parse failed"); block = True

    if block: R["check_status"] = "BLOCKER"
    elif R["warnings"]: R["check_status"] = "WARN"
    print("="*50); print("INTEL DESK CHECKER"); print("="*50)
    print(f"Status: {R['check_status']}")
    for k in ["md_exists","json_exists","latest_exists","json_parsed","v2_section","v4_section","risk_section","guards_ok"]: print(f"  {k}: {R[k]}")
    if R["blockers"]: print(f"\nBLOCKERS ({len(R['blockers'])}):"); [print(f"  ! {b}") for b in R["blockers"]]; sys.exit(1)
    print("Dashboard OK.")
sys.exit(main())
