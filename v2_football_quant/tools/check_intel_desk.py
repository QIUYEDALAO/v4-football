#!/usr/bin/env python3
"""Intel Desk Checker — dynamic date, validates latest dashboard"""
import argparse, json, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
IDIR = MODULE / "reports" / "intel_desk"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="")
    args = ap.parse_args()

    R = {"check_status":"PASS","md_exists":False,"json_exists":False,
         "latest_exists":False,"json_parsed":False,"v2_current_ok":False,
         "v2_historical_ok":False,"v4_section":False,"risk_section":False,
         "actions_section":False,"c_observation_text":False,
         "skip_not_recommendation_text":False,"guards_ok":False,
         "blockers":[],"warnings":[]}
    block = False

    if args.date:
        mdf = IDIR / f"INTEL_DASHBOARD_{args.date}.md"
        jf = IDIR / f"INTEL_DASHBOARD_{args.date}.json"
    else:
        # Use latest
        jf = IDIR / "INTEL_DASHBOARD_20260520.json"
        mdf = IDIR / "INTEL_DASHBOARD_20260520.md"
        # Try to find latest by reading LATEST.md metadata
        if not jf.is_file():
            # scan for most recent
            jsons = sorted(IDIR.glob("INTEL_DASHBOARD_20*.json"), reverse=True)
            if jsons: jf = jsons[0]; mdf = IDIR / jf.name.replace(".json", ".md")

    lf = IDIR / "INTEL_DASHBOARD_LATEST.md"
    R["md_exists"] = mdf.is_file()
    R["json_exists"] = jf.is_file()
    R["latest_exists"] = lf.is_file()
    for key, name in [("md_exists", str(mdf)), ("json_exists", str(jf)), ("latest_exists", "LATEST.md")]:
        if not R[key]: R["blockers"].append(f"Missing: {name}"); block = True

    if jf.is_file():
        try:
            d = json.loads(jf.read_text())
            R["json_parsed"] = True
            R["dashboard_version"] = d.get("dashboard_version", "?")
            R["source_freshness"] = d.get("source_freshness", "?")
            R["attribution_dates"] = d.get("attribution_dates", [])

            R["v2_current_ok"] = d.get("v2_current") is not None
            R["v2_historical_ok"] = d.get("v2_historical") is not None
            if not R["v2_current_ok"]: R["warnings"].append("v2_current null")
            if not R["v2_historical_ok"]: R["blockers"].append("v2_historical missing"); block = True

            v4t = d.get("v4_today", {})
            R["v4_section"] = bool(v4t)
            R["v4_source_mode"] = v4t.get("source_mode", "MISSING")
            if v4t.get("hardcoded", True):
                R["blockers"].append("v4_today.hardcoded=true!"); block = True
            if R["v4_source_mode"] == "SOURCE_MISSING":
                # Must NOT have old grade counts when source missing
                for k in ["total_matches", "A_count", "B_count", "C_count", "SKIP_count"]:
                    if v4t.get(k) is not None and v4t.get(k) != 0:
                        R["blockers"].append(f"v4_today.{k}={v4t[k]} but source_missing"); block = True
            c_note = v4t.get("C_note", "")
            s_note = v4t.get("SKIP_note", "")
            R["c_observation_text"] = "observation-only" in c_note.lower() or "观察" in c_note
            R["skip_not_recommendation_text"] = "not recommendation" in s_note.lower() or "非推荐" in s_note
            if not R["c_observation_text"]: R["warnings"].append("C observation-only missing")
            if not R["skip_not_recommendation_text"]: R["warnings"].append("SKIP not-recommendation missing")

            R["risk_section"] = bool(d.get("risk"))
            R["actions_section"] = bool(d.get("actions"))
            if not R["actions_section"]: R["warnings"].append("actions section missing")

            g = d.get("guards", {})
            R["guards_ok"] = all(not g.get(f, True) for f in
                ["qq_sent", "state_written", "verified_written", "proof_executed", "d13", "cron"])
            if not R["guards_ok"]: R["blockers"].append("Guard violation"); block = True
        except Exception as e: R["blockers"].append(f"JSON: {e}"); block = True

    if block: R["check_status"] = "BLOCKER"
    elif R["warnings"]: R["check_status"] = "WARN"
    print("="*50); print("INTEL DESK CHECKER"); print("="*50)
    print(f"Status: {R['check_status']}  |  v: {R.get('dashboard_version','?')}  |  attr: {R.get('attribution_dates',[])}")
    for k in ["md_exists","json_exists","latest_exists","json_parsed","v2_current_ok",
              "v2_historical_ok","v4_section","risk_section","actions_section",
              "c_observation_text","skip_not_recommendation_text","guards_ok"]:
        print(f"  {k}: {R[k]}")
    if R["blockers"]:
        print(f"\nBLOCKERS ({len(R['blockers'])}):");
        for b in R["blockers"]: print(f"  ! {b}")
        sys.exit(1)
    if R["warnings"]:
        print(f"\nWARNINGS ({len(R['warnings'])}):")
        for w in R["warnings"]: print(f"  ~ {w}")
    sys.exit(0)

if __name__=="__main__": main()
